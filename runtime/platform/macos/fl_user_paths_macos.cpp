// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_user_paths.h"

#include <cstdlib>

namespace facman::platform {

facman::core::Result<UserPaths> user_paths()
{
    const char* value = std::getenv("HOME");
    const std::filesystem::path home = value == nullptr ? std::filesystem::path {} : std::filesystem::path(value);
    if (home.empty() || !home.is_absolute()) {
        return facman::core::Result<UserPaths>::failure(
            {"user_path_unavailable", "HOME is missing or is not absolute", "HOME"});
    }
    UserPaths output;
    output.home = home.lexically_normal();
    output.data = output.home / "Library" / "Application Support";
    output.config = output.data;
    output.cache = output.home / "Library" / "Caches";
    output.state = output.data;
    return facman::core::Result<UserPaths>::success(std::move(output));
}

} // namespace facman::platform
