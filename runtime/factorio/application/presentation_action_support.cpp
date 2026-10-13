// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "presentation_action_support.h"
#include "flb_factorio_instance_model.h"

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

json::ObjectBuilder action_descriptor(
    const char* action_id,
    const char* command_id,
    const char* label,
    const char* role,
    const char* effect,
    bool available,
    const char* refusal_code,
    const char* confirmation,
    const char* input_contract,
    const std::vector<ActionInputField>& input_fields)
{
    json::ObjectBuilder action;
    action.add_string("action_id", action_id);
    action.add_string("command_id", command_id);
    action.add_string("label", label);
    action.add_string("accessibility_label", label);
    action.add_string("role", role);
    action.add_string("availability", available ? "available" : "refused");
    json::ArrayBuilder effects;
    effects.add_string(effect);
    action.add_array("effects", effects);
    action.add_string("confirmation", confirmation);
    action.add_string("input_contract", input_contract);
    json::ArrayBuilder fields;
    for (const auto& field : input_fields) {
        json::ObjectBuilder item;
        item.add_string("field_id", field.id);
        item.add_string("label", field.label);
        item.add_string("type", field.type);
        item.add_bool("required", field.required);
        if (field.default_value.empty()) item.add_null("default");
        else item.add_string("default", field.default_value);
        json::ArrayBuilder choices;
        for (const auto& choice : field.choices) choices.add_string(choice);
        item.add_array("choices", choices);
        fields.add_object(item);
    }
    action.add_array("input_fields", fields);
    action.add_bool("backend_owned", true);
    if (available) action.add_null("refusal");
    else {
        json::ObjectBuilder refusal;
        refusal.add_string("code", refusal_code == nullptr ? "action_unavailable" : refusal_code);
        refusal.add_string("reason", "The backend has not admitted this action");
        refusal.add_bool("recoverable", true);
        action.add_object("refusal", refusal);
    }
    return action;
}

std::string action_request_json(const SemanticActionRequest& request)
{
    json::ObjectBuilder input;
    input.add_string("action_id", request.action_id);
    input.add_string("scope", request.scope);
    input.add_string("expected_snapshot_revision", request.expected_snapshot_revision);
    input.add_string("request_id", request.request_id);
    input.add_string("selected_instance_id", request.selected_instance_id);
    input.add_string("durable_operation_id", request.durable_operation_id);
    input.add_string("attempt_id", request.attempt_id);
    input.add_string("confirmation", request.confirmation);
    input.add_string("installation_id", request.installation_id);
    input.add_string("installation_path", request.installation_path);
    input.add_string("new_instance_id", request.new_instance_id);
    input.add_string("display_name", request.display_name);
    input.add_string("template_id", request.template_id);
    input.add_string("profile_id", request.profile_id);
    input.add_string("mod_identity", request.mod_identity);
    input.add_string("save", request.save);
    input.add_string("output_path", request.output_path);
    input.add_string("source_data_root", request.source_data_root);
    input.add_string("transaction_id", request.transaction_id);
    json::ArrayBuilder roots;
    for (const auto& root : request.roots) roots.add_string(root);
    input.add_array("roots", roots);
    if (request.launch_intent == "load_save") input.add_string("launch_intent", request.launch_intent);
    // Preserve the immutable legacy fingerprint when the new input is absent.
    if (!request.source_path.empty()) input.add_string("source_path", request.source_path);
    return input.serialize();
}

bool recorded_action_request_shape(const json::Value& request)
{
    if (!request.is_object()) return false;
    std::vector<std::string> expected = {
        "action_id", "scope", "expected_snapshot_revision", "request_id",
        "selected_instance_id", "durable_operation_id", "attempt_id", "confirmation",
        "installation_id", "installation_path", "new_instance_id", "display_name",
        "template_id", "profile_id", "mod_identity", "save", "output_path",
        "source_data_root", "transaction_id", "roots",
    };
    // Optional extensions leave immutable legacy request bytes unchanged.
    if (request.find("launch_intent") != nullptr) {
        if (string_field(request, "launch_intent") != "load_save") return false;
        expected.emplace_back("launch_intent");
    }
    if (request.find("source_path") != nullptr) {
        if (string_field(request, "source_path").empty()) return false;
        expected.emplace_back("source_path");
    }
    auto actual = request.object_keys();
    std::sort(actual.begin(), actual.end());
    std::sort(expected.begin(), expected.end());
    return actual == expected;
}

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

std::string selected_save_preparation_json(const std::filesystem::path& workspace,
    const std::string& instance_id, const std::string& launch_intent)
{
    auto planned = instance::selected_save_preparation_plan(workspace, {instance_id, launch_intent});
    json::ObjectBuilder identity;
    identity.add_string("instance_id", instance_id);
    identity.add_string("launch_intent", launch_intent);
    if (planned) {
        add_json(identity, "plan", planned.value());
        identity.add_null("refusal");
    } else {
        identity.add_null("plan");
        json::ObjectBuilder refusal;
        refusal.add_string("code", planned.error().code);
        refusal.add_string("detail", planned.error().message);
        identity.add_object("refusal", refusal);
    }
    return identity.serialize();
}

json::ObjectBuilder selected_save_action_descriptor(const std::string& preparation, const std::string& instance_id)
{
    auto document = json::parse(preparation);
    const auto* refusal = document ? document.value().find("refusal") : nullptr;
    const bool available = refusal && refusal->is_null();
    const std::string code = refusal ? string_field(*refusal, "code") : "selected_context_plan_invalid";
    const std::vector<ActionInputField> fields {{"selected_instance_id", "Selected instance", "enum", true,
        instance_id, instance_id.empty() ? std::vector<std::string>() : std::vector<std::string> {instance_id}}};
    return action_descriptor("readiness.prepare_selected_save", "presentation.action", "Record selected save context",
        "manage", "workspace_write", available, available ? nullptr : code.c_str(), "explicit",
        "facman.semantic_action_input.v1", fields);
}

facman::core::Result<std::string> snapshot_selected_save_plan(const std::string& snapshot,
    const std::string& instance_id, const std::string& launch_intent)
{
    using Result = facman::core::Result<std::string>;
    auto document = json::parse(snapshot);
    const auto* dependencies = document ? document.value().find("dependency_identities") : nullptr;
    const auto* identity = dependencies ? dependencies->find("selected_save_preparation") : nullptr;
    if (!identity || string_field(*identity, "instance_id") != instance_id ||
        string_field(*identity, "launch_intent") != launch_intent) return Result::failure({
            "selected_context_plan_invalid", "Snapshot does not bind this selected context component", {}});
    const auto* refusal = identity->find("refusal");
    const auto* plan = identity->find("plan");
    if (refusal && refusal->is_object()) return Result::failure({string_field(*refusal, "code"), string_field(*refusal, "detail"), {}});
    const std::string sha = plan ? string_field(*plan, "plan_sha256") : std::string();
    if (!refusal || !refusal->is_null() || !lower_hex_digest(sha)) return Result::failure({
        "selected_context_plan_invalid", "Selected context owner plan is invalid", {}});
    return Result::success(sha);
}

std::string configuration_preparation_json(const std::filesystem::path& workspace,
    const std::string& instance_id, const std::string& launch_intent)
{
    auto planned = instance::configuration_preparation_plan(workspace, {instance_id, launch_intent});
    json::ObjectBuilder identity;
    identity.add_string("instance_id", instance_id);
    identity.add_string("launch_intent", launch_intent);
    if (planned) {
        add_json(identity, "plan", planned.value());
        identity.add_null("refusal");
    } else {
        identity.add_null("plan");
        json::ObjectBuilder refusal;
        refusal.add_string("code", planned.error().code);
        refusal.add_string("detail", planned.error().message);
        identity.add_object("refusal", refusal);
    }
    return identity.serialize();
}

json::ObjectBuilder configuration_action_descriptor(const std::string& preparation, const std::string& instance_id)
{
    auto document = json::parse(preparation);
    const auto* refusal = document ? document.value().find("refusal") : nullptr;
    const bool available = refusal && refusal->is_null();
    const std::string code = refusal ? string_field(*refusal, "code") : "configuration_plan_invalid";
    const std::vector<ActionInputField> fields {{"selected_instance_id", "Selected instance", "enum", true,
        instance_id, instance_id.empty() ? std::vector<std::string>() : std::vector<std::string> {instance_id}}};
    return action_descriptor("readiness.prepare_configuration", "presentation.action", "Prepare routing configuration",
        "manage", "workspace_write", available, available ? nullptr : code.c_str(), "explicit",
        "facman.semantic_action_input.v1", fields);
}

facman::core::Result<std::string> snapshot_configuration_plan(const std::string& snapshot,
    const std::string& instance_id, const std::string& launch_intent)
{
    using Result = facman::core::Result<std::string>;
    auto document = json::parse(snapshot);
    const auto* dependencies = document ? document.value().find("dependency_identities") : nullptr;
    const auto* identity = dependencies ? dependencies->find("configuration_preparation") : nullptr;
    if (!identity || string_field(*identity, "instance_id") != instance_id ||
        string_field(*identity, "launch_intent") != launch_intent) return Result::failure({
            "configuration_plan_invalid", "Snapshot does not bind this configuration component", {}});
    const auto* refusal = identity->find("refusal");
    const auto* plan = identity->find("plan");
    if (refusal && refusal->is_object()) return Result::failure({string_field(*refusal, "code"), string_field(*refusal, "detail"), {}});
    const std::string sha = plan ? string_field(*plan, "plan_sha256") : std::string();
    if (!refusal || !refusal->is_null() || !lower_hex_digest(sha)) return Result::failure({
        "configuration_plan_invalid", "Configuration owner plan is invalid", {}});
    return Result::success(sha);
}

facman::core::Result<MakeReadyStage> snapshot_make_ready_stage(const std::string& snapshot,
    const std::string& instance_id, const std::string& launch_intent)
{
    using Result = facman::core::Result<MakeReadyStage>;
    auto configuration = snapshot_configuration_plan(snapshot, instance_id, launch_intent);
    if (configuration) return Result::success(
        {MakeReadyComponent::routing_configuration, configuration.take_value()});
    // Only a satisfied routing observation permits selected-context admission.
    // Every other owner refusal remains a refusal, including missing repair support.
    if (configuration.error().code != "configuration_already_current")
        return Result::failure(configuration.error());
    auto selected = snapshot_selected_save_plan(snapshot, instance_id, launch_intent);
    if (!selected) return Result::failure(selected.error());
    return Result::success({MakeReadyComponent::selected_save_declared_context, selected.take_value()});
}

json::ObjectBuilder make_ready_action_descriptor(const std::string& configuration,
    const std::string& selected_save, const std::string& instance_id, const std::string& launch_intent)
{
    // These reports are the same reports bound into the presentation revision.
    json::ObjectBuilder dependencies;
    add_json(dependencies, "configuration_preparation", configuration);
    add_json(dependencies, "selected_save_preparation", selected_save);
    json::ObjectBuilder snapshot;
    snapshot.add_object("dependency_identities", dependencies);
    auto stage = snapshot_make_ready_stage(snapshot.serialize(), instance_id, launch_intent);
    const std::vector<ActionInputField> fields {{"selected_instance_id", "Selected instance", "enum", true,
        instance_id, instance_id.empty() ? std::vector<std::string>() : std::vector<std::string> {instance_id}}};
    return action_descriptor("readiness.prepare", "presentation.action", "Make Ready",
        "manage", "workspace_write", stage.ok(), stage ? nullptr : stage.error().code.c_str(), "explicit",
        "facman.semantic_action_input.v1", fields);
}

facman::core::Result<std::string> make_ready_stage_result(const MakeReadyStage& stage,
    const std::string& instance_id, const std::string& launch_intent, const std::string& owner_result)
{
    using Result = facman::core::Result<std::string>;
    const bool configuration = stage.component == MakeReadyComponent::routing_configuration;
    const char* owner_command = configuration ? "readiness.prepare_configuration" : "readiness.prepare_selected_save";
    const char* owner_schema = configuration ? "factorio.configuration_preparation_result.v1"
        : "factorio.selected_save_preparation_result.v1";
    auto owner = json::parse(owner_result);
    const auto false_field = [&](const char* name) {
        const auto* field = owner ? owner.value().find(name) : nullptr;
        auto value = field ? field->bool_value() : facman::core::Result<bool>::failure({"missing", "missing", {}});
        return value && !value.value();
    };
    if (!owner || !owner.value().is_object() || string_field(owner.value(), "schema") != owner_schema ||
        string_field(owner.value(), "command") != owner_command ||
        string_field(owner.value(), "instance_id") != instance_id ||
        string_field(owner.value(), "transaction_id").empty() ||
        string_field(owner.value(), "composition") != "partial" ||
        !false_field("execution_started") || !false_field("permit_issued") || !lower_hex_digest(stage.plan_sha256))
        return Result::failure({"make_ready_owner_result_unknown",
            "The owner may have committed; inspect its journal before any retry", {},
            facman::core::OutcomeKind::recovery_required});
    json::ObjectBuilder completed;
    completed.add_string("component", configuration ? "routing_configuration" : "selected_save_declared_context");
    completed.add_string("owner_command", owner_command);
    completed.add_string("transaction_id", string_field(owner.value(), "transaction_id"));
    completed.add_string("plan_sha256", stage.plan_sha256);
    completed.add_value("owner_result", owner.value());
    json::ArrayBuilder effects;
    effects.add_object(completed);
    json::ArrayBuilder deferred;
    if (configuration && launch_intent == "load_save") {
        json::ObjectBuilder next;
        next.add_string("component", "selected_save_declared_context");
        next.add_string("reason", "fresh_revision_required");
        deferred.add_object(next);
    }
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.make_ready_preparation_result.v1");
    output.add_string("command", "readiness.prepare");
    output.add_string("instance_id", instance_id);
    output.add_string("launch_intent", launch_intent);
    output.add_string("composition", "partial");
    output.add_array("completed_components", effects);
    output.add_array("deferred_components", deferred);
    output.add_bool("fresh_revision_required", true);
    output.add_bool("readiness_complete", false);
    output.add_bool("execution_started", false);
    output.add_bool("permit_issued", false);
    output.add_string("factorio_support_claim", "unclaimed");
    return Result::success(output.serialize());
}

bool has_preparation_plan(const std::string& action_id)
{
    return action_id == "readiness.prepare_joined" || action_id == "profile.select" || action_id == "readiness.prepare_selected_save" ||
        action_id == "readiness.prepare_configuration" || action_id == "readiness.prepare";
}

facman::core::Result<std::string> snapshot_action_preparation_plan(const std::string& snapshot,
    const SemanticActionRequest& request, MakeReadyStage& make_ready_stage)
{
    using Result = facman::core::Result<std::string>;
    if (request.action_id == "readiness.prepare_joined") return snapshot_joined_plan(snapshot, request);
    if (request.action_id != "readiness.prepare")
        return request.action_id == "profile.select"
            ? snapshot_profile_plan(snapshot, request.selected_instance_id, request.profile_id)
            : request.action_id == "readiness.prepare_configuration"
                ? snapshot_configuration_plan(snapshot, request.selected_instance_id, request.launch_intent)
                : snapshot_selected_save_plan(snapshot, request.selected_instance_id, request.launch_intent);
    auto bound = snapshot_make_ready_stage(snapshot, request.selected_instance_id, request.launch_intent);
    if (!bound) return Result::failure(bound.error());
    make_ready_stage = bound.take_value();
    return Result::success(make_ready_stage.plan_sha256);
}

bool effectful_semantic_action(const std::string& action_id)
{
    return action_id == "readiness.prepare_joined" || action_id == "readiness.prepare" || action_id == "readiness.prepare_configuration" || action_id == "readiness.prepare_selected_save" || action_id == "workspace.initialize" ||
        action_id == "installation.register_read_only" ||
        action_id == "instance.create_isolated" ||
        action_id == "profile.create" ||
        action_id == "profile.select" ||
        action_id == "modsets.apply" ||
        action_id == "modsets.import" ||
        action_id == "modsets.export" ||
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
    if (std::holds_alternative<modsets::ExportResult>(result.output)) {
        return modsets::to_json(std::get<modsets::ExportResult>(result.output));
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

void add_json(json::ObjectBuilder& output, const char* key, const std::string& source)
{
    auto value = json::parse(source);
    if (value) output.add_value(key, value.value());
    else output.add_null(key);
}

void add_problem(
    json::ArrayBuilder& problems,
    const std::string& code,
    const std::string& summary,
    const std::string& detail)
{
    json::ObjectBuilder problem;
    problem.add_string("code", code);
    problem.add_string("summary", summary);
    if (detail.empty()) problem.add_null("detail");
    else problem.add_string("detail", detail);
    problems.add_object(problem);
}

std::string action_result_json(
    const SemanticActionRequest& request,
    const char* outcome,
    const std::string& replacement_snapshot,
    const std::string& action_payload,
    const std::string& problem_code,
    const std::string& problem_summary,
    bool invalidated,
    std::initializer_list<const char*> declared_effects)
{
    json::ObjectBuilder operation;
    operation.add_string("request_id", request.request_id);
    if (request.durable_operation_id.empty()) {
        operation.add_null("operation_id");
        operation.add_null("durable_operation_id");
    } else {
        operation.add_string("operation_id", request.durable_operation_id);
        operation.add_string("durable_operation_id", request.durable_operation_id);
    }
    if (request.attempt_id.empty()) operation.add_null("attempt_id");
    else operation.add_string("attempt_id", request.attempt_id);
    const std::string& target_instance = request.new_instance_id.empty()
        ? request.selected_instance_id : request.new_instance_id;
    if (target_instance.empty()) operation.add_null("target_instance_id");
    else operation.add_string("target_instance_id", target_instance);
    if (request.installation_id.empty()) operation.add_null("target_installation_id");
    else operation.add_string("target_installation_id", request.installation_id);
    operation.add_string("outcome", outcome);

    json::ArrayBuilder effects;
    for (const char* effect : declared_effects) effects.add_string(effect);
    json::ArrayBuilder diagnostics;
    json::ArrayBuilder problems;
    if (!problem_code.empty()) add_problem(problems, problem_code, problem_summary);
    json::ObjectBuilder output;
    output.add_string("schema", "facman.semantic_action_result.v1");
    output.add_string("command", "presentation.action");
    output.add_string("action_id", request.action_id);
    output.add_string("request_id", request.request_id);
    output.add_string("outcome", outcome);
    output.add_object("operation", operation);
    output.add_array("effects", effects);
    output.add_array("diagnostics", diagnostics);
    output.add_array("problems", problems);
    if (replacement_snapshot.empty()) output.add_null("replacement_snapshot");
    else add_json(output, "replacement_snapshot", replacement_snapshot);
    if (action_payload.empty()) output.add_null("action_payload");
    else add_json(output, "action_payload", action_payload);
    if (!invalidated) output.add_null("invalidation");
    else {
        json::ObjectBuilder invalidation;
        invalidation.add_bool("required", true);
        invalidation.add_string("reason", "explicit_installation_scan_completed");
        output.add_object("invalidation", invalidation);
    }
    return output.serialize();
}

std::string joined_preparation_json(const std::filesystem::path& workspace,
    const std::string& instance_id, const std::string& launch_intent)
{
    auto planned = instance::joined_preparation_plan(workspace, {instance_id, launch_intent});
    json::ObjectBuilder report;
    if (planned) {
        add_json(report, "plan", planned.value());
        report.add_null("refusal");
    } else {
        report.add_null("plan");
        json::ObjectBuilder refusal;
        refusal.add_string("code", planned.error().code);
        refusal.add_string("detail", planned.error().message);
        report.add_object("refusal", refusal);
    }
    return report.serialize();
}

json::ObjectBuilder joined_preparation_descriptor(const std::string& preparation)
{
    auto report = json::parse(preparation);
    const auto* plan = report ? report.value().find("plan") : nullptr;
    const auto* refusal = report ? report.value().find("refusal") : nullptr;
    const auto* desired = plan ? plan->find("desired_state") : nullptr;
    const bool available = plan && plan->is_object() && desired && refusal && refusal->is_null();
    std::vector<ActionInputField> fields;
    if (available) {
        const auto add = [&](const char* id, const char* label, const std::string& value) {
            fields.push_back({id, label, "enum", true, value, {value}});
        };
        add("selected_instance_id", "Instance", string_field(*plan, "instance_id"));
        add("installation_id", "Registered installation", string_field(*desired, "installation_id"));
        add("profile_id", "Current profile", string_field(*desired, "profile_id"));
        if (string_field(*plan, "launch_intent") == "load_save")
            add("save", "Exact selected save", string_field(*desired, "selected_save"));
    }
    const auto code = refusal ? string_field(*refusal, "code") : "make_ready_plan_invalid";
    return action_descriptor("readiness.prepare_joined", "presentation.action", "Make Ready with current settings",
        "primary", "workspace_write", available, available ? nullptr : code.c_str(),
        "explicit", "facman.semantic_action_input.v1", fields);
}

facman::core::Result<std::string> snapshot_joined_plan(const std::string& snapshot,
    const SemanticActionRequest& request)
{
    using Result = facman::core::Result<std::string>;
    auto document = json::parse(snapshot);
    const auto* dependencies = document ? document.value().find("dependency_identities") : nullptr;
    const auto* report = dependencies ? dependencies->find("joined_preparation") : nullptr;
    const auto* plan = report ? report->find("plan") : nullptr;
    const auto* desired = plan ? plan->find("desired_state") : nullptr;
    if (!desired || !request.new_instance_id.empty() || string_field(*plan, "instance_id") != request.selected_instance_id ||
        string_field(*plan, "launch_intent") != request.launch_intent ||
        string_field(*desired, "installation_id") != request.installation_id ||
        string_field(*desired, "profile_id") != request.profile_id ||
        string_field(*desired, "selected_save") != request.save ||
        !lower_hex_digest(string_field(*plan, "plan_sha256")))
        return Result::failure({"make_ready_desired_state_mismatch",
            "Desired installation, current profile and selected save must match the reviewed plan and its locked content", {}, facman::core::OutcomeKind::refused});
    return Result::success(plan->serialize());
}

std::string joined_preparation_result(const std::string& source,
    const std::vector<std::string>& components, const std::string& readiness,
    const std::string& continuation, bool effects_verified)
{
    auto plan = json::parse(source);
    auto observed = json::parse(readiness);
    const bool complete = observed && string_field(observed.value(), "configuration_state") == "ready" &&
        string_field(observed.value(), "preparation_state") == "already_prepared";
    json::ObjectBuilder result;
    result.add_string("schema", "factorio.make_ready_joined_result.v1");
    result.add_string("command", "readiness.prepare_joined");
    add_json(result, "plan", source);
    result.add_string("plan_sha256", plan ? string_field(plan.value(), "plan_sha256") : "");
    json::ArrayBuilder completed;
    for (const auto& component : components) {
        auto receipt = json::parse(component);
        const auto* effects = receipt ? receipt.value().find("completed_components") : nullptr;
        if (effects && effects->size() == 1U) completed.add_value(*effects->at(0));
    }
    result.add_array("completed_components", completed);
    result.add_string("continuation", continuation);
    result.add_bool("completed_effects_verified", effects_verified);
    result.add_bool("remaining_effects_blocked_before_effects", continuation == "fresh_request_after_input_correction");
    add_json(result, "readiness_observation", readiness);
    result.add_bool("preparation_complete", complete);
    result.add_bool("fresh_revision_required", !complete);
    result.add_bool("readiness_complete", false);
    result.add_bool("execution_started", false);
    result.add_bool("permit_issued", false);
    result.add_string("factorio_support_claim", "unclaimed");
    return result.serialize();
}

} // namespace facman::factorio::application
