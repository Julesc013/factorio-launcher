// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "presentation_action_support.h"

#include <algorithm>
#include <iterator>
#include <variant>

namespace facman::factorio::application {

bool effectful_semantic_action(const std::string& action_id)
{
    return action_id == "workspace.initialize" ||
        action_id == "installation.register_read_only" ||
        action_id == "instance.create_isolated" ||
        action_id == "profile.create" ||
        action_id == "profile.select" ||
        action_id == "modsets.apply" ||
        action_id == "modsets.rollback" ||
        action_id == "saves.associate" ||
        action_id == "saves.backup" ||
        action_id == "saves.restore" ||
        action_id == "support.export_redacted_bundle" ||
        action_id == "recovery.apply_supported" ||
        action_id == "launch.play" ||
        action_id == "sessions.stop";
}

bool terminal_session_state(const std::string& state)
{
    static const char* const terminal_states[] = {
        "cancelled",
        "completed",
        "failed",
        "outcome_unknown",
        "recovery_required",
        "refused",
    };
    return std::find(std::begin(terminal_states), std::end(terminal_states), state) !=
        std::end(terminal_states);
}

std::string result_string(const ApplicationResult& result)
{
    if (std::holds_alternative<std::string>(result.output)) {
        return std::get<std::string>(result.output);
    }
    if (std::holds_alternative<modsets::VerifyResult>(result.output)) {
        return modsets::to_json(std::get<modsets::VerifyResult>(result.output));
    }
    if (std::holds_alternative<modsets::Refusal>(result.output)) {
        return modsets::to_json(std::get<modsets::Refusal>(result.output));
    }
    if (std::holds_alternative<saves::BackupResult>(result.output)) {
        return saves::to_json(std::get<saves::BackupResult>(result.output));
    }
    if (std::holds_alternative<saves::CloneResult>(result.output)) {
        return saves::to_json(std::get<saves::CloneResult>(result.output));
    }
    if (std::holds_alternative<saves::Refusal>(result.output)) {
        return saves::to_json(std::get<saves::Refusal>(result.output));
    }
    if (std::holds_alternative<diagnostics::ExportResult>(result.output)) {
        return diagnostics::to_json(std::get<diagnostics::ExportResult>(result.output));
    }
    if (std::holds_alternative<diagnostics::Refusal>(result.output)) {
        return diagnostics::to_json(std::get<diagnostics::Refusal>(result.output));
    }
    return {};
}

} // namespace facman::factorio::application
