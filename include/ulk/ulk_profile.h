#ifndef ULK_PROFILE_H
#define ULK_PROFILE_H

#include "ulk_types.h"

typedef struct ulk_profile_ref_v1 {
    ulk_size struct_size;
    ulk_string_view profile_id;
} ulk_profile_ref_v1;

#endif
