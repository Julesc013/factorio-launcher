// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#pragma once

#include <cstddef>
#include <map>
#include <string>
#include <vector>

namespace facman::tui {

enum class TuiPage {
    home,
    instances,
    installations,
    content,
    saves,
    activity,
    settings,
    advanced,
};

enum class TuiEventKind {
    navigate,
    select,
    select_action,
    search,
    activate_action,
    edit_field,
    confirm_plan,
    cancel,
    resize,
    refresh,
    operation_event,
    transport_disconnected,
    snapshot_received,
};

enum class TuiFocusRegion {
    navigation,
    items,
    actions,
    search,
};

enum class FormFieldType {
    string,
    multiline,
    integer,
    boolean,
    enumeration,
    multi_select,
    path,
    size,
    duration,
    version,
    digest,
    secret_reference,
};

struct FormFieldSpec {
    std::string id;
    std::string label;
    FormFieldType type = FormFieldType::string;
    bool required = false;
    bool secret = false;
    std::string default_value;
    std::vector<std::string> choices;
    std::string visible_when_field;
    std::string visible_when_value;
};

struct TuiForm {
    std::string id;
    std::string title;
    std::vector<FormFieldSpec> fields;
    std::map<std::string, std::string> values;
    std::vector<std::string> problems;
    std::string plan_preview;
    std::string confirmation_digest;
};

struct TuiItem {
    std::string id;
    std::string title;
    std::string detail;
    bool selected = false;
};

struct TuiAction {
    std::string id;
    std::string label;
    std::string role;
    std::string effect;
    std::string confirmation;
    bool available = false;
    std::string blocker;
    std::vector<FormFieldSpec> input_fields;
};

struct TuiSnapshot {
    std::string revision;
    std::string scope;
    std::string summary;
    std::string selected_instance_id;
    std::string selected_instance_name;
    std::string factorio_version;
    std::string profile;
    std::string readiness;
    std::string last_run;
    std::string active_operation;
    std::string workspace_status;
    std::string workspace_path;
    std::string workspace_id;
    bool workspace_initialized = false;
    std::vector<std::string> blockers;
    std::vector<TuiAction> actions;
    std::vector<TuiItem> items;
};

struct TuiEvent {
    TuiEventKind kind = TuiEventKind::refresh;
    TuiPage page = TuiPage::home;
    std::size_t index = 0;
    std::size_t columns = 0;
    std::size_t rows = 0;
    std::string name;
    std::string value;
    TuiSnapshot snapshot;
};

struct TuiState {
    TuiPage page = TuiPage::home;
    TuiFocusRegion focus_region = TuiFocusRegion::navigation;
    std::size_t selected_item = 0;
    std::size_t selected_action = 0;
    std::size_t columns = 80;
    std::size_t rows = 24;
    std::string search;
    std::string status = "Connecting to FacMan";
    std::string pending_action;
    std::string operation_status;
    bool help_visible = false;
    bool command_palette_visible = false;
    bool refresh_requested = true;
    bool transport_connected = true;
    bool quit_requested = false;
    bool advanced_requested = false;
    std::size_t action_sequence = 0U;
    TuiSnapshot snapshot;
    TuiForm form;
};

struct TuiActionIdentity {
    std::string request_id;
    std::string idempotency_key;
    std::string durable_operation_id;
    std::string attempt_id;
};

struct TuiRenderModel {
    std::string title;
    std::vector<std::string> navigation;
    std::size_t active_navigation = 0;
    std::vector<std::string> launch_deck;
    std::string page_title;
    std::vector<std::string> body;
    std::size_t active_body_line = 0;
    bool has_active_body_line = false;
    std::vector<std::string> problems;
    std::vector<std::string> actions;
    std::size_t active_action = 0;
    TuiFocusRegion focus_region = TuiFocusRegion::navigation;
    std::string focus;
    std::string primary_action;
    bool primary_action_available = false;
    std::string status;
    std::string footer;
};

const char* tui_page_name(TuiPage page) noexcept;
std::size_t tui_page_index(TuiPage page) noexcept;
TuiPage tui_page_at(std::size_t index) noexcept;
const char* form_field_type_name(FormFieldType type) noexcept;
std::vector<std::string> validate_form(const TuiForm& form);
TuiState reduce_tui_state(const TuiState& state, const TuiEvent& event);
TuiRenderModel make_tui_render_model(const TuiState& state, bool unicode);
TuiSnapshot parse_presentation_snapshot(const std::string& source);
TuiActionIdentity issue_action_identity(TuiState& state, const std::string& action_id);

} // namespace facman::tui
