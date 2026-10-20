// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_APPLICATION_PRESENTATION_ACTION_SUPPORT_H
#define FACMAN_FACTORIO_APPLICATION_PRESENTATION_ACTION_SUPPORT_H

#include "application_types.h"

#include <initializer_list>
#include <optional>
#include <string>

namespace facman::core::json { class Value; class ObjectBuilder; class ArrayBuilder; }

namespace facman::factorio::application {

class ApplicationContext;
class PresentationActionLedger;

struct AdvertisedAction {
    bool found = false;
    bool available = false;
    std::string refusal_code;
    std::string refusal_reason;
};
AdvertisedAction advertised_action(const std::string& snapshot, const std::string& action_id);
// Only the private strict ledger reader supplies its already verified original receipt/request.
facman::core::Result<std::string> verified_repair_review_binding(const std::filesystem::path& workspace,
    const std::string& instance_id, const std::string& receipt, const std::string& original_request);
std::string reviewed_repair_preparation_json(const std::filesystem::path& workspace,
    const PresentationQueryRequest& request, const facman::core::Result<std::string>& verified_review);
facman::core::json::ObjectBuilder installation_repair_review_descriptor(
    const std::vector<facman::workspace::InstanceRecord>& instances,
    const std::string& instance_id, const std::string& default_instance);
std::string dispatch_installation_repair_review(ApplicationContext& context,
    const SemanticActionRequest& request, const std::string& snapshot);

std::string joined_preparation_json(const std::filesystem::path& workspace,
    const PresentationQueryRequest& request, const PresentationActionLedger& ledger);
std::optional<ApplicationResult> installation_repair_admission(ApplicationContext& context,
    const SemanticActionRequest& request, const std::string& snapshot);

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
std::vector<std::filesystem::path> local_modset_maintenance_paths(
    const std::vector<facman::factorio::mods::ModRef>& inventory,
    const std::vector<facman::workspace::InstanceRecord>& instances,
    const std::string& instance_id);
std::string append_modset_maintenance_choice(const facman::factorio::mods::ModRef& mod,
    const std::vector<std::filesystem::path>& paths, std::vector<std::string>& choices);
ApplicationResult dispatch_content_modset(ApplicationContext& context,
    const SemanticActionRequest& request, const std::string& snapshot);
std::string snapshot_create_input_problem(const SemanticActionRequest& request);
ApplicationResult dispatch_snapshot_create(ApplicationContext& context, const SemanticActionRequest& request);
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


std::string configuration_preparation_json(const std::filesystem::path& workspace,
    const std::string& instance_id, const std::string& launch_intent);
facman::core::json::ObjectBuilder configuration_action_descriptor(
    const std::string& preparation, const std::string& instance_id);
facman::core::Result<std::string> snapshot_configuration_plan(const std::string& snapshot,
    const std::string& instance_id, const std::string& launch_intent);

enum class MakeReadyComponent { routing_configuration, selected_save_declared_context };
struct MakeReadyStage {
    MakeReadyComponent component = MakeReadyComponent::routing_configuration;
    std::string plan_sha256;
};
facman::core::Result<MakeReadyStage> snapshot_make_ready_stage(const std::string& snapshot,
    const std::string& instance_id, const std::string& launch_intent);
facman::core::json::ObjectBuilder make_ready_action_descriptor(
    const std::string& configuration, const std::string& selected_save,
    const std::string& instance_id, const std::string& launch_intent);
facman::core::Result<std::string> make_ready_stage_result(const MakeReadyStage& stage,
    const std::string& instance_id, const std::string& launch_intent, const std::string& owner_result);
bool has_preparation_plan(const std::string& action_id);
facman::core::Result<std::string> snapshot_action_preparation_plan(const std::string& snapshot,
    const SemanticActionRequest& request, MakeReadyStage& make_ready_stage);

std::string joined_preparation_json(const std::filesystem::path& workspace,
    const std::string& instance_id, const std::string& launch_intent);
std::string joined_installation_preparation_result(const std::string& plan,
    const std::string& installation_receipt, const std::string& remaining_result,
    const std::string& continuation, bool installation_verified, bool effects_verified);
facman::core::json::ObjectBuilder joined_preparation_descriptor(const std::string& preparation);
facman::core::Result<std::string> snapshot_joined_plan(const std::string& snapshot,
    const SemanticActionRequest& request);
std::string joined_preparation_result(const std::string& plan,
    const std::vector<std::string>& components, const std::string& readiness,
    const std::string& continuation = "inspect_original_request", bool effects_verified = false);
std::string joined_content_preparation_result(const std::string& plan,
    const std::string& content_receipt, const std::string& joined_result,
    const std::string& continuation, bool content_verified, bool effects_verified);

} // namespace facman::factorio::application

#endif
