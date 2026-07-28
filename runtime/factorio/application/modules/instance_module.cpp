// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "modules/instance_module.h"

#include "command_result.h"
#include "handlers/instances.h"
#include "handlers/saves.h"

namespace facman::factorio::application {

bool InstanceApplicationModule::handles(CommandId command) const noexcept
{
    switch (command) {
    case CommandId::instance_list:
    case CommandId::instance_create:
    case CommandId::instances_describe:
    case CommandId::instances_readiness:
    case CommandId::instances_inspect:
    case CommandId::instances_verify:
    case CommandId::instances_diff:
    case CommandId::instances_clone:
    case CommandId::instances_rename:
    case CommandId::instances_archive:
    case CommandId::instances_restore:
    case CommandId::instance_export:
    case CommandId::instance_import:
        return true;
    default:
        return false;
    }
}

ApplicationResult InstanceApplicationModule::execute(
    ApplicationContext& context,
    const ApplicationRequest& request,
    const CommandAdmissionDecision&,
    const std::string&) const
{
    switch (request.command) {
    case CommandId::instance_list:
        return handlers::list_instances(context);
    case CommandId::instance_create:
        return handlers::create_instance(
            context, std::get<CreateInstanceRequest>(request.payload));
    case CommandId::instances_describe:
        return handlers::describe_instance(
            context, std::get<InstanceProjectionRequest>(request.payload));
    case CommandId::instances_readiness:
        return handlers::readiness_instance(
            context, std::get<InstanceProjectionRequest>(request.payload));
    case CommandId::instances_inspect:
    case CommandId::instances_verify:
    case CommandId::instances_diff:
    case CommandId::instances_clone:
    case CommandId::instances_rename:
    case CommandId::instances_archive:
    case CommandId::instances_restore:
        return handlers::dispatch_instance_lifecycle(context, request);
    case CommandId::instance_export:
        return handlers::export_instance(
            context, std::get<ExportInstanceRequest>(request.payload));
    case CommandId::instance_import:
        return handlers::import_instance(
            context, std::get<ImportInstanceRequest>(request.payload));
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
