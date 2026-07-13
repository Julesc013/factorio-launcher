// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_client_internal.h"

#include <utility>

namespace facman::client {
namespace json = facman::core::json;

namespace detail {

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
    return facman::core::Result<CommandResponse>::success(std::move(response));
}

} // namespace detail

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
    if (!transport_) return detail::failure("client_transport_missing", "FacMan client transport is not configured");
    if (detail::cancelled(request)) {
        return detail::failure(
            "client_operation_cancelled",
            "command was cancelled before transport selection",
            {},
            facman::core::OutcomeKind::cancelled);
    }
    if (request.timeout.count() <= 0) return detail::failure("client_timeout_invalid", "command timeout must be positive");
    return transport_->execute(request);
}

const char* FacManClient::transport_name() const noexcept
{
    return transport_ ? transport_->name() : "missing";
}

} // namespace facman::client
