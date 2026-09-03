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
    return from_recovery_outcome(transactions::apply(context.workspace(), request.transaction_id));
}
ApplicationResult migration(
    ApplicationContext& context,
    const std::string& operation,
    const WorkspaceMigrationRequest& request)
{
    auto outcome = operation == "workspace.migration.inspect" ? context.workspace_repository().inspect_migration() :
        operation == "workspace.migration.plan" ? context.workspace_repository().plan_migration() :
        context.workspace_repository().apply_migration(request.apply);
    if (!outcome) {
        const bool recovery_required = outcome.error().code == "workspace_migration_recovery_required";
        const bool conflict = outcome.error().code == "workspace_migration_conflict";
        return refused(
            safety_refusal(operation, outcome.error().code, outcome.error().message,
                outcome.error().path, recovery_required || conflict, conflict),
            outcome.error().code,
            outcome.error().message,
            conflict ? facman::core::OutcomeKind::conflict : facman::core::OutcomeKind::refused);
    }
    ApplicationResult result;
    result.output = facman::workspace::migration_report_json(outcome.value());
    return result;
}
}
