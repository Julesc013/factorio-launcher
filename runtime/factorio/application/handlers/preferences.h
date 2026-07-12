// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_HANDLERS_PREFERENCES_H
#define FACMAN_FACTORIO_APPLICATION_HANDLERS_PREFERENCES_H

#include "application_context.h"
#include "application_types.h"
#include "command_result.h"

namespace facman::factorio::application::handlers {

ApplicationResult inspect_preferences(ApplicationContext& context);
ApplicationResult validate_preferences(ApplicationContext& context, const PreferencesRequest& request);
ApplicationResult plan_preferences(ApplicationContext& context, const PreferencesRequest& request);
ApplicationResult apply_preferences(ApplicationContext& context, const PreferencesRequest& request);
ApplicationResult plan_preferences_reset(ApplicationContext& context);
ApplicationResult apply_preferences_reset(ApplicationContext& context);

} // namespace facman::factorio::application::handlers

#endif
