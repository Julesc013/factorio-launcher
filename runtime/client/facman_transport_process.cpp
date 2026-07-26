// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_transport_process.h"

#include "facman_client_internal.h"
#include "fl_file_io.h"
#include "fl_process_supervisor.h"

namespace facman::client {
namespace json = facman::core::json;

CliProcessTransport::CliProcessTransport(std::filesystem::path executable, std::filesystem::path workspace)
    : executable_(std::move(executable)), workspace_(std::move(workspace))
{
}

facman::core::Result<CommandResponse> CliProcessTransport::execute(const CommandRequest& request)
{
    if (request.command.empty()) {
        return detail::terminal_response(
            request, 1, facman::core::OutcomeKind::invalid_argument, "invalid_argument",
            "client_request_invalid", "command must not be empty", OperationOutcome::refused_before_effects);
    }
    if (!std::filesystem::is_regular_file(executable_)) {
        return detail::terminal_response(
            request, 1, facman::core::OutcomeKind::not_found, "not_found",
            "cli_process_executable_missing", "CLI process executable does not exist",
            OperationOutcome::refused_before_effects);
    }
    json::Limits limits;
    limits.maximum_bytes = 1024U * 1024U;
    limits.maximum_depth = 32;
    limits.maximum_nodes = 32768;
    limits.maximum_string_bytes = 512U * 1024U;
    auto payload = json::parse(request.json_payload.empty() ? "{}" : request.json_payload, limits);
    if (!payload || !payload.value().is_object()) {
        return detail::terminal_response(
            request, 1, facman::core::OutcomeKind::invalid_argument, "invalid_argument",
            "client_request_invalid",
            payload ? "command payload must be an object" : payload.error().message,
            OperationOutcome::refused_before_effects);
    }
    json::ObjectBuilder envelope;
    envelope.add_string("schema", "facman.transport_request.v2");
    envelope.add_string("request_id", request.attempt_id);
    (void)envelope.add_unsigned_integer("protocol_version", 2);
    envelope.add_string("operation_id", request.operation_id);
    envelope.add_string("attempt_id", request.attempt_id);
    envelope.add_string("command", request.command);
    envelope.add_value("payload", payload.value());
    envelope.add_bool("dry_run", request.dry_run);
    if (!workspace_.empty()) {
        envelope.add_string("workspace", facman::platform::path_to_utf8(workspace_.lexically_normal()));
    }
    detail::progress(request, "starting_cli_process", 0, 3);
    facman::platform::ProcessRequest process;
    process.executable = executable_;
    process.arguments = {"rpc", "--stdio"};
    process.standard_input = envelope.serialize();
    process.timeout = request.timeout;
    process.cancellation_requested = [&request]() { return detail::cancelled(request); };
    auto result = facman::platform::supervise_process(process);
    if (result.termination == facman::platform::ProcessTermination::cancelled) {
        const bool dispatched = result.identity.process_id != 0;
        return detail::terminal_response(
            request, 1, facman::core::OutcomeKind::cancelled, "cancelled",
            "client_operation_cancelled",
            dispatched
                ? "CLI process command was cancelled after dispatch; effects may have occurred"
                : "CLI process command was cancelled before dispatch",
            dispatched ? OperationOutcome::outcome_unknown : OperationOutcome::cancelled_before_dispatch);
    }
    if (result.termination == facman::platform::ProcessTermination::timed_out) {
        return detail::terminal_response(
            request, 1, facman::core::OutcomeKind::timeout, "timeout",
            "cli_process_timeout", "CLI process exceeded its timeout after dispatch; effects may have occurred",
            result.identity.process_id == 0
                ? OperationOutcome::refused_before_effects
                : OperationOutcome::outcome_unknown);
    }
    if (result.termination == facman::platform::ProcessTermination::output_limit) {
        return detail::terminal_response(
            request, 1, facman::core::OutcomeKind::internal_error, "internal_error",
            "cli_process_output_too_large", "CLI process exceeded its output budget after dispatch",
            result.identity.process_id == 0
                ? OperationOutcome::refused_before_effects
                : OperationOutcome::outcome_unknown);
    }
    if (!result.error.empty()) {
        return detail::terminal_response(
            request, 1, facman::core::OutcomeKind::unavailable, "unavailable",
            "cli_process_start_failed", result.error,
            result.identity.process_id == 0
                ? OperationOutcome::refused_before_effects
                : OperationOutcome::outcome_unknown);
    }
    detail::progress(request, "decoding_cli_response", 2, 3);
    if (result.standard_output.empty()) {
        return detail::terminal_response(
            request, 1, facman::core::OutcomeKind::internal_error, "internal_error",
            "cli_process_response_empty",
            result.standard_error.empty()
                ? "CLI process returned no machine response after dispatch; effects may have occurred"
                : result.standard_error,
            result.identity.process_id == 0
                ? OperationOutcome::refused_before_effects
                : OperationOutcome::outcome_unknown);
    }
    auto response = detail::decode_response(result.exit_code, std::move(result.standard_output));
    detail::progress(request, "completed", 3, 3);
    if (!response) return response;
    return detail::finalize_response(
        request, response.take_value(), detail::cancelled(request));
}

} // namespace facman::client
