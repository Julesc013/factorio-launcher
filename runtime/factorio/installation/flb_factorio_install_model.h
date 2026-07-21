// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_INSTALL_MODEL_H
#define FLB_FACTORIO_INSTALL_MODEL_H

#include "fl_result.h"
#include "flb_factorio_discovery.h"

#include <string>

namespace facman::factorio::installation {

struct DesiredInstallationState {
    std::string install_id;
    std::string version;
    std::string source_ref;
    std::string target_root;
    std::string management_mode = "preserve";
    std::string deployment_style = "preserve";
    std::string data_policy = "preserve";
    std::string integration_mode = "preserve";
    std::string update_policy = "preserve";
};

std::string installation_model_json(const discovery::InstallRef& install);

facman::core::Result<std::string> reconciliation_plan_json(
    const discovery::InstallRef& install,
    const DesiredInstallationState& desired);

} // namespace facman::factorio::installation

#endif
