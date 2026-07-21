// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_INSTANCE_MODEL_H
#define FLB_FACTORIO_INSTANCE_MODEL_H

#include "fl_result.h"

#include <filesystem>
#include <string>

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

} // namespace facman::factorio::instance

#endif
