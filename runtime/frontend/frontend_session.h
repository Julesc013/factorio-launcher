// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_RUNTIME_FRONTEND_FRONTEND_SESSION_H
#define FACMAN_RUNTIME_FRONTEND_FRONTEND_SESSION_H

#include "facman_client.h"

#include <chrono>
#include <filesystem>
#include <memory>
#include <string>
#include <vector>

namespace facman::frontend {

enum class TransportKind { direct, process, daemon };

struct FrontendSessionOptions {
    std::filesystem::path workspace;
    TransportKind transport = TransportKind::direct;
    std::filesystem::path process_executable;
    std::chrono::milliseconds timeout {std::chrono::minutes(5)};
};

struct FrontendInvocation {
    std::string command;
    std::string payload = "{}";
    bool dry_run = true;
    std::string request_id;
    std::string operation_id;
    std::string attempt_id;
    std::shared_ptr<facman::client::CancellationToken> cancellation;
    std::shared_ptr<facman::client::ProgressSink> progress;
    std::chrono::milliseconds timeout {0};
};

struct FrontendExecution {
    FrontendExecution(
        std::string request,
        std::string operation,
        std::string attempt,
        facman::core::Result<facman::client::CommandResponse> result);

    std::string request_id;
    std::string operation_id;
    std::string attempt_id;
    facman::core::Result<facman::client::CommandResponse> response;
    std::string correlation_json() const;
};

struct FrontendSessionIdentity {
    std::string transport;
    std::string factorio_launcher_revision;
    std::string universal_launcher_revision;
    std::string universal_setup_revision;
    std::string command_catalog_sha256;
    std::string contract_set_sha256;
    std::string last_run_provider;
    std::string snapshot_revision;
    std::string raw_snapshot;

    std::string json() const;
};

class FrontendSession {
public:
    explicit FrontendSession(FrontendSessionOptions options);

    FrontendExecution execute(FrontendInvocation invocation);
    facman::core::Result<FrontendSessionIdentity> negotiate(
        const std::string& scope = "launch_deck",
        const std::string& selected_instance_id = {},
        const std::string& search = {});

    const std::string& current_snapshot_revision() const noexcept {
        return current_snapshot_revision_;
    }
    const char* transport_name() const noexcept;

private:
    FrontendSessionOptions options_;
    facman::client::FacManClient client_;
    std::string current_snapshot_revision_;
};

const char* transport_kind_name(TransportKind kind) noexcept;
facman::core::Result<TransportKind> parse_transport_kind(const std::string& value);

} // namespace facman::frontend

#endif
