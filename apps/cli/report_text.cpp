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

std::optional<std::string> save_intelligence_text(const json::Value& report)
{
    if (text_field(report, "schema") != "factorio.save_intelligence.v1") return std::nullopt;
    const json::Value* saves = report.find("saves");
    if (saves == nullptr || !saves->is_array()) return std::nullopt;
    std::ostringstream output;
    output << text_field(report, "command") << " for instance " << text_field(report, "instance_id")
           << "\nReport status: " << text_field(report, "status") << "\nSaves: " << saves->size() << '\n';
    for (std::size_t index = 0; index < saves->size(); ++index) {
        const json::Value* save = saves->at(index);
        if (save == nullptr || !save->is_object()) return std::nullopt;
        const json::Value* association = save->find("association");
        if (association == nullptr || !association->is_object()) return std::nullopt;
        output << text_field(*save, "filename") << "\n  Save bytes: " << text_field(*association, "status")
               << "\n  SHA-256: " << text_field(*save, "sha256") << '\n';
        const json::Value* context = association->find("context");
        if (context == nullptr || !context->is_object()) {
            output << "  Declared context: Not observed\n";
            continue;
        }
        const json::Value* version = context->find("factorio_version");
        const json::Value* content = context->find("modset_lock");
        if (version == nullptr || !version->is_object() || content == nullptr || !content->is_object()) {
            return std::nullopt;
        }
        output << "  Declared context: " << text_field(*context, "status")
               << "\n    Version: " << text_field(*version, "status")
               << " (recorded " << text_field(*version, "recorded")
               << "; current " << text_field(*version, "current") << ")"
               << "\n    Content: " << text_field(*content, "status")
               << "\n      Recorded lock SHA-256: " << text_field(*content, "recorded_sha256")
               << "\n      Current lock SHA-256: " << text_field(*content, "current_sha256")
               << " (" << text_field(*content, "current_presence") << ")\n";
        for (const json::Value* dimension : {version, content}) {
            const std::string diagnostic = guidance_field(*dimension, "diagnostic");
            if (!diagnostic.empty()) output << "    Observation: " << diagnostic << '\n';
        }
        output << "  Gameplay compatibility: " << text_field(*context, "gameplay_compatibility") << '\n';
    }
    output << "Deep Factorio save metadata: " << text_field(report, "deep_factorio_save_metadata") << '\n';
    return output.str();
}

std::optional<std::string> local_content_text(const json::Value& report)
{
    const std::string schema = text_field(report, "schema");
    std::ostringstream output;
    output << text_field(report, "command") << ": " << text_field(report, "status") << '\n';
    if (schema == "factorio.mod_inventory.v1" || schema == "factorio.mod_inventory_record.v1") {
        const json::Value* records = report.find("records");
        const json::Value* record = report.find("record");
        if (schema == "factorio.mod_inventory.v1" && (records == nullptr || !records->is_array())) return std::nullopt;
        if (schema == "factorio.mod_inventory_record.v1" && (record == nullptr || !record->is_object())) return std::nullopt;
        if (records != nullptr) output << "Records: " << text_field(report, "record_count") << '\n';
        const std::size_t count = record != nullptr ? 1U : records->size();
        for (std::size_t index = 0; index < count; ++index) {
            const json::Value* item = record != nullptr ? record : records->at(index);
            if (item == nullptr || !item->is_object()) return std::nullopt;
            output << "  " << text_field(*item, "name") << " " << text_field(*item, "version")
                   << " [" << text_field(*item, "validation_status") << "] " << text_field(*item, "file_name")
                   << "\n    Source: " << text_field(*item, "source") << " (" << text_field(*item, "source_path") << ")"
                   << "\n    Metadata: " << text_field(*item, "metadata_source")
                   << "; built-in: " << text_field(*item, "virtual_package")
                   << "\n    SHA-256: " << text_field(*item, "sha256")
                   << "\n    Dependencies: " << text_field(*item, "dependencies") << '\n';
            const json::Value* refusal = item->find("refusal");
            if (refusal != nullptr) output << "    Refusal: " << text_field(*refusal, "code") << ": " << text_field(*refusal, "reason") << '\n';
        }
    } else if (schema == "factorio.modset_plan.v1" || schema == "factorio.modset_apply.v1") {
        const json::Value* desired = report.find("desired_mods");
        const json::Value* changes = report.find("changes");
        const json::Value* explanation = report.find("explanation");
        if (desired == nullptr || !desired->is_array() || changes == nullptr || !changes->is_array() ||
            explanation == nullptr || !explanation->is_array()) return std::nullopt;
        output << "Instance: " << text_field(report, "instance_id") << "\nPlan SHA-256: " << text_field(report, "plan_id")
               << "\nCurrent state SHA-256: " << text_field(report, "current_state_sha256") << '\n';
        if (schema == "factorio.modset_apply.v1") output << "Rollback transaction: " << text_field(report, "transaction_id") << '\n';
        output << "Selected packages: " << desired->size() << '\n';
        for (std::size_t index = 0; index < desired->size(); ++index) {
            const json::Value* item = desired->at(index);
            if (item == nullptr || !item->is_object()) return std::nullopt;
            output << "  " << text_field(*item, "name") << " " << text_field(*item, "version")
                   << " (" << text_field(*item, "file_name") << "; " << text_field(*item, "source")
                   << "; built-in: " << text_field(*item, "virtual_package") << ")\n";
        }
        output << "Changes:\n";
        for (std::size_t index = 0; index < changes->size(); ++index) {
            const json::Value* item = changes->at(index);
            if (item == nullptr || !item->is_object()) return std::nullopt;
            output << "  " << text_field(*item, "action") << ": " << text_field(*item, "name")
                   << " " << text_field(*item, "from_version") << " -> " << text_field(*item, "to_version") << '\n';
        }
        output << "Explanation:\n";
        for (std::size_t index = 0; index < explanation->size(); ++index) {
            const json::Value* item = explanation->at(index);
            if (item == nullptr || !item->string_value()) return std::nullopt;
            output << "  " << item->string_value().value() << '\n';
        }
        output << "Budget usage: " << text_field(report, "budget_usage") << '\n';
    } else if (schema == "factorio.modset_rollback.v1") {
        output << "Instance: " << text_field(report, "instance_id")
               << "\nRollback transaction: " << text_field(report, "transaction_id") << '\n';
    } else return std::nullopt;
    output << "Portal access: " << text_field(report, "portal_access")
           << "\nMutation executed: " << text_field(report, "mutation_executed") << '\n';
    return output.str();
}

} // namespace facman::cli
