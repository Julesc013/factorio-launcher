// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_workspace_migration_internal.h"

#include "fl_workspace_io_internal.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_system_services.h"

#include <algorithm>
#include <limits>
#include <system_error>
#include <utility>

namespace facman::workspace {
namespace fs = std::filesystem;
namespace json = facman::core::json;
using persistence_detail::parse_record;
using persistence_detail::write_new_durable;
namespace {

template <typename T>
Result<T> failure(std::string code, std::string message, const fs::path& path = {})
{
    return Result<T>::failure({
        std::move(code), std::move(message), facman::platform::path_to_utf8(path)});
}

std::string migration_journal_json(const MigrationJournal& journal)
{
    if (journal.format_version == 1U) {
        json::ArrayBuilder actions;
        for (const MigrationJournalAction& action : journal.actions) {
            json::ObjectBuilder item;
            item.add_string("kind", action.kind);
            item.add_string("source", action.source);
            item.add_string("target", action.target);
            item.add_string("source_sha256", action.source_sha256);
            item.add_string("target_sha256", action.target_sha256);
            actions.add_object(item);
        }
        json::ObjectBuilder legacy;
        legacy.add_string("schema", "facman.workspace_migration_journal.v1");
        legacy.add_string("migration_id", journal.id);
        legacy.add_string("state", journal.state);
        (void)legacy.add_unsigned_integer(
            "completed_actions", static_cast<std::uint64_t>(journal.completed_actions));
        legacy.add_array("actions", actions);
        return legacy.serialize() + "\n";
    }
    json::ArrayBuilder effects;
    json::ArrayBuilder completed_steps;
    json::ArrayBuilder staged_outputs;
    json::ArrayBuilder committed_outputs;
    for (const MigrationJournalAction& action : journal.actions) {
        json::ObjectBuilder item;
        item.add_string("step_id", action.step_id);
        item.add_string("kind", action.kind);
        item.add_string("source", action.source);
        item.add_string("target", action.target);
        item.add_string("source_sha256", action.source_sha256);
        item.add_string("target_sha256", action.target_sha256);
        effects.add_object(item);

        json::ObjectBuilder staged;
        staged.add_string("path", action.target);
        staged.add_string("sha256", action.target_sha256);
        staged_outputs.add_object(staged);
    }
    for (std::size_t index = 0U;
         index < journal.completed_actions && index < journal.actions.size(); ++index) {
        completed_steps.add_string(journal.actions[index].step_id);
        json::ObjectBuilder committed;
        committed.add_string("path", journal.actions[index].target);
        committed.add_string("sha256", journal.actions[index].target_sha256);
        committed_outputs.add_object(committed);
    }
    const bool complete = journal.state == "complete";
    const bool rolled_back = journal.state == "rolled_back";
    const bool recovery_required = journal.state == "recovery_required";
    const std::string phase = complete ? "completed" : rolled_back ? "rolled_back" :
        recovery_required ? "recovery_required" :
        journal.state == "rolling_back" ? "rolling_back" : "applying";
    const std::string terminal = complete ? "completed" : rolled_back ? "rolled_back" :
        recovery_required ? "recovery_required" : "none";
    const std::string boundary = complete ? "fully_committed" :
        rolled_back ? "rolled_back" : journal.completed_actions == 0U ? "staged_only" :
        "partially_committed_recoverable";

    json::ObjectBuilder operation;
    operation.add_string("schema", "facman.workspace_migration_operation.v1");
    operation.add_string("operation_id", journal.operation_id);
    operation.add_string("attempt_id", journal.attempt_id);
    operation.add_string("request_id", journal.request_id);
    operation.add_string("idempotency_key", journal.idempotency_key);
    operation.add_string("migration_id", journal.migration_id);
    operation.add_string("plan_digest", journal.plan_digest);
    operation.add_string("expected_workspace_revision", journal.expected_workspace_revision);
    operation.add_string("expected_root_identity", journal.expected_root_identity);
    operation.add_string("current_phase", phase);
    operation.add_string("terminal_classification", terminal);
    operation.add_array("completed_steps", completed_steps);
    operation.add_array("staged_outputs", staged_outputs);
    operation.add_array("committed_outputs", committed_outputs);
    json::ArrayBuilder operation_verification;
    for (const std::string& result : journal.verification_results) {
        operation_verification.add_string(result);
    }
    operation.add_array("verification_results", operation_verification);
    operation.add_string("recovery_boundary", boundary);

    json::ObjectBuilder identities;
    identities.add_string("root_identity", journal.expected_root_identity);
    identities.add_string("workspace_revision", journal.expected_workspace_revision);
    identities.add_string("inventory_digest", journal.inventory_digest);
    identities.add_string("plan_digest", journal.plan_digest);

    json::ObjectBuilder document;
    document.add_string("schema", "facman.workspace_migration_journal.v2");
    document.add_object("operation", operation);
    document.add_object("input_identities", identities);
    document.add_array("effects", effects);
    json::ArrayBuilder journal_completed;
    for (std::size_t index = 0U;
         index < journal.completed_actions && index < journal.actions.size(); ++index) {
        journal_completed.add_string(journal.actions[index].step_id);
    }
    document.add_array("completed_steps", journal_completed);
    json::ArrayBuilder journal_staged;
    json::ArrayBuilder journal_committed;
    for (std::size_t index = 0U; index < journal.actions.size(); ++index) {
        json::ObjectBuilder staged;
        staged.add_string("path", journal.actions[index].target);
        staged.add_string("sha256", journal.actions[index].target_sha256);
        journal_staged.add_object(staged);
        if (index < journal.completed_actions) {
            json::ObjectBuilder committed;
            committed.add_string("path", journal.actions[index].target);
            committed.add_string("sha256", journal.actions[index].target_sha256);
            journal_committed.add_object(committed);
        }
    }
    document.add_array("staged_outputs", journal_staged);
    document.add_array("committed_outputs", journal_committed);
    json::ArrayBuilder verification;
    for (const std::string& result : journal.verification_results) {
        verification.add_string(result);
    }
    document.add_array("verification_results", verification);
    document.add_string("recovery_boundary", boundary);
    document.add_bool("rollback_retained", journal.rollback_retained);
    if (journal.resulting_workspace_revision.empty()) {
        document.add_null("resulting_workspace_revision");
    } else {
        document.add_string(
            "resulting_workspace_revision", journal.resulting_workspace_revision);
    }
    if (journal.rollback_operation_id.empty()) {
        document.add_null("rollback_operation");
    } else {
        json::ObjectBuilder rollback;
        rollback.add_string("operation_id", journal.rollback_operation_id);
        rollback.add_string("attempt_id", journal.rollback_attempt_id);
        rollback.add_string("request_id", journal.rollback_request_id);
        rollback.add_string("idempotency_key", journal.rollback_idempotency_key);
        rollback.add_string(
            "expected_workspace_revision", journal.rollback_expected_workspace_revision);
        document.add_object("rollback_operation", rollback);
    }
    return document.serialize() + "\n";
}

Result<std::string> journal_string(
    const json::Value& object,
    const char* key,
    const fs::path& path)
{
    const json::Value* value = object.find(key);
    if (value == nullptr || !value->is_string()) {
        return failure<std::string>(
            "workspace_migration_apply_unproven",
            std::string("migration journal string is missing: ") + key,
            path);
    }
    auto decoded = value->string_value();
    if (!decoded || decoded.value().empty()) {
        return failure<std::string>(
            "workspace_migration_apply_unproven",
            std::string("migration journal string is invalid: ") + key,
            path);
    }
    return decoded;
}

} // namespace

bool copy_migration_kind(const std::string& kind)
{
    return kind == "canonicalize_legacy_install_ref" ||
        kind == "canonicalize_legacy_instance_manifest";
}

std::string sha256_text(const std::string& text)
{
    return facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(text.data()), text.size());
}

std::string root_identity_digest(
    const WorkspaceLayout& layout,
    const WorkspaceRootInspection& inspection)
{
    facman::platform::PathIdentity identity;
    if (inspection.root_authority) {
        identity = inspection.root_authority->identity();
    } else {
        std::error_code error;
        fs::path parent = layout.root().parent_path();
        if (parent.empty()) parent = fs::current_path(error);
        if (!error) (void)facman::platform::inspect_path_no_follow(parent, identity);
    }
    const std::string material =
        std::string(workspace_root_state_name(inspection.state)) + "\n" +
        facman::platform::path_to_utf8(inspection.canonical_root) + "\n" +
        std::to_string(identity.device) + ":" + std::to_string(identity.object) + ":" +
        std::to_string(static_cast<unsigned int>(identity.kind));
    return sha256_text(material);
}

std::string random_workspace_uuid()
{
    facman::platform::RandomIdGenerator random;
    std::string value = random.next("workspace");
    value = value.substr(value.find('-') + 1);
    value[12] = '4';
    value[16] = "89ab"[static_cast<unsigned char>(value[16]) % 4];
    return value.substr(0, 8) + "-" + value.substr(8, 4) + "-" +
        value.substr(12, 4) + "-" + value.substr(16, 4) + "-" + value.substr(20, 12);
}

fs::path migration_root(const WorkspaceLayout& layout)
{
    return layout.root() / "transactions" / "workspace-migrations";
}

fs::path migration_journal_path(
    const WorkspaceLayout& layout,
    const std::string& id,
    unsigned int format_version)
{
    return migration_root(layout) /
        (id + (format_version == 1U ? ".workspace-migration.v1.json" :
                                     ".workspace-migration.v2.json"));
}

fs::path migration_data_root(const WorkspaceLayout& layout, const std::string& id)
{
    return migration_root(layout) / (id + ".data");
}

bool safe_relative_text(const fs::path& root, const fs::path& path, std::string& output)
{
    const fs::path normalized_root = root.lexically_normal();
    const fs::path normalized_path = path.lexically_normal();
    const fs::path relative = normalized_path.lexically_relative(normalized_root);
    if (relative.empty() || relative.is_absolute() || relative.has_root_name()) return false;
    for (const fs::path& segment : relative) {
        if (segment.empty() || segment == "." || segment == "..") return false;
    }
    output = relative.generic_u8string();
    return !output.empty() && output.find('\\') == std::string::npos &&
        output.find(':') == std::string::npos;
}

Result<fs::path> resolve_relative_path(
    const WorkspaceLayout& layout,
    const std::string& value)
{
    if (value.empty() || value.find('\\') != std::string::npos ||
        value.find(':') != std::string::npos) {
        return failure<fs::path>(
            "workspace_migration_apply_unproven",
            "migration journal contains a non-portable path");
    }
    const fs::path relative = facman::platform::path_from_utf8(value);
    if (relative.is_absolute() || relative.has_root_name() ||
        relative.lexically_normal() != relative) {
        return failure<fs::path>(
            "workspace_migration_apply_unproven",
            "migration journal path is not normalized and relative");
    }
    for (const fs::path& segment : relative) {
        if (segment.empty() || segment == "." || segment == "..") {
            return failure<fs::path>(
                "workspace_migration_apply_unproven",
                "migration journal path contains an unsafe segment");
        }
    }
    return Result<fs::path>::success((layout.root() / relative).lexically_normal());
}

Result<void> ensure_owned_directory(
    const WorkspaceRootInspection& authority,
    const fs::path& path)
{
    const auto before = authority.root_authority->validate_descendant(path, true);
    if (!before.ok()) return failure<void>(before.code, before.detail, path);
    std::error_code error;
    const fs::file_status status = fs::symlink_status(path, error);
    if (!error && fs::exists(status)) {
        if (!fs::is_directory(status)) {
            return failure<void>(
                "workspace_migration_apply_unproven",
                "migration state path is not a plain directory",
                path);
        }
    } else {
        error.clear();
        fs::create_directory(path, error);
        if (error) {
            return failure<void>("workspace_directory_create_failed", error.message(), path);
        }
    }
    const auto after = authority.root_authority->validate_descendant(path);
    if (!after.ok()) return failure<void>(after.code, after.detail, path);
    return Result<void>::success();
}

Result<void> write_replace_durable(const fs::path& path, const std::string& text)
{
    facman::platform::RandomIdGenerator random;
    const fs::path temporary = path.parent_path() /
        (path.filename().string() + ".next-" + random.next("migration"));
    facman::platform::DurableOutputFile output;
    auto status = output.create_exclusive(temporary, 1024ULL * 1024ULL);
    if (!status.ok()) return failure<void>(status.code, status.detail, temporary);
    if (output.write_at(0U, text.data(), text.size()) != text.size()) {
        output.close_without_flush();
        facman::platform::StableInputFile created;
        if (created.open_no_follow(temporary).ok()) {
            (void)facman::platform::remove_exact_object(temporary, created.identity());
        }
        return failure<void>(
            "workspace_record_write_failed", "short migration journal write", temporary);
    }
    status = output.flush_file_and_parent();
    if (!status.ok()) {
        output.close_without_flush();
        facman::platform::StableInputFile created;
        if (created.open_no_follow(temporary).ok()) {
            (void)facman::platform::remove_exact_object(temporary, created.identity());
        }
        return failure<void>(status.code, status.detail, temporary);
    }
    status = facman::platform::replace_existing_durable(temporary, path);
    if (!status.ok()) {
        facman::platform::StableInputFile created;
        if (created.open_no_follow(temporary).ok()) {
            (void)facman::platform::remove_exact_object(temporary, created.identity());
        }
        return failure<void>(status.code, status.detail, path);
    }
    return Result<void>::success();
}

Result<void> persist_journal(
    const WorkspaceLayout& layout,
    const MigrationJournal& journal,
    bool create)
{
    const fs::path path = migration_journal_path(
        layout, journal.id, journal.format_version);
    const std::string text = migration_journal_json(journal);
    if (text.size() > 1024U * 1024U) {
        return failure<void>(
            "workspace_migration_apply_unproven",
            "migration journal exceeds its byte budget",
            path);
    }
    if (create) {
        auto written = write_new_durable(path, text);
        return written ? Result<void>::success() :
            failure<void>(written.error().code, written.error().message, path);
    }
    return write_replace_durable(path, text);
}

std::string workspace_creation_journal_json(
    const MigrationApplyRequest& request,
    const std::string& workspace_id,
    const std::string& state,
    const std::string& resulting_workspace_revision,
    const std::string& migration_id,
    const std::string& inventory_digest,
    const std::string& target_sha256)
{
    json::ObjectBuilder creation;
    creation.add_string("schema", "facman.workspace_creation_journal.v1");
    creation.add_string("operation_id", request.operation_id);
    creation.add_string("attempt_id", request.attempt_id);
    creation.add_string("request_id", request.request_id);
    creation.add_string("idempotency_key", request.idempotency_key);
    creation.add_string("migration_id", migration_id);
    creation.add_string("plan_digest", request.plan_digest);
    creation.add_string("expected_workspace_revision", request.expected_workspace_revision);
    creation.add_string("expected_root_identity", request.expected_root_identity);
    creation.add_string("inventory_digest", inventory_digest);
    creation.add_string("target_sha256", target_sha256);
    creation.add_string("workspace_id", workspace_id);
    creation.add_string("state", state);
    if (resulting_workspace_revision.empty()) {
        creation.add_null("resulting_workspace_revision");
    } else {
        creation.add_string(
            "resulting_workspace_revision", resulting_workspace_revision);
    }
    return creation.serialize() + "\n";
}

bool sha256_text_valid(const std::string& value)
{
    return value.size() == 64U &&
        std::all_of(value.begin(), value.end(), [](unsigned char ch) {
            return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
        });
}

Result<MigrationJournal> load_legacy_migration_journal(const fs::path& path)
{
    auto document = parse_record(path);
    if (!document) {
        return failure<MigrationJournal>(document.error().code, document.error().message, path);
    }
    auto schema = journal_string(document.value(), "schema", path);
    auto id = journal_string(document.value(), "migration_id", path);
    auto state = journal_string(document.value(), "state", path);
    if (!schema || !id || !state) {
        const auto& problem = !schema ? schema.error() : !id ? id.error() : state.error();
        return failure<MigrationJournal>(problem.code, problem.message, path);
    }
    std::string id_detail;
    if (schema.value() != "facman.workspace_migration_journal.v1" ||
        !facman::base::validate_identifier(id.value(), id_detail) ||
        path.filename() != id.value() + ".workspace-migration.v1.json" ||
        (state.value() != "planned" && state.value() != "applying" &&
         state.value() != "complete" && state.value() != "rolled_back" &&
         state.value() != "recovery_required")) {
        return failure<MigrationJournal>(
            "workspace_migration_apply_unproven",
            "migration journal identity, schema, or state is unsupported",
            path);
    }
    const json::Value* completed = document.value().find("completed_actions");
    const json::Value* actions = document.value().find("actions");
    if (completed == nullptr || !completed->is_number() ||
        actions == nullptr || !actions->is_array() ||
        actions->size() > kMaximumMigrationActions) {
        return failure<MigrationJournal>(
            "workspace_migration_apply_unproven",
            "migration journal action bounds are invalid",
            path);
    }
    auto completed_value = completed->unsigned_integer_value();
    if (!completed_value || completed_value.value() > actions->size() ||
        completed_value.value() > std::numeric_limits<std::size_t>::max()) {
        return failure<MigrationJournal>(
            "workspace_migration_apply_unproven",
            "migration journal completion index is invalid",
            path);
    }
    MigrationJournal journal;
    journal.format_version = 1U;
    journal.id = id.take_value();
    journal.migration_id = journal.id;
    journal.state = state.take_value();
    journal.completed_actions = static_cast<std::size_t>(completed_value.value());
    for (std::size_t index = 0U; index < actions->size(); ++index) {
        const json::Value* item = actions->at(index);
        if (item == nullptr || !item->is_object()) {
            return failure<MigrationJournal>(
                "workspace_migration_apply_unproven",
                "migration journal action is not an object",
                path);
        }
        auto kind = journal_string(*item, "kind", path);
        auto source = journal_string(*item, "source", path);
        auto target = journal_string(*item, "target", path);
        auto source_sha = journal_string(*item, "source_sha256", path);
        auto target_sha = journal_string(*item, "target_sha256", path);
        if (!kind || !source || !target || !source_sha || !target_sha ||
            !copy_migration_kind(kind.value()) ||
            !sha256_text_valid(source_sha.value()) ||
            !sha256_text_valid(target_sha.value())) {
            return failure<MigrationJournal>(
                "workspace_migration_apply_unproven",
                "migration journal action is unsupported or corrupt",
                path);
        }
        journal.actions.push_back({
            "step-" + std::to_string(index + 1U),
            kind.take_value(), source.take_value(), target.take_value(),
            source_sha.take_value(), target_sha.take_value()});
    }
    return Result<MigrationJournal>::success(std::move(journal));
}

Result<MigrationJournal> load_migration_journal(const fs::path& path)
{
    auto document = parse_record(path);
    if (!document) {
        return failure<MigrationJournal>(document.error().code, document.error().message, path);
    }
    auto schema = journal_string(document.value(), "schema", path);
    if (!schema) {
        return failure<MigrationJournal>(schema.error().code, schema.error().message, path);
    }
    if (schema.value() == "facman.workspace_migration_journal.v1") {
        return load_legacy_migration_journal(path);
    }
    if (schema.value() != "facman.workspace_migration_journal.v2") {
        return failure<MigrationJournal>(
            "workspace_migration_apply_unproven",
            "migration journal schema is unsupported",
            path);
    }
    const json::Value* operation = document.value().find("operation");
    const json::Value* identities = document.value().find("input_identities");
    const json::Value* effects = document.value().find("effects");
    const json::Value* completed = document.value().find("completed_steps");
    const json::Value* staged = document.value().find("staged_outputs");
    const json::Value* committed = document.value().find("committed_outputs");
    const json::Value* verification = document.value().find("verification_results");
    const json::Value* recovery_boundary = document.value().find("recovery_boundary");
    const json::Value* rollback_retained = document.value().find("rollback_retained");
    const json::Value* resulting_revision = document.value().find("resulting_workspace_revision");
    const json::Value* rollback_operation = document.value().find("rollback_operation");
    if (operation == nullptr || !operation->is_object() ||
        identities == nullptr || !identities->is_object() ||
        effects == nullptr || !effects->is_array() ||
        completed == nullptr || !completed->is_array() ||
        staged == nullptr || !staged->is_array() ||
        committed == nullptr || !committed->is_array() ||
        verification == nullptr || !verification->is_array() ||
        recovery_boundary == nullptr || !recovery_boundary->is_string() ||
        rollback_retained == nullptr || !rollback_retained->is_bool() ||
        resulting_revision == nullptr || rollback_operation == nullptr ||
        (!resulting_revision->is_null() && !resulting_revision->is_string()) ||
        (!rollback_operation->is_null() && !rollback_operation->is_object()) ||
        effects->size() > kMaximumMigrationActions || completed->size() > effects->size() ||
        staged->size() != effects->size() || committed->size() != completed->size()) {
        return failure<MigrationJournal>(
            "workspace_migration_apply_unproven",
            "migration journal v2 structure or bounds are invalid",
            path);
    }
    MigrationJournal journal;
    auto operation_id = journal_string(*operation, "operation_id", path);
    auto attempt_id = journal_string(*operation, "attempt_id", path);
    auto request_id = journal_string(*operation, "request_id", path);
    auto idempotency_key = journal_string(*operation, "idempotency_key", path);
    auto migration_id = journal_string(*operation, "migration_id", path);
    auto plan_digest = journal_string(*operation, "plan_digest", path);
    auto expected_revision = journal_string(*operation, "expected_workspace_revision", path);
    auto expected_root = journal_string(*operation, "expected_root_identity", path);
    auto current_phase = journal_string(*operation, "current_phase", path);
    auto terminal_classification = journal_string(
        *operation, "terminal_classification", path);
    auto identity_root = journal_string(*identities, "root_identity", path);
    auto identity_revision = journal_string(*identities, "workspace_revision", path);
    auto inventory_digest = journal_string(*identities, "inventory_digest", path);
    auto identity_plan = journal_string(*identities, "plan_digest", path);
    if (!operation_id || !attempt_id || !request_id || !idempotency_key ||
        !migration_id || !plan_digest || !expected_revision || !expected_root ||
        !current_phase || !terminal_classification ||
        !identity_root || !identity_revision ||
        !inventory_digest || !identity_plan) {
        return failure<MigrationJournal>(
            "workspace_migration_apply_unproven",
            "migration journal v2 identities are incomplete",
            path);
    }
    std::string detail;
    if (!facman::base::validate_identifier(operation_id.value(), detail) ||
        !facman::base::validate_identifier(attempt_id.value(), detail) ||
        !facman::base::validate_identifier(request_id.value(), detail) ||
        !facman::base::validate_identifier(idempotency_key.value(), detail) ||
        !facman::base::validate_identifier(migration_id.value(), detail) ||
        !sha256_text_valid(plan_digest.value()) ||
        !sha256_text_valid(expected_revision.value()) ||
        !sha256_text_valid(expected_root.value()) ||
        !sha256_text_valid(inventory_digest.value()) ||
        expected_root.value() != identity_root.value() ||
        expected_revision.value() != identity_revision.value() ||
        plan_digest.value() != identity_plan.value() ||
        path.filename() != operation_id.value() + ".workspace-migration.v2.json") {
        return failure<MigrationJournal>(
            "workspace_migration_apply_unproven",
            "migration journal v2 identity binding is invalid",
            path);
    }
    journal.id = operation_id.value();
    journal.operation_id = operation_id.take_value();
    journal.attempt_id = attempt_id.take_value();
    journal.request_id = request_id.take_value();
    journal.idempotency_key = idempotency_key.take_value();
    journal.migration_id = migration_id.take_value();
    journal.plan_digest = plan_digest.take_value();
    journal.expected_workspace_revision = expected_revision.take_value();
    journal.expected_root_identity = expected_root.take_value();
    journal.inventory_digest = inventory_digest.take_value();
    const std::string phase = current_phase.take_value();
    const std::string terminal = terminal_classification.take_value();
    if (phase == "completed" && terminal == "completed") {
        journal.state = "complete";
    } else if (phase == "rolled_back" && terminal == "rolled_back") {
        journal.state = "rolled_back";
    } else if (phase == "recovery_required" && terminal == "recovery_required") {
        journal.state = "recovery_required";
    } else if ((phase == "applying" || phase == "rolling_back") && terminal == "none") {
        journal.state = phase;
    } else {
        return failure<MigrationJournal>(
            "workspace_migration_apply_unproven",
            "migration journal operation phase or terminal classification is invalid",
            path);
    }
    auto retained = rollback_retained->bool_value();
    if (!retained) {
        return failure<MigrationJournal>(
            "workspace_migration_apply_unproven",
            "migration journal rollback retention is invalid",
            path);
    }
    journal.rollback_retained = retained.value();
    if (resulting_revision->is_string()) {
        auto result = resulting_revision->string_value();
        if (!result || !sha256_text_valid(result.value())) {
            return failure<MigrationJournal>(
                "workspace_migration_apply_unproven",
                "migration journal resulting revision is invalid",
                path);
        }
        journal.resulting_workspace_revision = result.take_value();
    }
    if (rollback_operation->is_object()) {
        auto operation_value = journal_string(*rollback_operation, "operation_id", path);
        auto attempt_value = journal_string(*rollback_operation, "attempt_id", path);
        auto request_value = journal_string(*rollback_operation, "request_id", path);
        auto key_value = journal_string(*rollback_operation, "idempotency_key", path);
        auto revision_value = journal_string(
            *rollback_operation, "expected_workspace_revision", path);
        if (!operation_value || !attempt_value || !request_value || !key_value ||
            !revision_value ||
            !facman::base::validate_identifier(operation_value.value(), detail) ||
            !facman::base::validate_identifier(attempt_value.value(), detail) ||
            !facman::base::validate_identifier(request_value.value(), detail) ||
            !facman::base::validate_identifier(key_value.value(), detail) ||
            !sha256_text_valid(revision_value.value())) {
            return failure<MigrationJournal>(
                "workspace_migration_apply_unproven",
                "migration rollback operation identity is invalid", path);
        }
        journal.rollback_operation_id = operation_value.take_value();
        journal.rollback_attempt_id = attempt_value.take_value();
        journal.rollback_request_id = request_value.take_value();
        journal.rollback_idempotency_key = key_value.take_value();
        journal.rollback_expected_workspace_revision = revision_value.take_value();
    }
    for (std::size_t index = 0U; index < effects->size(); ++index) {
        const json::Value* item = effects->at(index);
        if (item == nullptr || !item->is_object()) {
            return failure<MigrationJournal>(
                "workspace_migration_apply_unproven",
                "migration journal v2 effect is not an object",
                path);
        }
        auto step_id = journal_string(*item, "step_id", path);
        auto kind = journal_string(*item, "kind", path);
        auto source = journal_string(*item, "source", path);
        auto target = journal_string(*item, "target", path);
        auto source_sha = journal_string(*item, "source_sha256", path);
        auto target_sha = journal_string(*item, "target_sha256", path);
        if (!step_id || !kind || !source || !target || !source_sha || !target_sha ||
            !facman::base::validate_identifier(step_id.value(), detail) ||
            !copy_migration_kind(kind.value()) ||
            !sha256_text_valid(source_sha.value()) ||
            !sha256_text_valid(target_sha.value())) {
            return failure<MigrationJournal>(
                "workspace_migration_apply_unproven",
                "migration journal v2 effect is unsupported or corrupt",
                path);
        }
        journal.actions.push_back({
            step_id.take_value(), kind.take_value(), source.take_value(),
            target.take_value(), source_sha.take_value(), target_sha.take_value()});
    }
    for (std::size_t index = 0U; index < completed->size(); ++index) {
        const json::Value* item = completed->at(index);
        if (item == nullptr || !item->is_string()) {
            return failure<MigrationJournal>(
                "workspace_migration_apply_unproven",
                "migration journal completed step is not a string",
                path);
        }
        auto step = item->string_value();
        if (!step || step.value() != journal.actions[index].step_id) {
            return failure<MigrationJournal>(
                "workspace_migration_apply_unproven",
                "migration journal completed steps are not an exact ordered prefix",
                path);
        }
    }
    journal.completed_actions = completed->size();
    const auto validate_outputs = [&journal, &path](
        const json::Value& outputs,
        std::size_t expected_count) -> Result<void> {
        for (std::size_t index = 0U; index < expected_count; ++index) {
            const json::Value* item = outputs.at(index);
            if (item == nullptr || !item->is_object()) {
                return failure<void>(
                    "workspace_migration_apply_unproven",
                    "migration journal bound output is not an object",
                    path);
            }
            auto output_path = journal_string(*item, "path", path);
            auto output_sha = journal_string(*item, "sha256", path);
            if (!output_path || !output_sha ||
                output_path.value() != journal.actions[index].target ||
                output_sha.value() != journal.actions[index].target_sha256) {
                return failure<void>(
                    "workspace_migration_apply_unproven",
                    "migration journal output closure differs from its effect",
                    path);
            }
        }
        return Result<void>::success();
    };
    auto outputs_valid = validate_outputs(*staged, staged->size());
    if (!outputs_valid) {
        return failure<MigrationJournal>(
            outputs_valid.error().code, outputs_valid.error().message, path);
    }
    outputs_valid = validate_outputs(*committed, committed->size());
    if (!outputs_valid) {
        return failure<MigrationJournal>(
            outputs_valid.error().code, outputs_valid.error().message, path);
    }
    auto boundary = recovery_boundary->string_value();
    const std::string expected_boundary = journal.state == "complete" ? "fully_committed" :
        journal.state == "rolled_back" ? "rolled_back" :
        journal.completed_actions == 0U ? "staged_only" :
        "partially_committed_recoverable";
    if (!boundary || boundary.value() != expected_boundary) {
        return failure<MigrationJournal>(
            "workspace_migration_apply_unproven",
            "migration journal recovery boundary is inconsistent",
            path);
    }
    for (std::size_t index = 0U; index < verification->size(); ++index) {
        const json::Value* item = verification->at(index);
        if (item == nullptr || !item->is_string()) {
            return failure<MigrationJournal>(
                "workspace_migration_apply_unproven",
                "migration journal verification result is not a string",
                path);
        }
        auto result = item->string_value();
        if (!result || result.value().empty()) {
            return failure<MigrationJournal>(
                "workspace_migration_apply_unproven",
                "migration journal verification result is invalid",
                path);
        }
        journal.verification_results.push_back(result.take_value());
    }
    if ((journal.state == "complete") !=
        !journal.resulting_workspace_revision.empty()) {
        return failure<MigrationJournal>(
            "workspace_migration_apply_unproven",
            "migration journal terminal revision does not match its state",
            path);
    }
    if ((journal.state == "rolling_back" || journal.state == "rolled_back") &&
        journal.rollback_operation_id.empty()) {
        return failure<MigrationJournal>(
            "workspace_migration_apply_unproven",
            "migration rollback state lacks its control operation", path);
    }
    return Result<MigrationJournal>::success(std::move(journal));
}

Result<WorkspaceCreationJournal> load_workspace_creation_journal(const fs::path& path)
{
    auto document = parse_record(path);
    if (!document) {
        return failure<WorkspaceCreationJournal>(
            document.error().code, document.error().message, path);
    }
    auto schema = journal_string(document.value(), "schema", path);
    auto operation_id = journal_string(document.value(), "operation_id", path);
    auto attempt_id = journal_string(document.value(), "attempt_id", path);
    auto request_id = journal_string(document.value(), "request_id", path);
    auto idempotency_key = journal_string(document.value(), "idempotency_key", path);
    auto migration_id = journal_string(document.value(), "migration_id", path);
    auto plan_digest = journal_string(document.value(), "plan_digest", path);
    auto expected_revision = journal_string(
        document.value(), "expected_workspace_revision", path);
    auto expected_root = journal_string(document.value(), "expected_root_identity", path);
    auto inventory_digest = journal_string(document.value(), "inventory_digest", path);
    auto target_sha256 = journal_string(document.value(), "target_sha256", path);
    auto workspace_id = journal_string(document.value(), "workspace_id", path);
    auto state = journal_string(document.value(), "state", path);
    const json::Value* resulting_revision =
        document.value().find("resulting_workspace_revision");
    if (!schema || !operation_id || !attempt_id || !request_id ||
        !idempotency_key || !migration_id || !plan_digest || !expected_revision ||
        !expected_root || !inventory_digest || !target_sha256 ||
        !workspace_id || !state || resulting_revision == nullptr ||
        (!resulting_revision->is_null() && !resulting_revision->is_string())) {
        return failure<WorkspaceCreationJournal>(
            "workspace_migration_apply_unproven",
            "workspace creation journal is incomplete", path);
    }
    std::string detail;
    if (schema.value() != "facman.workspace_creation_journal.v1" ||
        !facman::base::validate_identifier(operation_id.value(), detail) ||
        !facman::base::validate_identifier(attempt_id.value(), detail) ||
        !facman::base::validate_identifier(request_id.value(), detail) ||
        !facman::base::validate_identifier(idempotency_key.value(), detail) ||
        !facman::base::validate_identifier(migration_id.value(), detail) ||
        !sha256_text_valid(plan_digest.value()) ||
        !sha256_text_valid(expected_revision.value()) ||
        !sha256_text_valid(expected_root.value()) ||
        !sha256_text_valid(inventory_digest.value()) ||
        !sha256_text_valid(target_sha256.value()) ||
        !facman::core::WorkspaceId::parse(workspace_id.value()) ||
        (state.value() != "applying" && state.value() != "completed") ||
        path.filename() != operation_id.value() + ".workspace-creation.v1.json") {
        return failure<WorkspaceCreationJournal>(
            "workspace_migration_apply_unproven",
            "workspace creation journal identity binding is invalid", path);
    }
    WorkspaceCreationJournal journal;
    journal.operation_id = operation_id.take_value();
    journal.attempt_id = attempt_id.take_value();
    journal.request_id = request_id.take_value();
    journal.idempotency_key = idempotency_key.take_value();
    journal.migration_id = migration_id.take_value();
    journal.plan_digest = plan_digest.take_value();
    journal.expected_workspace_revision = expected_revision.take_value();
    journal.expected_root_identity = expected_root.take_value();
    journal.inventory_digest = inventory_digest.take_value();
    journal.target_sha256 = target_sha256.take_value();
    journal.workspace_id = workspace_id.take_value();
    journal.state = state.take_value();
    if (resulting_revision->is_string()) {
        auto result = resulting_revision->string_value();
        if (!result || !sha256_text_valid(result.value())) {
            return failure<WorkspaceCreationJournal>(
                "workspace_migration_apply_unproven",
                "workspace creation journal terminal revision is invalid", path);
        }
        journal.resulting_workspace_revision = result.take_value();
    }
    if ((journal.state == "completed") !=
        !journal.resulting_workspace_revision.empty()) {
        return failure<WorkspaceCreationJournal>(
            "workspace_migration_apply_unproven",
            "workspace creation journal state and terminal revision disagree", path);
    }
    return Result<WorkspaceCreationJournal>::success(std::move(journal));
}

} // namespace facman::workspace
