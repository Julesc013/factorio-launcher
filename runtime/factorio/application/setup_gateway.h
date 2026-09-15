// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_SETUP_GATEWAY_H
#define FACMAN_FACTORIO_SETUP_GATEWAY_H

#include "fl_result.h"
#include "flb_factorio_setup_recipe.h"
#include "application_configuration.h"

#include <cstdint>
#include <filesystem>
#include <memory>
#include <string>
#include <vector>

namespace facman::factorio::application {

struct PackageVerifyRequest {
    std::filesystem::path package_root;
    std::string target_os;
    std::string target_arch;
    std::string linkage_model;
};

struct PackageVerifyResult {
    bool verified = false;
    std::string authenticity;
    std::uint64_t files_verified = 0;
    std::string detail;
};

struct InstallPlanRequest {
    std::string request_id;
    std::string install_id;
    std::string created_at;
    std::string version;
    std::filesystem::path archive;
    std::filesystem::path target;
};

struct InstallPlan {
    bool archive_inspected = false;
    bool product_layout_verified = false;
    bool inputs_confirmed = false;
    std::string plan_id;
    std::string plan_digest;
    std::string provider_response;
};

struct UninstallPlanRequest {
    std::string request_id;
    std::string plan_id;
    std::string install_id;
    std::string created_at;
    std::filesystem::path target;
    std::string setup_state_ref;
    std::string last_verification_identity;
    std::string state_revision;
    std::string lifecycle_status;
};

struct UninstallPlan {
    std::string plan_id;
    std::string plan_digest;
    std::string provider_response;
};

struct RepairFile {
    std::string relative_path;
    std::string reason;
    std::string expected_sha256;
};

struct RepairPlanRequest {
    std::string request_id;
    std::string plan_id;
    std::string install_id;
    std::string created_at;
    std::string version;
    std::filesystem::path archive;
    std::filesystem::path target;
    std::string setup_state_ref;
    std::string last_verification_identity;
    std::string state_revision;
    std::string lifecycle_status;
};

struct RepairPlan {
    std::string plan_id;
    std::string provider_plan_digest;
    std::string created_at;
    std::string installed_state_digest;
    std::string ownership_manifest_digest;
    std::string recipe_digest;
    std::string source_digest;
    std::string before_verification_digest;
    std::string pre_target_snapshot_digest;
    std::string plan_request;
    std::string provider_response;
    std::vector<RepairFile> repairs;
    std::vector<std::string> retained_unknown_paths;
};

struct RepairApplyRequest {
    RepairPlanRequest plan_request;
    RepairPlan reviewed_plan;
    std::string transaction_id;
    std::string applied_at;
    std::string confirmation;
};

struct RepairReport {
    std::string report_id;
    std::string report_digest;
    std::string completed_at;
    std::string setup_state_ref;
    std::string last_verification_identity;
    std::string state_revision;
    std::string lifecycle_status;
    std::string verification_status;
    std::string installed_state_digest;
    std::string ownership_manifest_digest;
    std::string provider_response;
};

struct RepairRecoveryRequest {
    std::string request_id;
    std::string plan_id;
    std::string install_id;
    std::string plan_created_at;
    std::string reviewed_plan_digest;
    std::string provider_plan_digest;
    std::string transaction_id;
    std::string applied_at;
    std::filesystem::path target;
    std::string pre_installed_state_digest;
    std::string pre_ownership_manifest_digest;
    std::string recipe_digest;
    std::string source_digest;
    std::string pre_setup_state_ref;
    std::string pre_last_verification_identity;
    std::string pre_state_revision;
    std::string pre_lifecycle_status;
};

struct RepairRecoveryInspection {
    std::string classification;
    std::string provider_observed_state;
    std::string provider_journal_digest;
    std::string provider_journal_snapshot_sha256;
    std::string provider_installed_state_digest;
    RepairReport terminal_report;
    bool provider_journal_present = false;
    bool target_exists = false;
};

struct ManagedRepairCoordinator {
    std::string request_id;
    std::string plan_id;
    std::string install_id;
    std::string plan_created_at;
    std::string reviewed_plan_digest;
    std::string provider_plan_digest;
    std::string provider_installed_state_digest;
    std::string provider_ownership_manifest_digest;
    std::string provider_recipe_digest;
    std::string provider_source_digest;
    std::string transaction_id;
    std::string applied_at;
    std::string target_root;
    std::string pre_record_sha256;
    std::string pre_setup_state_ref;
    std::string pre_last_verification_identity;
    std::string pre_state_revision;
    std::string pre_lifecycle_status;
    std::string phase;
};

bool decode_managed_repair_coordinator(
    const std::string& text,
    ManagedRepairCoordinator& output,
    std::string& detail);

struct ManagedRepairEnvelope {
    std::string document;
    std::string digest;
};

facman::core::Result<ManagedRepairEnvelope> encode_managed_repair_envelope(
    const RepairPlan& plan,
    const std::string& install_record_sha256);
std::string encode_managed_repair_context(
    const RepairPlanRequest& plan,
    const RepairPlan& provider_plan,
    const std::string& reviewed_plan_id,
    const std::string& reviewed_plan_digest,
    const std::string& transaction_id,
    const std::string& applied_at,
    const std::string& target,
    const std::string& pre_record_digest,
    const std::string& phase,
    const RepairReport* report,
    const std::string& projected_record_digest);
std::string project_repaired_install_record(
    const std::string& record_text,
    const RepairReport& report);

facman::core::Result<RepairReport> decode_repair_provider_report(
    const std::string& response,
    const RepairApplyRequest& request);

struct UninstallApplyRequest {
    UninstallPlanRequest plan_request;
    std::string reviewed_plan_id;
    std::string reviewed_plan_digest;
    std::string transaction_id;
    std::string applied_at;
    std::string confirmation;
};

struct UninstallReport {
    std::string report_id;
    std::string report_digest;
    std::string status;
    std::string completed_at;
    std::string ownership_manifest_digest;
    std::string setup_state_ref;
    std::string last_verification_identity;
    std::string state_revision;
    std::string lifecycle_status;
    std::string verification_status;
    std::string installed_state_digest;
    std::string audit_chain_id;
    std::string provider_response;
};

struct UninstallRecoveryRequest {
    UninstallPlanRequest plan_request;
    std::string reviewed_plan_digest;
    std::string transaction_id;
    std::string applied_at;
};

struct UninstallRecoveryInspection {
    std::string classification;
    std::string provider_observed_state;
    std::string provider_journal_digest;
    std::string provider_journal_snapshot_sha256;
    std::string provider_installed_state_digest;
    std::string ownership_manifest_digest;
    std::string setup_state_ref;
    std::string last_verification_identity;
    std::string state_revision;
    std::string lifecycle_status;
    std::string verification_status;
    bool provider_journal_present = false;
    bool target_exists = false;
};

struct UninstallProviderRecoveryReport {
    std::string observed_state;
    std::string journal_digest;
    std::string snapshot_sha256;
    std::string audit_chain_id;
    std::string audit_chain_digest;
};

facman::core::Result<UninstallProviderRecoveryReport>
decode_uninstall_provider_recovery_report(
    const std::string& response,
    const UninstallRecoveryRequest& request);
facman::core::Error wrap_uninstall_recovery_inspection_refusal(
    const facman::core::Error& provider_error,
    const std::string& message);

struct ManagedUninstallCoordinator {
    std::string schema;
    std::string request_id;
    std::string plan_id;
    std::string install_id;
    std::string plan_created_at;
    std::string reviewed_plan_digest;
    std::string transaction_id;
    std::string applied_at;
    std::string target_root;
    std::string pre_record_sha256;
    std::string pre_setup_state_ref;
    std::string pre_last_verification_identity;
    std::string pre_state_revision;
    std::string pre_lifecycle_status;
    std::string phase;
    std::string recovery_plan_id;
    std::string recovery_plan_digest;
    std::string classification;
    std::string provider_journal_snapshot_sha256;
    std::string provider_installed_state_sha256;
    std::string projected_record_sha256;
};

bool decode_managed_uninstall_coordinator(
    const std::string& text,
    ManagedUninstallCoordinator& output,
    std::string& detail);
bool validate_managed_install_recovery_lock(
    const std::string& text,
    const std::string& transaction_id,
    const std::string& identity,
    std::string& detail);
facman::core::Result<std::string> canonicalize_managed_uninstall_recovery_plan(
    const std::string& text);

bool valid_utc_seconds(const std::string& value) noexcept;

struct FactorioArchiveInspectRequest {
    std::string version;
    std::filesystem::path archive;
};

struct SetupRefusal {
    std::string code;
    std::string reason;
};

class SetupGateway {
public:
    virtual ~SetupGateway() = default;
    virtual facman::core::Result<PackageVerifyResult> verify_package(const PackageVerifyRequest& request) = 0;
    virtual facman::core::Result<facman::factorio::setup::ArchiveAssessment> inspect_install_archive(
        const FactorioArchiveInspectRequest& request) = 0;
    virtual facman::core::Result<InstallPlan> plan_install(const InstallPlanRequest& request) = 0;
    virtual facman::core::Result<UninstallPlan> plan_uninstall(
        const UninstallPlanRequest& request) = 0;
    virtual facman::core::Result<RepairPlan> plan_repair(
        const RepairPlanRequest& request) = 0;
    virtual facman::core::Result<RepairReport> apply_repair(
        const RepairApplyRequest& request) = 0;
    virtual facman::core::Result<RepairRecoveryInspection> inspect_repair_recovery(
        const RepairRecoveryRequest& request) = 0;
    virtual facman::core::Result<UninstallReport> apply_uninstall(
        const UninstallApplyRequest& request) = 0;
    virtual facman::core::Result<UninstallRecoveryInspection> inspect_uninstall_recovery(
        const UninstallRecoveryRequest& request) = 0;
    virtual facman::core::Result<SetupRefusal> verify_install(const std::string& install_id) = 0;
    virtual facman::core::Result<SetupRefusal> repair_install(const std::string& install_id) = 0;
    virtual facman::core::Result<SetupRefusal> uninstall_install(const std::string& install_id) = 0;
};

std::unique_ptr<SetupGateway> make_setup_gateway(const SetupConfiguration& configuration = {});

} // namespace facman::factorio::application

#endif
