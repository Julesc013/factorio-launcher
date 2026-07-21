// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_install_model.h"

#include "fl_json.h"
#include "fl_file_io.h"
#include "fl_sha256.h"

#include <algorithm>
#include <filesystem>
#include <initializer_list>
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

enum class ManagementMode { preserve, managed, reference, external };
enum class DeploymentStyle {
    preserve,
    standalone_directory,
    vendor_installed,
    portable_in_place,
    external_manager,
};
enum class DataPolicy { preserve, instance_local, system_shared, install_local };
enum class IntegrationMode { preserve, none, facman_owned, external };
enum class UpdatePolicy { preserve, pinned, manual, follow_channel };
enum class SourceTrustStatus {
    unselected,
    selected_unverified,
    inspection_required,
    verified,
    unavailable,
};
enum class PlanEffect { workspace_read, workspace_write, setup_preview };

struct TypedDesiredInstallationState {
    std::string install_id;
    std::string version;
    std::string source_ref;
    std::string target_root;
    ManagementMode management_mode = ManagementMode::preserve;
    DeploymentStyle deployment_style = DeploymentStyle::preserve;
    DataPolicy data_policy = DataPolicy::preserve;
    IntegrationMode integration_mode = IntegrationMode::preserve;
    UpdatePolicy update_policy = UpdatePolicy::preserve;
    SourceTrustStatus source_trust_status = SourceTrustStatus::unselected;
};

constexpr const char* canonicalization_version = "facman.sorted-json.v1";
constexpr const char* effect_vocabulary_version = "common.effects.v1";
constexpr const char* policy_revision = "factorio.install-reconciliation-policy.v1";

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

std::string canonical_json(const std::string& text)
{
    auto parsed = json::parse(text);
    return parsed ? parsed.value().serialize() : text;
}

const char* to_string(ManagementMode value)
{
    switch (value) {
    case ManagementMode::preserve: return "preserve";
    case ManagementMode::managed: return "managed";
    case ManagementMode::reference: return "reference";
    case ManagementMode::external: return "external";
    }
    return "preserve";
}

const char* to_string(DeploymentStyle value)
{
    switch (value) {
    case DeploymentStyle::preserve: return "preserve";
    case DeploymentStyle::standalone_directory: return "standalone_directory";
    case DeploymentStyle::vendor_installed: return "vendor_installed";
    case DeploymentStyle::portable_in_place: return "portable_in_place";
    case DeploymentStyle::external_manager: return "external_manager";
    }
    return "preserve";
}

const char* to_string(DataPolicy value)
{
    switch (value) {
    case DataPolicy::preserve: return "preserve";
    case DataPolicy::instance_local: return "instance_local";
    case DataPolicy::system_shared: return "system_shared";
    case DataPolicy::install_local: return "install_local";
    }
    return "preserve";
}

const char* to_string(IntegrationMode value)
{
    switch (value) {
    case IntegrationMode::preserve: return "preserve";
    case IntegrationMode::none: return "none";
    case IntegrationMode::facman_owned: return "facman_owned";
    case IntegrationMode::external: return "external";
    }
    return "preserve";
}

const char* to_string(UpdatePolicy value)
{
    switch (value) {
    case UpdatePolicy::preserve: return "preserve";
    case UpdatePolicy::pinned: return "pinned";
    case UpdatePolicy::manual: return "manual";
    case UpdatePolicy::follow_channel: return "follow_channel";
    }
    return "preserve";
}

const char* to_string(SourceTrustStatus value)
{
    switch (value) {
    case SourceTrustStatus::unselected: return "unselected";
    case SourceTrustStatus::selected_unverified: return "selected_unverified";
    case SourceTrustStatus::inspection_required: return "inspection_required";
    case SourceTrustStatus::verified: return "verified";
    case SourceTrustStatus::unavailable: return "unavailable";
    }
    return "unavailable";
}

const char* to_string(PlanEffect value)
{
    switch (value) {
    case PlanEffect::workspace_read: return "workspace_read";
    case PlanEffect::workspace_write: return "workspace_write";
    case PlanEffect::setup_preview: return "setup_preview";
    }
    return "workspace_read";
}

facman::core::Result<TypedDesiredInstallationState> decode_desired(
    const DesiredInstallationState& desired)
{
    TypedDesiredInstallationState typed;
    typed.install_id = desired.install_id;
    typed.version = desired.version;
    typed.source_ref = desired.source_ref;
    typed.target_root = desired.target_root;
    typed.source_trust_status = desired.source_ref.empty()
        ? SourceTrustStatus::unselected
        : SourceTrustStatus::selected_unverified;

    const auto unsupported = [](const char* field, const std::string& value) {
        return facman::core::Result<TypedDesiredInstallationState>::failure({
            "invalid_request",
            std::string(field) + " has an unsupported compatibility value: " + value,
            field,
            facman::core::OutcomeKind::invalid_argument,
        });
    };

    if (desired.management_mode == "preserve") typed.management_mode = ManagementMode::preserve;
    else if (desired.management_mode == "managed") typed.management_mode = ManagementMode::managed;
    else if (desired.management_mode == "reference") typed.management_mode = ManagementMode::reference;
    else if (desired.management_mode == "external") typed.management_mode = ManagementMode::external;
    else return unsupported("management_mode", desired.management_mode);

    if (desired.deployment_style == "preserve") typed.deployment_style = DeploymentStyle::preserve;
    else if (desired.deployment_style == "standalone_directory") typed.deployment_style = DeploymentStyle::standalone_directory;
    else if (desired.deployment_style == "vendor_installed") typed.deployment_style = DeploymentStyle::vendor_installed;
    else if (desired.deployment_style == "portable_in_place") typed.deployment_style = DeploymentStyle::portable_in_place;
    else if (desired.deployment_style == "external_manager") typed.deployment_style = DeploymentStyle::external_manager;
    else return unsupported("deployment_style", desired.deployment_style);

    if (desired.data_policy == "preserve") typed.data_policy = DataPolicy::preserve;
    else if (desired.data_policy == "instance_local") typed.data_policy = DataPolicy::instance_local;
    else if (desired.data_policy == "system_shared") typed.data_policy = DataPolicy::system_shared;
    else if (desired.data_policy == "install_local") typed.data_policy = DataPolicy::install_local;
    else return unsupported("data_policy", desired.data_policy);

    if (desired.integration_mode == "preserve") typed.integration_mode = IntegrationMode::preserve;
    else if (desired.integration_mode == "none") typed.integration_mode = IntegrationMode::none;
    else if (desired.integration_mode == "facman_owned") typed.integration_mode = IntegrationMode::facman_owned;
    else if (desired.integration_mode == "external") typed.integration_mode = IntegrationMode::external;
    else return unsupported("integration_mode", desired.integration_mode);

    if (desired.update_policy == "preserve") typed.update_policy = UpdatePolicy::preserve;
    else if (desired.update_policy == "pinned") typed.update_policy = UpdatePolicy::pinned;
    else if (desired.update_policy == "manual") typed.update_policy = UpdatePolicy::manual;
    else if (desired.update_policy == "follow_channel") typed.update_policy = UpdatePolicy::follow_channel;
    else return unsupported("update_policy", desired.update_policy);

    return facman::core::Result<TypedDesiredInstallationState>::success(std::move(typed));
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
    const SourceTrustStatus source_trust = model.install.source_ref.empty()
        ? SourceTrustStatus::unselected
        : SourceTrustStatus::selected_unverified;
    json::ObjectBuilder source;
    source.add_string("schema", "factorio.source_reference.v1");
    source.add_string("kind", model.source_kind);
    source.add_string("provider", model.install.provider_id.empty() ? "unknown" : model.install.provider_id);
    source.add_string("source_ref", model.install.source_ref);
    source.add_string("reconstruction", model.reconstruction);
    source.add_string("requirement", "required_for_reconstruction");
    source.add_string("candidate_status", model.install.source_ref.empty() ? "unselected" : "selected");
    source.add_string("evidence_status", "not_observed");
    source.add_string("evidence_identity", "");
    source.add_string("provider_revision", "not_observed");
    source.add_string("trust_status", to_string(source_trust));

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

    json::ObjectBuilder dependencies;
    dependencies.add_string(
        "installation_record_revision",
        model.install.state_revision.empty() ? "not_observed" : model.install.state_revision);
    dependencies.add_string(
        "installation_root_identity",
        model.install.root.empty()
            ? "not_observed"
            : "path_reference_sha256:" + sha256_text(path_string(model.install.root)));
    dependencies.add_string("executable_identity", "must_be_probed_per_operation");
    dependencies.add_string(
        "verification_identity",
        model.install.last_verification_identity.empty()
            ? "not_observed"
            : model.install.last_verification_identity);
    dependencies.add_string(
        "setup_state_identity",
        model.install.setup_state_ref.empty() ? "not_observed" : model.install.setup_state_ref);
    dependencies.add_string(
        "integration_identity",
        "projection_sha256:" + sha256_text(
            model.integration_kind + "\n" + model.integration_owner + "\n" +
            model.install.uninstall_integration));
    dependencies.add_string("filesystem_volume_identity", "must_be_probed_per_operation");
    dependencies.add_string("provider_revision", "not_observed");
    dependencies.add_null("captured_at");

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
    evidence.add_object("dependencies", dependencies);
    return evidence;
}

json::ObjectBuilder no_write_guarantees_builder()
{
    json::ObjectBuilder guarantees;
    guarantees.add_bool("installation_bytes_changed", false);
    guarantees.add_bool("source_bytes_changed", false);
    guarantees.add_bool("registry_state_changed", false);
    guarantees.add_bool("setup_apply_invoked", false);
    guarantees.add_bool("persisted_record_rewritten", false);
    guarantees.add_bool("workspace_created", false);
    guarantees.add_bool("journal_created", false);
    guarantees.add_bool("temporary_state_created", false);
    guarantees.add_bool("source_deletion_allowed", false);
    return guarantees;
}

json::ObjectBuilder provider_revisions_builder(const ProjectedModel& model)
{
    json::ObjectBuilder revisions;
    revisions.add_string("installation_projection", "factorio.installation_model.v2");
    revisions.add_string(
        "installation_provider",
        model.install.provider_id.empty() ? "unknown" : model.install.provider_id);
    revisions.add_string("installation_provider_revision", "not_observed");
    revisions.add_string("source_provider_revision", "not_observed");
    revisions.add_string("setup_provider_revision", "not_observed");
    revisions.add_string("integration_provider_revision", "not_observed");
    return revisions;
}

json::ArrayBuilder revalidation_requirements_builder()
{
    json::ArrayBuilder requirements;
    for (const char* value : {
             "installation_record_revision",
             "installation_root_identity",
             "executable_identity",
             "verification_identity",
             "setup_state_identity",
             "integration_identity",
             "filesystem_volume_identity",
             "provider_revisions",
             "policy_revision",
             "source_evidence",
         }) {
        requirements.add_string(value);
    }
    return requirements;
}

json::ObjectBuilder model_builder(const ProjectedModel& model)
{
    json::ArrayBuilder actions;
    for (const ActionDecision& action : model.actions) actions.add_object(action_builder(action));
    const json::ObjectBuilder current_evidence = current_evidence_builder(model);
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
    output.add_string("canonicalization_version", canonicalization_version);
    output.add_string(
        "current_evidence_digest",
        sha256_text(canonical_json(current_evidence.serialize())));
    output.add_object("current_evidence", current_evidence);
    output.add_array("available_actions", actions);
    output.add_array("recommendations", strings(model.recommendations));
    output.add_object("compatibility", compatibility);
    output.add_object("no_write_guarantees", no_write_guarantees_builder());
    return output;
}

json::ObjectBuilder desired_builder(
    const ProjectedModel& model,
    const TypedDesiredInstallationState& desired,
    bool source_required)
{
    json::ObjectBuilder integration;
    integration.add_string("mode", to_string(desired.integration_mode));
    integration.add_string(
        "effective",
        desired.integration_mode == IntegrationMode::preserve
            ? model.integration_kind
            : to_string(desired.integration_mode));

    json::ObjectBuilder source;
    source.add_string(
        "requirement",
        source_required ? "required_for_materialisation" : "not_required_for_selected_transition");
    source.add_string("candidate", desired.source_ref);
    source.add_string("evidence_status", "not_observed");
    source.add_string("evidence_identity", "");
    source.add_string("provider_revision", "not_observed");
    source.add_string("trust_status", to_string(desired.source_trust_status));

    json::ObjectBuilder output;
    output.add_string("schema", "factorio.install_desired_state.v1");
    output.add_string("install_id", desired.install_id);
    output.add_string("version", desired.version.empty() ? model.install.version : desired.version);
    output.add_string("source_ref", desired.source_ref);
    output.add_object("source", source);
    output.add_string("target_root", desired.target_root.empty()
        ? path_string(model.install.root) : desired.target_root);
    output.add_string("management_mode", to_string(desired.management_mode));
    output.add_string("deployment_style", to_string(desired.deployment_style));
    output.add_string("data_policy", to_string(desired.data_policy));
    output.add_string("update_policy", to_string(desired.update_policy));
    output.add_object("integration", integration);
    return output;
}

void add_step(
    json::ArrayBuilder& steps,
    const char* step_kind,
    const std::string& status,
    const char* owner,
    std::initializer_list<PlanEffect> effects,
    const std::string& reason)
{
    json::ArrayBuilder encoded_effects;
    for (const PlanEffect effect : effects) encoded_effects.add_string(to_string(effect));
    json::ObjectBuilder step;
    step.add_string("step_kind", step_kind);
    step.add_string("status", status);
    step.add_string("owner", owner);
    step.add_array("effects", encoded_effects);
    step.add_string("reason", reason);
    steps.add_object(step);
}

} // namespace

std::string installation_model_json(const discovery::InstallRef& install)
{
    return model_builder(project(install)).serialize() + "\n";
}

facman::core::Result<std::string> reconciliation_plan_json(
    const discovery::InstallRef& install,
    const DesiredInstallationState& desired)
{
    const ProjectedModel model = project(install);
    auto decoded = decode_desired(desired);
    if (!decoded) {
        return facman::core::Result<std::string>::failure(decoded.error());
    }
    const TypedDesiredInstallationState& typed = decoded.value();
    const std::string current_root = path_string(model.install.root);
    const bool management_change = typed.management_mode != ManagementMode::preserve &&
        to_string(typed.management_mode) != model.management_class;
    const bool deployment_change = typed.deployment_style != DeploymentStyle::preserve &&
        to_string(typed.deployment_style) != model.deployment_style;
    const bool data_change = typed.data_policy != DataPolicy::preserve &&
        to_string(typed.data_policy) != model.install.data_routing;
    const bool integration_change = typed.integration_mode != IntegrationMode::preserve &&
        to_string(typed.integration_mode) != model.integration_kind;
    const bool version_change = !typed.version.empty() &&
        typed.version != model.install.version;
    const bool target_change = !typed.target_root.empty() &&
        typed.target_root != current_root;
    const bool update_policy_change = typed.update_policy != UpdatePolicy::preserve;
    const bool source_selected = typed.source_trust_status != SourceTrustStatus::unselected;
    const bool application_change = management_change || deployment_change ||
        version_change || target_change;
    const bool source_required = application_change;
    const std::size_t change_count = static_cast<std::size_t>(management_change) +
        static_cast<std::size_t>(deployment_change) + static_cast<std::size_t>(data_change) +
        static_cast<std::size_t>(integration_change) + static_cast<std::size_t>(version_change) +
        static_cast<std::size_t>(target_change) + static_cast<std::size_t>(update_policy_change);

    std::vector<std::string> blockers;
    std::vector<std::string> risks;
    if (source_required && !source_selected) {
        blockers.push_back("source_candidate_required_for_materialisation");
    } else if (source_required &&
        typed.source_trust_status != SourceTrustStatus::verified) {
        blockers.push_back("source_inspection_required_for_materialisation");
    }
    if (management_change && typed.management_mode == ManagementMode::managed &&
        model.management_class == "external" && !target_change) {
        blockers.push_back("external_root_requires_distinct_managed_target");
    }
    if (integration_change && typed.integration_mode == IntegrationMode::facman_owned &&
        typed.management_mode != ManagementMode::managed && model.management_class != "managed") {
        blockers.push_back("facman_integration_requires_managed_desired_state");
    }
    if (management_change && typed.management_mode == ManagementMode::managed &&
        typed.target_root == current_root) {
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
    if (!source_selected && source_required) {
        risks.push_back("source_identity_not_yet_bound");
    }

    json::ArrayBuilder steps;
    add_step(steps, "evidence.capture", "required", "facman", {PlanEffect::workspace_read},
        "Revalidate the registered reference and live read-only evidence");
    add_step(
        steps,
        "source.inspect",
        !source_required
            ? "not_required"
            : !source_selected
                ? "blocked_missing_source_candidate"
                : typed.source_trust_status == SourceTrustStatus::verified
                    ? "required"
                    : "blocked_pending_source_inspection",
        "facman",
        {PlanEffect::workspace_read},
        source_selected
            ? "A provider must bind authenticated source evidence before materialisation"
            : "No source candidate was selected");
    add_step(steps, "application.materialize",
        !application_change
            ? "not_required"
            : typed.source_trust_status != SourceTrustStatus::verified
                ? "blocked_pending_source_inspection"
                : blockers.empty() ? "required" : "blocked",
        "universal_setup", {PlanEffect::setup_preview},
        "Application closure changes must use a separate staged target");
    add_step(steps, "instance_data.separate", data_change ? "required" : "not_required",
        "facman", {PlanEffect::workspace_write}, "Mutable data belongs to explicit instances");
    add_step(steps, "integration.reconcile",
        integration_change ? (blockers.empty() ? "required" : "blocked") : "not_required",
        "integration_provider", {PlanEffect::setup_preview},
        "OS integration is an optional independently owned overlay");
    add_step(steps, "application.verify", change_count == 0 ? "not_required" : "required",
        "universal_setup", {PlanEffect::setup_preview},
        "Verify exact owned application files before switching");
    add_step(steps, "instances.verify_dependents", change_count == 0 ? "not_required" : "required",
        "facman", {PlanEffect::workspace_read},
        "Revalidate every selected instance against the desired version");
    add_step(steps, "rollback.retain", change_count == 0 ? "not_required" : "required",
        "universal_setup", {PlanEffect::setup_preview},
        "Retain the original root until reviewed acceptance");

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

    const json::ObjectBuilder current_evidence = current_evidence_builder(model);
    const std::string current_evidence_digest =
        sha256_text(canonical_json(current_evidence.serialize()));
    const json::ObjectBuilder desired_state = desired_builder(model, typed, source_required);
    const std::string desired_state_digest =
        sha256_text(canonical_json(desired_state.serialize()));
    const json::ObjectBuilder provider_revisions = provider_revisions_builder(model);
    const json::ArrayBuilder revalidation_requirements = revalidation_requirements_builder();

    json::ObjectBuilder plan_core;
    plan_core.add_string("schema", "factorio.install_reconciliation_plan.v1");
    plan_core.add_string("canonicalization_version", canonicalization_version);
    plan_core.add_string("effect_vocabulary_version", effect_vocabulary_version);
    plan_core.add_string("install_id", typed.install_id);
    plan_core.add_string("current_evidence_digest", current_evidence_digest);
    plan_core.add_string("desired_state_digest", desired_state_digest);
    plan_core.add_array("steps", steps);
    plan_core.add_array("blockers", strings(blockers));
    plan_core.add_array("risks", strings(risks));
    plan_core.add_object("provider_revisions", provider_revisions);
    plan_core.add_string("policy_revision", policy_revision);
    plan_core.add_array("revalidation_requirements", revalidation_requirements);
    const std::string core = plan_core.serialize();
    const std::string plan_digest = sha256_text(canonical_json(core));

    json::ObjectBuilder output;
    output.add_string("schema", "factorio.install_reconciliation_plan.v1");
    output.add_string("command", "installs.reconcile.plan");
    output.add_string("install_id", typed.install_id);
    output.add_string("canonicalization_version", canonicalization_version);
    output.add_string("effect_vocabulary_version", effect_vocabulary_version);
    output.add_string("current_evidence_digest", current_evidence_digest);
    output.add_string("desired_state_digest", desired_state_digest);
    output.add_string("plan_digest", plan_digest);
    output.add_string("plan_id", plan_digest);
    output.add_null("created_at");
    output.add_string("mode", "plan_only");
    output.add_bool("mutation_executed", false);
    output.add_bool("apply_available", false);
    output.add_object("current_evidence", current_evidence);
    output.add_object("desired_state", desired_state);
    output.add_array("steps", steps);
    output.add_array("blockers", strings(blockers));
    output.add_array("risks", strings(risks));
    output.add_object("provider_revisions", provider_revisions);
    output.add_string("policy_revision", policy_revision);
    output.add_array("revalidation_requirements", revalidation_requirements);
    output.add_object("summary", summary);
    output.add_object("authority", authority);
    output.add_object("rollback", rollback);
    output.add_object("no_write_guarantees", no_write_guarantees_builder());
    return facman::core::Result<std::string>::success(output.serialize() + "\n");
}

} // namespace facman::factorio::installation
