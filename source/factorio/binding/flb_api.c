#include "flb/flb_api.h"

#include <stdlib.h>
#include <string.h>

struct flb_context {
    flb_config_v1 config;
};

int flb_context_create_v1(
    const flb_config_v1* config,
    flb_context** out_context
)
{
    flb_context* context;

    if (out_context == 0) {
        return ULK_STATUS_INVALID_ARGUMENT;
    }

    context = (flb_context*)malloc(sizeof(*context));
    if (context == 0) {
        *out_context = 0;
        return ULK_STATUS_ERROR;
    }

    memset(context, 0, sizeof(*context));
    if (config != 0) {
        context->config = *config;
    }
    *out_context = context;
    return ULK_STATUS_OK;
}

int flb_command_execute_v1(
    flb_context* context,
    const ulk_command_request_v1* request,
    ulk_command_response_v1* response
)
{
    static const char payload[] = "{\"binding\":\"factorio\",\"status\":\"not_implemented\"}";
    static const char message[] = "Factorio binding command handlers are not implemented yet";

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

void flb_context_destroy_v1(flb_context* context)
{
    free(context);
}
