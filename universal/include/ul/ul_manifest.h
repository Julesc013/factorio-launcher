#ifndef UL_MANIFEST_H
#define UL_MANIFEST_H

#include "ul_types.h"

typedef struct ul_manifest_ref_v1 {
    ul_size struct_size;
    ul_string_view schema_id;
    ul_string_view json_payload;
} ul_manifest_ref_v1;

#endif

