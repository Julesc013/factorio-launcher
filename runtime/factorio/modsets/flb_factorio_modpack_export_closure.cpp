// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_modpack_export_closure.h"

#include "fl_archive_platform.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_transaction.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdlib>
#include <set>
#include <thread>

namespace facman::factorio::content {
namespace json = facman::core::json;
namespace {
constexpr std::size_t kMaximumRecordBytes = 16U * 1024U * 1024U;

template <typename T>
facman::core::Result<T> failure(
    const std::string& code,
    const std::string& message,
    const std::string& path = {})
{
    return facman::core::Result<T>::failure(
        {code, message, path, facman::core::OutcomeKind::invalid_argument});
}

std::string sha256_text(const std::string& value)
{
    return facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(value.data()), value.size());
}

facman::core::Result<ModpackSourceFile> capture_source_file(
    const facman::platform::StableDirectoryObject& directory,
    const std::string& leaf, const std::string& archive_path, bool allow_absent,
    std::uint64_t maximum_size = 16ULL * 1024ULL * 1024ULL * 1024ULL)
{
    ModpackSourceFile file;
    file.archive_path = archive_path;
    file.source_path = directory.path() / facman::platform::path_from_utf8(leaf);
    auto checked = directory.validate_descendant(file.source_path, allow_absent);
    facman::platform::PathIdentity path_identity;
    if (checked.ok()) checked = facman::platform::inspect_path_no_follow(file.source_path, path_identity);
    if (!checked.ok() || path_identity.reparse_or_link ||
        (path_identity.exists && path_identity.kind != facman::platform::PathObjectKind::regular_file) ||
        (!path_identity.exists && !allow_absent)) {
        return failure<ModpackSourceFile>("modset_verification_failed",
            checked.ok() ? "Export source is not a plain file or admitted absence" : checked.detail, archive_path);
    }
    if (!path_identity.exists) {
        if (!directory.revalidate().ok()) return failure<ModpackSourceFile>(
            "modset_verification_failed", "Export source directory changed", archive_path);
        return facman::core::Result<ModpackSourceFile>::success(std::move(file));
    }
    facman::platform::StableInputFile input;
    checked = directory.open_child_file_no_follow_pinned(facman::platform::path_from_utf8(leaf), input);
    if (!checked.ok() || !input.identity().regular_file || input.identity().link_count != 1U) {
        return failure<ModpackSourceFile>("modset_verification_failed",
            checked.ok() ? "Export source must be a singly linked plain file" : checked.detail, archive_path);
    }
    if (input.size() > maximum_size) return failure<ModpackSourceFile>(
        "modset_verification_failed", "Export source size exceeds its expected bound", archive_path);
    const bool settings_or_lock = archive_path == "modset-lock.v1.json" ||
        archive_path == "mods/mod-list.json" || archive_path == "mods/mod-settings.dat" ||
        archive_path == ".facman-archive-staging.v1";
    if (settings_or_lock && input.size() > kMaximumRecordBytes) return failure<ModpackSourceFile>(
        "modset_verification_failed", "Export settings or lock exceed the 16 MiB bound", archive_path);
    facman::base::Sha256Hasher digest;
    std::array<unsigned char, 65536> block {};
    for (std::uint64_t offset = 0; offset < input.size();) {
        const auto count = static_cast<std::size_t>(std::min<std::uint64_t>(block.size(), input.size() - offset));
        if (input.read_at(offset, block.data(), count) != count) return failure<ModpackSourceFile>(
            "modset_verification_failed", "Export source changed during identity capture", archive_path);
        digest.update(block.data(), count);
        offset += count;
    }
    if (!input.revalidate_path().ok() || !directory.revalidate().ok()) return failure<ModpackSourceFile>(
        "modset_verification_failed", "Export source path changed during identity capture", archive_path);
    file.present = true;
    file.blob = {digest.finish(), input.size()};
    file.identity = input.identity();
    return facman::core::Result<ModpackSourceFile>::success(std::move(file));
}

} // namespace

facman::core::Result<ModpackExportSource> capture_modpack_export_source(
    const std::filesystem::path& instance_root, const std::string& exact_lock_json)
{
    auto lock = content_lock_from_modset_lock_json(exact_lock_json);
    if (!lock) return failure<ModpackExportSource>(lock.error().code, lock.error().message, lock.error().path);
    std::string link_detail;
    if (facman::base::path_crosses_link_or_reparse_point(instance_root, link_detail)) {
        return failure<ModpackExportSource>("modset_verification_failed", link_detail);
    }
    ModpackExportSource output;
    auto checked = output.instance_directory.open_no_follow(instance_root);
    if (checked.ok()) checked = output.instance_directory.open_child_directory_no_follow("mods", output.mods_directory);
    if (!checked.ok()) return failure<ModpackExportSource>("modset_verification_failed", checked.detail);
    auto raw_lock = capture_source_file(output.mods_directory, "modset-lock.v1.json", "modset-lock.v1.json", false);
    if (!raw_lock || raw_lock.value().blob.sha256 != lock.value().source_lock_sha256) {
        return failure<ModpackExportSource>("modset_verification_failed", "Exact source lock changed before export");
    }
    const BlobIdentity source_lock = raw_lock.value().blob;
    output.files.push_back(raw_lock.take_value());
    std::vector<BlobIdentity> blobs;
    for (const ContentLockEntry& entry : lock.value().entries) {
        if (entry.virtual_package) continue;
        auto file = capture_source_file(output.mods_directory, entry.file_name, "mods/" + entry.file_name, false);
        if (!file || file.value().blob.sha256 != entry.sha256) return failure<ModpackExportSource>(
            "modset_verification_failed", "Selected artifact changed before export", entry.file_name);
        blobs.push_back(file.value().blob);
        output.files.push_back(file.take_value());
    }
    auto manifest = modpack_manifest_from_content_lock(lock.value().instance_id, lock.value(), blobs);
    if (!manifest) return failure<ModpackExportSource>(manifest.error().code, manifest.error().message);
    output.manifest = manifest.take_value();
    output.manifest.source_lock = source_lock;
    for (const char* leaf : {"mod-list.json", "mod-settings.dat"}) {
        auto file = capture_source_file(output.mods_directory, leaf, std::string("mods/") + leaf, true);
        if (!file) return failure<ModpackExportSource>(file.error().code, file.error().message, file.error().path);
        output.manifest.settings.push_back({file.value().archive_path, file.value().present, file.value().blob});
        if (std::string(leaf) == "mod-settings.dat") {
            auto& content_lock = output.manifest.content_lock;
            if (!content_lock.startup_settings_sha256.empty() &&
                content_lock.startup_settings_sha256 != file.value().blob.sha256) return failure<ModpackExportSource>(
                    "modset_verification_failed", "Startup settings differ from their source lock binding", leaf);
            content_lock.startup_settings_state = file.value().present ? "sha256_bound" : "absent";
            content_lock.startup_settings_sha256 = file.value().blob.sha256;
        }
        output.files.push_back(file.take_value());
    }
    return facman::core::Result<ModpackExportSource>::success(std::move(output));
}

facman::platform::IoStatus revalidate_modpack_export_source(const ModpackExportSource& source)
{
    std::string link_detail;
    if (facman::base::path_crosses_link_or_reparse_point(source.mods_directory.path(), link_detail) ||
        !source.instance_directory.revalidate().ok() || !source.mods_directory.revalidate().ok()) {
        return facman::platform::IoStatus::failure("modset_verification_failed", "Export instance or mods directory changed");
    }
    for (const ModpackSourceFile& file : source.files) {
        auto current = capture_source_file(source.mods_directory,
            facman::platform::path_to_utf8(file.source_path.filename()), file.archive_path, !file.present);
        if (!current || current.value().present != file.present ||
            current.value().blob.sha256 != file.blob.sha256 || current.value().blob.size != file.blob.size ||
            (file.present && !current.value().identity.unchanged(file.identity))) {
            return facman::platform::IoStatus::failure("modset_verification_failed",
                "Export source presence, identity or bytes changed: " + file.archive_path);
        }
    }
    return facman::platform::IoStatus::success();
}

facman::platform::IoStatus bind_modpack_export_staging_text(
    ModpackExportStaging& state, const std::string& leaf, const std::string& expected_text)
{
    auto file = capture_source_file(state.directory, leaf, leaf, false, expected_text.size());
    if (!file || file.value().blob.sha256 != sha256_text(expected_text) || file.value().blob.size != expected_text.size()) {
        return facman::platform::IoStatus::failure("modpack_staging_verification_failed", "Staging text changed: " + leaf);
    }
    state.owned_files.push_back(file.take_value());
    return facman::platform::IoStatus::success();
}

namespace {
facman::platform::IoStatus write_owned_staging_text(
    ModpackExportStaging& state, const std::string& leaf, const std::string& text)
{
    facman::platform::DurableOutputFile file;
    auto checked = state.directory.create_child_file_exclusive(leaf, text.size(), file);
    if (!checked.ok()) return checked;
    ModpackSourceFile expected;
    expected.archive_path = leaf;
    expected.source_path = state.directory.path() / leaf;
    expected.present = true;
    expected.blob = {sha256_text(text), static_cast<std::uint64_t>(text.size())};
    expected.identity = file.identity();
    expected.identity.size = text.size();
    state.owned_files.push_back(std::move(expected));
    if (file.write_at(0U, text.data(), text.size()) != text.size())
        return facman::platform::IoStatus::failure("modpack_manifest_staging_failed", "Owned staging text short write");
    return file.flush_file_and_parent();
}
} // namespace

facman::platform::IoStatus prepare_modpack_export_staging(
    const std::filesystem::path& staging, const std::string& manifest_json, ModpackExportStaging& state)
{
    std::string link_detail;
    if (facman::base::path_crosses_link_or_reparse_point(staging.parent_path(), link_detail))
        return facman::platform::IoStatus::failure("modpack_staging_parent_unsafe", link_detail);
    auto checked = state.parent_directory.open_no_follow_for_relative_writes(staging.parent_path());
    if (checked.ok()) checked = state.parent_directory.create_child_directory_exclusive(staging.filename(), state.directory);
    if (!checked.ok()) return checked;
    checked = write_owned_staging_text(state, ".facman-archive-staging.v1", "schema=facman.archive_staging.v1\n");
    if (checked.ok()) checked = write_owned_staging_text(state, "modpack-manifest.v1.json", manifest_json);
    return checked;
}

facman::platform::IoStatus pause_modpack_export_staging(ModpackExportStaging& state, bool private_copy)
{
    const char* enabled = std::getenv(private_copy ? "FACMAN_TEST_MODSET_EXPORT_PAUSE_AFTER_PRIVATE_COPY" :
        "FACMAN_TEST_MODSET_EXPORT_PAUSE_AFTER_STAGE");
    if (enabled == nullptr || std::string(enabled) != "1") return facman::platform::IoStatus::success();
    const std::string prefix = private_copy ? ".facman-modset-private-copy" : ".facman-modset-export";
    auto checked = write_owned_staging_text(state, prefix + "-paused", private_copy ? "copied\n" : "staged\n");
    if (!checked.ok()) return checked;
    const auto release = state.directory.path() / (prefix + "-release");
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
    while (!std::filesystem::exists(release) && std::chrono::steady_clock::now() < deadline)
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
    if (!std::filesystem::exists(release))
        return facman::platform::IoStatus::failure("modset_verification_failed", "Modpack export test pause timed out");
    return bind_modpack_export_staging_text(state, prefix + "-release", "");
}

facman::platform::IoStatus bind_modpack_export_archive(
    ModpackExportStaging& state, const facman::archive::WriteResult& archive, const facman::archive::Limits& limits)
{
    auto checked = state.directory.open_child_directory_no_follow("archive", state.archive_directory);
    if (!checked.ok()) return checked;
    auto marker = capture_source_file(state.archive_directory, ".facman-archive-staging.v1", "archive/.facman-archive-staging.v1", false);
    if (!marker || marker.value().blob.sha256 != sha256_text("schema=facman.archive_staging.v1\n"))
        return facman::platform::IoStatus::failure("modpack_staging_verification_failed", "Archive ownership marker changed");
    state.owned_files.push_back(marker.take_value());
    std::string digest;
    const auto hashed = facman::archive::archive_sha256(archive.verified_plan, limits, digest);
    if (!hashed.ok()) return facman::platform::IoStatus::failure(hashed.code, hashed.detail);
    auto file = capture_source_file(state.archive_directory, facman::platform::path_to_utf8(archive.archive_path.filename()),
        "archive/" + facman::platform::path_to_utf8(archive.archive_path.filename()), false);
    if (!file || file.value().blob.sha256 != digest || file.value().blob.size != archive.verified_plan.archive_size)
        return facman::platform::IoStatus::failure("modpack_staging_verification_failed", "Written archive changed before binding");
    state.archive_blob = file.value().blob;
    state.owned_files.push_back(file.take_value());
    return facman::platform::IoStatus::success();
}

facman::platform::IoStatus bind_modpack_export_transaction_marker(
    ModpackExportStaging& state, const facman::transaction::Record& record)
{
    json::ObjectBuilder marker;
    marker.add_string("schema", "facman.transaction_staging.v2");
    marker.add_string("transaction_id", record.transaction_id);
    marker.add_string("command_id", record.command_id);
    marker.add_string("target_sha256", sha256_text(facman::platform::path_to_utf8(
        std::filesystem::absolute(record.target).lexically_normal())));
    marker.add_string("nonce", record.marker_nonce);
    return bind_modpack_export_staging_text(state, ".facman-transaction-staging.v2.json", marker.serialize() + "\n");
}

facman::platform::IoStatus cleanup_modpack_export_staging(ModpackExportStaging& state)
{
    if (!state.directory.open()) return facman::platform::IoStatus::success();
    const std::string retained = "; retained staging: " + facman::platform::path_to_utf8(state.directory.path());
    auto failure = [&](const std::string& reason) {
        return facman::platform::IoStatus::failure("modpack_staging_retained", reason + retained);
    };
    if (!state.parent_directory.revalidate().ok() || !state.directory.revalidate().ok() ||
        (state.archive_directory.open() && !state.archive_directory.revalidate().ok()))
        return failure("Owned staging directory identity changed");
    std::set<std::string> expected_names;
    for (const auto& file : state.owned_files) expected_names.insert(file.archive_path);
    for (const auto* directory : {&state.directory, &state.archive_directory}) {
        if (!directory->open()) continue;
        std::vector<std::filesystem::path> names;
        const auto listed = directory->list_child_names_bounded(16U, names);
        if (!listed.ok()) return failure(listed.detail);
        for (const auto& name : names) {
            const std::string path = (directory == &state.archive_directory ? "archive/" : "") + facman::platform::path_to_utf8(name);
            if (path == "archive" && state.archive_directory.open()) continue;
            if (expected_names.count(path) == 0U) return failure("Unknown staging child: " + path);
        }
    }
    // Check every admitted object and its bytes before removing any object.
    std::vector<const ModpackSourceFile*> present;
    for (const auto& file : state.owned_files) {
        const bool archive_file = file.archive_path.rfind("archive/", 0U) == 0U;
        const auto& directory = archive_file ? state.archive_directory : state.directory;
        const bool published_zip = archive_file && file.source_path.extension() == ".zip" && state.archive_published;
        auto current = capture_source_file(directory, facman::platform::path_to_utf8(file.source_path.filename()), file.archive_path, published_zip, file.blob.size);
        if (!current) return failure(current.error().message);
        if (!current.value().present && published_zip) continue;
        if (!current.value().identity.unchanged(file.identity) || current.value().blob.sha256 != file.blob.sha256 ||
            current.value().blob.size != file.blob.size) return failure("Owned staging file changed: " + file.archive_path);
        present.push_back(&file);
    }
    auto same_bytes = [](const facman::platform::StableInputFile& input, const BlobIdentity& expected) {
        if (input.size() != expected.size) return false;
        facman::base::Sha256Hasher digest;
        std::array<unsigned char, 65536> block {};
        for (std::uint64_t offset = 0; offset < input.size();) {
            const auto count = static_cast<std::size_t>(std::min<std::uint64_t>(block.size(), input.size() - offset));
            if (input.read_at(offset, block.data(), count) != count) return false;
            digest.update(block.data(), count);
            offset += count;
        }
        return digest.finish() == expected.sha256;
    };
    for (const auto* file : present) {
        const auto& directory = file->archive_path.rfind("archive/", 0U) == 0U ? state.archive_directory : state.directory;
        const auto removed = directory.remove_child_file_no_follow_if_matches(file->source_path.filename(), file->identity,
            [&](const auto& input) { return same_bytes(input, file->blob); });
        if (!removed.ok()) return failure(removed.detail);
    }
    if (state.archive_directory.open()) {
        const auto identity = state.archive_directory.identity();
        state.archive_directory = facman::platform::StableDirectoryObject();
        const auto removed = state.directory.remove_child_empty_directory_no_follow_if_matches("archive", identity);
        if (!removed.ok()) return failure(removed.detail);
    }
    const auto identity = state.directory.identity();
    const auto leaf = state.directory.path().filename();
    state.directory = facman::platform::StableDirectoryObject();
    const auto removed = state.parent_directory.remove_child_empty_directory_no_follow_if_matches(leaf, identity);
    return removed.ok() ? removed : failure(removed.detail);
}

void append_modpack_manifest_closure_fields(
    json::ObjectBuilder& output, const ModpackManifest& value, const json::ArrayBuilder& artifacts)
{
    output.add_array("artifacts", artifacts);
    if (!value.settings.empty()) {
        auto ordered = value.settings;
        std::sort(ordered.begin(), ordered.end(), [](const auto& left, const auto& right) {
            return left.path < right.path;
        });
        json::ArrayBuilder settings;
        for (const ModpackSetting& setting : ordered) {
            json::ObjectBuilder entry;
            entry.add_string("path", setting.path);
            entry.add_string("state", setting.present ? "present" : "absent");
            (void)entry.add_unsigned_integer("size", setting.blob.size);
            entry.add_string("sha256", setting.blob.sha256);
            settings.add_object(entry);
        }
        output.add_array("settings", settings);
        json::ObjectBuilder source_lock;
        source_lock.add_string("path", "modset-lock.v1.json");
        json::ObjectBuilder blob;
        blob.add_string("algorithm", "sha256");
        blob.add_string("sha256", value.source_lock.sha256);
        (void)blob.add_unsigned_integer("size", value.source_lock.size);
        source_lock.add_object("blob", blob);
        output.add_object("source_lock", source_lock);
    }
}

bool modpack_startup_settings_bound(const ModpackManifest& value)
{
    return value.content_lock.startup_settings_state == "absent" || !value.content_lock.startup_settings_sha256.empty();
}

std::string modpack_startup_settings_state(const ContentLock& value)
{
    return !value.startup_settings_state.empty() ? value.startup_settings_state :
        (value.startup_settings_sha256.empty() ? "unbound" : "sha256_bound");
}

} // namespace facman::factorio::content
