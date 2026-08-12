// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "modules/presentation_module.h"

#include "command_result.h"

namespace facman::factorio::application {

bool PresentationApplicationModule::handles(CommandId command) const noexcept
{
    return command == CommandId::presentation_query ||
        command == CommandId::presentation_action;
}

ApplicationResult PresentationApplicationModule::execute(
    ApplicationContext& context,
    const ApplicationRequest& request,
    const CommandAdmissionDecision&,
    const std::string&) const
{
    PresentationService service(context, context.last_run_provider(), action_ledger_);
    switch (request.command) {
    case CommandId::presentation_query:
        return service.query(std::get<PresentationQueryRequest>(request.payload));
    case CommandId::presentation_action:
        return service.action(std::get<SemanticActionRequest>(request.payload));
    default:
        return refused(
            safety_refusal(
                "presentation.module", "invalid_request",
                "Unsupported presentation command", {}, false),
            "invalid_request", "Unsupported presentation command");
    }
}

} // namespace facman::factorio::application
