// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_RUNTIME_FRONTEND_FRONTEND_SESSION_H
#define FACMAN_RUNTIME_FRONTEND_FRONTEND_SESSION_H

#include "facman_client.h"
#include "generated/presentation_contracts.v1.h"

#include <chrono>
#include <filesystem>
#include <map>
#include <memory>
#include <optional>
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

struct FrontendNegotiationRequest {
    std::string request_id;
    std::string operation_id;
    std::string attempt_id;
    std::string scope = "launch_deck";
    std::string target_instance_id;
    std::string search;
    std::string known_revision;
    std::chrono::milliseconds deadline {0};
    std::shared_ptr<facman::client::CancellationToken> cancellation;
    std::shared_ptr<facman::client::ProgressSink> progress;
};

struct FrontendQueryRequest {
    std::string request_id;
    std::string operation_id;
    std::string attempt_id;
    std::string scope = "launch_deck";
    std::string target_instance_id;
    std::string search;
    std::string known_revision;
    std::chrono::milliseconds deadline {0};
    std::shared_ptr<facman::client::CancellationToken> cancellation;
    std::shared_ptr<facman::client::ProgressSink> progress;
};

struct FrontendQueryResult {
    facman::contracts::presentation_v1::PresentationSnapshot snapshot;
    std::string raw_snapshot;
    std::string revision;
    std::string request_id;
    std::string operation_id;
    std::string attempt_id;
};

struct FrontendActionRequest {
    std::string request_id;
    std::string action_id;
    std::string scope;
    std::string target_instance_id;
    std::string target_installation_id;
    std::string target_operation_id;
    std::string expected_snapshot_revision;
    std::string idempotency_key;
    std::string operation_id;
    std::string attempt_id;
    std::chrono::milliseconds deadline {0};
    bool dry_run = true;
    bool explain = false;
    std::string confirmation;
    std::map<std::string, std::string> inputs;
    std::vector<std::string> roots;
    std::shared_ptr<facman::client::CancellationToken> cancellation;
    std::shared_ptr<facman::client::ProgressSink> progress;
};

struct FrontendActionExecution {
    explicit FrontendActionExecution(FrontendExecution value);

    FrontendExecution execution;
    std::optional<facman::contracts::presentation_v1::SemanticActionResult> result;
    std::string raw_result;
};

struct FrontendOperationInspectRequest {
    std::string request_id;
    std::string operation_id;
    std::string attempt_id;
    std::string target_operation_id;
    std::string target_instance_id;
    std::chrono::milliseconds deadline {0};
    std::shared_ptr<facman::client::CancellationToken> cancellation;
    std::shared_ptr<facman::client::ProgressSink> progress;
};

struct FrontendOperationProjection {
    std::string schema = "facman.frontend_operation_projection.v1";
    std::string kind;
    std::string operation_id;
    std::string attempt_id;
    std::string target_instance_id;
    std::string state;
    std::string terminal_outcome;
    std::string authority;
    std::string snapshot_revision;
    std::string raw_projection;
};

struct FrontendCancellationRequest {
    std::string request_id;
    std::string target_operation_id;
    std::string target_instance_id;
    std::string expected_snapshot_revision;
    std::string idempotency_key;
    std::string operation_id;
    std::string attempt_id;
    std::chrono::milliseconds deadline {0};
    bool dry_run = false;
    bool explain = false;
    std::string confirmation = "explicit";
    std::shared_ptr<facman::client::CancellationToken> cancellation;
    std::shared_ptr<facman::client::ProgressSink> progress;
};

struct FrontendCapabilitySnapshot {
    std::string schema = "facman.frontend_capability_snapshot.v1";
    std::vector<unsigned int> transport_protocol_versions {2U};
    std::string presentation_schema = "facman.presentation_snapshot.v1";
    std::string semantic_action_schema = "facman.semantic_action_result.v1";
    std::string transport;
    std::vector<std::string> typed_methods;
    std::string command_catalog_sha256;
    std::string contract_set_sha256;
    FrontendSessionIdentity backend_identity;
    std::string raw_json;
};

class FrontendSession {
public:
    explicit FrontendSession(FrontendSessionOptions options);

    FrontendExecution advanced_execute(FrontendInvocation invocation);
    FrontendExecution execute(FrontendInvocation invocation);
    facman::core::Result<FrontendSessionIdentity> negotiate(
        FrontendNegotiationRequest request);
    facman::core::Result<FrontendSessionIdentity> negotiate(
        const std::string& scope = "launch_deck",
        const std::string& selected_instance_id = {},
        const std::string& search = {});
    facman::core::Result<FrontendQueryResult> query(FrontendQueryRequest request);
    FrontendActionExecution act(FrontendActionRequest request);
    facman::core::Result<FrontendOperationProjection> inspect(
        FrontendOperationInspectRequest request);
    FrontendActionExecution cancel(FrontendCancellationRequest request);
    facman::core::Result<FrontendCapabilitySnapshot> capabilities();

    const std::string& current_snapshot_revision() const noexcept {
        return current_snapshot_revision_;
    }
    const char* transport_name() const noexcept;

private:
    FrontendSessionOptions options_;
    facman::client::FacManClient client_;
    std::string current_snapshot_revision_;
    std::optional<FrontendSessionIdentity> negotiated_identity_;
};

const char* transport_kind_name(TransportKind kind) noexcept;
facman::core::Result<TransportKind> parse_transport_kind(const std::string& value);

} // namespace facman::frontend

#endif
