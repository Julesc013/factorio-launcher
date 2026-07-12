// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_HANDLERS_SETUP_H
#define FACMAN_FACTORIO_APPLICATION_HANDLERS_SETUP_H

#include "application_context.h"
#include "application_types.h"

namespace facman::factorio::application::handlers {
ApplicationResult preview_setup(ApplicationContext& context);
ApplicationResult verify_package(ApplicationContext& context, const ServiceOperationRequest& request);
ApplicationResult install_version(ApplicationContext& context, const ServiceOperationRequest& request);
ApplicationResult verify_install(ApplicationContext& context, const ServiceOperationRequest& request);
ApplicationResult repair_install(ApplicationContext& context, const ServiceOperationRequest& request);
ApplicationResult uninstall_install(ApplicationContext& context, const ServiceOperationRequest& request);
}
#endif
