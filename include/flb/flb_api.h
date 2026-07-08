#ifndef FLB_API_H
#define FLB_API_H

#include "ulk/ulk_command.h"
#include "ulk/ulk_types.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct flb_context flb_context;

typedef struct flb_config_v1 {
    ulk_size struct_size;
    ulk_string_view product_root;
    ulk_string_view workspace_root;
} flb_config_v1;

int flb_context_create_v1(
    const flb_config_v1* config,
    flb_context** out_context
);

int flb_command_execute_v1(
    flb_context* context,
    const ulk_command_request_v1* request,
    ulk_command_response_v1* response
);

void flb_context_destroy_v1(flb_context* context);

#ifdef __cplusplus
}
#endif

#endif
