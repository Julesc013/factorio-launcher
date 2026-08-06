// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_client.h"
#include "fl_json.h"
#include "fl_transaction.h"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <string>
#include <variant>

namespace fs = std::filesystem;
namespace client = facman::client;
namespace json = facman::core::json;
namespace tx = facman::transaction;

namespace {

constexpr const char* kJournalId = "tx-11111111111111111111111111111111";

class CancellingProgress final : public client::ProgressSink {
public:
    explicit CancellingProgress(std::shared_ptr<client::CancellationToken> token)
        : token_(std::move(token)) {}

    void report(const client::ProgressUpdate& update) noexcept override
    {
        if (update.stage == "executing_direct_transport") token_->request_cancellation();
    }

private:
    std::shared_ptr<client::CancellationToken> token_;
};

class UnknownOutcomeTransport final : public client::Transport {
public:
    explicit UnknownOutcomeTransport(std::string code) : code_(std::move(code)) {}

    facman::core::Result<client::CommandResponse> execute(
        const client::CommandRequest& request) override
    {
        client::CommandResponse response;
        response.status = 1;
        response.outcome_kind = facman::core::OutcomeKind::unavailable;
        response.outcome = "unavailable";
        response.error_code = code_;
        response.error_message = "test-owned post-dispatch outcome is unknown";
        response.operation.operation_id = request.operation_id;
        response.operation.attempt_id = request.attempt_id;
        response.operation.outcome = client::OperationOutcome::outcome_unknown;
        response.operation.effects_may_have_occurred = true;
        response.operation.recovery.required = true;
        response.operation.recovery.transaction_id = kJournalId;
        response.operation.recovery.inspect_command = "workspace.recovery.inspect";
        if (!client::operation_result_valid(response.operation)) {
            return facman::core::Result<client::CommandResponse>::failure({
                "semantic_fixture_invalid",
                "test-owned unknown outcome violates the provider operation contract",
                "",
                facman::core::OutcomeKind::internal_error});
        }
        return facman::core::Result<client::CommandResponse>::success(std::move(response));
    }

    const char* name() const noexcept override { return "semantic-fixture"; }

private:
    std::string code_;
};

client::CommandResponse require_response(
    facman::core::Result<client::CommandResponse> result,
    const char* label)
{
    if (!result) {
        std::cerr << label << " did not return a command response\n";
        std::exit(20);
    }
    return result.take_value();
}

client::CommandRequest request(
    std::string command,
    std::string payload,
    bool dry_run,
    std::string identity)
{
    client::CommandRequest value {std::move(command), std::move(payload), dry_run};
    value.operation_id = "operation-semantic-" + identity;
    value.attempt_id = "attempt-semantic-" + identity;
    return value;
}

json::ObjectBuilder operation_record(
    const std::string& id,
    const client::CommandResponse& response)
{
    json::ObjectBuilder recovery;
    recovery.add_bool("required", response.operation.recovery.required);
    recovery.add_string("transaction_id", response.operation.recovery.transaction_id);
    recovery.add_string("inspect_command", response.operation.recovery.inspect_command);

    json::ObjectBuilder value;
    value.add_string("id", id);
    value.add_string("operation_id", response.operation.operation_id);
    value.add_string("attempt_id", response.operation.attempt_id);
    value.add_string("owner", "facman.client");
    value.add_string("phase", response.operation.effects_may_have_occurred
        ? "post_dispatch" : "pre_dispatch_or_read_only");
    value.add_string("terminal_outcome", client::operation_outcome_name(response.operation.outcome));
    value.add_bool("effects_may_have_occurred", response.operation.effects_may_have_occurred);
    value.add_string("error_code", response.error_code);
    value.add_object("recovery", recovery);
    return value;
}

json::ObjectBuilder refusal_record(
    const std::string& id,
    const std::string& code,
    const std::string& owner,
    const std::string& reason,
    const std::string& safe_next_action,
    const std::string& diagnostic_category)
{
    json::ObjectBuilder value;
    value.add_string("id", id);
    value.add_string("code", code);
    value.add_string("owner", owner);
    value.add_string("reason", reason);
    value.add_string("safe_next_action", safe_next_action);
    value.add_string("effect_classification", "none");
    value.add_string("diagnostic_category", diagnostic_category);
    return value;
}

bool write_recovery_fixture(const fs::path& workspace)
{
    std::error_code error;
    fs::create_directories(workspace / "transactions", error);
    if (error) return false;
    const fs::path journal = workspace / "transactions" /
        (std::string(kJournalId) + ".transaction.v1.json");
    if (fs::exists(journal)) return false;
    std::ofstream output(journal, std::ios::binary);
    output << "{"
           << "\"schema\":\"facman.transaction.v1\","
           << "\"transaction_id\":\"" << kJournalId << "\","
           << "\"command_id\":\"semantic.fixture\","
           << "\"workspace_id\":\"workspace-semantic\","
           << "\"target\":\"semantic-target\","
           << "\"source_identities\":[],"
           << "\"created_utc\":\"2026-08-06T00:00:00Z\","
           << "\"updated_utc\":\"2026-08-06T00:00:00Z\","
           << "\"state\":\"recovery_required\","
           << "\"completed_steps\":[],"
           << "\"owned_staging_roots\":[],"
           << "\"expected_file_hashes\":[],"
           << "\"commit_strategy\":\"inspect_only\","
           << "\"error\":\"test_owned_interruption\","
           << "\"recovery_actions\":[]"
           << "}\n";
    return static_cast<bool>(output);
}

std::string recovery_json(const tx::Outcome& outcome)
{
    if (!std::holds_alternative<tx::RecoveryResult>(outcome)) return {};
    return std::get<tx::RecoveryResult>(outcome).json;
}

bool supported_mode(const std::string& mode)
{
    return mode == "source_static" || mode == "source_shared" ||
        mode == "installed_static" || mode == "installed_shared" ||
        mode == "relocated_installed_static" ||
        mode == "relocated_installed_shared" || mode == "private_runtime";
}

} // namespace

int main(int argc, char** argv)
{
    fs::path workspace;
    std::string mode;
    std::string linkage;
    for (int index = 1; index < argc; ++index) {
        const std::string value = argv[index];
        if (value == "--workspace" && index + 1 < argc) workspace = fs::u8path(argv[++index]);
        else if (value == "--mode" && index + 1 < argc) mode = argv[++index];
        else if (value == "--linkage" && index + 1 < argc) linkage = argv[++index];
        else return 2;
    }
    if (workspace.empty() || !workspace.is_absolute() || !supported_mode(mode) ||
        (linkage != "static" && linkage != "shared")) return 3;
    if (fs::exists(workspace) || !write_recovery_fixture(workspace)) return 4;

    client::FacManClient direct(std::make_unique<client::DirectFlbTransport>(workspace));
    const auto product = require_response(
        direct.execute(request("product.inspect", "{}", true, "completed")),
        "product.inspect");
    const auto command_graph = require_response(
        direct.execute(request("command_graph.inspect", "{}", true, "command-graph")),
        "command_graph.inspect");
    const auto unsupported = require_response(
        direct.execute(request(
            "utility.operation", "{\"operation\":\"semantic.unsupported\"}", true,
            "unsupported-command")),
        "utility.operation");
    if (!product.ok() || !command_graph.ok() || unsupported.ok()) return 5;

    client::FacManClient missing_transport(std::unique_ptr<client::Transport> {});
    const auto refused = require_response(
        missing_transport.execute(request("product.inspect", "{}", true, "refused-before-dispatch")),
        "missing transport");
    client::FacManClient missing_process(std::make_unique<client::CliProcessTransport>(
        workspace / "missing-facman"));
    const auto failed = require_response(
        missing_process.execute(request("product.inspect", "{}", true, "failed-before-dispatch")),
        "missing process");
    auto cancellation = std::make_shared<client::CancellationToken>();
    cancellation->request_cancellation();
    auto cancelled_request = request("product.inspect", "{}", true, "cancelled-before-dispatch");
    cancelled_request.cancellation = cancellation;
    const auto cancelled = require_response(direct.execute(cancelled_request), "cancelled request");
    auto race_token = std::make_shared<client::CancellationToken>();
    auto race_request = request(
        "product.inspect", "{}", true, "cancellation-requested-but-completed");
    race_request.cancellation = race_token;
    race_request.progress = std::make_shared<CancellingProgress>(race_token);
    const auto completed_race = require_response(direct.execute(race_request), "cancellation race");
    auto timeout_request = request("product.inspect", "{}", true, "timeout-before-dispatch");
    timeout_request.timeout = std::chrono::milliseconds(0);
    const auto timeout = require_response(direct.execute(timeout_request), "invalid timeout");
    client::FacManClient post_dispatch(
        std::make_unique<UnknownOutcomeTransport>("post_dispatch_response_lost"));
    const auto post_dispatch_unknown = require_response(
        post_dispatch.execute(request(
            "product.inspect", "{}", true, "post-dispatch-outcome-unknown")),
        "post-dispatch unknown");
    client::FacManClient transport_loss(
        std::make_unique<UnknownOutcomeTransport>("transport_lost_after_dispatch"));
    const auto transport_loss_unknown = require_response(
        transport_loss.execute(request(
            "product.inspect", "{}", true, "transport-loss-outcome-unknown")),
        "transport-loss unknown");

    const auto malformed = require_response(
        direct.execute(request("", "{}", true, "malformed-request")),
        "malformed request");
    const auto isolation = require_response(
        direct.execute(request("run.execute", "{}", false, "isolation-not-proven")),
        "run.execute refusal");
    if (malformed.error_code != "client_request_invalid" ||
        unsupported.error_code != "unsupported_command" ||
        isolation.error_code != "isolation_not_proven") return 6;

    const std::string first_inspection = recovery_json(tx::inspect(workspace));
    const std::string second_inspection = recovery_json(tx::inspect(workspace));
    const std::string plan = recovery_json(tx::plan(workspace, kJournalId));
    if (first_inspection.empty() || first_inspection != second_inspection ||
        first_inspection.find("recovery_required") == std::string::npos ||
        plan.find("mark_recovery_required") == std::string::npos) return 7;

    json::ArrayBuilder command_records;
    for (const auto& item : {
             std::pair<const char*, const client::CommandResponse*> {"product-inspect", &product},
             {"command-graph", &command_graph},
             {"unsupported-command", &unsupported}}) {
        json::ObjectBuilder record;
        record.add_string("id", item.first);
        record.add_string("command", item.second == &product
            ? "product.inspect" : item.second == &command_graph
                ? "command_graph.inspect" : "utility.operation");
        record.add_string("status", item.second->ok() ? "ok" : "refused");
        record.add_bool("request_validated", item.second != &unsupported);
        record.add_string("dispatch_classification", item.second == &unsupported
            ? "unsupported" : "read_only");
        record.add_string("response_ownership", "client_owned_value");
        command_records.add_object(record);
    }

    json::ArrayBuilder operation_records;
    operation_records.add_object(operation_record("completed", product));
    operation_records.add_object(operation_record("refused-before-dispatch", refused));
    operation_records.add_object(operation_record("failed-before-dispatch", failed));
    operation_records.add_object(operation_record("cancelled-before-dispatch", cancelled));
    operation_records.add_object(operation_record(
        "cancellation-requested-but-completed", completed_race));
    operation_records.add_object(operation_record("timeout-before-dispatch", timeout));
    operation_records.add_object(operation_record(
        "post-dispatch-outcome-unknown", post_dispatch_unknown));
    operation_records.add_object(operation_record(
        "transport-loss-outcome-unknown", transport_loss_unknown));

    json::ArrayBuilder refusals;
    refusals.add_object(refusal_record(
        "malformed-request", malformed.error_code, "facman.client",
        malformed.error_message, "correct_request", "request_validation"));
    refusals.add_object(refusal_record(
        "unsupported-command", unsupported.error_code, "facman.binding",
        unsupported.error_message, "inspect_command_graph", "unsupported_command"));
    refusals.add_object(refusal_record(
        "isolation-not-proven", isolation.error_code, "facman.product",
        isolation.error_message, "qualify_exact_route", "authority_refusal"));
    refusals.add_object(refusal_record(
        "stale-readiness", "stale_readiness", "facman.presentation",
        "Readiness revision is stale", "refresh_readiness", "stale_projection"));

    json::ObjectBuilder recovery;
    recovery.add_string("journal_identity", kJournalId);
    recovery.add_string("operation_id", "operation-semantic-recovery");
    recovery.add_string("attempt_id", "attempt-semantic-recovery");
    recovery.add_string("known_effects", "none_observed");
    recovery.add_string("recovery_state", "recovery_required");
    recovery.add_string("available_recovery_action", "mark_recovery_required");
    recovery.add_string("plan_identity", "workspace.recovery.plan");
    recovery.add_bool("idempotent_reinspection", true);

    json::ObjectBuilder semantics;
    semantics.add_array("command_dispatch", command_records);
    semantics.add_array("operation_outcomes", operation_records);
    semantics.add_array("structured_refusals", refusals);
    semantics.add_object("interrupted_recovery", recovery);

    json::ObjectBuilder output;
    output.add_string("schema", "facman.provider_semantic_probe.v1");
    output.add_string("provider_mode", mode);
    output.add_string("linkage", linkage);
    output.add_string("workspace", workspace.u8string());
    output.add_object("semantics", semantics);
    std::cout << output.serialize() << '\n';
    return 0;
}
