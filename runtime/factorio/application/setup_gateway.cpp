// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "setup_gateway.h"

#include "fl_json.h"
#include "fl_file_io.h"
#include "fl_sha256.h"

#include <algorithm>
#include <array>
#include <initializer_list>
#include <set>
#include <system_error>
#include <tuple>

#ifndef FACMAN_WITH_SETUP
#define FACMAN_WITH_SETUP 0
#endif

#if FACMAN_WITH_SETUP
#include "usk/usk_api.h"
#endif

namespace facman::factorio::application {
namespace {

facman::core::Error unavailable_error()
{
    facman::core::Error error {"disabled_by_build", "Universal Setup support is disabled in this build", ""};
    error.kind = facman::core::OutcomeKind::unavailable;
    error.recoverable = true;
    return error;
}

class UnavailableSetupGateway final : public SetupGateway {
public:
    facman::core::Result<PackageVerifyResult> verify_package(const PackageVerifyRequest&) override
    {
        return facman::core::Result<PackageVerifyResult>::failure(unavailable_error());
    }
    facman::core::Result<facman::factorio::setup::ArchiveAssessment> inspect_install_archive(
        const FactorioArchiveInspectRequest&) override
    {
        return facman::core::Result<facman::factorio::setup::ArchiveAssessment>::failure(
            unavailable_error());
    }
    facman::core::Result<InstallPlan> plan_install(const InstallPlanRequest&) override
    {
        return facman::core::Result<InstallPlan>::failure(unavailable_error());
    }
    facman::core::Result<UninstallPlan> plan_uninstall(const UninstallPlanRequest&) override
    {
        return facman::core::Result<UninstallPlan>::failure(unavailable_error());
    }
    facman::core::Result<SetupRefusal> verify_install(const std::string&) override
    {
        return facman::core::Result<SetupRefusal>::failure(unavailable_error());
    }
    facman::core::Result<SetupRefusal> repair_install(const std::string&) override
    {
        return facman::core::Result<SetupRefusal>::failure(unavailable_error());
    }
    facman::core::Result<SetupRefusal> uninstall_install(const std::string&) override
    {
        return facman::core::Result<SetupRefusal>::failure(unavailable_error());
    }
};

#if FACMAN_WITH_SETUP
usk_string_view view(const std::string& text)
{
    return {text.data(), static_cast<usk_size>(text.size())};
}

facman::core::Result<std::string> execute_setup(
    const std::string& command,
    const std::string& payload,
    const SetupConfiguration& setup,
    bool dry_run = true)
{
    const char* state_root = setup.state_root.empty() ? nullptr : setup.state_root.c_str();
    const char* acceptance_root = setup.acceptance_root.empty() ? nullptr : setup.acceptance_root.c_str();
    const char* activation = setup.policy_activation.empty() ? nullptr : setup.policy_activation.c_str();
    const bool any_configured = setup.configured();
    if (any_configured &&
        (state_root == nullptr || *state_root == '\0' ||
         acceptance_root == nullptr || *acceptance_root == '\0' ||
         activation == nullptr || *activation == '\0')) {
        return facman::core::Result<std::string>::failure({
            "setup_configuration_incomplete",
            "FACMAN setup planning requires state, acceptance-root, and policy activation together",
            ""});
    }
    if (activation != nullptr && std::string(activation) != "operator_acceptance_candidate") {
        return facman::core::Result<std::string>::failure({
            "setup_policy_activation_refused",
            "This build accepts only the bounded operator_acceptance_candidate managed-target policy",
            ""});
    }
    usk_config_v1 config {};
    const usk_config_v1* configured = nullptr;
    if (any_configured) {
        config.struct_size = sizeof(config);
        config.state_root = state_root;
        config.authorized_acceptance_root = acceptance_root;
        config.target_policy_activation = activation;
        configured = &config;
    }
    usk_context* context = nullptr;
    if (usk_context_create_v1(configured, &context) != USK_STATUS_OK || context == nullptr) {
        return facman::core::Result<std::string>::failure({"setup_context_failed", "Universal Setup context creation failed", ""});
    }
    usk_command_request_v1 request {};
    usk_command_response_v1 response {};
    request.struct_size = sizeof(request);
    request.command_name = view(command);
    request.json_payload = view(payload);
    request.dry_run = dry_run ? 1 : 0;
    response.struct_size = sizeof(response);
    const int status = usk_command_execute_v1(context, &request, &response);
    std::string output;
    if (response.json_payload.data != nullptr) {
        output.assign(response.json_payload.data, response.json_payload.data + response.json_payload.size);
    }
    usk_context_destroy_v1(context);
    if (status != USK_STATUS_OK) {
        facman::core::Error error {
            "setup_provider_refused",
            "Universal Setup refused the request",
            "",
            facman::core::OutcomeKind::refused};
        error.detail = std::move(output);
        return facman::core::Result<std::string>::failure(std::move(error));
    }
    return facman::core::Result<std::string>::success(std::move(output));
}

facman::core::Result<std::filesystem::path> absolute_normalized(
    const std::filesystem::path& path,
    const char* field)
{
    if (path.empty()) {
        return facman::core::Result<std::filesystem::path>::failure({
            "setup_plan_input_missing", std::string(field) + " is required", ""});
    }
    std::error_code error;
    const std::filesystem::path absolute = std::filesystem::absolute(path, error);
    if (error) {
        return facman::core::Result<std::filesystem::path>::failure({
            "setup_plan_path_invalid", std::string(field) + " could not be made absolute", ""});
    }
    return facman::core::Result<std::filesystem::path>::success(absolute.lexically_normal());
}

std::string string_field(const facman::core::json::Value& object, const char* key)
{
    const auto* value = object.find(key);
    if (value == nullptr) return {};
    auto text = value->string_value();
    return text ? text.take_value() : std::string();
}

bool sha256_field(const std::string& value)
{
    if (value.size() != 64) return false;
    for (const char character : value) {
        if (!((character >= '0' && character <= '9') ||
              (character >= 'a' && character <= 'f'))) return false;
    }
    return true;
}

bool bounded_string(const facman::core::json::Value& object, const char* key, std::size_t maximum)
{
    const auto* value = object.find(key);
    if (value == nullptr || !value->is_string()) return false;
    auto text = value->string_value();
    return text && !text.value().empty() && text.value().size() <= maximum;
}

bool bounded_value_string(const facman::core::json::Value& value, std::size_t maximum)
{
    if (!value.is_string()) return false;
    auto text = value.string_value();
    return text && !text.value().empty() && text.value().size() <= maximum;
}

bool exact_members(
    const facman::core::json::Value& object,
    std::initializer_list<const char*> expected)
{
    if (!object.is_object() || object.size() != expected.size()) return false;
    std::set<std::string> expected_keys;
    for (const char* key : expected) expected_keys.insert(key);
    const std::vector<std::string> actual = object.object_keys();
    return actual.size() == expected_keys.size() &&
        std::set<std::string>(actual.begin(), actual.end()) == expected_keys;
}

bool normalized_absolute_path(
    const std::string& value,
    const std::filesystem::path& expected)
{
    if (value.empty() || value.size() > 32768) return false;
    const std::filesystem::path path = facman::platform::path_from_utf8(value);
    return path.is_absolute() && path == path.lexically_normal() &&
        path == expected;
}

bool safe_relative_path(const std::string& value)
{
    if (value.empty() || value.size() > 4096 || value.front() == '/' ||
        value.find('\\') != std::string::npos || value.find(':') != std::string::npos) return false;
    std::size_t begin = 0;
    while (begin < value.size()) {
        const std::size_t end = value.find('/', begin);
        const std::string component = value.substr(begin, end - begin);
        if (component.empty() || component == "." || component == "..") return false;
        if (end == std::string::npos) return true;
        begin = end + 1;
    }
    return false;
}

bool response_envelope(
    const facman::core::json::Value& document,
    const facman::core::json::Value*& payload)
{
    if (!exact_members(document, {"error", "payload", "schema", "status"}) ||
        string_field(document, "schema") != "usk.command_response.v1" ||
        string_field(document, "status") != "ok") return false;
    const auto* error = document.find("error");
    payload = document.find("payload");
    return error != nullptr && error->is_null() && payload != nullptr && payload->is_object();
}

struct InspectedInstallState {
    std::filesystem::path target;
    std::string installed_state_digest;
    std::string ownership_manifest_digest;
    std::string recipe_digest;
    std::string source_digest;
    std::string provider_revision;
};

facman::core::Result<std::string> installed_state_digest(
    const facman::core::json::Value& state)
{
    facman::core::json::ObjectBuilder payload;
    for (const char* key : {
            "audit_chain_id", "component_selection", "created_at", "entrypoints",
            "install_id", "lifecycle_status", "ownership_manifest_digest",
            "ownership_manifest_ref", "product_id", "product_version", "recipe_digest",
            "setup_abi", "source_archive_digest", "target_root", "target_scope",
            "transaction_id"}) {
        const auto* value = state.find(key);
        if (value == nullptr || !payload.add_value(key, *value)) {
            return facman::core::Result<std::string>::failure({
                "setup_installed_state_response_invalid",
                "Universal Setup returned an invalid installed-state response",
                "installed-state digest input"});
        }
    }
    auto document = facman::core::json::parse(payload.serialize());
    if (!document) return facman::core::Result<std::string>::failure(document.error());
    auto canonical = facman::core::json::canonical_integer_json(document.value());
    if (!canonical) return facman::core::Result<std::string>::failure(canonical.error());
    const std::string& bytes = canonical.value();
    return facman::core::Result<std::string>::success(facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(bytes.data()), bytes.size()));
}

bool lifecycle_matches(const std::string& facman_lifecycle, const std::string& usk_lifecycle)
{
    if (facman_lifecycle == "active") {
        return usk_lifecycle == "installed" || usk_lifecycle == "verified";
    }
    if (facman_lifecycle == "verification_failed") {
        return usk_lifecycle == "repair_required" || usk_lifecycle == "uninstall_blocked";
    }
    return facman_lifecycle == "recovery_required" && usk_lifecycle == "recovery_required";
}

facman::core::Result<InspectedInstallState> decode_installed_state(
    const std::string& response,
    const UninstallPlanRequest& request,
    const SetupConfiguration& configuration)
{
    const auto invalid = [](const char* detail) {
        return facman::core::Result<InspectedInstallState>::failure({
            "setup_installed_state_response_invalid",
            "Universal Setup returned an invalid installed-state response",
            detail});
    };
    facman::core::json::Limits limits;
    limits.maximum_bytes = 4U * 1024U * 1024U;
    limits.maximum_depth = 32;
    limits.maximum_nodes = 100000;
    limits.maximum_string_bytes = 32768;
    auto document = facman::core::json::parse(response, limits);
    const facman::core::json::Value* state = nullptr;
    if (!document || !response_envelope(document.value(), state) ||
        !exact_members(*state, {"audit_chain_id", "component_selection", "created_at", "entrypoints",
            "install_id", "last_verification", "lifecycle_status", "ownership_manifest_digest",
            "ownership_manifest_ref", "product_id", "product_version", "recipe_digest", "schema",
            "setup_abi", "source_archive_digest", "target_root", "target_scope", "transaction_id"}) ||
        string_field(*state, "schema") != "usk.installed_state.v1" ||
        string_field(*state, "target_scope") != "portable" ||
        string_field(*state, "install_id") != request.install_id ||
        !bounded_string(*state, "product_id", 256) || !bounded_string(*state, "product_version", 128) ||
        !bounded_string(*state, "ownership_manifest_ref", 4096) ||
        !bounded_string(*state, "transaction_id", 256) || !bounded_string(*state, "created_at", 64) ||
        !bounded_string(*state, "audit_chain_id", 256) || !bounded_string(*state, "lifecycle_status", 64) ||
        !sha256_field(string_field(*state, "ownership_manifest_digest")) ||
        !sha256_field(string_field(*state, "recipe_digest")) ||
        !sha256_field(string_field(*state, "source_archive_digest"))) return invalid("state envelope");

    auto expected_target = absolute_normalized(request.target, "target");
    auto setup_root = absolute_normalized(facman::platform::path_from_utf8(configuration.state_root), "setup state root");
    if (!expected_target || !setup_root ||
        !normalized_absolute_path(string_field(*state, "target_root"), expected_target.value())) {
        return invalid("target binding");
    }

    const auto* verification = state->find("last_verification");
    const auto* abi = state->find("setup_abi");
    const auto* components = state->find("component_selection");
    const auto* entrypoints = state->find("entrypoints");
    if (verification == nullptr || abi == nullptr || components == nullptr || entrypoints == nullptr ||
        !exact_members(*verification, {"report_digest", "report_id", "status", "verified_at"}) ||
        !exact_members(*abi, {"major", "minor", "provider_revision"}) ||
        !components->is_array() || components->size() == 0 || !entrypoints->is_array() || entrypoints->size() == 0 ||
        !sha256_field(string_field(*verification, "report_digest")) ||
        string_field(*verification, "report_digest") != request.last_verification_identity ||
        !bounded_string(*verification, "report_id", 256) || !bounded_string(*verification, "status", 16) ||
        !bounded_string(*verification, "verified_at", 64) ||
        (string_field(*verification, "status") != "pass" && string_field(*verification, "status") != "warn" &&
            string_field(*verification, "status") != "fail") ||
        !bounded_string(*abi, "provider_revision", 256)) return invalid("state evidence");
    const auto* major = abi->find("major");
    const auto* minor = abi->find("minor");
    if (major == nullptr || minor == nullptr) return invalid("setup ABI");
    const auto major_value = major->unsigned_integer_value();
    const auto minor_value = minor->unsigned_integer_value();
    if (!major_value || !minor_value || major_value.value() == 0) return invalid("setup ABI");
    for (std::size_t index = 0; index < components->size(); ++index) {
        const auto* component = components->at(index);
        if (component == nullptr || !component->is_string() || component->string_value().value().empty() ||
            component->string_value().value().size() > 256) return invalid("component");
    }
    for (std::size_t index = 0; index < entrypoints->size(); ++index) {
        const auto* entrypoint = entrypoints->at(index);
        if (entrypoint == nullptr || !exact_members(*entrypoint, {"entrypoint_id", "kind", "relative_path"}) ||
            !bounded_string(*entrypoint, "entrypoint_id", 256) ||
            !safe_relative_path(string_field(*entrypoint, "relative_path")) ||
            (string_field(*entrypoint, "kind") != "application" && string_field(*entrypoint, "kind") != "tool" &&
                string_field(*entrypoint, "kind") != "server")) return invalid("entrypoint");
    }
    const std::filesystem::path expected_state_ref = setup_root.value() / "state" / "installed" /
        (request.install_id + "." + string_field(*state, "transaction_id") + ".json");
    auto supplied_state_ref = absolute_normalized(
        facman::platform::path_from_utf8(request.setup_state_ref), "setup state reference");
    if (!supplied_state_ref || supplied_state_ref.value() != expected_state_ref ||
        request.state_revision != string_field(*state, "transaction_id") + ":" +
            string_field(*state, "ownership_manifest_digest") ||
        !lifecycle_matches(request.lifecycle_status, string_field(*state, "lifecycle_status"))) {
        return invalid("retained record binding");
    }

    auto digest = installed_state_digest(*state);
    if (!digest || !sha256_field(digest.value())) return invalid("installed-state digest");
    InspectedInstallState result;
    result.target = expected_target.take_value();
    result.installed_state_digest = digest.take_value();
    result.ownership_manifest_digest = string_field(*state, "ownership_manifest_digest");
    result.recipe_digest = string_field(*state, "recipe_digest");
    result.source_digest = string_field(*state, "source_archive_digest");
    result.provider_revision = string_field(*abi, "provider_revision");
    return facman::core::Result<InspectedInstallState>::success(std::move(result));
}

facman::core::Result<UninstallPlan> decode_uninstall_plan(
    const std::string& response,
    const UninstallPlanRequest& request,
    const InspectedInstallState& installed,
    const SetupConfiguration& configuration)
{
    const auto invalid = [](const char* detail) {
        return facman::core::Result<UninstallPlan>::failure({
            "setup_uninstall_plan_response_invalid",
            "Universal Setup returned an invalid managed uninstall plan",
            detail});
    };
    facman::core::json::Limits limits;
    limits.maximum_bytes = 64U * 1024U * 1024U;
    limits.maximum_depth = 32;
    limits.maximum_nodes = 1000000;
    limits.maximum_string_bytes = 32768;
    auto document = facman::core::json::parse(response, limits);
    const facman::core::json::Value* payload = nullptr;
    if (!document || !response_envelope(document.value(), payload) ||
        !exact_members(*payload, {"created_at", "effects", "input_identity", "install_id", "operation",
            "plan_digest", "plan_id", "revalidation", "roots", "schema", "status", "target_snapshots",
            "unknown_file_policy"}) ||
        string_field(*payload, "schema") != "usk.operation_plan.v1" ||
        string_field(*payload, "operation") != "uninstall" || string_field(*payload, "status") != "planned" ||
        string_field(*payload, "unknown_file_policy") != "retain_and_report" ||
        string_field(*payload, "install_id") != request.install_id || string_field(*payload, "plan_id") != request.plan_id ||
        string_field(*payload, "created_at") != request.created_at || !bounded_string(*payload, "plan_id", 256) ||
        !bounded_string(*payload, "created_at", 64) || !sha256_field(string_field(*payload, "plan_digest"))) return invalid("envelope");

    const auto* input_identity = payload->find("input_identity");
    const auto* roots = payload->find("roots");
    const auto* effects = payload->find("effects");
    const auto* target_snapshots = payload->find("target_snapshots");
    const auto* revalidation = payload->find("revalidation");
    if (input_identity == nullptr || !exact_members(*input_identity, {"installed_state_digest", "ownership_manifest_digest",
            "policy_digest", "provider_revision", "recipe_digest", "source_digest"}) ||
        string_field(*input_identity, "installed_state_digest") != installed.installed_state_digest ||
        string_field(*input_identity, "ownership_manifest_digest") != installed.ownership_manifest_digest ||
        string_field(*input_identity, "recipe_digest") != installed.recipe_digest ||
        string_field(*input_identity, "source_digest") != installed.source_digest ||
        string_field(*input_identity, "provider_revision") != installed.provider_revision ||
        !sha256_field(string_field(*input_identity, "policy_digest")) || !bounded_string(*input_identity, "provider_revision", 256) ||
        roots == nullptr || !roots->is_array() || roots->size() != 4 || effects == nullptr || !effects->is_array() ||
        effects->size() < 3 || target_snapshots == nullptr || !exact_members(*target_snapshots, {"pre_target_digest"}) ||
        !sha256_field(string_field(*target_snapshots, "pre_target_digest")) || revalidation == nullptr ||
        !exact_members(*revalidation, {"immediately_before_apply", "invalidate_on"})) return invalid("required evidence");

    auto setup_root = absolute_normalized(facman::platform::path_from_utf8(configuration.state_root), "setup state root");
    if (!setup_root) return invalid("setup root");
    const std::array<std::tuple<const char*, const char*, std::filesystem::path>, 4> expected_roots {{
        {"current", "managed_install", installed.target},
        {"staging", "setup_owned", setup_root.value() / "staging"},
        {"setup_state", "setup_owned", setup_root.value() / "state"},
        {"audit", "audit_owned", setup_root.value() / "audit"},
    }};
    std::set<std::string> root_roles;
    for (std::size_t index = 0; index < roots->size(); ++index) {
        const auto* root = roots->at(index);
        if (root == nullptr || !exact_members(*root, {"classification", "role", "root"}) ||
            !bounded_string(*root, "role", 32) || !bounded_string(*root, "classification", 64)) return invalid("root entry");
        const std::string role = string_field(*root, "role");
        const auto expected = std::find_if(expected_roots.begin(), expected_roots.end(), [&](const auto& value) {
            return role == std::get<0>(value);
        });
        if (expected == expected_roots.end() || !root_roles.insert(role).second ||
            string_field(*root, "classification") != std::get<1>(*expected) ||
            !normalized_absolute_path(string_field(*root, "root"), std::get<2>(*expected))) return invalid("root binding");
    }

    std::set<std::string> effect_ids;
    std::set<std::string> write_kinds;
    for (std::size_t index = 0; index < effects->size(); ++index) {
        const auto* effect = effects->at(index);
        if (effect == nullptr || !effect->is_object() || !bounded_string(*effect, "effect_id", 256) ||
            !bounded_string(*effect, "kind", 32) || !bounded_string(*effect, "root_role", 32) ||
            !safe_relative_path(string_field(*effect, "relative_path")) || !effect_ids.insert(string_field(*effect, "effect_id")).second) {
            return invalid("effect entry");
        }
        const auto* ownership = effect->find("ownership_required");
        if (ownership == nullptr || !ownership->is_bool() || !ownership->bool_value().value()) return invalid("effect ownership");
        const std::string kind = string_field(*effect, "kind");
        const std::string root_role = string_field(*effect, "root_role");
        const auto* digest = effect->find("expected_sha256");
        const bool has_digest = digest != nullptr;
        if (has_digest && (!digest->is_string() || !sha256_field(string_field(*effect, "expected_sha256")))) return invalid("effect digest");
        if (kind == "delete_owned_file") {
            if (!has_digest || root_role != "current" || !exact_members(*effect, {"effect_id", "expected_sha256", "kind", "ownership_required", "relative_path", "root_role"})) return invalid("delete effect");
        } else if (kind == "retain_path") {
            if (root_role != "current" || !(exact_members(*effect, {"effect_id", "kind", "ownership_required", "relative_path", "root_role"}) ||
                exact_members(*effect, {"effect_id", "expected_sha256", "kind", "ownership_required", "relative_path", "root_role"}))) return invalid("retain effect");
        } else if (kind == "write_journal" || kind == "write_state" || kind == "write_audit") {
            const char* expected_role = kind == "write_audit" ? "audit" : "setup_state";
            const char* expected_path = kind == "write_journal" ? "transactions" : kind == "write_state" ? "installed" : "chains";
            if (has_digest || root_role != expected_role || string_field(*effect, "relative_path") != expected_path ||
                !exact_members(*effect, {"effect_id", "kind", "ownership_required", "relative_path", "root_role"}) ||
                !write_kinds.insert(kind).second) return invalid("state effect");
        } else return invalid("effect kind");
    }
    if (write_kinds.size() != 3) return invalid("required state effects");

    const auto* immediate = revalidation->find("immediately_before_apply");
    const auto* invalidators = revalidation->find("invalidate_on");
    if (immediate == nullptr || !immediate->is_bool() || !immediate->bool_value().value() || invalidators == nullptr ||
        !invalidators->is_array() || invalidators->size() != 5) return invalid("revalidation");
    const std::set<std::string> expected_invalidators {"target", "installed_state", "ownership_manifest", "policy", "provider_revision"};
    std::set<std::string> actual_invalidators;
    for (std::size_t index = 0; index < invalidators->size(); ++index) {
        const auto* value = invalidators->at(index);
        if (value == nullptr || !bounded_value_string(*value, 32)) return invalid("revalidation item");
        auto text = value->string_value();
        if (!text) return invalid("revalidation item");
        actual_invalidators.insert(text.value());
    }
    if (actual_invalidators != expected_invalidators) return invalid("revalidation set");

    UninstallPlan result;
    result.plan_id = string_field(*payload, "plan_id");
    result.plan_digest = string_field(*payload, "plan_digest");
    result.provider_response = payload->serialize();
    return facman::core::Result<UninstallPlan>::success(std::move(result));
}

facman::core::Error provider_error(
    const facman::core::Error& fallback,
    const char* default_code,
    const char* default_message)
{
    auto document = facman::core::json::parse(fallback.detail);
    const auto* error = document && document.value().is_object()
        ? document.value().find("error")
        : nullptr;
    const std::string code = error != nullptr && error->is_object()
        ? string_field(*error, "code")
        : std::string();
    const std::string message = error != nullptr && error->is_object()
        ? string_field(*error, "message")
        : std::string();
    facman::core::Error result {
        code.empty() ? default_code : code,
        message.empty() ? default_message : message,
        "",
        facman::core::OutcomeKind::refused};
    result.detail = fallback.detail;
    return result;
}

facman::core::Result<facman::factorio::setup::ArchiveInspection> decode_archive_inspection(
    const std::string& response)
{
    facman::core::json::Limits limits;
    limits.maximum_bytes = 64U * 1024U * 1024U;
    limits.maximum_depth = 16;
    limits.maximum_nodes = 1000000;
    limits.maximum_string_bytes = 4096;
    auto document = facman::core::json::parse(response, limits);
    const auto* report = document && document.value().is_object()
        ? document.value().find("payload")
        : nullptr;
    if (!document || string_field(document.value(), "status") != "ok" ||
        report == nullptr || !report->is_object() ||
        string_field(*report, "schema") != "usk.archive_inspection.v1" ||
        string_field(*report, "status") != "pass" ||
        string_field(*report, "normalization_policy") != "ascii_case_insensitive_v1") {
        return facman::core::Result<facman::factorio::setup::ArchiveInspection>::failure({
            "setup_archive_response_invalid",
            "Universal Setup returned an invalid archive inspection envelope",
            ""});
    }
    const auto* source = report->find("source");
    const auto* totals = report->find("totals");
    const auto* entries = report->find("entries");
    const auto* problems = report->find("problems");
    if (source == nullptr || !source->is_object() ||
        string_field(*source, "schema") != "usk.source.v1" ||
        string_field(*source, "kind") != "local_archive" ||
        string_field(*source, "archive_format") != "zip" ||
        totals == nullptr || !totals->is_object() ||
        entries == nullptr || !entries->is_array() || entries->size() == 0 ||
        problems == nullptr || !problems->is_array() || problems->size() != 0) {
        return facman::core::Result<facman::factorio::setup::ArchiveInspection>::failure({
            "setup_archive_response_invalid",
            "Universal Setup archive inspection fields are incomplete",
            ""});
    }
    const auto* stable = source->find("stable_read");
    if (stable == nullptr || !stable->is_bool()) {
        return facman::core::Result<facman::factorio::setup::ArchiveInspection>::failure({
            "setup_archive_response_invalid",
            "Universal Setup did not bind stable archive identity",
            ""});
    }
    auto stable_value = stable->bool_value();
    if (!stable_value || !stable_value.value()) {
        return facman::core::Result<facman::factorio::setup::ArchiveInspection>::failure({
            "setup_archive_response_invalid",
            "Universal Setup did not prove a stable archive read",
            ""});
    }

    const auto unsigned_field = [](const facman::core::json::Value& object, const char* key) {
        const auto* field = object.find(key);
        return field == nullptr
            ? facman::core::Result<std::uint64_t>::failure({"json_field_missing", key, ""})
            : field->unsigned_integer_value();
    };
    auto file_count = unsigned_field(*totals, "file_count");
    auto directory_count = unsigned_field(*totals, "directory_count");
    auto uncompressed_bytes = unsigned_field(*totals, "uncompressed_bytes");
    if (!file_count || !directory_count || !uncompressed_bytes) {
        return facman::core::Result<facman::factorio::setup::ArchiveInspection>::failure({
            "setup_archive_response_invalid",
            "Universal Setup archive totals are invalid",
            ""});
    }

    facman::factorio::setup::ArchiveInspection inspection;
    inspection.archive_sha256 = string_field(*source, "sha256");
    inspection.entry_set_digest = string_field(*report, "entry_set_digest");
    inspection.file_count = file_count.value();
    inspection.directory_count = directory_count.value();
    inspection.uncompressed_bytes = uncompressed_bytes.value();
    inspection.entries.reserve(entries->size());
    for (std::size_t index = 0; index < entries->size(); ++index) {
        const auto* entry = entries->at(index);
        if (entry == nullptr || !entry->is_object()) {
            return facman::core::Result<facman::factorio::setup::ArchiveInspection>::failure({
                "setup_archive_response_invalid",
                "Universal Setup archive entry is invalid",
                ""});
        }
        facman::factorio::setup::ArchiveEntry decoded;
        decoded.normalized_path = string_field(*entry, "normalized_path");
        decoded.entry_type = string_field(*entry, "entry_type");
        if (decoded.normalized_path.empty() || decoded.entry_type.empty()) {
            return facman::core::Result<facman::factorio::setup::ArchiveInspection>::failure({
                "setup_archive_response_invalid",
                "Universal Setup archive entry fields are incomplete",
                ""});
        }
        inspection.entries.push_back(std::move(decoded));
    }
    return facman::core::Result<facman::factorio::setup::ArchiveInspection>::success(
        std::move(inspection));
}

class UskSetupGateway final : public SetupGateway {
public:
    explicit UskSetupGateway(SetupConfiguration configuration)
        : configuration_(std::move(configuration))
    {
    }

    facman::core::Result<PackageVerifyResult> verify_package(const PackageVerifyRequest& request) override
    {
        facman::core::json::ObjectBuilder payload;
        payload.add_string("schema", "usk.package_verify_request.v1");
        payload.add_string("package_root", facman::platform::path_to_utf8(request.package_root));
        payload.add_string("expected_target_os", request.target_os);
        payload.add_string("expected_target_arch", request.target_arch);
        payload.add_string("expected_linkage_model", request.linkage_model);
        auto response = execute_setup("package.verify", payload.serialize(), configuration_);
        if (!response) {
            auto document = facman::core::json::parse(response.error().detail);
            if (document && document.value().is_object()) {
                const auto* provider_error = document.value().find("error");
                if (provider_error != nullptr && provider_error->is_object()) {
                    const std::string code = string_field(*provider_error, "code");
                    const std::string message = string_field(*provider_error, "message");
                    if (!code.empty() && !message.empty()) {
                        facman::core::Error error {
                            code,
                            message,
                            "",
                            facman::core::OutcomeKind::refused};
                        error.detail = response.error().detail;
                        return facman::core::Result<PackageVerifyResult>::failure(std::move(error));
                    }
                }
            }
            return facman::core::Result<PackageVerifyResult>::failure(response.error());
        }
        auto document = facman::core::json::parse(response.value());
        if (!document || !document.value().is_object()) {
            return facman::core::Result<PackageVerifyResult>::failure({"setup_response_invalid", "Universal Setup returned invalid JSON", ""});
        }
        const auto* report = document.value().find("payload");
        if (string_field(document.value(), "status") != "ok" || report == nullptr || !report->is_object()) {
            return facman::core::Result<PackageVerifyResult>::failure({
                "setup_response_invalid",
                "Universal Setup package verification envelope has no successful report payload",
                ""});
        }
        PackageVerifyResult result;
        result.verified = string_field(*report, "integrity") == "pass" &&
            string_field(*report, "compatibility") == "pass" &&
            string_field(*report, "completeness") == "pass" &&
            string_field(*report, "target_match") == "pass";
        result.authenticity = string_field(*report, "authenticity");
        const auto* files = report->find("files_verified");
        if (files != nullptr) {
            auto count = files->unsigned_integer_value();
            if (count) result.files_verified = count.value();
        }
        result.detail = response.take_value();
        return facman::core::Result<PackageVerifyResult>::success(std::move(result));
    }

    facman::core::Result<facman::factorio::setup::ArchiveAssessment> inspect_install_archive(
        const FactorioArchiveInspectRequest& request) override
    {
        auto recipe = facman::factorio::setup::portable_windows_zip_recipe();
        if (!recipe) {
            return facman::core::Result<facman::factorio::setup::ArchiveAssessment>::failure(
                recipe.error());
        }
        facman::core::json::ObjectBuilder budgets;
        budgets.add_unsigned_integer("max_entries", 100000);
        budgets.add_unsigned_integer("max_uncompressed_bytes", 16ULL * 1024ULL * 1024ULL * 1024ULL);
        budgets.add_unsigned_integer("max_entry_bytes", 8ULL * 1024ULL * 1024ULL * 1024ULL);
        budgets.add_unsigned_integer("max_depth", 64);
        budgets.add_unsigned_integer("max_ratio", 1000);
        budgets.add_unsigned_integer("max_elapsed_ms", 120000);
        facman::core::json::ObjectBuilder payload;
        payload.add_string("schema", "usk.archive_inspect_request.v1");
        payload.add_string("archive_path", facman::platform::path_to_utf8(request.archive));
        payload.add_string("archive_format", recipe.value().archive_format);
        payload.add_object("budgets", budgets);
        auto response = execute_setup("install_local.inspect", payload.serialize(), configuration_);
        if (!response) {
            return facman::core::Result<facman::factorio::setup::ArchiveAssessment>::failure(
                provider_error(
                    response.error(),
                    "setup_archive_inspection_refused",
                    "Universal Setup refused Factorio archive inspection"));
        }
        auto inspection = decode_archive_inspection(response.value());
        if (!inspection) {
            return facman::core::Result<facman::factorio::setup::ArchiveAssessment>::failure(
                inspection.error());
        }
        return facman::factorio::setup::assess_portable_archive(
            recipe.value(),
            request.version,
            inspection.value());
    }

    facman::core::Result<InstallPlan> plan_install(const InstallPlanRequest& request) override
    {
        if (request.request_id.empty() || request.install_id.empty() ||
            request.created_at.empty()) {
            return facman::core::Result<InstallPlan>::failure({
                "setup_plan_input_missing",
                "Factorio install planning requires request, install, and timestamp identities",
                ""});
        }
        FactorioArchiveInspectRequest inspection_request;
        inspection_request.version = request.version;
        inspection_request.archive = request.archive;
        auto assessment = inspect_install_archive(inspection_request);
        if (!assessment) {
            return facman::core::Result<InstallPlan>::failure(assessment.error());
        }
        auto recipe = facman::factorio::setup::portable_windows_zip_recipe();
        if (!recipe) return facman::core::Result<InstallPlan>::failure(recipe.error());
        auto archive = absolute_normalized(request.archive, "archive");
        if (!archive) return facman::core::Result<InstallPlan>::failure(archive.error());
        auto target = absolute_normalized(request.target, "target");
        if (!target) return facman::core::Result<InstallPlan>::failure(target.error());

        facman::core::json::ObjectBuilder budgets;
        budgets.add_unsigned_integer("max_entries", 100000);
        budgets.add_unsigned_integer("max_uncompressed_bytes", 16ULL * 1024ULL * 1024ULL * 1024ULL);
        budgets.add_unsigned_integer("max_entry_bytes", 8ULL * 1024ULL * 1024ULL * 1024ULL);
        budgets.add_unsigned_integer("max_depth", 64);
        budgets.add_unsigned_integer("max_ratio", 1000);
        budgets.add_unsigned_integer("max_elapsed_ms", 120000);
        facman::core::json::ObjectBuilder archive_binding;
        archive_binding.add_string("path", facman::platform::path_to_utf8(archive.value()));
        archive_binding.add_string("format", recipe.value().archive_format);
        archive_binding.add_string("expected_sha256", assessment.value().archive_sha256);
        archive_binding.add_string("strip_prefix", assessment.value().application_root_prefix);
        archive_binding.add_object("budgets", budgets);
        facman::core::json::ObjectBuilder target_binding;
        target_binding.add_string("root", facman::platform::path_to_utf8(target.value()));
        target_binding.add_string("class", "operator_acceptance");
        facman::core::json::ArrayBuilder components;
        for (const std::string& component : assessment.value().capabilities) {
            components.add_string(component);
        }
        facman::core::json::ObjectBuilder entrypoint;
        entrypoint.add_string("entrypoint_id", "factorio");
        entrypoint.add_string("relative_path", recipe.value().entrypoint);
        entrypoint.add_string("kind", "application");
        facman::core::json::ArrayBuilder entrypoints;
        entrypoints.add_object(entrypoint);
        facman::core::json::ObjectBuilder recipe_binding;
        recipe_binding.add_string("product_id", assessment.value().product_id);
        recipe_binding.add_string("product_version", assessment.value().requested_version);
        recipe_binding.add_string("recipe_digest", assessment.value().recipe_digest);
        recipe_binding.add_string("provider_revision", "facman.factorio.recipe.v1");
        recipe_binding.add_array("components", components);
        recipe_binding.add_array("entrypoints", entrypoints);
        facman::core::json::ObjectBuilder payload;
        payload.add_string("schema", "usk.install_local_plan_request.v1");
        payload.add_string("request_id", request.request_id);
        payload.add_string("created_at", request.created_at);
        payload.add_string("install_id", request.install_id);
        payload.add_object("archive", archive_binding);
        payload.add_object("target", target_binding);
        payload.add_object("recipe", recipe_binding);
        auto response = execute_setup("install_local.plan", payload.serialize(), configuration_);
        if (!response) {
            return facman::core::Result<InstallPlan>::failure(provider_error(
                response.error(),
                "setup_install_plan_refused",
                "Universal Setup refused the target-bound Factorio install plan"));
        }
        facman::core::json::Limits limits;
        limits.maximum_bytes = 64U * 1024U * 1024U;
        limits.maximum_depth = 64;
        limits.maximum_nodes = 1000000;
        limits.maximum_string_bytes = 32U * 1024U * 1024U;
        auto document = facman::core::json::parse(response.value(), limits);
        const auto* provider_plan = document && document.value().is_object()
            ? document.value().find("payload")
            : nullptr;
        const std::string plan_id = provider_plan != nullptr && provider_plan->is_object()
            ? string_field(*provider_plan, "plan_id")
            : std::string();
        const std::string plan_digest = provider_plan != nullptr && provider_plan->is_object()
            ? string_field(*provider_plan, "plan_digest")
            : std::string();
        if (!document || string_field(document.value(), "status") != "ok" ||
            provider_plan == nullptr || !provider_plan->is_object() ||
            string_field(*provider_plan, "schema") != "usk.install_plan.v1" ||
            string_field(*provider_plan, "status") != "planned" ||
            plan_id != request.request_id || plan_digest.size() != 64) {
            return facman::core::Result<InstallPlan>::failure({
                "setup_install_plan_response_invalid",
                "Universal Setup returned an invalid target-bound install plan",
                ""});
        }
        InstallPlan plan;
        plan.archive_inspected = true;
        plan.product_layout_verified = assessment.value().layout_verified;
        plan.inputs_confirmed = true;
        plan.plan_id = plan_id;
        plan.plan_digest = plan_digest;
        plan.provider_response = provider_plan->serialize();
        return facman::core::Result<InstallPlan>::success(std::move(plan));
    }

    facman::core::Result<UninstallPlan> plan_uninstall(
        const UninstallPlanRequest& request) override
    {
        if (request.request_id.empty() || request.plan_id.empty() ||
            request.install_id.empty() || request.created_at.empty() || request.target.empty() ||
            request.setup_state_ref.empty() || request.last_verification_identity.empty() ||
            request.state_revision.empty() || request.lifecycle_status.empty()) {
            return facman::core::Result<UninstallPlan>::failure({
                "setup_uninstall_plan_input_missing",
                "Managed uninstall planning requires request, plan, record evidence, and target bindings",
                ""});
        }
        facman::core::json::ObjectBuilder inspect_payload;
        inspect_payload.add_string("schema", "usk.installed_inspect_request.v1");
        inspect_payload.add_string("request_id", request.request_id + ".inspect");
        inspect_payload.add_string("install_id", request.install_id);
        auto inspected_response = execute_setup(
            "installed.inspect", inspect_payload.serialize(), configuration_);
        if (!inspected_response) {
            return facman::core::Result<UninstallPlan>::failure(provider_error(
                inspected_response.error(),
                "setup_installed_state_inspection_refused",
                "Universal Setup refused the managed installed-state inspection"));
        }
        auto inspected = decode_installed_state(inspected_response.value(), request, configuration_);
        if (!inspected) return facman::core::Result<UninstallPlan>::failure(inspected.error());
        facman::core::json::ObjectBuilder payload;
        payload.add_string("schema", "usk.uninstall_plan_request.v1");
        payload.add_string("request_id", request.request_id);
        payload.add_string("plan_id", request.plan_id);
        payload.add_string("install_id", request.install_id);
        payload.add_string("created_at", request.created_at);
        auto response = execute_setup("uninstall.plan", payload.serialize(), configuration_);
        if (!response) {
            return facman::core::Result<UninstallPlan>::failure(provider_error(
                response.error(),
                "setup_uninstall_plan_refused",
                "Universal Setup refused the managed uninstall plan"));
        }
        return decode_uninstall_plan(response.value(), request, inspected.value(), configuration_);
    }

    facman::core::Result<SetupRefusal> verify_install(const std::string&) override
    {
        return unsupported(
            "live_target_acceptance_required",
            "Managed-target verification authority is unavailable until its separate live-target policy gate passes");
    }
    facman::core::Result<SetupRefusal> repair_install(const std::string&) override
    {
        return unsupported(
            "live_target_acceptance_required",
            "Managed-target repair authority is unavailable until its separate live-target policy gate passes");
    }
    facman::core::Result<SetupRefusal> uninstall_install(const std::string&) override
    {
        return unsupported(
            "live_target_acceptance_required",
            "Managed-target uninstall authority is unavailable until its separate live-target policy gate passes");
    }

private:
    SetupConfiguration configuration_;

    static facman::core::Result<SetupRefusal> unsupported(const char* code, const char* reason)
    {
        return facman::core::Result<SetupRefusal>::success({code, reason});
    }
};
#endif

} // namespace

std::unique_ptr<SetupGateway> make_setup_gateway(const SetupConfiguration& configuration)
{
#if FACMAN_WITH_SETUP
    return std::make_unique<UskSetupGateway>(configuration);
#else
    (void)configuration;
    return std::make_unique<UnavailableSetupGateway>();
#endif
}

} // namespace facman::factorio::application
