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
#include "fl_sha256.h"
#include "fl_transaction.h"
#include "flb_factorio_discovery.h"

#include <filesystem>
#include <cstdlib>
#endif
#include <string>

namespace facman::factorio::application::handlers {
#if FACMAN_WITH_SETUP
namespace fs = std::filesystem;

namespace {
std::string managed_uninstall_context(
    const UninstallPlanRequest& plan,
    const ServiceOperationRequest& request,
    const std::string& target,
    const std::string& pre_record_digest)
{
    facman::core::json::ObjectBuilder plan_request;
    plan_request.add_string("schema", "usk.uninstall_plan_request.v1");
    plan_request.add_string("request_id", plan.request_id);
    plan_request.add_string("plan_id", plan.plan_id);
    plan_request.add_string("install_id", plan.install_id);
    plan_request.add_string("created_at", plan.created_at);
    facman::core::json::ObjectBuilder document;
    document.add_string("schema", "facman.managed_uninstall_coordinator.v1");
    document.add_object("plan_request", plan_request);
    document.add_string("reviewed_plan_id", request.plan_id);
    document.add_string("reviewed_plan_digest", request.plan_digest);
    document.add_string("transaction_id", request.transaction_id);
    document.add_string("applied_at", request.applied_at);
    document.add_string("target_root", target);
    document.add_string("pre_record_sha256", pre_record_digest);
    document.add_string("phase", "provider_entry_pending");
    return document.serialize();
}

std::string uninstalled_install_record(
    const facman::workspace::InstallRecord& record,
    const UninstallReport& report)
{
    facman::factorio::discovery::InstallRef terminal;
    terminal.install_id = record.id.str();
    terminal.provider_id = record.provider_id;
    terminal.root = record.root;
    terminal.executable = record.executable;
    terminal.version = record.version;
    terminal.ownership = "managed";
    terminal.source = "universal-setup";
    terminal.source_ref = "uninstall-report:" + report.report_id + ":" + report.report_digest;
    terminal.platform = record.platform;
    terminal.distribution_origin = record.distribution_origin;
    terminal.platform_integration = record.platform_integration;
    terminal.strict_isolation_eligibility = record.strict_isolation_eligibility;
    terminal.external_state_domains = record.external_state_domains;
    terminal.setup_state_ref = report.setup_state_ref;
    terminal.lifecycle_status = report.lifecycle_status;
    terminal.last_verification_identity = report.last_verification_identity;
    terminal.state_revision = report.state_revision;
    terminal.verification_status = report.verification_status;
    return facman::factorio::discovery::install_ref_json(terminal);
}

bool uninstall_refusal_proves_no_provider_effect(const std::string& code)
{
    return code == "stale_plan" || code == "foreign_content_review_required" ||
        code == "invalid_argument" || code == "unknown_install" ||
        code == "setup_uninstall_apply_input_invalid" ||
        code == "setup_installed_state_inspection_refused" ||
        code == "setup_installed_state_response_invalid";
}

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
    std::error_code stage_error;
    const bool canonical_stage = fs::is_regular_file(
        root / "manifest" / "stage.v1.json", stage_error) && !stage_error;
    if (canonical_stage) {
        const facman::package::RuntimePackageEvidence verification = request.path.empty()
            ? facman::package::inspect_runtime_package()
            : facman::package::inspect_package(root, root / "bin" / "facman.exe");
        ApplicationResult result;
        result.status = verification.verified ? ULK_STATUS_OK : ULK_STATUS_ERROR;
        if (!verification.verified) {
            result.error_code = "package_verification_failed";
            result.error_message = "Package verification failed";
        }
        facman::core::json::ObjectBuilder output;
        output.add_string("schema", "facman.package_verify.v1");
        output.add_string("status", verification.verified ? "pass" : "error");
        output.add_string(
            "integrity",
            verification.verified ? "sha256_consistent" : "failed");
        output.add_string("authenticity", "not_proven_unsigned");
        output.add_unsigned_integer("files_verified", verification.files_verified);
        output.add_string("detail", verification.detail);
        result.output = output.serialize();
        return result;
    }
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
        {"windows_product_x64", "windows", "x64", "compatibility_bundle"},
        {"macos_product_x64", "macos", "x64", "static_terminal_process_boundary"},
        {"linux_product_x64", "linux", "x64", "static_terminal_process_boundary"},
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
bool managed_plan_lifecycle_eligible(const std::string& lifecycle)
{
    return lifecycle == "active" || lifecycle == "verification_failed" ||
        lifecycle == "recovery_required";
}

ApplicationResult managed_uninstall_plan(
    ApplicationContext& context,
    const ServiceOperationRequest& request)
{
#if FACMAN_WITH_SETUP
    const std::string& install_id = request.install_id.empty() ? request.id : request.install_id;
    auto parsed_id = facman::core::InstallId::parse_legacy(install_id);
    if (!parsed_id) return refused(
        safety_refusal("installs.uninstall.plan", parsed_id.error().code, "Install id is invalid", parsed_id.error().message, false),
        parsed_id.error().code, parsed_id.error().message, parsed_id.error().kind);
    auto install = context.installs().load(parsed_id.value());
    if (!install) return refused(
        safety_refusal("installs.uninstall.plan", "unknown_install", "Install reference is not registered", install_id, true),
        "unknown_install", "Install reference is not registered");
    const auto& record = install.value();
    if (record.ownership != "managed") return refused(
        safety_refusal("installs.uninstall.plan", "ownership_denied", "Uninstall planning is available only for registered managed installs", record.ownership, true),
        "ownership_denied", "Uninstall planning is available only for registered managed installs");
    if (record.provider_id != "universal-setup" || record.source != "universal-setup") return refused(
        safety_refusal("installs.uninstall.plan", "managed_install_provider_mismatch", "Managed uninstall planning requires a Universal Setup managed record", record.provider_id + ":" + record.source, true),
        "managed_install_provider_mismatch", "Managed uninstall planning requires a Universal Setup managed record");
    if (!managed_plan_lifecycle_eligible(record.lifecycle_status)) {
        const std::string lifecycle = record.lifecycle_status.empty()
            ? "unknown"
            : record.lifecycle_status;
        constexpr const char* message =
            "Uninstall planning requires an active, verification_failed, or "
            "recovery_required managed install";
        return refused(
            safety_refusal(
                "installs.uninstall.plan",
                "uninstall_lifecycle_ineligible",
                message,
                lifecycle,
                true),
            "uninstall_lifecycle_ineligible",
            message);
    }
    if (record.root.empty() || record.setup_state_ref.empty() ||
        record.last_verification_identity.empty() || record.state_revision.empty()) return refused(
        safety_refusal("installs.uninstall.plan", "managed_install_evidence_incomplete", "Managed uninstall planning requires target, setup, verification, and revision evidence", install_id, true),
        "managed_install_evidence_incomplete", "Managed uninstall planning requires target, setup, verification, and revision evidence");
    UninstallPlanRequest plan_request;
    plan_request.plan_id = context.ids().next("uninstall-plan");
    plan_request.request_id = plan_request.plan_id;
    plan_request.install_id = record.id.str();
    plan_request.created_at = context.clock().now_utc();
    plan_request.target = record.root;
    plan_request.setup_state_ref = record.setup_state_ref;
    plan_request.last_verification_identity = record.last_verification_identity;
    plan_request.state_revision = record.state_revision;
    plan_request.lifecycle_status = record.lifecycle_status;
    auto plan = context.setup().plan_uninstall(plan_request);
    if (!plan) return unavailable(
        context, "installs.uninstall.plan", plan.error().code, plan.error().message);
    ApplicationResult result;
    result.output = plan.value().provider_response;
    return result;
#else
    (void)request;
    return unavailable(context, "installs.uninstall.plan", "setup_unavailable", "Universal Setup support is disabled in this build");
#endif
}

ApplicationResult managed_install_policy(
    ApplicationContext& context,
    const ServiceOperationRequest& request,
    const char* operation)
{
#if FACMAN_WITH_SETUP
    const std::string& install_id = request.install_id.empty() ? request.id : request.install_id;
    auto parsed_id = facman::core::InstallId::parse_legacy(install_id);
    if (!parsed_id) return refused(safety_refusal(operation, parsed_id.error().code, "Install id is invalid", parsed_id.error().message, false), parsed_id.error().code, parsed_id.error().message, parsed_id.error().kind);
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
            "Managed-target " + action + " planning is unavailable until its separate live-target policy gate passes");
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
        "Managed-target setup apply is unavailable until its separate live-target policy gate passes");
}
}

ApplicationResult repair_install(ApplicationContext& context, const ServiceOperationRequest& request)
{
    return managed_install_policy(context, request, "installs.repair");
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
    return managed_uninstall_plan(context, request);
}

ApplicationResult apply_uninstall_install(ApplicationContext& context, const ServiceOperationRequest& request)
{
#if FACMAN_WITH_SETUP
    if (!valid_utc_seconds(request.plan_created_at) || !valid_utc_seconds(request.applied_at) ||
        request.applied_at <= request.plan_created_at) return refused(
        safety_refusal("installs.uninstall.apply", "invalid_timestamp",
            "Uninstall apply timestamps must be valid UTC seconds and applied_at must follow plan_created_at",
            "plan_created_at/applied_at", false),
        "invalid_timestamp",
        "Uninstall apply timestamps must be valid UTC seconds and applied_at must follow plan_created_at");
    auto parsed_transaction = facman::core::TransactionId::parse(request.transaction_id);
    if (!parsed_transaction) return refused(
        safety_refusal("installs.uninstall.apply", parsed_transaction.error().code,
            "Transaction id is not portable", parsed_transaction.error().message, false),
        parsed_transaction.error().code, parsed_transaction.error().message, parsed_transaction.error().kind);
    auto parsed_id = facman::core::InstallId::parse_legacy(request.install_id);
    if (!parsed_id) return refused(
        safety_refusal("installs.uninstall.apply", parsed_id.error().code, "Install id is invalid", parsed_id.error().message, false),
        parsed_id.error().code, parsed_id.error().message, parsed_id.error().kind);
    auto install = context.installs().load(parsed_id.value());
    if (!install) return refused(
        safety_refusal("installs.uninstall.apply", "unknown_install", "Install reference is not registered", request.install_id, true),
        "unknown_install", "Install reference is not registered");
    const auto& record = install.value();
    if (record.ownership != "managed" || record.provider_id != "universal-setup" ||
        record.source != "universal-setup" || !managed_plan_lifecycle_eligible(record.lifecycle_status) ||
        record.root.empty() || record.setup_state_ref.empty() || record.last_verification_identity.empty() ||
        record.state_revision.empty()) return refused(
        safety_refusal("installs.uninstall.apply", "managed_install_evidence_incomplete", "Managed uninstall apply requires an eligible Universal Setup managed install", request.install_id, true),
        "managed_install_evidence_incomplete", "Managed uninstall apply requires an eligible Universal Setup managed install");
    const std::string record_text = read_text(record.source_path);
    if (record_text.empty()) return refused(
        safety_refusal("installs.uninstall.apply", "workspace_record_read_failed", "Managed install record cannot be read stably", record.source_path.string(), true),
        "workspace_record_read_failed", "Managed install record cannot be read stably");
    UninstallPlanRequest plan;
    plan.request_id = request.plan_id;
    plan.plan_id = request.plan_id;
    plan.install_id = record.id.str();
    plan.created_at = request.plan_created_at;
    plan.target = record.root;
    plan.setup_state_ref = record.setup_state_ref;
    plan.last_verification_identity = record.last_verification_identity;
    plan.state_revision = record.state_revision;
    plan.lifecycle_status = record.lifecycle_status;
    facman::transaction::Record journal_record;
    journal_record.transaction_id = parsed_transaction.value().str();
    journal_record.command_id = "installs.uninstall.apply";
    journal_record.target = record.root;
    journal_record.sources = {record.source_path};
    journal_record.commit_strategy = "provider_uninstall_then_durable_install_reference_replacement";
    journal_record.operation_context = managed_uninstall_context(plan, request,
        facman::platform::path_to_utf8(record.root), facman::base::sha256_hex_bytes(
            reinterpret_cast<const unsigned char*>(record_text.data()), record_text.size()));
    auto started = facman::transaction::TransactionSession::begin(context.workspace(), std::move(journal_record));
    if (!started) return refused(
        safety_refusal("installs.uninstall.apply", "recovery_write_refused", "Uninstall coordinator journal could not be prepared", started.error().message, true),
        "recovery_write_refused", started.error().message);
    auto session = started.take_value();
    if (!session.validated("reviewed_plan_bound") || !session.planned("exact_plan_request_persisted") ||
        !session.staged("provider_entry_prepared") || !session.verified("current_record_bound") ||
        !session.committing("provider_entry_started")) return refused(
        safety_refusal("installs.uninstall.apply", "recovery_write_refused", "Uninstall coordinator journal could not enter provider phase", session.detail(), true),
        "recovery_write_refused", session.detail());
    UninstallApplyRequest apply;
    apply.plan_request = plan;
    apply.reviewed_plan_id = request.plan_id;
    apply.reviewed_plan_digest = request.plan_digest;
    apply.transaction_id = request.transaction_id;
    apply.applied_at = request.applied_at;
    apply.confirmation = request.confirmation;
    auto report = context.setup().apply_uninstall(apply);
    if (!report) {
        if (uninstall_refusal_proves_no_provider_effect(report.error().code)) {
            if (!session.refused(report.error().code + ": " + report.error().message)) {
                return refused(safety_refusal("installs.uninstall.apply", "recovery_write_refused",
                    "Provider refusal could not be durably closed", session.detail(), true),
                    "recovery_write_refused", session.detail(),
                    facman::core::OutcomeKind::recovery_required);
            }
            return refused(safety_refusal("installs.uninstall.apply", report.error().code,
                "Universal Setup refused managed uninstall before mutation", report.error().message, true),
                report.error().code, report.error().message, report.error().kind);
        }
        session.failed(report.error().code + ": " + report.error().message);
        return refused(safety_refusal("installs.uninstall.apply", "transaction_recovery_required",
            "Universal Setup uninstall outcome requires recovery", report.error().message, false),
            "transaction_recovery_required", report.error().code + ": " + report.error().message,
            facman::core::OutcomeKind::recovery_required);
    }
    const char* injected = std::getenv("FACMAN_TEST_UNINSTALL_INTERRUPT_AFTER_PROVIDER");
    if (injected != nullptr && std::string(injected) == "1") return refused(
        safety_refusal("installs.uninstall.apply", "transaction_recovery_required",
            "Injected interruption after provider uninstall", request.transaction_id, false),
        "transaction_recovery_required", "Injected interruption after provider uninstall",
        facman::core::OutcomeKind::recovery_required);
    const std::string pre_record_digest = facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(record_text.data()), record_text.size());
    auto replaced = context.installs().replace(
        record, pre_record_digest, uninstalled_install_record(record, report.value()));
    if (!replaced || !session.committed("uninstalled_reference_projected") || !session.complete()) return refused(
        safety_refusal("installs.uninstall.apply", "transaction_recovery_required", "Uninstall provider result requires recovery before terminal projection is durable", replaced ? session.detail() : replaced.error().message, false),
        "transaction_recovery_required", replaced ? session.detail() : replaced.error().message,
        facman::core::OutcomeKind::recovery_required);
    ApplicationResult result;
    result.output = report.value().provider_response;
    return result;
#else
    (void)request;
    return unavailable(context, "installs.uninstall.apply", "setup_unavailable", "Universal Setup support is disabled in this build");
#endif
}

ApplicationResult inspect_install_recovery(ApplicationContext& context, const ServiceOperationRequest&)
{
    return unavailable(
        context,
        "installs.recovery.inspect",
        "live_target_acceptance_required",
        "Managed-target recovery is unavailable until its separate live-target policy gate passes");
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
