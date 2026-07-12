// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_application.h"

#include "application_context.h"
#include "application_types.h"
#include "command_dispatch.h"
#include "command_result.h"
#include "handlers/diagnostics.h"
#include "handlers/doctor.h"
#include "handlers/installs.h"
#include "handlers/instances.h"
#include "handlers/launch.h"
#include "handlers/mods.h"
#include "handlers/modsets.h"
#include "handlers/product.h"
#include "handlers/recovery.h"
#include "handlers/saves.h"
#include "handlers/setup.h"
#include "handlers/unavailable.h"
#include "handlers/utility.h"

#include <filesystem>
#include <mutex>
#include <new>
#include <string>
#include <variant>

namespace facman::factorio::application {
namespace {

int write_boundary_error(ulk_command_response_v1* response, const char* code, const char* message) noexcept
{
    static const char payload[] =
        "{\"schema\":\"ulk.command_response.v1\",\"status\":\"internal_error\",\"payload\":null,"
        "\"error\":{\"code\":\"cxx_exception_contained\",\"message\":\"A C++ exception was contained at the FLB boundary\"}}";
    if (response == nullptr || response->struct_size < sizeof(*response)) return ULK_STATUS_INVALID_ARGUMENT;
    response->struct_size = sizeof(*response);
    response->status = ULK_STATUS_ERROR;
    response->json_payload.data = payload;
    response->json_payload.size = sizeof(payload) - 1;
    response->error.struct_size = sizeof(response->error);
    response->error.code = ULK_STATUS_ERROR;
    response->error.message.data = message;
    response->error.message.size = message == nullptr ? 0 : std::char_traits<char>::length(message);
    response->error.detail.data = code;
    response->error.detail.size = code == nullptr ? 0 : std::char_traits<char>::length(code);
    return ULK_STATUS_ERROR;
}

} // namespace

class FactorioApplication {
public:
    explicit FactorioApplication(std::string workspace_root)
        : context_(workspace_root.empty() ? std::filesystem::path() : std::filesystem::path(workspace_root))
    {
    }

    int handle(const ulk_command_request_v1* request, ulk_command_response_v1* response)
    {
        std::lock_guard<std::mutex> lock(request_mutex_);
        current_command_.assign(
            request->command_name.data,
            request->command_name.data + request->command_name.size);
        std::string payload;
        if (request->json_payload.data != nullptr) {
            payload.assign(request->json_payload.data, request->json_payload.data + request->json_payload.size);
        }
        ApplicationRequest typed;
        std::string decode_error;
        if (!decode_request(command_id(request->command_name), payload, request->dry_run != 0, typed, decode_error)) {
            return write_response(
                refused(
                    safety_refusal("command.execute", "invalid_request", "Command request payload is invalid", decode_error, false),
                    "invalid_request",
                    decode_error),
                response);
        }
        return write_response(execute(typed), response);
    }

private:
    ApplicationResult execute(const ApplicationRequest& request)
    {
        if (request.command == CommandId::product_inspect) return handlers::inspect_product(context_, current_command_);
        if (context_.workspace().empty()) {
            return refused(
                safety_refusal("command.execute", "workspace_unavailable", "Workspace root is required", "", true),
                "workspace_unavailable",
                "Workspace root is required");
        }
        if (request.dry_run && writes_persistent_state(request.command)) {
            return refused(
                safety_refusal(
                    "command.execute",
                    "dry_run_write_not_executed",
                    "Dry-run requests never execute data writes",
                    "submit the canonical command with dry_run=false after reviewing its target",
                    true),
                "dry_run_write_not_executed",
                "Dry-run requests never execute data writes");
        }
        switch (request.command) {
        case CommandId::doctor_run: return handlers::run_doctor(context_, std::get<DoctorRequest>(request.payload));
        case CommandId::install_list: return handlers::list_installs(context_);
        case CommandId::install_scan: return handlers::scan_installs(context_, std::get<ScanInstallRefsRequest>(request.payload));
        case CommandId::install_import: return handlers::import_install(context_, std::get<ImportInstallRefRequest>(request.payload));
        case CommandId::install_inspect: return handlers::inspect_install(context_, std::get<InspectInstallRefRequest>(request.payload));
        case CommandId::instance_list: return handlers::list_instances(context_);
        case CommandId::instance_create: return handlers::create_instance(context_, std::get<CreateInstanceRequest>(request.payload));
        case CommandId::launch_plan_build: return handlers::preview_launch(context_, std::get<BuildLaunchPlanRequest>(request.payload), "launch_plan.build");
        case CommandId::run_preview: return handlers::preview_launch(context_, std::get<BuildLaunchPlanRequest>(request.payload), "run.preview");
        case CommandId::run_execute: return handlers::unavailable(context_, "run.execute", "isolation_not_proven", "real Factorio write isolation has not been proven");
        case CommandId::setup_preview: return handlers::preview_setup(context_);
        case CommandId::setup_operation: return handlers::setup_operation(context_, std::get<ServiceOperationRequest>(request.payload));
        case CommandId::utility_operation: return handlers::utility_operation(context_, std::get<ServiceOperationRequest>(request.payload));
        case CommandId::launch_plan_preflight: return handlers::preflight_launch(context_, std::get<BuildLaunchPlanRequest>(request.payload));
        case CommandId::mods_import: return handlers::import_mod(context_, std::get<ImportModRequest>(request.payload));
        case CommandId::modsets_lock: return handlers::lock_modset(context_, std::get<ModsetInstanceRequest>(request.payload));
        case CommandId::modsets_verify: return handlers::verify_modset(context_, std::get<ModsetInstanceRequest>(request.payload));
        case CommandId::modsets_export: return handlers::export_modset(context_, std::get<ExportModsetRequest>(request.payload));
        case CommandId::saves_list: return handlers::list_saves(context_, std::get<ListSavesRequest>(request.payload));
        case CommandId::saves_backup: return handlers::backup_save(context_, std::get<BackupSaveRequest>(request.payload));
        case CommandId::saves_clone: return handlers::clone_save(context_, std::get<CloneSaveRequest>(request.payload));
        case CommandId::instance_export: return handlers::export_instance(context_, std::get<ExportInstanceRequest>(request.payload));
        case CommandId::instance_import: return handlers::import_instance(context_, std::get<ImportInstanceRequest>(request.payload));
        case CommandId::recovery_inspect: return handlers::recovery_inspect(context_);
        case CommandId::recovery_plan: return handlers::recovery_plan(context_, std::get<RecoveryRequest>(request.payload));
        case CommandId::recovery_apply: return handlers::recovery_apply(context_, std::get<RecoveryRequest>(request.payload));
        case CommandId::migration_inspect: return handlers::migration(context_, "workspace.migration.inspect");
        case CommandId::migration_plan: return handlers::migration(context_, "workspace.migration.plan");
        case CommandId::migration_apply: return handlers::migration(context_, "workspace.migration.apply");
        case CommandId::diagnostics_export: return handlers::export_diagnostics(context_, std::get<ExportDiagnosticRequest>(request.payload));
        default:
            return refused(
                safety_refusal("command.execute", "invalid_request", "Unsupported application command", "", false),
                "invalid_request",
                "Unsupported application command");
        }
    }

    int write_response(const ApplicationResult& result, ulk_command_response_v1* response)
    {
        response_json_ = response_envelope(result, current_command_);
        response->status = result.status;
        response->json_payload.data = response_json_.data();
        response->json_payload.size = static_cast<ulk_size>(response_json_.size());
        response->error.struct_size = sizeof(response->error);
        response->error.code = result.status;
        error_message_ = result.error_message;
        response->error.message.data = error_message_.empty() ? nullptr : error_message_.data();
        response->error.message.size = static_cast<ulk_size>(error_message_.size());
        response->error.detail.data = nullptr;
        response->error.detail.size = 0;
        return result.status;
    }

    ApplicationContext context_;
    std::string current_command_;
    std::string response_json_;
    std::string error_message_;
    std::mutex request_mutex_;
};

} // namespace facman::factorio::application

extern "C" void* flb_factorio_application_create(const char* workspace_root)
{
    try {
        return new facman::factorio::application::FactorioApplication(
            workspace_root == nullptr ? "" : workspace_root);
    } catch (...) {
        return nullptr;
    }
}

extern "C" void flb_factorio_application_destroy(void* application)
{
    try {
        delete static_cast<facman::factorio::application::FactorioApplication*>(application);
    } catch (...) {
    }
}

extern "C" int ULK_CALL flb_factorio_application_handle_v1(
    void* application,
    const ulk_command_request_v1* request,
    ulk_command_response_v1* response)
{
    if (response == nullptr || response->struct_size < sizeof(*response)) return ULK_STATUS_INVALID_ARGUMENT;
    response->status = ULK_STATUS_INVALID_ARGUMENT;
    response->json_payload = {};
    response->error = {};
    response->struct_size = sizeof(*response);
    response->error.struct_size = sizeof(response->error);
    response->error.code = ULK_STATUS_INVALID_ARGUMENT;
    if (application == nullptr || request == nullptr || request->struct_size < sizeof(*request)) {
        return ULK_STATUS_INVALID_ARGUMENT;
    }
    try {
        return static_cast<facman::factorio::application::FactorioApplication*>(application)->handle(request, response);
    } catch (const std::bad_alloc&) {
        return facman::factorio::application::write_boundary_error(
            response,
            "allocation_failure",
            "Memory allocation failed while handling the FLB command");
    } catch (...) {
        return facman::factorio::application::write_boundary_error(
            response,
            "cxx_exception_contained",
            "A C++ exception was contained at the FLB boundary");
    }
}
