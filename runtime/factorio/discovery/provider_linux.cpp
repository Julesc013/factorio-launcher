// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "discovery_service.h"

namespace facman::factorio::discovery::internal {

void add_linux_provider_roots(std::vector<SearchRoot>& roots)
{
#if defined(__linux__)
    for (const auto& root : environment_paths("FACMAN_STANDALONE_ROOTS")) {
        append_search_root(roots, root, "linux.standalone.environment", "standalone", "foreign_owned", {"FACMAN_STANDALONE_ROOTS"});
    }
    if (defaults_disabled()) return;
    const auto home = home_directory();
    std::vector<std::filesystem::path> steam_roots;
    if (!home.empty()) {
        append_unique_path(steam_roots, home / ".local" / "share" / "Steam");
        append_unique_path(steam_roots, home / ".steam" / "steam");
        append_unique_path(steam_roots, home / ".var" / "app" / "com.valvesoftware.Steam" / "data" / "Steam");
        append_search_root(roots, home / "factorio", "linux.home", "standalone", "foreign_owned", {"bounded_default"});
    }
    for (const auto& steam : steam_roots) {
        for (const auto& library : steam_library_roots(steam)) {
            append_search_root(
                roots,
                library / "steamapps" / "common" / "Factorio",
                "linux.steam",
                "steam",
                "foreign_owned",
                {"libraryfolders.vdf", comparison_key(steam)});
        }
    }
    append_search_root(roots, "/opt/factorio", "linux.opt", "headless", "foreign_owned", {"bounded_default"});
#else
    (void)roots;
#endif
}

} // namespace facman::factorio::discovery::internal
