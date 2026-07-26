// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_client.h"

#include <filesystem>
#include <atomic>
#include <memory>
#include <string>
#include <thread>
#include <vector>

namespace {

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

}

int main()
{
    namespace fs = std::filesystem;
    const fs::path workspace = fs::temp_directory_path() / "facman-client-smoke";
    facman::client::FacManClient client(
        std::make_unique<facman::client::DirectFlbTransport>(workspace));
    auto product = client.execute({"product.inspect", "{}", true});
    if (!product || !product.value().ok() || product.value().payload.find("\"product_id\":\"factorio\"") == std::string::npos) return 1;
    if (!facman::client::operation_result_valid(product.value().operation) ||
        product.value().operation.outcome != facman::client::OperationOutcome::completed ||
        product.value().operation.effects_may_have_occurred) return 15;
    auto direct_status = client.execute({"workspace.status", "{}", true});
    if (!direct_status || !direct_status.value().ok() ||
        direct_status.value().payload_string("command") != "workspace.status") return 13;
    if (direct_status.value().operation.operation_id == product.value().operation.operation_id ||
        direct_status.value().operation.attempt_id == product.value().operation.attempt_id) return 17;
    auto unavailable = client.execute({"run.execute", "{}", false});
    if (!unavailable || unavailable.value().ok() || unavailable.value().error_code != "isolation_not_proven" ||
        unavailable.value().outcome_kind != facman::core::OutcomeKind::unavailable ||
        unavailable.value().outcome != "unavailable") return 2;
    if (product.value().payload_string("product_id") != "factorio" ||
        product.value().payload_string("product_id") != "factorio") return 4;
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
    if (failures != 0) return 5;
    auto progress = std::make_shared<RecordingProgress>();
    facman::client::CommandRequest observed {"product.inspect", "{}", true};
    observed.progress = progress;
    auto observed_response = client.execute(observed);
    if (!observed_response || progress->stages.empty() || progress->stages.back() != "completed") return 6;
    auto cancellation = std::make_shared<facman::client::CancellationToken>();
    cancellation->request_cancellation();
    facman::client::CommandRequest cancelled {"product.inspect", "{}", true};
    cancelled.cancellation = cancellation;
    auto cancelled_response = client.execute(cancelled);
    if (!cancelled_response || cancelled_response.value().ok() ||
        cancelled_response.value().error_code != "client_operation_cancelled" ||
        cancelled_response.value().operation.outcome !=
            facman::client::OperationOutcome::cancelled_before_dispatch ||
        cancelled_response.value().operation.effects_may_have_occurred) return 7;
    facman::client::CommandRequest invalid_timeout {"product.inspect", "{}", true};
    invalid_timeout.timeout = std::chrono::milliseconds(0);
    auto timeout_response = client.execute(invalid_timeout);
    if (!timeout_response || timeout_response.value().ok() ||
        timeout_response.value().error_code != "client_timeout_invalid" ||
        timeout_response.value().operation.outcome !=
            facman::client::OperationOutcome::refused_before_effects) return 8;
    auto race_cancellation = std::make_shared<facman::client::CancellationToken>();
    auto race_progress = std::make_shared<CancellingProgress>(race_cancellation);
    facman::client::CommandRequest completed_during_cancellation {"product.inspect", "{}", true};
    completed_during_cancellation.cancellation = race_cancellation;
    completed_during_cancellation.progress = race_progress;
    auto completed_race = client.execute(completed_during_cancellation);
    if (!completed_race || !completed_race.value().ok() ||
        completed_race.value().payload_string("product_id") != "factorio" ||
        completed_race.value().operation.outcome !=
            facman::client::OperationOutcome::cancellation_requested_but_completed) return 16;
    facman::client::FacManClient cli(std::make_unique<facman::client::CliProcessTransport>(
        fs::path(FACMAN_TEST_CLI_PATH), workspace));
    facman::client::CommandRequest cli_product_request {"product.inspect", "{}", true};
    cli_product_request.operation_id = "op-process-preserved";
    cli_product_request.attempt_id = "attempt-process-preserved";
    auto cli_product = cli.execute(cli_product_request);
    if (!cli_product || !cli_product.value().ok() ||
        cli_product.value().payload_string("product_id") != "factorio" ||
        cli_product.value().operation.operation_id != cli_product_request.operation_id ||
        cli_product.value().operation.attempt_id != cli_product_request.attempt_id) return 9;
    auto cli_status = cli.execute({"workspace.status", "{}", true});
    if (!cli_status || !cli_status.value().ok() ||
        cli_status.value().payload_string("command") != direct_status.value().payload_string("command")) return 14;
    facman::client::FacManClient missing_cli(std::make_unique<facman::client::CliProcessTransport>(
        workspace / "missing-facman"));
    auto missing_response = missing_cli.execute({"product.inspect", "{}", true});
    if (!missing_response || missing_response.value().ok() ||
        missing_response.value().error_code != "cli_process_executable_missing" ||
        missing_response.value().operation.outcome !=
            facman::client::OperationOutcome::refused_before_effects) return 10;
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
    auto process_timeout = timeout_cli.execute(timeout_request);
    std::this_thread::sleep_for(std::chrono::milliseconds(1000));
    if (!process_timeout || process_timeout.value().ok() ||
        process_timeout.value().error_code != "cli_process_timeout" ||
        process_timeout.value().operation.outcome !=
            facman::client::OperationOutcome::outcome_unknown ||
        !process_timeout.value().operation.effects_may_have_occurred ||
        !process_timeout.value().operation.recovery.required ||
        process_timeout.value().operation.recovery.inspect_command != "workspace.recovery.inspect" ||
        fs::exists(marker)) return 11;
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
        !process_cancelled.value().operation.recovery.required ||
        fs::exists(cancelled_marker)) return 12;
#ifdef _WIN32
    _putenv_s("FACMAN_PROCESS_PROBE_MARKER", "");
#else
    unsetenv("FACMAN_PROCESS_PROBE_MARKER");
#endif
    facman::client::FacManClient daemon(std::make_unique<facman::client::DaemonTransport>());
    auto daemon_response = daemon.execute({"product.inspect", "{}", true});
    if (!daemon_response || daemon_response.value().ok() ||
        daemon_response.value().operation.outcome !=
            facman::client::OperationOutcome::refused_before_effects) return 3;
    return 0;
}
