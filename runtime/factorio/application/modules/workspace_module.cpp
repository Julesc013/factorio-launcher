// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "modules/workspace_module.h"

#include "command_result.h"
#include "handlers/doctor.h"
#include "handlers/intelligence.h"
#include "handlers/preferences.h"
#include "handlers/product.h"

namespace facman::factorio::application {

bool WorkspaceApplicationModule::handles(CommandId command) const noexcept
{
    switch (command) {
    case CommandId::product_inspect:
    case CommandId::workspace_status:
    case CommandId::workspace_paths:
    case CommandId::preferences_inspect:
    case CommandId::preferences_validate:
    case CommandId::preferences_plan:
    case CommandId::preferences_apply:
    case CommandId::preferences_reset_plan:
    case CommandId::preferences_reset_apply:
    case CommandId::capabilities_inspect:
    case CommandId::onboarding_plan:
    case CommandId::doctor_explain:
    case CommandId::launch_plan_explain:
    case CommandId::doctor_run:
        return true;
    default:
        return false;
    }
}

bool WorkspaceApplicationModule::requires_workspace(CommandId command) const noexcept
{
    return command != CommandId::product_inspect;
}

ApplicationResult WorkspaceApplicationModule::execute(
    ApplicationContext& context,
    const ApplicationRequest& request,
    const CommandAdmissionDecision&,
    const std::string& command_name) const
{
    switch (request.command) {
    case CommandId::product_inspect:
        return handlers::inspect_product(context, command_name);
    case CommandId::workspace_status:
        return handlers::workspace_status(context);
    case CommandId::workspace_paths:
        return handlers::workspace_paths(context);
    case CommandId::preferences_inspect:
        return handlers::inspect_preferences(context);
    case CommandId::preferences_validate:
        return handlers::validate_preferences(
            context, std::get<PreferencesRequest>(request.payload));
    case CommandId::preferences_plan:
        return handlers::plan_preferences(
            context, std::get<PreferencesRequest>(request.payload));
    case CommandId::preferences_apply:
        return handlers::apply_preferences(
            context, std::get<PreferencesRequest>(request.payload));
    case CommandId::preferences_reset_plan:
        return handlers::plan_preferences_reset(context);
    case CommandId::preferences_reset_apply:
        return handlers::apply_preferences_reset(context);
    case CommandId::capabilities_inspect:
        return handlers::capabilities_inspect(context);
    case CommandId::onboarding_plan:
        return handlers::onboarding_plan(
            context, std::get<OnboardingPlanRequest>(request.payload));
    case CommandId::doctor_explain:
        return handlers::doctor_explain(context);
    case CommandId::launch_plan_explain:
        return handlers::launch_plan_explain(
            context, std::get<ExplainInstanceRequest>(request.payload));
    case CommandId::doctor_run:
        return handlers::run_doctor(
            context, std::get<DoctorRequest>(request.payload));
    default:
        return refused(
            safety_refusal(
                "workspace.module",
                "invalid_request",
                "Unsupported workspace command",
                "",
                false),
            "invalid_request",
            "Unsupported workspace command");
    }
}

} // namespace facman::factorio::application
