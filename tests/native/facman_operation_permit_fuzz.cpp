// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_operation_permit_fuzz_common.h"

#include <fstream>
#include <iterator>
#include <string>

int main(int argc, char** argv)
{
    for (int index = 1; index < argc; ++index) {
        std::ifstream input(argv[index], std::ios::binary);
        input.seekg(0, std::ios::end);
        const std::streamoff size = input.tellg();
        if (size < 0 || size > static_cast<std::streamoff>(1024U * 1024U)) continue;
        input.seekg(0, std::ios::beg);
        std::string text {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
        facman_fuzz_operation_permit(
            reinterpret_cast<const std::uint8_t*>(text.data()), text.size());
    }
    return 0;
}
