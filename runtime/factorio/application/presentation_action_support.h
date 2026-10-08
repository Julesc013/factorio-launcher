// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_PRESENTATION_ACTION_SUPPORT_H
#define FACMAN_FACTORIO_APPLICATION_PRESENTATION_ACTION_SUPPORT_H

#include "application_types.h"

#include <initializer_list>
#include <string>

namespace facman::core::json { class Value; class ObjectBuilder; class ArrayBuilder; }

namespace facman::factorio::application {

struct ActionInputField {
    std::string id;
    std::string label;
    std::string type;
    bool required = false;
    std::string default_value;
    std::vector<std::string> choices;
};

facman::core::json::ObjectBuilder action_descriptor(
    const char* action_id,
    const char* command_id,
    const char* label,
    const char* role,
    const char* effect,
    bool available,
    const char* refusal_code = nullptr,
    const char* confirmation = "none",
    const char* input_contract = "none",
    const std::vector<ActionInputField>& input_fields = {});

std::string action_request_json(const SemanticActionRequest& request);
bool recorded_action_request_shape(const facman::core::json::Value& request);
bool effectful_semantic_action(const std::string& action_id);
bool terminal_session_state(const std::string& state);
std::string result_string(const ApplicationResult& result);
void add_json(facman::core::json::ObjectBuilder& output, const char* key, const std::string& source);
void add_problem(
    facman::core::json::ArrayBuilder& problems,
    const std::string& code, const std::string& summary, const std::string& detail = {});
std::string action_result_json(
    const SemanticActionRequest& request, const char* outcome,
    const std::string& replacement_snapshot, const std::string& action_payload,
    const std::string& problem_code, const std::string& problem_summary,
    bool invalidated, std::initializer_list<const char*> declared_effects = {});
bool lower_hex_digest(const std::string& value);
std::string snapshot_revision(const std::string& snapshot);
std::string profile_preparation_json(
    const std::filesystem::path& workspace,
    const std::string& instance_id,
    std::vector<std::string> profile_ids);
facman::core::Result<std::string> snapshot_profile_plan(
    const std::string& snapshot,
    const std::string& instance_id,
    const std::string& profile_id);
std::string selected_save_preparation_json(const std::filesystem::path& workspace,
    const std::string& instance_id, const std::string& launch_intent);
facman::core::json::ObjectBuilder selected_save_action_descriptor(
    const std::string& preparation, const std::string& instance_id);
facman::core::Result<std::string> snapshot_selected_save_plan(const std::string& snapshot,
    const std::string& instance_id, const std::string& launch_intent);

} // namespace facman::factorio::application

#endif
