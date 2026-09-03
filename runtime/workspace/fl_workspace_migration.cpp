// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_workspace_io_internal.h"
#include "fl_workspace_migration_internal.h"

#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_local_operation_lock.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_system_services.h"
#include "fl_workspace_root_authority.h"
#include <algorithm>
#include <limits>
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

} // namespace

namespace {

constexpr std::uint64_t kMaximumMigrationBytes = 64ULL * 1024ULL * 1024ULL;

struct PreparedMigrationAction {
    MigrationAction action;
    std::string source_text;
    std::string target_text;
    std::string source_sha256;
    std::string target_sha256;
    fs::path source_backup;
    fs::path target_payload;
};

bool copy_migration_plan(const std::vector<MigrationAction>& actions)
{
    return std::all_of(actions.begin(), actions.end(), [](const MigrationAction& action) {
        return copy_migration_kind(action.kind) && action.source != action.target &&
            action.backup_required && action.journal_required;
    });
}

bool creation_migration_plan(const std::vector<MigrationAction>& actions)
{
    return actions.size() == 1U &&
        actions.front().kind == "create_workspace_identity" &&
        actions.front().source.empty() && !actions.front().target.empty() &&
        !actions.front().backup_required && actions.front().journal_required;
}

Result<void> validate_legacy_install_document(
    const fs::path& source,
    const std::string& expected_id)
{
    auto document = parse_record(source);
    if (!document) return failure<void>(document.error().code, document.error().message, source);
    auto schema = required_string(document.value(), "schema", source);
    auto stored_id = required_string(document.value(), "install_id", source);
    auto root = required_string(document.value(), "root", source);
    if (!root) root = required_string(document.value(), "app_dir", source);
    if (!schema || !stored_id || !root) {
        const auto& problem = !schema ? schema.error() : !stored_id ? stored_id.error() : root.error();
        return failure<void>(problem.code, problem.message, source);
    }
    if ((schema.value() != "factorio.install_ref.v1" &&
         schema.value() != "usk.installed_state.v1") ||
        stored_id.value() != expected_id) {
        return failure<void>(
            schema.value() != "factorio.install_ref.v1" &&
                    schema.value() != "usk.installed_state.v1" ?
                "workspace_record_future_or_unknown_schema" : "workspace_record_id_mismatch",
            schema.value() != "factorio.install_ref.v1" &&
                    schema.value() != "usk.installed_state.v1" ?
                schema.value() : stored_id.value(),
            source);
    }
    return Result<void>::success();
}

Result<std::string> canonical_instance_manifest(
    const fs::path& source,
    const std::string& expected_id)
{
    auto document = parse_record(source);
    if (!document) return failure<std::string>(document.error().code, document.error().message, source);
    const std::string current_schema = optional_string(document.value(), "schema", "factorio.instance.legacy");
    if (current_schema != "factorio.instance.legacy" && current_schema != "factorio.instance.v1") {
        return failure<std::string>(
            "workspace_record_future_or_unknown_schema", current_schema, source);
    }
    auto stored_id = required_string(document.value(), "instance_id", source);
    auto install_ref = required_string(document.value(), "install_ref", source);
    if (!stored_id || !install_ref) {
        const auto& problem = !stored_id ? stored_id.error() : install_ref.error();
        return failure<std::string>(problem.code, problem.message, source);
    }
    if (stored_id.value() != expected_id) {
        return failure<std::string>(
            "workspace_record_id_mismatch", stored_id.value(), source);
    }
    auto parsed_install = InstallId::parse_legacy(install_ref.value());
    if (!parsed_install) {
        return failure<std::string>(
            parsed_install.error().code, parsed_install.error().message, source);
    }
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.instance.v1");
    for (const std::string& key : document.value().object_keys()) {
        if (key == "schema") continue;
        const json::Value* value = document.value().find(key);
        if (value == nullptr || !output.add_value(key, *value)) {
            return failure<std::string>(
                "workspace_manifest_invalid", "legacy instance contains duplicate fields", source);
        }
    }
    return Result<std::string>::success(output.serialize() + "\n");
}

Result<PreparedMigrationAction> prepare_copy_action(
    const WorkspaceLayout& layout,
    const WorkspaceRootInspection& authority,
    const MigrationAction& action)
{
    if (!copy_migration_kind(action.kind) || action.source == action.target) {
        return failure<PreparedMigrationAction>(
            "workspace_migration_action_unsupported",
            "only deterministic legacy-record canonicalization is enabled");
    }
    const auto source_safe = authority.root_authority->validate_descendant(action.source);
    const auto target_safe = authority.root_authority->validate_descendant(action.target, true);
    if (!source_safe.ok() || !target_safe.ok()) {
        const auto& problem = !source_safe.ok() ? source_safe : target_safe;
        return failure<PreparedMigrationAction>(problem.code, problem.detail, action.source);
    }
    facman::platform::PathIdentity source_identity;
    facman::platform::PathIdentity target_identity;
    auto status = facman::platform::inspect_path_no_follow(action.source, source_identity);
    if (!status.ok() || !source_identity.exists || source_identity.reparse_or_link ||
        source_identity.kind != facman::platform::PathObjectKind::regular_file) {
        return failure<PreparedMigrationAction>(
            "workspace_migration_conflict",
            status.ok() ? "migration source is not a plain regular file" : status.detail,
            action.source);
    }
    status = facman::platform::inspect_path_no_follow(action.target, target_identity);
    if (!status.ok() || target_identity.exists) {
        return failure<PreparedMigrationAction>(
            "workspace_migration_conflict",
            status.ok() ? "migration target already exists" : status.detail,
            action.target);
    }
    auto source_text = read_bounded(action.source);
    if (!source_text) {
        return failure<PreparedMigrationAction>(
            source_text.error().code, source_text.error().message, action.source);
    }
    std::string target_text = source_text.value();
    if (action.kind == "canonicalize_legacy_install_ref") {
        auto id = InstallId::parse_legacy(action.source.stem().string());
        if (!id) return failure<PreparedMigrationAction>(id.error().code, id.error().message, action.source);
        auto valid_document = validate_legacy_install_document(action.source, id.value().str());
        if (!valid_document) {
            return failure<PreparedMigrationAction>(
                valid_document.error().code, valid_document.error().message, action.source);
        }
        auto record = InstallRepository(layout).load(id.value());
        if (!record || !record.value().legacy_path ||
            record.value().source_path.lexically_normal() != action.source.lexically_normal()) {
            return failure<PreparedMigrationAction>(
                record ? "workspace_migration_conflict" : record.error().code,
                record ? "legacy install migration source did not resolve exactly" : record.error().message,
                action.source);
        }
    } else {
        auto id = InstanceId::parse_legacy(action.source.parent_path().filename().string());
        if (!id) return failure<PreparedMigrationAction>(id.error().code, id.error().message, action.source);
        auto record = InstanceRepository(layout).load(id.value());
        if (!record || !record.value().legacy_path ||
            record.value().source_path.lexically_normal() != action.source.lexically_normal()) {
            return failure<PreparedMigrationAction>(
                record ? "workspace_migration_conflict" : record.error().code,
                record ? "legacy instance migration source did not resolve exactly" : record.error().message,
                action.source);
        }
        auto canonical = canonical_instance_manifest(action.source, id.value().str());
        if (!canonical) {
            return failure<PreparedMigrationAction>(
                canonical.error().code, canonical.error().message, action.source);
        }
        target_text = canonical.take_value();
    }
    PreparedMigrationAction prepared;
    prepared.action = action;
    prepared.source_text = source_text.take_value();
    prepared.target_text = std::move(target_text);
    prepared.source_sha256 = sha256_text(prepared.source_text);
    prepared.target_sha256 = sha256_text(prepared.target_text);
    return Result<PreparedMigrationAction>::success(std::move(prepared));
}

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
                auto record = InstallRepository(layout).load(id.value());
                if (!record || !record.value().legacy_path ||
                    record.value().source_path.lexically_normal() != entry.path().lexically_normal()) {
                    return failure<std::vector<MigrationAction>>(
                        record ? "workspace_migration_conflict" : record.error().code,
                        record ? "legacy install migration source did not resolve exactly" : record.error().message,
                        entry.path());
                }
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
                auto id = InstanceId::parse_legacy(entry.path().filename().string());
                if (!id) {
                    return failure<std::vector<MigrationAction>>(
                        id.error().code, id.error().message, entry.path());
                }
                auto record = InstanceRepository(layout).load(id.value());
                if (!record || !record.value().legacy_path ||
                    record.value().source_path.lexically_normal() != legacy.lexically_normal()) {
                    return failure<std::vector<MigrationAction>>(
                        record ? "workspace_migration_conflict" : record.error().code,
                        record ? "legacy instance migration source did not resolve exactly" : record.error().message,
                        legacy);
                }
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
    auto authority = inspect_workspace_root(layout.root());
    if (!authority) {
        return failure<MigrationReport>(
            authority.error().code, authority.error().message, layout.root());
    }
    MigrationReport report;
    report.operation = operation;
    report.actions = actions.take_value();
    report.expected_root_identity = root_identity_digest(layout, authority.value());
    report.current_format = report.actions.size() == 1U &&
            report.actions.front().kind == "create_workspace_identity"
        ? "uninitialized"
        : "facman.factorio.workspace.v1";
    std::string inventory_material = report.current_format + "\n";
    if (fs::is_regular_file(layout.manifest())) {
        auto manifest = read_bounded(layout.manifest());
        if (!manifest) {
            return failure<MigrationReport>(
                manifest.error().code, manifest.error().message, layout.manifest());
        }
        inventory_material += "workspace.v1.json\n" + sha256_text(manifest.value()) + "\n";
    }
    for (std::size_t index = 0U; index < report.actions.size(); ++index) {
        MigrationAction& action = report.actions[index];
        action.step_id = "step-" + std::to_string(index + 1U);
        if (copy_migration_kind(action.kind) &&
            authority.value().state == WorkspaceRootState::facman_owned) {
            auto prepared = prepare_copy_action(layout, authority.value(), action);
            if (!prepared) {
                return failure<MigrationReport>(
                    prepared.error().code, prepared.error().message, prepared.error().path);
            }
            action.source_sha256 = prepared.value().source_sha256;
            action.target_sha256 = prepared.value().target_sha256;
        } else if (action.kind == "create_workspace_identity") {
            action.target_sha256 = sha256_text(
                "facman.factorio.workspace.v1\nos-random-rfc4122-v4\n");
        }
        inventory_material += action.step_id + "\n" + action.kind + "\n" +
            facman::platform::path_to_utf8(action.source) + "\n" +
            facman::platform::path_to_utf8(action.target) + "\n" +
            action.source_sha256 + "\n" + action.target_sha256 + "\n";
    }
    report.inventory_digest = sha256_text(inventory_material);
    report.expected_workspace_revision = sha256_text(
        report.expected_root_identity + "\n" + report.inventory_digest + "\n" +
        report.current_format + "\n");
    std::string plan_material = "facman.workspace_migration_plan.v2\n" +
        report.expected_root_identity + "\n" + report.expected_workspace_revision + "\n" +
        report.inventory_digest + "\n" + report.current_format + "\n" + report.target_format + "\n";
    for (const MigrationAction& action : report.actions) {
        plan_material += action.step_id + "\n" + action.kind + "\n" +
            facman::platform::path_to_utf8(action.source) + "\n" +
            facman::platform::path_to_utf8(action.target) + "\n" +
            action.source_sha256 + "\n" + action.target_sha256 + "\n" +
            (action.backup_required ? "backup" : "no-backup") + "\n" +
            (action.journal_required ? "journal" : "no-journal") + "\n";
    }
    report.plan_digest = sha256_text(plan_material);
    report.migration_id = "workspace-migration-" + report.plan_digest.substr(0U, 24U);
    report.apply_enabled = copy_migration_plan(report.actions) ||
        creation_migration_plan(report.actions) || report.actions.empty();
    if (copy_migration_plan(report.actions) && !report.actions.empty()) {
        auto workspace = WorkspaceRepository(layout).load();
        report.apply_enabled = workspace &&
            authority.value().state == WorkspaceRootState::facman_owned &&
            authority.value().mutation_allowed &&
            authority.value().workspace_id == workspace.value().id.str();
    } else if (creation_migration_plan(report.actions)) {
        report.apply_enabled = authority.value().state == WorkspaceRootState::missing ||
            authority.value().state == WorkspaceRootState::empty_unowned ||
            authority.value().state == WorkspaceRootState::facman_owned;
    }
    report.state = report.actions.empty() ? "healthy" :
        std::string(operation) == "workspace.migration.inspect" ? "migration_available" :
        "confirmation_required";
    return Result<MigrationReport>::success(std::move(report));
}

Result<WorkspaceRootInspection> owned_migration_authority(const WorkspaceLayout& layout)
{
    auto authority = inspect_workspace_root(layout.root());
    if (!authority || authority.value().state != WorkspaceRootState::facman_owned ||
        !authority.value().mutation_allowed || !authority.value().root_authority) {
        return failure<WorkspaceRootInspection>(
            "workspace_migration_conflict",
            "migration apply requires an already-owned workspace root",
            layout.root());
    }
    WorkspaceRepository repository(layout);
    auto workspace = repository.load();
    if (!workspace || workspace.value().id.str() != authority.value().workspace_id) {
        return failure<WorkspaceRootInspection>(
            workspace ? "workspace_migration_conflict" : workspace.error().code,
            workspace ? "workspace manifest and ownership marker identities differ" : workspace.error().message,
            layout.manifest());
    }
    auto stable = revalidate_workspace_root(authority.value());
    if (!stable) {
        return failure<WorkspaceRootInspection>(stable.error().code, stable.error().message, layout.root());
    }
    return authority;
}

bool recognized_migration_lock(const std::string& content)
{
    json::Limits limits;
    limits.maximum_bytes = 4096U;
    limits.maximum_depth = 4U;
    limits.maximum_nodes = 16U;
    limits.maximum_string_bytes = 1024U;
    auto document = json::parse(content, limits);
    if (!document || !document.value().is_object()) return false;
    const json::Value* schema = document.value().find("schema");
    const json::Value* identity = document.value().find("identity");
    if (schema == nullptr || identity == nullptr || !schema->is_string() ||
        !identity->is_string()) return false;
    auto schema_text = schema->string_value();
    auto identity_text = identity->string_value();
    return schema_text && identity_text &&
        schema_text.value() == "facman.workspace_migration_lock.v1" &&
        !identity_text.value().empty();
}

class ScopedMigrationLock {
public:
    Result<void> acquire(const fs::path& path)
    {
        auto result = lock_.create(path);
        if (result.code == facman::base::StableLockCode::exists) {
            facman::base::StableLocalLock stale;
            std::string content;
            auto opened = stale.open_existing(path, 4096U, content);
            if (opened.code == facman::base::StableLockCode::contended) {
                return failure<void>(
                    "workspace_migration_conflict",
                    "another workspace migration owns the migration lock",
                    path);
            }
            if (!opened.acquired() || !recognized_migration_lock(content)) {
                return failure<void>(
                    "workspace_migration_conflict",
                    "existing workspace migration lock is unsafe or unrecognized",
                    path);
            }
            std::string detail;
            if (!stale.remove_exact(detail)) {
                return failure<void>(
                    "workspace_migration_conflict", detail, path);
            }
            result = lock_.create(path);
        }
        if (!result.acquired()) {
            return failure<void>(
                "workspace_migration_conflict", result.detail, path);
        }
        json::ObjectBuilder document;
        document.add_string("schema", "facman.workspace_migration_lock.v1");
        document.add_string("identity", lock_.identity_text());
        std::string detail;
        if (!lock_.write_text(document.serialize() + "\n", detail)) {
            (void)lock_.remove_exact(detail);
            return failure<void>(
                "workspace_migration_conflict", detail, path);
        }
        acquired_ = true;
        return Result<void>::success();
    }

    Result<void> release()
    {
        if (!acquired_) return Result<void>::success();
        std::string detail;
        if (!lock_.remove_exact(detail)) {
            return failure<void>(
                "workspace_migration_conflict",
                "migration lock identity changed before release: " + detail,
                lock_.path());
        }
        acquired_ = false;
        return Result<void>::success();
    }

    ~ScopedMigrationLock()
    {
        if (!acquired_) return;
        std::string ignored;
        (void)lock_.remove_exact(ignored);
    }

private:
    facman::base::StableLocalLock lock_;
    bool acquired_ = false;
};

Result<void> verify_journal_action_shape(
    const WorkspaceLayout& layout,
    const MigrationJournalAction& action,
    fs::path& source,
    fs::path& target)
{
    auto source_path = resolve_relative_path(layout, action.source);
    auto target_path = resolve_relative_path(layout, action.target);
    if (!source_path || !target_path) {
        const auto& problem = !source_path ? source_path.error() : target_path.error();
        return failure<void>(problem.code, problem.message);
    }
    source = source_path.take_value();
    target = target_path.take_value();
    bool exact = false;
    if (action.kind == "canonicalize_legacy_install_ref") {
        auto id = InstallId::parse_legacy(source.stem().string());
        if (id) {
            auto expected_source = layout.legacy_install_ref(id.value());
            auto expected_target = layout.install_ref(id.value());
            exact = expected_source && expected_target &&
                expected_source.value().lexically_normal() == source.lexically_normal() &&
                expected_target.value().lexically_normal() == target.lexically_normal();
        }
    } else if (action.kind == "canonicalize_legacy_instance_manifest") {
        auto id = InstanceId::parse_legacy(source.parent_path().filename().string());
        if (id) {
            auto expected_source = layout.legacy_instance_manifest(id.value());
            auto expected_target = layout.instance_manifest(id.value());
            exact = expected_source && expected_target &&
                expected_source.value().lexically_normal() == source.lexically_normal() &&
                expected_target.value().lexically_normal() == target.lexically_normal();
        }
    }
    return exact ? Result<void>::success() : failure<void>(
        "workspace_migration_action_unsupported",
        "migration journal action does not match a known canonical path pair");
}

Result<std::string> expected_journal_target_payload(
    const MigrationJournalAction& action,
    const fs::path& source,
    const std::string& source_text)
{
    if (action.kind == "canonicalize_legacy_install_ref") {
        auto id = InstallId::parse_legacy(source.stem().string());
        if (!id) return failure<std::string>(id.error().code, id.error().message, source);
        auto valid = validate_legacy_install_document(source, id.value().str());
        if (!valid) return failure<std::string>(valid.error().code, valid.error().message, source);
        return Result<std::string>::success(source_text);
    }
    auto id = InstanceId::parse_legacy(source.parent_path().filename().string());
    if (!id) return failure<std::string>(id.error().code, id.error().message, source);
    return canonical_instance_manifest(source, id.value().str());
}

Result<void> resume_migration_journal(
    const WorkspaceLayout& layout,
    const WorkspaceRootInspection& authority,
    MigrationJournal& journal)
{
    if (journal.state == "complete" || journal.state == "rolled_back") {
        return Result<void>::success();
    }
    if (journal.state == "recovery_required") {
        return failure<void>(
            "workspace_migration_recovery_required",
            "a prior migration journal requires manual recovery",
            migration_journal_path(layout, journal.id, journal.format_version));
    }
    const fs::path data_root = migration_data_root(layout, journal.id);
    const auto data_safe = authority.root_authority->validate_descendant(data_root);
    if (!data_safe.ok()) return failure<void>(data_safe.code, data_safe.detail, data_root);
    journal.state = "applying";
    auto persisted = persist_journal(layout, journal, false);
    if (!persisted) return persisted;
    for (std::size_t index = 0U; index < journal.actions.size(); ++index) {
        const MigrationJournalAction& action = journal.actions[index];
        fs::path source;
        fs::path target;
        auto shaped = verify_journal_action_shape(layout, action, source, target);
        if (!shaped) return shaped;
        const auto source_safe = authority.root_authority->validate_descendant(source);
        const auto target_safe = authority.root_authority->validate_descendant(target, true);
        if (!source_safe.ok() || !target_safe.ok()) {
            const auto& problem = !source_safe.ok() ? source_safe : target_safe;
            return failure<void>(problem.code, problem.detail, source);
        }
        const fs::path source_backup = data_root / (std::to_string(index) + ".source.json");
        const fs::path target_payload = data_root / (std::to_string(index) + ".target.json");
        auto current_source = read_bounded(source);
        auto backed_source = read_bounded(source_backup);
        auto payload = read_bounded(target_payload);
        auto expected_payload = current_source ? expected_journal_target_payload(
            action, source, current_source.value()) :
            failure<std::string>(
                "workspace_migration_conflict", "migration source is unreadable", source);
        if (!current_source || !backed_source || !payload ||
            !expected_payload || payload.value() != expected_payload.value() ||
            sha256_text(current_source ? current_source.value() : std::string {}) != action.source_sha256 ||
            sha256_text(backed_source ? backed_source.value() : std::string {}) != action.source_sha256 ||
            sha256_text(payload ? payload.value() : std::string {}) != action.target_sha256) {
            return failure<void>(
                "workspace_migration_conflict",
                "migration source, backup, or staged payload changed during recovery",
                source);
        }
        auto stable = revalidate_workspace_root(authority);
        if (!stable) return failure<void>(stable.error().code, stable.error().message, layout.root());
        facman::platform::PathIdentity target_identity;
        const auto target_status = facman::platform::inspect_path_no_follow(target, target_identity);
        if (!target_status.ok()) return failure<void>(target_status.code, target_status.detail, target);
        if (!target_identity.exists) {
            auto written = write_new_durable(target, payload.value());
            if (!written) return failure<void>(written.error().code, written.error().message, target);
        } else {
            if (target_identity.reparse_or_link ||
                target_identity.kind != facman::platform::PathObjectKind::regular_file) {
                return failure<void>(
                    "workspace_migration_conflict",
                    "migration recovery target is not a plain regular file",
                    target);
            }
            auto current_target = read_bounded(target);
            if (!current_target || sha256_text(current_target.value()) != action.target_sha256) {
                return failure<void>(
                    "workspace_migration_conflict",
                    "migration recovery refuses to replace a divergent target",
                    target);
            }
        }
        journal.completed_actions = index + 1U;
        persisted = persist_journal(layout, journal, false);
        if (!persisted) return persisted;
    }
    auto stable = revalidate_workspace_root(authority);
    if (!stable) return failure<void>(stable.error().code, stable.error().message, layout.root());
    journal.state = "complete";
    return persist_journal(layout, journal, false);
}

Result<void> recover_incomplete_migrations(
    const WorkspaceLayout& layout,
    const WorkspaceRootInspection& authority)
{
    std::error_code error;
    std::vector<fs::path> journals;
    for (fs::directory_iterator iterator(
             migration_root(layout), fs::directory_options::skip_permission_denied, error), end;
         iterator != end && !error; iterator.increment(error)) {
        const fs::file_status status = iterator->symlink_status(error);
        if (error) break;
        const std::string name = iterator->path().filename().string();
        const std::string legacy_suffix = ".workspace-migration.v1.json";
        const std::string current_suffix = ".workspace-migration.v2.json";
        const bool recognized_name =
            name.size() > legacy_suffix.size() &&
            name.compare(name.size() - legacy_suffix.size(), legacy_suffix.size(), legacy_suffix) == 0;
        const bool current_name =
            name.size() > current_suffix.size() &&
            name.compare(name.size() - current_suffix.size(), current_suffix.size(), current_suffix) == 0;
        if (fs::is_regular_file(status) && (recognized_name || current_name)) {
            journals.push_back(iterator->path());
        }
    }
    if (error) return failure<void>("workspace_migration_scan_failed", error.message(), migration_root(layout));
    std::sort(journals.begin(), journals.end());
    for (const fs::path& path : journals) {
        auto journal = load_migration_journal(path);
        if (!journal) return failure<void>(journal.error().code, journal.error().message, path);
        auto resumed = resume_migration_journal(layout, authority, journal.value());
        if (!resumed) return resumed;
    }
    return Result<void>::success();
}

} // namespace

Result<MigrationReport> migration_detail::inspect(const WorkspaceLayout& layout)
{
    return migration_report(layout, "workspace.migration.inspect");
}

Result<MigrationReport> migration_detail::plan(const WorkspaceLayout& layout)
{
    return migration_report(layout, "workspace.migration.plan");
}

Result<MigrationReport> migration_detail::apply(
    const WorkspaceLayout& layout,
    const MigrationApplyRequest& request)
{
    const WorkspaceLayout& layout_ = layout;
    auto report = migration_report(layout_, "workspace.migration.apply");
    if (!report) return report;
    std::string identifier_detail;
    const bool identities_valid =
        facman::base::validate_identifier(request.request_id, identifier_detail) &&
        facman::base::validate_identifier(request.operation_id, identifier_detail) &&
        facman::base::validate_identifier(request.attempt_id, identifier_detail) &&
        facman::base::validate_identifier(request.idempotency_key, identifier_detail);
    if (!identities_valid || !sha256_text_valid(request.expected_workspace_revision) ||
        !sha256_text_valid(request.expected_root_identity) ||
        !sha256_text_valid(request.plan_digest) || request.confirmation != "explicit") {
        return failure<MigrationReport>(
            "workspace_migration_confirmation_required",
            "migration apply requires exact revision, root, plan, operation identities, and explicit confirmation");
    }
    const auto request_matches = [&request](const MigrationReport& value) {
        return request.expected_workspace_revision == value.expected_workspace_revision &&
            request.expected_root_identity == value.expected_root_identity &&
            request.plan_digest == value.plan_digest;
    };
    if (!request_matches(report.value())) {
        return failure<MigrationReport>(
            "workspace_migration_stale_plan",
            "workspace root, revision, inputs, or plan digest changed before effects",
            layout_.root());
    }
    report.value().request_id = request.request_id;
    report.value().operation_id = request.operation_id;
    report.value().attempt_id = request.attempt_id;
    report.value().idempotency_key = request.idempotency_key;
    std::error_code state_error;
    const bool has_migration_state = fs::is_directory(migration_root(layout_), state_error) &&
        !state_error;
    if (report.value().actions.empty() && !has_migration_state) {
        report.value().apply_enabled = true;
        report.value().state = "completed";
        report.value().resulting_workspace_revision =
            report.value().expected_workspace_revision;
        return report;
    }
    if (creation_migration_plan(report.value().actions)) {
        auto before = inspect_workspace_root(layout_.root());
        if (!before || root_identity_digest(layout_, before.value()) != request.expected_root_identity ||
            (before.value().state != WorkspaceRootState::missing &&
             before.value().state != WorkspaceRootState::empty_unowned &&
             before.value().state != WorkspaceRootState::facman_owned)) {
            return failure<MigrationReport>(
                "workspace_migration_stale_plan",
                "workspace root changed before explicit creation",
                layout_.root());
        }
        WorkspaceRootInspection authority;
        if (before.value().state == WorkspaceRootState::missing ||
            before.value().state == WorkspaceRootState::empty_unowned) {
            auto claimed = claim_workspace_root(layout_.root(), random_workspace_uuid());
            if (!claimed) {
                return failure<MigrationReport>(
                    claimed.error().code, claimed.error().message, claimed.error().path);
            }
            authority = claimed.take_value();
        } else {
            authority = before.take_value();
        }
        auto directory = ensure_owned_directory(authority, layout_.root() / "transactions");
        if (!directory) {
            return failure<MigrationReport>(
                directory.error().code, directory.error().message, directory.error().path);
        }
        directory = ensure_owned_directory(authority, migration_root(layout_));
        if (!directory) {
            return failure<MigrationReport>(
                directory.error().code, directory.error().message, directory.error().path);
        }
        ScopedMigrationLock migration_lock;
        auto locked = migration_lock.acquire(migration_root(layout_) / "workspace-migration.lock");
        if (!locked) {
            return failure<MigrationReport>(
                locked.error().code, locked.error().message, locked.error().path);
        }
        const fs::path creation_path = migration_root(layout_) /
            (request.operation_id + ".workspace-creation.v1.json");
        auto journal_written = write_new_durable(
            creation_path, workspace_creation_journal_json(request,
                authority.workspace_id, "applying", {}));
        if (!journal_written) {
            return failure<MigrationReport>(
                journal_written.error().code, journal_written.error().message, creation_path);
        }
        auto created = WorkspaceRepository(layout_).ensure();
        if (!created) {
            return failure<MigrationReport>(
                created.error().code, created.error().message, created.error().path);
        }
        auto resulting = migration_report(layout_, "workspace.migration.apply");
        if (!resulting || !resulting.value().actions.empty()) {
            return failure<MigrationReport>(
                resulting ? "workspace_migration_recovery_required" : resulting.error().code,
                resulting ? "created workspace did not verify as healthy" : resulting.error().message,
                layout_.root());
        }
        report.value().resulting_workspace_revision =
            resulting.value().expected_workspace_revision;
        auto completed = write_replace_durable(
            creation_path, workspace_creation_journal_json(request,
                authority.workspace_id, "completed",
                report.value().resulting_workspace_revision));
        if (!completed) {
            return failure<MigrationReport>(
                completed.error().code, completed.error().message, completed.error().path);
        }
        auto released = migration_lock.release();
        if (!released) {
            return failure<MigrationReport>(
                released.error().code, released.error().message, released.error().path);
        }
        report.value().state = "completed";
        report.value().mutation_executed = true;
        report.value().apply_enabled = true;
        return report;
    }
    if (!report.value().apply_enabled && !report.value().actions.empty()) {
        return failure<MigrationReport>(
            "workspace_migration_action_unsupported",
            "migration apply supports only backup-and-journal-proven legacy record canonicalization");
    }

    auto authority = owned_migration_authority(layout_);
    if (!authority) {
        return failure<MigrationReport>(
            authority.error().code, authority.error().message, authority.error().path);
    }
    auto directory = ensure_owned_directory(authority.value(), layout_.root() / "transactions");
    if (!directory) {
        return failure<MigrationReport>(directory.error().code, directory.error().message, directory.error().path);
    }
    directory = ensure_owned_directory(authority.value(), migration_root(layout_));
    if (!directory) {
        return failure<MigrationReport>(directory.error().code, directory.error().message, directory.error().path);
    }

    ScopedMigrationLock migration_lock;
    auto locked = migration_lock.acquire(migration_root(layout_) / "workspace-migration.lock");
    if (!locked) {
        return failure<MigrationReport>(locked.error().code, locked.error().message, locked.error().path);
    }
    auto recovered = recover_incomplete_migrations(layout_, authority.value());
    if (!recovered) {
        return failure<MigrationReport>(
            recovered.error().code, recovered.error().message, recovered.error().path);
    }

    report = migration_report(layout_, "workspace.migration.apply");
    if (!report) return report;
    if (!request_matches(report.value())) {
        return failure<MigrationReport>(
            "workspace_migration_stale_plan",
            "workspace revision or migration inputs changed while acquiring the mutation lock",
            layout_.root());
    }
    report.value().request_id = request.request_id;
    report.value().operation_id = request.operation_id;
    report.value().attempt_id = request.attempt_id;
    report.value().idempotency_key = request.idempotency_key;
    if (report.value().actions.empty()) {
        report.value().apply_enabled = true;
        report.value().state = "completed";
        report.value().resulting_workspace_revision =
            report.value().expected_workspace_revision;
        auto released = migration_lock.release();
        return released ? report : failure<MigrationReport>(
            released.error().code, released.error().message, released.error().path);
    }
    if (!report.value().apply_enabled || report.value().actions.size() > kMaximumMigrationActions) {
        return failure<MigrationReport>(
            "workspace_migration_action_unsupported",
            "migration plan contains an unsupported or excessive action set");
    }

    std::vector<PreparedMigrationAction> prepared;
    prepared.reserve(report.value().actions.size());
    std::uint64_t total_bytes = 0U;
    for (const MigrationAction& action : report.value().actions) {
        auto item = prepare_copy_action(layout_, authority.value(), action);
        if (!item) {
            return failure<MigrationReport>(item.error().code, item.error().message, item.error().path);
        }
        const std::uint64_t source_size = static_cast<std::uint64_t>(item.value().source_text.size());
        const std::uint64_t target_size = static_cast<std::uint64_t>(item.value().target_text.size());
        if (source_size > kMaximumMigrationBytes || target_size > kMaximumMigrationBytes ||
            total_bytes > kMaximumMigrationBytes - source_size ||
            total_bytes + source_size > kMaximumMigrationBytes - target_size) {
            return failure<MigrationReport>(
                "workspace_migration_action_unsupported",
                "migration payload set exceeds its aggregate byte budget");
        }
        total_bytes += source_size + target_size;
        prepared.push_back(item.take_value());
    }
    auto stable = revalidate_workspace_root(authority.value());
    if (!stable) {
        return failure<MigrationReport>(stable.error().code, stable.error().message, layout_.root());
    }

    MigrationJournal journal;
    journal.id = request.operation_id;
    journal.migration_id = report.value().migration_id;
    journal.operation_id = request.operation_id;
    journal.attempt_id = request.attempt_id;
    journal.request_id = request.request_id;
    journal.idempotency_key = request.idempotency_key;
    journal.plan_digest = request.plan_digest;
    journal.expected_workspace_revision = request.expected_workspace_revision;
    journal.expected_root_identity = request.expected_root_identity;
    journal.inventory_digest = report.value().inventory_digest;
    journal.state = "planned";
    const fs::path data_root = migration_data_root(layout_, journal.id);
    directory = ensure_owned_directory(authority.value(), data_root);
    if (!directory) {
        return failure<MigrationReport>(directory.error().code, directory.error().message, directory.error().path);
    }
    for (std::size_t index = 0U; index < prepared.size(); ++index) {
        PreparedMigrationAction& item = prepared[index];
        item.source_backup = data_root / (std::to_string(index) + ".source.json");
        item.target_payload = data_root / (std::to_string(index) + ".target.json");
        auto source_backup = write_new_durable(item.source_backup, item.source_text);
        if (!source_backup) {
            return failure<MigrationReport>(
                source_backup.error().code, source_backup.error().message, item.source_backup);
        }
        auto target_payload = write_new_durable(item.target_payload, item.target_text);
        if (!target_payload) {
            return failure<MigrationReport>(
                target_payload.error().code, target_payload.error().message, item.target_payload);
        }
        std::string source_relative;
        std::string target_relative;
        if (!safe_relative_text(layout_.root(), item.action.source, source_relative) ||
            !safe_relative_text(layout_.root(), item.action.target, target_relative)) {
            return failure<MigrationReport>(
                "workspace_migration_apply_unproven",
                "migration paths could not be represented relative to the owned workspace");
        }
        journal.actions.push_back({
            item.action.step_id, item.action.kind, std::move(source_relative),
            std::move(target_relative), item.source_sha256, item.target_sha256});
    }
    journal.verification_results.push_back("staged_payloads_verified");
    auto journal_written = persist_journal(layout_, journal, true);
    if (!journal_written) {
        return failure<MigrationReport>(
            journal_written.error().code, journal_written.error().message, journal_written.error().path);
    }

    std::vector<std::pair<fs::path, std::string>> created_targets;
    const auto rollback = [&](const std::string& reason, const fs::path& problem_path) -> Result<MigrationReport> {
        bool rollback_complete = true;
        std::string rollback_problem;
        for (auto iterator = created_targets.rbegin(); iterator != created_targets.rend(); ++iterator) {
            facman::platform::StableInputFile target;
            auto opened = target.open_no_follow(iterator->first);
            std::string current;
            bool current_valid = opened.ok() && target.size() <= 1024ULL * 1024ULL;
            if (current_valid) {
                current.assign(static_cast<std::size_t>(target.size()), '\0');
                std::uint64_t offset = 0U;
                while (offset < target.size()) {
                    const std::size_t count = target.read_at(
                        offset,
                        current.data() + static_cast<std::size_t>(offset),
                        static_cast<std::size_t>(target.size() - offset));
                    if (count == 0U) {
                        current_valid = false;
                        break;
                    }
                    offset += count;
                }
                current_valid = current_valid && target.revalidate().ok();
            }
            if (!current_valid || current != iterator->second) {
                rollback_complete = false;
                rollback_problem = "created migration target changed before rollback";
                break;
            }
            const auto removed = facman::platform::remove_exact_object(
                iterator->first, target.identity());
            if (!removed.ok()) {
                rollback_complete = false;
                rollback_problem = removed.detail;
                break;
            }
        }
        journal.state = rollback_complete ? "rolled_back" : "recovery_required";
        journal.resulting_workspace_revision.clear();
        auto recorded = persist_journal(layout_, journal, false);
        if (!recorded) {
            rollback_complete = false;
            if (rollback_problem.empty()) rollback_problem = recorded.error().message;
        }
        return failure<MigrationReport>(
            rollback_complete ? "workspace_migration_conflict" : "workspace_migration_recovery_required",
            reason + (rollback_complete ? "; created targets were rolled back" :
                "; migration recovery is required: " + rollback_problem),
            problem_path);
    };

    journal.state = "applying";
    auto journal_updated = persist_journal(layout_, journal, false);
    if (!journal_updated) {
        return rollback(journal_updated.error().message, journal_updated.error().path);
    }
    for (std::size_t index = 0U; index < prepared.size(); ++index) {
        PreparedMigrationAction& item = prepared[index];
        auto current_source = read_bounded(item.action.source);
        if (!current_source || current_source.value() != item.source_text) {
            return rollback("migration source changed after backup", item.action.source);
        }
        stable = revalidate_workspace_root(authority.value());
        if (!stable) return rollback(stable.error().message, layout_.root());
        auto committed = write_new_durable(item.action.target, item.target_text);
        if (!committed) {
            return rollback(committed.error().message, item.action.target);
        }
        created_targets.emplace_back(item.action.target, item.target_text);
        auto verified = read_bounded(item.action.target);
        if (!verified || verified.value() != item.target_text) {
            return rollback("migration target verification failed", item.action.target);
        }
        journal.completed_actions = index + 1U;
        journal.verification_results.push_back(
            "committed_output_verified:" + item.action.step_id);
        journal_updated = persist_journal(layout_, journal, false);
        if (!journal_updated) {
            return rollback(journal_updated.error().message, journal_updated.error().path);
        }
    }
    auto remaining = collect_migration_actions(layout_);
    if (!remaining || !remaining.value().empty()) {
        return rollback(
            remaining ? "migration verification still reports pending actions" : remaining.error().message,
            layout_.root());
    }
    stable = revalidate_workspace_root(authority.value());
    if (!stable) return rollback(stable.error().message, layout_.root());
    auto resulting = migration_report(layout_, "workspace.migration.apply");
    if (!resulting || !resulting.value().actions.empty()) {
        return rollback(
            resulting ? "migration target state did not become healthy" : resulting.error().message,
            layout_.root());
    }
    report.value().resulting_workspace_revision =
        resulting.value().expected_workspace_revision;
    journal.resulting_workspace_revision = report.value().resulting_workspace_revision;
    journal.verification_results.push_back("target_state_verified");
    journal.state = "complete";
    journal_updated = persist_journal(layout_, journal, false);
    if (!journal_updated) {
        return rollback(journal_updated.error().message, journal_updated.error().path);
    }
    auto released = migration_lock.release();
    if (!released) {
        return failure<MigrationReport>(
            released.error().code, released.error().message, released.error().path);
    }
    report.value().apply_enabled = true;
    report.value().state = "completed";
    report.value().mutation_executed = true;
    return report;
}

std::string migration_detail::report_json(const MigrationReport& report)
{
    json::ArrayBuilder actions;
    for (const MigrationAction& action : report.actions) {
        json::ObjectBuilder item;
        item.add_string("step_id", action.step_id);
        item.add_string("kind", action.kind);
        if (action.source.empty()) item.add_null("source");
        else item.add_string("source", facman::platform::path_to_utf8(action.source));
        item.add_string("target", facman::platform::path_to_utf8(action.target));
        if (action.source_sha256.empty()) item.add_null("source_sha256");
        else item.add_string("source_sha256", action.source_sha256);
        item.add_string("target_sha256", action.target_sha256);
        item.add_bool("backup_required", action.backup_required);
        item.add_bool("journal_required", action.journal_required);
        item.add_string("backup_disposition", action.backup_required ?
            "required_preserve_original" : "not_applicable");
        item.add_string("rollback_disposition", action.kind == "create_workspace_identity" ?
            "remove_created_target" : "remove_created_target");
        actions.add_object(item);
    }
    json::ObjectBuilder document;
    document.add_string("schema", "facman.workspace_migration.v2");
    document.add_string("command", report.operation);
    document.add_string("state", report.state);
    document.add_string("status", report.actions.empty() ? "no_changes" : "changes_detected");
    document.add_string("migration_id", report.migration_id);
    document.add_string("current_format", report.current_format);
    document.add_string("target_format", report.target_format);
    document.add_string("expected_workspace_revision", report.expected_workspace_revision);
    document.add_string("expected_root_identity", report.expected_root_identity);
    document.add_string("inventory_digest", report.inventory_digest);
    document.add_string("plan_digest", report.plan_digest);
    if (report.resulting_workspace_revision.empty()) {
        document.add_null("resulting_workspace_revision");
    } else {
        document.add_string(
            "resulting_workspace_revision", report.resulting_workspace_revision);
    }
    document.add_bool("apply_enabled", report.apply_enabled);
    document.add_bool("confirmation_required", report.confirmation_required);
    document.add_bool("mutation_executed", report.mutation_executed);
    if (!report.operation_id.empty()) {
        json::ObjectBuilder operation;
        operation.add_string("schema", "facman.workspace_migration_operation.v1");
        operation.add_string("operation_id", report.operation_id);
        operation.add_string("attempt_id", report.attempt_id);
        operation.add_string("request_id", report.request_id);
        operation.add_string("idempotency_key", report.idempotency_key);
        operation.add_string("migration_id", report.migration_id);
        operation.add_string("plan_digest", report.plan_digest);
        operation.add_string("expected_workspace_revision", report.expected_workspace_revision);
        operation.add_string("expected_root_identity", report.expected_root_identity);
        operation.add_string("current_phase", report.state);
        operation.add_string("terminal_classification",
            report.state == "completed" ? "completed" : "none");
        json::ArrayBuilder completed_steps;
        if (report.mutation_executed) {
            for (const MigrationAction& action : report.actions) {
                completed_steps.add_string(action.step_id);
            }
        }
        operation.add_array("completed_steps", completed_steps);
        json::ArrayBuilder staged_outputs;
        json::ArrayBuilder committed_outputs;
        if (report.mutation_executed) {
            for (const MigrationAction& action : report.actions) {
                json::ObjectBuilder output;
                output.add_string("path", facman::platform::path_to_utf8(action.target));
                output.add_string("sha256", action.target_sha256);
                committed_outputs.add_object(output);
            }
        }
        operation.add_array("staged_outputs", staged_outputs);
        operation.add_array("committed_outputs", committed_outputs);
        json::ArrayBuilder verification_results;
        if (report.mutation_executed) verification_results.add_string("target_state_verified");
        operation.add_array("verification_results", verification_results);
        operation.add_string("recovery_boundary",
            report.state == "completed" ? "fully_committed" : "no_effects");
        document.add_object("operation", operation);
    }
    document.add_array("actions", actions);
    return document.serialize() + "\n";
}

} // namespace facman::workspace
