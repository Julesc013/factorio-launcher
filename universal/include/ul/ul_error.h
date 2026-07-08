#ifndef UL_ERROR_H
#define UL_ERROR_H

#include "ul_types.h"

typedef struct ul_error_v1 {
    ul_size struct_size;
    int code;
    ul_string_view message;
    ul_string_view detail;
} ul_error_v1;

#endif

