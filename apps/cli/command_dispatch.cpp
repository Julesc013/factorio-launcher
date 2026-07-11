// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "command_dispatch.h"

#include "facman_client.h"
#include "version.h"
#include "generated/command_help.inc"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <iostream>
#include <memory>
#include <sstream>
#include <string>
#include <vector>

namespace {
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

std::string q(const std::string& value) { return facman::client::quote_json_string(value); }

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
        std::cout << "{\"schema\":\"facman.client_refusal.v1\",\"status\":\"refused\",\"refusal\":{\"code\":"
            << q(response.error().code) << ",\"reason\":" << q(response.error().message) << "}}\n";
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

std::string operation_payload(
    const std::string& operation,
    const std::vector<std::pair<std::string, std::string>>& fields = {})
{
    std::ostringstream out;
    out << "{\"operation\":" << q(operation);
    for (const auto& field : fields) if (!field.second.empty()) out << ',' << q(field.first) << ':' << q(field.second);
    out << '}';
    return out.str();
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
        return emit_basic(call(options, "diagnostics.export", "{\"instance_id\":" + q(instance) + ",\"output_path\":" + q(bundle) + "}", false), flag(options.args, "--json"), "Diagnostic bundle exported");
    }
    std::vector<std::string> roots = option_values(options.args, "--path");
    const auto search = option_values(options.args, "--search-root"); roots.insert(roots.end(), search.begin(), search.end());
    std::ostringstream payload; payload << "{\"roots\":[";
    for (std::size_t index = 0; index < roots.size(); ++index) { if (index) payload << ','; payload << q(roots[index]); }
    payload << "]}";
    auto response = call(options, "doctor.run", payload.str());
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
        std::ostringstream payload; payload << "{\"roots\":[";
        for (std::size_t index = 0; index < roots.size(); ++index) { if (index) payload << ','; payload << q(roots[index]); }
        payload << "]}";
        return emit_basic(call(options, "install_refs.scan", payload.str()), flag(options.args, "--json"), "Install scan completed");
    }
    if (action == "import" && options.args.size() >= 3) {
        const std::string id = option(options.args, "--id", slugify(options.args[2]));
        auto response = call(options, "install_refs.import", "{\"path\":" + q(options.args[2]) + ",\"install_id\":" + q(id) + "}", false);
        if (flag(options.args, "--json")) return emit_json(response);
        if (!response || !response.value().ok()) return 1;
        std::cout << "Registered " << id << " at " << response.value().payload_string("root") << '\n';
        return 0;
    }
    if (action == "inspect" && options.args.size() >= 3) return emit_basic(call(options, "install_refs.inspect", "{\"install_id\":" + q(options.args[2]) + "}"), flag(options.args, "--json"), "Install inspected");
    if (action == "install-version" && options.args.size() >= 3) {
        const std::string archive = option(options.args, "--archive");
        return emit_basic(
            call(options, "setup.operation", operation_payload(
                "installs.install-version", {{"version", options.args[2]}, {"archive", archive}})),
            flag(options.args, "--json"),
            "Managed install plan created through Universal Setup.");
    }
    if ((action == "verify" || action == "repair" || action == "uninstall") && options.args.size() >= 3) {
        return emit_basic(call(options, "setup.operation", operation_payload("installs." + action, {{"id", options.args[2]}})), flag(options.args, "--json"), "Setup operation previewed");
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
        const std::string payload = "{\"display_name\":" + q(options.args[2]) + ",\"instance_id\":" + q(id) +
            ",\"install_id\":" + q(install) + ",\"template_id\":" + q(option(options.args, "--template", "vanilla")) + "}";
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
        return emit_basic(call(options, "mods.import", "{\"source_path\":" + q(options.args[2]) + ",\"instance_id\":" + q(instance) + "}", false), flag(options.args, "--json"), "Mod imported");
    }
    if (action == "search" || action == "install" || action == "update") {
        const std::string query = options.args.size() >= 3 && action != "update" ? options.args[2] : "";
        return emit_basic(call(options, "utility.operation", operation_payload("mods." + action, {{"query", query}, {"instance_id", option(options.args, "--instance")}}), false), flag(options.args, "--json"), "");
    }
    return 2;
}

int command_modsets(const Options& options)
{
    if (options.args.size() < 3) return 2;
    const std::string action = options.args[1], instance = options.args[2];
    if (action == "lock" || action == "verify") return emit_basic(call(options, "modsets." + action, "{\"instance_id\":" + q(instance) + "}", action == "verify"), flag(options.args, "--json"), "Modset " + action + " completed");
    if (action == "export" && options.args.size() >= 4) {
        return emit_basic(
            call(options, "modsets.export", "{\"instance_id\":" + q(instance) +
                ",\"output_path\":" + q(options.args[3]) + "}", false),
            flag(options.args, "--json"),
            "Modset exported");
    }
    return 2;
}

int command_saves(const Options& options)
{
    if (options.args.size() < 2) return 2;
    const std::string action = options.args[1];
    if (action == "list") return emit_basic(call(options, "saves.list", "{\"instance_id\":" + q(option(options.args, "--instance")) + "}"), flag(options.args, "--json"), "Saves listed");
    if (action == "backup" && options.args.size() >= 3) {
        const std::string payload = "{\"instance_id\":" + q(option(options.args, "--instance")) +
            ",\"save\":" + q(options.args[2]) +
            ",\"output_path\":" + q(option(options.args, "--to")) + "}";
        return emit_basic(
            call(options, "saves.backup", payload, false),
            flag(options.args, "--json"),
            "Save backed up");
    }
    if (action == "clone" && options.args.size() >= 3) {
        const std::string payload = "{\"source_instance_id\":" + q(option(options.args, "--instance")) +
            ",\"target_instance_id\":" + q(option(options.args, "--to-instance")) +
            ",\"save\":" + q(options.args[2]) + "}";
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
            call(options, "utility.operation", operation_payload(
                "diagnostics.redact", {{"path", options.args[2]}}), false),
            flag(options.args, "--json"),
            "Diagnostic input redacted");
    }
    if (options.args[1] == "export") {
        const std::string instance = option(options.args, "--instance"), output = option(options.args, "--out");
        return emit_basic(call(options, "diagnostics.export", "{\"instance_id\":" + q(instance) + ",\"output_path\":" + q(output) + "}", false), flag(options.args, "--json"), "Diagnostic bundle exported");
    }
    return 2;
}

int command_launch(const Options& options, bool run)
{
    std::size_t id_index = 1;
    if (!run && options.args[0] == "launch" && options.args.size() > 2 && options.args[1] == "plan") id_index = 2;
    if (options.args.size() <= id_index) return 2;
    const std::string instance = options.args[id_index];
    if (run && flag(options.args, "--execute")) return emit_basic(call(options, "run.execute", "{\"instance_id\":" + q(instance) + "}", false), flag(options.args, "--json"), "");
    const std::string command = run ? "run.preview" : flag(options.args, "--preflight") ? "launch_plan.preflight" : "launch_plan.build";
    auto response = call(options, command, "{\"instance_id\":" + q(instance) + "}");
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
    if (exporting) return emit_basic(call(options, "instance.export", "{\"instance_id\":" + q(options.args[2]) + ",\"output_path\":" + q(options.args[3]) + "}", false), flag(options.args, "--json"), "Instance exported");
    return emit_basic(call(options, "instance.import", "{\"source_path\":" + q(options.args[2]) + ",\"instance_id\":" + q(option(options.args, "--id")) + "}", false), flag(options.args, "--json"), "Instance imported");
}

int command_servers(const Options& options)
{
    if (options.args.size() < 2) return 2;
    const std::string action = options.args[1];
    std::vector<std::pair<std::string, std::string>> fields;
    if (action == "create" && options.args.size() >= 3) fields = {{"name", options.args[2]}, {"id", option(options.args, "--id")}, {"instance_id", option(options.args, "--instance")}};
    else if (action == "start" || action == "stop" || action == "rcon") { if (options.args.size() < 3) return 2; fields = {{"id", options.args[2]}}; }
    return emit_basic(call(options, "utility.operation", operation_payload("servers." + action, fields), false), flag(options.args, "--json"), action == "create" ? "Server profile created" : "Servers listed");
}

int command_dev(const Options& options)
{
    if (options.args.size() < 2) return 2;
    return emit_basic(call(options, "utility.operation", operation_payload("dev." + options.args[1]), false), flag(options.args, "--json"), "Bug report created");
}

int command_workspace(const Options& options)
{
    if (options.args.size() < 3) return 2;
    const std::string family = options.args[1], action = options.args[2];
    if (family != "recovery" && family != "migration") return 2;
    std::string command = "workspace." + family + "." + action;
    std::string payload = "{}";
    if (family == "recovery" && action != "inspect") { if (options.args.size() < 4) return 2; payload = "{\"transaction_id\":" + q(options.args[3]) + "}"; }
    return emit_basic(call(options, command, payload, action != "apply"), flag(options.args, "--json"), "Workspace operation completed");
}

int command_package(const Options& options)
{
    if (options.args.size() < 2 || options.args[1] != "verify") return 2;
    return emit_basic(call(options, "setup.operation", operation_payload("package.verify")), flag(options.args, "--json"), "Package integrity verified");
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
