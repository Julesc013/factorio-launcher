// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "tui_command_client.hpp"

#include "generated_command_catalog.hpp"

namespace facman::tui {
namespace {

facman::frontend::FrontendSessionOptions session_options(
    std::filesystem::path workspace,
    const std::string& transport,
    std::filesystem::path process_executable)
{
    facman::frontend::FrontendSessionOptions options;
    options.workspace = std::move(workspace);
    options.process_executable = std::move(process_executable);
    auto parsed = facman::frontend::parse_transport_kind(transport);
    options.transport = parsed
        ? parsed.value()
        : facman::frontend::TransportKind::daemon;
    return options;
}

}  // namespace

CommandClient::CommandClient(
    std::filesystem::path workspace,
    std::string transport,
    std::filesystem::path process_executable)
    : session_(session_options(std::move(workspace), transport, std::move(process_executable)))
{
}

facman::core::Result<facman::client::CommandResponse> CommandClient::execute(const Invocation& invocation)
{
    const GeneratedCommand* command = find_command(invocation.command);
    const bool dynamic_semantic_action = invocation.command == "presentation.action";
    const bool effectful_dispatch = invocation.allow_write &&
        (dynamic_semantic_action || (command != nullptr && command_writes(*command)));
    const bool dry_run = !effectful_dispatch;
    facman::frontend::FrontendInvocation request;
    request.command = invocation.command;
    request.payload = invocation.payload;
    request.request_id = invocation.request_id;
    request.operation_id = invocation.operation_id;
    request.attempt_id = invocation.attempt_id;
    request.dry_run = dry_run;
    request.timeout = invocation.timeout;
    request.progress = invocation.progress;
    if (invocation.cancel_before_start) {
        request.cancellation = std::make_shared<facman::client::CancellationToken>();
        request.cancellation->request_cancellation();
    }
    return session_.execute(std::move(request)).response;
}

facman::core::Result<facman::frontend::FrontendSessionIdentity> CommandClient::negotiate(
    const std::string& scope,
    const std::string& selected_instance_id,
    const std::string& search)
{
    return session_.negotiate(scope, selected_instance_id, search);
}

const char* CommandClient::transport_name() const noexcept
{
    return session_.transport_name();
}

const GeneratedCommand* find_command(const std::string& command)
{
    for (const auto& item : kGeneratedCommands) {
        if (command == item.command_id || command == item.runtime_id) return &item;
    }
    return nullptr;
}

bool command_writes(const GeneratedCommand& command)
{
    return command.writes_state != 0;
}

}  // namespace facman::tui
