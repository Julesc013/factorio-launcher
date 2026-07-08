#include "flb/flb_api.h"

#include "ulk/ulk_api.h"

#include <stdlib.h>
#include <string.h>

struct flb_context {
    flb_config_v1 config;
    ulk_context* launcher_context;
};

static int flb_string_equals(ulk_string_view value, const char* expected)
{
    ulk_size index;
    ulk_size expected_size;

    if (value.data == 0 || expected == 0) {
        return 0;
    }

    expected_size = (ulk_size)strlen(expected);
    if (value.size != expected_size) {
        return 0;
    }

    for (index = 0; index < expected_size; ++index) {
        if (value.data[index] != expected[index]) {
            return 0;
        }
    }

    return 1;
}

static void flb_set_response(
    ulk_command_response_v1* response,
    int status,
    const char* payload,
    const char* error_message
)
{
    if (response == 0) {
        return;
    }

    memset(response, 0, sizeof(*response));
    response->struct_size = sizeof(*response);
    response->status = status;

    if (payload != 0) {
        response->json_payload.data = payload;
        response->json_payload.size = (ulk_size)strlen(payload);
    }

    response->error.struct_size = sizeof(response->error);
    response->error.code = status;
    if (error_message != 0) {
        response->error.message.data = error_message;
        response->error.message.size = (ulk_size)strlen(error_message);
    }
}

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
    if (ulk_context_create_v1(0, &context->launcher_context) != ULK_STATUS_OK) {
        free(context);
        *out_context = 0;
        return ULK_STATUS_ERROR;
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
    static const char product_payload[] =
        "{\"schema\":\"ulk.command_response.v1\",\"status\":\"ok\",\"payload\":{\"schema\":\"factorio.product.v1\",\"product_id\":\"factorio\",\"display_name\":\"Factorio\",\"public_name\":\"FacMan - unofficial launcher and isolated instance manager for Factorio\",\"binding_id\":\"flb.factorio\",\"unofficial\":true,\"capabilities\":[\"install_refs\",\"instances\",\"profiles\",\"artifact_sets\",\"launch_plans\",\"diagnostics\",\"mods\",\"saves\",\"servers\"],\"boundaries\":{\"bundles_factorio_binaries\":false,\"repairs_foreign_installs\":false,\"uninstalls_foreign_installs\":false,\"uses_official_branding\":false,\"default_run_mode\":\"dry-run\"}},\"error\":null}";
    static const char invalid_payload[] =
        "{\"schema\":\"ulk.command_response.v1\",\"status\":\"invalid_argument\",\"payload\":null,\"error\":{\"code\":\"invalid_argument\",\"message\":\"Factorio binding command request is invalid\"}}";
    static const char invalid_message[] = "Factorio binding command request is invalid";

    if (context == 0 ||
        request == 0 ||
        request->struct_size < (ulk_size)sizeof(*request) ||
        request->command_name.data == 0 ||
        request->command_name.size == 0) {
        flb_set_response(response, ULK_STATUS_INVALID_ARGUMENT, invalid_payload, invalid_message);
        return ULK_STATUS_INVALID_ARGUMENT;
    }

    if (flb_string_equals(request->command_name, "product.inspect") ||
        flb_string_equals(request->command_name, "factorio.product.inspect")) {
        flb_set_response(response, ULK_STATUS_OK, product_payload, 0);
        return ULK_STATUS_OK;
    }

    return ulk_command_execute_v1(context->launcher_context, request, response);
}

void flb_context_destroy_v1(flb_context* context)
{
    if (context != 0) {
        ulk_context_destroy_v1(context->launcher_context);
    }
    free(context);
}
