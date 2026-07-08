#ifndef ULK_MANIFEST_H
#define ULK_MANIFEST_H

#include "ulk_types.h"

typedef struct ulk_manifest_ref_v1 {
    ulk_size struct_size;
    ulk_string_view schema_id;
    ulk_string_view json_payload;
} ulk_manifest_ref_v1;

#endif
