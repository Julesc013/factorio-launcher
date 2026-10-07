// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_PRESENTATION_ACTION_SUPPORT_H
#define FACMAN_FACTORIO_APPLICATION_PRESENTATION_ACTION_SUPPORT_H

#include "application_types.h"

#include <string>

namespace facman::core::json { class Value; }

namespace facman::factorio::application {

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
