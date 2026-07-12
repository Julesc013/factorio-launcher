// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "discovery_service.h"

namespace facman::factorio::discovery::internal {

void add_macos_provider_roots(std::vector<SearchRoot>& roots)
{
#if defined(__APPLE__)
    for (const auto& root : environment_paths("FACMAN_STANDALONE_ROOTS")) {
        append_search_root(roots, root, "macos.standalone.environment", "app_bundle", "foreign_owned", {"FACMAN_STANDALONE_ROOTS"});
    }
    if (defaults_disabled()) return;
    const auto home = home_directory();
    if (!home.empty()) {
        append_search_root(roots, home / "Applications" / "Factorio.app", "macos.user-applications", "app_bundle", "foreign_owned", {"bounded_default"});
        const auto steam = home / "Library" / "Application Support" / "Steam";
        for (const auto& library : steam_library_roots(steam)) {
            append_search_root(
                roots,
                library / "steamapps" / "common" / "Factorio" / "Factorio.app",
                "macos.steam",
                "steam",
                "foreign_owned",
                {"libraryfolders.vdf", comparison_key(steam)});
        }
    }
    append_search_root(roots, "/Applications/Factorio.app", "macos.system-applications", "app_bundle", "foreign_owned", {"bounded_default"});
#else
    (void)roots;
#endif
}

} // namespace facman::factorio::discovery::internal
