// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb/flb_api.h"

#include "ulk/ulk_api.h"
#include "flb_factorio_application.h"
#include "command_catalog.h"
#include "fl_json_boundary_c.h"

#include <stdlib.h>
#include <string.h>

struct flb_context {
    ulk_context* launcher_context;
    void* application;
};

static void flb_set_response(
    ulk_command_response_v1* response,
    int status,
    const char* payload,
    const char* error_message
)
{
    response->status = 0;
    response->json_payload.data = 0;
    response->json_payload.size = 0;
    memset(&response->error, 0, sizeof(response->error));
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

static int flb_copy_string(ulk_string_view value, char** out_copy)
{
    char* copy;
    if (out_copy == 0) {
        return ULK_STATUS_INVALID_ARGUMENT;
    }
    *out_copy = 0;
    if (value.size == 0) {
        return ULK_STATUS_OK;
    }
    if (value.data == 0 || value.size > (ulk_size)(SIZE_MAX - 1u)) {
        return ULK_STATUS_INVALID_ARGUMENT;
    }
    copy = (char*)malloc((size_t)value.size + 1);
    if (copy == 0) {
        return ULK_STATUS_ERROR;
    }
    memcpy(copy, value.data, (size_t)value.size);
    copy[value.size] = '\0';
    *out_copy = copy;
    return ULK_STATUS_OK;
}

static int flb_register_application_command(
    flb_context* context,
    const facman_generated_command_descriptor* generated)
{
    const char* availability = generated->availability;
    ulk_command_descriptor_v2 descriptor;
#if !FACMAN_WITH_SETUP
    if (strncmp(generated->command_name, "setup.", 6) == 0 && strcmp(availability, "available") == 0) {
        availability = "disabled_by_build";
    }
#endif
    memset(&descriptor, 0, sizeof(descriptor));
    descriptor.struct_size = sizeof(descriptor);
    descriptor.command_name.data = generated->command_name;
    descriptor.command_name.size = (ulk_size)strlen(generated->command_name);
    descriptor.effects_json.data = generated->effects_json;
    descriptor.effects_json.size = (ulk_size)strlen(generated->effects_json);
    descriptor.request_schema.data = generated->request_schema;
    descriptor.request_schema.size = (ulk_size)strlen(generated->request_schema);
    descriptor.response_schema.data = generated->response_schema;
    descriptor.response_schema.size = (ulk_size)strlen(generated->response_schema);
    descriptor.result_schema.data = generated->result_schema;
    descriptor.result_schema.size = (ulk_size)strlen(generated->result_schema);
    descriptor.refusal_schema.data = generated->refusal_schema;
    descriptor.refusal_schema.size = (ulk_size)strlen(generated->refusal_schema);
    descriptor.dry_run_behavior.data = generated->dry_run_behavior;
    descriptor.dry_run_behavior.size = (ulk_size)strlen(generated->dry_run_behavior);
    descriptor.availability.data = availability;
    descriptor.availability.size = (ulk_size)strlen(availability);
    descriptor.owner.data = generated->owner;
    descriptor.owner.size = (ulk_size)strlen(generated->owner);
    descriptor.binding.data = generated->binding;
    descriptor.binding.size = (ulk_size)strlen(generated->binding);
    descriptor.user = context->application;
    descriptor.handler = flb_factorio_application_handle_v1;
    return ulk_command_register_v2(context->launcher_context, &descriptor);
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
    *out_context = 0;
    if (config != 0 && config->struct_size < (ulk_size)sizeof(*config)) {
        return ULK_STATUS_INVALID_ARGUMENT;
    }
    if (config != 0 && (config->product_root.data != 0 || config->product_root.size != 0)) {
        return ULK_STATUS_INVALID_ARGUMENT;
    }
    if (config != 0 && config->workspace_root.size != 0 && config->workspace_root.data == 0) {
        return ULK_STATUS_INVALID_ARGUMENT;
    }

    context = (flb_context*)malloc(sizeof(*context));
    if (context == 0) {
        *out_context = 0;
        return ULK_STATUS_ERROR;
    }

    memset(context, 0, sizeof(*context));
    if (ulk_context_create_v1(0, &context->launcher_context) != ULK_STATUS_OK) {
        free(context);
        *out_context = 0;
        return ULK_STATUS_ERROR;
    }
    {
        char* workspace_root = 0;
        const int copy_status = config == 0
            ? ULK_STATUS_OK
            : flb_copy_string(config->workspace_root, &workspace_root);
        if (copy_status != ULK_STATUS_OK) {
            ulk_context_destroy_v1(context->launcher_context);
            free(context);
            return copy_status;
        }
        context->application = flb_factorio_application_create(workspace_root);
        free(workspace_root);
    }
    if (context->application != 0) {
        size_t command_index;
        for (command_index = 0;
             command_index < FACMAN_GENERATED_REGISTERED_COMMAND_COUNT;
             ++command_index) {
            const facman_generated_command_descriptor* descriptor =
                &facman_generated_registered_commands[command_index];
            if (flb_register_application_command(context, descriptor) != ULK_STATUS_OK) {
                break;
            }
        }
        if (command_index == FACMAN_GENERATED_REGISTERED_COMMAND_COUNT) {
            *out_context = context;
            return ULK_STATUS_OK;
        }
    }
    {
        flb_factorio_application_destroy(context->application);
        ulk_context_destroy_v1(context->launcher_context);
        free(context);
        *out_context = 0;
        return ULK_STATUS_ERROR;
    }
}

int flb_command_execute_v1(
    flb_context* context,
    const ulk_command_request_v1* request,
    ulk_command_response_v1* response
)
{
    static const char invalid_payload[] = FACMAN_JSON_BOUNDARY_INVALID_REQUEST;
    static const char invalid_message[] = "Factorio binding command request is invalid";

    if (response == 0 || response->struct_size < (ulk_size)sizeof(*response)) {
        return ULK_STATUS_INVALID_ARGUMENT;
    }
    if (context == 0 ||
        request == 0 ||
        request->struct_size < (ulk_size)sizeof(*request) ||
        request->command_name.data == 0 ||
        request->command_name.size == 0) {
        flb_set_response(response, ULK_STATUS_INVALID_ARGUMENT, invalid_payload, invalid_message);
        return ULK_STATUS_INVALID_ARGUMENT;
    }

    return ulk_command_execute_v1(context->launcher_context, request, response);
}

uint32_t flb_abi_version_v1(void)
{
    return (uint32_t)FLB_ABI_VERSION;
}

uint32_t flb_required_ulk_abi_v1(void)
{
    return ((uint32_t)ULK_API_VERSION_MAJOR << 16) | (uint32_t)ULK_API_VERSION_MINOR;
}

int flb_abi_is_compatible_v1(uint32_t requested_abi)
{
    const uint32_t requested_major = requested_abi >> 16;
    const uint32_t requested_minor = requested_abi & 0xffffu;
    return requested_major == (uint32_t)FLB_ABI_VERSION_MAJOR &&
        requested_minor <= (uint32_t)FLB_ABI_VERSION_MINOR;
}

void flb_context_destroy_v1(flb_context* context)
{
    if (context != 0) {
        flb_factorio_application_destroy(context->application);
        ulk_context_destroy_v1(context->launcher_context);
    }
    free(context);
}
