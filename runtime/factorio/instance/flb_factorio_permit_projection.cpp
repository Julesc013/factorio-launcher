// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_permit_projection.h"

#include "fl_json.h"
#include "fl_sha256.h"
#include "flb_factorio_instance_model.h"

#include <algorithm>
#include <tuple>
#include <utility>

namespace facman::factorio::instance {
namespace {

namespace json = facman::core::json;
namespace permit = facman::core::permit;

facman::core::Error projection_error(std::string code, std::string message, std::string path)
{
    return {std::move(code), std::move(message), std::move(path), facman::core::OutcomeKind::refused};
}

std::string sha256_text(const std::string& value)
{
    return facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(value.data()), value.size());
}

facman::core::Result<std::string> string_field(
    const json::Value& object,
    const char* field,
    const std::string& path)
{
    const json::Value* value = object.find(field);
    if (value == nullptr) return facman::core::Result<std::string>::failure(
        projection_error("permit_wrong_evidence", "instance projection field is missing", path));
    auto text = value->string_value();
    if (!text) return facman::core::Result<std::string>::failure(
        projection_error("permit_wrong_evidence", "instance projection field is not a string", path));
    return facman::core::Result<std::string>::success(text.take_value());
}

const json::Value* object_field(const json::Value& object, const char* field)
{
    const json::Value* value = object.find(field);
    return value != nullptr && value->is_object() ? value : nullptr;
}

bool digest(const std::string& value)
{
    return value.size() == 64U && std::all_of(value.begin(), value.end(), [](unsigned char byte) {
        return (byte >= '0' && byte <= '9') || (byte >= 'a' && byte <= 'f');
    });
}

permit::ResourceBinding resource(
    std::string kind,
    std::string role,
    std::string logical_id,
    std::string identity_digest,
    permit::ProviderIdentity provider,
    std::vector<std::string> effects = {"workspace_read"})
{
    return {std::move(kind), std::move(role), std::move(logical_id),
        std::move(identity_digest), std::move(provider), std::move(effects)};
}

json::ObjectBuilder provider_json(const permit::ProviderIdentity& provider)
{
    json::ObjectBuilder output;
    output.add_string("provider_id", provider.provider_id);
    output.add_string("provider_revision", provider.provider_revision);
    return output;
}

json::ObjectBuilder resource_json(const permit::ResourceBinding& value)
{
    json::ArrayBuilder effects;
    for (const std::string& effect : value.permitted_effects) effects.add_string(effect);
    json::ObjectBuilder output;
    output.add_string("resource_kind", value.resource_kind);
    output.add_string("role", value.role);
    output.add_string("logical_id", value.logical_id);
    output.add_string("current_identity_digest", value.current_identity_digest);
    output.add_object("owning_provider", provider_json(value.owning_provider));
    output.add_array("permitted_effects", effects);
    return output;
}

} // namespace

facman::core::Result<MenuPermitResourceProjection> project_menu_permit_resources(
    const std::filesystem::path& workspace,
    const std::string& instance_id)
{
    ProjectionRequest request {instance_id, "menu"};
    auto described = describe_instance(workspace, request);
    if (!described) return facman::core::Result<MenuPermitResourceProjection>::failure(described.error());
    auto view = json::parse(described.value());
    if (!view || !view.value().is_object()) return facman::core::Result<MenuPermitResourceProjection>::failure(
        projection_error("permit_wrong_evidence", "instance view is not strict JSON", "$instance_view"));
    auto schema = string_field(view.value(), "schema", "$instance_view.schema");
    auto projected_id = string_field(view.value(), "instance_id", "$instance_view.instance_id");
    const json::Value* spec = object_field(view.value(), "instance_spec");
    const json::Value* binding = object_field(view.value(), "instance_binding");
    const json::Value* readiness = object_field(view.value(), "instance_readiness");
    if (!schema || !projected_id || schema.value() != "factorio.instance_view.v1" ||
        projected_id.value() != instance_id || spec == nullptr || binding == nullptr || readiness == nullptr) {
        return facman::core::Result<MenuPermitResourceProjection>::failure(
            projection_error("permit_wrong_evidence", "instance view identity or components are invalid", "$instance_view"));
    }

    auto spec_digest = string_field(*spec, "spec_digest", "$instance_view.instance_spec.spec_digest");
    auto binding_digest = string_field(*binding, "binding_digest", "$instance_view.instance_binding.binding_digest");
    auto readiness_digest = string_field(*readiness, "readiness_digest", "$instance_view.instance_readiness.readiness_digest");
    auto launch_intent = string_field(*readiness, "launch_intent", "$instance_view.instance_readiness.launch_intent");
    auto installation_digest = string_field(*binding, "installation_evidence_digest", "$instance_view.instance_binding.installation_evidence_digest");
    auto environment_identity = string_field(*binding, "execution_environment_identity", "$instance_view.instance_binding.execution_environment_identity");
    auto modset_identity = string_field(*binding, "modset_lock_identity", "$instance_view.instance_binding.modset_lock_identity");
    const json::Value* root = object_field(*binding, "instance_root");
    const json::Value* config = object_field(*binding, "effective_config");
    auto root_identity = root == nullptr
        ? facman::core::Result<std::string>::failure(projection_error(
            "permit_wrong_evidence", "instance root identity is missing", "$instance_view.instance_binding.instance_root"))
        : string_field(*root, "observed_identity", "$instance_view.instance_binding.instance_root.observed_identity");
    auto config_digest = config == nullptr
        ? facman::core::Result<std::string>::failure(projection_error(
            "permit_wrong_evidence", "effective config identity is missing", "$instance_view.instance_binding.effective_config"))
        : string_field(*config, "digest", "$instance_view.instance_binding.effective_config.digest");
    if (!spec_digest || !binding_digest || !readiness_digest || !launch_intent ||
        !installation_digest || !environment_identity || !modset_identity || !root_identity || !config_digest ||
        !digest(spec_digest.value()) || !digest(binding_digest.value()) || !digest(readiness_digest.value()) ||
        launch_intent.value() != "menu" || !digest(installation_digest.value()) ||
        !digest(config_digest.value()) || root_identity.value() == "not_observed") {
        return facman::core::Result<MenuPermitResourceProjection>::failure(
            projection_error("permit_wrong_evidence", "instance evidence is incomplete or not current", "$instance_view"));
    }

    const permit::ProviderIdentity instance_provider {
        "factorio.instance-model", "factorio.instance-model.v1"};
    const permit::ProviderIdentity installation_provider {
        "factorio.installation-model", "factorio.installation-model.v2"};
    const permit::ProviderIdentity launch_provider {
        "factorio.launch.local", "dormant-permit-verifier.v1"};

    MenuPermitResourceProjection output;
    output.instance_id = instance_id;
    output.provider_revisions = {installation_provider, instance_provider, launch_provider};
    output.resources = {
        resource("factorio.instance-spec", "portable-intent", "instance:" + instance_id + ":spec",
            spec_digest.value(), instance_provider),
        resource("factorio.instance-binding", "machine-binding", "instance:" + instance_id + ":binding",
            binding_digest.value(), instance_provider),
        resource("factorio.instance-readiness", "current-evidence", "instance:" + instance_id + ":readiness",
            readiness_digest.value(), instance_provider),
        resource("factorio.instance-root", "mutable-data", "instance:" + instance_id + ":root",
            sha256_text(root_identity.value()), instance_provider),
        resource("factorio.installation-evidence", "application-image", "instance:" + instance_id + ":installation",
            installation_digest.value(), installation_provider),
        resource("factorio.effective-config", "configuration", "instance:" + instance_id + ":config",
            config_digest.value(), instance_provider),
        resource("factorio.modset-lock", "mod-content", "instance:" + instance_id + ":modset",
            modset_identity.value().rfind("sha256:", 0) == 0 && digest(modset_identity.value().substr(7U))
                ? modset_identity.value().substr(7U)
                : sha256_text("explicit-state:" + modset_identity.value()), instance_provider),
        resource("factorio.execution-environment", "execution-environment", "instance:" + instance_id + ":environment",
            sha256_text(environment_identity.value()), launch_provider),
        resource("factorio.launch-intent", "launch-intent", "instance:" + instance_id + ":intent",
            sha256_text("menu"), launch_provider)};
    std::sort(output.resources.begin(), output.resources.end(), [](const auto& left, const auto& right) {
        return std::tie(left.resource_kind, left.role, left.logical_id) <
            std::tie(right.resource_kind, right.role, right.logical_id);
    });
    std::sort(output.provider_revisions.begin(), output.provider_revisions.end(), [](const auto& left, const auto& right) {
        return std::tie(left.provider_id, left.provider_revision) <
            std::tie(right.provider_id, right.provider_revision);
    });

    json::ArrayBuilder resources;
    for (const auto& value : output.resources) resources.add_object(resource_json(value));
    json::ArrayBuilder providers;
    for (const auto& value : output.provider_revisions) providers.add_object(provider_json(value));
    json::ObjectBuilder evidence;
    evidence.add_string("schema", "factorio.menu_permit_resource_projection.v1");
    evidence.add_string("instance_id", instance_id);
    evidence.add_string("launch_intent", "menu");
    evidence.add_array("resources", resources);
    evidence.add_array("provider_revisions", providers);
    auto canonical = json::parse(evidence.serialize());
    if (!canonical) return facman::core::Result<MenuPermitResourceProjection>::failure(
        projection_error("permit_wrong_evidence", "permit evidence could not be canonicalized", "$permit_projection"));
    output.evidence_digest = sha256_text(canonical.value().serialize());
    output.missing_play_resources = {
        "exact_executable_identity", "exact_launch_plan_digest", "frozen_play_policy",
        "operation_permit_issuance", "real_process_provider_authority"};
    output.launch_authority_complete = false;
    return facman::core::Result<MenuPermitResourceProjection>::success(std::move(output));
}

} // namespace facman::factorio::instance
