// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_LAUNCH_H
#define FLB_LAUNCH_H

#include "flb_api.h"

int flb_launch_plan_build_v1(
    flb_context* context,
    const ulk_command_request_v1* request,
    ulk_command_response_v1* response
);

#endif
