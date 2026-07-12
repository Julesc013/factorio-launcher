// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_RUNTIME_CLIENT_FACMAN_CLIENT_H
#define FACMAN_RUNTIME_CLIENT_FACMAN_CLIENT_H

#include "fl_result.h"
#include "fl_json.h"
#include "flb/flb_api.h"
#include "workspace_resolver.h"

#include <filesystem>
#include <atomic>
#include <chrono>
#include <memory>
#include <mutex>
#include <string>
#include <utility>

namespace facman::client {

class CancellationToken {
public:
    void request_cancellation() noexcept { cancelled_.store(true, std::memory_order_release); }
    bool cancellation_requested() const noexcept { return cancelled_.load(std::memory_order_acquire); }

private:
    std::atomic<bool> cancelled_ {false};
};

struct ProgressUpdate {
    std::string stage;
    std::uint64_t completed = 0;
    std::uint64_t total = 0;
};

class ProgressSink {
public:
    virtual ~ProgressSink() = default;
    virtual void report(const ProgressUpdate& update) noexcept = 0;
};

struct CommandRequest {
    CommandRequest() = default;
    CommandRequest(std::string command_value, std::string payload_value, bool dry_run_value)
        : command(std::move(command_value)),
          json_payload(std::move(payload_value)),
          dry_run(dry_run_value) {}

    std::string command;
    std::string json_payload = "{}";
    bool dry_run = true;
    std::shared_ptr<CancellationToken> cancellation;
    std::shared_ptr<ProgressSink> progress;
    std::chrono::milliseconds timeout {std::chrono::minutes(5)};
};

struct CommandResponse {
    int status = 0;
    facman::core::OutcomeKind outcome_kind = facman::core::OutcomeKind::internal_error;
    std::string outcome = "internal_error";
    std::string envelope;
    std::string payload;
    std::string error_code;
    std::string error_message;
    std::shared_ptr<facman::core::json::Value> parsed_payload;
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
    ~DirectFlbTransport() override;
    facman::core::Result<CommandResponse> execute(const CommandRequest& request) override;
    const char* name() const noexcept override { return "direct-flb"; }

private:
    std::filesystem::path workspace_;
    flb_context* context_ = nullptr;
    std::mutex mutex_;
};

class CliProcessTransport final : public Transport {
public:
    explicit CliProcessTransport(std::filesystem::path executable, std::filesystem::path workspace = {});
    facman::core::Result<CommandResponse> execute(const CommandRequest& request) override;
    const char* name() const noexcept override { return "cli-process-compatibility"; }

private:
    std::filesystem::path executable_;
    std::filesystem::path workspace_;
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
