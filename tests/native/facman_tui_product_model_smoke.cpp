// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "tui_product_model.hpp"
#include "tui_product_renderer.hpp"

#include <sstream>
#include <string>

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
      "specific_blockers":[{"code":"route_unqualified","message":"Real Play remains gated"}],
      "available_semantic_actions":[
        {"action_id":"presentation.refresh","label":"Refresh","availability":"available","refusal":null},
        {"action_id":"launch.play","label":"Play","availability":"refused","refusal":{"code":"execution_authority_unavailable","reason":"not admitted"}}
      ],
      "active_operations":[],
      "last_run":{"authority_state":"outcome_unknown","record":null}
    })";
    TuiSnapshot snapshot = parse_presentation_snapshot(source);
    if (snapshot.revision.size() != 64U || snapshot.items.size() != 2U ||
        snapshot.selected_instance_id != "main" || snapshot.readiness != "ready" ||
        snapshot.last_run != "outcome_unknown" || snapshot.blockers.size() != 1U ||
        snapshot.actions.size() != 2U) return 2;

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
    if (state.refresh_requested || !state.transport_connected) return 3;

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
        model.launch_deck.size() != 6U || model.primary_action.find("unavailable") == std::string::npos) return 6;
    std::ostringstream linear;
    ProductRenderer::render_linear(linear, model);
    if (linear.str().find("Launch Deck") == std::string::npos ||
        linear.str().find("\x1b[") != std::string::npos) return 7;

    TerminalCapabilities capabilities;
    capabilities.observed.columns = 80U;
    capabilities.observed.rows = 24U;
    std::ostringstream full;
    ProductRenderer::render_full_screen(full, model, capabilities);
    if (full.str().find("\x1b[H") == std::string::npos || full.str().find("Instances") == std::string::npos) return 8;

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
    return 0;
}
