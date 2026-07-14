// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb/flb_api.h"

int main(void)
{
    flb_context* context = 0;
    flb_config_v1 config = {0};
    config.struct_size = sizeof(config);
    if (flb_abi_version_v1() != FLB_ABI_VERSION || FLB_ABI_VERSION != 0x00010003u) return 1;
    if (flb_required_ulk_abi_v1() != 0x00010003u) return 2;
    if (!flb_abi_is_compatible_v1(0x00010001u) ||
        !flb_abi_is_compatible_v1(0x00010002u) ||
        !flb_abi_is_compatible_v1(0x00010003u) ||
        flb_abi_is_compatible_v1(0x00010004u)) return 3;
    if (flb_context_create_v1(&config, &context) != 0 || context == 0) return 4;
    flb_context_destroy_v1(context);
    return 0;
}
