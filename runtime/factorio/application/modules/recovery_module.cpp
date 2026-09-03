// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "modules/recovery_module.h"

#include "command_result.h"
#include "handlers/recovery.h"

namespace facman::factorio::application {

bool RecoveryApplicationModule::handles(CommandId command) const noexcept
{
    switch (command) {
    case CommandId::recovery_inspect:
    case CommandId::recovery_plan:
    case CommandId::recovery_apply:
    case CommandId::migration_inspect:
    case CommandId::migration_operation_inspect:
    case CommandId::migration_plan:
    case CommandId::migration_apply:
    case CommandId::migration_resume:
    case CommandId::migration_recover:
    case CommandId::migration_rollback:
        return true;
    default:
        return false;
    }
}

ApplicationResult RecoveryApplicationModule::execute(
    ApplicationContext& context,
    const ApplicationRequest& request,
    const CommandAdmissionDecision&,
    const std::string&) const
{
    switch (request.command) {
    case CommandId::recovery_inspect:
        return handlers::recovery_inspect(context);
    case CommandId::recovery_plan:
        return handlers::recovery_plan(
            context, std::get<RecoveryRequest>(request.payload));
    case CommandId::recovery_apply:
        return handlers::recovery_apply(
            context, std::get<RecoveryRequest>(request.payload));
    case CommandId::migration_inspect:
        return handlers::migration(
            context, "workspace.migration.inspect",
            std::get<WorkspaceMigrationRequest>(request.payload));
    case CommandId::migration_operation_inspect:
        return handlers::migration(
            context, "workspace.migration.operation.inspect",
            std::get<WorkspaceMigrationRequest>(request.payload));
    case CommandId::migration_plan:
        return handlers::migration(
            context, "workspace.migration.plan",
            std::get<WorkspaceMigrationRequest>(request.payload));
    case CommandId::migration_apply:
        return handlers::migration(
            context, "workspace.migration.apply",
            std::get<WorkspaceMigrationRequest>(request.payload));
    case CommandId::migration_resume:
        return handlers::migration(
            context, "workspace.migration.resume",
            std::get<WorkspaceMigrationRequest>(request.payload));
    case CommandId::migration_recover:
        return handlers::migration(
            context, "workspace.migration.recover",
            std::get<WorkspaceMigrationRequest>(request.payload));
    case CommandId::migration_rollback:
        return handlers::migration(
            context, "workspace.migration.rollback",
            std::get<WorkspaceMigrationRequest>(request.payload));
    default:
        return refused(
            safety_refusal(
                "recovery.module",
                "invalid_request",
                "Unsupported recovery command",
                "",
                false),
            "invalid_request",
            "Unsupported recovery command");
    }
}

} // namespace facman::factorio::application
