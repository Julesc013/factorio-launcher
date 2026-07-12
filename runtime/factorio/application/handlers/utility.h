// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_HANDLERS_UTILITY_H
#define FACMAN_FACTORIO_APPLICATION_HANDLERS_UTILITY_H

#include "application_context.h"
#include "application_types.h"

namespace facman::factorio::application::handlers {
ApplicationResult refuse_mod_portal(ApplicationContext& context, const ServiceOperationRequest& request);
ApplicationResult create_server(ApplicationContext& context, const ServiceOperationRequest& request);
ApplicationResult list_servers(ApplicationContext& context);
ApplicationResult control_server(ApplicationContext& context, const ServiceOperationRequest& request);
ApplicationResult dispatch_server_plan(ApplicationContext& context, const ApplicationRequest& request);
ApplicationResult redact_diagnostics(ApplicationContext& context, const ServiceOperationRequest& request);
ApplicationResult create_bug_report(ApplicationContext& context);
ApplicationResult refuse_dev_execution(ApplicationContext& context, const ServiceOperationRequest& request);
}
#endif
