// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_command_client_cabi.h"

#include "ulk/ulk_client.h"

#include <string.h>

static ulk_string_view fl_command_client_view(const char* value)
{
    ulk_string_view result;
    result.data = value;
    result.size = value == 0 ? 0u : (ulk_size)strlen(value);
    return result;
}

static int ULK_CALL fl_command_client_execute_flb(
    void* user_data,
    const ulk_command_request_v1* request,
    ulk_command_response_v1* response
)
{
    return flb_command_execute_v1((flb_context*)user_data, request, response);
}

int fl_command_client_execute_cabi_v1(
    flb_context* context,
    const ulk_command_request_v1* request,
    ulk_command_response_v1* response
)
{
    ulk_client_v1 client;
    ulk_transport_adapter_v1 adapter;
    /*
     * Preserve the FLB 1.x invalid-envelope response contract. The neutral ULK
     * client rejects malformed envelopes before transport dispatch, while the
     * established FacMan ABI also asks FLB to populate its structured refusal
     * payload when a usable response object was supplied.
     */
    if (
        request == 0 ||
        request->struct_size < (ulk_size)sizeof(*request) ||
        response == 0 ||
        response->struct_size < (ulk_size)sizeof(*response)
    ) {
        return flb_command_execute_v1(context, request, response);
    }
    memset(&client, 0, sizeof(client));
    memset(&adapter, 0, sizeof(adapter));
    client.struct_size = sizeof(client);
    adapter.struct_size = sizeof(adapter);
    adapter.kind = ULK_TRANSPORT_DIRECT;
    adapter.revision = fl_command_client_view("facman.flb.direct.v1");
    adapter.execute = fl_command_client_execute_flb;
    adapter.user_data = context;
    if (ulk_client_initialize_v1(&client, &adapter) != ULK_STATUS_OK) {
        return ULK_STATUS_INVALID_ARGUMENT;
    }
    return ulk_client_execute_v1(&client, request, response);
}
