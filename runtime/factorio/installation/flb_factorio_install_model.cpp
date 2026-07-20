// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_install_model.h"

#include "fl_json.h"
#include "fl_file_io.h"
#include "fl_sha256.h"

#include <algorithm>
#include <filesystem>
#include <string_view>
#include <utility>
#include <vector>

namespace facman::factorio::installation {
namespace fs = std::filesystem;
namespace json = facman::core::json;

namespace {

struct ActionDecision {
    std::string id;
    std::string status;
    std::string reason;
    std::string owner;
    bool changes_install = false;
};

struct ProjectedModel {
    discovery::InstallRef install;
    std::string source_kind;
    std::string deployment_style;
    std::string management_class;
    std::string authority_status;
    std::string integration_kind;
    std::string integration_owner;
    std::string health;
    std::string provenance_status;
    std::string reconstruction;
    std::vector<std::string> findings;
    std::vector<std::string> recommendations;
    std::vector<ActionDecision> actions;
    bool setup_proof = false;
};

std::string path_string(const fs::path& path)
{
    return facman::platform::path_to_utf8(path.lexically_normal());
}

bool contains(const std::vector<std::string>& values, std::string_view value)
{
    return std::any_of(values.begin(), values.end(), [value](const std::string& text) {
        return std::string_view(text) == value;
    });
}

json::ArrayBuilder strings(const std::vector<std::string>& values)
{
    json::ArrayBuilder output;
    for (const std::string& value : values) output.add_string(value);
    return output;
}

std::string sha256_text(const std::string& text)
{
    facman::base::Sha256Hasher hash;
    hash.update(reinterpret_cast<const unsigned char*>(text.data()), text.size());
    return hash.finish();
}

std::string source_kind(const discovery::InstallRef& install)
{
    if (install.distribution_origin == "website_zip") return "official_archive";
    if (install.distribution_origin == "website_installer") return "vendor_installer";
    if (install.distribution_origin == "steam") return "steam";
    if (install.distribution_origin == "os_package") return "package_manager";
    if (install.distribution_origin == "gog") return "external_distribution";
    if (install.distribution_origin == "local_archive") return "existing_tree_or_archive";
    if (install.distribution_origin == "manually_imported") return "existing_tree";
    return "unknown";
}

std::string deployment_style(const discovery::InstallRef& install)
{
    if (install.installation_layout == "official_installer") return "vendor_installed";
    if (install.installation_layout == "portable_archive") return "portable_in_place";
    if (install.installation_layout == "steam_managed") return "external_manager";
    if (install.installation_layout == "app_bundle") return "application_bundle";
    if (install.installation_layout == "installer_style_tree") return "standalone_directory";
    return "unknown";
}

std::string management_class(const discovery::InstallRef& install)
{
    if (install.platform_integration == "steam" ||
        install.distribution_origin == "steam" ||
        install.distribution_origin == "os_package") return "external";
    if (install.ownership == "managed") return "managed";
    if (install.ownership == "adopted") return "adopted";
    if (install.ownership == "imported" || install.ownership == "portable" ||
        install.ownership == "foreign" || install.ownership == "foreign_owned") {
        return "reference";
    }
    return "unknown";
}

void add_action(
    ProjectedModel& model,
    std::string id,
    std::string status,
    std::string reason,
    std::string owner,
    bool changes_install = false)
{
    model.actions.push_back({
        std::move(id), std::move(status), std::move(reason),
        std::move(owner), changes_install});
}

void project_actions(ProjectedModel& model)
{
    const bool structural = model.install.verification_status == "structural";
    add_action(model, "inspect", "available", "Read-only evidence is available", "facman");
    add_action(
        model,
        "verify",
        structural ? "available_structural" : "diagnostic_only",
        structural ? "The application has structural identity" : "The tree is not structurally healthy",
        "facman");
    add_action(
        model,
        "reconcile_plan",
        "available_plan_only",
        "Desired state can be compared without applying changes",
        "facman");
    add_action(
        model,
        "snapshot_selected_data",
        structural ? "available" : "available_salvage_only",
        "User-selected mutable data can be copied without changing the source",
        "facman");

    if (model.management_class == "external") {
        add_action(model, "launch", "available_scoped", "External state must remain disclosed", "facman");
        add_action(model, "clone_to_managed", "available_plan_only", "The external root remains immutable", "facman");
        for (const char* action : {"repair", "move", "update", "reinstall", "uninstall"}) {
            add_action(model, action, "delegate", "The external manager retains application authority", "external_manager", true);
        }
        return;
    }

    if (model.management_class == "managed" || model.management_class == "adopted") {
        add_action(model, "launch", "available_scoped", "Launch still requires its isolation gate", "facman");
        const std::string status = model.setup_proof
            ? "available_plan_only_apply_gated"
            : "unavailable_missing_ownership_proof";
        const std::string reason = model.setup_proof
            ? "Universal Setup owns mutation and apply remains separately gated"
            : "Legacy ownership text does not grant mutation authority";
        for (const char* action : {"repair", "move", "update", "downgrade", "reinstall", "uninstall"}) {
            add_action(model, action, status, reason, "universal_setup", true);
        }
        add_action(model, "detach", "available_plan_only", "Detachment must preserve the application tree", "facman");
        return;
    }

    if (model.management_class == "reference") {
        add_action(model, "launch", "available_scoped", "FacMan may route an isolated instance", "facman");
        add_action(model, "clone_to_managed", "available_plan_only", "Materialise a separate owned closure", "facman");
        if (model.install.installation_layout == "portable_archive") {
            add_action(model, "adopt", "available_plan_only", "Adoption requires snapshot and ownership proof", "facman");
        }
        for (const char* action : {"repair", "move", "update", "downgrade", "reinstall", "uninstall"}) {
            add_action(model, action, "requires_adoption_or_clone", "The registered tree remains foreign", "universal_setup", true);
        }
        add_action(model, "detach", "available_plan_only", "Remove only the FacMan reference", "facman");
        return;
    }

    add_action(model, "launch", "restricted", "Identity and authority are unknown", "facman");
    for (const char* action : {"repair", "move", "update", "downgrade", "reinstall", "uninstall"}) {
        add_action(model, action, "unavailable", "Identity and authority must be proven first", "universal_setup", true);
    }
}

ProjectedModel project(discovery::InstallRef install)
{
    discovery::classify_install_isolation(install);
    discovery::classify_install_layout(install);
    ProjectedModel model;
    model.install = std::move(install);
    model.source_kind = source_kind(model.install);
    model.deployment_style = deployment_style(model.install);
    model.management_class = management_class(model.install);
    model.setup_proof =
        (model.management_class == "managed" || model.management_class == "adopted") &&
        !model.install.setup_state_ref.empty() &&
        !model.install.last_verification_identity.empty();
    model.authority_status = model.setup_proof
        ? "setup_proof_present_apply_still_gated"
        : "conservative_read_only_projection";

    if (model.install.platform_integration == "steam") {
        model.integration_kind = "steam";
        model.integration_owner = "external_manager";
    } else if (model.install.uninstall_integration == "uninstaller_present") {
        model.integration_kind = "vendor_uninstaller";
        model.integration_owner = "vendor";
    } else {
        model.integration_kind = "none_detected";
        model.integration_owner = "none";
    }

    if (model.install.verification_status == "invalid") {
        model.health = "damaged_or_unknown";
        model.findings.push_back("structural_identity_missing");
    } else if (model.install.executable.empty()) {
        model.health = "incomplete";
        model.findings.push_back("entrypoint_missing");
    } else if (model.install.program_data_separation == "conflated") {
        model.health = "attention";
        model.findings.push_back("mutable_data_inside_application_root");
    } else if (model.install.data_routing == "system_shared_with_local_residue") {
        model.health = "attention";
        model.findings.push_back("local_data_residue_beside_system_routing");
    } else {
        model.health = "healthy_structural";
    }
    if (model.install.side_by_side_safety ==
        "program_files_separate_but_registration_may_be_superseded") {
        model.findings.push_back("shared_vendor_registration_identity_risk");
    }
    if (!model.install.external_state_domains.empty()) {
        model.findings.push_back("external_state_domains_present");
    }

    if (!model.install.last_verification_identity.empty() &&
        !model.install.state_revision.empty()) {
        model.provenance_status = "verification_bound";
    } else if (!model.install.version.empty() && model.install.version != "unknown") {
        model.provenance_status = "partial_version_only";
    } else {
        model.provenance_status = "unknown";
    }
    model.reconstruction = !model.install.source_ref.empty()
        ? "source_identity_bound"
        : "source_not_bound";

    if (model.install.program_data_separation == "conflated") {
        model.recommendations.push_back("separate_mutable_data_into_instance");
    }
    if (contains(model.install.external_state_domains, "default_factorio_data")) {
        model.recommendations.push_back("prefer_explicit_instance_data_routing");
    }
    if (model.management_class == "reference") {
        model.recommendations.push_back("keep_source_read_only");
        model.recommendations.push_back("clone_to_managed_for_full_lifecycle");
    }
    if (model.management_class == "external") {
        model.recommendations.push_back("delegate_application_mutation");
    }
    if (model.install.side_by_side_safety ==
        "program_files_separate_but_registration_may_be_superseded") {
        model.recommendations.push_back("do_not_clone_vendor_registration");
    }
    project_actions(model);
    return model;
}

json::ObjectBuilder action_builder(const ActionDecision& action)
{
    json::ObjectBuilder output;
    output.add_string("id", action.id);
    output.add_string("status", action.status);
    output.add_string("reason", action.reason);
    output.add_string("owner", action.owner);
    output.add_bool("changes_install", action.changes_install);
    return output;
}

json::ObjectBuilder current_evidence_builder(const ProjectedModel& model)
{
    json::ObjectBuilder source;
    source.add_string("schema", "factorio.source_reference.v1");
    source.add_string("kind", model.source_kind);
    source.add_string("provider", model.install.provider_id.empty() ? "unknown" : model.install.provider_id);
    source.add_string("source_ref", model.install.source_ref);
    source.add_string("reconstruction", model.reconstruction);

    json::ObjectBuilder deployment;
    deployment.add_string("schema", "factorio.deployment_record.v1");
    deployment.add_string("style", model.deployment_style);
    deployment.add_string("layout", model.install.installation_layout);
    deployment.add_string("root", path_string(model.install.root));
    deployment.add_string("executable", path_string(model.install.executable));
    deployment.add_string("platform", model.install.platform);

    json::ObjectBuilder authority;
    authority.add_string("schema", "factorio.ownership_authority.v1");
    authority.add_string("recorded_ownership", model.install.ownership);
    authority.add_string("management_class", model.management_class);
    authority.add_string("status", model.authority_status);
    authority.add_bool("setup_proof_present", model.setup_proof);
    authority.add_bool("mutation_authority", false);
    authority.add_string("mutation_owner", "universal_setup");
    authority.add_string("setup_state_ref", model.install.setup_state_ref);

    json::ObjectBuilder data;
    data.add_string("schema", "factorio.data_routing_policy.v1");
    data.add_string("routing", model.install.data_routing);
    data.add_string("program_data_separation", model.install.program_data_separation);
    data.add_array("local_domains", strings(model.install.local_data_domains));
    data.add_array("external_domains", strings(model.install.external_state_domains));

    json::ObjectBuilder integration;
    integration.add_string("schema", "factorio.integration_record.v1");
    integration.add_string("kind", model.integration_kind);
    integration.add_string("owner", model.integration_owner);
    integration.add_string("side_by_side_safety", model.install.side_by_side_safety);
    integration.add_string("uninstall_integration", model.install.uninstall_integration);

    json::ObjectBuilder health;
    health.add_string("schema", "factorio.verification_snapshot.v1");
    health.add_string("status", model.health);
    health.add_string("structural_verification", model.install.verification_status);
    health.add_array("findings", strings(model.findings));

    json::ObjectBuilder provenance;
    provenance.add_string("schema", "factorio.provenance_record.v1");
    provenance.add_string("status", model.provenance_status);
    provenance.add_string("version", model.install.version);
    provenance.add_string("state_revision", model.install.state_revision);
    provenance.add_string("verification_identity", model.install.last_verification_identity);

    json::ObjectBuilder filesystem;
    filesystem.add_string("schema", "factorio.filesystem_capability.v1");
    filesystem.add_string("class", "local_or_unknown");
    filesystem.add_string("move_capability", "must_be_probed_per_plan");
    filesystem.add_string("stable_identity", "must_be_revalidated_per_operation");

    json::ObjectBuilder evidence;
    evidence.add_string("schema", "factorio.install_current_evidence.v1");
    evidence.add_string("install_id", model.install.install_id);
    evidence.add_string("product_id", "factorio");
    evidence.add_string("version", model.install.version);
    evidence.add_object("source", source);
    evidence.add_object("deployment", deployment);
    evidence.add_object("ownership_and_authority", authority);
    evidence.add_object("data_policy", data);
    evidence.add_object("integration", integration);
    evidence.add_object("health", health);
    evidence.add_object("provenance", provenance);
    evidence.add_object("filesystem", filesystem);
    return evidence;
}

json::ObjectBuilder model_builder(const ProjectedModel& model)
{
    json::ArrayBuilder actions;
    for (const ActionDecision& action : model.actions) actions.add_object(action_builder(action));
    json::ObjectBuilder compatibility;
    compatibility.add_string("source_schema", "factorio.install_ref.v1");
    compatibility.add_string("projection_schema", "factorio.installation_model.v2");
    compatibility.add_bool("persisted_record_rewritten", false);
    compatibility.add_bool("conservative_defaults_applied", true);
    compatibility.add_string("missing_authority_default", "read_only");

    json::ObjectBuilder output;
    output.add_string("schema", "factorio.installation_model.v2");
    output.add_string("command", "installs.describe");
    output.add_string("install_id", model.install.install_id);
    output.add_object("current_evidence", current_evidence_builder(model));
    output.add_array("available_actions", actions);
    output.add_array("recommendations", strings(model.recommendations));
    output.add_object("compatibility", compatibility);
    return output;
}

json::ObjectBuilder desired_builder(
    const ProjectedModel& model,
    const DesiredInstallationState& desired)
{
    json::ObjectBuilder integration;
    integration.add_string("mode", desired.integration_mode);
    integration.add_string(
        "effective",
        desired.integration_mode == "preserve" ? model.integration_kind : desired.integration_mode);

    json::ObjectBuilder output;
    output.add_string("schema", "factorio.install_desired_state.v1");
    output.add_string("install_id", desired.install_id);
    output.add_string("version", desired.version.empty() ? model.install.version : desired.version);
    output.add_string("source_ref", desired.source_ref);
    output.add_string("target_root", desired.target_root.empty()
        ? path_string(model.install.root) : desired.target_root);
    output.add_string("management_mode", desired.management_mode);
    output.add_string("deployment_style", desired.deployment_style);
    output.add_string("data_policy", desired.data_policy);
    output.add_string("update_policy", desired.update_policy);
    output.add_object("integration", integration);
    return output;
}

void add_step(
    json::ArrayBuilder& steps,
    const char* id,
    const std::string& status,
    const char* owner,
    const char* effect,
    const std::string& reason)
{
    json::ObjectBuilder step;
    step.add_string("id", id);
    step.add_string("status", status);
    step.add_string("owner", owner);
    step.add_string("effect", effect);
    step.add_string("reason", reason);
    steps.add_object(step);
}

} // namespace

std::string installation_model_json(const discovery::InstallRef& install)
{
    return model_builder(project(install)).serialize() + "\n";
}

std::string reconciliation_plan_json(
    const discovery::InstallRef& install,
    const DesiredInstallationState& desired)
{
    const ProjectedModel model = project(install);
    const std::string current_root = path_string(model.install.root);
    const bool management_change = desired.management_mode != "preserve" &&
        desired.management_mode != model.management_class;
    const bool deployment_change = desired.deployment_style != "preserve" &&
        desired.deployment_style != model.deployment_style;
    const bool data_change = desired.data_policy != "preserve" &&
        desired.data_policy != model.install.data_routing;
    const bool integration_change = desired.integration_mode != "preserve" &&
        desired.integration_mode != model.integration_kind;
    const bool version_change = !desired.version.empty() &&
        desired.version != model.install.version;
    const bool target_change = !desired.target_root.empty() &&
        desired.target_root != current_root;
    const bool update_policy_change = desired.update_policy != "preserve";
    const bool source_inspection = !desired.source_ref.empty();
    const std::size_t change_count = static_cast<std::size_t>(management_change) +
        static_cast<std::size_t>(deployment_change) + static_cast<std::size_t>(data_change) +
        static_cast<std::size_t>(integration_change) + static_cast<std::size_t>(version_change) +
        static_cast<std::size_t>(target_change) + static_cast<std::size_t>(update_policy_change);

    std::vector<std::string> blockers;
    std::vector<std::string> risks;
    if (management_change && desired.management_mode == "managed" &&
        model.management_class != "managed" && desired.source_ref.empty()) {
        blockers.push_back("trusted_source_ref_required_for_managed_materialisation");
    }
    if (management_change && desired.management_mode == "managed" &&
        model.management_class == "external" && !target_change) {
        blockers.push_back("external_root_requires_distinct_managed_target");
    }
    if (integration_change && desired.integration_mode == "facman_owned" &&
        desired.management_mode != "managed" && model.management_class != "managed") {
        blockers.push_back("facman_integration_requires_managed_desired_state");
    }
    if (management_change && desired.management_mode == "managed" &&
        desired.target_root == current_root) {
        blockers.push_back("in_place_authority_conversion_refused");
    }
    if (model.install.side_by_side_safety ==
        "program_files_separate_but_registration_may_be_superseded") {
        risks.push_back("vendor_registration_identity_collision");
    }
    if (!model.install.external_state_domains.empty()) {
        risks.push_back("external_state_requires_snapshot_or_explicit_exclusion");
    }
    if (model.install.program_data_separation == "conflated") {
        risks.push_back("mutable_data_must_be_preserved_before_materialisation");
    }
    if (desired.source_ref.empty() && (version_change || deployment_change || target_change)) {
        risks.push_back("source_identity_not_yet_bound");
    }

    json::ArrayBuilder steps;
    add_step(steps, "capture_current_evidence", "required", "facman", "workspace_read",
        "Revalidate the registered reference and live read-only evidence");
    add_step(steps, "inspect_source", source_inspection ? "required" : "not_required",
        "facman", "source_read", source_inspection
            ? "Bind source identity and reconstruction evidence"
            : "No source reference was selected");
    add_step(steps, "materialize_application",
        (management_change || deployment_change || version_change || target_change)
            ? (blockers.empty() ? "required" : "blocked") : "not_required",
        "universal_setup", "setup_preview",
        "Application closure changes must use a separate staged target");
    add_step(steps, "separate_instance_data", data_change ? "required" : "not_required",
        "facman", "workspace_preview", "Mutable data belongs to explicit instances");
    add_step(steps, "reconcile_integration",
        integration_change ? (blockers.empty() ? "required" : "blocked") : "not_required",
        "integration_provider", "integration_preview",
        "OS integration is an optional independently owned overlay");
    add_step(steps, "verify_application_closure", change_count == 0 ? "not_required" : "required",
        "universal_setup", "verification", "Verify exact owned application files before switching");
    add_step(steps, "verify_dependent_instances", change_count == 0 ? "not_required" : "required",
        "facman", "workspace_read", "Revalidate every selected instance against the desired version");
    add_step(steps, "retain_rollback", change_count == 0 ? "not_required" : "required",
        "universal_setup", "rollback", "Retain the original root until reviewed acceptance");

    json::ObjectBuilder summary;
    summary.add_string("status", !blockers.empty()
        ? "blocked_plan" : change_count == 0 ? "already_reconciled" : "plan_ready_for_provider_review");
    summary.add_unsigned_integer("change_count", change_count);
    summary.add_unsigned_integer("blocker_count", blockers.size());

    json::ObjectBuilder authority;
    authority.add_string("management_class", model.management_class);
    authority.add_string("planning_authority", "facman_read_only");
    authority.add_string("mutation_owner", "universal_setup");
    authority.add_bool("apply_available", false);
    authority.add_bool("mutation_authority_inferred", false);

    json::ObjectBuilder rollback;
    rollback.add_string("strategy", "side_by_side_switch_with_retained_original");
    rollback.add_bool("required", change_count != 0);
    rollback.add_bool("source_deletion_allowed", false);
    rollback.add_string("acceptance", "human_review_required_before_retirement");

    json::ObjectBuilder plan_core;
    plan_core.add_string("install_id", desired.install_id);
    plan_core.add_object("desired_state", desired_builder(model, desired));
    plan_core.add_array("steps", steps);
    plan_core.add_array("blockers", strings(blockers));
    plan_core.add_array("risks", strings(risks));
    const std::string core = plan_core.serialize();

    auto parsed_core = json::parse(core);
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.install_reconciliation_plan.v1");
    output.add_string("command", "installs.reconcile.plan");
    output.add_string("plan_id", sha256_text(core));
    output.add_string("mode", "plan_only");
    output.add_bool("mutation_executed", false);
    output.add_bool("apply_available", false);
    output.add_object("current_evidence", current_evidence_builder(model));
    if (parsed_core && parsed_core.value().is_object()) {
        const json::Value* value = parsed_core.value().find("desired_state");
        if (value != nullptr) output.add_value("desired_state", *value);
        value = parsed_core.value().find("steps");
        if (value != nullptr) output.add_value("steps", *value);
        value = parsed_core.value().find("blockers");
        if (value != nullptr) output.add_value("blockers", *value);
        value = parsed_core.value().find("risks");
        if (value != nullptr) output.add_value("risks", *value);
    }
    output.add_object("summary", summary);
    output.add_object("authority", authority);
    output.add_object("rollback", rollback);
    return output.serialize() + "\n";
}

} // namespace facman::factorio::installation
