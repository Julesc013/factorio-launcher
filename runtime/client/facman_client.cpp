// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_client_internal.h"

#include "fl_system_services.h"
#include "ulk/ulk_operation.h"

#include <utility>

namespace facman::client {
namespace json = facman::core::json;

namespace detail {

std::string string_value(const facman::core::json::Value& object, const char* key);

ulk_string_view view(const std::string& text)
{
    return {text.data(), static_cast<ulk_size>(text.size())};
}

ulk_operation_outcome_v1 native_outcome(OperationOutcome outcome)
{
    switch (outcome) {
    case OperationOutcome::cancelled_before_dispatch: return ULK_OPERATION_CANCELLED_BEFORE_DISPATCH;
    case OperationOutcome::refused_before_effects: return ULK_OPERATION_REFUSED_BEFORE_EFFECTS;
    case OperationOutcome::completed: return ULK_OPERATION_COMPLETED;
    case OperationOutcome::cancellation_requested_but_completed:
        return ULK_OPERATION_CANCELLATION_REQUESTED_BUT_COMPLETED;
    case OperationOutcome::recovery_required: return ULK_OPERATION_RECOVERY_REQUIRED;
    case OperationOutcome::outcome_unknown: return ULK_OPERATION_OUTCOME_UNKNOWN;
    }
    return ULK_OPERATION_OUTCOME_UNKNOWN;
}

bool decode_operation_outcome(const std::string& name, OperationOutcome& outcome)
{
    if (name == "cancelled_before_dispatch") outcome = OperationOutcome::cancelled_before_dispatch;
    else if (name == "refused_before_effects") outcome = OperationOutcome::refused_before_effects;
    else if (name == "completed") outcome = OperationOutcome::completed;
    else if (name == "cancellation_requested_but_completed") {
        outcome = OperationOutcome::cancellation_requested_but_completed;
    } else if (name == "recovery_required") outcome = OperationOutcome::recovery_required;
    else if (name == "outcome_unknown") outcome = OperationOutcome::outcome_unknown;
    else return false;
    return true;
}

bool bool_value(const json::Value& object, const char* key, bool& output)
{
    const auto* field = object.find(key);
    if (field == nullptr || !field->is_bool()) return false;
    auto parsed = field->bool_value();
    if (!parsed) return false;
    output = parsed.value();
    return true;
}

bool decode_operation(const json::Value& document, OperationResult& operation)
{
    const auto* value = document.find("operation");
    if (value == nullptr || !value->is_object()) return false;
    const auto* recovery = value->find("recovery");
    if (recovery == nullptr || !recovery->is_object()) return false;
    operation.operation_id = string_value(*value, "operation_id");
    operation.attempt_id = string_value(*value, "attempt_id");
    operation.recovery.transaction_id = string_value(*recovery, "transaction_id");
    operation.recovery.inspect_command = string_value(*recovery, "inspect_command");
    return string_value(*value, "schema") == "ulk.operation_outcome.v1" &&
        decode_operation_outcome(string_value(*value, "outcome"), operation.outcome) &&
        bool_value(*value, "effects_may_have_occurred", operation.effects_may_have_occurred) &&
        bool_value(*recovery, "required", operation.recovery.required) &&
        operation_result_valid(operation);
}

OperationResult operation_for(
    const CommandRequest& request,
    OperationOutcome outcome,
    const CommandResponse* response = nullptr)
{
    OperationResult operation;
    operation.operation_id = request.operation_id;
    operation.attempt_id = request.attempt_id;
    operation.outcome = outcome;
    operation.effects_may_have_occurred =
        outcome == OperationOutcome::recovery_required ||
        outcome == OperationOutcome::outcome_unknown ||
        ((outcome == OperationOutcome::completed ||
          outcome == OperationOutcome::cancellation_requested_but_completed) && !request.dry_run);
    if (outcome == OperationOutcome::recovery_required || outcome == OperationOutcome::outcome_unknown) {
        operation.recovery.required = true;
        operation.recovery.inspect_command = "workspace.recovery.inspect";
        if (response != nullptr) operation.recovery.transaction_id = response->payload_string("transaction_id");
    }
    return operation;
}

bool cancelled(const CommandRequest& request) noexcept
{
    return request.cancellation && request.cancellation->cancellation_requested();
}

void progress(const CommandRequest& request, const char* stage, std::uint64_t completed, std::uint64_t total) noexcept
{
    if (request.progress) request.progress->report({stage, completed, total});
}

facman::core::Result<CommandResponse> failure(
    std::string code,
    std::string message,
    std::string path,
    facman::core::OutcomeKind kind)
{
    return facman::core::Result<CommandResponse>::failure(
        {std::move(code), std::move(message), std::move(path), kind});
}

std::string string_value(const facman::core::json::Value& object, const char* key)
{
    const auto* field = object.find(key);
    if (field == nullptr || !field->is_string()) return {};
    auto value = field->string_value();
    return value ? value.value() : std::string();
}

facman::core::Result<CommandResponse> decode_response(int status, std::string envelope)
{
    facman::core::json::Limits limits;
    limits.maximum_bytes = 64U * 1024U * 1024U;
    limits.maximum_depth = 64;
    limits.maximum_nodes = 1000000;
    limits.maximum_string_bytes = 32U * 1024U * 1024U;
    auto document = facman::core::json::parse(envelope, limits);
    if (!document || !document.value().is_object()) {
        return failure(
            "client_response_invalid",
            document ? "command response must be an object" : document.error().message);
    }
    CommandResponse response;
    response.status = status;
    response.envelope = std::move(envelope);
    response.outcome = string_value(document.value(), "outcome");
    if (response.outcome.empty()) response.outcome = status == 0 ? "ok" : "refused";
    response.outcome_kind = facman::core::outcome_kind_from_name(response.outcome);
    const auto* payload = document.value().find("payload");
    if (payload != nullptr && !payload->is_null()) {
        response.payload = payload->serialize();
        auto parsed_payload = facman::core::json::parse(response.payload, limits);
        if (parsed_payload) {
            response.parsed_payload = std::make_shared<facman::core::json::Value>(
                parsed_payload.take_value());
        }
    }
    const auto* error = document.value().find("error");
    if (error != nullptr && error->is_object()) {
        response.error_code = string_value(*error, "code");
        response.error_message = string_value(*error, "message");
    }
    const auto* operation = document.value().find("operation");
    if (operation != nullptr && !decode_operation(document.value(), response.operation)) {
        return failure("client_operation_result_invalid", "command response contains an invalid operation result");
    }
    return facman::core::Result<CommandResponse>::success(std::move(response));
}

facman::core::Result<CommandResponse> terminal_response(
    const CommandRequest& request,
    int status,
    facman::core::OutcomeKind command_outcome_kind,
    std::string command_outcome,
    std::string error_code,
    std::string error_message,
    OperationOutcome operation_outcome)
{
    CommandResponse response;
    response.status = status;
    response.outcome_kind = command_outcome_kind;
    response.outcome = std::move(command_outcome);
    response.error_code = std::move(error_code);
    response.error_message = std::move(error_message);
    response.operation = operation_for(request, operation_outcome);
    return facman::core::Result<CommandResponse>::success(std::move(response));
}

facman::core::Result<CommandResponse> finalize_response(
    const CommandRequest& request,
    CommandResponse response,
    bool cancellation_after_dispatch)
{
    if (response.operation.operation_id.empty()) {
        OperationOutcome outcome = OperationOutcome::refused_before_effects;
        if (response.outcome_kind == facman::core::OutcomeKind::recovery_required) {
            outcome = OperationOutcome::recovery_required;
        } else if (response.status == 0) {
            outcome = cancellation_after_dispatch
                ? OperationOutcome::cancellation_requested_but_completed
                : OperationOutcome::completed;
        }
        response.operation = operation_for(request, outcome, &response);
    } else {
        if (!operation_result_valid(response.operation) ||
            response.operation.operation_id != request.operation_id ||
            response.operation.attempt_id != request.attempt_id) {
            return failure(
                "client_operation_identity_mismatch",
                "transport response operation identity does not match its request");
        }
        if (cancellation_after_dispatch &&
            response.operation.outcome == OperationOutcome::completed) {
            response.operation.outcome = OperationOutcome::cancellation_requested_but_completed;
        }
    }
    if (!operation_result_valid(response.operation)) {
        return failure("client_operation_result_invalid", "transport produced an invalid operation result");
    }
    return facman::core::Result<CommandResponse>::success(std::move(response));
}

} // namespace detail

const char* operation_outcome_name(OperationOutcome outcome) noexcept
{
    const ulk_string_view value = ulk_operation_outcome_name_v1(detail::native_outcome(outcome));
    return value.data == nullptr ? "outcome_unknown" : value.data;
}

bool operation_result_valid(const OperationResult& result) noexcept
{
    ulk_operation_result_v1 native {};
    native.struct_size = sizeof(native);
    native.identity.struct_size = sizeof(native.identity);
    native.identity.operation_id = detail::view(result.operation_id);
    native.identity.attempt_id = detail::view(result.attempt_id);
    native.outcome = detail::native_outcome(result.outcome);
    native.effects_may_have_occurred = result.effects_may_have_occurred ? 1 : 0;
    native.recovery.struct_size = sizeof(native.recovery);
    native.recovery.required = result.recovery.required ? 1 : 0;
    native.recovery.transaction_id = detail::view(result.recovery.transaction_id);
    native.recovery.inspect_command = detail::view(result.recovery.inspect_command);
    return ulk_operation_result_validate_v1(&native) == ULK_STATUS_OK;
}

std::string operation_result_json(const OperationResult& result)
{
    json::ObjectBuilder recovery;
    recovery.add_bool("required", result.recovery.required);
    recovery.add_string("transaction_id", result.recovery.transaction_id);
    recovery.add_string("inspect_command", result.recovery.inspect_command);
    json::ObjectBuilder operation;
    operation.add_string("schema", "ulk.operation_outcome.v1");
    operation.add_string("operation_id", result.operation_id);
    operation.add_string("attempt_id", result.attempt_id);
    operation.add_string("outcome", operation_outcome_name(result.outcome));
    operation.add_bool("effects_may_have_occurred", result.effects_may_have_occurred);
    operation.add_object("recovery", recovery);
    return operation.serialize();
}

std::string quote_json_string(const std::string& value)
{
    return facman::core::json::escape_string(value);
}

std::string CommandResponse::payload_string(const char* key) const
{
    return parsed_payload && parsed_payload->is_object()
        ? detail::string_value(*parsed_payload, key)
        : std::string();
}

std::string CommandResponse::payload_member_json(const char* key, const std::string& fallback) const
{
    if (!parsed_payload || !parsed_payload->is_object()) return fallback;
    const auto* field = parsed_payload->find(key);
    return field == nullptr ? fallback : field->serialize();
}

FacManClient::FacManClient(std::unique_ptr<Transport> transport) : transport_(std::move(transport)) {}

facman::core::Result<CommandResponse> FacManClient::execute(const CommandRequest& request)
{
    CommandRequest normalized = request;
    facman::platform::RandomIdGenerator ids;
    if (normalized.operation_id.empty()) normalized.operation_id = ids.next("op");
    if (normalized.attempt_id.empty()) normalized.attempt_id = ids.next("attempt");
    OperationResult identity_probe;
    identity_probe.operation_id = normalized.operation_id;
    identity_probe.attempt_id = normalized.attempt_id;
    if (!operation_result_valid(identity_probe)) {
        return detail::failure(
            "client_operation_identity_invalid",
            "operation_id and attempt_id must satisfy the Universal Launcher identity contract");
    }
    if (!transport_) {
        return detail::terminal_response(
            normalized,
            1,
            facman::core::OutcomeKind::unavailable,
            "unavailable",
            "client_transport_missing",
            "FacMan client transport is not configured",
            OperationOutcome::refused_before_effects);
    }
    if (detail::cancelled(normalized)) {
        return detail::terminal_response(
            normalized,
            1,
            facman::core::OutcomeKind::cancelled,
            "cancelled",
            "client_operation_cancelled",
            "command was cancelled before transport selection",
            OperationOutcome::cancelled_before_dispatch);
    }
    if (normalized.timeout.count() <= 0) {
        return detail::terminal_response(
            normalized,
            1,
            facman::core::OutcomeKind::invalid_argument,
            "invalid_argument",
            "client_timeout_invalid",
            "command timeout must be positive",
            OperationOutcome::refused_before_effects);
    }
    return transport_->execute(normalized);
}

const char* FacManClient::transport_name() const noexcept
{
    return transport_ ? transport_->name() : "missing";
}

} // namespace facman::client
