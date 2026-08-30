// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_VERSION_FAMILY_H
#define FLB_FACTORIO_VERSION_FAMILY_H

#include <cstdint>
#include <string>
#include <string_view>

namespace facman::factorio::version {

enum class VersionFamily {
    f100,
    f110,
    f200,
    f210,
    outside_target,
    invalid,
};

struct ParsedVersion {
    std::uint32_t major = 0;
    std::uint32_t minor = 0;
    std::uint32_t patch = 0;
    bool has_patch = false;
};

struct VersionClassification {
    VersionFamily family = VersionFamily::invalid;
    ParsedVersion version;
    bool valid = false;
};

bool parse(std::string_view text, ParsedVersion& output);
VersionClassification classify(std::string_view text);
const char* family_id(VersionFamily family);
const char* classification_status(VersionFamily family);
bool is_target_family(VersionFamily family);
std::string version_line(const ParsedVersion& version);
std::string normalized_version(const ParsedVersion& version);

} // namespace facman::factorio::version

#endif
