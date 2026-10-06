// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#ifndef FLB_FACTORIO_INSTANCE_STAGING_H
#define FLB_FACTORIO_INSTANCE_STAGING_H
#include "fl_workspace_store.h"
#include "flb_factorio_discovery.h"
namespace facman::factorio::instance {
std::string instance_manifest_json(const facman::workspace::InstanceRecord& instance);
std::string instance_effective_config(const facman::workspace::InstanceRecord& instance,
    const facman::factorio::discovery::InstallRef& install);
bool prepare_instance_layout(const std::filesystem::path& staging, std::string& detail);
}
#endif
