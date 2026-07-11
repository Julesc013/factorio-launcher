// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_archive.h"

#include <chrono>
#include <filesystem>

int main(int argc, char** argv)
{
    facman::archive::Limits limits;
    limits.maximum_archive_bytes = 16 * 1024 * 1024;
    limits.maximum_entry_count = 256;
    limits.maximum_total_expanded_bytes = 32 * 1024 * 1024;
    limits.maximum_read_milliseconds = 2000;
    for (int index = 1; index < argc; ++index) {
        facman::archive::Plan plan;
        if (!facman::archive::inspect_archive(argv[index], limits, plan).ok()) continue;
        const std::filesystem::path staging = std::filesystem::temp_directory_path() /
            ("facman-archive-fuzz-" + std::to_string(index) + "-" +
             std::to_string(std::chrono::steady_clock::now().time_since_epoch().count()));
        (void)facman::archive::extract_to_new_owned_staging(plan, staging, limits);
        std::error_code error;
        std::filesystem::remove_all(staging, error);
    }
    return 0;
}
