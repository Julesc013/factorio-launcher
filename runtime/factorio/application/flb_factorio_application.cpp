// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "flb_factorio_application.h"
#include "application_context.h"
#include "application_types.h"
#include "command_dispatch.h"
#include "command_admission.h"
#include "command_result.h"
#include "handlers/unavailable.h"
#include "modules/application_module.h"
#include "modules/content_module.h"
#include "modules/diagnostics_module.h"
#include "modules/installation_module.h"
#include "modules/instance_module.h"
#include "modules/launch_module.h"
#include "modules/profile_module.h"
#include "modules/presentation_module.h"
#include "modules/recovery_module.h"
#include "modules/setup_module.h"
#include "modules/workspace_module.h"
#include "fl_json_boundary.h"
#include "fl_file_io.h"
#include <array>
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
              : facman::platform::path_from_utf8(workspace_root)),
          modules_{
              &workspace_module_,
              &setup_module_,
              &installation_module_,
              &instance_module_,
              &profile_module_,
              &presentation_module_,
              &content_module_,
              &recovery_module_,
              &diagnostics_module_,
              &launch_module_}
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
    const ApplicationModule* module_for(CommandId command) const noexcept
    {
        for (const ApplicationModule* module : modules_) {
            if (module->handles(command)) return module;
        }
        return nullptr;
    }
    ApplicationResult execute(const ApplicationRequest& request)
    {
        const ApplicationModule* module = module_for(request.command);
        if (module == nullptr) {
            return refused(
                safety_refusal("command.execute", "invalid_request", "Unsupported application command", "", false),
                "invalid_request",
                "Unsupported application command");
        }
        if (module->requires_workspace(request.command) && context_.workspace().empty()) {
            return refused(
                safety_refusal("command.execute", "workspace_unavailable", "Workspace root is required", "", true),
                "workspace_unavailable",
                "Workspace root is required");
        }
        if (request.dry_run && requires_non_dry_run(request.command)) {
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
        if (!admission.admitted && denied_admission_disposition(
                request.command, admission) == DeniedAdmissionDisposition::reject)
            return handlers::unavailable(context_, current_command_, admission.code, admission.reason);
        return module->execute(context_, request, admission, current_command_);
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
    WorkspaceApplicationModule workspace_module_;
    SetupApplicationModule setup_module_;
    InstallationApplicationModule installation_module_;
    InstanceApplicationModule instance_module_;
    ProfileApplicationModule profile_module_;
    PresentationApplicationModule presentation_module_;
    ContentApplicationModule content_module_;
    RecoveryApplicationModule recovery_module_;
    DiagnosticsApplicationModule diagnostics_module_;
    LaunchApplicationModule launch_module_;
    std::array<const ApplicationModule*, 10> modules_;
    std::string current_command_, response_json_, error_message_;
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
