// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "fl_resource_export_inspection.h"
#include "fl_json.h"
#include <exception>
namespace facman::resources {
facman::core::Result<std::string> inspect_export_destination(const std::string& destination)
{
    using Output = facman::core::Result<std::string>;
    try {
        if (destination.empty() || destination.size() > 4096 ||
            destination.find('\0') != std::string::npos)
            return Output::failure({"resource_inspect_path_invalid", "A bounded absolute path is required", "$",
                facman::core::OutcomeKind::invalid_argument});
        const auto path = std::filesystem::u8path(destination);
        if (!path.is_absolute())
            return Output::failure({"resource_inspect_path_invalid", "Inspection requires an absolute destination", "$",
                facman::core::OutcomeKind::invalid_argument});
        std::vector<std::filesystem::path> components;
        for (const auto& part : path.relative_path()) {
            if (part.empty() || part == "." || part == ".." || part.native().size() > 255)
                return Output::failure({"resource_inspect_path_invalid", "Ambiguous or overlong path component", "$",
                    facman::core::OutcomeKind::invalid_argument});
            components.push_back(part);
        }
        if (components.empty() || components.size() > 64)
            return Output::failure({"resource_inspect_path_invalid", "Destination must have 1 to 64 components", "$",
                facman::core::OutcomeKind::invalid_argument});
        const auto observed = detail::observe_export_path(path.root_path(), components);
        facman::core::json::ObjectBuilder result;
        result.add_string("schema", "facman.resource_export_inspection.v1");
        result.add_string("destination", destination);
        result.add_string("scope", "destination_type_and_identity_only");
        result.add_string("state", observed.state);
        result.add_string("kind", observed.kind);
        result.add_string("detail", observed.detail);
        result.add_string("device", std::to_string(observed.device));
        result.add_string("object", std::to_string(observed.object));
        result.add_bool("contents_verified", false);
        result.add_bool("ownership_proven", false);
        result.add_bool("retry_authorized", false);
        result.add_bool("delete_authorized", false);
        result.add_bool("resume_authorized", false);
        return Output::success(result.serialize());
    } catch (const std::exception& error) {
        return Output::failure({"resource_inspection_unavailable", error.what(), "$",
            facman::core::OutcomeKind::unavailable});
    } catch (...) {
        return Output::failure({"resource_inspection_unavailable", "Unknown observation failure", "$",
            facman::core::OutcomeKind::unavailable});
    }
}
}
