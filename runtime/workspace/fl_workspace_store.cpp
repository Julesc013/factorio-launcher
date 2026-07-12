// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_workspace_store.h"

#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_system_services.h"

#include <algorithm>
#include <cmath>
#include <set>
#include <system_error>
#include <vector>

namespace facman::workspace {
namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace {

template <typename T>
Result<T> failure(std::string code, std::string message, const fs::path& path = {})
{
    return Result<T>::failure({std::move(code), std::move(message), facman::platform::path_to_utf8(path)});
}

Result<std::string> read_bounded(const fs::path& path, std::uint64_t maximum_bytes = 1024ULL * 1024ULL)
{
    facman::platform::StableInputFile input;
    const auto opened = input.open_no_follow(path);
    if (!opened.ok()) return failure<std::string>(opened.code, opened.detail, path);
    if (input.size() > maximum_bytes) {
        return failure<std::string>("workspace_record_too_large", "persistent record exceeds its byte budget", path);
    }
    std::string text(static_cast<std::size_t>(input.size()), '\0');
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t read = input.read_at(
            offset,
            text.data() + static_cast<std::size_t>(offset),
            static_cast<std::size_t>(input.size() - offset));
        if (read == 0) return failure<std::string>("workspace_record_read_failed", "short persistent record read", path);
        offset += read;
    }
    const auto stable = input.revalidate();
    if (!stable.ok()) return failure<std::string>(stable.code, stable.detail, path);
    return Result<std::string>::success(std::move(text));
}

Result<fs::path> write_new_durable(const fs::path& path, const std::string& text)
{
    std::error_code error;
    fs::create_directories(path.parent_path(), error);
    if (error) return failure<fs::path>("workspace_directory_create_failed", error.message(), path.parent_path());
    facman::platform::DurableOutputFile output;
    auto status = output.create_exclusive(path, 1024ULL * 1024ULL);
    if (!status.ok()) return failure<fs::path>(status.code, status.detail, path);
    if (output.write_at(0, text.data(), text.size()) != text.size()) {
        output.close_without_flush();
        return failure<fs::path>("workspace_record_write_failed", "short persistent record write", path);
    }
    status = output.flush_file_and_parent();
    if (!status.ok()) return failure<fs::path>(status.code, status.detail, path);
    return Result<fs::path>::success(path);
}

Result<json::Value> parse_record(const fs::path& path)
{
    auto text = read_bounded(path);
    if (!text) return failure<json::Value>(text.error().code, text.error().message, path);
    json::Limits limits;
    limits.maximum_bytes = 1024U * 1024U;
    limits.maximum_depth = 24;
    limits.maximum_nodes = 20000;
    limits.maximum_string_bytes = 256U * 1024U;
    auto parsed = json::parse(text.value(), limits);
    if (!parsed) return failure<json::Value>(parsed.error().code, parsed.error().message, path);
    if (!parsed.value().is_object()) return failure<json::Value>("workspace_record_type", "persistent record must be a JSON object", path);
    return parsed;
}

Result<std::string> required_string(const json::Value& object, const char* key, const fs::path& path)
{
    const json::Value* value = object.find(key);
    if (value == nullptr) return failure<std::string>("workspace_record_missing_field", std::string("missing field: ") + key, path);
    auto result = value->string_value();
    if (!result) return failure<std::string>("workspace_record_field_type", std::string("field must be a string: ") + key, path);
    if (result.value().empty()) return failure<std::string>("workspace_record_empty_field", std::string("field must not be empty: ") + key, path);
    return result;
}

std::string optional_string(const json::Value& object, const char* key, const std::string& fallback = {})
{
    const json::Value* value = object.find(key);
    if (value == nullptr || !value->is_string()) return fallback;
    auto result = value->string_value();
    return result ? result.value() : fallback;
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
    record.root = facman::platform::path_from_utf8(root.value());
    const std::string executable = optional_string(document.value(), "executable");
    record.executable = executable.empty() ? fs::path() : facman::platform::path_from_utf8(executable);
    record.version = optional_string(document.value(), "version");
    record.ownership = optional_string(document.value(), "ownership");
    record.source = optional_string(document.value(), "source", legacy ? "legacy" : "registered");
    record.platform = optional_string(document.value(), "platform");
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
    std::error_code manifest_error;
    if (fs::is_regular_file(layout_.manifest(), manifest_error) && !manifest_error) return load();
    const std::vector<fs::path> directories = {
        "installs/refs", "installs/setup_state_refs", "instances", "modsets", "saves", "profiles",
        "accounts", "audit", "diagnostics/reports", "exports", "transactions"};
    for (const fs::path& relative : directories) {
        std::error_code error;
        fs::create_directories(layout_.root() / relative, error);
        if (error) return failure<WorkspaceRecord>("workspace_directory_create_failed", error.message(), layout_.root() / relative);
    }
    auto written = write_new_durable(layout_.manifest(), workspace_json(uuid_from_random()));
    if (!written) return failure<WorkspaceRecord>(written.error().code, written.error().message, layout_.manifest());
    return load();
}

namespace {

Result<std::vector<MigrationAction>> collect_migration_actions(const WorkspaceLayout& layout)
{
    std::vector<MigrationAction> actions;
    std::error_code error;
    if (!fs::is_regular_file(layout.manifest(), error) || error) {
        actions.push_back({"create_workspace_identity", {}, layout.manifest(), false, true});
    } else {
        WorkspaceRepository repository(layout);
        auto workspace = repository.load();
        if (!workspace) return failure<std::vector<MigrationAction>>(workspace.error().code, workspace.error().message, layout.manifest());
        if (workspace.value().legacy_local_identity) {
            actions.push_back({"replace_literal_local_workspace_identity", layout.manifest(), layout.manifest(), true, true});
        }
    }

    error.clear();
    if (fs::is_directory(layout.legacy_installs_dir(), error) && !error) {
        for (const fs::directory_entry& entry : fs::directory_iterator(layout.legacy_installs_dir())) {
            const fs::file_status status = entry.symlink_status(error);
            if (error) return failure<std::vector<MigrationAction>>("workspace_migration_scan_failed", error.message(), entry.path());
            if (!fs::is_regular_file(status) || entry.path().extension() != ".json") continue;
            auto id = InstallId::parse_legacy(entry.path().stem().string());
            if (!id) return failure<std::vector<MigrationAction>>(id.error().code, id.error().message, entry.path());
            auto target = layout.install_ref(id.value());
            if (!target) return failure<std::vector<MigrationAction>>(target.error().code, target.error().message, entry.path());
            error.clear();
            if (!fs::exists(target.value(), error) && !error) {
                actions.push_back({"canonicalize_legacy_install_ref", entry.path(), target.value(), true, true});
            }
        }
    }

    const fs::path instances = layout.root() / "instances";
    error.clear();
    if (fs::is_directory(instances, error) && !error) {
        for (const fs::directory_entry& entry : fs::directory_iterator(instances)) {
            const fs::file_status status = entry.symlink_status(error);
            if (error) return failure<std::vector<MigrationAction>>("workspace_migration_scan_failed", error.message(), entry.path());
            if (!fs::is_directory(status)) continue;
            const fs::path legacy = entry.path() / "instance.manifest.json";
            const fs::path current = entry.path() / "instance.v1.json";
            if (fs::is_regular_file(legacy, error) && !error && !fs::exists(current, error) && !error) {
                actions.push_back({"canonicalize_legacy_instance_manifest", legacy, current, true, true});
            }
            error.clear();
        }
    }
    std::sort(actions.begin(), actions.end(), [](const MigrationAction& left, const MigrationAction& right) {
        if (left.kind != right.kind) return left.kind < right.kind;
        return left.source.generic_string() < right.source.generic_string();
    });
    return Result<std::vector<MigrationAction>>::success(std::move(actions));
}

Result<MigrationReport> migration_report(const WorkspaceLayout& layout, const char* operation)
{
    auto actions = collect_migration_actions(layout);
    if (!actions) return failure<MigrationReport>(actions.error().code, actions.error().message);
    MigrationReport report;
    report.operation = operation;
    report.actions = actions.take_value();
    report.apply_enabled = report.actions.empty();
    return Result<MigrationReport>::success(std::move(report));
}

} // namespace

Result<MigrationReport> WorkspaceRepository::inspect_migration() const
{
    return migration_report(layout_, "workspace.migration.inspect");
}

Result<MigrationReport> WorkspaceRepository::plan_migration() const
{
    return migration_report(layout_, "workspace.migration.plan");
}

Result<MigrationReport> WorkspaceRepository::apply_migration() const
{
    auto report = migration_report(layout_, "workspace.migration.apply");
    if (!report) return report;
    if (!report.value().actions.empty()) {
        return failure<MigrationReport>(
            "workspace_migration_apply_unproven",
            "migration apply refuses until backup and transaction-journal execution has dedicated proof");
    }
    report.value().apply_enabled = true;
    return report;
}

std::string migration_report_json(const MigrationReport& report)
{
    json::ArrayBuilder actions;
    for (const MigrationAction& action : report.actions) {
        json::ObjectBuilder item;
        item.add_string("kind", action.kind);
        item.add_string("source", facman::platform::path_to_utf8(action.source));
        item.add_string("target", facman::platform::path_to_utf8(action.target));
        item.add_bool("backup_required", action.backup_required);
        item.add_bool("journal_required", action.journal_required);
        actions.add_object(item);
    }
    json::ObjectBuilder document;
    document.add_string("schema", "facman.workspace_migration.v1");
    document.add_string("command", report.operation);
    document.add_string("status", report.actions.empty() ? "no_changes" : "changes_detected");
    document.add_bool("apply_enabled", report.apply_enabled);
    document.add_array("actions", actions);
    return document.serialize() + "\n";
}

} // namespace facman::workspace
