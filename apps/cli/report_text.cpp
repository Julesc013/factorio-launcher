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
    const json::Value* identity = report.find("plan_sha256");
    if (identity != nullptr) output << "Preparation plan SHA-256: " << text_field(report, "plan_sha256") << '\n';
    if (!applied) output << "No files changed.\n";
    return output.str();
}

std::optional<std::string> instance_readiness_text(const json::Value& report)
{
    const json::Value* readiness = report.find("instance_readiness");
    if (readiness == nullptr) readiness = &report;
    if (!readiness->is_object() || text_field(*readiness, "schema") != "factorio.instance_readiness.v1") {
        return std::nullopt;
    }
    const json::Value* dimensions = readiness->find("dimensions");
    const json::Value* blockers = readiness->find("blockers");
    const json::Value* actions = readiness->find("safe_next_actions");
    if (dimensions == nullptr || !dimensions->is_array() || blockers == nullptr || !blockers->is_array() ||
        actions == nullptr || !actions->is_array()) return std::nullopt;
    std::ostringstream output;
    output << "Instance " << text_field(*readiness, "instance_id") << " ("
           << text_field(*readiness, "launch_intent") << " readiness)\n";
    output << "  Overall: " << text_field(*readiness, "overall_state")
           << "\n  Configuration: " << text_field(*readiness, "configuration_state")
           << "\n  Preparation: " << text_field(*readiness, "preparation_state")
           << "\n  Play authority: " << text_field(*readiness, "play_authority_state") << '\n';
    output << "Dimensions:\n";
    for (std::size_t index = 0; index < dimensions->size(); ++index) {
        const json::Value* item = dimensions->at(index);
        if (item == nullptr || !item->is_object()) return std::nullopt;
        output << "  " << text_field(*item, "id") << ": " << text_field(*item, "state")
               << " - " << text_field(*item, "summary") << '\n';
    }
    if (blockers->size() != 0U) output << "Blockers:\n";
    for (std::size_t index = 0; index < blockers->size(); ++index) {
        const json::Value* item = blockers->at(index);
        if (item == nullptr || !item->is_object()) return std::nullopt;
        output << "  [" << text_field(*item, "code") << "] " << text_field(*item, "reason")
               << "\n    " << text_field(*item, "detail")
               << "\n    Next action: " << text_field(*item, "safe_next_action") << '\n';
    }
    if (actions->size() != 0U) output << "Next actions:\n";
    for (std::size_t index = 0; index < actions->size(); ++index) {
        const json::Value* item = actions->at(index);
        if (item == nullptr || !item->is_object()) return std::nullopt;
        output << "  [" << text_field(*item, "id") << "] " << text_field(*item, "label") << '\n';
        const json::Value* command = item->find("command");
        if (command != nullptr && !command->is_null()) output << "    " << text_field(*item, "command") << '\n';
    }
    return output.str();
}

} // namespace facman::cli
