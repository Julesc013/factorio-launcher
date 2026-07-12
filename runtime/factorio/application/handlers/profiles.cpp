// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "handlers/profiles.h"

#include "command_result.h"
#include "flb_factorio_profiles.h"

namespace facman::factorio::application::handlers {
namespace profile_ops = facman::factorio::profiles;
namespace {
ApplicationResult profile_result(const char* operation, facman::core::Result<std::string> result)
{
    if (result) {
        ApplicationResult output;
        output.output = result.take_value();
        return output;
    }
    return refused(
        safety_refusal(operation, result.error().code, "Profile or template operation was refused",
            result.error().message, result.error().recoverable),
        result.error().code, result.error().message, result.error().kind);
}
}

ApplicationResult dispatch_profiles(ApplicationContext& context, const ApplicationRequest& request)
{
    switch (request.command) {
    case CommandId::templates_list: return profile_result("templates.list", profile_ops::templates_list(context.workspace()));
    case CommandId::templates_inspect: return profile_result("templates.inspect", profile_ops::templates_inspect(
        context.workspace(), std::get<ProfileIdRequest>(request.payload)));
    case CommandId::templates_validate: return profile_result("templates.validate", profile_ops::templates_validate(
        context.workspace(), std::get<ProfileIdRequest>(request.payload)));
    case CommandId::profiles_list: return profile_result("profiles.list", profile_ops::profiles_list(context.workspace()));
    case CommandId::profiles_inspect: return profile_result("profiles.inspect", profile_ops::profiles_inspect(
        context.workspace(), std::get<ProfileIdRequest>(request.payload)));
    case CommandId::profiles_create: return profile_result("profiles.create", profile_ops::profiles_create(
        context.workspace(), std::get<CreateProfileRequest>(request.payload)));
    case CommandId::profiles_clone: return profile_result("profiles.clone", profile_ops::profiles_clone(
        context.workspace(), std::get<CloneProfileRequest>(request.payload)));
    case CommandId::profiles_diff: return profile_result("profiles.diff", profile_ops::profiles_diff(
        context.workspace(), std::get<DiffProfileRequest>(request.payload)));
    case CommandId::profiles_plan: return profile_result("profiles.plan", profile_ops::profiles_plan(
        context.workspace(), std::get<EffectiveProfileRequest>(request.payload)));
    case CommandId::profiles_apply: return profile_result("profiles.apply", profile_ops::profiles_apply(
        context.workspace(), std::get<EffectiveProfileRequest>(request.payload)));
    case CommandId::profiles_archive: return profile_result("profiles.archive", profile_ops::profiles_archive(
        context.workspace(), std::get<ProfileIdRequest>(request.payload)));
    default: return profile_result("profiles", facman::core::Result<std::string>::failure(
        {"unsupported_operation", "Unsupported profile or template command", "profiles"}));
    }
}
}
