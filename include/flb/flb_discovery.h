// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_DISCOVERY_H
#define FLB_DISCOVERY_H

#include "flb_api.h"

int flb_discovery_scan_v1(
    flb_context* context,
    const ulk_command_request_v1* request,
    ulk_command_response_v1* response
);

#endif
