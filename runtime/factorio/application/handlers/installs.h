// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_HANDLERS_INSTALLS_H
#define FACMAN_FACTORIO_APPLICATION_HANDLERS_INSTALLS_H

#include "application_context.h"
#include "application_types.h"

namespace facman::factorio::application::handlers {
ApplicationResult list_installs(ApplicationContext& context);
ApplicationResult scan_installs(ApplicationContext& context, const ScanInstallRefsRequest& request);
ApplicationResult import_install(ApplicationContext& context, const ImportInstallRefRequest& request);
ApplicationResult inspect_install(ApplicationContext& context, const InspectInstallRefRequest& request);
}
#endif
