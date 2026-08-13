// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "frontend_session.h"

#include "fl_json.h"
#include "fl_system_services.h"

#include <utility>

namespace facman::frontend {
namespace json = facman::core::json;

namespace {

std::unique_ptr<facman::client::Transport> make_transport(
    const FrontendSessionOptions& options)
{
    if (options.transport == TransportKind::process) {
        return std::make_unique<facman::client::CliProcessTransport>(
            options.process_executable, options.workspace);
    }
    if (options.transport == TransportKind::daemon) {
        return std::make_unique<facman::client::DaemonTransport>();
    }
    return std::make_unique<facman::client::DirectFlbTransport>(options.workspace);
}

std::string string_field(const json::Value& object, const char* name)
{
    const json::Value* value = object.find(name);
    if (value == nullptr || !value->is_string()) return {};
    auto text = value->string_value();
    return text ? text.take_value() : std::string();
}

facman::core::Result<FrontendSessionIdentity> identity_failure(
    std::string code,
    std::string message,
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::internal_error)
{
    return facman::core::Result<FrontendSessionIdentity>::failure(
        {std::move(code), std::move(message), "$", kind});
}

} // namespace

FrontendExecution::FrontendExecution(
    std::string request,
    std::string operation,
    std::string attempt,
    facman::core::Result<facman::client::CommandResponse> result)
    : request_id(std::move(request)),
      operation_id(std::move(operation)),
      attempt_id(std::move(attempt)),
      response(std::move(result))
{
}

std::string FrontendExecution::correlation_json() const
{
    json::ObjectBuilder output;
    output.add_string("schema", "facman.frontend_correlation.v1");
    output.add_string("request_id", request_id);
    output.add_string("operation_id", operation_id);
    output.add_string("attempt_id", attempt_id);
    output.add_string("outcome", response
        ? response.value().outcome
        : facman::core::outcome_kind_name(response.error().kind));
    if (response) {
        output.add_string(
            "operation_outcome",
            facman::client::operation_outcome_name(response.value().operation.outcome));
    } else {
        output.add_string("operation_outcome", "refused_before_effects");
    }
    output.add_bool("redacted", true);
    return output.serialize();
}

std::string FrontendSessionIdentity::json() const
{
    json::ArrayBuilder protocols;
    protocols.add_unsigned_integer(2U);
    json::ObjectBuilder output;
    output.add_string("schema", "facman.frontend_session_identity.v1");
    output.add_string("transport", transport);
    output.add_array("transport_protocol_versions", protocols);
    output.add_string("presentation_schema", "facman.presentation_snapshot.v1");
    output.add_string("factorio_launcher_revision", factorio_launcher_revision);
    output.add_string("universal_launcher_revision", universal_launcher_revision);
    output.add_string("universal_setup_revision", universal_setup_revision);
    output.add_string("command_catalog_sha256", command_catalog_sha256);
    output.add_string("contract_set_sha256", contract_set_sha256);
    output.add_string("last_run_provider", last_run_provider);
    output.add_string("snapshot_revision", snapshot_revision);
    output.add_bool("unknown_additive_fields_preserved", true);
    return output.serialize();
}

FrontendSession::FrontendSession(FrontendSessionOptions options)
    : options_(std::move(options)),
      client_(make_transport(options_))
{
}

FrontendExecution FrontendSession::execute(FrontendInvocation invocation)
{
    facman::platform::RandomIdGenerator ids;
    if (invocation.request_id.empty()) invocation.request_id = ids.next("request");
    if (invocation.operation_id.empty()) invocation.operation_id = ids.next("op");
    if (invocation.attempt_id.empty()) invocation.attempt_id = ids.next("attempt");
    facman::client::CommandRequest request {
        invocation.command, invocation.payload, invocation.dry_run};
    request.operation_id = invocation.operation_id;
    request.attempt_id = invocation.attempt_id;
    request.cancellation = std::move(invocation.cancellation);
    request.progress = std::move(invocation.progress);
    request.timeout = invocation.timeout.count() == 0 ? options_.timeout : invocation.timeout;
    auto response = client_.execute(request);
    return FrontendExecution(
        std::move(invocation.request_id),
        std::move(invocation.operation_id),
        std::move(invocation.attempt_id),
        std::move(response));
}

facman::core::Result<FrontendSessionIdentity> FrontendSession::negotiate(
    const std::string& scope,
    const std::string& selected_instance_id,
    const std::string& search)
{
    json::ObjectBuilder request;
    request.add_string("scope", scope);
    if (!selected_instance_id.empty()) {
        request.add_string("selected_instance_id", selected_instance_id);
    }
    if (!search.empty()) request.add_string("search", search);
    FrontendInvocation invocation;
    invocation.command = "presentation.query";
    invocation.payload = request.serialize();
    FrontendExecution execution = execute(std::move(invocation));
    if (!execution.response) {
        return identity_failure(
            execution.response.error().code,
            execution.response.error().message,
            execution.response.error().kind);
    }
    const auto& response = execution.response.value();
    if (!response.ok()) {
        return identity_failure(
            response.error_code.empty() ? "frontend_session_negotiation_refused" : response.error_code,
            response.error_message.empty() ? "Backend refused frontend-session negotiation" : response.error_message,
            response.outcome_kind);
    }
    if (!response.parsed_payload || !response.parsed_payload->is_object()) {
        return identity_failure(
            "frontend_session_identity_invalid",
            "Presentation negotiation returned no typed snapshot");
    }
    const json::Value& snapshot = *response.parsed_payload;
    if (string_field(snapshot, "schema") != "facman.presentation_snapshot.v1") {
        return identity_failure(
            "frontend_session_protocol_incompatible",
            "Backend presentation schema is outside the supported range",
            facman::core::OutcomeKind::unavailable);
    }
    const json::Value* backend = snapshot.find("backend_provider_identity");
    if (backend == nullptr || !backend->is_object()) {
        return identity_failure(
            "frontend_session_identity_invalid",
            "Presentation snapshot omits backend/provider identity");
    }
    FrontendSessionIdentity identity;
    identity.transport = transport_name();
    identity.factorio_launcher_revision = string_field(*backend, "factorio_launcher_revision");
    identity.universal_launcher_revision = string_field(*backend, "universal_launcher_revision");
    identity.universal_setup_revision = string_field(*backend, "universal_setup_revision");
    identity.command_catalog_sha256 = string_field(*backend, "command_catalog_sha256");
    identity.contract_set_sha256 = string_field(*backend, "contract_set_sha256");
    identity.last_run_provider = string_field(*backend, "last_run_provider");
    identity.snapshot_revision = string_field(snapshot, "revision");
    identity.raw_snapshot = response.payload;
    if (identity.factorio_launcher_revision.empty() ||
        identity.universal_launcher_revision.empty() ||
        identity.universal_setup_revision.empty() ||
        identity.command_catalog_sha256.empty() ||
        identity.contract_set_sha256.empty() ||
        identity.last_run_provider.empty() ||
        identity.snapshot_revision.empty()) {
        return identity_failure(
            "frontend_session_identity_invalid",
            "Presentation snapshot contains incomplete backend/provider identity");
    }
    current_snapshot_revision_ = identity.snapshot_revision;
    return facman::core::Result<FrontendSessionIdentity>::success(std::move(identity));
}

const char* FrontendSession::transport_name() const noexcept
{
    return transport_kind_name(options_.transport);
}

const char* transport_kind_name(TransportKind kind) noexcept
{
    switch (kind) {
    case TransportKind::direct: return "direct";
    case TransportKind::process: return "process";
    case TransportKind::daemon: return "daemon";
    }
    return "direct";
}

facman::core::Result<TransportKind> parse_transport_kind(const std::string& value)
{
    if (value == "direct") {
        return facman::core::Result<TransportKind>::success(TransportKind::direct);
    }
    if (value == "process") {
        return facman::core::Result<TransportKind>::success(TransportKind::process);
    }
    if (value == "daemon") {
        return facman::core::Result<TransportKind>::success(TransportKind::daemon);
    }
    return facman::core::Result<TransportKind>::failure({
        "frontend_transport_invalid",
        "Frontend transport must be direct, process, or daemon",
        "$.transport",
        facman::core::OutcomeKind::invalid_argument});
}

} // namespace facman::frontend
