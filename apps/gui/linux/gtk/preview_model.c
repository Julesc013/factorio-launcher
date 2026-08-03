// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "preview_model.h"

static const FacManPreviewRecord records[] = {
    { FACMAN_PREVIEW_READY, "positive", "Ready — revision 7", "Ready", "Play",
      "Play deterministic fixture journey", "No active operations.", "", "No previous run", "", "" },
    { FACMAN_PREVIEW_STALE_READINESS, "refused", "Stale — observed revision 7; current revision 8",
      "Play unavailable: readiness changed", "Play", "Play unavailable because readiness is stale",
      "No process started. Play was refused before effects.", "", "No previous run", "", "stale_readiness" },
    { FACMAN_PREVIEW_RUNNING, "running", "Ready — revision 7", "Running under backend supervision",
      "Show in Activity", "Show running operation in Activity",
      "1 operation is running.", "operation.fixture-play-001",
      "No previous run", "", "" },
    { FACMAN_PREVIEW_EXITED, "exited", "Ready — revision 7",
      "Last run exited normally; ready to relaunch", "Relaunch",
      "Relaunch deterministic fixture journey", "Last fixture operation exited normally.", "",
      "Exited normally · code 0 · operation.fixture-play-001", "", "" },
    { FACMAN_PREVIEW_INTERRUPTED, "interrupted", "Ready — revision 7",
      "Recovery required after interruption", "Inspect recovery",
      "Inspect interrupted operation recovery", "1 interrupted operation requires recovery.",
      "operation.fixture-play-001", "Interrupted · outcome unknown · operation.fixture-play-001",
      "recovery.fixture-play-001", "" }
};

const FacManPreviewRecord *facman_preview_record(FacManPreviewState state)
{
    if (state < FACMAN_PREVIEW_READY || state > FACMAN_PREVIEW_INTERRUPTED)
        state = FACMAN_PREVIEW_READY;
    return &records[state];
}
