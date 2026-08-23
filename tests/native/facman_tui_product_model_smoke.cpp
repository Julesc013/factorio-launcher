// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "tui_product_model.hpp"
#include "tui_product_renderer.hpp"
#include "tui_product_shell.hpp"

#include <chrono>
#include <sstream>
#include <string>
#include <utility>

int main()
{
    using namespace facman::tui;
    const std::string source = R"({
      "schema":"facman.presentation_snapshot.v1",
      "revision":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "selected_context":{"instance_id":"main"},
      "page":{"scope":"launch_deck","summary":"Launch Deck for main","items":[
        {"instance_id":"main","display_name":"Main world","factorio_version":"2.0.77","profile":"default","selected":true},
        {"instance_id":"test","display_name":"Test world","factorio_version":"2.0.77","profile":"safe","selected":false}
      ]},
      "readiness":{"schema":"factorio.instance_readiness.v1","configuration_state":"ready"},
      "workspace_health":{"status":"available","workspace":"C:/FacMan","workspace_id":"workspace-main","initialized":true},
      "specific_blockers":[{"code":"route_unqualified","message":"Real Play remains gated"}],
      "available_semantic_actions":[
        {"action_id":"presentation.refresh","label":"Refresh","role":"manage","effects":["read_only"],"availability":"available","refusal":null},
        {"action_id":"doctor.run","label":"Run Doctor","role":"diagnostic","effects":["read_only"],"availability":"available","refusal":null},
        {"action_id":"launch.play","label":"Play","role":"primary","effects":["process_execution"],"confirmation":"explicit","availability":"refused","refusal":{"code":"execution_authority_unavailable","reason":"not admitted"}},
        {"action_id":"sessions.stop","label":"Stop session","role":"session","effects":["process_control"],"confirmation":"explicit","availability":"available","refusal":null}
      ],
      "active_operations":[{"schema":"facman.presentation_operation.v1","operation_id":"operation-running","state":"running","authority_scope":"fixture_only"}],
      "last_run":{"authority_state":"outcome_unknown","record":null}
    })";
    TuiSnapshot snapshot = parse_presentation_snapshot(source);
    if (snapshot.revision.size() != 64U || snapshot.items.size() != 2U ||
        snapshot.selected_instance_id != "main" || snapshot.readiness != "ready" ||
        snapshot.last_run != "outcome_unknown" || snapshot.blockers.size() != 1U ||
        snapshot.actions.size() != 4U || snapshot.actions[1U].role != "diagnostic" ||
        snapshot.actions[1U].effect != "read_only" ||
        snapshot.actions[2U].effect != "process_execution" ||
        snapshot.actions[2U].confirmation != "explicit" ||
        snapshot.actions[3U].effect != "process_control" ||
        snapshot.actions[3U].confirmation != "explicit" ||
        !snapshot.workspace_initialized || snapshot.workspace_status != "available" ||
        snapshot.workspace_path != "C:/FacMan" ||
        snapshot.workspace_id != "workspace-main" ||
        snapshot.active_operation != "running") return 2;

    const TuiSnapshot installation_snapshot = parse_presentation_snapshot(R"({
      "schema":"facman.presentation_snapshot.v1",
      "revision":"bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      "selected_context":{},
      "page":{"scope":"installations","summary":"Registered installations","items":[
        {"installation_id":"portable","version":"2.0.77","ownership":"imported",
         "installation_layout":"portable_archive","distribution_origin":"local_archive",
         "strict_isolation_eligibility":"candidate","root":"C:/Factorio"}
      ]},
      "available_semantic_actions":[],"active_operations":[],
      "last_run":{"authority_state":"no_record","record":null}
    })");
    if (installation_snapshot.items.size() != 1U ||
        installation_snapshot.items[0U].detail.find("portable_archive") == std::string::npos ||
        installation_snapshot.items[0U].detail.find("local_archive") == std::string::npos ||
        installation_snapshot.items[0U].detail.find("candidate") == std::string::npos ||
        installation_snapshot.items[0U].detail.find("C:/Factorio") == std::string::npos) return 28;

    const std::string completed_source = R"({
      "schema":"facman.presentation_snapshot.v1",
      "scope":"launch_deck",
      "revision":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "items":[],
      "selected_instance":null,
      "readiness":null,
      "available_semantic_actions":[],
      "active_operations":[],
      "last_run":{
        "authority_state":"authoritative_record_available",
        "record":{
          "schema":"ulk.session_record.v1",
          "state":"terminal",
          "terminal_result":{"outcome":"completed"}
        }
      }
    })";
    if (parse_presentation_snapshot(completed_source).last_run != "completed") return 16;

    TuiState state;
    TuiEvent received;
    received.kind = TuiEventKind::snapshot_received;
    received.snapshot = snapshot;
    state = reduce_tui_state(state, received);
    if (state.refresh_requested || !state.transport_connected || state.selected_action != 0U) return 3;

    TuiState settings_state = state;
    settings_state.page = TuiPage::settings;
    const TuiRenderModel settings_model = make_tui_render_model(settings_state, false);
    std::ostringstream settings_linear;
    ProductRenderer::render_linear(settings_linear, settings_model);
    if (settings_linear.str().find("Workspace: C:/FacMan") == std::string::npos ||
        settings_linear.str().find("Workspace status: available") == std::string::npos ||
        settings_linear.str().find("Workspace identity: workspace-main") ==
            std::string::npos) return 29;

    TuiEvent action_selection;
    action_selection.kind = TuiEventKind::select_action;
    action_selection.index = 2U;
    state = reduce_tui_state(state, action_selection);
    if (state.selected_action != 2U || state.status.find("unavailable") == std::string::npos) return 21;
    state = reduce_tui_state(state, received);
    if (state.selected_action != 2U) return 22;

    TuiEvent navigation;
    navigation.kind = TuiEventKind::navigate;
    navigation.page = TuiPage::instances;
    state = reduce_tui_state(state, navigation);
    TuiEvent selection;
    selection.kind = TuiEventKind::select;
    selection.index = 1U;
    state = reduce_tui_state(state, selection);
    TuiEvent search;
    search.kind = TuiEventKind::search;
    search.value = "test";
    state = reduce_tui_state(state, search);
    TuiEvent resize;
    resize.kind = TuiEventKind::resize;
    resize.columns = 20U;
    resize.rows = 5U;
    state = reduce_tui_state(state, resize);
    if (state.page != TuiPage::instances || state.snapshot.selected_instance_id != "test" ||
        state.search != "test" || state.columns != 20U || state.rows != 5U) return 4;

    const TuiActionIdentity first_identity = issue_action_identity(state, "installations.scan");
    const TuiActionIdentity second_identity = issue_action_identity(state, "installations.scan");
    if (first_identity.request_id != first_identity.idempotency_key ||
        second_identity.request_id != second_identity.idempotency_key ||
        first_identity.request_id == second_identity.request_id ||
        first_identity.durable_operation_id != "operation-" + first_identity.request_id ||
        first_identity.attempt_id != "attempt-" + first_identity.request_id ||
        first_identity.request_id.find("0123456789ab") == std::string::npos) return 17;

    state.form.fields = {
        {"name", "Name", FormFieldType::string, true, false, {}, {}, {}, {}},
        {"count", "Count", FormFieldType::integer, true, false, {}, {}, {}, {}},
        {"digest", "Digest", FormFieldType::digest, false, false, {}, {}, {}, {}},
        {"secret", "Secret reference", FormFieldType::secret_reference, false, true, {}, {}, {}, {}},
    };
    TuiEvent edit;
    edit.kind = TuiEventKind::edit_field;
    edit.name = "count";
    edit.value = "many";
    state = reduce_tui_state(state, edit);
    if (state.form.problems.size() != 2U ||
        std::string(form_field_type_name(FormFieldType::secret_reference)) != "secret-reference") return 5;

    TuiRenderModel model = make_tui_render_model(state, false);
    if (model.navigation.size() != 8U || model.active_navigation != 1U ||
        model.launch_deck.size() != 6U || model.actions.size() != 4U ||
        model.active_action != 0U || model.primary_action != "Refresh" ||
        model.focus != "Search: test") return 6;
    std::ostringstream linear;
    ProductRenderer::render_linear(linear, model);
    if (linear.str().find("Launch Deck") == std::string::npos ||
        linear.str().find("Actions") == std::string::npos ||
        linear.str().find("> Refresh") == std::string::npos ||
        linear.str().find("Focus: Search: test") == std::string::npos ||
        linear.str().find("\x1b[") != std::string::npos) return 7;

    TerminalCapabilities capabilities;
    capabilities.observed.columns = 80U;
    capabilities.observed.rows = 24U;
    std::ostringstream full;
    ProductRenderer::render_full_screen(full, model, capabilities);
    if (full.str().find("\x1b[H") == std::string::npos || full.str().find("Instances") == std::string::npos) return 8;

    capabilities.observed.columns = 40U;
    capabilities.observed.rows = 12U;
    std::ostringstream compact;
    ProductRenderer::render_full_screen(compact, model, capabilities);
    if (compact.str().find("Launch Deck |") == std::string::npos ||
        compact.str().find("Focus: Search: test") == std::string::npos) return 23;

    capabilities.observed.columns = 30U;
    capabilities.observed.rows = 10U;
    std::ostringstream small;
    ProductRenderer::render_full_screen(small, model, capabilities);
    if (small.str().find("\x1b[") != std::string::npos ||
        small.str().find("Launch Deck") == std::string::npos) return 18;

    const std::string combined = "e\xCC\x81";
    const std::string wide = "A\xE7\x95\x8C";
    const std::string joined = "\xF0\x9F\x91\xA9\xE2\x80\x8D\xF0\x9F\x92\xBB";
    const std::string keycap = "1\xEF\xB8\x8F\xE2\x83\xA3";
    const std::string invalid("bad\xF0\x28\x8C\x28", 7U);
    if (terminal_display_width(combined) != 1U || terminal_display_width(wide) != 3U ||
        terminal_display_width(joined) != 2U || terminal_display_width(keycap) != 2U ||
        clip_terminal_text(wide, 2U) != "A" ||
        clip_terminal_text("abcdef", 5U) != "ab..." ||
        clip_terminal_text(invalid, 20U).find("\xEF\xBF\xBD") == std::string::npos ||
        clip_terminal_text(std::string("safe\x1b[2J"), 20U).find('\x1b') != std::string::npos) return 19;

    std::ostringstream lifecycle;
    ProductRenderer::enter_full_screen(lifecycle);
    ProductRenderer::leave_full_screen(lifecycle);
    if (lifecycle.str() != "\x1b[?1049h\x1b[?25l\x1b[?25h\x1b[?1049l") return 20;

    TuiEvent disconnected;
    disconnected.kind = TuiEventKind::transport_disconnected;
    disconnected.value = "transport lost";
    state = reduce_tui_state(state, disconnected);
    TuiEvent cancelled;
    cancelled.kind = TuiEventKind::cancel;
    state = reduce_tui_state(state, cancelled);
    if (state.transport_connected || !state.pending_action.empty() ||
        state.status.find("manufacturing") == std::string::npos) return 9;

    TuiAction launch_action;
    launch_action.label = "Start fake session";
    facman::client::CommandResponse unknown;
    unknown.status = 1;
    unknown.error_code = "cli_process_timeout";
    unknown.operation.outcome = facman::client::OperationOutcome::outcome_unknown;
    if (action_response_status(launch_action, unknown).find("Outcome unknown") == std::string::npos ||
        action_response_status(launch_action, unknown).find("cli_process_timeout") == std::string::npos) return 24;
    facman::client::CommandResponse recovery;
    recovery.status = 1;
    recovery.error_code = "journal_recovery_required";
    recovery.operation.outcome = facman::client::OperationOutcome::recovery_required;
    if (action_response_status(launch_action, recovery).find("Recovery required") == std::string::npos) return 25;
    facman::client::CommandResponse completed;
    completed.status = 0;
    completed.operation.outcome = facman::client::OperationOutcome::completed;
    if (action_response_status(launch_action, completed) != "Start fake session completed") return 26;

    TuiState long_state;
    long_state.page = TuiPage::instances;
    long_state.focus_region = TuiFocusRegion::items;
    long_state.selected_item = 9999U;
    long_state.snapshot.items.reserve(10000U);
    for (std::size_t index = 0U; index < 10000U; ++index) {
        TuiItem item;
        item.id = "instance-" + std::to_string(index);
        item.title = "Instance " + std::to_string(index);
        item.detail = "long-list performance fixture";
        long_state.snapshot.items.push_back(std::move(item));
    }
    const auto started = std::chrono::steady_clock::now();
    const TuiRenderModel long_model = make_tui_render_model(long_state, false);
    capabilities.observed.columns = 80U;
    capabilities.observed.rows = 24U;
    std::ostringstream long_output;
    ProductRenderer::render_full_screen(long_output, long_model, capabilities);
    const auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now() - started);
    if (elapsed > std::chrono::milliseconds(3000) ||
        long_output.str().size() > 16U * 1024U ||
        long_output.str().find("Instance 9999") == std::string::npos ||
        long_output.str().find("... earlier content ...") == std::string::npos) return 27;
    return 0;
}
