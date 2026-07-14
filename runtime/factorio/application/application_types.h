// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_TYPES_H
#define FACMAN_FACTORIO_APPLICATION_TYPES_H

#include "flb_factorio_diagnostics.h"
#include "flb_factorio_launch_plan.h"
#include "flb_factorio_modset_operations.h"
#include "flb_factorio_modset_solver.h"
#include "flb_factorio_mods.h"
#include "flb_factorio_save_operations.h"
#include "flb_factorio_save_index.h"
#include "fl_transaction.h"
#include "fl_identity.h"
#include "fl_result.h"
#include "fl_preferences.h"
#include "flb_factorio_instance_lifecycle.h"
#include "flb_factorio_snapshots.h"
#include "flb_factorio_profiles.h"
#include "flb_factorio_server_plan.h"

#include "ulk/ulk_command.h"

#include <string>
#include <variant>
#include <vector>

namespace facman::factorio::application {

namespace diagnostics = facman::factorio::diagnostics;
namespace launch = facman::factorio::launch;
namespace modsets = facman::factorio::modsets::operations;
namespace saves = facman::factorio::saves::operations;
namespace transactions = facman::transaction;
namespace preferences = facman::preferences;
namespace instance_lifecycle = facman::factorio::instance;
namespace snapshots = facman::factorio::snapshots;
namespace profiles = facman::factorio::profiles;

enum class CommandId {
#include "generated/command_ids.inc"
    unsupported,
};

struct ScanInstallRefsRequest { std::vector<std::string> roots; };
struct DoctorRequest { std::vector<std::string> roots; };
struct ImportInstallRefRequest { std::string path; std::string install_id; };
struct InspectInstallRefRequest { std::string install_id; };
struct CreateInstanceRequest {
    std::string display_name;
    std::string instance_id;
    std::string install_id;
    std::string template_id = "vanilla";
};
struct BuildLaunchPlanRequest { std::string instance_id; };
struct ExecuteRunRequest { facman::core::InstanceId instance_id; };
struct OnboardingPlanRequest {
    std::string preferred_install;
    std::string instance_display_name;
    std::string template_id;
    std::string workspace;
};
struct ExplainInstanceRequest { facman::core::InstanceId instance_id; };
struct RecoveryRequest { std::string transaction_id; };
struct PreferencesRequest { preferences::Preferences values; };
struct ServiceOperationRequest {
    std::string operation;
    std::string name;
    std::string id;
    std::string instance_id;
    std::string path;
    std::string query;
    std::string version;
    std::string archive;
    std::string target_root;
    std::string install_id;
    std::string plan_id;
    std::string plan_digest;
    std::string confirmation;
    std::string transaction_id;
};

using ImportModRequest = modsets::ImportRequest;
using ModInventoryRequest = facman::factorio::mods::InventoryRequest;
using ModsetInstanceRequest = modsets::InstanceRequest;
using ExportModsetRequest = modsets::ExportRequest;
using ModsetSolverRequest = facman::factorio::modsets::solver::Request;
using ListSavesRequest = saves::InstanceRequest;
using SaveIndexRequest = facman::factorio::saves::index::Request;
using BackupSaveRequest = saves::BackupRequest;
using CloneSaveRequest = saves::CloneRequest;
using ExportInstanceRequest = saves::ExportRequest;
using ImportInstanceRequest = saves::ImportRequest;
using ExportDiagnosticRequest = diagnostics::ExportRequest;
using InspectInstanceRequest = instance_lifecycle::InspectRequest;
using DiffInstanceRequest = instance_lifecycle::DiffRequest;
using CloneInstanceRequest = instance_lifecycle::CloneRequest;
using RenameInstanceRequest = instance_lifecycle::RenameRequest;
using ArchiveInstanceRequest = instance_lifecycle::ArchiveRequest;
using RestoreInstanceRequest = instance_lifecycle::RestoreRequest;
using CreateSnapshotRequest = snapshots::CreateRequest;
using ListSnapshotsRequest = snapshots::ListRequest;
using SnapshotRequest = snapshots::SnapshotRequest;
using DiffSnapshotRequest = snapshots::DiffRequest;
using RestoreSnapshotRequest = snapshots::RestoreRequest;
using SnapshotRetentionRequest = snapshots::RetentionRequest;
using ProfileIdRequest = profiles::IdRequest;
using CreateProfileRequest = profiles::CreateRequest;
using CloneProfileRequest = profiles::CloneRequest;
using DiffProfileRequest = profiles::DiffRequest;
using EffectiveProfileRequest = profiles::EffectiveRequest;
using ServerPlanRequest = facman::factorio::server::Request;

using ApplicationPayload = std::variant<
    std::monostate,
    ScanInstallRefsRequest,
    DoctorRequest,
    ImportInstallRefRequest,
    InspectInstallRefRequest,
    CreateInstanceRequest,
    BuildLaunchPlanRequest,
    ExecuteRunRequest,
    OnboardingPlanRequest,
    ExplainInstanceRequest,
    ImportModRequest,
    ModInventoryRequest,
    ModsetInstanceRequest,
    ExportModsetRequest,
    ModsetSolverRequest,
    ListSavesRequest,
    SaveIndexRequest,
    BackupSaveRequest,
    CloneSaveRequest,
    ExportInstanceRequest,
    ImportInstanceRequest,
    RecoveryRequest,
    PreferencesRequest,
    InspectInstanceRequest,
    DiffInstanceRequest,
    CloneInstanceRequest,
    RenameInstanceRequest,
    ArchiveInstanceRequest,
    RestoreInstanceRequest,
    CreateSnapshotRequest,
    ListSnapshotsRequest,
    SnapshotRequest,
    DiffSnapshotRequest,
    RestoreSnapshotRequest,
    SnapshotRetentionRequest,
    ProfileIdRequest,
    CreateProfileRequest,
    CloneProfileRequest,
    DiffProfileRequest,
    EffectiveProfileRequest,
    ServerPlanRequest,
    ServiceOperationRequest,
    ExportDiagnosticRequest>;

struct ApplicationRequest {
    CommandId command = CommandId::unsupported;
    ApplicationPayload payload;
    bool dry_run = true;
};

using ApplicationOutput = std::variant<
    std::monostate,
    std::string,
    launch::LaunchPlanResult,
    launch::LaunchPreflightResult,
    modsets::ImportResult,
    modsets::LockResult,
    modsets::VerifyResult,
    modsets::ExportResult,
    modsets::Refusal,
    saves::ListResult,
    saves::BackupResult,
    saves::CloneResult,
    saves::ExportResult,
    saves::ImportResult,
    saves::Refusal,
    transactions::RecoveryResult,
    transactions::Refusal,
    diagnostics::ExportResult,
    diagnostics::Refusal>;

struct ApplicationResult {
    int status = ULK_STATUS_OK;
    facman::core::OutcomeKind outcome_kind = facman::core::OutcomeKind::ok;
    ApplicationOutput output;
    std::string error_code;
    std::string error_message;
};

} // namespace facman::factorio::application

#endif
