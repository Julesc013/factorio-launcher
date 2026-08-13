// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_client_c.h"
#include "tui_host.h"

int main(int argc, char** argv)
{
    facman_client_initialize_process(argc > 0 ? argv[0] : nullptr);
    return facman_tui_run(argc, argv);
}
