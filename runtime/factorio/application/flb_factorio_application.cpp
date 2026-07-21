// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "flb_factorio_application.h"
#include "application_context.h"
#include "application_types.h"
#include "command_dispatch.h"
#include "command_admission.h"
#include "command_result.h"
#include "handlers/diagnostics.h"
#include "handlers/doctor.h"
#include "handlers/instances.h"
#include "handlers/intelligence.h"
#include "handlers/mods.h"
#include "handlers/modsets.h"
#include "handlers/product.h"
#include "handlers/preferences.h"
#include "handlers/profiles.h"
#include "handlers/recovery.h"
#include "handlers/saves.h"
#include "handlers/setup.h"
#include "handlers/snapshots.h"
#include "handlers/unavailable.h"
#include "handlers/utility.h"
#include "modules/installation_module.h"
#include "modules/instance_module.h"
#include "modules/launch_module.h"
#include "fl_json_boundary.h"
#include "fl_file_io.h"
#include <filesystem>
#include <mutex>
#include <string>
#include <variant>
namespace facman::factorio::application {
namespace {
const char* request_decode_refusal_code(const std::string& detail) noexcept
{
    return detail.rfind("invalid_identifier:", 0) == 0
        ? "invalid_identifier"
        : "invalid_request";
}
int write_boundary_error(ulk_command_response_v1* response, const char* code, const char* message) noexcept
{
    const char* payload = facman::core::json::boundary::contained_exception_response;
    if (response == nullptr || response->struct_size < sizeof(*response)) return ULK_STATUS_INVALID_ARGUMENT;
    response->struct_size = sizeof(*response);
    response->status = ULK_STATUS_ERROR;
    response->json_payload.data = payload;
    response->json_payload.size = std::char_traits<char>::length(payload);
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
        : context_(workspace_root.empty()
              ? std::filesystem::path()
              : facman::platform::path_from_utf8(workspace_root))
    {}
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
            const char* refusal_code = request_decode_refusal_code(decode_error);
            return write_response(
                refused(
                    safety_refusal("command.execute", refusal_code, "Command request payload is invalid", decode_error, false),
                    refusal_code,
                    decode_error,
                    facman::core::OutcomeKind::invalid_argument),
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
        const CommandAdmissionDecision admission = admit_command(context_.configuration(), request.command);
        if (handlers::is_setup_command(request.command)) {
            if (!admission.admitted) return handlers::unavailable(context_, current_command_, admission.code, admission.reason);
            return handlers::dispatch_setup(context_, request);
        }
        if (launch_module_.handles(request.command)) {
            return launch_module_.execute(context_, request, admission);
        }
        if (!admission.admitted && admission.code == "network_forbidden") {
            return handlers::refuse_mod_portal(context_, std::get<ServiceOperationRequest>(request.payload));
        }
        if (!admission.admitted) {
            return handlers::unavailable(context_, current_command_, admission.code, admission.reason);
        }
        if (installation_module_.handles(request.command)) {
            return installation_module_.execute(context_, request);
        }
        if (instance_module_.handles(request.command)) {
            return instance_module_.execute(context_, request);
        }
        switch (request.command) {
        case CommandId::workspace_status: return handlers::workspace_status(context_);
        case CommandId::workspace_paths: return handlers::workspace_paths(context_);
        case CommandId::preferences_inspect: return handlers::inspect_preferences(context_);
        case CommandId::preferences_validate: return handlers::validate_preferences(context_, std::get<PreferencesRequest>(request.payload));
        case CommandId::preferences_plan: return handlers::plan_preferences(context_, std::get<PreferencesRequest>(request.payload));
        case CommandId::preferences_apply: return handlers::apply_preferences(context_, std::get<PreferencesRequest>(request.payload));
        case CommandId::preferences_reset_plan: return handlers::plan_preferences_reset(context_);
        case CommandId::preferences_reset_apply: return handlers::apply_preferences_reset(context_);
        case CommandId::capabilities_inspect: return handlers::capabilities_inspect(context_);
        case CommandId::onboarding_plan: return handlers::onboarding_plan(context_, std::get<OnboardingPlanRequest>(request.payload));
        case CommandId::doctor_explain: return handlers::doctor_explain(context_);
        case CommandId::launch_plan_explain: return handlers::launch_plan_explain(context_, std::get<ExplainInstanceRequest>(request.payload));
        case CommandId::doctor_run: return handlers::run_doctor(context_, std::get<DoctorRequest>(request.payload));
        case CommandId::instance_list: return handlers::list_instances(context_);
        case CommandId::instance_create: return handlers::create_instance(context_, std::get<CreateInstanceRequest>(request.payload));
        case CommandId::instances_inspect: case CommandId::instances_verify: case CommandId::instances_diff:
        case CommandId::instances_clone: case CommandId::instances_rename: case CommandId::instances_archive:
        case CommandId::instances_restore: return handlers::dispatch_instance_lifecycle(context_, request);
        case CommandId::snapshots_create: case CommandId::snapshots_list: case CommandId::snapshots_inspect:
        case CommandId::snapshots_verify: case CommandId::snapshots_diff: case CommandId::snapshots_restore:
        case CommandId::snapshots_retention_plan: case CommandId::snapshots_retention_apply:
            return handlers::dispatch_snapshots(context_, request);
        case CommandId::templates_list: case CommandId::templates_inspect: case CommandId::templates_validate:
        case CommandId::profiles_list: case CommandId::profiles_inspect: case CommandId::profiles_create:
        case CommandId::profiles_clone: case CommandId::profiles_diff: case CommandId::profiles_plan: case CommandId::profiles_apply:
        case CommandId::profiles_archive: return handlers::dispatch_profiles(context_, request);
        case CommandId::mods_search: case CommandId::mods_install:
        case CommandId::mods_update: return handlers::refuse_mod_portal(context_, std::get<ServiceOperationRequest>(request.payload));
        case CommandId::servers_list: return handlers::list_servers(context_);
        case CommandId::servers_create: return handlers::create_server(context_, std::get<ServiceOperationRequest>(request.payload));
        case CommandId::servers_inspect: case CommandId::servers_validate: case CommandId::servers_plan: case CommandId::servers_diff: case CommandId::servers_export: return handlers::dispatch_server_plan(context_, request);
        case CommandId::servers_start: case CommandId::servers_stop:
        case CommandId::servers_rcon: return handlers::control_server(context_, std::get<ServiceOperationRequest>(request.payload));
        case CommandId::diagnostics_redact: return handlers::redact_diagnostics(context_, std::get<ServiceOperationRequest>(request.payload));
        case CommandId::dev_bug_report: return handlers::create_bug_report(context_);
        case CommandId::dev_dump_data: case CommandId::dev_dump_icons:
        case CommandId::dev_benchmark:
        case CommandId::dev_instrument_mod: return handlers::refuse_dev_execution(context_, std::get<ServiceOperationRequest>(request.payload));
        case CommandId::mods_import: return handlers::import_mod(context_, std::get<ImportModRequest>(request.payload));
        case CommandId::mods_list: case CommandId::mods_inspect: case CommandId::mods_verify: case CommandId::mods_index: case CommandId::mods_explain: return handlers::dispatch_mod_inventory(context_, request);
        case CommandId::modsets_lock: return handlers::lock_modset(context_, std::get<ModsetInstanceRequest>(request.payload));
        case CommandId::modsets_verify: return handlers::verify_modset(context_, std::get<ModsetInstanceRequest>(request.payload));
        case CommandId::modsets_export: return handlers::export_modset(context_, std::get<ExportModsetRequest>(request.payload));
        case CommandId::modsets_plan: case CommandId::modsets_diff: case CommandId::modsets_explain: case CommandId::modsets_apply: case CommandId::modsets_rollback: return handlers::dispatch_modset_solver(context_, request);
        case CommandId::saves_list: return handlers::list_saves(context_, std::get<ListSavesRequest>(request.payload));
        case CommandId::saves_backup: return handlers::backup_save(context_, std::get<BackupSaveRequest>(request.payload));
        case CommandId::saves_clone: return handlers::clone_save(context_, std::get<CloneSaveRequest>(request.payload));
        case CommandId::saves_index: case CommandId::saves_inspect: case CommandId::saves_verify: case CommandId::saves_associate:
        case CommandId::saves_diff: case CommandId::saves_retention_plan: case CommandId::saves_retention_apply: return handlers::dispatch_save_index(context_, request);
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
    InstallationApplicationModule installation_module_;
    InstanceApplicationModule instance_module_;
    LaunchApplicationModule launch_module_;
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
