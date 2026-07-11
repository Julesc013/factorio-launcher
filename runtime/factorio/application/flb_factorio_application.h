// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_APPLICATION_H
#define FLB_FACTORIO_APPLICATION_H

#include "ulk/ulk_command.h"

#ifdef __cplusplus
extern "C" {
#endif

void* flb_factorio_application_create(const char* workspace_root);

void flb_factorio_application_destroy(void* application);

int ULK_CALL flb_factorio_application_handle_v1(
    void* application,
    const ulk_command_request_v1* request,
    ulk_command_response_v1* response);

#ifdef __cplusplus
}
#endif

#endif
