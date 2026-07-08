#include "fl_command_client_cabi.h"

int fl_command_client_execute_cabi_v1(
    flb_context* context,
    const ulk_command_request_v1* request,
    ulk_command_response_v1* response
)
{
    return flb_command_execute_v1(context, request, response);
}
