// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "frontend_session.h"
#include "fl_file_io.h"

#include <filesystem>
#include <iostream>
#include <memory>
#include <string>

int main()
{
    namespace fs = std::filesystem;
    using facman::frontend::FrontendInvocation;
    using facman::frontend::FrontendSession;
    using facman::frontend::FrontendSessionOptions;
    using facman::frontend::TransportKind;

    const fs::path workspace = fs::temp_directory_path() /
        facman::platform::path_from_utf8("facman-frontend-session-Ω-empty");
    std::error_code ignored;
    fs::remove_all(workspace, ignored);

    FrontendSessionOptions direct_options;
    direct_options.workspace = workspace;
    FrontendSession direct(direct_options);
    auto direct_identity = direct.negotiate();
    if (!direct_identity) {
        std::cerr << direct_identity.error().code << ": " << direct_identity.error().message << '\n';
        return 2;
    }
    if (direct_identity.value().transport != "direct" ||
        direct_identity.value().snapshot_revision.size() != 64U ||
        direct_identity.value().raw_snapshot.find("facman.presentation_snapshot.v1") == std::string::npos ||
        direct.current_snapshot_revision() != direct_identity.value().snapshot_revision ||
        fs::exists(workspace)) {
        std::cerr << "direct identity invariant failed: transport=" << direct_identity.value().transport
                  << " revision=" << direct_identity.value().snapshot_revision
                  << " raw=" << direct_identity.value().raw_snapshot.size()
                  << " workspace_exists=" << fs::exists(workspace) << '\n';
        return 2;
    }

    FrontendSessionOptions process_options;
    process_options.workspace = workspace;
    process_options.transport = TransportKind::process;
    process_options.process_executable = facman::platform::path_from_utf8(FACMAN_TEST_CLI_PATH);
    FrontendSession process(process_options);
    auto process_identity = process.negotiate();
    if (!process_identity) {
        std::cerr << process_identity.error().code << ": " << process_identity.error().message << '\n';
        return 3;
    }
    if (process_identity.value().transport != "process" ||
        process_identity.value().snapshot_revision != direct_identity.value().snapshot_revision ||
        process_identity.value().universal_launcher_revision !=
            direct_identity.value().universal_launcher_revision ||
        process_identity.value().contract_set_sha256 != direct_identity.value().contract_set_sha256 ||
        fs::exists(workspace)) {
        std::cerr << "process identity invariant failed\n";
        return 3;
    }

    FrontendInvocation invocation;
    invocation.command = "workspace.status";
    invocation.payload = "{\"sensitive_path\":\"must-not-appear\"}";
    invocation.request_id = "request.frontend-smoke";
    invocation.operation_id = "operation.frontend-smoke";
    invocation.attempt_id = "attempt.frontend-smoke";
    invocation.cancellation = std::make_shared<facman::client::CancellationToken>();
    invocation.cancellation->request_cancellation();
    auto cancelled = direct.execute(std::move(invocation));
    if (!cancelled.response || cancelled.response.value().outcome != "cancelled" ||
        cancelled.response.value().operation.outcome !=
            facman::client::OperationOutcome::cancelled_before_dispatch ||
        cancelled.correlation_json().find("facman.frontend_correlation.v1") == std::string::npos ||
        cancelled.correlation_json().find("must-not-appear") != std::string::npos) return 4;

    auto invalid = facman::frontend::parse_transport_kind("tcp");
    if (invalid || invalid.error().code != "frontend_transport_invalid") return 5;
    if (direct_identity.value().json().find("facman.frontend_session_identity.v1") == std::string::npos ||
        direct_identity.value().json().find("unknown_additive_fields_preserved\":true") ==
            std::string::npos) return 6;
    return 0;
}
