// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_archive.h"

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <system_error>

extern "C" int LLVMFuzzerTestOneInput(const std::uint8_t* data, std::size_t size)
{
    if (size > 1024 * 1024) return 0;
    const std::filesystem::path input =
        std::filesystem::temp_directory_path() / "facman-libfuzzer-input.zip";
    {
        std::ofstream stream(input, std::ios::binary | std::ios::trunc);
        stream.write(reinterpret_cast<const char*>(data), static_cast<std::streamsize>(size));
    }
    facman::archive::Limits limits;
    limits.maximum_archive_bytes = 1024 * 1024;
    limits.maximum_entry_count = 128;
    limits.maximum_total_expanded_bytes = 4 * 1024 * 1024;
    limits.maximum_read_milliseconds = 250;
    facman::archive::Plan plan;
    (void)facman::archive::inspect_archive(input, limits, plan);
    std::error_code error;
    std::filesystem::remove(input, error);
    return 0;
}
