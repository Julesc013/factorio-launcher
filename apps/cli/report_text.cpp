// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "report_text.h"

#include "fl_json.h"

#include <sstream>

namespace facman::cli {
namespace json = facman::core::json;
namespace {

std::string text_field(const json::Value& object, const char* key)
{
    const json::Value* value = object.find(key);
    if (value == nullptr) return "(missing)";
    if (value->is_null()) return "(none)";
    auto string = value->string_value();
    return string ? string.take_value() : value->serialize();
}

std::string guidance_field(const json::Value& object, const char* key)
{
    const json::Value* value = object.find(key);
    if (value == nullptr) return {};
    auto string = value->string_value();
    return string ? string.take_value() : std::string();
}

} // namespace

std::string guidance_text(const json::Value& report)
{
    std::ostringstream output;
    output << guidance_field(report, "command") << "\nStatus: " << guidance_field(report, "status") << '\n';
    const json::Value* reasons = report.find("reasons");
    if (reasons != nullptr && reasons->is_array()) {
        for (std::size_t index = 0; index < reasons->size(); ++index) {
            const json::Value* reason = reasons->at(index);
            if (reason == nullptr || !reason->is_object()) continue;
            output << "- [" << guidance_field(*reason, "code") << "] " << guidance_field(*reason, "summary")
                   << "\n  Evidence: " << guidance_field(*reason, "evidence") << '\n';
        }
    }
    output << "No steps were executed. Use --json for the complete typed report.\n";
    return output.str();
}

std::optional<std::string> effective_profile_text(const json::Value& report)
{
    const json::Value* settings = report.find("settings");
    const json::Value* provenance = report.find("provenance");
    const json::Value* sources = provenance == nullptr ? nullptr : provenance->find("setting_sources");
    const json::Value* arguments = provenance == nullptr ? nullptr : provenance->find("additional_argument_sources");
    if (settings == nullptr || !settings->is_object() || sources == nullptr || !sources->is_object() ||
        arguments == nullptr || !arguments->is_array()) return std::nullopt;
    const std::string command = text_field(report, "command");
    if (command != "profiles.plan" && command != "profiles.apply") return std::nullopt;
    const bool applied = command == "profiles.apply";
    std::ostringstream output;
    output << (applied ? "Applied" : "Planned") << " profile " << text_field(report, "profile_id")
           << " for instance " << text_field(report, "instance_id")
           << " (template " << text_field(report, "template_id") << ")\n";
    for (const char* key : {"window_mode", "graphics_quality", "audio", "selection_mode",
             "selection", "launch_mode", "benchmark_ticks"}) {
        const std::string source = text_field(*sources, key);
        if (source != "profile" && source != "request_override") return std::nullopt;
        output << "  " << key << ": " << text_field(*settings, key) << " ["
               << (source == "request_override" ? "request override" : "profile") << "]\n";
    }
    output << "  additional_arguments: " << arguments->size() << '\n';
    for (std::size_t index = 0; index < arguments->size(); ++index) {
        const json::Value* item = arguments->at(index);
        if (item == nullptr || !item->is_object()) return std::nullopt;
        const std::string source = text_field(*item, "source");
        if (source != "profile" && source != "request_override") return std::nullopt;
        output << "    " << text_field(*item, "value") << " ["
               << (source == "request_override" ? "request override" : "profile") << "]\n";
    }
    output << "Source manifest SHA-256: " << text_field(report, "source_manifest_sha256") << '\n';
    if (!applied) output << "No files changed.\n";
    return output.str();
}

} // namespace facman::cli
