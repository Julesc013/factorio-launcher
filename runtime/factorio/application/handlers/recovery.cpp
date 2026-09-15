// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "handlers/recovery.h"

#include "command_result.h"

namespace facman::factorio::application::handlers {
ApplicationResult recovery_inspect(ApplicationContext& context)
{
    return from_recovery_outcome(transactions::inspect(context.workspace()));
}
ApplicationResult recovery_plan(ApplicationContext& context, const RecoveryRequest& request)
{
    return from_recovery_outcome(transactions::plan(context.workspace(), request.transaction_id));
}
ApplicationResult recovery_apply(ApplicationContext& context, const RecoveryRequest& request)
{
    transactions::Record record;
    std::string detail;
    if (transactions::read_record(context.workspace(), request.transaction_id, record, detail) &&
        record.command_id == "installs.uninstall.apply") {
        return refused(
            safety_refusal(
                "workspace.recovery.apply",
                "operation_specific_recovery_required",
                "Managed uninstall recovery must use its operation-specific recovery path",
                request.transaction_id,
                true,
                false),
            "operation_specific_recovery_required",
            "Generic workspace recovery cannot classify an interrupted managed uninstall",
            facman::core::OutcomeKind::recovery_required);
    }
    return from_recovery_outcome(transactions::apply(context.workspace(), request.transaction_id));
}
ApplicationResult migration(
    ApplicationContext& context,
    const std::string& operation,
    const WorkspaceMigrationRequest& request)
{
    auto outcome = [&]() -> facman::workspace::Result<facman::workspace::MigrationReport> {
        if (operation == "workspace.migration.inspect") {
            return context.workspace_repository().inspect_migration();
        }
        if (operation == "workspace.migration.plan") {
            return context.workspace_repository().plan_migration();
        }
        if (operation == "workspace.migration.apply") {
            return context.workspace_repository().apply_migration(request.apply);
        }
        if (operation == "workspace.migration.operation.inspect") {
            return context.workspace_repository().inspect_migration_operation(
                request.target_operation_id);
        }
        if (operation == "workspace.migration.resume") {
            return context.workspace_repository().resume_migration(request.control);
        }
        if (operation == "workspace.migration.recover") {
            return context.workspace_repository().recover_migration(request.control);
        }
        return context.workspace_repository().rollback_migration(request.control);
    }();
    if (!outcome) {
        const bool recovery_required = outcome.error().code == "workspace_migration_recovery_required";
        const bool conflict = outcome.error().code == "workspace_migration_conflict";
        const bool interrupted = outcome.error().code == "workspace_migration_interrupted";
        return refused(
            safety_refusal(operation, outcome.error().code, outcome.error().message,
                outcome.error().path, recovery_required || conflict || interrupted,
                conflict || interrupted),
            outcome.error().code,
            outcome.error().message,
            conflict ? facman::core::OutcomeKind::conflict : facman::core::OutcomeKind::refused);
    }
    ApplicationResult result;
    result.output = facman::workspace::migration_report_json(outcome.value());
    return result;
}
}
