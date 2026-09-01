// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_APPS_CLI_RESOURCE_COMMANDS_H
#define FACMAN_APPS_CLI_RESOURCE_COMMANDS_H

#include "fl_result.h"

#include <string>
#include <vector>

namespace facman::cli {

struct ResourceCommandResult {
    bool valid_invocation = false;
    facman::core::Result<std::string> payload = facman::core::Result<std::string>::failure(
        {"resource_command_invalid", "Invalid resources command", "$",
         facman::core::OutcomeKind::invalid_argument});
    std::string human_output;
};

ResourceCommandResult run_resource_command(
    const std::vector<std::string>& arguments,
    const std::string& executable_path);

} // namespace facman::cli

#endif
