// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_transaction.h"
#include "fl_archive.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_workspace_store.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <chrono>
#include <functional>
#include <map>

namespace facman::transaction {
namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace {
constexpr const char* strategy = "snapshot_restore_bound_install_v1";
bool refuse(std::string& detail, const std::string& text) { detail = text; return false; }
std::string text(const json::Value& object, const char* key)
{
    const auto* value = object.find(key);
    auto decoded = value ? value->string_value() : facman::core::Result<std::string>::failure({"missing", "missing", key});
    return decoded ? decoded.value() : "";
}
json::Limits binding_limits()
{
    json::Limits limits;
    limits.maximum_bytes = 128U * 1024U;
    limits.maximum_string_bytes = 64U * 1024U;
    limits.maximum_nodes = 128U;
    limits.maximum_depth = 8U;
    return limits;
}
bool object_identity(const std::string& value)
{
    const auto colon = value.find(':');
    return colon != std::string::npos && colon > 0U && colon + 1U < value.size() && value.size() <= 41U &&
        std::count(value.begin(), value.end(), ':') == 1 &&
        std::all_of(value.begin(), value.end(), [](unsigned char c) { return c == ':' || (c >= '0' && c <= '9'); });
}
bool observation_valid(const std::string& encoded)
{
    auto value = json::parse(encoded, binding_limits());
    if (!value || !value.value().is_object() || value.value().size() != 4U) return false;
    const auto* size = value.value().find("size");
    const auto n = size ? size->unsigned_integer_value() : facman::core::Result<std::uint64_t>::failure({"size", "missing", ""});
    return !text(value.value(), "path").empty() && fs::u8path(text(value.value(), "path")).is_absolute() &&
        object_identity(text(value.value(), "object")) && facman::core::Sha256Digest::parse(text(value.value(), "sha256")) &&
        n && n.value() <= 4ULL * 1024ULL * 1024ULL * 1024ULL;
}
bool file_observation(const fs::path& path, std::uint64_t maximum,
    std::string& observation, std::string& detail, std::string* captured_bytes = nullptr)
{
    if (facman::base::path_crosses_link_or_reparse_point(path, detail)) return false;
    facman::platform::StableInputFile file;
    const auto opened = file.open_no_follow_pinned(path);
    if (!opened.ok() || !file.identity().regular_file || file.identity().link_count != 1U || file.size() > maximum)
        return refuse(detail, opened.ok() ? "Restore binding file is unsafe or exceeds its bound" : opened.detail);
    facman::base::Sha256Hasher hash;
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(
        facman::archive::InstanceSnapshotPolicy::limits().maximum_read_milliseconds);
    if (captured_bytes) captured_bytes->clear();
    std::array<unsigned char, 65536> block {};
    for (std::uint64_t offset = 0; offset < file.size();) {
        if (std::chrono::steady_clock::now() > deadline) return refuse(detail, "Restore evidence read exceeded its time bound");
        const auto count = static_cast<std::size_t>(std::min<std::uint64_t>(block.size(), file.size() - offset));
        if (file.read_at(offset, block.data(), count) != count) return refuse(detail, "Restore binding file changed during read");
        hash.update(block.data(), count); offset += count;
        if (captured_bytes) captured_bytes->append(reinterpret_cast<const char*>(block.data()), count);
    }
    if (!file.revalidate_path().ok()) return refuse(detail, "Restore binding file identity changed");
    json::ObjectBuilder value;
    value.add_string("path", path.generic_u8string());
    value.add_string("object", std::to_string(file.identity().device) + ":" + std::to_string(file.identity().object));
    value.add_string("sha256", hash.finish());
    (void)value.add_unsigned_integer("size", file.size());
    observation = value.serialize();
    return true;
}
bool installation_observation(const fs::path& workspace, const std::string& id_text,
    const std::string& version, std::string& observation, std::string& detail,
    facman::workspace::InstallRecord* captured_install = nullptr)
{
    const auto id = facman::core::InstallId::parse_legacy(id_text);
    if (!id) return refuse(detail, id.error().message);
    facman::workspace::WorkspaceLayout layout(workspace);
    auto selected_path = layout.install_ref(id.value());
    if (!selected_path) return refuse(detail, selected_path.error().message);
    bool legacy = false;
    std::error_code error;
    if (!fs::is_regular_file(selected_path.value(), error) || error) {
        selected_path = layout.legacy_install_ref(id.value()); legacy = true;
    }
    if (!selected_path) return refuse(detail, selected_path.error().message);
    std::string record_before, record_bytes, executable, setup_state, base_info, base_bytes;
    if (!file_observation(selected_path.value(), 1024U * 1024U, record_before, detail, &record_bytes)) return false;
    auto install = facman::workspace::decode_install_record(id.value(), selected_path.value(), record_bytes, legacy);
    if (!install || install.value().version != version)
        return refuse(detail, "Selected restore installation is missing or version-incompatible");
    if (facman::base::path_crosses_link_or_reparse_point(install.value().root, detail)) return false;
    facman::platform::StableDirectoryObject root;
    if (!root.open_no_follow(install.value().root).ok() ||
        !file_observation(install.value().executable, 1024ULL * 1024ULL * 1024ULL, executable, detail))
        return refuse(detail, detail.empty() ? "Selected restore installation root is unavailable" : detail);
    if (!root.validate_descendant(install.value().executable).ok() ||
        !file_observation(install.value().root / "data/base/info.json", 1024U * 1024U, base_info, detail, &base_bytes))
        return refuse(detail, "Selected restore installation base metadata is unavailable or executable is outside its root");
    auto base = json::parse(base_bytes);
    if (!base || text(base.value(), "name") != "base" || text(base.value(), "version") != version)
        return refuse(detail, "Selected restore installation base version differs from the snapshot");
    if (!install.value().setup_state_ref.empty() &&
        !file_observation(fs::u8path(install.value().setup_state_ref), 16U * 1024U * 1024U, setup_state, detail)) return false;
    std::string final_record;
    if (!root.revalidate().ok() ||
        !file_observation(install.value().source_path, 4U * 1024U * 1024U, final_record, detail) || final_record != record_before)
        return refuse(detail, "Selected restore installation evidence changed during observation");
    json::ObjectBuilder value;
    value.add_string("record", record_before);
    value.add_string("root", install.value().root.generic_u8string());
    value.add_string("root_object", directory_effect_identity(root));
    value.add_string("executable", executable);
    value.add_string("base_info", base_info);
    value.add_string("setup_state", setup_state);
    observation = value.serialize();
    if (captured_install) *captured_install = install.take_value();
    return true;
}
bool context(const Record& record, json::Value& output, std::string& detail)
{
    auto parsed = json::parse(record.operation_context, binding_limits());
    if (record.command_id != "snapshots.restore" || record.commit_strategy != strategy ||
        record.sources.size() != 1U || !parsed || !parsed.value().is_object() ||
        parsed.value().size() != 7U || text(parsed.value(), "schema") != "facman.snapshot_restore_binding.v1" ||
        text(parsed.value(), "install_id").empty() || text(parsed.value(), "factorio_version").empty() ||
        text(parsed.value(), "installation").empty() || text(parsed.value(), "archive").empty())
        return refuse(detail, "Snapshot restore installation binding is missing, incomplete or incompatible");
    for (const char* key : {"schema", "install_id", "factorio_version", "installation", "archive", "original_install_id", "closure_sha256"}) {
        const auto* field = parsed.value().find(key);
        if (!field || !field->string_value()) return refuse(detail, "Snapshot restore binding member is missing or malformed");
    }
    if (text(parsed.value(), "original_install_id").empty()) return refuse(detail, "Original snapshot installation provenance is missing");
    const auto installation = json::parse(text(parsed.value(), "installation"), binding_limits());
    if (!facman::core::InstallId::parse_legacy(text(parsed.value(), "install_id")) ||
        !facman::core::InstallId::parse_legacy(text(parsed.value(), "original_install_id")) ||
        !observation_valid(text(parsed.value(), "archive")) || !installation || !installation.value().is_object() ||
        installation.value().size() != 6U || !observation_valid(text(installation.value(), "record")) ||
        !observation_valid(text(installation.value(), "executable")) || !observation_valid(text(installation.value(), "base_info")) ||
        !fs::u8path(text(installation.value(), "root")).is_absolute() || !object_identity(text(installation.value(), "root_object")) ||
        (!text(installation.value(), "setup_state").empty() && !observation_valid(text(installation.value(), "setup_state"))) ||
        (!text(parsed.value(), "closure_sha256").empty() && !facman::core::Sha256Digest::parse(text(parsed.value(), "closure_sha256"))))
        return refuse(detail, "Snapshot restore nested evidence or closure is malformed");
    for (const char* key : {"record", "executable", "base_info", "root", "root_object", "setup_state"}) {
        const auto* field = installation.value().find(key);
        if (!field || !field->is_string()) return refuse(detail, "Snapshot restore installation evidence member is malformed");
    }
    output = parsed.take_value();
    return true;
}
std::string encode(const json::Value& previous, const std::string& closure)
{
    json::ObjectBuilder value;
    for (const char* key : {"schema", "install_id", "factorio_version", "installation", "archive", "original_install_id"})
        value.add_string(key, text(previous, key));
    value.add_string("closure_sha256", closure);
    return value.serialize();
}
bool inventory(const fs::path& path, std::vector<ExpectedFile>& files,
    std::string& digest, std::string& identity, std::string& detail)
{
    if (facman::base::path_crosses_link_or_reparse_point(path, detail)) return false;
    facman::platform::StableDirectoryObject root;
    if (!root.open_no_follow(path).ok()) return refuse(detail, "Restore target directory is unavailable");
    identity = directory_effect_identity(root);
    json::ArrayBuilder entries;
    std::size_t count = 0;
    std::uint64_t bytes = 0;
    const auto limits = facman::archive::InstanceSnapshotPolicy::limits();
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(limits.maximum_read_milliseconds);
    std::function<bool(const facman::platform::StableDirectoryObject&, const std::string&, std::size_t)> scan;
    scan = [&](const facman::platform::StableDirectoryObject& directory, const std::string& prefix, std::size_t depth) {
        std::vector<fs::path> names;
        if (depth > limits.maximum_directory_depth || !directory.list_child_names_bounded(
                static_cast<std::size_t>(limits.maximum_entry_count + 3U), names).ok())
            return refuse(detail, "Restore inventory exceeds its directory bound");
        std::sort(names.begin(), names.end(), [](const fs::path& left, const fs::path& right) {
            return left.generic_u8string() < right.generic_u8string();
        });
        for (const auto& leaf : names) {
            if (std::chrono::steady_clock::now() > deadline) return refuse(detail, "Restore inventory exceeded its time bound");
            if (prefix.empty() && (leaf == facman::archive::owned_staging_marker_name() ||
                    leaf == transaction_staging_marker_name())) continue;
            if (++count > limits.maximum_entry_count) return refuse(detail, "Restore inventory exceeds its entry bound");
            const std::string relative = prefix + leaf.u8string();
            facman::platform::StableDirectoryObject child;
            if (directory.open_child_directory_no_follow(leaf, child).ok()) {
                entries.add_string("directory:" + relative);
                if (!scan(child, relative + "/", depth + 1U)) return false;
                continue;
            }
            facman::platform::StableInputFile file;
            if (!directory.open_child_file_no_follow_pinned(leaf, file).ok() ||
                !file.identity().regular_file || file.identity().link_count != 1U ||
                file.size() > limits.maximum_entry_expanded_bytes ||
                bytes > limits.maximum_total_expanded_bytes - file.size())
                return refuse(detail, "Restore inventory contains an unsafe or oversized file");
            bytes += file.size();
            facman::base::Sha256Hasher hash;
            std::array<unsigned char, 65536> block {};
            for (std::uint64_t offset = 0; offset < file.size();) {
                if (std::chrono::steady_clock::now() > deadline) return refuse(detail, "Restore inventory exceeded its time bound");
                const auto n = static_cast<std::size_t>(std::min<std::uint64_t>(block.size(), file.size() - offset));
                if (file.read_at(offset, block.data(), n) != n) return refuse(detail, "Restore inventory file changed");
                hash.update(block.data(), n); offset += n;
            }
            const auto sha = hash.finish();
            auto relative_path = RelativePath::parse(relative);
            auto sha_value = facman::core::Sha256Digest::parse(sha);
            if (!relative_path || !sha_value || !file.revalidate_path().ok()) return refuse(detail, "Restore inventory identity changed");
            files.push_back({relative_path.take_value(), sha_value.take_value(), file.size()});
            entries.add_string("file:" + relative + ":" + sha + ":" + std::to_string(file.size()));
        }
        return directory.revalidate().ok() || refuse(detail, "Restore inventory directory changed");
    };
    if (!scan(root, "", 0)) return false;
    const auto serialized = entries.serialize();
    digest = facman::base::sha256_hex_bytes(reinterpret_cast<const unsigned char*>(serialized.data()), serialized.size());
    return true;
}
} // namespace

bool bind_snapshot_restore(const fs::path& workspace, Record& record,
    const std::string& install_id, const std::string& version,
    const std::string& archive_sha256, facman::workspace::InstallRecord& captured_install, std::string& detail)
{
    if (record.sources.size() != 1U) return refuse(detail, "Restore requires one selected archive");
    std::string installation, archive;
    if (!installation_observation(workspace, install_id, version, installation, detail, &captured_install) ||
        !file_observation(record.sources.front(), facman::archive::InstanceSnapshotPolicy::limits().maximum_archive_bytes,
            archive, detail)) return false;
    const auto source = json::parse(archive, binding_limits());
    if (!source || text(source.value(), "sha256") != archive_sha256)
        return refuse(detail, "Snapshot source differs from the exact archive reader used for inspection");
    json::ObjectBuilder value;
    value.add_string("schema", "facman.snapshot_restore_binding.v1");
    value.add_string("install_id", install_id);
    value.add_string("factorio_version", version);
    value.add_string("installation", installation);
    value.add_string("archive", archive);
    value.add_string("original_install_id", record.operation_context);
    value.add_string("closure_sha256", "");
    record.operation_context = value.serialize();
    record.commit_strategy = strategy;
    return true;
}

bool verify_snapshot_restore_inputs(const fs::path& workspace, const Record& record, std::string& detail)
{
    json::Value value;
    if (!context(record, value, detail)) return false;
    std::string installation, archive;
    return (installation_observation(workspace, text(value, "install_id"), text(value, "factorio_version"), installation, detail) &&
        file_observation(record.sources.front(), facman::archive::InstanceSnapshotPolicy::limits().maximum_archive_bytes, archive, detail) &&
        installation == text(value, "installation") && archive == text(value, "archive")) ||
        refuse(detail, detail.empty() ? "Selected restore installation or source archive differs from its durable binding" : detail);
}

bool bind_snapshot_restore_target(Record& record, const fs::path& staging, std::string& detail)
{
    json::Value value;
    if (!context(record, value, detail)) return false;
    std::vector<ExpectedFile> files;
    std::string closure, identity;
    if (!inventory(staging, files, closure, identity, detail)) return false;
    record.expected_files = std::move(files);
    record.effect_file_identity = identity;
    record.operation_context = encode(value, closure);
    return true;
}

bool verify_snapshot_restore_target(const Record& record, const fs::path& target, std::string& detail)
{
    json::Value value;
    if (!context(record, value, detail) || text(value, "closure_sha256").empty() || record.effect_file_identity.empty())
        return refuse(detail, "Restore target has no complete bound inventory");
    std::vector<ExpectedFile> files;
    std::string closure, identity;
    if (!inventory(target, files, closure, identity, detail) || identity != record.effect_file_identity ||
        closure != text(value, "closure_sha256") || files.size() != record.expected_files.size())
        return refuse(detail, detail.empty() ? "Restore target identity or regenerated closure differs from the journal" : detail);
    for (std::size_t i = 0; i < files.size(); ++i)
        if (files[i].path.str() != record.expected_files[i].path.str() || files[i].sha256.str() != record.expected_files[i].sha256.str() ||
            files[i].size != record.expected_files[i].size) return refuse(detail, "Restore expected file inventory differs");
    return true;
}

std::string snapshot_restore_lock_text(const Record& record, const facman::base::StableLocalLock& lock)
{
    json::ObjectBuilder value;
    value.add_string("schema", "facman.snapshot_restore_recovery_lock.v1");
    value.add_string("identity", lock.identity_text());
    value.add_string("transaction_id", record.transaction_id);
    value.add_string("marker_nonce", record.marker_nonce);
    return value.serialize() + "\n";
}

bool snapshot_restore_lock_matches(const Record& record, const facman::base::StableLocalLock& lock,
    const facman::platform::StableDirectoryObject& parent, std::string& detail, bool expect_empty)
{
    std::string bytes;
    return (parent.open() && parent.path() == lock.path().parent_path() && parent.revalidate().ok() &&
        lock.identity_matches_path(detail) && lock.read_text(4096U, bytes, detail) &&
        bytes == (expect_empty ? std::string() : snapshot_restore_lock_text(record, lock)) &&
        lock.identity_matches_path(detail) && parent.revalidate().ok()) ||
        refuse(detail, detail.empty() ? "Snapshot restore lease metadata, object or parent changed" : detail);
}

bool initialize_snapshot_restore_lock(const Record& record, facman::base::StableLocalLock& lock,
    const facman::platform::StableDirectoryObject& parent, bool newly_created, std::string& detail)
{
    if (!snapshot_restore_lock_matches(record, lock, parent, detail, newly_created)) return false;
    // An exact orphan already has the desired bytes. Never rewrite it merely
    // because recovery obtained its kernel lock.
    return (!newly_created || lock.write_text(snapshot_restore_lock_text(record, lock), detail)) &&
        snapshot_restore_lock_matches(record, lock, parent, detail);
}

bool release_snapshot_restore_lock(const Record& record, facman::base::StableLocalLock& lock,
    const facman::platform::StableDirectoryObject& parent, std::string& detail)
{
    if (!snapshot_restore_lock_matches(record, lock, parent, detail)) { lock.close(); return false; }
    // POSIX's final compare/unlink interval remains observable; this is not an
    // atomic byte-conditioned unlink against an uncooperative namespace writer.
    return lock.remove_exact(detail);
}

bool snapshot_restore_recovery_precheck(const fs::path& workspace, const Record& record,
    bool& published, std::string& detail)
{
    published = false;
    const auto id = facman::core::InstanceId::parse(record.target.filename().u8string());
    if (!id || record.staging_roots.size() != 1U || record.target != workspace / "instances" / id.value().str() ||
        record.staging_roots.front().parent_path() != record.target.parent_path())
        return refuse(detail, "Restore journal paths are not bound to this workspace");
    if (!verify_snapshot_restore_inputs(workspace, record, detail)) return false;
    const auto present = [&](const fs::path& path, bool& exists) {
        std::error_code error;
        const auto status = fs::symlink_status(path, error);
        if (error && error != std::errc::no_such_file_or_directory) return refuse(detail, error.message());
        exists = !error && status.type() != fs::file_type::not_found;
        return true;
    };
    bool target_present = false, staging_present = false;
    if (!present(record.target, target_present) || !present(record.staging_roots.front(), staging_present)) return false;
    if (target_present) {
        if (std::find(record.completed_steps.begin(), record.completed_steps.end(), "snapshot_restore_commit_started") == record.completed_steps.end() ||
            !verify_snapshot_restore_target(record, record.target, detail)) return refuse(detail,
                detail.empty() ? "Restore destination is not the bound published object" : detail);
        published = true;
    }
    const bool prepared = record.state == State::verified || record.state == State::committing ||
        record.state == State::committed || record.state == State::audited || !record.effect_file_identity.empty();
    if (!published && prepared && !terminal(record.state) && !staging_present)
        return refuse(detail, "Verified restore staging is missing; reconstruction cannot be completed or cleaned up automatically");
    if (staging_present && prepared && !verify_snapshot_restore_target(record, record.staging_roots.front(), detail)) return false;
    return true;
}
} // namespace facman::transaction
