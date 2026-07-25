// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "modules/content_module.h"

#include "command_result.h"
#include "handlers/mods.h"
#include "handlers/modsets.h"
#include "handlers/saves.h"
#include "handlers/snapshots.h"
#include "handlers/utility.h"

namespace facman::factorio::application {

bool ContentApplicationModule::handles(CommandId command) const noexcept
{
    switch (command) {
    case CommandId::snapshots_create:
    case CommandId::snapshots_list:
    case CommandId::snapshots_inspect:
    case CommandId::snapshots_verify:
    case CommandId::snapshots_diff:
    case CommandId::snapshots_restore:
    case CommandId::snapshots_retention_plan:
    case CommandId::snapshots_retention_apply:
    case CommandId::mods_search:
    case CommandId::mods_install:
    case CommandId::mods_update:
    case CommandId::mods_import:
    case CommandId::mods_list:
    case CommandId::mods_inspect:
    case CommandId::mods_verify:
    case CommandId::mods_index:
    case CommandId::mods_explain:
    case CommandId::modsets_lock:
    case CommandId::modsets_verify:
    case CommandId::modsets_export:
    case CommandId::modsets_plan:
    case CommandId::modsets_diff:
    case CommandId::modsets_explain:
    case CommandId::modsets_apply:
    case CommandId::modsets_rollback:
    case CommandId::saves_list:
    case CommandId::saves_backup:
    case CommandId::saves_clone:
    case CommandId::saves_index:
    case CommandId::saves_inspect:
    case CommandId::saves_verify:
    case CommandId::saves_associate:
    case CommandId::saves_diff:
    case CommandId::saves_retention_plan:
    case CommandId::saves_retention_apply:
    case CommandId::servers_list:
    case CommandId::servers_create:
    case CommandId::servers_inspect:
    case CommandId::servers_validate:
    case CommandId::servers_plan:
    case CommandId::servers_diff:
    case CommandId::servers_export:
    case CommandId::servers_start:
    case CommandId::servers_stop:
    case CommandId::servers_rcon:
        return true;
    default:
        return false;
    }
}

bool ContentApplicationModule::accepts_denied_admission(
    const CommandAdmissionDecision& admission) const noexcept
{
    return admission.code == "network_forbidden";
}

ApplicationResult ContentApplicationModule::execute(
    ApplicationContext& context,
    const ApplicationRequest& request,
    const CommandAdmissionDecision&,
    const std::string&) const
{
    switch (request.command) {
    case CommandId::snapshots_create:
    case CommandId::snapshots_list:
    case CommandId::snapshots_inspect:
    case CommandId::snapshots_verify:
    case CommandId::snapshots_diff:
    case CommandId::snapshots_restore:
    case CommandId::snapshots_retention_plan:
    case CommandId::snapshots_retention_apply:
        return handlers::dispatch_snapshots(context, request);
    case CommandId::mods_search:
    case CommandId::mods_install:
    case CommandId::mods_update:
        return handlers::refuse_mod_portal(
            context, std::get<ServiceOperationRequest>(request.payload));
    case CommandId::mods_import:
        return handlers::import_mod(
            context, std::get<ImportModRequest>(request.payload));
    case CommandId::mods_list:
    case CommandId::mods_inspect:
    case CommandId::mods_verify:
    case CommandId::mods_index:
    case CommandId::mods_explain:
        return handlers::dispatch_mod_inventory(context, request);
    case CommandId::modsets_lock:
        return handlers::lock_modset(
            context, std::get<ModsetInstanceRequest>(request.payload));
    case CommandId::modsets_verify:
        return handlers::verify_modset(
            context, std::get<ModsetInstanceRequest>(request.payload));
    case CommandId::modsets_export:
        return handlers::export_modset(
            context, std::get<ExportModsetRequest>(request.payload));
    case CommandId::modsets_plan:
    case CommandId::modsets_diff:
    case CommandId::modsets_explain:
    case CommandId::modsets_apply:
    case CommandId::modsets_rollback:
        return handlers::dispatch_modset_solver(context, request);
    case CommandId::saves_list:
        return handlers::list_saves(
            context, std::get<ListSavesRequest>(request.payload));
    case CommandId::saves_backup:
        return handlers::backup_save(
            context, std::get<BackupSaveRequest>(request.payload));
    case CommandId::saves_clone:
        return handlers::clone_save(
            context, std::get<CloneSaveRequest>(request.payload));
    case CommandId::saves_index:
    case CommandId::saves_inspect:
    case CommandId::saves_verify:
    case CommandId::saves_associate:
    case CommandId::saves_diff:
    case CommandId::saves_retention_plan:
    case CommandId::saves_retention_apply:
        return handlers::dispatch_save_index(context, request);
    case CommandId::servers_list:
        return handlers::list_servers(context);
    case CommandId::servers_create:
        return handlers::create_server(
            context, std::get<ServiceOperationRequest>(request.payload));
    case CommandId::servers_inspect:
    case CommandId::servers_validate:
    case CommandId::servers_plan:
    case CommandId::servers_diff:
    case CommandId::servers_export:
        return handlers::dispatch_server_plan(context, request);
    case CommandId::servers_start:
    case CommandId::servers_stop:
    case CommandId::servers_rcon:
        return handlers::control_server(
            context, std::get<ServiceOperationRequest>(request.payload));
    default:
        return refused(
            safety_refusal(
                "content.module",
                "invalid_request",
                "Unsupported content command",
                "",
                false),
            "invalid_request",
            "Unsupported content command");
    }
}

} // namespace facman::factorio::application
