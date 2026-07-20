// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "modules/launch_module.h"

#include "command_result.h"
#include "handlers/launch.h"

namespace facman::factorio::application {

bool LaunchApplicationModule::handles(CommandId command) const noexcept
{
    return command == CommandId::launch_plan_build ||
        command == CommandId::launch_plan_preflight ||
        command == CommandId::run_preview ||
        command == CommandId::run_execute;
}

ApplicationResult LaunchApplicationModule::execute(
    ApplicationContext& context,
    const ApplicationRequest& request,
    const CommandAdmissionDecision& admission) const
{
    switch (request.command) {
    case CommandId::launch_plan_build:
        return handlers::preview_launch(
            context, std::get<BuildLaunchPlanRequest>(request.payload), "launch_plan.build");
    case CommandId::launch_plan_preflight:
        return handlers::preflight_launch(
            context, std::get<BuildLaunchPlanRequest>(request.payload));
    case CommandId::run_preview:
        return handlers::preview_launch(
            context, std::get<BuildLaunchPlanRequest>(request.payload), "run.preview");
    case CommandId::run_execute:
        return handlers::refuse_execute(
            context, std::get<ExecuteRunRequest>(request.payload), admission);
    default:
        return refused(
            safety_refusal("launch.module", "invalid_request", "Unsupported launch command", "", false),
            "invalid_request",
            "Unsupported launch command");
    }
}

} // namespace facman::factorio::application
