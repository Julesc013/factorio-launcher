// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "handlers/saves.h"

#include "command_result.h"
#include "flb_factorio_save_index.h"

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

namespace {
ApplicationResult index_result(const char* operation, facman::core::Result<std::string> result)
{
    if (result) { ApplicationResult output; output.output = result.take_value(); return output; }
    return refused(safety_refusal(operation, result.error().code, "Save intelligence operation was refused",
        result.error().message, result.error().recoverable), result.error().code, result.error().message, result.error().kind);
}
}

ApplicationResult dispatch_save_index(ApplicationContext& context, const ApplicationRequest& request)
{
    const auto& value = std::get<SaveIndexRequest>(request.payload);
    namespace save_index = facman::factorio::saves::index;
    switch (request.command) {
    case CommandId::saves_index: return index_result("saves.index", save_index::list(context.workspace(), value));
    case CommandId::saves_inspect: return index_result("saves.inspect", save_index::inspect(context.workspace(), value));
    case CommandId::saves_verify: return index_result("saves.verify", save_index::verify(context.workspace(), value));
    case CommandId::saves_associate: return index_result("saves.associate", save_index::associate(context.workspace(), value));
    case CommandId::saves_diff: return index_result("saves.diff", save_index::diff(context.workspace(), value));
    case CommandId::saves_retention_plan: return index_result("saves.retention.plan", save_index::retention_plan(context.workspace(), value));
    case CommandId::saves_retention_apply: return index_result("saves.retention.apply", save_index::retention_apply(context.workspace(), value));
    default: return index_result("saves.index", facman::core::Result<std::string>::failure(
        {"unsupported_operation", "Unsupported save intelligence command", "saves"}));
    }
}
}
