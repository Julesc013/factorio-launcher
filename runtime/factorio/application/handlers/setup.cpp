#include "handlers/setup.h"

#include "command_result.h"
#include "handlers/unavailable.h"

#ifndef FACMAN_WITH_SETUP
#define FACMAN_WITH_SETUP 0
#endif

#if FACMAN_WITH_SETUP
#include "fl_file_io.h"
#include "fl_runtime_verify.h"
#include "usk/usk_api.h"

#include <cctype>
#include <filesystem>
#include <sstream>
#endif
#include <string>

namespace facman::factorio::application::handlers {
#if FACMAN_WITH_SETUP
namespace fs = std::filesystem;

namespace {
usk_string_view view(const std::string& text) { return {text.data(), static_cast<usk_size>(text.size())}; }

std::string setup_execute(const std::string& command, const std::string& payload)
{
    usk_context* context = nullptr;
    if (usk_context_create_v1(nullptr, &context) != USK_STATUS_OK || context == nullptr) return "";
    usk_command_request_v1 request {};
    usk_command_response_v1 response {};
    request.struct_size = sizeof(request);
    request.command_name = view(command);
    request.json_payload = view(payload);
    request.dry_run = 1;
    response.struct_size = sizeof(response);
    (void)usk_command_execute_v1(context, &request, &response);
    std::string output;
    if (response.json_payload.data != nullptr) output.assign(response.json_payload.data, response.json_payload.data + response.json_payload.size);
    usk_context_destroy_v1(context);
    return output;
}

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

ApplicationResult package_verify(const ServiceOperationRequest& request)
{
    struct Expected { const char* id; const char* os; const char* arch; const char* linkage; };
    static const Expected profiles[] = {
        {"windows_portable_cli_x64", "windows", "x64", "static_first"},
        {"linux_portable_cli_x64", "linux", "x64", "static_first"},
        {"macos_portable_cli_x64", "macos", "x64", "static_first"},
        {"windows_legacy_winforms_x64", "windows", "x64", "compatibility_bundle"},
        {"portable_cli_x64", "portable", "x64", "static_first_with_reference_components"},
        {"portable_tui_x64", "portable", "x64", "static_first_with_reference_components"},
    };
    const fs::path root = request.path.empty() ? fs::path(fl_runtime_package_root()) : fs::path(request.path);
    const std::string profile = toml_value(read_text(root / "manifest" / "package.v1.toml"), "profile_id");
    const Expected* expected = nullptr;
    for (const Expected& item : profiles) if (profile == item.id) expected = &item;
    if (expected == nullptr) return refused(safety_refusal("package.verify", "package_profile_unsupported", "Unknown built package profile", profile, false), "package_profile_unsupported", "Unknown built package profile");
    const std::string payload = "{\"schema\":\"usk.package_verify_request.v1\",\"package_root\":" + json_quote(root.string()) +
        ",\"expected_target_os\":" + json_quote(expected->os) + ",\"expected_target_arch\":" + json_quote(expected->arch) +
        ",\"expected_linkage_model\":" + json_quote(expected->linkage) + "}";
    const std::string setup = setup_execute("package.verify", payload);
    const SetupVerificationSummary verification = decode_setup_verification(setup);
    ApplicationResult result;
    result.status = verification.verified ? ULK_STATUS_OK : ULK_STATUS_ERROR;
    if (!verification.verified) {
        result.error_code = "package_verification_failed";
        result.error_message = "Package verification failed";
    }
    result.output = "{\"schema\":\"facman.package_verify.v1\",\"status\":\"" +
        std::string(verification.verified ? "pass" : "error") + "\",\"integrity\":\"" +
        std::string(verification.verified ? "sha256_consistent" : "failed") + "\",\"authenticity\":" +
        json_quote(verification.authenticity.empty() ? "not_proven_unsigned" : verification.authenticity) +
        ",\"files_verified\":" + std::to_string(verification.files_verified) + ",\"detail\":" +
        json_quote(verification.verified
            ? "verified by Universal Setup; publisher authenticity is not proven"
            : setup) + "}";
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
    if (request.operation == "package.verify") return package_verify(request);
    if (request.operation == "installs.verify") return unavailable(context, request.operation, "setup_verification_not_implemented", "Universal Setup package verification is not implemented");
    if (request.operation == "installs.repair" || request.operation == "installs.uninstall") {
        auto install = context.installs().load(facman::core::InstallId(request.id));
        if (!install) return refused(safety_refusal(request.operation, "unknown_install", "Install reference is not registered", request.id, true), "unknown_install", "Install reference is not registered");
        const std::string reason = "setup may not " + request.operation.substr(9) + " " + install.value().ownership + " installs";
        ApplicationResult result;
        result.status = ULK_STATUS_ERROR;
        result.error_code = "ownership_denied";
        result.error_message = reason;
        result.output = "{\"schema\":\"factorio.managed_install_refusal.v1\",\"operation\":" + json_quote(request.operation.substr(9)) +
            ",\"status\":\"refused\",\"setup_authority\":\"universal-setup\",\"setup_command\":\"policy.inspect\","
            "\"mutates_install\":false,\"install_id\":" + json_quote(request.id) + ",\"ownership\":" + json_quote(install.value().ownership) +
            ",\"refusal\":{\"schema\":\"common.refusal.v1\",\"code\":\"ownership_denied\",\"reason\":" + json_quote(reason) + ",\"recoverable\":true}}";
        return result;
    }
    if (request.operation == "installs.install-version") {
        const std::string setup = setup_execute("install_local.plan", "{}");
        ApplicationResult result;
        result.output = "{\"schema\":\"factorio.managed_install_plan.v1\",\"operation\":\"install-version\",\"status\":\"planned\","
            "\"setup_authority\":\"universal-setup\",\"setup_command\":\"install_local.plan\",\"mutates_install\":false,\"mutation_executed\":false,"
            "\"version\":" + json_quote(request.version) + ",\"archive\":" + json_quote(request.archive) + ",\"setup_response\":" + setup + "}";
        return result;
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
