// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_transport_process.h"

#include "facman_client_internal.h"
#include "fl_file_io.h"
#include "fl_process_supervisor.h"

#include <atomic>

namespace facman::client {
namespace json = facman::core::json;

CliProcessTransport::CliProcessTransport(std::filesystem::path executable, std::filesystem::path workspace)
    : executable_(std::move(executable)), workspace_(std::move(workspace))
{
}

facman::core::Result<CommandResponse> CliProcessTransport::execute(const CommandRequest& request)
{
    if (request.command.empty()) return detail::failure("client_request_invalid", "command must not be empty");
    if (!std::filesystem::is_regular_file(executable_)) {
        return detail::failure(
            "cli_process_executable_missing",
            "CLI process executable does not exist",
            facman::platform::path_to_utf8(executable_),
            facman::core::OutcomeKind::not_found);
    }
    json::Limits limits;
    limits.maximum_bytes = 1024U * 1024U;
    limits.maximum_depth = 32;
    limits.maximum_nodes = 32768;
    limits.maximum_string_bytes = 512U * 1024U;
    auto payload = json::parse(request.json_payload.empty() ? "{}" : request.json_payload, limits);
    if (!payload || !payload.value().is_object()) {
        return detail::failure(
            "client_request_invalid",
            payload ? "command payload must be an object" : payload.error().message);
    }
    static std::atomic<std::uint64_t> next_request {1};
    json::ObjectBuilder envelope;
    envelope.add_string("schema", "facman.transport_request.v1");
    envelope.add_string(
        "request_id",
        "cli-" + std::to_string(next_request.fetch_add(1, std::memory_order_relaxed)));
    (void)envelope.add_unsigned_integer("protocol_version", 1);
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
        return detail::failure(
            "client_operation_cancelled",
            "CLI process command was cancelled",
            {},
            facman::core::OutcomeKind::cancelled);
    }
    if (result.termination == facman::platform::ProcessTermination::timed_out) {
        return detail::failure(
            "cli_process_timeout",
            "CLI process exceeded its timeout",
            {},
            facman::core::OutcomeKind::timeout);
    }
    if (result.termination == facman::platform::ProcessTermination::output_limit) {
        return detail::failure("cli_process_output_too_large", "CLI process exceeded its output budget");
    }
    if (!result.error.empty()) {
        return detail::failure(
            "cli_process_start_failed",
            result.error,
            facman::platform::path_to_utf8(executable_));
    }
    detail::progress(request, "decoding_cli_response", 2, 3);
    if (result.standard_output.empty()) {
        return detail::failure(
            "cli_process_response_empty",
            result.standard_error.empty() ? "CLI process returned no machine response" : result.standard_error);
    }
    auto response = detail::decode_response(result.exit_code, std::move(result.standard_output));
    detail::progress(request, "completed", 3, 3);
    return response;
}

} // namespace facman::client
