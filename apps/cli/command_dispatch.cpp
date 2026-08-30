// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "command_dispatch.h"

#include "facman_client.h"
#include "fl_json.h"
#include "fl_file_io.h"
#include "fl_system_services.h"
#include "version.h"
#include "generated/command_help.inc"
#if FACMAN_TUI_HOST_AVAILABLE
#include "tui_host.h"
#endif

#include <algorithm>
#include <cctype>
#include <iostream>
#include <memory>
#include <optional>
#include <set>
#include <string>
#include <vector>

namespace {
namespace json = facman::core::json;

constexpr std::size_t kTransportInputLimit = 1024U * 1024U;
constexpr std::size_t kTransportOutputLimit = 16U * 1024U * 1024U;
thread_local bool g_machine_result_emitted = false;

#ifndef FACMAN_BUILD_SOURCE_REVISION
#define FACMAN_BUILD_SOURCE_REVISION "unknown"
#endif

#ifndef FACMAN_BUILD_CONFIGURATION
#define FACMAN_BUILD_CONFIGURATION ""
#endif

const char* build_configuration()
{
    return *FACMAN_BUILD_CONFIGURATION == '\0' ? "default" : FACMAN_BUILD_CONFIGURATION;
}

struct Options {
    std::string workspace;
    std::optional<facman::core::Error> workspace_error;
    std::vector<std::string> args;
};

struct CliResponse {
    CliResponse(
        std::string command_value,
        std::string request_id_value,
        std::string operation_id_value,
        std::string attempt_id_value,
        facman::core::Result<facman::client::CommandResponse> response_value)
        : command(std::move(command_value)),
          request_id(std::move(request_id_value)),
          operation_id(std::move(operation_id_value)),
          attempt_id(std::move(attempt_id_value)),
          response(std::move(response_value)) {}

    explicit operator bool() const noexcept { return static_cast<bool>(response); }
    const facman::client::CommandResponse& value() const { return response.value(); }
    facman::client::CommandResponse& value() { return response.value(); }
    const facman::core::Error& error() const { return response.error(); }

    std::string command;
    std::string request_id;
    std::string operation_id;
    std::string attempt_id;
    facman::core::Result<facman::client::CommandResponse> response;
};

std::string transport_response(
    const std::string& request_id,
    const std::string& command,
    const facman::core::Result<facman::client::CommandResponse>& response,
    unsigned int protocol_version,
    const std::string& operation_id,
    const std::string& attempt_id);

Options parse_options(int argc, char** argv)
{
    Options options;
    std::string explicit_workspace;
    for (int index = 1; index < argc; ++index) {
        const std::string value = argv[index];
        if (value == "--workspace" && index + 1 < argc) explicit_workspace = argv[++index];
        else options.args.push_back(value);
    }
    auto resolution = facman::client::resolve_workspace(
        facman::platform::path_from_utf8(explicit_workspace));
    if (resolution) options.workspace = facman::platform::path_to_utf8(resolution.value().path);
    else options.workspace_error = resolution.error();
    return options;
}

bool flag(const std::vector<std::string>& args, const std::string& value)
{
    if (std::find(args.begin(), args.end(), value) != args.end()) return true;
    if (value != "--json") return false;
    for (std::size_t index = 0; index + 1 < args.size(); ++index) {
        if (args[index] == "--format" && args[index + 1] == "json") return true;
    }
    return false;
}

std::string option(const std::vector<std::string>& args, const std::string& name, const std::string& fallback = {})
{
    for (std::size_t index = 0; index + 1 < args.size(); ++index) if (args[index] == name) return args[index + 1];
    return fallback;
}

std::vector<std::string> option_values(const std::vector<std::string>& args, const std::string& name)
{
    std::vector<std::string> output;
    for (std::size_t index = 0; index + 1 < args.size(); ++index) if (args[index] == name) output.push_back(args[++index]);
    return output;
}

std::string slugify(const std::string& value)
{
    std::string output;
    bool dash = false;
    for (unsigned char ch : value) {
        if (std::isalnum(ch)) { output.push_back(static_cast<char>(std::tolower(ch))); dash = false; }
        else if (!output.empty() && !dash) { output.push_back('-'); dash = true; }
    }
    while (!output.empty() && output.back() == '-') output.pop_back();
    return output.empty() ? "item" : output;
}

CliResponse call(
    const Options& options,
    const std::string& command,
    const std::string& payload = "{}",
    bool dry_run = true,
    const std::string& requested_request_id = {},
    const std::string& requested_operation_id = {},
    const std::string& requested_attempt_id = {})
{
    facman::platform::RandomIdGenerator ids;
    const std::string request_id = requested_request_id.empty()
        ? ids.next("request") : requested_request_id;
    const std::string operation_id = requested_operation_id.empty()
        ? ids.next("op") : requested_operation_id;
    const std::string attempt_id = requested_attempt_id.empty()
        ? ids.next("attempt") : requested_attempt_id;
    if (options.workspace_error) {
        return {command, request_id, operation_id, attempt_id,
            facman::core::Result<facman::client::CommandResponse>::failure(*options.workspace_error)};
    }
    facman::client::FacManClient client(
        std::make_unique<facman::client::DirectFlbTransport>(facman::platform::path_from_utf8(options.workspace)));
    facman::client::CommandRequest request {command, payload, dry_run};
    request.request_id = request_id;
    request.operation_id = operation_id;
    request.attempt_id = attempt_id;
    return {command, request_id, operation_id, attempt_id, client.execute(request)};
}

CliResponse local_success(const std::string& command, const std::string& payload)
{
    facman::platform::RandomIdGenerator ids;
    const std::string request_id = ids.next("request");
    const std::string operation_id = ids.next("op");
    const std::string attempt_id = ids.next("attempt");
    facman::client::CommandResponse value;
    value.status = 0;
    value.outcome_kind = facman::core::OutcomeKind::ok;
    value.outcome = "ok";
    value.payload = payload;
    auto parsed = json::parse(payload);
    if (parsed) value.parsed_payload = std::make_shared<json::Value>(parsed.take_value());
    value.operation.operation_id = operation_id;
    value.operation.attempt_id = attempt_id;
    value.operation.outcome = facman::client::OperationOutcome::completed;
    return {command, request_id, operation_id, attempt_id,
        facman::core::Result<facman::client::CommandResponse>::success(std::move(value))};
}

CliResponse local_failure(
    const std::string& command,
    const std::string& code,
    const std::string& message,
    facman::core::OutcomeKind kind)
{
    facman::platform::RandomIdGenerator ids;
    const std::string request_id = ids.next("request");
    const std::string operation_id = ids.next("op");
    const std::string attempt_id = ids.next("attempt");
    return {command, request_id, operation_id, attempt_id,
        facman::core::Result<facman::client::CommandResponse>::failure(
            {code, message, "$", kind})};
}

int outcome_exit_code(
    facman::core::OutcomeKind kind,
    facman::client::OperationOutcome operation_outcome = facman::client::OperationOutcome::refused_before_effects)
{
    switch (kind) {
    case facman::core::OutcomeKind::ok: return 0;
    case facman::core::OutcomeKind::invalid_argument: return 2;
    case facman::core::OutcomeKind::refused:
    case facman::core::OutcomeKind::unavailable:
    case facman::core::OutcomeKind::not_found:
    case facman::core::OutcomeKind::conflict:
    case facman::core::OutcomeKind::cancelled: return 1;
    case facman::core::OutcomeKind::recovery_required: return 3;
    case facman::core::OutcomeKind::outcome_unknown: return 4;
    case facman::core::OutcomeKind::timeout:
    case facman::core::OutcomeKind::internal_error:
        if (operation_outcome == facman::client::OperationOutcome::outcome_unknown) return 4;
        return 5;
    }
    return 5;
}

int cli_exit_code(const CliResponse& response)
{
    return response
        ? outcome_exit_code(response.value().outcome_kind, response.value().operation.outcome)
        : outcome_exit_code(response.error().kind);
}

int emit_json(const CliResponse& response)
{
    g_machine_result_emitted = true;
    std::cout << transport_response(
        response.request_id,
        response.command,
        response.response,
        2U,
        response.operation_id,
        response.attempt_id) << '\n';
    return cli_exit_code(response);
}

int emit_basic(const CliResponse& response, bool as_json, const std::string& success)
{
    if (as_json) return emit_json(response);
    if (!response) { std::cerr << response.error().message << '\n'; return cli_exit_code(response); }
    if (!response.value().ok()) { std::cerr << (response.value().error_message.empty() ? "Command refused" : response.value().error_message) << '\n'; return cli_exit_code(response); }
    std::cout << success << '\n';
    return 0;
}

int emit_guidance(const CliResponse& response, bool as_json)
{
    if (as_json) return emit_json(response);
    if (!response || !response.value().ok() || !response.value().parsed_payload) return emit_basic(response, false, "");
    const json::Value& report = *response.value().parsed_payload;
    const auto text = [&report](const char* key) {
        const json::Value* value = report.find(key);
        if (value == nullptr) return std::string();
        auto string = value->string_value();
        return string ? string.take_value() : std::string();
    };
    std::cout << text("command") << "\nStatus: " << text("status") << '\n';
    const json::Value* reasons = report.find("reasons");
    if (reasons != nullptr && reasons->is_array()) {
        for (std::size_t index = 0; index < reasons->size(); ++index) {
            const json::Value* reason = reasons->at(index);
            if (reason == nullptr || !reason->is_object()) continue;
            const auto field = [reason](const char* key) {
                const json::Value* value = reason->find(key);
                if (value == nullptr) return std::string();
                auto string = value->string_value();
                return string ? string.take_value() : std::string();
            };
            std::cout << "- [" << field("code") << "] " << field("summary") << "\n  Evidence: " << field("evidence") << '\n';
        }
    }
    std::cout << "No steps were executed. Use --json for the complete typed report.\n";
    return 0;
}

std::string fields_payload(const std::vector<std::pair<std::string, std::string>>& fields = {})
{
    json::ObjectBuilder output;
    for (const auto& field : fields) if (!field.second.empty()) output.add_string(field.first, field.second);
    return output.serialize();
}

std::string exact_fields_payload(const std::vector<std::pair<std::string, std::string>>& fields)
{
    json::ObjectBuilder output;
    for (const auto& field : fields) output.add_string(field.first, field.second);
    return output.serialize();
}

std::string roots_payload(const std::vector<std::string>& roots)
{
    json::ArrayBuilder values;
    for (const std::string& root : roots) values.add_string(root);
    json::ObjectBuilder output;
    output.add_array("roots", values);
    return output.serialize();
}

std::string preferences_payload(const std::vector<std::string>& args)
{
    json::ObjectBuilder output;
    for (const auto& field : std::vector<std::pair<std::string, std::string>> {
             {"preferred_workspace", option(args, "--preferred-workspace")},
             {"preferred_transport", option(args, "--transport")},
             {"default_instance_template", option(args, "--template")},
             {"default_launch_profile", option(args, "--profile")},
             {"display_color_policy", option(args, "--color")},
             {"tui_page_size", option(args, "--page-size")},
             {"command_timeout_seconds", option(args, "--timeout-seconds")},
             {"backup_destination", option(args, "--backup-destination")},
             {"backup_keep_last", option(args, "--backup-keep-last")},
         }) {
        if (!field.second.empty()) output.add_string(field.first, field.second);
    }
    for (const auto& array_field : std::vector<std::pair<std::string, std::vector<std::string>>> {
             {"discovery_providers", option_values(args, "--discovery-provider")},
             {"discovery_roots", option_values(args, "--discovery-root")},
         }) {
        if (array_field.second.empty()) continue;
        json::ArrayBuilder values;
        for (const std::string& value : array_field.second) values.add_string(value);
        output.add_array(array_field.first, values);
    }
    return output.serialize();
}

std::string profile_payload(
    const std::vector<std::string>& args,
    const std::vector<std::pair<std::string, std::string>>& identity)
{
    json::ObjectBuilder output;
    for (const auto& field : identity) output.add_string(field.first, field.second);
    for (const auto& field : std::vector<std::pair<std::string, std::string>> {
             {"template_id", option(args, "--template")}, {"window_mode", option(args, "--window-mode")},
             {"graphics_quality", option(args, "--graphics-quality")}, {"audio", option(args, "--audio")},
             {"selection_mode", option(args, "--selection-mode")}, {"selection", option(args, "--selection")},
             {"launch_mode", option(args, "--launch-mode")}, {"benchmark_ticks", option(args, "--benchmark-ticks")},
         }) if (!field.second.empty()) output.add_string(field.first, field.second);
    const auto arguments = option_values(args, "--arg");
    if (!arguments.empty()) {
        json::ArrayBuilder values;
        for (const std::string& value : arguments) values.add_string(value);
        output.add_array("additional_arguments", values);
    }
    return output.serialize();
}

std::string modset_solver_payload(
    const std::vector<std::string>& args,
    const std::string& instance,
    const std::string& transaction = {})
{
    json::ObjectBuilder output;
    output.add_string("instance_id", instance);
    if (!transaction.empty()) output.add_string("transaction_id", transaction);
    for (const auto& field : std::vector<std::pair<std::string, std::vector<std::string>>> {
             {"enabled_mods", option_values(args, "--enable")},
             {"disabled_mods", option_values(args, "--disable")},
             {"version_preferences", option_values(args, "--prefer")},
         }) {
        if (field.second.empty()) continue;
        json::ArrayBuilder values;
        for (const std::string& value : field.second) values.add_string(value);
        output.add_array(field.first, values);
    }
    for (const auto& field : std::vector<std::pair<std::string, std::string>> {
             {"maximum_packages", option(args, "--max-packages")},
             {"maximum_versions_per_package", option(args, "--max-versions-per-package")},
             {"maximum_graph_edges", option(args, "--max-graph-edges")},
             {"maximum_solver_states", option(args, "--max-solver-states")},
             {"maximum_backtracks", option(args, "--max-backtracks")},
             {"maximum_elapsed_ms", option(args, "--max-elapsed-ms")},
             {"maximum_explanation_nodes", option(args, "--max-explanation-nodes")},
         }) if (!field.second.empty()) output.add_string(field.first, field.second);
    return output.serialize();
}

std::string save_index_payload(
    const std::vector<std::string>& args,
    const std::vector<std::pair<std::string, std::string>>& identity)
{
    json::ObjectBuilder output;
    for (const auto& field : identity) output.add_string(field.first, field.second);
    for (const auto& field : std::vector<std::pair<std::string, std::string>> {
             {"profile_id", option(args, "--profile")}, {"source_operation", option(args, "--source-operation")},
             {"keep_last", option(args, "--keep-last")}, {"keep_daily", option(args, "--keep-daily")},
             {"keep_weekly", option(args, "--keep-weekly")}, {"maximum_total_bytes", option(args, "--max-total-bytes")},
             {"minimum_age_days", option(args, "--min-age-days")},
         }) if (!field.second.empty()) output.add_string(field.first, field.second);
    return output.serialize();
}

std::string transport_response(
    const std::string& request_id,
    const std::string& command,
    const facman::core::Result<facman::client::CommandResponse>& response,
    unsigned int protocol_version = 1,
    const std::string& operation_id = {},
    const std::string& attempt_id = {})
{
    json::ObjectBuilder output;
    output.add_string(
        "schema",
        protocol_version == 2 ? "facman.transport_response.v2" : "facman.transport_response.v1");
    output.add_string("request_id", request_id);
    output.add_unsigned_integer("protocol_version", protocol_version);
    output.add_string("command", command);
    output.add_string(
        "outcome",
        response ? response.value().outcome : facman::core::outcome_kind_name(response.error().kind));
    if (response && response.value().parsed_payload) output.add_value("payload", *response.value().parsed_payload);
    else output.add_null("payload");
    if (response && response.value().ok()) {
        output.add_null("error");
    } else {
        json::ObjectBuilder error;
        error.add_string("code", response ? response.value().error_code : response.error().code);
        error.add_string("message", response ? response.value().error_message : response.error().message);
        output.add_object("error", error);
    }
    json::ArrayBuilder diagnostics;
    json::ArrayBuilder effects;
    output.add_array("diagnostics", diagnostics);
    output.add_array("effects", effects);
    if (protocol_version == 2) {
        facman::client::OperationResult operation;
        if (response) {
            operation = response.value().operation;
        } else {
            operation.operation_id = operation_id;
            operation.attempt_id = attempt_id;
            operation.outcome = facman::client::OperationOutcome::refused_before_effects;
        }
        auto operation_value = json::parse(facman::client::operation_result_json(operation));
        if (operation_value) output.add_value("operation", operation_value.value());
    }
    return output.serialize();
}

int transport_refusal(
    const std::string& request_id,
    const std::string& command,
    const std::string& code,
    const std::string& message,
    unsigned int protocol_version = 1,
    const std::string& operation_id = {},
    const std::string& attempt_id = {})
{
    facman::core::OutcomeKind kind =
        code == "transport_protocol_invalid" || code == "transport_request_invalid" ||
            code == "transport_input_too_large"
        ? facman::core::OutcomeKind::invalid_argument
        : code == "transport_output_too_large"
            ? facman::core::OutcomeKind::internal_error
            : facman::core::OutcomeKind::refused;
    auto failure = facman::core::Result<facman::client::CommandResponse>::failure({code, message, "$", kind});
    std::cout << transport_response(
        request_id, command, failure, protocol_version, operation_id, attempt_id) << '\n';
    return outcome_exit_code(kind);
}

std::string json_string_field(const json::Value& object, const char* key)
{
    const auto* field = object.find(key);
    if (field == nullptr) return {};
    auto value = field->string_value();
    return value ? value.take_value() : std::string();
}

int command_rpc(const Options& options)
{
    if (!flag(options.args, "--stdio")) return 2;
    std::string input;
    input.resize(kTransportInputLimit + 1);
    std::cin.read(input.data(), static_cast<std::streamsize>(input.size()));
    input.resize(static_cast<std::size_t>(std::cin.gcount()));
    if (input.size() >= 3U && static_cast<unsigned char>(input[0]) == 0xEFU &&
        static_cast<unsigned char>(input[1]) == 0xBBU && static_cast<unsigned char>(input[2]) == 0xBFU) {
        input.erase(0, 3);
    }
    if (input.size() > kTransportInputLimit) {
        return transport_refusal("", "", "transport_input_too_large", "Transport request exceeds the input budget");
    }
    json::Limits limits;
    limits.maximum_bytes = kTransportInputLimit;
    limits.maximum_depth = 32;
    limits.maximum_nodes = 32768;
    limits.maximum_string_bytes = 512U * 1024U;
    auto document = json::parse(input, limits);
    if (!document || !document.value().is_object()) {
        return transport_refusal("", "", "transport_request_invalid", document ? "Transport request must be an object" : document.error().message);
    }
    const json::Value& request = document.value();
    const std::string request_id = json_string_field(request, "request_id");
    const std::string command = json_string_field(request, "command");
    const std::string schema = json_string_field(request, "schema");
    const std::string operation_id = json_string_field(request, "operation_id");
    const std::string attempt_id = json_string_field(request, "attempt_id");
    const auto* version = request.find("protocol_version");
    const auto* dry_run = request.find("dry_run");
    const auto* payload = request.find("payload");
    const bool protocol_v1 =
        schema == "facman.transport_request.v1" &&
        version != nullptr &&
        version->unsigned_integer_value() &&
        version->unsigned_integer_value().value() == 1;
    facman::client::OperationResult identity_probe;
    identity_probe.operation_id = operation_id;
    identity_probe.attempt_id = attempt_id;
    const bool protocol_v2 =
        schema == "facman.transport_request.v2" &&
        version != nullptr &&
        version->unsigned_integer_value() &&
        version->unsigned_integer_value().value() == 2 &&
        facman::client::operation_result_valid(identity_probe);
    if ((!protocol_v1 && !protocol_v2) || request_id.empty() || command.empty() ||
        dry_run == nullptr || !dry_run->bool_value() || payload == nullptr || !payload->is_object()) {
        return transport_refusal(
            request_id,
            command,
            "transport_protocol_invalid",
            "Transport request does not satisfy protocol v1 or v2");
    }
    const std::string requested_workspace = json_string_field(request, "workspace");
    if (requested_workspace.empty() && options.workspace_error) {
        return transport_refusal(
            request_id,
            command,
            options.workspace_error->code,
            options.workspace_error->message,
            protocol_v2 ? 2U : 1U,
            operation_id,
            attempt_id);
    }
    const std::string workspace = requested_workspace.empty() ? options.workspace : requested_workspace;
    facman::client::FacManClient client(
        std::make_unique<facman::client::DirectFlbTransport>(facman::platform::path_from_utf8(workspace)));
    facman::client::CommandRequest client_request {
        command, payload->serialize(), dry_run->bool_value().value()};
    client_request.request_id = request_id;
    if (protocol_v2) {
        client_request.operation_id = operation_id;
        client_request.attempt_id = attempt_id;
    }
    auto response = client.execute(client_request);
    std::string output = transport_response(
        request_id,
        command,
        response,
        protocol_v2 ? 2U : 1U,
        operation_id,
        attempt_id);
    if (output.size() > kTransportOutputLimit) {
        return transport_refusal(
            request_id,
            command,
            "transport_output_too_large",
            "Transport response exceeds the output budget",
            protocol_v2 ? 2U : 1U,
            operation_id,
            attempt_id);
    }
    std::cout << output << '\n';
    return response
        ? outcome_exit_code(response.value().outcome_kind, response.value().operation.outcome)
        : outcome_exit_code(response.error().kind);
}

int command_product(const Options& options)
{
    if (options.args.size() < 2 || options.args[1] != "inspect") return 2;
    auto response = call(options, "product.inspect");
    if (flag(options.args, "--json")) return emit_json(response);
    if (!response || !response.value().ok()) return cli_exit_code(response);
    std::cout << "FacMan - an unofficial launcher and isolated instance manager for Factorio\nProduct ID: factorio\nBundles Factorio binaries: no\nDefault run mode: dry-run\n";
    return 0;
}

int command_doctor(const Options& options)
{
    if (options.args.size() >= 2 && options.args[1] == "explain") {
        return emit_guidance(call(options, "doctor.explain"), flag(options.args, "--json"));
    }
    const std::string bundle = option(options.args, "--diagnostic-bundle");
    if (!bundle.empty()) {
        const std::string instance = option(options.args, "--instance");
        if (instance.empty()) { std::cerr << "doctor --diagnostic-bundle requires --instance\n"; return 2; }
        return emit_basic(call(options, "diagnostics.export", exact_fields_payload({{"instance_id", instance}, {"output_path", bundle}}), false), flag(options.args, "--json"), "Diagnostic bundle exported");
    }
    std::vector<std::string> roots = option_values(options.args, "--path");
    const auto search = option_values(options.args, "--search-root"); roots.insert(roots.end(), search.begin(), search.end());
    auto response = call(options, "doctor.run", roots_payload(roots));
    if (flag(options.args, "--json")) return emit_json(response);
    if (!response || !response.value().ok()) return cli_exit_code(response);
    const std::string status = response.value().payload_string("status");
    std::cout << "FacMan doctor\nStatus: " << status << '\n';
    if (status == "warning") std::cout << "Warning: no install references registered yet\nSuggestion: scan or import a Factorio install reference\n";
    return 0;
}

int command_installs(const Options& options)
{
    if (options.args.size() < 2) return 2;
    const std::string action = options.args[1];
    if (action == "workflow") {
        if (flag(options.args, "--json")) {
            return emit_json(local_success("installs.workflow", kGeneratedSetupWorkflowJson));
        }
        std::cout << kGeneratedSetupWorkflowText << '\n';
        return 0;
    }
    if (action == "list") {
        auto response = call(options, "install_refs.list");
        return emit_basic(response, flag(options.args, "--json"), "Install references listed");
    }
    if (action == "scan") {
        std::vector<std::string> roots = option_values(options.args, "--path");
        for (const char* name : {"--search-root", "--roots"}) { const auto more = option_values(options.args, name); roots.insert(roots.end(), more.begin(), more.end()); }
        return emit_basic(call(options, "install_refs.scan", roots_payload(roots)), flag(options.args, "--json"), "Install scan completed");
    }
    if (action == "import" && options.args.size() >= 3) {
        const std::string id = option(options.args, "--id", slugify(options.args[2]));
        auto response = call(options, "install_refs.import", exact_fields_payload({{"path", options.args[2]}, {"install_id", id}}), false);
        if (flag(options.args, "--json")) return emit_json(response);
        if (!response || !response.value().ok()) return cli_exit_code(response);
        std::cout << "Registered " << id << " at " << response.value().payload_string("root") << '\n';
        return 0;
    }
    if (action == "inspect" && options.args.size() >= 3) return emit_basic(call(options, "install_refs.inspect", exact_fields_payload({{"install_id", options.args[2]}})), flag(options.args, "--json"), "Install inspected");
    if (action == "describe" && options.args.size() >= 3) return emit_basic(
        call(options, "installs.describe", exact_fields_payload({{"install_id", options.args[2]}})),
        flag(options.args, "--json"), "Installation model described");
    if (action == "reconcile" && options.args.size() >= 4 && options.args[2] == "plan") {
        std::vector<std::pair<std::string, std::string>> fields = {{"install_id", options.args[3]}};
        for (const auto& [option_name, field_name] : std::vector<std::pair<std::string, std::string>>{
                 {"--version", "version"}, {"--source-ref", "source_ref"}, {"--target", "target_root"},
                 {"--management", "management_mode"}, {"--deployment-style", "deployment_style"},
                 {"--data-policy", "data_policy"}, {"--integration", "integration_mode"},
                 {"--update-policy", "update_policy"}}) {
            const std::string value = option(options.args, option_name);
            if (!value.empty()) fields.push_back({field_name, value});
        }
        return emit_basic(
            call(options, "installs.reconcile.plan", exact_fields_payload(fields)),
            flag(options.args, "--json"), "Installation reconciliation plan rendered");
    }
    if (action == "install" && options.args.size() >= 4) {
        const std::string phase = options.args[2];
        if (phase == "plan") {
            const std::string archive = option(options.args, "--archive");
            const std::string target = option(options.args, "--target");
            const std::string install_id = option(options.args, "--id");
            if (archive.empty() || target.empty() || install_id.empty()) return 2;
            return emit_basic(
                call(options, "installs.install.plan", exact_fields_payload({
                    {"version", options.args[3]}, {"archive", archive},
                    {"target_root", target}, {"install_id", install_id}})),
                flag(options.args, "--json"),
                "Managed install plan reviewed through Universal Setup.");
        }
        if (phase == "apply") {
            const std::string digest = option(options.args, "--digest");
            const std::string confirmation = option(options.args, "--confirm");
            if (digest.empty() || confirmation != "APPLY") return 2;
            return emit_basic(
                call(options, "installs.install.apply", exact_fields_payload({
                    {"plan_id", options.args[3]}, {"plan_digest", digest},
                    {"confirmation", confirmation}}), false),
                flag(options.args, "--json"),
                "Managed install apply dispatched.");
        }
        return 2;
    }
    if ((action == "repair" || action == "move" || action == "uninstall") && options.args.size() >= 4 &&
        (options.args[2] == "plan" || options.args[2] == "apply")) {
        const std::string phase = options.args[2];
        if (phase == "plan") {
            std::vector<std::pair<std::string, std::string>> fields = {{"install_id", options.args[3]}};
            if (action == "repair") fields.push_back({"archive", option(options.args, "--archive")});
            if (action == "move") {
                const std::string target = option(options.args, "--target");
                if (target.empty()) return 2;
                fields.push_back({"target_root", target});
            }
            return emit_basic(
                call(options, "installs." + action + ".plan", exact_fields_payload(fields)),
                flag(options.args, "--json"),
                "Managed " + action + " plan reviewed through Universal Setup.");
        }
        if (phase == "apply") {
            const std::string digest = option(options.args, "--digest");
            const std::string confirmation = option(options.args, "--confirm");
            if (digest.empty() || confirmation != "APPLY") return 2;
            return emit_basic(
                call(options, "installs." + action + ".apply", exact_fields_payload({
                    {"plan_id", options.args[3]}, {"plan_digest", digest},
                    {"confirmation", confirmation}}), false),
                flag(options.args, "--json"),
                "Managed " + action + " apply dispatched.");
        }
        return 2;
    }
    if (action == "recovery" && options.args.size() >= 4) {
        const std::string phase = options.args[2];
        if (phase == "inspect") {
            return emit_basic(
                call(options, "installs.recovery.inspect", exact_fields_payload({
                    {"transaction_id", options.args[3]}})),
                flag(options.args, "--json"),
                "Setup recovery state inspected.");
        }
        if (phase == "apply") {
            const std::string digest = option(options.args, "--digest");
            const std::string confirmation = option(options.args, "--confirm");
            if (digest.empty() || confirmation != "APPLY") return 2;
            return emit_basic(
                call(options, "installs.recovery.apply", exact_fields_payload({
                    {"plan_id", options.args[3]}, {"plan_digest", digest},
                    {"confirmation", confirmation}}), false),
                flag(options.args, "--json"),
                "Setup recovery apply dispatched.");
        }
        return 2;
    }
    if (action == "install-version" && options.args.size() >= 3) {
        const std::string archive = option(options.args, "--archive");
        return emit_basic(
            call(options, "installs.install_version", fields_payload(
                {{"version", options.args[2]}, {"archive", archive}})),
            flag(options.args, "--json"),
            "Managed install plan created through Universal Setup.");
    }
    if ((action == "verify" || action == "repair" || action == "uninstall") && options.args.size() >= 3) {
        return emit_basic(call(options, "installs." + action, fields_payload({{"id", options.args[2]}})), flag(options.args, "--json"), "Setup operation previewed");
    }
    return 2;
}

int command_instances(const Options& options)
{
    if (options.args.size() < 2) return 2;
    if (options.args[1] == "list") {
        auto response = call(options, "instance.list");
        return emit_basic(response, flag(options.args, "--json"), "Instances listed");
    }
    if (options.args[1] == "create" && options.args.size() >= 3) {
        const std::string install = option(options.args, "--install");
        if (install.empty()) return 2;
        const std::string id = option(options.args, "--id", slugify(options.args[2]));
        std::vector<std::pair<std::string, std::string>> fields = {
            {"display_name", options.args[2]}, {"instance_id", id}, {"install_id", install},
            {"template_id", option(options.args, "--template", "vanilla")}};
        const std::string source_data_root = option(options.args, "--import-data");
        if (!source_data_root.empty()) fields.push_back({"source_data_root", source_data_root});
        const std::string payload = exact_fields_payload(fields);
        return emit_basic(call(options, "instance.create", payload, false), flag(options.args, "--json"), "Created instance " + id);
    }
    const std::string action = options.args[1];
    if ((action == "describe" || action == "readiness") && options.args.size() >= 3) {
        for (std::size_t index = 3; index < options.args.size(); ++index) {
            if (options.args[index] == "--json") continue;
            if (options.args[index] != "--intent" || index + 1 >= options.args.size()) return 2;
            ++index;
        }
        return emit_basic(
            call(options, "instances." + action, fields_payload({
                {"instance_id", options.args[2]}, {"intent", option(options.args, "--intent")}})),
            flag(options.args, "--json"), "Instance " + action + " completed");
    }
    if ((action == "inspect" || action == "verify" || action == "archive") && options.args.size() >= 3) {
        for (std::size_t index = 3; index < options.args.size(); ++index) if (options.args[index] != "--json") return 2;
        return emit_basic(
            call(options, "instances." + action, exact_fields_payload({{"instance_id", options.args[2]}}), action != "archive"),
            flag(options.args, "--json"), "Instance " + action + " completed");
    }
    if (action == "diff" && options.args.size() >= 4) {
        for (std::size_t index = 4; index < options.args.size(); ++index) if (options.args[index] != "--json") return 2;
        return emit_basic(call(options, "instances.diff", exact_fields_payload({
            {"left_instance_id", options.args[2]}, {"right_ref", options.args[3]}})),
            flag(options.args, "--json"), "Instance diff completed");
    }
    if (action == "clone" && options.args.size() >= 4) {
        for (std::size_t index = 4; index < options.args.size(); ++index) {
            if (options.args[index] == "--json") continue;
            if ((options.args[index] != "--name" && options.args[index] != "--install") || index + 1 >= options.args.size()) return 2;
            ++index;
        }
        return emit_basic(call(options, "instances.clone", fields_payload({
            {"source_instance_id", options.args[2]}, {"destination_instance_id", options.args[3]},
            {"display_name", option(options.args, "--name")}, {"install_ref", option(options.args, "--install")}}), false),
            flag(options.args, "--json"), "Instance clone completed");
    }
    if (action == "rename" && options.args.size() >= 3) {
        const std::string name = option(options.args, "--name");
        if (name.empty()) return 2;
        for (std::size_t index = 3; index < options.args.size(); ++index) {
            if (options.args[index] == "--json") continue;
            if (options.args[index] != "--name" || index + 1 >= options.args.size()) return 2;
            ++index;
        }
        return emit_basic(call(options, "instances.rename", exact_fields_payload({
            {"instance_id", options.args[2]}, {"display_name", name}}), false),
            flag(options.args, "--json"), "Instance display name updated");
    }
    if (action == "restore" && options.args.size() >= 3) {
        for (std::size_t index = 3; index < options.args.size(); ++index) {
            if (options.args[index] == "--json") continue;
            if (options.args[index] != "--new-id" || index + 1 >= options.args.size()) return 2;
            ++index;
        }
        return emit_basic(call(options, "instances.restore", fields_payload({
            {"archive_id", options.args[2]}, {"new_instance_id", option(options.args, "--new-id")}}), false),
            flag(options.args, "--json"), "Instance restored");
    }
    return 2;
}

int command_mods(const Options& options)
{
    if (options.args.size() < 2) return 2;
    const std::string action = options.args[1];
    if (action == "list") return emit_basic(call(options, "mods.list"), flag(options.args, "--json"), "Local mods listed");
    if (action == "index") {
        json::ArrayBuilder roots;
        for (const std::string& root : option_values(options.args, "--root")) roots.add_string(root);
        json::ObjectBuilder payload;
        payload.add_array("roots", roots);
        return emit_basic(call(options, "mods.index", payload.serialize()), flag(options.args, "--json"), "Local mods indexed");
    }
    if ((action == "inspect" || action == "verify" || action == "explain") && options.args.size() >= 3) return emit_basic(
        call(options, "mods." + action, exact_fields_payload({{"identity", options.args[2]}})),
        flag(options.args, "--json"), "Local mod " + action + " completed");
    if (action == "import" && options.args.size() >= 3) {
        const std::string instance = option(options.args, "--instance");
        return emit_basic(call(options, "mods.import", exact_fields_payload({{"source_path", options.args[2]}, {"instance_id", instance}}), false), flag(options.args, "--json"), "Mod imported");
    }
    if (action == "search" || action == "install" || action == "update") {
        const std::string query = options.args.size() >= 3 && action != "update" ? options.args[2] : "";
        return emit_basic(call(options, "mods." + action, fields_payload({{"query", query}, {"instance_id", option(options.args, "--instance")}}), false), flag(options.args, "--json"), "");
    }
    return 2;
}

int command_snapshots(const Options& options)
{
    if (options.args.size() < 3) return 2;
    const std::string action = options.args[1];
    const bool as_json = flag(options.args, "--json");
    if (action == "create" && options.args.size() >= 4) {
        for (std::size_t index = 4; index < options.args.size(); ++index) {
            if (options.args[index] == "--json") continue;
            if (options.args[index] != "--save" || index + 1 >= options.args.size()) return 2;
            ++index;
        }
        json::ArrayBuilder saves;
        for (const std::string& value : option_values(options.args, "--save")) saves.add_string(value);
        json::ObjectBuilder payload;
        payload.add_string("instance_id", options.args[2]);
        payload.add_string("snapshot_id", options.args[3]);
        payload.add_array("saves", saves);
        return emit_basic(call(options, "snapshots.create", payload.serialize(), false), as_json, "Snapshot created");
    }
    if (action == "list") return emit_basic(call(options, "snapshots.list", exact_fields_payload(
        {{"instance_id", options.args[2]}})), as_json, "Snapshots listed");
    if ((action == "inspect" || action == "verify") && options.args.size() >= 4) {
        return emit_basic(call(options, "snapshots." + action, exact_fields_payload(
            {{"instance_id", options.args[2]}, {"snapshot_id", options.args[3]}})), as_json, "Snapshot " + action + " completed");
    }
    if (action == "diff" && options.args.size() >= 5) {
        return emit_basic(call(options, "snapshots.diff", exact_fields_payload({
            {"instance_id", options.args[2]}, {"left_snapshot_id", options.args[3]},
            {"right_snapshot_id", options.args[4]}})), as_json, "Snapshot diff completed");
    }
    if (action == "restore" && options.args.size() >= 4) {
        return emit_basic(call(options, "snapshots.restore", exact_fields_payload({
            {"snapshot_ref", options.args[2]}, {"target_instance_id", options.args[3]}}), false), as_json, "Snapshot restored");
    }
    if (action == "retention" && options.args.size() >= 4 &&
        (options.args[2] == "plan" || options.args[2] == "apply")) {
        const std::set<std::string> value_options = {
            "--keep-last", "--keep-daily", "--keep-weekly", "--maximum-total-bytes", "--minimum-age-days"};
        for (std::size_t index = 4; index < options.args.size(); ++index) {
            if (options.args[index] == "--json") continue;
            if (value_options.count(options.args[index]) == 0 || index + 1 >= options.args.size()) return 2;
            ++index;
        }
        const std::string payload = fields_payload({
            {"instance_id", options.args[3]}, {"keep_last", option(options.args, "--keep-last")},
            {"keep_daily", option(options.args, "--keep-daily")}, {"keep_weekly", option(options.args, "--keep-weekly")},
            {"maximum_total_bytes", option(options.args, "--maximum-total-bytes")},
            {"minimum_age_days", option(options.args, "--minimum-age-days")}});
        const bool apply = options.args[2] == "apply";
        return emit_basic(call(options, "snapshots.retention." + options.args[2], payload, !apply), as_json,
            apply ? "Snapshot retention applied" : "Snapshot retention planned");
    }
    return 2;
}

int command_templates(const Options& options)
{
    if (options.args.size() < 2) return 2;
    const std::string action = options.args[1];
    if (action == "list") return emit_basic(call(options, "templates.list"), flag(options.args, "--json"), "Templates listed");
    if ((action == "inspect" || action == "validate") && options.args.size() >= 3) return emit_basic(
        call(options, "templates." + action, exact_fields_payload({{"template_id", options.args[2]}})),
        flag(options.args, "--json"), "Template " + action + " completed");
    return 2;
}

int command_profiles(const Options& options)
{
    if (options.args.size() < 2) return 2;
    const std::string action = options.args[1];
    const bool as_json = flag(options.args, "--json");
    if (action == "list") return emit_basic(call(options, "profiles.list"), as_json, "Profiles listed");
    if ((action == "inspect" || action == "archive") && options.args.size() >= 3) return emit_basic(
        call(options, "profiles." + action, exact_fields_payload({{"profile_id", options.args[2]}}), action != "archive"),
        as_json, "Profile " + action + " completed");
    if (action == "create" && options.args.size() >= 3) return emit_basic(
        call(options, "profiles.create", profile_payload(options.args, {{"profile_id", options.args[2]}}), false),
        as_json, "Profile created");
    if ((action == "clone" || action == "diff") && options.args.size() >= 4) {
        const auto fields = action == "clone"
            ? std::vector<std::pair<std::string, std::string>> {{"source_profile_id", options.args[2]}, {"destination_profile_id", options.args[3]}}
            : std::vector<std::pair<std::string, std::string>> {{"left_profile_id", options.args[2]}, {"right_profile_id", options.args[3]}};
        return emit_basic(call(options, "profiles." + action, exact_fields_payload(fields), action == "diff"), as_json,
            "Profile " + action + " completed");
    }
    if ((action == "plan" || action == "apply") && options.args.size() >= 4) return emit_basic(
        call(options, "profiles." + action, profile_payload(options.args,
            {{"instance_id", options.args[2]}, {"profile_id", options.args[3]}}), action == "plan"),
        as_json, "Profile " + action + " completed");
    return 2;
}

int command_modsets(const Options& options)
{
    if (options.args.size() < 3) return 2;
    const std::string action = options.args[1], instance = options.args[2];
    if (action == "plan" || action == "diff" || action == "explain" || action == "apply") {
        return emit_basic(call(options, "modsets." + action, modset_solver_payload(options.args, instance), action != "apply"),
            flag(options.args, "--json"), "Modset " + action + " completed");
    }
    if (action == "rollback" && options.args.size() >= 4) {
        return emit_basic(call(options, "modsets.rollback", modset_solver_payload(options.args, instance, options.args[3]), false),
            flag(options.args, "--json"), "Modset rollback completed");
    }
    if (action == "lock" || action == "verify") return emit_basic(call(options, "modsets." + action, exact_fields_payload({{"instance_id", instance}}), action == "verify"), flag(options.args, "--json"), "Modset " + action + " completed");
    if (action == "export" && options.args.size() >= 4) {
        return emit_basic(
            call(options, "modsets.export", exact_fields_payload({{"instance_id", instance}, {"output_path", options.args[3]}}), false),
            flag(options.args, "--json"),
            "Modset exported");
    }
    return 2;
}

int command_saves(const Options& options)
{
    if (options.args.size() < 2) return 2;
    const std::string action = options.args[1];
    const std::string instance = option(options.args, "--instance");
    if (action == "index") return emit_basic(call(options, "saves.index", save_index_payload(
        options.args, {{"instance_id", instance}})), flag(options.args, "--json"), "Saves indexed");
    if ((action == "inspect" || action == "verify" || action == "associate") && options.args.size() >= 3) {
        return emit_basic(call(options, "saves." + action, save_index_payload(options.args,
            {{"instance_id", instance}, {"save", options.args[2]}}), action != "associate"),
            flag(options.args, "--json"), "Save " + action + " completed");
    }
    if (action == "diff" && options.args.size() >= 4) return emit_basic(call(options, "saves.diff", save_index_payload(
        options.args, {{"instance_id", instance}, {"save", options.args[2]}, {"other_save", options.args[3]}})),
        flag(options.args, "--json"), "Save diff completed");
    if (action == "retention" && options.args.size() >= 3 && (options.args[2] == "plan" || options.args[2] == "apply")) {
        const bool apply = options.args[2] == "apply";
        return emit_basic(call(options, "saves.retention." + options.args[2], save_index_payload(
            options.args, {{"instance_id", instance}}), !apply), flag(options.args, "--json"), "Save retention completed");
    }
    if (action == "list") return emit_basic(call(options, "saves.list", exact_fields_payload({{"instance_id", option(options.args, "--instance")}})), flag(options.args, "--json"), "Saves listed");
    if (action == "backup" && options.args.size() >= 3) {
        const std::string payload = exact_fields_payload({{"instance_id", option(options.args, "--instance")},
            {"save", options.args[2]}, {"output_path", option(options.args, "--to")}});
        return emit_basic(
            call(options, "saves.backup", payload, false),
            flag(options.args, "--json"),
            "Save backed up");
    }
    if (action == "clone" && options.args.size() >= 3) {
        const std::string payload = exact_fields_payload({{"source_instance_id", option(options.args, "--instance")},
            {"target_instance_id", option(options.args, "--to-instance")}, {"save", options.args[2]}});
        return emit_basic(
            call(options, "saves.clone", payload, false),
            flag(options.args, "--json"),
            "Save cloned");
    }
    return 2;
}

int command_diagnostics(const Options& options)
{
    if (options.args.size() < 2) return 2;
    if (options.args[1] == "report") return emit_basic(call(options, "diagnostics.run"), flag(options.args, "--json"), "Diagnostics completed");
    if (options.args[1] == "redact" && options.args.size() >= 3) {
        return emit_basic(
            call(options, "diagnostics.redact", fields_payload(
                {{"path", options.args[2]}}), false),
            flag(options.args, "--json"),
            "Diagnostic input redacted");
    }
    if (options.args[1] == "export") {
        const std::string instance = option(options.args, "--instance"), output = option(options.args, "--out");
        return emit_basic(call(options, "diagnostics.export", exact_fields_payload({{"instance_id", instance}, {"output_path", output}}), false), flag(options.args, "--json"), "Diagnostic bundle exported");
    }
    return 2;
}

int command_launch(const Options& options, bool run, bool play = false)
{
    if (!run && options.args.size() >= 3 && options.args[0] == "launch" && options.args[1] == "explain") {
        return emit_guidance(call(options, "launch_plan.explain", exact_fields_payload({{"instance_id", options.args[2]}})), flag(options.args, "--json"));
    }
    std::size_t id_index = 1;
    if (!run && options.args[0] == "launch" && options.args.size() > 2 && options.args[1] == "plan") id_index = 2;
    if (options.args.size() <= id_index) return 2;
    const std::string instance = options.args[id_index];
    if (play || (run && flag(options.args, "--execute"))) {
        return emit_basic(
            call(options, "run.execute", exact_fields_payload({{"instance_id", instance}}), false),
            flag(options.args, "--json"),
            "Play session completed");
    }
    const std::string command = run ? "run.preview" : flag(options.args, "--preflight") ? "launch_plan.preflight" : "launch_plan.build";
    auto response = call(options, command, exact_fields_payload({{"instance_id", instance}}));
    if (flag(options.args, "--json")) return emit_json(response);
    if (!response || !response.value().ok()) return cli_exit_code(response);
    if (run) {
        std::cout << "Dry-run only\n" << response.value().payload_string("command_line")
                  << "\nNo process was started.\n";
    }
    else std::cout << "Launch plan created; no process was started.\n";
    return 0;
}

int command_transfer(const Options& options, bool exporting)
{
    if (options.args.size() < (exporting ? 4U : 3U) || options.args[1] != "instance") return 2;
    if (exporting) return emit_basic(call(options, "instance.export", exact_fields_payload({{"instance_id", options.args[2]}, {"output_path", options.args[3]}}), false), flag(options.args, "--json"), "Instance exported");
    return emit_basic(call(options, "instance.import", exact_fields_payload({{"source_path", options.args[2]}, {"instance_id", option(options.args, "--id")}}), false), flag(options.args, "--json"), "Instance imported");
}

int command_servers(const Options& options)
{
    if (options.args.size() < 2) return 2;
    const std::string action = options.args[1];
    if ((action == "inspect" || action == "validate" || action == "plan") && options.args.size() >= 3) {
        return emit_basic(call(options, "servers." + action, fields_payload({{"server_id", options.args[2]},
            {"save", option(options.args, "--save")}})), flag(options.args, "--json"), "Server " + action + " completed");
    }
    if (action == "diff" && options.args.size() >= 4) return emit_basic(call(options, "servers.diff", fields_payload(
        {{"server_id", options.args[2]}, {"other_server_id", options.args[3]}})), flag(options.args, "--json"), "Server diff completed");
    if (action == "export" && options.args.size() >= 4) return emit_basic(call(options, "servers.export", fields_payload(
        {{"server_id", options.args[2]}, {"output_path", options.args[3]}, {"save", option(options.args, "--save")},
         {"include_save", flag(options.args, "--include-save") ? "true" : "false"}}), false),
        flag(options.args, "--json"), "Server plan exported");
    std::vector<std::pair<std::string, std::string>> fields;
    if (action == "create" && options.args.size() >= 3) fields = {{"name", options.args[2]}, {"id", option(options.args, "--id")}, {"instance_id", option(options.args, "--instance")}};
    else if (action == "start" || action == "stop" || action == "rcon") { if (options.args.size() < 3) return 2; fields = {{"id", options.args[2]}}; }
    return emit_basic(call(options, "servers." + action, fields_payload(fields), false), flag(options.args, "--json"), action == "create" ? "Server profile created" : "Servers listed");
}

int command_dev(const Options& options)
{
    if (options.args.size() < 2) return 2;
    std::string action = options.args[1];
    std::replace(action.begin(), action.end(), '-', '_');
    return emit_basic(call(options, "dev." + action, "{}", false), flag(options.args, "--json"), "Bug report created");
}

int command_workspace(const Options& options)
{
    if (options.args.size() >= 2 && (options.args[1] == "status" || options.args[1] == "paths")) {
        return emit_guidance(call(options, "workspace." + options.args[1]), flag(options.args, "--json"));
    }
    if (options.args.size() < 3) return 2;
    const std::string family = options.args[1], action = options.args[2];
    if (family != "recovery" && family != "migration") return 2;
    std::string command = "workspace." + family + "." + action;
    std::string payload = "{}";
    if (family == "recovery" && action != "inspect") { if (options.args.size() < 4) return 2; payload = exact_fields_payload({{"transaction_id", options.args[3]}}); }
    return emit_basic(call(options, command, payload, action != "apply"), flag(options.args, "--json"), "Workspace operation completed");
}

int command_preferences(const Options& options)
{
    if (options.args.size() < 2) return 2;
    const bool as_json = flag(options.args, "--json");
    if (options.args[1] == "reset") {
        if (options.args.size() < 3 || (options.args[2] != "plan" && options.args[2] != "apply")) return 2;
        for (std::size_t index = 3; index < options.args.size(); ++index) {
            if (options.args[index] != "--json") return 2;
        }
        const bool apply = options.args[2] == "apply";
        return emit_basic(
            call(options, "preferences.reset." + options.args[2], "{}", !apply),
            as_json,
            apply ? "Preferences reset" : "Preferences reset plan created");
    }
    const std::string action = options.args[1];
    if (action != "inspect" && action != "validate" && action != "plan" && action != "apply") return 2;
    if (action == "inspect") {
        for (std::size_t index = 2; index < options.args.size(); ++index) {
            if (options.args[index] != "--json") return 2;
        }
    }
    const std::set<std::string> value_options = {
        "--preferred-workspace", "--transport", "--template", "--profile", "--color",
        "--page-size", "--timeout-seconds", "--backup-destination", "--backup-keep-last",
        "--discovery-provider", "--discovery-root",
    };
    for (std::size_t index = 2; index < options.args.size(); ++index) {
        if (options.args[index] == "--json") continue;
        if (value_options.count(options.args[index]) == 0 || index + 1 >= options.args.size()) return 2;
        ++index;
    }
    const std::string payload = action == "inspect" ? "{}" : preferences_payload(options.args);
    return emit_basic(
        call(options, "preferences." + action, payload, action != "apply"),
        as_json,
        "Preferences " + action + " completed");
}

int command_capabilities(const Options& options)
{
    if (options.args.size() < 2 || options.args[1] != "inspect") return 2;
    return emit_guidance(call(options, "capabilities.inspect"), flag(options.args, "--json"));
}

int command_onboarding(const Options& options)
{
    if (options.args.size() < 2 || options.args[1] != "plan") return 2;
    return emit_guidance(
        call(options, "onboarding.plan", fields_payload({
            {"preferred_install", option(options.args, "--preferred-install")},
            {"instance_display_name", option(options.args, "--name")},
            {"template_id", option(options.args, "--template")},
            {"workspace", options.workspace}})),
        flag(options.args, "--json"));
}

int command_package(const Options& options)
{
    if (options.args.size() < 2 || options.args[1] != "verify") return 2;
    return emit_basic(call(options, "package.verify"), flag(options.args, "--json"), "Package integrity verified");
}

int command_graph(const Options& options)
{
    if (options.args.size() < 2 || options.args[1] != "inspect") return 2;
    return emit_basic(call(options, "command_graph.inspect"), flag(options.args, "--json"), "Command graph inspected");
}

int command_presentation(const Options& options)
{
    if (options.args.size() < 3) return 2;
    const bool as_json = flag(options.args, "--json");
    if (options.args[1] == "query") {
        return emit_basic(call(options, "presentation.query", fields_payload({
            {"scope", options.args[2]},
            {"selected_instance_id", option(options.args, "--instance")},
            {"search", option(options.args, "--search")},
            {"known_revision", option(options.args, "--known-revision")}})),
            as_json, "Presentation snapshot computed");
    }
    if (options.args[1] == "action") {
        const std::string scope = option(options.args, "--scope");
        const std::string expected = option(options.args, "--expected-revision");
        const std::string request_id = option(options.args, "--request-id");
        if (scope.empty() || expected.empty() || request_id.empty()) return 2;
        json::ObjectBuilder payload;
        payload.add_string("action_id", options.args[2]);
        payload.add_string("scope", scope);
        payload.add_string("expected_snapshot_revision", expected);
        payload.add_string("request_id", request_id);
        const std::string instance = option(options.args, "--instance");
        const std::string key = option(options.args, "--idempotency-key");
        const std::string operation = option(options.args, "--operation-id");
        const std::string attempt = option(options.args, "--attempt-id");
        const std::string confirmation = option(options.args, "--confirmation");
        const std::string installation = option(options.args, "--installation");
        const std::string installation_path = option(options.args, "--installation-path");
        const std::string new_instance = option(options.args, "--new-instance");
        const std::string display_name = option(options.args, "--display-name");
        const std::string template_id = option(options.args, "--template");
        const std::string profile_id = option(options.args, "--profile");
        const std::string mod_identity = option(options.args, "--mod");
        const std::string save = option(options.args, "--save");
        const std::string output_path = option(options.args, "--output");
        const std::string source_data_root = option(options.args, "--source-data-root");
        const std::string transaction = option(options.args, "--transaction");
        if (!instance.empty()) payload.add_string("selected_instance_id", instance);
        if (!key.empty()) payload.add_string("idempotency_key", key);
        if (!operation.empty()) payload.add_string("durable_operation_id", operation);
        if (!attempt.empty()) payload.add_string("attempt_id", attempt);
        if (!confirmation.empty()) payload.add_string("confirmation", confirmation);
        if (!installation.empty()) payload.add_string("installation_id", installation);
        if (!installation_path.empty()) payload.add_string("installation_path", installation_path);
        if (!new_instance.empty()) payload.add_string("new_instance_id", new_instance);
        if (!display_name.empty()) payload.add_string("display_name", display_name);
        if (!template_id.empty()) payload.add_string("template_id", template_id);
        if (!profile_id.empty()) payload.add_string("profile_id", profile_id);
        if (!mod_identity.empty()) payload.add_string("mod_identity", mod_identity);
        if (!save.empty()) payload.add_string("save", save);
        if (!output_path.empty()) payload.add_string("output_path", output_path);
        if (!source_data_root.empty()) payload.add_string("source_data_root", source_data_root);
        if (!transaction.empty()) payload.add_string("transaction_id", transaction);
        const auto root_values = option_values(options.args, "--root");
        if (!root_values.empty()) {
            json::ArrayBuilder roots;
            for (const auto& root : root_values) roots.add_string(root);
            payload.add_array("roots", roots);
        }
        return emit_basic(call(
                options, "presentation.action", payload.serialize(),
                confirmation != "explicit", request_id, operation, attempt),
            as_json, "Presentation action completed");
    }
    return 2;
}

int usage()
{
    std::cout << "facman " << FACMAN_VERSION_SEMVER << "\n";
    for (const char* line : kGeneratedCommandHelp) std::cout << "  " << line << '\n';
    std::cout << "  installs workflow [--json] (generated setup review sequence)\n";
    std::cout << "  tui [--advanced|--list|--capabilities] (same-binary terminal UI)\n";
    std::cout << "  rpc --stdio (bounded machine transport)\n";
    std::cout << "  --rpc (alias for rpc --stdio)\n";
    std::cout << "Global machine format: --json or --format json\n";
    return 0;
}

} // namespace

extern "C" int flaunch_dispatch_command(int argc, char** argv)
{
    g_machine_result_emitted = false;
    const Options options = parse_options(argc, argv);
    if (options.args.empty()) return usage();
    const std::string& command = options.args[0];
    if (command == "--version" || command == "version") {
        std::cout << "FacMan " << FACMAN_VERSION_SEMVER
                  << " (revision " << FACMAN_BUILD_SOURCE_REVISION
                  << ", configuration " << build_configuration() << ")\n";
        return 0;
    }
    if (command == "--help" || command == "help") return usage();
#if FACMAN_TUI_HOST_AVAILABLE
    if (command == "tui") return facman_tui_run(argc, argv);
#else
    if (command == "tui") {
        if (flag(options.args, "--json")) {
            return emit_json(local_failure(
                "tui",
                "tui_host_unavailable",
                "This FacMan build does not contain the TUI host",
                facman::core::OutcomeKind::unavailable));
        }
        std::cerr << "This FacMan build does not contain the TUI host\n";
        return 1;
    }
#endif
    int result = 2;
    if (command == "--rpc") {
        Options rpc_options = options;
        rpc_options.args[0] = "rpc";
        rpc_options.args.push_back("--stdio");
        result = command_rpc(rpc_options);
    }
    else if (command == "rpc") result = command_rpc(options);
    else if (command == "product") result = command_product(options);
    else if (command == "command-graph") result = command_graph(options);
    else if (command == "presentation") result = command_presentation(options);
    else if (command == "diagnostics") result = command_diagnostics(options);
    else if (command == "doctor") result = command_doctor(options);
    else if (command == "installs") result = command_installs(options);
    else if (command == "instances") result = command_instances(options);
    else if (command == "snapshots") result = command_snapshots(options);
    else if (command == "templates") result = command_templates(options);
    else if (command == "profiles") result = command_profiles(options);
    else if (command == "mods") result = command_mods(options);
    else if (command == "modsets") result = command_modsets(options);
    else if (command == "saves") result = command_saves(options);
    else if (command == "launch-plan" || command == "launch") result = command_launch(options, false);
    else if (command == "run") result = command_launch(options, true);
    else if (command == "play") result = command_launch(options, true, true);
    else if (command == "export") result = command_transfer(options, true);
    else if (command == "import") result = command_transfer(options, false);
    else if (command == "servers") result = command_servers(options);
    else if (command == "dev") result = command_dev(options);
    else if (command == "workspace") result = command_workspace(options);
    else if (command == "preferences") result = command_preferences(options);
    else if (command == "capabilities") result = command_capabilities(options);
    else if (command == "onboarding") result = command_onboarding(options);
    else if (command == "package") result = command_package(options);
    if (result == 2 && flag(options.args, "--json") && !g_machine_result_emitted) {
        return emit_json(local_failure(
            command,
            "cli_invalid_invocation",
            "Command arguments do not match a supported invocation",
            facman::core::OutcomeKind::invalid_argument));
    }
    if (result == 2 && command != "rpc" && !g_machine_result_emitted) {
        std::cerr << "Unknown or invalid command: " << command << '\n';
    }
    return result;
}
