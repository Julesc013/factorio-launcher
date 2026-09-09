// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "resource_commands.h"
#include "fl_json.h"
#include <memory>
namespace facman::cli {
namespace {
std::string recovery_payload(const ResourceCommandResult& result,
    const std::string& operation_id, const std::string& attempt_id)
{
    facman::core::json::ObjectBuilder payload;
    payload.add_string("schema", "facman.resource_export_recovery.v1");
    payload.add_string("destination", result.destination);
    payload.add_string("operation_id", operation_id);
    payload.add_string("attempt_id", attempt_id);
    payload.add_string("phase", result.extraction.phase());
    payload.add_string("error_code", result.payload.error().code);
    payload.add_string("error_message", result.payload.error().message);
    payload.add_string("inspect_command", "resources.export.inspect");
    facman::core::json::ArrayBuilder arguments;
    for (const auto& argument : std::vector<std::string>{
            "resources", "inspect-export", result.destination, "--json"})
        arguments.add_string(argument);
    payload.add_array("inspect_arguments", arguments);
    payload.add_bool("ownership_proven", false);
    return payload.serialize();
}
}
facman::client::CommandResponse resource_command_response(
    const ResourceCommandResult& result, const std::string& operation_id, const std::string& attempt_id)
{
    facman::client::CommandResponse response;
    response.operation.operation_id = operation_id;
    response.operation.attempt_id = attempt_id;
    response.operation.effects_may_have_occurred = result.extraction.effects_possible();
    if (result.payload) {
        response.status = 0;
        response.outcome_kind = facman::core::OutcomeKind::ok;
        response.operation.outcome = facman::client::OperationOutcome::completed;
        response.payload = result.payload.value();
    } else {
        response.status = 1;
        response.outcome_kind = result.payload.error().kind;
        response.error_code = result.payload.error().code;
        response.error_message = result.payload.error().message;
        if (result.extraction.effects_possible()) {
            response.outcome_kind = facman::core::OutcomeKind::recovery_required;
            response.operation.outcome = facman::client::OperationOutcome::recovery_required;
            response.operation.recovery.required = true;
            response.operation.recovery.inspect_command = "resources.export.inspect";
            response.payload = recovery_payload(result, operation_id, attempt_id);
        }
    }
    response.outcome = facman::core::outcome_kind_name(response.outcome_kind);
    if (!response.payload.empty()) {
        auto parsed = facman::core::json::parse(response.payload);
        if (parsed) response.parsed_payload =
            std::make_shared<facman::core::json::Value>(parsed.take_value());
    }
    return response;
}
}
