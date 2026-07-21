// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_PERMIT_PROJECTION_H
#define FLB_FACTORIO_PERMIT_PROJECTION_H

#include "fl_operation_permit.h"
#include "fl_result.h"

#include <filesystem>
#include <string>
#include <vector>

namespace facman::factorio::instance {

struct MenuPermitResourceProjection {
    std::string instance_id;
    std::vector<facman::core::permit::ResourceBinding> resources;
    std::vector<facman::core::permit::ProviderIdentity> provider_revisions;
    std::string evidence_digest;
    std::vector<std::string> missing_play_resources;
    bool launch_authority_complete = false;
};

facman::core::Result<MenuPermitResourceProjection> project_menu_permit_resources(
    const std::filesystem::path& workspace,
    const std::string& instance_id);

} // namespace facman::factorio::instance

#endif
