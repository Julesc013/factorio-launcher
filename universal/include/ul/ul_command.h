#ifndef UL_COMMAND_H
#define UL_COMMAND_H

#include "ul_error.h"
#include "ul_types.h"

typedef struct ul_command_request_v1 {
    ul_size struct_size;
    ul_string_view command_name;
    ul_string_view json_payload;
    ul_bool dry_run;
} ul_command_request_v1;

typedef struct ul_command_response_v1 {
    ul_size struct_size;
    int status;
    ul_string_view json_payload;
    ul_error_v1 error;
} ul_command_response_v1;

#endif

