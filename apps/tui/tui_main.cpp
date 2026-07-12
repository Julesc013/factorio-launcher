// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "tui_command_client.hpp"
#include "tui_guided_forms.hpp"
#include "tui_views.hpp"

#include "facman_client_c.h"
#include "fl_file_io.h"
#include "fl_preferences.h"
#include "version.h"

#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <optional>
#include <string>

#ifdef _WIN32
#include <io.h>
#else
#include <unistd.h>
#endif

namespace {

struct Options {
    std::string workspace;
    std::optional<facman::core::Error> workspace_error;
    std::string command;
    std::string payload = "{}";
    bool structured = false;
    bool list = false;
    bool interactive = false;
    bool allow_write = false;
    bool cancel_before_start = false;
    bool plain = false;
    bool invalid = false;
    bool transport_explicit = false;
    bool color_explicit = false;
    bool page_size_explicit = false;
    bool timeout_explicit = false;
    std::string transport = "direct";
    std::string color = "auto";
    std::string cli_path;
    std::size_t page_size = 25;
    long timeout_ms = 300000;
};

bool terminal_input()
{
#ifdef _WIN32
    return _isatty(_fileno(stdin)) != 0;
#else
    return isatty(STDIN_FILENO) != 0;
#endif
}

bool terminal_output()
{
#ifdef _WIN32
    return _isatty(_fileno(stdout)) != 0;
#else
    return isatty(STDOUT_FILENO) != 0;
#endif
}

Options parse(int argc, char** argv)
{
    Options options;
    std::string explicit_workspace;
    bool workspace_explicit = false;
    for (int index = 1; index < argc; ++index) {
        const std::string value = argv[index];
        if (value == "--workspace" && index + 1 < argc) { explicit_workspace = argv[++index]; workspace_explicit = true; }
        else if (value == "--command" && index + 1 < argc) options.command = argv[++index];
        else if (value == "--payload" && index + 1 < argc) options.payload = argv[++index];
        else if (value == "--json" || value == "--structured") options.structured = true;
        else if (value == "--list") options.list = true;
        else if (value == "--interactive") options.interactive = true;
        else if (value == "--apply") options.allow_write = true;
        else if (value == "--cancel") options.cancel_before_start = true;
        else if (value == "--plain") options.plain = true;
        else if (value == "--transport" && index + 1 < argc) { options.transport = argv[++index]; options.transport_explicit = true; }
        else if (value == "--cli-path" && index + 1 < argc) options.cli_path = argv[++index];
        else if (value == "--color" && index + 1 < argc) { options.color = argv[++index]; options.color_explicit = true; }
        else if (value == "--page-size" && index + 1 < argc) {
            options.page_size_explicit = true;
            try { options.page_size = static_cast<std::size_t>(std::stoul(argv[++index])); } catch (...) { options.invalid = true; }
        }
        else if (value == "--timeout-ms" && index + 1 < argc) {
            options.timeout_explicit = true;
            try { options.timeout_ms = std::stol(argv[++index]); } catch (...) { options.timeout_ms = 0; }
        }
        else if (value == "--help") options.command = "__help__";
        else if (value == "--version") options.command = "__version__";
        else if (options.command.empty()) options.command = value;
    }
    auto preferences = facman::preferences::inspect();
    if (preferences && preferences.value().present) {
        const auto& values = preferences.value().values;
        if (!workspace_explicit && !values.preferred_workspace.empty()) explicit_workspace = values.preferred_workspace;
        if (!options.transport_explicit && !values.preferred_transport.empty()) options.transport = values.preferred_transport;
        if (!options.color_explicit && !values.display_color_policy.empty()) options.color = values.display_color_policy;
        if (!options.page_size_explicit && values.tui_page_size != 0) options.page_size = values.tui_page_size;
        if (!options.timeout_explicit && values.command_timeout_seconds != 0)
            options.timeout_ms = static_cast<long>(values.command_timeout_seconds) * 1000L;
    }
    if (options.transport != "direct" && options.transport != "process" && options.transport != "daemon") options.invalid = true;
    if (options.color != "auto" && options.color != "always" && options.color != "never") options.invalid = true;
    if (options.page_size < 5 || options.page_size > 1000 || options.timeout_ms <= 0) options.invalid = true;
    if (options.plain) options.color = "never";
    auto resolution = facman::client::resolve_workspace(
        facman::platform::path_from_utf8(explicit_workspace));
    if (resolution) options.workspace = facman::platform::path_to_utf8(resolution.value().path);
    else options.workspace_error = resolution.error();
    return options;
}

void usage(std::ostream& output)
{
    output << "Usage: facman-tui [--workspace PATH] [--list] [--json]\n"
              "       facman-tui --command ID [--payload JSON] [--apply] [--cancel]\n"
              "       facman-tui --interactive [--transport direct|process|daemon]\n"
              "Options: --color auto|always|never --plain --page-size N --timeout-ms N\n"
              "         --cli-path PATH (process transport override)\n";
}

}  // namespace

int main(int argc, char** argv)
{
    facman_client_initialize_process(argc > 0 ? argv[0] : nullptr);
    const Options options = parse(argc, argv);
    if (options.invalid) {
        std::cerr << "Invalid TUI option: transport, color, page size, and timeout values are bounded\n";
        usage(std::cerr);
        return 2;
    }
    if (options.command == "__help__") { usage(std::cout); return 0; }
    if (options.command == "__version__") { std::cout << "FacMan " FACMAN_VERSION_SEMVER " TUI\n"; return 0; }
    if (options.command == "help") { usage(std::cout); return 0; }
    if (options.list || options.command == "command_graph.inspect") {
        facman::tui::render_catalog(std::cout, options.structured);
        return 0;
    }
    if (options.workspace_error) {
        std::cerr << "Workspace resolution refused: " << options.workspace_error->code
                  << ": " << options.workspace_error->message << '\n';
        return 2;
    }
    std::filesystem::path process_executable = facman::platform::path_from_utf8(options.cli_path);
    if (options.transport == "process" && process_executable.empty()) {
        std::filesystem::path current = argc > 0 ? std::filesystem::absolute(argv[0]) : std::filesystem::path();
#ifdef _WIN32
        process_executable = current.parent_path() / "facman.exe";
#else
        process_executable = current.parent_path() / "facman";
#endif
    }
    facman::tui::CommandClient client(
        facman::platform::path_from_utf8(options.workspace), options.transport, process_executable);
    if (options.interactive || (options.command.empty() && terminal_input() && terminal_output())) {
        const bool no_color = std::getenv("NO_COLOR") != nullptr;
        facman::tui::GuidedOptions guided;
        guided.page_size = options.page_size;
        guided.page_results = terminal_output() && !options.plain;
        guided.plain = options.plain;
        guided.color = !no_color && !options.plain &&
            (options.color == "always" || (options.color == "auto" && terminal_output()));
        return facman::tui::run_guided(client, std::cin, std::cout, std::cerr, guided);
    }
    std::string command = options.command.empty() ? "workspace.status" : options.command;
    if (command == "doctor") command = "doctor.run";
    if (command == "instances.list") command = "instance.list";
    const auto* descriptor = facman::tui::find_command(command);
    if (descriptor == nullptr) {
        std::cerr << "Unknown generated command: " << command << '\n';
        return 2;
    }
    if (std::string(descriptor->runtime_id) == "run.execute" && options.allow_write) {
        std::cerr << "run.execute remains human-gated and cannot be promoted by the TUI\n";
        return 2;
    }
    facman::tui::Invocation invocation;
    invocation.command = descriptor->runtime_id;
    invocation.payload = options.payload;
    invocation.allow_write = options.allow_write;
    invocation.cancel_before_start = options.cancel_before_start;
    invocation.timeout = std::chrono::milliseconds(options.timeout_ms);
    auto response = client.execute(invocation);
    return facman::tui::render_response(
        std::cout, std::cerr, descriptor->command_id, response, options.structured);
}
