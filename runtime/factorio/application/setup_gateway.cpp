// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "setup_gateway.h"

#include "fl_json.h"
#include "fl_file_io.h"

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

facman::core::Result<std::string> execute_setup(const std::string& command, const std::string& payload)
{
    usk_context* context = nullptr;
    if (usk_context_create_v1(nullptr, &context) != USK_STATUS_OK || context == nullptr) {
        return facman::core::Result<std::string>::failure({"setup_context_failed", "Universal Setup context creation failed", ""});
    }
    usk_command_request_v1 request {};
    usk_command_response_v1 response {};
    request.struct_size = sizeof(request);
    request.command_name = view(command);
    request.json_payload = view(payload);
    request.dry_run = 1;
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
    facman::core::Result<PackageVerifyResult> verify_package(const PackageVerifyRequest& request) override
    {
        facman::core::json::ObjectBuilder payload;
        payload.add_string("schema", "usk.package_verify_request.v1");
        payload.add_string("package_root", facman::platform::path_to_utf8(request.package_root));
        payload.add_string("expected_target_os", request.target_os);
        payload.add_string("expected_target_arch", request.target_arch);
        payload.add_string("expected_linkage_model", request.linkage_model);
        auto response = execute_setup("package.verify", payload.serialize());
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
        auto response = execute_setup("install_local.inspect", payload.serialize());
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
        facman::core::json::ObjectBuilder payload;
        payload.add_string("schema", "facman.install_plan_request.v1");
        payload.add_string("version", request.version);
        payload.add_string("archive", facman::platform::path_to_utf8(request.archive));
        payload.add_string("target", facman::platform::path_to_utf8(request.target));
        auto response = execute_setup("install_local.plan", payload.serialize());
        if (!response) return facman::core::Result<InstallPlan>::failure(response.error());
        InstallPlan plan;
        plan.provider_response = response.take_value();
        auto document = facman::core::json::parse(plan.provider_response);
        const auto* report = document && document.value().is_object()
            ? document.value().find("payload")
            : nullptr;
        const auto* evaluated = report != nullptr && report->is_object()
            ? report->find("evaluated_inputs")
            : nullptr;
        const auto* mutation = report != nullptr && report->is_object()
            ? report->find("mutation_executed")
            : nullptr;
        plan.inputs_confirmed =
            document && string_field(document.value(), "status") == "ok" &&
            report != nullptr && report->is_object() &&
            string_field(*report, "schema") == "usk.install_plan.v1" &&
            evaluated != nullptr && evaluated->is_object() &&
            string_field(*evaluated, "requested_version") == request.version &&
            string_field(*evaluated, "source_archive") == facman::platform::path_to_utf8(request.archive) &&
            string_field(*evaluated, "target") == facman::platform::path_to_utf8(request.target) &&
            mutation != nullptr && mutation->bool_value() && !mutation->bool_value().value();
        return facman::core::Result<InstallPlan>::success(std::move(plan));
    }

    facman::core::Result<SetupRefusal> verify_install(const std::string&) override
    {
        return unsupported("setup_verification_not_implemented", "Installed-state verification is not implemented");
    }
    facman::core::Result<SetupRefusal> repair_install(const std::string&) override
    {
        return unsupported("setup_mutation_not_implemented", "Installed-state repair is not implemented");
    }
    facman::core::Result<SetupRefusal> uninstall_install(const std::string&) override
    {
        return unsupported("setup_mutation_not_implemented", "Installed-state uninstall is not implemented");
    }

private:
    static facman::core::Result<SetupRefusal> unsupported(const char* code, const char* reason)
    {
        return facman::core::Result<SetupRefusal>::success({code, reason});
    }
};
#endif

} // namespace

std::unique_ptr<SetupGateway> make_setup_gateway()
{
#if FACMAN_WITH_SETUP
    return std::make_unique<UskSetupGateway>();
#else
    return std::make_unique<UnavailableSetupGateway>();
#endif
}

} // namespace facman::factorio::application
