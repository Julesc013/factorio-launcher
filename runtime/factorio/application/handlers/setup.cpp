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
#include "fl_local_operation_lock.h"
#include "fl_path_safety.h"
#include "fl_runtime_verify.h"
#include "fl_sha256.h"
#include "fl_transaction.h"
#include "flb_factorio_discovery.h"

#include <filesystem>
#include <algorithm>
#include <cstdlib>
#include <memory>
#endif
#include <string>

namespace facman::factorio::application::handlers {
#if FACMAN_WITH_SETUP
namespace fs = std::filesystem;

namespace {
std::string digest_text(const std::string& value);

std::string managed_repair_result(
    const ServiceOperationRequest& request,
    const RepairPlan& plan,
    const RepairReport& report)
{
    facman::core::json::ObjectBuilder document;
    document.add_string("schema", "factorio.managed_repair_apply_result.v1");
    document.add_string("status", "completed");
    document.add_string("disposition", "applied");
    document.add_string("install_id", request.install_id);
    document.add_string("plan_id", request.plan_id);
    document.add_string("plan_digest", request.plan_digest);
    document.add_string("provider_plan_digest", plan.provider_plan_digest);
    document.add_string("transaction_id", request.transaction_id);
    document.add_string("completed_at", request.applied_at);
    document.add_string("installed_state_digest", report.installed_state_digest);
    document.add_string("setup_state_ref", report.setup_state_ref);
    document.add_string("last_verification_identity", report.last_verification_identity);
    document.add_string("state_revision", report.state_revision);
    document.add_string("verification_status", report.verification_status);
    return document.serialize();
}

bool repair_refusal_proves_no_provider_effect(const std::string& code)
{
    return code == "stale_plan" || code == "source_drift" || code == "invalid_argument" ||
        code == "unknown_install" ||
        code == "setup_repair_apply_input_invalid" ||
        code == "setup_installed_state_inspection_refused" ||
        code == "setup_installed_state_response_invalid";
}

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
    document.add_string("schema", "facman.managed_uninstall_coordinator.v2");
    document.add_object("plan_request", plan_request);
    document.add_string("reviewed_plan_id", request.plan_id);
    document.add_string("reviewed_plan_digest", request.plan_digest);
    document.add_string("transaction_id", request.transaction_id);
    document.add_string("applied_at", request.applied_at);
    document.add_string("target_root", target);
    document.add_string("pre_record_sha256", pre_record_digest);
    document.add_string("pre_setup_state_ref", plan.setup_state_ref);
    document.add_string("pre_last_verification_identity", plan.last_verification_identity);
    document.add_string("pre_state_revision", plan.state_revision);
    document.add_string("pre_lifecycle_status", plan.lifecycle_status);
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
    terminal.source_ref = "uninstall-state:" + report.state_revision.substr(
        0U, report.state_revision.find(':')) + ":" + report.installed_state_digest;
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

std::string digest_text(const std::string& value)
{
    return facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(value.data()), value.size());
}

std::string checkpointed_uninstall_context(
    const ManagedUninstallCoordinator& context,
    const UninstallRecoveryInspection& inspection,
    const std::string& recovery_plan_id,
    const std::string& recovery_plan_digest,
    const std::string& projected_record_sha256)
{
    facman::core::json::ObjectBuilder plan_request;
    plan_request.add_string("schema", "usk.uninstall_plan_request.v1");
    plan_request.add_string("request_id", context.request_id);
    plan_request.add_string("plan_id", context.plan_id);
    plan_request.add_string("install_id", context.install_id);
    plan_request.add_string("created_at", context.plan_created_at);
    facman::core::json::ObjectBuilder document;
    document.add_string("schema", "facman.managed_uninstall_coordinator.v2");
    document.add_object("plan_request", plan_request);
    document.add_string("reviewed_plan_id", context.plan_id);
    document.add_string("reviewed_plan_digest", context.reviewed_plan_digest);
    document.add_string("transaction_id", context.transaction_id);
    document.add_string("applied_at", context.applied_at);
    document.add_string("target_root", context.target_root);
    document.add_string("pre_record_sha256", context.pre_record_sha256);
    document.add_string("pre_setup_state_ref", context.pre_setup_state_ref);
    document.add_string("pre_last_verification_identity", context.pre_last_verification_identity);
    document.add_string("pre_state_revision", context.pre_state_revision);
    document.add_string("pre_lifecycle_status", context.pre_lifecycle_status);
    document.add_string("phase", "terminal_projection_prepared");
    document.add_string("recovery_plan_id", recovery_plan_id);
    document.add_string("recovery_plan_digest", recovery_plan_digest);
    document.add_string("classification", inspection.classification);
    document.add_string("provider_journal_snapshot_sha256", inspection.provider_journal_snapshot_sha256);
    document.add_string("provider_installed_state_sha256", inspection.provider_installed_state_digest);
    document.add_string("projected_record_sha256", projected_record_sha256);
    return document.serialize();
}

class ManagedUninstallLease {
public:
    static facman::core::Result<std::unique_ptr<ManagedUninstallLease>> acquire(
        const fs::path& workspace,
        const std::string& transaction_id,
        bool adopt_existing)
    {
        auto parsed = facman::core::TransactionId::parse(transaction_id);
        if (!parsed) return facman::core::Result<std::unique_ptr<ManagedUninstallLease>>::failure(parsed.error());
        auto journal = facman::workspace::WorkspaceLayout(workspace).transaction_journal(parsed.value());
        if (!journal) return facman::core::Result<std::unique_ptr<ManagedUninstallLease>>::failure(journal.error());
        auto lease = std::unique_ptr<ManagedUninstallLease>(new ManagedUninstallLease());
        lease->path_ = journal.value();
        lease->path_ += ".recovery.lock";
        auto acquired = lease->lock_.create(lease->path_);
        if (acquired.code == facman::base::StableLockCode::exists && adopt_existing) {
            std::string stored;
            acquired = lease->lock_.open_existing(lease->path_, 4096U, stored);
            if (acquired.acquired()) {
                std::string metadata_detail;
                if (!validate_managed_uninstall_recovery_lock(
                        stored, transaction_id, lease->lock_.identity_text(), metadata_detail)) {
                    lease->lock_.close();
                    return facman::core::Result<std::unique_ptr<ManagedUninstallLease>>::failure({
                        "recovery_write_refused", "Existing uninstall recovery lock identity is invalid",
                        metadata_detail});
                }
                lease->owned_ = true;
                return facman::core::Result<std::unique_ptr<ManagedUninstallLease>>::success(std::move(lease));
            }
        }
        if (!acquired.acquired()) return facman::core::Result<std::unique_ptr<ManagedUninstallLease>>::failure({
            acquired.code == facman::base::StableLockCode::exists ||
                acquired.code == facman::base::StableLockCode::contended
                ? "recovery_lock_contended" : "recovery_write_refused",
            acquired.detail.empty() ? "Another uninstall or recovery owns this transaction" : acquired.detail,
            facman::platform::path_to_utf8(lease->path_)});
        facman::core::json::ObjectBuilder metadata;
        metadata.add_string("schema", "facman.managed_uninstall_recovery_lock.v1");
        metadata.add_string("transaction_id", transaction_id);
        metadata.add_string("identity", lease->lock_.identity_text());
        std::string detail;
        if (!lease->lock_.write_text(metadata.serialize() + "\n", detail)) {
            std::string ignored;
            (void)lease->lock_.remove_exact(ignored);
            return facman::core::Result<std::unique_ptr<ManagedUninstallLease>>::failure({
                "recovery_write_refused", "Uninstall recovery lock metadata could not be written", detail});
        }
        lease->owned_ = true;
        return facman::core::Result<std::unique_ptr<ManagedUninstallLease>>::success(std::move(lease));
    }

    ~ManagedUninstallLease()
    {
        if (!owned_) return;
        std::string ignored;
        (void)lock_.remove_exact(ignored);
    }

private:
    ManagedUninstallLease() = default;
    facman::base::StableLocalLock lock_;
    fs::path path_;
    bool owned_ = false;
};

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

struct ManagedUninstallRecoveryPlan {
    facman::transaction::Record journal;
    ManagedUninstallCoordinator coordinator;
    facman::workspace::InstallRecord install;
    std::string install_record_text;
    std::string journal_sha256;
    UninstallRecoveryInspection inspection;
    std::string plan_id;
    std::string plan_digest;
    std::string action;
    std::string projected_record;
    std::string projected_record_sha256;
    std::string output;
};

std::string uninstall_recovery_document(
    const ManagedUninstallRecoveryPlan& plan,
    const std::string& status,
    const std::string& digest)
{
    facman::core::json::ObjectBuilder document;
    document.add_string("schema", "facman.managed_uninstall_recovery.v1");
    document.add_string("status", status);
    document.add_string("transaction_id", plan.coordinator.transaction_id);
    document.add_string("install_id", plan.coordinator.install_id);
    document.add_string("plan_id", plan.plan_id);
    if (!digest.empty()) document.add_string("plan_digest", digest);
    document.add_string("classification", plan.inspection.classification);
    document.add_string("action", plan.action);
    document.add_string("facman_journal_sha256", plan.journal_sha256);
    document.add_string("pre_record_sha256", plan.coordinator.pre_record_sha256);
    document.add_string("current_record_sha256", digest_text(plan.install_record_text));
    document.add_bool("provider_journal_present", plan.inspection.provider_journal_present);
    document.add_string("provider_observed_state", plan.inspection.provider_observed_state);
    document.add_string("provider_journal_digest", plan.inspection.provider_journal_digest);
    document.add_string("provider_journal_snapshot_sha256", plan.inspection.provider_journal_snapshot_sha256);
    document.add_string("provider_installed_state_sha256", plan.inspection.provider_installed_state_digest);
    document.add_bool("target_exists", plan.inspection.target_exists);
    document.add_string("projected_record_sha256", plan.projected_record_sha256);
    return document.serialize();
}

facman::core::Result<ManagedUninstallRecoveryPlan> build_uninstall_recovery_plan(
    ApplicationContext& application,
    const std::string& transaction_id)
{
    ManagedUninstallRecoveryPlan result;
    std::string detail;
    if (!facman::transaction::read_record(
            application.workspace(), transaction_id, result.journal, detail)) {
        return facman::core::Result<ManagedUninstallRecoveryPlan>::failure({
            "recovery_journal_invalid", "Managed uninstall coordinator journal is invalid", detail});
    }
    if (result.journal.schema_version != 2U ||
        result.journal.command_id != "installs.uninstall.apply" ||
        result.journal.commit_strategy != "provider_uninstall_then_durable_install_reference_replacement" ||
        result.journal.transaction_id != transaction_id || result.journal.sources.size() != 1U ||
        !decode_managed_uninstall_coordinator(
            result.journal.operation_context, result.coordinator, detail) ||
        result.coordinator.transaction_id != transaction_id) {
        return facman::core::Result<ManagedUninstallRecoveryPlan>::failure({
            "recovery_journal_invalid", "Transaction is not an exact managed uninstall coordinator", detail});
    }
    const bool pending_state = result.journal.state == facman::transaction::State::committing ||
        result.journal.state == facman::transaction::State::commit_uncertain ||
        result.journal.state == facman::transaction::State::recovery_required;
    const bool prepared_state = pending_state ||
        result.journal.state == facman::transaction::State::committed ||
        result.journal.state == facman::transaction::State::audited ||
        (result.journal.state == facman::transaction::State::complete &&
            !result.coordinator.recovery_plan_id.empty());
    if ((result.coordinator.phase == "provider_entry_pending" && !pending_state) ||
        (result.coordinator.phase == "terminal_projection_prepared" && !prepared_state)) {
        return facman::core::Result<ManagedUninstallRecoveryPlan>::failure({
            "recovery_journal_invalid",
            "Managed uninstall coordinator is not in a recoverable phase",
            facman::transaction::state_name(result.journal.state)});
    }
    auto workspace = application.workspace_repository().load();
    if (!workspace || result.journal.workspace_id != workspace.value().id.str()) {
        return facman::core::Result<ManagedUninstallRecoveryPlan>::failure({
            "recovery_journal_invalid", "Managed uninstall coordinator belongs to another workspace", "workspace id"});
    }
    auto install_id = facman::core::InstallId::parse_legacy(result.coordinator.install_id);
    if (!install_id) return facman::core::Result<ManagedUninstallRecoveryPlan>::failure({
        "recovery_journal_invalid", "Managed uninstall coordinator install id is invalid", install_id.error().message});
    auto loaded = application.installs().load(install_id.value());
    if (!loaded) return facman::core::Result<ManagedUninstallRecoveryPlan>::failure({
        "uninstall_recovery_projection_conflict", "Managed install reference is unavailable", loaded.error().message});
    result.install = loaded.take_value();
    result.install_record_text = read_text(result.install.source_path);
    if (result.install_record_text.empty() ||
        result.journal.sources.front().lexically_normal() != result.install.source_path.lexically_normal() ||
        result.journal.target.lexically_normal() !=
            facman::platform::path_from_utf8(result.coordinator.target_root).lexically_normal() ||
        result.install.root.lexically_normal() != result.journal.target.lexically_normal()) {
        return facman::core::Result<ManagedUninstallRecoveryPlan>::failure({
            "uninstall_recovery_projection_conflict",
            "Managed install reference no longer binds the uninstall coordinator", "record path or target"});
    }
    const std::string current_sha256 = digest_text(result.install_record_text);
    if (result.coordinator.schema == "facman.managed_uninstall_coordinator.v1") {
        if (current_sha256 != result.coordinator.pre_record_sha256) {
            return facman::core::Result<ManagedUninstallRecoveryPlan>::failure({
                "uninstall_recovery_projection_conflict",
                "Legacy uninstall coordinator has no durable terminal postimage identity", current_sha256});
        }
        result.coordinator.pre_setup_state_ref = result.install.setup_state_ref;
        result.coordinator.pre_last_verification_identity = result.install.last_verification_identity;
        result.coordinator.pre_state_revision = result.install.state_revision;
        result.coordinator.pre_lifecycle_status = result.install.lifecycle_status;
    } else if (result.coordinator.phase == "provider_entry_pending" &&
        current_sha256 != result.coordinator.pre_record_sha256) {
        return facman::core::Result<ManagedUninstallRecoveryPlan>::failure({
            "uninstall_recovery_projection_conflict",
            "Managed install reference changed before terminal projection", current_sha256});
    } else if (result.coordinator.phase == "terminal_projection_prepared" &&
        current_sha256 != result.coordinator.pre_record_sha256 &&
        current_sha256 != result.coordinator.projected_record_sha256) {
        return facman::core::Result<ManagedUninstallRecoveryPlan>::failure({
            "uninstall_recovery_projection_conflict",
            "Managed install reference is neither the prepared preimage nor postimage", current_sha256});
    }
    UninstallRecoveryRequest request;
    request.plan_request.request_id = result.coordinator.request_id;
    request.plan_request.plan_id = result.coordinator.plan_id;
    request.plan_request.install_id = result.coordinator.install_id;
    request.plan_request.created_at = result.coordinator.plan_created_at;
    request.plan_request.target = facman::platform::path_from_utf8(result.coordinator.target_root);
    request.plan_request.setup_state_ref = result.coordinator.pre_setup_state_ref;
    request.plan_request.last_verification_identity = result.coordinator.pre_last_verification_identity;
    request.plan_request.state_revision = result.coordinator.pre_state_revision;
    request.plan_request.lifecycle_status = result.coordinator.pre_lifecycle_status;
    request.reviewed_plan_digest = result.coordinator.reviewed_plan_digest;
    request.transaction_id = result.coordinator.transaction_id;
    request.applied_at = result.coordinator.applied_at;
    auto inspected = application.setup().inspect_uninstall_recovery(request);
    if (!inspected) return facman::core::Result<ManagedUninstallRecoveryPlan>::failure(inspected.error());
    result.inspection = inspected.take_value();
    result.action = result.inspection.classification == "no_provider_effect" ? "close_no_provider_effect" :
        (result.inspection.classification == "provider_retired" ||
         result.inspection.classification == "provider_uninstall_blocked") ? "project_terminal" : "none";
    if (result.action == "project_terminal") {
        UninstallReport report;
        report.setup_state_ref = result.inspection.setup_state_ref;
        report.last_verification_identity = result.inspection.last_verification_identity;
        report.state_revision = result.inspection.state_revision;
        report.lifecycle_status = result.inspection.lifecycle_status;
        report.verification_status = result.inspection.verification_status;
        report.installed_state_digest = result.inspection.provider_installed_state_digest;
        result.projected_record = uninstalled_install_record(result.install, report);
        result.projected_record_sha256 = digest_text(result.projected_record);
    } else {
        result.projected_record = result.install_record_text;
        result.projected_record_sha256 = result.coordinator.pre_record_sha256;
    }
    auto raw_journal = application.transactions().load_journal(
        facman::core::TransactionId::parse(transaction_id).value());
    if (!raw_journal) return facman::core::Result<ManagedUninstallRecoveryPlan>::failure({
        "recovery_journal_invalid", "Managed uninstall coordinator could not be read stably", raw_journal.error().message});
    result.journal_sha256 = digest_text(raw_journal.value());
    result.plan_id = "uninstall-recovery." + transaction_id;
    const std::string unsigned_plan = uninstall_recovery_document(
        result, result.action == "none" ? "blocked" : "planned", "");
    auto canonical_plan = canonicalize_managed_uninstall_recovery_plan(unsigned_plan);
    if (!canonical_plan) return facman::core::Result<ManagedUninstallRecoveryPlan>::failure(canonical_plan.error());
    result.plan_digest = digest_text(canonical_plan.value());
    result.output = uninstall_recovery_document(
        result, result.action == "none" ? "blocked" : "planned", result.plan_digest);
    return facman::core::Result<ManagedUninstallRecoveryPlan>::success(std::move(result));
}

ApplicationResult uninstall_recovery_failure(
    const std::string& operation,
    const facman::core::Error& error)
{
    const bool conflict = error.code == "uninstall_recovery_projection_conflict";
    const bool retryable = error.code == "recovery_lock_contended" ||
        error.code == "recovery_write_refused" || error.code == "stale_plan";
    return refused(
        safety_refusal(operation, error.code, error.message, error.detail, true, retryable),
        error.code, error.message,
        conflict ? facman::core::OutcomeKind::conflict :
            error.code == "uninstall_recovery_indeterminate" ?
                facman::core::OutcomeKind::recovery_required : error.kind);
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

ApplicationResult plan_repair_install(ApplicationContext& context, const ServiceOperationRequest& request)
{
#if FACMAN_WITH_SETUP
    auto parsed_id = facman::core::InstallId::parse_legacy(request.install_id);
    if (!parsed_id) return refused(
        safety_refusal("installs.repair.plan", parsed_id.error().code, "Install id is invalid", parsed_id.error().message, false),
        parsed_id.error().code, parsed_id.error().message, parsed_id.error().kind);
    auto install = context.installs().load(parsed_id.value());
    if (!install) return refused(
        safety_refusal("installs.repair.plan", "unknown_install", "Install reference is not registered", request.install_id, true),
        "unknown_install", "Install reference is not registered");
    const auto& record = install.value();
    if (record.ownership != "managed") return refused(
        safety_refusal("installs.repair.plan", "ownership_denied", "Repair planning is available only for registered managed installs", record.ownership, true),
        "ownership_denied", "Repair planning is available only for registered managed installs");
    if (record.provider_id != "universal-setup" || record.source != "universal-setup") return refused(
        safety_refusal("installs.repair.plan", "managed_install_provider_mismatch", "Managed repair planning requires a Universal Setup managed record", record.provider_id + ":" + record.source, true),
        "managed_install_provider_mismatch", "Managed repair planning requires a Universal Setup managed record");
    if (record.lifecycle_status == "recovery_required") return refused(
        safety_refusal("installs.repair.plan", "operation_specific_recovery_required", "Interrupted managed installation work must be recovered before repair", request.install_id, true),
        "operation_specific_recovery_required", "Interrupted managed installation work must be recovered before repair",
        facman::core::OutcomeKind::recovery_required);
    if (record.lifecycle_status != "active" && record.lifecycle_status != "verification_failed") return refused(
        safety_refusal("installs.repair.plan", "repair_lifecycle_ineligible", "Repair planning requires an active or verification_failed managed install", record.lifecycle_status, true),
        "repair_lifecycle_ineligible", "Repair planning requires an active or verification_failed managed install");
    if (record.root.empty() || record.version.empty() || request.archive.empty() ||
        record.setup_state_ref.empty() || record.last_verification_identity.empty() || record.state_revision.empty()) {
        return refused(
            safety_refusal("installs.repair.plan", "managed_install_evidence_incomplete", "Managed repair planning requires archive, version, target, setup, verification, and revision evidence", request.install_id, true),
            "managed_install_evidence_incomplete", "Managed repair planning requires complete managed-install evidence");
    }
    const std::string record_text = read_text(record.source_path);
    if (record_text.empty()) return refused(
        safety_refusal("installs.repair.plan", "workspace_record_read_failed", "Managed install record cannot be read stably", record.source_path.string(), true),
        "workspace_record_read_failed", "Managed install record cannot be read stably");
    RepairPlanRequest plan_request;
    plan_request.plan_id = context.ids().next("repair-plan");
    plan_request.request_id = plan_request.plan_id;
    plan_request.install_id = record.id.str();
    plan_request.created_at = context.clock().now_utc();
    plan_request.version = record.version;
    plan_request.archive = facman::platform::path_from_utf8(request.archive);
    plan_request.target = record.root;
    plan_request.setup_state_ref = record.setup_state_ref;
    plan_request.last_verification_identity = record.last_verification_identity;
    plan_request.state_revision = record.state_revision;
    plan_request.lifecycle_status = record.lifecycle_status;
    auto plan = context.setup().plan_repair(plan_request);
    if (!plan) return refused(
        safety_refusal("installs.repair.plan", plan.error().code, "Universal Setup refused managed repair planning",
            plan.error().path.empty() ? plan.error().message : plan.error().message + ": " + plan.error().path, true),
        plan.error().code, plan.error().message, plan.error().kind);
    auto envelope = encode_managed_repair_envelope(plan.value(), digest_text(record_text));
    if (!envelope) return refused(
        safety_refusal("installs.repair.plan", envelope.error().code, "Managed repair plan could not be bound", envelope.error().message, true),
        envelope.error().code, envelope.error().message);
    ApplicationResult result;
    result.output = envelope.value().document;
    return result;
#else
    (void)request;
    return unavailable(context, "installs.repair.plan", "setup_unavailable", "Universal Setup support is disabled in this build");
#endif
}

ApplicationResult apply_repair_install(ApplicationContext& context, const ServiceOperationRequest& request)
{
#if FACMAN_WITH_SETUP
    // This implemented provider route replaces the former live_target_acceptance_required stub.
    if (!valid_utc_seconds(request.plan_created_at) || !valid_utc_seconds(request.applied_at) ||
        request.applied_at <= request.plan_created_at || request.confirmation != "APPLY") return refused(
        safety_refusal("installs.repair.apply", "invalid_timestamp", "Repair apply requires exact confirmation and advancing UTC timestamps", "plan_created_at/applied_at", false),
        "invalid_timestamp", "Repair apply requires exact confirmation and advancing UTC timestamps");
    auto parsed_transaction = facman::core::TransactionId::parse(request.transaction_id);
    if (!parsed_transaction) return refused(
        safety_refusal("installs.repair.apply", parsed_transaction.error().code, "Transaction id is not portable", parsed_transaction.error().message, false),
        parsed_transaction.error().code, parsed_transaction.error().message, parsed_transaction.error().kind);
    facman::transaction::Record existing;
    std::string existing_detail;
    if (facman::transaction::read_record(context.workspace(), parsed_transaction.value().str(), existing, existing_detail)) {
        return refused(
            safety_refusal("installs.repair.apply", "operation_specific_recovery_required", "Existing managed repair transaction requires operation-specific recovery", request.transaction_id, true),
            "operation_specific_recovery_required", "Existing managed repair transaction requires operation-specific recovery",
            facman::core::OutcomeKind::recovery_required);
    }
    auto parsed_id = facman::core::InstallId::parse_legacy(request.install_id);
    if (!parsed_id) return refused(
        safety_refusal("installs.repair.apply", parsed_id.error().code, "Install id is invalid", parsed_id.error().message, false),
        parsed_id.error().code, parsed_id.error().message, parsed_id.error().kind);
    auto install = context.installs().load(parsed_id.value());
    if (!install) return refused(
        safety_refusal("installs.repair.apply", "unknown_install", "Install reference is not registered", request.install_id, true),
        "unknown_install", "Install reference is not registered");
    const auto& record = install.value();
    if (record.ownership != "managed" || record.provider_id != "universal-setup" ||
        record.source != "universal-setup" ||
        (record.lifecycle_status != "active" && record.lifecycle_status != "verification_failed") ||
        record.root.empty() || record.version.empty() || request.archive.empty() ||
        record.setup_state_ref.empty() || record.last_verification_identity.empty() || record.state_revision.empty()) {
        return refused(
            safety_refusal("installs.repair.apply", "managed_install_evidence_incomplete", "Managed repair apply requires an eligible Universal Setup managed install", request.install_id, true),
            "managed_install_evidence_incomplete", "Managed repair apply requires an eligible Universal Setup managed install");
    }
    const std::string record_text = read_text(record.source_path);
    if (record_text.empty()) return refused(
        safety_refusal("installs.repair.apply", "workspace_record_read_failed", "Managed install record cannot be read stably", record.source_path.string(), true),
        "workspace_record_read_failed", "Managed install record cannot be read stably");
    const std::string record_digest = digest_text(record_text);
    if (request.install_record_sha256 != record_digest) return refused(
        safety_refusal("installs.repair.apply", "managed_install_record_preimage_changed", "Managed install record changed after repair planning", request.install_id, true),
        "managed_install_record_preimage_changed", "Managed install record changed after repair planning",
        facman::core::OutcomeKind::conflict);
    RepairPlanRequest plan_request;
    plan_request.plan_id = request.plan_id;
    plan_request.request_id = request.plan_id;
    plan_request.install_id = record.id.str();
    plan_request.created_at = request.plan_created_at;
    plan_request.version = record.version;
    plan_request.archive = facman::platform::path_from_utf8(request.archive);
    plan_request.target = record.root;
    plan_request.setup_state_ref = record.setup_state_ref;
    plan_request.last_verification_identity = record.last_verification_identity;
    plan_request.state_revision = record.state_revision;
    plan_request.lifecycle_status = record.lifecycle_status;
    auto plan = context.setup().plan_repair(plan_request);
    if (!plan) return refused(
        safety_refusal("installs.repair.apply", "stale_plan", "Reviewed repair plan no longer revalidates", plan.error().code + ": " + plan.error().message, true),
        "stale_plan", plan.error().code + ": " + plan.error().message);
    auto envelope = encode_managed_repair_envelope(plan.value(), record_digest);
    if (!envelope || envelope.value().digest != request.plan_digest) return refused(
        safety_refusal("installs.repair.apply", "stale_plan", "Reviewed repair plan identity changed before apply", request.plan_id, true),
        "stale_plan", "Reviewed repair plan identity changed before apply");

    facman::transaction::Record journal_record;
    journal_record.transaction_id = parsed_transaction.value().str();
    journal_record.command_id = "installs.repair.apply";
    journal_record.target = record.root;
    journal_record.sources = {record.source_path, plan_request.archive};
    journal_record.commit_strategy = "provider_repair_then_durable_install_reference_replacement";
    journal_record.operation_context = encode_managed_repair_context(
        plan_request, plan.value(), request.plan_id, request.plan_digest,
        request.transaction_id, request.applied_at, facman::platform::path_to_utf8(record.root),
        record_digest, "provider_entry_pending", nullptr, "");
    auto started = facman::transaction::TransactionSession::begin(context.workspace(), std::move(journal_record));
    if (!started) return refused(
        safety_refusal("installs.repair.apply", "recovery_write_refused", "Repair coordinator journal could not be prepared", started.error().message, true),
        "recovery_write_refused", started.error().message, facman::core::OutcomeKind::recovery_required);
    auto session = started.take_value();
    if (!session.validated("reviewed_outer_plan_bound") || !session.planned("exact_provider_plan_persisted") ||
        !session.staged("provider_entry_prepared") || !session.verified("current_record_bound")) {
        return refused(safety_refusal("installs.repair.apply", "recovery_write_refused", "Repair coordinator journal could not enter provider phase", session.detail(), true),
            "recovery_write_refused", session.detail(), facman::core::OutcomeKind::recovery_required);
    }
    session.record().operation_context = encode_managed_repair_context(
        plan_request, plan.value(), request.plan_id, request.plan_digest,
        request.transaction_id, request.applied_at, facman::platform::path_to_utf8(record.root),
        record_digest, "provider_entry_started", nullptr, "");
    if (!session.committing("provider_entry_started")) return refused(
        safety_refusal("installs.repair.apply", "recovery_write_refused", "Repair provider-entry intent could not be recorded", session.detail(), true),
        "recovery_write_refused", session.detail(), facman::core::OutcomeKind::recovery_required);
    RepairApplyRequest apply;
    apply.plan_request = plan_request;
    apply.reviewed_plan = plan.value();
    apply.transaction_id = request.transaction_id;
    apply.applied_at = request.applied_at;
    apply.confirmation = request.confirmation;
    auto report = context.setup().apply_repair(apply);
    if (!report) {
        if (repair_refusal_proves_no_provider_effect(report.error().code)) {
            if (!session.refused(report.error().code + ": " + report.error().message)) {
                return refused(safety_refusal("installs.repair.apply", "recovery_write_refused", "Provider repair refusal could not be durably closed", session.detail(), true),
                    "recovery_write_refused", session.detail(), facman::core::OutcomeKind::recovery_required);
            }
            return refused(safety_refusal("installs.repair.apply", report.error().code, "Universal Setup refused managed repair before mutation", report.error().message, true),
                report.error().code, report.error().message, report.error().kind);
        }
        session.failed(report.error().code + ": " + report.error().message);
        return refused(safety_refusal("installs.repair.apply", "transaction_recovery_required", "Universal Setup repair outcome requires recovery", report.error().detail.empty() ? report.error().message : report.error().detail, false),
            "transaction_recovery_required", report.error().code + ": " + report.error().message,
            facman::core::OutcomeKind::recovery_required);
    }
    const std::string terminal_record = project_repaired_install_record(record_text, report.value());
    if (terminal_record.empty()) {
        session.failed("terminal record projection could not preserve the managed record");
        return refused(safety_refusal("installs.repair.apply", "transaction_recovery_required", "Repair completed in Universal Setup but its FacMan record cannot be projected", request.install_id, false),
            "transaction_recovery_required", "Managed install record projection failed",
            facman::core::OutcomeKind::recovery_required);
    }
    const std::string terminal_digest = digest_text(terminal_record);
    session.record().operation_context = encode_managed_repair_context(
        plan_request, plan.value(), request.plan_id, request.plan_digest,
        request.transaction_id, request.applied_at, facman::platform::path_to_utf8(record.root),
        record_digest, "terminal_projection_prepared", &report.value(), terminal_digest);
    if (!session.checkpoint("terminal_projection_prepared")) {
        const std::string detail = session.detail();
        session.failed("terminal projection checkpoint failed: " + detail);
        return refused(safety_refusal("installs.repair.apply", "transaction_recovery_required", "Repair terminal projection intent could not be recorded", detail, false),
            "transaction_recovery_required", detail, facman::core::OutcomeKind::recovery_required);
    }
    const char* injected = std::getenv("FACMAN_TEST_REPAIR_INTERRUPT_AFTER_PROVIDER");
    if (injected != nullptr && std::string(injected) == "1") {
        session.failed("Injected interruption after provider repair");
        return refused(safety_refusal("installs.repair.apply", "transaction_recovery_required", "Injected interruption after provider repair", request.transaction_id, false),
            "transaction_recovery_required", "Injected interruption after provider repair",
            facman::core::OutcomeKind::recovery_required);
    }
    auto replaced = context.installs().replace(record, record_digest, terminal_record);
    if (!replaced) {
        session.failed("terminal projection failed: " + replaced.error().message);
        return refused(safety_refusal("installs.repair.apply", "transaction_recovery_required", "Repair completed in Universal Setup but its FacMan reference requires recovery", replaced.error().message, false),
            "transaction_recovery_required", replaced.error().message, facman::core::OutcomeKind::recovery_required);
    }
    if (!session.committed("repaired_reference_projected") || !session.complete()) return refused(
        safety_refusal("installs.repair.apply", "transaction_recovery_required", "Repair projection completed but its coordinator could not close", session.detail(), false),
        "transaction_recovery_required", session.detail(), facman::core::OutcomeKind::recovery_required);
    ApplicationResult result;
    result.output = managed_repair_result(request, plan.value(), report.value());
    return result;
#else
    (void)request;
    return unavailable(context, "installs.repair.apply", "setup_unavailable", "Universal Setup support is disabled in this build");
#endif
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
    // This implemented provider route replaces the former live_target_acceptance_required stub.
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
    auto coordinator_lease = ManagedUninstallLease::acquire(
        context.workspace(), request.transaction_id, false);
    if (!coordinator_lease) {
        session.failed(coordinator_lease.error().code + ": " + coordinator_lease.error().message);
        return refused(
            safety_refusal("installs.uninstall.apply", coordinator_lease.error().code,
                "Uninstall coordinator lease could not be acquired", coordinator_lease.error().message, true),
            coordinator_lease.error().code, coordinator_lease.error().message,
            facman::core::OutcomeKind::recovery_required);
    }
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
    const char* before_provider = std::getenv("FACMAN_TEST_UNINSTALL_INTERRUPT_BEFORE_PROVIDER");
    if (before_provider != nullptr && std::string(before_provider) == "1") {
        session.failed("Injected interruption before provider uninstall");
        return refused(
            safety_refusal("installs.uninstall.apply", "transaction_recovery_required",
                "Injected interruption before provider uninstall", request.transaction_id, false),
            "transaction_recovery_required", "Injected interruption before provider uninstall",
            facman::core::OutcomeKind::recovery_required);
    }
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
    UninstallRecoveryRequest recovery_evidence_request;
    recovery_evidence_request.plan_request = plan;
    recovery_evidence_request.reviewed_plan_digest = request.plan_digest;
    recovery_evidence_request.transaction_id = request.transaction_id;
    recovery_evidence_request.applied_at = request.applied_at;
    auto recovery_evidence = context.setup().inspect_uninstall_recovery(
        recovery_evidence_request);
    const std::string expected_classification =
        report.value().lifecycle_status == "uninstalled" ?
            "provider_retired" : "provider_uninstall_blocked";
    if (!recovery_evidence ||
        recovery_evidence.value().classification != expected_classification ||
        recovery_evidence.value().provider_installed_state_digest !=
            report.value().installed_state_digest ||
        recovery_evidence.value().setup_state_ref != report.value().setup_state_ref ||
        recovery_evidence.value().last_verification_identity !=
            report.value().last_verification_identity ||
        recovery_evidence.value().state_revision != report.value().state_revision ||
        recovery_evidence.value().lifecycle_status != report.value().lifecycle_status ||
        recovery_evidence.value().verification_status != report.value().verification_status) {
        const std::string evidence_detail = recovery_evidence ?
            "provider terminal identity mismatch" :
            recovery_evidence.error().code + ": " + recovery_evidence.error().message;
        session.failed("terminal provider evidence inspection failed: " + evidence_detail);
        return refused(safety_refusal("installs.uninstall.apply", "transaction_recovery_required",
            "Uninstall provider result requires exact recovery inspection before projection",
            evidence_detail, false),
            "transaction_recovery_required", evidence_detail,
            facman::core::OutcomeKind::recovery_required);
    }
    const std::string terminal_record = uninstalled_install_record(record, report.value());
    const std::string terminal_record_digest = digest_text(terminal_record);
    ManagedUninstallCoordinator coordinator;
    std::string coordinator_detail;
    if (!decode_managed_uninstall_coordinator(
            session.record().operation_context, coordinator, coordinator_detail)) {
        session.failed("coordinator checkpoint decode failed: " + coordinator_detail);
        return refused(safety_refusal("installs.uninstall.apply", "transaction_recovery_required",
            "Uninstall provider result could not be checkpointed", coordinator_detail, false),
            "transaction_recovery_required", coordinator_detail,
            facman::core::OutcomeKind::recovery_required);
    }
    session.record().operation_context = checkpointed_uninstall_context(
        coordinator, recovery_evidence.value(), "", "", terminal_record_digest);
    if (!session.checkpoint("terminal_projection_prepared")) {
        const std::string checkpoint_detail = session.detail();
        session.failed("terminal projection checkpoint failed: " + checkpoint_detail);
        return refused(
            safety_refusal("installs.uninstall.apply", "transaction_recovery_required",
                "Uninstall terminal projection intent could not be recorded", checkpoint_detail, false),
            "transaction_recovery_required", checkpoint_detail,
            facman::core::OutcomeKind::recovery_required);
    }
    const char* injected = std::getenv("FACMAN_TEST_UNINSTALL_INTERRUPT_AFTER_PROVIDER");
    if (injected != nullptr && std::string(injected) == "1") {
        session.failed("Injected interruption after provider uninstall");
        return refused(
            safety_refusal("installs.uninstall.apply", "transaction_recovery_required",
                "Injected interruption after provider uninstall", request.transaction_id, false),
            "transaction_recovery_required", "Injected interruption after provider uninstall",
            facman::core::OutcomeKind::recovery_required);
    }
    const std::string pre_record_digest = facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(record_text.data()), record_text.size());
    auto replaced = context.installs().replace(
        record, pre_record_digest, terminal_record);
    if (!replaced) {
        session.failed("terminal projection failed: " + replaced.error().message);
        return refused(
            safety_refusal("installs.uninstall.apply", "transaction_recovery_required",
                "Uninstall provider result requires recovery before terminal projection is durable",
                replaced.error().message, false),
            "transaction_recovery_required", replaced.error().message,
            facman::core::OutcomeKind::recovery_required);
    }
    if (!session.committed("uninstalled_reference_projected") || !session.complete()) return refused(
        safety_refusal("installs.uninstall.apply", "transaction_recovery_required",
            "Uninstall provider result requires recovery before terminal projection is durable",
            session.detail(), false),
        "transaction_recovery_required", session.detail(), facman::core::OutcomeKind::recovery_required);
    ApplicationResult result;
    result.output = report.value().provider_response;
    return result;
#else
    (void)request;
    return unavailable(context, "installs.uninstall.apply", "setup_unavailable", "Universal Setup support is disabled in this build");
#endif
}

ApplicationResult inspect_install_recovery(ApplicationContext& context, const ServiceOperationRequest& request)
{
#if FACMAN_WITH_SETUP
    auto parsed = facman::core::TransactionId::parse(request.transaction_id);
    if (!parsed) return uninstall_recovery_failure("installs.recovery.inspect", parsed.error());
    auto planned = build_uninstall_recovery_plan(context, parsed.value().str());
    if (!planned) return uninstall_recovery_failure("installs.recovery.inspect", planned.error());
    ApplicationResult result;
    result.output = planned.value().output;
    return result;
#else
    (void)request;
    return unavailable(context, "installs.recovery.inspect", "setup_unavailable",
        "Universal Setup support is disabled in this build");
#endif
}

ApplicationResult apply_install_recovery(ApplicationContext& context, const ServiceOperationRequest& request)
{
#if FACMAN_WITH_SETUP
    auto parsed = facman::core::TransactionId::parse(request.transaction_id);
    if (!parsed) return uninstall_recovery_failure("installs.recovery.apply", parsed.error());
    auto lease = ManagedUninstallLease::acquire(context.workspace(), parsed.value().str(), true);
    if (!lease) return uninstall_recovery_failure("installs.recovery.apply", lease.error());
    auto planned = build_uninstall_recovery_plan(context, parsed.value().str());
    if (!planned) return uninstall_recovery_failure("installs.recovery.apply", planned.error());
    auto plan = planned.take_value();
    const bool checkpointed_review = !plan.coordinator.recovery_plan_id.empty();
    const std::string expected_plan_id = checkpointed_review ?
        plan.coordinator.recovery_plan_id : plan.plan_id;
    const std::string expected_plan_digest = checkpointed_review ?
        plan.coordinator.recovery_plan_digest : plan.plan_digest;
    if (request.confirmation != "APPLY" || request.plan_id != expected_plan_id ||
        request.plan_digest != expected_plan_digest) {
        return uninstall_recovery_failure("installs.recovery.apply", {
            "stale_plan", "Reviewed uninstall recovery plan changed before apply", request.plan_id});
    }
    if (plan.action == "none") return uninstall_recovery_failure("installs.recovery.apply", {
        "uninstall_recovery_indeterminate",
        "Universal Setup uninstall is not in a safely projectable terminal state",
        plan.inspection.provider_observed_state});
    if (plan.coordinator.phase == "terminal_projection_prepared") {
        if (plan.coordinator.classification != plan.inspection.classification ||
            plan.coordinator.provider_installed_state_sha256 !=
                plan.inspection.provider_installed_state_digest ||
            plan.coordinator.projected_record_sha256 != plan.projected_record_sha256 ||
            (!plan.coordinator.provider_journal_snapshot_sha256.empty() &&
             plan.coordinator.provider_journal_snapshot_sha256 !=
                plan.inspection.provider_journal_snapshot_sha256)) {
            return uninstall_recovery_failure("installs.recovery.apply", {
                "stale_plan", "Prepared uninstall terminal identity changed before recovery", "checkpoint"});
        }
    }
    if (facman::transaction::terminal(plan.journal.state)) {
        plan.plan_id = request.plan_id;
        plan.plan_digest = request.plan_digest;
        ApplicationResult result;
        result.output = uninstall_recovery_document(plan, "completed", request.plan_digest);
        return result;
    }
    plan.journal.operation_context = checkpointed_uninstall_context(
        plan.coordinator, plan.inspection, request.plan_id, request.plan_digest,
        plan.projected_record_sha256);
    std::string detail;
    if (!facman::transaction::checkpoint(
            context.workspace(), plan.journal, "terminal_projection_prepared", detail)) {
        return uninstall_recovery_failure("installs.recovery.apply", {
            "recovery_write_refused", "Uninstall terminal projection checkpoint failed", detail});
    }
    const std::string current_sha256 = digest_text(plan.install_record_text);
    if (current_sha256 == plan.coordinator.pre_record_sha256) {
        auto replaced = context.installs().replace(
            plan.install, plan.coordinator.pre_record_sha256, plan.projected_record);
        if (!replaced) return uninstall_recovery_failure("installs.recovery.apply", {
            replaced.error().code == "workspace_record_preimage_changed" ?
                "uninstall_recovery_projection_conflict" : "recovery_write_refused",
            "Uninstall terminal reference projection failed", replaced.error().message});
    } else if (current_sha256 != plan.coordinator.pre_record_sha256 &&
        current_sha256 != plan.projected_record_sha256) {
        return uninstall_recovery_failure("installs.recovery.apply", {
            "uninstall_recovery_projection_conflict",
            "Managed install reference changed before recovery projection", current_sha256});
    }
    const char* interrupt = std::getenv("FACMAN_TEST_UNINSTALL_RECOVERY_INTERRUPT_AFTER_PROJECTION");
    if (interrupt != nullptr && std::string(interrupt) == "1") {
        return uninstall_recovery_failure("installs.recovery.apply", {
            "transaction_recovery_required",
            "Injected interruption after uninstall recovery projection", request.transaction_id});
    }
    plan.journal.recovery_actions.push_back(
        plan.action == "project_terminal" ? "projected_terminal_install_reference" :
            "confirmed_no_provider_effect");
    if (plan.journal.state == facman::transaction::State::committing) {
        if (plan.action == "project_terminal") {
            if (!facman::transaction::advance(
                    context.workspace(), plan.journal, "committed",
                    "uninstall_terminal_projection_recovered", detail)) {
                return uninstall_recovery_failure("installs.recovery.apply", {
                    "recovery_write_refused", "Recovered uninstall commit could not be recorded", detail});
            }
        } else if (!facman::transaction::advance(
                context.workspace(), plan.journal, "recovery_required",
                "uninstall_no_effect_recovered", detail)) {
            return uninstall_recovery_failure("installs.recovery.apply", {
                "recovery_write_refused", "No-effect uninstall recovery could not be recorded", detail});
        }
    }
    if (plan.journal.state == facman::transaction::State::audited) {
        if (!facman::transaction::advance(
                context.workspace(), plan.journal, "complete", "journal_closed", detail)) {
            return uninstall_recovery_failure("installs.recovery.apply", {
                "recovery_write_refused", "Uninstall recovery journal could not be closed", detail});
        }
    } else if (!facman::transaction::terminal(plan.journal.state) &&
        !facman::transaction::complete(context.workspace(), plan.journal, detail)) {
        return uninstall_recovery_failure("installs.recovery.apply", {
            "recovery_write_refused", "Uninstall recovery journal could not be closed", detail});
    }
    plan.plan_id = request.plan_id;
    plan.plan_digest = request.plan_digest;
    auto final_journal = context.transactions().load_journal(parsed.value());
    if (!final_journal) return uninstall_recovery_failure("installs.recovery.apply", {
        "recovery_write_refused", "Completed uninstall recovery journal could not be read",
        final_journal.error().message});
    plan.journal_sha256 = digest_text(final_journal.value());
    plan.install_record_text = read_text(plan.install.source_path);
    if (plan.install_record_text.empty()) return uninstall_recovery_failure("installs.recovery.apply", {
        "workspace_record_read_failed", "Completed uninstall recovery reference could not be read",
        facman::platform::path_to_utf8(plan.install.source_path)});
    ApplicationResult result;
    result.output = uninstall_recovery_document(plan, "completed", request.plan_digest);
    return result;
#else
    (void)request;
    return unavailable(context, "installs.recovery.apply", "setup_unavailable",
        "Universal Setup support is disabled in this build");
#endif
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
