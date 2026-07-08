#ifndef ULK_AUDIT_H
#define ULK_AUDIT_H

#include "ulk_types.h"

typedef struct ulk_audit_event_v1 {
    ulk_size struct_size;
    ulk_string_view event_type;
    ulk_string_view json_payload;
} ulk_audit_event_v1;

#endif
