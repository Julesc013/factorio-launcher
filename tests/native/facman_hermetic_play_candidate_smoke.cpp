// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_json.h"
#include "fl_operation_permit.h"
#include "fl_sha256.h"
#include "flb_factorio_candidate_manifest.h"
#include "flb_factorio_hermetic_candidate.h"

#include <algorithm>
#include <array>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <set>
#include <string>
#include <vector>

namespace {

namespace fs = std::filesystem;
namespace permit = facman::core::permit;
namespace launch = facman::factorio::launch;

std::string digest(const std::string& value)
{
    return facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(value.data()), value.size());
}

std::string read_text(const fs::path& path)
{
    std::ifstream input(path, std::ios::binary);
    return std::string(
        std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>());
}

void write_text(const fs::path& path, const std::string& text)
{
    fs::create_directories(path.parent_path());
    std::ofstream(path, std::ios::binary | std::ios::trunc) << text;
}

struct TemporaryTree {
    fs::path path;
    ~TemporaryTree()
    {
        std::error_code ignored;
        fs::remove_all(path, ignored);
    }
};

class ManualClock final : public permit::PermitClock {
public:
    std::uint64_t unix_seconds() const override { return unix_; }
    std::uint64_t monotonic_milliseconds() const override { return monotonic_; }
    void advance(std::uint64_t seconds)
    {
        unix_ += seconds;
        monotonic_ += seconds * 1000U;
    }

private:
    std::uint64_t unix_ = 10000U;
    std::uint64_t monotonic_ = 50000U;
};

class FixtureEntropy final : public permit::PermitEntropySource {
public:
    facman::core::Result<void> fill(
        unsigned char* output,
        std::size_t size) noexcept override
    {
        for (std::size_t index = 0; index < size; ++index) {
            output[index] = static_cast<unsigned char>((next_++ % 251U) + 1U);
        }
        return facman::core::Result<void>::success();
    }

private:
    std::size_t next_ = 0U;
};

class FakeObserver final : public launch::CandidateEffectObserver {
public:
    facman::core::Result<void> begin(
        const launch::HermeticCandidatePlan& plan) override
    {
        active_ = !fail_begin;
        plan_digest_ = plan.plan_digest;
        return fail_begin
            ? facman::core::Result<void>::failure({
                "permit_wrong_evidence", "synthetic observer refused",
                "$test.observer", facman::core::OutcomeKind::unavailable})
            : facman::core::Result<void>::success();
    }

    bool active() const noexcept override { return active_; }

    launch::CandidateObservationResult finish(
        const launch::HermeticCandidatePlan& plan,
        const facman::platform::ProcessResult& process) override
    {
        launch::CandidateObservationResult result;
        result.plan_digest = plan.plan_digest;
        result.capture_session_digest = digest("capture-session");
        result.raw_artifact_digest = digest("raw-observation-artifact");
        result.active_before_process = active_ && plan.plan_digest == plan_digest_;
        result.capture_complete = result.active_before_process && !force_gap;
        result.gaps.lost_events = force_gap;
        if (process.identity.restart_safe()) {
            result.effects.push_back({
                1U, "filesystem", digest(process.identity.stable_start_identity),
                digest("instance-log"), "instance.logs", "writable"});
            result.effects.push_back({
                2U, "process", digest("process-identity:" + process.identity.stable_start_identity),
                digest("primary-process"), "process.primary", "writable"});
        }
        active_ = false;
        return result;
    }

    bool fail_begin = false;
    bool force_gap = false;

private:
    bool active_ = false;
    std::string plan_digest_;
};

class FakeSupervisor final : public launch::ProcessSupervisor {
public:
    facman::platform::ProcessResult run(
        const facman::platform::ProcessRequest& request) override
    {
        if (before_run) before_run();
        ++calls;
        last_request = request;
        facman::platform::ProcessResult result;
        result.termination = facman::platform::ProcessTermination::exited;
        result.identity = {4242U, "synthetic-process-v1", "synthetic-start:4242:1"};
        result.exit_code = 0;
        result.standard_output = "synthetic output must remain outside lifecycle state";
        result.standard_error = "";
        if (request.started) request.started(result.identity);
        return result;
    }

    int calls = 0;
    std::function<void()> before_run;
    facman::platform::ProcessRequest last_request;
};

const std::vector<std::string> kEvidenceIds = {
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

const std::vector<std::string> kProtectedIds = {
    "effects.external_filesystem", "effects.external_registry", "facman.package",
    "factorio.appdata", "factorio.default_user_data", "factorio.localappdata",
    "factorio.programdata", "factorio.source_material", "host.external_unobserved",
    "installation.selected", "installation.siblings", "instances.other",
    "registry.factorio", "registry.factorio_uninstall", "registry.steam",
    "steam.cloud_cache", "steam.install_roots", "steam.userdata",
};

const std::vector<std::string> kAutomatedControls = {
    "add_wildcard_or_prefix_resource", "attempt_concurrent_launch",
    "cancel_before_process_creation", "cancel_during_execution",
    "change_installation_evidence", "change_launch_intent", "change_modset_state",
    "change_protected_root_identity", "change_isolation_mode", "expire_permit",
    "fail_journal_write", "force_process_crash", "force_timeout",
    "lose_observer_events", "mutate_authenticated_permit_claim",
    "present_stale_run_lock", "replace_effective_config",
    "replace_executable_same_path", "replay_permit_concurrently",
    "replay_permit_sequentially", "restart_issuer_session",
    "restart_provider_session", "select_sibling_instance", "stale_readiness",
    "write_os_global_temporary_directory",
};

permit::ResourceBinding resource(
    std::string kind,
    std::string role,
    std::string id,
    permit::ProviderIdentity provider,
    std::vector<std::string> effects)
{
    return {std::move(kind), std::move(role), std::move(id),
        digest("resource:" + kind + ":" + role + ":" + id),
        std::move(provider), std::move(effects)};
}

launch::CandidatePlanInput plan_input(
    const launch::FrozenHermeticPlayPolicy& policy)
{
    const permit::ProviderIdentity launch_provider {
        launch::kHermeticCandidateProviderId,
        launch::kHermeticCandidateProviderRevision};
    const permit::ProviderIdentity observer_provider {
        launch::kHermeticObservationProviderId,
        launch::kHermeticObservationProviderRevision};
    const permit::ProviderIdentity instance_provider {
        "factorio.instance-model", "factorio.instance-model.v1"};
    const permit::ProviderIdentity install_provider {
        "factorio.installation-model", "factorio.installation-model.v2"};

    launch::CandidatePlanInput input;
    input.policy = policy;
    input.selector = {
        "windows", "x86_64", "2.0.77", "standalone_non_steam",
        "sha256_bound_to_authenticated_wube_source", "ntfs", "fixed_local",
        "facman_owned", "explicit_empty_lock", "none", "none", "none"};
    input.instance_id = "main";
    input.machine_binding_id = "machine:fixture";
    input.principal = {
        "local.fixture", "principal:fixture", "application-session:fixture"};
    for (const std::string& id : kEvidenceIds) {
        input.evidence.push_back({id, digest("evidence:" + id)});
    }
    input.provider_revisions = {
        install_provider, instance_provider, launch_provider, observer_provider};
    input.permit_resources = {
        resource("factorio.instance-spec", "portable-intent", "instance:main:spec",
            instance_provider, {"workspace_read"}),
        resource("factorio.instance-binding", "machine-binding", "instance:main:binding",
            instance_provider, {"workspace_read"}),
        resource("factorio.instance-readiness", "current-evidence", "instance:main:readiness",
            instance_provider, {"workspace_read"}),
        resource("factorio.installation-evidence", "application-image", "install:fixture",
            install_provider, {"workspace_read"}),
        resource("factorio.executable", "process-image", "install:fixture:executable",
            launch_provider, {"process_execute", "workspace_read"}),
        resource("factorio.effective-config", "configuration", "instance:main:config",
            instance_provider, {"workspace_read"}),
        resource("factorio.modset-lock", "mod-content", "instance:main:modset",
            instance_provider, {"workspace_read"}),
        resource("factorio.instance-root", "mutable-data", "instance:main:root",
            instance_provider, {"workspace_read"}),
        resource("factorio.observation", "effect-evidence", "operation:fixture:observer",
            observer_provider, {"workspace_read", "workspace_write"}),
        resource("factorio.operation-state", "operation-record", "operation:fixture:record",
            launch_provider, {"workspace_read", "workspace_write"}),
    };
    for (const std::string id : {
             "instance.config", "instance.locks", "instance.logs", "instance.mods",
             "instance.saves", "instance.state", "operation.record", "operation.temporary"}) {
        input.permit_resources.push_back(resource(
            "factorio.writable-root", id, "writable:" + id,
            launch_provider, {"workspace_read", "workspace_write"}));
    }
    input.writable_resource_ids = {
        "instance.config", "instance.locks", "instance.logs", "instance.mods",
        "instance.saves", "instance.state", "operation.record", "operation.temporary"};
    input.protected_resource_ids = kProtectedIds;
    input.process.executable = "C:/Factorio/2.0.77/bin/x64/factorio.exe";
    input.process.arguments = {
        "--config", "C:/FacMan/instances/main/config/config.ini",
        "--mod-directory", "C:/FacMan/instances/main/mods"};
    input.process.working_directory = "C:/Factorio/2.0.77/bin/x64";
    input.process.environment = {
        {"SystemRoot", "C:/Windows"},
        {"TEMP", "C:/FacMan/temporary/fixture/process"},
        {"TMP", "C:/FacMan/temporary/fixture/process"},
        {"USERPROFILE", "C:/FacMan/instances/main/state/userprofile"},
        {"WINDIR", "C:/Windows"},
    };
    input.process.inherit_environment = false;
    input.process.timeout = std::chrono::minutes(30);
    input.environment_revision = "factorio.menu-minimal.v1";
    return input;
}

launch::ProtectedComparisonResult protected_unchanged()
{
    launch::ProtectedComparisonResult result;
    result.complete = true;
    for (const std::string& id : kProtectedIds) {
        const std::string value = digest("protected:" + id);
        result.resources.push_back({id, value, value, true, false});
    }
    return result;
}

std::vector<launch::CandidateAutomatedCaseResult> automated_passes()
{
    std::vector<launch::CandidateAutomatedCaseResult> result;
    for (const std::string& id : kAutomatedControls) result.push_back({id, true});
    return result;
}

int fail(int code) { return code; }

} // namespace

int main()
{
    const fs::path source_root = FACMAN_TEST_SOURCE_ROOT;
    std::string canonical_policy = read_text(
        source_root / "contracts" / "generated-index" /
        "hermetic_standalone_play_policy.v1.canonical.json");
    auto policy = launch::FrozenHermeticPlayPolicy::verify_canonical_document(canonical_policy);
    if (!policy || !policy.value().verified ||
        policy.value().policy_digest != launch::kHermeticCandidatePolicyDigest) return fail(1);

    std::string mutated_policy = canonical_policy;
    const std::size_t version = mutated_policy.find("2.0.77");
    if (version == std::string::npos) return fail(2);
    mutated_policy.replace(version, 6U, "2.0.78");
    if (launch::FrozenHermeticPlayPolicy::verify_canonical_document(mutated_policy)) return fail(3);

    auto first_plan = launch::build_hermetic_candidate_plan(plan_input(policy.value()));
    auto second_plan = launch::build_hermetic_candidate_plan(plan_input(policy.value()));
    if (!first_plan || !second_plan || first_plan.value().plan_digest != second_plan.value().plan_digest ||
        first_plan.value().evidence.size() != 31U ||
        first_plan.value().writable_resource_ids.size() >= 13U) return fail(4);
    auto wrong_selector = plan_input(policy.value());
    wrong_selector.selector.factorio_version = "2.1.11";
    if (launch::build_hermetic_candidate_plan(std::move(wrong_selector))) return fail(5);
    auto missing_evidence = plan_input(policy.value());
    missing_evidence.evidence.pop_back();
    if (launch::build_hermetic_candidate_plan(std::move(missing_evidence))) return fail(6);
    auto broad_scope = plan_input(policy.value());
    broad_scope.writable_resource_ids.push_back("workspace.audit");
    broad_scope.writable_resource_ids.push_back("instance.cache");
    broad_scope.writable_resource_ids.push_back("instance.crash");
    broad_scope.writable_resource_ids.push_back("instance.scenarios");
    broad_scope.writable_resource_ids.push_back("instance.script_output");
    if (launch::build_hermetic_candidate_plan(std::move(broad_scope))) return fail(7);
    auto wrong_intent = plan_input(policy.value());
    wrong_intent.process.arguments = {"--load-game", "save.zip", "--config", "config.ini"};
    if (launch::build_hermetic_candidate_plan(std::move(wrong_intent))) return fail(8);
    auto escaped_temporary = plan_input(policy.value());
    for (auto& value : escaped_temporary.process.environment) {
        if (value.name == "TEMP" || value.name == "TMP") value.value = "C:/Windows/Temp";
    }
    if (launch::build_hermetic_candidate_plan(std::move(escaped_temporary))) return fail(81);
    auto write_escalation = plan_input(policy.value());
    write_escalation.permit_resources.front().permitted_effects.push_back("workspace_write");
    if (launch::build_hermetic_candidate_plan(std::move(write_escalation))) return fail(82);

    FixtureEntropy entropy;
    auto authenticator = permit::ProcessSessionAuthenticator::create(entropy);
    if (!authenticator) return fail(9);
    ManualClock clock;
    permit::PermitLedger ledger;
    launch::CandidatePermitIssuer issuer;
    auto mutated_plan = first_plan.value();
    mutated_plan.process.arguments[1] = "C:/FacMan/instances/other/config/config.ini";
    permit::PermitLedger mutated_ledger;
    if (issuer.issue(
            mutated_plan, *authenticator.value(), entropy, mutated_ledger, clock)) return fail(83);
    auto envelope = issuer.issue(
        first_plan.value(), *authenticator.value(), entropy, ledger, clock);
    if (!envelope || launch::CandidatePermitIssuer::public_issuance_available()) return fail(10);

    FakeObserver observer;
    FakeSupervisor supervisor;
    launch::HermeticCandidateLaunchProvider provider;
    const auto current = [&]() {
        return facman::core::Result<permit::PermitValidationContext>::success(
            launch::candidate_permit_context(first_plan.value()));
    };
    observer.fail_begin = true;
    auto observer_start_refused = provider.consume_and_execute(
        envelope.value(), first_plan.value(), current, *authenticator.value(),
        ledger, clock, observer, supervisor);
    if (observer_start_refused ||
        observer_start_refused.error().code != "permit_wrong_evidence" ||
        observer_start_refused.error().message != "synthetic observer refused" ||
        observer_start_refused.error().path != "$test.observer" ||
        supervisor.calls != 0) return fail(101);
    observer.fail_begin = false;
    auto executed = provider.consume_and_execute(
        envelope.value(), first_plan.value(), current, *authenticator.value(),
        ledger, clock, observer, supervisor);
    if (!executed || !executed.value().permit.accepted ||
        !executed.value().permit.consumed || supervisor.calls != 1 ||
        !executed.value().process.identity.restart_safe() ||
        launch::HermeticCandidateLaunchProvider::public_execution_available()) return fail(11);

    const fs::path bound_observation_path =
        fs::path(FACMAN_TEST_TEMP_ROOT) / "bound-observation.json";
    permit::PermitLedger bound_observation_ledger;
    auto bound_observation_envelope = issuer.issue(
        first_plan.value(), *authenticator.value(), entropy, bound_observation_ledger, clock);
    if (!bound_observation_envelope) return fail(111);
    const std::string capture_session = digest("bound-capture-session");
    int observation_starts = 0;
    int observation_finishes = 0;
    launch::BoundArtifactCandidateEffectObserver bound_observer(
        [&](const launch::HermeticCandidatePlan&) {
            ++observation_starts;
            return facman::core::Result<std::string>::success(capture_session);
        },
        [&](const launch::HermeticCandidatePlan& plan,
            const facman::platform::ProcessResult& process) {
            ++observation_finishes;
            launch::CandidateObservationResult result;
            result.plan_digest = plan.plan_digest;
            result.capture_session_digest = capture_session;
            result.raw_artifact_digest = digest("bound-raw-artifact");
            result.active_before_process = true;
            result.capture_complete = true;
            result.effects.push_back({
                1U, "process",
                digest("process-identity:" + process.identity.stable_start_identity),
                digest("primary-process"), "process.primary", "writable"});
            write_text(
                bound_observation_path,
                launch::candidate_observation_artifact_json(result));
            return facman::core::Result<fs::path>::success(bound_observation_path);
        });
    bool observer_active_at_process_boundary = false;
    supervisor.before_run = [&]() {
        observer_active_at_process_boundary = bound_observer.active();
    };
    auto bound_execution = provider.consume_and_execute(
        bound_observation_envelope.value(), first_plan.value(), current,
        *authenticator.value(), bound_observation_ledger, clock,
        bound_observer, supervisor);
    supervisor.before_run = {};
    if (!bound_execution || !bound_execution.value().permit.consumed ||
        !bound_execution.value().observation.capture_complete ||
        bound_execution.value().observation.gaps.any() ||
        observation_starts != 1 || observation_finishes != 1 ||
        !observer_active_at_process_boundary) return fail(112);

    auto replay = provider.consume_and_execute(
        envelope.value(), first_plan.value(), current, *authenticator.value(),
        ledger, clock, observer, supervisor);
    if (!replay || replay.value().permit.accepted ||
        replay.value().permit.code != "permit_replayed" || supervisor.calls != 2) return fail(12);

    auto packet = launch::build_candidate_evidence_packet(
        first_plan.value(), executed.value(), protected_unchanged(), automated_passes());
    if (!packet || packet.value().technical_disposition !=
            launch::CandidateTechnicalDisposition::eligible_for_human_verdict ||
        packet.value().human_verdict != "unset" || packet.value().grants_authority ||
        packet.value().product_route_available || packet.value().packet_digest.size() != 64U ||
        packet.value().canonical_json().find("authenticator_value") != std::string::npos ||
        packet.value().canonical_json().find("synthetic output") != std::string::npos) return fail(13);
    auto parsed_packet = facman::core::json::parse(packet.value().canonical_json());
    if (!parsed_packet || !parsed_packet.value().is_object()) return fail(14);
    const auto* observation_value = parsed_packet.value().find("observation");
    if (observation_value == nullptr) return fail(145);
    const std::string observation_artifact = observation_value->serialize();
    auto decoded_observation = launch::decode_candidate_observation_artifact(
        observation_artifact, first_plan.value(), executed.value().process);
    if (!decoded_observation || !decoded_observation.value().capture_complete ||
        decoded_observation.value().gaps.any()) return fail(146);
    TemporaryTree artifacts {fs::path(FACMAN_TEST_TEMP_ROOT) / "artifact-fixture"};
    std::error_code artifact_error;
    fs::remove_all(artifacts.path, artifact_error);
    auto persisted = launch::persist_candidate_artifacts(
        artifacts.path, "operation-fixture", packet.value(), executed.value().process);
    if (!persisted) return fail(140);
    if (persisted.value().lifecycle_packet_path.parent_path().filename() != "lifecycle" ||
        persisted.value().standard_output_path.parent_path().filename() != "output") return fail(142);
    if (read_text(persisted.value().lifecycle_packet_path).find("synthetic output") !=
        std::string::npos) return fail(143);
    if (read_text(persisted.value().standard_output_path) !=
        executed.value().process.standard_output) return fail(144);
    auto stable_lifecycle = launch::read_candidate_lifecycle_packet_no_follow(
        persisted.value().lifecycle_packet_path, packet.value().packet_digest);
    if (!stable_lifecycle) {
        std::cerr << stable_lifecycle.error().code << ": "
                  << stable_lifecycle.error().message << " ("
                  << stable_lifecycle.error().detail << ") path="
                  << stable_lifecycle.error().path << "\n";
        return fail(141);
    }
    if (
        stable_lifecycle.value().find(packet.value().packet_digest) == std::string::npos ||
        launch::persist_candidate_artifacts(
            artifacts.path, "operation-fixture", packet.value(), executed.value().process)) return fail(141);
    std::string tampered_lifecycle = stable_lifecycle.value();
    const std::size_t unset_position = tampered_lifecycle.find("\"human_verdict\":\"unset\"");
    if (unset_position == std::string::npos) return fail(148);
    tampered_lifecycle.replace(
        unset_position, std::string("\"human_verdict\":\"unset\"").size(),
        "\"human_verdict\":\"Pass\"");
    write_text(persisted.value().lifecycle_packet_path, tampered_lifecycle);
    if (launch::read_candidate_lifecycle_packet_no_follow(
            persisted.value().lifecycle_packet_path, packet.value().packet_digest)) return fail(149);
    const fs::path observation_path = artifacts.path / "observation.json";
    write_text(observation_path, observation_artifact);
    auto stable_observation = launch::read_candidate_observation_artifact_no_follow(
        observation_path, first_plan.value(), executed.value().process);
    if (!stable_observation ||
        stable_observation.value().raw_artifact_digest != digest("raw-observation-artifact")) return fail(147);

    launch::CandidateExecutionRecord gap_execution = executed.value();
    gap_execution.observation.gaps.lost_events = true;
    gap_execution.observation.capture_complete = false;
    gap_execution.observation.output_digest.clear();
    auto inconclusive = launch::build_candidate_evidence_packet(
        first_plan.value(), gap_execution, protected_unchanged(), automated_passes());
    if (!inconclusive || inconclusive.value().technical_disposition !=
            launch::CandidateTechnicalDisposition::inconclusive) return fail(15);
    auto changed_comparison = protected_unchanged();
    changed_comparison.resources.front().changed = true;
    changed_comparison.resources.front().after_digest = digest("changed");
    auto failed = launch::build_candidate_evidence_packet(
        first_plan.value(), executed.value(), std::move(changed_comparison), automated_passes());
    if (!failed || failed.value().technical_disposition !=
            launch::CandidateTechnicalDisposition::fail_evidence) return fail(16);
    auto missing_case = automated_passes();
    missing_case.pop_back();
    if (launch::build_candidate_evidence_packet(
            first_plan.value(), executed.value(), protected_unchanged(), std::move(missing_case))) return fail(17);

    permit::PermitLedger drift_ledger;
    auto drift_envelope = issuer.issue(
        first_plan.value(), *authenticator.value(), entropy, drift_ledger, clock);
    if (!drift_envelope) return fail(18);
    auto stale = [&]() {
        auto context = launch::candidate_permit_context(first_plan.value());
        context.evidence_digest = digest("stale evidence");
        return facman::core::Result<permit::PermitValidationContext>::success(std::move(context));
    };
    auto refused = provider.consume_and_execute(
        drift_envelope.value(), first_plan.value(), stale, *authenticator.value(),
        drift_ledger, clock, observer, supervisor);
    if (!refused || refused.value().permit.accepted ||
        refused.value().permit.code != "permit_wrong_evidence" || supervisor.calls != 2) return fail(19);

    permit::PermitLedger missing_context_ledger;
    auto missing_context_envelope = issuer.issue(
        first_plan.value(), *authenticator.value(), entropy, missing_context_ledger, clock);
    if (!missing_context_envelope) return fail(191);
    auto missing_context = provider.consume_and_execute(
        missing_context_envelope.value(), first_plan.value(), {}, *authenticator.value(),
        missing_context_ledger, clock, observer, supervisor);
    if (missing_context || observer.active() || supervisor.calls != 2) return fail(192);

    launch::PlatformPermitEntropySource platform_entropy;
    std::array<unsigned char, 32> random {};
    if (!platform_entropy.fill(random.data(), random.size()) ||
        std::all_of(random.begin(), random.end(), [](unsigned char value) { return value == 0; })) return fail(20);

    TemporaryTree manifests {fs::path(FACMAN_TEST_TEMP_ROOT) / "manifest-fixture"};
    std::error_code ignored;
    fs::remove_all(manifests.path, ignored);
    write_text(manifests.path / "protected" / "one.txt", "one");
    write_text(manifests.path / "protected" / "nested" / "two.txt", "two");
    auto before = launch::capture_candidate_stable_manifest(
        "installation.selected", manifests.path / "protected", false);
    auto unchanged_after = launch::capture_candidate_stable_manifest(
        "installation.selected", manifests.path / "protected", false);
    if (!before || !unchanged_after || !before.value().complete ||
        before.value().manifest_digest != unchanged_after.value().manifest_digest) return fail(21);
    auto unchanged = launch::compare_candidate_stable_manifests(
        before.value(), unchanged_after.value());
    if (!unchanged || !unchanged.value().complete || unchanged.value().changed) return fail(22);
    fs::remove(manifests.path / "protected" / "one.txt", ignored);
    write_text(manifests.path / "protected" / "one.txt", "replacement");
    auto changed_after = launch::capture_candidate_stable_manifest(
        "installation.selected", manifests.path / "protected", false);
    auto changed = launch::compare_candidate_stable_manifests(
        before.value(), changed_after.value());
    if (!changed_after || !changed || !changed.value().complete || !changed.value().changed) return fail(23);
    launch::CandidateManifestLimits tiny;
    tiny.maximum_entries = 1U;
    auto incomplete_manifest = launch::capture_candidate_stable_manifest(
        "installation.selected", manifests.path / "protected", false, tiny);
    if (!incomplete_manifest || incomplete_manifest.value().complete ||
        incomplete_manifest.value().gap_codes.empty()) return fail(24);
    auto absent_before = launch::capture_candidate_stable_manifest(
        "factorio.default_user_data", manifests.path / "absent", true);
    fs::create_directories(manifests.path / "absent");
    auto absent_after = launch::capture_candidate_stable_manifest(
        "factorio.default_user_data", manifests.path / "absent", true);
    auto appeared = launch::compare_candidate_stable_manifests(
        absent_before.value(), absent_after.value());
    if (!absent_before || !absent_after || !appeared || !appeared.value().changed) return fail(25);

    return 0;
}
