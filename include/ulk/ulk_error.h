#ifndef ULK_ERROR_H
#define ULK_ERROR_H

#include "ulk_types.h"

typedef enum ulk_status {
    ULK_STATUS_OK = 0,
    ULK_STATUS_ERROR = 1,
    ULK_STATUS_INVALID_ARGUMENT = 2,
    ULK_STATUS_UNSUPPORTED_VERSION = 3
} ulk_status;

typedef struct ulk_error_v1 {
    ulk_size struct_size;
    int code;
    ulk_string_view message;
    ulk_string_view detail;
} ulk_error_v1;

#endif
