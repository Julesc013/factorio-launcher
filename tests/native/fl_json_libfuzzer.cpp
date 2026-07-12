// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_json.h"

#include <cstddef>
#include <cstdint>
#include <string>

extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t* data, std::size_t size)
{
    if (size > 1024U * 1024U) return 0;
    facman::core::json::Limits limits;
    limits.maximum_bytes = 1024U * 1024U;
    limits.maximum_depth = 64;
    limits.maximum_nodes = 100000;
    limits.maximum_string_bytes = 512U * 1024U;
    const std::string text(reinterpret_cast<const char*>(data), size);
    auto value = facman::core::json::parse(text, limits);
    if (value) {
        const std::string serialized = value.value().serialize();
        (void)facman::core::json::parse(serialized, limits);
    }
    return 0;
}
