// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "flb_factorio_modpack_import.h"
#include "flb_factorio_instance_staging.h"
#include "fl_file_io.h"
#include "fl_directory_publication.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_transaction_pack_import.h"
#include <algorithm>
#include <array>
#include <map>
#include <set>
#include <chrono>
#include <cstdlib>
#include <thread>
namespace facman::factorio::modsets::operations {
namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace tx = facman::transaction;
namespace content = facman::factorio::content;
namespace discovery = facman::factorio::discovery;
namespace lifecycle = facman::factorio::instance;
namespace {
facman::core::Result<std::string> failure(const std::string& code, const std::string& detail,
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::refused)
{
    return facman::core::Result<std::string>::failure({code, detail, "",
        kind});
}
std::string digest(const std::string& bytes)
{
    return facman::base::sha256_hex_bytes(reinterpret_cast<const unsigned char*>(bytes.data()), bytes.size());
}
bool bind_text(tx::Record& record, const std::string& path, const std::string& bytes)
{
    auto relative = tx::RelativePath::parse(path);
    auto hash = facman::core::Sha256Digest::parse(digest(bytes));
    if (!relative || !hash) return false;
    record.expected_files.push_back({relative.take_value(), hash.take_value(), bytes.size()});
    return true;
}
bool bind_pack_source(tx::Record& record, const pack_import::Source& source,
    const PackImportRequest& request, std::string& detail)
{
    auto installed = json::parse(record.operation_context);
    if (!installed || !installed.value().is_object()) {
        detail = "Import installation binding is unavailable"; return false;
    }
    json::ObjectBuilder binding;
    for (const auto& key : installed.value().object_keys()) {
        const auto* value = installed.value().find(key);
        if (!value || !binding.add_value(key, *value)) {
            detail = "Import installation binding could not be retained"; return false;
        }
    }
    json::ObjectBuilder source_binding;
    source_binding.add_string("schema", "facman.modpack_import_source.v1");
    source_binding.add_string("archive_sha256", source.archive_sha256);
    (void)source_binding.add_unsigned_integer("archive_size", source.plan.archive_size);
    source_binding.add_string("manifest_sha256", digest(source.manifest_json));
    source_binding.add_string("lock_sha256", digest(source.lock_json));
    source_binding.add_string("instance_id", request.instance_id);
    source_binding.add_string("install_id", request.install_id);
    source_binding.add_string("display_name", request.display_name.empty() ? source.manifest.name : request.display_name);
    binding.add_object("source_binding", source_binding);
    const auto context = binding.serialize();
    if (context.size() > 256U * 1024U) {
        detail = "Import source binding exceeds the journal budget"; return false;
    }
    for (const auto& file : source.files) {
        auto relative = tx::RelativePath::parse(file.path);
        auto hash = facman::core::Sha256Digest::parse(file.sha256);
        if (!relative || !hash) { detail = "Unsafe import source inventory"; return false; }
        record.expected_files.push_back({relative.take_value(), hash.take_value(), file.bytes});
    }
    record.operation_context = context;
    record.completed_steps.push_back("pack_source_inventory_bound");
    return true;
}
bool pause(const fs::path& workspace, const char* point)
{
    const char* requested = std::getenv("FACMAN_TEST_MODPACK_IMPORT_PAUSE");
    if (!requested || std::string(requested) != point) return true;
    std::string detail;
    const auto signal = workspace / (std::string(".facman-modpack-import-") + point + "-paused");
    const auto release = workspace / (std::string(".facman-modpack-import-") + point + "-release");
    if (!facman::base::write_text_new_atomic(signal, "paused\n", detail)) return false;
    for (unsigned i = 0; i != 600U; ++i) {
        if (fs::exists(release)) return true;
        std::this_thread::sleep_for(std::chrono::milliseconds(50));
    }
    return false;
}
bool has_step(const tx::Record& record, const char* step)
{
    return std::find(record.completed_steps.begin(), record.completed_steps.end(), step) != record.completed_steps.end();
}
struct RecoveryPackSource {
    pack_import::Source source;
    PackImportRequest request;
    facman::platform::StableDirectoryObject staging, parent, installation, workspace_root;
    std::vector<facman::archive::VerifiedEntry> markers;
    std::vector<facman::platform::StableInputFile> held_markers, held_install_metadata;
    std::vector<std::string> install_metadata_hashes;
    std::chrono::steady_clock::time_point verify_until = std::chrono::steady_clock::now() +
        std::chrono::milliseconds(facman::archive::Limits().maximum_read_milliseconds);
};

bool exact_fields(const json::Value& value, const std::set<std::string>& expected)
{
    if (!value.is_object()) return false;
    const auto keys = value.object_keys();
    return std::set<std::string>(keys.begin(), keys.end()) == expected;
}
bool bound_string(const json::Value& object, const char* key, std::string& output)
{
    const auto* value = object.find(key);
    if (!value || !value->string_value()) return false;
    output = value->string_value().value();
    return true;
}
// Owner-only strict admission. Legacy transaction parsing remains unchanged.
bool read_strict_import_record(const fs::path& workspace, const std::string& id,
    tx::Record& output, std::string& detail)
{
    auto identifier = facman::core::TransactionId::parse(id);
    if (!identifier) { detail = "Invalid import transaction id"; return false; }
    auto path = facman::workspace::TransactionRepository(facman::workspace::WorkspaceLayout(workspace)).journal(identifier.value());
    if (!path || facman::base::path_crosses_link_or_reparse_point(path.value(), detail)) return false;
    facman::platform::StableInputFile file;
    if (!file.open_no_follow_pinned(path.value()).ok() || !file.identity().regular_file ||
        file.identity().link_count != 1U || file.size() > 1024U * 1024U) {
        detail = "Import journal is not a bounded pinned plain file"; return false;
    }
    std::string bytes(static_cast<std::size_t>(file.size()), '\0');
    if (file.read_at(0, bytes.data(), bytes.size()) != bytes.size()) { detail = "Import journal short read"; return false; }
    json::Limits limits; limits.maximum_bytes = 1024U * 1024U; limits.maximum_depth = 24U; limits.maximum_nodes = 20000U;
    auto parsed = json::parse(bytes, limits);
    if (!parsed || !exact_fields(parsed.value(), {"schema", "transaction_id", "command_id", "workspace_id", "marker_nonce",
        "target", "source_identities", "created_utc", "updated_utc", "state", "completed_steps", "owned_staging_roots",
        "expected_files", "commit_strategy", "operation_context", "effect_parent_identity", "effect_file_identity", "error", "recovery_actions"})) {
        detail = "Import journal fields are unsupported"; return false;
    }
    const auto* inventory = parsed.value().find("expected_files");
    if (!inventory || !inventory->is_array() || inventory->size() > 3004U) {
        detail = "Import raw inventory is malformed or oversized"; return false;
    }
    // Validate numeric types/ranges before the maintained compatibility loader
    // can perform a floating-point-to-integer conversion.
    for (std::size_t index = 0; index < inventory->size(); ++index) {
        const auto* item = inventory->at(index);
        const auto* size = item ? item->find("size") : nullptr;
        if (!item || !exact_fields(*item, {"path", "sha256", "size"}) || !size || !size->unsigned_integer_value() ||
            size->unsigned_integer_value().value() > facman::archive::Limits().maximum_entry_expanded_bytes) {
            detail = "Import inventory requires bounded exact unsigned sizes"; return false;
        }
    }
    tx::Record current;
    if (!tx::read_record(workspace, id, current, detail) || !file.revalidate_path().ok() ||
        inventory->size() != current.expected_files.size()) return false;
    for (std::size_t index = 0; index < inventory->size(); ++index) {
        const auto* item = inventory->at(index);
        std::string relative, hash;
        const auto* size = item ? item->find("size") : nullptr;
        if (!item || !exact_fields(*item, {"path", "sha256", "size"}) || !bound_string(*item, "path", relative) ||
            !bound_string(*item, "sha256", hash) || !size || !size->unsigned_integer_value() ||
            relative != current.expected_files[index].path.str() || hash != current.expected_files[index].sha256.str() ||
            size->unsigned_integer_value().value() != current.expected_files[index].size) {
            detail = "Import inventory requires exact integer sizes and supported fields"; return false;
        }
    }
    auto owned_workspace = facman::workspace::WorkspaceRepository(facman::workspace::WorkspaceLayout(workspace)).load();
    if (!owned_workspace || current.workspace_id != owned_workspace.value().id.str()) {
        detail = "Import journal belongs to a different workspace identity"; return false;
    }
    output = std::move(current);
    return true;
}

bool retain_authenticated_marker(RecoveryPackSource& result, const char* leaf,
    const std::string* exact, std::string& detail)
{
    facman::platform::StableInputFile input;
    if (!result.staging.open_child_file_no_follow_pinned(leaf, input).ok() ||
        !input.identity().regular_file || input.identity().link_count != 1U || input.size() > 65536U) {
        detail = "Recovery ownership marker is not a bounded pinned plain file"; return false;
    }
    std::string bytes(static_cast<std::size_t>(input.size()), '\0');
    if (input.read_at(0, bytes.data(), bytes.size()) != bytes.size() ||
        (exact && bytes != *exact) || !input.revalidate_path().ok()) {
        detail = "Recovery ownership marker bytes changed"; return false;
    }
    result.markers.push_back({leaf, bytes.size(), digest(bytes)});
    result.held_markers.push_back(std::move(input));
    return true;
}


bool retain_owned_pack_stage(const tx::Record& record, RecoveryPackSource& owner, std::string& detail)
{
    if (!owner.staging.open_no_follow_for_relative_writes(record.staging_roots.front()).ok() ||
        tx::directory_effect_identity(owner.staging) != record.effect_file_identity) {
        detail = "Recovery staging differs from its exclusively created directory"; return false;
    }
    const std::string archive_marker = "schema=facman.archive_staging.v1\n";
    return retain_authenticated_marker(owner, facman::archive::owned_staging_marker_name(), &archive_marker, detail) &&
        retain_authenticated_marker(owner, tx::transaction_staging_marker_name(), nullptr, detail) &&
        tx::verify_staging_ownership(record, owner.staging.path(), detail);
}
bool before_pack_staging_creation(const tx::Record& record)
{
    if (!record.effect_file_identity.empty()) return false;
    const std::vector<std::vector<std::string>> early_prefixes {
        {"pack_source_inventory_bound"},
        {"pack_source_inventory_bound", "request_validated"},
        {"pack_source_inventory_bound", "recovery_source_validated"},
        {"pack_source_inventory_bound", "request_validated", "target_and_sources_validated"},
        {"pack_source_inventory_bound", "request_validated", "recovery_source_planned"},
        {"pack_source_inventory_bound", "recovery_source_validated", "recovery_source_planned"}};
    if (std::find(early_prefixes.begin(), early_prefixes.end(), record.completed_steps) == early_prefixes.end()) return false;
    const auto count = record.completed_steps.size();
    return (record.state == tx::State::requested && count == 1U) ||
        (record.state == tx::State::validated && count == 2U) ||
        (record.state == tx::State::planned && count == 3U) || record.state == tx::State::recovery_required;
}

bool retain_install_custody(const fs::path& workspace, const tx::Record& record,
    RecoveryPackSource& owner, std::string& detail)
{
    json::Limits limits; limits.maximum_bytes = 256U * 1024U; limits.maximum_depth = 24U; limits.maximum_nodes = 20000U;
    auto parsed = json::parse(record.operation_context, limits);
    const auto* files = parsed ? parsed.value().find("files") : nullptr;
    if (!files || !files->is_array() || !files->size() || files->size() > 4097U) {
        detail = "Original installation metadata custody is unavailable"; return false;
    }
    auto retain = [&](const fs::path& path, const std::string* expected_hash, std::uint64_t expected_size) {
        if (facman::base::path_crosses_link_or_reparse_point(path, detail)) return false;
        facman::platform::StableInputFile input;
        if (!input.open_no_follow_pinned(path).ok() || !input.identity().regular_file || input.identity().link_count != 1U ||
            input.size() > 16U * 1024U * 1024U || (expected_hash && input.size() != expected_size)) {
            detail = "Original install metadata is not a bound plain file"; return false;
        }
        facman::base::Sha256Hasher hash;
        std::array<unsigned char, 65536> block {};
        for (std::uint64_t offset = 0; offset < input.size();) {
            if (std::chrono::steady_clock::now() > owner.verify_until) { detail = "Installation admission deadline exceeded"; return false; }
            const auto count = static_cast<std::size_t>(std::min<std::uint64_t>(block.size(), input.size() - offset));
            if (input.read_at(offset, block.data(), count) != count) { detail = "Installation metadata short read"; return false; }
            hash.update(block.data(), count); offset += count;
        }
        const auto actual = hash.finish();
        if ((expected_hash && actual != *expected_hash) || !input.revalidate_path().ok()) {
            detail = "Original installation metadata changed"; return false;
        }
        owner.install_metadata_hashes.push_back(actual);
        owner.held_install_metadata.push_back(std::move(input));
        return true;
    };
    for (std::size_t index = 0; index < files->size(); ++index) {
        const auto* item = files->at(index);
        std::string path, hash;
        const auto* size = item ? item->find("size") : nullptr;
        if (!item || !exact_fields(*item, {"path", "sha256", "size"}) || !bound_string(*item, "path", path) ||
            !bound_string(*item, "sha256", hash) || !size || !size->unsigned_integer_value() ||
            !retain(facman::platform::path_from_utf8(path), &hash, size->unsigned_integer_value().value())) return false;
    }
    // Keep the already compared current workspace identity stable through effects.
    const auto manifest = facman::workspace::WorkspaceLayout(workspace).manifest();
    if (!retain(manifest, nullptr, 0U)) return false;
    auto current = facman::workspace::WorkspaceRepository(facman::workspace::WorkspaceLayout(workspace)).load();
    if (!current || current.value().id.str() != record.workspace_id) {
        detail = "Original workspace identity changed"; return false;
    }
    return true;
}
bool verify_install_custody(const RecoveryPackSource& owner, std::string& detail, bool hash_content = false)
{
    if (owner.held_install_metadata.empty()) { detail = "Installation metadata is not held"; return false; }
    for (std::size_t index = 0; index < owner.held_install_metadata.size(); ++index) {
        const auto& input = owner.held_install_metadata[index];
        if (!input.revalidate_path().ok()) { detail = "Installation metadata object changed"; return false; }
        if (!hash_content) continue;
        facman::base::Sha256Hasher hash;
        std::array<unsigned char, 65536> block {};
        for (std::uint64_t offset = 0; offset < input.size();) {
            if (std::chrono::steady_clock::now() > owner.verify_until) { detail = "Installation verification deadline exceeded"; return false; }
            const auto count = static_cast<std::size_t>(std::min<std::uint64_t>(block.size(), input.size() - offset));
            if (input.read_at(offset, block.data(), count) != count) { detail = "Installation metadata short read"; return false; }
            hash.update(block.data(), count); offset += count;
        }
        if (hash.finish() != owner.install_metadata_hashes[index] || !input.revalidate_path().ok()) {
            detail = "Installation metadata bytes changed"; return false;
        }
    }
    return true;
}

// The operation-specific caller must already hold the existing recovery lock
// and reread this record under that lock before calling this read-only helper.
bool inspect_partial_pack_authority(const fs::path& workspace, const tx::Record& record,
    RecoveryPackSource& result, std::string& detail)
{
    auto unsafe = [&](const char* message) { detail = message; return false; };
    if (record.schema_version != 2U || record.command_id != "modsets.import" ||
        record.commit_strategy != "modpack_instance_no_replace_v1" || record.sources.size() != 2U ||
        record.staging_roots.size() != 1U ||
        (!before_pack_staging_creation(record) && record.state != tx::State::staging && record.state != tx::State::recovery_required) ||
        std::find(record.completed_steps.begin(), record.completed_steps.end(), "pack_source_inventory_bound") == record.completed_steps.end() ||
        std::find(record.completed_steps.begin(), record.completed_steps.end(), "pack_inventory_bound") != record.completed_steps.end())
        return unsafe("This is not an original-source-bound incomplete pack import");
    json::Limits bounds;
    bounds.maximum_bytes = 256U * 1024U;
    bounds.maximum_depth = 24U;
    bounds.maximum_nodes = 20000U;
    auto context = json::parse(record.operation_context, bounds);
    if (!context || !exact_fields(context.value(), {"schema", "install_id", "root_identity", "files", "source_binding"}))
        return unsafe("Recovery installation/source binding has unsupported fields");
    std::string schema, install_id, root_identity;
    if (!bound_string(context.value(), "schema", schema) || schema != "facman.modpack_import_install.v1" ||
        !bound_string(context.value(), "install_id", install_id) ||
        !bound_string(context.value(), "root_identity", root_identity) || root_identity.empty())
        return unsafe("Recovery installation binding is malformed");
    const auto* binding = context.value().find("source_binding");
    if (!binding || !exact_fields(*binding, {"schema", "archive_sha256", "archive_size", "manifest_sha256",
            "lock_sha256", "instance_id", "install_id", "display_name"}))
        return unsafe("Recovery source binding has unsupported fields");
    std::string archive_hash, manifest_hash, lock_hash, source_install;
    if (!bound_string(*binding, "schema", schema) || schema != "facman.modpack_import_source.v1" ||
        !bound_string(*binding, "archive_sha256", archive_hash) ||
        !bound_string(*binding, "manifest_sha256", manifest_hash) ||
        !bound_string(*binding, "lock_sha256", lock_hash) ||
        !bound_string(*binding, "instance_id", result.request.instance_id) ||
        !bound_string(*binding, "install_id", source_install) || source_install != install_id ||
        !bound_string(*binding, "display_name", result.request.display_name) ||
        result.request.display_name.empty() || result.request.display_name.size() > 128U)
        return unsafe("Recovery source request is malformed");
    auto instance = facman::core::InstanceId::parse(result.request.instance_id);
    auto installed = facman::core::InstallId::parse_legacy(install_id);
    const auto* archive_size = binding->find("archive_size");
    if (!instance || !installed || !archive_size || !archive_size->unsigned_integer_value() ||
        record.target != workspace / "instances" / instance.value().str() ||
        record.staging_roots.front() != workspace / (".facman-pack-import-" + instance.value().str()) ||
        record.sources.front() != fs::absolute(record.sources.front()).lexically_normal())
        return unsafe("Recovery request paths are not bound to this workspace");
    result.request.install_id = install_id;
    result.request.source_path = record.sources.front();
    auto inspected = pack_import::inspect(result.request.source_path);
    if (!inspected) { detail = inspected.error().message; return false; }
    result.source = inspected.take_value();
    const auto& source = result.source;
    if (source.archive_sha256 != archive_hash || source.plan.archive_size != archive_size->unsigned_integer_value().value() ||
        digest(source.manifest_json) != manifest_hash || digest(source.lock_json) != lock_hash ||
        record.expected_files.size() != source.files.size() + (has_step(record, "pack_generated_inventory_bound") ? 4U : 0U) || source.files.size() > 3000U)
        return unsafe("Original pack or source inventory differs from its durable binding");
    std::map<std::string, const tx::ExpectedFile*> expected;
    for (const auto& file : record.expected_files)
        if (!expected.emplace(file.path.str(), &file).second)
            return unsafe("Recovery source inventory is duplicated");
    std::size_t estimated_bytes = 0;
    for (const auto& file : source.files) {
        estimated_bytes += file.path.size() + 160U;
        const auto found = expected.find(file.path);
        if (found == expected.end() || found->second->sha256.str() != file.sha256 || found->second->size != file.bytes)
            return unsafe("Recovery inventory no longer equals the original selected pack");
    }
    const std::set<std::string> generated_paths {"mods/modset-lock.v1.json", "instance.v1.json", "config/config.ini", "modpack-import.v1.json"};
    for (const auto& item : expected) {
        const bool raw = std::any_of(source.files.begin(), source.files.end(), [&](const facman::archive::VerifiedEntry& file) { return file.path == item.first; });
        if (!raw && (!has_step(record, "pack_generated_inventory_bound") || !generated_paths.count(item.first)))
            return unsafe("Import inventory contains an unbound generated path");
    }
    if (estimated_bytes > 512U * 1024U) return unsafe("Recovery inventory exceeds the existing journal bound");
    facman::workspace::WorkspaceLayout layout(workspace);
    auto registration = facman::workspace::InstallRepository(layout).load(installed.value());
    auto inventory = facman::factorio::mods::local_inventory(workspace);
    if (!registration || !inventory || registration.value().version != source.manifest.content_lock.factorio_version ||
        !tx::verify_pack_import_install(record, workspace, detail))
        return unsafe("Original local installation no longer matches the pack");
    std::set<fs::path> metadata {registration.value().source_path};
    for (const auto& selected : source.manifest.content_lock.entries) {
        if (!selected.virtual_package) continue;
        const auto found = std::find_if(inventory.value().begin(), inventory.value().end(), [&](const ModRef& mod) {
            return mod.virtual_package && mod.valid && mod.source == "install-data:" + install_id &&
                mod.name == selected.name && mod.version == selected.version && mod.file_name == selected.file_name;
        });
        if (found == inventory.value().end()) return unsafe("A selected built-in package is unavailable");
        metadata.insert(found->file_path / "info.json");
    }
    const auto* files = context.value().find("files");
    if (!files || !files->is_array() || files->size() != metadata.size())
        return unsafe("Original install binding omits or adds selected metadata");
    std::set<fs::path> actual_metadata;
    for (std::size_t index = 0; index < files->size(); ++index) {
        const auto* file = files->at(index);
        std::string path, hash;
        if (!file || !exact_fields(*file, {"path", "sha256", "size"}) ||
            !bound_string(*file, "path", path) || !bound_string(*file, "sha256", hash) ||
            !actual_metadata.insert(facman::platform::path_from_utf8(path)).second)
            return unsafe("Original install metadata fields are malformed or duplicated");
    }
    if (actual_metadata != metadata) return unsafe("Original install binding differs from selected metadata");
    if (!retain_install_custody(workspace, record, result, detail)) return false;
    if (facman::base::path_crosses_link_or_reparse_point(workspace, detail) ||
        facman::base::path_crosses_link_or_reparse_point(record.target.parent_path(), detail) ||
        facman::base::path_crosses_link_or_reparse_point(record.staging_roots.front(), detail) ||
        facman::base::path_crosses_link_or_reparse_point(registration.value().root, detail)) return false;
    facman::platform::PathIdentity target;
    if (!facman::platform::inspect_path_no_follow(record.target, target).ok() || target.exists ||
        !result.parent.open_no_follow(record.target.parent_path()).ok() ||
        tx::directory_effect_identity(result.parent) != record.effect_parent_identity ||
        !result.installation.open_no_follow(registration.value().root).ok() ||
        tx::directory_effect_identity(result.installation) != root_identity)
        return unsafe("Recovery target, parent or installation directory identity differs");
    if (before_pack_staging_creation(record)) {
        facman::platform::PathIdentity staging;
        if (!facman::platform::inspect_path_no_follow(record.staging_roots.front(), staging).ok() || staging.exists ||
            !result.workspace_root.open_no_follow_for_relative_writes(workspace).ok())
            return unsafe("Unbound import staging must be absent; existing objects are never adopted");
    } else if (!retain_owned_pack_stage(record, result, detail)) return false;
    return result.parent.revalidate().ok() && (result.staging.open() ? result.staging.revalidate().ok() : result.workspace_root.revalidate().ok()) &&
        result.installation.revalidate().ok() &&
        verify_install_custody(result, detail, true) && tx::verify_pack_import_install(record, workspace, detail) &&
        std::chrono::steady_clock::now() <= result.verify_until;
}

bool create_bound_missing_pack_stage(const fs::path& workspace, tx::Record& record,
    RecoveryPackSource& owner, std::string& detail)
{
    if (!before_pack_staging_creation(record) || !owner.workspace_root.revalidate().ok() ||
        !owner.parent.revalidate().ok() || !owner.installation.revalidate().ok() ||
        !verify_install_custody(owner, detail, true) || !tx::verify_pack_import_install(record, workspace, detail)) return false;
    if (!pause(workspace, "recovery-precreate")) { detail = "Recovery paused before exclusive staging creation"; return false; }
    // Reuse the original validated source and existing exclusively-created archive
    // staging implementation. A concurrent directory is refused, never marked.
    facman::platform::PathIdentity staging;
    if (!owner.workspace_root.revalidate().ok() || !owner.parent.revalidate().ok() ||
        !verify_install_custody(owner, detail, true) ||
        !facman::platform::inspect_path_no_follow(record.staging_roots.front(), staging).ok() || staging.exists) {
        detail = "Recovery staging appeared before exclusive creation; all existing data retained"; return false;
    }
    if (record.state == tx::State::requested && !tx::advance(workspace, record, "validated", "recovery_source_validated", detail)) return false;
    if (record.state == tx::State::validated && !tx::advance(workspace, record, "planned", "recovery_source_planned", detail)) return false;
    const auto extracted = facman::archive::extract_verified_to_new_retained_staging(owner.source.plan,
        record.staging_roots.front(), facman::archive::Limits(), owner.source.files,
        [&](std::uint32_t, const char* point) {
            if (!owner.workspace_root.revalidate().ok() || !owner.parent.revalidate().ok() ||
                !owner.installation.revalidate().ok() || !verify_install_custody(owner, detail)) return false;
            if (std::string(point) == "root_ready") {
                facman::platform::StableDirectoryObject created;
                if (!created.open_no_follow(record.staging_roots.front()).ok()) return false;
                record.effect_file_identity = tx::directory_effect_identity(created);
                if (record.effect_file_identity.empty() || !created.revalidate().ok()) return false;
                // Preserve recovery_required rather than changing the shared state
                // machine. Its existing incomplete-import owner accepts that phase.
                return record.state == tx::State::recovery_required ?
                    tx::checkpoint(workspace, record, "pack_extraction_started", detail) :
                    tx::advance(workspace, record, "staging", "pack_extraction_started", detail);
            }
            if (std::string(point) == "after_entry" && !pause(workspace, "extracted-entry")) return false;
            const char* fault = std::getenv("FACMAN_TEST_MODPACK_IMPORT_EXTRACT_FAULT");
            return !(fault && std::string(fault) == point);
        });
    if (!extracted.ok()) { detail = extracted.detail; return false; }
    return owner.workspace_root.revalidate().ok() && retain_owned_pack_stage(record, owner, detail) &&
        verify_install_custody(owner, detail, true) && tx::verify_pack_import_install(record, workspace, detail);
}

using GeneratedFiles = std::vector<std::pair<std::string, std::string>>;
const std::vector<std::string> pack_directories {"config", "mods", "saves", "scenarios", "script-output",
    "logs", "crash", "exports", "cache", "locks"};
GeneratedFiles generated_pack_files(const facman::workspace::InstanceRecord& instance,
    const discovery::InstallRef& install, const pack_import::Source& source, const std::vector<ModRef>& selected)
{
    const auto target_lock = pack_import::target_lock_json(instance.id.str(), instance.factorio_version, selected);
    json::ObjectBuilder receipt;
    receipt.add_string("schema", "factorio.modpack_import.v1");
    receipt.add_string("command", "modsets.import");
    receipt.add_string("instance_id", instance.id.str());
    receipt.add_string("install_ref", instance.install_ref.str());
    receipt.add_string("source_instance_id", source.manifest.content_lock.instance_id);
    receipt.add_string("archive_sha256", source.archive_sha256);
    (void)receipt.add_unsigned_integer("archive_size", source.plan.archive_size);
    receipt.add_string("source_manifest_sha256", digest(source.manifest_json));
    receipt.add_string("source_lock_sha256", digest(source.lock_json));
    receipt.add_string("target_lock_sha256", digest(target_lock));
    receipt.add_string("modpack_manifest_sha256", content::modpack_manifest_identity(source.manifest));
    receipt.add_string("path", facman::platform::path_to_utf8(instance.root));
    receipt.add_bool("offline", true);
    return {{"mods/modset-lock.v1.json", target_lock}, {"instance.v1.json", lifecycle::instance_manifest_json(instance)},
        {"config/config.ini", lifecycle::instance_effective_config(instance, install)},
        {"modpack-import.v1.json", receipt.serialize() + "\n"}};
}
bool generated_inventory_matches(const tx::Record& record, const pack_import::Source& source,
    const GeneratedFiles& generated, std::string& detail)
{
    if (record.expected_files.size() != source.files.size() + generated.size()) {
        detail = "Generated import inventory is incomplete"; return false;
    }
    for (const auto& file : generated) {
        const auto found = std::find_if(record.expected_files.begin(), record.expected_files.end(), [&](const tx::ExpectedFile& item) {
            return item.path.str() == file.first;
        });
        if (found == record.expected_files.end() || found->sha256.str() != digest(file.second) || found->size != file.second.size()) {
            detail = "Generated intent differs from the original request and selected content"; return false;
        }
    }
    return true;
}
bool bind_generated_intent(const fs::path& workspace, tx::Record& record,
    const pack_import::Source& source, const GeneratedFiles& generated, std::string& detail)
{
    if (has_step(record, "pack_generated_inventory_bound"))
        return generated_inventory_matches(record, source, generated, detail);
    if (record.expected_files.size() != source.files.size()) {
        detail = "Unrecognized inventory precedes generated intent"; return false;
    }
    auto candidate = record;
    for (const auto& file : generated) if (!bind_text(candidate, file.first, file.second)) {
        detail = "Generated inventory path or digest is unsafe"; return false;
    }
    // Persist all generated bytes' identities before creating any layout or file.
    if (!tx::checkpoint(workspace, candidate, "pack_generated_inventory_bound", detail)) return false;
    record = std::move(candidate);
    return true;
}
bool retain_pack_file(facman::platform::StableDirectoryObject& root,
    const facman::archive::VerifiedEntry& expected,
    std::vector<facman::platform::StableInputFile>& pins, std::string& detail,
    const std::chrono::steady_clock::time_point& deadline)
{
    const fs::path relative = fs::u8path(expected.path);
    facman::platform::StableDirectoryObject parent;
    auto* directory = &root;
    if (!relative.parent_path().empty()) {
        if ((relative.parent_path() != "mods" && relative.parent_path() != "config") ||
            !root.open_child_directory_no_follow(relative.parent_path(), parent).ok()) {
            detail = "Import file parent is unsafe"; return false;
        }
        directory = &parent;
    }
    facman::platform::StableInputFile input;
    if (!directory->open_child_file_no_follow_pinned(relative.filename(), input).ok() ||
        !input.identity().regular_file || input.identity().link_count != 1U || input.size() != expected.bytes) {
        detail = "Retained import file is incomplete or changed: " + expected.path; return false;
    }
    facman::base::Sha256Hasher hash;
    std::array<unsigned char, 65536> block {};
    for (std::uint64_t offset = 0; offset < input.size();) {
        if (std::chrono::steady_clock::now() > deadline) { detail = "Import verification deadline exceeded"; return false; }
        const auto count = static_cast<std::size_t>(std::min<std::uint64_t>(block.size(), input.size() - offset));
        if (input.read_at(offset, block.data(), count) != count) { detail = "Import file short read"; return false; }
        hash.update(block.data(), count); offset += count;
    }
    if (hash.finish() != expected.sha256 || !input.revalidate_path().ok() || !directory->revalidate().ok()) {
        detail = "Retained import digest changed: " + expected.path; return false;
    }
    pins.push_back(std::move(input));
    return true;
}
bool complete_generated_files(const fs::path& workspace, const tx::Record& record,
    RecoveryPackSource& owner, const pack_import::Source& source,
    const GeneratedFiles& generated, std::string& detail)
{
    if (owner.held_install_metadata.empty() && !retain_install_custody(workspace, record, owner, detail)) return false;
    if (!verify_install_custody(owner, detail, true)) return false;
    std::vector<facman::platform::StableInputFile> pins;
    // Generation is permitted only after every original archive entry is complete.
    for (const auto& file : source.files) if (!retain_pack_file(owner.staging, file, pins, detail, owner.verify_until)) return false;
    auto retained = owner.markers;
    std::set<std::string> present;
    for (const auto& file : generated) {
        facman::platform::PathIdentity found;
        if (!facman::platform::inspect_path_no_follow(owner.staging.path() / fs::u8path(file.first), found).ok()) {
            detail = "Generated file path cannot be inspected"; return false;
        }
        if (!found.exists) continue;
        facman::archive::VerifiedEntry expected {file.first, file.second.size(), digest(file.second)};
        if (!retain_pack_file(owner.staging, expected, pins, detail, owner.verify_until)) return false;
        retained.push_back(std::move(expected)); present.insert(file.first);
    }
    std::map<std::string, facman::platform::StableDirectoryObject> directories;
    for (const auto& name : pack_directories) {
        facman::platform::PathIdentity found;
        if (!facman::platform::inspect_path_no_follow(owner.staging.path() / name, found).ok()) {
            detail = "Import directory cannot be inspected"; return false;
        }
        if (found.exists && !owner.staging.open_child_directory_no_follow_for_relative_writes(name, directories[name]).ok()) {
            detail = "Existing import directory is unsafe"; return false;
        }
    }
    for (const auto& pin : pins) if (!pin.revalidate_path().ok()) { detail = "Pinned import data changed"; return false; }
    const auto checked = facman::archive::extract_verified_missing_to_retained_staging(source.plan, owner.staging,
        facman::archive::Limits(), source.files, retained, pack_directories);
    if (!checked.ok()) { detail = checked.detail; return false; }
    std::map<std::string, facman::platform::FileIdentity> objects;
    for (std::size_t i = 0; i < source.files.size(); ++i) objects.emplace(source.files[i].path, pins[i].identity());
    for (std::size_t i = 0; i < owner.markers.size(); ++i) objects.emplace(owner.markers[i].path, owner.held_markers[i].identity());
    for (std::size_t i = owner.markers.size(); i < retained.size(); ++i)
        objects.emplace(retained[i].path, pins[source.files.size() + i - owner.markers.size()].identity());
    const auto deadline = owner.verify_until;
    auto audit = [&]() {
        if (!owner.staging.revalidate().ok() || std::chrono::steady_clock::now() > deadline) {
            detail = "Import directory changed or generation deadline exceeded"; return false;
        }
        for (const auto& pin : pins) if (!pin.revalidate_path().ok()) { detail = "Pinned import data changed"; return false; }
        if (!verify_install_custody(owner, detail)) return false;
        std::set<std::string> files_found, dirs_found;
        auto scan = [&](const facman::platform::StableDirectoryObject& directory, const std::string& prefix) {
            std::vector<fs::path> names;
            if (!directory.list_child_names_bounded(objects.size() + pack_directories.size(), names).ok()) return false;
            for (const auto& leaf : names) {
                if (std::chrono::steady_clock::now() > deadline) return false;
                const auto path = prefix + leaf.u8string();
                if (prefix.empty() && directories.count(path)) {
                    const auto& held = directories.at(path);
                    facman::platform::StableDirectoryObject current;
                    if (!held.revalidate().ok() || !directory.open_child_directory_no_follow(leaf, current).ok() ||
                        current.identity().device != held.identity().device || current.identity().object != held.identity().object) return false;
                    dirs_found.insert(path); continue;
                }
                const auto expected = objects.find(path);
                facman::platform::StableInputFile input;
                if (expected == objects.end() || !directory.open_child_file_no_follow_pinned(leaf, input).ok() ||
                    !input.identity().unchanged(expected->second) || !input.revalidate_path().ok()) return false;
                files_found.insert(path);
            }
            return directory.revalidate().ok();
        };
        if (!scan(owner.staging, "")) { detail = "Unrecognized or changed import entry"; return false; }
        for (const auto& item : directories) if (!scan(item.second, item.first + "/")) {
            detail = "Unrecognized or changed import layout entry"; return false;
        }
        if (files_found.size() != objects.size() || dirs_found.size() != directories.size()) {
            detail = "Import data disappeared during generation"; return false;
        }
        return true;
    };
    for (const auto& name : pack_directories) {
        if (directories.count(name)) continue;
        if (!audit()) return false;
        auto& directory = directories[name];
        const auto status = owner.staging.create_child_directory_exclusive_utf8(name, directory);
        if (!status.ok()) { detail = status.detail; return false; }
    }
    for (const auto& file : generated) {
        if (present.count(file.first)) continue;
        if (!audit()) return false;
        const auto relative = fs::u8path(file.first);
        auto* parent = relative.parent_path().empty() ? &owner.staging : &directories.at(relative.parent_path().u8string());
        facman::platform::DurableOutputFile output;
        auto status = parent->create_child_file_exclusive_utf8(relative.filename().u8string(), file.second.size(), output);
        if (!status.ok()) { detail = status.detail; return false; }
        const auto created = output.identity();
        if (output.write_at(0, file.second.data(), file.second.size()) != file.second.size() || !output.flush_file_and_parent().ok()) {
            detail = "Generated import file could not be durably written"; return false;
        }
        facman::archive::VerifiedEntry expected {file.first, file.second.size(), digest(file.second)};
        if (!retain_pack_file(owner.staging, expected, pins, detail, owner.verify_until)) return false;
        if (pins.back().identity().device != created.device || pins.back().identity().object != created.object) {
            detail = "Generated file differs from its exclusively created object"; return false;
        }
        objects.emplace(file.first, pins.back().identity());
        retained.push_back(std::move(expected)); present.insert(file.first);
        if (!pause(workspace, "generated-entry")) { detail = "Generated entry paused"; return false; }
        const char* fault = std::getenv("FACMAN_TEST_MODPACK_IMPORT_GENERATE_FAULT");
        if (fault && std::string(fault) == "after_entry") {
            detail = "Generated import interrupted after a durable file"; return false;
        }
    }
    return audit() && verify_install_custody(owner, detail, true) && tx::verify_pack_import_install(record, workspace, detail) &&
        tx::verify_pack_import_tree(record, owner.staging.path(), false, detail) &&
        std::chrono::steady_clock::now() <= deadline;
}

struct OperationLock {
    facman::base::StableLocalLock lock;
    ~OperationLock() { std::string ignored; if (lock.open()) (void)lock.remove_exact(ignored); }
};
}
facman::core::Result<std::string> import_modpack(const fs::path& workspace_input, const PackImportRequest& request)
{
    const fs::path workspace = fs::absolute(workspace_input).lexically_normal();
    auto id = facman::core::InstanceId::parse(request.instance_id);
    auto install_id = facman::core::InstallId::parse_legacy(request.install_id);
    if (!id || !install_id || request.display_name.size() > 128U)
        return failure("invalid_request", "A portable new instance id and registered install are required");
    auto target = facman::base::managed_directory(workspace, "instances", id.value().str());
    if (!target.ok()) return failure(target.code, target.detail);
    facman::platform::PathIdentity existing;
    auto checked = facman::platform::inspect_path_no_follow(target.path, existing);
    if (!checked.ok() || existing.exists) return failure("persistent_target_exists", "Instance target already exists or is unsafe");
    auto source_result = pack_import::inspect(request.source_path);
    if (!source_result) return failure(source_result.error().code, source_result.error().message);
    auto source = source_result.take_value();
    // The shared transaction format remains capped at 1 MiB/20000 nodes.
    // Admit the import inventory within that existing recovery budget before
    // effects, leaving room for generated files, install bindings and paths.
    std::size_t journal_inventory_bytes = 0;
    for (const auto& file : source.files) journal_inventory_bytes += file.path.size() + 160U;
    if (source.files.size() > 3000U || journal_inventory_bytes > 512U * 1024U)
        return failure("modpack_journal_budget_exceeded", "Pack inventory exceeds the existing transaction recovery budget");
    facman::workspace::WorkspaceLayout layout(workspace);
    auto registered = facman::workspace::InstallRepository(layout).load(install_id.value());
    if (!registered) return failure("unknown_install", "The selected local installation is not registered");
    auto install_record = registered.take_value();
    std::string detail;
    if (install_record.version != source.manifest.content_lock.factorio_version ||
        !fs::is_regular_file(install_record.executable) ||
        facman::base::path_crosses_link_or_reparse_point(install_record.executable, detail) ||
        facman::base::path_crosses_link_or_reparse_point(install_record.root / "data", detail) ||
        install_record.lifecycle_status == "archived" || install_record.lifecycle_status == "removed")
        return failure("modpack_install_incompatible", "The registered local installation does not match the pack");
    facman::platform::StableDirectoryObject install_directory;
    if (!install_directory.open_no_follow(install_record.root).ok()) return failure("modpack_install_incompatible", "Local installation is unsafe");
    auto inventory = facman::factorio::mods::local_inventory(workspace);
    if (!inventory) return failure(inventory.error().code, inventory.error().message);
    // Bind the same selected built-ins before any extraction effects.
    std::vector<fs::path> builtin_metadata;
    for (const auto& entry : source.manifest.content_lock.entries) {
        if (!entry.virtual_package) continue;
        bool found = false;
        for (const auto& mod : inventory.value()) {
            if (mod.virtual_package && mod.valid && mod.source == "install-data:" + install_id.value().str() &&
                mod.name == entry.name && mod.version == entry.version && mod.file_name == entry.file_name &&
                !facman::base::path_crosses_link_or_reparse_point(mod.file_path / "info.json", detail)) {
                builtin_metadata.push_back(mod.file_path / "info.json");
                found = true;
                break;
            }
        }
        if (!found) return failure("modpack_install_incompatible", "A selected built-in package is unavailable or incompatible: " + entry.name);
    }
    auto ready = facman::workspace::WorkspaceRepository(layout).ensure();
    if (!ready) return failure(ready.error().code, ready.error().message);
    const fs::path staging = workspace / (".facman-pack-import-" + id.value().str());
    facman::platform::PathIdentity stage_exists;
    checked = facman::platform::inspect_path_no_follow(staging, stage_exists);
    if (!checked.ok() || stage_exists.exists) return failure("staging_target_exists", "Retained import staging already exists; use workspace recovery");
    facman::platform::StableDirectoryObject destination_parent;
    if (!destination_parent.open_no_follow(target.path.parent_path()).ok()) return failure("persistent_write_refused", "Instance parent is unsafe");
    tx::Record record;
    record.command_id = "modsets.import";
    record.target = target.path;
    record.sources = {fs::absolute(request.source_path).lexically_normal(), install_record.root};
    record.staging_roots = {staging};
    record.commit_strategy = "modpack_instance_no_replace_v1";
    record.effect_parent_identity = tx::directory_effect_identity(destination_parent);
    // The existing first durable journal contains source/request/install truth.
    // This does not authorize resuming legacy or incompletely extracted stages.
    if (!tx::bind_pack_import_install(record, workspace, install_id.value().str(), builtin_metadata, detail) ||
        !bind_pack_source(record, source, request, detail))
        return failure("modpack_install_incompatible", detail);
    auto started = tx::TransactionSession::begin(workspace, std::move(record));
    if (!started) return failure(started.error().code, started.error().message);
    auto session = started.take_value();
    auto retained = [&](const std::string& code, const std::string& error) {
        session.require_recovery(error);
        return failure(code, error + "; retained import data requires workspace recovery",
            facman::core::OutcomeKind::recovery_required);
    };
    OperationLock operation;
    auto acquired = operation.lock.create(tx::recovery_lock_path(workspace, session.record().transaction_id));
    json::ObjectBuilder lock_json;
    lock_json.add_string("schema", "facman.recovery_lock.v1");
    lock_json.add_string("identity", operation.lock.identity_text());
    if (!acquired.acquired() || !operation.lock.write_text(lock_json.serialize() + "\n", detail))
        return retained("recovery_write_refused", "Import recovery lock could not be held");
    if (!pause(workspace, "precreate")) return retained("transaction_recovery_required", "Import paused before exclusive staging creation");
    if (!session.validated() || !session.planned()) return retained("recovery_write_refused", session.detail());
    const facman::archive::Limits limits;
    const auto extracted = facman::archive::extract_verified_to_new_retained_staging(source.plan, staging, limits, source.files,
        [&](std::uint32_t, const char* point) {
            if (std::string(point) == "root_ready") {
                facman::platform::StableDirectoryObject created;
                if (!created.open_no_follow(staging).ok()) return false;
                session.record().effect_file_identity = tx::directory_effect_identity(created);
                return !session.record().effect_file_identity.empty() && created.revalidate().ok() &&
                    session.staging("pack_extraction_started");
            }
            if (std::string(point) == "after_entry" && !pause(workspace, "extracted-entry")) return false;
            const char* fault = std::getenv("FACMAN_TEST_MODPACK_IMPORT_EXTRACT_FAULT");
            return !(fault && std::string(fault) == point);
        });
    if (!extracted.ok()) return retained(extracted.code, extracted.detail);
    facman::platform::StableDirectoryObject held_stage;
    if (!held_stage.open_no_follow(staging).ok() ||
        tx::directory_effect_identity(held_stage) != session.record().effect_file_identity)
        return retained("modpack_staging_changed", "Staged directory differs from its exclusively created object");
    auto selected = pack_import::validate_selected(source, staging, inventory.value(), install_id.value().str());
    if (!selected) return retained(selected.error().code, selected.error().message);
    // Revalidate the original write-ahead binding; never replace it with later
    // install metadata that changed during extraction.
    if (!tx::verify_pack_import_install(session.record(), workspace, detail))
        return retained("modpack_install_incompatible", detail);
    RecoveryPackSource install_owner;
    if (!retain_install_custody(workspace, session.record(), install_owner, detail))
        return retained("modpack_install_incompatible", detail);
    auto bound_registration = facman::workspace::InstallRepository(layout).load(install_id.value());
    if (!bound_registration || bound_registration.value().root != install_record.root ||
        bound_registration.value().version != source.manifest.content_lock.factorio_version ||
        bound_registration.value().lifecycle_status == "archived" || bound_registration.value().lifecycle_status == "removed" ||
        !verify_install_custody(install_owner, detail, true) ||
        !tx::verify_pack_import_install(session.record(), workspace, detail))
        return retained("modpack_install_incompatible", "Original bound installation is unavailable or incompatible");
    install_record = bound_registration.take_value();
    auto bound_inventory = facman::factorio::mods::local_inventory(workspace);
    if (!bound_inventory) return retained("modpack_install_incompatible", bound_inventory.error().message);
    auto bound_selected = pack_import::validate_selected(source, staging, bound_inventory.value(), install_id.value().str());
    if (!bound_selected || !verify_install_custody(install_owner, detail, true))
        return retained("modpack_install_incompatible", "Selected content differs from the original pinned installation");
    selected = std::move(bound_selected);
    facman::workspace::InstanceRecord instance;
    instance.id = id.take_value();
    instance.install_ref = install_id.take_value();
    instance.root = target.path;
    instance.factorio_version = install_record.version;
    instance.display_name = request.display_name.empty() ? source.manifest.name : request.display_name;
    discovery::InstallRef install;
    install.root = install_record.root;
    install.executable = install_record.executable;
    install.ownership = install_record.ownership;
    install.distribution_origin = install_record.distribution_origin;
    install.platform_integration = install_record.platform_integration;
    install.strict_isolation_eligibility = install_record.strict_isolation_eligibility;
    install.external_state_domains = install_record.external_state_domains;
    const auto generated = generated_pack_files(instance, install, source, selected.value());
    if (!bind_generated_intent(workspace, session.record(), source, generated, detail))
        return retained("recovery_write_refused", detail);
    {
        RecoveryPackSource owner;
        const std::string archive_marker = "schema=facman.archive_staging.v1\n";
        if (!owner.staging.open_no_follow_for_relative_writes(staging).ok() ||
            tx::directory_effect_identity(owner.staging) != session.record().effect_file_identity ||
            !retain_authenticated_marker(owner, facman::archive::owned_staging_marker_name(), &archive_marker, detail) ||
            !retain_authenticated_marker(owner, tx::transaction_staging_marker_name(), nullptr, detail) ||
            !tx::verify_staging_ownership(session.record(), staging, detail) ||
            !complete_generated_files(workspace, session.record(), owner, source, generated, detail))
            return retained("persistent_write_refused", detail);
    }
    const auto& receipt_text = generated.back().second;
    if (!session.staged("pack_inventory_bound") ||
        !tx::verify_pack_import_tree(session.record(), staging, false, detail) || !session.verified("pack_instance_verified"))
        return retained("modpack_staging_changed", detail.empty() ? session.detail() : detail);
    if (!pause(workspace, "verified")) return retained("transaction_recovery_required", "Verified import paused");
    std::string current_archive_sha256;
    const auto archive_checked = facman::archive::archive_sha256(source.plan, limits, current_archive_sha256);
    if (!archive_checked.ok() || current_archive_sha256 != source.archive_sha256)
        return retained("modpack_source_changed", "The opened pack changed during reconstruction");
    auto current_inventory = facman::factorio::mods::local_inventory(workspace);
    auto current_install = facman::workspace::InstallRepository(layout).load(instance.install_ref);
    if (!current_inventory || !current_install || current_install.value().root != install_record.root ||
        current_install.value().executable != install_record.executable || current_install.value().version != install_record.version ||
        !install_directory.revalidate().ok() ||
        !pack_import::validate_selected(source, staging, current_inventory.value(), instance.install_ref.str()))
        return retained("modpack_install_incompatible", "Local content/install changed during import");
    if (!tx::verify_pack_import_install(session.record(), workspace, detail) ||
        !destination_parent.revalidate().ok() || !held_stage.revalidate().ok() ||
        !tx::verify_pack_import_tree(session.record(), staging, false, detail) || !session.committing())
        return retained("modpack_staging_changed", detail.empty() ? session.detail() : detail);
    // Reopen and match the captured object before native handle publication.
    // Full inventory is verified again while the publication object is held.
    held_stage = facman::platform::StableDirectoryObject();
    const auto published = facman::platform::publish_directory_no_replace_if_matches(staging, target.path,
        session.record().effect_file_identity, session.record().effect_parent_identity,
        [&](std::string& error) { return tx::verify_pack_import_tree(session.record(), staging, false, error) &&
            tx::verify_pack_import_install(session.record(), workspace, error); });
    if (!published.ok()) {
        detail = published.code + ": " + published.detail;
        session.commit_uncertain("pack_rename_result_uncertain");
        return retained("transaction_recovery_required", detail);
    }
    if (!pause(workspace, "published")) return retained("transaction_recovery_required", "Published import paused before commit receipt");
    if (!tx::verify_pack_import_tree(session.record(), target.path, true, detail) || !session.committed("pack_instance_committed"))
        return retained("transaction_recovery_required", detail.empty() ? session.detail() : detail);
    if (!pause(workspace, "committed") || !tx::finalize_pack_import(session.record(), detail) || !session.complete())
        return retained("transaction_recovery_required", detail.empty() ? session.detail() : detail);
    return facman::core::Result<std::string>::success(receipt_text);
}

bool has_incomplete_pack_source_binding(const fs::path& workspace, const std::string& id)
{
    auto identifier = facman::core::TransactionId::parse(id);
    if (!identifier) return false;
    auto bytes = facman::workspace::TransactionRepository(facman::workspace::WorkspaceLayout(workspace)).load_journal(identifier.value());
    json::Limits limits; limits.maximum_bytes = 1024U * 1024U; limits.maximum_depth = 24U; limits.maximum_nodes = 20000U;
    auto parsed = json::parse(bytes ? bytes.value() : "null", limits);
    std::string command, strategy, state;
    if (!parsed || !bound_string(parsed.value(), "command_id", command) || command != "modsets.import" ||
        !bound_string(parsed.value(), "commit_strategy", strategy) || strategy != "modpack_instance_no_replace_v1" ||
        !bound_string(parsed.value(), "state", state)) return false;
    auto phase = tx::parse_state(state);
    const auto* steps = parsed.value().find("completed_steps");
    if (!phase || tx::terminal(phase.value()) || !steps || !steps->is_array()) return false;
    bool source_bound = false, complete_bound = false;
    for (std::size_t index = 0; index < steps->size(); ++index) {
        auto step = steps->at(index)->string_value();
        if (!step) return false;
        source_bound = source_bound || step.value() == "pack_source_inventory_bound";
        complete_bound = complete_bound || step.value() == "pack_inventory_bound";
    }
    return source_bound && !complete_bound;
}

facman::core::Result<std::string> recover_modpack_import(const fs::path& workspace_input, const std::string& transaction_id)
{
    const fs::path workspace = fs::absolute(workspace_input).lexically_normal();
    tx::Record record;
    std::string detail;
    if (!read_strict_import_record(workspace, transaction_id, record, detail)) return failure("recovery_modpack_import_unsafe", detail);
    if (record.command_id != "modsets.import" || record.commit_strategy != "modpack_instance_no_replace_v1" ||
        tx::terminal(record.state) || has_step(record, "pack_inventory_bound"))
        return failure("recovery_modpack_import_unsafe", "This import requires its existing complete-inventory recovery path");
    OperationLock operation;
    const auto lock_path = tx::recovery_lock_path(workspace, transaction_id);
    auto acquired = operation.lock.create(lock_path);
    if (acquired.code == facman::base::StableLockCode::exists) {
        facman::base::StableLocalLock existing;
        std::string bytes;
        auto opened = existing.open_existing(lock_path, 4096U, bytes);
        json::ObjectBuilder expected;
        expected.add_string("schema", "facman.recovery_lock.v1");
        expected.add_string("identity", existing.identity_text());
        if (!opened.acquired() || bytes != expected.serialize() + "\n")
            return failure("recovery_lock_contended", "Another import owns this lock or its exact metadata cannot be adopted");
        operation.lock = std::move(existing); acquired = opened;
    }
    if (!acquired.acquired()) return failure("recovery_write_refused", acquired.detail);
    json::ObjectBuilder metadata;
    metadata.add_string("schema", "facman.recovery_lock.v1");
    metadata.add_string("identity", operation.lock.identity_text());
    tx::Record current;
    if (!operation.lock.write_text(metadata.serialize() + "\n", detail)) return failure("recovery_write_refused", detail);
    if (!read_strict_import_record(workspace, transaction_id, current, detail)) return failure("recovery_modpack_import_unsafe", detail);
    record = std::move(current);
    auto unsafe = [&]() { return failure("recovery_modpack_import_unsafe", detail + "; all existing import data retained"); };
    RecoveryPackSource owner;
    {
        if (!inspect_partial_pack_authority(workspace, record, owner, detail)) return unsafe();
        if (before_pack_staging_creation(record) && !create_bound_missing_pack_stage(workspace, record, owner, detail)) return unsafe();
        const bool generated_intent = has_step(record, "pack_generated_inventory_bound");
        if (!generated_intent) {
            owner.verify_until = std::chrono::steady_clock::now() + std::chrono::milliseconds(facman::archive::Limits().maximum_read_milliseconds);
            const auto extracted = facman::archive::extract_verified_missing_to_retained_staging(owner.source.plan, owner.staging,
                facman::archive::Limits(), owner.source.files, owner.markers, {"mods"},
                [&](std::uint32_t, const char* point) {
                    if (std::string(point) == "retained_ready" && !pause(workspace, "recovery-ready")) return false;
                    if (!verify_install_custody(owner, detail, std::string(point) == "retained_ready")) return false;
                    const char* fault = std::getenv("FACMAN_TEST_MODPACK_IMPORT_EXTRACT_FAULT");
                    return !(fault && std::string(fault) == point);
                });
            if (!extracted.ok()) { detail = extracted.detail; return unsafe(); }
        }
        // A generated-intent journal can only follow a complete raw inventory.
        // Prove all raw files and keep their pins before any further effects.
        owner.verify_until = std::chrono::steady_clock::now() + std::chrono::milliseconds(facman::archive::Limits().maximum_read_milliseconds);
        std::vector<facman::platform::StableInputFile> raw_pins;
        for (const auto& file : owner.source.files)
            if (!retain_pack_file(owner.staging, file, raw_pins, detail, owner.verify_until)) return unsafe();
        auto installed = facman::core::InstallId::parse_legacy(owner.request.install_id);
        auto id = facman::core::InstanceId::parse(owner.request.instance_id);
        auto registration = facman::workspace::InstallRepository(facman::workspace::WorkspaceLayout(workspace)).load(installed.value());
        auto inventory = facman::factorio::mods::local_inventory(workspace);
        if (!registration || !inventory || !tx::verify_pack_import_install(record, workspace, detail)) return unsafe();
        auto selected = pack_import::validate_selected(owner.source, owner.staging.path(), inventory.value(), owner.request.install_id);
        if (!selected) { detail = selected.error().message; return unsafe(); }
        facman::workspace::InstanceRecord instance;
        instance.id = id.take_value(); instance.install_ref = installed.take_value();
        instance.root = record.target; instance.factorio_version = registration.value().version;
        instance.display_name = owner.request.display_name;
        discovery::InstallRef install;
        install.root = registration.value().root; install.executable = registration.value().executable;
        install.ownership = registration.value().ownership;
        install.distribution_origin = registration.value().distribution_origin;
        install.platform_integration = registration.value().platform_integration;
        install.strict_isolation_eligibility = registration.value().strict_isolation_eligibility;
        install.external_state_domains = registration.value().external_state_domains;
        const auto generated = generated_pack_files(instance, install, owner.source, selected.value());
        if (!bind_generated_intent(workspace, record, owner.source, generated, detail) ||
            !complete_generated_files(workspace, record, owner, owner.source, generated, detail)) return unsafe();
        std::string archive_hash;
        const auto checked = facman::archive::archive_sha256(owner.source.plan, facman::archive::Limits(), archive_hash);
        if (!checked.ok() || archive_hash != owner.source.archive_sha256 || !owner.parent.revalidate().ok() ||
            !owner.installation.revalidate().ok() || !owner.staging.revalidate().ok() ||
            !tx::verify_pack_import_install(record, workspace, detail)) {
            detail = "Original pack, installation or staging changed before recovery publication"; return unsafe();
        }
        if (!tx::checkpoint(workspace, record, "pack_inventory_bound", detail)) return unsafe();
    }
    // Release staging and marker pins before the existing native no-replace
    // publication and exact marker finalization acquire their own capabilities.
    owner.staging = facman::platform::StableDirectoryObject();
    owner.parent = facman::platform::StableDirectoryObject();
    owner.workspace_root = facman::platform::StableDirectoryObject();
    owner.held_markers.clear();
    // Original reader and authenticated install/workspace metadata remain held.
    if (!verify_install_custody(owner, detail, true) || !tx::recover_pack_import(workspace, record, detail)) return unsafe();
    if (!operation.lock.remove_exact(detail)) return failure("recovery_write_refused", detail);
    return facman::core::Result<std::string>::success("complete");
}
}
