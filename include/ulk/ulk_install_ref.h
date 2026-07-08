#ifndef ULK_INSTALL_REF_H
#define ULK_INSTALL_REF_H

#include "ulk_types.h"

typedef struct ulk_install_ref_v1 {
    ulk_size struct_size;
    ulk_string_view install_id;
    ulk_string_view product_id;
    ulk_string_view ownership;
} ulk_install_ref_v1;

#endif
