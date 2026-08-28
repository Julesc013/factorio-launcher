// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "frontend_session.h"

#include "fl_json.h"
#include "fl_system_services.h"

#include <algorithm>
#include <set>
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

facman::core::Error frontend_error(
    std::string code,
    std::string message,
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::invalid_argument)
{
    return {std::move(code), std::move(message), "$", kind};
}

bool sha256_text(const std::string& value) noexcept
{
    if (value.size() != 64U) return false;
    return std::all_of(value.begin(), value.end(), [](char byte) {
        return (byte >= '0' && byte <= '9') || (byte >= 'a' && byte <= 'f');
    });
}

bool allowed_projection_key(const std::string& key)
{
    static const std::set<std::string> known {
        "schema", "command", "snapshot_id", "revision", "freshness",
        "dependency_identities", "workspace_health", "selected_context", "page",
        "readiness", "specific_blockers", "available_semantic_actions",
        "active_operations", "last_run", "recovery", "support_classification",
        "backend_provider_identity", "package_identity"};
    return known.count(key) != 0U || key.rfind("x-", 0U) == 0U;
}

bool required_member(const json::Value& value, const char* key, bool object)
{
    const json::Value* member = value.find(key);
    return member != nullptr && (object ? member->is_object() : member->is_array());
}

std::vector<std::string> serialized_array(const json::Value& value, const char* key)
{
    std::vector<std::string> output;
    const json::Value* array = value.find(key);
    if (array == nullptr || !array->is_array()) return output;
    output.reserve(array->size());
    for (std::size_t index = 0; index < array->size(); ++index) {
        const json::Value* item = array->at(index);
        if (item != nullptr) output.push_back(item->serialize());
    }
    return output;
}

std::vector<json::Value> value_array(const json::Value& value, const char* key)
{
    std::vector<json::Value> output;
    const json::Value* array = value.find(key);
    if (array == nullptr || !array->is_array()) return output;
    output.reserve(array->size());
    for (std::size_t index = 0; index < array->size(); ++index) {
        const json::Value* item = array->at(index);
        if (item != nullptr) output.push_back(*item);
    }
    return output;
}

facman::core::Result<FrontendQueryResult> decode_query_result(
    const FrontendExecution& execution)
{
    if (!execution.response) {
        return facman::core::Result<FrontendQueryResult>::failure(
            execution.response.error());
    }
    const auto& response = execution.response.value();
    if (!response.ok()) {
        return facman::core::Result<FrontendQueryResult>::failure(frontend_error(
            response.error_code.empty() ? "frontend_query_refused" : response.error_code,
            response.error_message.empty() ? "Backend refused presentation query" : response.error_message,
            response.outcome_kind));
    }
    if (!response.parsed_payload || !response.parsed_payload->is_object()) {
        return facman::core::Result<FrontendQueryResult>::failure(frontend_error(
            "frontend_snapshot_invalid", "Presentation query returned no object snapshot"));
    }
    const json::Value& value = *response.parsed_payload;
    for (const std::string& key : value.object_keys()) {
        if (!allowed_projection_key(key)) {
            return facman::core::Result<FrontendQueryResult>::failure(frontend_error(
                "frontend_snapshot_unknown_field",
                "Presentation snapshot contains an ordinary unknown field"));
        }
    }
    const std::string schema = string_field(value, "schema");
    const std::string command = string_field(value, "command");
    const std::string revision = string_field(value, "revision");
    if (schema != "facman.presentation_snapshot.v1" || command != "presentation.query" ||
        !sha256_text(revision) || string_field(value, "snapshot_id").empty() ||
        !required_member(value, "freshness", true) ||
        !required_member(value, "dependency_identities", true) ||
        !required_member(value, "workspace_health", true) ||
        !required_member(value, "selected_context", true) ||
        !required_member(value, "page", true) ||
        !required_member(value, "specific_blockers", false) ||
        !required_member(value, "available_semantic_actions", false) ||
        !required_member(value, "active_operations", false) ||
        !required_member(value, "last_run", true) ||
        !required_member(value, "recovery", true) ||
        !required_member(value, "backend_provider_identity", true) ||
        !required_member(value, "package_identity", true)) {
        return facman::core::Result<FrontendQueryResult>::failure(frontend_error(
            "frontend_snapshot_invalid",
            "Presentation snapshot does not satisfy the typed v1 projection boundary"));
    }

    using Snapshot = facman::contracts::presentation_v1::PresentationSnapshot;
    Snapshot snapshot;
    snapshot.schema = schema;
    snapshot.command = command;
    snapshot.snapshot_id = string_field(value, "snapshot_id");
    snapshot.revision = revision;
    snapshot.support_classification = string_field(value, "support_classification");
    snapshot.freshness = *value.find("freshness");
    snapshot.dependency_identities = *value.find("dependency_identities");
    snapshot.workspace_health = *value.find("workspace_health");
    snapshot.selected_context = *value.find("selected_context");
    snapshot.page = *value.find("page");
    const json::Value* readiness = value.find("readiness");
    if (readiness != nullptr && !readiness->is_null()) snapshot.readiness = *readiness;
    snapshot.specific_blockers = value_array(value, "specific_blockers");
    snapshot.available_semantic_actions = value_array(value, "available_semantic_actions");
    snapshot.active_operations = value_array(value, "active_operations");
    snapshot.last_run = *value.find("last_run");
    snapshot.recovery = *value.find("recovery");
    snapshot.backend_provider_identity = *value.find("backend_provider_identity");
    snapshot.package_identity = *value.find("package_identity");
    snapshot.raw_canonical_json = response.payload;

    FrontendQueryResult result;
    result.snapshot = std::move(snapshot);
    result.raw_snapshot = response.payload;
    result.revision = revision;
    result.request_id = execution.request_id;
    result.operation_id = execution.operation_id;
    result.attempt_id = execution.attempt_id;
    return facman::core::Result<FrontendQueryResult>::success(std::move(result));
}

bool contains_identity(
    const json::Value& value,
    const char* key,
    const std::string& identity)
{
    if (value.is_object()) {
        if (string_field(value, key) == identity) return true;
        for (const std::string& name : value.object_keys()) {
            const json::Value* child = value.find(name);
            if (child != nullptr && contains_identity(*child, key, identity)) return true;
        }
    } else if (value.is_array()) {
        for (std::size_t index = 0; index < value.size(); ++index) {
            const json::Value* child = value.at(index);
            if (child != nullptr && contains_identity(*child, key, identity)) return true;
        }
    }
    return false;
}

std::set<std::string> descriptor_input_fields(
    const std::string& raw_snapshot,
    const std::string& action_id)
{
    std::set<std::string> output;
    auto snapshot = json::parse(raw_snapshot);
    const json::Value* actions = snapshot && snapshot.value().is_object()
        ? snapshot.value().find("available_semantic_actions") : nullptr;
    if (actions == nullptr || !actions->is_array()) return output;
    for (std::size_t index = 0; index < actions->size(); ++index) {
        const json::Value* action = actions->at(index);
        if (action == nullptr || !action->is_object() ||
            string_field(*action, "action_id") != action_id) continue;
        const json::Value* fields = action->find("input_fields");
        if (fields == nullptr || !fields->is_array()) return output;
        for (std::size_t field_index = 0; field_index < fields->size(); ++field_index) {
            const json::Value* field = fields->at(field_index);
            if (field == nullptr || !field->is_object()) continue;
            const std::string id = string_field(*field, "field_id");
            if (!id.empty()) output.insert(id);
        }
        return output;
    }
    return output;
}

void allocate_action_identities(FrontendActionRequest& request)
{
    facman::platform::RandomIdGenerator ids;
    if (request.request_id.empty()) request.request_id = ids.next("request");
    if (request.operation_id.empty()) request.operation_id = ids.next("op");
    if (request.attempt_id.empty()) request.attempt_id = ids.next("attempt");
}

FrontendActionExecution rejected_action(
    FrontendActionRequest request,
    facman::core::Error error)
{
    allocate_action_identities(request);
    return FrontendActionExecution(FrontendExecution(
        std::move(request.request_id),
        std::move(request.operation_id),
        std::move(request.attempt_id),
        facman::core::Result<facman::client::CommandResponse>::failure(std::move(error))));
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

FrontendActionExecution::FrontendActionExecution(FrontendExecution value)
    : execution(std::move(value))
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

FrontendExecution FrontendSession::advanced_execute(FrontendInvocation invocation)
{
    if (invocation.command == "presentation.action") {
        auto payload = json::parse(invocation.payload);
        if (payload && payload.value().is_object()) {
            const std::string payload_request_id =
                string_field(payload.value(), "request_id");
            const std::string payload_operation_id =
                string_field(payload.value(), "durable_operation_id");
            const std::string payload_attempt_id =
                string_field(payload.value(), "attempt_id");
            const bool conflict =
                (!invocation.request_id.empty() && !payload_request_id.empty() &&
                    invocation.request_id != payload_request_id) ||
                (!invocation.operation_id.empty() && !payload_operation_id.empty() &&
                    invocation.operation_id != payload_operation_id) ||
                (!invocation.attempt_id.empty() && !payload_attempt_id.empty() &&
                    invocation.attempt_id != payload_attempt_id);
            if (conflict) {
                auto refused = facman::core::Result<facman::client::CommandResponse>::failure(
                    frontend_error(
                        "frontend_invocation_identity_conflict",
                        "Invocation identities conflict with the semantic action payload"));
                return FrontendExecution(
                    std::move(invocation.request_id),
                    std::move(invocation.operation_id),
                    std::move(invocation.attempt_id),
                    std::move(refused));
            }
            if (invocation.request_id.empty()) invocation.request_id = payload_request_id;
            if (invocation.operation_id.empty()) invocation.operation_id = payload_operation_id;
            if (invocation.attempt_id.empty()) invocation.attempt_id = payload_attempt_id;
        }
    }
    facman::platform::RandomIdGenerator ids;
    if (invocation.request_id.empty()) invocation.request_id = ids.next("request");
    if (invocation.operation_id.empty()) invocation.operation_id = ids.next("op");
    if (invocation.attempt_id.empty()) invocation.attempt_id = ids.next("attempt");
    facman::client::CommandRequest request {
        invocation.command, invocation.payload, invocation.dry_run};
    request.request_id = invocation.request_id;
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

FrontendExecution FrontendSession::execute(FrontendInvocation invocation)
{
    return advanced_execute(std::move(invocation));
}

facman::core::Result<FrontendQueryResult> FrontendSession::query(
    FrontendQueryRequest request)
{
    json::ObjectBuilder payload;
    payload.add_string("scope", request.scope);
    if (!request.target_instance_id.empty()) {
        payload.add_string("selected_instance_id", request.target_instance_id);
    }
    if (!request.search.empty()) payload.add_string("search", request.search);
    if (!request.known_revision.empty()) {
        if (!sha256_text(request.known_revision)) {
            return facman::core::Result<FrontendQueryResult>::failure(frontend_error(
                "frontend_known_revision_invalid",
                "known_revision must be a lowercase SHA-256 digest"));
        }
        payload.add_string("known_revision", request.known_revision);
    }
    FrontendInvocation invocation;
    invocation.command = "presentation.query";
    invocation.payload = payload.serialize();
    invocation.request_id = std::move(request.request_id);
    invocation.operation_id = std::move(request.operation_id);
    invocation.attempt_id = std::move(request.attempt_id);
    invocation.cancellation = std::move(request.cancellation);
    invocation.progress = std::move(request.progress);
    invocation.timeout = request.deadline;
    FrontendExecution execution = advanced_execute(std::move(invocation));
    auto decoded = decode_query_result(execution);
    if (decoded) current_snapshot_revision_ = decoded.value().revision;
    return decoded;
}

facman::core::Result<FrontendSessionIdentity> FrontendSession::negotiate(
    FrontendNegotiationRequest request)
{
    FrontendQueryRequest query_request;
    query_request.request_id = std::move(request.request_id);
    query_request.operation_id = std::move(request.operation_id);
    query_request.attempt_id = std::move(request.attempt_id);
    query_request.scope = std::move(request.scope);
    query_request.target_instance_id = std::move(request.target_instance_id);
    query_request.search = std::move(request.search);
    query_request.known_revision = std::move(request.known_revision);
    query_request.deadline = request.deadline;
    query_request.cancellation = std::move(request.cancellation);
    query_request.progress = std::move(request.progress);
    auto queried = query(std::move(query_request));
    if (!queried) {
        return identity_failure(
            queried.error().code, queried.error().message, queried.error().kind);
    }
    auto snapshot = json::parse(queried.value().raw_snapshot);
    if (!snapshot || !snapshot.value().is_object()) {
        return identity_failure(
            "frontend_session_identity_invalid",
            "Presentation negotiation returned no typed snapshot");
    }
    const json::Value* backend = snapshot.value().find("backend_provider_identity");
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
    identity.snapshot_revision = queried.value().revision;
    identity.raw_snapshot = queried.value().raw_snapshot;
    if (identity.factorio_launcher_revision.empty() ||
        identity.universal_launcher_revision.empty() ||
        identity.universal_setup_revision.empty() ||
        !sha256_text(identity.command_catalog_sha256) ||
        !sha256_text(identity.contract_set_sha256) ||
        identity.last_run_provider.empty() ||
        !sha256_text(identity.snapshot_revision)) {
        return identity_failure(
            "frontend_session_identity_invalid",
            "Presentation snapshot contains incomplete backend/provider identity");
    }
    negotiated_identity_ = identity;
    return facman::core::Result<FrontendSessionIdentity>::success(std::move(identity));
}

facman::core::Result<FrontendSessionIdentity> FrontendSession::negotiate(
    const std::string& scope,
    const std::string& selected_instance_id,
    const std::string& search)
{
    FrontendNegotiationRequest request;
    request.scope = scope;
    request.target_instance_id = selected_instance_id;
    request.search = search;
    return negotiate(std::move(request));
}

FrontendActionExecution FrontendSession::act(FrontendActionRequest request)
{
    allocate_action_identities(request);
    if (request.action_id.empty() || request.scope.empty()) {
        return rejected_action(std::move(request), frontend_error(
            "frontend_action_invalid", "action_id and scope are required"));
    }
    if (!sha256_text(request.expected_snapshot_revision)) {
        return rejected_action(std::move(request), frontend_error(
            "frontend_expected_revision_invalid",
            "expected_snapshot_revision must be a lowercase SHA-256 digest"));
    }
    if (request.explain && !request.dry_run) {
        return rejected_action(std::move(request), frontend_error(
            "frontend_action_disposition_invalid",
            "explain disposition cannot authorize effects"));
    }
    if (!request.dry_run && (request.idempotency_key.empty() ||
            request.operation_id.empty() || request.attempt_id.empty() ||
            request.confirmation != "explicit")) {
        return rejected_action(std::move(request), frontend_error(
            "frontend_effect_identity_required",
            "Effectful actions require idempotency, operation, attempt, and explicit confirmation"));
    }
    static const std::set<std::string> allowed_inputs {
        "selected_instance_id", "installation_id", "installation_path",
        "new_instance_id", "display_name", "template_id", "profile_id",
        "mod_identity", "save", "output_path", "source_data_root",
        "transaction_id"};
    for (const auto& item : request.inputs) {
        if (allowed_inputs.count(item.first) == 0U) {
            return rejected_action(std::move(request), frontend_error(
                "frontend_action_input_unknown",
                "Semantic action input contains an ordinary unknown field"));
        }
    }
    if (!request.inputs.empty() || !request.roots.empty()) {
        FrontendQueryRequest descriptor_query;
        descriptor_query.scope = request.scope;
        descriptor_query.target_instance_id = request.target_instance_id;
        descriptor_query.deadline = request.deadline;
        auto described = query(std::move(descriptor_query));
        if (!described) {
            return rejected_action(std::move(request), described.error());
        }
        if (described.value().revision == request.expected_snapshot_revision) {
            const auto declared = descriptor_input_fields(
                described.value().raw_snapshot, request.action_id);
            for (const auto& item : request.inputs) {
                if (declared.count(item.first) == 0U) {
                    return rejected_action(std::move(request), frontend_error(
                        "frontend_action_input_not_declared",
                        "Semantic action input is not declared by the backend descriptor"));
                }
            }
            if (!request.roots.empty() && declared.count("roots") == 0U) {
                return rejected_action(std::move(request), frontend_error(
                    "frontend_action_input_not_declared",
                    "Semantic action roots are not declared by the backend descriptor"));
            }
        }
    }
    const auto input_value = [&request](const char* key) {
        const auto found = request.inputs.find(key);
        return found == request.inputs.end() ? std::string() : found->second;
    };
    const std::string selected_instance = request.target_instance_id.empty()
        ? input_value("selected_instance_id") : request.target_instance_id;
    const std::string installation_id = request.target_installation_id.empty()
        ? input_value("installation_id") : request.target_installation_id;
    if ((!request.target_instance_id.empty() &&
            !input_value("selected_instance_id").empty() &&
            input_value("selected_instance_id") != request.target_instance_id) ||
        (!request.target_installation_id.empty() &&
            !input_value("installation_id").empty() &&
            input_value("installation_id") != request.target_installation_id)) {
        return rejected_action(std::move(request), frontend_error(
            "frontend_action_target_conflict",
            "Named action target and descriptor input name different identities"));
    }

    json::ObjectBuilder payload;
    payload.add_string("action_id", request.action_id);
    payload.add_string("scope", request.scope);
    payload.add_string("expected_snapshot_revision", request.expected_snapshot_revision);
    payload.add_string("request_id", request.request_id);
    if (!selected_instance.empty()) payload.add_string("selected_instance_id", selected_instance);
    if (!request.idempotency_key.empty()) {
        payload.add_string("idempotency_key", request.idempotency_key);
    }
    payload.add_string("durable_operation_id", request.operation_id);
    payload.add_string("attempt_id", request.attempt_id);
    if (!request.confirmation.empty()) payload.add_string("confirmation", request.confirmation);
    if (!installation_id.empty()) payload.add_string("installation_id", installation_id);
    for (const auto& item : request.inputs) {
        if (item.first == "selected_instance_id" || item.first == "installation_id") continue;
        payload.add_string(item.first, item.second);
    }
    if (!request.roots.empty()) {
        json::ArrayBuilder roots;
        for (const std::string& root : request.roots) roots.add_string(root);
        payload.add_array("roots", roots);
    }

    FrontendInvocation invocation;
    invocation.command = "presentation.action";
    invocation.payload = payload.serialize();
    invocation.dry_run = request.dry_run || request.explain;
    invocation.request_id = request.request_id;
    invocation.operation_id = request.operation_id;
    invocation.attempt_id = request.attempt_id;
    invocation.cancellation = std::move(request.cancellation);
    invocation.progress = std::move(request.progress);
    invocation.timeout = request.deadline;
    FrontendActionExecution output(advanced_execute(std::move(invocation)));
    if (!output.execution.response ||
        !output.execution.response.value().parsed_payload ||
        !output.execution.response.value().parsed_payload->is_object()) return output;
    const json::Value& value = *output.execution.response.value().parsed_payload;
    if (string_field(value, "schema") != "facman.semantic_action_result.v1") return output;
    const json::Value* operation = value.find("operation");
    const json::Value* action_payload = value.find("action_payload");
    const json::Value* replacement = value.find("replacement_snapshot");
    const json::Value* invalidation = value.find("invalidation");
    if (operation == nullptr || !operation->is_object()) return output;
    facman::contracts::presentation_v1::SemanticActionResult result;
    result.schema = string_field(value, "schema");
    result.command = string_field(value, "command");
    result.action_id = string_field(value, "action_id");
    result.request_id = string_field(value, "request_id");
    result.outcome = string_field(value, "outcome");
    result.operation = *operation;
    result.effects = serialized_array(value, "effects");
    result.diagnostics = serialized_array(value, "diagnostics");
    result.problems = value_array(value, "problems");
    if (action_payload != nullptr && !action_payload->is_null()) {
        result.action_payload = *action_payload;
    }
    if (replacement != nullptr && !replacement->is_null()) {
        result.replacement_snapshot = *replacement;
    }
    if (invalidation != nullptr && !invalidation->is_null()) {
        result.invalidation = *invalidation;
    }
    output.raw_result = value.serialize();
    result.raw_canonical_json = output.raw_result;
    output.result = std::move(result);
    return output;
}

facman::core::Result<FrontendOperationProjection> FrontendSession::inspect(
    FrontendOperationInspectRequest request)
{
    if (request.target_operation_id.empty()) {
        return facman::core::Result<FrontendOperationProjection>::failure(frontend_error(
            "frontend_operation_identity_required", "target_operation_id is required"));
    }
    FrontendQueryRequest query_request;
    query_request.request_id = std::move(request.request_id);
    query_request.operation_id = std::move(request.operation_id);
    query_request.attempt_id = std::move(request.attempt_id);
    query_request.scope = "activity_recovery";
    query_request.target_instance_id = request.target_instance_id;
    query_request.deadline = request.deadline;
    query_request.cancellation = std::move(request.cancellation);
    query_request.progress = std::move(request.progress);
    auto queried = query(std::move(query_request));
    if (!queried) {
        return facman::core::Result<FrontendOperationProjection>::failure(queried.error());
    }
    auto snapshot = json::parse(queried.value().raw_snapshot);
    if (!snapshot || !snapshot.value().is_object()) {
        return facman::core::Result<FrontendOperationProjection>::failure(frontend_error(
            "frontend_snapshot_invalid", "Operation inspection snapshot is invalid"));
    }
    const json::Value* active = snapshot.value().find("active_operations");
    if (active != nullptr && active->is_array()) {
        for (std::size_t index = 0; index < active->size(); ++index) {
            const json::Value* item = active->at(index);
            if (item == nullptr || !item->is_object() ||
                string_field(*item, "operation_id") != request.target_operation_id) continue;
            if (string_field(*item, "kind") != "launch_session") {
                return facman::core::Result<FrontendOperationProjection>::failure(frontend_error(
                    "frontend_operation_class_unsupported",
                    "Typed inspection supports launch-session operations only"));
            }
            if (!request.target_instance_id.empty() &&
                string_field(*item, "target_instance_id") != request.target_instance_id) {
                return facman::core::Result<FrontendOperationProjection>::failure(frontend_error(
                    "frontend_operation_target_mismatch",
                    "Operation projection names a different target instance"));
            }
            FrontendOperationProjection projection;
            projection.kind = string_field(*item, "kind");
            projection.operation_id = string_field(*item, "operation_id");
            projection.attempt_id = string_field(*item, "attempt_id");
            projection.target_instance_id = string_field(*item, "target_instance_id");
            projection.state = string_field(*item, "state");
            projection.authority = string_field(*item, "authority_scope");
            projection.snapshot_revision = queried.value().revision;
            projection.raw_projection = item->serialize();
            return facman::core::Result<FrontendOperationProjection>::success(
                std::move(projection));
        }
    }
    const json::Value* last_run = snapshot.value().find("last_run");
    if (last_run != nullptr && last_run->is_object() &&
        contains_identity(*last_run, "operation_id", request.target_operation_id)) {
        FrontendOperationProjection projection;
        projection.kind = "launch_session";
        projection.operation_id = request.target_operation_id;
        projection.target_instance_id = request.target_instance_id;
        projection.state = "terminal";
        projection.authority = string_field(*last_run, "provider_id");
        projection.snapshot_revision = queried.value().revision;
        projection.raw_projection = last_run->serialize();
        const json::Value* record = last_run->find("record");
        const json::Value* terminal = record != nullptr && record->is_object()
            ? record->find("terminal_result") : nullptr;
        if (terminal != nullptr && terminal->is_object()) {
            projection.terminal_outcome = string_field(*terminal, "outcome");
            projection.attempt_id = string_field(*terminal, "attempt_id");
        }
        return facman::core::Result<FrontendOperationProjection>::success(
            std::move(projection));
    }
    return facman::core::Result<FrontendOperationProjection>::failure(frontend_error(
        "frontend_operation_not_found",
        "No live or authoritative terminal projection matches target_operation_id",
        facman::core::OutcomeKind::not_found));
}

FrontendActionExecution FrontendSession::cancel(FrontendCancellationRequest request)
{
    FrontendActionRequest action;
    action.request_id = std::move(request.request_id);
    action.action_id = "sessions.stop";
    action.scope = "activity_recovery";
    action.target_instance_id = request.target_instance_id;
    action.target_operation_id = request.target_operation_id;
    action.expected_snapshot_revision = request.expected_snapshot_revision;
    action.idempotency_key = request.idempotency_key;
    action.operation_id = request.operation_id;
    action.attempt_id = request.attempt_id;
    action.deadline = request.deadline;
    action.dry_run = request.dry_run;
    action.explain = request.explain;
    action.confirmation = request.confirmation;
    action.cancellation = std::move(request.cancellation);
    action.progress = std::move(request.progress);
    allocate_action_identities(action);
    if (action.target_operation_id.empty() || action.target_instance_id.empty()) {
        return rejected_action(std::move(action), frontend_error(
            "frontend_cancellation_target_required",
            "Cancellation requires target_operation_id and target_instance_id"));
    }
    FrontendOperationInspectRequest inspect_request;
    inspect_request.target_operation_id = action.target_operation_id;
    inspect_request.target_instance_id = action.target_instance_id;
    inspect_request.deadline = action.deadline;
    auto projection = inspect(std::move(inspect_request));
    if (!projection) {
        return rejected_action(std::move(action), projection.error());
    }
    if (projection.value().state == "terminal") {
        return rejected_action(std::move(action), frontend_error(
            "frontend_operation_already_terminal",
            "Authoritative Last Run already records a terminal outcome",
            facman::core::OutcomeKind::conflict));
    }
    return act(std::move(action));
}

facman::core::Result<FrontendCapabilitySnapshot> FrontendSession::capabilities()
{
    if (!negotiated_identity_) {
        auto identity = negotiate(FrontendNegotiationRequest {});
        if (!identity) {
            return facman::core::Result<FrontendCapabilitySnapshot>::failure(
                identity.error());
        }
    }
    FrontendCapabilitySnapshot snapshot;
    snapshot.transport = transport_name();
    snapshot.typed_methods = {
        "negotiate", "query", "act", "inspect", "cancel", "capabilities",
        "advanced_execute"};
    snapshot.command_catalog_sha256 = negotiated_identity_->command_catalog_sha256;
    snapshot.contract_set_sha256 = negotiated_identity_->contract_set_sha256;
    snapshot.backend_identity = *negotiated_identity_;
    json::ArrayBuilder protocols;
    protocols.add_unsigned_integer(2U);
    json::ArrayBuilder methods;
    for (const std::string& method : snapshot.typed_methods) methods.add_string(method);
    auto backend = json::parse(snapshot.backend_identity.json());
    json::ObjectBuilder output;
    output.add_string("schema", snapshot.schema);
    output.add_array("transport_protocol_versions", protocols);
    output.add_string("presentation_schema", snapshot.presentation_schema);
    output.add_string("semantic_action_schema", snapshot.semantic_action_schema);
    output.add_string("transport", snapshot.transport);
    output.add_array("typed_methods", methods);
    output.add_string("command_catalog_sha256", snapshot.command_catalog_sha256);
    output.add_string("contract_set_sha256", snapshot.contract_set_sha256);
    if (backend) output.add_value("backend_identity", backend.value());
    snapshot.raw_json = output.serialize();
    return facman::core::Result<FrontendCapabilitySnapshot>::success(
        std::move(snapshot));
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
