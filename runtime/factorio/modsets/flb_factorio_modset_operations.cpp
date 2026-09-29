// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_modset_operations.h"

#include "fl_archive.h"
#include "fl_archive_platform.h"
#include "fl_path_safety.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_sha256.h"
#include "fl_transaction.h"
#include "fl_workspace_store.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <map>
#include <sstream>
#include <thread>

namespace facman::factorio::modsets::operations {
namespace fs = std::filesystem;
namespace tx = facman::transaction;
namespace json = facman::core::json;
namespace {

struct Instance {
    std::string instance_id;
    std::string factorio_version;
    fs::path root;
};

std::string path_string(const fs::path& path)
{
    return path.lexically_normal().generic_string();
}

std::string read_text(const fs::path& path)
{
    std::ifstream input(path, std::ios::binary);
    std::ostringstream output;
    output << input.rdbuf();
    return output.str();
}

Refusal refuse(
    const std::string& command,
    const std::string& instance_id,
    const std::string& code,
    const std::string& reason,
    const std::string& detail,
    bool recoverable = true)
{
    Refusal refusal;
    refusal.command = command;
    refusal.instance_id = instance_id;
    refusal.code = code;
    refusal.reason = reason;
    refusal.detail = detail;
    refusal.recoverable = recoverable;
    return refusal;
}

bool load_instance(const fs::path& workspace, const std::string& instance_id, Instance& instance)
{
    auto parsed_id = facman::core::InstanceId::parse(instance_id);
    if (!parsed_id) return false;
    auto record = facman::workspace::InstanceRepository(facman::workspace::WorkspaceLayout(workspace)).load(
        parsed_id.value());
    if (!record) return false;
    instance.instance_id = record.value().id.str();
    instance.factorio_version = record.value().factorio_version;
    instance.root = record.value().root;
    return !instance.factorio_version.empty();
}

fs::path instance_lock_path(const Instance& instance)
{
    auto parsed_id = facman::core::InstanceId::parse(instance.instance_id);
    if (!parsed_id) return {};
    auto path = facman::workspace::WorkspaceLayout(instance.root.parent_path().parent_path()).instance_modset_lock(
        parsed_id.value());
    return path ? path.value() : fs::path();
}

fs::path workspace_lock_path(const fs::path& workspace, const Instance& instance)
{
    auto parsed_id = facman::core::InstanceId::parse(instance.instance_id);
    if (!parsed_id) return {};
    auto path = facman::workspace::ModsetRepository(facman::workspace::WorkspaceLayout(workspace)).canonical_lock(
        parsed_id.value());
    return path ? path.value() : fs::path();
}

std::vector<ModRef> instance_mods(const Instance& instance)
{
    std::vector<ModRef> mods;
    const fs::path root = instance.root / "mods";
    std::error_code error;
    if (!fs::is_directory(root, error)) return mods;
    for (const fs::directory_entry& entry : fs::directory_iterator(root)) {
        if (entry.path().extension() == ".zip" && entry.is_regular_file(error) && !error) {
            mods.push_back(inspect_mod_zip(entry.path()));
        }
    }
    std::sort(mods.begin(), mods.end(), [](const ModRef& left, const ModRef& right) {
        return left.file_name < right.file_name;
    });
    return mods;
}

std::string lock_json(const Instance& instance, const std::vector<ModRef>& mods)
{
    json::ArrayBuilder entries;
    for (const ModRef& mod : mods) {
        auto value = json::parse(::facman::factorio::modsets::mod_ref_json(mod));
        if (value) entries.add_value(value.value());
    }
    json::ObjectBuilder output;
    (void)output.add_unsigned_integer("lockfile_version", 1);
    output.add_string("schema", "factorio.modset_lock.v1");
    output.add_string("instance_id", instance.instance_id);
    output.add_string("factorio_version", instance.factorio_version);
    output.add_array("mods", entries);
    return output.serialize() + "\n";
}

struct LockEntry {
    std::string file_name;
    std::string sha1;
    std::string sha256;
};

std::vector<LockEntry> lock_entries(const std::string& text)
{
    std::vector<LockEntry> entries;
    json::Limits limits;
    limits.maximum_bytes = 8U * 1024U * 1024U;
    limits.maximum_depth = 24;
    limits.maximum_nodes = 100000;
    auto document = json::parse(text, limits);
    if (!document || !document.value().is_object()) return entries;
    const json::Value* mods = document.value().find("mods");
    if (mods == nullptr || !mods->is_array()) return entries;
    for (std::size_t index = 0; index < mods->size(); ++index) {
        const json::Value* item = mods->at(index);
        if (item == nullptr || !item->is_object()) return {};
        const json::Value* file_name = item->find("file_name");
        const json::Value* sha1 = item->find("sha1");
        const json::Value* sha256 = item->find("sha256");
        if (file_name == nullptr || sha1 == nullptr) return {};
        auto file_text = file_name->string_value();
        auto sha1_text = sha1->string_value();
        if (!file_text || !sha1_text) return {};
        LockEntry entry;
        entry.file_name = file_text.take_value();
        entry.sha1 = sha1_text.take_value();
        if (sha256 != nullptr) {
            auto sha256_text = sha256->string_value();
            if (!sha256_text) return {};
            entry.sha256 = sha256_text.take_value();
        }
        if (!entry.file_name.empty()) entries.push_back(entry);
    }
    return entries;
}

std::vector<std::string> verify_lock(const Instance& instance)
{
    std::vector<std::string> problems;
    const fs::path path = instance_lock_path(instance);
    if (!fs::is_regular_file(path)) {
        problems.push_back("missing modset lockfile");
        return problems;
    }
    const std::string current_lock = read_text(path);
    for (const LockEntry& entry : lock_entries(current_lock)) {
        const fs::path mod_path = instance.root / "mods" / entry.file_name;
        if (!fs::is_regular_file(mod_path)) {
            problems.push_back("missing mod file: " + entry.file_name);
            continue;
        }
        if (sha1_hex_file(mod_path) != entry.sha1) {
            problems.push_back("sha1 mismatch: " + entry.file_name);
        }
        if (!entry.sha256.empty() && sha256_hex_file(mod_path) != entry.sha256) {
            problems.push_back("sha256 mismatch: " + entry.file_name);
        }
    }
    const std::vector<ModRef> mods = instance_mods(instance);
    for (const ModsetIssue& issue : validate_modset(mods, instance.factorio_version)) {
        problems.push_back(issue.code + ": " + issue.detail);
    }
    if (current_lock != lock_json(instance, mods)) {
        problems.push_back("metadata drift: modset lock does not match inspected archives");
    }
    return problems;
}

fs::path unique_staging(const fs::path& parent, const std::string& prefix)
{
    const auto stamp = std::chrono::steady_clock::now().time_since_epoch().count();
    for (int attempt = 0; attempt < 100; ++attempt) {
        const fs::path candidate = parent / (prefix + std::to_string(stamp) + "-" + std::to_string(attempt));
        if (!fs::exists(candidate)) return candidate;
    }
    return {};
}

bool stream_copy(const fs::path& source, const fs::path& destination)
{
    facman::platform::StableInputFile input;
    if (!input.open_no_follow(source).ok()) return false;
    facman::platform::DurableOutputFile output;
    if (!output.create_exclusive(destination, input.size()).ok()) return false;
    std::array<char, 64 * 1024> buffer {};
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t requested = static_cast<std::size_t>(
            std::min<std::uint64_t>(buffer.size(), input.size() - offset));
        const std::size_t count = input.read_at(offset, buffer.data(), requested);
        if (count == 0 || output.write_at(offset, buffer.data(), count) != count) {
            output.close_without_flush();
            return false;
        }
        offset += count;
    }
    if (!input.revalidate().ok()) {
        output.close_without_flush();
        return false;
    }
    return output.flush_file_and_parent().ok();
}

facman::platform::IoStatus pause_after_private_import_copy(const fs::path& staging)
{
    const char* enabled = std::getenv("FACMAN_TEST_MOD_IMPORT_PAUSE_AFTER_PRIVATE_COPY");
    if (enabled == nullptr || std::string(enabled) != "1") {
        return facman::platform::IoStatus::success();
    }
    std::string detail;
    if (!facman::base::write_text_new_atomic(
            staging / ".facman-mod-import-private-paused", "copied\n", detail)) {
        return facman::platform::IoStatus::failure("mod_staging_verification_failed", detail);
    }
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
    while (!fs::exists(staging / ".facman-mod-import-private-release") &&
        std::chrono::steady_clock::now() < deadline) {
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }
    if (!fs::exists(staging / ".facman-mod-import-private-release")) {
        return facman::platform::IoStatus::failure(
            "mod_staging_verification_failed", "Private mod copy test pause timed out");
    }
    return facman::platform::IoStatus::success();
}

} // namespace

ImportOutcome import_mod(const fs::path& workspace, const ImportRequest& request)
{
    const std::string command = "mods.import";
    Instance instance;
    if (!load_instance(workspace, request.instance_id, instance)) {
        return refuse(command, request.instance_id, "unknown_instance", "Instance is not registered", request.instance_id);
    }
    if (!fs::is_regular_file(request.source_path) || request.source_path.extension() != ".zip") {
        return refuse(command, request.instance_id, "mod_zip_source_invalid", "Mod import requires a local ZIP file", path_string(request.source_path));
    }
    ModRef mod = inspect_mod_zip(request.source_path);
    if (!mod.valid) {
        Refusal refusal = refuse(
            command,
            request.instance_id,
            mod.refusal_code,
            mod.refusal_reason,
            mod.refusal_detail);
        refusal.source_path = request.source_path;
        refusal.file_name = request.source_path.filename().string();
        refusal.metadata_source = mod.metadata_source;
        refusal.suggested_next_command = "facman mods import <mod.zip> --instance <id> --json";
        return refusal;
    }
    if (!factorio_versions_compatible(mod.factorio_version, instance.factorio_version)) {
        Refusal refusal = refuse(
            command,
            request.instance_id,
            "mod_factorio_version_incompatible",
            "Mod factorio_version is not compatible with this instance",
            mod.factorio_version + " != " + factorio_minor_version(instance.factorio_version));
        refusal.source_path = request.source_path;
        refusal.file_name = request.source_path.filename().string();
        refusal.metadata_source = mod.metadata_source;
        refusal.suggested_next_command = "facman mods import <mod.zip> --instance <id> --json";
        return refusal;
    }
    const fs::path mods_root = instance.root / "mods";
    const fs::path destination = mods_root / request.source_path.filename();
    if (fs::exists(destination)) {
        return refuse(command, request.instance_id, "persistent_target_exists", "Mod target already exists", path_string(destination));
    }
    const std::uintmax_t source_size = fs::file_size(request.source_path);
    const fs::file_time_type source_time = fs::last_write_time(request.source_path);
    const std::string source_sha256 = sha256_hex_file(request.source_path);
    const fs::path staging = unique_staging(mods_root, ".facman-mod-import-");
    tx::Record transaction;
    transaction.command_id = command;
    transaction.target = destination;
    transaction.sources = {request.source_path};
    transaction.staging_roots = {staging};
    auto expected_path = tx::RelativePath::parse(facman::platform::path_to_utf8(request.source_path.filename()));
    auto expected_digest = facman::core::Sha256Digest::parse(source_sha256);
    if (!expected_path || !expected_digest) {
        return refuse(command, request.instance_id, "mod_staging_verification_failed", "Mod expectation could not be represented safely", request.source_path.string());
    }
    transaction.expected_files.push_back(
        {expected_path.take_value(), expected_digest.take_value(), static_cast<std::uint64_t>(source_size)});
    transaction.commit_strategy = "destination_volume_stage_then_atomic_no_replace";
    auto started = tx::TransactionSession::begin(workspace, std::move(transaction));
    if (!started) {
        return refuse(command, request.instance_id, "recovery_write_refused", "Mod import journal preparation failed", started.error().message);
    }
    tx::TransactionSession session = started.take_value();
    if (!session.validated("request_validated") ||
        !session.planned("source_and_target_validated")) {
        return refuse(command, request.instance_id, "recovery_write_refused", "Mod import journal preparation failed", session.detail());
    }
    facman::archive::Status status = facman::archive::create_owned_staging_root(staging);
    if (!status.ok()) {
        session.failed(status.detail);
        return refuse(command, request.instance_id, "persistent_write_refused", "Could not create owned mod staging", status.code + ": " + status.detail);
    }
    if (!session.staging("owned_staging_created")) return refuse(command, request.instance_id, "recovery_write_refused", "Mod import staging journal update failed", session.detail());
    const fs::path staged_file = staging / request.source_path.filename();
    auto fail_staging = [&](const std::string& code, const std::string& reason, const std::string& detail) -> ImportOutcome {
        const auto cleaned = facman::archive::cleanup_owned_staging_root(staging);
        if (!cleaned.ok()) {
            const std::string recovery_detail = detail + "; staging cleanup: " + cleaned.detail;
            session.require_recovery(recovery_detail);
            return refuse(command, request.instance_id, "transaction_recovery_required",
                "Mod import staging requires recovery", recovery_detail, false);
        }
        session.failed(detail);
        return refuse(command, request.instance_id, code, reason, detail);
    };
    if (!stream_copy(request.source_path, staged_file) || fs::file_size(request.source_path) != source_size ||
        fs::last_write_time(request.source_path) != source_time ||
        sha256_hex_file(request.source_path) != source_sha256 ||
        sha256_hex_file(staged_file) != source_sha256) {
        return fail_staging("mod_source_changed", "Mod source changed while it was copied", path_string(request.source_path));
    }
    ModRef staged_mod = inspect_mod_zip(staged_file);
    if (!staged_mod.valid || staged_mod.name != mod.name || staged_mod.version != mod.version) {
        return fail_staging("mod_staging_verification_failed", "Staged mod did not match inspected source", staged_mod.refusal_detail);
    }
    const char* pause_after_stage = std::getenv("FACMAN_TEST_MOD_IMPORT_PAUSE_AFTER_STAGE");
    if (pause_after_stage != nullptr && std::string(pause_after_stage) == "1") {
        std::string marker_detail;
        if (!facman::base::write_text_new_atomic(
                staging / ".facman-mod-import-paused", "staged\n", marker_detail)) {
            return fail_staging("mod_staging_verification_failed", "Import test pause failed", marker_detail);
        }
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
        while (!fs::exists(staging / ".facman-mod-import-release") &&
            std::chrono::steady_clock::now() < deadline) {
            std::this_thread::sleep_for(std::chrono::milliseconds(20));
        }
        if (!fs::exists(staging / ".facman-mod-import-release")) {
            return fail_staging("mod_staging_verification_failed", "Import test pause timed out", path_string(staging));
        }
    }
    facman::platform::FileIdentity staged_identity;
    const auto staged_check = [&]() {
        facman::platform::StableInputFile staged_input;
        const auto opened = staged_input.open_no_follow_pinned(staged_file);
        if (!opened.ok() || !staged_input.identity().regular_file ||
            staged_input.identity().link_count != 1U || staged_input.size() != source_size) {
            return facman::platform::IoStatus::failure("mod_staging_verification_failed",
                opened.ok() ? "Staged mod identity changed" : opened.detail);
        }
        facman::base::Sha256Hasher digest;
        std::array<unsigned char, 65536> block {};
        for (std::uint64_t offset = 0; offset < staged_input.size();) {
            const auto count = static_cast<std::size_t>(std::min<std::uint64_t>(
                block.size(), staged_input.size() - offset));
            if (staged_input.read_at(offset, block.data(), count) != count) {
                return facman::platform::IoStatus::failure(
                    "mod_staging_verification_failed", "Staged mod read changed");
            }
            digest.update(block.data(), count);
            offset += count;
        }
        if (!staged_input.revalidate_path().ok() || digest.finish() != source_sha256) {
            return facman::platform::IoStatus::failure(
                "mod_staging_verification_failed", "Staged mod differs from inspected source");
        }
        staged_identity = staged_input.identity();
        return facman::platform::IoStatus::success();
    }();
    if (!staged_check.ok()) {
        return fail_staging("mod_staging_verification_failed", "Staged mod no longer matches inspected source",
            staged_check.detail);
    }
    if (!session.staged("source_copied") ||
        !session.verified("staged_mod_verified") ||
        !session.committing("no_clobber_commit_started")) {
        return fail_staging("recovery_write_refused", "Mod import journal update failed", session.detail());
    }
    const auto published = [&]() {
        facman::platform::StableDirectoryObject stage_parent;
        facman::platform::StableDirectoryObject target_parent;
        auto result = stage_parent.open_no_follow_for_relative_writes(staging);
        if (result.ok()) result = target_parent.open_no_follow_for_relative_writes(mods_root);
#ifdef _WIN32
        facman::platform::DurableOutputFile private_copy;
        if (result.ok()) result = stage_parent.create_child_file_exclusive(
            "verified-private.zip", static_cast<std::uint64_t>(source_size), private_copy);
        if (result.ok()) {
            facman::platform::StableInputFile staged_input;
            result = stage_parent.open_child_file_no_follow_pinned(
                staged_file.filename(), staged_input);
            if (result.ok() &&
                (!staged_input.identity().unchanged(staged_identity) || staged_input.size() != source_size)) {
                result = facman::platform::IoStatus::failure(
                    "mod_staging_verification_failed", "Staged mod identity changed before private copy");
            }
            facman::base::Sha256Hasher digest;
            std::array<unsigned char, 65536> block {};
            for (std::uint64_t offset = 0; result.ok() && offset < staged_input.size();) {
                const auto count = static_cast<std::size_t>(std::min<std::uint64_t>(
                    block.size(), staged_input.size() - offset));
                if (staged_input.read_at(offset, block.data(), count) != count ||
                    private_copy.write_at(offset, block.data(), count) != count) {
                    result = facman::platform::IoStatus::failure(
                        "mod_staging_verification_failed", "Private mod copy failed");
                    break;
                }
                digest.update(block.data(), count);
                offset += count;
            }
            if (result.ok() &&
                (!staged_input.revalidate_path().ok() || digest.finish() != source_sha256)) {
                result = facman::platform::IoStatus::failure(
                    "mod_staging_verification_failed", "Private mod copy differs from inspected source");
            }
        }
        if (result.ok()) result = pause_after_private_import_copy(staging);
        if (result.ok()) result = private_copy.publish_in_directory_no_replace(
            target_parent, destination.filename());
#else
        facman::platform::StableInputFile staged_input;
        if (result.ok()) result = staged_input.open_no_follow_pinned(staged_file);
        if (result.ok() &&
            (!staged_input.identity().unchanged(staged_identity) || staged_input.size() != source_size)) {
            result = facman::platform::IoStatus::failure(
                "mod_staging_verification_failed", "Staged mod identity changed before private copy");
        }
        facman::platform::PrivatePublicationFile private_copy;
        if (result.ok()) result = private_copy.create(
            stage_parent, target_parent, static_cast<std::uint64_t>(source_size));
        facman::base::Sha256Hasher digest;
        std::array<unsigned char, 65536> block {};
        for (std::uint64_t offset = 0; result.ok() && offset < staged_input.size();) {
            const auto count = static_cast<std::size_t>(std::min<std::uint64_t>(
                block.size(), staged_input.size() - offset));
            if (staged_input.read_at(offset, block.data(), count) != count ||
                private_copy.write_at(offset, block.data(), count) != count) {
                result = facman::platform::IoStatus::failure(
                    "mod_staging_verification_failed", "Private mod copy failed");
                break;
            }
            digest.update(block.data(), count);
            offset += count;
        }
        if (result.ok() &&
            (!staged_input.revalidate_path().ok() || digest.finish() != source_sha256)) {
            result = facman::platform::IoStatus::failure(
                "mod_staging_verification_failed", "Private mod copy differs from inspected source");
        }
        if (result.ok()) result = pause_after_private_import_copy(staging);
        if (result.ok()) result = private_copy.publish_no_replace(destination.filename());
#endif
        return result;
    }();
    if (!published.ok()) {
        if (published.code == "output_published_unverified") {
            session.require_recovery(published.detail);
            return refuse(command, request.instance_id, "transaction_recovery_required",
                "Mod publication requires recovery", published.detail, false);
        }
        const bool verification_failed = published.code == "mod_staging_verification_failed";
        return fail_staging(verification_failed ? "mod_staging_verification_failed" : "persistent_write_refused",
            verification_failed ? "Staged mod no longer matches inspected source" : "Mod no-clobber commit failed",
            published.detail);
    }
    if (!session.committed("mod_file_committed")) return refuse(command, request.instance_id, "transaction_recovery_required", "Mod committed but journal update failed", session.detail(), false);
    status = facman::archive::cleanup_owned_staging_root(staging);
    if (!status.ok()) {
        session.require_recovery(status.code + ": " + status.detail);
        return refuse(command, request.instance_id, "transaction_recovery_required",
            "Committed mod but staging cleanup requires recovery", status.code + ": " + status.detail, false);
    }
    if (!session.complete()) return refuse(command, request.instance_id, "transaction_recovery_required", "Mod committed but journal close requires recovery", session.detail(), false);
    mod.file_path = destination;
    return ImportResult {request.instance_id, request.source_path, destination, mod};
}

LockOutcome lock_modset(const fs::path& workspace, const InstanceRequest& request)
{
    const std::string command = "modsets.lock";
    Instance instance;
    if (!load_instance(workspace, request.instance_id, instance)) {
        return refuse(command, request.instance_id, "unknown_instance", "Instance is not registered", request.instance_id);
    }
    const std::vector<ModRef> mods = instance_mods(instance);
    const std::vector<ModsetIssue> issues = validate_modset(mods, instance.factorio_version);
    if (!issues.empty()) {
        Refusal refusal = refuse(
            command,
            request.instance_id,
            issues[0].code,
            issues[0].reason,
            issues[0].detail);
        refusal.file_name = issues[0].file_name;
        refusal.recoverable = issues[0].code != "mod_incompatibility_detected";
        refusal.suggested_next_command = "facman modsets lock <instance-id> --json";
        return refusal;
    }
    const std::string text = lock_json(instance, mods);
    const fs::path local_path = instance_lock_path(instance);
    const fs::path shared_path = workspace_lock_path(workspace, instance);
    const bool local_exists = fs::is_regular_file(local_path);
    const bool shared_exists = fs::is_regular_file(shared_path);
    if ((local_exists && read_text(local_path) != text) ||
        (shared_exists && read_text(shared_path) != text)) {
        return refuse(command, request.instance_id, "persistent_target_exists", "Existing modset lock differs from the requested lock", path_string(local_exists ? local_path : shared_path));
    }
    if (local_exists && shared_exists) {
        return LockResult {request.instance_id, instance.factorio_version, local_path, shared_path, mods, text};
    }
    tx::Record transaction;
    transaction.command_id = command;
    transaction.target = shared_path;
    for (const ModRef& mod : mods) transaction.sources.push_back(mod.file_path);
    transaction.commit_strategy = "durable_exclusive_multi_file_create";
    auto started = tx::TransactionSession::begin(workspace, std::move(transaction));
    if (!started) {
        return refuse(command, request.instance_id, "recovery_write_refused", "Modset lock journal preparation failed", started.error().message);
    }
    tx::TransactionSession session = started.take_value();
    if (!session.validated("modset_validated") ||
        !session.planned("lock_targets_validated") ||
        !session.staged("lock_record_serialized") ||
        !session.verified("lock_record_verified") ||
        !session.committing("durable_exclusive_writes_started")) {
        return refuse(command, request.instance_id, "recovery_write_refused", "Modset lock journal preparation failed", session.detail());
    }
    std::string detail;
    const bool local_ok = local_exists || facman::base::write_text_new_atomic(local_path, text, detail);
    const bool shared_ok = shared_exists || facman::base::write_text_new_atomic(shared_path, text, detail);
    if (!local_ok || !shared_ok) {
        session.failed(detail);
        return refuse(command, request.instance_id, "persistent_write_refused", "Modset lock no-clobber write failed", detail);
    }
    if (!session.committed("lock_files_committed") || !session.complete()) {
        return refuse(command, request.instance_id, "transaction_recovery_required", "Modset lock committed but journal finalization failed", session.detail(), false);
    }
    return LockResult {request.instance_id, instance.factorio_version, local_path, shared_path, mods, text};
}

VerifyOutcome verify_modset(const fs::path& workspace, const InstanceRequest& request)
{
    Instance instance;
    if (!load_instance(workspace, request.instance_id, instance)) {
        return refuse("modsets.verify", request.instance_id, "unknown_instance", "Instance is not registered", request.instance_id);
    }
    return VerifyResult {request.instance_id, verify_lock(instance)};
}

ExportOutcome export_modset(const fs::path& workspace, const ExportRequest& request)
{
    const std::string command = "modsets.export";
    Instance instance;
    if (!load_instance(workspace, request.instance_id, instance)) {
        return refuse(command, request.instance_id, "unknown_instance", "Instance is not registered", request.instance_id);
    }
    const std::vector<std::string> verification = verify_lock(instance);
    if (!verification.empty()) {
        return refuse(command, request.instance_id, "modset_verification_failed", "Modset must verify before export", verification.front());
    }
    const std::vector<ModRef> mods = instance_mods(instance);
    const std::string expected_lock = lock_json(instance, mods);
    if (read_text(instance_lock_path(instance)) != expected_lock) {
        return refuse(command, request.instance_id, "modset_verification_failed",
            "Modset lock changed before export", path_string(instance_lock_path(instance)));
    }
    std::map<std::string, std::string> expected_archive_digests;
    expected_archive_digests.emplace("modset-lock.v1.json",
        facman::base::sha256_hex_bytes(
            reinterpret_cast<const unsigned char*>(expected_lock.data()), expected_lock.size()));
    for (const ModRef& mod : mods) {
        if (mod.sha256.size() != 64U ||
            !expected_archive_digests.emplace("mods/" + mod.file_name, mod.sha256).second) {
            return refuse(command, request.instance_id, "modset_verification_failed",
                "Modset contains an ambiguous archive entry", mod.file_name);
        }
    }
    if (fs::exists(request.output_path)) {
        return refuse(command, request.instance_id, "persistent_target_exists", "Modset export target already exists", path_string(request.output_path));
    }
    fs::path output_parent = request.output_path.parent_path();
    if (output_parent.empty()) output_parent = fs::current_path();
    if (!fs::is_directory(output_parent)) {
        return refuse(command, request.instance_id, "persistent_write_refused", "Modset export parent does not exist", path_string(output_parent));
    }
    std::vector<facman::archive::WriteEntry> entries;
    entries.push_back({"modset-lock.v1.json", instance_lock_path(instance), false});
    for (const ModRef& mod : mods) {
        entries.push_back({"mods/" + mod.file_name, mod.file_path, false});
    }
    const fs::path staging = unique_staging(output_parent, ".facman-modset-export-");
    tx::Record transaction;
    transaction.command_id = command;
    transaction.target = request.output_path;
    transaction.sources = {instance.root};
    transaction.staging_roots = {staging};
    transaction.commit_strategy = "destination_volume_stage_then_atomic_no_replace";
    auto started = tx::TransactionSession::begin(workspace, std::move(transaction));
    if (!started) {
        return refuse(command, request.instance_id, "recovery_write_refused", "Modset export journal preparation failed", started.error().message);
    }
    tx::TransactionSession session = started.take_value();
    if (!session.validated("request_validated") ||
        !session.planned("verified_modset_and_target_validated") ||
        !session.staging("owned_staging_selected")) {
        return refuse(command, request.instance_id, "recovery_write_refused", "Modset export journal preparation failed", session.detail());
    }
    facman::archive::WriteOptions options;
    options.method = facman::archive::CompressionMethod::deflate;
    options.reproducible = true;
    options.limits = facman::archive::PackageArchivePolicy::limits();
    facman::archive::WriteResult written;
    facman::archive::Status status = facman::archive::write_to_new_owned_staging(
        staging,
        request.output_path.filename().string(),
        entries,
        options,
        written);
    if (!status.ok()) {
        session.failed(status.detail);
        return refuse(command, request.instance_id, "persistent_write_refused", "Modset archive staging failed", status.code + ": " + status.detail);
    }
    std::string closure_error;
    const char* pause_after_stage = std::getenv("FACMAN_TEST_MODSET_EXPORT_PAUSE_AFTER_STAGE");
    if (pause_after_stage != nullptr && std::string(pause_after_stage) == "1") {
        const fs::path pause_marker = staging / ".facman-modset-export-paused";
        const fs::path pause_release = staging / ".facman-modset-export-release";
        std::string marker_detail;
        if (!facman::base::write_text_new_atomic(
                pause_marker, "staged\n", marker_detail)) {
            closure_error = "modset export test pause marker could not be written: " + marker_detail;
        }
        const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
        while (closure_error.empty() && !fs::exists(pause_release) &&
            std::chrono::steady_clock::now() < deadline) {
            std::this_thread::sleep_for(std::chrono::milliseconds(20));
        }
        if (closure_error.empty() && !fs::exists(pause_release)) {
            closure_error = "modset export test pause timed out";
        }
    }
    if (closure_error.empty() &&
        written.verified_plan.entries.size() != expected_archive_digests.size()) {
        closure_error = "staged archive entry count differs from the verified lock";
    } else if (closure_error.empty()) {
        for (const facman::archive::Entry& entry : written.verified_plan.entries) {
            const auto expected = expected_archive_digests.find(entry.path);
            if (entry.directory || expected == expected_archive_digests.end()) {
                closure_error = "staged archive contains an unbound entry: " + entry.path;
                break;
            }
            facman::base::Sha256Hasher digest;
            status = facman::archive::stream_entry(written.verified_plan, entry.index,
                options.limits, [&](const unsigned char* bytes, std::size_t size) {
                    digest.update(bytes, size);
                    return true;
                });
            if (!status.ok() || digest.finish() != expected->second) {
                closure_error = "staged archive differs from the verified lock: " + entry.path;
                break;
            }
        }
    }
    if (closure_error.empty()) {
        const std::vector<std::string> after_staging = verify_lock(instance);
        if (!after_staging.empty()) {
            closure_error = "modset source changed during export: " + after_staging.front();
        }
    }
    std::string archive_digest;
    if (closure_error.empty()) {
        status = facman::archive::archive_sha256(written.verified_plan, options.limits, archive_digest);
        if (!status.ok()) closure_error = "staged archive digest failed: " + status.detail;
    }
    facman::platform::FileIdentity exact_archive_identity;
    if (closure_error.empty()) {
        facman::platform::StableInputFile staged_archive;
        const auto opened = staged_archive.open_no_follow_pinned(written.archive_path);
        if (!opened.ok() || !staged_archive.identity().regular_file ||
            staged_archive.identity().link_count != 1U ||
            staged_archive.size() != written.verified_plan.archive_size) {
            closure_error = opened.ok() ? "staged archive identity changed" : opened.detail;
        } else {
            facman::base::Sha256Hasher digest;
            std::array<unsigned char, 65536> block {};
            for (std::uint64_t offset = 0; offset < staged_archive.size();) {
                const auto count = static_cast<std::size_t>(std::min<std::uint64_t>(
                    block.size(), staged_archive.size() - offset));
                if (staged_archive.read_at(offset, block.data(), count) != count) {
                    closure_error = "staged archive changed during final identity check";
                    break;
                }
                digest.update(block.data(), count);
                offset += count;
            }
            if (closure_error.empty() &&
                (!staged_archive.revalidate_path().ok() || digest.finish() != archive_digest)) {
                closure_error = "staged archive differs from verified bytes";
            }
            if (closure_error.empty()) exact_archive_identity = staged_archive.identity();
        }
    }
    if (!closure_error.empty()) {
        written.verified_plan.reader.reset();
        const facman::archive::Status cleaned =
            facman::archive::cleanup_owned_staging_root(staging);
        if (!cleaned.ok()) closure_error += "; cleanup: " + cleaned.detail;
        session.failed(closure_error);
        return refuse(command, request.instance_id, "modset_verification_failed",
            "Modset export no longer matches its verified lock", closure_error);
    }
    if (!session.staged("archive_written") ||
        !session.verified("archive_self_verified") ||
        !session.committing("no_clobber_commit_started")) {
        return refuse(command, request.instance_id, "recovery_write_refused", "Modset export journal update failed", session.detail());
    }
    written.verified_plan.reader.reset();
    const auto opened = [&]() {
        facman::platform::StableDirectoryObject source_parent;
        facman::platform::StableDirectoryObject target_parent;
        auto result = source_parent.open_no_follow_for_relative_writes(staging);
        if (result.ok()) result = target_parent.open_no_follow_for_relative_writes(output_parent);
#ifdef _WIN32
        facman::platform::DurableOutputFile exact_archive;
        if (result.ok()) result = source_parent.reopen_child_file_no_follow_for_relative_publish(
            written.archive_path.filename(), exact_archive_identity,
            options.limits.maximum_archive_bytes, exact_archive);
        if (result.ok()) result = exact_archive.publish_in_directory_no_replace(
            target_parent, request.output_path.filename());
#else
        facman::platform::StableInputFile staged_archive;
        if (result.ok()) result = staged_archive.open_no_follow_pinned(written.archive_path);
        if (result.ok() &&
            (!staged_archive.identity().same_object(exact_archive_identity) ||
             staged_archive.size() != written.verified_plan.archive_size))
            result = facman::platform::IoStatus::failure(
                "modset_verification_failed", "staged archive identity changed before private copy");
        facman::platform::PrivatePublicationFile private_copy;
        if (result.ok()) result = private_copy.create(
            source_parent, target_parent, options.limits.maximum_archive_bytes);
        facman::base::Sha256Hasher private_digest;
        std::array<unsigned char, 65536> block {};
        for (std::uint64_t offset = 0; result.ok() && offset < staged_archive.size();) {
            const auto count = static_cast<std::size_t>(std::min<std::uint64_t>(
                block.size(), staged_archive.size() - offset));
            if (staged_archive.read_at(offset, block.data(), count) != count ||
                private_copy.write_at(offset, block.data(), count) != count) {
                result = facman::platform::IoStatus::failure(
                    "modset_verification_failed", "private archive copy failed");
                break;
            }
            private_digest.update(block.data(), count);
            offset += count;
        }
        if (result.ok() &&
            (!staged_archive.revalidate_path().ok() || private_digest.finish() != archive_digest))
            result = facman::platform::IoStatus::failure(
                "modset_verification_failed", "private archive copy differs from verified bytes");
        if (result.ok()) {
            const std::vector<std::string> after_copy = verify_lock(instance);
            if (!after_copy.empty()) result = facman::platform::IoStatus::failure(
                "modset_verification_failed", after_copy.front());
        }
        const char* pause_private = std::getenv("FACMAN_TEST_MODSET_EXPORT_PAUSE_AFTER_PRIVATE_COPY");
        if (result.ok() && pause_private != nullptr && std::string(pause_private) == "1") {
            std::string marker_detail;
            if (!facman::base::write_text_new_atomic(
                    staging / ".facman-modset-private-copy-paused", "copied\n", marker_detail))
                result = facman::platform::IoStatus::failure(
                    "modset_verification_failed", marker_detail);
            const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(10);
            while (result.ok() &&
                !fs::exists(staging / ".facman-modset-private-copy-release") &&
                std::chrono::steady_clock::now() < deadline)
                std::this_thread::sleep_for(std::chrono::milliseconds(20));
            if (result.ok() && !fs::exists(staging / ".facman-modset-private-copy-release"))
                result = facman::platform::IoStatus::failure(
                    "modset_verification_failed", "private archive copy test pause timed out");
        }
        if (result.ok()) result = private_copy.publish_no_replace(request.output_path.filename());
#endif
        return result;
    }();
    if (!opened.ok()) {
        if (opened.code == "output_published_unverified") {
            session.require_recovery(opened.detail);
            return refuse(command, request.instance_id, "transaction_recovery_required",
                "Modset archive publication requires recovery", opened.detail, false);
        }
        (void)facman::archive::cleanup_owned_staging_root(staging);
        session.failed(opened.detail);
        const bool verification_failed = opened.code == "modset_verification_failed";
        return refuse(command, request.instance_id,
            verification_failed ? "modset_verification_failed" : "persistent_write_refused",
            verification_failed ? "Modset export no longer matches its verified lock" : "Modset archive commit failed",
            opened.detail);
    }
    if (!session.committed("modset_archive_committed")) {
        return refuse(
            command,
            request.instance_id,
            "transaction_recovery_required",
            "Modset export committed but journal update failed",
            session.detail(),
            false);
    }
    status = facman::archive::cleanup_owned_staging_root(staging);
    if (!status.ok()) {
        return refuse(command, request.instance_id, "persistent_write_refused", "Committed export staging cleanup requires review", status.code + ": " + status.detail, false);
    }
    if (!session.complete()) return refuse(command, request.instance_id, "transaction_recovery_required", "Modset export committed but journal close requires recovery", session.detail(), false);
    return ExportResult {request.instance_id, request.output_path, entries.size()};
}

std::string to_json(const ImportResult& result)
{
    return ::facman::factorio::modsets::mod_ref_json(result.mod);
}

std::string to_json(const LockResult& result)
{
    return result.lock_json;
}

std::string to_json(const VerifyResult& result)
{
    json::ArrayBuilder problems;
    for (const std::string& problem : result.problems) problems.add_string(problem);
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.modset_verify.v1");
    output.add_string("instance_id", result.instance_id);
    output.add_string("status", result.problems.empty() ? "ok" : "error");
    output.add_array("problems", problems);
    if (!result.problems.empty()) {
        json::ObjectBuilder refusal;
        refusal.add_string("schema", "common.refusal.v1");
        refusal.add_string("code", "mod_hash_mismatch");
        refusal.add_string("reason", "Locked modset verification failed");
        refusal.add_bool("recoverable", true);
        refusal.add_bool("retryable", true);
        refusal.add_string("severity", "error");
        output.add_object("refusal", refusal);
    }
    return output.serialize() + "\n";
}

std::string to_json(const ExportResult& result)
{
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.modset_export.v1");
    output.add_string("instance_id", result.instance_id);
    output.add_string("path", path_string(result.output_path));
    (void)output.add_unsigned_integer("files", result.file_count);
    return output.serialize() + "\n";
}

std::string to_json(const Refusal& refusal)
{
    const bool mod_import = refusal.command == "mods.import" && !refusal.source_path.empty();
    json::ObjectBuilder output;
    output.add_string("schema", mod_import ? "factorio.mod_refusal.v1" : "factorio.modset_refusal.v1");
    output.add_string("command", refusal.command);
    output.add_string("status", "refused");
    output.add_string("instance_id", refusal.instance_id);
    if (!refusal.file_name.empty()) {
        output.add_string("file_name", refusal.file_name);
    }
    if (mod_import) {
        output.add_string("path", path_string(refusal.source_path));
    }
    json::ObjectBuilder refusal_value;
    refusal_value.add_string("schema", "common.refusal.v1");
    refusal_value.add_string("code", refusal.code);
    refusal_value.add_string("reason", refusal.reason);
    refusal_value.add_bool("recoverable", refusal.recoverable);
    refusal_value.add_bool("retryable", refusal.recoverable);
    refusal_value.add_string("severity", "blocked");
    output.add_object("refusal", refusal_value);
    json::ObjectBuilder details;
    if (mod_import) {
        details.add_string("metadata_source", refusal.metadata_source);
    }
    details.add_string("detail", refusal.detail);
    output.add_object("details", details);
    if (!refusal.suggested_next_command.empty()) {
        output.add_string("suggested_next_command", refusal.suggested_next_command);
    }
    return output.serialize() + "\n";
}

} // namespace facman::factorio::modsets::operations
