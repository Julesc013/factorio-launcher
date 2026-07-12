// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_HANDLERS_INSTANCES_H
#define FACMAN_FACTORIO_APPLICATION_HANDLERS_INSTANCES_H

#include "application_context.h"
#include "application_types.h"

namespace facman::factorio::application::handlers {
ApplicationResult list_instances(ApplicationContext& context);
ApplicationResult create_instance(ApplicationContext& context, const CreateInstanceRequest& request);
ApplicationResult inspect_instance(ApplicationContext& context, const InspectInstanceRequest& request);
ApplicationResult verify_instance(ApplicationContext& context, const InspectInstanceRequest& request);
ApplicationResult diff_instances(ApplicationContext& context, const DiffInstanceRequest& request);
ApplicationResult clone_instance(ApplicationContext& context, const CloneInstanceRequest& request);
ApplicationResult rename_instance(ApplicationContext& context, const RenameInstanceRequest& request);
ApplicationResult archive_instance(ApplicationContext& context, const ArchiveInstanceRequest& request);
ApplicationResult restore_instance(ApplicationContext& context, const RestoreInstanceRequest& request);
ApplicationResult dispatch_instance_lifecycle(ApplicationContext& context, const ApplicationRequest& request);
}
#endif
