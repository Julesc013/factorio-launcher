// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_APPS_CLI_WORKSPACE_COMMANDS_H
#define FACMAN_APPS_CLI_WORKSPACE_COMMANDS_H

#include <string>
#include <vector>

namespace facman::cli {

struct WorkspaceMigrationApplyCommand {
    bool matched = false;
    bool valid = false;
    std::string payload;
    std::string request_id;
    std::string operation_id;
    std::string attempt_id;
};

WorkspaceMigrationApplyCommand parse_workspace_migration_apply(
    const std::vector<std::string>& args);

} // namespace facman::cli

#endif
