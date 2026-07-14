// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "handlers/setup.h"

#include "command_result.h"
#include "handlers/unavailable.h"

#ifndef FACMAN_WITH_SETUP
#define FACMAN_WITH_SETUP 0
#endif

#if FACMAN_WITH_SETUP
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_runtime_verify.h"

#include <filesystem>
#endif
#include <string>

namespace facman::factorio::application::handlers {
#if FACMAN_WITH_SETUP
namespace fs = std::filesystem;

namespace {
std::string read_text(const fs::path& path)
{
    facman::platform::StableInputFile input;
    if (!input.open_no_follow(path).ok() || input.size() > 1024U * 1024U) return {};
    std::string text(static_cast<std::size_t>(input.size()), '\0');
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t count = input.read_at(offset, text.data() + static_cast<std::size_t>(offset), static_cast<std::size_t>(input.size() - offset));
        if (count == 0) return {};
        offset += count;
    }
    return input.revalidate().ok() ? text : std::string();
}

std::string toml_value(const std::string& text, const std::string& key)
{
    const std::string marker = key + " = \"";
    const std::size_t start = text.find(marker);
    if (start == std::string::npos) return {};
    const std::size_t value = start + marker.size();
    const std::size_t end = text.find('"', value);
    return end == std::string::npos ? std::string() : text.substr(value, end - value);
}

ApplicationResult verify_package_impl(ApplicationContext& context, const ServiceOperationRequest& request)
{
    const fs::path root = request.path.empty()
        ? facman::platform::path_from_utf8(fl_runtime_package_root())
        : facman::platform::path_from_utf8(request.path);
    const std::string manifest = read_text(root / "manifest" / "package.v1.toml");
    struct ExpectedProfile { const char* id; const char* os; const char* arch; const char* linkage; };
    static const ExpectedProfile profiles[] = {
        {"windows_portable_cli_x64", "windows", "x64", "static_first"},
        {"linux_portable_cli_x64", "linux", "x64", "static_first"},
        {"macos_portable_cli_x64", "macos", "x64", "static_first"},
        {"windows_portable_tui_x64", "windows", "x64", "static_first"},
        {"linux_portable_tui_x64", "linux", "x64", "static_first"},
        {"macos_portable_tui_x64", "macos", "x64", "static_first"},
        {"windows_legacy_winforms_x64", "windows", "x64", "compatibility_bundle"},
        {"macos_legacy_appkit_x64", "macos", "x64", "compatibility_bundle"},
        {"linux_x11_gtk_x64", "linux", "x64", "compatibility_bundle"},
        {"portable_cli_x64", "portable", "x64", "static_first_with_reference_components"},
        {"portable_tui_x64", "portable", "x64", "static_first_with_reference_components"},
    };
    const std::string profile = toml_value(manifest, "profile_id");
    const ExpectedProfile* expected = nullptr;
    for (const ExpectedProfile& candidate : profiles) {
        if (profile == candidate.id) expected = &candidate;
    }
    if (expected == nullptr) {
        return refused(
            safety_refusal("package.verify", "package_profile_unsupported", "Unknown built package profile", profile, false),
            "package_profile_unsupported",
            "Unknown built package profile");
    }
    PackageVerifyRequest verify_request;
    verify_request.package_root = root;
    verify_request.target_os = expected->os;
    verify_request.target_arch = expected->arch;
    verify_request.linkage_model = expected->linkage;
    auto verification = context.setup().verify_package(verify_request);
    if (!verification) return unavailable(context, "package.verify", verification.error().code, verification.error().message);
    ApplicationResult result;
    result.status = verification.value().verified ? ULK_STATUS_OK : ULK_STATUS_ERROR;
    if (!verification.value().verified) {
        result.error_code = "package_verification_failed";
        result.error_message = "Package verification failed";
    }
    facman::core::json::ObjectBuilder output;
    output.add_string("schema", "facman.package_verify.v1");
    output.add_string("status", verification.value().verified ? "pass" : "error");
    output.add_string("integrity", verification.value().verified ? "sha256_consistent" : "failed");
    output.add_string("authenticity", verification.value().authenticity.empty()
        ? "not_proven_unsigned" : verification.value().authenticity);
    output.add_unsigned_integer("files_verified", verification.value().files_verified);
    output.add_string("detail", verification.value().verified
        ? "verified by Universal Setup; publisher authenticity is not proven"
        : verification.value().detail);
    result.output = output.serialize();
    return result;
}
}
#endif

ApplicationResult preview_setup(ApplicationContext& context)
{
    return unavailable(context, "setup.preview", "setup_unavailable", "Universal Setup preview is unavailable in this application configuration");
}

ApplicationResult verify_package(ApplicationContext& context, const ServiceOperationRequest& request)
{
#if FACMAN_WITH_SETUP
    return verify_package_impl(context, request);
#else
    (void)request;
    return unavailable(context, "package.verify", "setup_unavailable", "Universal Setup support is disabled in this build");
#endif
}

ApplicationResult verify_install(ApplicationContext& context, const ServiceOperationRequest& request)
{
#if FACMAN_WITH_SETUP
    auto provider = context.setup().verify_install(request.id);
    if (!provider) return unavailable(context, "installs.verify", provider.error().code, provider.error().message);
    return unavailable(context, "installs.verify", provider.value().code, provider.value().reason);
#else
    (void)request;
    return unavailable(context, "installs.verify", "setup_unavailable", "Universal Setup support is disabled in this build");
#endif
}

namespace {
ApplicationResult managed_install_policy(
    ApplicationContext& context,
    const ServiceOperationRequest& request,
    const char* operation)
{
#if FACMAN_WITH_SETUP
    const std::string& install_id = request.install_id.empty() ? request.id : request.install_id;
    auto parsed_id = facman::core::InstallId::parse_legacy(install_id);
    if (!parsed_id) return refused(safety_refusal(operation, parsed_id.error().code, "Install id is invalid", parsed_id.error().message, false), parsed_id.error().code, parsed_id.error().message);
    auto install = context.installs().load(parsed_id.value());
    if (!install) return refused(safety_refusal(operation, "unknown_install", "Install reference is not registered", install_id, true), "unknown_install", "Install reference is not registered");
    std::string action = std::string(operation).substr(9);
    const std::size_t suffix = action.find(".plan");
    if (suffix != std::string::npos) action.erase(suffix);
    if (install.value().ownership == "managed") {
        return unavailable(
            context,
            operation,
            "live_target_acceptance_required",
            "A human M2 live-target acceptance Pass is required before managed " + action + " planning is activated");
    }
    const std::string reason = "setup may not " + action + " " + install.value().ownership + " installs";
    ApplicationResult result;
    result.status = ULK_STATUS_ERROR;
    result.error_code = "ownership_denied";
    result.error_message = reason;
    facman::core::json::ObjectBuilder refusal;
    refusal.add_string("schema", "common.refusal.v1");
    refusal.add_string("code", "ownership_denied");
    refusal.add_string("reason", reason);
    refusal.add_bool("recoverable", true);
    facman::core::json::ObjectBuilder output;
    output.add_string("schema", "factorio.managed_install_refusal.v1");
    output.add_string("operation", std::string(operation).find(".plan") == std::string::npos
        ? action
        : std::string(operation));
    output.add_string("status", "refused");
    output.add_string("setup_authority", "universal-setup");
    output.add_string("setup_command", "policy.inspect");
    output.add_bool("mutates_install", false);
    output.add_string("install_id", install_id);
    output.add_string("ownership", install.value().ownership);
    output.add_object("refusal", refusal);
    result.output = output.serialize();
    return result;
#else
    (void)request;
    return unavailable(context, operation, "setup_unavailable", "Universal Setup support is disabled in this build");
#endif
}

ApplicationResult install_plan_impl(
    ApplicationContext& context,
    const ServiceOperationRequest& request,
    const char* operation)
{
#if FACMAN_WITH_SETUP
    InstallPlanRequest plan_request;
    plan_request.request_id = context.ids().next("setup-plan");
    plan_request.install_id = request.install_id.empty() ? request.id : request.install_id;
    plan_request.created_at = context.clock().now_utc();
    plan_request.version = request.version;
    plan_request.archive = facman::platform::path_from_utf8(request.archive);
    if (!request.target_root.empty()) {
        plan_request.target = facman::platform::path_from_utf8(request.target_root);
    }
    if (plan_request.install_id.empty() || plan_request.target.empty()) {
        FactorioArchiveInspectRequest inspection_request;
        inspection_request.version = plan_request.version;
        inspection_request.archive = plan_request.archive;
        auto inspection = context.setup().inspect_install_archive(inspection_request);
        if (!inspection) {
            return unavailable(
                context,
                operation,
                inspection.error().code,
                inspection.error().message);
        }
        return unavailable(
            context,
            operation,
            "setup_plan_inputs_not_confirmed",
            "The legacy preview does not bind an install identity and operator-selected target");
    }
    auto plan = context.setup().plan_install(plan_request);
    if (!plan) return unavailable(context, operation, plan.error().code, plan.error().message);
    if (!plan.value().inputs_confirmed) {
        return unavailable(
            context,
            operation,
            "setup_plan_inputs_not_confirmed",
            plan.value().archive_inspected && plan.value().product_layout_verified
                ? "The archive passed Universal Setup inspection and the Factorio recipe, but no authoritative target-bound setup plan is available"
                : "Universal Setup did not return a typed confirmation for the requested version, archive, target, and install identity");
    }
    ApplicationResult result;
    result.output = plan.value().provider_response;
    return result;
#else
    (void)request;
    return unavailable(context, operation, "setup_unavailable", "Universal Setup support is disabled in this build");
#endif
}

ApplicationResult live_target_acceptance_required(
    ApplicationContext& context,
    const char* operation)
{
    return unavailable(
        context,
        operation,
        "live_target_acceptance_required",
        "A human M2 live-target acceptance Pass is required before FacMan setup apply is available");
}
}

ApplicationResult repair_install(ApplicationContext& context, const ServiceOperationRequest& request)
{
    return managed_install_policy(context, request, "installs.repair");
}

ApplicationResult plan_repair_install(ApplicationContext& context, const ServiceOperationRequest& request)
{
    return managed_install_policy(context, request, "installs.repair.plan");
}

ApplicationResult apply_repair_install(ApplicationContext& context, const ServiceOperationRequest&)
{
    return live_target_acceptance_required(context, "installs.repair.apply");
}

ApplicationResult plan_move_install(ApplicationContext& context, const ServiceOperationRequest& request)
{
    return managed_install_policy(context, request, "installs.move.plan");
}

ApplicationResult apply_move_install(ApplicationContext& context, const ServiceOperationRequest&)
{
    return live_target_acceptance_required(context, "installs.move.apply");
}

ApplicationResult uninstall_install(ApplicationContext& context, const ServiceOperationRequest& request)
{
    return managed_install_policy(context, request, "installs.uninstall");
}

ApplicationResult plan_uninstall_install(ApplicationContext& context, const ServiceOperationRequest& request)
{
    return managed_install_policy(context, request, "installs.uninstall.plan");
}

ApplicationResult apply_uninstall_install(ApplicationContext& context, const ServiceOperationRequest&)
{
    return live_target_acceptance_required(context, "installs.uninstall.apply");
}

ApplicationResult inspect_install_recovery(ApplicationContext& context, const ServiceOperationRequest&)
{
    return unavailable(
        context,
        "installs.recovery.inspect",
        "live_target_acceptance_required",
        "A human M2 live-target acceptance Pass is required before FacMan setup recovery is activated");
}

ApplicationResult apply_install_recovery(ApplicationContext& context, const ServiceOperationRequest&)
{
    return live_target_acceptance_required(context, "installs.recovery.apply");
}

ApplicationResult install_version(ApplicationContext& context, const ServiceOperationRequest& request)
{
    return install_plan_impl(context, request, "installs.install_version");
}

ApplicationResult plan_install(ApplicationContext& context, const ServiceOperationRequest& request)
{
    return install_plan_impl(context, request, "installs.install.plan");
}

ApplicationResult apply_install(ApplicationContext& context, const ServiceOperationRequest&)
{
    return live_target_acceptance_required(context, "installs.install.apply");
}

bool is_setup_command(CommandId command) noexcept
{
    switch (command) {
    case CommandId::setup_preview:
    case CommandId::package_verify:
    case CommandId::installs_install_plan:
    case CommandId::installs_install_apply:
    case CommandId::installs_install_version:
    case CommandId::installs_verify:
    case CommandId::installs_repair_plan:
    case CommandId::installs_repair_apply:
    case CommandId::installs_repair:
    case CommandId::installs_move_plan:
    case CommandId::installs_move_apply:
    case CommandId::installs_uninstall_plan:
    case CommandId::installs_uninstall_apply:
    case CommandId::installs_uninstall:
    case CommandId::installs_recovery_inspect:
    case CommandId::installs_recovery_apply:
        return true;
    default:
        return false;
    }
}

ApplicationResult dispatch_setup(ApplicationContext& context, const ApplicationRequest& request)
{
    if (request.command == CommandId::setup_preview) return preview_setup(context);
    const auto& operation = std::get<ServiceOperationRequest>(request.payload);
    switch (request.command) {
    case CommandId::package_verify: return verify_package(context, operation);
    case CommandId::installs_install_plan: return plan_install(context, operation);
    case CommandId::installs_install_apply: return apply_install(context, operation);
    case CommandId::installs_install_version: return install_version(context, operation);
    case CommandId::installs_verify: return verify_install(context, operation);
    case CommandId::installs_repair_plan: return plan_repair_install(context, operation);
    case CommandId::installs_repair_apply: return apply_repair_install(context, operation);
    case CommandId::installs_repair: return repair_install(context, operation);
    case CommandId::installs_move_plan: return plan_move_install(context, operation);
    case CommandId::installs_move_apply: return apply_move_install(context, operation);
    case CommandId::installs_uninstall_plan: return plan_uninstall_install(context, operation);
    case CommandId::installs_uninstall_apply: return apply_uninstall_install(context, operation);
    case CommandId::installs_uninstall: return uninstall_install(context, operation);
    case CommandId::installs_recovery_inspect: return inspect_install_recovery(context, operation);
    case CommandId::installs_recovery_apply: return apply_install_recovery(context, operation);
    default:
        return unavailable(context, "setup.dispatch", "invalid_request", "Command is not a setup workflow");
    }
}

} // namespace facman::factorio::application::handlers
