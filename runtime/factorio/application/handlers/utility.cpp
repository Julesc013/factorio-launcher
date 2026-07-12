// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "handlers/utility.h"

#include "command_result.h"
#include "handlers/unavailable.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "flb_factorio_diagnostics.h"
#include "flb_factorio_server_plan.h"

#include <algorithm>
#include <cctype>
#include <filesystem>
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
    facman::core::json::ObjectBuilder refusal;
    refusal.add_string("schema", "common.refusal.v1");
    refusal.add_string("operation", request.operation);
    refusal.add_string("code", "network_forbidden");
    refusal.add_string("reason", "Mod Portal network access is not enabled in this portable build");
    refusal.add_bool("recoverable", true);
    facman::core::json::ObjectBuilder output;
    output.add_string("schema", "factorio.mod_portal_refusal.v1");
    output.add_string("operation", request.operation);
    output.add_string("status", "refused");
    output.add_bool("network_allowed", false);
    output.add_string("query", request.query);
    output.add_string("instance_id", request.instance_id);
    output.add_object("refusal", refusal);
    return output.serialize();
}

std::string server_json(const std::string& id, const std::string& name, const std::string& instance)
{
    facman::core::json::ObjectBuilder visibility;
    visibility.add_bool("public", false);
    visibility.add_bool("lan", true);
    facman::core::json::ObjectBuilder autosave;
    (void)autosave.add_unsigned_integer("interval_minutes", 10);
    (void)autosave.add_unsigned_integer("slots", 5);
    facman::core::json::ObjectBuilder settings;
    settings.add_string("name", name);
    (void)settings.add_unsigned_integer("maximum_players", 0);
    (void)settings.add_unsigned_integer("port", 34197);
    facman::core::json::ObjectBuilder map_generation;
    map_generation.add_string("preset", "default");
    facman::core::json::ObjectBuilder map_settings;
    map_settings.add_string("difficulty", "normal");
    facman::core::json::ArrayBuilder tags;
    facman::core::json::ArrayBuilder references;
    facman::core::json::ObjectBuilder output;
    output.add_string("schema", "factorio.server_profile.v2");
    (void)output.add_unsigned_integer("schema_version", 2);
    output.add_string("server_id", id);
    output.add_string("display_name", name);
    output.add_string("instance_id", instance);
    output.add_string("save_selection", "");
    output.add_string("launch_profile", "headless-plan");
    output.add_object("server_settings", settings);
    output.add_object("map_generation_settings", map_generation);
    output.add_object("map_settings", map_settings);
    output.add_object("visibility_policy", visibility);
    output.add_object("autosave_policy", autosave);
    output.add_string("description", "");
    output.add_array("tags", tags);
    output.add_array("allowlist_references", references);
    facman::core::json::ArrayBuilder bans;
    output.add_array("banlist_references", bans);
    facman::core::json::ArrayBuilder credentials;
    output.add_array("credential_references", credentials);
    output.add_string("status", "stopped");
    output.add_string("start_policy", "manual");
    output.add_string("execution", "not_implemented");
    return output.serialize();
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
    facman::core::json::ArrayBuilder output;
    for (const auto& file : files) {
        auto text = read_bounded(file, 1024U * 1024U);
        if (!text) return refused(safety_refusal("servers.list", text.error().code, "Server profile could not be read", text.error().message, true), text.error().code, text.error().message);
        auto document = decode_json_value(text.value());
        if (!document) return refused(safety_refusal("servers.list", document.error().code, "Server profile is invalid", document.error().message, false), document.error().code, document.error().message);
        output.add_value(document.value());
    }
    ApplicationResult result; result.output = output.serialize(); return result;
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
    facman::core::json::ObjectBuilder refusal;
    refusal.add_string("schema", "common.refusal.v1");
    refusal.add_string("code", "execution_not_enabled");
    refusal.add_string("reason", reason);
    refusal.add_bool("recoverable", true);
    facman::core::json::ObjectBuilder output;
    output.add_string("schema", "factorio.server_refusal.v1");
    output.add_string("operation", request.operation);
    output.add_string("status", "refused");
    output.add_string("server_id", request.id);
    output.add_string("instance_id", instance_id);
    output.add_object("refusal", refusal);
    result.output = output.serialize();
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
    facman::core::json::ObjectBuilder output;
    output.add_string("schema", "factorio.diagnostic_redact.v1");
    output.add_string("command", "diagnostics.redact");
    output.add_string("status", "ok");
    output.add_string("redacted_text", redacted.text);
    auto report = decode_json_value(diagnostics::redaction_report_json(redacted.events));
    if (report) output.add_value("redaction_report", report.value());
    result.output = output.serialize();
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
    facman::core::json::ObjectBuilder output;
    output.add_string("schema", "factorio.bug_report.v1");
    output.add_string("workspace", context.workspace().string());
    output.add_unsigned_integer("installs", installs.value().size());
    output.add_unsigned_integer("instances", instances.value().size());
    output.add_unsigned_integer("servers", server_count);
    output.add_bool("redacts_secrets", true);
    output.add_bool("includes_factorio_binaries", false);
    ApplicationResult result;
    result.output = output.serialize();
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

ApplicationResult dispatch_server_plan(ApplicationContext& context, const ApplicationRequest& request)
{
    const auto& value = std::get<ServerPlanRequest>(request.payload);
    namespace planner = facman::factorio::server;
    facman::core::Result<std::string> result = [&]() {
        switch (request.command) {
        case CommandId::servers_inspect: return planner::inspect(context.workspace(), value);
        case CommandId::servers_validate: return planner::validate(context.workspace(), value);
        case CommandId::servers_plan: return planner::plan(context.workspace(), value);
        case CommandId::servers_diff: return planner::diff(context.workspace(), value);
        case CommandId::servers_export: return planner::export_bundle(context.workspace(), value);
        default: return facman::core::Result<std::string>::failure(
            {"unsupported_operation", "Unsupported server planning command", "servers"});
        }
    }();
    const std::string operation = request.command == CommandId::servers_inspect ? "servers.inspect" :
        request.command == CommandId::servers_validate ? "servers.validate" :
        request.command == CommandId::servers_plan ? "servers.plan" :
        request.command == CommandId::servers_diff ? "servers.diff" : "servers.export";
    if (result) { ApplicationResult output; output.output = result.take_value(); return output; }
    return refused(safety_refusal(operation, result.error().code, "Server planning operation was refused",
        result.error().message, result.error().recoverable), result.error().code, result.error().message, result.error().kind);
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
