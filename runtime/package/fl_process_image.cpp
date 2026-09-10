// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "fl_process_image.h"
#include <array>
#ifdef _WIN32
#include <windows.h>
#elif defined(__APPLE__)
#include <mach-o/dyld.h>
#else
#include <unistd.h>
#endif
namespace facman::package {
facman::core::Result<std::filesystem::path> process_image()
{
    using Output = facman::core::Result<std::filesystem::path>;
    std::filesystem::path path;
#ifdef _WIN32
    std::array<wchar_t, 32768> buffer {};
    const DWORD count = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (count > 0 && count < buffer.size()) path = std::wstring(buffer.data(), count);
#elif defined(__APPLE__)
    std::array<char, 65536> buffer {};
    std::uint32_t size = static_cast<std::uint32_t>(buffer.size());
    if (_NSGetExecutablePath(buffer.data(), &size) == 0) path = buffer.data();
#else
    std::array<char, 65536> buffer {};
    const auto count = readlink("/proc/self/exe", buffer.data(), buffer.size());
    if (count > 0 && static_cast<std::size_t>(count) < buffer.size())
        path = std::string(buffer.data(), static_cast<std::size_t>(count));
#endif
    std::error_code error;
    if (!path.empty()) path = std::filesystem::canonical(path, error);
    if (path.empty() || error)
        return Output::failure({"resource_process_image_unavailable", "Cannot resolve the running process image", "$", facman::core::OutcomeKind::unavailable});
    return Output::success(std::move(path));
}
}
