// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_API_H
#define FLB_API_H

#include "ulk/ulk_command.h"
#include "ulk/ulk_types.h"

#if defined(_WIN32) && defined(FLB_BUILD_SHARED)
#define FLB_API __declspec(dllexport)
#elif defined(_WIN32) && defined(FLB_USE_SHARED)
#define FLB_API __declspec(dllimport)
#elif defined(__GNUC__) && defined(FLB_BUILD_SHARED)
#define FLB_API __attribute__((visibility("default")))
#else
#define FLB_API
#endif
#define FLB_CALL ULK_CALL

#ifdef __cplusplus
extern "C" {
#endif

typedef struct flb_context flb_context;

#define FLB_ABI_VERSION_MAJOR 1u
#define FLB_ABI_VERSION_MINOR 3u
#define FLB_ABI_VERSION ((FLB_ABI_VERSION_MAJOR << 16) | FLB_ABI_VERSION_MINOR)

typedef struct flb_config_v1 {
    ulk_size struct_size;
    /* Reserved for a future product-content root. V1 callers must pass {0, 0}. */
    ulk_string_view product_root;
    ulk_string_view workspace_root;
} flb_config_v1;

FLB_API int FLB_CALL flb_context_create_v1(
    const flb_config_v1* config,
    flb_context** out_context
);

FLB_API int FLB_CALL flb_command_execute_v1(
    flb_context* context,
    const ulk_command_request_v1* request,
    ulk_command_response_v1* response
);

FLB_API uint32_t FLB_CALL flb_abi_version_v1(void);

FLB_API uint32_t FLB_CALL flb_required_ulk_abi_v1(void);

FLB_API int FLB_CALL flb_abi_is_compatible_v1(uint32_t requested_abi);

FLB_API void FLB_CALL flb_context_destroy_v1(flb_context* context);

#ifdef __cplusplus
}
#endif

#endif
