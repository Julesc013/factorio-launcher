// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "generated_command_catalog.hpp"
#include "fl_file_io.h"
#include "tui_command_client.hpp"
#include "tui_views.hpp"

#include <filesystem>
#include <sstream>
#include <string>

int main()
{
    namespace fs = std::filesystem;
    using facman::tui::CommandClient;
    using facman::tui::Invocation;

    static_assert(facman::tui::kGeneratedCommandCount >= 56, "generated TUI catalog is incomplete");
    const auto* status_command = facman::tui::find_command("workspace.status");
    const auto* diagnostics = facman::tui::find_command("diagnostics.export");
    if (status_command == nullptr || diagnostics == nullptr) return 2;
    if (std::string(diagnostics->runtime_id) != "diagnostics.export" ||
        !facman::tui::command_writes(*diagnostics)) return 3;

    const fs::path workspace = fs::temp_directory_path() /
        facman::platform::path_from_utf8("facman-tui-Ω-empty");
    std::error_code ignored;
    fs::remove_all(workspace, ignored);
    CommandClient client(workspace);
    auto status = client.execute({"workspace.status", "{}", false});
    if (!status || !status.value().ok() ||
        status.value().payload.find("factorio.guidance_report.v1") == std::string::npos ||
        fs::exists(workspace)) return 4;

    std::ostringstream output;
    std::ostringstream error;
    if (facman::tui::render_response(output, error, "workspace.status", status, false) != 0 ||
        output.str().find("Outcome: ok") == std::string::npos) return 5;

    auto unavailable = client.execute({"run.execute", "{\"instance_id\":\"space-age-main\"}", false});
    if (!unavailable || unavailable.value().ok() || unavailable.value().outcome != "unavailable") return 6;

    std::ostringstream catalog;
    facman::tui::render_catalog(catalog, true);
    if (catalog.str().find("facman.tui_catalog.v1") == std::string::npos ||
        catalog.str().find("isolation_not_proven") == std::string::npos) return 7;
    return 0;
}
