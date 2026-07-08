#ifndef FL_COMMAND_CLIENT_CABI_H
#define FL_COMMAND_CLIENT_CABI_H

#include "flb/flb_api.h"

#ifdef __cplusplus
extern "C" {
#endif

const char* fl_command_client_cabi_transport(void);

int fl_command_client_execute_cabi_v1(
    flb_context* context,
    const ulk_command_request_v1* request,
    ulk_command_response_v1* response
);

#ifdef __cplusplus
}
#endif

#endif
