// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_client_c.h"
#include "flb/flb_api.h"

#include <cstddef>
#include <cstdint>
#include <type_traits>

static_assert(sizeof(ulk_size) == sizeof(std::uint64_t));
static_assert(std::is_standard_layout<ulk_string_view>::value);
static_assert(std::is_standard_layout<ulk_command_request_v1>::value);
static_assert(std::is_standard_layout<ulk_command_response_v1>::value);
static_assert(std::is_standard_layout<flb_config_v1>::value);
static_assert(offsetof(ulk_command_request_v1, struct_size) == 0);
static_assert(offsetof(ulk_command_response_v1, struct_size) == 0);
static_assert(offsetof(flb_config_v1, struct_size) == 0);
static_assert(sizeof(flb_config_v1) == sizeof(ulk_size) + 2 * sizeof(ulk_string_view));

int main()
{
    facman_client_initialize_process(nullptr);
    return flb_abi_version_v1() == 0x00010001u ? 0 : 1;
}
