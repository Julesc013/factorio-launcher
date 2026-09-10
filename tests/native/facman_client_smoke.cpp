// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_client.h"

#include <algorithm>
#include <filesystem>
#include <atomic>
#include <iostream>
#include <memory>
#include <string>
#include <thread>
#include <vector>

namespace {

int fail(int code, const char* stage)
{
    std::cerr << "facman_client_smoke: stage=" << stage << " exit=" << code << '\n';
    return code;
}

int fail_response(int code, const char* stage,
    const facman::core::Result<facman::client::CommandResponse>& response)
{
    std::cerr << "facman_client_smoke: stage=" << stage << " exit=" << code;
    if (!response) {
        std::cerr << " result_error_code=" << response.error().code
                  << " result_error_message=" << response.error().message;
    } else {
        const auto& value = response.value();
        std::cerr << " status=" << value.status
                  << " error_code=" << value.error_code
                  << " error_message=" << value.error_message
                  << " request_id=" << value.request_id
                  << " command=" << value.command
                  << " operation_outcome="
                  << facman::client::operation_outcome_name(value.operation.outcome)
                  << " operation_id=" << value.operation.operation_id
                  << " attempt_id=" << value.operation.attempt_id;
    }
    std::cerr << '\n';
    return code;
}

class RecordingProgress final : public facman::client::ProgressSink {
public:
    void report(const facman::client::ProgressUpdate& update) noexcept override
    {
        stages.push_back(update.stage);
    }
    std::vector<std::string> stages;
};

class CancellingProgress final : public facman::client::ProgressSink {
public:
    explicit CancellingProgress(std::shared_ptr<facman::client::CancellationToken> token)
        : token_(std::move(token)) {}
    void report(const facman::client::ProgressUpdate& update) noexcept override
    {
        if (update.stage == "executing_direct_transport") token_->request_cancellation();
    }
private:
    std::shared_ptr<facman::client::CancellationToken> token_;
};

std::size_t completed_count(const RecordingProgress& progress)
{
    return static_cast<std::size_t>(std::count(
        progress.stages.begin(), progress.stages.end(), "completed"));
}

}

int main()
{
    namespace fs = std::filesystem;
    const fs::path workspace = fs::temp_directory_path() / "facman-client-smoke";
    facman::client::FacManClient client(
        std::make_unique<facman::client::DirectFlbTransport>(workspace));
    auto product = client.execute({"product.inspect", "{}", true});
    if (!product || !product.value().ok() || product.value().payload.find("\"product_id\":\"factorio\"") == std::string::npos)
        return fail_response(1, "direct_product_inspect", product);
    if (!facman::client::operation_result_valid(product.value().operation) ||
        product.value().operation.outcome != facman::client::OperationOutcome::completed ||
        product.value().operation.effects_may_have_occurred)
        return fail_response(15, "direct_product_operation", product);
    auto direct_status = client.execute({"workspace.status", "{}", true});
    if (!direct_status || !direct_status.value().ok() ||
        direct_status.value().payload_string("command") != "workspace.status")
        return fail_response(13, "direct_workspace_status", direct_status);
    if (direct_status.value().operation.operation_id == product.value().operation.operation_id ||
        direct_status.value().operation.attempt_id == product.value().operation.attempt_id)
        return fail_response(17, "direct_operation_identity_uniqueness", direct_status);
    auto unavailable = client.execute({"run.execute", "{}", false});
    if (!unavailable || unavailable.value().ok() || unavailable.value().error_code != "isolation_not_proven" ||
        unavailable.value().outcome_kind != facman::core::OutcomeKind::unavailable ||
        unavailable.value().outcome != "unavailable")
        return fail_response(2, "unavailable_execution", unavailable);
    if (product.value().payload_string("product_id") != "factorio" ||
        product.value().payload_string("product_id") != "factorio")
        return fail_response(4, "direct_payload_accessor", product);
    std::atomic<int> failures {0};
    std::vector<std::thread> readers;
    for (int index = 0; index < 8; ++index) {
        readers.emplace_back([&client, &failures]() {
            auto response = client.execute({"product.inspect", "{}", true});
            if (!response || !response.value().ok() || response.value().payload_string("product_id") != "factorio") {
                ++failures;
            }
        });
    }
    for (auto& reader : readers) reader.join();
    if (failures != 0) return fail(5, "concurrent_direct_reads");
    auto progress = std::make_shared<RecordingProgress>();
    facman::client::CommandRequest observed {"product.inspect", "{}", true};
    observed.progress = progress;
    auto observed_response = client.execute(observed);
    if (!observed_response || progress->stages.empty() || progress->stages.back() != "completed")
        return fail_response(6, "direct_progress", observed_response);
    auto cancellation = std::make_shared<facman::client::CancellationToken>();
    cancellation->request_cancellation();
    facman::client::CommandRequest cancelled {"product.inspect", "{}", true};
    cancelled.cancellation = cancellation;
    auto cancelled_response = client.execute(cancelled);
    if (!cancelled_response || cancelled_response.value().ok() ||
        cancelled_response.value().error_code != "client_operation_cancelled" ||
        cancelled_response.value().operation.outcome !=
            facman::client::OperationOutcome::cancelled_before_dispatch ||
        cancelled_response.value().operation.effects_may_have_occurred)
        return fail_response(7, "pre_dispatch_cancellation", cancelled_response);
    facman::client::CommandRequest invalid_timeout {"product.inspect", "{}", true};
    invalid_timeout.timeout = std::chrono::milliseconds(0);
    auto timeout_response = client.execute(invalid_timeout);
    if (!timeout_response || timeout_response.value().ok() ||
        timeout_response.value().error_code != "client_timeout_invalid" ||
        timeout_response.value().operation.outcome !=
            facman::client::OperationOutcome::refused_before_effects)
        return fail_response(8, "invalid_timeout", timeout_response);
    auto race_cancellation = std::make_shared<facman::client::CancellationToken>();
    auto race_progress = std::make_shared<CancellingProgress>(race_cancellation);
    facman::client::CommandRequest completed_during_cancellation {"product.inspect", "{}", true};
    completed_during_cancellation.cancellation = race_cancellation;
    completed_during_cancellation.progress = race_progress;
    auto completed_race = client.execute(completed_during_cancellation);
    if (!completed_race || !completed_race.value().ok() ||
        completed_race.value().payload_string("product_id") != "factorio" ||
        completed_race.value().operation.outcome !=
            facman::client::OperationOutcome::cancellation_requested_but_completed)
        return fail_response(16, "completion_after_cancellation", completed_race);
    facman::client::FacManClient cli(std::make_unique<facman::client::CliProcessTransport>(
        fs::path(FACMAN_TEST_CLI_PATH), workspace));
    facman::client::CommandRequest cli_product_request {"product.inspect", "{}", true};
    cli_product_request.request_id = u8"request-process-ß-quoted-\"";
    cli_product_request.operation_id = "op-process-preserved";
    cli_product_request.attempt_id = "attempt-process-preserved";
    auto cli_progress = std::make_shared<RecordingProgress>();
    cli_product_request.progress = cli_progress;
    auto cli_product = cli.execute(cli_product_request);
    if (!cli_product || !cli_product.value().ok() ||
        cli_product.value().payload_string("product_id") != "factorio" ||
        cli_product.value().request_id != cli_product_request.request_id ||
        cli_product.value().command != cli_product_request.command ||
        cli_product.value().transport_schema != "facman.transport_response.v2" ||
        cli_product.value().transport_protocol_version != 2U ||
        cli_product.value().operation.operation_id != cli_product_request.operation_id ||
        cli_product.value().operation.attempt_id != cli_product_request.attempt_id ||
        completed_count(*cli_progress) != 1U || cli_progress->stages.back() != "completed")
        return fail_response(9, "cli_process_product_inspect", cli_product);
    auto cli_status = cli.execute({"workspace.status", "{}", true});
    if (!cli_status || !cli_status.value().ok() ||
        cli_status.value().payload_string("command") != direct_status.value().payload_string("command"))
        return fail_response(14, "cli_process_workspace_status", cli_status);
    facman::client::FacManClient missing_cli(std::make_unique<facman::client::CliProcessTransport>(
        workspace / "missing-facman"));
    auto missing_response = missing_cli.execute({"product.inspect", "{}", true});
    if (!missing_response || missing_response.value().ok() ||
        missing_response.value().error_code != "cli_process_executable_missing" ||
        missing_response.value().operation.outcome !=
            facman::client::OperationOutcome::refused_before_effects)
        return fail_response(10, "missing_cli_refusal", missing_response);
    const fs::path marker = workspace / "process-tree-survivor.txt";
#ifdef _WIN32
    _putenv_s("FACMAN_PROCESS_PROBE_MARKER", marker.string().c_str());
#else
    setenv("FACMAN_PROCESS_PROBE_MARKER", marker.string().c_str(), 1);
#endif
    facman::client::FacManClient timeout_cli(std::make_unique<facman::client::CliProcessTransport>(
        fs::path(FACMAN_TEST_PROCESS_PROBE_PATH)));
    facman::client::CommandRequest timeout_request {"product.inspect", "{}", true};
    timeout_request.timeout = std::chrono::milliseconds(100);
    auto timeout_progress = std::make_shared<RecordingProgress>();
    timeout_request.progress = timeout_progress;
    auto process_timeout = timeout_cli.execute(timeout_request);
    std::this_thread::sleep_for(std::chrono::milliseconds(1000));
    if (!process_timeout || process_timeout.value().ok() ||
        process_timeout.value().error_code != "cli_process_timeout" ||
        process_timeout.value().operation.outcome !=
            facman::client::OperationOutcome::outcome_unknown ||
        !process_timeout.value().operation.effects_may_have_occurred ||
        !process_timeout.value().operation.recovery.required ||
        process_timeout.value().operation.recovery.inspect_command != "workspace.recovery.inspect" ||
        process_timeout.value().error_message !=
            "CLI process exceeded its timeout after dispatch; effects may have occurred" ||
        completed_count(*timeout_progress) != 0U ||
        fs::exists(marker))
        return fail_response(11, "cli_process_timeout", process_timeout);
    const fs::path cancelled_marker = workspace / "cancelled-process-tree-survivor.txt";
#ifdef _WIN32
    _putenv_s("FACMAN_PROCESS_PROBE_MARKER", cancelled_marker.string().c_str());
#else
    setenv("FACMAN_PROCESS_PROBE_MARKER", cancelled_marker.string().c_str(), 1);
#endif
    auto process_cancellation = std::make_shared<facman::client::CancellationToken>();
    facman::client::CommandRequest process_cancel_request {"product.inspect", "{}", true};
    process_cancel_request.cancellation = process_cancellation;
    process_cancel_request.timeout = std::chrono::seconds(5);
    auto cancellation_progress = std::make_shared<RecordingProgress>();
    process_cancel_request.progress = cancellation_progress;
    std::thread canceller([process_cancellation]() {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        process_cancellation->request_cancellation();
    });
    auto process_cancelled = timeout_cli.execute(process_cancel_request);
    canceller.join();
    std::this_thread::sleep_for(std::chrono::milliseconds(1000));
    if (!process_cancelled || process_cancelled.value().ok() ||
        process_cancelled.value().error_code != "client_operation_cancelled" ||
        process_cancelled.value().operation.outcome !=
            facman::client::OperationOutcome::outcome_unknown ||
        !process_cancelled.value().operation.effects_may_have_occurred ||
        !process_cancelled.value().operation.recovery.required ||
        process_cancelled.value().operation.recovery.inspect_command != "workspace.recovery.inspect" ||
        process_cancelled.value().error_message !=
            "CLI process command was cancelled after dispatch; effects may have occurred" ||
        completed_count(*cancellation_progress) != 0U ||
        fs::exists(cancelled_marker))
        return fail_response(12, "cli_process_cancellation", process_cancelled);
#ifdef _WIN32
    _putenv_s("FACMAN_PROCESS_PROBE_MARKER", "");
#else
    unsetenv("FACMAN_PROCESS_PROBE_MARKER");
#endif
    facman::client::FacManClient identity_probe_cli(
        std::make_unique<facman::client::CliProcessTransport>(
            fs::path(FACMAN_TEST_PROCESS_PROBE_PATH)));
    const auto expect_post_dispatch_unknown = [&identity_probe_cli](
        const char* mode, const char* expected_code, const char* expected_message) {
#ifdef _WIN32
        _putenv_s("FACMAN_PROCESS_PROBE_RPC_MODE", mode);
#else
        setenv("FACMAN_PROCESS_PROBE_RPC_MODE", mode, 1);
#endif
        facman::client::CommandRequest request {"product.inspect", "{}", true};
        if (std::string(mode).rfind("semantic-", 0) == 0) request.command = "presentation.action";
        request.request_id = "request-identity-probe";
        request.operation_id = "operation-identity-probe";
        request.attempt_id = "attempt-identity-probe";
        auto progress = std::make_shared<RecordingProgress>();
        request.progress = progress;
        auto response = identity_probe_cli.execute(request);
        return response && !response.value().ok() &&
            response.value().error_code == expected_code &&
            (expected_message == nullptr
                ? !response.value().error_message.empty()
                : response.value().error_message == expected_message) &&
            response.value().operation.outcome ==
                facman::client::OperationOutcome::outcome_unknown &&
            response.value().operation.effects_may_have_occurred &&
            response.value().operation.recovery.required &&
            response.value().operation.recovery.inspect_command == "workspace.recovery.inspect" &&
            completed_count(*progress) == 0U;
    };
    if (!expect_post_dispatch_unknown("empty", "cli_process_response_empty",
            "CLI process returned no machine response after dispatch; effects may have occurred") ||
        !expect_post_dispatch_unknown("malformed", "client_response_invalid", nullptr) ||
        !expect_post_dispatch_unknown("oversized", "cli_process_output_too_large",
            "CLI process exceeded its output budget after dispatch") ||
        !expect_post_dispatch_unknown("request", "client_request_identity_mismatch",
            "CLI process response request identity does not match its request") ||
        !expect_post_dispatch_unknown("command", "client_command_identity_mismatch",
            "CLI process response command identity does not match its request") ||
        !expect_post_dispatch_unknown("operation", "client_operation_identity_mismatch",
            "CLI process response operation identity does not match its request") ||
        !expect_post_dispatch_unknown("attempt", "client_operation_identity_mismatch",
            "CLI process response operation identity does not match its request") ||
        !expect_post_dispatch_unknown("protocol", "client_response_protocol_mismatch",
            "CLI process response does not identify FacMan transport protocol v2") ||
        !expect_post_dispatch_unknown("semantic-identity", "client_semantic_identity_mismatch",
            "presentation.action result identity does not match its request") ||
        !expect_post_dispatch_unknown("semantic-operation", "client_semantic_operation_identity_mismatch",
            "presentation.action operation identity does not match its request") ||
        !expect_post_dispatch_unknown("semantic-attempt", "client_semantic_operation_identity_mismatch",
            "presentation.action operation identity does not match its request"))
        return fail(18, "cli_process_post_dispatch_failures");
#ifdef _WIN32
    _putenv_s("FACMAN_PROCESS_PROBE_RPC_MODE", "");
#else
    unsetenv("FACMAN_PROCESS_PROBE_RPC_MODE");
#endif
    facman::client::FacManClient daemon(std::make_unique<facman::client::DaemonTransport>());
    auto daemon_response = daemon.execute({"product.inspect", "{}", true});
    if (!daemon_response || daemon_response.value().ok() ||
        daemon_response.value().operation.outcome !=
            facman::client::OperationOutcome::refused_before_effects)
        return fail_response(3, "daemon_refusal", daemon_response);
    return 0;
}
