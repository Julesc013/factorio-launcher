#ifndef UL_TYPES_H
#define UL_TYPES_H

#define UL_API_VERSION_MAJOR 1
#define UL_API_VERSION_MINOR 0

typedef unsigned long ul_size;
typedef int ul_bool;

typedef struct ul_string_view {
    const char* data;
    ul_size size;
} ul_string_view;

#endif

