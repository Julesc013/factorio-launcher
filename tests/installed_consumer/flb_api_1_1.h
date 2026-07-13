// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_TEST_FLB_API_1_1_H
#define FACMAN_TEST_FLB_API_1_1_H

#include "ulk/ulk_command.h"
#include "ulk/ulk_types.h"

#if defined(_WIN32)
#define FLB_1_1_API __declspec(dllimport)
#else
#define FLB_1_1_API
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef struct flb_context flb_context;

typedef struct flb_config_v1 {
    ulk_size struct_size;
    ulk_string_view product_root;
    ulk_string_view workspace_root;
} flb_config_v1;

FLB_1_1_API int ULK_CALL flb_context_create_v1(
    const flb_config_v1* config,
    flb_context** out_context
);
FLB_1_1_API int ULK_CALL flb_command_execute_v1(
    flb_context* context,
    const ulk_command_request_v1* request,
    ulk_command_response_v1* response
);
FLB_1_1_API uint32_t ULK_CALL flb_abi_version_v1(void);
FLB_1_1_API void ULK_CALL flb_context_destroy_v1(flb_context* context);

#ifdef __cplusplus
}
#endif

#endif
