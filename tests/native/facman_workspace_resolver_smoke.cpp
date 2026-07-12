// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "workspace_resolver.h"

#include <filesystem>

int main()
{
    namespace fs = std::filesystem;
    using facman::client::LegacyWorkspaceState;
    using facman::client::WorkspaceResolutionInputs;
    WorkspaceResolutionInputs inputs;
    inputs.user_paths.home = fs::path("root") / "home";
    inputs.user_paths.data = fs::path("root") / "data";

    inputs.explicit_workspace = fs::path("chosen") / "explicit";
    inputs.facman_workspace = fs::path("chosen") / "primary";
    inputs.compatibility_workspace = fs::path("chosen") / "compatibility";
    auto result = facman::client::resolve_workspace_from_inputs(inputs);
    if (!result || result.value().source != "explicit" || result.value().path != inputs.explicit_workspace) return 1;

    inputs.explicit_workspace.clear();
    result = facman::client::resolve_workspace_from_inputs(inputs);
    if (!result || result.value().source != "FACMAN_WORKSPACE" || result.value().path != inputs.facman_workspace) return 2;

    inputs.facman_workspace.clear();
    result = facman::client::resolve_workspace_from_inputs(inputs);
    if (!result || result.value().source != "FACTORIO_LAUNCHER_WORKSPACE") return 3;

    inputs.compatibility_workspace.clear();
    inputs.preferred_workspace = fs::path("chosen") / "preferences";
    result = facman::client::resolve_workspace_from_inputs(inputs);
    if (!result || result.value().source != "preferences" || result.value().path != inputs.preferred_workspace) return 4;

    inputs.preferred_workspace.clear();
    inputs.legacy_state = LegacyWorkspaceState::directory;
    result = facman::client::resolve_workspace_from_inputs(inputs);
    if (!result || !result.value().legacy || result.value().source != "existing_legacy" ||
        result.value().path != inputs.user_paths.home / ".facman" / "workspace") return 5;

    inputs.legacy_state = LegacyWorkspaceState::missing;
    result = facman::client::resolve_workspace_from_inputs(inputs);
    if (!result || result.value().legacy || result.value().source != "platform_native" ||
        result.value().path != inputs.user_paths.data / "facman" / "workspace") return 6;

    inputs.legacy_state = LegacyWorkspaceState::unsafe;
    result = facman::client::resolve_workspace_from_inputs(inputs);
    if (result || result.error().code != "workspace_legacy_unsafe") return 7;

    inputs.legacy_state = LegacyWorkspaceState::missing;
    inputs.user_paths_available = false;
    result = facman::client::resolve_workspace_from_inputs(inputs);
    if (result || result.error().code != "workspace_default_unavailable" ||
        result.error().kind != facman::core::OutcomeKind::unavailable) return 8;
    return 0;
}
