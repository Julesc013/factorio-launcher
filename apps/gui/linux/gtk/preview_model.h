// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#pragma once

#include <glib.h>

typedef enum {
    FACMAN_PREVIEW_READY = 0,
    FACMAN_PREVIEW_STALE_READINESS,
    FACMAN_PREVIEW_RUNNING,
    FACMAN_PREVIEW_EXITED,
    FACMAN_PREVIEW_INTERRUPTED
} FacManPreviewState;

typedef struct {
    FacManPreviewState state;
    const gchar *state_id;
    const gchar *readiness;
    const gchar *status_text;
    const gchar *primary_label;
    const gchar *primary_accessibility_label;
    const gchar *activity_summary;
    const gchar *operation_id;
    const gchar *last_run;
    const gchar *recovery_id;
    const gchar *refusal_code;
} FacManPreviewRecord;

const FacManPreviewRecord *facman_preview_record(FacManPreviewState state);
