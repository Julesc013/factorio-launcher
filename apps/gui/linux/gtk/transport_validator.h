// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#pragma once

#include <glib.h>

typedef struct {
    const gchar *request_id;
    const gchar *operation_id;
    const gchar *attempt_id;
    const gchar *command;
} FacManGtkTransportExpectation;

// Returns NULL for a strict, correlated transport response. The caller owns
// the stable local refusal returned for malformed or mismatched output.
gchar *facman_gtk_transport_validate(
    const guint8 *stdout_data,
    gsize stdout_size,
    const guint8 *stderr_data,
    gsize stderr_size,
    const FacManGtkTransportExpectation *expectation);
