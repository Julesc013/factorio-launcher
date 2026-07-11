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
ApplicationResult migration(ApplicationContext& context, const std::string& operation)
{
    auto outcome = operation == "workspace.migration.inspect" ? context.workspace_repository().inspect_migration() :
        operation == "workspace.migration.plan" ? context.workspace_repository().plan_migration() :
        context.workspace_repository().apply_migration();
    if (!outcome) {
        return refused(
            safety_refusal(operation, outcome.error().code, outcome.error().message, outcome.error().path, false),
            outcome.error().code,
            outcome.error().message);
    }
    ApplicationResult result;
    result.output = facman::workspace::migration_report_json(outcome.value());
    return result;
}
}
