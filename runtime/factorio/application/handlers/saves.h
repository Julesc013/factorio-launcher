// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_HANDLERS_SAVES_H
#define FACMAN_FACTORIO_APPLICATION_HANDLERS_SAVES_H

#include "application_context.h"
#include "application_types.h"

namespace facman::factorio::application::handlers {
ApplicationResult list_saves(ApplicationContext& context, const ListSavesRequest& request);
ApplicationResult backup_save(ApplicationContext& context, const BackupSaveRequest& request);
ApplicationResult clone_save(ApplicationContext& context, const CloneSaveRequest& request);
ApplicationResult export_instance(ApplicationContext& context, const ExportInstanceRequest& request);
ApplicationResult import_instance(ApplicationContext& context, const ImportInstanceRequest& request);
ApplicationResult dispatch_save_index(ApplicationContext& context, const ApplicationRequest& request);
}
#endif
