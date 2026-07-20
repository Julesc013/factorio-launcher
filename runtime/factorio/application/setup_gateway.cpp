// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "setup_gateway.h"

#include "fl_json.h"
#include "fl_file_io.h"

#include <system_error>

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
