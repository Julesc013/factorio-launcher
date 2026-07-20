// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "tui_command_client.hpp"

#include "generated_command_catalog.hpp"

#include <memory>

namespace facman::tui {
namespace {

std::unique_ptr<facman::client::Transport> make_transport(
    std::filesystem::path workspace,
    const std::string& transport,
    std::filesystem::path process_executable)
{
    if (transport == "process") return std::make_unique<facman::client::CliProcessTransport>(
        std::move(process_executable), std::move(workspace));
    if (transport == "daemon") return std::make_unique<facman::client::DaemonTransport>();
    return std::make_unique<facman::client::DirectFlbTransport>(std::move(workspace));
}

}  // namespace

CommandClient::CommandClient(
    std::filesystem::path workspace,
    std::string transport,
    std::filesystem::path process_executable)
    : client_(make_transport(std::move(workspace), transport, std::move(process_executable)))
{
}

facman::core::Result<facman::client::CommandResponse> CommandClient::execute(const Invocation& invocation)
{
    const GeneratedCommand* command = find_command(invocation.command);
    const bool dry_run = command == nullptr || !command_writes(*command) || !invocation.allow_write;
    facman::client::CommandRequest request {invocation.command, invocation.payload, dry_run};
    request.timeout = invocation.timeout;
    request.progress = invocation.progress;
    if (invocation.cancel_before_start) {
        request.cancellation = std::make_shared<facman::client::CancellationToken>();
        request.cancellation->request_cancellation();
    }
    return client_.execute(request);
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
