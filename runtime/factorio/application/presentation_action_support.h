// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_PRESENTATION_ACTION_SUPPORT_H
#define FACMAN_FACTORIO_APPLICATION_PRESENTATION_ACTION_SUPPORT_H

#include "application_types.h"

#include <string>

namespace facman::core::json { class Value; class ObjectBuilder; }

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

} // namespace facman::factorio::application

#endif
