// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_json.h"

#include <fstream>
#include <iterator>
#include <string>

int main(int argc, char** argv)
{
    facman::core::json::Limits limits;
    limits.maximum_bytes = 1024U * 1024U;
    limits.maximum_depth = 64;
    limits.maximum_nodes = 100000;
    limits.maximum_string_bytes = 512U * 1024U;
    for (int index = 1; index < argc; ++index) {
        std::ifstream input(argv[index], std::ios::binary);
        std::string text {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
        auto value = facman::core::json::parse(text, limits);
        if (value) {
            const std::string serialized = value.value().serialize();
            (void)facman::core::json::parse(serialized, limits);
        }
    }
    return 0;
}
