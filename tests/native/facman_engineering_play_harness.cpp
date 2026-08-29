// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_json.h"
#include "fl_file_io.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_system_services.h"
#include "facman_release_route_permit_gate.h"
#include "flb_factorio_execution.h"
#include "last_run_provider.h"

#include <algorithm>
#include <chrono>
#include <cctype>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#if defined(_WIN32)
#include <windows.h>
#endif

namespace {
namespace fs = std::filesystem;
namespace application = facman::factorio::application;
namespace json = facman::core::json;
namespace launch = facman::factorio::launch;
namespace permit = facman::core::permit;
namespace release_route = facman::release_route;

constexpr const char* kFactorioInitialisedMarker = "Factorio initialised";
constexpr const char* kClosedDuringLoadingMarker = "Closed during loading.";

bool factorio_menu_observed(const std::string& standard_output)
{
    return standard_output.find(kFactorioInitialisedMarker) != std::string::npos &&
        standard_output.find(kClosedDuringLoadingMarker) == std::string::npos;
}

#if defined(_WIN32)
constexpr const char* kRequiredAcknowledgement =
#if defined(FACMAN_RELEASE_ROUTE_BOUND)
    "FACMAN-RELEASE-ROUTE-D3-D4-ONE-USE";
#else
    "TEST-HARNESS-NO-REAL-RELEASE-AUTHORITY";
#endif

std::string path_text(const fs::path& path)
{
    return facman::platform::path_to_utf8(path.lexically_normal());
}

fs::path normalized_absolute(const fs::path& path)
{
    std::error_code error;
    fs::path value = fs::absolute(path, error);
    return error ? path.lexically_normal() : value.lexically_normal();
}

bool path_within(const fs::path& parent, const fs::path& child)
{
    const fs::path left = normalized_absolute(parent);
    const fs::path right = normalized_absolute(child);
    auto parent_part = left.begin();
    auto child_part = right.begin();
    for (; parent_part != left.end(); ++parent_part, ++child_part) {
        if (child_part == right.end()) return false;
#if defined(_WIN32)
        std::wstring parent_text = parent_part->wstring();
        std::wstring child_text = child_part->wstring();
        if (_wcsicmp(parent_text.c_str(), child_text.c_str()) != 0) return false;
#else
        if (*parent_part != *child_part) return false;
#endif
    }
    return true;
}

std::string read_bounded(const fs::path& path, std::size_t maximum = 4U * 1024U * 1024U)
{
    std::ifstream input(path, std::ios::binary);
    if (!input) return {};
    std::string value((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
    return value.size() <= maximum ? value : std::string {};
}

std::string environment_text(const char* name)
{
    const char* value = std::getenv(name);
    return value == nullptr ? std::string {} : std::string(value);
}

struct Options {
    fs::path task_root;
    fs::path workspace;
    fs::path source_root;
    fs::path instance_root;
    fs::path executable;
    fs::path route_record;
    fs::path config;
    fs::path mod_directory;
    fs::path result_file;
    std::string instance_id;
    std::string acknowledgement;
    unsigned int close_after_seconds = 45U;
    unsigned int timeout_seconds = 150U;
#if defined(FACMAN_RELEASE_ROUTE_BOUND)
    fs::path candidate_package;
    fs::path private_archive;
    fs::path guest_runner;
    fs::path bundle_builder;
    fs::path sandbox_configuration;
    fs::path host_freshness;
    fs::path permit_envelope;
    fs::path permit_session_custody;
    fs::path permit_claim_directory;
    fs::path permit_consume_receipt;
    fs::path permit_refusal_receipt;
    std::string permit_envelope_sha256;
    std::string launch_action;
    std::string operation_id;
    std::string attempt_id;
    unsigned int launch_ordinal = 0U;
#endif
};

bool option_value(int argc, char** argv, int& index, std::string& output)
{
    if (index + 1 >= argc) return false;
    output = argv[++index];
    return true;
}

bool parse_options(int argc, char** argv, Options& output)
{
    std::map<std::string, std::string> values;
    for (int index = 1; index < argc; ++index) {
        const std::string key = argv[index];
        std::string value;
        if (!option_value(argc, argv, index, value)) return false;
        if (!values.emplace(key, value).second) return false;
    }
    const auto required = [&](const char* key) -> std::string {
        const auto found = values.find(key);
        return found == values.end() ? std::string {} : found->second;
    };
    output.task_root = facman::platform::path_from_utf8(required("--task-root"));
    output.workspace = facman::platform::path_from_utf8(required("--workspace"));
    output.source_root = facman::platform::path_from_utf8(required("--source-root"));
    output.instance_root = facman::platform::path_from_utf8(required("--instance-root"));
    output.executable = facman::platform::path_from_utf8(required("--executable"));
    output.route_record = facman::platform::path_from_utf8(required("--route-record"));
    output.config = facman::platform::path_from_utf8(required("--config"));
    output.mod_directory = facman::platform::path_from_utf8(required("--mod-directory"));
    output.result_file = facman::platform::path_from_utf8(required("--result-file"));
    output.instance_id = required("--instance-id");
    output.acknowledgement = required("--acknowledge");
    try {
        const std::string close = required("--close-after-seconds");
        const std::string timeout = required("--timeout-seconds");
        if (!close.empty()) output.close_after_seconds = static_cast<unsigned int>(std::stoul(close));
        if (!timeout.empty()) output.timeout_seconds = static_cast<unsigned int>(std::stoul(timeout));
#if defined(FACMAN_RELEASE_ROUTE_BOUND)
        const std::string ordinal = required("--launch-ordinal");
        if (!ordinal.empty()) output.launch_ordinal = static_cast<unsigned int>(std::stoul(ordinal));
#endif
    } catch (const std::exception&) {
        return false;
    }
#if defined(FACMAN_RELEASE_ROUTE_BOUND)
    output.candidate_package = facman::platform::path_from_utf8(required("--candidate-package"));
    output.private_archive = facman::platform::path_from_utf8(required("--private-archive"));
    output.guest_runner = facman::platform::path_from_utf8(required("--guest-runner"));
    output.bundle_builder = facman::platform::path_from_utf8(required("--bundle-builder"));
    output.sandbox_configuration =
        facman::platform::path_from_utf8(required("--sandbox-configuration"));
    output.host_freshness = facman::platform::path_from_utf8(required("--host-freshness"));
    output.permit_envelope = facman::platform::path_from_utf8(required("--permit-envelope"));
    output.permit_session_custody =
        facman::platform::path_from_utf8(required("--permit-session-custody"));
    output.permit_claim_directory =
        facman::platform::path_from_utf8(required("--permit-claim-directory"));
    output.permit_consume_receipt =
        facman::platform::path_from_utf8(required("--permit-consume-receipt"));
    output.permit_refusal_receipt =
        facman::platform::path_from_utf8(required("--permit-refusal-receipt"));
    output.permit_envelope_sha256 = required("--permit-envelope-sha256");
    output.launch_action = required("--launch-action");
    output.operation_id = required("--operation-id");
    output.attempt_id = required("--attempt-id");
    constexpr std::size_t required_count = 29U;
#else
    constexpr std::size_t required_count = 13U;
#endif
    return values.size() == required_count && !output.result_file.empty() &&
        output.close_after_seconds >= 20U &&
        output.close_after_seconds <= 300U &&
        output.timeout_seconds > output.close_after_seconds + 20U &&
        output.timeout_seconds <= 600U;
}

bool safe_existing_path(const fs::path& task_root, const fs::path& path, bool directory)
{
    std::error_code error;
    std::string detail;
    return path_within(task_root, path) &&
        (directory ? fs::is_directory(path, error) : fs::is_regular_file(path, error)) &&
        !error && !facman::base::path_crosses_link_or_reparse_point(path, detail);
}

bool route_record_valid(const fs::path& route_record, std::string& route_digest)
{
    const std::string text = read_bounded(route_record);
    if (text.empty()) return false;
    route_digest = facman::base::sha256_hex_file(route_record);
#if defined(FACMAN_RELEASE_ROUTE_BOUND)
    const std::vector<std::string> anchors = {
        "schema = \"facman.successor_play_route_definition.v5\"",
        std::string("route_id = \"") + FACMAN_ENGINEERING_ROUTE_ID + "\"",
        std::string("executable_sha256 = \"") +
            FACMAN_ENGINEERING_EXECUTABLE_SHA256 + "\"",
        "factorio_execution_authorized = false",
        "d3_active = false",
        "d4_route_verdict_active = false",
        "publication = false",
    };
#else
    const std::vector<std::string> anchors = {
        "schema = \"facman.factorio_route_version_decision.v1\"",
        std::string("selected_engineering_route_id = \"") +
            FACMAN_ENGINEERING_ROUTE_ID + "\"",
        "selected_engineering_version = \"2.1.14\"",
        std::string("sha256 = \"") + FACMAN_ENGINEERING_EXECUTABLE_SHA256 + "\"",
        "product_execution = false",
        "release_route_activation = false",
        "publication = false",
    };
#endif
    if (route_digest != FACMAN_ENGINEERING_ROUTE_RECORD_SHA256) return false;
    for (const std::string& anchor : anchors) {
        if (text.find(anchor) == std::string::npos) return false;
    }
    return true;
}

#if defined(FACMAN_RELEASE_ROUTE_BOUND)
bool lowercase_digest(const std::string& value)
{
    return value.size() == 64U &&
        std::all_of(value.begin(), value.end(), [](unsigned char byte) {
            return std::isdigit(byte) || (byte >= 'a' && byte <= 'f');
        });
}

std::string text_digest(const std::string& value)
{
    return facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(value.data()), value.size());
}

std::string normalized_source_digest(const fs::path& path)
{
    const std::string source = read_bounded(path, 2U * 1024U * 1024U);
    std::string normalized;
    normalized.reserve(source.size());
    for (std::size_t index = 0U; index < source.size(); ++index) {
        if (source[index] != '\r') {
            normalized.push_back(source[index]);
            continue;
        }
        if (index + 1U >= source.size() || source[index + 1U] != '\n') return {};
    }
    return text_digest(normalized);
}

bool exact_keys(const json::Value& value, const std::set<std::string>& expected)
{
    if (!value.is_object()) return false;
    const std::vector<std::string> keys = value.object_keys();
    return std::set<std::string>(keys.begin(), keys.end()) == expected;
}

bool read_json_string(
    const json::Value& object,
    const char* key,
    std::string& output)
{
    const json::Value* value = object.find(key);
    if (value == nullptr) return false;
    auto parsed = value->string_value();
    if (!parsed) return false;
    output = parsed.take_value();
    return true;
}

bool exact_guest_file(const fs::path& path, const wchar_t* expected)
{
    const fs::path actual = normalized_absolute(path);
    const fs::path wanted = normalized_absolute(fs::path(expected));
    std::string detail;
    std::error_code error;
    return _wcsicmp(actual.c_str(), wanted.c_str()) == 0 &&
        fs::is_regular_file(actual, error) && !error &&
        !facman::base::path_crosses_link_or_reparse_point(actual, detail);
}

fs::path current_executable()
{
    std::vector<wchar_t> buffer(32768U);
    const DWORD size = GetModuleFileNameW(
        nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (size == 0U || size >= buffer.size()) return {};
    return normalized_absolute(fs::path(std::wstring(buffer.data(), size)));
}

struct HostFreshness {
    std::string sandbox_configuration_sha256;
    std::string guest_runner_sha256;
    std::string bundle_builder_sha256;
    std::string first_terminal_receipt_sha256;
    std::uint64_t observed_at_unix_seconds = 0U;
};

bool read_host_freshness(
    const Options& options,
    HostFreshness& output,
    std::string& detail)
{
    const std::string text = read_bounded(options.host_freshness, 64U * 1024U);
    auto document = json::parse(text, {64U * 1024U, 8U, 64U, 1024U});
    const std::set<std::string> keys = {
        "schema", "route_id", "route_record_sha256", "route_definition_digest",
        "launch_ordinal", "operation_id", "attempt_id", "action",
        "candidate_record_sha256", "candidate_package_sha256", "contract_set_sha256",
        "provider_lock_sha256", "factorio_archive_sha256", "factorio_executable_sha256",
        "clean_host_qualification_sha256", "observer_source_sha256",
        "sandbox_configuration_sha256", "guest_runner_sha256", "bundle_builder_sha256",
        "observed_at_unix_seconds", "safety_revalidated", "first_terminal_receipt_sha256"};
    if (!document || !exact_keys(document.value(), keys)) {
        detail = "host freshness is not one closed bounded record";
        return false;
    }
    std::string schema;
    std::string route_id;
    std::string route_record;
    std::string route_definition;
    std::string operation_id;
    std::string attempt_id;
    std::string action;
    std::string candidate_record;
    std::string candidate_package;
    std::string contract_set;
    std::string provider_lock;
    std::string factorio_archive;
    std::string factorio_executable;
    std::string clean_host;
    std::string observer_source;
    const json::Value* ordinal = document.value().find("launch_ordinal");
    const json::Value* observed = document.value().find("observed_at_unix_seconds");
    const json::Value* revalidated = document.value().find("safety_revalidated");
    if (!read_json_string(document.value(), "schema", schema) ||
        !read_json_string(document.value(), "route_id", route_id) ||
        !read_json_string(document.value(), "route_record_sha256", route_record) ||
        !read_json_string(document.value(), "route_definition_digest", route_definition) ||
        !read_json_string(document.value(), "operation_id", operation_id) ||
        !read_json_string(document.value(), "attempt_id", attempt_id) ||
        !read_json_string(document.value(), "action", action) ||
        !read_json_string(document.value(), "candidate_record_sha256", candidate_record) ||
        !read_json_string(document.value(), "candidate_package_sha256", candidate_package) ||
        !read_json_string(document.value(), "contract_set_sha256", contract_set) ||
        !read_json_string(document.value(), "provider_lock_sha256", provider_lock) ||
        !read_json_string(document.value(), "factorio_archive_sha256", factorio_archive) ||
        !read_json_string(
            document.value(), "factorio_executable_sha256", factorio_executable) ||
        !read_json_string(document.value(), "clean_host_qualification_sha256", clean_host) ||
        !read_json_string(document.value(), "observer_source_sha256", observer_source) ||
        !read_json_string(
            document.value(), "sandbox_configuration_sha256",
            output.sandbox_configuration_sha256) ||
        !read_json_string(document.value(), "guest_runner_sha256", output.guest_runner_sha256) ||
        !read_json_string(document.value(), "bundle_builder_sha256", output.bundle_builder_sha256) ||
        ordinal == nullptr || observed == nullptr || revalidated == nullptr) {
        detail = "host freshness fields have invalid types";
        return false;
    }
    auto launch_ordinal = ordinal->unsigned_integer_value();
    auto observed_at = observed->unsigned_integer_value();
    auto safety = revalidated->bool_value();
    const json::Value* first = document.value().find("first_terminal_receipt_sha256");
    if (!launch_ordinal || !observed_at || !safety || first == nullptr ||
        schema != "facman.route_host_freshness.v2" ||
        route_id != FACMAN_ENGINEERING_ROUTE_ID ||
        launch_ordinal.value() != options.launch_ordinal || !safety.value() ||
        route_record != FACMAN_ENGINEERING_ROUTE_RECORD_SHA256 ||
        route_definition != FACMAN_ENGINEERING_ROUTE_DEFINITION_SHA256 ||
        operation_id != options.operation_id || attempt_id != options.attempt_id ||
        action != options.launch_action ||
        candidate_record != FACMAN_ENGINEERING_CANDIDATE_RECORD_SHA256 ||
        candidate_package != FACMAN_ENGINEERING_CANDIDATE_SHA256 ||
        contract_set != FACMAN_ENGINEERING_CONTRACT_SET_SHA256 ||
        provider_lock != FACMAN_ENGINEERING_PROVIDER_LOCK_SHA256 ||
        factorio_archive != FACMAN_ENGINEERING_ARCHIVE_SHA256 ||
        factorio_executable != FACMAN_ENGINEERING_EXECUTABLE_SHA256 ||
        clean_host != FACMAN_ENGINEERING_CLEAN_HOST_SHA256 ||
        observer_source != FACMAN_ENGINEERING_OBSERVER_SOURCE_SHA256 ||
        !lowercase_digest(output.sandbox_configuration_sha256) ||
        output.guest_runner_sha256 != FACMAN_ENGINEERING_GUEST_RUNNER_SOURCE_SHA256 ||
        output.bundle_builder_sha256 != FACMAN_ENGINEERING_BUNDLE_BUILDER_SOURCE_SHA256) {
        detail = "host freshness changed its route, qualification, launch, or safety binding";
        return false;
    }
    output.observed_at_unix_seconds = observed_at.value();
    if (options.launch_ordinal == 1U) {
        if (!first->is_null()) {
            detail = "first-launch freshness may not claim a prior terminal receipt";
            return false;
        }
    } else {
        auto prior = first->string_value();
        const fs::path first_result =
            options.result_file.parent_path() / "engineering-launch.v1.json";
        if (!prior || !lowercase_digest(prior.value()) ||
            !safe_existing_path(options.task_root, first_result, false) ||
            facman::base::sha256_hex_file(first_result) != prior.value()) {
            detail = "second-launch freshness is not bound to the first terminal receipt";
            return false;
        }
        output.first_terminal_receipt_sha256 = prior.take_value();
    }
    return true;
}

permit::ResourceBinding route_resource(
    std::string kind,
    std::string role,
    std::string logical_id,
    std::string identity,
    permit::ProviderIdentity owner,
    std::vector<std::string> effects)
{
    return {
        std::move(kind), std::move(role), std::move(logical_id), std::move(identity),
        std::move(owner), std::move(effects)};
}

permit::PermitValidationContext release_permit_context(
    const Options& options,
    const HostFreshness& freshness,
    const std::string& route_digest,
    const std::string& executable_digest,
    const std::string& candidate_digest,
    const std::string& archive_digest,
    const std::string& observer_binary_digest)
{
    const permit::ProviderIdentity control {
        "facman.release-route-control", "host-guest-two-phase.v1"};
    const permit::ProviderIdentity observer {
        "facman.release-route-observer", FACMAN_ENGINEERING_OBSERVER_SOURCE_SHA256};
    const permit::ProviderIdentity process {
        "factorio.launch.local", "release-route-harness.v3"};
    const permit::ProviderIdentity ulk {
        "universal-launcher", "1.9.1@5479939ca5cbc9ee0f901608a92012778b4752ae"};
    const permit::ProviderIdentity usk {
        "universal-setup", "1.0.0@d2a2aae7e61c47035c92334b0522143b4fea3880"};

    json::ObjectBuilder plan;
    plan.add_string("route_id", FACMAN_ENGINEERING_ROUTE_ID);
    plan.add_string("route_digest", route_digest);
    plan.add_string("operation_id", options.operation_id);
    plan.add_string("attempt_id", options.attempt_id);
    plan.add_string("action", options.launch_action);
    plan.add_unsigned_integer("launch_ordinal", options.launch_ordinal);
    plan.add_string("host_freshness_sha256", facman::base::sha256_hex_file(options.host_freshness));
    plan.add_string("candidate_sha256", candidate_digest);
    plan.add_string("candidate_record_sha256", FACMAN_ENGINEERING_CANDIDATE_RECORD_SHA256);
    plan.add_string("contract_set_sha256", FACMAN_ENGINEERING_CONTRACT_SET_SHA256);
    plan.add_string("provider_lock_sha256", FACMAN_ENGINEERING_PROVIDER_LOCK_SHA256);
    plan.add_string("archive_sha256", archive_digest);
    plan.add_string("executable_sha256", executable_digest);
    const std::string plan_digest = text_digest(plan.serialize());

    json::ObjectBuilder evidence;
    evidence.add_string("plan_digest", plan_digest);
    evidence.add_string("observer_binary_sha256", observer_binary_digest);
    evidence.add_string("observer_source_sha256", FACMAN_ENGINEERING_OBSERVER_SOURCE_SHA256);
    evidence.add_string("sandbox_configuration_sha256", freshness.sandbox_configuration_sha256);
    evidence.add_string("guest_runner_sha256", freshness.guest_runner_sha256);
    evidence.add_string("bundle_builder_sha256", freshness.bundle_builder_sha256);
    evidence.add_string("first_terminal_receipt_sha256", freshness.first_terminal_receipt_sha256);
    const std::string evidence_digest = text_digest(evidence.serialize());

    permit::PermitValidationContext output;
    output.operation = {"instance.play", "menu", "sandbox_task_owned_instance"};
    output.plan = {options.operation_id, plan_digest};
    output.consumer = process;
    output.effects = {"process_execute", "workspace_read", "workspace_write"};
    output.required_capabilities = {
        "launch.execute.sandbox", "process.execute", "route.observe.menu"};
    output.machine_binding_id = "facman.successor-play.clean-host.03:" +
        facman::base::sha256_hex_file(options.host_freshness).substr(0U, 32U);
    output.principal = {
        control.provider_id, "Jules", options.operation_id + ":" + options.attempt_id};
    output.evidence_digest = evidence_digest;
    output.policy = {"3", FACMAN_ENGINEERING_POLICY_SHA256};
    output.provider_revisions = {control, observer, process, ulk, usk};
    const std::vector<std::string> read {"workspace_read"};
    const std::vector<std::string> execute {"process_execute"};
    output.resources = {
        route_resource("source.revision", "candidate_source", "facman-alpha1-revision",
            text_digest("fa60aaa17e9044bef7bb7347261056959690f1cd"), control, read),
        route_resource("source.tree", "candidate_tree", "facman-alpha1-tree",
            text_digest("5536891662461d3617ee40e93654cb2f0659905c"), control, read),
        route_resource("package.archive", "candidate_package", "facman-alpha1-package",
            candidate_digest, control, read),
        route_resource("package.resolution", "candidate_resolution", "facman-alpha1-resolution",
            FACMAN_ENGINEERING_RESOLUTION_SHA256, control, read),
        route_resource("package.manifest", "candidate_record", "facman-alpha1-candidate-record",
            FACMAN_ENGINEERING_CANDIDATE_RECORD_SHA256, control, read),
        route_resource("contract.set", "candidate_contracts", "facman-alpha1-contract-set",
            FACMAN_ENGINEERING_CONTRACT_SET_SHA256, control, read),
        route_resource("provider.lock", "provider_set", "facman-providers-lock-v2",
            FACMAN_ENGINEERING_PROVIDER_LOCK_SHA256, control, read),
        route_resource("provider.identity", "launcher_provider", "universal-launcher-1.9.1",
            text_digest(ulk.provider_revision), ulk, read),
        route_resource("provider.identity", "setup_provider", "universal-setup-1.0.0",
            text_digest(usk.provider_revision), usk, read),
        route_resource("factorio.archive", "private_input", "factorio-2.1.14-archive",
            archive_digest, process, read),
        route_resource("factorio.executable", "process_image", "factorio-2.1.14-executable",
            executable_digest, process, execute),
        route_resource("host.qualification", "clean_host", "windows-sandbox-clean-host-03",
            FACMAN_ENGINEERING_CLEAN_HOST_SHA256, control, read),
        route_resource("host.freshness", "launch_freshness", options.attempt_id,
            facman::base::sha256_hex_file(options.host_freshness), control, read),
        route_resource("route.definition", "release_route", FACMAN_ENGINEERING_ROUTE_ID,
            route_digest, control, read),
        route_resource("route.policy", "release_policy", "windows-sandbox-play-2.1.14",
            FACMAN_ENGINEERING_POLICY_SHA256, control, read),
        route_resource("observer.source", "route_observer", "release-route-observer-source",
            FACMAN_ENGINEERING_OBSERVER_SOURCE_SHA256, observer, read),
        route_resource("observer.binary", "route_observer", "release-route-observer-binary",
            observer_binary_digest, observer, execute),
        route_resource("observer.guest-runner", "guest_control", "windows-private-route-guest",
            freshness.guest_runner_sha256, observer, read),
        route_resource("observer.bundle-builder", "host_control", "windows-private-route-bundle",
            freshness.bundle_builder_sha256, observer, read),
        route_resource("host.sandbox-config", "isolation_configuration", "windows-sandbox-wsb",
            freshness.sandbox_configuration_sha256, observer, read),
        route_resource("operation.attempt", "launch_slot", options.operation_id,
            plan_digest, control, execute),
    };
    return output;
}
#endif

struct TreeInventory {
    std::string digest;
    std::uint64_t files = 0;
    std::uint64_t bytes = 0;
};

bool tree_inventory(const fs::path& root, TreeInventory& output, std::string& detail)
{
    std::vector<fs::path> files;
    std::error_code error;
    for (fs::recursive_directory_iterator iterator(
             root, fs::directory_options::skip_permission_denied, error), end;
         iterator != end && !error;
         iterator.increment(error)) {
        const fs::file_status status = iterator->symlink_status(error);
        if (error) break;
        if (fs::is_symlink(status)) {
            detail = "source tree contains a symbolic link: " + path_text(iterator->path());
            return false;
        }
        if (fs::is_regular_file(status)) files.push_back(iterator->path());
    }
    if (error) {
        detail = "source tree enumeration failed: " + error.message();
        return false;
    }
    std::sort(files.begin(), files.end(), [&](const fs::path& left, const fs::path& right) {
        return path_text(left.lexically_relative(root)) < path_text(right.lexically_relative(root));
    });
    facman::base::Sha256Hasher inventory;
    try {
        for (const fs::path& path : files) {
            std::string link_detail;
            if (facman::base::path_crosses_link_or_reparse_point(path, link_detail)) {
                detail = "source tree path is unsafe: " + link_detail;
                return false;
            }
            const std::uint64_t size = fs::file_size(path);
            const std::string separator(1U, '\0');
            const std::string record = path_text(path.lexically_relative(root)) + separator +
                std::to_string(size) + separator + facman::base::sha256_hex_file(path) + "\n";
            inventory.update(
                reinterpret_cast<const unsigned char*>(record.data()), record.size());
            ++output.files;
            output.bytes += size;
        }
        output.digest = inventory.finish();
    } catch (const std::exception& exception) {
        detail = exception.what();
        return false;
    }
    return true;
}

struct CloseWindowsContext {
    DWORD process_id = 0;
    bool posted = false;
};

BOOL CALLBACK close_process_window(HWND window, LPARAM parameter)
{
    auto* context = reinterpret_cast<CloseWindowsContext*>(parameter);
    DWORD process_id = 0;
    GetWindowThreadProcessId(window, &process_id);
    if (process_id == context->process_id && IsWindowVisible(window)) {
        if (PostMessageW(window, WM_CLOSE, 0, 0)) context->posted = true;
    }
    return TRUE;
}

void close_after_delay(std::uint64_t process_id, unsigned int seconds)
{
    std::this_thread::sleep_for(std::chrono::seconds(seconds));
    for (unsigned int attempt = 0; attempt < 20U; ++attempt) {
        CloseWindowsContext context {static_cast<DWORD>(process_id), false};
        EnumWindows(close_process_window, reinterpret_cast<LPARAM>(&context));
        if (context.posted) return;
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }
}
#endif

int fail(const std::string& code, const std::string& detail)
{
    json::ObjectBuilder error;
    error.add_string("schema", "facman.engineering_play_result.v1");
    error.add_string("status", "refused");
    error.add_string("code", code);
    error.add_string("detail", detail);
    std::cerr << error.serialize() << '\n';
    return 2;
}

} // namespace

int main(int argc, char** argv)
{
#if defined(FACMAN_RELEASE_ROUTE_BOUND)
    if (argc == 2 && std::string(argv[1]) == "--self-test-menu-observation") {
        const bool loading_refused = !factorio_menu_observed(
            "Loading mod base 2.1.14 (data.lua)\nClosed during loading.\nGoodbye\n");
        const bool menu_accepted = factorio_menu_observed(
            "Loading mod base 2.1.14 (data.lua)\nFactorio initialised\nGoodbye\n");
        if (!loading_refused || !menu_accepted) {
            return fail("menu_observation_self_test_failed",
                "The release observer did not distinguish loading from the main menu");
        }
        std::cout << "{\"schema\":\"facman.release_route_menu_observation_self_test.v1\","
                     "\"status\":\"pass\"}\n";
        return 0;
    }
#endif
#if !defined(_WIN32)
    (void)argc;
    (void)argv;
    return fail("unsupported_platform", "The reviewed engineering route is Windows x64 only");
#else
    Options options;
    if (!parse_options(argc, argv, options)) {
        return fail("invalid_arguments", "Exact task, workspace, source, instance, executable, route record, config, mod, result, acknowledgement, close, and timeout values are required");
    }
    options.task_root = normalized_absolute(options.task_root);
    options.workspace = normalized_absolute(options.workspace);
    options.source_root = normalized_absolute(options.source_root);
    options.instance_root = normalized_absolute(options.instance_root);
    options.executable = normalized_absolute(options.executable);
    options.route_record = normalized_absolute(options.route_record);
    options.config = normalized_absolute(options.config);
    options.mod_directory = normalized_absolute(options.mod_directory);
    options.result_file = normalized_absolute(options.result_file);
#if defined(FACMAN_RELEASE_ROUTE_BOUND)
    options.candidate_package = normalized_absolute(options.candidate_package);
    options.private_archive = normalized_absolute(options.private_archive);
    options.guest_runner = normalized_absolute(options.guest_runner);
    options.bundle_builder = normalized_absolute(options.bundle_builder);
    options.sandbox_configuration = normalized_absolute(options.sandbox_configuration);
    options.host_freshness = normalized_absolute(options.host_freshness);
    options.permit_envelope = normalized_absolute(options.permit_envelope);
    options.permit_session_custody = normalized_absolute(options.permit_session_custody);
    options.permit_claim_directory = normalized_absolute(options.permit_claim_directory);
    options.permit_consume_receipt = normalized_absolute(options.permit_consume_receipt);
    options.permit_refusal_receipt = normalized_absolute(options.permit_refusal_receipt);
#endif

#if !defined(FACMAN_RELEASE_ROUTE_BOUND)
    if (options.acknowledgement != kRequiredAcknowledgement) {
        return fail("engineering_acknowledgement_required", kRequiredAcknowledgement);
    }
#endif
    if (options.instance_id.empty() ||
        !safe_existing_path(options.task_root, options.source_root, true) ||
        !safe_existing_path(options.task_root, options.workspace, true) ||
        !safe_existing_path(options.task_root, options.instance_root, true) ||
        !safe_existing_path(options.task_root, options.executable, false) ||
        !safe_existing_path(options.task_root, options.route_record, false) ||
        !safe_existing_path(options.task_root, options.config, false) ||
        !safe_existing_path(options.task_root, options.mod_directory, true) ||
        !safe_existing_path(options.task_root, options.result_file.parent_path(), true) ||
        !path_within(options.task_root, options.result_file) ||
        fs::exists(options.result_file) ||
        !path_within(options.source_root, options.executable) ||
        !path_within(options.workspace, options.instance_root) ||
        !path_within(options.instance_root, options.config) ||
        !path_within(options.instance_root, options.mod_directory) ||
        path_within(options.source_root, options.instance_root) ||
        path_within(options.instance_root, options.source_root)) {
        return fail("engineering_path_refused", "All inputs must be safe, exact, disjoint descendants of the task root");
    }
#if defined(FACMAN_RELEASE_ROUTE_BOUND)
    const bool first_slot = options.launch_ordinal == 1U &&
        options.launch_action == "launch" &&
        options.operation_id == "facman.successor-play.launch-1.operation.05" &&
        options.attempt_id == "facman.successor-play.launch-1.attempt.05";
    const bool second_slot = options.launch_ordinal == 2U &&
        options.launch_action == "relaunch" &&
        options.operation_id == "facman.successor-play.launch-2.operation.05" &&
        options.attempt_id == "facman.successor-play.launch-2.attempt.05";
    if ((!first_slot && !second_slot) ||
        !lowercase_digest(options.permit_envelope_sha256) ||
        !exact_guest_file(options.candidate_package, L"C:\\FacManCandidate\\candidate.zip") ||
        !exact_guest_file(options.private_archive, L"C:\\FacManPrivate\\private-input.zip") ||
        !exact_guest_file(options.guest_runner, L"C:\\FacManHarness\\run.ps1") ||
        !exact_guest_file(options.bundle_builder, L"C:\\FacManHarness\\bundle-builder.py") ||
        !exact_guest_file(options.sandbox_configuration, L"C:\\FacManHarness\\sandbox.wsb") ||
        !safe_existing_path(options.task_root, options.host_freshness, false) ||
        !safe_existing_path(options.task_root, options.permit_envelope, false) ||
        !safe_existing_path(options.task_root, options.permit_session_custody, false) ||
        !safe_existing_path(options.task_root, options.permit_claim_directory, true) ||
        !safe_existing_path(
            options.task_root, options.permit_consume_receipt.parent_path(), true) ||
        !safe_existing_path(
            options.task_root, options.permit_refusal_receipt.parent_path(), true) ||
        !path_within(options.task_root, options.permit_consume_receipt) ||
        !path_within(options.task_root, options.permit_refusal_receipt) ||
        fs::exists(options.permit_consume_receipt) ||
        fs::exists(options.permit_refusal_receipt)) {
        return fail("route_permit_input_refused",
            "Permit custody, launch slot, mapped inputs, state, or receipt paths changed");
    }
#endif
#if defined(FACMAN_RELEASE_ROUTE_BOUND)
    const auto route_fail = [&](const std::string& code, const std::string& detail) -> int {
        json::ObjectBuilder receipt;
        receipt.add_string("schema", "facman.route_permit_refusal_receipt.v1");
        receipt.add_string("status", "refused");
        receipt.add_string("code", code);
        receipt.add_string("route_id", FACMAN_ENGINEERING_ROUTE_ID);
        receipt.add_string("operation_id", options.operation_id);
        receipt.add_string("attempt_id", options.attempt_id);
        receipt.add_unsigned_integer("launch_ordinal", options.launch_ordinal);
        receipt.add_bool("secret_material_retained", false);
        std::string ignored;
        (void)facman::base::write_text_new_atomic(
            options.permit_refusal_receipt, receipt.serialize() + "\n", ignored);
        return fail(code, detail);
    };
#endif
    const std::string executable_sha256 = facman::base::sha256_hex_file(options.executable);
    if (executable_sha256 != FACMAN_ENGINEERING_EXECUTABLE_SHA256) {
#if defined(FACMAN_RELEASE_ROUTE_BOUND)
        return route_fail("engineering_executable_identity_mismatch", executable_sha256);
#else
        return fail("engineering_executable_identity_mismatch", executable_sha256);
#endif
    }
    const std::string config = read_bounded(options.config);
    const std::string expected_read = "read-data=" + path_text(options.source_root / "data");
    const std::string expected_write = "write-data=" + path_text(options.instance_root);
    if (config.find(expected_read) == std::string::npos ||
        config.find(expected_write) == std::string::npos ||
        config.find("check-updates=false") == std::string::npos) {
        return fail("engineering_config_refused", "The exact FacMan config does not route read/write data or disable updates as reviewed");
    }
    std::string route_record_sha256;
    if (!route_record_valid(options.route_record, route_record_sha256)) {
        return fail("engineering_route_record_mismatch", "The compiled route-decision record changed or opens authority");
    }
    TreeInventory source_before;
    std::string inventory_detail;
    if (!tree_inventory(options.source_root, source_before, inventory_detail)) {
        return fail("engineering_source_inventory_failed", inventory_detail);
    }

#if defined(FACMAN_RELEASE_ROUTE_BOUND)
    const std::string candidate_sha256 =
        facman::base::sha256_hex_file(options.candidate_package);
    const std::string archive_sha256 =
        facman::base::sha256_hex_file(options.private_archive);
    if (candidate_sha256 != FACMAN_ENGINEERING_CANDIDATE_SHA256) {
        return route_fail("permit_wrong_package", "Candidate package identity changed");
    }
    if (archive_sha256 != FACMAN_ENGINEERING_ARCHIVE_SHA256) {
        return route_fail("permit_wrong_archive", "Private Factorio archive identity changed");
    }
    HostFreshness freshness;
    std::string freshness_detail;
    if (!read_host_freshness(options, freshness, freshness_detail)) {
        return route_fail("permit_wrong_host_freshness", freshness_detail);
    }
    if (normalized_source_digest(options.guest_runner) !=
            freshness.guest_runner_sha256 ||
        normalized_source_digest(options.bundle_builder) !=
            freshness.bundle_builder_sha256 ||
        facman::base::sha256_hex_file(options.sandbox_configuration) !=
            freshness.sandbox_configuration_sha256) {
        return route_fail("permit_wrong_observer",
            "Guest runner, bundle builder, or Sandbox configuration changed");
    }
    const fs::path observer_executable = current_executable();
    if (observer_executable.empty()) {
        return route_fail("permit_wrong_observer", "Observer binary identity is unavailable");
    }
    const std::string observer_binary_sha256 =
        facman::base::sha256_hex_file(observer_executable);
    const std::string envelope_text = read_bounded(options.permit_envelope, 1024U * 1024U);
    const std::string permit_session_text =
        read_bounded(options.permit_session_custody, 4096U);
    auto decoded_envelope = permit::decode_envelope(envelope_text);
    if (decoded_envelope &&
        decoded_envelope.value().claims.issued_at_unix_seconds <
            freshness.observed_at_unix_seconds) {
        return route_fail("permit_issued_before_host_freshness",
            "Permit issuance predates the launch-specific host freshness observation");
    }
    auto authenticator =
        release_route::CustodiedProcessAuthenticator::decode(permit_session_text);
    if (!authenticator) {
        return route_fail(authenticator.error().code, authenticator.error().message);
    }
    if (options.acknowledgement != kRequiredAcknowledgement) {
        return route_fail("engineering_acknowledgement_required", kRequiredAcknowledgement);
    }
    const permit::PermitValidationContext expected_permit = release_permit_context(
        options, freshness, route_record_sha256, executable_sha256,
        candidate_sha256, archive_sha256, observer_binary_sha256);
    const release_route::RoutePermitConsumeOutcome permit_outcome =
        release_route::consume_route_permit(
            {envelope_text,
             options.permit_envelope_sha256,
             expected_permit,
             options.permit_claim_directory,
             options.permit_consume_receipt,
             options.permit_refusal_receipt},
            *authenticator.value(),
            facman::core::permit::SystemPermitClock {});
    if (!permit_outcome.consumed) {
        return fail(permit_outcome.code,
            "The one-time route permit refused before process dispatch");
    }
#endif

    const fs::path redirected = options.instance_root / "host-state";
    std::error_code error;
    for (const char* child : {"appdata", "localappdata", "programdata", "profile", "temp"}) {
        fs::create_directories(redirected / child, error);
        if (error) return fail("engineering_host_state_refused", error.message());
    }

    facman::platform::RealClock clock;
    facman::platform::RandomIdGenerator ids;
    launch::PlatformProcessSupervisor supervisor;
    launch::LaunchExecutionService service(supervisor, clock, ids);
    launch::LaunchExecutionRequest request;
    request.ulk_session_journal_root = application::ulk_session_journal_root(options.workspace);
    request.runnable_reference = "facman.instance:" + options.instance_id;
    request.relaunch_reference = "relaunch:" + options.instance_id;
    request.instance_id = options.instance_id;
    request.instance_root = options.instance_root;
    request.executable = options.executable;
    request.engineering_task_root = options.task_root;
    request.engineering_source_root = options.source_root;
    request.arguments = {
        "--config", path_text(options.config),
        "--mod-directory", path_text(options.mod_directory),
        "--fullscreen=false", "--disable-audio", "--window-size", "1280x720",
        "--no-log-rotation",
    };
    request.working_directory = options.instance_root;
    request.environment = {
        {"APPDATA", path_text(redirected / "appdata")},
        {"LOCALAPPDATA", path_text(redirected / "localappdata")},
        {"PROGRAMDATA", path_text(redirected / "programdata")},
        {"USERPROFILE", path_text(redirected / "profile")},
        {"TEMP", path_text(redirected / "temp")},
        {"TMP", path_text(redirected / "temp")},
        {"SystemRoot", environment_text("SystemRoot")},
        {"WINDIR", environment_text("WINDIR")},
        {"ComSpec", environment_text("ComSpec")},
        {"PATH", environment_text("PATH")},
    };
    request.execution_mode = "isolated_engineering";
    request.engineering_route_id = FACMAN_ENGINEERING_ROUTE_ID;
    request.expected_executable_sha256 = FACMAN_ENGINEERING_EXECUTABLE_SHA256;
    request.immutable_plan_identity = facman::base::sha256_hex_file(options.config);
    request.authority = launch::ExecutionAuthority::isolated_engineering_process;
    request.timeout = std::chrono::seconds(options.timeout_seconds);
    request.maximum_standard_output = 4U * 1024U * 1024U;
    request.maximum_standard_error = 4U * 1024U * 1024U;

    std::thread closer;
    request.process_started = [&](const facman::platform::ProcessIdentity& identity) {
        closer = std::thread(close_after_delay, identity.process_id, options.close_after_seconds);
    };
    auto result = service.execute(request);
    if (closer.joinable()) closer.join();
    if (!result) return fail(result.error().code, result.error().message + ": " + result.error().detail);
#if defined(FACMAN_RELEASE_ROUTE_BOUND)
    const bool release_menu_observed =
        factorio_menu_observed(result.value().process.standard_output);
#else
    const bool release_menu_observed = true;
#endif
    TreeInventory source_after;
    if (!tree_inventory(options.source_root, source_after, inventory_detail)) {
        return fail("engineering_source_inventory_failed", inventory_detail);
    }
    const bool source_unchanged = source_before.digest == source_after.digest &&
        source_before.files == source_after.files && source_before.bytes == source_after.bytes;

    const std::string session_text = launch::launch_session_json(result.value());
    auto session = json::parse(session_text);
    auto last_run_provider = application::make_ulk_session_last_run_provider(options.workspace);
    const auto last_run = last_run_provider->last_run(request.runnable_reference);
    auto last_run_value = json::parse(last_run.record_json);
    if (!session || !last_run_value) {
        return fail("engineering_result_encoding_failed", "Session or Last Run output is not valid JSON");
    }
    json::ObjectBuilder output;
    output.add_string("schema", "facman.engineering_play_result.v1");
    output.add_string("status",
        result.value().successful && release_menu_observed
            ? "completed"
            : "terminal_non_success");
#if defined(FACMAN_RELEASE_ROUTE_BOUND)
    output.add_string("classification", "external_route_permit_required_no_source_authority");
#else
    output.add_string("classification", "test_harness_no_release_authority");
#endif
    output.add_string("route_id", FACMAN_ENGINEERING_ROUTE_ID);
    output.add_string("route_record_sha256", route_record_sha256);
    output.add_string("executable_sha256", executable_sha256);
    json::ObjectBuilder source_inventory;
    source_inventory.add_string("before_sha256", source_before.digest);
    source_inventory.add_string("after_sha256", source_after.digest);
    source_inventory.add_unsigned_integer("files", source_after.files);
    source_inventory.add_unsigned_integer("bytes", source_after.bytes);
    source_inventory.add_bool("unchanged", source_unchanged);
    output.add_object("source_inventory", source_inventory);
    output.add_string("last_run_authority_state", application::last_run_authority_state_name(last_run.state));
    output.add_value("session", session.value());
    output.add_value("last_run", last_run_value.value());
    const std::string output_text = output.serialize() + "\n";
    std::string result_detail;
    if (!facman::base::write_text_new_atomic(
            options.result_file, output_text, result_detail)) {
        return fail("engineering_result_write_failed", result_detail);
    }
    std::cout << output_text;
    return result.value().successful && release_menu_observed &&
        result.value().authoritative_last_run_recorded && source_unchanged ? 0 : 3;
#endif
}
