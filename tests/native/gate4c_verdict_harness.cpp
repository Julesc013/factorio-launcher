// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_operation_permit.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "flb_factorio_candidate_projection.h"
#include "flb_factorio_hermetic_candidate.h"
#include "gate4c_observer_broker_windows.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <limits>
#include <memory>
#include <optional>
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

#ifdef _WIN32
namespace gate4c = facman::gate4c;

constexpr const char* kSessionSchema = "factorio.gate4c_verdict_session.v1";
constexpr const char* kComparisonSchema =
    "factorio.gate4c_baseline_comparison.v1";
constexpr const char* kWorkUnit =
    "FACMAN-HERMETIC-STANDALONE-PLAY-VERDICT-01";
constexpr const char* kObserverStartRepairWorkUnit =
    "FACMAN-HERMETIC-STANDALONE-PLAY-OBSERVER-START-REPAIR-01";
constexpr const char* kPrivilegeRepairWorkUnit =
    "FACMAN-GATE4C-PRIVILEGE-SEPARATION-REPAIR-01";
constexpr const char* kBrokerRequestSchema =
    "factorio.gate4c_observer_broker_request.v1";
constexpr const char* kBrokerResponseSchema =
    "factorio.gate4c_observer_broker_response.v1";
constexpr const char* kPrivilegeProbeRequestSchema =
    "factorio.gate4c_privilege_probe_request.v1";
constexpr const char* kObserverProviderRevision =
    "gate4c-etw-file-registry-process.v5";

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

#endif

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

std::uint64_t unsigned_member(const json::Value& object, const char* key)
{
    auto value = require_member(object, key).unsigned_integer_value();
    if (!value) {
        throw std::runtime_error(
            std::string("session member is not an unsigned integer: ") + key);
    }
    return value.value();
}

void require_closed_keys(
    const json::Value& object,
    const std::set<std::string>& expected,
    const char* context)
{
    const std::vector<std::string> actual_values = object.object_keys();
    const std::set<std::string> actual(
        actual_values.begin(), actual_values.end());
    if (!object.is_object() || actual != expected) {
        throw std::runtime_error(std::string(context) + " is not a closed object");
    }
}

json::Value parse_bounded_object(
    const std::string& text,
    const std::set<std::string>& expected_keys,
    const char* context)
{
    auto parsed =
        json::parse(text, {1024U * 1024U, 12U, 128U, 256U * 1024U});
    if (!parsed || !parsed.value().is_object()) {
        throw std::runtime_error(std::string(context) + " is not strict JSON");
    }
    require_closed_keys(parsed.value(), expected_keys, context);
    return parsed.take_value();
}

bool lowercase_hex(const std::string& value, std::size_t size)
{
    return value.size() == size &&
        std::all_of(value.begin(), value.end(), [](unsigned char byte) {
            return (byte >= '0' && byte <= '9') ||
                (byte >= 'a' && byte <= 'f');
        });
}

std::uint64_t unix_time_milliseconds()
{
    return static_cast<std::uint64_t>(
        std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::system_clock::now().time_since_epoch())
            .count());
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

std::string canonical_object_digest(const std::string& text)
{
    auto parsed = json::parse(
        text, {1024U * 1024U, 16U, 256U, 256U * 1024U});
    if (!parsed || !parsed.value().is_object()) {
        throw std::runtime_error(
            "protocol object could not be canonicalized");
    }
    return digest(canonical_without(parsed.value(), ""));
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

std::string reviewed_plan_digest(const Session& session)
{
    auto parsed = json::parse(
        stable_read(session.plan_out, 8U * 1024U * 1024U),
        {8U * 1024U * 1024U, 32U, 100000U, 1024U * 1024U});
    if (!parsed || !parsed.value().is_object()) {
        throw std::runtime_error("reviewed plan artifact is malformed");
    }
    const std::string plan_digest =
        string_member(parsed.value(), "plan_digest");
    if (!lowercase_hex(plan_digest, 64U)) {
        throw std::runtime_error("reviewed plan digest is malformed");
    }
    return plan_digest;
}

std::string broker_resource_binding_digest(const Session& session)
{
    return digest(
        "facman.gate4c.observer-broker-resources.v1\n"
        "session=" + session.session_digest + "\n"
        "preflight=" + session.preflight_digest + "\n"
        "baseline=" + session.baseline_bundle_sha256 + "\n"
        "classification=" + session.classification_roots_sha256 + "\n"
        "observer=" + session.observer_tool_sha256 + "\n"
        "python=" + session.python_executable_sha256 + "\n"
        "operation=" + session.operation_id + "\n");
}

std::string start_request_json(
    const Session& session,
    DWORD coordinator_process_id,
    const std::string& plan_digest,
    const std::string& nonce,
    std::uint64_t not_before,
    std::uint64_t expires_at,
    const std::string& request_digest)
{
    json::ObjectBuilder document;
    document.add_string("schema", kBrokerRequestSchema);
    document.add_string("command", "observer_start");
    (void)document.add_unsigned_integer(
        "coordinator_process_id", coordinator_process_id);
    document.add_string("operation_id", session.operation_id);
    document.add_string("session_digest", session.session_digest);
    document.add_string("preflight_digest", session.preflight_digest);
    document.add_string(
        "policy_digest", launch::kHermeticCandidatePolicyDigest);
    document.add_string("plan_digest", plan_digest);
    document.add_string(
        "observer_provider_revision", kObserverProviderRevision);
    document.add_string(
        "resource_binding_digest", broker_resource_binding_digest(session));
    document.add_string("nonce", nonce);
    (void)document.add_unsigned_integer("not_before_unix_ms", not_before);
    (void)document.add_unsigned_integer("expires_at_unix_ms", expires_at);
    if (!request_digest.empty()) {
        document.add_string("request_digest", request_digest);
    }
    return document.serialize();
}

std::string finish_request_json(
    const Session& session,
    const std::string& plan_digest,
    const std::string& nonce,
    const std::string& start_request_digest,
    const std::string& capture_session_digest,
    const platform::ProcessResult& process,
    const std::string& request_digest)
{
    json::ObjectBuilder document;
    document.add_string("schema", kBrokerRequestSchema);
    document.add_string("command", "observer_finish");
    document.add_string("operation_id", session.operation_id);
    document.add_string("session_digest", session.session_digest);
    document.add_string("plan_digest", plan_digest);
    document.add_string("nonce", nonce);
    document.add_string("start_request_digest", start_request_digest);
    document.add_string(
        "capture_session_digest", capture_session_digest);
    (void)document.add_unsigned_integer(
        "process_id", process.identity.process_id);
    document.add_string(
        "process_stable_identity", process.identity.stable_start_identity);
    document.add_string(
        "executable", platform::path_to_utf8(session.executable));
    document.add_string(
        "classification_roots",
        platform::path_to_utf8(session.classification_roots));
    if (!request_digest.empty()) {
        document.add_string("request_digest", request_digest);
    }
    return document.serialize();
}

std::string abort_request_json(
    const Session& session,
    const std::string& nonce,
    const std::string& start_request_digest,
    const std::string& capture_session_digest,
    const std::string& reason,
    const std::string& request_digest)
{
    json::ObjectBuilder document;
    document.add_string("schema", kBrokerRequestSchema);
    document.add_string("command", "observer_abort");
    document.add_string("operation_id", session.operation_id);
    document.add_string("session_digest", session.session_digest);
    document.add_string("nonce", nonce);
    document.add_string("start_request_digest", start_request_digest);
    document.add_string(
        "capture_session_digest", capture_session_digest);
    document.add_string("reason", reason);
    if (!request_digest.empty()) {
        document.add_string("request_digest", request_digest);
    }
    return document.serialize();
}

std::string status_request_json(
    const Session& session,
    const std::string& nonce,
    const std::string& start_request_digest,
    const std::string& capture_session_digest,
    const std::string& request_digest)
{
    json::ObjectBuilder document;
    document.add_string("schema", kBrokerRequestSchema);
    document.add_string("command", "observer_status");
    document.add_string("operation_id", session.operation_id);
    document.add_string("session_digest", session.session_digest);
    document.add_string("nonce", nonce);
    document.add_string("start_request_digest", start_request_digest);
    document.add_string(
        "capture_session_digest", capture_session_digest);
    if (!request_digest.empty()) {
        document.add_string("request_digest", request_digest);
    }
    return document.serialize();
}

std::string response_json(
    const std::string& command,
    const std::string& status,
    const std::string& nonce,
    const std::string& request_digest,
    const std::string& capture_session_digest,
    const gate4c::ProcessSecurityIdentity& coordinator,
    const gate4c::ProcessSecurityIdentity& broker,
    const std::string& detail)
{
    json::ObjectBuilder document;
    document.add_string("schema", kBrokerResponseSchema);
    document.add_string("command", command);
    document.add_string("status", status);
    document.add_string("nonce", nonce);
    document.add_string("request_digest", request_digest);
    document.add_string(
        "capture_session_digest", capture_session_digest);
    (void)document.add_unsigned_integer(
        "coordinator_process_id", coordinator.process_id);
    (void)document.add_unsigned_integer(
        "broker_process_id", broker.process_id);
    document.add_string(
        "coordinator_integrity",
        gate4c::integrity_label(coordinator.integrity_rid));
    document.add_string(
        "broker_integrity", gate4c::integrity_label(broker.integrity_rid));
    (void)document.add_unsigned_integer(
        "windows_session_id", coordinator.windows_session_id);
    document.add_string("principal_sid_digest", digest(coordinator.user_sid));
    document.add_string("detail", detail);
    const std::string core = document.serialize();
    auto parsed = json::parse(core);
    if (!parsed) throw std::runtime_error("broker response encoding failed");
    json::ObjectBuilder final_document;
    for (const std::string& key : parsed.value().object_keys()) {
        final_document.add_value(key, require_member(parsed.value(), key.c_str()));
    }
    final_document.add_string(
        "response_digest", canonical_object_digest(core));
    return final_document.serialize();
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

const std::set<std::string> kStartRequestKeys{
    "command",
    "coordinator_process_id",
    "expires_at_unix_ms",
    "nonce",
    "not_before_unix_ms",
    "observer_provider_revision",
    "operation_id",
    "plan_digest",
    "policy_digest",
    "preflight_digest",
    "request_digest",
    "resource_binding_digest",
    "schema",
    "session_digest",
};

const std::set<std::string> kFinishRequestKeys{
    "capture_session_digest",
    "classification_roots",
    "command",
    "executable",
    "nonce",
    "operation_id",
    "plan_digest",
    "process_id",
    "process_stable_identity",
    "request_digest",
    "schema",
    "session_digest",
    "start_request_digest",
};

const std::set<std::string> kAbortRequestKeys{
    "capture_session_digest",
    "command",
    "nonce",
    "operation_id",
    "reason",
    "request_digest",
    "schema",
    "session_digest",
    "start_request_digest",
};

const std::set<std::string> kStatusRequestKeys{
    "capture_session_digest",
    "command",
    "nonce",
    "operation_id",
    "request_digest",
    "schema",
    "session_digest",
    "start_request_digest",
};

const std::set<std::string> kBrokerResponseKeys{
    "broker_integrity",
    "broker_process_id",
    "capture_session_digest",
    "command",
    "coordinator_integrity",
    "coordinator_process_id",
    "detail",
    "nonce",
    "principal_sid_digest",
    "request_digest",
    "response_digest",
    "schema",
    "status",
    "windows_session_id",
};

void validate_request_digest(
    const json::Value& request,
    const std::string& expected_digest)
{
    const std::string claimed = string_member(request, "request_digest");
    if (!lowercase_hex(claimed, 64U) ||
        digest(canonical_without(request, "request_digest")) != claimed ||
        (!expected_digest.empty() && claimed != expected_digest)) {
        throw std::runtime_error("observer broker request digest is invalid");
    }
}

json::Value validate_broker_response(
    const std::string& text,
    const std::string& expected_command,
    const std::string& expected_nonce,
    const std::string& expected_request_digest,
    const std::string& expected_capture_session_digest,
    const gate4c::ProcessSecurityIdentity& coordinator,
    const gate4c::ProcessSecurityIdentity& broker)
{
    json::Value response = parse_bounded_object(
        text, kBrokerResponseKeys, "observer broker response");
    if (string_member(response, "schema") != kBrokerResponseSchema ||
        string_member(response, "command") != expected_command ||
        string_member(response, "status") != "ok" ||
        string_member(response, "nonce") != expected_nonce ||
        string_member(response, "request_digest") != expected_request_digest ||
        (!expected_capture_session_digest.empty() &&
            string_member(response, "capture_session_digest") !=
                expected_capture_session_digest) ||
        unsigned_member(response, "coordinator_process_id") !=
            coordinator.process_id ||
        unsigned_member(response, "broker_process_id") != broker.process_id ||
        string_member(response, "coordinator_integrity") != "medium" ||
        string_member(response, "broker_integrity") != "high" ||
        unsigned_member(response, "windows_session_id") !=
            coordinator.windows_session_id ||
        string_member(response, "principal_sid_digest") !=
            digest(coordinator.user_sid) ||
        digest(canonical_without(response, "response_digest")) !=
            string_member(response, "response_digest")) {
        throw std::runtime_error(
            "observer broker response identity is invalid");
    }
    return response;
}

void record_broker_recovery_required(
    const Session& session,
    const std::string& plan_digest,
    const std::string& capture_session_digest,
    const std::string& reason) noexcept
{
    try {
        json::ObjectBuilder document;
        document.add_string(
            "schema", "factorio.gate4c_observer_recovery_required.v1");
        document.add_string("work_unit", kPrivilegeRepairWorkUnit);
        document.add_string(
            "policy_digest", launch::kHermeticCandidatePolicyDigest);
        document.add_string("plan_digest", plan_digest);
        document.add_string("session_digest", session.session_digest);
        document.add_string(
            "capture_session_digest", capture_session_digest);
        document.add_string("reason", reason);
        document.add_bool("factorio_authority_promoted", false);
        document.add_bool("human_verdict_recorded", false);
        const std::string core = document.serialize();
        auto parsed = json::parse(core);
        if (!parsed) return;
        json::ObjectBuilder closed;
        for (const std::string& key : parsed.value().object_keys()) {
            closed.add_value(
                key, require_member(parsed.value(), key.c_str()));
        }
        closed.add_string(
            "recovery_digest", canonical_object_digest(core));
        write_new(
            session.operation_root / "candidate-artifacts" /
                "observer-recovery-required.json",
            closed.serialize() + "\n");
    } catch (...) {
    }
}

class ObserverBrokerClient {
public:
    ObserverBrokerClient(
        const Session& session,
        std::string plan_digest)
        : session_(session),
          plan_digest_(std::move(plan_digest)),
          coordinator_(gate4c::current_process_security_identity())
    {
        if (!gate4c::is_exact_medium_integrity(coordinator_)) {
            throw std::runtime_error(
                "Gate 4C coordinator must run at medium integrity");
        }
    }

    ~ObserverBrokerClient()
    {
        abort_noexcept("coordinator_disconnected");
    }

    facman::core::Result<std::string> begin()
    {
        try {
            connection_ =
                std::make_unique<gate4c::ElevatedBrokerConnection>(
                    gate4c::ElevatedBrokerConnection::launch(
                        session_.harness_path, L"--observer-broker",
                        {
                            session_.session_path.wstring(),
                            std::to_wstring(coordinator_.process_id),
                        },
                        std::chrono::minutes(2)));
            nonce_ = gate4c::secure_nonce_hex(32U);
            const std::uint64_t now = unix_time_milliseconds();
            const std::string core = start_request_json(
                session_, coordinator_.process_id, plan_digest_, nonce_,
                now > 1000U ? now - 1000U : 0U, now + 90000U, {});
            start_request_digest_ = canonical_object_digest(core);
            const std::string request = start_request_json(
                session_, coordinator_.process_id, plan_digest_, nonce_,
                now > 1000U ? now - 1000U : 0U, now + 90000U,
                start_request_digest_);
            connection_->channel().write_frame(request);
            start_response_text_ =
                connection_->channel().read_frame(1024U * 1024U);
            const json::Value response = validate_broker_response(
                start_response_text_, "observer_started", nonce_,
                start_request_digest_, {}, coordinator_,
                connection_->broker_identity());
            capture_session_digest_ =
                string_member(response, "capture_session_digest");
            if (!lowercase_hex(capture_session_digest_, 64U)) {
                throw std::runtime_error(
                    "observer broker returned an invalid capture identity");
            }
            active_ = true;
            const std::string status_core = status_request_json(
                session_, nonce_, start_request_digest_,
                capture_session_digest_, {});
            const std::string status_request_digest =
                canonical_object_digest(status_core);
            connection_->channel().write_frame(status_request_json(
                session_, nonce_, start_request_digest_,
                capture_session_digest_, status_request_digest));
            status_response_text_ =
                connection_->channel().read_frame(1024U * 1024U);
            (void)validate_broker_response(
                status_response_text_, "observer_ready", nonce_,
                status_request_digest, capture_session_digest_, coordinator_,
                connection_->broker_identity());
            return facman::core::Result<std::string>::success(
                capture_session_digest_);
        } catch (const std::exception& exception) {
            abort_noexcept("coordinator_disconnected");
            return facman::core::Result<std::string>::failure(harness_error(
                "permit_wrong_evidence",
                std::string("elevated observer broker start failed: ") +
                    exception.what(),
                "$gate4c.observer.broker"));
        }
    }

    facman::core::Result<fs::path> finish(
        const platform::ProcessResult& process)
    {
        if (!active_ || !connection_) {
            return facman::core::Result<fs::path>::failure(harness_error(
                "permit_wrong_evidence",
                "observer broker was not active",
                "$gate4c.observer.broker"));
        }
        if (!process.identity.restart_safe() ||
            process.termination ==
                platform::ProcessTermination::start_failed) {
            abort_noexcept("launch_refused");
            return facman::core::Result<fs::path>::failure(harness_error(
                "permit_wrong_evidence",
                "candidate process was not created; observer was aborted",
                "$gate4c.observer.broker"));
        }
        try {
            const std::string core = finish_request_json(
                session_, plan_digest_, nonce_, start_request_digest_,
                capture_session_digest_, process, {});
            const std::string request_digest =
                canonical_object_digest(core);
            connection_->channel().write_frame(finish_request_json(
                session_, plan_digest_, nonce_, start_request_digest_,
                capture_session_digest_, process, request_digest));
            finish_response_text_ =
                connection_->channel().read_frame(1024U * 1024U);
            (void)validate_broker_response(
                finish_response_text_, "observer_finished", nonce_,
                request_digest, capture_session_digest_, coordinator_,
                connection_->broker_identity());
            write_privilege_evidence();
            active_ = false;
            connection_->close_channel();
            if (connection_->wait_for_exit(std::chrono::seconds(30)) !=
                WAIT_OBJECT_0) {
                throw std::runtime_error(
                    "observer broker did not terminate after finish");
            }
            return facman::core::Result<fs::path>::success(
                session_.operation_root / "process" / "observation" /
                "observation.json");
        } catch (const std::exception& exception) {
            abort_noexcept("coordinator_disconnected");
            return facman::core::Result<fs::path>::failure(harness_error(
                "permit_wrong_evidence",
                std::string("elevated observer broker finish failed: ") +
                    exception.what(),
                "$gate4c.observer.broker"));
        }
    }

private:
    void write_privilege_evidence()
    {
        auto start = json::parse(start_response_text_);
        auto status = json::parse(status_response_text_);
        auto finish = json::parse(finish_response_text_);
        if (!start || !status || !finish) {
            throw std::runtime_error(
                "observer broker response evidence could not be decoded");
        }
        json::ObjectBuilder document;
        document.add_string(
            "schema", "factorio.gate4c_privilege_boundary.v1");
        document.add_string("work_unit", kPrivilegeRepairWorkUnit);
        document.add_string(
            "policy_digest", launch::kHermeticCandidatePolicyDigest);
        document.add_string("plan_digest", plan_digest_);
        document.add_string("session_digest", session_.session_digest);
        document.add_string("coordinator_integrity", "medium");
        document.add_string("factorio_required_integrity", "medium");
        document.add_string("observer_broker_integrity", "high");
        document.add_value("start", start.value());
        document.add_value("status", status.value());
        document.add_value("finish", finish.value());
        const std::string core = document.serialize();
        auto parsed = json::parse(core);
        if (!parsed) {
            throw std::runtime_error(
                "privilege-boundary evidence encoding failed");
        }
        json::ObjectBuilder closed;
        for (const std::string& key : parsed.value().object_keys()) {
            closed.add_value(key, require_member(parsed.value(), key.c_str()));
        }
        closed.add_string("evidence_digest", digest(core));
        write_new(
            session_.operation_root / "candidate-artifacts" /
                "privilege-boundary.json",
            closed.serialize() + "\n");
    }

    void abort_noexcept(const std::string& reason) noexcept
    {
        if (!active_ || !connection_) return;
        try {
            const std::string core = abort_request_json(
                session_, nonce_, start_request_digest_,
                capture_session_digest_, reason, {});
            const std::string request_digest =
                canonical_object_digest(core);
            connection_->channel().write_frame(abort_request_json(
                session_, nonce_, start_request_digest_,
                capture_session_digest_, reason, request_digest));
            const std::string response =
                connection_->channel().read_frame(1024U * 1024U);
            (void)validate_broker_response(
                response, "observer_aborted", nonce_, request_digest,
                capture_session_digest_, coordinator_,
                connection_->broker_identity());
        } catch (...) {
            record_broker_recovery_required(
                session_, plan_digest_, capture_session_digest_,
                "broker_abort_or_channel_failed_wpr_state_requires_elevated_check");
        }
        active_ = false;
        connection_->close_channel();
        (void)connection_->wait_for_exit(std::chrono::seconds(30));
    }

    const Session& session_;
    std::string plan_digest_;
    gate4c::ProcessSecurityIdentity coordinator_;
    std::unique_ptr<gate4c::ElevatedBrokerConnection> connection_;
    std::string nonce_;
    std::string start_request_digest_;
    std::string capture_session_digest_;
    std::string start_response_text_;
    std::string status_response_text_;
    std::string finish_response_text_;
    bool active_ = false;
};

void abort_capture(
    const Session& session,
    const std::string& capture_session_digest,
    const std::string& reason)
{
    const fs::path token =
        session.operation_root / "process" / "observation" /
        "capture-token.json";
    auto aborted = run_python(
        session,
        {
            platform::path_to_utf8(session.observer_tool),
            "observer-abort",
            "--task-root", platform::path_to_utf8(session.task_root),
            "--operation-root", platform::path_to_utf8(session.operation_root),
            "--capture-token", platform::path_to_utf8(token),
            "--capture-session-digest", capture_session_digest,
            "--reason", reason,
        },
        std::chrono::minutes(5));
    if (!aborted) {
        throw std::runtime_error(
            "fail-closed observer abort failed: " +
            aborted.error().message);
    }
}

int run_observer_broker(
    const std::wstring& pipe_name,
    const fs::path& session_path,
    DWORD expected_coordinator_process_id,
    const fs::path& running_harness)
{
    Session session = load_session(session_path, running_harness);
    const gate4c::ProcessSecurityIdentity broker =
        gate4c::current_process_security_identity();
    gate4c::BrokerServerConnection connection =
        gate4c::connect_to_coordinator(
            pipe_name, expected_coordinator_process_id, running_harness,
            std::chrono::minutes(2));

    bool capture_active = false;
    std::string capture_session_digest;
    try {
        const std::string start_text =
            connection.channel.read_frame(1024U * 1024U);
        const json::Value start = parse_bounded_object(
            start_text, kStartRequestKeys, "observer broker start request");
        validate_request_digest(start, {});
        const std::string start_request_digest =
            string_member(start, "request_digest");
        const std::string nonce = string_member(start, "nonce");
        const std::uint64_t not_before =
            unsigned_member(start, "not_before_unix_ms");
        const std::uint64_t expires_at =
            unsigned_member(start, "expires_at_unix_ms");
        const std::uint64_t now = unix_time_milliseconds();
        if (string_member(start, "schema") != kBrokerRequestSchema ||
            string_member(start, "command") != "observer_start" ||
            unsigned_member(start, "coordinator_process_id") !=
                connection.coordinator_identity.process_id ||
            string_member(start, "operation_id") != session.operation_id ||
            string_member(start, "session_digest") != session.session_digest ||
            string_member(start, "preflight_digest") !=
                session.preflight_digest ||
            string_member(start, "policy_digest") !=
                launch::kHermeticCandidatePolicyDigest ||
            string_member(start, "plan_digest") !=
                reviewed_plan_digest(session) ||
            string_member(start, "observer_provider_revision") !=
                kObserverProviderRevision ||
            string_member(start, "resource_binding_digest") !=
                broker_resource_binding_digest(session) ||
            !lowercase_hex(nonce, 64U) ||
            not_before > now + 1000U || expires_at <= now ||
            expires_at - now > 90000U || expires_at <= not_before) {
            throw std::runtime_error(
                "observer broker start request binding is invalid");
        }
        auto policy =
            launch::FrozenHermeticPlayPolicy::verify_canonical_document(
                stable_read(
                    session.policy_path, 2U * 1024U * 1024U));
        if (!policy || !policy.value().verified ||
            policy.value().policy_digest !=
                launch::kHermeticCandidatePolicyDigest) {
            throw std::runtime_error(
                "observer broker independently rejected the frozen policy");
        }

        const fs::path token =
            session.operation_root / "process" / "observation" /
            "capture-token.json";
        auto started = run_python(
            session,
            {
                platform::path_to_utf8(session.observer_tool),
                "observer-start",
                "--task-root", platform::path_to_utf8(session.task_root),
                "--operation-root",
                platform::path_to_utf8(session.operation_root),
                "--preflight-digest", session.preflight_digest,
                "--launch-provider-process-id",
                std::to_string(static_cast<unsigned long long>(
                    connection.coordinator_identity.process_id)),
                "--out", platform::path_to_utf8(token),
            },
            std::chrono::minutes(5));
        if (!started) {
            throw std::runtime_error(started.error().message);
        }
        auto token_value = json::parse(
            stable_read(token, 4U * 1024U * 1024U));
        if (!token_value || !token_value.value().is_object()) {
            throw std::runtime_error("capture token is malformed");
        }
        capture_session_digest =
            string_member(token_value.value(), "capture_session_digest");
        if (!lowercase_hex(capture_session_digest, 64U)) {
            throw std::runtime_error("capture token digest is malformed");
        }
        capture_active = true;
        connection.channel.write_frame(response_json(
            "observer_started", "ok", nonce, start_request_digest,
            capture_session_digest, connection.coordinator_identity, broker,
            "wpr_active_before_process_boundary"));

        const std::string status_text =
            connection.channel.read_frame(1024U * 1024U);
        const json::Value status = parse_bounded_object(
            status_text, kStatusRequestKeys,
            "observer broker status request");
        validate_request_digest(status, {});
        const std::string status_request_digest =
            string_member(status, "request_digest");
        if (string_member(status, "schema") != kBrokerRequestSchema ||
            string_member(status, "command") != "observer_status" ||
            string_member(status, "operation_id") != session.operation_id ||
            string_member(status, "session_digest") !=
                session.session_digest ||
            string_member(status, "nonce") != nonce ||
            string_member(status, "start_request_digest") !=
                start_request_digest ||
            string_member(status, "capture_session_digest") !=
                capture_session_digest) {
            throw std::runtime_error(
                "observer broker status request binding is invalid");
        }
        auto status_result = run_python(
            session,
            {
                platform::path_to_utf8(session.observer_tool),
                "observer-status",
                "--task-root", platform::path_to_utf8(session.task_root),
                "--operation-root",
                platform::path_to_utf8(session.operation_root),
                "--capture-token", platform::path_to_utf8(token),
                "--capture-session-digest", capture_session_digest,
            },
            std::chrono::minutes(2));
        if (!status_result) {
            throw std::runtime_error(status_result.error().message);
        }
        connection.channel.write_frame(response_json(
            "observer_ready", "ok", nonce, status_request_digest,
            capture_session_digest, connection.coordinator_identity, broker,
            "wpr_status_revalidated_active"));

        const std::string next_text =
            connection.channel.read_frame(1024U * 1024U);
        auto untyped = json::parse(
            next_text, {1024U * 1024U, 12U, 128U, 256U * 1024U});
        if (!untyped || !untyped.value().is_object()) {
            throw std::runtime_error(
                "observer broker final request is not strict JSON");
        }
        const std::string command =
            string_member(untyped.value(), "command");
        if (command == "observer_abort") {
            const json::Value request = parse_bounded_object(
                next_text, kAbortRequestKeys,
                "observer broker abort request");
            validate_request_digest(request, {});
            const std::string request_digest =
                string_member(request, "request_digest");
            if (string_member(request, "schema") != kBrokerRequestSchema ||
                string_member(request, "operation_id") !=
                    session.operation_id ||
                string_member(request, "session_digest") !=
                    session.session_digest ||
                string_member(request, "nonce") != nonce ||
                string_member(request, "start_request_digest") !=
                    start_request_digest ||
                string_member(request, "capture_session_digest") !=
                    capture_session_digest ||
                (string_member(request, "reason") != "launch_refused" &&
                    string_member(request, "reason") !=
                        "coordinator_disconnected" &&
                    string_member(request, "reason") !=
                        "operator_cancelled")) {
                throw std::runtime_error(
                    "observer broker abort request binding is invalid");
            }
            abort_capture(
                session, capture_session_digest,
                string_member(request, "reason"));
            capture_active = false;
            connection.channel.write_frame(response_json(
                "observer_aborted", "ok", nonce, request_digest,
                capture_session_digest, connection.coordinator_identity,
                broker, "wpr_stopped_without_process"));
            return 0;
        }
        if (command != "observer_finish") {
            throw std::runtime_error(
                "observer broker command is outside the closed surface");
        }
        const json::Value finish = parse_bounded_object(
            next_text, kFinishRequestKeys,
            "observer broker finish request");
        validate_request_digest(finish, {});
        const std::string finish_request_digest =
            string_member(finish, "request_digest");
        if (string_member(finish, "schema") != kBrokerRequestSchema ||
            string_member(finish, "operation_id") != session.operation_id ||
            string_member(finish, "session_digest") !=
                session.session_digest ||
            string_member(finish, "plan_digest") !=
                reviewed_plan_digest(session) ||
            string_member(finish, "nonce") != nonce ||
            string_member(finish, "start_request_digest") !=
                start_request_digest ||
            string_member(finish, "capture_session_digest") !=
                capture_session_digest ||
            unsigned_member(finish, "process_id") == 0U ||
            string_member(finish, "process_stable_identity").empty() ||
            normalized_absolute(platform::path_from_utf8(
                string_member(finish, "executable"))) !=
                normalized_absolute(session.executable) ||
            normalized_absolute(platform::path_from_utf8(
                string_member(finish, "classification_roots"))) !=
                normalized_absolute(session.classification_roots)) {
            throw std::runtime_error(
                "observer broker finish request binding is invalid");
        }

        auto finished = run_python(
            session,
            {
                platform::path_to_utf8(session.observer_tool),
                "observer-finish",
                "--task-root", platform::path_to_utf8(session.task_root),
                "--operation-root",
                platform::path_to_utf8(session.operation_root),
                "--capture-token", platform::path_to_utf8(token),
                "--plan-digest", string_member(finish, "plan_digest"),
                "--process-id",
                std::to_string(unsigned_member(finish, "process_id")),
                "--process-stable-identity",
                string_member(finish, "process_stable_identity"),
                "--executable", platform::path_to_utf8(session.executable),
                "--classification-roots",
                platform::path_to_utf8(session.classification_roots),
            },
            std::chrono::minutes(10));
        if (!finished) {
            throw std::runtime_error(finished.error().message);
        }
        capture_active = false;
        connection.channel.write_frame(response_json(
            "observer_finished", "ok", nonce, finish_request_digest,
            capture_session_digest, connection.coordinator_identity, broker,
            "wpr_stopped_and_observation_hash_closed"));
        return 0;
    } catch (...) {
        if (capture_active) {
            try {
                abort_capture(
                    session, capture_session_digest,
                    "coordinator_disconnected");
            } catch (...) {
                record_broker_recovery_required(
                    session, reviewed_plan_digest(session),
                    capture_session_digest,
                    "broker_fail_closed_abort_failed_wpr_state_requires_elevated_check");
            }
        }
        throw;
    }
}

const std::set<std::string> kPrivilegeProbeRequestKeys{
    "command",
    "coordinator_process_id",
    "nonce",
    "request_digest",
    "schema",
};

std::string privilege_probe_request_json(
    DWORD coordinator_process_id,
    const std::string& nonce,
    const std::string& request_digest)
{
    json::ObjectBuilder document;
    document.add_string("schema", kPrivilegeProbeRequestSchema);
    document.add_string("command", "privilege_probe");
    (void)document.add_unsigned_integer(
        "coordinator_process_id", coordinator_process_id);
    document.add_string("nonce", nonce);
    if (!request_digest.empty()) {
        document.add_string("request_digest", request_digest);
    }
    return document.serialize();
}

int run_observer_broker_probe(
    const std::wstring& pipe_name,
    DWORD expected_coordinator_process_id,
    const fs::path& running_harness)
{
    const gate4c::ProcessSecurityIdentity broker =
        gate4c::current_process_security_identity();
    gate4c::BrokerServerConnection connection =
        gate4c::connect_to_coordinator(
            pipe_name, expected_coordinator_process_id, running_harness,
            std::chrono::minutes(2));
    const std::string request_text =
        connection.channel.read_frame(64U * 1024U);
    const json::Value request = parse_bounded_object(
        request_text, kPrivilegeProbeRequestKeys,
        "privilege-boundary probe request");
    validate_request_digest(request, {});
    const std::string nonce = string_member(request, "nonce");
    const std::string request_digest =
        string_member(request, "request_digest");
    if (string_member(request, "schema") !=
            kPrivilegeProbeRequestSchema ||
        string_member(request, "command") != "privilege_probe" ||
        unsigned_member(request, "coordinator_process_id") !=
            connection.coordinator_identity.process_id ||
        !lowercase_hex(nonce, 64U)) {
        throw std::runtime_error(
            "privilege-boundary probe binding is invalid");
    }
    connection.channel.write_frame(response_json(
        "privilege_probe", "ok", nonce, request_digest,
        digest("not_applicable"), connection.coordinator_identity, broker,
        "mutual_process_token_and_binary_identity_verified"));
    return 0;
}

int privilege_boundary_probe(
    const fs::path& task_root,
    const std::string& probe_id,
    const fs::path& running_harness)
{
    if (normalized_absolute(task_root).filename() !=
            kPrivilegeRepairWorkUnit ||
        probe_id.rfind("gate4c-privilege-probe-", 0U) != 0U ||
        !safe_identifier(probe_id)) {
        throw std::runtime_error(
            "privilege-boundary probe scope is not exact");
    }
    std::string path_detail;
    if (facman::base::path_crosses_link_or_reparse_point(
            task_root, path_detail) ||
        facman::base::path_crosses_link_or_reparse_point(
            running_harness, path_detail)) {
        throw std::runtime_error(
            "privilege-boundary probe crosses an unsafe path boundary");
    }
    const fs::path output =
        task_root / "evidence" / "privilege-probes" / (probe_id + ".json");
    if (fs::exists(output)) {
        throw std::runtime_error(
            "privilege-boundary probe identity already exists");
    }
    const auto coordinator =
        gate4c::current_process_security_identity();
    auto connection = gate4c::ElevatedBrokerConnection::launch(
        running_harness, L"--observer-broker-probe",
        {std::to_wstring(coordinator.process_id)}, std::chrono::minutes(2));
    const std::string nonce = gate4c::secure_nonce_hex(32U);
    const std::string core = privilege_probe_request_json(
        coordinator.process_id, nonce, {});
    const std::string request_digest = canonical_object_digest(core);
    connection.channel().write_frame(privilege_probe_request_json(
        coordinator.process_id, nonce, request_digest));
    const std::string response_text =
        connection.channel().read_frame(64U * 1024U);
    const json::Value response = validate_broker_response(
        response_text, "privilege_probe", nonce, request_digest,
        digest("not_applicable"), coordinator,
        connection.broker_identity());

    json::ObjectBuilder evidence;
    evidence.add_string(
        "schema", "factorio.gate4c_privilege_probe.v1");
    evidence.add_string("work_unit", kPrivilegeRepairWorkUnit);
    evidence.add_string("probe_id", probe_id);
    evidence.add_string(
        "frozen_policy_digest", launch::kHermeticCandidatePolicyDigest);
    evidence.add_bool("factorio_started", false);
    evidence.add_bool("wpr_started", false);
    evidence.add_value("authenticated_response", response);
    const std::string evidence_core = evidence.serialize();
    auto parsed = json::parse(evidence_core);
    if (!parsed) {
        throw std::runtime_error(
            "privilege-boundary probe evidence encoding failed");
    }
    json::ObjectBuilder closed;
    for (const std::string& key : parsed.value().object_keys()) {
        closed.add_value(
            key, require_member(parsed.value(), key.c_str()));
    }
    closed.add_string(
        "probe_digest", canonical_object_digest(evidence_core));
    write_new(output, closed.serialize() + "\n");
    connection.close_channel();
    if (connection.wait_for_exit(std::chrono::seconds(30)) !=
        WAIT_OBJECT_0) {
        throw std::runtime_error(
            "privilege-boundary probe broker did not terminate");
    }
    std::cout << "gate4c-privilege-boundary-probe: pass\n"
              << "  evidence: " << platform::path_to_utf8(output) << "\n";
    return 0;
}

std::string helper_result_json(
    const std::vector<std::string>& arguments,
    const platform::ProcessResult& result,
    bool harness_in_job)
{
    json::ArrayBuilder argument_values;
    for (const std::string& argument : arguments) {
        argument_values.add_string(argument);
    }
    json::ObjectBuilder identity;
    (void)identity.add_unsigned_integer("process_id", result.identity.process_id);
    identity.add_string("platform", result.identity.platform);
    identity.add_string(
        "stable_start_identity", result.identity.stable_start_identity);
    json::ObjectBuilder document;
    document.add_string(
        "schema", "factorio.gate4c_observer_helper_supervision.v1");
    document.add_string(
        "work_unit", kObserverStartRepairWorkUnit);
    document.add_array("arguments", argument_values);
    document.add_string(
        "termination", platform::process_termination_name(result.termination));
    (void)document.add_signed_integer("exit_code", result.exit_code);
    (void)document.add_signed_integer("native_status", result.native_status);
    document.add_string("stdout", result.standard_output);
    document.add_string("stderr", result.standard_error);
    document.add_string("supervisor_error", result.error);
    document.add_bool("process_tree_terminated", result.process_tree_terminated);
    document.add_bool("harness_in_job", harness_in_job);
    document.add_object("process_identity", identity);
    return document.serialize();
}

int observer_start_probe(
    const fs::path& task_root,
    const fs::path& python_executable,
    const std::string& probe_id)
{
    if (normalized_absolute(task_root).filename() !=
            kObserverStartRepairWorkUnit ||
        probe_id.rfind("gate4c-observer-start-probe-", 0U) != 0U ||
        !safe_identifier(probe_id)) {
        throw std::runtime_error("observer-start probe scope is not exact");
    }
    std::string detail;
    const fs::path source_root = FACMAN_TEST_SOURCE_ROOT;
    const fs::path observer_tool =
        source_root / "tools" / "gate4c_verdict_session.py";
    if (facman::base::path_crosses_link_or_reparse_point(task_root, detail) ||
        facman::base::path_crosses_link_or_reparse_point(
            python_executable, detail) ||
        facman::base::path_crosses_link_or_reparse_point(observer_tool, detail)) {
        throw std::runtime_error(
            "observer-start probe crosses a link or reparse boundary: " + detail);
    }
    const fs::path evidence_root =
        task_root / "evidence" / "observer-start-probes";
    const fs::path helper_out = evidence_root / (probe_id + ".json");
    const fs::path native_out =
        evidence_root / (probe_id + "-native-supervision.json");
    const fs::path temporary_root =
        task_root / "native-helper-temp" / probe_id;
    if (fs::exists(helper_out) || fs::exists(native_out) ||
        fs::exists(temporary_root)) {
        throw std::runtime_error("observer-start probe identity already exists");
    }
    std::error_code create_error;
    fs::create_directories(temporary_root, create_error);
    if (create_error ||
        facman::base::path_crosses_link_or_reparse_point(
            temporary_root, detail)) {
        throw std::runtime_error(
            "observer-start probe temporary boundary is unsafe: " + detail);
    }

    std::vector<std::string> arguments{
        platform::path_to_utf8(observer_tool),
        "observer-start-probe",
        "--task-root", platform::path_to_utf8(task_root),
        "--probe-id", probe_id,
        "--out", platform::path_to_utf8(helper_out),
    };
    platform::ProcessRequest request;
    request.executable = python_executable;
    request.arguments = arguments;
    request.working_directory = source_root;
    request.environment = {
        {"PYTHONDONTWRITEBYTECODE", "1"},
        {"TEMP", platform::path_to_utf8(temporary_root)},
        {"TMP", platform::path_to_utf8(temporary_root)}};
    request.inherit_environment = true;
    request.timeout = std::chrono::minutes(10);
    request.maximum_standard_output = 4U * 1024U * 1024U;
    request.maximum_standard_error = 4U * 1024U * 1024U;
    platform::ProcessResult result = platform::supervise_process(request);
    BOOL harness_in_job = FALSE;
    if (!IsProcessInJob(GetCurrentProcess(), nullptr, &harness_in_job)) {
        throw std::runtime_error("observer-start probe could not inspect job state");
    }
    fs::create_directories(evidence_root, create_error);
    if (create_error) {
        throw std::runtime_error("observer-start probe evidence root is unavailable");
    }
    write_new(
        native_out,
        helper_result_json(arguments, result, harness_in_job != FALSE) + "\n");
    std::cout
        << "gate4c-observer-start-native-probe: "
        << (result.termination == platform::ProcessTermination::exited &&
                   result.exit_code == 0
                ? "pass"
                : "inconclusive")
        << "\n  helper evidence: " << platform::path_to_utf8(helper_out)
        << "\n  supervision evidence: " << platform::path_to_utf8(native_out)
        << "\n";
    return result.termination == platform::ProcessTermination::exited &&
            result.exit_code == 0
        ? 0
        : 2;
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

int privilege_protocol_self_test()
{
#ifndef _WIN32
    return 0;
#else
    const auto current = gate4c::current_process_security_identity();
    if (current.process_id != GetCurrentProcessId() ||
        current.user_sid.rfind("S-", 0U) != 0U ||
        current.image_path.empty() ||
        gate4c::secure_nonce_hex(32U).size() != 64U ||
        !gate4c::is_exact_medium_integrity(
            {1U, 1U, SECURITY_MANDATORY_MEDIUM_RID, "S-1", {}}) ||
        gate4c::is_exact_medium_integrity(
            {1U, 1U, SECURITY_MANDATORY_HIGH_RID, "S-1", {}}) ||
        !gate4c::is_high_integrity(
            {1U, 1U, SECURITY_MANDATORY_HIGH_RID, "S-1", {}})) {
        std::cerr << "Gate 4C Windows security identity primitives failed.\n";
        return 1;
    }

    Session session;
    session.operation_id = "gate4c-protocol-smoke";
    session.session_digest = std::string(64U, '1');
    session.preflight_digest = std::string(64U, '2');
    session.baseline_bundle_sha256 = std::string(64U, '3');
    session.classification_roots_sha256 = std::string(64U, '4');
    session.observer_tool_sha256 = std::string(64U, '5');
    session.python_executable_sha256 = std::string(64U, '6');
    const std::string plan_digest(64U, '7');
    const std::string nonce(64U, '8');
    const std::uint64_t now = unix_time_milliseconds();
    const std::string core = start_request_json(
        session, current.process_id, plan_digest, nonce, now - 1U,
        now + 30000U, {});
    const std::string request_digest = canonical_object_digest(core);
    const std::string request = start_request_json(
        session, current.process_id, plan_digest, nonce, now - 1U,
        now + 30000U, request_digest);
    try {
        const json::Value parsed = parse_bounded_object(
            request, kStartRequestKeys, "protocol self-test request");
        validate_request_digest(parsed, request_digest);
        std::string mutated = request;
        const std::size_t position = mutated.find(request_digest);
        if (position == std::string::npos) return 2;
        mutated[position] = mutated[position] == 'a' ? 'b' : 'a';
        bool refused = false;
        try {
            const json::Value invalid = parse_bounded_object(
                mutated, kStartRequestKeys, "mutated protocol request");
            validate_request_digest(invalid, {});
        } catch (const std::exception&) {
            refused = true;
        }
        if (!refused) return 3;

        gate4c::ProcessSecurityIdentity coordinator{
            100U,
            10U,
            SECURITY_MANDATORY_MEDIUM_RID,
            "S-1-5-21-protocol",
            current.image_path,
        };
        gate4c::ProcessSecurityIdentity broker{
            200U,
            10U,
            SECURITY_MANDATORY_HIGH_RID,
            coordinator.user_sid,
            current.image_path,
        };
        const std::string response = response_json(
            "observer_started", "ok", nonce, request_digest,
            std::string(64U, '9'), coordinator, broker, "protocol_smoke");
        (void)validate_broker_response(
            response, "observer_started", nonce, request_digest,
            std::string(64U, '9'), coordinator, broker);
    } catch (const std::exception& exception) {
        std::cerr << "Gate 4C privilege protocol self-test failed: "
                  << exception.what() << "\n";
        return 4;
    }
    return 0;
#endif
}

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
    const gate4c::ProcessSecurityIdentity coordinator_security =
        gate4c::current_process_security_identity();
    if (!gate4c::is_exact_medium_integrity(coordinator_security)) {
        throw std::runtime_error(
            "Gate 4C coordinator must run at medium integrity; observed " +
            gate4c::integrity_label(coordinator_security.integrity_rid) +
            ". Start it from a normal non-elevated terminal.");
    }
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
    std::optional<gate4c::ProcessSecurityIdentity> factorio_security;
    std::string factorio_security_error;
    plan.value().process.validate_before_resume =
        [&](const platform::ProcessIdentity& identity) {
            try {
                const auto observed =
                    gate4c::inspect_process_security_identity(
                        static_cast<DWORD>(identity.process_id));
                json::ObjectBuilder document;
                document.add_string(
                    "schema", "factorio.gate4c_process_integrity.v1");
                document.add_string("work_unit", kPrivilegeRepairWorkUnit);
                document.add_string("plan_digest", plan.value().plan_digest);
                (void)document.add_unsigned_integer(
                    "process_id", identity.process_id);
                document.add_string(
                    "stable_process_identity",
                    identity.stable_start_identity);
                document.add_string(
                    "integrity",
                    gate4c::integrity_label(observed.integrity_rid));
                (void)document.add_unsigned_integer(
                    "windows_session_id", observed.windows_session_id);
                document.add_string(
                    "principal_sid_digest", digest(observed.user_sid));
                document.add_string(
                    "executable_sha256",
                    session.expected_executable_sha256);
                const std::string core = document.serialize();
                auto parsed = json::parse(core);
                if (!parsed) {
                    throw std::runtime_error(
                        "Factorio integrity evidence encoding failed");
                }
                json::ObjectBuilder closed;
                for (const std::string& key :
                    parsed.value().object_keys()) {
                    closed.add_value(
                        key, require_member(parsed.value(), key.c_str()));
                }
                closed.add_string("evidence_digest", digest(core));
                write_new(
                    session.operation_root / "candidate-artifacts" /
                        "factorio-integrity.json",
                    closed.serialize() + "\n");
                factorio_security = observed;
                return gate4c::is_exact_medium_integrity(observed) &&
                    observed.user_sid == coordinator_security.user_sid &&
                    observed.windows_session_id ==
                        coordinator_security.windows_session_id;
            } catch (const std::exception& exception) {
                factorio_security_error = exception.what();
                return false;
            }
        };
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

    std::unique_ptr<ObserverBrokerClient> observer_broker;
    launch::BoundArtifactCandidateEffectObserver observer(
        [&](const launch::HermeticCandidatePlan&) {
            observer_broker =
                std::make_unique<ObserverBrokerClient>(
                    session, plan.value().plan_digest);
            return observer_broker->begin();
        },
        [&](const launch::HermeticCandidatePlan& reviewed,
            const platform::ProcessResult& process) {
            if (!observer_broker ||
                reviewed.plan_digest != plan.value().plan_digest) {
                return facman::core::Result<fs::path>::failure(harness_error(
                    "permit_wrong_evidence",
                    "observer broker is missing or bound to another plan",
                    "$gate4c.observer.broker"));
            }
            return observer_broker->finish(process);
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
    if (execution.value().process_creation_requested &&
        execution.value().process.termination !=
            platform::ProcessTermination::start_failed) {
        if (!factorio_security ||
            !factorio_security_error.empty() ||
            !gate4c::is_exact_medium_integrity(*factorio_security) ||
            factorio_security->user_sid != coordinator_security.user_sid ||
            factorio_security->windows_session_id !=
                coordinator_security.windows_session_id) {
            throw std::runtime_error(
                "Factorio medium-integrity evidence failed: " +
                factorio_security_error);
        }
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
        if (argc == 2 && std::string(argv[1]) == "--self-test-privilege-protocol") {
            return privilege_protocol_self_test();
        }
        if (argc == 4 && std::string(argv[1]) == "--verify-packet") {
            return verify_packet(
                facman::platform::path_from_utf8(argv[2]), argv[3]);
        }
#ifdef _WIN32
        if (argc == 4 &&
            std::string(argv[1]) == "--observer-broker-probe") {
            const unsigned long process_id = std::stoul(argv[3]);
            if (process_id == 0UL ||
                process_id > static_cast<unsigned long>(
                    std::numeric_limits<DWORD>::max())) {
                throw std::runtime_error(
                    "observer broker probe coordinator PID is invalid");
            }
            return run_observer_broker_probe(
                gate4c::utf8_to_wide(argv[2]),
                static_cast<DWORD>(process_id),
                fs::absolute(facman::platform::path_from_utf8(argv[0])));
        }
        if (argc == 4 &&
            std::string(argv[1]) == "--privilege-boundary-probe") {
            return privilege_boundary_probe(
                facman::platform::path_from_utf8(argv[2]), argv[3],
                fs::absolute(facman::platform::path_from_utf8(argv[0])));
        }
        if (argc == 5 && std::string(argv[1]) == "--observer-broker") {
            const unsigned long process_id = std::stoul(argv[4]);
            if (process_id == 0UL ||
                process_id > static_cast<unsigned long>(
                    std::numeric_limits<DWORD>::max())) {
                throw std::runtime_error(
                    "observer broker coordinator PID is invalid");
            }
            return run_observer_broker(
                gate4c::utf8_to_wide(argv[2]),
                facman::platform::path_from_utf8(argv[3]),
                static_cast<DWORD>(process_id),
                fs::absolute(facman::platform::path_from_utf8(argv[0])));
        }
        if (argc == 5 && std::string(argv[1]) == "--observer-start-probe") {
            return observer_start_probe(
                facman::platform::path_from_utf8(argv[2]),
                facman::platform::path_from_utf8(argv[3]),
                argv[4]);
        }
#endif
        if (argc != 3 || std::string(argv[1]) != "--run-session") {
            std::cerr
                << "Evidence-only Gate 4C harness. No public Play route is available.\n"
                << "Usage: facman_gate4c_verdict_harness --run-session <session.json>\n"
                << "       facman_gate4c_verdict_harness --observer-broker "
                   "<private-pipe> <session.json> <coordinator-pid>\n"
                << "       facman_gate4c_verdict_harness "
                   "--privilege-boundary-probe <repair-root> <probe-id>\n"
                << "       facman_gate4c_verdict_harness --observer-start-probe "
                   "<repair-root> <python.exe> <probe-id>\n";
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
