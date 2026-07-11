#include "handlers/instances.h"

#include "command_result.h"
#include "fl_file_io.h"
#include "fl_path_safety.h"
#include "flb_factorio_discovery.h"
#include "flb_factorio_launch_plan.h"

#include <filesystem>
#include <sstream>
#include <utility>

namespace facman::factorio::application::handlers {
namespace fs = std::filesystem;
namespace discovery = facman::factorio::discovery;
namespace launch = facman::factorio::launch;

namespace {
bool load_install(ApplicationContext& context, const std::string& id, discovery::InstallRef& install)
{
    auto record = context.installs().load(facman::core::InstallId(id));
    if (!record) return false;
    install.install_id = record.value().id.str();
    install.root = record.value().root;
    install.executable = record.value().executable;
    install.version = record.value().version;
    install.ownership = record.value().ownership;
    install.source = record.value().source;
    install.platform = record.value().platform;
    install.verification_status = record.value().verification_status;
    return true;
}

std::string instance_json(const facman::workspace::InstanceRecord& instance)
{
    std::ostringstream out;
    out << "{\n  \"schema\": \"factorio.instance.v1\",\n"
        << "  \"instance_id\": " << json_quote(instance.id.str()) << ",\n"
        << "  \"display_name\": " << json_quote(instance.display_name) << ",\n"
        << "  \"install_ref\": " << json_quote(instance.install_ref.str()) << ",\n"
        << "  \"factorio_version\": " << json_quote(instance.factorio_version) << ",\n"
        << "  \"local_data_root\": " << json_quote(facman::platform::path_to_utf8(instance.root.lexically_normal())) << ",\n"
        << "  \"profile\": " << json_quote(instance.profile) << ",\n"
        << "  \"modset\": null,\n  \"template\": " << json_quote(instance.template_id) << ",\n"
        << "  \"save_policy\": {\"mode\": \"instance-local\"},\n"
        << "  \"account_ref\": null,\n  \"concurrency\": {\"single_writer\": true},\n"
        << "  \"export_policy\": {\"portable\": true, \"redact_secrets\": true}\n}\n";
    return out.str();
}
}

ApplicationResult list_instances(ApplicationContext& context)
{
    auto records = context.instances().list();
    if (!records) return refused(
        safety_refusal("instance.list", records.error().code, "Instances could not be listed", records.error().message, true),
        records.error().code, records.error().message);
    std::ostringstream out;
    out << "{\"schema\":\"factorio.instances.v1\",\"command\":\"instance.list\",\"instances\":[";
    for (std::size_t index = 0; index < records.value().size(); ++index) {
        if (index) out << ',';
        out << instance_json(records.value()[index]);
    }
    out << "]}";
    ApplicationResult result;
    result.output = out.str();
    return result;
}

ApplicationResult create_instance(ApplicationContext& context, const CreateInstanceRequest& request)
{
    facman::workspace::InstanceRecord instance;
    instance.display_name = request.display_name;
    instance.id = facman::core::InstanceId(request.instance_id);
    instance.install_ref = facman::core::InstallId(request.install_id);
    instance.template_id = request.template_id;
    discovery::InstallRef install;
    if (!load_install(context, instance.install_ref.str(), install)) return refused(
        safety_refusal("instances.create", "unknown_install", "Install reference is not registered", instance.install_ref.str(), true),
        "unknown_install", "Install reference is not registered");
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
    launch::InstanceLaunchRef launch_instance {instance.id.str(), instance.profile, instance.root};
    launch::InstallLaunchRef launch_install {install.root, install.executable, install.ownership};
    const bool staged = facman::base::write_text_new_atomic(
            staging / "config" / "config.ini", launch::effective_config_ini(launch_instance, launch_install), error) &&
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

} // namespace facman::factorio::application::handlers
