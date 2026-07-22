// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_candidate_projection.h"

#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "flb_factorio_permit_projection.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <set>
#include <tuple>
#include <utility>

namespace facman::factorio::instance {
namespace {

namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace permit = facman::core::permit;
namespace play = facman::factorio::launch;

facman::core::Error projection_error(
    std::string code,
    std::string message,
    std::string path,
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::refused)
{
    return {std::move(code), std::move(message), std::move(path), kind};
}

#ifdef _WIN32
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

facman::core::Result<std::string> stable_file_sha256(const fs::path& path)
{
    facman::platform::StableInputFile input;
    const auto opened = input.open_no_follow(path);
    if (!opened.ok()) {
        return facman::core::Result<std::string>::failure(projection_error(
            "permit_wrong_evidence", opened.detail, "$candidate.executable"));
    }
    facman::base::Sha256Hasher hasher;
    std::array<unsigned char, 64U * 1024U> buffer {};
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t count = input.read_at(offset, buffer.data(), buffer.size());
        if (count == 0U) {
            return facman::core::Result<std::string>::failure(projection_error(
                "permit_wrong_evidence", "stable candidate file read was incomplete",
                "$candidate.executable"));
        }
        hasher.update(buffer.data(), count);
        offset += count;
    }
    const auto stable = input.revalidate();
    if (!stable.ok()) {
        return facman::core::Result<std::string>::failure(projection_error(
            "permit_resource_stale", stable.detail, "$candidate.executable"));
    }
    return facman::core::Result<std::string>::success(hasher.finish());
}

std::string path_identity_digest(const facman::platform::PathIdentity& value)
{
    json::ObjectBuilder identity;
    identity.add_unsigned_integer("kind", static_cast<std::uint64_t>(value.kind));
    identity.add_bool("exists", value.exists);
    identity.add_bool("reparse_or_link", value.reparse_or_link);
    identity.add_bool("fixed_local_volume", value.fixed_local_volume);
    identity.add_unsigned_integer("device", value.device);
    identity.add_unsigned_integer("object", value.object);
    identity.add_unsigned_integer("size", value.size);
    identity.add_unsigned_integer("last_write_ticks", value.last_write_ticks);
    identity.add_string("filesystem_name", value.filesystem_name);
    return sha256_text(identity.serialize());
}

bool path_is_beneath(const fs::path& root, const fs::path& candidate)
{
    const fs::path relative = candidate.lexically_relative(root);
    if (relative.empty() || relative.is_absolute()) return false;
    const std::string value = relative.generic_string();
    return value != ".." && value.rfind("../", 0U) != 0U;
}

facman::core::Result<std::string> exact_path_identity(
    const fs::path& path,
    bool require_file)
{
    std::string detail;
    if (facman::base::path_crosses_link_or_reparse_point(path, detail)) {
        return facman::core::Result<std::string>::failure(projection_error(
            "permit_wrong_resource", detail, "$candidate.path"));
    }
    facman::platform::PathIdentity identity;
    const auto observed = facman::platform::inspect_path_no_follow(path, identity);
    const auto expected_kind = require_file
        ? facman::platform::PathObjectKind::regular_file
        : facman::platform::PathObjectKind::directory;
    if (!observed.ok() || !identity.exists || identity.reparse_or_link ||
        identity.kind != expected_kind) {
        return facman::core::Result<std::string>::failure(projection_error(
            "permit_wrong_resource",
            observed.ok() ? "candidate path kind or identity is invalid" : observed.detail,
            "$candidate.path"));
    }
#ifdef _WIN32
    std::string filesystem = identity.filesystem_name;
    std::transform(filesystem.begin(), filesystem.end(), filesystem.begin(), [](unsigned char byte) {
        return static_cast<char>(std::tolower(byte));
    });
    if (!identity.fixed_local_volume || filesystem != "ntfs") {
        return facman::core::Result<std::string>::failure(projection_error(
            "permit_wrong_resource", "candidate requires a fixed local NTFS object",
            "$candidate.path"));
    }
#endif
    return facman::core::Result<std::string>::success(path_identity_digest(identity));
}

facman::core::Result<std::string> optional_directory_identity(
    const fs::path& workspace,
    const fs::path& path)
{
    std::error_code root_error;
    const fs::path root = fs::weakly_canonical(workspace, root_error);
    if (root_error) {
        return facman::core::Result<std::string>::failure(projection_error(
            "permit_wrong_resource", "candidate workspace identity is unavailable",
            "$candidate.writable_resource"));
    }
    const fs::path normalized = path.lexically_normal();
    if (!path_is_beneath(root, normalized)) {
        return facman::core::Result<std::string>::failure(projection_error(
            "permit_wrong_resource", "candidate writable resource escapes the workspace",
            "$candidate.writable_resource"));
    }
    std::string detail;
    if (facman::base::path_crosses_link_or_reparse_point(normalized, detail)) {
        return facman::core::Result<std::string>::failure(projection_error(
            "permit_wrong_resource", detail, "$candidate.writable_resource"));
    }
    auto root_identity = exact_path_identity(root, false);
    if (!root_identity) return root_identity;
    facman::platform::PathIdentity identity;
    const auto observed = facman::platform::inspect_path_no_follow(normalized, identity);
    if (!observed.ok() || identity.reparse_or_link ||
        (identity.exists && identity.kind != facman::platform::PathObjectKind::directory)) {
        return facman::core::Result<std::string>::failure(projection_error(
            "permit_wrong_resource",
            observed.ok() ? "candidate writable resource is not a directory" : observed.detail,
            "$candidate.writable_resource"));
    }
#ifdef _WIN32
    if (identity.exists) {
        std::string filesystem = identity.filesystem_name;
        std::transform(filesystem.begin(), filesystem.end(), filesystem.begin(), [](unsigned char byte) {
            return static_cast<char>(std::tolower(byte));
        });
        if (!identity.fixed_local_volume || filesystem != "ntfs") {
            return facman::core::Result<std::string>::failure(projection_error(
                "permit_wrong_resource", "candidate writable resource requires fixed local NTFS",
                "$candidate.writable_resource"));
        }
    }
#endif
    json::ObjectBuilder binding;
    binding.add_string("workspace_identity_digest", root_identity.value());
    binding.add_string("relative_path_digest", sha256_text(
        normalized.lexically_relative(root).generic_string()));
    binding.add_bool("exists", identity.exists);
    binding.add_string(
        "object_identity_digest",
        identity.exists ? path_identity_digest(identity) : sha256_text("absent"));
    return facman::core::Result<std::string>::success(sha256_text(binding.serialize()));
}

const permit::ResourceBinding* find_resource(
    const std::vector<permit::ResourceBinding>& resources,
    const std::string& kind)
{
    const auto found = std::find_if(resources.begin(), resources.end(), [&](const auto& value) {
        return value.resource_kind == kind;
    });
    return found == resources.end() ? nullptr : &*found;
}

permit::ResourceBinding resource(
    std::string kind,
    std::string role,
    std::string id,
    std::string identity,
    permit::ProviderIdentity provider,
    std::vector<std::string> effects)
{
    return {std::move(kind), std::move(role), std::move(id), std::move(identity),
        std::move(provider), std::move(effects)};
}
#endif

} // namespace

facman::core::Result<play::HermeticCandidatePlan>
project_hermetic_candidate_plan(
    const HermeticCandidateProjectionRequest& request)
{
#ifndef _WIN32
    (void)request;
    return facman::core::Result<play::HermeticCandidatePlan>::failure(projection_error(
        "permit_wrong_operation", "the frozen candidate is available only on Windows x64",
        "$candidate.selector", facman::core::OutcomeKind::unavailable));
#else
    const std::vector<std::string> required_input_digests = {
        request.expected_executable_sha256,
        request.authenticated_source_artifact_digest,
        request.source_authentication_evidence_digest,
        request.facman_source_revision_digest,
        request.facman_build_identity_digest,
        request.protected_baseline_digest,
        request.writable_baseline_digest,
    };
    if (request.workspace.empty() || request.instance_id.empty() ||
        request.operation_id.empty() || request.installation_root.empty() ||
        request.executable.empty() || request.windows_system_root.empty() ||
        !std::all_of(required_input_digests.begin(), required_input_digests.end(), lowercase_digest)) {
        return facman::core::Result<play::HermeticCandidatePlan>::failure(projection_error(
            "permit_wrong_evidence", "candidate projection input is incomplete",
            "$candidate.projection"));
    }
    std::error_code install_error;
    std::error_code executable_error;
    const fs::path install = fs::weakly_canonical(request.installation_root, install_error);
    const fs::path executable = fs::weakly_canonical(request.executable, executable_error);
    if (install_error || executable_error || !path_is_beneath(install, executable)) {
        return facman::core::Result<play::HermeticCandidatePlan>::failure(projection_error(
            "permit_wrong_resource", "candidate executable is not inside selected installation",
            "$candidate.executable"));
    }
    auto installation_identity = exact_path_identity(install, false);
    auto executable_identity = exact_path_identity(executable, true);
    auto read_data_identity = exact_path_identity(install / "data", false);
    const fs::path instance_root = request.workspace / "instances" / request.instance_id;
    auto write_data_identity = exact_path_identity(instance_root, false);
    auto mod_root_identity = exact_path_identity(instance_root / "mods", false);
    auto executable_sha256 = stable_file_sha256(executable);
    auto base_capability = stable_file_sha256(install / "data" / "base" / "info.json");
    if (!installation_identity || !executable_identity || !read_data_identity ||
        !write_data_identity || !mod_root_identity || !executable_sha256 || !base_capability) {
        const facman::core::Error* error = nullptr;
        if (!installation_identity) error = &installation_identity.error();
        else if (!executable_identity) error = &executable_identity.error();
        else if (!read_data_identity) error = &read_data_identity.error();
        else if (!write_data_identity) error = &write_data_identity.error();
        else if (!mod_root_identity) error = &mod_root_identity.error();
        else if (!executable_sha256) error = &executable_sha256.error();
        else error = &base_capability.error();
        return facman::core::Result<play::HermeticCandidatePlan>::failure(*error);
    }
    if (executable_sha256.value() != request.expected_executable_sha256) {
        return facman::core::Result<play::HermeticCandidatePlan>::failure(projection_error(
            "permit_resource_stale", "installed executable differs from authenticated source evidence",
            "$candidate.executable.sha256"));
    }
    auto projected = project_menu_permit_resources(request.workspace, request.instance_id);
    if (!projected) {
        return facman::core::Result<play::HermeticCandidatePlan>::failure(projected.error());
    }
    const auto* spec = find_resource(projected.value().resources, "factorio.instance-spec");
    const auto* binding = find_resource(projected.value().resources, "factorio.instance-binding");
    const auto* readiness = find_resource(projected.value().resources, "factorio.instance-readiness");
    const auto* installation = find_resource(projected.value().resources, "factorio.installation-evidence");
    const auto* config = find_resource(projected.value().resources, "factorio.effective-config");
    const auto* modset = find_resource(projected.value().resources, "factorio.modset-lock");
    if (spec == nullptr || binding == nullptr || readiness == nullptr || installation == nullptr ||
        config == nullptr || modset == nullptr) {
        return facman::core::Result<play::HermeticCandidatePlan>::failure(projection_error(
            "permit_wrong_evidence", "Gate 2 projection lacks a required candidate resource",
            "$candidate.projection"));
    }

    const permit::ProviderIdentity candidate_provider {
        play::kHermeticCandidateProviderId, play::kHermeticCandidateProviderRevision};
    const permit::ProviderIdentity observer_provider {
        play::kHermeticObservationProviderId, play::kHermeticObservationProviderRevision};
    std::vector<permit::ProviderIdentity> providers;
    for (const auto& value : projected.value().provider_revisions) {
        if (value.provider_id != play::kHermeticCandidateProviderId) providers.push_back(value);
    }
    providers.push_back(candidate_provider);
    providers.push_back(observer_provider);

    std::vector<permit::ResourceBinding> resources = projected.value().resources;
    for (auto& value : resources) {
        if (value.owning_provider.provider_id == play::kHermeticCandidateProviderId) {
            value.owning_provider = candidate_provider;
        }
    }
    resources.push_back(resource(
        "factorio.executable", "process-image", "instance:" + request.instance_id + ":executable",
        sha256_text(executable_identity.value() + ":" + executable_sha256.value()),
        candidate_provider, {"process_execute", "workspace_read"}));
    resources.push_back(resource(
        "factorio.installation-root", "application-root", "instance:" + request.instance_id + ":read-data",
        installation_identity.value(), candidate_provider, {"workspace_read"}));
    resources.push_back(resource(
        "factorio.play-policy", "frozen-policy", "policy:" + request.policy.policy_id,
        request.policy.policy_digest, candidate_provider, {"workspace_read"}));
    resources.push_back(resource(
        "factorio.observation", "effect-evidence", "operation:" + request.operation_id + ":observer",
        sha256_text(play::kHermeticObservationProviderRevision), observer_provider,
        {"workspace_read", "workspace_write"}));
    resources.push_back(resource(
        "factorio.protected-baseline", "protected-state", "operation:" + request.operation_id + ":protected",
        request.protected_baseline_digest, observer_provider, {"workspace_read"}));
    resources.push_back(resource(
        "factorio.writable-baseline", "writable-state", "operation:" + request.operation_id + ":writable",
        request.writable_baseline_digest, observer_provider, {"workspace_read"}));
    resources.push_back(resource(
        "factorio.operation-state", "operation-record", "operation:" + request.operation_id + ":record",
        sha256_text("operation-record:" + request.operation_id), candidate_provider,
        {"workspace_read", "workspace_write"}));

    const std::vector<std::pair<std::string, fs::path>> writable_paths = {
        {"instance.config", instance_root / "config"},
        {"instance.locks", instance_root / "locks"},
        {"instance.logs", instance_root / "logs"},
        {"instance.mods", instance_root / "mods"},
        {"instance.saves", instance_root / "saves"},
        {"instance.state", instance_root / "state"},
        {"operation.record", request.workspace / "operations" / request.operation_id},
        {"operation.temporary", request.workspace / "temporary" / request.operation_id},
    };
    for (const auto& [resource_id, path] : writable_paths) {
        auto identity = optional_directory_identity(request.workspace, path);
        if (!identity) {
            return facman::core::Result<play::HermeticCandidatePlan>::failure(identity.error());
        }
        resources.push_back(resource(
            "factorio.writable-root", resource_id,
            "instance:" + request.instance_id + ":writable:" + resource_id,
            identity.value(), candidate_provider, {"workspace_read", "workspace_write"}));
    }

    facman::platform::ProcessRequest process;
    process.executable = executable;
    process.arguments = {
        "--config", facman::platform::path_to_utf8(instance_root / "config" / "config.ini"),
        "--mod-directory", facman::platform::path_to_utf8(instance_root / "mods")};
    process.working_directory = executable.parent_path();
    const fs::path operation_temporary =
        request.workspace / "temporary" / request.operation_id / "process";
    process.environment = {
        {"SystemRoot", facman::platform::path_to_utf8(request.windows_system_root)},
        {"TEMP", facman::platform::path_to_utf8(operation_temporary)},
        {"TMP", facman::platform::path_to_utf8(operation_temporary)},
        {"USERPROFILE", facman::platform::path_to_utf8(instance_root / "state" / "userprofile")},
        {"WINDIR", facman::platform::path_to_utf8(request.windows_system_root)},
    };
    process.inherit_environment = false;
    process.timeout = std::chrono::minutes(30);

    json::ArrayBuilder arguments;
    for (const std::string& value : process.arguments) arguments.add_string(sha256_text(value));
    json::ObjectBuilder launch_command;
    launch_command.add_string("executable_identity", executable_identity.value());
    launch_command.add_string("executable_sha256", executable_sha256.value());
    launch_command.add_array("argument_digests", arguments);
    launch_command.add_string("environment_revision", "factorio.menu-minimal.v1");
    launch_command.add_string("intent", "menu");
    launch_command.add_string("isolation", "hermetic");
    const std::string launch_command_digest = sha256_text(launch_command.serialize());
    const std::string launch_command_id = "menu-launch-" + launch_command_digest.substr(0U, 32U);

    std::vector<play::CandidateEvidenceBinding> evidence = {
        {"application.session", sha256_text(request.principal.application_session_id)},
        {"config.digest", config->current_identity_digest},
        {"executable.identity", executable_identity.value()},
        {"executable.publisher_source", sha256_text(
            request.authenticated_source_artifact_digest + ":" +
            request.source_authentication_evidence_digest)},
        {"executable.sha256", executable_sha256.value()},
        {"facman.build_identity", request.facman_build_identity_digest},
        {"facman.source_revision", request.facman_source_revision_digest},
        {"factorio.content_capabilities", base_capability.value()},
        {"factorio.version", sha256_text("2.0.77")},
        {"installation.evidence_digest", installation->current_identity_digest},
        {"installation.root_identity", installation_identity.value()},
        {"instance.binding_digest", binding->current_identity_digest},
        {"instance.readiness_digest", readiness->current_identity_digest},
        {"instance.spec_digest", spec->current_identity_digest},
        {"isolation.mode", sha256_text("hermetic")},
        {"launch.intent", sha256_text("menu")},
        {"launch.plan_digest", launch_command_digest},
        {"launch.plan_identity", sha256_text(launch_command_id)},
        {"machine.binding", sha256_text(request.machine_binding_id)},
        {"mod_root.identity", mod_root_identity.value()},
        {"modset.state", modset->current_identity_digest},
        {"observation.provider_revision", sha256_text(play::kHermeticObservationProviderRevision)},
        {"policy.digest", sha256_text(request.policy.policy_digest)},
        {"policy.revision", sha256_text(request.policy.policy_revision)},
        {"principal.identity", sha256_text(
            request.principal.provider_id + ":" + request.principal.principal_id)},
        {"protected.baseline_digest", request.protected_baseline_digest},
        {"read_data.identity", read_data_identity.value()},
        {"universal_launcher.revision", sha256_text("7bd4425f0c35414f738159b45d8bec42edf70235")},
        {"universal_setup.revision", sha256_text("3f8489275077347c2918f3bb03614ec6431362ff")},
        {"writable.baseline_digest", request.writable_baseline_digest},
        {"write_data.identity", write_data_identity.value()},
    };
    play::CandidatePlanInput plan;
    plan.policy = request.policy;
    plan.selector = {
        "windows", "x86_64", "2.0.77", "standalone_non_steam",
        "sha256_bound_to_authenticated_wube_source", "ntfs", "fixed_local",
        "facman_owned", "explicit_empty_lock", "none", "none", "none"};
    plan.instance_id = request.instance_id;
    plan.machine_binding_id = request.machine_binding_id;
    plan.principal = request.principal;
    plan.evidence = std::move(evidence);
    plan.permit_resources = std::move(resources);
    plan.provider_revisions = std::move(providers);
    plan.writable_resource_ids = {
        "instance.config", "instance.locks", "instance.logs", "instance.mods",
        "instance.saves", "instance.state", "operation.record", "operation.temporary"};
    plan.protected_resource_ids = play::hermetic_policy_protected_resource_ids();
    plan.process = std::move(process);
    plan.environment_revision = "factorio.menu-minimal.v1";
    return play::build_hermetic_candidate_plan(std::move(plan));
#endif
}

facman::core::Result<permit::PermitValidationContext>
reobserve_hermetic_candidate_context(
    const HermeticCandidateProjectionRequest& request)
{
    auto current = project_hermetic_candidate_plan(request);
    if (!current) {
        return facman::core::Result<permit::PermitValidationContext>::failure(current.error());
    }
    return facman::core::Result<permit::PermitValidationContext>::success(
        play::candidate_permit_context(current.value()));
}

} // namespace facman::factorio::instance
