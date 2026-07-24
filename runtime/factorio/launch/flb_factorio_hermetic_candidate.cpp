// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_hermetic_candidate.h"

#include "fl_json.h"
#include "fl_file_io.h"
#include "fl_path_safety.h"
#include "fl_random.h"
#include "fl_sha256.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <exception>
#include <limits>
#include <set>
#include <tuple>
#include <utility>

namespace facman::factorio::launch {
namespace {

namespace json = facman::core::json;
namespace permit = facman::core::permit;

const std::set<std::string> kRequiredEvidenceIds = {
    "application.session", "config.digest", "executable.identity",
    "executable.publisher_source", "executable.sha256", "facman.build_identity",
    "facman.source_revision", "factorio.content_capabilities", "factorio.version",
    "installation.evidence_digest", "installation.root_identity",
    "instance.binding_digest", "instance.readiness_digest", "instance.spec_digest",
    "isolation.mode", "launch.intent", "launch.plan_digest", "launch.plan_identity",
    "machine.binding", "mod_root.identity", "modset.state",
    "observation.provider_revision", "policy.digest", "policy.revision",
    "principal.identity", "protected.baseline_digest", "read_data.identity",
    "universal_launcher.revision", "universal_setup.revision",
    "writable.baseline_digest", "write_data.identity",
};

const std::set<std::string> kPolicyWritableResourceIds = {
    "instance.cache", "instance.config", "instance.crash", "instance.locks",
    "instance.logs", "instance.mods", "instance.saves", "instance.scenarios",
    "instance.script_output", "instance.state", "operation.record",
    "operation.temporary", "workspace.audit",
};

const std::set<std::string> kPolicyProtectedResourceIds = {
    "effects.external_filesystem", "effects.external_registry", "facman.package",
    "factorio.appdata", "factorio.default_user_data", "factorio.localappdata",
    "factorio.programdata", "factorio.source_material", "host.external_unobserved",
    "installation.selected", "installation.siblings", "instances.other",
    "registry.factorio", "registry.factorio_uninstall", "registry.steam",
    "steam.cloud_cache", "steam.install_roots", "steam.userdata",
};

const std::set<std::string> kAutomatedNegativeControls = {
    "add_wildcard_or_prefix_resource", "attempt_concurrent_launch",
    "cancel_before_process_creation", "cancel_during_execution",
    "change_installation_evidence", "change_launch_intent", "change_modset_state",
    "change_protected_root_identity", "change_isolation_mode",
    "expire_permit", "fail_journal_write", "force_process_crash", "force_timeout",
    "lose_observer_events", "mutate_authenticated_permit_claim",
    "present_stale_run_lock", "replace_effective_config",
    "replace_executable_same_path", "replay_permit_concurrently",
    "replay_permit_sequentially", "restart_issuer_session",
    "restart_provider_session", "select_sibling_instance", "stale_readiness",
    "write_os_global_temporary_directory",
};

facman::core::Error candidate_error(
    std::string code,
    std::string message,
    std::string path,
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::refused)
{
    return {std::move(code), std::move(message), std::move(path), kind};
}

bool lowercase_digest(const std::string& value)
{
    return value.size() == 64U &&
        std::all_of(value.begin(), value.end(), [](unsigned char byte) {
            return (byte >= '0' && byte <= '9') || (byte >= 'a' && byte <= 'f');
        });
}

std::string sha256_text(const std::string& value)
{
    return facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(value.data()), value.size());
}

bool string_field(
    const json::Value& object,
    const std::string& key,
    const std::string& expected)
{
    const json::Value* value = object.find(key);
    if (value == nullptr) return false;
    auto text = value->string_value();
    return text && text.value() == expected;
}

const json::Value* object_field(const json::Value& object, const std::string& key)
{
    const json::Value* value = object.find(key);
    return value != nullptr && value->is_object() ? value : nullptr;
}

bool bool_field(const json::Value& object, const std::string& key, bool expected)
{
    const json::Value* value = object.find(key);
    if (value == nullptr) return false;
    auto flag = value->bool_value();
    return flag && flag.value() == expected;
}

std::vector<std::string> sorted_unique(std::vector<std::string> values)
{
    std::sort(values.begin(), values.end());
    values.erase(std::unique(values.begin(), values.end()), values.end());
    return values;
}

bool exact_set(const std::vector<std::string>& values, const std::set<std::string>& expected)
{
    return std::set<std::string>(values.begin(), values.end()) == expected &&
        values.size() == expected.size();
}

json::ObjectBuilder provider_json(const permit::ProviderIdentity& provider)
{
    json::ObjectBuilder output;
    output.add_string("provider_id", provider.provider_id);
    output.add_string("provider_revision", provider.provider_revision);
    return output;
}

json::ArrayBuilder string_array(const std::vector<std::string>& values)
{
    json::ArrayBuilder output;
    for (const std::string& value : values) output.add_string(value);
    return output;
}

json::ObjectBuilder resource_json(const permit::ResourceBinding& value)
{
    json::ObjectBuilder output;
    output.add_string("resource_kind", value.resource_kind);
    output.add_string("role", value.role);
    output.add_string("logical_id", value.logical_id);
    output.add_string("current_identity_digest", value.current_identity_digest);
    output.add_object("owning_provider", provider_json(value.owning_provider));
    output.add_array("permitted_effects", string_array(value.permitted_effects));
    return output;
}

json::ObjectBuilder selector_json(const HermeticCandidateSelector& value)
{
    json::ObjectBuilder output;
    output.add_string("platform", value.platform);
    output.add_string("architecture", value.architecture);
    output.add_string("factorio_version", value.factorio_version);
    output.add_string("distribution", value.distribution);
    output.add_string("source_authentication", value.source_authentication);
    output.add_string("filesystem", value.filesystem);
    output.add_string("volume", value.volume);
    output.add_string("instance_ownership", value.instance_ownership);
    output.add_string("mod_state", value.mod_state);
    output.add_string("account_requirement", value.account_requirement);
    output.add_string("credential_requirement", value.credential_requirement);
    output.add_string("network_requirement", value.network_requirement);
    return output;
}

bool exact_selector(const HermeticCandidateSelector& value)
{
    return value.platform == "windows" && value.architecture == "x86_64" &&
        value.factorio_version == "2.0.77" &&
        value.distribution == "standalone_non_steam" &&
        value.source_authentication == "sha256_bound_to_authenticated_wube_source" &&
        value.filesystem == "ntfs" && value.volume == "fixed_local" &&
        value.instance_ownership == "facman_owned" &&
        value.mod_state == "explicit_empty_lock" &&
        value.account_requirement == "none" &&
        value.credential_requirement == "none" &&
        value.network_requirement == "none";
}

bool candidate_absolute_path(const std::filesystem::path& path)
{
    if (path.is_absolute()) return true;
    const std::string value = path.generic_string();
    return value.size() >= 3U &&
        ((value[0] >= 'A' && value[0] <= 'Z') ||
         (value[0] >= 'a' && value[0] <= 'z')) &&
        value[1] == ':' && value[2] == '/';
}

bool exact_process_shape(const facman::platform::ProcessRequest& process)
{
    if (process.executable.empty() || process.working_directory.empty() ||
        process.inherit_environment || process.timeout.count() <= 0 ||
        process.timeout > std::chrono::minutes(30)) return false;
    if (process.arguments.size() != 4U || process.arguments[0] != "--config" ||
        process.arguments[1].empty() || process.arguments[2] != "--mod-directory" ||
        process.arguments[3].empty()) return false;
    static const std::set<std::string> forbidden = {
        "--benchmark", "--connect", "--create", "--load-game", "--map-gen-settings",
        "--map-settings", "--scenario", "--start-server",
    };
    for (const std::string& argument : process.arguments) {
        if (forbidden.find(argument) != forbidden.end()) return false;
    }
    std::set<std::string> environment_names;
    static const std::set<std::string> required_environment = {
        "SystemRoot", "TEMP", "TMP", "USERPROFILE", "WINDIR",
    };
    for (const auto& entry : process.environment) {
        if (entry.name.empty() || entry.value.empty() ||
            !environment_names.insert(entry.name).second) return false;
    }
    if (environment_names != required_environment) return false;
    const std::filesystem::path executable = process.executable.lexically_normal();
    const std::filesystem::path working_directory =
        process.working_directory.lexically_normal();
    const std::filesystem::path config =
        facman::platform::path_from_utf8(process.arguments[1]).lexically_normal();
    const std::filesystem::path mods =
        facman::platform::path_from_utf8(process.arguments[3]).lexically_normal();
    if (!candidate_absolute_path(executable) || working_directory != executable.parent_path() ||
        !candidate_absolute_path(config) || !candidate_absolute_path(mods) ||
        config.filename() != "config.ini" || config.parent_path().filename() != "config") {
        return false;
    }
    const std::filesystem::path instance_root = config.parent_path().parent_path();
    if (instance_root.filename().empty() || instance_root.parent_path().filename() != "instances" ||
        mods != instance_root / "mods") return false;
    const std::filesystem::path workspace = instance_root.parent_path().parent_path();
    std::string temporary;
    std::string temporary_alias;
    std::string user_profile;
    for (const auto& entry : process.environment) {
        if (entry.name == "TEMP") temporary = entry.value;
        else if (entry.name == "TMP") temporary_alias = entry.value;
        else if (entry.name == "USERPROFILE") user_profile = entry.value;
    }
    const std::filesystem::path temporary_path =
        facman::platform::path_from_utf8(temporary).lexically_normal();
    const std::filesystem::path temporary_alias_path =
        facman::platform::path_from_utf8(temporary_alias).lexically_normal();
    const std::filesystem::path profile_path =
        facman::platform::path_from_utf8(user_profile).lexically_normal();
    const std::filesystem::path operation_root = temporary_path.parent_path();
    std::string operation_detail;
    return candidate_absolute_path(temporary_path) && temporary_path.filename() == "process" &&
        temporary_alias_path == temporary_path &&
        operation_root.parent_path() == workspace / "temporary" &&
        facman::base::validate_identifier(
            operation_root.filename().generic_string(), operation_detail) &&
        profile_path == instance_root / "state" / "userprofile";
}

bool exact_resource_closure(
    const std::vector<permit::ResourceBinding>& resources,
    const std::set<std::string>& writable)
{
    std::set<std::string> writable_roles;
    std::size_t executable_count = 0U;
    std::size_t observation_count = 0U;
    std::size_t operation_state_count = 0U;
    for (const auto& value : resources) {
        const std::set<std::string> effects(
            value.permitted_effects.begin(), value.permitted_effects.end());
        if (effects.size() != value.permitted_effects.size()) return false;
        if (value.resource_kind == "factorio.writable-root") {
            if (writable.find(value.role) == writable.end() ||
                effects != std::set<std::string>{"workspace_read", "workspace_write"} ||
                !writable_roles.insert(value.role).second) return false;
        } else if (value.resource_kind == "factorio.executable") {
            if (effects != std::set<std::string>{"process_execute", "workspace_read"}) return false;
            ++executable_count;
        } else if (value.resource_kind == "factorio.observation") {
            if (effects != std::set<std::string>{"workspace_read", "workspace_write"}) return false;
            ++observation_count;
        } else if (value.resource_kind == "factorio.operation-state") {
            if (effects != std::set<std::string>{"workspace_read", "workspace_write"}) return false;
            ++operation_state_count;
        } else if (effects.find("workspace_write") != effects.end() ||
                   effects.find("process_execute") != effects.end()) {
            return false;
        }
    }
    return writable_roles == writable && executable_count == 1U &&
        observation_count == 1U && operation_state_count == 1U;
}

bool provider_present(
    const std::vector<permit::ProviderIdentity>& values,
    const std::string& id,
    const std::string& revision)
{
    return std::any_of(values.begin(), values.end(), [&](const auto& value) {
        return value.provider_id == id && value.provider_revision == revision;
    });
}

std::string evidence_json(std::vector<CandidateEvidenceBinding> values)
{
    std::sort(values.begin(), values.end(), [](const auto& left, const auto& right) {
        return left.requirement_id < right.requirement_id;
    });
    json::ArrayBuilder bindings;
    for (const auto& value : values) {
        json::ObjectBuilder item;
        item.add_string("requirement_id", value.requirement_id);
        item.add_string("identity_digest", value.identity_digest);
        bindings.add_object(item);
    }
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.hermetic_play_candidate_evidence.v1");
    output.add_string("canonicalization_version", "facman.sorted-json.v1");
    output.add_array("bindings", bindings);
    return output.serialize();
}

std::string process_binding_json(const facman::platform::ProcessRequest& process)
{
    json::ArrayBuilder arguments;
    for (const std::string& value : process.arguments) {
        arguments.add_string(sha256_text("argument:" + value));
    }
    std::vector<facman::platform::ProcessEnvironmentEntry> environment = process.environment;
    std::sort(environment.begin(), environment.end(), [](const auto& left, const auto& right) {
        return left.name < right.name;
    });
    json::ArrayBuilder environment_values;
    for (const auto& value : environment) {
        json::ObjectBuilder item;
        item.add_string("name", value.name);
        item.add_string("value_digest", sha256_text("environment:" + value.name + "=" + value.value));
        environment_values.add_object(item);
    }
    json::ObjectBuilder output;
    output.add_string("executable_path_digest", sha256_text(
        "executable:" + process.executable.generic_string()));
    output.add_string("working_directory_digest", sha256_text(
        "working-directory:" + process.working_directory.generic_string()));
    output.add_array("argument_digests", arguments);
    output.add_array("environment", environment_values);
    output.add_bool("inherit_environment", process.inherit_environment);
    output.add_unsigned_integer(
        "timeout_milliseconds", static_cast<std::uint64_t>(process.timeout.count()));
    return output.serialize();
}

std::string plan_core_json(const HermeticCandidatePlan& plan)
{
    std::vector<permit::ResourceBinding> resources = plan.permit_resources;
    std::sort(resources.begin(), resources.end(), [](const auto& left, const auto& right) {
        return std::tie(left.resource_kind, left.role, left.logical_id) <
            std::tie(right.resource_kind, right.role, right.logical_id);
    });
    json::ArrayBuilder resource_values;
    for (const auto& value : resources) resource_values.add_object(resource_json(value));
    std::vector<permit::ProviderIdentity> providers = plan.provider_revisions;
    std::sort(providers.begin(), providers.end(), [](const auto& left, const auto& right) {
        return std::tie(left.provider_id, left.provider_revision) <
            std::tie(right.provider_id, right.provider_revision);
    });
    json::ArrayBuilder provider_values;
    for (const auto& value : providers) provider_values.add_object(provider_json(value));
    auto process = json::parse(process_binding_json(plan.process));

    json::ObjectBuilder output;
    output.add_string("schema", plan.schema);
    output.add_string("canonicalization_version", plan.canonicalization_version);
    output.add_string("policy_id", plan.policy.policy_id);
    output.add_string("policy_revision", plan.policy.policy_revision);
    output.add_string("policy_digest", plan.policy.policy_digest);
    output.add_object("candidate", selector_json(plan.selector));
    output.add_string("instance_id", plan.instance_id);
    output.add_string("machine_binding_id", plan.machine_binding_id);
    output.add_string("principal_provider", plan.principal.provider_id);
    output.add_string("principal_id", plan.principal.principal_id);
    output.add_string("application_session_id", plan.principal.application_session_id);
    output.add_string("operation", kHermeticCandidateOperation);
    output.add_string("launch_intent", kHermeticCandidateIntent);
    output.add_string("isolation_mode", kHermeticCandidateIsolation);
    output.add_string("evidence_digest", plan.evidence_digest);
    output.add_array("permit_resources", resource_values);
    output.add_array("provider_revisions", provider_values);
    output.add_array("writable_resource_ids", string_array(plan.writable_resource_ids));
    output.add_array("protected_resource_ids", string_array(plan.protected_resource_ids));
    output.add_string("environment_revision", plan.environment_revision);
    if (process) output.add_value("process_binding", process.value());
    return output.serialize();
}

bool plan_integrity_valid(const HermeticCandidatePlan& plan)
{
    return plan.evidence_digest == sha256_text(evidence_json(plan.evidence)) &&
        plan.plan_digest == sha256_text(plan_core_json(plan)) &&
        plan.plan_id == "play-plan-" + plan.plan_digest.substr(0U, 32U);
}

std::string random_prefixed_id(
    permit::PermitEntropySource& entropy,
    const std::string& prefix,
    facman::core::Error& error)
{
    std::array<unsigned char, 16> bytes {};
    auto filled = entropy.fill(bytes.data(), bytes.size());
    if (!filled) {
        error = filled.error();
        return {};
    }
    static const char hex[] = "0123456789abcdef";
    std::string output = prefix;
    output.reserve(prefix.size() + bytes.size() * 2U);
    for (unsigned char byte : bytes) {
        output.push_back(hex[(byte >> 4U) & 0x0fU]);
        output.push_back(hex[byte & 0x0fU]);
    }
    return output;
}

std::string observation_json(
    const CandidateObservationResult& observation,
    bool include_digest)
{
    std::vector<CandidateObservedEffect> effects = observation.effects;
    std::sort(effects.begin(), effects.end(), [](const auto& left, const auto& right) {
        return std::tie(left.sequence, left.domain, left.logical_resource_id) <
            std::tie(right.sequence, right.domain, right.logical_resource_id);
    });
    json::ArrayBuilder effect_values;
    for (const auto& value : effects) {
        json::ObjectBuilder item;
        item.add_unsigned_integer("sequence", value.sequence);
        item.add_string("domain", value.domain);
        item.add_string("process_identity_digest", value.process_identity_digest);
        item.add_string("target_identity_digest", value.target_identity_digest);
        item.add_string("logical_resource_id", value.logical_resource_id);
        item.add_string("classification", value.classification);
        effect_values.add_object(item);
    }
    json::ObjectBuilder gaps;
    gaps.add_bool("lost_events", observation.gaps.lost_events);
    gaps.add_bool("buffer_overflow", observation.gaps.buffer_overflow);
    gaps.add_bool("unknown_process_identity", observation.gaps.unknown_process_identity);
    gaps.add_bool("unresolved_target", observation.gaps.unresolved_target);
    gaps.add_bool("delayed_events", observation.gaps.delayed_events);
    gaps.add_bool("attribution_gap", observation.gaps.attribution_gap);
    gaps.add_bool("provider_failure", observation.gaps.provider_failure);
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.play_candidate_observation.v1");
    output.add_string("provider_id", observation.provider_id);
    output.add_string("provider_revision", observation.provider_revision);
    output.add_string("plan_digest", observation.plan_digest);
    output.add_string("capture_session_digest", observation.capture_session_digest);
    output.add_string("raw_artifact_digest", observation.raw_artifact_digest);
    output.add_bool("active_before_process", observation.active_before_process);
    output.add_bool("capture_complete", observation.capture_complete);
    output.add_object("gaps", gaps);
    output.add_array("effects", effect_values);
    if (include_digest) output.add_string("output_digest", observation.output_digest);
    return output.serialize();
}

std::string protected_json(
    const ProtectedComparisonResult& comparison,
    bool include_digest)
{
    std::vector<ProtectedResourceComparison> resources = comparison.resources;
    std::sort(resources.begin(), resources.end(), [](const auto& left, const auto& right) {
        return left.resource_id < right.resource_id;
    });
    json::ArrayBuilder values;
    for (const auto& value : resources) {
        json::ObjectBuilder item;
        item.add_string("resource_id", value.resource_id);
        item.add_string("before_digest", value.before_digest);
        item.add_string("after_digest", value.after_digest);
        item.add_bool("complete", value.complete);
        item.add_bool("changed", value.changed);
        values.add_object(item);
    }
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.play_candidate_protected_comparison.v1");
    output.add_string("provider_id", comparison.provider_id);
    output.add_string("provider_revision", comparison.provider_revision);
    output.add_bool("complete", comparison.complete);
    output.add_array("resources", values);
    if (include_digest) output.add_string("output_digest", comparison.output_digest);
    return output.serialize();
}

std::string packet_json(const PlayCandidateEvidencePacket& packet, bool include_digest)
{
    json::ArrayBuilder cases;
    for (const auto& value : packet.automated_cases) {
        json::ObjectBuilder item;
        item.add_string("case_id", value.case_id);
        item.add_bool("passed", value.passed);
        cases.add_object(item);
    }
    auto observation = json::parse(observation_json(packet.observation, true));
    auto comparison = json::parse(protected_json(packet.protected_comparison, true));
    json::ObjectBuilder process_output;
    process_output.add_unsigned_integer(
        "standard_output_bytes", packet.process_output.standard_output_bytes);
    process_output.add_unsigned_integer(
        "standard_error_bytes", packet.process_output.standard_error_bytes);
    process_output.add_string(
        "standard_output_digest", packet.process_output.standard_output_digest);
    process_output.add_string(
        "standard_error_digest", packet.process_output.standard_error_digest);
    process_output.add_string("combined_digest", packet.process_output.combined_digest);
    json::ObjectBuilder output;
    output.add_string("schema", packet.schema);
    output.add_string("canonicalization_version", packet.canonicalization_version);
    output.add_string(
        "technical_disposition",
        candidate_technical_disposition_name(packet.technical_disposition));
    output.add_string("policy_digest", packet.policy_digest);
    output.add_string("plan_id", packet.plan_id);
    output.add_string("plan_digest", packet.plan_digest);
    output.add_string("evidence_digest", packet.evidence_digest);
    output.add_string("permit_id", packet.permit_id);
    output.add_string("permit_claims_digest", packet.permit_claims_digest);
    output.add_bool("permit_consumed", packet.permit_consumed);
    output.add_string("process_identity_digest", packet.process_identity_digest);
    output.add_string("process_termination", packet.process_termination);
    if (observation) output.add_value("observation", observation.value());
    if (comparison) output.add_value("protected_comparison", comparison.value());
    output.add_object("process_output", process_output);
    output.add_array("automated_cases", cases);
    output.add_string("human_verdict", packet.human_verdict);
    output.add_bool("grants_authority", packet.grants_authority);
    output.add_bool("product_route_available", packet.product_route_available);
    if (include_digest) output.add_string("packet_digest", packet.packet_digest);
    return output.serialize();
}

} // namespace

std::vector<std::string> hermetic_policy_writable_resource_ids()
{
    return {kPolicyWritableResourceIds.begin(), kPolicyWritableResourceIds.end()};
}

std::vector<std::string> hermetic_policy_protected_resource_ids()
{
    return {kPolicyProtectedResourceIds.begin(), kPolicyProtectedResourceIds.end()};
}

std::vector<std::string> hermetic_candidate_automated_controls()
{
    return {kAutomatedNegativeControls.begin(), kAutomatedNegativeControls.end()};
}

facman::core::Result<FrozenHermeticPlayPolicy>
FrozenHermeticPlayPolicy::verify_canonical_document(
    const std::string& canonical_policy_json)
{
    auto policy = json::parse(canonical_policy_json);
    if (!policy || !policy.value().is_object()) {
        return facman::core::Result<FrozenHermeticPlayPolicy>::failure(candidate_error(
            "permit_wrong_policy", "frozen policy canonical document is not strict JSON",
            "$candidate.policy"));
    }
    std::string canonical = canonical_policy_json;
    while (!canonical.empty() &&
           std::isspace(static_cast<unsigned char>(canonical.back())) != 0) {
        canonical.pop_back();
    }
    if (sha256_text(canonical) != kHermeticCandidatePolicyDigest) {
        return facman::core::Result<FrozenHermeticPlayPolicy>::failure(candidate_error(
            "permit_wrong_policy", "frozen policy canonical digest does not match Gate 4A",
            "$candidate.policy.digest"));
    }
    const json::Value* candidate = object_field(policy.value(), "candidate");
    const json::Value* launch = object_field(policy.value(), "launch");
    const json::Value* claim = object_field(policy.value(), "claim");
    if (!string_field(policy.value(), "schema", "factorio.hermetic_standalone_play_policy.v1") ||
        !string_field(policy.value(), "policy_id", kHermeticCandidatePolicyId) ||
        !string_field(policy.value(), "policy_revision", kHermeticCandidatePolicyRevision) ||
        !string_field(policy.value(), "canonicalization_version", "facman.sorted-json.v1") ||
        candidate == nullptr || launch == nullptr || claim == nullptr ||
        !string_field(*candidate, "platform", "windows") ||
        !string_field(*candidate, "architecture", "x86_64") ||
        !string_field(*candidate, "factorio_version", "2.0.77") ||
        !string_field(*candidate, "distribution", "standalone_non_steam") ||
        !string_field(*launch, "operation_kind", kHermeticCandidateOperation) ||
        !string_field(*launch, "intent", kHermeticCandidateIntent) ||
        !string_field(*launch, "isolation_mode", kHermeticCandidateIsolation) ||
        !bool_field(*launch, "network_allowed", false) ||
        !bool_field(*launch, "credentials_allowed", false) ||
        !bool_field(*launch, "setup_allowed", false) ||
        !string_field(*claim, "claim_id", "factorio.hermetic_process_tree.v1") ||
        !bool_field(*claim, "whole_host_immutability_claimed", false)) {
        return facman::core::Result<FrozenHermeticPlayPolicy>::failure(candidate_error(
            "permit_wrong_policy", "frozen policy selectors or authority boundary changed",
            "$candidate.policy"));
    }
    FrozenHermeticPlayPolicy output;
    output.policy_id = kHermeticCandidatePolicyId;
    output.policy_revision = kHermeticCandidatePolicyRevision;
    output.policy_digest = kHermeticCandidatePolicyDigest;
    output.canonicalization_version = "facman.sorted-json.v1";
    output.verified = true;
    return facman::core::Result<FrozenHermeticPlayPolicy>::success(std::move(output));
}

facman::core::Result<HermeticCandidatePlan> build_hermetic_candidate_plan(
    CandidatePlanInput input)
{
    if (!input.policy.verified || input.policy.policy_id != kHermeticCandidatePolicyId ||
        input.policy.policy_revision != kHermeticCandidatePolicyRevision ||
        input.policy.policy_digest != kHermeticCandidatePolicyDigest) {
        return facman::core::Result<HermeticCandidatePlan>::failure(candidate_error(
            "permit_wrong_policy", "candidate requires the exact verified Gate 4A policy",
            "$candidate.policy"));
    }
    if (!exact_selector(input.selector)) {
        return facman::core::Result<HermeticCandidatePlan>::failure(candidate_error(
            "permit_wrong_operation", "candidate selector is outside the frozen class",
            "$candidate.selector"));
    }
    if (input.instance_id.empty() || input.machine_binding_id.empty() ||
        input.principal.provider_id.empty() || input.principal.principal_id.empty() ||
        input.principal.application_session_id.empty()) {
        return facman::core::Result<HermeticCandidatePlan>::failure(candidate_error(
            "permit_wrong_evidence", "instance, machine, and principal identities are required",
            "$candidate.identity"));
    }
    std::set<std::string> evidence_ids;
    for (const auto& binding : input.evidence) {
        if (!evidence_ids.insert(binding.requirement_id).second ||
            !lowercase_digest(binding.identity_digest)) {
            return facman::core::Result<HermeticCandidatePlan>::failure(candidate_error(
                "permit_wrong_evidence", "candidate evidence contains a duplicate or invalid digest",
                "$candidate.evidence"));
        }
    }
    if (evidence_ids != kRequiredEvidenceIds) {
        return facman::core::Result<HermeticCandidatePlan>::failure(candidate_error(
            "permit_wrong_evidence", "candidate does not bind the exact 31 policy evidence requirements",
            "$candidate.evidence"));
    }
    if (!exact_process_shape(input.process) || input.environment_revision != "factorio.menu-minimal.v1") {
        return facman::core::Result<HermeticCandidatePlan>::failure(candidate_error(
            "permit_wrong_plan", "candidate process request is not exact menu/minimal-environment shape",
            "$candidate.process"));
    }
    if (!exact_set(input.protected_resource_ids, kPolicyProtectedResourceIds)) {
        return facman::core::Result<HermeticCandidatePlan>::failure(candidate_error(
            "permit_wrong_resource", "candidate protected scope differs from frozen policy",
            "$candidate.protected_resources"));
    }
    const std::set<std::string> writable(
        input.writable_resource_ids.begin(), input.writable_resource_ids.end());
    if (writable.empty() || writable.size() != input.writable_resource_ids.size() ||
        writable.size() >= kPolicyWritableResourceIds.size() ||
        !std::includes(
            kPolicyWritableResourceIds.begin(), kPolicyWritableResourceIds.end(),
            writable.begin(), writable.end())) {
        return facman::core::Result<HermeticCandidatePlan>::failure(candidate_error(
            "permit_resource_set_not_closed",
            "runtime writable scope must be a duplicate-free strict subset of frozen policy",
            "$candidate.writable_resources"));
    }
    if (!exact_resource_closure(input.permit_resources, writable)) {
        return facman::core::Result<HermeticCandidatePlan>::failure(candidate_error(
            "permit_resource_set_not_closed",
            "candidate permit resources do not exactly bind writable and execution effects",
            "$candidate.permit_resources"));
    }
    if (input.permit_resources.empty() ||
        !provider_present(
            input.provider_revisions,
            kHermeticCandidateProviderId,
            kHermeticCandidateProviderRevision) ||
        !provider_present(
            input.provider_revisions,
            kHermeticObservationProviderId,
            kHermeticObservationProviderRevision)) {
        return facman::core::Result<HermeticCandidatePlan>::failure(candidate_error(
            "permit_wrong_provider", "candidate provider bindings are incomplete",
            "$candidate.providers"));
    }

    HermeticCandidatePlan output;
    output.policy = std::move(input.policy);
    output.selector = std::move(input.selector);
    output.instance_id = std::move(input.instance_id);
    output.machine_binding_id = std::move(input.machine_binding_id);
    output.principal = std::move(input.principal);
    output.evidence = std::move(input.evidence);
    output.evidence_digest = sha256_text(evidence_json(output.evidence));
    output.permit_resources = std::move(input.permit_resources);
    output.provider_revisions = std::move(input.provider_revisions);
    output.writable_resource_ids = sorted_unique(std::move(input.writable_resource_ids));
    output.protected_resource_ids = sorted_unique(std::move(input.protected_resource_ids));
    output.process = std::move(input.process);
    output.environment_revision = std::move(input.environment_revision);
    output.plan_digest = sha256_text(plan_core_json(output));
    output.plan_id = "play-plan-" + output.plan_digest.substr(0U, 32U);

    permit::OperationPermitClaims validation;
    validation.permit_id = "permit-00000000000000000000000000000000";
    validation.issuer_session_id = "session-00000000000000000000000000000000";
    validation.operation = {kHermeticCandidateOperation,
        std::string(kHermeticCandidateIntent), std::string(kHermeticCandidateIsolation)};
    validation.plan = {output.plan_id, output.plan_digest};
    validation.audience = {kHermeticCandidateProviderId, kHermeticCandidateProviderRevision};
    validation.resources = output.permit_resources;
    validation.effects = {"workspace_read", "workspace_write", "process_execute"};
    validation.required_capabilities = {"launch.execute.hermetic", "process.execute"};
    validation.machine_binding_id = output.machine_binding_id;
    validation.principal = output.principal;
    validation.evidence_digest = output.evidence_digest;
    validation.policy = {kHermeticCandidatePolicyRevision, kHermeticCandidatePolicyDigest};
    validation.provider_revisions = output.provider_revisions;
    validation.issued_at_unix_seconds = 1U;
    validation.not_before_unix_seconds = 1U;
    validation.expires_at_unix_seconds = 2U;
    validation.nonce = "nonce-00000000000000000000000000000000";
    if (auto canonical = permit::canonical_claims_json(validation); !canonical) {
        return facman::core::Result<HermeticCandidatePlan>::failure(canonical.error());
    }
    return facman::core::Result<HermeticCandidatePlan>::success(std::move(output));
}

std::string hermetic_candidate_plan_json(const HermeticCandidatePlan& plan)
{
    auto core = json::parse(plan_core_json(plan));
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.hermetic_play_candidate_plan.v1");
    output.add_string("canonicalization_version", "facman.sorted-json.v1");
    output.add_string("plan_id", plan.plan_id);
    output.add_string("plan_digest", plan.plan_digest);
    if (core) output.add_value("plan_core", core.value());
    output.add_bool("public_command_available", false);
    output.add_bool("human_verdict_recorded", false);
    return output.serialize();
}

permit::PermitValidationContext candidate_permit_context(
    const HermeticCandidatePlan& plan)
{
    permit::PermitValidationContext context;
    context.operation = {kHermeticCandidateOperation,
        std::string(kHermeticCandidateIntent), std::string(kHermeticCandidateIsolation)};
    context.plan = {plan.plan_id, plan.plan_digest};
    context.consumer = {kHermeticCandidateProviderId, kHermeticCandidateProviderRevision};
    context.resources = plan.permit_resources;
    context.effects = {"workspace_read", "workspace_write", "process_execute"};
    context.required_capabilities = {"launch.execute.hermetic", "process.execute"};
    context.machine_binding_id = plan.machine_binding_id;
    context.principal = plan.principal;
    context.evidence_digest = plan.evidence_digest;
    context.policy = {kHermeticCandidatePolicyRevision, kHermeticCandidatePolicyDigest};
    context.provider_revisions = plan.provider_revisions;
    return context;
}

facman::core::Result<void> PlatformPermitEntropySource::fill(
    unsigned char* output,
    std::size_t size) noexcept
{
    if (output == nullptr && size != 0U) {
        return facman::core::Result<void>::failure(candidate_error(
            "permit_missing", "secure random output is null", "$candidate.entropy",
            facman::core::OutcomeKind::unavailable));
    }
    try {
        facman::platform::fill_secure_random(output, size);
        return facman::core::Result<void>::success();
    } catch (const std::exception& error) {
        return facman::core::Result<void>::failure(candidate_error(
            "permit_missing", error.what(), "$candidate.entropy",
            facman::core::OutcomeKind::unavailable));
    } catch (...) {
        return facman::core::Result<void>::failure(candidate_error(
            "permit_missing", "platform secure random provider failed", "$candidate.entropy",
            facman::core::OutcomeKind::unavailable));
    }
}

CandidatePermitIssuer::CandidatePermitIssuer(std::uint64_t ttl_seconds)
    : ttl_seconds_(ttl_seconds)
{
}

facman::core::Result<permit::OperationPermitEnvelope> CandidatePermitIssuer::issue(
    const HermeticCandidatePlan& plan,
    const permit::PermitAuthenticator& authenticator,
    permit::PermitEntropySource& entropy,
    permit::PermitLedger& ledger,
    const permit::PermitClock& clock) const
{
    if (!plan.policy.verified || plan.policy.policy_digest != kHermeticCandidatePolicyDigest ||
        !exact_selector(plan.selector) || !plan_integrity_valid(plan) ||
        ttl_seconds_ == 0U || ttl_seconds_ > 30U) {
        return facman::core::Result<permit::OperationPermitEnvelope>::failure(candidate_error(
            "permit_wrong_policy", "candidate issuer rejected policy, selector, or TTL",
            "$candidate.issuer"));
    }
    facman::core::Error entropy_error = candidate_error(
        "permit_missing", "secure entropy unavailable", "$candidate.entropy",
        facman::core::OutcomeKind::unavailable);
    const std::string permit_id = random_prefixed_id(entropy, "permit-", entropy_error);
    if (permit_id.empty()) {
        return facman::core::Result<permit::OperationPermitEnvelope>::failure(entropy_error);
    }
    const std::string nonce = random_prefixed_id(entropy, "nonce-", entropy_error);
    if (nonce.empty()) {
        return facman::core::Result<permit::OperationPermitEnvelope>::failure(entropy_error);
    }
    const std::uint64_t now = clock.unix_seconds();
    const std::uint64_t monotonic = clock.monotonic_milliseconds();
    if (now > std::numeric_limits<std::uint64_t>::max() - ttl_seconds_ ||
        monotonic > std::numeric_limits<std::uint64_t>::max() - ttl_seconds_ * 1000U) {
        return facman::core::Result<permit::OperationPermitEnvelope>::failure(candidate_error(
            "permit_lifetime_exceeded", "candidate permit deadline overflowed",
            "$candidate.issuer.ttl"));
    }
    const permit::PermitValidationContext context = candidate_permit_context(plan);
    permit::OperationPermitClaims claims;
    claims.permit_id = permit_id;
    claims.issuer_session_id = authenticator.issuer_session_id();
    claims.operation = context.operation;
    claims.plan = context.plan;
    claims.audience = context.consumer;
    claims.resources = context.resources;
    claims.effects = context.effects;
    claims.required_capabilities = context.required_capabilities;
    claims.machine_binding_id = context.machine_binding_id;
    claims.principal = context.principal;
    claims.evidence_digest = context.evidence_digest;
    claims.policy = context.policy;
    claims.provider_revisions = context.provider_revisions;
    claims.issued_at_unix_seconds = now;
    claims.not_before_unix_seconds = now;
    claims.expires_at_unix_seconds = now + ttl_seconds_;
    claims.nonce = nonce;
    auto envelope = permit::seal_claims(claims, authenticator);
    if (!envelope) {
        return facman::core::Result<permit::OperationPermitEnvelope>::failure(envelope.error());
    }
    auto registered = ledger.register_issued(
        envelope.value(), monotonic, monotonic + ttl_seconds_ * 1000U);
    if (!registered) {
        return facman::core::Result<permit::OperationPermitEnvelope>::failure(registered.error());
    }
    return facman::core::Result<permit::OperationPermitEnvelope>::success(
        envelope.take_value());
}

bool ObservationGapState::any() const noexcept
{
    return lost_events || buffer_overflow || unknown_process_identity ||
        unresolved_target || delayed_events || attribution_gap || provider_failure;
}

std::string candidate_observation_artifact_json(
    const CandidateObservationResult& observation)
{
    CandidateObservationResult output = observation;
    output.output_digest = sha256_text(observation_json(output, false));
    return observation_json(output, true);
}

facman::core::Result<CandidateObservationResult> decode_candidate_observation_artifact(
    const std::string& text,
    const HermeticCandidatePlan& plan,
    const facman::platform::ProcessResult& process)
{
    auto document = json::parse(text, {64U * 1024U * 1024U, 32U, 1000000U, 4096U});
    if (!document || !document.value().is_object()) {
        return facman::core::Result<CandidateObservationResult>::failure(candidate_error(
            "permit_wrong_evidence", "observer artifact is not bounded strict JSON",
            "$candidate.observation"));
    }
    const std::set<std::string> expected_keys = {
        "active_before_process", "capture_complete", "capture_session_digest",
        "effects", "gaps", "output_digest", "plan_digest", "provider_id",
        "provider_revision", "raw_artifact_digest", "schema",
    };
    const std::vector<std::string> document_keys = document.value().object_keys();
    if (std::set<std::string>(document_keys.begin(), document_keys.end()) != expected_keys ||
        !string_field(document.value(), "schema", "factorio.play_candidate_observation.v1") ||
        !string_field(document.value(), "provider_id", kHermeticObservationProviderId) ||
        !string_field(document.value(), "provider_revision", kHermeticObservationProviderRevision) ||
        !string_field(document.value(), "plan_digest", plan.plan_digest)) {
        return facman::core::Result<CandidateObservationResult>::failure(candidate_error(
            "permit_wrong_evidence", "observer artifact identity or shape is not exact",
            "$candidate.observation"));
    }
    auto read_string = [&](const char* key, std::string& output) {
        const json::Value* value = document.value().find(key);
        if (value == nullptr) return false;
        auto decoded = value->string_value();
        if (!decoded) return false;
        output = decoded.take_value();
        return true;
    };
    auto read_bool = [&](const json::Value& object, const char* key, bool& output) {
        const json::Value* value = object.find(key);
        if (value == nullptr) return false;
        auto decoded = value->bool_value();
        if (!decoded) return false;
        output = decoded.value();
        return true;
    };
    CandidateObservationResult output;
    if (!read_string("plan_digest", output.plan_digest) ||
        !read_string("capture_session_digest", output.capture_session_digest) ||
        !read_string("raw_artifact_digest", output.raw_artifact_digest) ||
        !read_string("output_digest", output.output_digest) ||
        !lowercase_digest(output.capture_session_digest) ||
        !lowercase_digest(output.raw_artifact_digest) ||
        !lowercase_digest(output.output_digest) ||
        !read_bool(document.value(), "active_before_process", output.active_before_process) ||
        !read_bool(document.value(), "capture_complete", output.capture_complete)) {
        return facman::core::Result<CandidateObservationResult>::failure(candidate_error(
            "permit_wrong_evidence", "observer artifact bindings are malformed",
            "$candidate.observation"));
    }
    const json::Value* gaps = document.value().find("gaps");
    const json::Value* effects = document.value().find("effects");
    const std::vector<std::string> gap_keys =
        gaps != nullptr && gaps->is_object() ? gaps->object_keys() : std::vector<std::string> {};
    if (gaps == nullptr || !gaps->is_object() || effects == nullptr || !effects->is_array() ||
        std::set<std::string>(gap_keys.begin(), gap_keys.end()) !=
            std::set<std::string>{
                "attribution_gap", "buffer_overflow", "delayed_events", "lost_events",
                "provider_failure", "unknown_process_identity", "unresolved_target"} ||
        !read_bool(*gaps, "lost_events", output.gaps.lost_events) ||
        !read_bool(*gaps, "buffer_overflow", output.gaps.buffer_overflow) ||
        !read_bool(*gaps, "unknown_process_identity", output.gaps.unknown_process_identity) ||
        !read_bool(*gaps, "unresolved_target", output.gaps.unresolved_target) ||
        !read_bool(*gaps, "delayed_events", output.gaps.delayed_events) ||
        !read_bool(*gaps, "attribution_gap", output.gaps.attribution_gap) ||
        !read_bool(*gaps, "provider_failure", output.gaps.provider_failure)) {
        return facman::core::Result<CandidateObservationResult>::failure(candidate_error(
            "permit_wrong_evidence", "observer gap state is not closed",
            "$candidate.observation.gaps"));
    }
    const std::set<std::string> domains = {"filesystem", "process", "provider", "registry"};
    const std::set<std::string> classifications = {
        "external_unexpected", "external_unobserved", "forbidden", "protected",
        "unresolved", "writable"};
    bool primary_process_bound = false;
    for (std::size_t index = 0; index < effects->size(); ++index) {
        const json::Value* value = effects->at(index);
        const std::vector<std::string> effect_keys =
            value != nullptr && value->is_object()
                ? value->object_keys()
                : std::vector<std::string> {};
        if (value == nullptr || !value->is_object() ||
            std::set<std::string>(effect_keys.begin(), effect_keys.end()) !=
                std::set<std::string>{
                    "classification", "domain", "logical_resource_id",
                    "process_identity_digest", "sequence", "target_identity_digest"}) {
            return facman::core::Result<CandidateObservationResult>::failure(candidate_error(
                "permit_wrong_evidence", "observer effect shape is not exact",
                "$candidate.observation.effects"));
        }
        CandidateObservedEffect effect;
        auto read_effect_string = [&](const char* key, std::string& target) {
            const json::Value* member = value->find(key);
            if (member == nullptr) return false;
            auto decoded = member->string_value();
            if (!decoded) return false;
            target = decoded.take_value();
            return true;
        };
        const json::Value* sequence = value->find("sequence");
        auto sequence_value = sequence == nullptr
            ? facman::core::Result<std::uint64_t>::failure(candidate_error(
                "permit_wrong_evidence", "observer sequence is missing", "$candidate.observation"))
            : sequence->unsigned_integer_value();
        if (!sequence_value ||
            !read_effect_string("domain", effect.domain) ||
            !read_effect_string("process_identity_digest", effect.process_identity_digest) ||
            !read_effect_string("target_identity_digest", effect.target_identity_digest) ||
            !read_effect_string("logical_resource_id", effect.logical_resource_id) ||
            !read_effect_string("classification", effect.classification) ||
            domains.find(effect.domain) == domains.end() ||
            classifications.find(effect.classification) == classifications.end() ||
            !lowercase_digest(effect.process_identity_digest) ||
            !lowercase_digest(effect.target_identity_digest) ||
            effect.logical_resource_id.empty()) {
            return facman::core::Result<CandidateObservationResult>::failure(candidate_error(
                "permit_wrong_evidence", "observer effect value is invalid",
                "$candidate.observation.effects"));
        }
        effect.sequence = sequence_value.value();
        if (effect.domain == "process" && effect.logical_resource_id == "process.primary" &&
            process.identity.restart_safe() &&
            effect.process_identity_digest == sha256_text(
                "process-identity:" + process.identity.stable_start_identity)) {
            primary_process_bound = true;
        }
        output.effects.push_back(std::move(effect));
    }
    if (process.termination != facman::platform::ProcessTermination::start_failed &&
        !primary_process_bound) {
        output.gaps.unknown_process_identity = true;
        output.capture_complete = false;
    }
    if (output.output_digest != sha256_text(observation_json(output, false))) {
        return facman::core::Result<CandidateObservationResult>::failure(candidate_error(
            "permit_wrong_evidence", "observer artifact canonical digest does not match",
            "$candidate.observation.output_digest"));
    }
    return facman::core::Result<CandidateObservationResult>::success(std::move(output));
}

facman::core::Result<CandidateObservationResult>
read_candidate_observation_artifact_no_follow(
    const std::filesystem::path& path,
    const HermeticCandidatePlan& plan,
    const facman::platform::ProcessResult& process,
    std::size_t maximum_bytes)
{
    if (maximum_bytes == 0U) {
        return facman::core::Result<CandidateObservationResult>::failure(candidate_error(
            "permit_wrong_evidence", "observer artifact read limit is zero",
            "$candidate.observation"));
    }
    facman::platform::StableInputFile input;
    const auto opened = input.open_no_follow(path);
    if (!opened.ok() || input.size() > maximum_bytes) {
        return facman::core::Result<CandidateObservationResult>::failure(candidate_error(
            "permit_wrong_evidence",
            opened.ok() ? "observer artifact exceeds read bound" : opened.detail,
            "$candidate.observation"));
    }
    std::string text(static_cast<std::size_t>(input.size()), '\0');
    std::size_t offset = 0;
    while (offset < text.size()) {
        const std::size_t count = input.read_at(
            offset, text.data() + offset, text.size() - offset);
        if (count == 0U) {
            return facman::core::Result<CandidateObservationResult>::failure(candidate_error(
                "permit_wrong_evidence", "observer artifact stable read was incomplete",
                "$candidate.observation"));
        }
        offset += count;
    }
    const auto stable = input.revalidate();
    if (!stable.ok()) {
        return facman::core::Result<CandidateObservationResult>::failure(candidate_error(
            "permit_wrong_evidence", "observer artifact changed during stable read",
            "$candidate.observation"));
    }
    return decode_candidate_observation_artifact(text, plan, process);
}

BoundArtifactCandidateEffectObserver::BoundArtifactCandidateEffectObserver(
    CandidateObservationStart start_capture,
    CandidateObservationFinish finish_capture,
    std::size_t maximum_artifact_bytes)
    : start_capture_(std::move(start_capture)),
      finish_capture_(std::move(finish_capture)),
      maximum_artifact_bytes_(maximum_artifact_bytes)
{
}

facman::core::Result<void> BoundArtifactCandidateEffectObserver::begin(
    const HermeticCandidatePlan& plan)
{
    if (active_ || !start_capture_ || !finish_capture_ || maximum_artifact_bytes_ == 0U) {
        return facman::core::Result<void>::failure(candidate_error(
            "permit_wrong_evidence", "bound observation provider is not startable",
            "$candidate.observer", facman::core::OutcomeKind::unavailable));
    }
    auto started = start_capture_(plan);
    if (!started || !lowercase_digest(started.value())) {
        return facman::core::Result<void>::failure(
            started
                ? candidate_error(
                    "permit_wrong_evidence", "observer capture session identity is invalid",
                    "$candidate.observer.capture_session")
                : started.error());
    }
    plan_digest_ = plan.plan_digest;
    capture_session_digest_ = started.value();
    active_ = true;
    return facman::core::Result<void>::success();
}

bool BoundArtifactCandidateEffectObserver::active() const noexcept
{
    return active_;
}

CandidateObservationResult BoundArtifactCandidateEffectObserver::finish(
    const HermeticCandidatePlan& plan,
    const facman::platform::ProcessResult& process)
{
    CandidateObservationResult unavailable;
    unavailable.plan_digest = plan.plan_digest;
    unavailable.capture_session_digest = capture_session_digest_.empty()
        ? sha256_text("capture-session:unavailable")
        : capture_session_digest_;
    unavailable.raw_artifact_digest = sha256_text("observation-artifact:unavailable");
    unavailable.active_before_process = active_ && plan_digest_ == plan.plan_digest;
    unavailable.capture_complete = false;
    unavailable.gaps.provider_failure = true;
    active_ = false;
    if (!unavailable.active_before_process || !finish_capture_) {
        unavailable.output_digest = sha256_text(observation_json(unavailable, false));
        return unavailable;
    }
    auto artifact = finish_capture_(plan, process);
    if (!artifact) {
        unavailable.output_digest = sha256_text(observation_json(unavailable, false));
        return unavailable;
    }
    auto decoded = read_candidate_observation_artifact_no_follow(
        artifact.value(), plan, process, maximum_artifact_bytes_);
    if (!decoded || decoded.value().capture_session_digest != capture_session_digest_) {
        unavailable.output_digest = sha256_text(observation_json(unavailable, false));
        return unavailable;
    }
    return decoded.take_value();
}

facman::core::Result<CandidateExecutionRecord>
HermeticCandidateLaunchProvider::consume_and_execute(
    const permit::OperationPermitEnvelope& envelope,
    const HermeticCandidatePlan& reviewed_plan,
    const CandidateCurrentContext& observe_current,
    const permit::PermitAuthenticator& authenticator,
    permit::PermitLedger& ledger,
    const permit::PermitClock& clock,
    CandidateEffectObserver& observer,
    ProcessSupervisor& supervisor) const
{
    if (!reviewed_plan.policy.verified ||
        reviewed_plan.policy.policy_digest != kHermeticCandidatePolicyDigest ||
        !plan_integrity_valid(reviewed_plan)) {
        return facman::core::Result<CandidateExecutionRecord>::failure(candidate_error(
            "permit_wrong_policy", "launch provider rejected unverified candidate policy",
            "$candidate.provider.policy"));
    }
    auto observer_started = observer.begin(reviewed_plan);
    if (!observer_started) {
        return facman::core::Result<CandidateExecutionRecord>::failure(
            observer_started.error());
    }
    if (!observer.active()) {
        return facman::core::Result<CandidateExecutionRecord>::failure(candidate_error(
            "permit_wrong_evidence", "independent observer was not active before process boundary",
            "$candidate.observer", facman::core::OutcomeKind::unavailable));
    }
    const auto stop_observer_without_process = [&]() {
        facman::platform::ProcessResult not_started;
        not_started.termination = facman::platform::ProcessTermination::start_failed;
        (void)observer.finish(reviewed_plan, not_started);
    };
    if (!observe_current) {
        stop_observer_without_process();
        return facman::core::Result<CandidateExecutionRecord>::failure(candidate_error(
            "permit_wrong_evidence", "provider has no independent current-evidence callback",
            "$candidate.provider.evidence"));
    }
    auto current = observe_current();
    if (!current) {
        stop_observer_without_process();
        return facman::core::Result<CandidateExecutionRecord>::failure(current.error());
    }
    if (current.value().operation.kind != kHermeticCandidateOperation ||
        !current.value().operation.launch_intent ||
        *current.value().operation.launch_intent != kHermeticCandidateIntent ||
        !current.value().operation.isolation_mode ||
        *current.value().operation.isolation_mode != kHermeticCandidateIsolation ||
        current.value().consumer.provider_id != kHermeticCandidateProviderId ||
        current.value().consumer.provider_revision != kHermeticCandidateProviderRevision) {
        stop_observer_without_process();
        return facman::core::Result<CandidateExecutionRecord>::failure(candidate_error(
            "permit_wrong_operation", "launch provider current operation is outside exact candidate",
            "$candidate.provider.operation"));
    }

    CandidateExecutionRecord output;
    output.permit = validator_.consume(
        envelope, current.value(), authenticator, ledger, clock);
    if (!output.permit.accepted || !output.permit.consumed) {
        output.observation = observer.finish(reviewed_plan, output.process);
        return facman::core::Result<CandidateExecutionRecord>::success(std::move(output));
    }

    facman::platform::ProcessRequest request = reviewed_plan.process;
    const auto original_started = request.started;
    request.started = [original_started](const facman::platform::ProcessIdentity& identity) {
        if (original_started) original_started(identity);
    };
    output.process_creation_requested = true;
    output.process = supervisor.run(request);
    output.observation = observer.finish(reviewed_plan, output.process);
    if (output.process.termination != facman::platform::ProcessTermination::start_failed &&
        !output.process.identity.restart_safe()) {
        output.observation.gaps.unknown_process_identity = true;
        output.observation.capture_complete = false;
        output.observation.output_digest = sha256_text(
            observation_json(output.observation, false));
    }
    return facman::core::Result<CandidateExecutionRecord>::success(std::move(output));
}

CandidateOutputRecord candidate_output_record(
    const facman::platform::ProcessResult& process)
{
    CandidateOutputRecord output;
    output.standard_output_bytes = process.standard_output.size();
    output.standard_error_bytes = process.standard_error.size();
    output.standard_output_digest = sha256_text(process.standard_output);
    output.standard_error_digest = sha256_text(process.standard_error);
    output.combined_digest = sha256_text(
        "stdout:" + output.standard_output_digest + "\nstderr:" +
        output.standard_error_digest);
    return output;
}

const char* candidate_technical_disposition_name(
    CandidateTechnicalDisposition value) noexcept
{
    switch (value) {
    case CandidateTechnicalDisposition::refused_before_process:
        return "refused_before_process";
    case CandidateTechnicalDisposition::fail_evidence:
        return "fail_evidence";
    case CandidateTechnicalDisposition::inconclusive:
        return "inconclusive";
    case CandidateTechnicalDisposition::eligible_for_human_verdict:
        return "eligible_for_human_verdict";
    }
    return "inconclusive";
}

std::string PlayCandidateEvidencePacket::canonical_json() const
{
    return packet_json(*this, true);
}

facman::core::Result<PlayCandidateEvidencePacket> build_candidate_evidence_packet(
    const HermeticCandidatePlan& plan,
    const CandidateExecutionRecord& execution,
    ProtectedComparisonResult protected_comparison,
    std::vector<CandidateAutomatedCaseResult> automated_cases)
{
    if (!plan_integrity_valid(plan)) {
        return facman::core::Result<PlayCandidateEvidencePacket>::failure(candidate_error(
            "permit_wrong_plan", "candidate packet refused a mutated reviewed plan",
            "$candidate.packet.plan"));
    }
    std::set<std::string> comparison_ids;
    for (const auto& value : protected_comparison.resources) {
        if (!comparison_ids.insert(value.resource_id).second) {
            return facman::core::Result<PlayCandidateEvidencePacket>::failure(candidate_error(
                "permit_wrong_evidence", "protected comparison contains duplicate resources",
                "$candidate.packet.protected_comparison"));
        }
    }
    if (comparison_ids != std::set<std::string>(
            plan.protected_resource_ids.begin(), plan.protected_resource_ids.end())) {
        return facman::core::Result<PlayCandidateEvidencePacket>::failure(candidate_error(
            "permit_wrong_evidence", "protected comparison does not cover the exact policy scope",
            "$candidate.packet.protected_comparison"));
    }
    std::sort(automated_cases.begin(), automated_cases.end(), [](const auto& left, const auto& right) {
        return left.case_id < right.case_id;
    });
    std::set<std::string> case_ids;
    for (const auto& value : automated_cases) {
        if (!case_ids.insert(value.case_id).second) {
            return facman::core::Result<PlayCandidateEvidencePacket>::failure(candidate_error(
                "permit_wrong_evidence", "candidate automated matrix contains duplicate cases",
                "$candidate.packet.automated_cases"));
        }
    }
    if (case_ids != kAutomatedNegativeControls) {
        return facman::core::Result<PlayCandidateEvidencePacket>::failure(candidate_error(
            "permit_wrong_evidence", "candidate packet does not bind the exact automated matrix",
            "$candidate.packet.automated_cases"));
    }
    const std::string protected_core = protected_json(protected_comparison, false);
    if (protected_comparison.output_digest.empty()) {
        protected_comparison.output_digest = sha256_text(protected_core);
    } else if (protected_comparison.output_digest != sha256_text(protected_core)) {
        return facman::core::Result<PlayCandidateEvidencePacket>::failure(candidate_error(
            "permit_wrong_evidence", "protected comparison digest does not match its canonical output",
            "$candidate.packet.protected_comparison"));
    }
    CandidateObservationResult observation = execution.observation;
    if (observation.provider_id != kHermeticObservationProviderId ||
        observation.provider_revision != kHermeticObservationProviderRevision ||
        observation.plan_digest != plan.plan_digest ||
        !lowercase_digest(observation.capture_session_digest) ||
        !lowercase_digest(observation.raw_artifact_digest)) {
        return facman::core::Result<PlayCandidateEvidencePacket>::failure(candidate_error(
            "permit_wrong_evidence", "observer packet binding is missing or stale",
            "$candidate.packet.observation"));
    }
    const std::string observation_core = observation_json(observation, false);
    if (observation.output_digest.empty()) {
        observation.output_digest = sha256_text(observation_core);
    } else if (observation.output_digest != sha256_text(observation_core)) {
        return facman::core::Result<PlayCandidateEvidencePacket>::failure(candidate_error(
            "permit_wrong_evidence", "observer digest does not match its canonical output",
            "$candidate.packet.observation"));
    }

    PlayCandidateEvidencePacket output;
    output.policy_digest = plan.policy.policy_digest;
    output.plan_id = plan.plan_id;
    output.plan_digest = plan.plan_digest;
    output.evidence_digest = plan.evidence_digest;
    output.permit_id = execution.permit.permit_id;
    output.permit_claims_digest = execution.permit.claims_digest;
    output.permit_consumed = execution.permit.consumed;
    output.process_identity_digest = execution.process.identity.stable_start_identity.empty()
        ? sha256_text("process-identity:unavailable")
        : sha256_text("process-identity:" + execution.process.identity.stable_start_identity);
    output.process_termination = facman::platform::process_termination_name(
        execution.process.termination);
    output.observation = std::move(observation);
    output.protected_comparison = std::move(protected_comparison);
    output.process_output = candidate_output_record(execution.process);
    output.automated_cases = std::move(automated_cases);

    const bool automated_complete = std::all_of(
        output.automated_cases.begin(), output.automated_cases.end(),
        [](const auto& value) { return value.passed; });
    const bool protected_incomplete = !output.protected_comparison.complete ||
        std::any_of(
            output.protected_comparison.resources.begin(),
            output.protected_comparison.resources.end(),
            [](const auto& value) { return !value.complete; });
    const bool protected_changed = std::any_of(
        output.protected_comparison.resources.begin(),
        output.protected_comparison.resources.end(),
        [](const auto& value) { return value.changed; });
    const bool forbidden_effect = std::any_of(
        output.observation.effects.begin(), output.observation.effects.end(),
        [](const auto& value) {
            return value.classification == "forbidden" ||
                value.classification == "protected" ||
                value.classification == "external_unexpected";
        });
    if (!execution.permit.accepted || !execution.permit.consumed ||
        !execution.process_creation_requested) {
        output.technical_disposition = CandidateTechnicalDisposition::refused_before_process;
    } else if (output.observation.gaps.any() || !output.observation.capture_complete ||
        !output.observation.active_before_process || protected_incomplete ||
        !execution.process.identity.restart_safe() || !automated_complete) {
        output.technical_disposition = CandidateTechnicalDisposition::inconclusive;
    } else if (protected_changed || forbidden_effect) {
        output.technical_disposition = CandidateTechnicalDisposition::fail_evidence;
    } else {
        output.technical_disposition =
            CandidateTechnicalDisposition::eligible_for_human_verdict;
    }
    output.packet_digest = sha256_text(packet_json(output, false));
    return facman::core::Result<PlayCandidateEvidencePacket>::success(std::move(output));
}

facman::core::Result<CandidateArtifactRecord> persist_candidate_artifacts(
    const std::filesystem::path& workspace,
    const std::string& operation_id,
    const PlayCandidateEvidencePacket& packet,
    const facman::platform::ProcessResult& process)
{
    std::string identifier_detail;
    if (!facman::base::validate_identifier(operation_id, identifier_detail)) {
        return facman::core::Result<CandidateArtifactRecord>::failure(candidate_error(
            "permit_wrong_resource", identifier_detail, "$candidate.artifacts.operation_id"));
    }
    const CandidateOutputRecord output_record = candidate_output_record(process);
    if (output_record.combined_digest != packet.process_output.combined_digest ||
        packet.packet_digest != sha256_text(packet_json(packet, false)) ||
        packet.human_verdict != "unset" || packet.grants_authority ||
        packet.product_route_available) {
        return facman::core::Result<CandidateArtifactRecord>::failure(candidate_error(
            "permit_wrong_evidence", "candidate packet or separated process output is stale",
            "$candidate.artifacts"));
    }
    auto destination = facman::base::managed_directory(
        workspace, "operations", operation_id);
    auto operation_temporary = facman::base::managed_directory(
        workspace, "temporary", operation_id);
    if (!destination.ok() || !operation_temporary.ok()) {
        const auto& failed = destination.ok() ? operation_temporary : destination;
        return facman::core::Result<CandidateArtifactRecord>::failure(candidate_error(
            "permit_wrong_resource", failed.detail, "$candidate.artifacts"));
    }
    const std::filesystem::path staging =
        operation_temporary.path / "candidate-artifacts";
    std::error_code error;
    if (std::filesystem::exists(destination.path, error) ||
        std::filesystem::exists(staging, error)) {
        return facman::core::Result<CandidateArtifactRecord>::failure(candidate_error(
            "permit_wrong_resource", "candidate operation artifact directory already exists",
            "$candidate.artifacts"));
    }
    const std::filesystem::path marker = staging / ".facman-candidate-owned";
    const std::filesystem::path lifecycle =
        staging / "lifecycle" / "candidate-packet.json";
    const std::filesystem::path standard_output =
        staging / "output" / "stdout.log";
    const std::filesystem::path standard_error =
        staging / "output" / "stderr.log";
    std::string detail;
    const bool wrote_marker = facman::base::write_text_new_atomic(
        marker, "FACMAN-HERMETIC-STANDALONE-PLAY-CANDIDATE-01\n", detail);
    const bool wrote_output = wrote_marker && facman::base::write_text_new_atomic(
        standard_output, process.standard_output, detail);
    const bool wrote_error = wrote_output && facman::base::write_text_new_atomic(
        standard_error, process.standard_error, detail);
    const bool wrote_lifecycle = wrote_error && facman::base::write_text_new_atomic(
        lifecycle, packet.canonical_json() + "\n", detail);
    if (!wrote_lifecycle) {
        std::string cleanup_detail;
        if (wrote_marker) {
            (void)facman::base::remove_owned_staging_tree(
                staging, marker.filename().string(), cleanup_detail);
        }
        return facman::core::Result<CandidateArtifactRecord>::failure(candidate_error(
            "permit_wrong_evidence", "candidate artifact staging failed: " + detail,
            "$candidate.artifacts", facman::core::OutcomeKind::recovery_required));
    }
    std::filesystem::create_directories(destination.path.parent_path(), error);
    if (error) {
        std::string cleanup_detail;
        (void)facman::base::remove_owned_staging_tree(
            staging, marker.filename().string(), cleanup_detail);
        return facman::core::Result<CandidateArtifactRecord>::failure(candidate_error(
            "permit_wrong_resource", "candidate operation parent could not be created: " +
                error.message(),
            "$candidate.artifacts", facman::core::OutcomeKind::recovery_required));
    }
    if (!facman::base::commit_directory_no_clobber(
            staging, destination.path, detail)) {
        std::string cleanup_detail;
        (void)facman::base::remove_owned_staging_tree(
            staging, marker.filename().string(), cleanup_detail);
        return facman::core::Result<CandidateArtifactRecord>::failure(candidate_error(
            "permit_wrong_evidence", "candidate artifact commit failed: " + detail,
            "$candidate.artifacts", facman::core::OutcomeKind::recovery_required));
    }
    std::filesystem::remove(operation_temporary.path, error);
    CandidateArtifactRecord output;
    output.operation_directory = destination.path;
    output.lifecycle_packet_path =
        destination.path / "lifecycle" / "candidate-packet.json";
    output.standard_output_path = destination.path / "output" / "stdout.log";
    output.standard_error_path = destination.path / "output" / "stderr.log";
    output.process_output = output_record;
    return facman::core::Result<CandidateArtifactRecord>::success(std::move(output));
}

facman::core::Result<std::string> read_candidate_lifecycle_packet_no_follow(
    const std::filesystem::path& path,
    const std::string& expected_packet_digest,
    std::size_t maximum_bytes)
{
    if (maximum_bytes == 0U || !lowercase_digest(expected_packet_digest)) {
        return facman::core::Result<std::string>::failure(candidate_error(
            "permit_wrong_evidence", "candidate lifecycle read bound is invalid",
            "$candidate.lifecycle"));
    }
    facman::platform::StableInputFile input;
    const auto opened = input.open_no_follow(path);
    if (!opened.ok() || input.size() > maximum_bytes) {
        return facman::core::Result<std::string>::failure(candidate_error(
            "permit_wrong_evidence",
            opened.ok() ? "candidate lifecycle packet exceeds its read bound" : opened.detail,
            "$candidate.lifecycle"));
    }
    std::string text(static_cast<std::size_t>(input.size()), '\0');
    std::size_t offset = 0;
    while (offset < text.size()) {
        const std::size_t count = input.read_at(
            offset, text.data() + offset, text.size() - offset);
        if (count == 0U) {
            return facman::core::Result<std::string>::failure(candidate_error(
                "permit_wrong_evidence", "candidate lifecycle stable read was incomplete",
                "$candidate.lifecycle"));
        }
        offset += count;
    }
    const auto stable = input.revalidate();
    auto document = json::parse(text);
    const std::set<std::string> expected_keys = {
        "automated_cases", "canonicalization_version", "evidence_digest",
        "grants_authority", "human_verdict", "observation", "packet_digest",
        "permit_claims_digest", "permit_consumed", "permit_id", "plan_digest",
        "plan_id", "policy_digest", "process_identity_digest", "process_output",
        "process_termination", "product_route_available", "protected_comparison",
        "schema", "technical_disposition",
    };
    const std::vector<std::string> actual_keys =
        document && document.value().is_object()
            ? document.value().object_keys()
            : std::vector<std::string> {};
    std::string packet_digest;
    if (document && document.value().is_object()) {
        const json::Value* digest_value = document.value().find("packet_digest");
        if (digest_value != nullptr) {
            auto decoded = digest_value->string_value();
            if (decoded) packet_digest = decoded.value();
        }
    }
    std::string canonical_text = text;
    while (!canonical_text.empty() &&
           std::isspace(static_cast<unsigned char>(canonical_text.back())) != 0) {
        canonical_text.pop_back();
    }
    const std::string digest_suffix =
        "," + json::quote_string("packet_digest") + ":" +
        json::quote_string(packet_digest) + "}";
    const bool canonical_suffix = canonical_text.size() > digest_suffix.size() &&
        canonical_text.compare(
            canonical_text.size() - digest_suffix.size(), digest_suffix.size(), digest_suffix) == 0;
    std::string packet_core;
    if (canonical_suffix) {
        packet_core = canonical_text.substr(0U, canonical_text.size() - digest_suffix.size());
        packet_core.push_back('}');
    }
    const bool closed_shape =
        std::set<std::string>(actual_keys.begin(), actual_keys.end()) == expected_keys;
    const bool digest_matches = canonical_suffix && packet_digest == expected_packet_digest &&
        packet_digest == sha256_text(packet_core);
    const bool boundary_matches = document && document.value().is_object() &&
        string_field(document.value(), "schema", "factorio.play_candidate_evidence_packet.v1") &&
        string_field(document.value(), "human_verdict", "unset") &&
        bool_field(document.value(), "grants_authority", false) &&
        bool_field(document.value(), "product_route_available", false) &&
        document.value().find("authenticator_value") == nullptr;
    if (!stable.ok() || !document || !document.value().is_object() ||
        !closed_shape || !digest_matches || !boundary_matches) {
        std::string failure_detail;
        if (!stable.ok()) failure_detail += "unstable_read ";
        if (!document || !document.value().is_object()) failure_detail += "invalid_json ";
        if (!closed_shape) failure_detail += "open_shape ";
        if (!digest_matches) failure_detail += "digest_mismatch ";
        if (!boundary_matches) failure_detail += "authority_boundary ";
        return facman::core::Result<std::string>::failure(candidate_error(
            "permit_wrong_evidence", "candidate lifecycle packet is unstable or violates boundary",
            "$candidate.lifecycle:" + failure_detail));
    }
    return facman::core::Result<std::string>::success(std::move(text));
}

} // namespace facman::factorio::launch
