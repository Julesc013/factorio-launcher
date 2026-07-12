// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "handlers/utility.h"

#include "command_result.h"
#include "handlers/unavailable.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "flb_factorio_diagnostics.h"

#include <algorithm>
#include <cctype>
#include <filesystem>
#include <sstream>
#include <utility>
#include <vector>

namespace facman::factorio::application::handlers {
namespace fs = std::filesystem;
namespace diagnostics = facman::factorio::diagnostics;

namespace {
std::string slugify(const std::string& value)
{
    std::string output;
    bool separator = false;
    for (unsigned char ch : value) {
        if (std::isalnum(ch)) { output.push_back(static_cast<char>(std::tolower(ch))); separator = false; }
        else if (!output.empty() && !separator) { output.push_back('-'); separator = true; }
    }
    while (!output.empty() && output.back() == '-') output.pop_back();
    return output.empty() ? "server" : output;
}

facman::core::Result<std::string> read_bounded(const fs::path& path, std::uint64_t maximum = 8U * 1024U * 1024U)
{
    facman::platform::StableInputFile input;
    auto status = input.open_no_follow(path);
    if (!status.ok()) return facman::core::Result<std::string>::failure({status.code, status.detail, path.string()});
    if (input.size() > maximum) return facman::core::Result<std::string>::failure({"utility_input_too_large", "input exceeds its byte budget", path.string()});
    std::string text(static_cast<std::size_t>(input.size()), '\0');
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t count = input.read_at(offset, text.data() + static_cast<std::size_t>(offset), static_cast<std::size_t>(input.size() - offset));
        if (count == 0) return facman::core::Result<std::string>::failure({"utility_input_read_failed", "short stable read", path.string()});
        offset += count;
    }
    status = input.revalidate();
    if (!status.ok()) return facman::core::Result<std::string>::failure({status.code, status.detail, path.string()});
    return facman::core::Result<std::string>::success(std::move(text));
}

std::string portal_refusal(const ServiceOperationRequest& request)
{
    return "{\"schema\":\"factorio.mod_portal_refusal.v1\",\"operation\":" + json_quote(request.operation) +
        ",\"status\":\"refused\",\"network_allowed\":false,\"query\":" + json_quote(request.query) +
        ",\"instance_id\":" + json_quote(request.instance_id) +
        ",\"refusal\":{\"schema\":\"common.refusal.v1\",\"operation\":" + json_quote(request.operation) +
        ",\"code\":\"network_forbidden\",\"reason\":\"Mod Portal network access is not enabled in this portable build\",\"recoverable\":true}}";
}

std::string server_json(const std::string& id, const std::string& name, const std::string& instance)
{
    return "{\"schema\":\"factorio.server.v1\",\"server_id\":" + json_quote(id) +
        ",\"display_name\":" + json_quote(name) + ",\"instance_id\":" + json_quote(instance) +
        ",\"status\":\"stopped\",\"start_policy\":\"manual\",\"execution\":\"not_implemented\"}";
}

ApplicationResult server_create(ApplicationContext& context, const ServiceOperationRequest& request)
{
    auto parsed_id = facman::core::InstanceId::parse(request.instance_id);
    if (!parsed_id) return refused(
        safety_refusal("servers.create", parsed_id.error().code, "Instance id is not portable", parsed_id.error().message, false),
        parsed_id.error().code, parsed_id.error().message);
    auto instance = context.instances().load(parsed_id.value());
    if (!instance) return refused(
        safety_refusal("servers.create", "unknown_instance", "Instance is not registered", request.instance_id, true),
        "unknown_instance", "Instance is not registered");
    const std::string id = request.id.empty() ? slugify(request.name) : request.id;
    auto target = facman::base::managed_file(context.workspace(), "servers", id, ".server.v1.json");
    if (!target.ok()) return refused(safety_refusal("servers.create", target.code, "Server id is invalid", target.detail, false), target.code, target.detail);
    if (fs::exists(target.path)) return refused(safety_refusal("servers.create", "persistent_target_exists", "Server profile already exists", target.path.string(), true), "persistent_target_exists", "Server profile already exists");
    const std::string text = server_json(id, request.name, request.instance_id);
    transactions::Record record;
    record.command_id = "servers.create";
    record.target = target.path;
    record.sources = {instance.value().source_path};
    record.commit_strategy = "durable_exclusive_file_create";
    auto started = transactions::TransactionSession::begin(context.workspace(), std::move(record));
    if (!started) return refused(safety_refusal("servers.create", "recovery_write_refused", "Server journal could not be started", started.error().message, true), "recovery_write_refused", started.error().message);
    transactions::TransactionSession session = started.take_value();
    if (!session.validated() || !session.planned() || !session.staged("server_profile_serialized") ||
        !session.verified("server_profile_validated") || !session.committing()) {
        return refused(safety_refusal("servers.create", "recovery_write_refused", "Server journal update failed", session.detail(), true), "recovery_write_refused", session.detail());
    }
    std::error_code error;
    fs::create_directories(target.path.parent_path(), error);
    facman::platform::DurableOutputFile output;
    auto status = error ? facman::platform::IoStatus::failure("server_directory_create_failed", error.message()) : output.create_exclusive(target.path, 1024U * 1024U);
    if (status.ok() && output.write_at(0, text.data(), text.size()) != text.size()) status = facman::platform::IoStatus::failure("server_write_failed", "short server profile write");
    if (status.ok()) status = output.flush_file_and_parent();
    if (!status.ok()) {
        output.close_without_flush();
        session.failed(status.detail);
        return refused(safety_refusal("servers.create", "persistent_write_refused", "Server profile could not be committed", status.detail, true), "persistent_write_refused", status.detail);
    }
    if (!session.committed("server_profile_committed") || !session.complete()) return refused(
        safety_refusal("servers.create", "transaction_recovery_required", "Server profile committed but journal finalization failed", session.detail(), false),
        "transaction_recovery_required", session.detail());
    ApplicationResult result; result.output = text; return result;
}

ApplicationResult server_list(ApplicationContext& context)
{
    const fs::path root = context.workspace() / "servers";
    std::vector<fs::path> files;
    std::error_code error;
    if (fs::is_directory(root, error) && !error) {
        for (fs::directory_iterator iterator(root, fs::directory_options::skip_permission_denied, error), end; iterator != end && !error; iterator.increment(error)) {
            if (iterator->is_regular_file(error) && iterator->path().extension() == ".json") files.push_back(iterator->path());
        }
    }
    std::sort(files.begin(), files.end());
    std::string output = "[";
    for (std::size_t index = 0; index < files.size(); ++index) {
        auto text = read_bounded(files[index], 1024U * 1024U);
        if (!text) return refused(safety_refusal("servers.list", text.error().code, "Server profile could not be read", text.error().message, true), text.error().code, text.error().message);
        if (index) output += ',';
        output += text.value();
    }
    output += "]";
    ApplicationResult result; result.output = std::move(output); return result;
}

ApplicationResult server_unavailable(ApplicationContext& context, const ServiceOperationRequest& request)
{
    auto target = facman::base::managed_file(context.workspace(), "servers", request.id, ".server.v1.json");
    if (!target.ok() || !fs::is_regular_file(target.path)) return refused(safety_refusal(request.operation, "unknown_server", "Server profile is not registered", request.id, true), "unknown_server", "Server profile is not registered");
    auto text = read_bounded(target.path, 1024U * 1024U);
    if (!text) return refused(safety_refusal(request.operation, text.error().code, "Server profile could not be read", text.error().message, true), text.error().code, text.error().message);
    const std::string instance_id = decode_json_string_field(text.value(), "instance_id");
    const std::string reason = "server process execution is not enabled in this slice";
    ApplicationResult result;
    result.status = ULK_STATUS_ERROR;
    result.error_code = "execution_not_enabled";
    result.error_message = reason;
    result.output = "{\"schema\":\"factorio.server_refusal.v1\",\"operation\":" + json_quote(request.operation) +
        ",\"status\":\"refused\",\"server_id\":" + json_quote(request.id) + ",\"instance_id\":" + json_quote(instance_id) +
        ",\"refusal\":{\"schema\":\"common.refusal.v1\",\"code\":\"execution_not_enabled\",\"reason\":" + json_quote(reason) + ",\"recoverable\":true}}";
    return result;
}

ApplicationResult diagnostics_redact(const ServiceOperationRequest& request)
{
    const fs::path input(request.path);
    auto text = read_bounded(input);
    if (!text) return refused(safety_refusal("diagnostics.redact", text.error().code, "Diagnostic input could not be read", text.error().message, true), text.error().code, text.error().message);
    const std::vector<unsigned char> bytes(text.value().begin(), text.value().end());
    if (diagnostics::looks_binary(bytes)) {
        return refused(
            safety_refusal(
                "diagnostics.redact",
                "diagnostic_structured_input_invalid",
                "Binary source cannot be redacted as text",
                input.filename().string(),
                false),
            "diagnostic_structured_input_invalid",
            "Binary source cannot be redacted as text");
    }
    diagnostics::RedactionResult redacted = diagnostics::redact_text(text.value(), input.filename().generic_string());
    if (!redacted.safe) return refused(safety_refusal("diagnostics.redact", "diagnostic_structured_input_invalid", "Structured diagnostic input is invalid", redacted.error, false), "diagnostic_structured_input_invalid", redacted.error);
    ApplicationResult result;
    result.output = "{\"schema\":\"factorio.diagnostic_redact.v1\",\"command\":\"diagnostics.redact\",\"status\":\"ok\",\"redacted_text\":" +
        json_quote(redacted.text) + ",\"redaction_report\":" + diagnostics::redaction_report_json(redacted.events) + "}";
    return result;
}

ApplicationResult bug_report(ApplicationContext& context)
{
    auto installs = context.installs().list();
    auto instances = context.instances().list();
    if (!installs || !instances) return refused(safety_refusal("dev.bug_report", "workspace_list_failed", "Workspace records could not be listed", "", true), "workspace_list_failed", "Workspace records could not be listed");
    const fs::path servers = context.workspace() / "servers";
    std::size_t server_count = 0;
    std::error_code error;
    if (fs::is_directory(servers, error) && !error) for (fs::directory_iterator iterator(servers, error), end; iterator != end && !error; iterator.increment(error)) if (iterator->is_regular_file(error)) ++server_count;
    ApplicationResult result;
    result.output = "{\"schema\":\"factorio.bug_report.v1\",\"workspace\":" + json_quote(context.workspace().string()) +
        ",\"installs\":" + std::to_string(installs.value().size()) + ",\"instances\":" + std::to_string(instances.value().size()) +
        ",\"servers\":" + std::to_string(server_count) + ",\"redacts_secrets\":true,\"includes_factorio_binaries\":false}";
    return result;
}
}

ApplicationResult refuse_mod_portal(ApplicationContext&, const ServiceOperationRequest& request)
{
    ApplicationResult result;
    result.status = ULK_STATUS_ERROR;
    result.error_code = "network_forbidden";
    result.error_message = "Mod Portal network access is not enabled in this portable build";
    result.output = portal_refusal(request);
    return result;
}

ApplicationResult create_server(ApplicationContext& context, const ServiceOperationRequest& request)
{
    return server_create(context, request);
}

ApplicationResult list_servers(ApplicationContext& context)
{
    return server_list(context);
}

ApplicationResult control_server(ApplicationContext& context, const ServiceOperationRequest& request)
{
    return server_unavailable(context, request);
}

ApplicationResult redact_diagnostics(ApplicationContext&, const ServiceOperationRequest& request)
{
    return diagnostics_redact(request);
}

ApplicationResult create_bug_report(ApplicationContext& context)
{
    return bug_report(context);
}

ApplicationResult refuse_dev_execution(ApplicationContext& context, const ServiceOperationRequest& request)
{
    return unavailable(context, request.operation, "execution_not_enabled", "Factorio execution-based developer tooling is not enabled in this slice");
}

} // namespace facman::factorio::application::handlers
