// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_operation_permit.h"
#include "fl_sha256.h"
#include "facman/build_identity.hpp"
#include "flb_factorio_candidate_projection.h"
#include "flb_factorio_discovery.h"
#include "flb_factorio_hermetic_candidate.h"
#include "flb_factorio_launch_permit.h"
#include "flb_factorio_launch_plan.h"
#include "flb_factorio_permit_projection.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <iterator>
#include <map>
#include <optional>
#include <string>
#include <vector>

namespace {

namespace fs = std::filesystem;
namespace permit = facman::core::permit;
namespace factorio_instance = facman::factorio::instance;
namespace factorio_launch = facman::factorio::launch;

constexpr const char* kDigestA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
constexpr const char* kDigestB = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";

#ifdef _WIN32
std::string digest(const std::string& value)
{
    return facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(value.data()), value.size());
}

const std::string* evidence_digest(
    const factorio_launch::HermeticCandidatePlan& plan,
    const std::string& requirement_id)
{
    const auto found = std::find_if(
        plan.evidence.begin(), plan.evidence.end(),
        [&](const auto& value) {
            return value.requirement_id == requirement_id;
        });
    return found == plan.evidence.end()
        ? nullptr
        : &found->identity_digest;
}
#endif

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
    std::uint64_t unix_seconds() const override { return 2000U; }
    std::uint64_t monotonic_milliseconds() const override { return 50000U; }
};

class FixtureEntropy final : public permit::PermitEntropySource {
public:
    facman::core::Result<void> fill(unsigned char* output, std::size_t size) noexcept override
    {
        for (std::size_t index = 0; index < size; ++index) {
            output[index] = static_cast<unsigned char>((next_++ % 251U) + 1U);
        }
        return facman::core::Result<void>::success();
    }

private:
    std::size_t next_ = 0U;
};

void write_text(const fs::path& path, const std::string& text)
{
    fs::create_directories(path.parent_path());
    std::ofstream(path, std::ios::binary | std::ios::trunc) << text;
}

#ifdef _WIN32
std::string read_text(const fs::path& path)
{
    std::ifstream input(path, std::ios::binary);
    return std::string(
        std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>());
}
#endif

fs::path executable_path(const fs::path& install)
{
#ifdef _WIN32
    return install / "bin" / "x64" / "factorio.exe";
#else
    return install / "bin" / "x64" / "factorio";
#endif
}

void make_fixture(const fs::path& workspace, const fs::path& install)
{
    write_text(install / "data" / "base" / "info.json", "{\"version\":\"2.0.77\"}");
    write_text(executable_path(install), "fixture-not-executable");
    write_text(install / "config-path.cfg",
        "config-path=__PATH__executable__/../../config\n"
        "use-system-read-write-data-directories=false\n");
    auto record = facman::factorio::discovery::inspect_install(install, "fixture");
    record.provider_id = "native-smoke";
    record.ownership = "portable";
    write_text(workspace / "installs" / "refs" / "fixture.json",
        facman::factorio::discovery::install_ref_json(record));

    const fs::path instance_root = workspace / "instances" / "main";
    fs::create_directories(instance_root / "mods");
    fs::create_directories(instance_root / "saves");
    write_text(instance_root / "instance.v1.json",
        "{\"schema\":\"factorio.instance.v1\",\"instance_id\":\"main\","
        "\"display_name\":\"Main\",\"install_ref\":\"fixture\","
        "\"factorio_version\":\"2.0.77\",\"profile\":\"gui\",\"template\":\"vanilla\"}");
    facman::factorio::launch::InstanceLaunchRef instance_ref;
    instance_ref.instance_id = "main";
    instance_ref.profile_id = "gui";
    instance_ref.local_data_root = instance_root;
    instance_ref.launch_mode = "gui";
    facman::factorio::launch::InstallLaunchRef install_ref;
    install_ref.root = install;
    install_ref.executable = executable_path(install);
    install_ref.ownership = "portable";
    install_ref.distribution_origin = "standalone";
    install_ref.platform_integration = "none";
    install_ref.strict_isolation_eligibility = "eligible";
    write_text(instance_root / "config" / "config.ini",
        facman::factorio::launch::effective_config_ini(instance_ref, install_ref));
}

std::map<std::string, std::string> snapshot(const fs::path& root)
{
    std::map<std::string, std::string> output;
    std::error_code error;
    for (fs::recursive_directory_iterator iterator(root, fs::directory_options::none, error), end;
         iterator != end && !error; iterator.increment(error)) {
        if (!iterator->is_regular_file(error) || error) continue;
        std::ifstream input(iterator->path(), std::ios::binary);
        output[iterator->path().lexically_relative(root).generic_string()] =
            std::string((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
    }
    return output;
}

facman::core::Result<permit::PermitValidationContext> current_context(
    const fs::path& workspace)
{
    auto projection = factorio_instance::project_menu_permit_resources(workspace, "main");
    if (!projection) return facman::core::Result<permit::PermitValidationContext>::failure(projection.error());
    permit::PermitValidationContext context;
    context.operation.kind = factorio_launch::DormantLaunchPermitVerifier::kFoundationOperation;
    context.operation.launch_intent = "menu";
    context.operation.isolation_mode = "hermetic";
    context.plan = {"foundation-factorio-permit-plan-v1", kDigestA};
    context.consumer = {
        factorio_launch::DormantLaunchPermitVerifier::kProviderId,
        factorio_launch::DormantLaunchPermitVerifier::kProviderRevision};
    context.resources = projection.value().resources;
    context.effects = {"workspace_read"};
    context.required_capabilities = {"foundation.permit.verify"};
    context.machine_binding_id = "machine:foundation-fixture";
    context.principal = {"local.fixture", "principal:fixture", "application-session:fixture"};
    context.evidence_digest = projection.value().evidence_digest;
    context.policy = {"foundation-factorio-permit-policy.v1", kDigestB};
    context.provider_revisions = projection.value().provider_revisions;
    return facman::core::Result<permit::PermitValidationContext>::success(std::move(context));
}

permit::OperationPermitClaims claims_from(
    const permit::PermitValidationContext& context,
    const permit::PermitAuthenticator& authenticator)
{
    permit::OperationPermitClaims claims;
    claims.permit_id = "permit-55555555555555555555555555555555";
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
    claims.issued_at_unix_seconds = 2000U;
    claims.not_before_unix_seconds = 2000U;
    claims.expires_at_unix_seconds = 2060U;
    claims.nonce = "nonce-66666666666666666666666666666666";
    return claims;
}

int fail(int code)
{
    return code;
}

} // namespace

int main()
{
    TemporaryTree fixture {fs::path(FACMAN_TEST_TEMP_ROOT) / "fixture"};
    std::error_code cleanup_error;
    fs::remove_all(fixture.path, cleanup_error);
    const fs::path workspace = fixture.path / "workspace";
    const fs::path install = fixture.path / "install";
    make_fixture(workspace, install);
    const auto before = snapshot(fixture.path);

    auto first_projection = factorio_instance::project_menu_permit_resources(workspace, "main");
    auto second_projection = factorio_instance::project_menu_permit_resources(workspace, "main");
    if (!first_projection || !second_projection ||
        first_projection.value().evidence_digest != second_projection.value().evidence_digest ||
        first_projection.value().resources.size() != 9U ||
        first_projection.value().launch_authority_complete ||
        first_projection.value().missing_play_resources.size() != 5U) return fail(1);
    for (const auto& resource : first_projection.value().resources) {
        if (resource.logical_id.find(fixture.path.string()) != std::string::npos ||
            resource.permitted_effects != std::vector<std::string>{"workspace_read"}) return fail(2);
    }

#ifdef _WIN32
    const std::string canonical_policy = read_text(
        fs::path(FACMAN_TEST_SOURCE_ROOT) / "contracts" / "generated-index" /
        "hermetic_standalone_play_policy.v1.canonical.json");
    auto frozen_policy = factorio_launch::FrozenHermeticPlayPolicy::verify_canonical_document(
        canonical_policy);
    if (!frozen_policy) return fail(16);
    factorio_instance::HermeticCandidateProjectionRequest candidate_request;
    candidate_request.workspace = workspace;
    candidate_request.instance_id = "main";
    candidate_request.operation_id = "candidate-fixture";
    candidate_request.installation_root = install;
    candidate_request.executable = executable_path(install);
    candidate_request.expected_executable_sha256 = digest("fixture-not-executable");
    candidate_request.authenticated_source_artifact_digest = digest("source-artifact");
    candidate_request.source_authentication_evidence_digest = digest("source-authentication");
    candidate_request.facman_source_revision_digest = digest("facman-source-revision");
    candidate_request.facman_build_identity_digest = digest("facman-build-identity");
    candidate_request.protected_baseline_digest = digest("protected-baseline");
    candidate_request.writable_baseline_digest = digest("writable-baseline");
    candidate_request.machine_binding_id = "machine:fixture";
    candidate_request.principal = {
        "local.fixture", "principal:fixture", "application-session:fixture"};
    candidate_request.windows_system_root = "C:/Windows";
    candidate_request.policy = frozen_policy.value();
    auto candidate_plan = factorio_instance::project_hermetic_candidate_plan(candidate_request);
    auto repeated_candidate_plan = factorio_instance::project_hermetic_candidate_plan(candidate_request);
    auto reobserved_candidate = factorio_instance::reobserve_hermetic_candidate_context(
        candidate_request);
    if (!candidate_plan) {
        std::cerr << candidate_plan.error().code << ": "
                  << candidate_plan.error().message << " ("
                  << candidate_plan.error().path << ")\n";
        return fail(17);
    }
    if (!repeated_candidate_plan) {
        std::cerr << repeated_candidate_plan.error().code << ": "
                  << repeated_candidate_plan.error().message << " ("
                  << repeated_candidate_plan.error().path << ")\n";
        return fail(17);
    }
    if (!reobserved_candidate) {
        std::cerr << reobserved_candidate.error().code << ": "
                  << reobserved_candidate.error().message << " ("
                  << reobserved_candidate.error().path << ")\n";
        return fail(17);
    }
    if (
        candidate_plan.value().plan_digest != repeated_candidate_plan.value().plan_digest ||
        reobserved_candidate.value().plan.plan_digest != candidate_plan.value().plan_digest ||
        candidate_plan.value().permit_resources.size() != 24U ||
        candidate_plan.value().writable_resource_ids.size() != 8U ||
        factorio_launch::hermetic_candidate_plan_json(candidate_plan.value()).find(
            fixture.path.generic_string()) != std::string::npos) return fail(17);
    const std::string* hermetic_launcher_revision = evidence_digest(
        candidate_plan.value(), "universal_launcher.revision");
    const std::string* hermetic_setup_revision = evidence_digest(
        candidate_plan.value(), "universal_setup.revision");
    if (hermetic_launcher_revision == nullptr ||
        hermetic_setup_revision == nullptr ||
        *hermetic_launcher_revision != digest(
            facman::build_identity::universal_launcher_revision) ||
        *hermetic_setup_revision != digest(
            facman::build_identity::universal_setup_revision)) {
        return fail(170);
    }
    const auto temp_environment = std::find_if(
        candidate_plan.value().process.environment.begin(),
        candidate_plan.value().process.environment.end(),
        [](const auto& value) { return value.name == "TEMP"; });
    const auto profile_environment = std::find_if(
        candidate_plan.value().process.environment.begin(),
        candidate_plan.value().process.environment.end(),
        [](const auto& value) { return value.name == "USERPROFILE"; });
    if (temp_environment == candidate_plan.value().process.environment.end() ||
        profile_environment == candidate_plan.value().process.environment.end() ||
        fs::path(temp_environment->value) !=
            workspace / "temporary" / "candidate-fixture" / "process" ||
        fs::path(profile_environment->value) !=
            workspace / "instances" / "main" / "state" / "userprofile") return fail(171);
    const std::string original_config = read_text(
        workspace / "instances" / "main" / "config" / "config.ini");
    write_text(workspace / "instances" / "main" / "config" / "config.ini", original_config + "\n# drift\n");
    auto config_drift_plan = factorio_instance::project_hermetic_candidate_plan(candidate_request);
    if (!config_drift_plan ||
        config_drift_plan.value().plan_digest == candidate_plan.value().plan_digest) return fail(18);
    write_text(workspace / "instances" / "main" / "config" / "config.ini", original_config);
    write_text(executable_path(install), "replacement-executable");
    if (factorio_instance::project_hermetic_candidate_plan(candidate_request)) return fail(19);
    write_text(executable_path(install), "fixture-not-executable");

    const std::string isolated_policy_document = read_text(
        fs::path(FACMAN_TEST_SOURCE_ROOT) / "contracts" / "generated-index" /
        "windows_instance_isolated_play_policy.v1.canonical.json");
    auto isolated_policy =
        factorio_launch::FrozenHermeticPlayPolicy::
            verify_instance_isolated_canonical_document(
                isolated_policy_document);
    if (!isolated_policy ||
        isolated_policy.value().policy_digest !=
            factorio_launch::kInstanceIsolatedCandidatePolicyDigest) {
        return fail(190);
    }
    factorio_instance::InstanceIsolatedCandidateProjectionRequest
        isolated_request = candidate_request;
    isolated_request.operation_id = "instance-isolated-fixture";
    isolated_request.policy = isolated_policy.value();
    auto isolated_plan =
        factorio_instance::project_instance_isolated_candidate_plan(
            isolated_request);
    auto isolated_context =
        factorio_instance::reobserve_instance_isolated_candidate_context(
            isolated_request);
    if (!isolated_plan || !isolated_context ||
        isolated_plan.value().schema !=
            "factorio.instance_isolated_play_candidate_plan.v1" ||
        isolated_plan.value().isolation_mode != "instance_isolated" ||
        isolated_plan.value().evidence.size() != 35U ||
        isolated_plan.value().writable_resource_ids.size() != 7U ||
        isolated_plan.value().protected_resource_ids.size() != 12U ||
        isolated_plan.value().permit_resources.size() != 23U ||
        isolated_context.value().operation.isolation_mode !=
            std::optional<std::string>("instance_isolated") ||
        isolated_context.value().required_capabilities !=
            std::vector<std::string>{
                "launch.execute.instance_isolated", "process.execute"} ||
        !isolated_plan.value().instance_root_authority ||
        !isolated_plan.value().instance_root_authority->open() ||
        !isolated_plan.value().instance_root_authority->revalidate().ok() ||
        factorio_launch::hermetic_candidate_plan_json(
            isolated_plan.value()).find(fixture.path.generic_string()) !=
            std::string::npos) {
        return fail(191);
    }
    const std::string* isolated_launcher_revision = evidence_digest(
        isolated_plan.value(), "universal_launcher_exact_revision");
    const std::string* isolated_setup_revision = evidence_digest(
        isolated_plan.value(), "universal_setup_exact_revision");
    if (isolated_launcher_revision == nullptr ||
        isolated_setup_revision == nullptr ||
        *isolated_launcher_revision != digest(
            facman::build_identity::universal_launcher_revision) ||
        *isolated_setup_revision != digest(
            facman::build_identity::universal_setup_revision)) {
        return fail(194);
    }
    const auto sibling_escape =
        isolated_plan.value().instance_root_authority->validate_descendant(
            workspace / "instances" / "sibling");
    if (sibling_escape.ok()) return fail(192);
    std::error_code replacement_error;
    fs::rename(
        workspace / "instances" / "main",
        workspace / "instances" / "replacement",
        replacement_error);
    if (!replacement_error ||
        !isolated_plan.value().instance_root_authority->revalidate().ok()) {
        return fail(193);
    }
#endif

    FixtureEntropy process_entropy;
    auto authenticator = permit::ProcessSessionAuthenticator::create(process_entropy);
    auto expected = current_context(workspace);
    if (!authenticator || !expected) return fail(3);
    auto sealed = permit::seal_claims(claims_from(expected.value(), *authenticator.value()),
        *authenticator.value());
    if (!sealed) return fail(4);
    permit::PermitLedger ledger;
    ManualClock clock;
    if (!ledger.register_issued(sealed.value(), 50000U, 110000U)) return fail(5);

    factorio_launch::DormantLaunchPermitVerifier verifier;
    std::atomic<int> observations{0};
    auto observer = [&]() {
        observations.fetch_add(1, std::memory_order_relaxed);
        return current_context(workspace);
    };
    auto admitted = verifier.validate(
        sealed.value(), observer, *authenticator.value(), ledger, clock);
    if (!admitted.accepted || admitted.consumed || observations.load() != 1 ||
        factorio_launch::DormantLaunchPermitVerifier::execution_available()) return fail(6);
    auto consumed = verifier.consume_foundation_proof(
        sealed.value(), observer, *authenticator.value(), ledger, clock);
    if (!consumed.accepted || !consumed.consumed || observations.load() != 2 ||
        snapshot(fixture.path) != before) return fail(7);
    auto replayed = verifier.consume_foundation_proof(
        sealed.value(), observer, *authenticator.value(), ledger, clock);
    if (replayed.accepted || replayed.code != "permit_replayed" ||
        replayed.consumption_json().find("authenticator_value") != std::string::npos) return fail(8);

    auto wrong_operation_observer = [expected]() mutable {
        expected.value().operation.kind = "instance.play";
        return expected;
    };
    auto wrong_operation = verifier.validate(
        sealed.value(), wrong_operation_observer, *authenticator.value(), ledger, clock);
    if (wrong_operation.accepted || wrong_operation.code != "permit_wrong_operation") return fail(9);

    auto wrong_intent_observer = [expected]() mutable {
        expected.value().operation.launch_intent = "load_save";
        return expected;
    };
    auto wrong_intent = verifier.validate(
        sealed.value(), wrong_intent_observer, *authenticator.value(), ledger, clock);
    if (wrong_intent.accepted || wrong_intent.code != "permit_intent_mismatch") return fail(10);
    auto wrong_isolation_observer = [expected]() mutable {
        expected.value().operation.isolation_mode = "instance_isolated";
        return expected;
    };
    auto wrong_isolation = verifier.validate(
        sealed.value(), wrong_isolation_observer, *authenticator.value(), ledger, clock);
    if (wrong_isolation.accepted || wrong_isolation.code != "permit_isolation_mismatch") return fail(11);
    auto effect_escalation_observer = [expected]() mutable {
        expected.value().effects = {"process_execute", "workspace_read"};
        return expected;
    };
    auto effect_escalation = verifier.validate(
        sealed.value(), effect_escalation_observer, *authenticator.value(), ledger, clock);
    if (effect_escalation.accepted || effect_escalation.code != "permit_effect_scope_mismatch") return fail(12);

    auto fresh_context = current_context(workspace);
    if (!fresh_context) return fail(13);
    permit::OperationPermitClaims drift_claims = claims_from(fresh_context.value(), *authenticator.value());
    drift_claims.permit_id = "permit-77777777777777777777777777777777";
    drift_claims.nonce = "nonce-88888888888888888888888888888888";
    auto drift_envelope = permit::seal_claims(drift_claims, *authenticator.value());
    permit::PermitLedger drift_ledger;
    if (!drift_envelope || !drift_ledger.register_issued(drift_envelope.value(), 50000U, 110000U)) return fail(14);
    write_text(workspace / "instances" / "main" / "config" / "config.ini",
        "[path]\nread-data=C:/changed\nwrite-data=C:/changed\n");
    auto drifted = verifier.consume_foundation_proof(
        drift_envelope.value(), [&]() { return current_context(workspace); },
        *authenticator.value(), drift_ledger, clock);
    if (drifted.accepted || drifted.code != "permit_wrong_evidence") return fail(15);

    return 0;
}
