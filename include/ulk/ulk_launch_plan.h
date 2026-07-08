#ifndef ULK_LAUNCH_PLAN_H
#define ULK_LAUNCH_PLAN_H

#include "ulk_types.h"

typedef struct ulk_launch_plan_ref_v1 {
    ulk_size struct_size;
    ulk_string_view instance_id;
    ulk_string_view profile_id;
    ulk_string_view json_payload;
} ulk_launch_plan_ref_v1;

#endif
