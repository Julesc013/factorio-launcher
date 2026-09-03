// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_workspace_store.h"

#include "fl_workspace_io_internal.h"
#include "fl_workspace_migration_internal.h"

// Bounded StableInputFile reads and DurableOutputFile publication are shared
// with the migration engine through fl_workspace_io_internal.

#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_system_services.h"
#include "fl_workspace_root_authority.h"

#include <algorithm>
#include <cmath>
#include <set>
#include <system_error>
#include <utility>
#include <vector>

namespace facman::workspace {
namespace fs = std::filesystem;
namespace json = facman::core::json;
using persistence_detail::optional_string;
using persistence_detail::parse_record;
using persistence_detail::read_bounded;
using persistence_detail::required_string;
using persistence_detail::write_new_durable;
namespace {

template <typename T>
Result<T> failure(std::string code, std::string message, const fs::path& path = {})
{
    return Result<T>::failure({std::move(code), std::move(message), facman::platform::path_to_utf8(path)});
}

std::vector<std::string> optional_strings(const json::Value& object, const char* key)
{
    std::vector<std::string> output;
    const json::Value* values = object.find(key);
    if (values == nullptr || !values->is_array()) return output;
    for (std::size_t index = 0; index < values->size(); ++index) {
        const json::Value* value = values->at(index);
        if (value == nullptr || !value->is_string()) return {};
        auto parsed = value->string_value();
        if (!parsed) return {};
        output.push_back(parsed.take_value());
    }
    return output;
}

std::string verification_status(const json::Value& object)
{
    const json::Value* verification = object.find("verification");
    return verification == nullptr ? optional_string(object, "status") : optional_string(*verification, "status");
}

std::string uuid_from_random()
{
    facman::platform::RandomIdGenerator random;
    std::string value = random.next("workspace");
    value = value.substr(value.find('-') + 1);
    value[12] = '4';
    value[16] = "89ab"[static_cast<unsigned char>(value[16]) % 4];
    return value.substr(0, 8) + "-" + value.substr(8, 4) + "-" + value.substr(12, 4) + "-" +
        value.substr(16, 4) + "-" + value.substr(20, 12);
}

std::string workspace_json(const std::string& id)
{
    json::ObjectBuilder roots;
    roots.add_string("installs", "installs");
    roots.add_string("instances", "instances");
    roots.add_string("profiles", "profiles");
    roots.add_string("modsets", "modsets");
    roots.add_string("accounts", "accounts");
    roots.add_string("cache", "cache");
    roots.add_string("audit", "audit");
    roots.add_string("diagnostics", "diagnostics");
    roots.add_string("exports", "exports");

    json::ObjectBuilder document;
    document.add_string("schema", "facman.factorio.workspace.v1");
    document.add_string("workspace_id", id);
    (void)document.add_unsigned_integer("layout_version", 1);
    document.add_object("roots", roots);
    return document.serialize() + "\n";
}

} // namespace

WorkspaceLayout::WorkspaceLayout(fs::path root) : root_(std::move(root)) {}
const fs::path& WorkspaceLayout::root() const noexcept { return root_; }
fs::path WorkspaceLayout::manifest() const { return root_ / "workspace.v1.json"; }
fs::path WorkspaceLayout::installs_refs_dir() const { return root_ / "installs" / "refs"; }
fs::path WorkspaceLayout::legacy_installs_dir() const { return root_ / "installs" / "installed_state"; }

Result<fs::path> WorkspaceLayout::install_ref(const InstallId& id) const
{
    const auto path = facman::base::managed_file(root_, "installs/refs", id.str(), ".json");
    return path.ok() ? Result<fs::path>::success(path.path) : failure<fs::path>(path.code, path.detail);
}

Result<fs::path> WorkspaceLayout::legacy_install_ref(const InstallId& id) const
{
    const auto path = facman::base::managed_file(root_, "installs/installed_state", id.str(), ".json");
    return path.ok() ? Result<fs::path>::success(path.path) : failure<fs::path>(path.code, path.detail);
}

Result<fs::path> WorkspaceLayout::instance_root(const InstanceId& id) const
{
    const auto path = facman::base::managed_directory(root_, "instances", id.str());
    return path.ok() ? Result<fs::path>::success(path.path) : failure<fs::path>(path.code, path.detail);
}

Result<fs::path> WorkspaceLayout::instance_manifest(const InstanceId& id) const
{
    auto root = instance_root(id);
    return root ? Result<fs::path>::success(root.value() / "instance.v1.json") : failure<fs::path>(root.error().code, root.error().message);
}

Result<fs::path> WorkspaceLayout::legacy_instance_manifest(const InstanceId& id) const
{
    auto root = instance_root(id);
    return root ? Result<fs::path>::success(root.value() / "instance.manifest.json") : failure<fs::path>(root.error().code, root.error().message);
}

Result<fs::path> WorkspaceLayout::modset_lock(const InstanceId& id) const
{
    const auto path = facman::base::managed_file(root_, "modsets", id.str(), ".modset-lock.v1.json");
    return path.ok() ? Result<fs::path>::success(path.path) : failure<fs::path>(path.code, path.detail);
}

Result<fs::path> WorkspaceLayout::instance_modset_lock(const InstanceId& id) const
{
    auto root = instance_root(id);
    return root ? Result<fs::path>::success(root.value() / "mods" / "modset-lock.v1.json") : failure<fs::path>(root.error().code, root.error().message);
}

Result<fs::path> WorkspaceLayout::transaction_journal(const TransactionId& id) const
{
    const auto path = facman::base::managed_file(root_, "transactions", id.str(), ".transaction.v1.json");
    return path.ok() ? Result<fs::path>::success(path.path) : failure<fs::path>(path.code, path.detail);
}

Result<fs::path> WorkspaceLayout::diagnostic_output(const std::string& file_name) const
{
    const fs::path value = facman::platform::path_from_utf8(file_name);
    if (value.filename() != value || value.extension() != ".zip") {
        return failure<fs::path>("diagnostic_output_name_invalid", "diagnostic output must be one ZIP filename");
    }
    return Result<fs::path>::success(root_ / "diagnostics" / "reports" / value);
}

InstallRepository::InstallRepository(WorkspaceLayout layout) : layout_(std::move(layout)) {}

Result<InstallRecord> InstallRepository::load(const InstallId& id) const
{
    auto canonical = layout_.install_ref(id);
    if (!canonical) return failure<InstallRecord>(canonical.error().code, canonical.error().message);
    fs::path path = canonical.value();
    bool legacy = false;
    std::error_code error;
    if (!fs::is_regular_file(path, error) || error) {
        auto fallback = layout_.legacy_install_ref(id);
        if (!fallback) return failure<InstallRecord>(fallback.error().code, fallback.error().message);
        path = fallback.value();
        legacy = true;
    }
    auto document = parse_record(path);
    if (!document) return failure<InstallRecord>(document.error().code, document.error().message, path);
    auto schema = required_string(document.value(), "schema", path);
    auto stored_id = required_string(document.value(), "install_id", path);
    auto root = required_string(document.value(), "root", path);
    if (!root) root = required_string(document.value(), "app_dir", path);
    if (!schema || !stored_id || !root) {
        const auto& problem = !schema ? schema.error() : !stored_id ? stored_id.error() : root.error();
        return failure<InstallRecord>(problem.code, problem.message, path);
    }
    if (schema.value() != "factorio.install_ref.v1" && schema.value() != "usk.installed_state.v1") {
        return failure<InstallRecord>("workspace_record_future_or_unknown_schema", schema.value(), path);
    }
    if (stored_id.value() != id.str()) return failure<InstallRecord>("workspace_record_id_mismatch", stored_id.value(), path);
    InstallRecord record;
    record.id = id;
    record.provider_id = optional_string(document.value(), "provider_id");
    record.root = facman::platform::path_from_utf8(root.value());
    const std::string executable = optional_string(document.value(), "executable");
    record.executable = executable.empty() ? fs::path() : facman::platform::path_from_utf8(executable);
    record.version = optional_string(document.value(), "version");
    record.ownership = optional_string(document.value(), "ownership");
    record.source = optional_string(document.value(), "source", legacy ? "legacy" : "registered");
    record.source_ref = optional_string(document.value(), "source_ref");
    record.platform = optional_string(document.value(), "platform");
    record.distribution_origin = optional_string(document.value(), "distribution_origin");
    record.platform_integration = optional_string(document.value(), "platform_integration");
    record.strict_isolation_eligibility = optional_string(document.value(), "strict_isolation_eligibility");
    record.external_state_domains = optional_strings(document.value(), "external_state_domains");
    record.setup_state_ref = optional_string(document.value(), "setup_state_ref");
    record.lifecycle_status = optional_string(document.value(), "lifecycle_status");
    record.last_verification_identity = optional_string(document.value(), "last_verification_identity");
    record.state_revision = optional_string(document.value(), "state_revision");
    record.verification_status = verification_status(document.value());
    if (record.verification_status.empty()) record.verification_status = optional_string(document.value(), "state");
    record.schema = schema.value();
    record.legacy_path = legacy;
    record.source_path = path;
    return Result<InstallRecord>::success(std::move(record));
}

Result<std::vector<InstallRecord>> InstallRepository::list() const
{
    std::set<std::string> ids;
    for (const fs::path& directory : {layout_.installs_refs_dir(), layout_.legacy_installs_dir()}) {
        std::error_code error;
        if (!fs::is_directory(directory, error) || error) continue;
        for (fs::directory_iterator iterator(directory, fs::directory_options::skip_permission_denied, error), end;
             iterator != end && !error; iterator.increment(error)) {
            const fs::file_status status = iterator->symlink_status(error);
            if (error || !fs::is_regular_file(status) || iterator->path().extension() != ".json") continue;
            ids.insert(iterator->path().stem().string());
        }
        if (error) return failure<std::vector<InstallRecord>>("workspace_list_failed", error.message(), directory);
    }
    std::vector<InstallRecord> records;
    for (const std::string& id : ids) {
        auto parsed_id = InstallId::parse_legacy(id);
        if (!parsed_id) return failure<std::vector<InstallRecord>>(parsed_id.error().code, parsed_id.error().message);
        auto record = load(parsed_id.value());
        if (!record) return failure<std::vector<InstallRecord>>(record.error().code, record.error().message, record.error().path);
        records.push_back(record.take_value());
    }
    return Result<std::vector<InstallRecord>>::success(std::move(records));
}

Result<fs::path> InstallRepository::create(const InstallRecord& record, const std::string& json_text) const
{
    auto target = layout_.install_ref(record.id);
    if (!target) return failure<fs::path>(target.error().code, target.error().message);
    return write_new_durable(target.value(), json_text);
}

InstanceRepository::InstanceRepository(WorkspaceLayout layout) : layout_(std::move(layout)) {}

Result<InstanceRecord> InstanceRepository::load(const InstanceId& id) const
{
    auto canonical = layout_.instance_manifest(id);
    if (!canonical) return failure<InstanceRecord>(canonical.error().code, canonical.error().message);
    fs::path path = canonical.value();
    bool legacy = false;
    std::error_code error;
    if (!fs::is_regular_file(path, error) || error) {
        auto fallback = layout_.legacy_instance_manifest(id);
        if (!fallback) return failure<InstanceRecord>(fallback.error().code, fallback.error().message);
        path = fallback.value();
        legacy = true;
    }
    auto document = parse_record(path);
    if (!document) return failure<InstanceRecord>(document.error().code, document.error().message, path);
    const std::string schema = optional_string(document.value(), "schema", legacy ? "factorio.instance.legacy" : "");
    if (schema != "factorio.instance.v1" && schema != "factorio.instance.legacy") {
        return failure<InstanceRecord>("workspace_record_future_or_unknown_schema", schema, path);
    }
    auto stored_id = required_string(document.value(), "instance_id", path);
    auto install_ref = required_string(document.value(), "install_ref", path);
    if (!stored_id || !install_ref) {
        const auto& problem = !stored_id ? stored_id.error() : install_ref.error();
        return failure<InstanceRecord>(problem.code, problem.message, path);
    }
    if (stored_id.value() != id.str()) return failure<InstanceRecord>("workspace_record_id_mismatch", stored_id.value(), path);
    auto root = layout_.instance_root(id);
    if (!root) return failure<InstanceRecord>(root.error().code, root.error().message);
    InstanceRecord record;
    record.id = id;
    record.display_name = optional_string(document.value(), "display_name", id.str());
    auto parsed_install = InstallId::parse_legacy(install_ref.value());
    if (!parsed_install) return failure<InstanceRecord>(parsed_install.error().code, parsed_install.error().message, path);
    record.install_ref = parsed_install.take_value();
    record.factorio_version = optional_string(document.value(), "factorio_version");
    record.profile = optional_string(document.value(), "profile", "gui");
    record.template_id = optional_string(document.value(), "template", "vanilla");
    record.root = root.value();
    // local_data_root is descriptive legacy data, never path authority.  Derive the
    // live root exclusively from the managed workspace layout so a modified
    // manifest cannot redirect reads or writes outside the instance directory.
    record.schema = schema;
    record.legacy_path = legacy;
    record.source_path = path;
    return Result<InstanceRecord>::success(std::move(record));
}

Result<std::vector<InstanceRecord>> InstanceRepository::list() const
{
    std::set<std::string> ids;
    const fs::path directory = layout_.root() / "instances";
    std::error_code error;
    const bool directory_exists = fs::exists(directory, error);
    if (!directory_exists && !error) {
        return Result<std::vector<InstanceRecord>>::success({});
    }
    if (error) return failure<std::vector<InstanceRecord>>("workspace_list_failed", error.message(), directory);
    if (fs::is_directory(directory, error) && !error) {
        for (fs::directory_iterator iterator(directory, fs::directory_options::skip_permission_denied, error), end;
             iterator != end && !error; iterator.increment(error)) {
            const fs::file_status status = iterator->symlink_status(error);
            if (error || !fs::is_directory(status)) continue;
            const fs::path canonical = iterator->path() / "instance.v1.json";
            const fs::path legacy = iterator->path() / "instance.manifest.json";
            std::error_code manifest_error;
            if (fs::is_regular_file(canonical, manifest_error) || fs::is_regular_file(legacy, manifest_error)) {
                ids.insert(iterator->path().filename().string());
            }
        }
    }
    if (error) return failure<std::vector<InstanceRecord>>("workspace_list_failed", error.message(), directory);
    std::vector<InstanceRecord> records;
    for (const std::string& id : ids) {
        auto parsed_id = InstanceId::parse_legacy(id);
        if (!parsed_id) return failure<std::vector<InstanceRecord>>(parsed_id.error().code, parsed_id.error().message);
        auto record = load(parsed_id.value());
        if (!record) return failure<std::vector<InstanceRecord>>(record.error().code, record.error().message, record.error().path);
        records.push_back(record.take_value());
    }
    return Result<std::vector<InstanceRecord>>::success(std::move(records));
}

ModsetRepository::ModsetRepository(WorkspaceLayout layout) : layout_(std::move(layout)) {}

Result<fs::path> ModsetRepository::canonical_lock(const InstanceId& id) const
{
    return layout_.modset_lock(id);
}

Result<std::string> ModsetRepository::load_lock(const InstanceId& id) const
{
    auto canonical = layout_.modset_lock(id);
    if (!canonical) return failure<std::string>(canonical.error().code, canonical.error().message);
    fs::path path = canonical.value();
    std::error_code error;
    if (!fs::is_regular_file(path, error) || error) {
        auto fallback = layout_.instance_modset_lock(id);
        if (!fallback) return failure<std::string>(fallback.error().code, fallback.error().message);
        path = fallback.value();
    }
    return read_bounded(path);
}

TransactionRepository::TransactionRepository(WorkspaceLayout layout) : layout_(std::move(layout)) {}

Result<fs::path> TransactionRepository::journal(const TransactionId& id) const
{
    return layout_.transaction_journal(id);
}

Result<std::string> TransactionRepository::load_journal(const TransactionId& id) const
{
    auto path = layout_.transaction_journal(id);
    return path ? read_bounded(path.value()) : failure<std::string>(path.error().code, path.error().message);
}

WorkspaceRepository::WorkspaceRepository(WorkspaceLayout layout) : layout_(std::move(layout)) {}

Result<WorkspaceRecord> WorkspaceRepository::load() const
{
    const fs::path path = layout_.manifest();
    auto document = parse_record(path);
    if (!document) return failure<WorkspaceRecord>(document.error().code, document.error().message, path);
    auto schema = required_string(document.value(), "schema", path);
    auto id = required_string(document.value(), "workspace_id", path);
    const json::Value* version_value = document.value().find("layout_version");
    if (!schema || !id || version_value == nullptr || !version_value->is_number()) {
        return failure<WorkspaceRecord>("workspace_manifest_invalid", "workspace schema, identity, and layout version are required", path);
    }
    auto version = version_value->number_value();
    if (!version || std::floor(version.value()) != version.value()) {
        return failure<WorkspaceRecord>("workspace_manifest_invalid", "layout version must be an integer", path);
    }
    if (schema.value() != "facman.factorio.workspace.v1" || version.value() != 1.0) {
        return failure<WorkspaceRecord>("workspace_layout_future_or_unknown", schema.value(), path);
    }
    WorkspaceRecord record;
    auto parsed_id = WorkspaceId::parse_legacy(id.value());
    if (!parsed_id) return failure<WorkspaceRecord>(parsed_id.error().code, parsed_id.error().message, path);
    record.id = parsed_id.take_value();
    record.layout_version = 1;
    record.schema = schema.value();
    record.legacy_local_identity = id.value() == "local";
    return Result<WorkspaceRecord>::success(std::move(record));
}

Result<WorkspaceRecord> WorkspaceRepository::ensure() const
{
    auto inspected = inspect_workspace_root(layout_.root());
    if (!inspected) {
        return failure<WorkspaceRecord>(
            inspected.error().code, inspected.error().message, layout_.root());
    }
    WorkspaceRootInspection authority;
    std::string workspace_id;
    if (inspected.value().state == WorkspaceRootState::missing ||
        inspected.value().state == WorkspaceRootState::empty_unowned) {
        workspace_id = uuid_from_random();
        auto claimed = claim_workspace_root(layout_.root(), workspace_id);
        if (!claimed) {
            return failure<WorkspaceRecord>(
                claimed.error().code, claimed.error().message, layout_.root());
        }
        authority = claimed.take_value();
    } else if (inspected.value().state == WorkspaceRootState::facman_owned) {
        authority = inspected.take_value();
        workspace_id = authority.workspace_id;
    } else {
        std::string code = "workspace_root_inspection_failed";
        if (inspected.value().state == WorkspaceRootState::legacy_facman) {
            auto legacy = load();
            if (!legacy) return legacy;
            code = "workspace_root_legacy_adoption_required";
        } else if (inspected.value().state == WorkspaceRootState::foreign_nonempty) {
            code = "workspace_root_foreign_refused";
        } else if (inspected.value().state == WorkspaceRootState::link_or_reparse) {
            code = "workspace_root_link_refused";
        }
        return failure<WorkspaceRecord>(
            code,
            inspected.value().detail + "; action=" + inspected.value().recovery_action,
            layout_.root());
    }
    auto stable = revalidate_workspace_root(authority);
    if (!stable) {
        return failure<WorkspaceRecord>(stable.error().code, stable.error().message, layout_.root());
    }

    std::error_code manifest_error;
    const bool manifest_exists = fs::exists(layout_.manifest(), manifest_error);
    if (manifest_error) {
        return failure<WorkspaceRecord>(
            "workspace_manifest_inspection_failed", manifest_error.message(), layout_.manifest());
    }
    if (manifest_exists) {
        auto loaded = load();
        if (!loaded) return loaded;
        if (loaded.value().id.str() != workspace_id) {
            return failure<WorkspaceRecord>(
                "workspace_root_identity_mismatch",
                "ownership marker and workspace manifest identify different roots",
                layout_.manifest());
        }
        stable = revalidate_workspace_root(authority);
        if (!stable) {
            return failure<WorkspaceRecord>(stable.error().code, stable.error().message, layout_.root());
        }
        return loaded;
    }

    const std::vector<fs::path> directories = {
        "installs", "installs/refs", "installs/setup_state_refs", "instances", "modsets",
        "saves", "profiles", "accounts", "audit", "diagnostics", "diagnostics/reports",
        "exports", "transactions"};
    for (const fs::path& relative : directories) {
        const fs::path target = layout_.root() / relative;
        const auto safe_before = authority.root_authority->validate_descendant(target, true);
        if (!safe_before.ok()) {
            return failure<WorkspaceRecord>(safe_before.code, safe_before.detail, target);
        }
        std::error_code error;
        fs::create_directory(target, error);
        if (error) {
            return failure<WorkspaceRecord>(
                "workspace_directory_create_failed", error.message(), target);
        }
        const auto safe_after = authority.root_authority->validate_descendant(target);
        if (!safe_after.ok()) {
            return failure<WorkspaceRecord>(safe_after.code, safe_after.detail, target);
        }
    }
    const auto manifest_safe = authority.root_authority->validate_descendant(
        layout_.manifest(), true);
    if (!manifest_safe.ok()) {
        return failure<WorkspaceRecord>(
            manifest_safe.code, manifest_safe.detail, layout_.manifest());
    }
    auto written = write_new_durable(layout_.manifest(), workspace_json(workspace_id));
    if (!written) return failure<WorkspaceRecord>(written.error().code, written.error().message, layout_.manifest());
    stable = revalidate_workspace_root(authority);
    if (!stable) {
        return failure<WorkspaceRecord>(stable.error().code, stable.error().message, layout_.root());
    }
    return load();
}

Result<MigrationReport> WorkspaceRepository::inspect_migration() const
{
    return migration_detail::inspect(layout_);
}

Result<MigrationReport> WorkspaceRepository::plan_migration() const
{
    return migration_detail::plan(layout_);
}

Result<MigrationReport> WorkspaceRepository::apply_migration(const MigrationApplyRequest& request) const
{
    return migration_detail::apply(layout_, request);
}

Result<MigrationReport> WorkspaceRepository::rollback_migration(
    const MigrationControlRequest& request) const
{
    return rollback_migration_operation(layout_, request);
}

std::string migration_report_json(const MigrationReport& report)
{
    return migration_detail::report_json(report);
}

} // namespace facman::workspace
