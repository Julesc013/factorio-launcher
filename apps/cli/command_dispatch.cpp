// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "command_dispatch.h"

#include "facman_client.h"
#include "fl_json.h"
#include "version.h"
#include "generated/command_help.inc"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <string>
#include <vector>

namespace {
namespace json = facman::core::json;

constexpr std::size_t kTransportInputLimit = 1024U * 1024U;
constexpr std::size_t kTransportOutputLimit = 16U * 1024U * 1024U;

struct Options {
    std::string workspace;
    std::vector<std::string> args;
};

std::string default_workspace()
{
    if (const char* value = std::getenv("FACMAN_WORKSPACE")) if (*value) return value;
    if (const char* value = std::getenv("FACTORIO_LAUNCHER_WORKSPACE")) if (*value) return value;
#ifdef _WIN32
    const char* home = std::getenv("USERPROFILE");
#else
    const char* home = std::getenv("HOME");
#endif
    return home && *home ? std::string(home) + "/.facman/workspace" : "factorio_workspace";
}

Options parse_options(int argc, char** argv)
{
    Options options;
    options.workspace = default_workspace();
    for (int index = 1; index < argc; ++index) {
        const std::string value = argv[index];
        if (value == "--workspace" && index + 1 < argc) options.workspace = argv[++index];
        else options.args.push_back(value);
    }
    return options;
}

bool flag(const std::vector<std::string>& args, const std::string& value)
{
    return std::find(args.begin(), args.end(), value) != args.end();
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

facman::core::Result<facman::client::CommandResponse> call(
    const Options& options,
    const std::string& command,
    const std::string& payload = "{}",
    bool dry_run = true)
{
    facman::client::FacManClient client(
        std::make_unique<facman::client::DirectFlbTransport>(options.workspace));
    return client.execute({command, payload, dry_run});
}

int emit_json(const facman::core::Result<facman::client::CommandResponse>& response)
{
    if (!response) {
        json::ObjectBuilder refusal;
        refusal.add_string("code", response.error().code);
        refusal.add_string("reason", response.error().message);
        json::ObjectBuilder output;
        output.add_string("schema", "facman.client_refusal.v1");
        output.add_string("status", "refused");
        output.add_object("refusal", refusal);
        std::cout << output.serialize() << '\n';
        return 1;
    }
    std::cout << (response.value().payload.empty() ? response.value().envelope : response.value().payload) << '\n';
    return response.value().ok() ? 0 : 1;
}

int emit_basic(const facman::core::Result<facman::client::CommandResponse>& response, bool as_json, const std::string& success)
{
    if (as_json) return emit_json(response);
    if (!response) { std::cerr << response.error().message << '\n'; return 1; }
    if (!response.value().ok()) { std::cerr << (response.value().error_message.empty() ? "Command refused" : response.value().error_message) << '\n'; return 1; }
    std::cout << success << '\n';
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

std::string transport_response(
    const std::string& request_id,
    const std::string& command,
    const facman::core::Result<facman::client::CommandResponse>& response)
{
    json::ObjectBuilder output;
    output.add_string("schema", "facman.transport_response.v1");
    output.add_string("request_id", request_id);
    output.add_unsigned_integer("protocol_version", 1);
    output.add_string("command", command);
    output.add_string("outcome", response && response.value().ok() ? "ok" : "refused");
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
    return output.serialize();
}

int transport_refusal(
    const std::string& request_id,
    const std::string& command,
    const std::string& code,
    const std::string& message)
{
    auto failure = facman::core::Result<facman::client::CommandResponse>::failure({code, message, "$"});
    std::cout << transport_response(request_id, command, failure) << '\n';
    return 1;
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
    const auto* version = request.find("protocol_version");
    const auto* dry_run = request.find("dry_run");
    const auto* payload = request.find("payload");
    if (schema != "facman.transport_request.v1" || request_id.empty() || command.empty() ||
        version == nullptr || !version->unsigned_integer_value() || version->unsigned_integer_value().value() != 1 ||
        dry_run == nullptr || !dry_run->bool_value() || payload == nullptr || !payload->is_object()) {
        return transport_refusal(request_id, command, "transport_protocol_invalid", "Transport request does not satisfy protocol v1");
    }
    const std::string requested_workspace = json_string_field(request, "workspace");
    const std::string workspace = requested_workspace.empty() ? options.workspace : requested_workspace;
    facman::client::FacManClient client(std::make_unique<facman::client::DirectFlbTransport>(workspace));
    auto response = client.execute({command, payload->serialize(), dry_run->bool_value().value()});
    std::string output = transport_response(request_id, command, response);
    if (output.size() > kTransportOutputLimit) {
        return transport_refusal(request_id, command, "transport_output_too_large", "Transport response exceeds the output budget");
    }
    std::cout << output << '\n';
    return response && response.value().ok() ? 0 : 1;
}

int command_product(const Options& options)
{
    if (options.args.size() < 2 || options.args[1] != "inspect") return 2;
    auto response = call(options, "product.inspect");
    if (flag(options.args, "--json")) return emit_json(response);
    if (!response || !response.value().ok()) return 1;
    std::cout << "FacMan - an unofficial launcher and isolated instance manager for Factorio\nProduct ID: factorio\nBundles Factorio binaries: no\nDefault run mode: dry-run\n";
    return 0;
}

int command_doctor(const Options& options)
{
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
    if (!response || !response.value().ok()) return 1;
    const std::string status = response.value().payload_string("status");
    std::cout << "FacMan doctor\nStatus: " << status << '\n';
    if (status == "warning") std::cout << "Warning: no install references registered yet\nSuggestion: scan or import a Factorio install reference\n";
    return 0;
}

int command_installs(const Options& options)
{
    if (options.args.size() < 2) return 2;
    const std::string action = options.args[1];
    if (action == "list") {
        auto response = call(options, "install_refs.list");
        if (flag(options.args, "--json") && response && response.value().ok()) {
            std::cout << response.value().payload_member_json("install_refs", "[]") << '\n';
            return 0;
        }
        return emit_basic(response, false, "Install references listed");
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
        if (!response || !response.value().ok()) return 1;
        std::cout << "Registered " << id << " at " << response.value().payload_string("root") << '\n';
        return 0;
    }
    if (action == "inspect" && options.args.size() >= 3) return emit_basic(call(options, "install_refs.inspect", exact_fields_payload({{"install_id", options.args[2]}})), flag(options.args, "--json"), "Install inspected");
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
        if (flag(options.args, "--json") && response && response.value().ok()) {
            std::cout << response.value().payload_member_json("instances", "[]") << '\n';
            return 0;
        }
        return emit_basic(response, false, "Instances listed");
    }
    if (options.args[1] == "create" && options.args.size() >= 3) {
        const std::string install = option(options.args, "--install");
        if (install.empty()) return 2;
        const std::string id = option(options.args, "--id", slugify(options.args[2]));
        const std::string payload = exact_fields_payload({
            {"display_name", options.args[2]}, {"instance_id", id}, {"install_id", install},
            {"template_id", option(options.args, "--template", "vanilla")}});
        return emit_basic(call(options, "instance.create", payload, false), flag(options.args, "--json"), "Created instance " + id);
    }
    return 2;
}

int command_mods(const Options& options)
{
    if (options.args.size() < 2) return 2;
    const std::string action = options.args[1];
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

int command_modsets(const Options& options)
{
    if (options.args.size() < 3) return 2;
    const std::string action = options.args[1], instance = options.args[2];
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

int command_launch(const Options& options, bool run)
{
    std::size_t id_index = 1;
    if (!run && options.args[0] == "launch" && options.args.size() > 2 && options.args[1] == "plan") id_index = 2;
    if (options.args.size() <= id_index) return 2;
    const std::string instance = options.args[id_index];
    if (run && flag(options.args, "--execute")) return emit_basic(call(options, "run.execute", exact_fields_payload({{"instance_id", instance}}), false), flag(options.args, "--json"), "");
    const std::string command = run ? "run.preview" : flag(options.args, "--preflight") ? "launch_plan.preflight" : "launch_plan.build";
    auto response = call(options, command, exact_fields_payload({{"instance_id", instance}}));
    if (flag(options.args, "--json")) return emit_json(response);
    if (!response || !response.value().ok()) return 1;
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
    if (options.args.size() < 3) return 2;
    const std::string family = options.args[1], action = options.args[2];
    if (family != "recovery" && family != "migration") return 2;
    std::string command = "workspace." + family + "." + action;
    std::string payload = "{}";
    if (family == "recovery" && action != "inspect") { if (options.args.size() < 4) return 2; payload = exact_fields_payload({{"transaction_id", options.args[3]}}); }
    return emit_basic(call(options, command, payload, action != "apply"), flag(options.args, "--json"), "Workspace operation completed");
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

int usage()
{
    std::cout << "facman " << FACMAN_VERSION_SEMVER << "\n";
    for (const char* line : kGeneratedCommandHelp) std::cout << "  " << line << '\n';
    std::cout << "  rpc --stdio (bounded machine transport)\n";
    return 0;
}

} // namespace

extern "C" int flaunch_dispatch_command(int argc, char** argv)
{
    const Options options = parse_options(argc, argv);
    if (options.args.empty()) return usage();
    const std::string& command = options.args[0];
    if (command == "--version" || command == "version") { std::cout << "FacMan " << FACMAN_VERSION_SEMVER << '\n'; return 0; }
    if (command == "--help" || command == "help") return usage();
    if (command == "rpc") return command_rpc(options);
    if (command == "product") return command_product(options);
    if (command == "command-graph") return command_graph(options);
    if (command == "diagnostics") return command_diagnostics(options);
    if (command == "doctor") return command_doctor(options);
    if (command == "installs") return command_installs(options);
    if (command == "instances") return command_instances(options);
    if (command == "mods") return command_mods(options);
    if (command == "modsets") return command_modsets(options);
    if (command == "saves") return command_saves(options);
    if (command == "launch-plan" || command == "launch") return command_launch(options, false);
    if (command == "run") return command_launch(options, true);
    if (command == "export") return command_transfer(options, true);
    if (command == "import") return command_transfer(options, false);
    if (command == "servers") return command_servers(options);
    if (command == "dev") return command_dev(options);
    if (command == "workspace") return command_workspace(options);
    if (command == "package") return command_package(options);
    std::cerr << "Unknown command: " << command << '\n';
    return 2;
}
