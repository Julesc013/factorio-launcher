#ifndef ULK_API_H
#define ULK_API_H

#include "ulk_allocator.h"
#include "ulk_command.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct ulk_context ulk_context;

int ulk_context_create_v1(
    const ulk_allocator_v1* allocator,
    ulk_context** out_context
);

int ulk_command_execute_v1(
    ulk_context* context,
    const ulk_command_request_v1* request,
    ulk_command_response_v1* response
);

void ulk_context_destroy_v1(ulk_context* context);

#ifdef __cplusplus
}
#endif

#endif
