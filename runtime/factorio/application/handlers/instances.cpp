// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "handlers/instances.h"

#include "command_result.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "flb_factorio_discovery.h"
#include "flb_factorio_launch_plan.h"
#include "flb_factorio_instance_lifecycle.h"
#include "flb_factorio_instance_model.h"
#include "flb_factorio_local_data_import.h"

#include <filesystem>
#include <utility>

namespace facman::factorio::application::handlers {
namespace fs = std::filesystem;
namespace discovery = facman::factorio::discovery;
namespace launch = facman::factorio::launch;
namespace lifecycle = facman::factorio::instance;

namespace {
bool load_install(ApplicationContext& context, const std::string& id, discovery::InstallRef& install)
{
    auto parsed_id = facman::core::InstallId::parse_legacy(id);
    if (!parsed_id) return false;
    auto record = context.installs().load(parsed_id.value());
    if (!record) return false;
    install.install_id = record.value().id.str();
    install.root = record.value().root;
    install.executable = record.value().executable;
    install.version = record.value().version;
    install.ownership = record.value().ownership;
    install.source = record.value().source;
    install.platform = record.value().platform;
    install.distribution_origin = record.value().distribution_origin;
    install.platform_integration = record.value().platform_integration;
    install.strict_isolation_eligibility = record.value().strict_isolation_eligibility;
    install.external_state_domains = record.value().external_state_domains;
    install.setup_state_ref = record.value().setup_state_ref;
    install.lifecycle_status = record.value().lifecycle_status;
    install.last_verification_identity = record.value().last_verification_identity;
    install.state_revision = record.value().state_revision;
    install.verification_status = record.value().verification_status;
    discovery::classify_install_isolation(install);
    discovery::classify_install_layout(install);
    return true;
}

std::string instance_json(const facman::workspace::InstanceRecord& instance)
{
    facman::core::json::ObjectBuilder save_policy;
    save_policy.add_string("mode", "instance-local");
    facman::core::json::ObjectBuilder concurrency;
    concurrency.add_bool("single_writer", true);
    facman::core::json::ObjectBuilder export_policy;
    export_policy.add_bool("portable", true);
    export_policy.add_bool("redact_secrets", true);
    facman::core::json::ObjectBuilder output;
    output.add_string("schema", "factorio.instance.v1");
    output.add_string("instance_id", instance.id.str());
    output.add_string("display_name", instance.display_name);
    output.add_string("install_ref", instance.install_ref.str());
    output.add_string("factorio_version", instance.factorio_version);
    output.add_string("local_data_root", facman::platform::path_to_utf8(instance.root.lexically_normal()));
    output.add_string("profile", instance.profile);
    output.add_null("modset");
    output.add_string("template", instance.template_id);
    output.add_object("save_policy", save_policy);
    output.add_null("account_ref");
    output.add_object("concurrency", concurrency);
    output.add_object("export_policy", export_policy);
    return output.serialize();
}

ApplicationResult lifecycle_result(const char* operation, facman::core::Result<std::string> result)
{
    if (result) {
        ApplicationResult output;
        output.output = result.take_value();
        return output;
    }
    return refused(
        safety_refusal(operation, result.error().code, "Instance lifecycle operation was refused",
            result.error().message, result.error().recoverable),
        result.error().code, result.error().message, result.error().kind);
}
}

ApplicationResult list_instances(ApplicationContext& context)
{
    auto records = context.instances().list();
    if (!records) return refused(
        safety_refusal("instance.list", records.error().code, "Instances could not be listed", records.error().message, true),
        records.error().code, records.error().message);
    facman::core::json::ArrayBuilder instances;
    for (const auto& record : records.value()) {
        auto encoded = decode_json_value(instance_json(record));
        if (encoded) instances.add_value(encoded.value());
    }
    facman::core::json::ObjectBuilder output;
    output.add_string("schema", "factorio.instances.v1");
    output.add_string("command", "instance.list");
    output.add_array("instances", instances);
    ApplicationResult result;
    result.output = output.serialize();
    return result;
}

ApplicationResult create_instance(ApplicationContext& context, const CreateInstanceRequest& request)
{
    auto instance_id = facman::core::InstanceId::parse(request.instance_id);
    if (!instance_id) return refused(
        safety_refusal("instances.create", instance_id.error().code, "Instance id is not portable", instance_id.error().message, false),
        instance_id.error().code, instance_id.error().message);
    auto install_id = facman::core::InstallId::parse_legacy(request.install_id);
    if (!install_id) return refused(
        safety_refusal("instances.create", install_id.error().code, "Install id is invalid", install_id.error().message, false),
        install_id.error().code, install_id.error().message);
    facman::workspace::InstanceRecord instance;
    instance.display_name = request.display_name;
    instance.id = instance_id.take_value();
    instance.install_ref = install_id.take_value();
    instance.template_id = request.template_id;
    discovery::InstallRef install;
    if (!load_install(context, instance.install_ref.str(), install)) return refused(
        safety_refusal("instances.create", "unknown_install", "Install reference is not registered", instance.install_ref.str(), true),
        "unknown_install", "Install reference is not registered");
    fs::path source_data_root;
    if (!request.source_data_root.empty()) {
        std::error_code source_error;
        source_data_root = fs::absolute(
            facman::platform::path_from_utf8(request.source_data_root), source_error).lexically_normal();
        const bool same_install = !source_error && fs::equivalent(source_data_root, install.root, source_error);
        std::string link_detail;
        if (source_error || !same_install ||
            facman::base::path_crosses_link_or_reparse_point(source_data_root, link_detail)) {
            return refused(
                safety_refusal("instances.create", "local_data_import_source_refused",
                    "Player data may only be imported from the selected registered installation root",
                    request.source_data_root, false),
                "local_data_import_source_refused",
                "Player data import source does not match the selected installation root");
        }
    }
    auto target = facman::base::managed_directory(context.workspace(), "instances", instance.id.str());
    if (!target.ok()) return refused(
        safety_refusal("instances.create", target.code, "Instance id cannot be used as a managed path", target.detail, false),
        target.code, target.detail);
    if (fs::exists(target.path)) return refused(
        safety_refusal("instances.create", "persistent_target_exists", "Instance target already exists", target.path.string(), true),
        "persistent_target_exists", "Instance target already exists");
    auto workspace_ready = context.workspace_repository().ensure();
    if (!workspace_ready) return refused(
        safety_refusal("instances.create", workspace_ready.error().code, "Workspace layout is unavailable", workspace_ready.error().message, false),
        workspace_ready.error().code, workspace_ready.error().message);
    instance.factorio_version = install.version;
    instance.root = target.path;
    fs::path staging = target.path;
    staging += ".facman-staging";
    if (fs::exists(staging)) return refused(
        safety_refusal("instances.create", "staging_target_exists", "Instance staging target already exists", staging.string(), true),
        "staging_target_exists", "Instance staging target already exists");

    transactions::Record transaction;
    transaction.command_id = "instance.create";
    transaction.target = target.path;
    transaction.sources = {install.root};
    if (!source_data_root.empty()) transaction.sources.push_back(source_data_root);
    transaction.staging_roots = {staging};
    transaction.commit_strategy = "destination_volume_stage_then_atomic_no_replace";
    auto started = transactions::TransactionSession::begin(context.workspace(), std::move(transaction));
    if (!started) return refused(
        safety_refusal("instances.create", "recovery_write_refused", "Instance journal preparation failed", started.error().message, true),
        "recovery_write_refused", started.error().message);
    transactions::TransactionSession session = started.take_value();
    if (!session.validated("request_validated") || !session.planned("target_and_install_validated")) return refused(
        safety_refusal("instances.create", "recovery_write_refused", "Instance journal preparation failed", session.detail(), true),
        "recovery_write_refused", session.detail());
    fs::create_directories(staging);
    std::string error;
    if (!facman::base::write_text_new_atomic(staging / ".facman-staging.v1", "facman-instance-staging-v1\n", error)) {
        session.failed(error);
        return refused(safety_refusal("instances.create", "persistent_write_refused", "Staging marker failed", error, true), "persistent_write_refused", error);
    }
    if (!session.staging("owned_staging_created")) return refused(
        safety_refusal("instances.create", "recovery_write_refused", "Instance staging journal update failed", session.detail(), true),
        "recovery_write_refused", session.detail());
    const char* dirs[] = {"config", "mods", "saves", "scenarios", "script-output", "logs", "crash", "exports", "cache", "locks"};
    for (const char* dir : dirs) fs::create_directories(staging / dir);
    if (!source_data_root.empty()) {
        auto imported = lifecycle::import_local_player_data(source_data_root, staging);
        if (!imported) {
            std::string cleanup;
            (void)facman::base::remove_owned_staging_tree(staging, ".facman-staging.v1", cleanup);
            session.failed(imported.error().message);
            return refused(
                safety_refusal("instances.create", imported.error().code,
                    "Local Factorio player data could not be preserved",
                    imported.error().detail, true),
                imported.error().code,
                imported.error().message);
        }
    }
    launch::InstanceLaunchRef launch_instance {instance.id.str(), instance.profile, instance.root, "gui", {}};
    launch::InstallLaunchRef launch_install {
        install.root,
        install.executable,
        install.ownership,
        install.distribution_origin,
        install.platform_integration,
        install.strict_isolation_eligibility,
        install.external_state_domains,
    };
    std::string effective_config = launch::effective_config_ini(launch_instance, launch_install);
    if (!source_data_root.empty()) {
        auto merged = lifecycle::merge_imported_config_settings(
            source_data_root / "config" / "config.ini", effective_config);
        if (!merged) {
            std::string cleanup;
            (void)facman::base::remove_owned_staging_tree(staging, ".facman-staging.v1", cleanup);
            session.failed(merged.error().message);
            return refused(
                safety_refusal("instances.create", merged.error().code,
                    "Imported Factorio settings could not be reconfigured for the isolated instance",
                    merged.error().detail, true),
                merged.error().code,
                merged.error().message);
        }
        effective_config = merged.take_value();
    }
    const bool staged = facman::base::write_text_new_atomic(
            staging / "config" / "config.ini", effective_config, error) &&
        facman::base::write_text_new_atomic(staging / "instance.v1.json", instance_json(instance), error);
    if (!staged || !session.staged("instance_files_staged") ||
        !session.verified("instance_configuration_verified") ||
        !session.committing("no_clobber_commit_started") ||
        !transactions::StagedDirectoryCommit::commit(staging, target.path, error)) {
        std::string cleanup;
        (void)facman::base::remove_owned_staging_tree(staging, ".facman-staging.v1", cleanup);
        session.failed(error.empty() ? session.detail() : error);
        return refused(safety_refusal("instances.create", "persistent_write_refused", "Instance commit failed", error, true), "persistent_write_refused", error);
    }
    if (!session.committed("instance_directory_committed")) return refused(
        safety_refusal("instances.create", "transaction_recovery_required", "Instance committed but journal update failed", session.detail(), false),
        "transaction_recovery_required", session.detail());
    std::error_code marker_error;
    fs::remove(target.path / ".facman-staging.v1", marker_error);
    if (marker_error || !session.complete()) return refused(
        safety_refusal("instances.create", "transaction_recovery_required", "Instance committed but finalization requires recovery", marker_error ? marker_error.message() : session.detail(), false),
        "transaction_recovery_required", session.detail());
    ApplicationResult result;
    result.output = instance_json(instance);
    return result;
}

ApplicationResult inspect_instance(ApplicationContext& context, const InspectInstanceRequest& request)
{
    return lifecycle_result("instances.inspect", lifecycle::inspect(context.workspace(), request));
}

ApplicationResult describe_instance(ApplicationContext& context, const InstanceProjectionRequest& request)
{
    return lifecycle_result("instances.describe", lifecycle::describe_instance(context.workspace(), request));
}

ApplicationResult readiness_instance(ApplicationContext& context, const InstanceProjectionRequest& request)
{
    return lifecycle_result("instances.readiness", lifecycle::instance_readiness(context.workspace(), request));
}

ApplicationResult verify_instance(ApplicationContext& context, const InspectInstanceRequest& request)
{
    return lifecycle_result("instances.verify", lifecycle::verify(context.workspace(), request));
}

ApplicationResult diff_instances(ApplicationContext& context, const DiffInstanceRequest& request)
{
    return lifecycle_result("instances.diff", lifecycle::diff(context.workspace(), request));
}

ApplicationResult clone_instance(ApplicationContext& context, const CloneInstanceRequest& request)
{
    return lifecycle_result("instances.clone", lifecycle::clone(context.workspace(), request));
}

ApplicationResult rename_instance(ApplicationContext& context, const RenameInstanceRequest& request)
{
    return lifecycle_result("instances.rename", lifecycle::rename_display(context.workspace(), request));
}

ApplicationResult archive_instance(ApplicationContext& context, const ArchiveInstanceRequest& request)
{
    return lifecycle_result("instances.archive", lifecycle::archive(context.workspace(), request));
}

ApplicationResult restore_instance(ApplicationContext& context, const RestoreInstanceRequest& request)
{
    return lifecycle_result("instances.restore", lifecycle::restore(context.workspace(), request));
}

ApplicationResult dispatch_instance_lifecycle(ApplicationContext& context, const ApplicationRequest& request)
{
    switch (request.command) {
    case CommandId::instances_inspect: return inspect_instance(context, std::get<InspectInstanceRequest>(request.payload));
    case CommandId::instances_verify: return verify_instance(context, std::get<InspectInstanceRequest>(request.payload));
    case CommandId::instances_diff: return diff_instances(context, std::get<DiffInstanceRequest>(request.payload));
    case CommandId::instances_clone: return clone_instance(context, std::get<CloneInstanceRequest>(request.payload));
    case CommandId::instances_rename: return rename_instance(context, std::get<RenameInstanceRequest>(request.payload));
    case CommandId::instances_archive: return archive_instance(context, std::get<ArchiveInstanceRequest>(request.payload));
    case CommandId::instances_restore: return restore_instance(context, std::get<RestoreInstanceRequest>(request.payload));
    default: return lifecycle_result("instances.lifecycle", facman::core::Result<std::string>::failure(
        {"unsupported_operation", "Unsupported instance lifecycle command", "instances"}));
    }
}

} // namespace facman::factorio::application::handlers
