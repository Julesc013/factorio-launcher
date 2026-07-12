// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "tui_command_client.hpp"
#include "tui_views.hpp"

#include "facman_client_c.h"
#include "fl_file_io.h"
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
    for (int index = 1; index < argc; ++index) {
        const std::string value = argv[index];
        if (value == "--workspace" && index + 1 < argc) explicit_workspace = argv[++index];
        else if (value == "--command" && index + 1 < argc) options.command = argv[++index];
        else if (value == "--payload" && index + 1 < argc) options.payload = argv[++index];
        else if (value == "--json" || value == "--structured") options.structured = true;
        else if (value == "--list") options.list = true;
        else if (value == "--interactive") options.interactive = true;
        else if (value == "--apply") options.allow_write = true;
        else if (value == "--cancel") options.cancel_before_start = true;
        else if (value == "--timeout-ms" && index + 1 < argc) {
            try { options.timeout_ms = std::stol(argv[++index]); } catch (...) { options.timeout_ms = 0; }
        }
        else if (value == "--help") options.command = "__help__";
        else if (value == "--version") options.command = "__version__";
        else if (options.command.empty()) options.command = value;
    }
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
              "       facman-tui --interactive\n";
}

int interactive(facman::tui::CommandClient& client)
{
    const bool ascii_only = std::getenv("NO_COLOR") != nullptr || !terminal_output();
    for (;;) {
        facman::tui::render_menu(std::cout, ascii_only);
        std::string selection;
        if (!std::getline(std::cin, selection) || selection == "q" || selection == "Q") return 0;
        unsigned long number = 0;
        try { number = std::stoul(selection); } catch (...) { continue; }
        const char* command = facman::tui::menu_command(static_cast<unsigned int>(number));
        if (command == nullptr) continue;
        std::cout << "JSON payload (empty for {}): " << std::flush;
        std::string payload;
        if (!std::getline(std::cin, payload)) return 0;
        auto response = client.execute({command, payload.empty() ? "{}" : payload, false});
        (void)facman::tui::render_response(std::cout, std::cerr, command, response, false);
        std::cout << '\n';
    }
}

}  // namespace

int main(int argc, char** argv)
{
    facman_client_initialize_process(argc > 0 ? argv[0] : nullptr);
    const Options options = parse(argc, argv);
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
    facman::tui::CommandClient client(facman::platform::path_from_utf8(options.workspace));
    if (options.interactive || (options.command.empty() && terminal_input() && terminal_output()))
        return interactive(client);
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
