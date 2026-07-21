// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "modules/installation_module.h"

#include "command_result.h"
#include "handlers/installs.h"

namespace facman::factorio::application {

bool InstallationApplicationModule::handles(CommandId command) const noexcept
{
    return command == CommandId::install_list ||
        command == CommandId::install_scan ||
        command == CommandId::install_import ||
        command == CommandId::install_inspect ||
        command == CommandId::installs_describe ||
        command == CommandId::installs_reconcile_plan;
}

ApplicationResult InstallationApplicationModule::execute(
    ApplicationContext& context,
    const ApplicationRequest& request) const
{
    switch (request.command) {
    case CommandId::install_list:
        return handlers::list_installs(context);
    case CommandId::install_scan:
        return handlers::scan_installs(context, std::get<ScanInstallRefsRequest>(request.payload));
    case CommandId::install_import:
        return handlers::import_install(context, std::get<ImportInstallRefRequest>(request.payload));
    case CommandId::install_inspect:
        return handlers::inspect_install(context, std::get<InspectInstallRefRequest>(request.payload));
    case CommandId::installs_describe:
        return handlers::describe_install(context, std::get<DescribeInstallRequest>(request.payload));
    case CommandId::installs_reconcile_plan:
        return handlers::plan_install_reconciliation(
            context, std::get<ReconcileInstallRequest>(request.payload));
    default:
        return refused(
            safety_refusal(
                "installation.module",
                "invalid_request",
                "Unsupported installation command",
                "",
                false),
            "invalid_request",
            "Unsupported installation command");
    }
}

} // namespace facman::factorio::application
