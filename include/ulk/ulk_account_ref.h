#ifndef ULK_ACCOUNT_REF_H
#define ULK_ACCOUNT_REF_H

#include "ulk_types.h"

typedef struct ulk_account_ref_v1 {
    ulk_size struct_size;
    ulk_string_view account_id;
    ulk_string_view provider;
} ulk_account_ref_v1;

#endif
