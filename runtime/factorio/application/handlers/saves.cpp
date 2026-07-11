// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "handlers/saves.h"

#include "command_result.h"

namespace facman::factorio::application::handlers {
ApplicationResult list_saves(ApplicationContext& context, const ListSavesRequest& request)
{
    return from_save_outcome(saves::list_saves(context.workspace(), request));
}
ApplicationResult backup_save(ApplicationContext& context, const BackupSaveRequest& request)
{
    return from_save_outcome(saves::backup_save(context.workspace(), request));
}
ApplicationResult clone_save(ApplicationContext& context, const CloneSaveRequest& request)
{
    return from_save_outcome(saves::clone_save(context.workspace(), request));
}
ApplicationResult export_instance(ApplicationContext& context, const ExportInstanceRequest& request)
{
    return from_save_outcome(saves::export_instance(context.workspace(), request));
}
ApplicationResult import_instance(ApplicationContext& context, const ImportInstanceRequest& request)
{
    return from_save_outcome(saves::import_instance(context.workspace(), request));
}
}
