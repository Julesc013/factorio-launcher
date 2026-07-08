#include "ulk/ulk_api.h"

#include <stdlib.h>
#include <string.h>

struct ulk_context {
    ulk_allocator_v1 allocator;
    int has_allocator;
};

static void* ulk_default_alloc(void* user, ulk_size size)
{
    (void)user;
    return malloc((size_t)size);
}

static void ulk_default_free(void* user, void* ptr)
{
    (void)user;
    free(ptr);
}

int ulk_context_create_v1(
    const ulk_allocator_v1* allocator,
    ulk_context** out_context
)
{
    ulk_context* context;
    ulk_allocator_v1 effective_allocator;

    if (out_context == 0) {
        return ULK_STATUS_INVALID_ARGUMENT;
    }

    effective_allocator.struct_size = sizeof(effective_allocator);
    effective_allocator.user = 0;
    effective_allocator.alloc = ulk_default_alloc;
    effective_allocator.free = ulk_default_free;

    if (allocator != 0 && allocator->alloc != 0 && allocator->free != 0) {
        effective_allocator = *allocator;
    }

    context = (ulk_context*)effective_allocator.alloc(effective_allocator.user, (ulk_size)sizeof(*context));
    if (context == 0) {
        *out_context = 0;
        return ULK_STATUS_ERROR;
    }

    memset(context, 0, sizeof(*context));
    context->allocator = effective_allocator;
    context->has_allocator = 1;
    *out_context = context;
    return ULK_STATUS_OK;
}

int ulk_command_execute_v1(
    ulk_context* context,
    const ulk_command_request_v1* request,
    ulk_command_response_v1* response
)
{
    static const char payload[] = "{\"status\":\"not_implemented\"}";
    static const char message[] = "native command graph is not implemented yet";

    (void)context;
    (void)request;

    if (response != 0) {
        memset(response, 0, sizeof(*response));
        response->struct_size = sizeof(*response);
        response->status = ULK_STATUS_UNSUPPORTED_VERSION;
        response->json_payload.data = payload;
        response->json_payload.size = (ulk_size)(sizeof(payload) - 1);
        response->error.struct_size = sizeof(response->error);
        response->error.code = ULK_STATUS_UNSUPPORTED_VERSION;
        response->error.message.data = message;
        response->error.message.size = (ulk_size)(sizeof(message) - 1);
    }

    return ULK_STATUS_UNSUPPORTED_VERSION;
}

void ulk_context_destroy_v1(ulk_context* context)
{
    ulk_allocator_v1 allocator;

    if (context == 0) {
        return;
    }

    allocator = context->allocator;
    if (context->has_allocator && allocator.free != 0) {
        allocator.free(allocator.user, context);
        return;
    }

    free(context);
}
