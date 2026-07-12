// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_user_paths.h"

#include <cstdlib>

namespace facman::platform {
namespace {

std::filesystem::path absolute_environment_path(const char* name)
{
    const char* value = std::getenv(name);
    if (value == nullptr || *value == '\0') return {};
    std::filesystem::path path(value);
    return path.is_absolute() ? path.lexically_normal() : std::filesystem::path {};
}

} // namespace

facman::core::Result<UserPaths> user_paths()
{
    const std::filesystem::path home = absolute_environment_path("HOME");
    if (home.empty()) {
        return facman::core::Result<UserPaths>::failure(
            {"user_path_unavailable", "HOME is missing or is not absolute", "HOME"});
    }
    UserPaths output;
    output.home = home;
    output.data = absolute_environment_path("XDG_DATA_HOME");
    output.config = absolute_environment_path("XDG_CONFIG_HOME");
    output.cache = absolute_environment_path("XDG_CACHE_HOME");
    output.state = absolute_environment_path("XDG_STATE_HOME");
    if (output.data.empty()) output.data = home / ".local" / "share";
    if (output.config.empty()) output.config = home / ".config";
    if (output.cache.empty()) output.cache = home / ".cache";
    if (output.state.empty()) output.state = home / ".local" / "state";
    return facman::core::Result<UserPaths>::success(std::move(output));
}

} // namespace facman::platform
