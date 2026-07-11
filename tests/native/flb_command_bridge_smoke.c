#include "fl_command_client_cabi.h"

#include <string.h>

static ulk_string_view view_from_cstr(const char* text)
{
    ulk_string_view view;
    view.data = text;
    view.size = (ulk_size)strlen(text);
    return view;
}

static int contains(ulk_string_view haystack, const char* needle)
{
    ulk_size index;
    ulk_size needle_size;

    if (haystack.data == 0 || needle == 0) {
        return 0;
    }

    needle_size = (ulk_size)strlen(needle);
    if (needle_size == 0 || needle_size > haystack.size) {
        return 0;
    }

    for (index = 0; index + needle_size <= haystack.size; ++index) {
        if (memcmp(haystack.data + index, needle, (size_t)needle_size) == 0) {
            return 1;
        }
    }

    return 0;
}

static int run_command(
    flb_context* context,
    const char* command_name,
    int dry_run,
    const char* required_fragment
)
{
    ulk_command_request_v1 request;
    ulk_command_response_v1 response;
    int status;

    memset(&request, 0, sizeof(request));
    memset(&response, 0, sizeof(response));
    response.struct_size = sizeof(response);
    request.struct_size = sizeof(request);
    request.command_name = view_from_cstr(command_name);
    request.json_payload = view_from_cstr("{}");
    request.dry_run = dry_run;

    status = fl_command_client_execute_cabi_v1(context, &request, &response);
    if (status != ULK_STATUS_OK) {
        return 1;
    }
    if (response.status != ULK_STATUS_OK) {
        return 2;
    }
    if (!contains(response.json_payload, "\"status\":\"ok\"")) {
        return 3;
    }
    if (!contains(response.json_payload, required_fragment)) {
        return 4;
    }

    return 0;
}

static int run_invalid_payload(
    flb_context* context,
    const char* command_name,
    const char* payload,
    const char* required_detail
)
{
    ulk_command_request_v1 request;
    ulk_command_response_v1 response;
    int status;

    memset(&request, 0, sizeof(request));
    memset(&response, 0, sizeof(response));
    response.struct_size = sizeof(response);
    request.struct_size = sizeof(request);
    request.command_name = view_from_cstr(command_name);
    request.json_payload = view_from_cstr(payload);
    request.dry_run = 1;

    status = fl_command_client_execute_cabi_v1(context, &request, &response);
    if (status == ULK_STATUS_OK || response.status == ULK_STATUS_OK) {
        return 1;
    }
    if (!contains(response.json_payload, "\"code\":\"invalid_request\"")) {
        return 2;
    }
    if (!contains(response.json_payload, required_detail)) {
        return 3;
    }
    return 0;
}

static int run_dry_run_write_refusal(
    flb_context* context,
    const char* command_name,
    const char* payload)
{
    ulk_command_request_v1 request;
    ulk_command_response_v1 response;
    int status;

    memset(&request, 0, sizeof(request));
    memset(&response, 0, sizeof(response));
    response.struct_size = sizeof(response);
    request.struct_size = sizeof(request);
    request.command_name = view_from_cstr(command_name);
    request.json_payload = view_from_cstr(payload);
    request.dry_run = 1;
    status = fl_command_client_execute_cabi_v1(context, &request, &response);
    if (status == ULK_STATUS_OK || response.status == ULK_STATUS_OK) return 1;
    if (!contains(response.json_payload, "\"code\":\"dry_run_write_not_executed\"")) return 2;
    return 0;
}

int main(void)
{
    flb_context* context = 0;
    flb_config_v1 config;
    ulk_command_request_v1 request;
    ulk_command_response_v1 response;
    int status;

    memset(&config, 0, sizeof(config));
    config.struct_size = sizeof(config);
    config.workspace_root = view_from_cstr("flb-smoke-workspace");
    if (flb_context_create_v1(&config, &context) != ULK_STATUS_OK || context == 0) {
        return 10;
    }
    if (flb_abi_version_v1() != ((ULK_API_VERSION_MAJOR << 16) | ULK_API_VERSION_MINOR)) {
        return 11;
    }

    if (run_command(context, "product.inspect", 1, "\"product_id\":\"factorio\"") != 0) {
        return 20;
    }
    if (run_command(context, "factorio.product.inspect", 1, "\"binding_id\":\"flb.factorio\"") != 0) {
        return 21;
    }
    if (run_command(context, "command_graph.inspect", 1, "\"command\":\"launch_plan.build\"") != 0) {
        return 22;
    }
    if (run_command(context, "command_graph.inspect", 1, "\"command\":\"run.preview\"") != 0 ||
        run_command(context, "command_graph.inspect", 1, "\"command\":\"launch_plan.preflight\"") != 0 ||
        run_command(context, "command_graph.inspect", 1, "\"command\":\"mods.import\"") != 0 ||
        run_command(context, "command_graph.inspect", 1, "\"command\":\"modsets.lock\"") != 0 ||
        run_command(context, "command_graph.inspect", 1, "\"command\":\"modsets.verify\"") != 0 ||
        run_command(context, "command_graph.inspect", 1, "\"command\":\"modsets.export\"") != 0 ||
        run_command(context, "command_graph.inspect", 1, "\"command\":\"saves.list\"") != 0 ||
        run_command(context, "command_graph.inspect", 1, "\"command\":\"saves.backup\"") != 0 ||
        run_command(context, "command_graph.inspect", 1, "\"command\":\"saves.clone\"") != 0 ||
        run_command(context, "command_graph.inspect", 1, "\"command\":\"instance.export\"") != 0 ||
        run_command(context, "command_graph.inspect", 1, "\"command\":\"instance.import\"") != 0 ||
        run_command(context, "command_graph.inspect", 1, "\"command\":\"workspace.recovery.inspect\"") != 0 ||
        run_command(context, "command_graph.inspect", 1, "\"command\":\"workspace.recovery.plan\"") != 0 ||
        run_command(context, "command_graph.inspect", 1, "\"command\":\"workspace.recovery.apply\"") != 0 ||
        run_command(context, "command_graph.inspect", 1, "\"command\":\"diagnostics.export\"") != 0 ||
        run_command(context, "command_graph.inspect", 1, "\"owner\":\"factorio-launcher\"") != 0 ||
        run_command(context, "command_graph.inspect", 1, "factorio_launch_preflight.v1.schema.json") != 0) {
        return 34;
    }
    if (run_command(context, "install_refs.list", 1, "\"install_refs\":[]") != 0) {
        return 23;
    }
    if (run_command(context, "install_refs.scan", 1, "\"schema\": \"factorio.discovery_report.v1\"") != 0) {
        return 24;
    }
    if (run_command(context, "diagnostics.run", 1, "\"report_id\":\"ulk.diagnostic.minimal\"") != 0) {
        return 25;
    }
    memset(&request, 0, sizeof(request));
    memset(&response, 0, sizeof(response));
    response.struct_size = sizeof(response);
    request.struct_size = sizeof(request);
    request.command_name = view_from_cstr("diagnostics.report");
    request.json_payload = view_from_cstr("{}");
    request.dry_run = 1;
    status = fl_command_client_execute_cabi_v1(context, &request, &response);
    if (status != ULK_STATUS_UNSUPPORTED_VERSION ||
        !contains(response.json_payload, "\"code\":\"unsupported_command\"")) {
        return 35;
    }
    if (run_invalid_payload(
            context,
            "install_refs.import",
            "{\"path\":\"first\",\"path\":\"second\",\"install_id\":\"fixture\"}",
            "duplicate field") != 0) {
        return 26;
    }
    if (run_invalid_payload(
            context,
            "install_refs.import",
            "{\"path\":[],\"install_id\":\"fixture\"}",
            "field must be a string") != 0) {
        return 27;
    }
    if (run_invalid_payload(
            context,
            "instance.create",
            "{\"display_name\":\"Missing IDs\"}",
            "missing non-empty string field") != 0) {
        return 28;
    }
    if (run_invalid_payload(
            context,
            "launch_plan.build",
            "{\"instance_id\":\"fixture\"} trailing",
            "trailing data") != 0) {
        return 29;
    }
    if (run_invalid_payload(
            context,
            "run.preview",
            "{}",
            "missing non-empty string field") != 0 ||
        run_invalid_payload(
            context,
            "launch_plan.preflight",
            "{}",
            "missing non-empty string field") != 0) {
        return 36;
    }
    if (run_invalid_payload(
            context,
            "mods.import",
            "{\"source_path\":\"mod.zip\"}",
            "missing non-empty string field") != 0 ||
        run_invalid_payload(
            context,
            "modsets.export",
            "{\"instance_id\":\"fixture\"}",
            "missing non-empty string field") != 0) {
        return 37;
    }
    if (run_dry_run_write_refusal(
            context,
            "mods.import",
            "{\"source_path\":\"mod.zip\",\"instance_id\":\"fixture\"}") != 0 ||
        run_dry_run_write_refusal(
            context,
            "modsets.lock",
            "{\"instance_id\":\"fixture\"}") != 0 ||
        run_dry_run_write_refusal(
            context,
            "modsets.export",
            "{\"instance_id\":\"fixture\",\"output_path\":\"pack.zip\"}") != 0 ||
        run_dry_run_write_refusal(
            context,
            "saves.backup",
            "{\"instance_id\":\"fixture\",\"save\":\"starter\"}") != 0 ||
        run_dry_run_write_refusal(
            context,
            "saves.clone",
            "{\"source_instance_id\":\"fixture\",\"target_instance_id\":\"other\",\"save\":\"starter\"}") != 0 ||
        run_dry_run_write_refusal(
            context,
            "instance.export",
            "{\"instance_id\":\"fixture\",\"output_path\":\"instance.zip\"}") != 0 ||
        run_dry_run_write_refusal(
            context,
            "instance.import",
            "{\"source_path\":\"instance.zip\"}") != 0 ||
        run_dry_run_write_refusal(
            context,
            "workspace.recovery.apply",
            "{\"transaction_id\":\"tx-example\"}") != 0 ||
        run_dry_run_write_refusal(
            context,
            "diagnostics.export",
            "{\"instance_id\":\"fixture\",\"output_path\":\"diagnostics.zip\"}") != 0) {
        return 38;
    }

    memset(&request, 0, sizeof(request));
    memset(&response, 0, sizeof(response));
    response.struct_size = sizeof(response);
    request.struct_size = sizeof(request);
    request.command_name = view_from_cstr("missing.command");
    request.json_payload = view_from_cstr("{}");
    request.dry_run = 1;
    status = fl_command_client_execute_cabi_v1(context, &request, &response);
    if (status != ULK_STATUS_UNSUPPORTED_VERSION ||
        response.status != ULK_STATUS_UNSUPPORTED_VERSION ||
        !contains(response.json_payload, "\"status\":\"unsupported\"") ||
        !contains(response.json_payload, "\"code\":\"unsupported_command\"") ||
        !contains(response.json_payload, "Command is not supported by the Universal Launcher command graph")) {
        return 30;
    }

    memset(&response, 0, sizeof(response));
    response.struct_size = sizeof(response);
    status = fl_command_client_execute_cabi_v1(context, 0, &response);
    if (status != ULK_STATUS_INVALID_ARGUMENT ||
        response.status != ULK_STATUS_INVALID_ARGUMENT ||
        !contains(response.json_payload, "\"status\":\"invalid_argument\"") ||
        !contains(response.json_payload, "\"code\":\"invalid_argument\"") ||
        !contains(response.json_payload, "Factorio binding command request is invalid")) {
        return 31;
    }

    memset(&response, 0, sizeof(response));
    response.struct_size = sizeof(response) - 1;
    status = fl_command_client_execute_cabi_v1(context, &request, &response);
    if (status != ULK_STATUS_INVALID_ARGUMENT) {
        return 32;
    }

    flb_context_destroy_v1(context);

    memset(&config, 0, sizeof(config));
    config.struct_size = sizeof(config) - 1;
    context = 0;
    if (flb_context_create_v1(&config, &context) != ULK_STATUS_INVALID_ARGUMENT || context != 0) {
        return 33;
    }
    return 0;
}
