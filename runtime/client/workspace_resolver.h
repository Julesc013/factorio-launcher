// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_RUNTIME_CLIENT_WORKSPACE_RESOLVER_H
#define FACMAN_RUNTIME_CLIENT_WORKSPACE_RESOLVER_H

#include "fl_result.h"
#include "fl_user_paths.h"

#include <filesystem>
#include <string>

namespace facman::client {

enum class LegacyWorkspaceState {
    missing,
    directory,
    unsafe,
};

struct WorkspaceResolutionInputs {
    std::filesystem::path explicit_workspace;
    std::filesystem::path facman_workspace;
    std::filesystem::path compatibility_workspace;
    facman::platform::UserPaths user_paths;
    bool user_paths_available = true;
    LegacyWorkspaceState legacy_state = LegacyWorkspaceState::missing;
};

struct WorkspaceResolution {
    std::filesystem::path path;
    std::string source;
    bool legacy = false;
};

facman::core::Result<WorkspaceResolution> resolve_workspace(
    const std::filesystem::path& explicit_workspace = {});
facman::core::Result<WorkspaceResolution> resolve_workspace_from_inputs(
    const WorkspaceResolutionInputs& inputs);

} // namespace facman::client

#endif
