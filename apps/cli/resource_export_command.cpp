// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "resource_commands.h"
#include "fl_json.h"
#include <exception>
namespace facman::cli {
namespace {
using Payload = facman::core::Result<std::string>;
void exception_failure(ResourceCommandResult& result, const std::string& message,
    const ResourceCommandCheckpoints& checkpoints)
{
    if (checkpoints.before_export_failure_report) checkpoints.before_export_failure_report();
    result.payload = Payload::failure({"resource_command_failed", message, "$",
        facman::core::OutcomeKind::internal_error});
}
}
void run_resource_export_into(ResourceCommandResult& result,
    const facman::resources::ResourceSelection& selected, const std::string& destination,
    const ResourceCommandCheckpoints& checkpoints)
{
    result.valid_invocation = true;
    result.command = "resources.export";
    // The observation outlives all calls, serialization and exception handlers.
    try {
        result.destination = facman::resources::absolute_export_destination_utf8(destination);
        auto exported = facman::resources::export_selected_resources(
            selected, result.destination, &result.extraction, checkpoints.extraction);
        if (!exported) {
            result.payload = Payload::failure(exported.error());
            return;
        }
        facman::core::json::ObjectBuilder payload;
        payload.add_string("schema", "facman.runtime_resource_pack_export.v1");
        payload.add_string("status", "pass");
        payload.add_string("source", selected.inspection.path.u8string());
        payload.add_string("destination", result.destination);
        payload.add_unsigned_integer("entry_count", selected.inspection.entries.size());
        result.payload = Payload::success(payload.serialize());
        result.human_output = "Verified resources exported to " + result.destination;
    } catch (const std::exception& error) {
        exception_failure(result, error.what(), checkpoints);
    } catch (...) {
        exception_failure(result, "Unknown resource export failure", checkpoints);
    }
}
ResourceCommandResult run_resource_export(
    const facman::resources::ResourceSelection& selected, const std::string& destination,
    const facman::archive::ExtractionCheckpoint& checkpoint)
{
    ResourceCommandResult result;
    run_resource_export_into(result, selected, destination, {checkpoint, {}});
    return result;
}
}
