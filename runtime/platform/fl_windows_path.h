// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_PLATFORM_WINDOWS_PATH_H
#define FACMAN_PLATFORM_WINDOWS_PATH_H

#ifdef _WIN32

#include <filesystem>
#include <string>
#include <system_error>

namespace facman::platform {

// Win32 path-taking APIs retain the legacy MAX_PATH limit unless an absolute
// extended-length path is supplied. Keep this conversion at the native API
// boundary so the higher-level ownership and no-follow checks continue to use
// ordinary std::filesystem paths.
inline std::wstring windows_extended_path(const std::filesystem::path& input)
{
    std::error_code error;
    std::filesystem::path absolute = input.is_absolute()
        ? input
        : std::filesystem::absolute(input, error);
    if (error) return input.native();

    std::wstring value = absolute.lexically_normal().native();
    if (value.rfind(L"\\\\?\\", 0) == 0 || value.rfind(L"\\\\.\\", 0) == 0) {
        return value;
    }
    if (value.rfind(L"\\\\", 0) == 0) {
        return L"\\\\?\\UNC\\" + value.substr(2);
    }
    return L"\\\\?\\" + value;
}

} // namespace facman::platform

#endif

#endif
