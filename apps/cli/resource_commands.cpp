// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "resource_commands.h"

#include "fl_json.h"
#include "fl_resource_pack.h"

#include <sstream>

namespace facman::cli {
namespace {

std::string option(
    const std::vector<std::string>& arguments,
    const std::string& name)
{
    for (std::size_t index = 0; index + 1 < arguments.size(); ++index) {
        if (arguments[index] == name) return arguments[index + 1];
    }
    return {};
}

} // namespace

ResourceCommandResult run_resource_command(
    const std::vector<std::string>& arguments,
    const std::string& executable_path)
{
    ResourceCommandResult result;
    if (arguments.size() < 2 ||
        (arguments[1] != "list" && arguments[1] != "verify" && arguments[1] != "export")) {
        return result;
    }
    if (arguments[1] == "export" && arguments.size() < 3) return result;
    result.valid_invocation = true;
    (void)executable_path; // Product selection uses the operating-system image.
    auto selected = facman::resources::inspect_selected_resources(option(arguments, "--pack"));
    if (!selected) {
        result.payload = facman::core::Result<std::string>::failure(selected.error());
        return result;
    }
    const auto& inspection = selected.value().inspection;
    if (arguments[1] == "export") {
        auto exported = facman::resources::export_selected_resources(selected.value(), arguments[2]);
        if (!exported) {
            result.payload = facman::core::Result<std::string>::failure(exported.error());
            return result;
        }
        facman::core::json::ObjectBuilder payload;
        payload.add_string("schema", "facman.runtime_resource_pack_export.v1");
        payload.add_string("status", "pass");
        payload.add_string("source", inspection.path.u8string());
        payload.add_string("destination", facman::resources::absolute_path_utf8(arguments[2]));
        payload.add_unsigned_integer("entry_count", inspection.entries.size());
        result.payload = facman::core::Result<std::string>::success(payload.serialize());
        result.human_output = "Verified resources exported to " + arguments[2];
        return result;
    }
    result.payload = facman::core::Result<std::string>::success(
        facman::resources::inspection_json(inspection));
    if (arguments[1] == "verify") {
        result.human_output = "Resource pack verified: " +
            std::to_string(inspection.entries.size()) + " entries, content " +
            inspection.content_sha256;
    } else {
        std::ostringstream output;
        output << "FacMan resources " << inspection.version << " ("
               << inspection.entries.size() << " entries)\n";
        for (const auto& entry : inspection.entries) output << entry << '\n';
        result.human_output = output.str();
        if (!result.human_output.empty()) result.human_output.pop_back();
    }
    return result;
}

} // namespace facman::cli
