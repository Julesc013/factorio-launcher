// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "discovery_service.h"

namespace facman::factorio::discovery::internal {

void add_explicit_provider_roots(
    std::vector<SearchRoot>& roots,
    const std::vector<std::filesystem::path>& explicit_roots)
{
    for (const auto& root : explicit_roots) {
        append_search_root(roots, root, "explicit.argument", "explicit", "imported", {"explicit_argument"});
    }
    for (const auto& root : environment_paths("FACMAN_DISCOVERY_ROOTS")) {
        append_search_root(roots, root, "explicit.environment", "explicit", "imported", {"FACMAN_DISCOVERY_ROOTS"});
    }
}

} // namespace facman::factorio::discovery::internal
