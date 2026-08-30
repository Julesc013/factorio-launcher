// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "presentation_service.h"

#include "command_result.h"
#include "facman/build_identity.hpp"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_transaction.h"
#include "flb_factorio_discovery.h"
#include "flb_factorio_instance_model.h"
#include "generated/version.h"
#include "handlers/diagnostics.h"
#include "handlers/doctor.h"
#include "handlers/installs.h"
#include "handlers/instances.h"
#include "handlers/launch.h"
#include "handlers/mods.h"
#include "handlers/modsets.h"
#include "handlers/profiles.h"
#include "handlers/recovery.h"
#include "handlers/saves.h"

#include <algorithm>
#include <atomic>
#include <cctype>
#include <chrono>
#include <fstream>
#include <initializer_list>
#include <iterator>
#include <utility>
#include <variant>

namespace facman::factorio::application {
namespace json = facman::core::json;
namespace lifecycle = facman::factorio::instance;
namespace transactions = facman::transaction;
namespace fs = std::filesystem;

namespace {

std::string digest(const std::string& value)
{
    return facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(value.data()), value.size());
}

constexpr std::uint64_t kMaximumActionReceiptBytes = 8U * 1024U * 1024U;

fs::path action_receipt_path(const fs::path& workspace, const std::string& key)
{
    // Keep the path compact for long Windows workspaces. The digest is the
    // bounded opaque key; the record itself carries the full schema and key.
    return workspace / ".facman" / "action-receipts-v2" /
        (digest(key) + ".v2.json");
}

bool exact_keys(const json::Value& value, std::initializer_list<const char*> expected)
{
    if (!value.is_object()) return false;
    std::vector<std::string> actual = value.object_keys();
    std::vector<std::string> wanted;
    wanted.reserve(expected.size());
    for (const char* key : expected) wanted.emplace_back(key);
    std::sort(actual.begin(), actual.end());
    std::sort(wanted.begin(), wanted.end());
    return actual == wanted;
}

std::string receipt_string(const json::Value& object, const char* key)
{
    const json::Value* value = object.find(key);
    if (value == nullptr || !value->is_string()) return {};
    auto decoded = value->string_value();
    return decoded ? decoded.take_value() : std::string();
}

bool nullable_string_matches(
    const json::Value& object,
    const char* key,
    const std::string& expected)
{
    const json::Value* value = object.find(key);
    if (value == nullptr) return false;
    if (expected.empty()) return value->is_null();
    return value->is_string() && receipt_string(object, key) == expected;
}

bool semantic_outcome(const std::string& outcome)
{
    return outcome == "cancelled_before_dispatch" ||
        outcome == "refused_before_effects" || outcome == "completed" ||
        outcome == "cancellation_requested_but_completed" ||
        outcome == "recovery_required" || outcome == "outcome_unknown";
}

bool lower_hex_digest(const std::string& value)
{
    return value.size() == 64U && std::all_of(value.begin(), value.end(), [](char ch) {
        return (ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f');
    });
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
    return input.serialize();
}

bool read_action_receipt(
    const fs::path& path,
    const SemanticActionRequest& request,
    std::string& fingerprint,
    std::string& receipt_state,
    std::string& result,
    std::string& detail)
{
    facman::platform::StableInputFile input;
    auto opened = input.open_no_follow(path);
    if (!opened.ok()) {
        detail = opened.code + ": " + opened.detail;
        return false;
    }
    if (input.size() == 0U || input.size() > kMaximumActionReceiptBytes) {
        detail = "presentation action receipt size is outside the admitted bounds";
        return false;
    }
    std::string source(static_cast<std::size_t>(input.size()), '\0');
    if (input.read_at(0U, source.data(), source.size()) != source.size()) {
        detail = "presentation action receipt could not be read completely";
        return false;
    }
    auto stable = input.revalidate();
    if (!stable.ok()) {
        detail = stable.code + ": " + stable.detail;
        return false;
    }
    json::Limits limits;
    limits.maximum_bytes = static_cast<std::size_t>(kMaximumActionReceiptBytes);
    limits.maximum_depth = 32U;
    limits.maximum_nodes = 100000U;
    limits.maximum_string_bytes = static_cast<std::size_t>(kMaximumActionReceiptBytes);
    auto document = json::parse(source, limits);
    if (!document || !exact_keys(document.value(), {
            "schema", "authority", "contract_version", "idempotency_key",
            "key_digest", "request_fingerprint", "action_id", "scope",
            "request_id", "operation_id", "attempt_id", "target_instance_id",
            "target_installation_id", "state", "result_length", "result_digest",
            "effect_set", "request_json", "result_json"})) {
        detail = "presentation action receipt shape is invalid or contains unknown fields";
        return false;
    }
    const json::Value& receipt = document.value();
    const json::Value* version = receipt.find("contract_version");
    if (version == nullptr || !version->is_number()) {
        detail = "presentation action receipt version is not an integer";
        return false;
    }
    const auto parsed_version = version->unsigned_integer_value();
    const std::string key = receipt_string(receipt, "idempotency_key");
    fingerprint = receipt_string(receipt, "request_fingerprint");
    const std::string state = receipt_string(receipt, "state");
    const std::string recorded_action = receipt_string(receipt, "action_id");
    const std::string recorded_scope = receipt_string(receipt, "scope");
    const std::string recorded_request = receipt_string(receipt, "request_id");
    const std::string recorded_operation = receipt_string(receipt, "operation_id");
    const std::string recorded_attempt = receipt_string(receipt, "attempt_id");
    const std::string recorded_instance = receipt_string(receipt, "target_instance_id");
    const std::string recorded_installation = receipt_string(receipt, "target_installation_id");
    receipt_state = state;
    if (receipt_string(receipt, "schema") != "facman.presentation_action_receipt.v2" ||
        receipt_string(receipt, "authority") != "facman.application.presentation_action.v1" ||
        !parsed_version || parsed_version.value() != 2U ||
        key != request.idempotency_key || receipt_string(receipt, "key_digest") != digest(key) ||
        !lower_hex_digest(fingerprint) || recorded_action.empty() || recorded_scope.empty() ||
        recorded_request.empty() || recorded_operation.empty() || recorded_attempt.empty() ||
        receipt.find("target_instance_id") == nullptr ||
        !receipt.find("target_instance_id")->is_string() ||
        receipt.find("target_installation_id") == nullptr ||
        !receipt.find("target_installation_id")->is_string() ||
        (state != "accepted_outcome_unknown" && state != "terminal")) {
        detail = "presentation action receipt authority, version, identity, or state is invalid";
        return false;
    }
    const json::Value* recorded_result = document.value().find("result_json");
    const json::Value* recorded_request_json = document.value().find("request_json");
    const json::Value* result_length = receipt.find("result_length");
    const json::Value* effect_set = receipt.find("effect_set");
    if (recorded_result == nullptr || !recorded_result->is_string() ||
        recorded_request_json == nullptr || !recorded_request_json->is_string() ||
        result_length == nullptr || !result_length->is_number() ||
        effect_set == nullptr || !effect_set->is_array()) {
        detail = "presentation action receipt is incomplete";
        return false;
    }
    auto decoded_request = recorded_request_json->string_value();
    if (!decoded_request || digest(decoded_request.value()) != fingerprint) {
        detail = "presentation action receipt request digest is invalid";
        return false;
    }
    auto request_document = json::parse(decoded_request.value(), limits);
    if (!request_document || !exact_keys(request_document.value(), {
            "action_id", "scope", "expected_snapshot_revision", "request_id",
            "selected_instance_id", "durable_operation_id", "attempt_id", "confirmation",
            "installation_id", "installation_path", "new_instance_id", "display_name",
            "template_id", "profile_id", "mod_identity", "save", "output_path",
            "source_data_root", "transaction_id", "roots"})) {
        detail = "presentation action receipt request shape is invalid";
        return false;
    }
    const json::Value& recorded_input = request_document.value();
    const char* const string_fields[] = {
        "action_id", "scope", "expected_snapshot_revision", "request_id",
        "selected_instance_id", "durable_operation_id", "attempt_id", "confirmation",
        "installation_id", "installation_path", "new_instance_id", "display_name",
        "template_id", "profile_id", "mod_identity", "save", "output_path",
        "source_data_root", "transaction_id",
    };
    for (const char* field : string_fields) {
        if (recorded_input.find(field) == nullptr || !recorded_input.find(field)->is_string()) {
            detail = "presentation action receipt request fields are invalid";
            return false;
        }
    }
    const json::Value* recorded_roots = recorded_input.find("roots");
    if (recorded_roots == nullptr || !recorded_roots->is_array()) {
        detail = "presentation action receipt request roots are invalid";
        return false;
    }
    for (std::size_t index = 0U; index < recorded_roots->size(); ++index) {
        if (recorded_roots->at(index) == nullptr || !recorded_roots->at(index)->is_string()) {
            detail = "presentation action receipt request root is invalid";
            return false;
        }
    }
    const std::string input_instance = receipt_string(recorded_input, "new_instance_id").empty()
        ? receipt_string(recorded_input, "selected_instance_id")
        : receipt_string(recorded_input, "new_instance_id");
    if (receipt_string(recorded_input, "action_id") != recorded_action ||
        receipt_string(recorded_input, "scope") != recorded_scope ||
        receipt_string(recorded_input, "request_id") != recorded_request ||
        receipt_string(recorded_input, "durable_operation_id") != recorded_operation ||
        receipt_string(recorded_input, "attempt_id") != recorded_attempt ||
        receipt_string(recorded_input, "installation_id") != recorded_installation ||
        input_instance != recorded_instance) {
        detail = "presentation action receipt request identity binding is invalid";
        return false;
    }
    auto decoded_result = recorded_result->string_value();
    if (!decoded_result) {
        detail = "presentation action receipt result could not be decoded";
        return false;
    }
    result = decoded_result.take_value();
    auto decoded_length = result_length->unsigned_integer_value();
    auto parsed_result = json::parse(result, limits);
    if (!decoded_length || decoded_length.value() != result.size() ||
        receipt_string(receipt, "result_digest") != digest(result) ||
        !parsed_result || !exact_keys(parsed_result.value(), {
            "schema", "command", "action_id", "request_id", "outcome", "operation",
            "effects", "diagnostics", "problems", "replacement_snapshot",
            "action_payload", "invalidation"})) {
        detail = "presentation action receipt result length, digest, or shape is invalid";
        return false;
    }
    const json::Value& semantic = parsed_result.value();
    const json::Value* operation = semantic.find("operation");
    const json::Value* effects = semantic.find("effects");
    const std::string outcome = receipt_string(semantic, "outcome");
    if (receipt_string(semantic, "schema") != "facman.semantic_action_result.v1" ||
        receipt_string(semantic, "command") != "presentation.action" ||
        receipt_string(semantic, "action_id") != recorded_action ||
        receipt_string(semantic, "request_id") != recorded_request ||
        !semantic_outcome(outcome) || operation == nullptr ||
        !exact_keys(*operation, {"request_id", "operation_id", "durable_operation_id",
            "attempt_id", "target_instance_id", "target_installation_id", "outcome"}) ||
        receipt_string(*operation, "request_id") != recorded_request ||
        !nullable_string_matches(*operation, "operation_id", recorded_operation) ||
        !nullable_string_matches(*operation, "durable_operation_id", recorded_operation) ||
        !nullable_string_matches(*operation, "attempt_id", recorded_attempt) ||
        !nullable_string_matches(*operation, "target_instance_id", recorded_instance) ||
        !nullable_string_matches(*operation, "target_installation_id", recorded_installation) ||
        receipt_string(*operation, "outcome") != outcome || effects == nullptr ||
        !effects->is_array() || effects->serialize() != effect_set->serialize() ||
        (state == "accepted_outcome_unknown" && outcome != "outcome_unknown")) {
        detail = "presentation action receipt semantic identity, outcome, or effect set is invalid";
        return false;
    }
    detail.clear();
    return true;
}

std::string action_receipt_json(
    const SemanticActionRequest& request,
    const std::string& fingerprint,
    const std::string& state,
    const std::string& result)
{
    auto semantic = json::parse(result);
    json::ObjectBuilder receipt;
    receipt.add_string("schema", "facman.presentation_action_receipt.v2");
    receipt.add_string("authority", "facman.application.presentation_action.v1");
    (void)receipt.add_unsigned_integer("contract_version", 2U);
    receipt.add_string("idempotency_key", request.idempotency_key);
    receipt.add_string("key_digest", digest(request.idempotency_key));
    receipt.add_string("request_fingerprint", fingerprint);
    receipt.add_string("action_id", request.action_id);
    receipt.add_string("scope", request.scope);
    receipt.add_string("request_id", request.request_id);
    receipt.add_string("operation_id", request.durable_operation_id);
    receipt.add_string("attempt_id", request.attempt_id);
    receipt.add_string("target_instance_id",
        request.new_instance_id.empty() ? request.selected_instance_id : request.new_instance_id);
    receipt.add_string("target_installation_id", request.installation_id);
    receipt.add_string("state", state);
    (void)receipt.add_unsigned_integer("result_length", result.size());
    receipt.add_string("result_digest", digest(result));
    if (semantic && semantic.value().is_object() && semantic.value().find("effects") != nullptr) {
        receipt.add_value("effect_set", *semantic.value().find("effects"));
    } else {
        json::ArrayBuilder effects;
        receipt.add_array("effect_set", effects);
    }
    receipt.add_string("request_json", action_request_json(request));
    receipt.add_string("result_json", result);
    return receipt.serialize() + "\n";
}

bool replace_action_receipt(
    const fs::path& path,
    const std::string& text,
    std::string& detail)
{
    static std::atomic<std::uint64_t> sequence {0U};
    const auto tick = std::chrono::steady_clock::now().time_since_epoch().count();
    const fs::path temporary = path.parent_path() /
        (path.filename().string() + ".next-" + std::to_string(tick) + "-" +
            std::to_string(++sequence));
    facman::platform::DurableOutputFile output;
    auto status = output.create_exclusive(temporary, kMaximumActionReceiptBytes);
    if (status.ok() && output.write_at(0U, text.data(), text.size()) != text.size()) {
        status = facman::platform::IoStatus::failure(
            "presentation_action_receipt_write_failed", "short receipt write");
    }
    if (status.ok()) status = output.flush_file_and_parent();
    if (status.ok()) status = facman::platform::replace_existing_durable(temporary, path);
    if (!status.ok()) {
        output.close_without_flush();
        std::error_code ignored;
        fs::remove(temporary, ignored);
        detail = status.code + ": " + status.detail;
        return false;
    }
    detail.clear();
    return true;
}

bool write_new_durable(
    const fs::path& path,
    const std::string& text,
    std::string& detail)
{
    std::error_code error;
    fs::create_directories(path.parent_path(), error);
    if (error) {
        detail = "could not create receipt parent: " + error.message();
        return false;
    }
    if (facman::base::path_crosses_link_or_reparse_point(path.parent_path(), detail)) {
        return false;
    }
    static std::atomic<std::uint64_t> sequence {0U};
    const auto tick = std::chrono::steady_clock::now().time_since_epoch().count();
    const fs::path temporary = path.parent_path() /
        (path.filename().string() + ".claim-" + std::to_string(tick) + "-" +
            std::to_string(++sequence));
    facman::platform::DurableOutputFile output;
    auto status = output.create_exclusive(temporary, kMaximumActionReceiptBytes);
    if (status.ok() && output.write_at(0U, text.data(), text.size()) != text.size()) {
        status = facman::platform::IoStatus::failure(
            "presentation_action_receipt_write_failed", "short receipt write");
    }
    if (status.ok()) status = output.flush_file_and_parent();
    if (status.ok()) status = facman::platform::commit_no_replace(temporary, path);
    if (!status.ok()) {
        output.close_without_flush();
        std::error_code ignored;
        fs::remove(temporary, ignored);
        detail = status.code + ": " + status.detail;
        return false;
    }
    detail.clear();
    return true;
}

bool ensure_workspace_admission_receipt(
    const fs::path& workspace,
    const std::string& workspace_id,
    std::string& detail)
{
    const fs::path path = workspace / ".facman" / "action-receipts-v2" /
        "workspace-admission.v1.json";
    const std::string root_digest = digest(facman::platform::path_to_utf8(
        fs::weakly_canonical(workspace)));
    std::error_code error;
    if (fs::exists(path, error)) {
        if (error) {
            detail = "workspace admission receipt could not be inspected: " + error.message();
            return false;
        }
        facman::platform::StableInputFile input;
        auto status = input.open_no_follow(path);
        if (!status.ok() || input.size() == 0U || input.size() > 65536U) {
            detail = status.ok() ? "workspace admission receipt size is invalid"
                                 : status.code + ": " + status.detail;
            return false;
        }
        std::string source(static_cast<std::size_t>(input.size()), '\0');
        if (input.read_at(0U, source.data(), source.size()) != source.size() ||
            !input.revalidate().ok()) {
            detail = "workspace admission receipt could not be read stably";
            return false;
        }
        auto record = json::parse(source);
        if (!record || !exact_keys(record.value(), {
                "schema", "authority", "workspace_id", "workspace_root_digest",
                "state", "effect_set"}) ||
            receipt_string(record.value(), "schema") !=
                "facman.presentation_workspace_admission.v1" ||
            receipt_string(record.value(), "authority") !=
                "facman.workspace.repository.ensure.v1" ||
            receipt_string(record.value(), "workspace_id") != workspace_id ||
            receipt_string(record.value(), "workspace_root_digest") != root_digest ||
            receipt_string(record.value(), "state") != "terminal" ||
            record.value().find("effect_set") == nullptr ||
            record.value().find("effect_set")->serialize() != "[\"workspace_initialization\"]") {
            detail = "workspace admission receipt is invalid or names different authority";
            return false;
        }
        detail.clear();
        return true;
    }
    json::ArrayBuilder effects;
    effects.add_string("workspace_initialization");
    json::ObjectBuilder record;
    record.add_string("schema", "facman.presentation_workspace_admission.v1");
    record.add_string("authority", "facman.workspace.repository.ensure.v1");
    record.add_string("workspace_id", workspace_id);
    record.add_string("workspace_root_digest", root_digest);
    record.add_string("state", "terminal");
    record.add_array("effect_set", effects);
    return write_new_durable(path, record.serialize() + "\n", detail);
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

bool contains_case_insensitive(const std::string& value, const std::string& search)
{
    if (search.empty()) return true;
    std::string lowered_value = value;
    std::string lowered_search = search;
    std::transform(lowered_value.begin(), lowered_value.end(), lowered_value.begin(),
        [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
    std::transform(lowered_search.begin(), lowered_search.end(), lowered_search.begin(),
        [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
    return lowered_value.find(lowered_search) != std::string::npos;
}

std::string json_string(const json::Value& value)
{
    if (!value.is_string()) return {};
    auto decoded = value.string_value();
    return decoded ? decoded.take_value() : std::string();
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
    const std::string& detail = {})
{
    json::ObjectBuilder problem;
    problem.add_string("code", code);
    problem.add_string("summary", summary);
    if (detail.empty()) problem.add_null("detail");
    else problem.add_string("detail", detail);
    problems.add_object(problem);
}

struct ActionInputField {
    std::string id;
    std::string label;
    std::string type;
    bool required = false;
    std::string default_value;
    std::vector<std::string> choices;
};

json::ObjectBuilder action_descriptor(
    const char* action_id,
    const char* command_id,
    const char* label,
    const char* role,
    const char* effect,
    bool available,
    const char* refusal_code = nullptr,
    const char* confirmation = "none",
    const char* input_contract = "none",
    const std::vector<ActionInputField>& input_fields = {})
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

std::string recovery_json(const std::filesystem::path& workspace)
{
    const transactions::Outcome outcome = transactions::inspect(workspace);
    if (std::holds_alternative<transactions::RecoveryResult>(outcome)) {
        return std::get<transactions::RecoveryResult>(outcome).json;
    }
    return transactions::to_json(
        std::get<transactions::Refusal>(outcome), "workspace.recovery.inspect");
}

std::string snapshot_revision(const std::string& snapshot)
{
    auto document = json::parse(snapshot);
    if (!document || !document.value().is_object()) return {};
    return decode_json_string_field(snapshot, "revision");
}

struct AdvertisedAction {
    bool found = false;
    bool available = false;
    std::string refusal_code;
    std::string refusal_reason;
};

AdvertisedAction advertised_action(const std::string& snapshot, const std::string& action_id)
{
    AdvertisedAction result;
    auto document = json::parse(snapshot);
    if (!document || !document.value().is_object()) return result;
    const json::Value* actions = document.value().find("available_semantic_actions");
    if (actions == nullptr || !actions->is_array()) return result;
    for (std::size_t index = 0; index < actions->size(); ++index) {
        const json::Value* action = actions->at(index);
        if (action == nullptr || !action->is_object()) continue;
        const json::Value* id = action->find("action_id");
        if (id == nullptr || json_string(*id) != action_id) continue;
        result.found = true;
        const json::Value* availability = action->find("availability");
        result.available = availability != nullptr && json_string(*availability) == "available";
        const json::Value* refusal = action->find("refusal");
        if (refusal != nullptr && refusal->is_object()) {
            const json::Value* code = refusal->find("code");
            const json::Value* reason = refusal->find("reason");
            if (code != nullptr) result.refusal_code = json_string(*code);
            if (reason != nullptr) result.refusal_reason = json_string(*reason);
        }
        return result;
    }
    return result;
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

ApplicationResult service_refusal(
    const char* action,
    const std::string& code,
    const std::string& message,
    const std::string& payload,
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::refused)
{
    return refused(payload.empty()
            ? safety_refusal(action, code, message, {}, true)
            : payload,
        code,
        message,
        kind);
}

std::string action_result_json(
    const SemanticActionRequest& request,
    const char* outcome,
    const std::string& replacement_snapshot,
    const std::string& action_payload,
    const std::string& problem_code,
    const std::string& problem_summary,
    bool invalidated,
    std::initializer_list<const char*> declared_effects = {})
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

ApplicationResult replayed_action_result(const std::string& source)
{
    auto document = json::parse(source);
    if (!document || !document.value().is_object()) {
        return service_refusal(
            "presentation.action", "idempotency_receipt_invalid",
            "The durable action receipt is not a valid semantic result", {},
            facman::core::OutcomeKind::recovery_required);
    }
    const std::string outcome = decode_json_string_field(source, "outcome");
    if (outcome == "completed" ||
        outcome == "cancellation_requested_but_completed") {
        ApplicationResult result;
        result.output = source;
        return result;
    }
    if (!semantic_outcome(outcome)) {
        return service_refusal(
            "presentation.action", "idempotency_receipt_invalid",
            "The durable action receipt contains an unsupported semantic outcome", {},
            facman::core::OutcomeKind::recovery_required);
    }
    std::string code = outcome == "outcome_unknown"
        ? "semantic_action_outcome_unknown"
        : outcome == "recovery_required"
            ? "semantic_action_recovery_required"
            : outcome == "cancelled_before_dispatch"
                ? "semantic_action_cancelled"
                : "semantic_action_refused";
    std::string message = outcome == "outcome_unknown"
        ? "The accepted semantic action outcome is unknown"
        : outcome == "recovery_required"
            ? "The semantic action requires recovery"
            : outcome == "cancelled_before_dispatch"
                ? "The semantic action was cancelled before dispatch"
                : "The semantic action was refused before effects";
    const json::Value* problems = document.value().find("problems");
    const json::Value* first = problems != nullptr && problems->is_array()
        ? problems->at(0U) : nullptr;
    if (first != nullptr && first->is_object()) {
        const json::Value* code_value = first->find("code");
        const json::Value* summary_value = first->find("summary");
        if (code_value != nullptr && code_value->is_string()) code = json_string(*code_value);
        if (summary_value != nullptr && summary_value->is_string()) message = json_string(*summary_value);
    }
    return service_refusal(
        "presentation.action", code, message, source,
        outcome == "outcome_unknown" ? facman::core::OutcomeKind::outcome_unknown
        : outcome == "recovery_required" ? facman::core::OutcomeKind::recovery_required
        : outcome == "cancelled_before_dispatch" ? facman::core::OutcomeKind::cancelled
        : facman::core::OutcomeKind::refused);
}

} // namespace

PresentationActionLedger::Lookup PresentationActionLedger::lookup(
    const std::filesystem::path& workspace,
    const SemanticActionRequest& request,
    const std::string& fingerprint,
    bool durable,
    std::string& result,
    std::string& detail) const
{
    if (request.idempotency_key.empty()) return Lookup::missing;
    if (durable) {
        const fs::path path = action_receipt_path(workspace, request.idempotency_key);
        facman::platform::PathIdentity identity;
        const auto inspected = facman::platform::inspect_path_no_follow(path, identity);
        if (!inspected.ok()) {
            detail = inspected.code + ": " + inspected.detail;
            return Lookup::invalid;
        }
        if (!identity.exists) {
            return Lookup::missing;
        }
        std::string recorded_fingerprint;
        std::string recorded_state;
        if (!read_action_receipt(
                path, request, recorded_fingerprint, recorded_state, result, detail)) {
            return Lookup::invalid;
        }
        return recorded_fingerprint == fingerprint ? Lookup::match : Lookup::conflict;
    }
    std::lock_guard<std::mutex> lock(mutex_);
    const auto found = entries_.find(request.idempotency_key);
    if (found == entries_.end()) return Lookup::missing;
    if (found->second.fingerprint != fingerprint) return Lookup::conflict;
    result = found->second.result;
    detail.clear();
    return Lookup::match;
}

bool PresentationActionLedger::claim(
    const std::filesystem::path& workspace,
    const SemanticActionRequest& request,
    const std::string& fingerprint,
    const std::string& pending_result,
    std::string& detail)
{
    if (request.idempotency_key.empty()) {
        detail = "effectful semantic action lacks an idempotency key";
        return false;
    }
    const fs::path path = action_receipt_path(workspace, request.idempotency_key);
    if (facman::base::path_crosses_link_or_reparse_point(path.parent_path(), detail)) {
        return false;
    }
    return write_new_durable(path,
        action_receipt_json(request, fingerprint, "accepted_outcome_unknown", pending_result),
        detail);
}

bool PresentationActionLedger::remember(
    const std::filesystem::path& workspace,
    const SemanticActionRequest& request,
    const std::string& fingerprint,
    const std::string& result,
    bool durable,
    std::string& detail)
{
    if (request.idempotency_key.empty()) return true;
    if (!durable) {
        std::lock_guard<std::mutex> lock(mutex_);
        entries_[request.idempotency_key] = {fingerprint, result};
        detail.clear();
        return true;
    }
    const fs::path path = action_receipt_path(workspace, request.idempotency_key);
    const std::string receipt = action_receipt_json(
        request, fingerprint, "terminal", result);
    facman::platform::PathIdentity identity;
    const auto inspected = facman::platform::inspect_path_no_follow(path, identity);
    if (!inspected.ok()) {
        detail = inspected.code + ": " + inspected.detail;
        return false;
    }
    if (!identity.exists) {
        detail = "accepted presentation action receipt is missing";
        return false;
    }
    std::string accepted_fingerprint;
    std::string accepted_state;
    std::string accepted_result;
    if (!read_action_receipt(
            path, request, accepted_fingerprint, accepted_state, accepted_result, detail) ||
        accepted_fingerprint != fingerprint ||
        accepted_state != "accepted_outcome_unknown") {
        if (detail.empty()) detail = "accepted presentation action receipt cannot transition";
        return false;
    }
    return replace_action_receipt(path, receipt, detail);
}

PresentationService::PresentationService(
    ApplicationContext& context,
    LastRunProvider& last_run_provider,
    PresentationActionLedger& action_ledger,
    PresentationLaunchExecutor* launch_executor)
    : context_(context),
      last_run_provider_(last_run_provider),
      action_ledger_(action_ledger),
      launch_executor_(launch_executor)
{
}

ApplicationResult PresentationService::query(const PresentationQueryRequest& request) const
{
    if (request.scope != "launch_deck" && request.scope != "instances" &&
        request.scope != "installations" && request.scope != "content" &&
        request.scope != "saves" && request.scope != "activity_recovery" &&
        request.scope != "settings_support") {
        return service_refusal(
            "presentation.query", "presentation_scope_invalid",
            "Presentation scope is not supported", {},
            facman::core::OutcomeKind::invalid_argument);
    }
    auto installs_result = context_.installs().list();
    auto instances_result = context_.instances().list();
    if (!installs_result || !instances_result) {
        return service_refusal(
            "presentation.query", "presentation_repository_unavailable",
            "Presentation repositories could not be read", {});
    }
    auto installs = installs_result.take_value();
    auto instances = instances_result.take_value();
    const auto workspace_record = context_.workspace_repository().load();
    std::sort(installs.begin(), installs.end(), [](const auto& left, const auto& right) {
        return left.id.str() < right.id.str();
    });
    std::sort(instances.begin(), instances.end(), [](const auto& left, const auto& right) {
        return left.id.str() < right.id.str();
    });

    json::ArrayBuilder install_items;
    std::vector<std::string> install_choices;
    for (const auto& install : installs) {
        install_choices.push_back(install.id.str());
        discovery::InstallRef observed;
        observed.install_id = install.id.str();
        observed.provider_id = install.provider_id;
        observed.root = install.root;
        observed.executable = install.executable;
        observed.version = install.version;
        observed.ownership = install.ownership;
        observed.source = install.source;
        observed.source_ref = install.source_ref;
        observed.platform = install.platform;
        observed.distribution_origin = install.distribution_origin;
        observed.platform_integration = install.platform_integration;
        observed.strict_isolation_eligibility = install.strict_isolation_eligibility;
        observed.external_state_domains = install.external_state_domains;
        observed.setup_state_ref = install.setup_state_ref;
        observed.lifecycle_status = install.lifecycle_status;
        observed.last_verification_identity = install.last_verification_identity;
        observed.state_revision = install.state_revision;
        observed.verification_status = install.verification_status;
        if (request.scope == "installations") {
            discovery::classify_install_isolation(observed);
            discovery::classify_install_layout(observed);
        }
        const std::string searchable = install.id.str() + " " + install.version + " " +
            install.ownership + " " + facman::platform::path_to_utf8(install.root) + " " +
            observed.installation_layout;
        if (!contains_case_insensitive(searchable, request.search)) continue;
        json::ObjectBuilder item;
        item.add_string("installation_id", install.id.str());
        item.add_string("provider_id", install.provider_id);
        item.add_string("root", facman::platform::path_to_utf8(install.root));
        item.add_string("executable", facman::platform::path_to_utf8(install.executable));
        item.add_string("version", install.version);
        item.add_string("ownership", install.ownership);
        item.add_string("source", install.source);
        item.add_string("source_ref", install.source_ref);
        item.add_string("platform", install.platform);
        item.add_string("distribution_origin", observed.distribution_origin);
        item.add_string("platform_integration", observed.platform_integration);
        item.add_string("installation_layout", observed.installation_layout);
        item.add_string("data_routing", observed.data_routing);
        item.add_string("program_data_separation", observed.program_data_separation);
        item.add_string("uninstall_integration", observed.uninstall_integration);
        item.add_string("side_by_side_safety", observed.side_by_side_safety);
        json::ArrayBuilder local_data_domains;
        for (const auto& domain : observed.local_data_domains) {
            local_data_domains.add_string(domain);
        }
        item.add_array("local_data_domains", local_data_domains);
        item.add_string("strict_isolation_eligibility", observed.strict_isolation_eligibility);
        json::ArrayBuilder external_state_domains;
        for (const auto& domain : observed.external_state_domains) {
            external_state_domains.add_string(domain);
        }
        item.add_array("external_state_domains", external_state_domains);
        item.add_string("lifecycle_status", install.lifecycle_status);
        item.add_string("verification_status", install.verification_status);
        item.add_string("state_revision", install.state_revision);
        install_items.add_object(item);
    }
    json::ArrayBuilder instance_items;
    std::vector<std::string> instance_choices;
    bool selected_exists = false;
    std::string selected_profile;
    std::string selected_name;
    std::string selected_installation;
    std::string selected_version;
    std::string selected_template;
    for (const auto& instance : instances) {
        instance_choices.push_back(instance.id.str());
        const bool selected = instance.id.str() == request.selected_instance_id;
        selected_exists = selected_exists || selected;
        if (selected) {
            selected_profile = instance.profile;
            selected_name = instance.display_name;
            selected_installation = instance.install_ref.str();
            selected_version = instance.factorio_version;
            selected_template = instance.template_id;
        }
        if (!contains_case_insensitive(instance.id.str() + " " + instance.display_name, request.search)) continue;
        json::ObjectBuilder item;
        item.add_string("instance_id", instance.id.str());
        item.add_string("display_name", instance.display_name);
        item.add_string("installation_id", instance.install_ref.str());
        item.add_string("factorio_version", instance.factorio_version);
        item.add_string("profile", instance.profile);
        item.add_string("template_id", instance.template_id);
        item.add_bool("selected", selected);
        instance_items.add_object(item);
    }

    json::ArrayBuilder content_items;
    std::vector<std::string> profile_choices;
    std::vector<std::string> mod_identity_choices;
    std::vector<std::string> mod_name_choices;
    std::vector<std::string> modset_transaction_choices;
    bool selected_modset_locked = false;
    std::string content_problem;
    auto profile_report = profiles::profiles_list(context_.workspace());
    if (!profile_report) {
        content_problem = profile_report.error().code + ": " + profile_report.error().message;
    } else {
        auto profile_document = json::parse(profile_report.value());
        const json::Value* profile_values = profile_document && profile_document.value().is_object()
            ? profile_document.value().find("profiles") : nullptr;
        if (profile_values == nullptr || !profile_values->is_array()) {
            content_problem = "profiles_list_invalid: profile inventory could not be decoded";
        } else {
            for (std::size_t index = 0; index < profile_values->size(); ++index) {
                const json::Value* value = profile_values->at(index);
                if (value == nullptr) continue;
                const std::string profile_id = json_string(*value);
                if (profile_id.empty()) continue;
                profile_choices.push_back(profile_id);
                if (!contains_case_insensitive(profile_id + " profile", request.search)) continue;
                json::ObjectBuilder item;
                item.add_string("id", "profile:" + profile_id);
                item.add_string("name", profile_id);
                item.add_string("kind", "launch_profile");
                item.add_string("status", profile_id == selected_profile ? "selected" : "available");
                item.add_bool("selected", profile_id == selected_profile);
                content_items.add_object(item);
            }
        }
    }
    auto local_mods = facman::factorio::mods::local_inventory(context_.workspace());
    if (!local_mods) {
        if (!content_problem.empty()) content_problem += "; ";
        content_problem += local_mods.error().code + ": " + local_mods.error().message;
    } else {
        for (const auto& mod : local_mods.value()) {
            const std::string identity = mod.name + "@" + mod.version;
            mod_identity_choices.push_back(identity);
            if (!mod.virtual_package && mod.valid &&
                std::find(mod_name_choices.begin(), mod_name_choices.end(), mod.name) ==
                    mod_name_choices.end()) {
                mod_name_choices.push_back(mod.name);
            }
            if (!contains_case_insensitive(
                    identity + " " + mod.title + " " + mod.validation_status,
                    request.search)) {
                continue;
            }
            json::ObjectBuilder item;
            item.add_string("id", "mod:" + identity);
            item.add_string("name", mod.title.empty() ? identity : mod.title);
            item.add_string("kind", mod.virtual_package ? "builtin_mod" : "local_mod");
            item.add_string("status", mod.validation_status);
            item.add_string("version", mod.version);
            item.add_string("factorio_version", mod.factorio_version);
            item.add_string("identity", identity);
            item.add_string("sha256", mod.sha256);
            item.add_string("source", mod.source);
            item.add_bool("enabled", mod.enabled);
            item.add_bool("selected", mod.enabled);
            item.add_bool("portal_access", false);
            content_items.add_object(item);
        }
    }
    if (!request.selected_instance_id.empty()) {
        auto instance_id = facman::core::InstanceId::parse(request.selected_instance_id);
        if (instance_id) {
            auto lock = context_.modsets().load_lock(instance_id.value());
            if (lock && contains_case_insensitive(request.selected_instance_id + " modset", request.search)) {
                selected_modset_locked = true;
                json::ObjectBuilder item;
                item.add_string("id", "modset:" + request.selected_instance_id);
                item.add_string("name", "Instance modset");
                item.add_string("kind", "modset_lock");
                item.add_string("status", "locked");
                item.add_bool("selected", false);
                content_items.add_object(item);
            }
            selected_modset_locked = selected_modset_locked || static_cast<bool>(lock);
            const auto selected = std::find_if(
                instances.begin(), instances.end(), [&](const auto& value) {
                    return value.id.str() == request.selected_instance_id;
                });
            if (selected != instances.end()) {
                const fs::path history_root =
                    selected->root / "mods" / ".facman-modset-history";
                std::error_code history_error;
                for (fs::directory_iterator entry(history_root, history_error), end;
                     entry != end && !history_error &&
                         modset_transaction_choices.size() < 128U;
                     entry.increment(history_error)) {
                    if (!entry->is_directory(history_error) || history_error) continue;
                    const std::string transaction = entry->path().filename().string();
                    if (lower_hex_digest(transaction)) {
                        modset_transaction_choices.push_back(transaction);
                    }
                }
                std::sort(
                    modset_transaction_choices.begin(),
                    modset_transaction_choices.end());
            }
        }
    }

    json::ArrayBuilder save_items;
    std::vector<std::string> save_choices;
    std::string saves_problem;
    if (request.scope == "saves") {
        if (request.selected_instance_id.empty()) {
            saves_problem = "Select an instance to inspect saves";
        } else {
            ApplicationRequest domain;
            domain.command = CommandId::saves_index;
            SaveIndexRequest save_request;
            save_request.instance_id = request.selected_instance_id;
            domain.payload = std::move(save_request);
            const ApplicationResult indexed = handlers::dispatch_save_index(context_, domain);
            auto save_document = json::parse(result_string(indexed));
            const json::Value* values = save_document && save_document.value().is_object()
                ? save_document.value().find("saves") : nullptr;
            if (indexed.status != ULK_STATUS_OK || values == nullptr || !values->is_array()) {
                saves_problem = indexed.error_code.empty()
                    ? "save_index_invalid: save inventory could not be decoded"
                    : indexed.error_code + ": " + indexed.error_message;
            } else {
                for (std::size_t index = 0U; index < values->size(); ++index) {
                    const json::Value* value = values->at(index);
                    if (value == nullptr || !value->is_object()) continue;
                    const std::string filename = receipt_string(*value, "filename");
                    if (filename.empty()) continue;
                    save_choices.push_back(filename);
                    const std::string sha256 = receipt_string(*value, "sha256");
                    const std::string backup = receipt_string(*value, "backup_sidecar_status");
                    const json::Value* association = value->find("association");
                    const std::string association_status =
                        association != nullptr && association->is_object()
                        ? receipt_string(*association, "status") : "absent";
                    if (!contains_case_insensitive(
                            filename + " " + association_status + " " + sha256,
                            request.search)) {
                        continue;
                    }
                    const json::Value* recognized = value->find("factorio_save_recognized");
                    bool recognized_value = false;
                    if (recognized != nullptr) {
                        const auto parsed = recognized->bool_value();
                        recognized_value = parsed && parsed.value();
                    }
                    const json::Value* size = value->find("size");
                    std::uint64_t size_value = 0U;
                    if (size != nullptr) {
                        const auto parsed = size->unsigned_integer_value();
                        if (parsed) size_value = parsed.value();
                    }
                    json::ObjectBuilder item;
                    item.add_string("save_id", filename);
                    item.add_string("name", filename);
                    item.add_string("kind", "factorio_save");
                    item.add_string("status", recognized_value
                        ? "recognized" : "unverified");
                    item.add_string("association_status", association_status);
                    item.add_string("backup_status", backup);
                    item.add_string("sha256", sha256);
                    item.add_unsigned_integer("size", size_value);
                    item.add_bool("selected", false);
                    item.add_bool("deep_metadata_inspected", false);
                    save_items.add_object(item);
                }
            }
        }
    }

    json::ArrayBuilder setting_items;
    const auto& configured = context_.configuration().preferences();
    const auto add_setting = [&](const char* id, const char* label, const std::string& value) {
        if (!contains_case_insensitive(std::string(label) + " " + value, request.search)) return;
        json::ObjectBuilder item;
        item.add_string("id", id);
        item.add_string("name", label);
        item.add_string("kind", "preference");
        item.add_string("value", value.empty() ? "default" : value);
        item.add_string("status", context_.configuration().preferences_present() ? "configured" : "default");
        item.add_bool("selected", false);
        setting_items.add_object(item);
    };
    add_setting("preferred_workspace", "Preferred workspace", configured.preferred_workspace);
    add_setting("preferred_transport", "Preferred transport", configured.preferred_transport);
    add_setting("default_instance_template", "Default instance template", configured.default_instance_template);
    add_setting("default_launch_profile", "Default launch profile", configured.default_launch_profile);
    add_setting("display_color_policy", "Display colour policy", configured.display_color_policy);

    std::string readiness;
    if (!request.selected_instance_id.empty()) {
        lifecycle::ProjectionRequest projection;
        projection.instance_id = request.selected_instance_id;
        projection.launch_intent = "menu";
        auto projected = lifecycle::instance_readiness(context_.workspace(), projection);
        if (projected) readiness = projected.take_value();
    }
    const std::string recovery = recovery_json(context_.workspace());
    const LastRunProjection last_run = request.selected_instance_id.empty()
        ? LastRunProjection {LastRunAuthorityState::no_record, last_run_provider_.provider_id(), {}, {}}
        : last_run_provider_.last_run("facman.instance:" + request.selected_instance_id);
    const std::string last_run_json = last_run_projection_json(last_run);

    // The launch executor may expose an in-memory view of a currently running
    // fixture session. Terminal truth is deliberately excluded here: ULK Last
    // Run remains the only authority for completed, cancelled, unknown, and
    // recovery-required sessions.
    json::ArrayBuilder active_operations;
    bool stop_available = false;
    if (launch_executor_ != nullptr) {
        for (const auto& operation : launch_executor_->inspect_sessions(request)) {
            if (!operation.fixture_only || operation.operation_id.empty() ||
                operation.instance_id.empty() || operation.state.empty() ||
                terminal_session_state(operation.state) ||
                (!request.selected_instance_id.empty() &&
                    operation.instance_id != request.selected_instance_id)) {
                continue;
            }
            json::ObjectBuilder item;
            item.add_string("schema", "facman.presentation_operation.v1");
            item.add_string("kind", "launch_session");
            item.add_string("session_id", operation.session_id);
            item.add_string("operation_id", operation.operation_id);
            item.add_string("attempt_id", operation.attempt_id);
            item.add_string("target_instance_id", operation.instance_id);
            item.add_string("state", operation.state);
            item.add_string("status", operation.state);
            item.add_bool("stop_available", operation.stop_available);
            item.add_string("authority_scope", "fixture_only");
            item.add_null("terminal_outcome");
            active_operations.add_object(item);
            stop_available = stop_available || operation.stop_available;
        }
    }

    json::ArrayBuilder problems;
    if (installs.empty()) add_problem(problems, "no_installations", "No installation is registered");
    if (request.scope == "launch_deck" && request.selected_instance_id.empty()) {
        add_problem(problems, "no_instance_selected", "Select an instance to compute readiness");
    } else if (!request.selected_instance_id.empty() && !selected_exists) {
        add_problem(problems, "selected_instance_missing", "The selected instance is not registered");
    } else if (!request.selected_instance_id.empty() && readiness.empty()) {
        add_problem(problems, "readiness_unavailable", "Readiness could not be computed");
    }
    if (last_run.state == LastRunAuthorityState::provider_unavailable) {
        add_problem(problems, "last_run_authority_unavailable", "Authoritative Last Run is unavailable");
    } else if (last_run.state == LastRunAuthorityState::record_corrupt_or_incompatible) {
        add_problem(problems, "last_run_record_invalid", "The authoritative Last Run record is invalid");
    } else if (last_run.state == LastRunAuthorityState::outcome_unknown) {
        add_problem(problems, "outcome_unknown", "The last operation outcome is unknown");
    } else if (last_run.state == LastRunAuthorityState::recovery_required) {
        add_problem(problems, "recovery_required", "The last operation requires recovery");
    }
    if (request.scope == "content" && !content_problem.empty()) {
        add_problem(problems, "content_projection_unavailable", "Content inventory is unavailable", content_problem);
    }
    if (request.scope == "saves" && !saves_problem.empty()) {
        add_problem(problems, request.selected_instance_id.empty()
            ? "no_instance_selected" : "save_inventory_unavailable",
            saves_problem);
    }
    if (request.scope == "settings_support" &&
        !context_.configuration().configuration_problem().empty()) {
        add_problem(problems, "preferences_unavailable", "Preferences could not be read",
            context_.configuration().configuration_problem());
    }

    json::ArrayBuilder actions;
    const std::string default_instance = request.selected_instance_id.empty()
        ? (instance_choices.empty() ? std::string() : instance_choices.front())
        : request.selected_instance_id;
    const std::string default_profile = selected_profile.empty()
        ? (profile_choices.empty() ? std::string() : profile_choices.front())
        : selected_profile;
    const std::vector<ActionInputField> instance_input = {{
        "selected_instance_id", "Instance", "enum", true,
        default_instance, instance_choices}};
    const std::vector<ActionInputField> profile_create_input = {{
        "profile_id", "New profile ID", "identifier", true,
        "new-profile", {}}};
    const std::vector<ActionInputField> profile_select_input = {
        {"selected_instance_id", "Instance", "enum", true,
            default_instance, instance_choices},
        {"profile_id", "Profile", "enum", true,
            default_profile, profile_choices},
    };
    const std::vector<ActionInputField> mod_inspect_input = {{
        "mod_identity", "Local mod", "enum", true,
        mod_identity_choices.empty() ? std::string() : mod_identity_choices.front(),
        mod_identity_choices}};
    const std::vector<ActionInputField> modset_plan_input = {
        {"selected_instance_id", "Instance", "enum", true,
            default_instance, instance_choices},
        {"mod_identity", "Local mod to enable", "enum", true,
            mod_name_choices.empty() ? std::string() : mod_name_choices.front(),
            mod_name_choices},
    };
    const std::vector<ActionInputField> modset_rollback_input = {
        {"selected_instance_id", "Instance", "enum", true,
            default_instance, instance_choices},
        {"transaction_id", "Activation plan ID", "enum", true,
            modset_transaction_choices.empty() ? std::string() :
                modset_transaction_choices.back(),
            modset_transaction_choices},
    };
    const std::vector<ActionInputField> save_input = {
        {"selected_instance_id", "Instance", "enum", true,
            default_instance, instance_choices},
        {"save", "Save", "enum", true,
            save_choices.empty() ? std::string() : save_choices.front(), save_choices},
    };
    const std::vector<ActionInputField> save_backup_input = {
        {"selected_instance_id", "Instance", "enum", true,
            default_instance, instance_choices},
        {"save", "Save", "enum", true,
            save_choices.empty() ? std::string() : save_choices.front(), save_choices},
        {"output_path", "Optional backup destination", "path", false, {}, {}},
    };
    const std::vector<ActionInputField> support_export_input = {
        {"selected_instance_id", "Instance", "enum", true,
            default_instance, instance_choices},
        {"output_path", "Support bundle destination", "path", true, {}, {}},
    };
    const std::vector<ActionInputField> optional_roots_input = {{
        "roots", "Search roots", "path_array", false, {}, {}}};
    const std::vector<ActionInputField> installation_register_input = {
        {"installation_id", "Installation ID", "identifier", true, "factorio", {}},
        {"installation_path", "Factorio installation path", "path", true, {}, {}},
    };
    const std::vector<ActionInputField> instance_create_input = {
        {"installation_id", "Installation", "enum", true,
            install_choices.empty() ? std::string() : install_choices.front(), install_choices},
        {"new_instance_id", "New instance ID", "identifier", true,
            "new-instance", {}},
        {"display_name", "Display name", "string", true,
            "New instance", {}},
    };
    const std::vector<ActionInputField> recovery_input = {{
        "transaction_id", "Recovery transaction", "identifier", true, {}, {}}};
    actions.add_object(action_descriptor(
        "presentation.refresh", "presentation.query", "Refresh", "secondary", "read_only", true));
    if (request.scope == "installations") {
        actions.add_object(action_descriptor(
            "installations.scan", "presentation.action", "Scan for installations", "manage", "read_only", true,
            nullptr, "none", "facman.semantic_action_input.v1", optional_roots_input));
        actions.add_object(action_descriptor(
            "installation.register_read_only", "presentation.action",
            "Register read-only installation", "manage", "workspace_write", true,
            nullptr, "explicit", "facman.semantic_action_input.v1", installation_register_input));
    }
    if (request.scope == "launch_deck" || request.scope == "instances") {
        if (request.scope == "launch_deck") {
            actions.add_object(action_descriptor(
                "doctor.run", "doctor.run", "Run Doctor", "diagnostic", "read_only", true,
                nullptr, "none", "facman.semantic_action_input.v1", optional_roots_input));
        }
        if (request.scope == "instances") {
            actions.add_object(action_descriptor(
                "instance.create_isolated", "presentation.action", "Create isolated instance",
                "manage", "workspace_write", !installs.empty(),
                installs.empty() ? "no_installations" : nullptr,
                "explicit", "facman.semantic_action_input.v1", instance_create_input));
            actions.add_object(action_descriptor(
                "instance.select_context", "presentation.action", "Select instance",
                "secondary", "read_only", !instances.empty(),
                instances.empty() ? "no_instances" : nullptr,
                "none", "facman.semantic_action_input.v1", instance_input));
        }
        actions.add_object(action_descriptor(
            "configuration.explain_effective", "presentation.action",
            "Explain effective configuration", "diagnostic", "read_only",
            selected_exists && !profile_choices.empty(),
            !selected_exists ? "no_instance_selected" :
                (profile_choices.empty() ? "no_profiles" : nullptr),
            "none", "facman.semantic_action_input.v1", profile_select_input));
        actions.add_object(action_descriptor(
            "launch.menu_plan", "presentation.action", "Preview menu launch",
            "secondary", "read_only", selected_exists,
            selected_exists ? nullptr : "no_instance_selected",
            "none", "facman.semantic_action_input.v1", instance_input));
        actions.add_object(action_descriptor(
            "readiness.refresh", "presentation.action", "Refresh readiness",
            "secondary", "read_only", selected_exists,
            selected_exists ? nullptr : "no_instance_selected",
            "none", "facman.semantic_action_input.v1", instance_input));
        const bool launch_available = launch_executor_ != nullptr &&
            launch_executor_->available(request);
        actions.add_object(action_descriptor(
            "launch.play", "run.execute",
            last_run.state == LastRunAuthorityState::authoritative_record_available
                ? "Relaunch" : "Play",
            "primary", "process_execution",
            launch_available,
            launch_available ? nullptr : "execution_authority_unavailable",
            "explicit", "facman.semantic_action_input.v1", instance_input));
        if (stop_available) {
            actions.add_object(action_descriptor(
                "sessions.stop", "presentation.action", "Stop session",
                "session", "process_control", true, nullptr,
                "explicit", "facman.semantic_action_input.v1", instance_input));
        }
    }
    if (request.scope == "instances" || request.scope == "content") {
        actions.add_object(action_descriptor(
            "profile.create", "presentation.action", "Create launch profile",
            "manage", "workspace_write", true, nullptr,
            "explicit", "facman.semantic_action_input.v1", profile_create_input));
        actions.add_object(action_descriptor(
            "profile.select", "presentation.action", "Select launch profile",
            "manage", "workspace_write", selected_exists && !profile_choices.empty(),
            !selected_exists ? "no_instance_selected" :
                (profile_choices.empty() ? "no_profiles" : nullptr),
            "explicit", "facman.semantic_action_input.v1", profile_select_input));
    }
    if (request.scope == "content") {
        actions.add_object(action_descriptor(
            "mods.inspect", "presentation.action", "Inspect local mod",
            "diagnostic", "read_only", !mod_identity_choices.empty(),
            mod_identity_choices.empty() ? "no_local_mods" : nullptr,
            "none", "facman.semantic_action_input.v1", mod_inspect_input));
        actions.add_object(action_descriptor(
            "modsets.plan", "presentation.action", "Plan instance modset",
            "diagnostic", "read_only", selected_exists && !mod_name_choices.empty(),
            !selected_exists ? "no_instance_selected" :
                (mod_name_choices.empty() ? "no_local_mods" : nullptr),
            "none", "facman.semantic_action_input.v1", modset_plan_input));
        actions.add_object(action_descriptor(
            "modsets.apply", "presentation.action", "Apply instance modset",
            "manage", "workspace_write", selected_exists && !mod_name_choices.empty(),
            !selected_exists ? "no_instance_selected" :
                (mod_name_choices.empty() ? "no_local_mods" : nullptr),
            "explicit", "facman.semantic_action_input.v1", modset_plan_input));
        actions.add_object(action_descriptor(
            "modsets.verify", "presentation.action", "Verify instance modset",
            "diagnostic", "read_only", selected_exists && selected_modset_locked,
            !selected_exists ? "no_instance_selected" :
                (!selected_modset_locked ? "no_modset_lock" : nullptr),
            "none", "facman.semantic_action_input.v1", instance_input));
        actions.add_object(action_descriptor(
            "modsets.rollback", "presentation.action", "Roll back instance modset",
            "manage", "workspace_write",
            selected_exists && !modset_transaction_choices.empty(),
            !selected_exists ? "no_instance_selected" :
                (modset_transaction_choices.empty() ? "no_modset_history" : nullptr),
            "explicit", "facman.semantic_action_input.v1", modset_rollback_input));
    }
    if (request.scope == "saves") {
        const bool saves_available = selected_exists && !save_choices.empty();
        const char* saves_refusal = !selected_exists
            ? "no_instance_selected" : (save_choices.empty() ? "no_saves" : nullptr);
        actions.add_object(action_descriptor(
            "saves.inspect", "presentation.action", "Inspect local save",
            "diagnostic", "read_only", saves_available, saves_refusal,
            "none", "facman.semantic_action_input.v1", save_input));
        actions.add_object(action_descriptor(
            "saves.associate", "presentation.action", "Associate local save",
            "manage", "workspace_write", saves_available, saves_refusal,
            "explicit", "facman.semantic_action_input.v1", save_input));
        actions.add_object(action_descriptor(
            "saves.backup", "presentation.action", "Back up local save",
            "manage", "workspace_write", saves_available, saves_refusal,
            "explicit", "facman.semantic_action_input.v1", save_backup_input));
    }
    if (request.scope == "settings_support") {
        actions.add_object(action_descriptor(
            "doctor.run", "presentation.action", "Run Doctor",
            "diagnostic", "read_only", true, nullptr, "none",
            "facman.semantic_action_input.v1", optional_roots_input));
        actions.add_object(action_descriptor(
            "support.export_redacted_bundle", "presentation.action",
            "Export redacted support bundle", "diagnostic", "workspace_write",
            selected_exists, selected_exists ? nullptr : "no_instance_selected",
            "explicit", "facman.semantic_action_input.v1", support_export_input));
        if (!workspace_record) {
            actions.add_object(action_descriptor(
                "workspace.initialize", "presentation.action", "Initialize workspace",
                "manage", "workspace_write", true, nullptr, "explicit", "none"));
        }
    }
    if (request.scope == "activity_recovery" &&
        transactions::incomplete_count(context_.workspace()) != 0U) {
        actions.add_object(action_descriptor(
            "recovery.inspect", "workspace.recovery.inspect", "Inspect recovery", "recovery", "read_only", true));
        actions.add_object(action_descriptor(
            "recovery.apply_supported", "presentation.action", "Apply supported recovery",
            "recovery", "workspace_write", true, nullptr, "explicit",
            "facman.semantic_action_input.v1", recovery_input));
    }
    if (request.scope == "activity_recovery" && stop_available) {
        actions.add_object(action_descriptor(
            "sessions.stop", "presentation.action", "Stop session",
            "session", "process_control", true, nullptr,
            "explicit", "facman.semantic_action_input.v1", instance_input));
    }

    json::ObjectBuilder page;
    page.add_string("scope", request.scope);
    page.add_string("search", request.search);
    if (request.scope == "installations") {
        page.add_string("summary", std::to_string(installs.size()) + " registered installations");
        page.add_array("items", install_items);
    } else if (request.scope == "instances") {
        page.add_string("summary", std::to_string(instances.size()) + " registered instances");
        page.add_array("items", instance_items);
    } else if (request.scope == "content") {
        page.add_string("summary", "Launch profiles and instance-local content");
        page.add_array("items", content_items);
    } else if (request.scope == "saves") {
        page.add_string("summary", request.selected_instance_id.empty()
            ? "Select an instance to inspect saves"
            : "Save inventory for " + request.selected_instance_id);
        page.add_array("items", save_items);
    } else if (request.scope == "activity_recovery") {
        page.add_string("summary", "Operations and recovery");
        json::ArrayBuilder empty;
        page.add_array("items", empty);
    } else if (request.scope == "settings_support") {
        page.add_string("summary", "Preferences, support, and exact runtime identity");
        page.add_array("items", setting_items);
    } else {
        page.add_string("summary", request.selected_instance_id.empty()
            ? "Select an instance" : "Launch Deck for " + request.selected_instance_id);
        page.add_array("items", instance_items);
    }

    json::ObjectBuilder workspace_health;
    workspace_health.add_string("status", workspace_record ? "available" : "uninitialized");
    workspace_health.add_string("workspace", facman::platform::path_to_utf8(context_.workspace()));
    workspace_health.add_bool("initialized", static_cast<bool>(workspace_record));
    workspace_health.add_bool("workspace_mutated", false);
    if (workspace_record) {
        workspace_health.add_string("workspace_id", workspace_record.value().id.str());
        workspace_health.add_unsigned_integer("layout_version", workspace_record.value().layout_version);
    } else {
        workspace_health.add_null("workspace_id");
        workspace_health.add_unsigned_integer("layout_version", 0U);
    }
    workspace_health.add_unsigned_integer(
        "incomplete_transactions", transactions::incomplete_count(context_.workspace()));

    json::ObjectBuilder selection;
    if (request.selected_instance_id.empty()) selection.add_null("instance_id");
    else selection.add_string("instance_id", request.selected_instance_id);
    if (!selected_exists) {
        selection.add_null("display_name");
        selection.add_null("installation_id");
        selection.add_null("factorio_version");
        selection.add_null("profile");
        selection.add_null("template_id");
    } else {
        selection.add_string("display_name", selected_name);
        selection.add_string("installation_id", selected_installation);
        selection.add_string("factorio_version", selected_version);
        selection.add_string("profile", selected_profile);
        selection.add_string("template_id", selected_template);
    }
    selection.add_bool("frontend_local", true);
    selection.add_bool("workspace_mutated", false);

    json::ObjectBuilder backend_identity;
    backend_identity.add_string("factorio_launcher_revision", facman::build_identity::factorio_launcher_revision);
    backend_identity.add_string("universal_launcher_revision", facman::build_identity::universal_launcher_revision);
    backend_identity.add_string("universal_setup_revision", facman::build_identity::universal_setup_revision);
    backend_identity.add_string("command_catalog_sha256", FACMAN_COMMAND_CATALOG_SHA256);
    backend_identity.add_string("contract_set_sha256", FACMAN_CONTRACT_SET_SHA256);
    backend_identity.add_string("last_run_provider", last_run_provider_.provider_id());

    json::ObjectBuilder revision_input;
    revision_input.add_object("workspace_health", workspace_health);
    revision_input.add_object("selected_context", selection);
    revision_input.add_object("page", page);
    if (readiness.empty()) revision_input.add_null("readiness");
    else add_json(revision_input, "readiness", readiness);
    add_json(revision_input, "recovery", recovery);
    add_json(revision_input, "last_run", last_run_json);
    revision_input.add_array("active_operations", active_operations);
    revision_input.add_object("backend_identity", backend_identity);
    const std::string revision = digest(revision_input.serialize());

    json::ObjectBuilder freshness;
    freshness.add_string("state", "current");
    freshness.add_string("refresh_kind", request.scope == "installations"
        ? "repository_and_registered_install_observation"
        : "repository_read_no_scan");
    freshness.add_bool("known_revision_matches", !request.known_revision.empty() && request.known_revision == revision);

    json::ObjectBuilder dependencies;
    dependencies.add_string("authoritative_digest", revision);
    dependencies.add_string("workspace_store", "json_toml_v1");
    dependencies.add_string("readiness_owner", "facman.factorio.instance_readiness");
    dependencies.add_string("recovery_owner", "facman.workspace.transactions");
    dependencies.add_string("last_run_owner", last_run_provider_.provider_id());

    json::ObjectBuilder package_identity;
    package_identity.add_string("classification", "current_runtime_identity");
    package_identity.add_string("support", "engineering_only_foundation");

    json::ObjectBuilder output;
    output.add_string("schema", "facman.presentation_snapshot.v1");
    output.add_string("command", "presentation.query");
    output.add_string("snapshot_id", "snapshot-" + revision.substr(0U, 32U));
    output.add_string("revision", revision);
    output.add_object("freshness", freshness);
    output.add_object("dependency_identities", dependencies);
    output.add_object("workspace_health", workspace_health);
    output.add_object("selected_context", selection);
    output.add_object("page", page);
    if (readiness.empty()) output.add_null("readiness");
    else add_json(output, "readiness", readiness);
    output.add_array("specific_blockers", problems);
    output.add_array("available_semantic_actions", actions);
    output.add_array("active_operations", active_operations);
    add_json(output, "last_run", last_run_json);
    add_json(output, "recovery", recovery);
    output.add_string("support_classification", "engineering_only_foundation");
    output.add_object("backend_provider_identity", backend_identity);
    output.add_object("package_identity", package_identity);

    ApplicationResult result;
    result.output = output.serialize();
    return result;
}

ApplicationResult PresentationService::action(
    const SemanticActionRequest& request,
    bool effectful_action_authorized)
{
    const bool durable_action = effectful_semantic_action(request.action_id);
    const std::string canonical_request = action_request_json(request);
    // Durable records need a fixed, externally validated digest. Process-local
    // replay can compare the complete bounded request and therefore does not
    // turn hash equality into semantic equality.
    const std::string fingerprint = durable_action
        ? digest(canonical_request) : canonical_request;
    std::string existing;
    std::string ledger_detail;
    const auto lookup = action_ledger_.lookup(
        context_.workspace(), request, fingerprint,
        durable_action, existing, ledger_detail);
    if (lookup == PresentationActionLedger::Lookup::match) {
        return replayed_action_result(existing);
    }
    if (lookup == PresentationActionLedger::Lookup::conflict) {
        const std::string payload = action_result_json(
            request, "refused_before_effects", {}, {},
            "idempotency_key_conflict", "The idempotency key names different action input", false);
        return service_refusal(
            "presentation.action", "idempotency_key_conflict",
            "Idempotency key has already been used with different input", payload,
            facman::core::OutcomeKind::conflict);
    }
    if (lookup == PresentationActionLedger::Lookup::invalid) {
        const std::string payload = action_result_json(
            request, "recovery_required", {}, {},
            "idempotency_receipt_invalid",
            ledger_detail.empty() ? "The durable action receipt is invalid" : ledger_detail,
            false);
        return service_refusal(
            "presentation.action", "idempotency_receipt_invalid",
            "The durable action receipt must be inspected before retrying", payload,
            facman::core::OutcomeKind::recovery_required);
    }

    PresentationQueryRequest query_request;
    query_request.scope = request.scope;
    query_request.selected_instance_id = request.selected_instance_id;
    ApplicationResult current = query(query_request);
    const std::string current_snapshot = result_string(current);
    if (current.status != ULK_STATUS_OK || current_snapshot.empty()) return current;
    const std::string current_revision = snapshot_revision(current_snapshot);
    if (request.expected_snapshot_revision != current_revision) {
        const std::string payload = action_result_json(
            request, "refused_before_effects", current_snapshot, {},
            "stale_snapshot_revision", "Refresh before retrying the action", false);
        return service_refusal(
            "presentation.action", "stale_snapshot_revision",
            "Expected presentation revision is stale", payload,
            facman::core::OutcomeKind::conflict);
    }
    const AdvertisedAction admission = advertised_action(current_snapshot, request.action_id);
    if (!admission.found) {
        const std::string payload = action_result_json(
            request, "refused_before_effects", current_snapshot, {},
            "semantic_action_unknown",
            "The action is not available in the requested presentation scope", false);
        return service_refusal(
            "presentation.action", "semantic_action_unknown",
            "Semantic action is not advertised in this scope", payload,
            facman::core::OutcomeKind::invalid_argument);
    }
    if (!admission.available) {
        const std::string code = admission.refusal_code.empty()
            ? "action_unavailable" : admission.refusal_code;
        const std::string reason = admission.refusal_reason.empty()
            ? "The backend has not admitted this action" : admission.refusal_reason;
        const std::string payload = action_result_json(
            request, "refused_before_effects", current_snapshot, {}, code, reason, false);
        return service_refusal(
            "presentation.action", code, reason, payload,
            facman::core::OutcomeKind::refused);
    }

    std::string required_input;
    if (request.action_id == "installation.register_read_only" &&
        (request.scope != "installations" || request.installation_id.empty() ||
            request.installation_path.empty())) {
        required_input = "installation_id and installation_path are required";
    } else if (request.action_id == "instance.create_isolated" &&
        (request.scope != "instances" || request.new_instance_id.empty() ||
            request.display_name.empty() || request.installation_id.empty())) {
        required_input = "new_instance_id, display_name, and installation_id are required";
    } else if (request.action_id == "recovery.apply_supported" &&
        (request.scope != "activity_recovery" || request.transaction_id.empty())) {
        required_input = "transaction_id is required";
    } else if (request.action_id == "profile.create" &&
        ((request.scope != "instances" && request.scope != "content") ||
            request.profile_id.empty())) {
        required_input = "profile_id is required";
    } else if ((request.action_id == "profile.select" ||
            request.action_id == "configuration.explain_effective") &&
        ((request.scope != "instances" && request.scope != "content" &&
             request.scope != "launch_deck") || request.selected_instance_id.empty() ||
            request.profile_id.empty())) {
        required_input = "selected_instance_id and profile_id are required";
    } else if (request.action_id == "mods.inspect" &&
        (request.scope != "content" || request.mod_identity.empty())) {
        required_input = "mod_identity is required";
    } else if ((request.action_id == "modsets.plan" ||
            request.action_id == "modsets.apply") &&
        (request.scope != "content" || request.selected_instance_id.empty() ||
            request.mod_identity.empty())) {
        required_input = "selected_instance_id and mod_identity are required";
    } else if (request.action_id == "modsets.verify" &&
        (request.scope != "content" || request.selected_instance_id.empty())) {
        required_input = "selected_instance_id is required";
    } else if (request.action_id == "modsets.rollback" &&
        (request.scope != "content" || request.selected_instance_id.empty() ||
            request.transaction_id.empty())) {
        required_input = "selected_instance_id and transaction_id are required";
    } else if ((request.action_id == "saves.inspect" ||
            request.action_id == "saves.associate" ||
            request.action_id == "saves.backup") &&
        (request.scope != "saves" || request.selected_instance_id.empty() ||
            request.save.empty())) {
        required_input = "selected_instance_id and save are required";
    } else if (request.action_id == "support.export_redacted_bundle" &&
        (request.scope != "settings_support" ||
            request.selected_instance_id.empty() || request.output_path.empty())) {
        required_input = "selected_instance_id and output_path are required";
    } else if ((request.action_id == "instance.select_context" ||
            request.action_id == "readiness.refresh" ||
            request.action_id == "launch.menu_plan" || request.action_id == "launch.play" ||
            request.action_id == "sessions.stop") &&
        request.selected_instance_id.empty()) {
        required_input = "selected_instance_id is required";
    }
    if (!required_input.empty()) {
        const std::string payload = action_result_json(
            request, "refused_before_effects", current_snapshot, {},
            "semantic_action_input_required", required_input, false);
        return service_refusal(
            "presentation.action", "semantic_action_input_required", required_input,
            payload, facman::core::OutcomeKind::invalid_argument);
    }

    const char* durable_effect = request.action_id == "launch.play"
        ? "process_execution"
        : request.action_id == "sessions.stop" ? "process_control" : "workspace_write";
    if (durable_action) {
        if (!effectful_action_authorized || request.confirmation != "explicit") {
            const std::string payload = action_result_json(
                request, "refused_before_effects", current_snapshot, {},
                "semantic_action_effect_confirmation_required",
                "Effectful semantic actions require explicit confirmation and non-dry-run dispatch",
                false, {durable_effect});
            return service_refusal(
                "presentation.action", "semantic_action_effect_confirmation_required",
                "Effectful semantic actions require explicit confirmation and non-dry-run dispatch",
                payload, facman::core::OutcomeKind::refused);
        }
        if (request.idempotency_key.empty() || request.durable_operation_id.empty() ||
            request.attempt_id.empty()) {
            const std::string payload = action_result_json(
                request, "refused_before_effects", current_snapshot, {},
                "semantic_action_identity_required",
                "Effectful semantic actions require idempotency, operation, and attempt identities",
                false, {durable_effect});
            return service_refusal(
                "presentation.action", "semantic_action_identity_required",
                "Effectful semantic actions require idempotency, operation, and attempt identities",
                payload, facman::core::OutcomeKind::invalid_argument);
        }
        // The durable receipt belongs to the authoritative workspace. Establish
        // workspace ownership before creating the receipt directory so the
        // first accepted semantic action cannot make an otherwise empty root
        // look foreign to the domain handler. This preparation is idempotent;
        // the receipt is still claimed before the requested domain effect.
        auto workspace_ready = context_.workspace_repository().ensure();
        if (!workspace_ready) {
            const std::string payload = action_result_json(
                request, "refused_before_effects", current_snapshot, {},
                workspace_ready.error().code, workspace_ready.error().message,
                false, {durable_effect});
            return service_refusal(
                "presentation.action", workspace_ready.error().code,
                "The authoritative workspace could not be prepared safely", payload,
                facman::core::OutcomeKind::refused);
        }
        const std::string pending = action_result_json(
            request, "outcome_unknown", {}, {},
            "semantic_action_dispatch_uncertain",
            "A durable action was accepted; inspect the receipt before retrying if dispatch is interrupted",
            false, {durable_effect});
        if (!ensure_workspace_admission_receipt(
                context_.workspace(), workspace_ready.value().id.str(), ledger_detail)) {
            const std::string payload = action_result_json(
                request, "refused_before_effects", current_snapshot, {},
                "workspace_admission_receipt_unavailable",
                ledger_detail.empty()
                    ? "The workspace prerequisite receipt could not be persisted"
                    : ledger_detail,
                false, {durable_effect});
            return service_refusal(
                "presentation.action", "workspace_admission_receipt_unavailable",
                "The workspace prerequisite could not be admitted durably", payload,
                facman::core::OutcomeKind::recovery_required);
        }
        if (!action_ledger_.claim(
                context_.workspace(), request, fingerprint,
                pending, ledger_detail)) {
            const auto raced = action_ledger_.lookup(
                context_.workspace(), request, fingerprint,
                true, existing, ledger_detail);
            if (raced == PresentationActionLedger::Lookup::match) {
                return replayed_action_result(existing);
            }
            const std::string code = raced == PresentationActionLedger::Lookup::conflict
                ? "idempotency_key_conflict" : "idempotency_receipt_unavailable";
            const std::string message = raced == PresentationActionLedger::Lookup::conflict
                ? "The idempotency key names different accepted action input"
                : "The durable action receipt could not be claimed safely";
            const std::string payload = action_result_json(
                request, "refused_before_effects", current_snapshot, {}, code,
                ledger_detail.empty() ? message : ledger_detail, false, {durable_effect});
            return service_refusal(
                "presentation.action", code, message, payload,
                raced == PresentationActionLedger::Lookup::conflict
                    ? facman::core::OutcomeKind::conflict
                    : facman::core::OutcomeKind::recovery_required);
        }
    }

    const auto finish = [&](std::string value) -> ApplicationResult {
        if (!action_ledger_.remember(
                context_.workspace(), request, fingerprint,
                value, durable_action, ledger_detail)) {
            const std::string uncertain = action_result_json(
                request, "outcome_unknown", {}, {},
                "idempotency_receipt_finalization_failed",
                ledger_detail.empty()
                    ? "The accepted action receipt could not be finalized"
                    : ledger_detail,
                false, {durable_effect});
            return service_refusal(
                "presentation.action", "idempotency_receipt_finalization_failed",
                "The action outcome is unknown until the durable receipt is inspected",
                uncertain, facman::core::OutcomeKind::outcome_unknown);
        }
        return replayed_action_result(value);
    };

    std::string output;
    if (request.action_id == "presentation.refresh") {
        output = action_result_json(
            request, "completed", current_snapshot, {}, {}, {}, false, {"read_only"});
    } else if (request.action_id == "workspace.initialize" &&
               request.scope == "settings_support") {
        auto initialized = context_.workspace_repository().ensure();
        if (!initialized) {
            output = action_result_json(
                request, "recovery_required", {}, {}, initialized.error().code,
                initialized.error().message, false, {"workspace_write"});
        } else {
            json::ObjectBuilder payload;
            payload.add_string("schema", "facman.workspace_initialization.v1");
            payload.add_string("workspace_id", initialized.value().id.str());
            payload.add_string("workspace", facman::platform::path_to_utf8(context_.workspace()));
            payload.add_unsigned_integer("layout_version", initialized.value().layout_version);
            payload.add_bool("initialized", true);
            const ApplicationResult replacement = query(query_request);
            output = action_result_json(
                request, "completed",
                replacement.status == ULK_STATUS_OK
                    ? result_string(replacement) : std::string(),
                payload.serialize(),
                replacement.status == ULK_STATUS_OK
                    ? std::string() : "replacement_snapshot_unavailable",
                replacement.status == ULK_STATUS_OK
                    ? std::string() : replacement.error_message,
                false, {"workspace_write"});
        }
    } else if (request.action_id == "doctor.run" &&
               (request.scope == "launch_deck" || request.scope == "settings_support")) {
        DoctorRequest doctor_request;
        doctor_request.roots = request.roots;
        const ApplicationResult doctor = handlers::run_doctor(context_, doctor_request);
        if (doctor.status == ULK_STATUS_OK) {
            output = action_result_json(
                request, "completed", {}, result_string(doctor), {}, {}, false,
                {"read_only"});
        } else {
            const std::string payload = action_result_json(
                request, "refused_before_effects", {}, result_string(doctor),
                doctor.error_code, doctor.error_message, false, {"read_only"});
            return service_refusal(
                "presentation.action", doctor.error_code, doctor.error_message, payload,
                doctor.outcome_kind);
        }
    } else if (request.action_id == "installations.scan") {
        std::vector<std::filesystem::path> roots_to_scan;
        for (const auto& root : request.roots) roots_to_scan.push_back(facman::platform::path_from_utf8(root));
        const std::string report = facman::factorio::discovery::discovery_report_json(
            facman::factorio::discovery::scan_install_candidates(roots_to_scan));
        output = action_result_json(
            request, "completed", {}, report, {}, {}, true,
            {"read_only", "filesystem_observation"});
    } else if (request.action_id == "installation.register_read_only" &&
               request.scope == "installations") {
        ImportInstallRefRequest import_request;
        import_request.path = request.installation_path;
        import_request.install_id = request.installation_id;
        const ApplicationResult imported = handlers::import_install(context_, import_request);
        if (imported.status != ULK_STATUS_OK) {
            const char* outcome = imported.outcome_kind == facman::core::OutcomeKind::recovery_required
                || imported.error_code == "transaction_recovery_required"
                ? "recovery_required" : "refused_before_effects";
            output = action_result_json(
                request, outcome, {}, result_string(imported), imported.error_code,
                imported.error_message, false, {"workspace_write"});
        } else {
            const ApplicationResult replacement = query(query_request);
            output = action_result_json(
                request, "completed",
                replacement.status == ULK_STATUS_OK ? result_string(replacement) : std::string(),
                result_string(imported),
                replacement.status == ULK_STATUS_OK ? std::string() : "replacement_snapshot_unavailable",
                replacement.status == ULK_STATUS_OK ? std::string() : replacement.error_message,
                false, {"workspace_write"});
        }
    } else if (request.action_id == "instance.create_isolated" &&
               request.scope == "instances") {
        CreateInstanceRequest create;
        create.instance_id = request.new_instance_id;
        create.display_name = request.display_name;
        create.install_id = request.installation_id;
        create.template_id = request.template_id.empty() ? "vanilla" : request.template_id;
        create.source_data_root = request.source_data_root;
        const ApplicationResult created = handlers::create_instance(context_, create);
        if (created.status != ULK_STATUS_OK) {
            const char* outcome = created.outcome_kind == facman::core::OutcomeKind::recovery_required
                || created.error_code == "transaction_recovery_required"
                ? "recovery_required" : "refused_before_effects";
            output = action_result_json(
                request, outcome, {}, result_string(created), created.error_code,
                created.error_message, false, {"workspace_write"});
        } else {
            query_request.selected_instance_id = request.new_instance_id;
            const ApplicationResult replacement = query(query_request);
            output = action_result_json(
                request, "completed",
                replacement.status == ULK_STATUS_OK ? result_string(replacement) : std::string(),
                result_string(created),
                replacement.status == ULK_STATUS_OK ? std::string() : "replacement_snapshot_unavailable",
                replacement.status == ULK_STATUS_OK ? std::string() : replacement.error_message,
                false, {"workspace_write"});
        }
    } else if (request.action_id == "instance.select_context" &&
               request.scope == "instances") {
        InspectInstanceRequest inspect;
        inspect.instance_id = request.selected_instance_id;
        const ApplicationResult inspected = handlers::inspect_instance(context_, inspect);
        if (inspected.status != ULK_STATUS_OK) {
            const std::string payload = action_result_json(
                request, "refused_before_effects", current_snapshot,
                result_string(inspected), inspected.error_code,
                inspected.error_message, false, {"read_only"});
            return service_refusal(
                "presentation.action", inspected.error_code,
                inspected.error_message, payload, inspected.outcome_kind);
        }
        const ApplicationResult replacement = query(query_request);
        output = action_result_json(
            request, "completed",
            replacement.status == ULK_STATUS_OK ? result_string(replacement) : std::string(),
            result_string(inspected),
            replacement.status == ULK_STATUS_OK ? std::string() : "replacement_snapshot_unavailable",
            replacement.status == ULK_STATUS_OK ? std::string() : replacement.error_message,
            false, {"read_only"});
    } else if (request.action_id == "profile.create" &&
               (request.scope == "instances" || request.scope == "content")) {
        ApplicationRequest domain;
        domain.command = CommandId::profiles_create;
        CreateProfileRequest create;
        create.profile_id = request.profile_id;
        create.template_id = request.template_id.empty() ? "vanilla" : request.template_id;
        domain.payload = std::move(create);
        domain.dry_run = false;
        const ApplicationResult created = handlers::dispatch_profiles(context_, domain);
        if (created.status != ULK_STATUS_OK) {
            output = action_result_json(
                request, "refused_before_effects", current_snapshot,
                result_string(created), created.error_code, created.error_message,
                false, {"workspace_write"});
        } else {
            const ApplicationResult replacement = query(query_request);
            output = action_result_json(
                request, "completed",
                replacement.status == ULK_STATUS_OK ? result_string(replacement) : std::string(),
                result_string(created),
                replacement.status == ULK_STATUS_OK ? std::string() : "replacement_snapshot_unavailable",
                replacement.status == ULK_STATUS_OK ? std::string() : replacement.error_message,
                false, {"workspace_write"});
        }
    } else if (request.action_id == "profile.select" &&
               (request.scope == "instances" || request.scope == "content")) {
        ApplicationRequest domain;
        domain.command = CommandId::profiles_apply;
        EffectiveProfileRequest select;
        select.instance_id = request.selected_instance_id;
        select.profile_id = request.profile_id;
        domain.payload = std::move(select);
        domain.dry_run = false;
        const ApplicationResult selected = handlers::dispatch_profiles(context_, domain);
        if (selected.status != ULK_STATUS_OK) {
            output = action_result_json(
                request, "refused_before_effects", current_snapshot,
                result_string(selected), selected.error_code, selected.error_message,
                false, {"workspace_write"});
        } else {
            const ApplicationResult replacement = query(query_request);
            output = action_result_json(
                request, "completed",
                replacement.status == ULK_STATUS_OK ? result_string(replacement) : std::string(),
                result_string(selected),
                replacement.status == ULK_STATUS_OK ? std::string() : "replacement_snapshot_unavailable",
                replacement.status == ULK_STATUS_OK ? std::string() : replacement.error_message,
                false, {"workspace_write"});
        }
    } else if (request.action_id == "configuration.explain_effective" &&
               (request.scope == "launch_deck" || request.scope == "instances" ||
                   request.scope == "content")) {
        ApplicationRequest domain;
        domain.command = CommandId::profiles_plan;
        EffectiveProfileRequest explain;
        explain.instance_id = request.selected_instance_id;
        explain.profile_id = request.profile_id;
        domain.payload = std::move(explain);
        const ApplicationResult explained = handlers::dispatch_profiles(context_, domain);
        if (explained.status != ULK_STATUS_OK) {
            const std::string payload = action_result_json(
                request, "refused_before_effects", current_snapshot,
                result_string(explained), explained.error_code,
                explained.error_message, false, {"read_only"});
            return service_refusal(
                "presentation.action", explained.error_code,
                explained.error_message, payload, explained.outcome_kind);
        }
        output = action_result_json(
            request, "completed", current_snapshot, result_string(explained),
            {}, {}, false, {"read_only"});
    } else if (request.action_id == "launch.menu_plan" &&
               (request.scope == "launch_deck" || request.scope == "instances")) {
        BuildLaunchPlanRequest plan;
        plan.instance_id = request.selected_instance_id;
        const ApplicationResult planned = handlers::preview_launch(
            context_, plan, "launch.menu_plan");
        if (planned.status != ULK_STATUS_OK) {
            const std::string payload = action_result_json(
                request, "refused_before_effects", current_snapshot,
                result_string(planned), planned.error_code,
                planned.error_message, false, {"read_only"});
            return service_refusal(
                "presentation.action", planned.error_code,
                planned.error_message, payload, planned.outcome_kind);
        }
        const std::string plan_payload =
            std::holds_alternative<launch::LaunchPlanResult>(planned.output)
            ? launch::launch_plan_json(
                std::get<launch::LaunchPlanResult>(planned.output))
            : result_string(planned);
        output = action_result_json(
            request, "completed", current_snapshot, plan_payload,
            {}, {}, false, {"read_only"});
    } else if (request.action_id == "mods.inspect" &&
               request.scope == "content") {
        ApplicationRequest domain;
        domain.command = CommandId::mods_inspect;
        ModInventoryRequest inspect;
        inspect.identity = request.mod_identity;
        domain.payload = std::move(inspect);
        const ApplicationResult inspected =
            handlers::dispatch_mod_inventory(context_, domain);
        if (inspected.status != ULK_STATUS_OK) {
            const std::string payload = action_result_json(
                request, "refused_before_effects", current_snapshot,
                result_string(inspected), inspected.error_code,
                inspected.error_message, false, {"read_only"});
            return service_refusal(
                "presentation.action", inspected.error_code,
                inspected.error_message, payload, inspected.outcome_kind);
        }
        output = action_result_json(
            request, "completed", current_snapshot, result_string(inspected),
            {}, {}, false, {"read_only"});
    } else if ((request.action_id == "modsets.plan" ||
                   request.action_id == "modsets.apply") &&
               request.scope == "content") {
        const bool applying = request.action_id == "modsets.apply";
        ApplicationRequest domain;
        domain.command = applying ? CommandId::modsets_apply : CommandId::modsets_plan;
        ModsetSolverRequest modset;
        modset.instance_id = request.selected_instance_id;
        modset.enabled_mods.push_back(request.mod_identity);
        domain.payload = std::move(modset);
        domain.dry_run = !applying;
        const ApplicationResult resolved =
            handlers::dispatch_modset_solver(context_, domain);
        if (resolved.status != ULK_STATUS_OK) {
            const char* outcome = resolved.outcome_kind ==
                    facman::core::OutcomeKind::recovery_required
                ? "recovery_required" : "refused_before_effects";
            output = action_result_json(
                request, outcome, current_snapshot, result_string(resolved),
                resolved.error_code, resolved.error_message, false,
                {applying ? "workspace_write" : "read_only"});
        } else if (!applying) {
            output = action_result_json(
                request, "completed", current_snapshot, result_string(resolved),
                {}, {}, false, {"read_only"});
        } else {
            const ApplicationResult replacement = query(query_request);
            output = action_result_json(
                request, "completed",
                replacement.status == ULK_STATUS_OK
                    ? result_string(replacement) : std::string(),
                result_string(resolved),
                replacement.status == ULK_STATUS_OK
                    ? std::string() : "replacement_snapshot_unavailable",
                replacement.status == ULK_STATUS_OK
                    ? std::string() : replacement.error_message,
                false, {"workspace_write"});
        }
    } else if (request.action_id == "modsets.verify" &&
               request.scope == "content") {
        ModsetInstanceRequest verify;
        verify.instance_id = request.selected_instance_id;
        const ApplicationResult verified = handlers::verify_modset(context_, verify);
        if (verified.status != ULK_STATUS_OK) {
            const std::string payload = action_result_json(
                request, "refused_before_effects", current_snapshot,
                result_string(verified), verified.error_code,
                verified.error_message, false, {"read_only"});
            return service_refusal(
                "presentation.action", verified.error_code,
                verified.error_message, payload, verified.outcome_kind);
        }
        output = action_result_json(
            request, "completed", current_snapshot, result_string(verified),
            {}, {}, false, {"read_only"});
    } else if (request.action_id == "modsets.rollback" &&
               request.scope == "content") {
        ApplicationRequest domain;
        domain.command = CommandId::modsets_rollback;
        ModsetSolverRequest rollback;
        rollback.instance_id = request.selected_instance_id;
        rollback.transaction_id = request.transaction_id;
        domain.payload = std::move(rollback);
        domain.dry_run = false;
        const ApplicationResult rolled_back =
            handlers::dispatch_modset_solver(context_, domain);
        if (rolled_back.status != ULK_STATUS_OK) {
            const char* outcome = rolled_back.outcome_kind ==
                    facman::core::OutcomeKind::recovery_required
                ? "recovery_required" : "refused_before_effects";
            output = action_result_json(
                request, outcome, current_snapshot, result_string(rolled_back),
                rolled_back.error_code, rolled_back.error_message, false,
                {"workspace_write"});
        } else {
            const ApplicationResult replacement = query(query_request);
            output = action_result_json(
                request, "completed",
                replacement.status == ULK_STATUS_OK
                    ? result_string(replacement) : std::string(),
                result_string(rolled_back),
                replacement.status == ULK_STATUS_OK
                    ? std::string() : "replacement_snapshot_unavailable",
                replacement.status == ULK_STATUS_OK
                    ? std::string() : replacement.error_message,
                false, {"workspace_write"});
        }
    } else if ((request.action_id == "saves.inspect" ||
                   request.action_id == "saves.associate") &&
               request.scope == "saves") {
        const bool associating = request.action_id == "saves.associate";
        ApplicationRequest domain;
        domain.command = associating
            ? CommandId::saves_associate : CommandId::saves_inspect;
        SaveIndexRequest save;
        save.instance_id = request.selected_instance_id;
        save.save = request.save;
        save.profile_id = request.profile_id;
        save.source_operation = "presentation.action";
        domain.payload = std::move(save);
        domain.dry_run = !associating;
        const ApplicationResult selected =
            handlers::dispatch_save_index(context_, domain);
        if (selected.status != ULK_STATUS_OK) {
            const char* outcome = selected.outcome_kind ==
                    facman::core::OutcomeKind::recovery_required
                ? "recovery_required" : "refused_before_effects";
            output = action_result_json(
                request, outcome, current_snapshot, result_string(selected),
                selected.error_code, selected.error_message, false,
                {associating ? "workspace_write" : "read_only"});
        } else if (!associating) {
            output = action_result_json(
                request, "completed", current_snapshot, result_string(selected),
                {}, {}, false, {"read_only"});
        } else {
            const ApplicationResult replacement = query(query_request);
            output = action_result_json(
                request, "completed",
                replacement.status == ULK_STATUS_OK
                    ? result_string(replacement) : std::string(),
                result_string(selected),
                replacement.status == ULK_STATUS_OK
                    ? std::string() : "replacement_snapshot_unavailable",
                replacement.status == ULK_STATUS_OK
                    ? std::string() : replacement.error_message,
                false, {"workspace_write"});
        }
    } else if (request.action_id == "saves.backup" &&
               request.scope == "saves") {
        BackupSaveRequest backup;
        backup.instance_id = request.selected_instance_id;
        backup.save = request.save;
        if (!request.output_path.empty()) {
            backup.output_path = facman::platform::path_from_utf8(request.output_path);
        }
        const ApplicationResult backed_up = handlers::backup_save(context_, backup);
        if (backed_up.status != ULK_STATUS_OK) {
            const char* outcome = backed_up.outcome_kind ==
                    facman::core::OutcomeKind::recovery_required
                ? "recovery_required" : "refused_before_effects";
            output = action_result_json(
                request, outcome, current_snapshot, result_string(backed_up),
                backed_up.error_code, backed_up.error_message, false,
                {"workspace_write"});
        } else {
            const ApplicationResult replacement = query(query_request);
            output = action_result_json(
                request, "completed",
                replacement.status == ULK_STATUS_OK
                    ? result_string(replacement) : std::string(),
                result_string(backed_up),
                replacement.status == ULK_STATUS_OK
                    ? std::string() : "replacement_snapshot_unavailable",
                replacement.status == ULK_STATUS_OK
                    ? std::string() : replacement.error_message,
                false, {"workspace_write"});
        }
    } else if (request.action_id == "support.export_redacted_bundle" &&
               request.scope == "settings_support") {
        ExportDiagnosticRequest export_request;
        export_request.instance_id = request.selected_instance_id;
        export_request.output_path =
            facman::platform::path_from_utf8(request.output_path);
        const ApplicationResult exported =
            handlers::export_diagnostics(context_, export_request);
        if (exported.status != ULK_STATUS_OK) {
            const char* outcome = exported.outcome_kind ==
                    facman::core::OutcomeKind::recovery_required
                ? "recovery_required" : "refused_before_effects";
            output = action_result_json(
                request, outcome, current_snapshot, result_string(exported),
                exported.error_code, exported.error_message, false,
                {"workspace_write"});
        } else {
            const ApplicationResult replacement = query(query_request);
            output = action_result_json(
                request, "completed",
                replacement.status == ULK_STATUS_OK
                    ? result_string(replacement) : std::string(),
                result_string(exported),
                replacement.status == ULK_STATUS_OK
                    ? std::string() : "replacement_snapshot_unavailable",
                replacement.status == ULK_STATUS_OK
                    ? std::string() : replacement.error_message,
                false, {"workspace_write"});
        }
    } else if (request.action_id == "readiness.refresh" &&
               (request.scope == "launch_deck" || request.scope == "instances")) {
        output = action_result_json(
            request, "completed", current_snapshot, {}, {}, {}, false, {"read_only"});
    } else if (request.action_id == "recovery.inspect" && request.scope == "activity_recovery") {
        output = action_result_json(
            request, "completed", {}, recovery_json(context_.workspace()), {}, {}, false,
            {"read_only"});
    } else if (request.action_id == "recovery.apply_supported" &&
               request.scope == "activity_recovery") {
        RecoveryRequest recovery_request;
        recovery_request.transaction_id = request.transaction_id;
        const ApplicationResult recovered = handlers::recovery_apply(context_, recovery_request);
        if (recovered.status != ULK_STATUS_OK) {
            output = action_result_json(
                request, "recovery_required", {}, result_string(recovered),
                recovered.error_code, recovered.error_message, false,
                {"workspace_write"});
        } else {
            const ApplicationResult replacement = query(query_request);
            output = action_result_json(
                request, "completed",
                replacement.status == ULK_STATUS_OK ? result_string(replacement) : std::string(),
                result_string(recovered),
                replacement.status == ULK_STATUS_OK ? std::string() : "replacement_snapshot_unavailable",
                replacement.status == ULK_STATUS_OK ? std::string() : replacement.error_message,
                false, {"workspace_write"});
        }
    } else if (request.action_id == "sessions.stop" &&
               (request.scope == "launch_deck" || request.scope == "instances" ||
                   request.scope == "activity_recovery") &&
               launch_executor_ != nullptr) {
        PresentationSessionStopExecution stopped =
            launch_executor_->request_stop(request);
        if (!stopped.accepted) {
            const std::string code = stopped.error_code.empty()
                ? "session_stop_unavailable" : stopped.error_code;
            const std::string message = stopped.error_message.empty()
                ? "The selected fixture session cannot be stopped" : stopped.error_message;
            output = action_result_json(
                request, "refused_before_effects", current_snapshot, stopped.payload,
                code, message, false, {"process_control"});
        } else {
            const ApplicationResult replacement = query(query_request);
            output = action_result_json(
                request, "completed",
                replacement.status == ULK_STATUS_OK
                    ? result_string(replacement) : std::string(),
                stopped.payload,
                replacement.status == ULK_STATUS_OK
                    ? std::string() : "replacement_snapshot_unavailable",
                replacement.status == ULK_STATUS_OK
                    ? std::string() : replacement.error_message,
                false, {"process_control"});
        }
    } else if (request.action_id == "launch.play" &&
               (request.scope == "launch_deck" || request.scope == "instances") &&
               launch_executor_ != nullptr) {
        PresentationLaunchExecution execution = launch_executor_->execute(request);
        if (!execution.error_code.empty()) {
            output = action_result_json(
                request, "refused_before_effects", current_snapshot, execution.payload,
                execution.error_code, execution.error_message, false,
                {"process_execution", "session_journal_write"});
        } else {
            static const char* const outcomes[] = {
                "cancelled_before_dispatch",
                "refused_before_effects",
                "completed",
                "cancellation_requested_but_completed",
                "recovery_required",
                "outcome_unknown",
            };
            if (std::find(std::begin(outcomes), std::end(outcomes),
                    execution.operation_outcome) == std::end(outcomes)) {
                output = action_result_json(
                    request, "outcome_unknown", current_snapshot, execution.payload,
                    "semantic_action_outcome_invalid",
                    "The launch executor returned an invalid operation outcome", false,
                    {"process_execution", "session_journal_write"});
            } else {
                const ApplicationResult replacement = query(query_request);
                output = action_result_json(
                    request, execution.operation_outcome.c_str(),
                    replacement.status == ULK_STATUS_OK
                        ? result_string(replacement) : std::string(),
                    execution.payload,
                    replacement.status == ULK_STATUS_OK
                        ? std::string() : "replacement_snapshot_unavailable",
                    replacement.status == ULK_STATUS_OK
                        ? std::string() : replacement.error_message,
                    false, {"process_execution", "session_journal_write"});
            }
        }
    } else {
        const std::string payload = action_result_json(
            request, "refused_before_effects", current_snapshot, {},
            "semantic_action_unknown",
            "The advertised semantic action has no callable handler", false);
        return service_refusal(
            "presentation.action", "semantic_action_unknown",
            "Advertised semantic action handler is unavailable", payload,
            facman::core::OutcomeKind::internal_error);
    }
    return finish(std::move(output));
}

} // namespace facman::factorio::application
