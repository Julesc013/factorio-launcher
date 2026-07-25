// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "modules/diagnostics_module.h"

#include "command_result.h"
#include "handlers/diagnostics.h"
#include "handlers/utility.h"

namespace facman::factorio::application {

bool DiagnosticsApplicationModule::handles(CommandId command) const noexcept
{
    switch (command) {
    case CommandId::diagnostics_redact:
    case CommandId::diagnostics_export:
    case CommandId::dev_bug_report:
    case CommandId::dev_dump_data:
    case CommandId::dev_dump_icons:
    case CommandId::dev_benchmark:
    case CommandId::dev_instrument_mod:
        return true;
    default:
        return false;
    }
}

ApplicationResult DiagnosticsApplicationModule::execute(
    ApplicationContext& context,
    const ApplicationRequest& request,
    const CommandAdmissionDecision&,
    const std::string&) const
{
    switch (request.command) {
    case CommandId::diagnostics_redact:
        return handlers::redact_diagnostics(
            context, std::get<ServiceOperationRequest>(request.payload));
    case CommandId::diagnostics_export:
        return handlers::export_diagnostics(
            context, std::get<ExportDiagnosticRequest>(request.payload));
    case CommandId::dev_bug_report:
        return handlers::create_bug_report(context);
    case CommandId::dev_dump_data:
    case CommandId::dev_dump_icons:
    case CommandId::dev_benchmark:
    case CommandId::dev_instrument_mod:
        return handlers::refuse_dev_execution(
            context, std::get<ServiceOperationRequest>(request.payload));
    default:
        return refused(
            safety_refusal(
                "diagnostics.module",
                "invalid_request",
                "Unsupported diagnostics command",
                "",
                false),
            "invalid_request",
            "Unsupported diagnostics command");
    }
}

} // namespace facman::factorio::application
