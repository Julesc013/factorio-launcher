// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_archive.h"

int main(int argc, char** argv)
{
    facman::archive::Limits limits;
    limits.maximum_archive_bytes = 16 * 1024 * 1024;
    limits.maximum_entry_count = 256;
    limits.maximum_total_expanded_bytes = 32 * 1024 * 1024;
    limits.maximum_read_milliseconds = 2000;
    for (int index = 1; index < argc; ++index) {
        facman::archive::Plan plan;
        (void)facman::archive::inspect_archive(argv[index], limits, plan);
    }
    return 0;
}
