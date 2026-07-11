#include "facman_client.h"

#include "fl_command_client_cabi.h"
#include "fl_json.h"
#include "fl_runtime_verify.h"
#include "flb/flb_api.h"

#include <cstring>
#include <utility>

namespace facman::client {
namespace {

facman::core::Result<CommandResponse> failure(std::string code, std::string message, std::string path = {})
{
    return facman::core::Result<CommandResponse>::failure(
        {std::move(code), std::move(message), std::move(path)});
}

ulk_string_view view(const std::string& text)
{
    return {text.data(), static_cast<ulk_size>(text.size())};
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
    limits.maximum_bytes = 16U * 1024U * 1024U;
    limits.maximum_depth = 64;
    limits.maximum_nodes = 250000;
    limits.maximum_string_bytes = 8U * 1024U * 1024U;
    auto document = facman::core::json::parse(envelope, limits);
    if (!document || !document.value().is_object()) {
        return failure("client_response_invalid", document ? "command response must be an object" : document.error().message);
    }
    CommandResponse response;
    response.status = status;
    response.envelope = std::move(envelope);
    const auto* payload = document.value().find("payload");
    if (payload != nullptr && !payload->is_null()) response.payload = payload->serialize();
    const auto* error = document.value().find("error");
    if (error != nullptr && error->is_object()) {
        response.error_code = string_value(*error, "code");
        response.error_message = string_value(*error, "message");
    }
    return facman::core::Result<CommandResponse>::success(std::move(response));
}

} // namespace

std::string quote_json_string(const std::string& value)
{
    return facman::core::json::escape_string(value);
}

std::string CommandResponse::payload_string(const char* key) const
{
    auto document = facman::core::json::parse(payload);
    return document && document.value().is_object()
        ? string_value(document.value(), key)
        : std::string();
}

std::string CommandResponse::payload_member_json(const char* key, const std::string& fallback) const
{
    auto document = facman::core::json::parse(payload);
    if (!document || !document.value().is_object()) return fallback;
    const auto* field = document.value().find(key);
    return field == nullptr ? fallback : field->serialize();
}

DirectFlbTransport::DirectFlbTransport(std::filesystem::path workspace)
    : workspace_(std::move(workspace))
{
}

facman::core::Result<CommandResponse> DirectFlbTransport::execute(const CommandRequest& request)
{
    if (request.command.empty()) return failure("client_request_invalid", "command must not be empty");
    const std::string workspace = workspace_.lexically_normal().string();
    flb_config_v1 config {};
    config.struct_size = sizeof(config);
    config.workspace_root = view(workspace);
    flb_context* context = nullptr;
    if (flb_context_create_v1(&config, &context) != ULK_STATUS_OK || context == nullptr) {
        return failure("client_context_create_failed", "Factorio binding context could not be created", workspace);
    }
    ulk_command_request_v1 native_request {};
    ulk_command_response_v1 native_response {};
    native_request.struct_size = sizeof(native_request);
    native_request.command_name = view(request.command);
    native_request.json_payload = view(request.json_payload);
    native_request.dry_run = request.dry_run ? 1 : 0;
    native_response.struct_size = sizeof(native_response);
    const int status = fl_command_client_execute_cabi_v1(context, &native_request, &native_response);
    std::string envelope;
    if (native_response.json_payload.data != nullptr) {
        envelope.assign(
            native_response.json_payload.data,
            native_response.json_payload.data + native_response.json_payload.size);
    }
    flb_context_destroy_v1(context);
    if (envelope.empty()) return failure("client_response_empty", "Factorio binding returned an empty response");
    return decode_response(status, std::move(envelope));
}

CliProcessTransport::CliProcessTransport(std::filesystem::path executable)
    : executable_(std::move(executable))
{
}

facman::core::Result<CommandResponse> CliProcessTransport::execute(const CommandRequest&)
{
    return failure(
        "cli_process_transport_unavailable",
        "CLI process compatibility transport is declared but not enabled for backend recursion",
        executable_.string());
}

facman::core::Result<CommandResponse> DaemonTransport::execute(const CommandRequest&)
{
    return failure("daemon_transport_unavailable", "Daemon transport is not implemented");
}

FacManClient::FacManClient(std::unique_ptr<Transport> transport) : transport_(std::move(transport)) {}

facman::core::Result<CommandResponse> FacManClient::execute(const CommandRequest& request)
{
    if (!transport_) return failure("client_transport_missing", "FacMan client transport is not configured");
    return transport_->execute(request);
}

const char* FacManClient::transport_name() const noexcept
{
    return transport_ ? transport_->name() : "missing";
}

} // namespace facman::client

extern "C" void facman_client_initialize_process(const char* executable_path)
{
    fl_runtime_set_executable_path(executable_path);
}
