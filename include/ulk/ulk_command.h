#ifndef ULK_COMMAND_H
#define ULK_COMMAND_H

#include "ulk_error.h"
#include "ulk_types.h"

typedef struct ulk_command_request_v1 {
    ulk_size struct_size;
    ulk_string_view command_name;
    ulk_string_view json_payload;
    ulk_bool dry_run;
} ulk_command_request_v1;

typedef struct ulk_command_response_v1 {
    ulk_size struct_size;
    int status;
    ulk_string_view json_payload;
    ulk_error_v1 error;
} ulk_command_response_v1;

#endif
