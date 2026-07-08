#ifndef ULK_INSTANCE_H
#define ULK_INSTANCE_H

#include "ulk_types.h"

typedef struct ulk_instance_ref_v1 {
    ulk_size struct_size;
    ulk_string_view instance_id;
    ulk_string_view install_id;
} ulk_instance_ref_v1;

#endif
