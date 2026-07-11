// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_HANDLERS_LAUNCH_H
#define FACMAN_FACTORIO_APPLICATION_HANDLERS_LAUNCH_H

#include "application_context.h"
#include "application_types.h"

namespace facman::factorio::application::handlers {
ApplicationResult preview_launch(ApplicationContext& context, const BuildLaunchPlanRequest& request, const std::string& command);
ApplicationResult preflight_launch(ApplicationContext& context, const BuildLaunchPlanRequest& request);
}
#endif
