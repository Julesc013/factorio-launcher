// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#ifndef FACMAN_CLI_RESOURCE_COMMANDS_H
#define FACMAN_CLI_RESOURCE_COMMANDS_H
#include "facman_client_model.h"
#include "fl_resource_pack.h"
#include <functional>
#include <string>
#include <vector>
namespace facman::cli {
struct ResourceCommandResult {
    bool valid_invocation = false;
    std::string command = "resources";
    std::string destination;
    facman::archive::ExtractionObservation extraction;
    facman::core::Result<std::string> payload = facman::core::Result<std::string>::failure(
        {"resource_command_invalid", "Invalid resources command", "$", facman::core::OutcomeKind::invalid_argument});
    std::string human_output;
};
struct ResourceCommandCheckpoints {
    facman::archive::ExtractionCheckpoint extraction;
    std::function<void()> before_export_failure_report;
};
// The CLI and native causal tests share this production export boundary.
// Checkpoints are internal C++ seams, never options/environment in the CLI.
ResourceCommandResult run_resource_export(
    const facman::resources::ResourceSelection& selected, const std::string& destination,
    const facman::archive::ExtractionCheckpoint& checkpoint = {});
// Caller-owned observation survives both extraction and reporting exceptions.
void run_resource_export_into(ResourceCommandResult& result,
    const facman::resources::ResourceSelection& selected, const std::string& destination,
    const ResourceCommandCheckpoints& checkpoints = {});
ResourceCommandResult run_resource_command(
    const std::vector<std::string>& arguments, const std::string& executable_path,
    const ResourceCommandCheckpoints& checkpoints = {});
facman::client::CommandResponse resource_command_response(
    const ResourceCommandResult& result, const std::string& operation_id, const std::string& attempt_id);
}
#endif
