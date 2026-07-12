// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_HANDLERS_MODSETS_H
#define FACMAN_FACTORIO_APPLICATION_HANDLERS_MODSETS_H

#include "application_context.h"
#include "application_types.h"

namespace facman::factorio::application::handlers {
ApplicationResult lock_modset(ApplicationContext& context, const ModsetInstanceRequest& request);
ApplicationResult verify_modset(ApplicationContext& context, const ModsetInstanceRequest& request);
ApplicationResult export_modset(ApplicationContext& context, const ExportModsetRequest& request);
ApplicationResult dispatch_modset_solver(ApplicationContext& context, const ApplicationRequest& request);
}
#endif
