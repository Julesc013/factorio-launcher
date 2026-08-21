// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#pragma once

#include "frontend_session.h"
#include "generated_command_catalog.hpp"

#include <filesystem>
#include <chrono>
#include <string>

namespace facman::tui {

struct Invocation {
    std::string command;
    std::string payload = "{}";
    bool allow_write = false;
    bool cancel_before_start = false;
    std::shared_ptr<facman::client::ProgressSink> progress;
    std::chrono::milliseconds timeout {std::chrono::minutes(5)};
    // Appended to preserve source compatibility for the existing aggregate
    // initializers used by generated/Advanced TUI call sites.
    std::string request_id;
    std::string operation_id;
    std::string attempt_id;
};

class CommandClient {
public:
    explicit CommandClient(
        std::filesystem::path workspace,
        std::string transport = "direct",
        std::filesystem::path process_executable = {});
    facman::core::Result<facman::client::CommandResponse> execute(const Invocation& invocation);
    facman::core::Result<facman::frontend::FrontendSessionIdentity> negotiate(
        const std::string& scope = "launch_deck",
        const std::string& selected_instance_id = {},
        const std::string& search = {});
    const char* transport_name() const noexcept;

private:
    facman::frontend::FrontendSession session_;
};

const GeneratedCommand* find_command(const std::string& command);
bool command_writes(const GeneratedCommand& command);

}  // namespace facman::tui
