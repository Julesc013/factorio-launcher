// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#ifndef FACMAN_PLATFORM_RETAINED_REWRITE_STATE_H
#define FACMAN_PLATFORM_RETAINED_REWRITE_STATE_H
#include <algorithm>
#include <cstddef>
#include <string>
namespace facman::platform::detail {
// Object/parent/context custody is a separate
// prerequisite; this predicate cannot grant write or recovery authority.
// Recognize the initial bytes, a prefix write at offset zero with the original
// suffix retained, an extension, or the final exact truncation. Unknown bytes
// and other lengths must remain untouched. Process loss, not power loss.
inline bool retained_rewrite_bytes_admissible(const std::string& original,
    const std::string& intended, const std::string& observed)
{
    constexpr std::size_t maximum = 64U * 1024U;
    if (original.empty() || intended.empty() || original.size() > maximum ||
        intended.size() > maximum || observed.size() > maximum) return false;
    if (observed == original || observed == intended) return true;
    if (observed.size() > original.size()) {
        return observed.size() <= intended.size() &&
            intended.compare(0, observed.size(), observed) == 0;
    }
    if (observed.size() != original.size()) return false;
    const std::size_t limit = std::min(intended.size(), observed.size());
    std::size_t prefix = 0;
    while (prefix < limit && observed[prefix] == intended[prefix]) ++prefix;
    std::size_t suffix = observed.size();
    while (suffix > 0 && observed[suffix-1] == original[suffix-1]) --suffix;
    return suffix <= prefix;
}
}
#endif
