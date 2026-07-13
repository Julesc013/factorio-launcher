// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_transport_direct.h"

#include "facman_client_internal.h"
#include "fl_command_client_cabi.h"
#include "fl_file_io.h"

namespace facman::client {
namespace {

ulk_string_view view(const std::string& text)
{
    return {text.data(), static_cast<ulk_size>(text.size())};
}

} // namespace

DirectFlbTransport::DirectFlbTransport(std::filesystem::path workspace)
    : workspace_(std::move(workspace))
{
    const std::string workspace_text = facman::platform::path_to_utf8(workspace_.lexically_normal());
    flb_config_v1 config {};
    config.struct_size = sizeof(config);
    config.workspace_root = view(workspace_text);
    (void)flb_context_create_v1(&config, &context_);
}

DirectFlbTransport::~DirectFlbTransport()
{
    flb_context_destroy_v1(context_);
}

facman::core::Result<CommandResponse> DirectFlbTransport::execute(const CommandRequest& request)
{
    if (request.command.empty()) return detail::failure("client_request_invalid", "command must not be empty");
    if (detail::cancelled(request)) {
        return detail::failure(
            "client_operation_cancelled",
            "command was cancelled before dispatch",
            {},
            facman::core::OutcomeKind::cancelled);
    }
    detail::progress(request, "waiting_for_direct_transport", 0, 3);
    std::lock_guard<std::mutex> lock(mutex_);
    if (detail::cancelled(request)) {
        return detail::failure(
            "client_operation_cancelled",
            "command was cancelled while waiting for transport",
            {},
            facman::core::OutcomeKind::cancelled);
    }
    if (context_ == nullptr) {
        return detail::failure(
            "client_context_create_failed",
            "Factorio binding context could not be created",
            facman::platform::path_to_utf8(workspace_.lexically_normal()));
    }
    ulk_command_request_v1 native_request {};
    ulk_command_response_v1 native_response {};
    native_request.struct_size = sizeof(native_request);
    native_request.command_name = view(request.command);
    native_request.json_payload = view(request.json_payload);
    native_request.dry_run = request.dry_run ? 1 : 0;
    native_response.struct_size = sizeof(native_response);
    detail::progress(request, "executing_direct_transport", 1, 3);
    const int status = fl_command_client_execute_cabi_v1(context_, &native_request, &native_response);
    if (detail::cancelled(request)) {
        return detail::failure(
            "client_operation_cancelled",
            "command was cancelled during dispatch",
            {},
            facman::core::OutcomeKind::cancelled);
    }
    std::string envelope;
    if (native_response.json_payload.data != nullptr) {
        envelope.assign(
            native_response.json_payload.data,
            native_response.json_payload.data + native_response.json_payload.size);
    }
    if (envelope.empty()) return detail::failure("client_response_empty", "Factorio binding returned an empty response");
    detail::progress(request, "decoding_response", 2, 3);
    auto response = detail::decode_response(status, std::move(envelope));
    detail::progress(request, "completed", 3, 3);
    return response;
}

} // namespace facman::client
