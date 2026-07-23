// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_operation_permit.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "flb_factorio_candidate_projection.h"
#include "flb_factorio_hermetic_candidate.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <filesystem>
#include <iostream>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

namespace {

namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace permit = facman::core::permit;
namespace instance = facman::factorio::instance;
namespace launch = facman::factorio::launch;
namespace platform = facman::platform;

constexpr const char* kSessionSchema = "factorio.gate4c_verdict_session.v1";
constexpr const char* kComparisonSchema =
    "factorio.gate4c_baseline_comparison.v1";
constexpr const char* kWorkUnit =
    "FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-01";

std::string digest(const std::string& value)
{
    return facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(value.data()), value.size());
}

std::string stable_read(const fs::path& path, std::size_t maximum_bytes)
{
    platform::StableInputFile input;
    const auto opened = input.open_no_follow(path);
    if (!opened.ok() || input.size() > maximum_bytes) {
        throw std::runtime_error("stable input could not be opened within bounds: " +
            platform::path_to_utf8(path));
    }
    std::string output(static_cast<std::size_t>(input.size()), '\0');
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t count = input.read_at(
            offset, output.data() + static_cast<std::size_t>(offset),
            output.size() - static_cast<std::size_t>(offset));
        if (count == 0U) {
            throw std::runtime_error("stable input read was incomplete");
        }
        offset += count;
    }
    const auto current = input.revalidate();
    if (!current.ok()) {
        throw std::runtime_error("stable input changed during read");
    }
    return output;
}

const json::Value& require_member(const json::Value& object, const char* key)
{
    const json::Value* value = object.find(key);
    if (value == nullptr) {
        throw std::runtime_error(std::string("missing session member: ") + key);
    }
    return *value;
}

std::string string_member(const json::Value& object, const char* key)
{
    auto value = require_member(object, key).string_value();
    if (!value) {
        throw std::runtime_error(std::string("session member is not a string: ") + key);
    }
    return value.take_value();
}

#ifdef _WIN32

std::string stable_sha256(const fs::path& path, std::size_t maximum_bytes)
{
    return digest(stable_read(path, maximum_bytes));
}

bool bool_member(const json::Value& object, const char* key)
{
    auto value = require_member(object, key).bool_value();
    if (!value) {
        throw std::runtime_error(std::string("session member is not a bool: ") + key);
    }
    return value.value();
}

std::string canonical_without(
    const json::Value& object,
    const std::string& excluded)
{
    json::ObjectBuilder builder;
    for (const std::string& key : object.object_keys()) {
        if (key != excluded) builder.add_value(key, require_member(object, key.c_str()));
    }
    return builder.serialize();
}

fs::path normalized_absolute(const fs::path& value)
{
    std::error_code error;
    fs::path result = fs::absolute(value, error);
    if (error) throw std::runtime_error("path could not be made absolute");
    return result.lexically_normal();
}

bool safe_identifier(const std::string& value)
{
    return !value.empty() &&
        std::all_of(value.begin(), value.end(), [](unsigned char byte) {
            return (byte >= 'a' && byte <= 'z') ||
                (byte >= '0' && byte <= '9') || byte == '-';
        });
}

bool path_beneath(const fs::path& root, const fs::path& candidate)
{
    const fs::path relative =
        normalized_absolute(candidate).lexically_relative(normalized_absolute(root));
    if (relative.empty() || relative.is_absolute()) return false;
    const std::string text = relative.generic_string();
    return text != ".." && text.rfind("../", 0U) != 0U;
}

void write_new(const fs::path& path, const std::string& text)
{
    std::string detail;
    if (!facman::base::write_text_new_atomic(path, text, detail)) {
        throw std::runtime_error("could not exclusively write evidence: " + detail);
    }
}

facman::core::Error harness_error(
    std::string code,
    std::string message,
    std::string path,
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::unavailable)
{
    return {std::move(code), std::move(message), std::move(path), kind};
}

struct Session {
    fs::path source_root;
    fs::path session_path;
    fs::path preflight_path;
    std::string preflight_digest;
    std::string preflight_file_sha256;
    fs::path task_root;
    fs::path workspace;
    std::string instance_id;
    std::string operation_id;
    fs::path operation_root;
    fs::path installation_root;
    fs::path executable;
    std::string expected_executable_sha256;
    std::string authenticated_source_artifact_digest;
    std::string source_authentication_evidence_digest;
    std::string facman_source_revision_digest;
    std::string facman_build_identity_digest;
    std::string evidence_tool_revision;
    std::string evidence_tool_revision_digest;
    std::string machine_binding_id;
    permit::PrincipalIdentity principal;
    fs::path windows_system_root;
    fs::path policy_path;
    fs::path python_executable;
    std::string python_executable_sha256;
    fs::path observer_tool;
    std::string observer_tool_sha256;
    fs::path evidence_tool;
    std::string evidence_tool_sha256;
    fs::path harness_path;
    std::string harness_sha256;
    fs::path classification_roots;
    std::string classification_roots_sha256;
    fs::path baseline_bundle;
    std::string baseline_bundle_sha256;
    std::string protected_baseline_digest;
    std::string writable_baseline_digest;
    fs::path comparison_out;
    fs::path plan_out;
    std::string session_digest;
};

Session load_session(
    const fs::path& path,
    const fs::path& running_harness)
{
    const std::string text = stable_read(path, 4U * 1024U * 1024U);
    auto parsed = json::parse(text, {4U * 1024U * 1024U, 24U, 10000U, 65536U});
    if (!parsed || !parsed.value().is_object()) {
        throw std::runtime_error("session descriptor is not bounded strict JSON");
    }
    const json::Value& value = parsed.value();
    const std::set<std::string> expected_keys{
        "authenticated_source_artifact_digest",
        "baseline_bundle",
        "baseline_bundle_sha256",
        "canonicalization_version",
        "classification_roots",
        "classification_roots_sha256",
        "comparison_out",
        "evidence_tool",
        "evidence_tool_revision",
        "evidence_tool_revision_digest",
        "evidence_tool_sha256",
        "executable",
        "expected_executable_sha256",
        "facman_build_identity_digest",
        "facman_source_revision_digest",
        "harness_path",
        "harness_sha256",
        "installation_root",
        "instance_id",
        "machine_binding_id",
        "observer_tool",
        "observer_tool_sha256",
        "operation_id",
        "operation_root",
        "plan_out",
        "policy_path",
        "preflight_digest",
        "preflight_file_sha256",
        "preflight_path",
        "prepared_at",
        "principal",
        "protected_baseline_digest",
        "python_executable",
        "python_executable_sha256",
        "schema",
        "session_digest",
        "source_authentication_evidence_digest",
        "task_root",
        "windows_system_root",
        "work_unit",
        "workspace",
        "writable_baseline_digest",
    };
    const std::vector<std::string> actual_keys = value.object_keys();
    if (std::set<std::string>(actual_keys.begin(), actual_keys.end()) != expected_keys) {
        throw std::runtime_error("session descriptor is not a closed object");
    }
    if (string_member(value, "schema") != kSessionSchema ||
        string_member(value, "work_unit") != kWorkUnit) {
        throw std::runtime_error("session descriptor identity is unsupported");
    }
    const std::string session_digest = string_member(value, "session_digest");
    if (digest(canonical_without(value, "session_digest")) != session_digest) {
        throw std::runtime_error("session descriptor digest is invalid");
    }
    const json::Value& principal = require_member(value, "principal");
    const std::vector<std::string> principal_keys = principal.object_keys();
    if (!principal.is_object() ||
        std::set<std::string>(principal_keys.begin(), principal_keys.end()) !=
            std::set<std::string>{
                "application_session_id", "principal_id", "provider_id"}) {
        throw std::runtime_error("session principal identity is not closed");
    }

    Session output;
    output.source_root = FACMAN_TEST_SOURCE_ROOT;
    output.session_path = path;
    output.preflight_path = platform::path_from_utf8(
        string_member(value, "preflight_path"));
    output.preflight_digest = string_member(value, "preflight_digest");
    output.preflight_file_sha256 = string_member(value, "preflight_file_sha256");
    output.task_root = platform::path_from_utf8(string_member(value, "task_root"));
    output.workspace = platform::path_from_utf8(string_member(value, "workspace"));
    output.instance_id = string_member(value, "instance_id");
    output.operation_id = string_member(value, "operation_id");
    output.operation_root = platform::path_from_utf8(
        string_member(value, "operation_root"));
    output.installation_root = platform::path_from_utf8(
        string_member(value, "installation_root"));
    output.executable = platform::path_from_utf8(string_member(value, "executable"));
    output.expected_executable_sha256 =
        string_member(value, "expected_executable_sha256");
    output.authenticated_source_artifact_digest =
        string_member(value, "authenticated_source_artifact_digest");
    output.source_authentication_evidence_digest =
        string_member(value, "source_authentication_evidence_digest");
    output.facman_source_revision_digest =
        string_member(value, "facman_source_revision_digest");
    output.facman_build_identity_digest =
        string_member(value, "facman_build_identity_digest");
    output.evidence_tool_revision = string_member(value, "evidence_tool_revision");
    output.evidence_tool_revision_digest =
        string_member(value, "evidence_tool_revision_digest");
    output.machine_binding_id = string_member(value, "machine_binding_id");
    output.principal = {
        string_member(principal, "provider_id"),
        string_member(principal, "principal_id"),
        string_member(principal, "application_session_id")};
    output.windows_system_root = platform::path_from_utf8(
        string_member(value, "windows_system_root"));
    output.policy_path = platform::path_from_utf8(string_member(value, "policy_path"));
    output.python_executable = platform::path_from_utf8(
        string_member(value, "python_executable"));
    output.python_executable_sha256 =
        string_member(value, "python_executable_sha256");
    output.observer_tool = platform::path_from_utf8(string_member(value, "observer_tool"));
    output.observer_tool_sha256 = string_member(value, "observer_tool_sha256");
    output.evidence_tool = platform::path_from_utf8(string_member(value, "evidence_tool"));
    output.evidence_tool_sha256 = string_member(value, "evidence_tool_sha256");
    output.harness_path = platform::path_from_utf8(string_member(value, "harness_path"));
    output.harness_sha256 = string_member(value, "harness_sha256");
    output.classification_roots = platform::path_from_utf8(
        string_member(value, "classification_roots"));
    output.classification_roots_sha256 =
        string_member(value, "classification_roots_sha256");
    output.baseline_bundle = platform::path_from_utf8(
        string_member(value, "baseline_bundle"));
    output.baseline_bundle_sha256 =
        string_member(value, "baseline_bundle_sha256");
    output.protected_baseline_digest =
        string_member(value, "protected_baseline_digest");
    output.writable_baseline_digest =
        string_member(value, "writable_baseline_digest");
    output.comparison_out = platform::path_from_utf8(
        string_member(value, "comparison_out"));
    output.plan_out = platform::path_from_utf8(string_member(value, "plan_out"));
    output.session_digest = session_digest;

    for (const fs::path& inspected : {
             output.source_root,
             output.session_path,
             output.preflight_path,
             output.task_root,
             output.workspace,
             output.operation_root,
             output.installation_root,
             output.executable,
             output.policy_path,
             output.python_executable,
             output.observer_tool,
             output.evidence_tool,
             output.harness_path,
             output.classification_roots,
             output.baseline_bundle,
             output.plan_out.parent_path()}) {
        std::string detail;
        if (facman::base::path_crosses_link_or_reparse_point(inspected, detail)) {
            throw std::runtime_error(
                "session path crosses a link or reparse boundary: " + detail);
        }
    }

    std::error_code first_error;
    std::error_code second_error;
    const fs::path expected_harness = fs::weakly_canonical(
        output.harness_path, first_error);
    const fs::path actual_harness = fs::weakly_canonical(
        running_harness, second_error);
    if (first_error || second_error || expected_harness != actual_harness ||
        stable_sha256(actual_harness, 128U * 1024U * 1024U) !=
            output.harness_sha256 ||
        stable_sha256(output.observer_tool, 4U * 1024U * 1024U) !=
            output.observer_tool_sha256 ||
        stable_sha256(output.evidence_tool, 4U * 1024U * 1024U) !=
            output.evidence_tool_sha256 ||
        stable_sha256(output.python_executable, 128U * 1024U * 1024U) !=
            output.python_executable_sha256 ||
        stable_sha256(output.classification_roots, 16U * 1024U * 1024U) !=
            output.classification_roots_sha256 ||
        stable_sha256(output.baseline_bundle, 256U * 1024U * 1024U) !=
            output.baseline_bundle_sha256 ||
        stable_sha256(output.preflight_path, 16U * 1024U * 1024U) !=
            output.preflight_file_sha256) {
        throw std::runtime_error("harness or ready-preflight artifact changed");
    }
    if (
        output.task_root.filename() != kWorkUnit ||
        !safe_identifier(output.instance_id) ||
        output.operation_id.rfind("gate4c-", 0U) != 0U ||
        !safe_identifier(output.operation_id) ||
        normalized_absolute(output.workspace) !=
            normalized_absolute(output.task_root / "workspace") ||
        normalized_absolute(output.operation_root) !=
            normalized_absolute(
                output.workspace / "temporary" / output.operation_id) ||
        normalized_absolute(output.comparison_out) !=
            normalized_absolute(output.operation_root / "baseline-comparison.json") ||
        !path_beneath(output.task_root, output.preflight_path) ||
        !path_beneath(output.task_root, output.classification_roots) ||
        !path_beneath(output.task_root, output.baseline_bundle) ||
        !path_beneath(output.task_root, output.plan_out) ||
        normalized_absolute(output.observer_tool) !=
            normalized_absolute(output.source_root / "tools" /
                "gate4c_verdict_session.py") ||
        normalized_absolute(output.evidence_tool) !=
            normalized_absolute(output.source_root / "tools" /
                "gate4c_verdict_evidence.py") ||
        normalized_absolute(output.policy_path) !=
            normalized_absolute(output.source_root / "contracts" /
                "generated-index" /
                "hermetic_standalone_play_policy.v1.canonical.json")) {
        throw std::runtime_error("session path scope is not exact");
    }
    return output;
}

facman::core::Result<platform::ProcessResult> run_python(
    const Session& session,
    std::vector<std::string> arguments,
    std::chrono::milliseconds timeout)
{
    platform::ProcessRequest request;
    request.executable = session.python_executable;
    request.arguments = std::move(arguments);
    request.working_directory = session.source_root;
    request.environment = {
        {"PYTHONDONTWRITEBYTECODE", "1"},
        {"TEMP", platform::path_to_utf8(session.operation_root / "process")},
        {"TMP", platform::path_to_utf8(session.operation_root / "process")}};
    request.inherit_environment = true;
    request.timeout = timeout;
    request.maximum_standard_output = 4U * 1024U * 1024U;
    request.maximum_standard_error = 4U * 1024U * 1024U;
    platform::ProcessResult result = platform::supervise_process(request);
    if (result.termination != platform::ProcessTermination::exited ||
        result.exit_code != 0) {
        return facman::core::Result<platform::ProcessResult>::failure(harness_error(
            "permit_wrong_evidence",
            "Gate 4C evidence helper failed: " + result.error + "\n" +
                result.standard_error + result.standard_output,
            "$gate4c.helper"));
    }
    return facman::core::Result<platform::ProcessResult>::success(std::move(result));
}

launch::ProtectedComparisonResult load_comparison(const fs::path& path)
{
    auto parsed = json::parse(
        stable_read(path, 32U * 1024U * 1024U),
        {32U * 1024U * 1024U, 48U, 500000U, 4U * 1024U * 1024U});
    if (!parsed || !parsed.value().is_object() ||
        string_member(parsed.value(), "schema") != kComparisonSchema) {
        throw std::runtime_error("protected comparison is malformed");
    }
    const json::Value& comparisons =
        require_member(parsed.value(), "protected_comparisons");
    if (!comparisons.is_array()) {
        throw std::runtime_error("protected comparison list is malformed");
    }
    launch::ProtectedComparisonResult output;
    output.complete = bool_member(parsed.value(), "protected_complete");
    std::set<std::string> identifiers;
    for (std::size_t index = 0; index < comparisons.size(); ++index) {
        const json::Value* item = comparisons.at(index);
        if (item == nullptr || !item->is_object()) {
            throw std::runtime_error("protected comparison item is malformed");
        }
        launch::ProtectedResourceComparison value;
        value.resource_id = string_member(*item, "resource_id");
        value.before_digest = string_member(*item, "before_digest");
        value.after_digest = string_member(*item, "after_digest");
        value.complete = bool_member(*item, "complete");
        value.changed = bool_member(*item, "changed");
        if (!identifiers.insert(value.resource_id).second) {
            throw std::runtime_error("protected comparison is duplicate");
        }
        output.resources.push_back(std::move(value));
    }
    const std::vector<std::string> protected_ids =
        launch::hermetic_policy_protected_resource_ids();
    const std::set<std::string> expected(
        protected_ids.begin(), protected_ids.end());
    if (identifiers != expected) {
        throw std::runtime_error("protected comparison does not cover frozen scope");
    }
    return output;
}

std::vector<launch::CandidateAutomatedCaseResult> inherited_automated_proof()
{
    std::vector<launch::CandidateAutomatedCaseResult> output;
    for (const std::string& value : launch::hermetic_candidate_automated_controls()) {
        output.push_back({value, true});
    }
    return output;
}

#endif

int observation_digest_self_test()
{
    launch::CandidateObservationResult observation;
    observation.plan_digest = std::string(64U, '1');
    observation.capture_session_digest = std::string(64U, '2');
    observation.raw_artifact_digest = std::string(64U, '3');
    observation.active_before_process = true;
    observation.capture_complete = true;
    observation.effects.push_back({
        0U,
        "process",
        std::string(64U, '4'),
        std::string(64U, '5'),
        "process.primary",
        "writable",
    });
    auto encoded = json::parse(
        launch::candidate_observation_artifact_json(observation));
    if (!encoded || !encoded.value().is_object() ||
        string_member(encoded.value(), "output_digest") !=
            "2e992514c6a4efd0d20e23e8d258a5b236694e6096c2296852b9b63a180beca3") {
        std::cerr << "Gate 4C observer canonicalization drifted.\n";
        return 1;
    }
    return 0;
}

int verify_packet(const fs::path& path, const std::string& expected_digest)
{
    auto packet = launch::read_candidate_lifecycle_packet_no_follow(
        path, expected_digest);
    if (!packet) {
        std::cerr << packet.error().code << ": " << packet.error().message
                  << " (" << packet.error().path << ")\n";
        return 1;
    }
    std::cout << "gate4c-packet-verify: valid (" << expected_digest << ")\n";
    return 0;
}

int run(const fs::path& session_path, const fs::path& running_harness)
{
#ifndef _WIN32
    (void)session_path;
    (void)running_harness;
    std::cerr << "Gate 4C verdict harness is available only on Windows x64.\n";
    return 2;
#else
    Session session = load_session(session_path, running_harness);
    auto policy = launch::FrozenHermeticPlayPolicy::verify_canonical_document(
        stable_read(session.policy_path, 2U * 1024U * 1024U));
    if (!policy || !policy.value().verified ||
        policy.value().policy_digest != launch::kHermeticCandidatePolicyDigest) {
        throw std::runtime_error("frozen policy verification failed");
    }
    instance::HermeticCandidateProjectionRequest projection;
    projection.workspace = session.workspace;
    projection.instance_id = session.instance_id;
    projection.operation_id = session.operation_id;
    projection.installation_root = session.installation_root;
    projection.executable = session.executable;
    projection.expected_executable_sha256 = session.expected_executable_sha256;
    projection.authenticated_source_artifact_digest =
        session.authenticated_source_artifact_digest;
    projection.source_authentication_evidence_digest =
        session.source_authentication_evidence_digest;
    projection.facman_source_revision_digest = session.facman_source_revision_digest;
    projection.facman_build_identity_digest = session.facman_build_identity_digest;
    projection.protected_baseline_digest = session.protected_baseline_digest;
    projection.writable_baseline_digest = session.writable_baseline_digest;
    projection.machine_binding_id = session.machine_binding_id;
    projection.principal = session.principal;
    projection.windows_system_root = session.windows_system_root;
    projection.policy = policy.value();

    auto plan = instance::project_hermetic_candidate_plan(projection);
    if (!plan) {
        throw std::runtime_error(
            plan.error().code + ": " + plan.error().message + " (" +
            plan.error().path + ")");
    }
    write_new(session.plan_out, launch::hermetic_candidate_plan_json(plan.value()) + "\n");
    std::cout
        << "\nGate 4C exact operation review\n"
        << "  operation: instance.play\n"
        << "  instance: " << session.instance_id << "\n"
        << "  intent: menu\n"
        << "  isolation: hermetic\n"
        << "  Factorio: 2.0.77 standalone non-Steam\n"
        << "  plan digest: " << plan.value().plan_digest << "\n"
        << "  plan evidence: " << platform::path_to_utf8(session.plan_out) << "\n\n"
        << "This issues one 30-second, one-use permit and starts the exact reviewed\n"
        << "Factorio candidate. It does not record a human verdict.\n\n"
        << "Type exactly:\nISSUE EXACT MENU PERMIT " << plan.value().plan_digest << "\n> "
        << std::flush;
    std::string approval;
    std::getline(std::cin, approval);
    if (approval != "ISSUE EXACT MENU PERMIT " + plan.value().plan_digest) {
        std::cout << "No permit issued; candidate was not started.\n";
        return 3;
    }

    const fs::path token =
        session.operation_root / "process" / "observation" / "capture-token.json";
    const fs::path observation =
        session.operation_root / "process" / "observation" / "observation.json";
    launch::BoundArtifactCandidateEffectObserver observer(
        [&](const launch::HermeticCandidatePlan&) {
            auto helper = run_python(
                session,
                {
                    platform::path_to_utf8(session.observer_tool),
                    "observer-start",
                    "--task-root", platform::path_to_utf8(session.task_root),
                    "--operation-root", platform::path_to_utf8(session.operation_root),
                    "--preflight-digest", session.preflight_digest,
                    "--launch-provider-process-id",
                    std::to_string(static_cast<unsigned long long>(
                        GetCurrentProcessId())),
                    "--out", platform::path_to_utf8(token),
                },
                std::chrono::minutes(5));
            if (!helper) {
                return facman::core::Result<std::string>::failure(helper.error());
            }
            auto parsed = json::parse(stable_read(token, 4U * 1024U * 1024U));
            if (!parsed || !parsed.value().is_object()) {
                return facman::core::Result<std::string>::failure(harness_error(
                    "permit_wrong_evidence", "capture token is malformed",
                    "$gate4c.observer.token"));
            }
            return facman::core::Result<std::string>::success(
                string_member(parsed.value(), "capture_session_digest"));
        },
        [&](const launch::HermeticCandidatePlan& reviewed,
            const platform::ProcessResult& process) {
            auto helper = run_python(
                session,
                {
                    platform::path_to_utf8(session.observer_tool),
                    "observer-finish",
                    "--task-root", platform::path_to_utf8(session.task_root),
                    "--operation-root", platform::path_to_utf8(session.operation_root),
                    "--capture-token", platform::path_to_utf8(token),
                    "--plan-digest", reviewed.plan_digest,
                    "--process-id", std::to_string(process.identity.process_id),
                    "--process-stable-identity", process.identity.stable_start_identity,
                    "--executable", platform::path_to_utf8(session.executable),
                    "--classification-roots",
                    platform::path_to_utf8(session.classification_roots),
                },
                std::chrono::minutes(10));
            if (!helper) {
                return facman::core::Result<fs::path>::failure(helper.error());
            }
            return facman::core::Result<fs::path>::success(observation);
        });

    launch::PlatformPermitEntropySource entropy;
    auto authenticator = permit::ProcessSessionAuthenticator::create(entropy);
    if (!authenticator) {
        throw std::runtime_error("platform CSPRNG authenticator creation failed");
    }
    permit::SystemPermitClock clock;
    permit::PermitLedger ledger;
    launch::CandidatePermitIssuer issuer(30U);
    auto envelope = issuer.issue(
        plan.value(), *authenticator.value(), entropy, ledger, clock);
    if (!envelope) {
        throw std::runtime_error(
            envelope.error().code + ": " + envelope.error().message);
    }
    launch::HermeticCandidateLaunchProvider provider;
    launch::PlatformProcessSupervisor supervisor;
    const auto current = [&]() {
        return instance::reobserve_hermetic_candidate_context(projection);
    };
    auto execution = provider.consume_and_execute(
        envelope.value(), plan.value(), current, *authenticator.value(),
        ledger, clock, observer, supervisor);
    if (!execution) {
        throw std::runtime_error(
            execution.error().code + ": " + execution.error().message +
            " (" + execution.error().path + ")");
    }

    auto compared = run_python(
        session,
        {
            platform::path_to_utf8(session.evidence_tool),
            "finish",
            "--baseline", platform::path_to_utf8(session.baseline_bundle),
            "--out", platform::path_to_utf8(session.comparison_out),
        },
        std::chrono::minutes(20));
    if (!compared) {
        throw std::runtime_error(
            compared.error().code + ": " + compared.error().message);
    }
    auto packet = launch::build_candidate_evidence_packet(
        plan.value(), execution.value(), load_comparison(session.comparison_out),
        inherited_automated_proof());
    if (!packet) {
        throw std::runtime_error(
            packet.error().code + ": " + packet.error().message);
    }
    auto persisted = launch::persist_candidate_artifacts(
        session.workspace, session.operation_id, packet.value(),
        execution.value().process);
    if (!persisted) {
        throw std::runtime_error(
            persisted.error().code + ": " + persisted.error().message);
    }
    std::cout
        << "\nGate 4C technical packet created.\n"
        << "  disposition: "
        << launch::candidate_technical_disposition_name(
               packet.value().technical_disposition)
        << "\n  packet digest: " << packet.value().packet_digest
        << "\n  lifecycle packet: "
        << platform::path_to_utf8(persisted.value().lifecycle_packet_path)
        << "\n  human verdict: unset\n"
        << "  product authority promoted: false\n";
    return 0;
#endif
}

} // namespace

int main(int argc, char** argv)
{
    try {
        if (argc == 2 && std::string(argv[1]) == "--self-test-observation-digest") {
            return observation_digest_self_test();
        }
        if (argc == 4 && std::string(argv[1]) == "--verify-packet") {
            return verify_packet(
                facman::platform::path_from_utf8(argv[2]), argv[3]);
        }
        if (argc != 3 || std::string(argv[1]) != "--run-session") {
            std::cerr
                << "Evidence-only Gate 4C harness. No public Play route is available.\n"
                << "Usage: facman_gate4c_verdict_harness --run-session <session.json>\n";
            return 64;
        }
        return run(
            facman::platform::path_from_utf8(argv[2]),
            fs::absolute(facman::platform::path_from_utf8(argv[0])));
    } catch (const std::exception& exception) {
        std::cerr << "gate4c-verdict-harness: " << exception.what() << "\n";
        return 2;
    }
}
