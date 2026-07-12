// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_user_paths.h"

#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <knownfolders.h>
#include <shlobj.h>

namespace facman::platform {
namespace {

facman::core::Result<std::filesystem::path> known_folder(REFKNOWNFOLDERID id, const char* name)
{
    PWSTR value = nullptr;
    const HRESULT status = SHGetKnownFolderPath(id, KF_FLAG_DEFAULT, nullptr, &value);
    if (FAILED(status) || value == nullptr) {
        return facman::core::Result<std::filesystem::path>::failure(
            {"user_path_unavailable", std::string("Windows known folder is unavailable: ") + name, name});
    }
    std::filesystem::path path(value);
    CoTaskMemFree(value);
    if (!path.is_absolute()) {
        return facman::core::Result<std::filesystem::path>::failure(
            {"user_path_invalid", std::string("Windows known folder is not absolute: ") + name, name});
    }
    return facman::core::Result<std::filesystem::path>::success(path.lexically_normal());
}

} // namespace

facman::core::Result<UserPaths> user_paths()
{
    auto home = known_folder(FOLDERID_Profile, "profile");
    auto roaming = known_folder(FOLDERID_RoamingAppData, "roaming-app-data");
    auto local = known_folder(FOLDERID_LocalAppData, "local-app-data");
    if (!home || !roaming || !local) {
        const auto& problem = !home ? home.error() : !roaming ? roaming.error() : local.error();
        return facman::core::Result<UserPaths>::failure(problem);
    }
    UserPaths output;
    output.home = home.take_value();
    output.data = roaming.value();
    output.config = roaming.take_value();
    output.cache = local.value() / "Cache";
    output.state = local.take_value();
    return facman::core::Result<UserPaths>::success(std::move(output));
}

} // namespace facman::platform
