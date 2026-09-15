// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_HANDLERS_SETUP_H
#define FACMAN_FACTORIO_APPLICATION_HANDLERS_SETUP_H

#include "application_context.h"
#include "application_types.h"

namespace facman::factorio::application::handlers {
bool is_setup_command(CommandId command) noexcept;
ApplicationResult dispatch_setup(ApplicationContext& context, const ApplicationRequest& request);
ApplicationResult preview_setup(ApplicationContext& context);
ApplicationResult verify_package(ApplicationContext& context, const ServiceOperationRequest& request);
ApplicationResult install_version(ApplicationContext& context, const ServiceOperationRequest& request);
ApplicationResult plan_install(ApplicationContext& context, const ServiceOperationRequest& request);
ApplicationResult apply_install(ApplicationContext& context, const ServiceOperationRequest& request);
ApplicationResult verify_install(ApplicationContext& context, const ServiceOperationRequest& request);
ApplicationResult repair_install(ApplicationContext& context, const ServiceOperationRequest& request);
ApplicationResult plan_repair_install(ApplicationContext& context, const ServiceOperationRequest& request);
ApplicationResult apply_repair_install(ApplicationContext& context, const ServiceOperationRequest& request);
ApplicationResult plan_move_install(ApplicationContext& context, const ServiceOperationRequest& request);
ApplicationResult apply_move_install(ApplicationContext& context, const ServiceOperationRequest& request);
ApplicationResult uninstall_install(ApplicationContext& context, const ServiceOperationRequest& request);
ApplicationResult plan_uninstall_install(ApplicationContext& context, const ServiceOperationRequest& request);
ApplicationResult apply_uninstall_install(ApplicationContext& context, const ServiceOperationRequest& request);
ApplicationResult inspect_install_recovery(ApplicationContext& context, const ServiceOperationRequest& request);
ApplicationResult apply_install_recovery(ApplicationContext& context, const ServiceOperationRequest& request);
}
#endif
