// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_HANDLERS_SNAPSHOTS_H
#define FACMAN_FACTORIO_APPLICATION_HANDLERS_SNAPSHOTS_H

#include "application_context.h"
#include "application_types.h"

namespace facman::factorio::application::handlers {
ApplicationResult dispatch_snapshots(ApplicationContext& context, const ApplicationRequest& request);
}

#endif
