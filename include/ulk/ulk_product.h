#ifndef ULK_PRODUCT_H
#define ULK_PRODUCT_H

#include "ulk_types.h"

typedef struct ulk_product_ref_v1 {
    ulk_size struct_size;
    ulk_string_view product_id;
    ulk_string_view binding_id;
} ulk_product_ref_v1;

#endif
