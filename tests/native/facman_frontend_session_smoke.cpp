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

    facman::frontend::FrontendQueryRequest direct_query_request;
    direct_query_request.scope = "settings_support";
    direct_query_request.request_id = "request-typed-query-direct";
    direct_query_request.operation_id = "operation-typed-query-direct";
    direct_query_request.attempt_id = "attempt-typed-query-direct";
    auto direct_query = direct.query(std::move(direct_query_request));
    facman::frontend::FrontendQueryRequest process_query_request;
    process_query_request.scope = "settings_support";
    process_query_request.request_id = "request-typed-query-process";
    process_query_request.operation_id = "operation-typed-query-process";
    process_query_request.attempt_id = "attempt-typed-query-process";
    auto process_query = process.query(std::move(process_query_request));
    if (!direct_query || !process_query ||
        direct_query.value().revision != process_query.value().revision ||
        direct_query.value().snapshot.schema != "facman.presentation_snapshot.v1" ||
        process_query.value().request_id != "request-typed-query-process") return 7;

    facman::frontend::FrontendActionRequest direct_action;
    direct_action.action_id = "presentation.refresh";
    direct_action.scope = "settings_support";
    direct_action.expected_snapshot_revision = direct_query.value().revision;
    direct_action.request_id = "request-typed-action-direct";
    direct_action.operation_id = "operation-typed-action-direct";
    direct_action.attempt_id = "attempt-typed-action-direct";
    auto direct_action_result = direct.act(std::move(direct_action));
    facman::frontend::FrontendActionRequest process_action;
    process_action.action_id = "presentation.refresh";
    process_action.scope = "settings_support";
    process_action.expected_snapshot_revision = process_query.value().revision;
    process_action.request_id = "request-typed-action-process";
    process_action.operation_id = "operation-typed-action-process";
    process_action.attempt_id = "attempt-typed-action-process";
    auto process_action_result = process.act(std::move(process_action));
    if (!direct_action_result.execution.response ||
        !process_action_result.execution.response ||
        !direct_action_result.result || !process_action_result.result ||
        direct_action_result.result->outcome != "completed" ||
        process_action_result.result->outcome != direct_action_result.result->outcome ||
        direct_action_result.result->request_id != "request-typed-action-direct" ||
        process_action_result.execution.response.value().request_id !=
            "request-typed-action-process") {
        std::cerr << "typed action mismatch: direct="
                  << (direct_action_result.execution.response
                          ? direct_action_result.execution.response.value().error_code
                          : direct_action_result.execution.response.error().code)
                  << " process="
                  << (process_action_result.execution.response
                          ? process_action_result.execution.response.value().error_code
                          : process_action_result.execution.response.error().code)
                  << " direct-result=" << static_cast<bool>(direct_action_result.result)
                  << " process-result=" << static_cast<bool>(process_action_result.result)
                  << '\n';
        return 8;
    }

    facman::frontend::FrontendActionRequest unicode_doctor;
    unicode_doctor.action_id = "doctor.run";
    unicode_doctor.scope = "settings_support";
    unicode_doctor.expected_snapshot_revision = direct_query.value().revision;
    unicode_doctor.request_id = "request-unicode-doctor";
    unicode_doctor.operation_id = "operation-unicode-doctor";
    unicode_doctor.attempt_id = "attempt-unicode-doctor";
    auto unicode_doctor_result = direct.act(std::move(unicode_doctor));
    if (!unicode_doctor_result.execution.response ||
        !unicode_doctor_result.result ||
        unicode_doctor_result.result->outcome != "completed" ||
        unicode_doctor_result.raw_result.find("facman.semantic_action_result.v1") ==
            std::string::npos) return 16;

    facman::frontend::FrontendActionRequest typed_cancelled;
    typed_cancelled.action_id = "presentation.refresh";
    typed_cancelled.scope = "settings_support";
    typed_cancelled.expected_snapshot_revision = direct_query.value().revision;
    typed_cancelled.cancellation =
        std::make_shared<facman::client::CancellationToken>();
    typed_cancelled.cancellation->request_cancellation();
    auto typed_cancelled_result = direct.act(std::move(typed_cancelled));
    if (!typed_cancelled_result.execution.response ||
        typed_cancelled_result.execution.response.value().operation.outcome !=
            facman::client::OperationOutcome::cancelled_before_dispatch ||
        typed_cancelled_result.result) return 17;

    facman::frontend::FrontendActionRequest unknown_input;
    unknown_input.action_id = "presentation.refresh";
    unknown_input.scope = "settings_support";
    unknown_input.expected_snapshot_revision = direct_query.value().revision;
    unknown_input.inputs.emplace("ordinary_unknown", "refuse-before-dispatch");
    auto unknown_result = direct.act(std::move(unknown_input));
    if (unknown_result.execution.response ||
        unknown_result.execution.response.error().code !=
            "frontend_action_input_unknown") return 9;

    facman::frontend::FrontendActionRequest undeclared_input;
    undeclared_input.action_id = "presentation.refresh";
    undeclared_input.scope = "settings_support";
    undeclared_input.expected_snapshot_revision = direct_query.value().revision;
    undeclared_input.inputs.emplace("profile_id", "ordinary-but-not-declared");
    auto undeclared_result = direct.act(std::move(undeclared_input));
    if (undeclared_result.execution.response ||
        undeclared_result.execution.response.error().code !=
            "frontend_action_input_not_declared") return 15;

    facman::frontend::FrontendActionRequest stale_action;
    stale_action.action_id = "presentation.refresh";
    stale_action.scope = "settings_support";
    stale_action.expected_snapshot_revision = std::string(64U, '0');
    auto stale_result = direct.act(std::move(stale_action));
    if (!stale_result.execution.response || stale_result.execution.response.value().ok() ||
        stale_result.execution.response.value().error_code != "stale_snapshot_revision" ||
        !stale_result.result || stale_result.result->outcome != "refused_before_effects") return 10;

    facman::frontend::FrontendOperationInspectRequest inspect_request;
    inspect_request.target_operation_id = "operation-not-present";
    auto missing_operation = direct.inspect(std::move(inspect_request));
    if (missing_operation || missing_operation.error().code !=
        "frontend_operation_not_found") return 11;
    facman::frontend::FrontendOperationInspectRequest process_inspect_request;
    process_inspect_request.target_operation_id = "operation-not-present";
    auto process_missing_operation = process.inspect(std::move(process_inspect_request));
    if (process_missing_operation || process_missing_operation.error().code !=
        "frontend_operation_not_found") return 20;

    facman::frontend::FrontendCancellationRequest cancel_request;
    cancel_request.target_operation_id = "operation-not-present";
    cancel_request.target_instance_id = "instance-not-present";
    cancel_request.expected_snapshot_revision = direct.current_snapshot_revision();
    cancel_request.idempotency_key = "cancel-not-present";
    cancel_request.operation_id = "operation-cancel-not-present";
    cancel_request.attempt_id = "attempt-cancel-not-present";
    auto cancel_result = direct.cancel(std::move(cancel_request));
    if (cancel_result.execution.response || cancel_result.execution.response.error().code !=
        "frontend_operation_not_found") return 12;
    facman::frontend::FrontendCancellationRequest process_cancel_request;
    process_cancel_request.target_operation_id = "operation-not-present";
    process_cancel_request.target_instance_id = "instance-not-present";
    process_cancel_request.expected_snapshot_revision = process.current_snapshot_revision();
    process_cancel_request.idempotency_key = "cancel-not-present-process";
    process_cancel_request.operation_id = "operation-cancel-not-present-process";
    process_cancel_request.attempt_id = "attempt-cancel-not-present-process";
    auto process_cancel_result = process.cancel(std::move(process_cancel_request));
    if (process_cancel_result.execution.response ||
        process_cancel_result.execution.response.error().code !=
            "frontend_operation_not_found") return 21;

    auto direct_capabilities = direct.capabilities();
    auto process_capabilities = process.capabilities();
    if (!direct_capabilities || !process_capabilities ||
        direct_capabilities.value().typed_methods.size() != 7U ||
        process_capabilities.value().typed_methods != direct_capabilities.value().typed_methods ||
        direct_capabilities.value().transport != "direct" ||
        process_capabilities.value().transport != "process" ||
        direct_capabilities.value().raw_json.find(
            "facman.frontend_capability_snapshot.v1") == std::string::npos) return 13;
    FrontendSessionOptions daemon_options;
    daemon_options.workspace = workspace;
    daemon_options.transport = TransportKind::daemon;
    FrontendSession daemon(daemon_options);
    auto daemon_capabilities = daemon.capabilities();
    if (daemon_capabilities || daemon_capabilities.error().code !=
        "daemon_transport_unavailable") return 19;

    FrontendInvocation advanced_direct;
    advanced_direct.command = "product.inspect";
    advanced_direct.request_id = "request-advanced-direct";
    auto advanced_direct_result = direct.advanced_execute(std::move(advanced_direct));
    FrontendInvocation advanced_process;
    advanced_process.command = "product.inspect";
    advanced_process.request_id = "request-advanced-process";
    auto advanced_process_result = process.advanced_execute(std::move(advanced_process));
    if (!advanced_direct_result.response || !advanced_process_result.response ||
        advanced_direct_result.response.value().request_id.size() != 0U ||
        advanced_process_result.response.value().request_id != "request-advanced-process" ||
        advanced_direct_result.response.value().payload_string("product_id") !=
            advanced_process_result.response.value().payload_string("product_id")) return 14;

    facman::core::json::ObjectBuilder legacy_action_payload;
    legacy_action_payload.add_string("action_id", "presentation.refresh");
    legacy_action_payload.add_string("scope", "settings_support");
    legacy_action_payload.add_string(
        "expected_snapshot_revision", direct_query.value().revision);
    legacy_action_payload.add_string("request_id", "request-legacy-action");
    legacy_action_payload.add_string("idempotency_key", "idempotency-legacy-action");
    legacy_action_payload.add_string("durable_operation_id", "operation-legacy-action");
    legacy_action_payload.add_string("attempt_id", "attempt-legacy-action");
    FrontendInvocation legacy_action;
    legacy_action.command = "presentation.action";
    legacy_action.payload = legacy_action_payload.serialize();
    auto legacy_action_result = direct.execute(std::move(legacy_action));
    if (!legacy_action_result.response ||
        legacy_action_result.request_id != "request-legacy-action" ||
        legacy_action_result.operation_id != "operation-legacy-action" ||
        legacy_action_result.attempt_id != "attempt-legacy-action" ||
        legacy_action_result.response.value().request_id != "request-legacy-action") return 22;
    FrontendInvocation conflicting_action;
    conflicting_action.command = "presentation.action";
    conflicting_action.payload = legacy_action_payload.serialize();
    conflicting_action.request_id = "request-conflicting-action";
    auto conflicting_action_result = direct.advanced_execute(std::move(conflicting_action));
    if (conflicting_action_result.response ||
        conflicting_action_result.response.error().code !=
            "frontend_invocation_identity_conflict") return 23;

    const auto effect_replay = [&](TransportKind transport, const char* suffix) {
        const fs::path effect_workspace = fs::temp_directory_path() /
            facman::platform::path_from_utf8(
                std::string("facman-frontend-effect-") + suffix);
        std::error_code cleanup_error;
        fs::remove_all(effect_workspace, cleanup_error);
        FrontendSessionOptions options;
        options.workspace = effect_workspace;
        options.transport = transport;
        options.process_executable = facman::platform::path_from_utf8(FACMAN_TEST_CLI_PATH);
        {
            FrontendSession effect_session(options);
            facman::frontend::FrontendQueryRequest effect_query_request;
            effect_query_request.scope = "settings_support";
            auto effect_query = effect_session.query(std::move(effect_query_request));
            if (!effect_query) return false;
            facman::frontend::FrontendActionRequest effect;
            effect.action_id = "workspace.initialize";
            effect.scope = "settings_support";
            effect.expected_snapshot_revision = effect_query.value().revision;
            effect.request_id = std::string("request-effect-") + suffix;
            effect.idempotency_key = std::string("idempotency-effect-") + suffix;
            effect.operation_id = std::string("operation-effect-") + suffix;
            effect.attempt_id = std::string("attempt-effect-") + suffix;
            effect.dry_run = false;
            effect.confirmation = "explicit";
            auto replay_request = effect;
            auto conflict_request = effect;
            auto first = effect_session.act(std::move(effect));
            auto replay = effect_session.act(std::move(replay_request));
            conflict_request.request_id += "-changed";
            conflict_request.operation_id += "-changed";
            conflict_request.attempt_id += "-changed";
            auto conflict = effect_session.act(std::move(conflict_request));
            if (!first.execution.response || !first.result ||
                first.result->outcome != "completed" ||
                !replay.execution.response || !replay.result ||
                replay.raw_result != first.raw_result ||
                !conflict.execution.response || conflict.execution.response.value().ok() ||
                conflict.execution.response.value().error_code != "idempotency_key_conflict" ||
                !conflict.result || conflict.result->outcome != "refused_before_effects") {
                std::cerr << "effect replay mismatch " << suffix
                          << " first=" << (first.execution.response
                                  ? first.execution.response.value().error_code
                                  : first.execution.response.error().code)
                          << " replay=" << (replay.execution.response
                                  ? replay.execution.response.value().error_code
                                  : replay.execution.response.error().code)
                          << " conflict=" << (conflict.execution.response
                                  ? conflict.execution.response.value().error_code
                                  : conflict.execution.response.error().code)
                          << " first-result=" << static_cast<bool>(first.result)
                          << " replay-result=" << static_cast<bool>(replay.result)
                          << " conflict-result=" << static_cast<bool>(conflict.result)
                          << '\n';
                return false;
            }
        }
        const fs::path receipts = effect_workspace / ".facman" / "action-receipts-v2";
        std::size_t receipt_count = 0U;
        if (fs::is_directory(receipts)) {
            for (const auto& entry : fs::directory_iterator(receipts)) {
                if (entry.is_regular_file()) ++receipt_count;
            }
        }
        fs::remove_all(effect_workspace, cleanup_error);
        if (receipt_count != 2U) {
            std::cerr << "effect receipt count " << suffix << "=" << receipt_count << '\n';
        }
        return receipt_count == 2U;
    };
    if (!effect_replay(TransportKind::direct, "direct") ||
        !effect_replay(TransportKind::process, "process")) return 18;
    return 0;
}
