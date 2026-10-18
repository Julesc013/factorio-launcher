// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "tui_product_shell.hpp"

#include "tui_product_model.hpp"
#include "tui_product_renderer.hpp"

#include "fl_json.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <cerrno>
#include <csignal>
#include <iostream>
#include <initializer_list>
#include <set>
#include <string>

#ifdef _WIN32
#include <conio.h>
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#else
#include <sys/select.h>
#include <termios.h>
#include <unistd.h>
#endif

namespace facman::tui {
namespace {

std::string scope_for(TuiPage page)
{
    switch (page) {
    case TuiPage::instances: return "instances";
    case TuiPage::installations: return "installations";
    case TuiPage::content: return "content";
    case TuiPage::saves: return "saves";
    case TuiPage::activity: return "activity_recovery";
    case TuiPage::settings: return "settings_support";
    case TuiPage::home:
    case TuiPage::advanced: return "launch_deck";
    }
    return "launch_deck";
}

std::string lower(std::string value)
{
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return value;
}

bool refresh(CommandClient& client, TuiState& state, std::ostream& error)
{
    const std::string scope = scope_for(state.page);
    auto identity = client.negotiate(
        scope, state.snapshot.selected_instance_id, state.search, state.launch_intent);
    if (!identity) {
        TuiEvent event;
        event.kind = TuiEventKind::transport_disconnected;
        event.value = identity.error().code + ": " + identity.error().message;
        state = reduce_tui_state(state, event);
        error << "Presentation refresh refused: " << event.value << '\n';
        return false;
    }
    TuiSnapshot snapshot = parse_presentation_snapshot(identity.value().raw_snapshot);
    if (snapshot.revision.empty() || snapshot.launch_intent != state.launch_intent) {
        TuiEvent event;
        event.kind = TuiEventKind::transport_disconnected;
        event.value = "Presentation snapshot could not be decoded or observation did not match";
        state = reduce_tui_state(state, event);
        error << event.value << '\n';
        return false;
    }
    if (snapshot.selected_instance_id.empty() && !state.snapshot.selected_instance_id.empty()) {
        // Selection identity is frontend interaction state. All descriptive
        // attributes remain backend-owned and must be reprojected.
        snapshot.selected_instance_id = state.snapshot.selected_instance_id;
    }
    if (snapshot.selected_instance_id.empty() && !snapshot.items.empty() &&
        (state.page == TuiPage::home || state.page == TuiPage::instances)) {
        const std::string selection = snapshot.items.front().id;
        auto selected = client.negotiate(scope, selection, state.search, state.launch_intent);
        if (selected) snapshot = parse_presentation_snapshot(selected.value().raw_snapshot);
    }
    if (snapshot.launch_intent != state.launch_intent) {
        state.transport_connected = false;
        state.refresh_requested = false;
        state.status = "Presentation observation did not match";
        return false;
    }
    TuiEvent event;
    event.kind = TuiEventKind::snapshot_received;
    event.snapshot = std::move(snapshot);
    state = reduce_tui_state(state, event);
    return true;
}

void navigate(TuiState& state, std::size_t index)
{
    TuiEvent event;
    event.kind = TuiEventKind::navigate;
    event.page = tui_page_at(index);
    state = reduce_tui_state(state, event);
}

void navigate_relative(TuiState& state, int direction)
{
    const std::size_t current = tui_page_index(state.page);
    const std::size_t index = direction < 0
        ? (current == 0U ? 7U : current - 1U)
        : (current + 1U) % 8U;
    navigate(state, index);
}

void select_relative(TuiState& state, int direction)
{
    if (state.snapshot.items.empty()) return;
    std::size_t index = state.selected_item;
    if (direction < 0) index = index == 0U ? state.snapshot.items.size() - 1U : index - 1U;
    else index = (index + 1U) % state.snapshot.items.size();
    TuiEvent event;
    event.kind = TuiEventKind::select;
    event.index = index;
    state = reduce_tui_state(state, event);
}

void select_action_relative(TuiState& state, int direction)
{
    if (state.snapshot.actions.empty()) return;
    std::size_t index = state.selected_action;
    if (direction < 0) index = index == 0U ? state.snapshot.actions.size() - 1U : index - 1U;
    else index = (index + 1U) % state.snapshot.actions.size();
    TuiEvent event;
    event.kind = TuiEventKind::select_action;
    event.index = index;
    state = reduce_tui_state(state, event);
}

void observe_launch_intent(TuiState& state, const std::string& intent)
{
    TuiEvent event;
    event.kind = TuiEventKind::observe_launch_intent;
    event.value = intent;
    state = reduce_tui_state(state, event);
}

void toggle_help(TuiState& state)
{
    state.help_visible = !state.help_visible;
    state.status = state.help_visible
        ? "Help: m Menu, s Selected Save, numbered pages, j/k or arrows, Enter, "
          "Tab/Shift+Tab, Space, /, Ctrl+R, Esc, Ctrl+C, q"
        : "Help closed";
}

int open_selected_item(TuiState& state)
{
    if (state.page == TuiPage::advanced) return kProductShellOpenAdvanced;
    if ((state.page == TuiPage::instances || state.page == TuiPage::home) &&
        !state.snapshot.items.empty()) {
        TuiEvent event;
        event.kind = TuiEventKind::select;
        event.index = state.selected_item;
        state = reduce_tui_state(state, event);
        return 0;
    }
    state.status = state.snapshot.items.empty()
        ? "No item is available to open"
        : "The selected item has no ordinary detail view yet";
    return 0;
}

std::string doctor_feedback(const facman::client::CommandResponse& response)
{
    if (!response.ok() || response.payload_string("schema") != "facman.semantic_action_result.v1" ||
        response.payload_string("action_id") != "doctor.run" ||
        response.payload_string("outcome") != "completed") return {};
    if (!response.parsed_payload) return {};
    const auto* action_payload = response.parsed_payload->find("action_payload");
    if (action_payload == nullptr || !action_payload->is_object()) return {};
    const auto* status = action_payload->find("status");
    if (status == nullptr || !status->is_string()) return {};
    auto decoded = status->string_value();
    if (!decoded) return {};
    std::string feedback = "Doctor completed: " + decoded.value();
    const auto append_first = [&feedback, action_payload](const char* key, const char* prefix) {
        const auto* values = action_payload->find(key);
        const auto* first = values != nullptr && values->is_array() ? values->at(0U) : nullptr;
        if (first == nullptr || !first->is_string()) return;
        auto value = first->string_value();
        if (value) feedback += std::string("; ") + prefix + value.value();
    };
    append_first("problems", "problem: ");
    append_first("suggested_fixes", "next: ");
    return feedback;
}

// Display only a correlated versioned receipt. Native journals remain the
// backend owner's authority; these fields do not independently verify effects.
bool joined_content_feedback_valid(const facman::client::CommandResponse& response,
    const facman::core::json::Value& result, bool partial)
{
    using V = facman::core::json::Value;
    const auto text = [](const V& v, const char* key) {
        const auto* p = v.find(key); auto s = p ? p->string_value() : facman::core::Result<std::string>::success("");
        return s ? s.value() : std::string();
    };
    const auto flag = [](const V& v, const char* key, bool value) {
        const auto* p = v.find(key); auto b = p ? p->bool_value() : facman::core::Result<bool>::success(!value);
        return b && b.value() == value;
    };
    const auto exact = [](const V& v, std::initializer_list<const char*> keys) {
        if (!v.is_object() || v.size() != keys.size()) return false;
        for (const auto* key : keys) if (!v.find(key)) return false;
        return true;
    };
    const auto strings = [](const V& v, std::initializer_list<const char*> keys) {
        for (const auto* key : keys) { const auto* p = v.find(key); if (!p || !p->is_string()) return false; }
        return true;
    };
    const auto digest = [](const std::string& s) {
        return s.size() == 64U && std::all_of(s.begin(), s.end(), [](char c) {
            return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'); });
    };
    const auto same = [](const V* a, const V* b) { return a && b && a->serialize() == b->serialize(); };
    const auto same_target = [](std::string actual, std::string expected) {
#ifdef _WIN32
        std::replace(actual.begin(), actual.end(), '/', '\\');
        std::replace(expected.begin(), expected.end(), '/', '\\');
        for (const auto& value : {actual, expected}) {
            if (value.rfind("\\\\?\\", 0) == 0U || value.rfind("\\\\.\\", 0) == 0U ||
                value.rfind("\\??\\", 0) == 0U) return false;
        }
#endif
        return actual == expected;
    };
    if (!response.parsed_payload || response.command != "presentation.action" || response.request_id.empty() ||
        response.payload_string("schema") != "facman.semantic_action_result.v1" ||
        response.payload_string("request_id") != response.request_id || response.operation.operation_id.empty() ||
        response.operation.attempt_id.empty()) return false;
    const auto* operation = response.parsed_payload->find("operation");
    if (!operation || !operation->is_object() || text(*operation, "operation_id") != response.operation.operation_id ||
        text(*operation, "attempt_id") != response.operation.attempt_id || text(*operation, "request_id") != response.request_id) return false;
    if (!exact(result, {"schema", "command", "plan", "plan_sha256", "completed_components", "continuation",
            "completed_effects_verified", "remaining_effects_blocked_before_effects", "readiness_observation",
            "preparation_complete", "fresh_revision_required", "readiness_complete", "execution_started", "permit_issued",
            "factorio_support_claim", "joined_result", "content_effect_verified"}) ||
        !strings(result, {"schema", "command", "plan_sha256", "continuation", "factorio_support_claim"}) ||
        text(result, "schema") != "factorio.make_ready_joined_result.v2" || text(result, "command") != "readiness.prepare_joined" ||
        text(result, "factorio_support_claim") != "unclaimed" || !flag(result, "content_effect_verified", true) ||
        !flag(result, "completed_effects_verified", true) || !flag(result, "execution_started", false) ||
        !flag(result, "permit_issued", false) || !flag(result, "readiness_complete", false) ||
        !flag(result, "remaining_effects_blocked_before_effects", partial) ||
        text(result, "continuation") != (partial ? "fresh_request_after_input_correction" : "observe_readiness")) return false;
    const auto& plan = *result.find("plan");
    if (!exact(plan, {"schema", "instance_id", "launch_intent", "desired_state", "inputs_sha256", "content_plan", "plan_sha256"}) ||
        !strings(plan, {"schema", "instance_id", "launch_intent", "inputs_sha256", "plan_sha256"}) ||
        text(plan, "schema") != "factorio.make_ready_joined_plan.v2" || text(plan, "instance_id").empty() ||
        (text(plan, "launch_intent") != "menu" && text(plan, "launch_intent") != "load_save") ||
        !digest(text(plan, "inputs_sha256")) || !digest(text(plan, "plan_sha256")) ||
        text(plan, "plan_sha256") != text(result, "plan_sha256")) return false;
    const auto& desired = *plan.find("desired_state");
    const auto& content = *plan.find("content_plan");
    if (text(*operation, "target_instance_id") != text(plan, "instance_id") ||
        text(*operation, "target_installation_id") != text(desired, "installation_id")) return false;
    if (!exact(desired, {"installation_id", "profile_id", "selected_save", "modset_lock_sha256"}) ||
        !strings(desired, {"installation_id", "profile_id", "selected_save", "modset_lock_sha256"}) ||
        text(desired, "installation_id").empty() || text(desired, "profile_id").empty() || !digest(text(desired, "modset_lock_sha256")) ||
        !exact(content, {"schema", "instance_id", "instance_identity", "root_identity", "lock_sha256", "mod_list_sha256", "owner_plan_id",
            "desired_mods", "before_targets", "artifact_inputs", "plan_sha256"}) ||
        !strings(content, {"schema", "instance_id", "instance_identity", "root_identity", "lock_sha256", "mod_list_sha256", "owner_plan_id", "plan_sha256"}) ||
        text(content, "schema") != "factorio.locked_content_activation_plan.v1" || text(content, "instance_id") != text(plan, "instance_id") ||
        text(content, "lock_sha256") != text(desired, "modset_lock_sha256")) return false;
    for (const auto* key : {"lock_sha256", "mod_list_sha256", "owner_plan_id", "plan_sha256"}) if (!digest(text(content, key))) return false;
    const auto& before = *content.find("before_targets");
    if (!exact(before, {"mod-list", "local-lock", "shared-lock"})) return false;
    for (const auto* key : {"mod-list", "local-lock", "shared-lock"}) {
        const auto& target = *before.find(key);
        if (!exact(target, {"path", "identity", "parent_identity", "present", "sha256"}) ||
            !strings(target, {"path", "identity", "parent_identity", "sha256"}) || text(target, "path").empty() || text(target, "parent_identity").empty()) return false;
        if (flag(target, "present", true)) {
            if (!digest(text(target, "sha256")) || text(target, "identity").rfind("file:", 0) != 0U) return false;
            if (std::string(key) != "mod-list" && text(target, "sha256") != text(content, "lock_sha256")) return false;
        } else if (!flag(target, "present", false) || std::string(key) != "mod-list" ||
            text(target, "identity") != "absent" || !text(target, "sha256").empty()) return false;
    }
    const auto* artifacts = content.find("artifact_inputs"); const auto* mods = content.find("desired_mods");
    if (!artifacts->is_array() || !mods->is_array() || artifacts->size() != mods->size() || mods->size() > 512U) return false;
    std::set<std::string> names;
    for (std::size_t i = 0; i < mods->size(); ++i) {
        const auto& mod = *mods->at(i); const auto& artifact = *artifacts->at(i);
        if (!exact(mod, {"name", "version", "file_name", "sha1", "sha256", "enabled", "virtual_package", "source"}) ||
            !strings(mod, {"name", "version", "file_name", "sha1", "sha256", "source"}) || !flag(mod, "enabled", true) ||
            (!flag(mod, "virtual_package", true) && !flag(mod, "virtual_package", false)) || text(mod, "name").empty() ||
            !names.insert(text(mod, "name")).second || !exact(artifact, {"path", "identity"}) ||
            !strings(artifact, {"path", "identity"}) || text(artifact, "path").empty() || text(artifact, "identity").rfind("file:", 0) != 0U) return false;
    }
    const auto* effects = result.find("completed_components");
    if (!effects->is_array() || effects->size() < 1U || effects->size() > 3U) return false;
    const auto& effect = *effects->at(0);
    if (!exact(effect, {"component", "owner_command", "transaction_id", "plan_sha256", "owner_result"}) ||
        !strings(effect, {"component", "owner_command", "transaction_id", "plan_sha256"}) ||
        text(effect, "component") != "locked_content_activation" || text(effect, "owner_command") != "modsets.apply") return false;
    const auto& owner = *effect.find("owner_result");
    if (!exact(owner, {"schema", "command", "instance_id", "plan_sha256", "transaction_id", "history_id", "operation_id", "attempt_id",
            "effect_binding_sha256", "apply_result", "execution_started", "permit_issued"}) ||
        !strings(owner, {"schema", "command", "instance_id", "plan_sha256", "transaction_id", "history_id", "operation_id", "attempt_id", "effect_binding_sha256"}) ||
        text(owner, "schema") != "factorio.locked_content_activation_result.v1" || text(owner, "command") != "modsets.apply" ||
        text(owner, "instance_id") != text(plan, "instance_id") || text(owner, "plan_sha256") != text(content, "plan_sha256") ||
        text(effect, "plan_sha256") != text(owner, "plan_sha256") || text(effect, "transaction_id") != text(owner, "transaction_id") ||
        text(owner, "transaction_id").empty() || !digest(text(owner, "history_id")) || !digest(text(owner, "effect_binding_sha256")) ||
        text(owner, "operation_id") != response.operation.operation_id || text(owner, "attempt_id") != response.operation.attempt_id ||
        !flag(owner, "execution_started", false) || !flag(owner, "permit_issued", false)) return false;
    const auto& applied = *owner.find("apply_result");
    if (!exact(applied, {"schema", "command", "status", "instance_id", "factorio_version", "plan_id", "transaction_id", "current_state_sha256", "desired_mods",
            "changes", "explanation", "budget_usage", "local_artifacts_only", "portal_access", "mutation_executed"}) ||
        !strings(applied, {"schema", "command", "status", "instance_id", "factorio_version", "plan_id", "transaction_id", "current_state_sha256"}) ||
        text(applied, "schema") != "factorio.modset_apply.v1" || text(applied, "command") != "modsets.apply" || text(applied, "status") != "applied" ||
        text(applied, "instance_id") != text(plan, "instance_id") || text(applied, "plan_id") != text(content, "owner_plan_id") ||
        text(applied, "transaction_id") != text(owner, "history_id") || !digest(text(applied, "current_state_sha256")) ||
        !same(applied.find("desired_mods"), mods) || !applied.find("changes")->is_array() || !applied.find("explanation")->is_array() ||
        !applied.find("budget_usage")->is_object() || !flag(applied, "local_artifacts_only", true) ||
        !flag(applied, "portal_access", false) || !flag(applied, "mutation_executed", true)) return false;
    const auto* nested = result.find("joined_result");
    if (nested->is_null()) return partial && effects->size() == 1U && flag(result, "preparation_complete", false) &&
        flag(result, "fresh_revision_required", true) && result.find("readiness_observation")->is_null();
    if (!exact(*nested, {"schema", "command", "plan", "plan_sha256", "completed_components", "continuation", "completed_effects_verified",
            "remaining_effects_blocked_before_effects", "readiness_observation", "preparation_complete", "fresh_revision_required", "readiness_complete",
            "execution_started", "permit_issued", "factorio_support_claim"}) || text(*nested, "schema") != "factorio.make_ready_joined_result.v1" ||
        text(*nested, "command") != "readiness.prepare_joined" || !flag(*nested, "execution_started", false) || !flag(*nested, "permit_issued", false) ||
        !flag(*nested, "readiness_complete", false) || text(*nested, "factorio_support_claim") != "unclaimed") return false;
    const auto* nested_plan = nested->find("plan"); const auto* nested_effects = nested->find("completed_components");
    if (!nested_plan || !exact(*nested_plan, {"schema", "instance_id", "launch_intent", "desired_state", "inputs_sha256", "configuration_plan",
            "configuration_sha256", "configuration_before_identity", "selected_context_before_identity", "selected_parent_before_identity",
            "selected_context_target", "selected_context_required", "selected_save_sha256", "plan_sha256"}) ||
        !strings(*nested_plan, {"schema", "instance_id", "launch_intent", "inputs_sha256", "configuration_sha256", "configuration_before_identity",
            "selected_context_before_identity", "selected_parent_before_identity", "selected_context_target", "selected_save_sha256", "plan_sha256"}) ||
        text(*nested_plan, "schema") != "factorio.make_ready_joined_plan.v1" || !digest(text(*nested_plan, "inputs_sha256")) ||
        !digest(text(*nested_plan, "configuration_sha256")) || !digest(text(*nested_plan, "plan_sha256")) ||
        (!flag(*nested_plan, "selected_context_required", true) && !flag(*nested_plan, "selected_context_required", false)) ||
        !same(nested_plan->find("desired_state"), &desired) || text(*nested_plan, "instance_id") != text(plan, "instance_id") ||
        text(*nested_plan, "launch_intent") != text(plan, "launch_intent") || !nested_effects->is_array() ||
        nested_effects->size() + 1U != effects->size() || text(*nested_plan, "plan_sha256") != text(*nested, "plan_sha256")) return false;
    std::set<std::string> transactions {text(owner, "transaction_id")};
    std::set<std::string> components;
    const auto* configuration = nested_plan->find("configuration_plan");
    if (!configuration->is_null() && (!exact(*configuration, {"plan_sha256", "component", "target"}) ||
        !strings(*configuration, {"plan_sha256", "component", "target"}) || !digest(text(*configuration, "plan_sha256")) ||
        text(*configuration, "target").empty() || (text(*configuration, "component") != "missing_routing_configuration" &&
            text(*configuration, "component") != "existing_routing_configuration"))) return false;
    for (std::size_t i = 0; i < nested_effects->size(); ++i) {
        const auto& item = *nested_effects->at(i);
        if (!same(&item, effects->at(i + 1U)) || !exact(item, {"component", "owner_command", "transaction_id", "plan_sha256", "owner_result"}) ||
            !strings(item, {"component", "owner_command", "transaction_id", "plan_sha256"}) || !digest(text(item, "plan_sha256")) ||
            !transactions.insert(text(item, "transaction_id")).second || text(item, "transaction_id").empty() ||
            !components.insert(text(item, "component")).second) return false;
        const bool config = text(item, "component") == "routing_configuration";
        const auto* child = item.find("owner_result");
        if ((!config && text(item, "component") != "selected_save_declared_context") || !child || !child->is_object() ||
            !strings(*child, {"schema", "command", "status", "instance_id", "transaction_id", "target", "composition", "factorio_support_claim"}) ||
            text(item, "owner_command") != (config ? "readiness.prepare_configuration" : "readiness.prepare_selected_save") ||
            text(*child, "schema") != (config ? "factorio.configuration_preparation_result.v1" : "factorio.selected_save_preparation_result.v1") ||
            text(*child, "command") != text(item, "owner_command") || text(*child, "transaction_id") != text(item, "transaction_id") ||
            text(*child, "instance_id") != text(plan, "instance_id") || !flag(*child, "mutation_executed", true) ||
            !flag(*child, "execution_started", false) || !flag(*child, "permit_issued", false) ||
            text(*child, "composition") != "partial" || text(*child, "factorio_support_claim") != "unclaimed") return false;
        if (config) {
            const bool reconciled = text(*child, "status") == "routing_configuration_reconciled";
            if (configuration->is_null() || (i != 0U) ||
                text(item, "plan_sha256") != text(*configuration, "plan_sha256") ||
                !same_target(text(*child, "target"), text(*configuration, "target")) ||
                text(*configuration, "component") != (reconciled ? "existing_routing_configuration" : "missing_routing_configuration") ||
                (!reconciled && text(*child, "status") != "routing_configuration_created") || !flag(*child, "existing_settings_modified", false)) return false;
            if (reconciled) {
                if (!exact(*child, {"schema", "command", "status", "instance_id", "transaction_id", "target", "composition", "factorio_support_claim",
                        "mutation_executed", "execution_started", "permit_issued", "existing_settings_modified", "routing_values_modified", "original_file_preserved"}) ||
                    !flag(*child, "routing_values_modified", true) || !flag(*child, "original_file_preserved", true)) return false;
            } else if (!exact(*child, {"schema", "command", "status", "instance_id", "transaction_id", "target", "composition", "factorio_support_claim",
                    "mutation_executed", "execution_started", "permit_issued", "existing_settings_modified"})) return false;
        } else if (!exact(*child, {"schema", "command", "status", "instance_id", "transaction_id", "target", "composition", "factorio_support_claim",
                "mutation_executed", "execution_started", "permit_issued", "save_content_modified"}) ||
            !flag(*child, "save_content_modified", false) || text(*child, "status") != "selected_context_recorded" ||
            !flag(*nested_plan, "selected_context_required", true) ||
            !same_target(text(*child, "target"), text(*nested_plan, "selected_context_target")) ||
            (!configuration->is_null() && components.count("routing_configuration") == 0U)) return false;
    }
    if (partial) {
        const bool empty = nested_effects->size() == 0U;
        return flag(result, "preparation_complete", false) && flag(result, "fresh_revision_required", true) &&
            result.find("readiness_observation")->is_null() && flag(*nested, "preparation_complete", false) &&
            flag(*nested, "fresh_revision_required", true) && nested->find("readiness_observation")->is_null() &&
            text(*nested, "continuation") == (empty ? "inspect_domain_recovery" : "fresh_request_after_input_correction") &&
            flag(*nested, "completed_effects_verified", !empty) && flag(*nested, "remaining_effects_blocked_before_effects", !empty);
    }
    const bool prepared = flag(*nested, "preparation_complete", true);
    const auto* observed = nested->find("readiness_observation");
    if (!observed || !observed->is_object() ||
        !strings(*observed, {"schema", "instance_id", "launch_intent", "configuration_state", "preparation_state", "readiness_digest", "freshness", "play_authority_state"}) ||
        text(*observed, "schema") != "factorio.instance_readiness.v1" || text(*observed, "instance_id") != text(plan, "instance_id") ||
        text(*observed, "launch_intent") != text(plan, "launch_intent") || !digest(text(*observed, "readiness_digest")) ||
        text(*observed, "freshness") != "current" || text(*observed, "play_authority_state") != "unavailable" ||
        !flag(*observed, "execution_started", false) || !flag(*observed, "permit_issued", false)) return false;
    const auto configuration_state = text(*observed, "configuration_state"), preparation_state = text(*observed, "preparation_state");
    if ((configuration_state != "ready" && configuration_state != "degraded" && configuration_state != "blocked") ||
        (preparation_state != "already_prepared" && preparation_state != "changes_required" && preparation_state != "unavailable") ||
        prepared != (configuration_state == "ready" && preparation_state == "already_prepared")) return false;
    return (prepared || flag(*nested, "preparation_complete", false)) && flag(result, "preparation_complete", prepared) &&
        flag(result, "fresh_revision_required", !prepared) && same(result.find("readiness_observation"), nested->find("readiness_observation")) &&
        nested->find("readiness_observation")->is_object() && text(*nested, "continuation") == "observe_readiness" &&
        flag(*nested, "remaining_effects_blocked_before_effects", false) && flag(*nested, "fresh_revision_required", !prepared) &&
        flag(*nested, "completed_effects_verified", nested_effects->size() != 0U);
}

std::string operation_feedback(const facman::client::CommandResponse& response)
{
    const bool semantic_action =
        response.payload_string("schema") == "facman.semantic_action_result.v1";
    const std::string outcome = semantic_action
        ? response.payload_string("outcome")
        : facman::client::operation_outcome_name(response.operation.outcome);
    const auto* preparation = response.parsed_payload ? response.parsed_payload->find("action_payload") : nullptr;
    if (semantic_action && response.ok() && outcome == "completed" &&
        response.payload_string("action_id") == "snapshots.create" && preparation && preparation->is_object()) {
        const auto text = [preparation](const char* key) {
            const auto* field = preparation->find(key);
            auto value = field ? field->string_value() : facman::core::Result<std::string>::success({});
            return value ? value.value() : std::string();
        };
        if (text("schema") == "factorio.snapshot_report.v1" && text("command") == "snapshots.create" &&
            text("status") == "ok" && !text("path").empty()) return "Snapshot created: " + text("path");
    }
    if (preparation && preparation->is_object() && response.payload_string("action_id") == "readiness.prepare_joined") {
        const auto text = [preparation](const char* key) {
            const auto* field = preparation->find(key);
            auto value = field ? field->string_value() : facman::core::Result<std::string>::success({});
            return value ? value.value() : std::string();
        };
        const auto flag = [preparation](const char* key, bool expected) {
            const auto* field = preparation->find(key);
            auto value = field ? field->bool_value() : facman::core::Result<bool>::failure({"missing", "missing", {}});
            return value && value.value() == expected;
        };
        const bool v2 = text("schema") == "factorio.make_ready_joined_result.v2";
        if (v2 && !joined_content_feedback_valid(response, *preparation, outcome == "recovery_required"))
            return "Preparation needs attention; inspect the original request and domain recovery before continuing";
        if ((text("schema") == "factorio.make_ready_joined_result.v1" ||
                v2) &&
            flag("execution_started", false) && flag("permit_issued", false) && flag("readiness_complete", false)) {
            const auto continuation = text("continuation");
            if (outcome == "completed" && continuation == "observe_readiness")
                return "Current settings were prepared; review remaining readiness checks; Play remains unavailable";
            const auto* effects = preparation->find("completed_components");
            if (outcome == "recovery_required" && continuation == "fresh_request_after_input_correction" &&
                effects && effects->is_array() && effects->size() != 0U && flag("completed_effects_verified", true) &&
                flag("remaining_effects_blocked_before_effects", true))
                return "Applied preparation is retained; correct changed inputs, refresh and confirm a new request";
        }
    }
    if (outcome == "outcome_unknown") {
        return "Outcome unknown; effects may have occurred; inspect recovery before retrying";
    }
    if (outcome == "recovery_required") {
        return "Recovery required; inspect authoritative recovery state before continuing";
    }
    if (outcome == "cancellation_requested_but_completed") {
        return "Cancellation was requested, but the operation completed";
    }
    if (outcome == "cancelled_before_dispatch") {
        return "Cancelled before dispatch; no effects occurred";
    }
    if (outcome == "refused_before_effects") {
        return "Refused before effects";
    }
    return outcome;
}

int activate_selected_action(CommandClient& client, TuiState& state)
{
    if (state.page == TuiPage::advanced) return kProductShellOpenAdvanced;
    if (state.snapshot.actions.empty()) {
        state.status = "No contextual action is available";
        return 0;
    }
    const std::size_t index = (std::min)(state.selected_action, state.snapshot.actions.size() - 1U);
    const TuiAction action = state.snapshot.actions[index];
    if (!state.transport_connected || state.refresh_requested || state.snapshot.revision.empty() ||
        state.snapshot.launch_intent != state.launch_intent) {
        state.pending_action.clear();
        state.status = "Action refused before effects: refresh the selected observation";
        return 0;
    }
    if (!action.available) {
        state.status = "Action refused before effects: " + action.blocker;
        return 0;
    }
    if (!action.input_fields.empty()) {
        if (state.form.id != action.id) {
            state.form = {};
            state.form.id = action.id;
            state.form.title = action.label;
            state.form.fields = action.input_fields;
            for (const auto& field : state.form.fields) {
                std::string value = field.default_value;
                if (field.id == "selected_instance_id" &&
                    !state.snapshot.selected_instance_id.empty()) {
                    value = state.snapshot.selected_instance_id;
                }
                if (!value.empty()) state.form.values[field.id] = value;
            }
            state.form.problems = validate_form(state.form);
            if (!state.form.problems.empty()) {
                state.status = "Review action input; enter field=value, then activate again";
                return 0;
            }
        }
        state.form.problems = validate_form(state.form);
        if (!state.form.problems.empty()) {
            state.status = "Action input is incomplete: " + state.form.problems.front();
            return 0;
        }
    }
    const bool effectful = action.effect != "read_only";
    if (effectful) {
        if (action.confirmation != "explicit") {
            state.status = "Action refused before effects: unsupported confirmation contract";
            return 0;
        }
        if (state.pending_action != action.id) {
            TuiEvent pending;
            pending.kind = TuiEventKind::activate_action;
            pending.name = action.id;
            state = reduce_tui_state(state, pending);
            state.status = "Confirm " + action.label +
                ": activate the same action again; Cancel returns without dispatch";
            return 0;
        }
        // Confirmation is single-use. Clear it before dispatch so transport
        // loss or an uncertain outcome can never turn the next activation
        // into an unreviewed retry.
        state.pending_action.clear();
    }

    const TuiActionIdentity identity = issue_action_identity(state, action.id);
    facman::core::json::ObjectBuilder payload;
    payload.add_string("action_id", action.id);
    payload.add_string("scope", scope_for(state.page));
    payload.add_string("launch_intent", state.snapshot.launch_intent);
    payload.add_string("expected_snapshot_revision", state.snapshot.revision);
    payload.add_string("request_id", identity.request_id);
    payload.add_string("idempotency_key", identity.idempotency_key);
    if (effectful) {
        payload.add_string("durable_operation_id", identity.durable_operation_id);
        payload.add_string("attempt_id", identity.attempt_id);
        payload.add_string("confirmation", "explicit");
    }
    if (!state.snapshot.selected_instance_id.empty()) {
        payload.add_string("selected_instance_id", state.snapshot.selected_instance_id);
    }
    for (const auto& field : action.input_fields) {
        const auto value = state.form.values.find(field.id);
        if (value != state.form.values.end() && !value->second.empty()) {
            payload.add_string(field.id, value->second);
        }
    }
    Invocation invocation;
    invocation.command = "presentation.action";
    invocation.payload = payload.serialize();
    invocation.request_id = identity.request_id;
    invocation.operation_id = identity.durable_operation_id;
    invocation.attempt_id = identity.attempt_id;
    invocation.allow_write = effectful;
    const auto response = client.execute(invocation);
    if (!response) {
        state.status = "Action transport error: " + response.error().code;
        return 0;
    }
    if (!response.value().ok()) {
        state.operation_status = operation_feedback(response.value());
        state.status = state.operation_status;
        if (!response.value().error_code.empty()) state.status += ": " + response.value().error_code;
        return 0;
    }

    TuiEvent event;
    event.kind = TuiEventKind::activate_action;
    event.name = action.id;
    state = reduce_tui_state(state, event);
    state.pending_action.clear();
    state.form = {};

    const std::string replacement_json =
        response.value().payload_member_json("replacement_snapshot");
    if (replacement_json != "null") {
        TuiSnapshot replacement = parse_presentation_snapshot(replacement_json);
        if (replacement.revision.empty() || replacement.scope != scope_for(state.page) ||
            replacement.launch_intent != state.launch_intent) {
            state.status = "Action response invalid: replacement snapshot did not match the active scope";
            return 0;
        }
        TuiEvent received;
        received.kind = TuiEventKind::snapshot_received;
        received.snapshot = std::move(replacement);
        state = reduce_tui_state(state, received);
    }
    state.operation_status = operation_feedback(response.value());
    state.status = action_response_status(action, response.value());
    const std::string feedback = doctor_feedback(response.value());
    if (!feedback.empty()) state.status = feedback;

    if (response.value().payload_member_json("invalidation") != "null") {
        state.status += "; refreshing authoritative state";
        state.refresh_requested = true;
    }
    return 0;
}

int process_line(CommandClient& client, TuiState& state, std::string command)
{
    if (!command.empty() && command.back() == '\r') command.pop_back();
    const std::string normalized = lower(command);
    if (normalized == "q" || normalized == "quit" || normalized == "exit") {
        state.quit_requested = true;
        return 0;
    }
    if (normalized == "help" || normalized == "f1" || normalized == "?") {
        toggle_help(state);
        return 0;
    }
    if (normalized == "m" || normalized == "menu" ||
        normalized == "s" || normalized == "selected-save") {
        observe_launch_intent(
            state, normalized == "m" || normalized == "menu" ? "menu" : "load_save");
        return 0;
    }
    if (normalized == "r" || normalized == "refresh") {
        TuiEvent event;
        event.kind = TuiEventKind::refresh;
        state = reduce_tui_state(state, event);
        return 0;
    }
    if (normalized == "j" || normalized == "down") {
        select_relative(state, 1);
        return 0;
    }
    if (normalized == "k" || normalized == "up") {
        select_relative(state, -1);
        return 0;
    }
    if (normalized == "tab" || normalized == "next-action") {
        select_action_relative(state, 1);
        return 0;
    }
    if (normalized == "shift-tab" || normalized == "previous-action") {
        select_action_relative(state, -1);
        return 0;
    }
    if (normalized == "space" || normalized == "run" || normalized == "action") {
        return activate_selected_action(client, state);
    }
    const std::size_t equals = command.find('=');
    if (!state.form.id.empty() && equals != std::string::npos && equals != 0U) {
        TuiEvent event;
        event.kind = TuiEventKind::edit_field;
        event.name = command.substr(0U, equals);
        event.value = command.substr(equals + 1U);
        const auto known = std::find_if(
            state.form.fields.begin(), state.form.fields.end(),
            [&event](const FormFieldSpec& field) { return field.id == event.name; });
        if (known == state.form.fields.end()) {
            state.status = "Unknown action input field: " + event.name;
            return 0;
        }
        state = reduce_tui_state(state, event);
        state.status = state.form.problems.empty()
            ? "Action input updated; activate the action to continue"
            : "Action input updated; " + state.form.problems.front();
        return 0;
    }
    if (normalized == "enter" || normalized == "open" || normalized.empty()) {
        return open_selected_item(state);
    }
    if (normalized == "a" || normalized == "advanced") {
        navigate(state, 7U);
        return kProductShellOpenAdvanced;
    }
    if (command.front() == '/') {
        TuiEvent event;
        event.kind = TuiEventKind::search;
        event.value = command.substr(1U);
        state = reduce_tui_state(state, event);
        return 0;
    }
    if (command.size() == 1U && command[0] >= '1' && command[0] <= '8') {
        navigate(state, static_cast<std::size_t>(command[0] - '1'));
        return 0;
    }
    state.status = "Unknown input; use help for portable keys";
    return 0;
}

class FullScreenSession {
public:
    explicit FullScreenSession(std::ostream& output) : output_(output)
    {
        resume();
    }

    ~FullScreenSession() noexcept
    {
        try {
            suspend();
        } catch (...) {
            // Terminal restoration is best-effort during stack unwinding.
        }
    }

    void suspend()
    {
        if (!active_) return;
        ProductRenderer::leave_full_screen(output_);
        active_ = false;
    }

    void resume()
    {
        if (active_) return;
        ProductRenderer::enter_full_screen(output_);
        active_ = true;
    }

private:
    std::ostream& output_;
    bool active_ = false;
};

#ifndef _WIN32
volatile std::sig_atomic_t pending_terminal_signal = 0;
volatile std::sig_atomic_t terminal_continue_observed = 0;

void terminal_signal_handler(int signal_number)
{
    pending_terminal_signal = signal_number;
}

void terminal_continue_handler(int)
{
    terminal_continue_observed = 1;
}

class TerminalSignals {
public:
    TerminalSignals()
    {
        sigemptyset(&handled_signals_);
        for (const int signal_number : signals_) {
            sigaddset(&handled_signals_, signal_number);
        }
        struct sigaction action {};
        action.sa_handler = terminal_signal_handler;
        action.sa_mask = handled_signals_;
        action.sa_flags = 0;
        for (std::size_t index = 0U; index < signals_.size(); ++index) {
            sigaction(signals_[index], &action, &original_[index]);
        }
    }

    ~TerminalSignals()
    {
        for (std::size_t index = 0U; index < signals_.size(); ++index) {
            sigaction(signals_[index], &original_[index], nullptr);
        }
    }

    int take() noexcept
    {
        sigset_t previous_mask {};
        const bool blocked =
            sigprocmask(SIG_BLOCK, &handled_signals_, &previous_mask) == 0;
        const int result = pending_terminal_signal;
        pending_terminal_signal = 0;
        if (blocked) sigprocmask(SIG_SETMASK, &previous_mask, nullptr);
        return result;
    }

    void suspend_process()
    {
        struct sigaction action {};
        struct sigaction original_continue {};
        action.sa_handler = terminal_continue_handler;
        sigemptyset(&action.sa_mask);
        action.sa_flags = 0;
        sigaction(SIGCONT, &action, &original_continue);
        terminal_continue_observed = 0;

        action.sa_handler = SIG_DFL;
        sigemptyset(&action.sa_mask);
        sigaction(SIGTSTP, &action, nullptr);
        std::raise(SIGTSTP);
        // POSIX permits a job-control stop signal to be discarded for an
        // orphaned process group. Headless PTY hosts can therefore return
        // from SIGTSTP even though the user explicitly requested suspend.
        // SIGSTOP supplies the same resumable boundary in that environment;
        // an ordinary interactive shell observes SIGCONT before returning.
        if (terminal_continue_observed == 0) std::raise(SIGSTOP);

        sigaction(SIGCONT, &original_continue, nullptr);
        action.sa_handler = terminal_signal_handler;
        action.sa_mask = handled_signals_;
        sigaction(SIGTSTP, &action, nullptr);
    }

private:
    const std::array<int, 4U> signals_ {SIGINT, SIGTERM, SIGHUP, SIGTSTP};
    sigset_t handled_signals_ {};
    std::array<struct sigaction, 4U> original_ {};
};
#else
class TerminalSignals {
public:
    int take() const noexcept { return 0; }
};
#endif

inline constexpr int kTerminalNoInput = -2;

class RawTerminal {
public:
    explicit RawTerminal(bool enabled) : enabled_(enabled)
    {
#ifdef _WIN32
        if (enabled_) {
            input_ = GetStdHandle(STD_INPUT_HANDLE);
            DWORD mode = 0;
            if (input_ != INVALID_HANDLE_VALUE && GetConsoleMode(input_, &mode) != 0) {
                original_mode_ = mode;
                const DWORD raw = mode & ~(ENABLE_LINE_INPUT | ENABLE_ECHO_INPUT | ENABLE_PROCESSED_INPUT);
                active_ = SetConsoleMode(input_, raw) != 0;
            }
        }
#else
        if (enabled_ && tcgetattr(STDIN_FILENO, &original_) == 0) {
            raw_ = original_;
            raw_.c_lflag &= static_cast<tcflag_t>(~(ICANON | ECHO | ISIG | IEXTEN));
            raw_.c_iflag &= static_cast<tcflag_t>(~(IXON | ICRNL));
            raw_.c_cc[VMIN] = 1;
            raw_.c_cc[VTIME] = 0;
            resume();
        }
#endif
    }

    ~RawTerminal()
    {
#ifdef _WIN32
        if (active_) SetConsoleMode(input_, original_mode_);
#else
        suspend();
#endif
    }

    void suspend()
    {
#ifndef _WIN32
        if (active_) {
            tcsetattr(STDIN_FILENO, TCSANOW, &original_);
            active_ = false;
        }
#endif
    }

    void resume()
    {
#ifndef _WIN32
        if (enabled_ && !active_) active_ = tcsetattr(STDIN_FILENO, TCSANOW, &raw_) == 0;
#endif
    }

    int read()
    {
#ifdef _WIN32
        if (!enabled_) return std::cin.get();
        return _getwch();
#else
        fd_set input;
        FD_ZERO(&input);
        FD_SET(STDIN_FILENO, &input);
        timeval timeout {0, 100000};
        const int ready = select(STDIN_FILENO + 1, &input, nullptr, nullptr, &timeout);
        if (ready == 0) return kTerminalNoInput;
        if (ready < 0) return EOF;
        unsigned char value = 0;
        return ::read(STDIN_FILENO, &value, 1U) == 1 ? static_cast<int>(value) : EOF;
#endif
    }

    int read_continuation()
    {
#ifdef _WIN32
        return read();
#else
        fd_set input;
        FD_ZERO(&input);
        FD_SET(STDIN_FILENO, &input);
        timeval timeout {0, 30000};
        if (select(STDIN_FILENO + 1, &input, nullptr, nullptr, &timeout) <= 0) return EOF;
        return read();
#endif
    }

private:
    bool enabled_ = false;
#ifdef _WIN32
    bool active_ = false;
    HANDLE input_ = INVALID_HANDLE_VALUE;
    DWORD original_mode_ = 0;
#else
    bool active_ = false;
    termios original_ {};
    termios raw_ {};
#endif
};

inline constexpr int kProductShellFallbackLinear = 65;

int run_full_screen(
    CommandClient& client,
    TuiState& state,
    std::ostream& output,
    std::ostream& error,
    const TerminalCapabilities& capabilities,
    bool unicode)
{
    TerminalSignals signals;
    FullScreenSession screen(output);
    RawTerminal terminal(true);
    TerminalCapabilities current_capabilities = capabilities;
    int result = 0;
    while (!state.quit_requested) {
        if (state.refresh_requested) refresh(client, state, error);
        current_capabilities = observe_terminal_capabilities(false);
        if (current_capabilities.selected_renderer != TerminalRendererMode::full_screen) {
            const std::string prior_status = state.status;
            state.status = "Switched to portable linear mode: " + current_capabilities.selection_reason;
            if (!prior_status.empty()) state.status += "; prior status: " + prior_status;
            return kProductShellFallbackLinear;
        }
        TuiEvent resized;
        resized.kind = TuiEventKind::resize;
        resized.columns = current_capabilities.observed.columns;
        resized.rows = current_capabilities.observed.rows;
        state = reduce_tui_state(state, resized);
        ProductRenderer::render_full_screen(
            output, make_tui_render_model(state, unicode), current_capabilities);
        int signal_number = signals.take();
        const int key = signal_number == 0 ? terminal.read() : kTerminalNoInput;
        if (signal_number == 0) signal_number = signals.take();
#ifndef _WIN32
        if (signal_number == SIGTSTP) {
            terminal.suspend();
            screen.suspend();
            signals.suspend_process();
            screen.resume();
            terminal.resume();
            if (refresh(client, state, error)) {
                state.status = "Terminal session resumed; authoritative state refreshed";
            }
            continue;
        }
        if (signal_number == SIGINT) {
            TuiEvent event;
            event.kind = TuiEventKind::cancel;
            state = reduce_tui_state(state, event);
            continue;
        }
        if (signal_number == SIGTERM || signal_number == SIGHUP) {
            result = 128 + signal_number;
            break;
        }
#else
        (void)signal_number;
#endif
        if (key == kTerminalNoInput) continue;
        if (key == EOF || key == 'q') break;
        if (key >= '1' && key <= '8') navigate(state, static_cast<std::size_t>(key - '1'));
        else if (key == 'm' || key == 's') {
            observe_launch_intent(state, key == 'm' ? "menu" : "load_save");
        }
        else if (key == 'j') select_relative(state, 1);
        else if (key == 'k') select_relative(state, -1);
        else if (key == '\t') select_action_relative(state, 1);
        else if (key == '\r' || key == '\n') {
            result = open_selected_item(state);
            if (result == kProductShellOpenAdvanced) break;
        } else if (key == ' ') {
            result = activate_selected_action(client, state);
            if (result == kProductShellOpenAdvanced) break;
        } else if (key == 0x10) {
            state.command_palette_visible = !state.command_palette_visible;
            state.status = state.command_palette_visible
                ? "Command palette: choose Advanced for the full generated catalogue"
                : "Command palette closed";
        } else if (key == 0x12) {
            TuiEvent event;
            event.kind = TuiEventKind::refresh;
            state = reduce_tui_state(state, event);
        } else if (key == 0x03) {
            TuiEvent event;
            event.kind = TuiEventKind::cancel;
            state = reduce_tui_state(state, event);
#ifndef _WIN32
        } else if (key == 0x1a) {
            terminal.suspend();
            screen.suspend();
            signals.suspend_process();
            screen.resume();
            terminal.resume();
            if (refresh(client, state, error)) {
                state.status = "Terminal session resumed; authoritative state refreshed";
            }
#endif
        } else if (key == '/') {
            std::string query;
            output << "\x1b[" << current_capabilities.observed.rows << ";1H\x1b[KSearch: " << std::flush;
            for (;;) {
                const int item = terminal.read();
                if (item == EOF || item == '\r' || item == '\n') break;
                if (item == 27) { query.clear(); break; }
                if ((item == 8 || item == 127) && !query.empty()) query.pop_back();
                else if (item >= 32 && item <= 126) query.push_back(static_cast<char>(item));
                output << "\r\x1b[KSearch: " << query << std::flush;
            }
            TuiEvent event;
            event.kind = TuiEventKind::search;
            event.value = std::move(query);
            state = reduce_tui_state(state, event);
        }
#ifdef _WIN32
        else if (key == 0 || key == 224) {
            const int extended = terminal.read();
            if (extended == 72) select_relative(state, -1);
            else if (extended == 80) select_relative(state, 1);
            else if (extended == 59) toggle_help(state);
        }
        else if (key == 27) {
            TuiEvent event;
            event.kind = TuiEventKind::cancel;
            state = reduce_tui_state(state, event);
        }
#else
        else if (key == 0x1b) {
            const int bracket = terminal.read_continuation();
            if (bracket == EOF) {
                TuiEvent event;
                event.kind = TuiEventKind::cancel;
                state = reduce_tui_state(state, event);
                continue;
            }
            const int direction = terminal.read_continuation();
            if (bracket == '[' && direction == 'A') select_relative(state, -1);
            else if (bracket == '[' && direction == 'B') select_relative(state, 1);
            else if (bracket == '[' && direction == 'C') navigate_relative(state, 1);
            else if (bracket == '[' && direction == 'D') navigate_relative(state, -1);
            else if (bracket == '[' && direction == 'Z') select_action_relative(state, -1);
            else if ((bracket == 'O' || bracket == '[') && direction == 'P') toggle_help(state);
        }
#endif
    }
    return result;
}

} // namespace

std::string action_response_status(
    const TuiAction& action,
    const facman::client::CommandResponse& response)
{
    const std::string semantic = operation_feedback(response);
    if (!response.ok()) {
        return response.error_code.empty() ? semantic : semantic + ": " + response.error_code;
    }
    const std::string action_outcome =
        response.payload_string("schema") == "facman.semantic_action_result.v1"
        ? response.payload_string("outcome")
        : facman::client::operation_outcome_name(response.operation.outcome);
    if (action_outcome != "completed") return semantic;
    if (action.id == "readiness.prepare_joined" || action.id == "snapshots.create") return semantic;
    return action.label + " completed";
}

int run_product_shell(
    CommandClient& client,
    std::istream& input,
    std::ostream& output,
    std::ostream& error,
    const TerminalCapabilities& capabilities,
    const ProductShellOptions& options)
{
    TuiState state;
    state.columns = capabilities.observed.columns == 0U ? 80U : capabilities.observed.columns;
    state.rows = capabilities.observed.rows == 0U ? 24U : capabilities.observed.rows;
    const bool full_screen = !options.force_linear &&
        capabilities.selected_renderer == TerminalRendererMode::full_screen &&
        &input == &std::cin && &output == &std::cout;
    if (full_screen) {
        const int result = run_full_screen(client, state, output, error, capabilities, options.unicode);
        if (result != kProductShellFallbackLinear) return result;
    }
    while (!state.quit_requested) {
        if (state.refresh_requested) refresh(client, state, error);
        ProductRenderer::render_linear(output, make_tui_render_model(state, options.unicode));
        std::string command;
        if (!std::getline(input, command)) break;
        const int result = process_line(client, state, std::move(command));
        if (result == kProductShellOpenAdvanced) return result;
    }
    return 0;
}

} // namespace facman::tui
