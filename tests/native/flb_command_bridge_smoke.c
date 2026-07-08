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

int main(void)
{
    flb_context* context = 0;
    flb_config_v1 config;
    ulk_command_request_v1 request;
    ulk_command_response_v1 response;
    int status;

    memset(&config, 0, sizeof(config));
    config.struct_size = sizeof(config);
    if (flb_context_create_v1(&config, &context) != ULK_STATUS_OK || context == 0) {
        return 10;
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
    if (run_command(context, "install_refs.list", 1, "\"install_refs\":[]") != 0) {
        return 23;
    }
    if (run_command(context, "launch_plan.build", 1, "\"dry_run\":true") != 0) {
        return 24;
    }
    if (run_command(context, "launch_plan.build", 1, "\"argv\":[]") != 0) {
        return 26;
    }
    if (run_command(context, "launch_plan.build", 1, "\"preflight\":[]") != 0) {
        return 27;
    }
    if (run_command(context, "diagnostics.report", 1, "\"report_id\":\"ulk.diagnostic.minimal\"") != 0) {
        return 25;
    }

    memset(&request, 0, sizeof(request));
    memset(&response, 0, sizeof(response));
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
    status = fl_command_client_execute_cabi_v1(context, 0, &response);
    if (status != ULK_STATUS_INVALID_ARGUMENT ||
        response.status != ULK_STATUS_INVALID_ARGUMENT ||
        !contains(response.json_payload, "\"status\":\"invalid_argument\"") ||
        !contains(response.json_payload, "\"code\":\"invalid_argument\"") ||
        !contains(response.json_payload, "Factorio binding command request is invalid")) {
        return 31;
    }

    flb_context_destroy_v1(context);
    return 0;
}
