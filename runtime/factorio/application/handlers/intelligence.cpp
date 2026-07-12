// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "handlers/intelligence.h"

#include "command_result.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_runtime_verify.h"

#include <array>
#include <filesystem>
#include <string>

#ifndef FACMAN_WITH_SETUP
#define FACMAN_WITH_SETUP 0
#endif

namespace facman::factorio::application::handlers {
namespace json = facman::core::json;

namespace {
constexpr const char* kUlkRevision = "de6c7c6cfa80c524296066bd6bb90a70ba02b760";
constexpr const char* kUskRevision = "4855e4f5dd23ae5dfa0d7f23a61ffbf46e1439d2";

const char* target_name() noexcept
{
#ifdef _WIN32
    return "windows-x64";
#elif defined(__APPLE__)
    return "macos-x64";
#else
    return "linux-x64";
#endif
}

void add_reason(
    json::ArrayBuilder& reasons,
    const std::string& code,
    const std::string& summary,
    const std::string& evidence)
{
    json::ObjectBuilder reason;
    reason.add_string("code", code);
    reason.add_string("summary", summary);
    reason.add_string("evidence", evidence);
    reasons.add_object(reason);
}

void add_remediation(
    json::ArrayBuilder& remediation,
    const std::string& code,
    const std::string& command,
    const std::string& explanation)
{
    json::ObjectBuilder item;
    item.add_string("code", code);
    item.add_string("command", command);
    item.add_string("explanation", explanation);
    item.add_bool("automatic", false);
    remediation.add_object(item);
}

ApplicationResult guidance(
    const std::string& command,
    const std::string& status,
    json::ObjectBuilder& observations,
    json::ArrayBuilder& reasons,
    json::ArrayBuilder& remediation,
    json::ArrayBuilder* steps = nullptr)
{
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.guidance_report.v1");
    output.add_string("command", command);
    output.add_string("status", status);
    output.add_object("observations", observations);
    output.add_array("reasons", reasons);
    output.add_array("remediation", remediation);
    if (steps != nullptr) output.add_array("steps", *steps);
    output.add_bool("mutation_executed", false);
    ApplicationResult result;
    result.output = output.serialize();
    return result;
}

bool lists(
    ApplicationContext& context,
    facman::core::Result<std::vector<facman::workspace::InstallRecord>>& installs,
    facman::core::Result<std::vector<facman::workspace::InstanceRecord>>& instances,
    ApplicationResult& failure)
{
    installs = context.installs().list();
    instances = context.instances().list();
    if (installs && instances) return true;
    const auto& error = !installs ? installs.error() : instances.error();
    failure = refused(
        safety_refusal("workspace.status", error.code, "Workspace records could not be inspected", error.message, true),
        error.code,
        error.message,
        error.kind);
    return false;
}

void add_step(
    json::ArrayBuilder& steps,
    const char* id,
    const char* command,
    const char* status,
    const std::string& reason)
{
    json::ObjectBuilder step;
    step.add_string("id", id);
    step.add_string("command", command);
    step.add_string("status", status);
    step.add_string("reason", reason);
    step.add_bool("executed", false);
    steps.add_object(step);
}
}

ApplicationResult workspace_status(ApplicationContext& context)
{
    facman::core::Result<std::vector<facman::workspace::InstallRecord>> installs = context.installs().list();
    facman::core::Result<std::vector<facman::workspace::InstanceRecord>> instances = context.instances().list();
    ApplicationResult failure;
    if (!lists(context, installs, instances, failure)) return failure;
    const auto workspace_record = context.workspace_repository().load();
    const std::size_t incomplete = transactions::incomplete_count(context.workspace());
    const char* package_root = fl_runtime_package_root();
    std::array<char, 512> package_detail {};
    std::size_t files_verified = 0;
    const bool packaged = package_root != nullptr && *package_root != '\0';
    const bool package_ok = packaged && fl_runtime_verify_package(package_detail.data(), package_detail.size(), &files_verified) == 0;

    json::ObjectBuilder observations;
    observations.add_string("workspace", facman::platform::path_to_utf8(context.workspace()));
    observations.add_string("workspace_id", workspace_record ? workspace_record.value().id.str() : "uninitialized");
    observations.add_unsigned_integer("layout_version", workspace_record ? workspace_record.value().layout_version : 0U);
    observations.add_string("package_integrity", package_ok ? "pass" : packaged ? "failed" : "not_packaged_checkout");
    observations.add_unsigned_integer("package_files_verified", files_verified);
    observations.add_string("universal_launcher_revision", kUlkRevision);
    observations.add_string("universal_setup_revision", kUskRevision);
    observations.add_unsigned_integer("install_count", installs.value().size());
    observations.add_unsigned_integer("instance_count", instances.value().size());
    observations.add_unsigned_integer("incomplete_transactions", incomplete);
    observations.add_string("setup_availability", FACMAN_WITH_SETUP ? "gateway_present_plan_unconfirmed" : "disabled_by_build");
    observations.add_string("execution_authority", "blocked_pending_h1_h3");
    observations.add_string("diagnostic_export", "implemented");
    observations.add_string("package_profile", packaged ? "package_manifest" : "source_checkout");
    observations.add_string("target", target_name());
    json::ArrayBuilder providers;
    providers.add_string("explicit.argument");
    providers.add_string("explicit.environment");
#ifdef _WIN32
    providers.add_string("windows.steam"); providers.add_string("windows.program-files");
#elif defined(__APPLE__)
    providers.add_string("macos.steam"); providers.add_string("macos.user-applications");
#else
    providers.add_string("linux.steam"); providers.add_string("linux.home"); providers.add_string("linux.opt");
#endif
    observations.add_array("discovery_providers", providers);
    json::ArrayBuilder quarantines;
    quarantines.add_string("run.execute"); quarantines.add_string("setup.mutation");
    quarantines.add_string("network.credentials"); quarantines.add_string("release.publication");
    observations.add_array("quarantines", quarantines);

    json::ArrayBuilder reasons;
    json::ArrayBuilder remediation;
    if (installs.value().empty()) {
        add_reason(reasons, "no_install_references", "No Factorio install reference is registered", "install_count=0");
        add_remediation(remediation, "scan_installs", "facman installs scan --json", "Discover read-only candidates before importing one");
    }
    if (incomplete != 0U) {
        add_reason(reasons, "recovery_required", "Incomplete transactions require inspection", "incomplete_transactions=" + std::to_string(incomplete));
        add_remediation(remediation, "inspect_recovery", "facman workspace recovery inspect --json", "Review transaction evidence before applying recovery");
    }
    add_reason(reasons, "isolation_not_proven", "run.execute remains unavailable", "execution_authority=blocked_pending_h1_h3");
    return guidance("workspace.status", installs.value().empty() || incomplete != 0U ? "warning" : "ok", observations, reasons, remediation);
}

ApplicationResult workspace_paths(ApplicationContext& context)
{
    json::ObjectBuilder observations;
    observations.add_string("root", facman::platform::path_to_utf8(context.layout().root()));
    observations.add_string("manifest", facman::platform::path_to_utf8(context.layout().manifest()));
    observations.add_string("install_refs", facman::platform::path_to_utf8(context.layout().installs_refs_dir()));
    observations.add_string("instances", facman::platform::path_to_utf8(context.layout().root() / "instances"));
    observations.add_string("transactions", facman::platform::path_to_utf8(context.layout().root() / "transactions"));
    observations.add_string("diagnostics", facman::platform::path_to_utf8(context.layout().root() / "diagnostics"));
    json::ArrayBuilder reasons;
    json::ArrayBuilder remediation;
    return guidance("workspace.paths", "ok", observations, reasons, remediation);
}

ApplicationResult capabilities_inspect(ApplicationContext&)
{
    json::ObjectBuilder observations;
    observations.add_string("execution_authority", "blocked_pending_h1_h3");
    observations.add_string("setup_mutation", "unavailable");
    json::ArrayBuilder capabilities;
    for (const auto& value : {
             std::pair<const char*, const char*>("workspace.status", "implemented"),
             {"installs.scan", "implemented"}, {"instances.create", "implemented"},
             {"launch_plan.preflight", "implemented"}, {"diagnostics.export", "implemented"},
             {"run.execute", "human_gated"}, {"installs.install_version", "unavailable"}}) {
        json::ObjectBuilder item;
        item.add_string("command", value.first);
        item.add_string("availability", value.second);
        item.add_string("reason", value.second == std::string("implemented") ? "registered_handler" : "authority_not_proven");
        capabilities.add_object(item);
    }
    observations.add_array("capabilities", capabilities);
    json::ArrayBuilder reasons;
    json::ArrayBuilder remediation;
    add_reason(reasons, "isolation_not_proven", "Execution capability is human-gated", "H1 and H3 reviewed passes are absent");
    return guidance("capabilities.inspect", "ok", observations, reasons, remediation);
}

ApplicationResult onboarding_plan(ApplicationContext& context, const OnboardingPlanRequest& request)
{
    const auto installs = context.installs().list();
    const auto instances = context.instances().list();
    if (!installs || !instances) {
        const auto& error = !installs ? installs.error() : instances.error();
        return refused(safety_refusal("onboarding.plan", error.code, error.message, error.path, true), error.code, error.message, error.kind);
    }
    const bool have_install = !request.preferred_install.empty() || !installs.value().empty();
    json::ObjectBuilder observations;
    observations.add_string("preferred_install", request.preferred_install);
    observations.add_string("instance_display_name", request.instance_display_name.empty() ? "My Factorio" : request.instance_display_name);
    observations.add_string("template_id", request.template_id.empty() ? "vanilla" : request.template_id);
    observations.add_string("workspace", request.workspace.empty() ? facman::platform::path_to_utf8(context.workspace()) : request.workspace);
    observations.add_unsigned_integer("existing_installs", installs.value().size());
    observations.add_unsigned_integer("existing_instances", instances.value().size());
    json::ArrayBuilder steps;
    add_step(steps, "scan", "installs.scan", "proposed", "read-only candidate discovery");
    add_step(steps, "select_candidate", "operator.select", have_install ? "ready" : "awaiting_selection", "operator chooses a verified candidate");
    add_step(steps, "import_install_reference", "installs.import", have_install ? "proposed" : "blocked", "persistent import requires explicit operator execution");
    add_step(steps, "create_instance", "instances.create", have_install ? "proposed" : "blocked", "instance is created only after install selection");
    add_step(steps, "build_launch_preview", "launch_plan.build", have_install ? "proposed" : "blocked", "no process starts");
    add_step(steps, "run_preflight", "launch_plan.preflight", have_install ? "proposed" : "blocked", "verifies the isolated plan without execution");
    json::ArrayBuilder reasons;
    json::ArrayBuilder remediation;
    if (!have_install) add_reason(reasons, "no_install_selected", "Onboarding requires an install candidate", "preferred_install empty and existing_installs=0");
    return guidance("onboarding.plan", have_install ? "ok" : "warning", observations, reasons, remediation, &steps);
}

ApplicationResult doctor_explain(ApplicationContext& context)
{
    const auto installs = context.installs().list();
    const std::size_t incomplete = transactions::incomplete_count(context.workspace());
    if (!installs) return refused(safety_refusal("doctor.explain", installs.error().code, installs.error().message, installs.error().path, true), installs.error().code, installs.error().message, installs.error().kind);
    json::ObjectBuilder observations;
    observations.add_unsigned_integer("install_count", installs.value().size());
    observations.add_unsigned_integer("incomplete_transactions", incomplete);
    json::ArrayBuilder reasons;
    json::ArrayBuilder remediation;
    if (installs.value().empty()) {
        add_reason(reasons, "no_install_references", "Doctor warns because no install is registered", "install_count=0");
        add_remediation(remediation, "scan_installs", "facman installs scan --json", "Review candidates and import one explicitly");
    }
    if (incomplete != 0U) {
        add_reason(reasons, "recovery_required", "Doctor warns because a transaction is incomplete", "incomplete_transactions=" + std::to_string(incomplete));
        add_remediation(remediation, "inspect_recovery", "facman workspace recovery inspect --json", "Inspect the journal before recovery");
    }
    add_reason(reasons, "isolation_not_proven", "run.execute is unavailable by policy", "real Factorio operator gates are pending");
    return guidance("doctor.explain", installs.value().empty() || incomplete != 0U ? "warning" : "ok", observations, reasons, remediation);
}

ApplicationResult launch_plan_explain(ApplicationContext& context, const ExplainInstanceRequest& request)
{
    const auto instance = context.instances().load(request.instance_id);
    json::ObjectBuilder observations;
    observations.add_string("instance_id", request.instance_id.str());
    observations.add_bool("instance_registered", static_cast<bool>(instance));
    if (instance) observations.add_string("install_id", instance.value().install_ref.str());
    json::ArrayBuilder reasons;
    json::ArrayBuilder remediation;
    if (!instance) {
        add_reason(reasons, instance.error().code, "Launch plan cannot be built for an unknown instance", instance.error().message);
        add_remediation(remediation, "list_instances", "facman instances list --json", "Choose a registered instance or create one");
    } else {
        add_reason(reasons, "plan_is_dry_run", "Launch planning resolves configuration without starting Factorio", "command=launch_plan.build");
    }
    add_reason(reasons, "isolation_not_proven", "run.execute remains unavailable", "execution_authority=blocked_pending_h1_h3");
    return guidance("launch_plan.explain", instance ? "ok" : "blocked", observations, reasons, remediation);
}

ApplicationResult modsets_explain(ApplicationContext& context, const ExplainInstanceRequest& request)
{
    const auto lock = context.modsets().load_lock(request.instance_id);
    json::ObjectBuilder observations;
    observations.add_string("instance_id", request.instance_id.str());
    observations.add_bool("lock_present", static_cast<bool>(lock));
    json::ArrayBuilder reasons;
    json::ArrayBuilder remediation;
    if (!lock) {
        add_reason(reasons, lock.error().code, "No readable canonical modset lock is available", lock.error().message);
        add_remediation(remediation, "lock_modset", "facman modsets lock " + request.instance_id.str() + " --json", "Review and execute the workspace-write command explicitly");
    } else {
        add_reason(reasons, "modset_lock_present", "The canonical modset lock can be verified", "lock_bytes=" + std::to_string(lock.value().size()));
        add_remediation(remediation, "verify_modset", "facman modsets verify " + request.instance_id.str() + " --json", "Compare installed mods with the lock");
    }
    return guidance("modsets.explain", lock ? "ok" : "warning", observations, reasons, remediation);
}

} // namespace facman::factorio::application::handlers
