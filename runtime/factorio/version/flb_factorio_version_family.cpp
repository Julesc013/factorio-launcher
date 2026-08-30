// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_version_family.h"

#include <limits>

namespace facman::factorio::version {
namespace {

bool component(std::string_view text, std::size_t& cursor, std::uint32_t& output)
{
    if (cursor >= text.size()) return false;
    const std::size_t start = cursor;
    if (text[cursor] == '0' && cursor + 1U < text.size() && text[cursor + 1U] != '.') {
        return false;
    }
    std::uint64_t value = 0;
    while (cursor < text.size() && text[cursor] >= '0' && text[cursor] <= '9') {
        const unsigned digit = static_cast<unsigned>(text[cursor] - '0');
        if (value > (std::numeric_limits<std::uint32_t>::max() - digit) / 10U) return false;
        value = value * 10U + digit;
        ++cursor;
    }
    if (cursor == start) return false;
    output = static_cast<std::uint32_t>(value);
    return true;
}

VersionFamily family_for(const ParsedVersion& value)
{
    if (value.major == 1U && value.minor == 0U) return VersionFamily::f100;
    if (value.major == 1U && value.minor == 1U) return VersionFamily::f110;
    if (value.major == 2U && value.minor == 0U) return VersionFamily::f200;
    if (value.major == 2U && value.minor == 1U) return VersionFamily::f210;
    return VersionFamily::outside_target;
}

} // namespace

bool parse(std::string_view text, ParsedVersion& output)
{
    ParsedVersion candidate;
    std::size_t cursor = 0;
    if (!component(text, cursor, candidate.major) || cursor >= text.size() || text[cursor] != '.') {
        return false;
    }
    ++cursor;
    if (!component(text, cursor, candidate.minor)) return false;
    if (cursor == text.size()) {
        output = candidate;
        return true;
    }
    if (text[cursor] != '.') return false;
    ++cursor;
    if (!component(text, cursor, candidate.patch) || cursor != text.size()) return false;
    candidate.has_patch = true;
    output = candidate;
    return true;
}

VersionClassification classify(std::string_view text)
{
    ParsedVersion parsed;
    if (!parse(text, parsed)) return {};
    return {family_for(parsed), parsed, true};
}

const char* family_id(VersionFamily family)
{
    switch (family) {
    case VersionFamily::f100: return "F100";
    case VersionFamily::f110: return "F110";
    case VersionFamily::f200: return "F200";
    case VersionFamily::f210: return "F210";
    case VersionFamily::outside_target:
    case VersionFamily::invalid: return nullptr;
    }
    return nullptr;
}

const char* classification_status(VersionFamily family)
{
    switch (family) {
    case VersionFamily::f100:
    case VersionFamily::f110:
    case VersionFamily::f200:
    case VersionFamily::f210: return "eligible";
    case VersionFamily::outside_target: return "outside";
    case VersionFamily::invalid: return "invalid";
    }
    return "invalid";
}

bool is_target_family(VersionFamily family)
{
    return family == VersionFamily::f100 || family == VersionFamily::f110 ||
        family == VersionFamily::f200 || family == VersionFamily::f210;
}

std::string version_line(const ParsedVersion& version)
{
    return std::to_string(version.major) + "." + std::to_string(version.minor) + ".x";
}

std::string normalized_version(const ParsedVersion& version)
{
    std::string output = std::to_string(version.major) + "." + std::to_string(version.minor);
    if (version.has_patch) output += "." + std::to_string(version.patch);
    return output;
}

} // namespace facman::factorio::version
