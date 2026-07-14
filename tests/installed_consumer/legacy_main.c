// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_api_1_1.h"

int main(void)
{
    flb_context* context = 0;
    flb_config_v1 config = {0};
    config.struct_size = sizeof(config);
    if (flb_abi_version_v1() != 0x00010003u) return 1;
    if (flb_context_create_v1(&config, &context) != 0 || context == 0) return 2;
    flb_context_destroy_v1(context);
    return 0;
}
