// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "modules/instance_module.h"

#include "command_result.h"
#include "handlers/instances.h"

namespace facman::factorio::application {

bool InstanceApplicationModule::handles(CommandId command) const noexcept
{
    return command == CommandId::instances_describe ||
        command == CommandId::instances_readiness;
}

ApplicationResult InstanceApplicationModule::execute(
    ApplicationContext& context,
    const ApplicationRequest& request) const
{
    switch (request.command) {
    case CommandId::instances_describe:
        return handlers::describe_instance(
            context, std::get<InstanceProjectionRequest>(request.payload));
    case CommandId::instances_readiness:
        return handlers::readiness_instance(
            context, std::get<InstanceProjectionRequest>(request.payload));
    default:
        return refused(
            safety_refusal(
                "instance.module",
                "invalid_request",
                "Unsupported instance projection command",
                "",
                false),
            "invalid_request",
            "Unsupported instance projection command");
    }
}

} // namespace facman::factorio::application
