// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "resource_commands.h"
#include "fl_resource_export_inspection.h"
#include "fl_json.h"
#include <exception>
#include <array>
#include <algorithm>
#include <sstream>
namespace facman::cli {
namespace {
using Payload = facman::core::Result<std::string>;
std::string option(const std::vector<std::string>& arguments, const std::string& name)
{
    for (std::size_t i = 0; i + 1 < arguments.size(); ++i)
        if (arguments[i] == name) return arguments[i + 1];
    return {};
}
void exception_failure(ResourceCommandResult& result, const std::string& message)
{
    result.payload = Payload::failure({"resource_command_failed", message, "$",
        facman::core::OutcomeKind::internal_error});
}
}
ResourceCommandResult run_resource_command(
    const std::vector<std::string>& arguments, const std::string& executable_path,
    const ResourceCommandCheckpoints& checkpoints)
{
    ResourceCommandResult result;
    if (arguments.size() < 2) return result;
    const auto& action = arguments[1];
    const std::array<std::string, 4> actions {"list", "verify", "export", "inspect-export"};
    if (std::find(actions.begin(), actions.end(), action) == actions.end())
        return result;
    if ((action == "export" || action == "inspect-export") && arguments.size() < 3) return result;
    result.valid_invocation = true;
    result.command = action == "inspect-export" ? "resources.export.inspect" : "resources." + action;
    (void)executable_path;
    try {
        // This read-only route works with an absent pack and marker.
        if (action == "inspect-export") {
            result.payload = facman::resources::inspect_export_destination(arguments[2]);
            result.human_output = result.payload ? result.payload.value() : "";
            return result;
        }
        auto selected = facman::resources::inspect_selected_resources(option(arguments, "--pack"));
        if (!selected) {
            result.payload = Payload::failure(selected.error());
            return result;
        }
        if (action == "export") {
            run_resource_export_into(result, selected.value(), arguments[2], checkpoints);
            return result;
        }
        const auto& inspection = selected.value().inspection;
        result.payload = Payload::success(facman::resources::inspection_json(inspection));
        if (action == "verify") {
            result.human_output = "Resource pack verified: " + std::to_string(inspection.entries.size()) +
                " entries, content " + inspection.content_sha256;
        } else {
            std::ostringstream output;
            output << "FacMan resources " << inspection.version << " (" << inspection.entries.size() << " entries)\n";
            for (const auto& entry : inspection.entries) output << entry << '\n';
            result.human_output = output.str();
            if (!result.human_output.empty()) result.human_output.pop_back();
        }
    } catch (const std::exception& error) {
        exception_failure(result, error.what());
    } catch (...) {
        exception_failure(result, "Unknown resource failure");
    }
    return result;
}
} // namespace facman::cli
