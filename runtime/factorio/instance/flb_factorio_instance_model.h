// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_INSTANCE_MODEL_H
#define FLB_FACTORIO_INSTANCE_MODEL_H

#include "fl_result.h"

#include <filesystem>
#include <string>

namespace facman::transaction { struct Record; }

namespace facman::factorio::instance {

struct ProjectionRequest {
    std::string instance_id;
    std::string launch_intent = "menu";
};

facman::core::Result<std::string> describe_instance(
    const std::filesystem::path& workspace,
    const ProjectionRequest& request);

facman::core::Result<std::string> instance_readiness(
    const std::filesystem::path& workspace,
    const ProjectionRequest& request);

facman::core::Result<std::string> selected_save_preparation_plan(
    const std::filesystem::path& workspace, const ProjectionRequest& request);
// Read-only context guard, excluding only this validated owner's permitted effects.
facman::core::Result<std::string> observe_selected_save_preparation_inputs(
    const std::filesystem::path& workspace, const ProjectionRequest& request,
    const facman::transaction::Record* own);
facman::core::Result<std::string> prepare_selected_save(
    const std::filesystem::path& workspace, const ProjectionRequest& request,
    const std::string& expected_plan_sha256, const std::string& operation_id,
    const std::string& attempt_id);
facman::core::Result<std::string> recover_selected_save_preparation(
    const std::filesystem::path& workspace, const std::string& transaction_id);

} // namespace facman::factorio::instance

#endif
