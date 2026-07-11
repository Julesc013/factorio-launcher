// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "json_mode.h"

#include <string.h>

int flaunch_json_mode_enabled(int argc, char** argv)
{
    int i;
    for (i = 1; i < argc; ++i) {
        if (strcmp(argv[i], "--json") == 0) {
            return 1;
        }
    }
    return 0;
}
