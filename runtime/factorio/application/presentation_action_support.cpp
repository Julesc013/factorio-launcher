// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "presentation_action_support.h"

#include "command_result.h"
#include "fl_json.h"
#include "flb_factorio_profiles.h"

#include <algorithm>
#include <iterator>
#include <variant>

namespace facman::factorio::application {
namespace json = facman::core::json;
namespace {

std::string string_field(const json::Value& value, const char* key)
{
    const auto* field = value.find(key);
    if (field == nullptr || !field->is_string()) return {};
    auto text = field->string_value();
    return text ? text.take_value() : std::string();
}

} // namespace

bool lower_hex_digest(const std::string& value)
{
    return value.size() == 64U && std::all_of(value.begin(), value.end(), [](char c) {
        return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
    });
}

std::string snapshot_revision(const std::string& snapshot)
{
    auto document = json::parse(snapshot);
    if (!document || !document.value().is_object()) return {};
    return decode_json_string_field(snapshot, "revision");
}

std::string profile_preparation_json(
    const std::filesystem::path& workspace,
    const std::string& instance_id,
    std::vector<std::string> profile_ids)
{
    std::sort(profile_ids.begin(), profile_ids.end());
    profile_ids.erase(std::unique(profile_ids.begin(), profile_ids.end()), profile_ids.end());
    json::ArrayBuilder identities;
    for (const auto& profile_id : profile_ids) {
        profiles::EffectiveRequest request;
        request.instance_id = instance_id;
        request.profile_id = profile_id;
        auto planned = profiles::profiles_plan(workspace, request);
        std::string sha;
        if (planned) {
            auto document = json::parse(planned.value());
            if (document && document.value().is_object()) sha = string_field(document.value(), "plan_sha256");
        }
        json::ObjectBuilder identity;
        identity.add_string("instance_id", instance_id);
        identity.add_string("profile_id", profile_id);
        if (lower_hex_digest(sha)) {
            identity.add_string("plan_sha256", sha);
            identity.add_null("refusal");
        } else {
            identity.add_null("plan_sha256");
            json::ObjectBuilder refusal;
            refusal.add_string("code", planned ? "profile_preparation_revision_invalid" : planned.error().code);
            refusal.add_string("detail", planned ? "Owner plan did not provide a valid preparation digest" : planned.error().message);
            identity.add_object("refusal", refusal);
        }
        identities.add_object(identity);
    }
    return identities.serialize();
}

facman::core::Result<std::string> snapshot_profile_plan(
    const std::string& snapshot,
    const std::string& instance_id,
    const std::string& profile_id)
{
    using Result = facman::core::Result<std::string>;
    const auto invalid = []() {
        return Result::failure({"profile_preparation_revision_invalid",
            "Snapshot does not bind one valid owner plan for the selected profile", {},
            facman::core::OutcomeKind::refused});
    };
    auto document = json::parse(snapshot);
    if (!document || !document.value().is_object()) return invalid();
    const auto* dependencies = document.value().find("dependency_identities");
    const auto* identities = dependencies != nullptr && dependencies->is_object()
        ? dependencies->find("profile_preparation") : nullptr;
    if (identities == nullptr || !identities->is_array()) return invalid();
    const json::Value* selected = nullptr;
    for (std::size_t index = 0U; index < identities->size(); ++index) {
        const auto* entry = identities->at(index);
        if (entry == nullptr || !entry->is_object() ||
            string_field(*entry, "instance_id") != instance_id ||
            string_field(*entry, "profile_id") != profile_id) continue;
        if (selected != nullptr) return invalid();
        selected = entry;
    }
    if (selected == nullptr) return invalid();
    const auto* refusal = selected->find("refusal");
    const auto* sha = selected->find("plan_sha256");
    if (refusal == nullptr || sha == nullptr) return invalid();
    if (refusal->is_object() && sha->is_null()) {
        const std::string code = string_field(*refusal, "code");
        const std::string detail = string_field(*refusal, "detail");
        if (!code.empty() && !detail.empty()) return Result::failure(
            {code, detail, {}, facman::core::OutcomeKind::refused});
    }
    const std::string value = string_field(*selected, "plan_sha256");
    if (!refusal->is_null() || !lower_hex_digest(value)) return invalid();
    return Result::success(value);
}

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
