// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "modules/profile_module.h"

#include "command_result.h"
#include "handlers/profiles.h"

namespace facman::factorio::application {

bool ProfileApplicationModule::handles(CommandId command) const noexcept
{
    switch (command) {
    case CommandId::templates_list:
    case CommandId::templates_inspect:
    case CommandId::templates_validate:
    case CommandId::profiles_list:
    case CommandId::profiles_inspect:
    case CommandId::profiles_create:
    case CommandId::profiles_clone:
    case CommandId::profiles_diff:
    case CommandId::profiles_plan:
    case CommandId::profiles_apply:
    case CommandId::profiles_archive:
        return true;
    default:
        return false;
    }
}

ApplicationResult ProfileApplicationModule::execute(
    ApplicationContext& context,
    const ApplicationRequest& request,
    const CommandAdmissionDecision&,
    const std::string&) const
{
    if (handles(request.command)) {
        return handlers::dispatch_profiles(context, request);
    }
    return refused(
        safety_refusal(
            "profile.module",
            "invalid_request",
            "Unsupported profile command",
            "",
            false),
        "invalid_request",
        "Unsupported profile command");
}

} // namespace facman::factorio::application
