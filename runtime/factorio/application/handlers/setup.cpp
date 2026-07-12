// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "handlers/setup.h"

#include "command_result.h"
#include "handlers/unavailable.h"

#ifndef FACMAN_WITH_SETUP
#define FACMAN_WITH_SETUP 0
#endif

#if FACMAN_WITH_SETUP
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_runtime_verify.h"

#include <filesystem>
#endif
#include <string>

namespace facman::factorio::application::handlers {
#if FACMAN_WITH_SETUP
namespace fs = std::filesystem;

namespace {
std::string read_text(const fs::path& path)
{
    facman::platform::StableInputFile input;
    if (!input.open_no_follow(path).ok() || input.size() > 1024U * 1024U) return {};
    std::string text(static_cast<std::size_t>(input.size()), '\0');
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t count = input.read_at(offset, text.data() + static_cast<std::size_t>(offset), static_cast<std::size_t>(input.size() - offset));
        if (count == 0) return {};
        offset += count;
    }
    return input.revalidate().ok() ? text : std::string();
}

std::string toml_value(const std::string& text, const std::string& key)
{
    const std::string marker = key + " = \"";
    const std::size_t start = text.find(marker);
    if (start == std::string::npos) return {};
    const std::size_t value = start + marker.size();
    const std::size_t end = text.find('"', value);
    return end == std::string::npos ? std::string() : text.substr(value, end - value);
}

ApplicationResult package_verify(ApplicationContext& context, const ServiceOperationRequest& request)
{
    const fs::path root = request.path.empty() ? fs::path(fl_runtime_package_root()) : fs::path(request.path);
    const std::string manifest = read_text(root / "manifest" / "package.v1.toml");
    PackageVerifyRequest verify_request;
    verify_request.package_root = root;
    verify_request.target_os = toml_value(manifest, "target_os");
    verify_request.target_arch = toml_value(manifest, "target_arch");
    verify_request.linkage_model = toml_value(manifest, "linkage_model");
    if (verify_request.target_os.empty() || verify_request.target_arch.empty() || verify_request.linkage_model.empty()) {
        return refused(
            safety_refusal("package.verify", "package_manifest_invalid", "Package manifest lacks target metadata", root.string(), false),
            "package_manifest_invalid",
            "Package manifest lacks target metadata");
    }
    auto verification = context.setup().verify_package(verify_request);
    if (!verification) return unavailable(context, "package.verify", verification.error().code, verification.error().message);
    ApplicationResult result;
    result.status = verification.value().verified ? ULK_STATUS_OK : ULK_STATUS_ERROR;
    if (!verification.value().verified) {
        result.error_code = "package_verification_failed";
        result.error_message = "Package verification failed";
    }
    facman::core::json::ObjectBuilder output;
    output.add_string("schema", "facman.package_verify.v1");
    output.add_string("status", verification.value().verified ? "pass" : "error");
    output.add_string("integrity", verification.value().verified ? "sha256_consistent" : "failed");
    output.add_string("authenticity", verification.value().authenticity.empty()
        ? "not_proven_unsigned" : verification.value().authenticity);
    output.add_unsigned_integer("files_verified", verification.value().files_verified);
    output.add_string("detail", verification.value().verified
        ? "verified by Universal Setup; publisher authenticity is not proven"
        : verification.value().detail);
    result.output = output.serialize();
    return result;
}
}
#endif

ApplicationResult preview_setup(ApplicationContext& context)
{
    return unavailable(context, "setup.preview", "setup_unavailable", "Universal Setup preview is unavailable in this application configuration");
}

ApplicationResult setup_operation(ApplicationContext& context, const ServiceOperationRequest& request)
{
#if FACMAN_WITH_SETUP
    if (request.operation == "package.verify") return package_verify(context, request);
    if (request.operation == "installs.verify") {
        auto provider = context.setup().verify_install(request.id);
        if (!provider) return unavailable(context, request.operation, provider.error().code, provider.error().message);
        return unavailable(context, request.operation, provider.value().code, provider.value().reason);
    }
    if (request.operation == "installs.repair" || request.operation == "installs.uninstall") {
        auto install = context.installs().load(facman::core::InstallId(request.id));
        if (!install) return refused(safety_refusal(request.operation, "unknown_install", "Install reference is not registered", request.id, true), "unknown_install", "Install reference is not registered");
        const std::string reason = "setup may not " + request.operation.substr(9) + " " + install.value().ownership + " installs";
        ApplicationResult result;
        result.status = ULK_STATUS_ERROR;
        result.error_code = "ownership_denied";
        result.error_message = reason;
        facman::core::json::ObjectBuilder refusal;
        refusal.add_string("schema", "common.refusal.v1");
        refusal.add_string("code", "ownership_denied");
        refusal.add_string("reason", reason);
        refusal.add_bool("recoverable", true);
        facman::core::json::ObjectBuilder output;
        output.add_string("schema", "factorio.managed_install_refusal.v1");
        output.add_string("operation", request.operation.substr(9));
        output.add_string("status", "refused");
        output.add_string("setup_authority", "universal-setup");
        output.add_string("setup_command", "policy.inspect");
        output.add_bool("mutates_install", false);
        output.add_string("install_id", request.id);
        output.add_string("ownership", install.value().ownership);
        output.add_object("refusal", refusal);
        result.output = output.serialize();
        return result;
    }
    if (request.operation == "installs.install-version") {
        InstallPlanRequest plan_request;
        plan_request.version = request.version;
        plan_request.archive = request.archive;
        auto plan = context.setup().plan_install(plan_request);
        if (!plan) return unavailable(context, request.operation, plan.error().code, plan.error().message);
        if (!plan.value().inputs_evaluated) {
            return unavailable(
                context,
                request.operation,
                "setup_plan_inputs_not_evaluated",
                "Universal Setup did not evaluate the requested version and archive");
        }
        return unavailable(context, request.operation, "setup_mutation_not_implemented", "Setup mutation remains unavailable");
    }
    return unavailable(context, request.operation, "setup_unavailable", "Setup operation is unavailable");
#else
    return unavailable(
        context,
        request.operation,
        "setup_unavailable",
        "Universal Setup support is disabled in this build");
#endif
}

} // namespace facman::factorio::application::handlers
