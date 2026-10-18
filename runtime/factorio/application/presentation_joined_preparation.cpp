// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "presentation_joined_preparation.h"
#include "presentation_action_support.h"
#include "flb_factorio_instance_model.h"
#include "flb_factorio_modset_solver.h"
#include "fl_file_io.h"
#include "fl_path_safety.h"
#include "fl_workspace_store.h"
#include "fl_json.h"
#include "command_result.h"

#include <chrono>
#include <cstdlib>
#include <thread>
#include <vector>

namespace facman::factorio::application {
namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace lifecycle = facman::factorio::instance;
namespace content_owner = facman::factorio::modsets::solver;

namespace {
JoinedPreparationOutcome prepare_joined_content(const fs::path& workspace, const fs::path& root,
    const SemanticActionRequest& request, const std::string& source,
    const std::function<bool(const std::string&, std::string&)>& checkpoint)
{
    auto plan = json::parse(source);
    const auto* owner = plan ? plan.value().find("content_plan") : nullptr;
    if (!owner) return {"refused_before_effects", joined_preparation_result(source, {}, {}),
        "make_ready_plan_invalid", "The reviewed content plan is unavailable"};
    const lifecycle::ProjectionRequest projection {request.selected_instance_id, request.launch_intent};
    const auto protected_inputs = [&]() {
        return lifecycle::verify_joined_content_inputs(workspace, projection, source);
    };
    if (std::getenv("FACMAN_TEST_MAKE_READY_PAUSE_BEFORE_CONTENT") != nullptr) {
        std::string detail;
        bool released = false;
        if (facman::base::write_text_new_atomic(root / ".facman-test-make-ready-before-content", "ready\n", detail)) {
            for (unsigned index = 0; index < 2000U; ++index) {
                std::error_code error;
                if (fs::exists(root / ".facman-test-make-ready-before-content-release", error) && !error) {
                    released = true; break;
                }
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
        }
        if (!released) return {"refused_before_effects", joined_preparation_result(source, {}, {}),
            "make_ready_test_pause_failed", "Test boundary timed out"};
    }
    auto current = protected_inputs();
    if (!current) return {"refused_before_effects", joined_preparation_result(source, {}, {}),
        current.error().code, current.error().message};
    const auto content_plan = owner->serialize();
    auto applied = content_owner::apply_locked_activation(workspace, request.selected_instance_id,
        decode_json_string_field(content_plan, "plan_sha256"), request.durable_operation_id, request.attempt_id, protected_inputs);
    if (!applied) return {
        applied.error().kind == facman::core::OutcomeKind::refused ? "refused_before_effects" : "recovery_required",
        joined_content_preparation_result(source, {}, {}, "inspect_domain_recovery", false, false),
        applied.error().code, applied.error().message};
    if (std::getenv("FACMAN_TEST_MAKE_READY_EXIT_AFTER_CONTENT_OWNER") != nullptr) std::_Exit(90);
    const char* unknown = std::getenv("FACMAN_TEST_MAKE_READY_OWNER_RESULT_UNKNOWN");
    if (unknown && std::string(unknown) == "content") applied = facman::core::Result<std::string>::success("{}");
    const auto receipt = applied.take_value();
    const auto current_content = [&]() {
        return static_cast<bool>(content_owner::verify_locked_activation(workspace,
            request.selected_instance_id, content_plan, receipt, request.durable_operation_id, request.attempt_id));
    };
    if (!current_content()) return {"recovery_required",
        joined_content_preparation_result(source, receipt, {}, "inspect_domain_recovery", false, false),
        "make_ready_owner_result_unknown", "Content may have committed; inspect its journal before any retry"};
    const auto pending = action_result_json(request, "outcome_unknown", {},
        joined_content_preparation_result(source, receipt, {}, "inspect_original_request", true, true),
        "semantic_action_dispatch_uncertain", "Completed content activation is retained; do not dispatch the accepted request again",
        false, {"workspace_write"});
    std::string detail;
    if (!checkpoint(pending, detail)) return {"recovery_required",
        joined_content_preparation_result(source, receipt, {}, "inspect_domain_recovery", current_content(), false),
        "make_ready_checkpoint_failed", detail};
    if (std::getenv("FACMAN_TEST_MAKE_READY_EXIT_AFTER_CONTENT") != nullptr) std::_Exit(89);
    if (std::getenv("FACMAN_TEST_MAKE_READY_PAUSE_AFTER_CONTENT") != nullptr) {
        const auto marker = root / ".facman-test-make-ready-after-content";
        const auto release = root / ".facman-test-make-ready-content-release";
        bool released = false;
        if (facman::base::write_text_new_atomic(marker, "ready\n", detail)) {
            for (unsigned index = 0; index < 2000U; ++index) {
                std::error_code error;
                if (fs::exists(release, error) && !error) { released = true; break; }
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
        }
        if (!released) return {"recovery_required",
            joined_content_preparation_result(source, receipt, {}, "inspect_domain_recovery", current_content(), false),
            "make_ready_test_pause_failed", detail.empty() ? "Test boundary timed out" : detail};
    }
    auto remaining = lifecycle::continue_joined_after_content(workspace, projection, source,
        receipt, request.durable_operation_id, request.attempt_id);
    if (!remaining) {
        const bool verified = current_content();
        return {"recovery_required", joined_content_preparation_result(source, receipt, {},
            verified ? "fresh_request_after_input_correction" : "inspect_domain_recovery", verified, verified),
            remaining.error().code, remaining.error().message};
    }
    auto nested = prepare_joined(workspace, request, remaining.value(),
        [&](const std::string& nested_pending, std::string& checkpoint_detail) {
            auto document = json::parse(nested_pending);
            const auto* result = document ? document.value().find("action_payload") : nullptr;
            if (!result || !result->is_object()) { checkpoint_detail = "Remaining owner checkpoint is unavailable"; return false; }
            const auto wrapped = action_result_json(request, "outcome_unknown", {},
                joined_content_preparation_result(source, receipt, result->serialize(), "inspect_original_request", current_content(), false),
                "semantic_action_dispatch_uncertain", "Completed owner effects are retained; do not dispatch the accepted request again",
                false, {"workspace_write"});
            return checkpoint(wrapped, checkpoint_detail);
        });
    auto nested_document = json::parse(nested.payload);
    const auto* nested_effects = nested_document ? nested_document.value().find("completed_components") : nullptr;
    const auto* verified_flag = nested_document ? nested_document.value().find("completed_effects_verified") : nullptr;
    auto nested_verified = verified_flag ? verified_flag->bool_value() : facman::core::Result<bool>::success(false);
    const std::string nested_outcome = nested.outcome;
    const bool content_verified = current_content();
    const bool effects_verified = content_verified && nested_effects && nested_effects->is_array() &&
        ((nested_effects->size() == 0U && (nested_outcome == "completed" || nested_outcome == "refused_before_effects")) ||
            (nested_verified && nested_verified.value()));
    const bool complete = nested_outcome == "completed" && effects_verified;
    const char* continuation = complete ? "observe_readiness" :
        (effects_verified ? "fresh_request_after_input_correction" : "inspect_domain_recovery");
    return {complete ? "completed" : "recovery_required",
        joined_content_preparation_result(source, receipt, nested.payload, continuation, content_verified, effects_verified),
        complete ? std::string() : nested.problem_code.empty() ? "make_ready_completed_effect_unknown" : nested.problem_code,
        complete ? std::string() : nested.problem_detail.empty() ? "Inspect retained owner effects before continuing" : nested.problem_detail};
}
} // namespace

JoinedPreparationOutcome prepare_joined(const fs::path& workspace,
    const SemanticActionRequest& request,
    const std::string& joined_plan,
    const std::function<bool(const std::string&, std::string&)>& checkpoint)
{
    const auto id = facman::core::InstanceId::parse_legacy(request.selected_instance_id);
    if (!id) return {"refused_before_effects", joined_preparation_result(joined_plan, {}, {}, "inspect_domain_recovery"),
        id.error().code, id.error().message};
    facman::workspace::InstanceRepository repository {facman::workspace::WorkspaceLayout(workspace)};
    auto instance = repository.load(id.value());
    if (!instance) return {"refused_before_effects", joined_preparation_result(joined_plan, {}, {}, "inspect_domain_recovery"),
        instance.error().code, instance.error().message};
    const auto instance_root = instance.value().root;
    const lifecycle::ProjectionRequest projection {request.selected_instance_id, request.launch_intent};
    const auto plan = json::parse(joined_plan);
    if (plan && decode_json_string_field(joined_plan, "schema") == "factorio.make_ready_joined_plan.v2")
        return prepare_joined_content(workspace, instance_root, request, joined_plan, checkpoint);
    const auto* configuration = plan.value().find("configuration_plan");
    std::vector<std::string> components;
    std::string configuration_transaction, selected_transaction, readiness;
    std::string problem, detail;
    bool uncertain = false;
    const auto prepare = [&](const MakeReadyStage& stage) {
        const auto owner = stage.component == MakeReadyComponent::routing_configuration
            ? lifecycle::prepare_configuration : lifecycle::prepare_selected_save;
        auto prepared = owner(workspace, projection, stage.plan_sha256,
            request.durable_operation_id, request.attempt_id);
        if (!prepared) {
            problem = prepared.error().code;
            detail = prepared.error().message;
            uncertain = prepared.error().kind != facman::core::OutcomeKind::refused;
            return false;
        }
        const char* unknown_result = std::getenv("FACMAN_TEST_MAKE_READY_OWNER_RESULT_UNKNOWN");
        if (unknown_result != nullptr && std::string(unknown_result) ==
                (stage.component == MakeReadyComponent::routing_configuration ? "configuration" : "selected_save"))
            prepared = facman::core::Result<std::string>::success("{}");
        auto receipt = make_ready_stage_result(stage, request.selected_instance_id,
            request.launch_intent, prepared.value());
        if (!receipt) {
            problem = receipt.error().code;
            detail = receipt.error().message;
            uncertain = true;
            return false;
        }
        components.push_back(receipt.take_value());
        const auto transaction = decode_json_string_field(prepared.value(), "transaction_id");
        if (stage.component == MakeReadyComponent::routing_configuration) configuration_transaction = transaction;
        else selected_transaction = transaction;
        const auto pending = action_result_json(request, "outcome_unknown", {},
            joined_preparation_result(joined_plan, components, {}), "semantic_action_dispatch_uncertain",
            "Completed preparation is retained; the accepted request must not be dispatched again", false, {"workspace_write"});
        std::string checkpoint_detail;
        if (!checkpoint(pending, checkpoint_detail)) {
            problem = "make_ready_checkpoint_failed";
            detail = checkpoint_detail;
            uncertain = true;
            return false;
        }
        return true;
    };
    if (configuration && !configuration->is_null())
        prepare({MakeReadyComponent::routing_configuration,
            decode_json_string_field(configuration->serialize(), "plan_sha256")});
    if (problem.empty() && !configuration_transaction.empty()) {
        if (std::getenv("FACMAN_TEST_MAKE_READY_EXIT_AFTER_CONFIGURATION") != nullptr) std::_Exit(88);
    }
    const auto pause = [&](const char* environment, const char* marker_name, const char* release_name) {
        if (std::getenv(environment) == nullptr) return;
        const auto marker = instance_root / marker_name;
        const auto release = instance_root / release_name;
        std::string paused_detail;
        if (!facman::base::write_text_new_atomic(marker, "ready\n", paused_detail)) {
            problem = "make_ready_test_pause_failed"; detail = paused_detail; uncertain = true;
        } else {
            bool released = false;
            for (unsigned retry = 0; retry < 2000U; ++retry) {
                std::error_code error;
                if (fs::exists(release, error) && !error) { released = true; break; }
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
            if (!released) { problem = "make_ready_test_pause_failed"; detail = "Test boundary timed out"; uncertain = true; }
        }
    };
    if (problem.empty()) pause("FACMAN_TEST_MAKE_READY_PAUSE_BEFORE_CONTEXT",
        ".facman-test-make-ready-before-context", ".facman-test-make-ready-context-release");
    if (problem.empty()) {
        auto verified = lifecycle::verify_joined_preparation(workspace, projection, joined_plan,
            configuration_transaction, {}, request.durable_operation_id, request.attempt_id);
        if (!verified) { problem = verified.error().code; detail = verified.error().message; }
    }
    const auto* selected_required = plan.value().find("selected_context_required");
    auto needed = selected_required ? selected_required->bool_value() : facman::core::Result<bool>::success(false);
    if (problem.empty() && needed && needed.value()) {
        auto selected = lifecycle::selected_save_preparation_plan(workspace, projection);
        if (!selected) { problem = selected.error().code; detail = selected.error().message; }
        else {
            auto still_bound = lifecycle::verify_joined_preparation(workspace, projection, joined_plan,
                configuration_transaction, {}, request.durable_operation_id, request.attempt_id);
            if (!still_bound) { problem = still_bound.error().code; detail = still_bound.error().message; }
            else prepare({MakeReadyComponent::selected_save_declared_context,
                decode_json_string_field(selected.value(), "plan_sha256")});
        }
    }
    pause("FACMAN_TEST_MAKE_READY_PAUSE_BEFORE_FINAL_RECEIPT",
        ".facman-test-make-ready-before-final-receipt", ".facman-test-make-ready-final-receipt-release");
    const bool effects_verified = !uncertain && lifecycle::joined_completed_effects_current(workspace,
        joined_plan, configuration_transaction, selected_transaction, request.durable_operation_id, request.attempt_id);
    if (problem.empty() && !components.empty() && !effects_verified) {
        problem = "make_ready_completed_effect_unknown";
        detail = "Applied preparation can no longer be verified; inspect recovery before continuing";
        readiness.clear();
        uncertain = true;
    }
    if (problem.empty()) {
        auto final = lifecycle::verify_joined_preparation(workspace, projection, joined_plan,
            configuration_transaction, selected_transaction, request.durable_operation_id, request.attempt_id);
        if (!final) { problem = final.error().code; detail = final.error().message; readiness.clear(); }
        else readiness = final.take_value();
    }
    const char* outcome = problem.empty() ? "completed" :
        (!components.empty() || uncertain ? "recovery_required" : "refused_before_effects");
    const char* continuation = problem.empty() ? "observe_readiness" :
        (!components.empty() && effects_verified ? "fresh_request_after_input_correction" : "inspect_domain_recovery");
    return {outcome, joined_preparation_result(joined_plan, components, readiness, continuation, effects_verified), problem, detail};
}

} // namespace facman::factorio::application
