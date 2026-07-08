#ifndef UL_API_H
#define UL_API_H

#include "ul_allocator.h"
#include "ul_command.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct ul_context ul_context;

int ul_create_context_v1(
    const ul_allocator_v1* allocator,
    ul_context** out_context
);

int ul_execute_command_v1(
    ul_context* context,
    const ul_command_request_v1* request,
    ul_command_response_v1* response
);

void ul_destroy_context_v1(ul_context* context);

#ifdef __cplusplus
}
#endif

#endif

