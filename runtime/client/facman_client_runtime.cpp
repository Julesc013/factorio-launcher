// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_client_c.h"

#include "fl_runtime_verify.h"

extern "C" void facman_client_initialize_process(const char* executable_path)
{
    fl_runtime_set_executable_path(executable_path);
}
