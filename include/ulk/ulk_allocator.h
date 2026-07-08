#ifndef ULK_ALLOCATOR_H
#define ULK_ALLOCATOR_H

#include "ulk_types.h"

typedef struct ulk_allocator_v1 {
    ulk_size struct_size;
    void* user;
    void* (*alloc)(void* user, ulk_size size);
    void (*free)(void* user, void* ptr);
} ulk_allocator_v1;

#endif
