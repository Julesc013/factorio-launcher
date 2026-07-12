// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_PLATFORM_USER_PATHS_H
#define FACMAN_PLATFORM_USER_PATHS_H

#include "fl_result.h"

#include <filesystem>

namespace facman::platform {

struct UserPaths {
    std::filesystem::path home;
    std::filesystem::path data;
    std::filesystem::path config;
    std::filesystem::path cache;
    std::filesystem::path state;
};

facman::core::Result<UserPaths> user_paths();

} // namespace facman::platform

#endif
