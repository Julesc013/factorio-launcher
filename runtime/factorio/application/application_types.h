#ifndef FACMAN_FACTORIO_APPLICATION_TYPES_H
#define FACMAN_FACTORIO_APPLICATION_TYPES_H

#include "flb_factorio_diagnostics.h"
#include "flb_factorio_launch_plan.h"
#include "flb_factorio_modset_operations.h"
#include "flb_factorio_save_operations.h"
#include "fl_transaction.h"

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

enum class CommandId {
    product_inspect,
    doctor_run,
    install_list,
    install_scan,
    install_import,
    install_inspect,
    instance_list,
    instance_create,
    launch_plan_build,
    launch_plan_preflight,
    run_preview,
    run_execute,
    setup_preview,
    setup_operation,
    utility_operation,
    mods_import,
    modsets_lock,
    modsets_verify,
    modsets_export,
    saves_list,
    saves_backup,
    saves_clone,
    instance_export,
    instance_import,
    recovery_inspect,
    recovery_plan,
    recovery_apply,
    migration_inspect,
    migration_plan,
    migration_apply,
    diagnostics_export,
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
struct RecoveryRequest { std::string transaction_id; };
struct ServiceOperationRequest {
    std::string operation;
    std::string name;
    std::string id;
    std::string instance_id;
    std::string path;
    std::string query;
    std::string version;
    std::string archive;
};

using ImportModRequest = modsets::ImportRequest;
using ModsetInstanceRequest = modsets::InstanceRequest;
using ExportModsetRequest = modsets::ExportRequest;
using ListSavesRequest = saves::InstanceRequest;
using BackupSaveRequest = saves::BackupRequest;
using CloneSaveRequest = saves::CloneRequest;
using ExportInstanceRequest = saves::ExportRequest;
using ImportInstanceRequest = saves::ImportRequest;
using ExportDiagnosticRequest = diagnostics::ExportRequest;

using ApplicationPayload = std::variant<
    std::monostate,
    ScanInstallRefsRequest,
    DoctorRequest,
    ImportInstallRefRequest,
    InspectInstallRefRequest,
    CreateInstanceRequest,
    BuildLaunchPlanRequest,
    ImportModRequest,
    ModsetInstanceRequest,
    ExportModsetRequest,
    ListSavesRequest,
    BackupSaveRequest,
    CloneSaveRequest,
    ExportInstanceRequest,
    ImportInstanceRequest,
    RecoveryRequest,
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
    ApplicationOutput output;
    std::string error_code;
    std::string error_message;
};

} // namespace facman::factorio::application

#endif
