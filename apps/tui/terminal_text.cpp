// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "terminal_text.hpp"

#include <algorithm>
#include <cstdint>
#include <string>
#include <vector>

namespace facman::tui {
namespace {

struct CodePoint {
    std::uint32_t value = 0xFFFDU;
    std::size_t bytes = 1U;
    bool valid = false;
};

struct Cluster {
    std::string text;
    std::size_t width = 0U;
};

bool continuation(unsigned char value) noexcept
{
    return (value & 0xC0U) == 0x80U;
}

CodePoint decode(const std::string& text, std::size_t offset) noexcept
{
    if (offset >= text.size()) return {};
    const auto first = static_cast<unsigned char>(text[offset]);
    if (first < 0x80U) return {first, 1U, true};
    if (first >= 0xC2U && first <= 0xDFU && offset + 1U < text.size()) {
        const auto second = static_cast<unsigned char>(text[offset + 1U]);
        if (continuation(second)) {
            return {static_cast<std::uint32_t>(((first & 0x1FU) << 6U) | (second & 0x3FU)), 2U, true};
        }
    }
    if (first >= 0xE0U && first <= 0xEFU && offset + 2U < text.size()) {
        const auto second = static_cast<unsigned char>(text[offset + 1U]);
        const auto third = static_cast<unsigned char>(text[offset + 2U]);
        const bool shortest = first != 0xE0U || second >= 0xA0U;
        const bool not_surrogate = first != 0xEDU || second < 0xA0U;
        if (continuation(second) && continuation(third) && shortest && not_surrogate) {
            return {static_cast<std::uint32_t>(((first & 0x0FU) << 12U) |
                ((second & 0x3FU) << 6U) | (third & 0x3FU)), 3U, true};
        }
    }
    if (first >= 0xF0U && first <= 0xF4U && offset + 3U < text.size()) {
        const auto second = static_cast<unsigned char>(text[offset + 1U]);
        const auto third = static_cast<unsigned char>(text[offset + 2U]);
        const auto fourth = static_cast<unsigned char>(text[offset + 3U]);
        const bool shortest = first != 0xF0U || second >= 0x90U;
        const bool bounded = first != 0xF4U || second <= 0x8FU;
        if (continuation(second) && continuation(third) && continuation(fourth) && shortest && bounded) {
            return {static_cast<std::uint32_t>(((first & 0x07U) << 18U) |
                ((second & 0x3FU) << 12U) | ((third & 0x3FU) << 6U) |
                (fourth & 0x3FU)), 4U, true};
        }
    }
    return {};
}

bool in_range(std::uint32_t value, std::uint32_t first, std::uint32_t last) noexcept
{
    return value >= first && value <= last;
}

bool is_combining(std::uint32_t value) noexcept
{
    return in_range(value, 0x0300U, 0x036FU) || in_range(value, 0x0483U, 0x0489U) ||
        in_range(value, 0x0591U, 0x05BDU) || in_range(value, 0x05BFU, 0x05BFU) ||
        in_range(value, 0x05C1U, 0x05C2U) || in_range(value, 0x0610U, 0x061AU) ||
        in_range(value, 0x064BU, 0x065FU) || in_range(value, 0x0670U, 0x0670U) ||
        in_range(value, 0x06D6U, 0x06EDU) || in_range(value, 0x0711U, 0x0711U) ||
        in_range(value, 0x0730U, 0x074AU) || in_range(value, 0x07A6U, 0x07B0U) ||
        in_range(value, 0x07EBU, 0x07F3U) || in_range(value, 0x0816U, 0x082DU) ||
        in_range(value, 0x0859U, 0x085BU) || in_range(value, 0x08D3U, 0x0902U) ||
        in_range(value, 0x093AU, 0x093CU) || in_range(value, 0x0941U, 0x0948U) ||
        in_range(value, 0x0951U, 0x0957U) || in_range(value, 0x0962U, 0x0963U) ||
        in_range(value, 0x1AB0U, 0x1AFFU) || in_range(value, 0x1DC0U, 0x1DFFU) ||
        in_range(value, 0x20D0U, 0x20FFU) || in_range(value, 0xFE20U, 0xFE2FU);
}

bool is_zero_width(std::uint32_t value) noexcept
{
    return value == 0x200BU || value == 0x200CU || value == 0x200DU ||
        value == 0x2060U || value == 0xFEFFU || in_range(value, 0xFE00U, 0xFE0FU) ||
        in_range(value, 0xE0100U, 0xE01EFU) || in_range(value, 0x1F3FBU, 0x1F3FFU) ||
        is_combining(value);
}

bool is_regional_indicator(std::uint32_t value) noexcept
{
    return in_range(value, 0x1F1E6U, 0x1F1FFU);
}

bool is_wide(std::uint32_t value) noexcept
{
    return value >= 0x1100U && (
        value <= 0x115FU || value == 0x2329U || value == 0x232AU ||
        in_range(value, 0x2E80U, 0x303EU) || in_range(value, 0x3040U, 0xA4CFU) ||
        in_range(value, 0xAC00U, 0xD7A3U) || in_range(value, 0xF900U, 0xFAFFU) ||
        in_range(value, 0xFE10U, 0xFE19U) || in_range(value, 0xFE30U, 0xFE6FU) ||
        in_range(value, 0xFF00U, 0xFF60U) || in_range(value, 0xFFE0U, 0xFFE6U) ||
        in_range(value, 0x1F000U, 0x1FAFFU) || in_range(value, 0x20000U, 0x3FFFDUL));
}

std::size_t code_point_width(std::uint32_t value) noexcept
{
    if (value == 0U || value < 0x20U || in_range(value, 0x7FU, 0x9FU) || is_zero_width(value)) return 0U;
    return is_wide(value) ? 2U : 1U;
}

bool is_control(std::uint32_t value) noexcept
{
    return value < 0x20U || in_range(value, 0x7FU, 0x9FU);
}

void append_code_point(Cluster& cluster, const std::string& source, std::size_t offset, const CodePoint& point)
{
    if (point.valid && !is_control(point.value)) cluster.text.append(source, offset, point.bytes);
    else if (point.valid) cluster.text += '?';
    else cluster.text += "\xEF\xBF\xBD";
}

Cluster next_cluster(const std::string& source, std::size_t& offset)
{
    Cluster cluster;
    bool joined = false;
    bool first_base = true;
    bool first_regional = false;
    while (offset < source.size()) {
        const CodePoint point = decode(source, offset);
        const bool extender = is_zero_width(point.value);
        const bool regional_pair = !first_base && first_regional && is_regional_indicator(point.value);
        if (!first_base && !joined && !extender && !regional_pair) break;
        append_code_point(cluster, source, offset, point);
        offset += point.bytes;
        if (point.value == 0xFE0FU || point.value == 0x20E3U) {
            cluster.width = std::max<std::size_t>(cluster.width, 2U);
        }
        if (point.value == 0x200DU) {
            joined = true;
            continue;
        }
        if (!extender) {
            const std::size_t width = is_control(point.value) ? 1U : code_point_width(point.value);
            cluster.width = std::max(cluster.width, width);
            if (first_base) first_regional = is_regional_indicator(point.value);
            first_base = false;
            joined = false;
            if (regional_pair) first_regional = false;
        }
    }
    return cluster;
}

std::vector<Cluster> clusters(const std::string& text)
{
    std::vector<Cluster> result;
    std::size_t offset = 0U;
    while (offset < text.size()) result.push_back(next_cluster(text, offset));
    return result;
}

} // namespace

std::size_t terminal_display_width(const std::string& text) noexcept
{
    std::size_t width = 0U;
    std::size_t offset = 0U;
    while (offset < text.size()) width += next_cluster(text, offset).width;
    return width;
}

std::string clip_terminal_text(const std::string& text, std::size_t width)
{
    if (width == 0U) return {};
    const auto values = clusters(text);
    std::size_t total = 0U;
    for (const auto& value : values) total += value.width;
    const bool clipped = total > width;
    const std::size_t available = clipped && width > 3U ? width - 3U : width;
    std::string result;
    std::size_t used = 0U;
    for (const auto& value : values) {
        if (used + value.width > available) break;
        result += value.text;
        used += value.width;
    }
    if (clipped && width > 3U) result += "...";
    return result;
}

} // namespace facman::tui
