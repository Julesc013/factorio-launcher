// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "discovery_service.h"

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

namespace facman::factorio::discovery::internal {
namespace fs = std::filesystem;

#ifdef _WIN32
namespace {
fs::path registry_path(HKEY root, const wchar_t* subkey, const wchar_t* name)
{
    DWORD type = 0;
    DWORD bytes = 0;
    if (RegGetValueW(root, subkey, name, RRF_RT_REG_SZ, &type, nullptr, &bytes) != ERROR_SUCCESS || bytes < 2U) return {};
    std::wstring value(bytes / sizeof(wchar_t), L'\0');
    if (RegGetValueW(root, subkey, name, RRF_RT_REG_SZ, &type, value.data(), &bytes) != ERROR_SUCCESS) return {};
    while (!value.empty() && value.back() == L'\0') value.pop_back();
    return fs::path(value);
}

fs::path environment_path(const wchar_t* name)
{
    const wchar_t* value = _wgetenv(name);
    return value == nullptr || *value == L'\0' ? fs::path() : fs::path(value);
}
}
#endif

void add_windows_provider_roots(std::vector<SearchRoot>& roots)
{
#ifdef _WIN32
    std::vector<fs::path> steam_roots = environment_paths("FACMAN_STEAM_ROOTS");
    for (const auto& root : environment_paths("FACMAN_STANDALONE_ROOTS")) {
        append_search_root(roots, root, "windows.standalone.environment", "standalone", "foreign_owned", {"FACMAN_STANDALONE_ROOTS"});
    }
    if (!defaults_disabled()) {
        append_unique_path(steam_roots, registry_path(HKEY_CURRENT_USER, L"Software\\Valve\\Steam", L"SteamPath"));
        append_unique_path(steam_roots, registry_path(HKEY_LOCAL_MACHINE, L"SOFTWARE\\WOW6432Node\\Valve\\Steam", L"InstallPath"));
        const fs::path program_files_x86 = environment_path(L"ProgramFiles(x86)");
        const fs::path program_files = environment_path(L"ProgramFiles");
        const fs::path local_app_data = environment_path(L"LOCALAPPDATA");
        if (!program_files_x86.empty()) append_unique_path(steam_roots, program_files_x86 / "Steam");
        if (!program_files.empty()) append_search_root(roots, program_files / "Factorio", "windows.program-files", "standalone", "foreign_owned", {"bounded_default"});
        if (!local_app_data.empty()) append_search_root(roots, local_app_data / "Programs" / "Factorio", "windows.local-app-data", "standalone", "foreign_owned", {"bounded_default"});
    }
    for (const auto& steam : steam_roots) {
        for (const auto& library : steam_library_roots(steam)) {
            append_search_root(
                roots,
                library / "steamapps" / "common" / "Factorio",
                "windows.steam",
                "steam",
                "foreign_owned",
                {"libraryfolders.vdf", comparison_key(steam)});
        }
    }
#else
    (void)roots;
#endif
}

} // namespace facman::factorio::discovery::internal
