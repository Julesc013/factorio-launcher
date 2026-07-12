// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "setup_gateway.h"

#include "fl_json.h"

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
        return facman::core::Result<std::string>::failure({"setup_provider_refused", "Universal Setup refused the request", ""});
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

class UskSetupGateway final : public SetupGateway {
public:
    facman::core::Result<PackageVerifyResult> verify_package(const PackageVerifyRequest& request) override
    {
        facman::core::json::ObjectBuilder payload;
        payload.add_string("schema", "usk.package_verify_request.v1");
        payload.add_string("package_root", request.package_root.string());
        payload.add_string("expected_target_os", request.target_os);
        payload.add_string("expected_target_arch", request.target_arch);
        payload.add_string("expected_linkage_model", request.linkage_model);
        auto response = execute_setup("package.verify", payload.serialize());
        if (!response) return facman::core::Result<PackageVerifyResult>::failure(response.error());
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

    facman::core::Result<InstallPlan> plan_install(const InstallPlanRequest& request) override
    {
        facman::core::json::ObjectBuilder payload;
        payload.add_string("schema", "facman.install_plan_request.v1");
        payload.add_string("version", request.version);
        payload.add_string("archive", request.archive.string());
        payload.add_string("target", request.target.string());
        auto response = execute_setup("install_local.plan", payload.serialize());
        if (!response) return facman::core::Result<InstallPlan>::failure(response.error());
        InstallPlan plan;
        plan.provider_response = response.take_value();
        plan.inputs_evaluated = plan.provider_response.find(request.version) != std::string::npos &&
            plan.provider_response.find(request.archive.string()) != std::string::npos;
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
