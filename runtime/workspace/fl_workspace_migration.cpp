// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_workspace_io_internal.h"
#include "fl_workspace_migration_internal.h"

#include "fl_file_io.h"
#include "fl_json.h"
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
using persistence_detail::read_bounded;
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

} // namespace

Result<MigrationReport> build_migration_report(
    const WorkspaceLayout& layout,
    const char* operation)
{
    return migration_report(layout, operation);
}

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
    auto replay = replay_migration_operation(layout_, request);
    if (!replay) {
        return failure<MigrationReport>(
            replay.error().code, replay.error().message, replay.error().path);
    }
    if (replay.value()) {
        return Result<MigrationReport>::success(std::move(*replay.value()));
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
                authority.workspace_id, "applying", {}, report.value().migration_id,
                report.value().inventory_digest, report.value().actions.front().target_sha256));
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
                report.value().resulting_workspace_revision, report.value().migration_id,
                report.value().inventory_digest, report.value().actions.front().target_sha256));
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
    if (workspace_migration_fault("after_staging_verification")) {
        return failure<MigrationReport>(
            "workspace_migration_interrupted",
            "migration stopped after durable staging verification");
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
        if (workspace_migration_fault("after_commit", index + 1U)) {
            return failure<MigrationReport>(
                "workspace_migration_interrupted",
                "migration stopped after a durably journaled commit", item.action.target);
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
    if (workspace_migration_fault("before_terminal_receipt")) {
        return failure<MigrationReport>(
            "workspace_migration_interrupted",
            "migration stopped after target verification and before its terminal receipt");
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
    return Result<MigrationReport>::success(
        project_migration_journal(layout_, journal));
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
    if (!report.observed_workspace_revision.empty()) {
        document.add_string("observed_workspace_revision", report.observed_workspace_revision);
    }
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
            report.state == "completed" ? "completed" :
            report.state == "rolled_back" ? "rolled_back" :
            report.state == "recovery_required" ? "recovery_required" : "none");
        json::ArrayBuilder completed_steps;
        const std::size_t completed_count = report.journal_projection ?
            report.completed_action_count : report.mutation_executed ?
                report.actions.size() : 0U;
        for (std::size_t index = 0U;
             index < completed_count && index < report.actions.size(); ++index) {
            completed_steps.add_string(report.actions[index].step_id);
        }
        operation.add_array("completed_steps", completed_steps);
        json::ArrayBuilder staged_outputs;
        json::ArrayBuilder committed_outputs;
        if (report.journal_projection) {
            for (std::size_t index = 0U; index < report.actions.size(); ++index) {
                json::ObjectBuilder output;
                output.add_string(
                    "path", facman::platform::path_to_utf8(report.actions[index].target));
                output.add_string("sha256", report.actions[index].target_sha256);
                staged_outputs.add_object(output);
                if (index < completed_count && !report.rollback_executed) {
                    json::ObjectBuilder committed;
                    committed.add_string(
                        "path", facman::platform::path_to_utf8(report.actions[index].target));
                    committed.add_string("sha256", report.actions[index].target_sha256);
                    committed_outputs.add_object(committed);
                }
            }
        } else if (report.mutation_executed && !report.rollback_executed) {
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
        if (!report.verification_results.empty()) {
            for (const std::string& result : report.verification_results) {
                verification_results.add_string(result);
            }
        } else if (report.mutation_executed) {
            verification_results.add_string("target_state_verified");
        }
        operation.add_array("verification_results", verification_results);
        const std::string recovery_boundary = report.state == "completed" ?
            "fully_committed" : report.state == "rolled_back" ? "rolled_back" :
            report.journal_projection && completed_count == 0U ? "staged_only" :
            report.journal_projection ? "partially_committed_recoverable" : "no_effects";
        operation.add_string("recovery_boundary", recovery_boundary);
        document.add_object("operation", operation);
    }
    if (report.journal_projection || report.state == "interrupted_recoverable" ||
        report.state == "recovery_required" || report.state == "rolled_back") {
        const bool resume_available = report.state == "interrupted_recoverable";
        const bool rollback_available = report.rollback_retained &&
            report.completed_action_count > 0U && report.state != "rolled_back";
        json::ArrayBuilder safe_actions;
        safe_actions.add_string("inspect");
        if (resume_available) safe_actions.add_string("resume");
        if (resume_available || report.state == "rollback_available") {
            safe_actions.add_string("recover");
        }
        if (rollback_available) safe_actions.add_string("rollback");
        if (report.state == "recovery_required") safe_actions.add_string("support_export");
        json::ObjectBuilder recovery;
        recovery.add_bool("resume_available", resume_available);
        recovery.add_bool("rollback_available", rollback_available);
        recovery.add_bool("rollback_retained", report.rollback_retained);
        recovery.add_array("safe_actions", safe_actions);
        document.add_object("recovery", recovery);
    }
    document.add_array("actions", actions);
    return document.serialize() + "\n";
}

} // namespace facman::workspace
