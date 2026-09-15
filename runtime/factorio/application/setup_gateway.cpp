// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "setup_gateway.h"

#include "fl_json.h"
#include "fl_file_io.h"
#include "fl_sha256.h"
#include "fl_path_safety.h"

#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdlib>
#include <initializer_list>
#include <map>
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
    facman::core::Result<RepairPlan> plan_repair(const RepairPlanRequest&) override
    {
        return facman::core::Result<RepairPlan>::failure(unavailable_error());
    }
    facman::core::Result<RepairReport> apply_repair(const RepairApplyRequest&) override
    {
        return facman::core::Result<RepairReport>::failure(unavailable_error());
    }
    facman::core::Result<UninstallReport> apply_uninstall(const UninstallApplyRequest&) override
    {
        return facman::core::Result<UninstallReport>::failure(unavailable_error());
    }
    facman::core::Result<UninstallRecoveryInspection> inspect_uninstall_recovery(
        const UninstallRecoveryRequest&) override
    {
        return facman::core::Result<UninstallRecoveryInspection>::failure(unavailable_error());
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
    std::string product_id;
    std::string product_version;
    std::string ownership_manifest_digest;
    std::string ownership_manifest_ref;
    std::string recipe_digest;
    std::string source_digest;
    std::string audit_chain_id;
    std::string provider_revision;
    std::string component_selection;
    std::string entrypoints;
    std::uint64_t setup_abi_major = 0;
    std::uint64_t setup_abi_minor = 0;
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

facman::core::Result<std::string> uninstall_report_digest(
    const facman::core::json::Value& report)
{
    facman::core::json::ObjectBuilder payload;
    for (const char* key : {
            "completed_at", "deleted_owned_files", "install_id", "ownership_manifest_digest",
            "plan_id", "report_id", "retained_changed_owned_files", "retained_directories",
            "retained_unknown_paths", "schema", "source_archive_deleted", "status", "transaction_id"}) {
        const auto* value = report.find(key);
        if (value == nullptr || !payload.add_value(key, *value)) {
            return facman::core::Result<std::string>::failure({
                "setup_uninstall_report_response_invalid",
                "Universal Setup returned an invalid managed uninstall report",
                "report digest input"});
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
        return usk_lifecycle == "installed" || usk_lifecycle == "verified" ||
            usk_lifecycle == "move_pending_acceptance";
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
    result.product_id = string_field(*state, "product_id");
    result.product_version = string_field(*state, "product_version");
    result.ownership_manifest_digest = string_field(*state, "ownership_manifest_digest");
    result.ownership_manifest_ref = string_field(*state, "ownership_manifest_ref");
    result.recipe_digest = string_field(*state, "recipe_digest");
    result.source_digest = string_field(*state, "source_archive_digest");
    result.audit_chain_id = string_field(*state, "audit_chain_id");
    result.provider_revision = string_field(*abi, "provider_revision");
    result.component_selection = components->serialize();
    result.entrypoints = entrypoints->serialize();
    result.setup_abi_major = major_value.value();
    result.setup_abi_minor = minor_value.value();
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

UninstallPlanRequest repair_install_binding(const RepairPlanRequest& request)
{
    UninstallPlanRequest binding;
    binding.request_id = request.request_id;
    binding.plan_id = request.plan_id;
    binding.install_id = request.install_id;
    binding.created_at = request.created_at;
    binding.target = request.target;
    binding.setup_state_ref = request.setup_state_ref;
    binding.last_verification_identity = request.last_verification_identity;
    binding.state_revision = request.state_revision;
    binding.lifecycle_status = request.lifecycle_status;
    return binding;
}

facman::core::Result<RepairPlan> decode_repair_plan(
    const std::string& response,
    const RepairPlanRequest& request,
    const InspectedInstallState& installed,
    const std::string& plan_request)
{
    const auto invalid = [](const char* detail) {
        return facman::core::Result<RepairPlan>::failure({
            "setup_repair_plan_response_invalid",
            "Universal Setup returned an invalid managed repair plan", detail});
    };
    facman::core::json::Limits limits;
    limits.maximum_bytes = 64U * 1024U * 1024U;
    limits.maximum_depth = 32;
    limits.maximum_nodes = 1000000;
    limits.maximum_string_bytes = 32768;
    auto document = facman::core::json::parse(response, limits);
    const facman::core::json::Value* payload = nullptr;
    if (!document || !response_envelope(document.value(), payload) ||
        !exact_members(*payload, {"before_verification_digest", "created_at", "install_id",
            "installed_state_digest", "operation", "ownership_manifest_digest", "plan_digest",
            "plan_id", "pre_target_snapshot_digest", "recipe_digest", "repairs",
            "retained_unknown_paths", "revalidation", "schema", "source_digest", "status"}) ||
        string_field(*payload, "schema") != "usk.repair_plan.v1" ||
        string_field(*payload, "operation") != "repair" ||
        string_field(*payload, "status") != "planned" ||
        string_field(*payload, "install_id") != request.install_id ||
        string_field(*payload, "plan_id") != request.plan_id ||
        string_field(*payload, "created_at") != request.created_at ||
        string_field(*payload, "installed_state_digest") != installed.installed_state_digest ||
        string_field(*payload, "ownership_manifest_digest") != installed.ownership_manifest_digest ||
        string_field(*payload, "recipe_digest") != installed.recipe_digest ||
        string_field(*payload, "source_digest") != installed.source_digest ||
        !sha256_field(string_field(*payload, "plan_digest")) ||
        !sha256_field(string_field(*payload, "before_verification_digest")) ||
        !sha256_field(string_field(*payload, "pre_target_snapshot_digest"))) return invalid("identity envelope");

    const auto* repairs = payload->find("repairs");
    const auto* unknown = payload->find("retained_unknown_paths");
    const auto* revalidation = payload->find("revalidation");
    if (repairs == nullptr || !repairs->is_array() || repairs->size() == 0U ||
        unknown == nullptr || !unknown->is_array() || revalidation == nullptr ||
        !exact_members(*revalidation, {"immediately_before_apply", "invalidate_on"})) {
        return invalid("repair evidence");
    }
    RepairPlan result;
    std::set<std::string> repair_paths;
    for (std::size_t index = 0; index < repairs->size(); ++index) {
        const auto* item = repairs->at(index);
        if (item == nullptr || !exact_members(*item, {"expected_sha256", "reason", "relative_path"}) ||
            !safe_relative_path(string_field(*item, "relative_path")) ||
            !sha256_field(string_field(*item, "expected_sha256")) ||
            (string_field(*item, "reason") != "missing" && string_field(*item, "reason") != "modified" &&
                string_field(*item, "reason") != "wrong_type") ||
            !repair_paths.insert(string_field(*item, "relative_path")).second) return invalid("repair entry");
        result.repairs.push_back({string_field(*item, "relative_path"), string_field(*item, "reason"),
            string_field(*item, "expected_sha256")});
    }
    std::set<std::string> unknown_paths;
    for (std::size_t index = 0; index < unknown->size(); ++index) {
        const auto* item = unknown->at(index);
        if (item == nullptr || !item->is_string()) return invalid("retained unknown path");
        auto path = item->string_value();
        if (!path || !safe_relative_path(path.value()) || !unknown_paths.insert(path.value()).second) {
            return invalid("retained unknown path");
        }
        result.retained_unknown_paths.push_back(path.value());
    }
    const auto* immediate = revalidation->find("immediately_before_apply");
    const auto* invalidators = revalidation->find("invalidate_on");
    if (immediate == nullptr || !immediate->is_bool() || !immediate->bool_value().value() ||
        invalidators == nullptr || !invalidators->is_array() || invalidators->size() != 7U) {
        return invalid("revalidation");
    }
    const std::set<std::string> expected_invalidators {"source", "recipe", "target", "installed_state",
        "ownership_manifest", "policy", "provider_revision"};
    std::set<std::string> actual_invalidators;
    for (std::size_t index = 0; index < invalidators->size(); ++index) {
        const auto* value = invalidators->at(index);
        if (value == nullptr || !value->is_string()) return invalid("revalidation item");
        const auto text = value->string_value();
        if (!text || !actual_invalidators.insert(text.value()).second) return invalid("revalidation item");
    }
    if (actual_invalidators != expected_invalidators) return invalid("revalidation set");
    result.plan_id = string_field(*payload, "plan_id");
    result.provider_plan_digest = string_field(*payload, "plan_digest");
    result.created_at = string_field(*payload, "created_at");
    result.installed_state_digest = string_field(*payload, "installed_state_digest");
    result.ownership_manifest_digest = string_field(*payload, "ownership_manifest_digest");
    result.recipe_digest = string_field(*payload, "recipe_digest");
    result.source_digest = string_field(*payload, "source_digest");
    result.before_verification_digest = string_field(*payload, "before_verification_digest");
    result.pre_target_snapshot_digest = string_field(*payload, "pre_target_snapshot_digest");
    result.plan_request = plan_request;
    result.provider_response = payload->serialize();
    return facman::core::Result<RepairPlan>::success(std::move(result));
}

bool relative_path_array(const facman::core::json::Value* value)
{
    if (value == nullptr || !value->is_array()) return false;
    std::set<std::string> paths;
    for (std::size_t index = 0; index < value->size(); ++index) {
        const auto* item = value->at(index);
        if (item == nullptr || !item->is_string()) return false;
        const auto text = item->string_value();
        if (!text || !safe_relative_path(text.value()) || !paths.insert(text.value()).second) return false;
    }
    return true;
}

facman::core::Result<std::string> repair_report_digest(const facman::core::json::Value& report)
{
    facman::core::json::ObjectBuilder payload;
    for (const char* key : {"after_verification_ref", "before_verification_ref", "completed_at",
            "install_id", "plan_id", "recipe_digest", "repaired_files", "report_id",
            "retained_unknown_paths", "schema", "source_digest", "status", "transaction_id"}) {
        const auto* value = report.find(key);
        if (value == nullptr || !payload.add_value(key, *value)) {
            return facman::core::Result<std::string>::failure({
                "setup_repair_report_response_invalid",
                "Universal Setup returned an invalid managed repair report", "report digest input"});
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

bool repair_report_ref(
    const facman::core::json::Value* value,
    const std::string& expected_id,
    std::string& digest,
    std::string& status)
{
    if (value == nullptr || !exact_members(*value, {"report_digest", "report_id", "status"}) ||
        string_field(*value, "report_id") != expected_id ||
        !sha256_field(string_field(*value, "report_digest")) ||
        (string_field(*value, "status") != "pass" && string_field(*value, "status") != "warn" &&
            string_field(*value, "status") != "fail" && string_field(*value, "status") != "refused")) {
        return false;
    }
    digest = string_field(*value, "report_digest");
    status = string_field(*value, "status");
    return true;
}

facman::core::Result<RepairReport> decode_repair_report(
    const std::string& response,
    const RepairApplyRequest& request)
{
    const auto invalid = [](const char* detail) {
        return facman::core::Result<RepairReport>::failure({
            "setup_repair_report_response_invalid",
            "Universal Setup returned an invalid managed repair report", detail});
    };
    facman::core::json::Limits limits;
    limits.maximum_bytes = 64U * 1024U * 1024U;
    limits.maximum_depth = 32;
    limits.maximum_nodes = 1000000;
    limits.maximum_string_bytes = 32768;
    auto document = facman::core::json::parse(response, limits);
    const facman::core::json::Value* report = nullptr;
    if (!document || !response_envelope(document.value(), report) ||
        !exact_members(*report, {"after_verification_ref", "before_verification_ref", "completed_at",
            "install_id", "plan_id", "recipe_digest", "repaired_files", "report_digest", "report_id",
            "retained_unknown_paths", "schema", "source_digest", "status", "transaction_id"}) ||
        string_field(*report, "schema") != "usk.repair_report.v1" ||
        string_field(*report, "status") != "completed" ||
        string_field(*report, "install_id") != request.plan_request.install_id ||
        string_field(*report, "plan_id") != request.reviewed_plan.plan_id ||
        string_field(*report, "transaction_id") != request.transaction_id ||
        string_field(*report, "report_id") != "repair." + request.transaction_id ||
        string_field(*report, "completed_at") != request.applied_at ||
        string_field(*report, "recipe_digest") != request.reviewed_plan.recipe_digest ||
        string_field(*report, "source_digest") != request.reviewed_plan.source_digest ||
        !valid_utc_seconds(string_field(*report, "completed_at")) ||
        !sha256_field(string_field(*report, "report_digest"))) return invalid("identity envelope");
    std::string before_digest;
    std::string before_status;
    std::string after_digest;
    std::string after_status;
    if (!repair_report_ref(report->find("before_verification_ref"),
            "verify." + request.transaction_id + ".before", before_digest, before_status) ||
        !repair_report_ref(report->find("after_verification_ref"),
            "verify." + request.transaction_id + ".after", after_digest, after_status) ||
        before_status != "fail" || (after_status != "pass" && after_status != "warn")) {
        return invalid("verification references");
    }
    const auto* repaired = report->find("repaired_files");
    if (repaired == nullptr || !repaired->is_array() ||
        repaired->size() != request.reviewed_plan.repairs.size() ||
        !relative_path_array(report->find("retained_unknown_paths"))) return invalid("effect report");
    std::set<std::string> reported_unknown;
    const auto* unknown = report->find("retained_unknown_paths");
    for (std::size_t index = 0; index < unknown->size(); ++index) {
        reported_unknown.insert(unknown->at(index)->string_value().value());
    }
    if (reported_unknown != std::set<std::string>(
            request.reviewed_plan.retained_unknown_paths.begin(),
            request.reviewed_plan.retained_unknown_paths.end())) return invalid("retained unknown binding");
    std::map<std::string, RepairFile> expected;
    for (const auto& item : request.reviewed_plan.repairs) expected.emplace(item.relative_path, item);
    std::set<std::string> observed;
    for (std::size_t index = 0; index < repaired->size(); ++index) {
        const auto* item = repaired->at(index);
        if (item == nullptr || !exact_members(*item, {"prior_status", "relative_path", "sha256"}) ||
            !safe_relative_path(string_field(*item, "relative_path")) ||
            !sha256_field(string_field(*item, "sha256")) ||
            !observed.insert(string_field(*item, "relative_path")).second) return invalid("repaired file");
        const auto found = expected.find(string_field(*item, "relative_path"));
        if (found == expected.end() || string_field(*item, "prior_status") != found->second.reason ||
            string_field(*item, "sha256") != found->second.expected_sha256) return invalid("repaired file binding");
    }
    auto digest = repair_report_digest(*report);
    if (!digest || digest.value() != string_field(*report, "report_digest")) return invalid("report digest");
    RepairReport result;
    result.report_id = string_field(*report, "report_id");
    result.report_digest = string_field(*report, "report_digest");
    result.completed_at = string_field(*report, "completed_at");
    result.last_verification_identity = after_digest;
    result.verification_status = after_status;
    result.provider_response = report->serialize();
    return facman::core::Result<RepairReport>::success(std::move(result));
}

facman::core::Result<UninstallReport> decode_uninstall_report(
    const std::string& response,
    const UninstallApplyRequest& request,
    const InspectedInstallState& installed)
{
    const auto invalid = [](const char* detail) {
        return facman::core::Result<UninstallReport>::failure({
            "setup_uninstall_report_response_invalid",
            "Universal Setup returned an invalid managed uninstall report", detail});
    };
    facman::core::json::Limits limits;
    limits.maximum_bytes = 4U * 1024U * 1024U;
    limits.maximum_depth = 32;
    limits.maximum_nodes = 100000;
    limits.maximum_string_bytes = 32768;
    auto document = facman::core::json::parse(response, limits);
    const facman::core::json::Value* report = nullptr;
    if (!document || !response_envelope(document.value(), report) ||
        !exact_members(*report, {"completed_at", "deleted_owned_files", "install_id",
            "ownership_manifest_digest", "plan_id", "report_digest", "report_id",
            "retained_changed_owned_files", "retained_directories", "retained_unknown_paths",
            "schema", "source_archive_deleted", "status", "transaction_id"}) ||
        string_field(*report, "schema") != "usk.uninstall_report.v1" ||
        (string_field(*report, "status") != "completed" &&
            string_field(*report, "status") != "retained_foreign_content") ||
        string_field(*report, "install_id") != request.plan_request.install_id ||
        string_field(*report, "plan_id") != request.reviewed_plan_id ||
        string_field(*report, "transaction_id") != request.transaction_id ||
        string_field(*report, "report_id") != "uninstall." + request.transaction_id ||
        string_field(*report, "ownership_manifest_digest") != installed.ownership_manifest_digest ||
        string_field(*report, "completed_at") != request.applied_at ||
        !bounded_string(*report, "report_id", 256) || !sha256_field(string_field(*report, "report_digest")) ||
        !valid_utc_seconds(string_field(*report, "completed_at"))) return invalid("identity envelope");
    const auto* source_archive_deleted = report->find("source_archive_deleted");
    const auto* retained_changed = report->find("retained_changed_owned_files");
    const auto* retained_unknown = report->find("retained_unknown_paths");
    const auto* retained_directories = report->find("retained_directories");
    if (source_archive_deleted == nullptr || !source_archive_deleted->is_bool() ||
        source_archive_deleted->bool_value().value() ||
        !relative_path_array(report->find("deleted_owned_files")) ||
        !relative_path_array(retained_changed) || !relative_path_array(retained_unknown) ||
        !relative_path_array(retained_directories)) return invalid("effect report");
    const std::size_t retained_count = retained_changed->size() + retained_unknown->size() +
        retained_directories->size();
    if ((string_field(*report, "status") == "completed" && retained_count != 0U) ||
        (string_field(*report, "status") == "retained_foreign_content" && retained_count == 0U)) {
        return invalid("status effects");
    }
    auto digest = uninstall_report_digest(*report);
    if (!digest || digest.value() != string_field(*report, "report_digest")) {
        return invalid("report digest");
    }
    UninstallReport result;
    result.report_id = string_field(*report, "report_id");
    result.report_digest = string_field(*report, "report_digest");
    result.status = string_field(*report, "status");
    result.completed_at = string_field(*report, "completed_at");
    result.ownership_manifest_digest = string_field(*report, "ownership_manifest_digest");
    result.provider_response = report->serialize();
    return facman::core::Result<UninstallReport>::success(std::move(result));
}

facman::core::Result<UninstallReport> bind_uninstall_terminal_state(
    const std::string& response,
    const UninstallApplyRequest& request,
    const InspectedInstallState& before,
    const SetupConfiguration& configuration,
    UninstallReport report)
{
    const auto invalid = [](const char* detail) {
        return facman::core::Result<UninstallReport>::failure({
            "setup_uninstall_terminal_state_response_invalid",
            "Universal Setup returned an invalid terminal installed-state response",
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
        string_field(*state, "install_id") != request.plan_request.install_id ||
        string_field(*state, "transaction_id") != request.transaction_id ||
        string_field(*state, "created_at") != request.applied_at ||
        string_field(*state, "product_id") != before.product_id ||
        string_field(*state, "product_version") != before.product_version ||
        string_field(*state, "ownership_manifest_digest") != report.ownership_manifest_digest ||
        string_field(*state, "ownership_manifest_ref") != before.ownership_manifest_ref ||
        string_field(*state, "recipe_digest") != before.recipe_digest ||
        string_field(*state, "source_archive_digest") != before.source_digest ||
        string_field(*state, "audit_chain_id") != before.audit_chain_id ||
        !sha256_field(string_field(*state, "recipe_digest")) ||
        !sha256_field(string_field(*state, "source_archive_digest"))) return invalid("state envelope");

    const std::string expected_lifecycle = report.status == "completed" ? "retired" : "uninstall_blocked";
    const std::string expected_verification = report.status == "completed" ? "pass" : "warn";
    if (string_field(*state, "lifecycle_status") != expected_lifecycle) return invalid("lifecycle status");
    auto expected_target = absolute_normalized(request.plan_request.target, "target");
    auto setup_root = absolute_normalized(
        facman::platform::path_from_utf8(configuration.state_root), "setup state root");
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
        !components->is_array() || components->size() == 0 ||
        !entrypoints->is_array() || entrypoints->size() == 0 ||
        !sha256_field(string_field(*verification, "report_digest")) ||
        string_field(*verification, "report_id") != "verify." + request.transaction_id + ".uninstall" ||
        string_field(*verification, "status") != expected_verification ||
        string_field(*verification, "verified_at") != request.applied_at ||
        string_field(*abi, "provider_revision") != before.provider_revision) return invalid("terminal evidence");
    const auto* major = abi->find("major");
    const auto* minor = abi->find("minor");
    if (major == nullptr || minor == nullptr || !major->unsigned_integer_value() ||
        !minor->unsigned_integer_value() || major->unsigned_integer_value().value() == 0) {
        return invalid("setup ABI");
    }
    if (major->unsigned_integer_value().value() != before.setup_abi_major ||
        minor->unsigned_integer_value().value() != before.setup_abi_minor ||
        components->serialize() != before.component_selection ||
        entrypoints->serialize() != before.entrypoints) return invalid("immutable installed-state binding");
    for (std::size_t index = 0; index < components->size(); ++index) {
        const auto* component = components->at(index);
        if (component == nullptr || !component->is_string() ||
            component->string_value().value().empty() || component->string_value().value().size() > 256) {
            return invalid("component");
        }
    }
    for (std::size_t index = 0; index < entrypoints->size(); ++index) {
        const auto* entrypoint = entrypoints->at(index);
        if (entrypoint == nullptr ||
            !exact_members(*entrypoint, {"entrypoint_id", "kind", "relative_path"}) ||
            !bounded_string(*entrypoint, "entrypoint_id", 256) ||
            !safe_relative_path(string_field(*entrypoint, "relative_path")) ||
            (string_field(*entrypoint, "kind") != "application" &&
                string_field(*entrypoint, "kind") != "tool" &&
                string_field(*entrypoint, "kind") != "server")) return invalid("entrypoint");
    }

    const std::filesystem::path state_ref = setup_root.value() / "state" / "installed" /
        (request.plan_request.install_id + "." + request.transaction_id + ".json");
    report.setup_state_ref = facman::platform::path_to_utf8(state_ref);
    report.last_verification_identity = string_field(*verification, "report_digest");
    report.state_revision = request.transaction_id + ":" + report.ownership_manifest_digest;
    report.lifecycle_status = report.status == "completed" ? "uninstalled" : "verification_failed";
    report.verification_status = expected_verification;
    report.audit_chain_id = string_field(*state, "audit_chain_id");
    auto state_digest = installed_state_digest(*state);
    if (!state_digest) return invalid("installed-state digest");
    report.installed_state_digest = state_digest.take_value();
    return facman::core::Result<UninstallReport>::success(std::move(report));
}

facman::core::Result<RepairReport> bind_repair_terminal_state(
    const std::string& response,
    const RepairApplyRequest& request,
    const InspectedInstallState& before,
    const SetupConfiguration& configuration,
    RepairReport report)
{
    const auto invalid = [](const char* detail) {
        return facman::core::Result<RepairReport>::failure({
            "setup_repair_terminal_state_response_invalid",
            "Universal Setup returned an invalid terminal repair installed state", detail});
    };
    facman::core::json::Limits limits;
    limits.maximum_bytes = 4U * 1024U * 1024U;
    limits.maximum_depth = 32;
    limits.maximum_nodes = 100000;
    limits.maximum_string_bytes = 32768;
    auto document = facman::core::json::parse(response, limits);
    const facman::core::json::Value* state = nullptr;
    const std::string expected_ownership_ref = "ownership/ownership." +
        request.plan_request.install_id + "." + request.transaction_id + ".json";
    if (!document || !response_envelope(document.value(), state) ||
        !exact_members(*state, {"audit_chain_id", "component_selection", "created_at", "entrypoints",
            "install_id", "last_verification", "lifecycle_status", "ownership_manifest_digest",
            "ownership_manifest_ref", "product_id", "product_version", "recipe_digest", "schema",
            "setup_abi", "source_archive_digest", "target_root", "target_scope", "transaction_id"}) ||
        string_field(*state, "schema") != "usk.installed_state.v1" ||
        string_field(*state, "target_scope") != "portable" ||
        string_field(*state, "install_id") != request.plan_request.install_id ||
        string_field(*state, "transaction_id") != request.transaction_id ||
        string_field(*state, "created_at") != request.applied_at ||
        string_field(*state, "lifecycle_status") != "verified" ||
        string_field(*state, "product_id") != before.product_id ||
        string_field(*state, "product_version") != before.product_version ||
        string_field(*state, "ownership_manifest_ref") != expected_ownership_ref ||
        string_field(*state, "recipe_digest") != before.recipe_digest ||
        string_field(*state, "source_archive_digest") != before.source_digest ||
        string_field(*state, "audit_chain_id") != before.audit_chain_id ||
        !sha256_field(string_field(*state, "ownership_manifest_digest"))) return invalid("state envelope");
    auto expected_target = absolute_normalized(request.plan_request.target, "target");
    auto setup_root = absolute_normalized(
        facman::platform::path_from_utf8(configuration.state_root), "setup state root");
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
        string_field(*verification, "report_id") != "verify." + request.transaction_id + ".after" ||
        string_field(*verification, "report_digest") != report.last_verification_identity ||
        string_field(*verification, "status") != report.verification_status ||
        string_field(*verification, "verified_at") != request.applied_at ||
        !exact_members(*abi, {"major", "minor", "provider_revision"}) ||
        string_field(*abi, "provider_revision") != before.provider_revision ||
        !components->is_array() || components->serialize() != before.component_selection ||
        !entrypoints->is_array() || entrypoints->serialize() != before.entrypoints) return invalid("terminal evidence");
    const auto* major = abi->find("major");
    const auto* minor = abi->find("minor");
    if (major == nullptr || minor == nullptr || !major->unsigned_integer_value() ||
        !minor->unsigned_integer_value() || major->unsigned_integer_value().value() != before.setup_abi_major ||
        minor->unsigned_integer_value().value() != before.setup_abi_minor) return invalid("setup ABI");
    report.ownership_manifest_digest = string_field(*state, "ownership_manifest_digest");
    report.setup_state_ref = facman::platform::path_to_utf8(setup_root.value() / "state" / "installed" /
        (request.plan_request.install_id + "." + request.transaction_id + ".json"));
    report.state_revision = request.transaction_id + ":" + report.ownership_manifest_digest;
    report.lifecycle_status = "active";
    auto state_digest = installed_state_digest(*state);
    if (!state_digest) return invalid("installed-state digest");
    report.installed_state_digest = state_digest.take_value();
    return facman::core::Result<RepairReport>::success(std::move(report));
}

facman::core::Result<std::string> read_provider_snapshot(const std::filesystem::path& path)
{
    facman::platform::StableInputFile input;
    auto opened = input.open_no_follow(path);
    if (!opened.ok() || !input.identity().regular_file || input.size() > 4U * 1024U * 1024U) {
        return facman::core::Result<std::string>::failure({
            "setup_uninstall_recovery_response_invalid",
            "Universal Setup prior installed-state snapshot is unavailable or unsafe",
            opened.ok() ? facman::platform::path_to_utf8(path) : opened.detail});
    }
    std::string text(static_cast<std::size_t>(input.size()), '\0');
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t count = input.read_at(
            offset, text.data() + static_cast<std::size_t>(offset),
            static_cast<std::size_t>(input.size() - offset));
        if (count == 0U) return facman::core::Result<std::string>::failure({
            "setup_uninstall_recovery_response_invalid",
            "Universal Setup prior installed-state snapshot could not be read stably", "short read"});
        offset += count;
    }
    auto stable = input.revalidate();
    if (!stable.ok()) return facman::core::Result<std::string>::failure({
        "setup_uninstall_recovery_response_invalid",
        "Universal Setup prior installed-state snapshot changed during inspection", stable.detail});
    return facman::core::Result<std::string>::success(std::move(text));
}

facman::core::Result<InspectedInstallState> decode_prior_installed_snapshot(
    const UninstallPlanRequest& request,
    const SetupConfiguration& configuration)
{
    auto expected_root = absolute_normalized(
        facman::platform::path_from_utf8(configuration.state_root), "setup state root");
    auto supplied = absolute_normalized(
        facman::platform::path_from_utf8(request.setup_state_ref), "setup state reference");
    if (!expected_root || !supplied || supplied.value().parent_path() !=
            expected_root.value() / "state" / "installed") {
        return facman::core::Result<InspectedInstallState>::failure({
            "setup_uninstall_recovery_response_invalid",
            "Prior installed-state snapshot is outside the configured provider authority", "state reference"});
    }
    auto text = read_provider_snapshot(supplied.value());
    if (!text) return facman::core::Result<InspectedInstallState>::failure(text.error());
    facman::core::json::Limits limits;
    limits.maximum_bytes = 4U * 1024U * 1024U;
    limits.maximum_depth = 32;
    limits.maximum_nodes = 100000;
    limits.maximum_string_bytes = 32768;
    auto state = facman::core::json::parse(text.value(), limits);
    if (!state || !state.value().is_object()) return facman::core::Result<InspectedInstallState>::failure({
        "setup_uninstall_recovery_response_invalid",
        "Prior installed-state snapshot is invalid", "JSON"});
    auto canonical = facman::core::json::canonical_integer_json(state.value());
    if (!canonical || (canonical.value() + "\n" != text.value() &&
            canonical.value() + "\r\n" != text.value())) {
        return facman::core::Result<InspectedInstallState>::failure({
            "setup_uninstall_recovery_response_invalid",
            "Prior installed-state snapshot is not canonical", "canonical JSON"});
    }
    facman::core::json::ObjectBuilder envelope;
    envelope.add_null("error");
    envelope.add_value("payload", state.value());
    envelope.add_string("schema", "usk.command_response.v1");
    envelope.add_string("status", "ok");
    auto decoded = decode_installed_state(envelope.serialize(), request, configuration);
    if (!decoded) return facman::core::Result<InspectedInstallState>::failure({
        "setup_uninstall_recovery_response_invalid",
        "Prior installed-state snapshot failed exact recovery binding",
        decoded.error().code + ": " + decoded.error().message});
    return decoded;
}

facman::core::Result<std::string> recovery_report_digest(
    const facman::core::json::Value& report)
{
    facman::core::json::ObjectBuilder payload;
    for (const char* key : {"audit_chain_digest", "audit_chain_id", "available_actions", "effects",
            "journal_digest", "journal_id", "journal_snapshot_sha256", "observed_state", "recorded_at",
            "report_id", "schema", "selected_action", "status", "transaction_id"}) {
        const auto* value = report.find(key);
        if (value == nullptr || !payload.add_value(key, *value)) {
            return facman::core::Result<std::string>::failure({
                "setup_uninstall_recovery_response_invalid",
                "Universal Setup returned an invalid uninstall recovery report", "digest input"});
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

facman::core::Error provider_error(
    const facman::core::Error& fallback,
    const char* default_code,
    const char* default_message)
{
    facman::core::json::Limits limits;
    limits.maximum_bytes = 4U * 1024U * 1024U;
    limits.maximum_depth = 8;
    limits.maximum_nodes = 128;
    limits.maximum_string_bytes = 32768;
    auto document = facman::core::json::parse(fallback.detail, limits);
    const auto* error = document &&
            exact_members(document.value(), {"error", "payload", "schema", "status"}) &&
            string_field(document.value(), "schema") == "usk.command_response.v1" &&
            (string_field(document.value(), "status") == "refused" ||
             string_field(document.value(), "status") == "invalid_argument")
        ? document.value().find("error")
        : nullptr;
    const auto* payload = document && document.value().is_object()
        ? document.value().find("payload")
        : nullptr;
    const bool exact_refusal = error != nullptr && payload != nullptr && payload->is_null() &&
        exact_members(*error, {"code", "message"}) &&
        bounded_string(*error, "code", 128) && bounded_string(*error, "message", 32768);
    const std::string code = exact_refusal ? string_field(*error, "code") : std::string();
    const std::string message = exact_refusal ? string_field(*error, "message") : std::string();
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

    facman::core::Result<RepairPlan> plan_repair(
        const RepairPlanRequest& request) override
    {
        if (request.request_id.empty() || request.request_id != request.plan_id ||
            request.install_id.empty() || request.created_at.empty() || request.version.empty() ||
            request.archive.empty() || request.target.empty() || request.setup_state_ref.empty() ||
            request.last_verification_identity.empty() || request.state_revision.empty() ||
            request.lifecycle_status.empty() || !valid_utc_seconds(request.created_at)) {
            return facman::core::Result<RepairPlan>::failure({
                "setup_repair_plan_input_invalid",
                "Managed repair planning requires exact archive, plan, and installed-record bindings", ""});
        }
        const UninstallPlanRequest binding = repair_install_binding(request);
        facman::core::json::ObjectBuilder inspect_payload;
        inspect_payload.add_string("schema", "usk.installed_inspect_request.v1");
        inspect_payload.add_string("request_id", request.request_id + ".inspect");
        inspect_payload.add_string("install_id", request.install_id);
        auto inspected_response = execute_setup("installed.inspect", inspect_payload.serialize(), configuration_);
        if (!inspected_response) return facman::core::Result<RepairPlan>::failure(provider_error(
            inspected_response.error(), "setup_installed_state_inspection_refused",
            "Universal Setup refused managed installed-state inspection before repair planning"));
        auto installed = decode_installed_state(inspected_response.value(), binding, configuration_);
        if (!installed) return facman::core::Result<RepairPlan>::failure(installed.error());

        FactorioArchiveInspectRequest archive_request;
        archive_request.version = request.version;
        archive_request.archive = request.archive;
        auto assessment = inspect_install_archive(archive_request);
        if (!assessment) return facman::core::Result<RepairPlan>::failure(assessment.error());
        if (assessment.value().archive_sha256 != installed.value().source_digest) {
            return facman::core::Result<RepairPlan>::failure({
                "source_drift", "Repair requires the exact archive bound by installed state", "archive sha256"});
        }
        auto archive = absolute_normalized(request.archive, "archive");
        if (!archive) return facman::core::Result<RepairPlan>::failure(archive.error());
        facman::core::json::ObjectBuilder archive_binding;
        archive_binding.add_string("path", facman::platform::path_to_utf8(archive.value()));
        archive_binding.add_string("format", "zip");
        archive_binding.add_string("expected_sha256", assessment.value().archive_sha256);
        archive_binding.add_string("strip_prefix", assessment.value().application_root_prefix);
        facman::core::json::ObjectBuilder payload;
        payload.add_string("schema", "usk.repair_plan_request.v1");
        payload.add_string("request_id", request.request_id);
        payload.add_string("plan_id", request.plan_id);
        payload.add_string("install_id", request.install_id);
        payload.add_string("created_at", request.created_at);
        payload.add_object("archive", archive_binding);
        const std::string plan_request = payload.serialize();
        auto response = execute_setup("repair.plan", plan_request, configuration_);
        if (!response) return facman::core::Result<RepairPlan>::failure(provider_error(
            response.error(), "setup_repair_plan_refused",
            "Universal Setup refused the ownership-bounded repair plan"));
        return decode_repair_plan(response.value(), request, installed.value(), plan_request);
    }

    facman::core::Result<RepairReport> apply_repair(
        const RepairApplyRequest& request) override
    {
        const RepairPlanRequest& plan = request.plan_request;
        if (plan.request_id != plan.plan_id || plan.plan_id != request.reviewed_plan.plan_id ||
            !sha256_field(request.reviewed_plan.provider_plan_digest) || request.transaction_id.empty() ||
            request.confirmation != "APPLY" || !valid_utc_seconds(plan.created_at) ||
            !valid_utc_seconds(request.applied_at) || request.applied_at <= plan.created_at ||
            request.reviewed_plan.plan_request.empty() || request.reviewed_plan.provider_response.empty()) {
            return facman::core::Result<RepairReport>::failure({
                "setup_repair_apply_input_invalid",
                "Managed repair apply requires the exact reviewed provider plan and stable replay identities", ""});
        }
        const UninstallPlanRequest binding = repair_install_binding(plan);
        facman::core::json::ObjectBuilder inspect_payload;
        inspect_payload.add_string("schema", "usk.installed_inspect_request.v1");
        inspect_payload.add_string("request_id", plan.request_id + ".apply.inspect");
        inspect_payload.add_string("install_id", plan.install_id);
        auto inspected_response = execute_setup("installed.inspect", inspect_payload.serialize(), configuration_);
        if (!inspected_response) return facman::core::Result<RepairReport>::failure(provider_error(
            inspected_response.error(), "setup_installed_state_inspection_refused",
            "Universal Setup refused managed installed-state inspection before repair apply"));
        auto installed = decode_installed_state(inspected_response.value(), binding, configuration_);
        if (!installed) return facman::core::Result<RepairReport>::failure(installed.error());
        auto plan_request = facman::core::json::parse(request.reviewed_plan.plan_request);
        if (!plan_request || !plan_request.value().is_object()) {
            return facman::core::Result<RepairReport>::failure({
                "setup_repair_apply_input_invalid", "Managed repair plan request is invalid", "plan_request"});
        }
        facman::core::json::ObjectBuilder payload;
        payload.add_string("schema", "usk.repair_apply_request.v1");
        payload.add_value("plan_request", plan_request.value());
        payload.add_string("reviewed_plan_id", request.reviewed_plan.plan_id);
        const char* inject_stale_plan = std::getenv("FACMAN_TEST_REPAIR_PROVIDER_STALE_PLAN");
        payload.add_string(
            "reviewed_plan_digest",
            inject_stale_plan != nullptr && std::string(inject_stale_plan) == "1"
                ? std::string(64, '0')
                : request.reviewed_plan.provider_plan_digest);
        payload.add_string("transaction_id", request.transaction_id);
        payload.add_string("applied_at", request.applied_at);
        payload.add_string("confirmation", request.confirmation);
        auto response = execute_setup("repair.apply", payload.serialize(), configuration_, false);
        if (!response) return facman::core::Result<RepairReport>::failure(provider_error(
            response.error(), "setup_repair_apply_refused",
            "Universal Setup repair outcome requires recovery inspection"));
        auto report = decode_repair_report(response.value(), request);
        if (!report) return report;
        facman::core::json::ObjectBuilder terminal_payload;
        terminal_payload.add_string("schema", "usk.installed_inspect_request.v1");
        terminal_payload.add_string("request_id", plan.request_id + ".apply.terminal.inspect");
        const char* inject_terminal_unknown =
            std::getenv("FACMAN_TEST_REPAIR_TERMINAL_UNKNOWN_INSTALL");
        terminal_payload.add_string(
            "install_id",
            inject_terminal_unknown != nullptr && std::string(inject_terminal_unknown) == "1"
                ? plan.install_id + "-missing"
                : plan.install_id);
        auto terminal_response = execute_setup("installed.inspect", terminal_payload.serialize(), configuration_);
        if (!terminal_response) {
            const auto provider = provider_error(
                terminal_response.error(), "setup_repair_terminal_state_inspection_refused",
                "Universal Setup terminal installed-state inspection failed after repair");
            facman::core::Error terminal_error {
                "setup_repair_terminal_state_inspection_refused",
                "Universal Setup terminal installed-state inspection failed after repair: " +
                    provider.code + ": " + provider.message,
                "",
                facman::core::OutcomeKind::recovery_required};
            terminal_error.detail = terminal_response.error().detail;
            return facman::core::Result<RepairReport>::failure(std::move(terminal_error));
        }
        auto terminal = bind_repair_terminal_state(
            terminal_response.value(), request, installed.value(), configuration_, report.take_value());
        if (!terminal) {
            facman::core::Error terminal_error {
                "setup_repair_terminal_state_response_invalid",
                "Universal Setup terminal installed state failed repair post-effect validation: " +
                    terminal.error().code + ": " + terminal.error().message,
                terminal.error().path,
                facman::core::OutcomeKind::recovery_required};
            terminal_error.detail = terminal.error().detail;
            return facman::core::Result<RepairReport>::failure(std::move(terminal_error));
        }
        return terminal;
    }

    facman::core::Result<UninstallReport> apply_uninstall(
        const UninstallApplyRequest& request) override
    {
        const UninstallPlanRequest& plan = request.plan_request;
        if (plan.request_id != plan.plan_id || plan.request_id != request.reviewed_plan_id ||
            plan.install_id.empty() || !sha256_field(request.reviewed_plan_digest) ||
            request.transaction_id.empty() || request.confirmation != "APPLY" ||
            !valid_utc_seconds(plan.created_at) || !valid_utc_seconds(request.applied_at) ||
            request.applied_at <= plan.created_at) {
            return facman::core::Result<UninstallReport>::failure({
                "setup_uninstall_apply_input_invalid",
                "Managed uninstall apply requires the exact reviewed plan request and stable replay identities", ""});
        }
        // Re-read and bind the current installed state before entering the provider.
        facman::core::json::ObjectBuilder inspect_payload;
        inspect_payload.add_string("schema", "usk.installed_inspect_request.v1");
        inspect_payload.add_string("request_id", plan.request_id + ".apply.inspect");
        inspect_payload.add_string("install_id", plan.install_id);
        auto inspected_response = execute_setup("installed.inspect", inspect_payload.serialize(), configuration_);
        if (!inspected_response) return facman::core::Result<UninstallReport>::failure(provider_error(
            inspected_response.error(), "setup_installed_state_inspection_refused",
            "Universal Setup refused managed installed-state inspection before uninstall"));
        auto installed = decode_installed_state(inspected_response.value(), plan, configuration_);
        if (!installed) return facman::core::Result<UninstallReport>::failure(installed.error());

        facman::core::json::ObjectBuilder plan_payload;
        plan_payload.add_string("schema", "usk.uninstall_plan_request.v1");
        plan_payload.add_string("request_id", plan.request_id);
        plan_payload.add_string("plan_id", plan.plan_id);
        plan_payload.add_string("install_id", plan.install_id);
        plan_payload.add_string("created_at", plan.created_at);
        facman::core::json::ObjectBuilder payload;
        payload.add_string("schema", "usk.uninstall_apply_request.v1");
        payload.add_object("plan_request", plan_payload);
        payload.add_string("reviewed_plan_id", request.reviewed_plan_id);
        payload.add_string("reviewed_plan_digest", request.reviewed_plan_digest);
        payload.add_string("transaction_id", request.transaction_id);
        payload.add_string("applied_at", request.applied_at);
        payload.add_string("confirmation", request.confirmation);
        auto response = execute_setup("uninstall.apply", payload.serialize(), configuration_, false);
        if (!response) return facman::core::Result<UninstallReport>::failure(provider_error(
            response.error(), "setup_uninstall_apply_refused",
            "Universal Setup refused the managed uninstall apply"));
        auto report = decode_uninstall_report(response.value(), request, installed.value());
        if (!report) return report;
        facman::core::json::ObjectBuilder terminal_inspect_payload;
        terminal_inspect_payload.add_string("schema", "usk.installed_inspect_request.v1");
        terminal_inspect_payload.add_string("request_id", plan.request_id + ".apply.terminal.inspect");
        const char* inject_terminal_unknown =
            std::getenv("FACMAN_TEST_UNINSTALL_TERMINAL_UNKNOWN_INSTALL");
        terminal_inspect_payload.add_string(
            "install_id",
            inject_terminal_unknown != nullptr && std::string(inject_terminal_unknown) == "1"
                ? plan.install_id + "-missing"
                : plan.install_id);
        auto terminal_response = execute_setup(
            "installed.inspect", terminal_inspect_payload.serialize(), configuration_);
        if (!terminal_response) {
            const auto provider = provider_error(
                terminal_response.error(), "setup_uninstall_terminal_state_inspection_refused",
                "Universal Setup terminal installed-state inspection failed after uninstall");
            facman::core::Error terminal_error {
                "setup_uninstall_terminal_state_inspection_refused",
                "Universal Setup terminal installed-state inspection failed after uninstall: " +
                    provider.code + ": " + provider.message,
                "",
                facman::core::OutcomeKind::recovery_required};
            terminal_error.detail = terminal_response.error().detail;
            return facman::core::Result<UninstallReport>::failure(std::move(terminal_error));
        }
        return bind_uninstall_terminal_state(
            terminal_response.value(), request, installed.value(), configuration_, report.take_value());
    }

    facman::core::Result<UninstallRecoveryInspection> inspect_uninstall_recovery(
        const UninstallRecoveryRequest& request) override
    {
        const UninstallPlanRequest& plan = request.plan_request;
        if (plan.request_id != plan.plan_id || plan.install_id.empty() ||
            !sha256_field(request.reviewed_plan_digest) || request.transaction_id.empty() ||
            !valid_utc_seconds(plan.created_at) || !valid_utc_seconds(request.applied_at) ||
            request.applied_at <= plan.created_at || !configuration_.mutation_configured()) {
            return facman::core::Result<UninstallRecoveryInspection>::failure({
                "setup_uninstall_recovery_input_invalid",
                "Managed uninstall recovery requires exact coordinator and provider identities", ""});
        }
        auto setup_root = absolute_normalized(
            facman::platform::path_from_utf8(configuration_.state_root), "setup state root");
        auto install_target = absolute_normalized(plan.target, "target");
        if (!setup_root || !install_target) return facman::core::Result<UninstallRecoveryInspection>::failure({
            "setup_uninstall_recovery_input_invalid",
            "Managed uninstall recovery roots are invalid", ""});
        const std::filesystem::path provider_journal = setup_root.value() / "state" /
            "transactions" / (request.transaction_id + ".journal.json");
        const auto journal_presence = [&]() -> int {
            std::error_code error;
            const auto status = std::filesystem::symlink_status(provider_journal, error);
            if (error == std::errc::no_such_file_or_directory) return 0;
            if (error || std::filesystem::is_symlink(status) ||
                (std::filesystem::exists(status) && !std::filesystem::is_regular_file(status))) return -1;
            return std::filesystem::exists(status) ? 1 : 0;
        };
        const auto target_presence = [&]() -> int {
            std::error_code error;
            const auto status = std::filesystem::symlink_status(install_target.value(), error);
            if (error == std::errc::no_such_file_or_directory) return 0;
            if (error) return -1;
            if (!std::filesystem::exists(status)) return 0;
            std::string unsafe;
            if (!std::filesystem::is_directory(status) ||
                facman::base::path_crosses_link_or_reparse_point(install_target.value(), unsafe)) return -1;
            return 1;
        };

        const int initial_journal = journal_presence();
        if (initial_journal < 0) return facman::core::Result<UninstallRecoveryInspection>::failure({
            "setup_uninstall_recovery_response_invalid",
            "Universal Setup uninstall journal is unsafe", facman::platform::path_to_utf8(provider_journal)});
        if (initial_journal == 0) {
            facman::core::json::ObjectBuilder inspect_payload;
            inspect_payload.add_string("schema", "usk.installed_inspect_request.v1");
            inspect_payload.add_string("request_id", plan.plan_id + ".recovery.pre.inspect");
            inspect_payload.add_string("install_id", plan.install_id);
            auto current_response = execute_setup("installed.inspect", inspect_payload.serialize(), configuration_);
            if (!current_response) return facman::core::Result<UninstallRecoveryInspection>::failure(
                wrap_uninstall_recovery_inspection_refusal(
                    current_response.error(),
                    "Universal Setup refused pre-effect uninstall recovery inspection"));
            auto current = decode_installed_state(current_response.value(), plan, configuration_);
            if (!current) return facman::core::Result<UninstallRecoveryInspection>::failure({
                "setup_uninstall_recovery_response_invalid",
                "Current installed state failed exact no-effect recovery binding",
                current.error().code + ": " + current.error().message});
            const int target = target_presence();
            if (journal_presence() != 0 || target != 1) {
                UninstallRecoveryInspection result;
                result.classification = "indeterminate";
                result.target_exists = target == 1;
                result.provider_installed_state_digest = current.value().installed_state_digest;
                return facman::core::Result<UninstallRecoveryInspection>::success(std::move(result));
            }
            UninstallRecoveryInspection result;
            result.classification = "no_provider_effect";
            result.target_exists = true;
            result.provider_installed_state_digest = current.value().installed_state_digest;
            result.ownership_manifest_digest = current.value().ownership_manifest_digest;
            result.setup_state_ref = plan.setup_state_ref;
            result.last_verification_identity = plan.last_verification_identity;
            result.state_revision = plan.state_revision;
            result.lifecycle_status = plan.lifecycle_status;
            return facman::core::Result<UninstallRecoveryInspection>::success(std::move(result));
        }

        std::string journal_unsafe;
        if (facman::base::path_crosses_link_or_reparse_point(provider_journal, journal_unsafe)) {
            return facman::core::Result<UninstallRecoveryInspection>::failure({
                "setup_uninstall_recovery_response_invalid",
                "Universal Setup uninstall journal path is redirected", journal_unsafe});
        }
        const std::filesystem::path provider_target = install_target.value().parent_path() /
            (".usk-uninstall-" + request.transaction_id);
        facman::core::json::ObjectBuilder payload;
        payload.add_string("schema", "usk.recovery_inspect_request.v1");
        payload.add_string("request_id", plan.plan_id + ".facman.recovery.inspect");
        payload.add_string("install_id", plan.install_id);
        payload.add_string("transaction_id", request.transaction_id);
        payload.add_string("plan_id", plan.plan_id);
        payload.add_string("plan_digest", request.reviewed_plan_digest);
        payload.add_string("operation", "uninstall");
        payload.add_string("target_root", facman::platform::path_to_utf8(provider_target));
        auto provider_response = execute_setup("recovery.inspect", payload.serialize(), configuration_);
        if (!provider_response) return facman::core::Result<UninstallRecoveryInspection>::failure(
            wrap_uninstall_recovery_inspection_refusal(
                provider_response.error(),
                "Universal Setup refused uninstall recovery inspection"));
        auto provider = decode_uninstall_provider_recovery_report(provider_response.value(), request);
        if (!provider) return facman::core::Result<UninstallRecoveryInspection>::failure(provider.error());
        UninstallRecoveryInspection result;
        result.provider_journal_present = true;
        result.provider_observed_state = provider.value().observed_state;
        result.provider_journal_digest = provider.value().journal_digest;
        result.provider_journal_snapshot_sha256 = provider.value().snapshot_sha256;
        result.target_exists = target_presence() == 1;
        if (provider.value().observed_state != "completed") {
            result.classification = "indeterminate";
            return facman::core::Result<UninstallRecoveryInspection>::success(std::move(result));
        }

        auto before = decode_prior_installed_snapshot(plan, configuration_);
        if (!before) return facman::core::Result<UninstallRecoveryInspection>::failure(before.error());
        facman::core::json::ObjectBuilder terminal_payload;
        terminal_payload.add_string("schema", "usk.installed_inspect_request.v1");
        terminal_payload.add_string("request_id", plan.plan_id + ".recovery.terminal.inspect");
        const char* inject_terminal_unknown =
            std::getenv("FACMAN_TEST_UNINSTALL_TERMINAL_UNKNOWN_INSTALL");
        terminal_payload.add_string(
            "install_id",
            inject_terminal_unknown != nullptr && std::string(inject_terminal_unknown) == "1"
                ? plan.install_id + "-missing"
                : plan.install_id);
        auto terminal_response = execute_setup("installed.inspect", terminal_payload.serialize(), configuration_);
        if (!terminal_response) return facman::core::Result<UninstallRecoveryInspection>::failure(
            wrap_uninstall_recovery_inspection_refusal(
                terminal_response.error(),
                "Universal Setup refused terminal uninstall recovery inspection"));
        auto terminal_document = facman::core::json::parse(terminal_response.value());
        const facman::core::json::Value* terminal_state = nullptr;
        if (!terminal_document || !response_envelope(terminal_document.value(), terminal_state)) {
            return facman::core::Result<UninstallRecoveryInspection>::failure({
                "setup_uninstall_recovery_response_invalid",
                "Universal Setup terminal recovery state is invalid", "envelope"});
        }
        const std::string provider_lifecycle = string_field(*terminal_state, "lifecycle_status");
        UninstallReport terminal_seed;
        terminal_seed.status = provider_lifecycle == "retired" ? "completed" :
            provider_lifecycle == "uninstall_blocked" ? "retained_foreign_content" : "";
        terminal_seed.ownership_manifest_digest = before.value().ownership_manifest_digest;
        if (terminal_seed.status.empty()) return facman::core::Result<UninstallRecoveryInspection>::failure({
            "setup_uninstall_recovery_response_invalid",
            "Universal Setup recovery state is not a terminal uninstall state", provider_lifecycle});
        UninstallApplyRequest terminal_request;
        terminal_request.plan_request = plan;
        terminal_request.reviewed_plan_id = plan.plan_id;
        terminal_request.reviewed_plan_digest = request.reviewed_plan_digest;
        terminal_request.transaction_id = request.transaction_id;
        terminal_request.applied_at = request.applied_at;
        terminal_request.confirmation = "APPLY";
        auto terminal = bind_uninstall_terminal_state(
            terminal_response.value(), terminal_request, before.value(), configuration_, std::move(terminal_seed));
        if (!terminal || terminal.value().audit_chain_id != provider.value().audit_chain_id ||
            provider.value().audit_chain_digest.empty()) {
            return facman::core::Result<UninstallRecoveryInspection>::failure(terminal ? facman::core::Error{
                "setup_uninstall_recovery_response_invalid",
                "Universal Setup terminal state does not bind the completed recovery journal", "audit chain"}
                : facman::core::Error{
                    "setup_uninstall_recovery_response_invalid",
                    "Universal Setup terminal state failed exact recovery binding",
                    terminal.error().code + ": " + terminal.error().message});
        }
        const int target = target_presence();
        if (target < 0 || (provider_lifecycle == "retired" && target != 0) ||
            (provider_lifecycle == "uninstall_blocked" && target != 1)) {
            result.classification = "indeterminate";
            result.target_exists = target == 1;
            return facman::core::Result<UninstallRecoveryInspection>::success(std::move(result));
        }
        result.classification = provider_lifecycle == "retired" ?
            "provider_retired" : "provider_uninstall_blocked";
        result.target_exists = target == 1;
        result.provider_installed_state_digest = terminal.value().installed_state_digest;
        result.ownership_manifest_digest = terminal.value().ownership_manifest_digest;
        result.setup_state_ref = terminal.value().setup_state_ref;
        result.last_verification_identity = terminal.value().last_verification_identity;
        result.state_revision = terminal.value().state_revision;
        result.lifecycle_status = terminal.value().lifecycle_status;
        result.verification_status = terminal.value().verification_status;
        return facman::core::Result<UninstallRecoveryInspection>::success(std::move(result));
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

#if FACMAN_WITH_SETUP
facman::core::Result<ManagedRepairEnvelope> encode_managed_repair_envelope(
    const RepairPlan& plan,
    const std::string& install_record_sha256)
{
    auto plan_request = facman::core::json::parse(plan.plan_request);
    auto provider_plan = facman::core::json::parse(plan.provider_response);
    if (!plan_request || !provider_plan || !plan_request.value().is_object() ||
        !provider_plan.value().is_object() || install_record_sha256.size() != 64U) {
        return facman::core::Result<ManagedRepairEnvelope>::failure({
            "setup_repair_plan_response_invalid", "Managed repair plan cannot be bound", "plan envelope"});
    }
    const auto body = [&](const std::string& digest) {
        facman::core::json::ObjectBuilder document;
        document.add_string("schema", "factorio.managed_repair_plan.v1");
        document.add_string("command", "installs.repair.plan");
        document.add_string(
            "install_id", plan_request.value().find("install_id")->string_value().value());
        document.add_string("plan_id", plan.plan_id);
        if (!digest.empty()) document.add_string("plan_digest", digest);
        document.add_string("created_at", plan.created_at);
        document.add_string("install_record_sha256", install_record_sha256);
        document.add_value("plan_request", plan_request.value());
        document.add_value("provider_plan", provider_plan.value());
        return document.serialize();
    };
    auto document = facman::core::json::parse(body(""));
    if (!document) return facman::core::Result<ManagedRepairEnvelope>::failure(document.error());
    auto canonical = facman::core::json::canonical_integer_json(document.value());
    if (!canonical) return facman::core::Result<ManagedRepairEnvelope>::failure(canonical.error());
    ManagedRepairEnvelope result;
    result.digest = facman::base::sha256_hex_bytes(
        reinterpret_cast<const std::uint8_t*>(canonical.value().data()), canonical.value().size());
    document = facman::core::json::parse(body(result.digest));
    if (!document) return facman::core::Result<ManagedRepairEnvelope>::failure(document.error());
    canonical = facman::core::json::canonical_integer_json(document.value());
    if (!canonical) return facman::core::Result<ManagedRepairEnvelope>::failure(canonical.error());
    result.document = canonical.take_value();
    return facman::core::Result<ManagedRepairEnvelope>::success(std::move(result));
}

std::string encode_managed_repair_context(
    const RepairPlanRequest& plan,
    const RepairPlan& provider_plan,
    const std::string& reviewed_plan_id,
    const std::string& reviewed_plan_digest,
    const std::string& transaction_id,
    const std::string& applied_at,
    const std::string& target,
    const std::string& pre_record_digest,
    const std::string& phase,
    const RepairReport* report,
    const std::string& projected_record_digest)
{
    auto plan_request = facman::core::json::parse(provider_plan.plan_request);
    auto provider_plan_document = facman::core::json::parse(provider_plan.provider_response);
    facman::core::json::ObjectBuilder document;
    document.add_string("schema", "facman.managed_repair_coordinator.v1");
    if (plan_request && plan_request.value().is_object()) {
        document.add_value("plan_request", plan_request.value());
    }
    if (provider_plan_document && provider_plan_document.value().is_object()) {
        document.add_value("provider_plan", provider_plan_document.value());
    }
    document.add_string("reviewed_plan_id", reviewed_plan_id);
    document.add_string("reviewed_plan_digest", reviewed_plan_digest);
    document.add_string("provider_plan_digest", provider_plan.provider_plan_digest);
    document.add_string("transaction_id", transaction_id);
    document.add_string("applied_at", applied_at);
    document.add_string("target_root", target);
    document.add_string("pre_record_sha256", pre_record_digest);
    document.add_string("pre_setup_state_ref", plan.setup_state_ref);
    document.add_string("pre_last_verification_identity", plan.last_verification_identity);
    document.add_string("pre_state_revision", plan.state_revision);
    document.add_string("pre_lifecycle_status", plan.lifecycle_status);
    document.add_string("phase", phase);
    if (report != nullptr) {
        document.add_string("provider_report_sha256", report->report_digest);
        document.add_string("provider_installed_state_sha256", report->installed_state_digest);
        document.add_string("post_setup_state_ref", report->setup_state_ref);
        document.add_string(
            "post_last_verification_identity", report->last_verification_identity);
        document.add_string("post_state_revision", report->state_revision);
        document.add_string("post_verification_status", report->verification_status);
        document.add_string("projected_record_sha256", projected_record_digest);
    }
    return document.serialize();
}

std::string project_repaired_install_record(
    const std::string& record_text,
    const RepairReport& report)
{
    auto current = facman::core::json::parse(record_text);
    if (!current || !current.value().is_object()) return {};
    facman::core::json::ObjectBuilder terminal;
    for (const std::string& key : current.value().object_keys()) {
        const auto* value = current.value().find(key);
        if (value == nullptr) return {};
        if (key == "setup_state_ref") terminal.add_string(key, report.setup_state_ref);
        else if (key == "lifecycle_status") terminal.add_string(key, report.lifecycle_status);
        else if (key == "last_verification_identity") {
            terminal.add_string(key, report.last_verification_identity);
        } else if (key == "state_revision") terminal.add_string(key, report.state_revision);
        else if (key == "verification") {
            if (!value->is_object()) return {};
            facman::core::json::ObjectBuilder verification;
            for (const std::string& verification_key : value->object_keys()) {
                const auto* verification_value = value->find(verification_key);
                if (verification_value == nullptr) return {};
                if (verification_key == "status") {
                    verification.add_string(verification_key, report.verification_status);
                } else if (!verification.add_value(verification_key, *verification_value)) return {};
            }
            terminal.add_object(key, verification);
        } else if (!terminal.add_value(key, *value)) return {};
    }
    return terminal.serialize();
}

facman::core::Result<RepairReport> decode_repair_provider_report(
    const std::string& response,
    const RepairApplyRequest& request)
{
    return decode_repair_report(response, request);
}

facman::core::Result<UninstallProviderRecoveryReport>
decode_uninstall_provider_recovery_report(
    const std::string& response,
    const UninstallRecoveryRequest& request)
{
    const auto invalid = [](const char* detail) {
        return facman::core::Result<UninstallProviderRecoveryReport>::failure({
            "setup_uninstall_recovery_response_invalid",
            "Universal Setup returned an invalid uninstall recovery inspection", detail});
    };
    facman::core::json::Limits limits;
    limits.maximum_bytes = 4U * 1024U * 1024U;
    limits.maximum_depth = 32;
    limits.maximum_nodes = 100000;
    limits.maximum_string_bytes = 32768;
    auto document = facman::core::json::parse(response, limits);
    const facman::core::json::Value* report = nullptr;
    const std::string expected_report_id =
        "recovery.inspect." + request.plan_request.plan_id + ".facman.recovery.inspect";
    if (!document || !response_envelope(document.value(), report) ||
        !exact_members(*report, {"audit_chain_digest", "audit_chain_id", "available_actions", "effects",
            "journal_digest", "journal_id", "journal_snapshot_sha256", "observed_state", "recorded_at",
            "report_digest", "report_id", "schema", "selected_action", "status", "transaction_id"}) ||
        string_field(*report, "schema") != "usk.recovery_report.v1" ||
        string_field(*report, "status") != "inspection_only" ||
        string_field(*report, "report_id") != expected_report_id ||
        string_field(*report, "transaction_id") != request.transaction_id ||
        string_field(*report, "journal_id") != "journal." + request.transaction_id ||
        !sha256_field(string_field(*report, "journal_digest")) ||
        !sha256_field(string_field(*report, "journal_snapshot_sha256")) ||
        !sha256_field(string_field(*report, "report_digest")) ||
        !bounded_string(*report, "report_id", 32768) ||
        !bounded_string(*report, "audit_chain_id", 32768) ||
        !valid_utc_seconds(string_field(*report, "recorded_at"))) return invalid("identity envelope");

    static const std::set<std::string> states {
        "created", "validated", "planned", "staging", "staged", "verified",
        "committing", "committed", "completed", "refused", "failed",
        "recovery_required", "rolled_back", "abandoned_by_operator"};
    static const std::set<std::string> action_values {
        "resume", "rollback", "accept_new_root", "retain_for_operator", "abandon"};
    static const std::set<std::string> effect_kinds {
        "resume_transition", "delete_staged_path", "restore_owned_file", "retain_path",
        "write_state", "write_audit"};
    static const std::set<std::string> root_classes {
        "owned_target", "staging", "setup_state", "audit"};
    if (states.count(string_field(*report, "observed_state")) != 1U) {
        return invalid("observed state");
    }
    const auto* selected_action = report->find("selected_action");
    const auto* actions = report->find("available_actions");
    const auto* effects = report->find("effects");
    const auto* audit_digest = report->find("audit_chain_digest");
    if (selected_action == nullptr || !selected_action->is_null() || actions == nullptr ||
        !actions->is_array() || effects == nullptr || !effects->is_array() || audit_digest == nullptr ||
        (!audit_digest->is_null() && (!audit_digest->is_string() ||
            !sha256_field(audit_digest->string_value().value())))) return invalid("recovery evidence");
    std::set<std::string> unique_actions;
    for (std::size_t index = 0; index < actions->size(); ++index) {
        const auto* action = actions->at(index);
        if (action == nullptr || !action->is_string()) return invalid("available action");
        const std::string value = action->string_value().value();
        if (action_values.count(value) != 1U || !unique_actions.insert(value).second) {
            return invalid("available action");
        }
    }
    for (std::size_t index = 0; index < effects->size(); ++index) {
        const auto* effect = effects->at(index);
        if (effect == nullptr || !exact_members(*effect, {"kind", "relative_path", "root_class"}) ||
            effect_kinds.count(string_field(*effect, "kind")) != 1U ||
            root_classes.count(string_field(*effect, "root_class")) != 1U ||
            !bounded_string(*effect, "relative_path", 4096U)) {
            return invalid("effect");
        }
    }
    auto digest = recovery_report_digest(*report);
    if (!digest || digest.value() != string_field(*report, "report_digest")) {
        return invalid("report digest");
    }
    UninstallProviderRecoveryReport result;
    result.observed_state = string_field(*report, "observed_state");
    result.journal_digest = string_field(*report, "journal_digest");
    result.snapshot_sha256 = string_field(*report, "journal_snapshot_sha256");
    result.audit_chain_id = string_field(*report, "audit_chain_id");
    if (!audit_digest->is_null()) result.audit_chain_digest = audit_digest->string_value().value();
    return facman::core::Result<UninstallProviderRecoveryReport>::success(std::move(result));
}

facman::core::Error wrap_uninstall_recovery_inspection_refusal(
    const facman::core::Error& provider,
    const std::string& message)
{
    const facman::core::Error nested = provider_error(
        provider, "setup_provider_refused", "Universal Setup refused the recovery inspection");
    facman::core::Error result {
        "setup_uninstall_recovery_inspection_refused",
        message,
        "",
        facman::core::OutcomeKind::refused};
    result.detail = "provider_code: " + nested.code +
        "\nprovider_message: " + nested.message +
        "\nprovider_envelope: " + provider.detail;
    return result;
}

bool decode_managed_uninstall_coordinator(
    const std::string& text,
    ManagedUninstallCoordinator& output,
    std::string& detail)
{
    facman::core::json::Limits limits;
    limits.maximum_bytes = 1024U * 1024U;
    limits.maximum_depth = 12;
    limits.maximum_nodes = 128;
    limits.maximum_string_bytes = 32768;
    auto document = facman::core::json::parse(text, limits);
    if (!document || !document.value().is_object()) {
        detail = "managed uninstall coordinator JSON is invalid";
        return false;
    }
    const auto& value = document.value();
    output.schema = string_field(value, "schema");
    const bool v1 = output.schema == "facman.managed_uninstall_coordinator.v1";
    const bool pending_v2 = output.schema == "facman.managed_uninstall_coordinator.v2" &&
        string_field(value, "phase") == "provider_entry_pending";
    const bool prepared_v2 = output.schema == "facman.managed_uninstall_coordinator.v2" &&
        string_field(value, "phase") == "terminal_projection_prepared";
    if ((v1 && !exact_members(value, {"applied_at", "phase", "plan_request", "pre_record_sha256",
            "reviewed_plan_digest", "reviewed_plan_id", "schema", "target_root", "transaction_id"})) ||
        (pending_v2 && !exact_members(value, {"applied_at", "phase", "plan_request",
            "pre_last_verification_identity", "pre_lifecycle_status", "pre_record_sha256",
            "pre_setup_state_ref", "pre_state_revision", "reviewed_plan_digest", "reviewed_plan_id",
            "schema", "target_root", "transaction_id"})) ||
        (prepared_v2 && !exact_members(value, {"applied_at", "classification", "phase", "plan_request",
            "pre_last_verification_identity", "pre_lifecycle_status", "pre_record_sha256",
            "pre_setup_state_ref", "pre_state_revision", "projected_record_sha256",
            "provider_installed_state_sha256", "provider_journal_snapshot_sha256",
            "recovery_plan_digest", "recovery_plan_id", "reviewed_plan_digest", "reviewed_plan_id",
            "schema", "target_root", "transaction_id"})) ||
        (!v1 && !pending_v2 && !prepared_v2)) {
        detail = "managed uninstall coordinator members or phase are invalid";
        return false;
    }
    const auto* plan = value.find("plan_request");
    if (plan == nullptr || !exact_members(*plan,
            {"created_at", "install_id", "plan_id", "request_id", "schema"}) ||
        string_field(*plan, "schema") != "usk.uninstall_plan_request.v1") {
        detail = "managed uninstall coordinator plan request is invalid";
        return false;
    }
    output.request_id = string_field(*plan, "request_id");
    output.plan_id = string_field(*plan, "plan_id");
    output.install_id = string_field(*plan, "install_id");
    output.plan_created_at = string_field(*plan, "created_at");
    output.reviewed_plan_digest = string_field(value, "reviewed_plan_digest");
    output.transaction_id = string_field(value, "transaction_id");
    output.applied_at = string_field(value, "applied_at");
    output.target_root = string_field(value, "target_root");
    output.pre_record_sha256 = string_field(value, "pre_record_sha256");
    output.pre_setup_state_ref = string_field(value, "pre_setup_state_ref");
    output.pre_last_verification_identity = string_field(value, "pre_last_verification_identity");
    output.pre_state_revision = string_field(value, "pre_state_revision");
    output.pre_lifecycle_status = string_field(value, "pre_lifecycle_status");
    output.phase = string_field(value, "phase");
    output.recovery_plan_id = string_field(value, "recovery_plan_id");
    output.recovery_plan_digest = string_field(value, "recovery_plan_digest");
    output.classification = string_field(value, "classification");
    output.provider_journal_snapshot_sha256 = string_field(value, "provider_journal_snapshot_sha256");
    output.provider_installed_state_sha256 = string_field(value, "provider_installed_state_sha256");
    output.projected_record_sha256 = string_field(value, "projected_record_sha256");
    if (output.request_id != output.plan_id || output.plan_id != string_field(value, "reviewed_plan_id") ||
        output.plan_id.empty() || output.plan_id.size() > 128U || output.install_id.empty() ||
        !valid_utc_seconds(output.plan_created_at) ||
        !valid_utc_seconds(output.applied_at) || output.applied_at <= output.plan_created_at ||
        !sha256_field(output.reviewed_plan_digest) || !sha256_field(output.pre_record_sha256) ||
        output.transaction_id.empty() || output.target_root.empty()) {
        detail = "managed uninstall coordinator identity is invalid";
        return false;
    }
    const std::size_t revision_separator = output.pre_state_revision.rfind(':');
    if (!v1 && (output.pre_setup_state_ref.empty() ||
            !sha256_field(output.pre_last_verification_identity) ||
            revision_separator == std::string::npos ||
            !sha256_field(output.pre_state_revision.substr(revision_separator + 1U)) ||
            (output.pre_lifecycle_status != "active" &&
             output.pre_lifecycle_status != "verification_failed" &&
             output.pre_lifecycle_status != "recovery_required"))) {
        detail = "managed uninstall coordinator preimage evidence is invalid";
        return false;
    }
    if (prepared_v2 && (((!output.recovery_plan_id.empty() || !output.recovery_plan_digest.empty()) &&
            (output.recovery_plan_id.empty() || !sha256_field(output.recovery_plan_digest))) ||
            !sha256_field(output.provider_installed_state_sha256) ||
            !sha256_field(output.projected_record_sha256) ||
            (output.classification != "no_provider_effect" &&
             output.classification != "provider_retired" &&
             output.classification != "provider_uninstall_blocked") ||
            (output.classification == "no_provider_effect"
                ? !output.provider_journal_snapshot_sha256.empty()
                : !sha256_field(output.provider_journal_snapshot_sha256)))) {
        detail = "managed uninstall terminal projection checkpoint is invalid";
        return false;
    }
    return true;
}

bool validate_managed_uninstall_recovery_lock(
    const std::string& text,
    const std::string& transaction_id,
    const std::string& identity,
    std::string& detail)
{
    facman::core::json::Limits limits;
    limits.maximum_bytes = 4096U;
    limits.maximum_depth = 4;
    limits.maximum_nodes = 8;
    limits.maximum_string_bytes = 1024U;
    auto metadata = facman::core::json::parse(text, limits);
    if (!metadata || !exact_members(metadata.value(), {"identity", "schema", "transaction_id"}) ||
        string_field(metadata.value(), "schema") != "facman.managed_uninstall_recovery_lock.v1" ||
        string_field(metadata.value(), "transaction_id") != transaction_id ||
        string_field(metadata.value(), "identity") != identity) {
        detail = "uninstall recovery lock metadata does not match its OS-backed owner";
        return false;
    }
    return true;
}

facman::core::Result<std::string> canonicalize_managed_uninstall_recovery_plan(
    const std::string& text)
{
    facman::core::json::Limits limits;
    limits.maximum_bytes = 1024U * 1024U;
    limits.maximum_depth = 12;
    limits.maximum_nodes = 128;
    limits.maximum_string_bytes = 32768;
    auto document = facman::core::json::parse(text, limits);
    if (!document) return facman::core::Result<std::string>::failure({
        "recovery_journal_invalid", "Recovery plan could not be parsed", document.error().detail});
    auto canonical = facman::core::json::canonical_integer_json(document.value());
    if (!canonical) return facman::core::Result<std::string>::failure({
        "recovery_journal_invalid", "Recovery plan could not be canonicalized", canonical.error().detail});
    return canonical;
}
#endif

bool valid_utc_seconds(const std::string& value) noexcept
{
    if (value.size() != 20U || value[4] != '-' || value[7] != '-' ||
        value[10] != 'T' || value[13] != ':' || value[16] != ':' || value[19] != 'Z') return false;
    const std::array<std::size_t, 14> digits {{0, 1, 2, 3, 5, 6, 8, 9, 11, 12, 14, 15, 17, 18}};
    if (!std::all_of(digits.begin(), digits.end(), [&](std::size_t index) {
            return value[index] >= '0' && value[index] <= '9';
        })) return false;
    const auto number = [&](std::size_t offset, std::size_t count) {
        unsigned result = 0;
        for (std::size_t index = 0; index < count; ++index) {
            result = result * 10U + static_cast<unsigned>(value[offset + index] - '0');
        }
        return result;
    };
    const unsigned year = number(0, 4);
    const unsigned month = number(5, 2);
    const unsigned day = number(8, 2);
    const unsigned hour = number(11, 2);
    const unsigned minute = number(14, 2);
    const unsigned second = number(17, 2);
    if (year == 0 || month == 0 || month > 12 || hour > 23 || minute > 59 || second > 59) return false;
    static constexpr std::array<unsigned, 12> days {{31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31}};
    unsigned maximum_day = days[month - 1U];
    const bool leap = year % 4U == 0U && (year % 100U != 0U || year % 400U == 0U);
    if (month == 2U && leap) maximum_day = 29U;
    return day != 0U && day <= maximum_day;
}

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
