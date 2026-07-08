#ifndef ULK_TYPES_H
#define ULK_TYPES_H

#define ULK_API_VERSION_MAJOR 1
#define ULK_API_VERSION_MINOR 0

typedef unsigned long ulk_size;
typedef int ulk_bool;

typedef struct ulk_string_view {
    const char* data;
    ulk_size size;
} ulk_string_view;

#endif
