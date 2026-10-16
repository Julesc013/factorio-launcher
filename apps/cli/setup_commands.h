// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#pragma once

#include <optional>
#include <string>
#include <vector>

namespace facman::cli {

struct SetupApplyCommand {
    std::string command;
    std::string payload;
    std::string success_message;
};

bool move_plan_arguments_valid(const std::vector<std::string>& args);

std::optional<SetupApplyCommand> setup_apply_request(
    const std::string& action,
    const std::vector<std::string>& args);

} // namespace facman::cli
