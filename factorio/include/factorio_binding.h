#ifndef FACTORIO_BINDING_H
#define FACTORIO_BINDING_H

#include "ul/ul_command.h"
#include "ul/ul_types.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct factorio_binding_context factorio_binding_context;

typedef struct factorio_binding_config_v1 {
    ul_size struct_size;
    ul_string_view product_root;
    ul_string_view workspace_root;
} factorio_binding_config_v1;

int factorio_binding_create_v1(
    const factorio_binding_config_v1* config,
    factorio_binding_context** out_context
);

int factorio_binding_execute_v1(
    factorio_binding_context* context,
    const ul_command_request_v1* request,
    ul_command_response_v1* response
);

void factorio_binding_destroy_v1(factorio_binding_context* context);

#ifdef __cplusplus
}
#endif

#endif

