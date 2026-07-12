// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#pragma once

#include "facman_client.h"
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
    std::chrono::milliseconds timeout {std::chrono::minutes(5)};
};

class CommandClient {
public:
    explicit CommandClient(std::filesystem::path workspace);
    facman::core::Result<facman::client::CommandResponse> execute(const Invocation& invocation);

private:
    facman::client::FacManClient client_;
};

const GeneratedCommand* find_command(const std::string& command);
bool command_writes(const GeneratedCommand& command);

}  // namespace facman::tui
