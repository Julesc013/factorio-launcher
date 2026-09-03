// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_workspace_migration_internal.h"

#include "fl_workspace_io_internal.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_local_operation_lock.h"
#include "fl_path_safety.h"
#include "fl_system_services.h"

#include <algorithm>
#include <cstdlib>
#include <system_error>
#include <utility>

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
    return Result<T>::failure({
        std::move(code), std::move(message), facman::platform::path_to_utf8(path)});
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

Result<void> ensure_uncommitted_stage_file(
    const fs::path& path,
    const std::string& expected)
{
    facman::platform::PathIdentity identity;
    const auto inspected = facman::platform::inspect_path_no_follow(path, identity);
    if (!inspected.ok()) {
        return failure<void>(inspected.code, inspected.detail, path);
    }
    if (!identity.exists) {
        auto written = write_new_durable(path, expected);
        return written ? Result<void>::success() :
            failure<void>(written.error().code, written.error().message, path);
    }
    if (identity.reparse_or_link ||
        identity.kind != facman::platform::PathObjectKind::regular_file) {
        return failure<void>(
            "workspace_migration_conflict",
            "migration staging path is not a plain regular file",
            path);
    }
    auto current = read_bounded(path);
    if (!current || current.value() != expected) {
        return failure<void>(
            "workspace_migration_conflict",
            "migration staging content differs from its bound payload",
            path);
    }
    return Result<void>::success();
}

Result<void> rollback_migration_journal(
    const WorkspaceLayout& layout,
    const WorkspaceRootInspection& authority,
    MigrationJournal& journal)
{
    journal.state = "rolling_back";
    journal.resulting_workspace_revision.clear();
    auto persisted = persist_journal(layout, journal, false);
    if (!persisted) return persisted;
    while (journal.completed_actions > 0U) {
        const std::size_t index = journal.completed_actions - 1U;
        const MigrationJournalAction& action = journal.actions[index];
        fs::path source;
        fs::path target;
        auto shaped = verify_journal_action_shape(layout, action, source, target);
        if (!shaped) return shaped;
        const auto source_safe = authority.root_authority->validate_descendant(source);
        const auto target_safe = authority.root_authority->validate_descendant(target);
        if (!source_safe.ok() || !target_safe.ok()) {
            const auto& problem = !source_safe.ok() ? source_safe : target_safe;
            return failure<void>(problem.code, problem.detail, target);
        }
        const fs::path backup =
            migration_data_root(layout, journal.id) / (std::to_string(index) + ".source.json");
        auto current_source = read_bounded(source);
        auto backed_source = read_bounded(backup);
        if (!current_source || !backed_source ||
            sha256_text(current_source ? current_source.value() : std::string {}) !=
                action.source_sha256 ||
            sha256_text(backed_source ? backed_source.value() : std::string {}) !=
                action.source_sha256) {
            journal.state = "recovery_required";
            (void)persist_journal(layout, journal, false);
            return failure<void>(
                "workspace_migration_recovery_required",
                "migration rollback backup or original no longer matches its bound digest",
                backup);
        }
        facman::platform::StableInputFile target_file;
        auto opened = target_file.open_no_follow(target);
        if (!opened.ok() || target_file.size() > 1024ULL * 1024ULL) {
            journal.state = "recovery_required";
            (void)persist_journal(layout, journal, false);
            return failure<void>(
                "workspace_migration_recovery_required",
                opened.ok() ? "migration rollback target exceeds its bounded size" : opened.detail,
                target);
        }
        std::string target_text(static_cast<std::size_t>(target_file.size()), '\0');
        std::uint64_t offset = 0U;
        while (offset < target_file.size()) {
            const std::size_t count = target_file.read_at(
                offset, target_text.data() + static_cast<std::size_t>(offset),
                static_cast<std::size_t>(target_file.size() - offset));
            if (count == 0U) break;
            offset += count;
        }
        if (offset != target_file.size() || !target_file.revalidate().ok() ||
            sha256_text(target_text) != action.target_sha256) {
            journal.state = "recovery_required";
            (void)persist_journal(layout, journal, false);
            return failure<void>(
                "workspace_migration_recovery_required",
                "migration rollback target no longer matches its committed digest", target);
        }
        auto stable = revalidate_workspace_root(authority);
        if (!stable) return failure<void>(
            stable.error().code, stable.error().message, layout.root());
        const auto removed = facman::platform::remove_exact_object(
            target, target_file.identity());
        if (!removed.ok()) {
            journal.state = "recovery_required";
            (void)persist_journal(layout, journal, false);
            return failure<void>(
                "workspace_migration_recovery_required", removed.detail, target);
        }
        journal.completed_actions = index;
        journal.verification_results.push_back(
            "rollback_output_removed:" + action.step_id);
        persisted = persist_journal(layout, journal, false);
        if (!persisted) return persisted;
        if (workspace_migration_fault(
                "during_rollback", journal.actions.size() - journal.completed_actions)) {
            return failure<void>(
                "workspace_migration_interrupted",
                "migration rollback stopped at an injected recovery boundary", target);
        }
    }
    auto restored = build_migration_report(layout, "workspace.migration.rollback");
    if (!restored || restored.value().plan_digest != journal.plan_digest ||
        restored.value().expected_workspace_revision != journal.expected_workspace_revision) {
        journal.state = "recovery_required";
        (void)persist_journal(layout, journal, false);
        return failure<void>(
            "workspace_migration_recovery_required",
            "migration rollback did not restore the exact bound source state", layout.root());
    }
    if (workspace_migration_fault("after_rollback_before_receipt")) {
        return failure<void>(
            "workspace_migration_interrupted",
            "migration rollback stopped after restoration and before its terminal receipt",
            layout.root());
    }
    journal.state = "rolled_back";
    journal.verification_results.push_back("rollback_state_verified");
    return persist_journal(layout, journal, false);
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
    if (journal.state == "rolling_back") {
        return rollback_migration_journal(layout, authority, journal);
    }
    const fs::path data_root = migration_data_root(layout, journal.id);
    auto data_ready = ensure_owned_directory(authority, data_root);
    if (!data_ready) return data_ready;
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
        auto expected_payload = current_source ? expected_journal_target_payload(
            action, source, current_source.value()) : failure<std::string>(
                "workspace_migration_conflict", "migration source is unreadable", source);
        if (!current_source || !expected_payload ||
            sha256_text(current_source ? current_source.value() : std::string {}) != action.source_sha256 ||
            sha256_text(expected_payload ? expected_payload.value() : std::string {}) != action.target_sha256) {
            return failure<void>(
                "workspace_migration_conflict",
                "migration source or derived target changed during recovery", source);
        }
        if (index < journal.staged_actions) {
            auto backed_source = read_bounded(source_backup);
            auto payload = read_bounded(target_payload);
            if (!backed_source || !payload ||
                backed_source.value() != current_source.value() ||
                payload.value() != expected_payload.value()) {
                return failure<void>(
                    "workspace_migration_conflict",
                    "journaled migration staging changed during recovery", source);
            }
        } else {
            auto staged = ensure_uncommitted_stage_file(
                source_backup, current_source.value());
            if (!staged) return staged;
            staged = ensure_uncommitted_stage_file(
                target_payload, expected_payload.value());
            if (!staged) return staged;
            journal.staged_actions = index + 1U;
            persisted = persist_journal(layout, journal, false);
            if (!persisted) return persisted;
        }
        auto stable = revalidate_workspace_root(authority);
        if (!stable) return failure<void>(stable.error().code, stable.error().message, layout.root());
        facman::platform::PathIdentity target_identity;
        const auto target_status = facman::platform::inspect_path_no_follow(target, target_identity);
        if (!target_status.ok()) return failure<void>(target_status.code, target_status.detail, target);
        if (!target_identity.exists) {
            auto written = write_new_durable(target, expected_payload.value());
            if (!written) return failure<void>(written.error().code, written.error().message, target);
        } else {
            if (target_identity.reparse_or_link ||
                target_identity.kind != facman::platform::PathObjectKind::regular_file) {
                return failure<void>(
                    "workspace_migration_conflict",
                    "migration recovery target is not a plain regular file", target);
            }
            auto current_target = read_bounded(target);
            if (!current_target || sha256_text(current_target.value()) != action.target_sha256) {
                return failure<void>(
                    "workspace_migration_conflict",
                    "migration recovery refuses to replace a divergent target", target);
            }
        }
        journal.completed_actions = index + 1U;
        const std::string verification = "committed_output_verified:" + action.step_id;
        if (std::find(journal.verification_results.begin(), journal.verification_results.end(),
                verification) == journal.verification_results.end()) {
            journal.verification_results.push_back(verification);
        }
        persisted = persist_journal(layout, journal, false);
        if (!persisted) return persisted;
    }
    if (std::find(journal.verification_results.begin(), journal.verification_results.end(),
            "staged_payloads_verified") == journal.verification_results.end()) {
        journal.verification_results.insert(
            journal.verification_results.begin(), "staged_payloads_verified");
        persisted = persist_journal(layout, journal, false);
        if (!persisted) return persisted;
    }
    auto stable = revalidate_workspace_root(authority);
    if (!stable) return failure<void>(stable.error().code, stable.error().message, layout.root());
    auto resulting = build_migration_report(layout, "workspace.migration.apply");
    if (!resulting || !resulting.value().actions.empty()) {
        return failure<void>(
            resulting ? "workspace_migration_recovery_required" : resulting.error().code,
            resulting ? "resumed migration did not verify as healthy" : resulting.error().message,
            layout.root());
    }
    if (journal.format_version == 2U) {
        journal.resulting_workspace_revision = resulting.value().expected_workspace_revision;
        if (std::find(journal.verification_results.begin(), journal.verification_results.end(),
                "target_state_verified") == journal.verification_results.end()) {
            journal.verification_results.push_back("target_state_verified");
        }
    }
    journal.state = "complete";
    return persist_journal(layout, journal, false);
}

MigrationReport migration_report_from_journal(
    const WorkspaceLayout& layout,
    const MigrationJournal& journal)
{
    MigrationReport report;
    report.operation = "workspace.migration.apply";
    report.state = journal.state == "complete" ? "completed" :
        journal.state == "applying" ? "interrupted_recoverable" :
        journal.state == "rolling_back" ? "rollback_available" : journal.state;
    report.migration_id = journal.migration_id;
    report.current_format = "facman.factorio.workspace.v1";
    report.expected_workspace_revision = journal.expected_workspace_revision;
    report.expected_root_identity = journal.expected_root_identity;
    report.inventory_digest = journal.inventory_digest;
    report.plan_digest = journal.plan_digest;
    report.resulting_workspace_revision = journal.resulting_workspace_revision;
    report.apply_enabled = true;
    report.mutation_executed = journal.state == "complete";
    report.journal_projection = true;
    report.rollback_retained = journal.rollback_retained;
    report.completed_action_count = journal.completed_actions;
    report.verification_results = journal.verification_results;
    report.operation_id = journal.operation_id;
    report.attempt_id = journal.attempt_id;
    report.request_id = journal.request_id;
    report.idempotency_key = journal.idempotency_key;
    for (const MigrationJournalAction& action : journal.actions) {
        auto source = resolve_relative_path(layout, action.source);
        auto target = resolve_relative_path(layout, action.target);
        if (!source || !target) continue;
        MigrationAction projected(
            action.kind, source.take_value(), target.take_value(), true, true);
        projected.step_id = action.step_id;
        projected.source_sha256 = action.source_sha256;
        projected.target_sha256 = action.target_sha256;
        report.actions.push_back(std::move(projected));
    }
    return report;
}

Result<MigrationReport> migration_report_from_creation(
    const WorkspaceLayout& layout,
    const WorkspaceCreationJournal& journal,
    const char* command)
{
    auto current = build_migration_report(layout, command);
    if (!current) return current;
    current.value().operation = command;
    current.value().state = journal.state == "completed" ?
        "completed" : "interrupted_recoverable";
    current.value().current_format = "uninitialized";
    current.value().migration_id = journal.migration_id;
    current.value().expected_workspace_revision = journal.expected_workspace_revision;
    current.value().expected_root_identity = journal.expected_root_identity;
    current.value().inventory_digest = journal.inventory_digest;
    current.value().plan_digest = journal.plan_digest;
    current.value().resulting_workspace_revision = journal.resulting_workspace_revision;
    current.value().apply_enabled = true;
    current.value().mutation_executed = journal.state == "completed";
    current.value().journal_projection = false;
    current.value().completed_action_count = journal.state == "completed" ? 1U : 0U;
    current.value().operation_id = journal.operation_id;
    current.value().attempt_id = journal.attempt_id;
    current.value().request_id = journal.request_id;
    current.value().idempotency_key = journal.idempotency_key;
    current.value().actions.clear();
    MigrationAction creation(
        "create_workspace_identity", {}, layout.manifest(), false, true);
    creation.step_id = "step-1";
    creation.target_sha256 = journal.target_sha256;
    current.value().actions.push_back(std::move(creation));
    if (journal.state == "completed") {
        current.value().verification_results.push_back("target_state_verified");
    }
    return current;
}

bool valid_control_request(const MigrationControlRequest& request, std::string& detail)
{
    return facman::base::validate_identifier(request.target_operation_id, detail) &&
        facman::base::validate_identifier(request.request_id, detail) &&
        facman::base::validate_identifier(request.operation_id, detail) &&
        facman::base::validate_identifier(request.attempt_id, detail) &&
        facman::base::validate_identifier(request.idempotency_key, detail) &&
        sha256_text_valid(request.expected_workspace_revision) &&
        request.confirmation == "explicit";
}

bool same_request_inputs(
    const MigrationApplyRequest& request,
    const std::string& plan_digest,
    const std::string& expected_revision,
    const std::string& expected_root)
{
    return request.plan_digest == plan_digest &&
        request.expected_workspace_revision == expected_revision &&
        request.expected_root_identity == expected_root;
}

} // namespace

MigrationReport project_migration_journal(
    const WorkspaceLayout& layout,
    const MigrationJournal& journal)
{
    return migration_report_from_journal(layout, journal);
}

bool workspace_migration_fault(
    const std::string& boundary,
    std::size_t completed_actions)
{
    const char* requested = std::getenv("FACMAN_TEST_WORKSPACE_MIGRATION_FAULT");
    if (requested == nullptr) return false;
    const std::string value(requested);
    return value == boundary ||
        (completed_actions > 0U &&
         value == boundary + ":" + std::to_string(completed_actions));
}

Result<void> ScopedMigrationLock::acquire(const fs::path& path)
{
    auto result = lock_.create(path);
    if (result.code == facman::base::StableLockCode::exists) {
        facman::base::StableLocalLock stale;
        std::string content;
        auto opened = stale.open_existing(path, 4096U, content);
        if (opened.code == facman::base::StableLockCode::contended) {
            return failure<void>(
                "workspace_migration_conflict",
                "another workspace migration owns the migration lock", path);
        }
        if (!opened.acquired() || !recognized_migration_lock(content)) {
            return failure<void>(
                "workspace_migration_conflict",
                "existing workspace migration lock is unsafe or unrecognized", path);
        }
        std::string detail;
        if (!stale.remove_exact(detail)) {
            return failure<void>("workspace_migration_conflict", detail, path);
        }
        result = lock_.create(path);
    }
    if (!result.acquired()) {
        return failure<void>("workspace_migration_conflict", result.detail, path);
    }
    json::ObjectBuilder document;
    document.add_string("schema", "facman.workspace_migration_lock.v1");
    document.add_string("identity", lock_.identity_text());
    std::string detail;
    if (!lock_.write_text(document.serialize() + "\n", detail)) {
        (void)lock_.remove_exact(detail);
        return failure<void>("workspace_migration_conflict", detail, path);
    }
    acquired_ = true;
    return Result<void>::success();
}

Result<void> ScopedMigrationLock::release()
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

ScopedMigrationLock::~ScopedMigrationLock()
{
    if (!acquired_) return;
    std::string ignored;
    (void)lock_.remove_exact(ignored);
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
         schema.value() != "usk.installed_state.v1") || stored_id.value() != expected_id) {
        return failure<void>(
            schema.value() != "factorio.install_ref.v1" &&
                    schema.value() != "usk.installed_state.v1" ?
                "workspace_record_future_or_unknown_schema" : "workspace_record_id_mismatch",
            schema.value() != "factorio.install_ref.v1" &&
                    schema.value() != "usk.installed_state.v1" ? schema.value() : stored_id.value(),
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
    const std::string current_schema = optional_string(
        document.value(), "schema", "factorio.instance.legacy");
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
        return failure<std::string>("workspace_record_id_mismatch", stored_id.value(), source);
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
        const bool legacy_name = name.size() > legacy_suffix.size() &&
            name.compare(name.size() - legacy_suffix.size(), legacy_suffix.size(), legacy_suffix) == 0;
        const bool current_name = name.size() > current_suffix.size() &&
            name.compare(name.size() - current_suffix.size(), current_suffix.size(), current_suffix) == 0;
        if (fs::is_regular_file(status) && (legacy_name || current_name)) {
            journals.push_back(iterator->path());
        }
    }
    if (error) {
        return failure<void>(
            "workspace_migration_scan_failed", error.message(), migration_root(layout));
    }
    std::sort(journals.begin(), journals.end());
    for (const fs::path& path : journals) {
        auto journal = load_migration_journal(path);
        if (!journal) return failure<void>(journal.error().code, journal.error().message, path);
        auto resumed = resume_migration_journal(layout, authority, journal.value());
        if (!resumed) return resumed;
    }
    return Result<void>::success();
}

Result<MigrationReport> rollback_migration_operation(
    const WorkspaceLayout& layout,
    const MigrationControlRequest& request)
{
    std::string detail;
    if (!valid_control_request(request, detail)) {
        return failure<MigrationReport>(
            "workspace_migration_confirmation_required",
            "migration rollback requires exact operation identities, current revision, and explicit confirmation");
    }
    auto authority = inspect_workspace_root(layout.root());
    if (!authority || authority.value().state != WorkspaceRootState::facman_owned ||
        !authority.value().mutation_allowed || !authority.value().root_authority) {
        return failure<MigrationReport>(
            "workspace_migration_conflict",
            "migration rollback requires the original owned workspace root", layout.root());
    }
    const fs::path path = migration_journal_path(layout, request.target_operation_id, 2U);
    auto journal = load_migration_journal(path);
    if (!journal) return failure<MigrationReport>(
        journal.error().code, journal.error().message, journal.error().path);
    ScopedMigrationLock lock;
    auto locked = lock.acquire(migration_root(layout) / "workspace-migration.lock");
    if (!locked) return failure<MigrationReport>(
        locked.error().code, locked.error().message, locked.error().path);
    journal = load_migration_journal(path);
    if (!journal) return failure<MigrationReport>(
        journal.error().code, journal.error().message, journal.error().path);
    const bool same_control =
        journal.value().rollback_operation_id == request.operation_id &&
        journal.value().rollback_attempt_id == request.attempt_id &&
        journal.value().rollback_request_id == request.request_id &&
        journal.value().rollback_idempotency_key == request.idempotency_key &&
        journal.value().rollback_expected_workspace_revision ==
            request.expected_workspace_revision;
    if (!journal.value().rollback_operation_id.empty() && !same_control) {
        return failure<MigrationReport>(
            "workspace_migration_conflict",
            "rollback operation or idempotency identity was reused with changed inputs", path);
    }
    auto current = build_migration_report(layout, "workspace.migration.rollback");
    if (!current || (!same_control && journal.value().state != "rolled_back" &&
            current.value().expected_workspace_revision !=
                request.expected_workspace_revision)) {
        return failure<MigrationReport>(
            current ? "workspace_migration_stale_plan" : current.error().code,
            current ? "workspace revision changed before rollback" : current.error().message,
            layout.root());
    }
    if (journal.value().state != "rolled_back") {
        if (journal.value().state != "complete" && journal.value().state != "applying" &&
            journal.value().state != "rolling_back") {
            return failure<MigrationReport>(
                "workspace_migration_recovery_required",
                "migration journal is not safely rollback-eligible", path);
        }
        journal.value().rollback_operation_id = request.operation_id;
        journal.value().rollback_attempt_id = request.attempt_id;
        journal.value().rollback_request_id = request.request_id;
        journal.value().rollback_idempotency_key = request.idempotency_key;
        journal.value().rollback_expected_workspace_revision =
            request.expected_workspace_revision;
        auto rolled_back = rollback_migration_journal(
            layout, authority.value(), journal.value());
        if (!rolled_back) return failure<MigrationReport>(
            rolled_back.error().code, rolled_back.error().message, rolled_back.error().path);
    }
    auto restored = build_migration_report(layout, "workspace.migration.rollback");
    if (!restored || restored.value().plan_digest != journal.value().plan_digest) {
        return failure<MigrationReport>(
            restored ? "workspace_migration_recovery_required" : restored.error().code,
            restored ? "rolled-back workspace no longer matches the original plan" :
                restored.error().message,
            layout.root());
    }
    restored.value().state = "rolled_back";
    restored.value().resulting_workspace_revision =
        restored.value().expected_workspace_revision;
    restored.value().apply_enabled = true;
    restored.value().mutation_executed = true;
    restored.value().rollback_executed = true;
    restored.value().completed_action_count = restored.value().actions.size();
    restored.value().verification_results = {"rollback_state_verified"};
    restored.value().operation_id = request.operation_id;
    restored.value().attempt_id = request.attempt_id;
    restored.value().request_id = request.request_id;
    restored.value().idempotency_key = request.idempotency_key;
    auto released = lock.release();
    if (!released) return failure<MigrationReport>(
        released.error().code, released.error().message, released.error().path);
    return restored;
}

Result<MigrationReport> inspect_migration_operation(
    const WorkspaceLayout& layout,
    const std::string& operation_id,
    const char* command)
{
    std::string detail;
    if (!facman::base::validate_identifier(operation_id, detail)) {
        return failure<MigrationReport>(
            "workspace_migration_apply_unproven",
            "workspace migration operation identifier is invalid");
    }
    const fs::path migration_path = migration_journal_path(layout, operation_id, 2U);
    std::error_code error;
    if (fs::is_regular_file(migration_path, error) && !error) {
        auto journal = load_migration_journal(migration_path);
        if (!journal) return failure<MigrationReport>(
            journal.error().code, journal.error().message, journal.error().path);
        MigrationReport report = migration_report_from_journal(layout, journal.value());
        report.operation = command;
        auto current = build_migration_report(layout, command);
        if (!current) return failure<MigrationReport>(
            current.error().code, current.error().message, current.error().path);
        report.observed_workspace_revision =
            current.value().expected_workspace_revision;
        return Result<MigrationReport>::success(std::move(report));
    }
    const fs::path creation_path = migration_root(layout) /
        (operation_id + ".workspace-creation.v1.json");
    auto creation = load_workspace_creation_journal(creation_path);
    if (!creation) return failure<MigrationReport>(
        creation.error().code, creation.error().message, creation.error().path);
    auto report = migration_report_from_creation(layout, creation.value(), command);
    if (!report) return report;
    auto current = build_migration_report(layout, command);
    if (!current) return failure<MigrationReport>(
        current.error().code, current.error().message, current.error().path);
    report.value().observed_workspace_revision =
        current.value().expected_workspace_revision;
    return report;
}

Result<MigrationReport> resume_migration_operation(
    const WorkspaceLayout& layout,
    const MigrationControlRequest& request,
    const char* command)
{
    std::string detail;
    if (!valid_control_request(request, detail)) {
        return failure<MigrationReport>(
            "workspace_migration_confirmation_required",
            "migration recovery requires exact operation identities, current revision, and explicit confirmation");
    }
    const fs::path migration_path =
        migration_journal_path(layout, request.target_operation_id, 2U);
    std::error_code error;
    if (fs::is_regular_file(migration_path, error) && !error) {
        auto journal = load_migration_journal(migration_path);
        if (!journal) return failure<MigrationReport>(
            journal.error().code, journal.error().message, journal.error().path);
        if (journal.value().state == "recovery_required") {
            return failure<MigrationReport>(
                "workspace_migration_recovery_required",
                "journal evidence does not prove a safe automatic recovery action",
                migration_path);
        }
        if (journal.value().state == "rolling_back") {
            if (std::string(command) != "workspace.migration.recover" ||
                journal.value().rollback_operation_id.empty()) {
                return failure<MigrationReport>(
                    "workspace_migration_recovery_required",
                    "rollback is in progress; use the recover action", migration_path);
            }
            MigrationControlRequest rollback;
            rollback.target_operation_id = journal.value().operation_id;
            rollback.expected_workspace_revision =
                journal.value().rollback_expected_workspace_revision;
            rollback.confirmation = "explicit";
            rollback.request_id = journal.value().rollback_request_id;
            rollback.operation_id = journal.value().rollback_operation_id;
            rollback.attempt_id = journal.value().rollback_attempt_id;
            rollback.idempotency_key = journal.value().rollback_idempotency_key;
            auto recovered = rollback_migration_operation(layout, rollback);
            if (recovered) recovered.value().operation = command;
            return recovered;
        }
        if (journal.value().state == "complete" || journal.value().state == "rolled_back") {
            MigrationReport report = migration_report_from_journal(layout, journal.value());
            report.operation = command;
            return Result<MigrationReport>::success(std::move(report));
        }
        auto current = build_migration_report(layout, command);
        if (!current || current.value().expected_workspace_revision !=
                request.expected_workspace_revision) {
            return failure<MigrationReport>(
                current ? "workspace_migration_stale_plan" : current.error().code,
                current ? "workspace revision changed before resume" : current.error().message,
                layout.root());
        }
        MigrationApplyRequest original;
        original.expected_workspace_revision = journal.value().expected_workspace_revision;
        original.expected_root_identity = journal.value().expected_root_identity;
        original.plan_digest = journal.value().plan_digest;
        original.confirmation = "explicit";
        original.request_id = journal.value().request_id;
        original.operation_id = journal.value().operation_id;
        original.attempt_id = journal.value().attempt_id;
        original.idempotency_key = journal.value().idempotency_key;
        auto replayed = replay_migration_operation(layout, original);
        if (!replayed) return failure<MigrationReport>(
            replayed.error().code, replayed.error().message, replayed.error().path);
        if (!replayed.value()) return failure<MigrationReport>(
            "workspace_migration_recovery_required",
            "migration journal could not be selected for exact resume", migration_path);
        replayed.value()->operation = command;
        return Result<MigrationReport>::success(std::move(*replayed.value()));
    }

    const fs::path creation_path = migration_root(layout) /
        (request.target_operation_id + ".workspace-creation.v1.json");
    auto creation = load_workspace_creation_journal(creation_path);
    if (!creation) return failure<MigrationReport>(
        creation.error().code, creation.error().message, creation.error().path);
    auto current = build_migration_report(layout, command);
    if (!current || (creation.value().state != "completed" &&
            current.value().expected_workspace_revision !=
                request.expected_workspace_revision)) {
        return failure<MigrationReport>(
            current ? "workspace_migration_stale_plan" : current.error().code,
            current ? "workspace revision changed before creation resume" :
                current.error().message,
            layout.root());
    }
    MigrationApplyRequest original;
    original.expected_workspace_revision = creation.value().expected_workspace_revision;
    original.expected_root_identity = creation.value().expected_root_identity;
    original.plan_digest = creation.value().plan_digest;
    original.confirmation = "explicit";
    original.request_id = creation.value().request_id;
    original.operation_id = creation.value().operation_id;
    original.attempt_id = creation.value().attempt_id;
    original.idempotency_key = creation.value().idempotency_key;
    auto replayed = replay_migration_operation(layout, original);
    if (!replayed || !replayed.value()) return failure<MigrationReport>(
        replayed ? "workspace_migration_recovery_required" : replayed.error().code,
        replayed ? "workspace creation journal could not be resumed" :
            replayed.error().message,
        creation_path);
    replayed.value()->operation = command;
    return Result<MigrationReport>::success(std::move(*replayed.value()));
}

Result<std::optional<MigrationReport>> replay_migration_operation(
    const WorkspaceLayout& layout,
    const MigrationApplyRequest& request)
{
    std::error_code error;
    if (!fs::is_directory(migration_root(layout), error) || error) {
        return Result<std::optional<MigrationReport>>::success(std::nullopt);
    }
    auto authority = inspect_workspace_root(layout.root());
    if (!authority || authority.value().state != WorkspaceRootState::facman_owned ||
        !authority.value().mutation_allowed || !authority.value().root_authority) {
        return Result<std::optional<MigrationReport>>::success(std::nullopt);
    }
    std::vector<fs::path> records;
    for (fs::directory_iterator iterator(
             migration_root(layout), fs::directory_options::skip_permission_denied, error), end;
         iterator != end && !error; iterator.increment(error)) {
        const fs::file_status status = iterator->symlink_status(error);
        if (error) break;
        const std::string name = iterator->path().filename().string();
        if (fs::is_regular_file(status) &&
            (name.find(".workspace-migration.v2.json") != std::string::npos ||
             name.find(".workspace-creation.v1.json") != std::string::npos)) {
            records.push_back(iterator->path());
        }
    }
    if (error) {
        return failure<std::optional<MigrationReport>>(
            "workspace_migration_scan_failed", error.message(), migration_root(layout));
    }
    std::sort(records.begin(), records.end());
    for (const fs::path& path : records) {
        if (path.filename().string().find(".workspace-creation.v1.json") != std::string::npos) {
            auto journal = load_workspace_creation_journal(path);
            if (!journal) {
                return failure<std::optional<MigrationReport>>(
                    journal.error().code, journal.error().message, path);
            }
            const bool selected = journal.value().operation_id == request.operation_id ||
                journal.value().idempotency_key == request.idempotency_key;
            if (!selected) continue;
            if (journal.value().idempotency_key != request.idempotency_key ||
                !same_request_inputs(request, journal.value().plan_digest,
                    journal.value().expected_workspace_revision,
                    journal.value().expected_root_identity)) {
                return failure<std::optional<MigrationReport>>(
                    "workspace_migration_conflict",
                    "operation or idempotency identity was reused with changed inputs", path);
            }
            ScopedMigrationLock lock;
            auto locked = lock.acquire(migration_root(layout) / "workspace-migration.lock");
            if (!locked) return failure<std::optional<MigrationReport>>(
                locked.error().code, locked.error().message, locked.error().path);
            auto current = build_migration_report(layout, "workspace.migration.apply");
            if (current && journal.value().state == "applying" &&
                current.value().actions.size() == 1U &&
                current.value().actions.front().kind == "create_workspace_identity" &&
                authority.value().workspace_id == journal.value().workspace_id) {
                auto created = WorkspaceRepository(layout).ensure();
                if (!created) return failure<std::optional<MigrationReport>>(
                    created.error().code, created.error().message, created.error().path);
                current = build_migration_report(layout, "workspace.migration.apply");
            }
            if (!current || !current.value().actions.empty()) {
                return failure<std::optional<MigrationReport>>(
                    current ? "workspace_migration_recovery_required" : current.error().code,
                    current ? "workspace creation cannot be finalized safely" : current.error().message,
                    layout.root());
            }
            if (journal.value().state != "completed") {
                journal.value().state = "completed";
                journal.value().resulting_workspace_revision =
                    current.value().expected_workspace_revision;
                auto saved = write_replace_durable(path, workspace_creation_journal_json(
                    request, journal.value().workspace_id, journal.value().state,
                    journal.value().resulting_workspace_revision,
                    journal.value().migration_id, journal.value().inventory_digest,
                    journal.value().target_sha256));
                if (!saved) return failure<std::optional<MigrationReport>>(
                    saved.error().code, saved.error().message, saved.error().path);
            } else if (journal.value().resulting_workspace_revision !=
                       current.value().expected_workspace_revision) {
                return failure<std::optional<MigrationReport>>(
                    "workspace_migration_conflict",
                    "completed workspace creation no longer matches its terminal revision", path);
            }
            current.value().state = "completed";
            current.value().current_format = "uninitialized";
            current.value().migration_id = journal.value().migration_id;
            current.value().expected_workspace_revision =
                journal.value().expected_workspace_revision;
            current.value().expected_root_identity = journal.value().expected_root_identity;
            current.value().inventory_digest = journal.value().inventory_digest;
            current.value().plan_digest = journal.value().plan_digest;
            current.value().resulting_workspace_revision =
                journal.value().resulting_workspace_revision;
            current.value().apply_enabled = true;
            current.value().mutation_executed = true;
            current.value().operation_id = journal.value().operation_id;
            current.value().attempt_id = journal.value().attempt_id;
            current.value().request_id = journal.value().request_id;
            current.value().idempotency_key = journal.value().idempotency_key;
            MigrationAction creation(
                "create_workspace_identity", {}, layout.manifest(), false, true);
            creation.step_id = "step-1";
            creation.target_sha256 = journal.value().target_sha256;
            current.value().actions.push_back(std::move(creation));
            auto released = lock.release();
            if (!released) return failure<std::optional<MigrationReport>>(
                released.error().code, released.error().message, released.error().path);
            return Result<std::optional<MigrationReport>>::success(
                std::optional<MigrationReport>(current.take_value()));
        }

        auto journal = load_migration_journal(path);
        if (!journal) return failure<std::optional<MigrationReport>>(
            journal.error().code, journal.error().message, path);
        const bool selected = journal.value().operation_id == request.operation_id ||
            journal.value().idempotency_key == request.idempotency_key;
        if (!selected) continue;
        if (journal.value().idempotency_key != request.idempotency_key ||
            !same_request_inputs(request, journal.value().plan_digest,
                journal.value().expected_workspace_revision,
                journal.value().expected_root_identity)) {
            return failure<std::optional<MigrationReport>>(
                "workspace_migration_conflict",
                "operation or idempotency identity was reused with changed inputs", path);
        }
        ScopedMigrationLock lock;
        auto locked = lock.acquire(migration_root(layout) / "workspace-migration.lock");
        if (!locked) return failure<std::optional<MigrationReport>>(
            locked.error().code, locked.error().message, locked.error().path);
        auto resumed = resume_migration_journal(layout, authority.value(), journal.value());
        if (!resumed) return failure<std::optional<MigrationReport>>(
            resumed.error().code, resumed.error().message, resumed.error().path);
        auto current = build_migration_report(layout, "workspace.migration.apply");
        if (!current || current.value().expected_workspace_revision !=
                journal.value().resulting_workspace_revision) {
            return failure<std::optional<MigrationReport>>(
                current ? "workspace_migration_conflict" : current.error().code,
                current ? "completed migration no longer matches its terminal revision" :
                    current.error().message,
                layout.root());
        }
        MigrationReport report = migration_report_from_journal(layout, journal.value());
        auto released = lock.release();
        if (!released) return failure<std::optional<MigrationReport>>(
            released.error().code, released.error().message, released.error().path);
        return Result<std::optional<MigrationReport>>::success(
            std::optional<MigrationReport>(std::move(report)));
    }
    return Result<std::optional<MigrationReport>>::success(std::nullopt);
}

} // namespace facman::workspace
