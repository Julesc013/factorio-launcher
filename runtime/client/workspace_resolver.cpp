// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "workspace_resolver.h"

#include "fl_file_io.h"
#include "fl_preferences.h"

#include <cstdlib>
#include <system_error>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

namespace facman::client {
namespace fs = std::filesystem;
namespace {

fs::path environment_path(const char* name)
{
#ifdef _WIN32
    std::wstring wide_name;
    while (*name != '\0') wide_name.push_back(static_cast<wchar_t>(*name++));
    const wchar_t* value = _wgetenv(wide_name.c_str());
    return value == nullptr || *value == L'\0' ? fs::path {} : fs::path(value);
#else
    const char* value = std::getenv(name);
    return value == nullptr || *value == '\0' ? fs::path {} : fs::path(value);
#endif
}

LegacyWorkspaceState inspect_legacy(const fs::path& path)
{
    std::error_code error;
    const fs::file_status status = fs::symlink_status(path, error);
    if (error == std::errc::no_such_file_or_directory || status.type() == fs::file_type::not_found) {
        return LegacyWorkspaceState::missing;
    }
    if (error || fs::is_symlink(status) || !fs::is_directory(status)) return LegacyWorkspaceState::unsafe;
#ifdef _WIN32
    const DWORD attributes = GetFileAttributesW(path.c_str());
    if (attributes == INVALID_FILE_ATTRIBUTES || (attributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0) {
        return LegacyWorkspaceState::unsafe;
    }
#endif
    return LegacyWorkspaceState::directory;
}

WorkspaceResolution selected(fs::path path, const char* source, bool legacy = false)
{
    return {path.lexically_normal(), source, legacy};
}

} // namespace

facman::core::Result<WorkspaceResolution> resolve_workspace_from_inputs(
    const WorkspaceResolutionInputs& inputs)
{
    if (!inputs.explicit_workspace.empty()) {
        return facman::core::Result<WorkspaceResolution>::success(
            selected(inputs.explicit_workspace, "explicit"));
    }
    if (!inputs.facman_workspace.empty()) {
        return facman::core::Result<WorkspaceResolution>::success(
            selected(inputs.facman_workspace, "FACMAN_WORKSPACE"));
    }
    if (!inputs.compatibility_workspace.empty()) {
        return facman::core::Result<WorkspaceResolution>::success(
            selected(inputs.compatibility_workspace, "FACTORIO_LAUNCHER_WORKSPACE"));
    }
    if (!inputs.preferred_workspace.empty()) {
        return facman::core::Result<WorkspaceResolution>::success(
            selected(inputs.preferred_workspace, "preferences"));
    }
    if (!inputs.user_paths_available || inputs.user_paths.home.empty() || inputs.user_paths.data.empty()) {
        return facman::core::Result<WorkspaceResolution>::failure({
            "workspace_default_unavailable",
            "No explicit workspace or safe platform user path is available",
            "workspace",
            facman::core::OutcomeKind::unavailable,
        });
    }
    const fs::path legacy = inputs.user_paths.home / ".facman" / "workspace";
    if (inputs.legacy_state == LegacyWorkspaceState::unsafe) {
        return facman::core::Result<WorkspaceResolution>::failure({
            "workspace_legacy_unsafe",
            "The existing legacy workspace is not a real directory or is a link/reparse point",
            facman::platform::path_to_utf8(legacy),
            facman::core::OutcomeKind::refused,
        });
    }
    if (inputs.legacy_state == LegacyWorkspaceState::directory) {
        return facman::core::Result<WorkspaceResolution>::success(selected(legacy, "existing_legacy", true));
    }
    return facman::core::Result<WorkspaceResolution>::success(
        selected(inputs.user_paths.data / "facman" / "workspace", "platform_native"));
}

facman::core::Result<WorkspaceResolution> resolve_workspace(const fs::path& explicit_workspace)
{
    WorkspaceResolutionInputs inputs;
    inputs.explicit_workspace = explicit_workspace;
    inputs.facman_workspace = environment_path("FACMAN_WORKSPACE");
    inputs.compatibility_workspace = environment_path("FACTORIO_LAUNCHER_WORKSPACE");
    if (!inputs.explicit_workspace.empty() || !inputs.facman_workspace.empty() ||
        !inputs.compatibility_workspace.empty()) {
        return resolve_workspace_from_inputs(inputs);
    }
    auto preferences = facman::preferences::inspect();
    if (!preferences) return facman::core::Result<WorkspaceResolution>::failure(preferences.error());
    if (preferences.value().present) {
        inputs.preferred_workspace = facman::platform::path_from_utf8(
            preferences.value().values.preferred_workspace);
    }
    auto paths = facman::platform::user_paths();
    if (paths) {
        inputs.user_paths = paths.take_value();
        inputs.legacy_state = inspect_legacy(inputs.user_paths.home / ".facman" / "workspace");
    } else {
        inputs.user_paths_available = false;
    }
    return resolve_workspace_from_inputs(inputs);
}

} // namespace facman::client
