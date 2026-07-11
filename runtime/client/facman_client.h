#ifndef FACMAN_RUNTIME_CLIENT_FACMAN_CLIENT_H
#define FACMAN_RUNTIME_CLIENT_FACMAN_CLIENT_H

#include "fl_result.h"

#include <filesystem>
#include <memory>
#include <string>

namespace facman::client {

struct CommandRequest {
    std::string command;
    std::string json_payload = "{}";
    bool dry_run = true;
};

struct CommandResponse {
    int status = 0;
    std::string envelope;
    std::string payload;
    std::string error_code;
    std::string error_message;
    bool ok() const noexcept { return status == 0; }
    std::string payload_string(const char* key) const;
    std::string payload_member_json(const char* key, const std::string& fallback = "null") const;
};

std::string quote_json_string(const std::string& value);

class Transport {
public:
    virtual ~Transport() = default;
    virtual facman::core::Result<CommandResponse> execute(const CommandRequest& request) = 0;
    virtual const char* name() const noexcept = 0;
};

class DirectFlbTransport final : public Transport {
public:
    explicit DirectFlbTransport(std::filesystem::path workspace);
    facman::core::Result<CommandResponse> execute(const CommandRequest& request) override;
    const char* name() const noexcept override { return "direct-flb"; }

private:
    std::filesystem::path workspace_;
};

class CliProcessTransport final : public Transport {
public:
    explicit CliProcessTransport(std::filesystem::path executable);
    facman::core::Result<CommandResponse> execute(const CommandRequest& request) override;
    const char* name() const noexcept override { return "cli-process-compatibility"; }

private:
    std::filesystem::path executable_;
};

class DaemonTransport final : public Transport {
public:
    facman::core::Result<CommandResponse> execute(const CommandRequest& request) override;
    const char* name() const noexcept override { return "daemon-unavailable"; }
};

class FacManClient {
public:
    explicit FacManClient(std::unique_ptr<Transport> transport);
    facman::core::Result<CommandResponse> execute(const CommandRequest& request);
    const char* transport_name() const noexcept;

private:
    std::unique_ptr<Transport> transport_;
};

} // namespace facman::client

#endif
