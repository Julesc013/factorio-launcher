#ifndef UL_ALLOCATOR_H
#define UL_ALLOCATOR_H

#include "ul_types.h"

typedef struct ul_allocator_v1 {
    ul_size struct_size;
    void* user;
    void* (*alloc)(void* user, ul_size size);
    void (*free)(void* user, void* ptr);
} ul_allocator_v1;

#endif

