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

struct WorkspaceMigrationControlCommand {
    bool matched = false;
    bool valid = false;
    std::string payload;
    std::string request_id;
    std::string operation_id;
    std::string attempt_id;
};

WorkspaceMigrationControlCommand parse_workspace_migration_control(
    const std::vector<std::string>& args);

struct WorkspaceCommand {
    bool valid = false;
    bool guidance = false;
    bool read_only = true;
    std::string command;
    std::string payload;
    std::string request_id;
    std::string operation_id;
    std::string attempt_id;
};

WorkspaceCommand parse_workspace_command(const std::vector<std::string>& args);

} // namespace facman::cli

#endif
