#include "flb/flb_api.h"

#include "ulk/ulk_api.h"
#include "flb_factorio_application.h"

#include <stdlib.h>
#include <string.h>

struct flb_context {
    ulk_context* launcher_context;
    void* application;
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

static char* flb_copy_string(ulk_string_view value)
{
    char* copy;
    if (value.data == 0 || value.size == 0) {
        return 0;
    }
    copy = (char*)malloc((size_t)value.size + 1);
    if (copy == 0) {
        return 0;
    }
    memcpy(copy, value.data, (size_t)value.size);
    copy[value.size] = '\0';
    return copy;
}

static int flb_register_application_command(
    flb_context* context,
    const char* command_name,
    const char* effects,
    const char* response_schema,
    const char* dry_run_behavior)
{
    static const char request_schema[] = "contracts/schema/common/command_request.v1.schema.json";
    static const char result_schema[] = "contracts/result/result.v1.schema.json";
    static const char refusal_schema[] = "contracts/refusal/refusal.v1.schema.json";
    static const char availability[] = "available";
    static const char owner[] = "factorio-launcher";
    static const char binding[] = "flb.factorio";
    ulk_command_descriptor_v2 descriptor;
    memset(&descriptor, 0, sizeof(descriptor));
    descriptor.struct_size = sizeof(descriptor);
    descriptor.command_name.data = command_name;
    descriptor.command_name.size = (ulk_size)strlen(command_name);
    descriptor.effects_json.data = effects;
    descriptor.effects_json.size = (ulk_size)strlen(effects);
    descriptor.request_schema.data = request_schema;
    descriptor.request_schema.size = (ulk_size)strlen(request_schema);
    descriptor.response_schema.data = response_schema;
    descriptor.response_schema.size = (ulk_size)strlen(response_schema);
    descriptor.result_schema.data = result_schema;
    descriptor.result_schema.size = (ulk_size)strlen(result_schema);
    descriptor.refusal_schema.data = refusal_schema;
    descriptor.refusal_schema.size = (ulk_size)strlen(refusal_schema);
    descriptor.dry_run_behavior.data = dry_run_behavior;
    descriptor.dry_run_behavior.size = (ulk_size)strlen(dry_run_behavior);
    descriptor.availability.data = availability;
    descriptor.availability.size = (ulk_size)strlen(availability);
    descriptor.owner.data = owner;
    descriptor.owner.size = (ulk_size)strlen(owner);
    descriptor.binding.data = binding;
    descriptor.binding.size = (ulk_size)strlen(binding);
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
    if (config != 0 && config->struct_size < (ulk_size)sizeof(*config)) {
        *out_context = 0;
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
        char* workspace_root = config == 0 ? 0 : flb_copy_string(config->workspace_root);
        context->application = flb_factorio_application_create(workspace_root);
        free(workspace_root);
    }
    if (context->application == 0 ||
        flb_register_application_command(
            context,
            "install_refs.scan",
            "[\"workspace_read\"]",
            "contracts/schema/factorio/factorio_discovery_report.v1.schema.json",
            "read_only") != ULK_STATUS_OK ||
        flb_register_application_command(
            context,
            "install_refs.import",
            "[\"workspace_read\",\"workspace_write\"]",
            "contracts/schema/factorio/factorio_install_ref.v1.schema.json",
            "explicit_persistent_write") != ULK_STATUS_OK ||
        flb_register_application_command(
            context,
            "install_refs.inspect",
            "[\"workspace_read\"]",
            "contracts/schema/factorio/factorio_install_ref.v1.schema.json",
            "read_only") != ULK_STATUS_OK ||
        flb_register_application_command(
            context,
            "instance.create",
            "[\"workspace_read\",\"workspace_write\"]",
            "contracts/schema/factorio/factorio_instance.v1.schema.json",
            "explicit_persistent_write") != ULK_STATUS_OK ||
        flb_register_application_command(
            context,
            "launch_plan.build",
            "[\"workspace_read\"]",
            "contracts/schema/factorio/factorio_launch_plan.v1.schema.json",
            "preview_only") != ULK_STATUS_OK ||
        flb_register_application_command(
            context,
            "launch_plan.preflight",
            "[\"workspace_read\"]",
            "contracts/schema/factorio/factorio_launch_preflight.v1.schema.json",
            "read_only_no_process") != ULK_STATUS_OK ||
        flb_register_application_command(
            context,
            "run.preview",
            "[\"workspace_read\"]",
            "contracts/schema/factorio/factorio_launch_plan.v1.schema.json",
            "preview_only_no_process") != ULK_STATUS_OK ||
        flb_register_application_command(
            context,
            "mods.import",
            "[\"workspace_read\",\"workspace_write\"]",
            "contracts/schema/factorio/factorio_mod_ref.v1.schema.json",
            "explicit_persistent_write") != ULK_STATUS_OK ||
        flb_register_application_command(
            context,
            "modsets.lock",
            "[\"workspace_read\",\"workspace_write\"]",
            "contracts/schema/factorio/factorio_modset_lock.v1.schema.json",
            "explicit_persistent_write") != ULK_STATUS_OK ||
        flb_register_application_command(
            context,
            "modsets.verify",
            "[\"workspace_read\"]",
            "contracts/schema/factorio/factorio_modset_verify.v1.schema.json",
            "read_only") != ULK_STATUS_OK ||
        flb_register_application_command(
            context,
            "modsets.export",
            "[\"workspace_read\",\"workspace_write\"]",
            "contracts/schema/factorio/factorio_modset_export.v1.schema.json",
            "explicit_persistent_write") != ULK_STATUS_OK ||
        flb_register_application_command(
            context,
            "saves.list",
            "[\"workspace_read\"]",
            "contracts/schema/factorio/factorio_saves.v1.schema.json",
            "read_only") != ULK_STATUS_OK ||
        flb_register_application_command(
            context,
            "saves.backup",
            "[\"workspace_read\",\"workspace_write\"]",
            "contracts/schema/factorio/factorio_save_backup.v1.schema.json",
            "explicit_persistent_write") != ULK_STATUS_OK ||
        flb_register_application_command(
            context,
            "saves.clone",
            "[\"workspace_read\",\"workspace_write\"]",
            "contracts/schema/factorio/factorio_save_clone.v1.schema.json",
            "explicit_persistent_write") != ULK_STATUS_OK ||
        flb_register_application_command(
            context,
            "instance.export",
            "[\"workspace_read\",\"workspace_write\"]",
            "contracts/schema/factorio/factorio_instance_export.v1.schema.json",
            "explicit_persistent_write") != ULK_STATUS_OK ||
        flb_register_application_command(
            context,
            "instance.import",
            "[\"workspace_read\",\"workspace_write\"]",
            "contracts/schema/factorio/factorio_instance_import.v1.schema.json",
            "explicit_persistent_write") != ULK_STATUS_OK ||
        flb_register_application_command(
            context,
            "diagnostics.export",
            "[\"workspace_read\",\"workspace_write\"]",
            "contracts/schema/factorio/diagnostic_bundle_export.v1.schema.json",
            "explicit_persistent_write") != ULK_STATUS_OK ||
        flb_register_application_command(
            context,
            "workspace.recovery.inspect",
            "[\"workspace_read\"]",
            "contracts/schema/facman/facman_workspace_recovery.v1.schema.json",
            "read_only") != ULK_STATUS_OK ||
        flb_register_application_command(
            context,
            "workspace.recovery.plan",
            "[\"workspace_read\"]",
            "contracts/schema/facman/facman_workspace_recovery.v1.schema.json",
            "read_only") != ULK_STATUS_OK ||
        flb_register_application_command(
            context,
            "workspace.recovery.apply",
            "[\"workspace_read\",\"workspace_write\"]",
            "contracts/schema/facman/facman_workspace_recovery.v1.schema.json",
            "explicit_persistent_write") != ULK_STATUS_OK) {
        flb_factorio_application_destroy(context->application);
        ulk_context_destroy_v1(context->launcher_context);
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

    if (flb_string_equals(request->command_name, "product.inspect") ||
        flb_string_equals(request->command_name, "factorio.product.inspect")) {
        flb_set_response(response, ULK_STATUS_OK, product_payload, 0);
        return ULK_STATUS_OK;
    }

    return ulk_command_execute_v1(context->launcher_context, request, response);
}

uint32_t flb_abi_version_v1(void)
{
    return ((uint32_t)ULK_API_VERSION_MAJOR << 16) | (uint32_t)ULK_API_VERSION_MINOR;
}

void flb_context_destroy_v1(flb_context* context)
{
    if (context != 0) {
        flb_factorio_application_destroy(context->application);
        ulk_context_destroy_v1(context->launcher_context);
    }
    free(context);
}
