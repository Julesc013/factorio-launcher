// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "modules/setup_module.h"

#include "handlers/setup.h"

namespace facman::factorio::application {

bool SetupApplicationModule::handles(CommandId command) const noexcept
{
    return handlers::is_setup_command(command);
}

ApplicationResult SetupApplicationModule::execute(
    ApplicationContext& context,
    const ApplicationRequest& request,
    const CommandAdmissionDecision&,
    const std::string&) const
{
    return handlers::dispatch_setup(context, request);
}

} // namespace facman::factorio::application
