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

std::string managed_install_record(
    const InstallApplyRequest& request,
    const InstallReport& report)
{
    auto install = facman::factorio::discovery::inspect_install(
        report.target, request.plan_request.install_id);
    if (install.executable.lexically_normal() != report.executable.lexically_normal()) return {};
    install.provider_id = "universal-setup";
    install.root = report.target;
    install.executable = report.executable;
    install.version = request.plan_request.version;
    install.ownership = "managed";
    install.source = "universal-setup";
    install.source_ref = "archive-sha256:" + report.source_archive_sha256;
    install.platform = "windows";
    install.distribution_origin = "local_archive";
    install.platform_integration = "none_detected";
    install.installation_layout = "portable_archive";
    install.setup_state_ref = report.setup_state_ref;
    install.lifecycle_status = "active";
    install.last_verification_identity = report.last_verification_identity;
    install.state_revision = report.state_revision;
    install.verification_status = report.verification_status;
    install.diagnostic_code.clear();
    install.setup_mutation_allowed = true;
    return facman::factorio::discovery::install_ref_json(install);
}

std::string prepared_install_context(const std::string& original, const std::string& record_digest)
{
    return prepare_managed_install_context(original, record_digest);
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

class ManagedInstallRecoveryLease {
public:
    static facman::core::Result<std::unique_ptr<ManagedInstallRecoveryLease>> acquire(
        const fs::path& workspace,
        const std::string& transaction_id,
        bool adopt_existing)
    {
        auto parsed = facman::core::TransactionId::parse(transaction_id);
        if (!parsed) return facman::core::Result<std::unique_ptr<ManagedInstallRecoveryLease>>::failure(parsed.error());
        auto journal = facman::workspace::WorkspaceLayout(workspace).transaction_journal(parsed.value());
        if (!journal) return facman::core::Result<std::unique_ptr<ManagedInstallRecoveryLease>>::failure(journal.error());
        auto lease = std::unique_ptr<ManagedInstallRecoveryLease>(new ManagedInstallRecoveryLease());
        lease->path_ = journal.value();
        lease->path_ += ".recovery.lock";
        auto acquired = lease->lock_.create(lease->path_);
        if (acquired.code == facman::base::StableLockCode::exists && adopt_existing) {
            std::string stored;
            acquired = lease->lock_.open_existing(lease->path_, 4096U, stored);
            if (acquired.acquired()) {
                std::string metadata_detail;
                if (!validate_managed_install_recovery_lock(
                        stored, transaction_id, lease->lock_.identity_text(), metadata_detail)) {
                    lease->lock_.close();
                    return facman::core::Result<std::unique_ptr<ManagedInstallRecoveryLease>>::failure({
                        "recovery_write_refused", "Existing managed install recovery lock identity is invalid",
                        metadata_detail});
                }
                lease->owned_ = true;
                return facman::core::Result<std::unique_ptr<ManagedInstallRecoveryLease>>::success(std::move(lease));
            }
        }
        if (!acquired.acquired()) return facman::core::Result<std::unique_ptr<ManagedInstallRecoveryLease>>::failure({
            acquired.code == facman::base::StableLockCode::exists ||
                acquired.code == facman::base::StableLockCode::contended
                ? "recovery_lock_contended" : "recovery_write_refused",
            acquired.detail.empty() ? "Another managed install recovery owns this transaction" : acquired.detail,
            facman::platform::path_to_utf8(lease->path_)});
        facman::core::json::ObjectBuilder metadata;
        metadata.add_string("schema", "facman.managed_install_recovery_lock.v1");
        metadata.add_string("transaction_id", transaction_id);
        metadata.add_string("identity", lease->lock_.identity_text());
        std::string detail;
        if (!lease->lock_.write_text(metadata.serialize() + "\n", detail)) {
            std::string ignored;
            (void)lease->lock_.remove_exact(ignored);
            return facman::core::Result<std::unique_ptr<ManagedInstallRecoveryLease>>::failure({
                "recovery_write_refused", "Managed install recovery lock metadata could not be written", detail});
        }
        lease->owned_ = true;
        return facman::core::Result<std::unique_ptr<ManagedInstallRecoveryLease>>::success(std::move(lease));
    }

    ~ManagedInstallRecoveryLease()
    {
        if (!owned_) return;
        std::string ignored;
        (void)lock_.remove_exact(ignored);
    }

private:
    ManagedInstallRecoveryLease() = default;
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

struct NewInstallRecoveryPlan {
    facman::transaction::Record journal;
    InstallRecoveryRequest original;
    InstallRecoveryInspection inspection;
    facman::core::InstallId install_id;
    fs::path record_path;
    std::string record_text;
    std::string projected_record;
    std::string prepared_record_sha256;
    std::string journal_sha256;
    std::string action;
    std::string plan_id;
    std::string plan_digest;
    std::string output;
    unsigned replay_attempt = 0;
    std::string replay_transaction_id;
    std::string retained_child_transaction_id;
    std::string retained_child_snapshot_sha256;
};

std::string new_install_recovery_document(
    const NewInstallRecoveryPlan& plan, const std::string& status, const std::string& digest)
{
    facman::core::json::ObjectBuilder document;
    document.add_string("schema", "facman.managed_install_recovery.v1");
    document.add_string("operation", "install");
    document.add_string("status", status);
    document.add_string("transaction_id", plan.journal.transaction_id);
    document.add_string("install_id", plan.original.apply.plan_request.install_id);
    document.add_string("plan_id", plan.plan_id);
    if (!digest.empty()) document.add_string("plan_digest", digest);
    document.add_string("classification", plan.inspection.classification);
    document.add_string("action", plan.action);
    document.add_string("facman_journal_sha256", plan.journal_sha256);
    document.add_string("pre_record_sha256", digest_text(""));
    document.add_string("current_record_sha256", digest_text(plan.record_text));
    document.add_bool("provider_journal_present", plan.inspection.provider_journal_present);
    document.add_string("provider_observed_state", plan.inspection.provider_observed_state);
    document.add_string("provider_journal_digest", plan.inspection.provider_journal_digest);
    document.add_string("provider_journal_snapshot_sha256",
        plan.inspection.provider_journal_snapshot_sha256);
    document.add_string("provider_installed_state_sha256",
        plan.inspection.terminal.installed_state_digest);
    document.add_string("retained_child_journal_snapshot_sha256", plan.retained_child_snapshot_sha256);
    document.add_bool("target_exists", plan.inspection.target_exists);
    document.add_string("projected_record_sha256", digest_text(plan.projected_record));
    return document.serialize();
}

facman::core::Result<NewInstallRecoveryPlan> build_new_install_recovery_plan(
    ApplicationContext& context, const std::string& transaction_id)
{
    const auto invalid = [](const std::string& detail) {
        return facman::core::Result<NewInstallRecoveryPlan>::failure({
            "recovery_journal_invalid", "Managed install coordinator is not an exact recoverable identity", detail});
    };
    NewInstallRecoveryPlan plan;
    std::string detail;
    if (!facman::transaction::read_record(context.workspace(), transaction_id, plan.journal, detail) ||
        plan.journal.schema_version != 2U || plan.journal.command_id != "installs.install.apply" ||
        plan.journal.commit_strategy != "provider_install_then_durable_install_reference_create" ||
        plan.journal.transaction_id != transaction_id || plan.journal.sources.size() != 1U) return invalid(detail);
    ManagedInstallCoordinator coordinator;
    if (!decode_managed_install_coordinator(plan.journal.operation_context, coordinator, detail))
        return invalid(detail);
    const bool prepared = coordinator.phase == "terminal_projection_prepared";
    const bool replay_pending = coordinator.phase == "provider_replay_prepared";
    plan.replay_attempt = coordinator.replay_attempt;
    auto& apply = plan.original.apply;
    apply = std::move(coordinator.apply);
    auto parsed_id = facman::core::InstallId::parse(apply.plan_request.install_id);
    auto parsed_transaction = facman::core::TransactionId::parse(coordinator.logical_transaction_id);
    auto provider_transaction = facman::core::TransactionId::parse(apply.transaction_id);
    plan.prepared_record_sha256 = coordinator.projected_record_sha256;
    auto workspace = context.workspace_repository().load();
    if (!parsed_id || !parsed_transaction || !provider_transaction ||
        parsed_transaction.value().str() != transaction_id ||
        !workspace || workspace.value().id.str() != plan.journal.workspace_id ||
        apply.plan_request.request_id.empty() || apply.plan_request.version.empty() ||
        !valid_utc_seconds(apply.plan_request.created_at) || !valid_utc_seconds(apply.applied_at) ||
        apply.applied_at <= apply.plan_request.created_at ||
        !apply.plan_request.archive.is_absolute() || !apply.plan_request.target.is_absolute() ||
        apply.plan_request.archive != apply.plan_request.archive.lexically_normal() ||
        apply.plan_request.target != apply.plan_request.target.lexically_normal() ||
        plan.journal.target.lexically_normal() != apply.plan_request.target ||
        plan.journal.sources.front().lexically_normal() != apply.plan_request.archive) return invalid("durable binding");
    plan.install_id = parsed_id.take_value();
    auto record_path = context.layout().install_ref(plan.install_id);
    auto legacy_path = context.layout().legacy_install_ref(plan.install_id);
    if (!record_path || !legacy_path) return invalid("install record path");
    plan.record_path = record_path.take_value();
    std::error_code path_error;
    auto legacy = fs::symlink_status(legacy_path.value(), path_error);
    if ((path_error && path_error != std::errc::no_such_file_or_directory) ||
        legacy.type() != fs::file_type::not_found) return invalid("legacy record appeared");
    path_error.clear();
    auto record = fs::symlink_status(plan.record_path, path_error);
    if ((path_error && path_error != std::errc::no_such_file_or_directory) ||
        (record.type() != fs::file_type::not_found && !fs::is_regular_file(record))) return invalid("record ownership");
    if (fs::is_regular_file(record)) {
        plan.record_text = read_text(plan.record_path);
        if (plan.record_text.empty()) return invalid("record cannot be read stably");
    }
    auto inspected = context.setup().inspect_install_recovery(plan.original);
    if (!inspected) return facman::core::Result<NewInstallRecoveryPlan>::failure(inspected.error());
    if (replay_pending && (inspected.value().classification == "no_provider_effect" ||
            inspected.value().replay_genesis_missing)) {
        // An interruption before the child journal is durable must never close
        // the logical operation as effect-free. Preserve any child audit and
        // replay the unchanged origin into a new, distinct transaction.
        if (!facman::core::TransactionId::parse(coordinator.replay_origin_transaction_id))
            return invalid("replay origin transaction");
        if (inspected.value().replay_genesis_missing) {
            if (inspected.value().replay_origin_transaction_id != coordinator.replay_origin_transaction_id ||
                inspected.value().replay_origin_snapshot_sha256 != coordinator.replay_origin_snapshot_sha256)
                return invalid("incomplete child does not bind its durable reviewed origin");
            plan.retained_child_transaction_id = apply.transaction_id;
            plan.retained_child_snapshot_sha256 = inspected.value().provider_journal_snapshot_sha256;
        }
        apply.transaction_id = coordinator.replay_origin_transaction_id;
        apply.is_stream_replay = apply.transaction_id != coordinator.logical_transaction_id;
        inspected = context.setup().inspect_install_recovery(plan.original);
        if (!inspected) return facman::core::Result<NewInstallRecoveryPlan>::failure(inspected.error());
        if (inspected.value().provider_journal_snapshot_sha256 != coordinator.replay_origin_snapshot_sha256 ||
            inspected.value().provider_audit_chain_digest != coordinator.replay_origin_audit_digest)
            return invalid("prepared replay origin changed");
    }
    plan.inspection = inspected.take_value();
    if (plan.inspection.classification == "provider_replay_available" && plan.replay_attempt >= 64U)
        plan.inspection.classification = "indeterminate";
    plan.action = plan.inspection.classification == "provider_installed" ? "project_terminal" :
        plan.inspection.classification == "provider_rollback_available" ? "rollback_provider" :
        plan.inspection.classification == "provider_rolled_back" ? "close_provider_rollback" :
        plan.inspection.classification == "provider_replay_available" && plan.replay_attempt < 64U ? "replay_provider" :
        plan.inspection.classification == "no_provider_effect" ? "close_no_provider_effect" : "none";
    if (plan.action == "replay_provider") plan.replay_transaction_id = "tx-replay-" +
        digest_text(transaction_id + "/" + std::to_string(plan.replay_attempt + 1U)).substr(0, 32);
    if (plan.action == "project_terminal") {
        plan.projected_record = managed_install_record(apply, plan.inspection.terminal);
        if (plan.projected_record.empty()) return invalid("terminal record cannot be projected");
    }
    if ((!plan.record_text.empty() && plan.record_text != plan.projected_record) ||
        (prepared && plan.prepared_record_sha256 != digest_text(plan.projected_record))) {
        return facman::core::Result<NewInstallRecoveryPlan>::failure({
            "install_recovery_projection_conflict", "Managed install reference differs from its exact prepared postimage", ""});
    }
    auto raw_journal = context.transactions().load_journal(parsed_transaction.value());
    if (!raw_journal) return invalid(raw_journal.error().message);
    plan.journal_sha256 = digest_text(raw_journal.value());
    plan.plan_id = "install-recovery." + transaction_id;
    const std::string unsigned_plan = new_install_recovery_document(
        plan, plan.action == "none" ? "blocked" : "planned", "");
    auto canonical = canonicalize_managed_uninstall_recovery_plan(unsigned_plan);
    if (!canonical) return invalid(canonical.error().message);
    plan.plan_digest = digest_text(canonical.value());
    plan.output = new_install_recovery_document(
        plan, plan.action == "none" ? "blocked" : "planned", plan.plan_digest);
    return facman::core::Result<NewInstallRecoveryPlan>::success(std::move(plan));
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

struct ManagedRepairRecoveryPlan {
    facman::transaction::Record journal;
    ManagedRepairCoordinator coordinator;
    facman::workspace::InstallRecord install;
    std::string install_record_text;
    std::string journal_sha256;
    RepairRecoveryInspection inspection;
    std::string plan_id;
    std::string plan_digest;
    std::string action;
    std::string projected_record;
    std::string projected_record_sha256;
    std::string output;
};

std::string repair_recovery_document(
    const ManagedRepairRecoveryPlan& plan,
    const std::string& status,
    const std::string& digest)
{
    facman::core::json::ObjectBuilder document;
    document.add_string("schema", "facman.managed_repair_recovery.v1");
    document.add_string("operation", "repair");
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
    document.add_string("provider_journal_snapshot_sha256",
        plan.inspection.provider_journal_snapshot_sha256);
    document.add_string("provider_installed_state_sha256",
        plan.inspection.provider_installed_state_digest);
    document.add_bool("target_exists", plan.inspection.target_exists);
    document.add_string("projected_record_sha256", plan.projected_record_sha256);
    return document.serialize();
}

facman::core::Result<ManagedRepairRecoveryPlan> build_repair_recovery_plan(
    ApplicationContext& application,
    const std::string& transaction_id)
{
    ManagedRepairRecoveryPlan result;
    std::string detail;
    if (!facman::transaction::read_record(
            application.workspace(), transaction_id, result.journal, detail)) {
        return facman::core::Result<ManagedRepairRecoveryPlan>::failure({
            "recovery_journal_invalid", "Managed repair coordinator journal is invalid", detail});
    }
    if (result.journal.schema_version != 2U ||
        result.journal.command_id != "installs.repair.apply" ||
        result.journal.commit_strategy != "provider_repair_then_durable_install_reference_replacement" ||
        result.journal.transaction_id != transaction_id || result.journal.sources.size() != 2U ||
        !decode_managed_repair_coordinator(
            result.journal.operation_context, result.coordinator, detail) ||
        result.coordinator.transaction_id != transaction_id) {
        return facman::core::Result<ManagedRepairRecoveryPlan>::failure({
            "recovery_journal_invalid", "Transaction is not an exact managed repair coordinator", detail});
    }
    const bool recoverable_state = result.journal.state == facman::transaction::State::committing ||
        result.journal.state == facman::transaction::State::commit_uncertain ||
        result.journal.state == facman::transaction::State::recovery_required ||
        result.journal.state == facman::transaction::State::committed ||
        result.journal.state == facman::transaction::State::audited ||
        result.journal.state == facman::transaction::State::complete;
    if (!recoverable_state) {
        return facman::core::Result<ManagedRepairRecoveryPlan>::failure({
            "recovery_journal_invalid", "Managed repair coordinator is not recoverable",
            facman::transaction::state_name(result.journal.state)});
    }
    auto workspace = application.workspace_repository().load();
    if (!workspace || result.journal.workspace_id != workspace.value().id.str()) {
        return facman::core::Result<ManagedRepairRecoveryPlan>::failure({
            "recovery_journal_invalid", "Managed repair coordinator belongs to another workspace",
            "workspace id"});
    }
    auto parsed_install = facman::core::InstallId::parse_legacy(result.coordinator.install_id);
    if (!parsed_install) return facman::core::Result<ManagedRepairRecoveryPlan>::failure({
        "recovery_journal_invalid", "Managed repair coordinator install id is invalid",
        parsed_install.error().message});
    auto loaded = application.installs().load(parsed_install.value());
    if (!loaded) return facman::core::Result<ManagedRepairRecoveryPlan>::failure({
        "repair_recovery_projection_conflict", "Managed install reference is unavailable",
        loaded.error().message});
    result.install = loaded.take_value();
    result.install_record_text = read_text(result.install.source_path);
    if (result.install_record_text.empty() ||
        result.journal.sources.front().lexically_normal() != result.install.source_path.lexically_normal() ||
        result.journal.target.lexically_normal() !=
            facman::platform::path_from_utf8(result.coordinator.target_root).lexically_normal() ||
        result.install.root.lexically_normal() != result.journal.target.lexically_normal()) {
        return facman::core::Result<ManagedRepairRecoveryPlan>::failure({
            "repair_recovery_projection_conflict",
            "Managed install reference no longer binds the repair coordinator",
            "record path or target"});
    }
    RepairRecoveryRequest request;
    request.request_id = result.coordinator.request_id;
    request.plan_id = result.coordinator.plan_id;
    request.install_id = result.coordinator.install_id;
    request.plan_created_at = result.coordinator.plan_created_at;
    request.reviewed_plan_digest = result.coordinator.reviewed_plan_digest;
    request.provider_plan_digest = result.coordinator.provider_plan_digest;
    request.transaction_id = result.coordinator.transaction_id;
    request.applied_at = result.coordinator.applied_at;
    request.target = facman::platform::path_from_utf8(result.coordinator.target_root);
    request.pre_installed_state_digest = result.coordinator.provider_installed_state_digest;
    request.pre_ownership_manifest_digest = result.coordinator.provider_ownership_manifest_digest;
    request.recipe_digest = result.coordinator.provider_recipe_digest;
    request.source_digest = result.coordinator.provider_source_digest;
    request.pre_setup_state_ref = result.coordinator.pre_setup_state_ref;
    request.pre_last_verification_identity = result.coordinator.pre_last_verification_identity;
    request.pre_state_revision = result.coordinator.pre_state_revision;
    request.pre_lifecycle_status = result.coordinator.pre_lifecycle_status;
    auto inspected = application.setup().inspect_repair_recovery(request);
    if (!inspected) return facman::core::Result<ManagedRepairRecoveryPlan>::failure(inspected.error());
    result.inspection = inspected.take_value();
    result.action = result.inspection.classification == "provider_repaired"
        ? "project_terminal"
        : result.inspection.classification == "no_provider_effect"
            ? "close_no_provider_effect" : "none";
    if (result.action == "project_terminal") {
        result.projected_record = project_repaired_install_record(
            result.install_record_text, result.inspection.terminal_report);
        if (result.projected_record.empty()) {
            return facman::core::Result<ManagedRepairRecoveryPlan>::failure({
                "repair_recovery_projection_conflict",
                "Managed repair terminal record cannot be projected", result.coordinator.install_id});
        }
        result.projected_record_sha256 = digest_text(result.projected_record);
    } else {
        result.projected_record = result.install_record_text;
        result.projected_record_sha256 = result.coordinator.pre_record_sha256;
    }
    const std::string current_sha256 = digest_text(result.install_record_text);
    if (result.action == "close_no_provider_effect" &&
        current_sha256 != result.coordinator.pre_record_sha256) {
        return facman::core::Result<ManagedRepairRecoveryPlan>::failure({
            "repair_recovery_projection_conflict",
            "Managed install reference changed before no-effect repair recovery", current_sha256});
    }
    if (result.action == "project_terminal" &&
        current_sha256 != result.coordinator.pre_record_sha256 &&
        current_sha256 != result.projected_record_sha256) {
        return facman::core::Result<ManagedRepairRecoveryPlan>::failure({
            "repair_recovery_projection_conflict",
            "Managed install reference is neither the repair preimage nor terminal postimage",
            current_sha256});
    }
    auto parsed_transaction = facman::core::TransactionId::parse(transaction_id);
    auto raw_journal = parsed_transaction
        ? application.transactions().load_journal(parsed_transaction.value())
        : facman::core::Result<std::string>::failure({"invalid_identifier", "Invalid transaction id", transaction_id});
    if (!raw_journal) return facman::core::Result<ManagedRepairRecoveryPlan>::failure({
        "recovery_journal_invalid", "Managed repair coordinator could not be read stably",
        raw_journal.error().message});
    result.journal_sha256 = digest_text(raw_journal.value());
    result.plan_id = "repair-recovery." + transaction_id;
    const std::string unsigned_plan = repair_recovery_document(
        result, result.action == "none" ? "blocked" : "planned", "");
    auto canonical = canonicalize_managed_uninstall_recovery_plan(unsigned_plan);
    if (!canonical) return facman::core::Result<ManagedRepairRecoveryPlan>::failure(canonical.error());
    result.plan_digest = digest_text(canonical.value());
    result.output = repair_recovery_document(
        result, result.action == "none" ? "blocked" : "planned", result.plan_digest);
    return facman::core::Result<ManagedRepairRecoveryPlan>::success(std::move(result));
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
            error.code == "uninstall_recovery_indeterminate" ||
                error.code == "transaction_recovery_required" || error.code == "recovery_write_refused" ?
                facman::core::OutcomeKind::recovery_required :
            retryable ? facman::core::OutcomeKind::refused : error.kind);
}

ApplicationResult repair_recovery_failure(
    const std::string& operation,
    const facman::core::Error& error)
{
    const bool conflict = error.code == "repair_recovery_projection_conflict";
    const bool retryable = error.code == "recovery_lock_contended" ||
        error.code == "recovery_write_refused" || error.code == "stale_plan";
    return refused(
        safety_refusal(operation, error.code, error.message, error.detail, true, retryable),
        error.code, error.message,
        conflict ? facman::core::OutcomeKind::conflict :
            error.code == "repair_recovery_indeterminate" ||
                error.code == "transaction_recovery_required" || error.code == "recovery_write_refused" ?
                facman::core::OutcomeKind::recovery_required :
            retryable ? facman::core::OutcomeKind::refused : error.kind);
}

ApplicationResult install_recovery_failure(
    const std::string& operation,
    const facman::core::Error& error)
{
    const bool conflict = error.code == "install_recovery_projection_conflict";
    const bool pending = error.code == "install_recovery_indeterminate" ||
        error.code == "transaction_recovery_required" || error.code == "recovery_write_refused";
    const bool retryable = error.code == "recovery_lock_contended" || error.code == "stale_plan";
    return refused(
        safety_refusal(operation, error.code, error.message, error.detail, true, retryable),
        error.code, error.message,
        conflict ? facman::core::OutcomeKind::conflict :
            pending ? facman::core::OutcomeKind::recovery_required :
            retryable ? facman::core::OutcomeKind::refused : error.kind);
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
    const char* interrupt_before_provider =
        std::getenv("FACMAN_TEST_REPAIR_INTERRUPT_BEFORE_PROVIDER");
    if (interrupt_before_provider != nullptr && std::string(interrupt_before_provider) == "1") {
        session.failed("Injected interruption before provider repair entry");
        return refused(
            safety_refusal("installs.repair.apply", "transaction_recovery_required",
                "Injected interruption before provider repair entry", request.transaction_id, false),
            "transaction_recovery_required", "Injected interruption before provider repair entry",
            facman::core::OutcomeKind::recovery_required);
    }
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
    auto coordinator_lease = ManagedInstallRecoveryLease::acquire(
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
    facman::transaction::Record journal;
    std::string detail;
    if (!facman::transaction::read_record(
            context.workspace(), parsed.value().str(), journal, detail)) {
        return uninstall_recovery_failure("installs.recovery.inspect", {
            "recovery_journal_invalid", "Managed install recovery journal is invalid", detail});
    }
    if (journal.command_id == "installs.install.apply") {
        auto planned = build_new_install_recovery_plan(context, parsed.value().str());
        if (!planned) return install_recovery_failure("installs.recovery.inspect", planned.error());
        ApplicationResult result;
        result.output = planned.value().output;
        return result;
    }
    if (journal.command_id == "installs.repair.apply") {
        auto repair = build_repair_recovery_plan(context, parsed.value().str());
        if (!repair) return repair_recovery_failure("installs.recovery.inspect", repair.error());
        ApplicationResult result;
        result.output = repair.value().output;
        return result;
    }
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
    auto lease = ManagedInstallRecoveryLease::acquire(context.workspace(), parsed.value().str(), true);
    if (!lease) return uninstall_recovery_failure("installs.recovery.apply", lease.error());
    facman::transaction::Record recovery_journal;
    std::string recovery_detail;
    if (!facman::transaction::read_record(
            context.workspace(), parsed.value().str(), recovery_journal, recovery_detail)) {
        return uninstall_recovery_failure("installs.recovery.apply", {
            "recovery_journal_invalid", "Managed install recovery journal is invalid", recovery_detail});
    }
    if (recovery_journal.command_id == "installs.install.apply") {
        auto planned = build_new_install_recovery_plan(context, parsed.value().str());
        if (!planned) return install_recovery_failure("installs.recovery.apply", planned.error());
        auto plan = planned.take_value();
        if (request.confirmation != "APPLY" || request.plan_id != plan.plan_id ||
            request.plan_digest != plan.plan_digest) return install_recovery_failure(
                "installs.recovery.apply", {"stale_plan",
                    "Reviewed install recovery plan changed before apply", request.plan_id});
        if (plan.action == "none") return install_recovery_failure("installs.recovery.apply", {
            "install_recovery_indeterminate", "Provider install is not in a safely projectable terminal state",
            plan.inspection.provider_observed_state});
        if (facman::transaction::terminal(plan.journal.state)) {
            if (plan.action == "rollback_provider" || plan.action == "replay_provider") return install_recovery_failure("installs.recovery.apply", {
                "install_recovery_indeterminate", "Terminal coordinator conflicts with pending provider effects", request.transaction_id});
            ApplicationResult result;
            result.output = new_install_recovery_document(plan, "completed", request.plan_digest);
            return result;
        }
        if (plan.action == "replay_provider") {
            if (!plan.retained_child_transaction_id.empty()) plan.journal.recovery_actions.push_back(
                "retained_incomplete_replay:" + plan.retained_child_transaction_id + ":" + plan.retained_child_snapshot_sha256);
            plan.journal.operation_context = prepare_managed_install_replay_context(
                plan.journal.operation_context, plan.replay_transaction_id,
                plan.original.apply.transaction_id, plan.inspection);
            std::string detail;
            if (plan.journal.operation_context.empty() || !facman::transaction::checkpoint(
                    context.workspace(), plan.journal, "provider_replay_prepared", detail))
                return install_recovery_failure("installs.recovery.apply", {"recovery_write_refused",
                    "Provider replay intent could not be recorded", detail});
            const char* before = std::getenv("FACMAN_TEST_INSTALL_RECOVERY_INTERRUPT_BEFORE_REPLAY");
            if (before != nullptr && std::string(before) == "1") return install_recovery_failure(
                "installs.recovery.apply", {"transaction_recovery_required",
                    "Injected interruption after durable replay intent", request.transaction_id});
            auto replayed = context.setup().replay_install_recovery(
                plan.original, plan.inspection, plan.replay_transaction_id);
            if (!replayed) return install_recovery_failure("installs.recovery.apply", replayed.error());
            const char* after = std::getenv("FACMAN_TEST_INSTALL_RECOVERY_INTERRUPT_AFTER_REPLAY");
            if (after != nullptr && std::string(after) == "1") return install_recovery_failure(
                "installs.recovery.apply", {"transaction_recovery_required",
                    "Injected interruption after verified provider replay", request.transaction_id});
            auto disposition = build_new_install_recovery_plan(context, parsed.value().str());
            if (!disposition) return install_recovery_failure("installs.recovery.apply", disposition.error());
            plan = disposition.take_value();
            if (plan.action != "project_terminal") return install_recovery_failure("installs.recovery.apply", {
                "transaction_recovery_required", "Provider replay disposition changed before projection", request.transaction_id});
            plan.journal.recovery_actions.push_back("replayed_provider_install_into_distinct_staging");
        }
        if (plan.action == "rollback_provider") {
            std::string detail;
            if (!facman::transaction::checkpoint(context.workspace(), plan.journal,
                    "provider_rollback_started", detail)) return install_recovery_failure(
                "installs.recovery.apply", {"recovery_write_refused", "Provider rollback intent could not be recorded", detail});
            auto rolled_back = context.setup().rollback_install_recovery(plan.original, plan.inspection);
            if (!rolled_back) return install_recovery_failure("installs.recovery.apply", rolled_back.error());
            auto disposition = build_new_install_recovery_plan(context, parsed.value().str());
            if (!disposition) return install_recovery_failure("installs.recovery.apply", disposition.error());
            plan = disposition.take_value();
            if (plan.inspection.classification != "provider_rolled_back" || plan.action != "close_provider_rollback")
                return install_recovery_failure("installs.recovery.apply", {"transaction_recovery_required",
                    "Provider rollback disposition changed before journal closure", request.transaction_id});
            plan.journal.recovery_actions.push_back("rolled_back_provider_install_staging");
            const char* interrupted = std::getenv("FACMAN_TEST_INSTALL_RECOVERY_INTERRUPT_AFTER_ROLLBACK");
            if (interrupted != nullptr && std::string(interrupted) == "1") return install_recovery_failure(
                "installs.recovery.apply", {"transaction_recovery_required",
                    "Injected interruption after provider install rollback", request.transaction_id});
        }
        plan.journal.operation_context = prepared_install_context(
            plan.journal.operation_context, digest_text(plan.projected_record));
        std::string detail;
        if (plan.journal.operation_context.empty() || !facman::transaction::checkpoint(
                context.workspace(), plan.journal, "terminal_projection_prepared", detail)) {
            return install_recovery_failure("installs.recovery.apply", {
                "recovery_write_refused", "Install recovery postimage checkpoint failed", detail});
        }
        if (plan.action == "project_terminal" && plan.record_text.empty()) {
            facman::workspace::InstallRecord record;
            record.id = plan.install_id;
            auto created = context.installs().create(record, plan.projected_record);
            if (!created) return install_recovery_failure("installs.recovery.apply", {
                "install_recovery_projection_conflict", "Recovered managed install reference could not be created",
                created.error().message});
        }
        const char* interrupt = std::getenv("FACMAN_TEST_INSTALL_RECOVERY_INTERRUPT_AFTER_PROJECTION");
        if (interrupt != nullptr && std::string(interrupt) == "1") return install_recovery_failure(
            "installs.recovery.apply", {"transaction_recovery_required",
                "Injected interruption after install recovery projection", request.transaction_id});
        plan.journal.recovery_actions.push_back(plan.action == "project_terminal" ?
            "projected_managed_install_reference" : plan.action == "close_provider_rollback" ?
                "confirmed_provider_install_rollback" : "confirmed_no_provider_effect");
        if (plan.journal.state == facman::transaction::State::committing) {
            if (!facman::transaction::advance(context.workspace(), plan.journal,
                    plan.action == "project_terminal" ? "committed" : "recovery_required",
                    "install_coordinator_recovered", detail)) return install_recovery_failure(
                "installs.recovery.apply", {"recovery_write_refused",
                    "Recovered install disposition could not be recorded", detail});
        }
        if (plan.journal.state == facman::transaction::State::audited) {
            if (!facman::transaction::advance(context.workspace(), plan.journal, "complete",
                    "journal_closed", detail)) return install_recovery_failure(
                "installs.recovery.apply", {"recovery_write_refused", "Install recovery journal could not close", detail});
        } else if (!facman::transaction::terminal(plan.journal.state) &&
            !facman::transaction::complete(context.workspace(), plan.journal, detail)) {
            return install_recovery_failure("installs.recovery.apply", {
                "recovery_write_refused", "Install recovery journal could not close", detail});
        }
        auto final_journal = context.transactions().load_journal(parsed.value());
        if (!final_journal) return install_recovery_failure("installs.recovery.apply", {
            "recovery_write_refused", "Completed install recovery journal cannot be read", final_journal.error().message});
        plan.journal_sha256 = digest_text(final_journal.value());
        plan.record_text = plan.action == "project_terminal" ? read_text(plan.record_path) : std::string();
        ApplicationResult result;
        result.output = new_install_recovery_document(plan, "completed", request.plan_digest);
        return result;
    }
    if (recovery_journal.command_id == "installs.repair.apply") {
        auto planned_repair = build_repair_recovery_plan(context, parsed.value().str());
        if (!planned_repair) {
            return repair_recovery_failure("installs.recovery.apply", planned_repair.error());
        }
        auto plan = planned_repair.take_value();
        if (request.confirmation != "APPLY" || request.plan_id != plan.plan_id ||
            request.plan_digest != plan.plan_digest) {
            return repair_recovery_failure("installs.recovery.apply", {
                "stale_plan", "Reviewed repair recovery plan changed before apply", request.plan_id});
        }
        if (plan.action == "none") return repair_recovery_failure("installs.recovery.apply", {
            "repair_recovery_indeterminate",
            "Universal Setup repair is not in a safely projectable terminal state",
            plan.inspection.provider_observed_state});
        if (facman::transaction::terminal(plan.journal.state)) {
            ApplicationResult result;
            result.output = repair_recovery_document(plan, "completed", request.plan_digest);
            return result;
        }
        const std::string current_sha256 = digest_text(plan.install_record_text);
        if (plan.action == "project_terminal" &&
            current_sha256 == plan.coordinator.pre_record_sha256) {
            auto replaced = context.installs().replace(
                plan.install, plan.coordinator.pre_record_sha256, plan.projected_record);
            if (!replaced) return repair_recovery_failure("installs.recovery.apply", {
                replaced.error().code == "workspace_record_preimage_changed"
                    ? "repair_recovery_projection_conflict" : "recovery_write_refused",
                "Repair terminal reference projection failed", replaced.error().message});
        } else if (plan.action == "project_terminal" &&
            current_sha256 != plan.projected_record_sha256) {
            return repair_recovery_failure("installs.recovery.apply", {
                "repair_recovery_projection_conflict",
                "Managed install reference changed before repair recovery projection",
                current_sha256});
        }
        const char* interrupt = std::getenv("FACMAN_TEST_REPAIR_RECOVERY_INTERRUPT_AFTER_PROJECTION");
        if (interrupt != nullptr && std::string(interrupt) == "1") {
            return repair_recovery_failure("installs.recovery.apply", {
                "transaction_recovery_required",
                "Injected interruption after repair recovery projection", request.transaction_id});
        }
        plan.journal.recovery_actions.push_back(
            plan.action == "project_terminal" ? "projected_repaired_install_reference" :
                "confirmed_no_provider_effect");
        std::string detail;
        if (plan.journal.state == facman::transaction::State::committing) {
            if (plan.action == "project_terminal") {
                if (!facman::transaction::advance(
                        context.workspace(), plan.journal, "committed",
                        "repair_terminal_projection_recovered", detail)) {
                    return repair_recovery_failure("installs.recovery.apply", {
                        "recovery_write_refused", "Recovered repair commit could not be recorded", detail});
                }
            } else if (!facman::transaction::advance(
                    context.workspace(), plan.journal, "recovery_required",
                    "repair_no_effect_recovered", detail)) {
                return repair_recovery_failure("installs.recovery.apply", {
                    "recovery_write_refused", "No-effect repair recovery could not be recorded", detail});
            }
        }
        if (plan.journal.state == facman::transaction::State::audited) {
            if (!facman::transaction::advance(
                    context.workspace(), plan.journal, "complete", "journal_closed", detail)) {
                return repair_recovery_failure("installs.recovery.apply", {
                    "recovery_write_refused", "Repair recovery journal could not be closed", detail});
            }
        } else if (!facman::transaction::terminal(plan.journal.state) &&
            !facman::transaction::complete(context.workspace(), plan.journal, detail)) {
            return repair_recovery_failure("installs.recovery.apply", {
                "recovery_write_refused", "Repair recovery journal could not be closed", detail});
        }
        auto final_journal = context.transactions().load_journal(parsed.value());
        if (!final_journal) return repair_recovery_failure("installs.recovery.apply", {
            "recovery_write_refused", "Completed repair recovery journal could not be read",
            final_journal.error().message});
        plan.journal_sha256 = digest_text(final_journal.value());
        plan.install_record_text = read_text(plan.install.source_path);
        if (plan.install_record_text.empty()) return repair_recovery_failure("installs.recovery.apply", {
            "workspace_record_read_failed", "Completed repair recovery reference could not be read",
            facman::platform::path_to_utf8(plan.install.source_path)});
        ApplicationResult result;
        result.output = repair_recovery_document(plan, "completed", request.plan_digest);
        return result;
    }
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

ApplicationResult apply_install(ApplicationContext& context, const ServiceOperationRequest& request)
{
#if FACMAN_WITH_SETUP
#if !defined(_WIN32)
    (void)request;
    return unavailable(context, "installs.install.apply", "setup_platform_recipe_unavailable",
        "The current managed portable install recipe applies to Windows ZIP packages");
#else
    if (!valid_utc_seconds(request.plan_created_at) || !valid_utc_seconds(request.applied_at) ||
        request.applied_at <= request.plan_created_at || request.confirmation != "APPLY") {
        return refused(safety_refusal("installs.install.apply", "invalid_timestamp",
            "Install apply requires exact confirmation and advancing UTC timestamps",
            "plan_created_at/applied_at", false), "invalid_timestamp",
            "Install apply requires exact confirmation and advancing UTC timestamps");
    }
    auto parsed_id = facman::core::InstallId::parse(request.install_id);
    auto parsed_transaction = facman::core::TransactionId::parse(request.transaction_id);
    if (!parsed_id || !parsed_transaction) {
        const auto& error = !parsed_id ? parsed_id.error() : parsed_transaction.error();
        return refused(safety_refusal("installs.install.apply", error.code,
            "Install or transaction id is not portable", error.message, false),
            error.code, error.message, error.kind);
    }
    auto record_path = context.layout().install_ref(parsed_id.value());
    auto legacy_path = context.layout().legacy_install_ref(parsed_id.value());
    if (!record_path || !legacy_path) return refused(safety_refusal("installs.install.apply",
            "invalid_identifier", "Install record path cannot be resolved", request.install_id, false),
        "invalid_identifier", "Install record path cannot be resolved");
    std::error_code path_error;
    const auto current_record = fs::symlink_status(record_path.value(), path_error);
    if ((path_error && path_error != std::errc::no_such_file_or_directory) ||
        current_record.type() != fs::file_type::not_found) return refused(safety_refusal(
            "installs.install.apply", "persistent_target_exists", "Install identity already has a workspace record",
            request.install_id, true), "persistent_target_exists", "Install identity already has a workspace record");
    path_error.clear();
    const auto legacy_record = fs::symlink_status(legacy_path.value(), path_error);
    if ((path_error && path_error != std::errc::no_such_file_or_directory) ||
        legacy_record.type() != fs::file_type::not_found) return refused(safety_refusal(
            "installs.install.apply", "persistent_target_exists", "Install identity already has a legacy record",
            request.install_id, true), "persistent_target_exists", "Install identity already has a legacy record");
    facman::transaction::Record existing;
    std::string existing_detail;
    if (facman::transaction::read_record(context.workspace(), request.transaction_id,
            existing, existing_detail)) return refused(safety_refusal(
        "installs.install.apply", "operation_specific_recovery_required",
        "Existing managed install transaction must be recovered", request.transaction_id, true),
        "operation_specific_recovery_required", "Existing managed install transaction must be recovered",
        facman::core::OutcomeKind::recovery_required);
    InstallApplyRequest apply;
    apply.plan_request.request_id = request.plan_id;
    apply.plan_request.install_id = parsed_id.value().str();
    apply.plan_request.created_at = request.plan_created_at;
    apply.plan_request.version = request.version;
    path_error.clear();
    apply.plan_request.archive = fs::absolute(
        facman::platform::path_from_utf8(request.archive), path_error).lexically_normal();
    if (path_error) return refused(safety_refusal("installs.install.apply", "setup_plan_path_invalid",
        "Reviewed archive path cannot be resolved", request.archive, false),
        "setup_plan_path_invalid", "Reviewed archive path cannot be resolved");
    apply.plan_request.target = fs::absolute(
        facman::platform::path_from_utf8(request.target_root), path_error).lexically_normal();
    if (path_error) return refused(safety_refusal("installs.install.apply", "setup_plan_path_invalid",
        "Reviewed target path cannot be resolved", request.target_root, false),
        "setup_plan_path_invalid", "Reviewed target path cannot be resolved");
    apply.reviewed_plan.plan_id = request.plan_id;
    apply.reviewed_plan.plan_digest = request.plan_digest;
    apply.transaction_id = parsed_transaction.value().str();
    apply.applied_at = request.applied_at;
    apply.confirmation = request.confirmation;
    auto reviewed = context.setup().plan_install(apply.plan_request);
    if (!reviewed || reviewed.value().plan_id != request.plan_id ||
        reviewed.value().plan_digest != request.plan_digest) return refused(safety_refusal(
            "installs.install.apply", "stale_plan", "Reviewed install plan changed before apply",
            reviewed ? request.plan_id : reviewed.error().message, true),
        "stale_plan", "Reviewed install plan changed before apply");
    auto workspace_ready = context.workspace_repository().ensure();
    if (!workspace_ready) return refused(safety_refusal("installs.install.apply",
        "recovery_write_refused", "Workspace cannot prepare managed install coordination",
        workspace_ready.error().message, true), "recovery_write_refused", workspace_ready.error().message);
    facman::core::json::ObjectBuilder coordinator;
    coordinator.add_string("schema", "facman.managed_install_coordinator.v2");
    coordinator.add_string("phase", "provider_entry_started");
    coordinator.add_string("install_id", request.install_id);
    coordinator.add_string("plan_id", request.plan_id);
    coordinator.add_string("plan_digest", request.plan_digest);
    coordinator.add_string("plan_created_at", request.plan_created_at);
    coordinator.add_string("transaction_id", request.transaction_id);
    coordinator.add_string("applied_at", request.applied_at);
    coordinator.add_string("version", request.version);
    coordinator.add_string("archive", facman::platform::path_to_utf8(apply.plan_request.archive));
    coordinator.add_string("target_root", facman::platform::path_to_utf8(apply.plan_request.target));
    coordinator.add_string("source_archive_sha256", reviewed.value().source_archive_sha256);
    coordinator.add_string("recipe_digest", reviewed.value().recipe_digest);
    coordinator.add_string("component_selection", reviewed.value().component_selection);
    coordinator.add_string("provider_plan_request", reviewed.value().plan_request);
    coordinator.add_string("provider_transaction_id", request.transaction_id);
    coordinator.add_string("replay_attempt", "0");
    coordinator.add_string("replay_origin_transaction_id", "");
    coordinator.add_string("replay_origin_snapshot_sha256", "");
    coordinator.add_string("replay_origin_audit_digest", "");
    facman::transaction::Record journal;
    journal.transaction_id = request.transaction_id;
    journal.command_id = "installs.install.apply";
    journal.target = apply.plan_request.target;
    journal.sources = {apply.plan_request.archive};
    journal.commit_strategy = "provider_install_then_durable_install_reference_create";
    journal.operation_context = coordinator.serialize();
    auto started = facman::transaction::TransactionSession::begin(
        context.workspace(), std::move(journal));
    if (!started) return refused(safety_refusal("installs.install.apply", "recovery_write_refused",
        "Install coordinator journal could not be prepared", started.error().message, true),
        "recovery_write_refused", started.error().message,
        facman::core::OutcomeKind::recovery_required);
    auto session = started.take_value();
    auto lease = ManagedInstallRecoveryLease::acquire(context.workspace(), request.transaction_id, false);
    if (!lease) return refused(safety_refusal("installs.install.apply", lease.error().code,
        "Managed install coordinator is already in use", lease.error().message, true),
        lease.error().code, lease.error().message, facman::core::OutcomeKind::recovery_required);
    facman::transaction::Record current_journal;
    std::string current_detail;
    if (!facman::transaction::read_record(context.workspace(), request.transaction_id,
            current_journal, current_detail) || current_journal.state != facman::transaction::State::requested ||
        current_journal.operation_context != session.record().operation_context) return refused(safety_refusal(
            "installs.install.apply", "operation_specific_recovery_required",
            "Managed install coordinator changed before provider entry", request.transaction_id, true),
        "operation_specific_recovery_required", "Managed install coordinator changed before provider entry",
        facman::core::OutcomeKind::recovery_required);
    if (!session.validated("reviewed_provider_plan_bound") ||
        !session.planned("exact_provider_plan_persisted") ||
        !session.staged("provider_entry_prepared") ||
        !session.verified("workspace_record_absent")) return refused(safety_refusal(
            "installs.install.apply", "recovery_write_refused",
            "Install coordinator journal could not enter provider phase", session.detail(), true),
        "recovery_write_refused", session.detail(), facman::core::OutcomeKind::recovery_required);
    if (!session.committing("provider_entry_started")) return refused(safety_refusal(
        "installs.install.apply", "recovery_write_refused",
        "Install provider-entry intent could not be recorded", session.detail(), true),
        "recovery_write_refused", session.detail(), facman::core::OutcomeKind::recovery_required);
    const char* before_provider = std::getenv("FACMAN_TEST_INSTALL_INTERRUPT_BEFORE_PROVIDER");
    if (before_provider != nullptr && std::string(before_provider) == "1") {
        session.failed("Injected interruption before provider install entry");
        return install_recovery_failure("installs.install.apply", {"transaction_recovery_required",
            "Injected interruption before provider install entry", request.transaction_id});
    }
    auto report = context.setup().apply_install(apply);
    if (!report) {
        session.failed(report.error().code + ": " + report.error().message);
        return refused(safety_refusal("installs.install.apply", "transaction_recovery_required",
            "Universal Setup install outcome requires recovery", report.error().message, false),
            "transaction_recovery_required", report.error().message,
            facman::core::OutcomeKind::recovery_required);
    }
    const std::string record_text = managed_install_record(apply, report.value());
    if (record_text.empty()) {
        session.failed("Installed Factorio entrypoint could not be projected");
        return refused(safety_refusal("installs.install.apply", "transaction_recovery_required",
            "Installed target cannot be projected to a managed record", request.install_id, false),
            "transaction_recovery_required", "Installed target cannot be projected to a managed record",
            facman::core::OutcomeKind::recovery_required);
    }
    session.record().operation_context = prepared_install_context(
        session.record().operation_context, digest_text(record_text));
    if (session.record().operation_context.empty() || !session.checkpoint("terminal_projection_prepared")) {
        session.failed("Managed install postimage checkpoint failed");
        return refused(safety_refusal("installs.install.apply", "transaction_recovery_required",
            "Managed install postimage could not be durably prepared", session.detail(), false),
            "transaction_recovery_required", session.detail(), facman::core::OutcomeKind::recovery_required);
    }
    const char* interrupt = std::getenv("FACMAN_TEST_INSTALL_INTERRUPT_AFTER_PROVIDER");
    if (interrupt != nullptr && std::string(interrupt) == "1") {
        session.failed("Injected interruption after provider install");
        return refused(safety_refusal("installs.install.apply", "transaction_recovery_required",
            "Injected interruption after provider install", request.transaction_id, false),
            "transaction_recovery_required", "Injected interruption after provider install",
            facman::core::OutcomeKind::recovery_required);
    }
    facman::workspace::InstallRecord record;
    record.id = parsed_id.take_value();
    auto created = context.installs().create(record, record_text);
    if (!created) {
        session.failed("Managed install record creation failed: " + created.error().message);
        return refused(safety_refusal("installs.install.apply", "transaction_recovery_required",
            "Provider install completed but its workspace record could not be committed",
            created.error().message, false), "transaction_recovery_required",
            created.error().message, facman::core::OutcomeKind::recovery_required);
    }
    if (!session.committed("managed_install_record_created") || !session.complete()) {
        return refused(safety_refusal("installs.install.apply", "transaction_recovery_required",
            "Managed install committed but its coordinator journal could not close",
            session.detail(), false), "transaction_recovery_required", session.detail(),
            facman::core::OutcomeKind::recovery_required);
    }
    ApplicationResult result;
    result.output = record_text;
    return result;
#endif
#else
    (void)request;
    return unavailable(context, "installs.install.apply", "setup_unavailable",
        "Universal Setup support is disabled in this build");
#endif
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
