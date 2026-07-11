// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "command_dispatch.h"
#include "facman_client_c.h"

int main(int argc, char** argv)
{
    facman_client_initialize_process(argc > 0 ? argv[0] : 0);
    return flaunch_dispatch_command(argc, argv);
}
