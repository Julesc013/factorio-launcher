// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "fl_json.h"
namespace facman::core::json {
namespace {
void escaped_unit(std::string& output, std::uint32_t value)
{
    static constexpr char hex[] = "0123456789abcdef";
    output += "\\u";
    for (int shift = 12; shift >= 0; shift -= 4)
        output.push_back(hex[(value >> shift) & 15U]);
}
}
Result<std::string> canonical_integer_ascii_json(const Value& value)
{
    auto canonical = canonical_integer_json(value);
    if (!canonical) return canonical;
    // Parsed values contain strict UTF-8. Canonical JSON can contain non-ASCII
    // bytes only inside a quoted string; escape those scalar values without
    // changing the ordinary canonical JSON contract used by other consumers.
    const auto& input = canonical.value(); std::string output;
    for (std::size_t index = 0; index < input.size();) {
        const auto first = static_cast<unsigned char>(input[index++]);
        if (first < 127U) { output.push_back(static_cast<char>(first)); continue; }
        std::uint32_t scalar = first;
        if (first >= 128U) {
            const unsigned count = first < 0xe0U ? 1U : first < 0xf0U ? 2U : 3U;
            scalar = first & ((1U << (6U - count)) - 1U);
            for (unsigned byte = 0; byte < count; ++byte)
                scalar = (scalar << 6U) | (static_cast<unsigned char>(input[index++]) & 63U);
        }
        if (scalar <= 0xffffU) escaped_unit(output, scalar);
        else {
            scalar -= 0x10000U;
            escaped_unit(output, 0xd800U + (scalar >> 10U));
            escaped_unit(output, 0xdc00U + (scalar & 1023U));
        }
    }
    return Result<std::string>::success(std::move(output));
}
}
