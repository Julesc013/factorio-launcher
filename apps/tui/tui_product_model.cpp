// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "tui_product_model.hpp"

#include "fl_json.h"

#include <algorithm>
#include <cctype>
#include <sstream>
#include <utility>

namespace facman::tui {
namespace json = facman::core::json;
namespace {

std::string string_member(const json::Value& object, const char* key)
{
    const json::Value* member = object.find(key);
    if (member == nullptr || !member->is_string()) return {};
    auto value = member->string_value();
    return value ? value.take_value() : std::string();
}

bool bool_member(const json::Value& object, const char* key)
{
    const json::Value* member = object.find(key);
    if (member == nullptr || !member->is_bool()) return false;
    auto value = member->bool_value();
    return value && value.value();
}

std::string first_array_string(const json::Value& object, const char* key)
{
    const json::Value* values = object.find(key);
    const json::Value* first = values != nullptr && values->is_array()
        ? values->at(0U) : nullptr;
    if (first == nullptr || !first->is_string()) return {};
    auto value = first->string_value();
    return value ? value.take_value() : std::string();
}

std::string first_string(const json::Value& object, const std::vector<const char*>& keys)
{
    for (const char* key : keys) {
        std::string value = string_member(object, key);
        if (!value.empty()) return value;
    }
    return {};
}

std::string lower(std::string value)
{
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return value;
}

bool visible(const FormFieldSpec& field, const TuiForm& form)
{
    if (field.visible_when_field.empty()) return true;
    const auto found = form.values.find(field.visible_when_field);
    return found != form.values.end() && found->second == field.visible_when_value;
}

bool all_digits(const std::string& value)
{
    return !value.empty() && std::all_of(value.begin(), value.end(), [](unsigned char ch) {
        return std::isdigit(ch) != 0;
    });
}

FormFieldType action_field_type(const std::string& value)
{
    if (value == "enum") return FormFieldType::enumeration;
    if (value == "integer") return FormFieldType::integer;
    if (value == "boolean") return FormFieldType::boolean;
    if (value == "path") return FormFieldType::path;
    return FormFieldType::string;
}

std::string readiness_text(const json::Value* readiness)
{
    if (readiness == nullptr || readiness->is_null()) return "Unavailable";
    if (!readiness->is_object()) return "Invalid readiness projection";
    const std::string value = first_string(
        *readiness, {"status", "state", "configuration_state", "outcome"});
    return value.empty() ? "Available" : value;
}

std::string last_run_text(const json::Value* last_run)
{
    if (last_run == nullptr || !last_run->is_object()) return "Unavailable";
    const std::string authority = string_member(*last_run, "authority_state");
    const json::Value* record = last_run->find("record");
    if (record != nullptr && record->is_object()) {
        const json::Value* terminal = record->find("terminal_result");
        if (terminal != nullptr && terminal->is_object()) {
            const std::string outcome = string_member(*terminal, "outcome");
            if (!outcome.empty()) return outcome;
        }
        const std::string outcome = first_string(
            *record, {"terminal_classification", "outcome", "status", "state"});
        if (!outcome.empty()) return outcome;
    }
    return authority.empty() ? "Unavailable" : authority;
}

std::string item_id(const json::Value& item)
{
    return first_string(item, {"instance_id", "installation_id", "save_id", "modset_id", "profile_id", "id"});
}

std::string item_title(const json::Value& item)
{
    return first_string(item, {"display_name", "name", "version", "instance_id", "installation_id", "id"});
}

std::string item_detail(const json::Value& item)
{
    std::vector<std::string> values;
    for (const char* key : {"factorio_version", "version", "profile", "ownership",
         "installation_layout", "distribution_origin", "strict_isolation_eligibility",
         "verification_status", "kind", "status", "value", "root"}) {
        const std::string value = string_member(item, key);
        if (!value.empty() && std::find(values.begin(), values.end(), value) == values.end()) {
            values.push_back(value);
        }
    }
    std::ostringstream output;
    for (std::size_t index = 0; index < values.size(); ++index) {
        if (index != 0) output << " | ";
        output << values[index];
    }
    return output.str();
}

std::size_t preferred_action_index(const std::vector<TuiAction>& actions)
{
    const auto available_role = [&actions](const char* role) {
        return std::find_if(actions.begin(), actions.end(), [role](const TuiAction& action) {
            return action.available && action.role == role;
        });
    };
    for (const char* role : {"primary", "manage", "recovery", "diagnostic"}) {
        const auto found = available_role(role);
        if (found != actions.end()) {
            return static_cast<std::size_t>(std::distance(actions.begin(), found));
        }
    }
    const auto available = std::find_if(actions.begin(), actions.end(), [](const TuiAction& action) {
        return action.available;
    });
    return available == actions.end()
        ? 0U : static_cast<std::size_t>(std::distance(actions.begin(), available));
}

} // namespace

const char* tui_page_name(TuiPage page) noexcept
{
    switch (page) {
    case TuiPage::home: return "Home";
    case TuiPage::instances: return "Instances";
    case TuiPage::installations: return "Installations";
    case TuiPage::content: return "Content";
    case TuiPage::saves: return "Saves";
    case TuiPage::activity: return "Activity";
    case TuiPage::settings: return "Settings";
    case TuiPage::advanced: return "Advanced";
    }
    return "Home";
}

std::size_t tui_page_index(TuiPage page) noexcept
{
    return static_cast<std::size_t>(page);
}

TuiPage tui_page_at(std::size_t index) noexcept
{
    return index < 8U ? static_cast<TuiPage>(index) : TuiPage::home;
}

const char* form_field_type_name(FormFieldType type) noexcept
{
    switch (type) {
    case FormFieldType::string: return "string";
    case FormFieldType::multiline: return "multiline";
    case FormFieldType::integer: return "integer";
    case FormFieldType::boolean: return "boolean";
    case FormFieldType::enumeration: return "enum";
    case FormFieldType::multi_select: return "multi-select";
    case FormFieldType::path: return "path";
    case FormFieldType::size: return "size";
    case FormFieldType::duration: return "duration";
    case FormFieldType::version: return "version";
    case FormFieldType::digest: return "digest";
    case FormFieldType::secret_reference: return "secret-reference";
    }
    return "string";
}

std::vector<std::string> validate_form(const TuiForm& form)
{
    std::vector<std::string> problems;
    for (const auto& field : form.fields) {
        if (!visible(field, form)) continue;
        const auto found = form.values.find(field.id);
        const std::string value = found == form.values.end() ? field.default_value : found->second;
        if (field.required && value.empty()) {
            problems.push_back(field.label + " is required");
            continue;
        }
        if (value.empty()) continue;
        if ((field.type == FormFieldType::integer || field.type == FormFieldType::size ||
             field.type == FormFieldType::duration) && !all_digits(value)) {
            problems.push_back(field.label + " must be a non-negative whole number");
        }
        if ((field.type == FormFieldType::enumeration || field.type == FormFieldType::multi_select) &&
            !field.choices.empty() &&
            std::find(field.choices.begin(), field.choices.end(), value) == field.choices.end()) {
            problems.push_back(field.label + " must use an available choice");
        }
        if (field.type == FormFieldType::boolean) {
            const std::string normalized = lower(value);
            if (normalized != "true" && normalized != "false" &&
                normalized != "yes" && normalized != "no") {
                problems.push_back(field.label + " must be true or false");
            }
        }
        if (field.type == FormFieldType::digest && value.size() != 64U) {
            problems.push_back(field.label + " must be a 64-character SHA-256 digest");
        }
    }
    if (!form.confirmation_digest.empty() && form.plan_preview.empty()) {
        problems.push_back("Digest confirmation requires a visible plan preview");
    }
    return problems;
}

TuiState reduce_tui_state(const TuiState& state, const TuiEvent& event)
{
    TuiState next = state;
    switch (event.kind) {
    case TuiEventKind::navigate:
        next.page = event.page;
        next.focus_region = TuiFocusRegion::navigation;
        next.selected_item = 0;
        next.selected_action = 0;
        next.pending_action.clear();
        next.refresh_requested = event.page != TuiPage::advanced;
        next.advanced_requested = event.page == TuiPage::advanced;
        next.status = std::string("Opened ") + tui_page_name(event.page);
        break;
    case TuiEventKind::select:
        next.focus_region = TuiFocusRegion::items;
        next.selected_item = next.snapshot.items.empty()
            ? 0U : std::min(event.index, next.snapshot.items.size() - 1U);
        if (!next.snapshot.items.empty()) {
            const auto& item = next.snapshot.items[next.selected_item];
            next.snapshot.selected_instance_id = item.id;
            next.snapshot.selected_instance_name = item.title;
        }
        next.refresh_requested = next.page == TuiPage::home || next.page == TuiPage::instances;
        break;
    case TuiEventKind::select_action:
        next.focus_region = TuiFocusRegion::actions;
        next.selected_action = next.snapshot.actions.empty()
            ? 0U : std::min(event.index, next.snapshot.actions.size() - 1U);
        next.pending_action.clear();
        if (!next.snapshot.actions.empty()) {
            const auto& action = next.snapshot.actions[next.selected_action];
            next.status = action.available
                ? "Selected action: " + action.label
                : "Selected unavailable action: " + action.label;
        }
        break;
    case TuiEventKind::search:
        next.focus_region = TuiFocusRegion::search;
        next.search = event.value;
        next.selected_item = 0;
        next.refresh_requested = true;
        next.status = event.value.empty() ? "Search cleared" : "Search filter applied";
        break;
    case TuiEventKind::activate_action:
        next.focus_region = TuiFocusRegion::actions;
        next.pending_action = event.name;
        next.status = event.name.empty() ? "No action available" : "Action selected: " + event.name;
        break;
    case TuiEventKind::edit_field:
        next.form.values[event.name] = event.value;
        next.form.problems = validate_form(next.form);
        break;
    case TuiEventKind::confirm_plan:
        next.form.problems = validate_form(next.form);
        next.status = next.form.problems.empty() ? "Plan confirmed" : "Plan has validation problems";
        break;
    case TuiEventKind::cancel:
        next.pending_action.clear();
        next.form = {};
        next.operation_status = "Cancellation requested";
        next.status = "Returned without manufacturing an operation outcome";
        break;
    case TuiEventKind::resize:
        next.columns = event.columns;
        next.rows = event.rows;
        break;
    case TuiEventKind::refresh:
        next.pending_action.clear();
        next.refresh_requested = true;
        next.status = "Refreshing authoritative state";
        break;
    case TuiEventKind::operation_event:
        next.operation_status = event.value;
        next.status = event.value.empty() ? "Operation state changed" : event.value;
        break;
    case TuiEventKind::transport_disconnected:
        next.transport_connected = false;
        next.refresh_requested = false;
        next.status = event.value.empty() ? "Backend unavailable" : event.value;
        break;
    case TuiEventKind::snapshot_received:
        {
        next.pending_action.clear();
        std::string selected_action_id;
        if (next.selected_action < next.snapshot.actions.size()) {
            selected_action_id = next.snapshot.actions[next.selected_action].id;
        }
        next.snapshot = event.snapshot;
        next.selected_action = preferred_action_index(next.snapshot.actions);
        if (!selected_action_id.empty()) {
            const auto selected = std::find_if(
                next.snapshot.actions.begin(), next.snapshot.actions.end(),
                [&selected_action_id](const TuiAction& action) {
                    return action.id == selected_action_id;
                });
            if (selected != next.snapshot.actions.end()) {
                next.selected_action = static_cast<std::size_t>(
                    std::distance(next.snapshot.actions.begin(), selected));
            }
        }
        next.transport_connected = true;
        next.refresh_requested = false;
        next.status = "Authoritative snapshot " + event.snapshot.revision.substr(
            0U, std::min<std::size_t>(12U, event.snapshot.revision.size()));
        if (next.selected_item >= next.snapshot.items.size()) next.selected_item = 0;
        break;
        }
    }
    return next;
}

TuiActionIdentity issue_action_identity(TuiState& state, const std::string& action_id)
{
    ++state.action_sequence;
    std::string bounded_action;
    bounded_action.reserve(std::min<std::size_t>(action_id.size(), 24U));
    for (const unsigned char value : action_id) {
        if (bounded_action.size() == 24U) break;
        bounded_action.push_back(std::isalnum(value) != 0 ? static_cast<char>(value) : '-');
    }
    const std::string revision = state.snapshot.revision.substr(
        0U, std::min<std::size_t>(12U, state.snapshot.revision.size()));
    TuiActionIdentity result;
    result.request_id = "tui-" + bounded_action + "-" + revision + "-" +
        std::to_string(state.action_sequence);
    result.idempotency_key = result.request_id;
    result.durable_operation_id = "operation-" + result.request_id;
    result.attempt_id = "attempt-" + result.request_id;
    return result;
}

TuiRenderModel make_tui_render_model(const TuiState& state, bool unicode)
{
    TuiRenderModel model;
    model.title = "FacMan - Factorio Manager";
    for (std::size_t index = 0; index < 8U; ++index) {
        model.navigation.push_back(
            std::to_string(index + 1U) + " " + tui_page_name(tui_page_at(index)));
    }
    model.active_navigation = tui_page_index(state.page);
    const std::string missing = unicode ? "\xE2\x80\x94" : "-";
    model.launch_deck = {
        "Instance: " + (state.snapshot.selected_instance_name.empty()
            ? (state.snapshot.selected_instance_id.empty() ? "Not selected" : state.snapshot.selected_instance_id)
            : state.snapshot.selected_instance_name),
        "Version: " + (state.snapshot.factorio_version.empty() ? missing : state.snapshot.factorio_version),
        "Profile/content/save: " + (state.snapshot.profile.empty() ? missing : state.snapshot.profile) + " / " + missing + " / " + missing,
        "Readiness: " + (state.snapshot.readiness.empty() ? "Unavailable" : state.snapshot.readiness),
        "Operation: " + (state.operation_status.empty()
            ? (state.snapshot.active_operation.empty() ? "None" : state.snapshot.active_operation)
            : state.operation_status),
        "Last Run: " + (state.snapshot.last_run.empty() ? "Unavailable" : state.snapshot.last_run),
    };
    model.page_title = tui_page_name(state.page);
    if (!state.snapshot.summary.empty()) model.body.push_back(state.snapshot.summary);
    if (!state.search.empty()) model.body.push_back("Filter: " + state.search);
    for (std::size_t index = 0; index < state.snapshot.items.size(); ++index) {
        const auto& item = state.snapshot.items[index];
        if (index == state.selected_item) {
            model.active_body_line = model.body.size();
            model.has_active_body_line = true;
        }
        std::string line = index == state.selected_item ? "> " : "  ";
        line += item.title.empty() ? item.id : item.title;
        if (!item.detail.empty()) line += " - " + item.detail;
        model.body.push_back(std::move(line));
    }
    if (state.page == TuiPage::content) {
        model.body.push_back("Content is projected by the backend from shared profile and modset authority.");
    } else if (state.page == TuiPage::saves) {
        model.body.push_back("Save inventory is read from the selected instance without frontend joins.");
    } else if (state.page == TuiPage::settings) {
        model.body.push_back("Preferences, support, and runtime identity come from one backend snapshot.");
        model.body.push_back("Workspace: " + (state.snapshot.workspace_path.empty()
            ? "not selected" : state.snapshot.workspace_path));
        model.body.push_back("Workspace status: " + (state.snapshot.workspace_status.empty()
            ? "uninitialized" : state.snapshot.workspace_status));
        model.body.push_back("Workspace identity: " + (state.snapshot.workspace_id.empty()
            ? "not allocated" : state.snapshot.workspace_id));
    } else if (state.page == TuiPage::advanced) {
        model.body.push_back("The generated command browser is available as the Advanced plane.");
        model.body.push_back("Press Enter to open it without leaving this binary.");
    }
    if (!state.form.id.empty()) {
        model.body.push_back("Action input: " + state.form.title);
        for (const auto& field : state.form.fields) {
            const auto found = state.form.values.find(field.id);
            const std::string value = found == state.form.values.end()
                ? field.default_value : found->second;
            model.body.push_back("  " + field.id + "=" + value +
                (field.required ? " (required)" : ""));
        }
        model.body.push_back("Enter field=value, then activate the action again.");
    }
    if (model.body.empty()) model.body.push_back("No records in this authoritative snapshot.");
    model.problems = state.snapshot.blockers;
    if (!state.transport_connected) model.problems.push_back("Backend connection unavailable; displayed state is not refreshed.");
    if (!state.form.problems.empty()) {
        model.problems.insert(model.problems.end(), state.form.problems.begin(), state.form.problems.end());
    }
    for (const auto& action : state.snapshot.actions) {
        model.actions.push_back(action.available
            ? action.label
            : action.label + " (unavailable: " + action.blocker + ")");
    }
    if (!state.snapshot.actions.empty()) {
        model.active_action = std::min(state.selected_action, state.snapshot.actions.size() - 1U);
        const auto& action = state.snapshot.actions[model.active_action];
        model.primary_action = action.available
            ? action.label
            : action.label + " (unavailable: " + action.blocker + ")";
        model.primary_action_available = action.available;
    }
    if (model.primary_action.empty()) model.primary_action = "No contextual primary action";
    model.focus_region = state.focus_region;
    switch (state.focus_region) {
    case TuiFocusRegion::navigation:
        model.focus = "Page: " + model.page_title;
        break;
    case TuiFocusRegion::items:
        model.focus = state.snapshot.items.empty()
            ? "Items: no item available"
            : "Item: " + (state.snapshot.items[state.selected_item].title.empty()
                ? state.snapshot.items[state.selected_item].id
                : state.snapshot.items[state.selected_item].title);
        break;
    case TuiFocusRegion::actions:
        model.focus = "Action: " + model.primary_action;
        break;
    case TuiFocusRegion::search:
        model.focus = state.search.empty() ? "Search: empty" : "Search: " + state.search;
        break;
    }
    model.status = state.status;
    model.footer = "F1 Help | Tab Actions | Space Run | 1..8 Pages | / Search | Ctrl+R Refresh | q Quit";
    return model;
}

TuiSnapshot parse_presentation_snapshot(const std::string& source)
{
    TuiSnapshot snapshot;
    auto document = json::parse(source, {8U * 1024U * 1024U, 64U, 250000U, 4U * 1024U * 1024U});
    if (!document || !document.value().is_object()) return snapshot;
    const json::Value& root = document.value();
    snapshot.revision = string_member(root, "revision");
    const json::Value* selected = root.find("selected_context");
    if (selected != nullptr && selected->is_object()) {
        snapshot.selected_instance_id = string_member(*selected, "instance_id");
    }
    const json::Value* page = root.find("page");
    if (page != nullptr && page->is_object()) {
        snapshot.scope = string_member(*page, "scope");
        snapshot.summary = string_member(*page, "summary");
        const json::Value* items = page->find("items");
        if (items != nullptr && items->is_array()) {
            for (std::size_t index = 0; index < items->size(); ++index) {
                const json::Value* value = items->at(index);
                if (value == nullptr || !value->is_object()) continue;
                TuiItem item;
                item.id = item_id(*value);
                item.title = item_title(*value);
                item.detail = item_detail(*value);
                item.selected = bool_member(*value, "selected");
                if (item.selected) {
                    snapshot.selected_instance_id = item.id;
                    snapshot.selected_instance_name = item.title;
                    snapshot.factorio_version = string_member(*value, "factorio_version");
                    snapshot.profile = string_member(*value, "profile");
                }
                snapshot.items.push_back(std::move(item));
            }
        }
    }
    snapshot.readiness = readiness_text(root.find("readiness"));
    snapshot.last_run = last_run_text(root.find("last_run"));
    const json::Value* workspace = root.find("workspace_health");
    if (workspace != nullptr && workspace->is_object()) {
        snapshot.workspace_status = string_member(*workspace, "status");
        snapshot.workspace_path = string_member(*workspace, "workspace");
        snapshot.workspace_id = string_member(*workspace, "workspace_id");
        snapshot.workspace_initialized = bool_member(*workspace, "initialized");
    }
    const json::Value* blockers = root.find("specific_blockers");
    if (blockers != nullptr && blockers->is_array()) {
        for (std::size_t index = 0; index < blockers->size(); ++index) {
            const json::Value* problem = blockers->at(index);
            if (problem == nullptr || !problem->is_object()) continue;
            std::string message = first_string(*problem, {"summary", "message", "detail", "code"});
            if (!message.empty()) snapshot.blockers.push_back(std::move(message));
        }
    }
    const json::Value* actions = root.find("available_semantic_actions");
    if (actions != nullptr && actions->is_array()) {
        for (std::size_t index = 0; index < actions->size(); ++index) {
            const json::Value* value = actions->at(index);
            if (value == nullptr || !value->is_object()) continue;
            TuiAction action;
            action.id = first_string(*value, {"action_id", "id"});
            action.label = first_string(*value, {"label", "title", "action_id"});
            action.role = string_member(*value, "role");
            action.effect = first_array_string(*value, "effects");
            action.confirmation = string_member(*value, "confirmation");
            action.available = bool_member(*value, "available") ||
                string_member(*value, "availability") == "available";
            action.blocker = first_string(*value, {"unavailable_reason", "blocker", "reason"});
            const json::Value* refusal = value->find("refusal");
            if (action.blocker.empty() && refusal != nullptr && refusal->is_object()) {
                action.blocker = first_string(*refusal, {"code", "reason"});
            }
            const json::Value* input_fields = value->find("input_fields");
            if (input_fields != nullptr && input_fields->is_array()) {
                for (std::size_t field_index = 0U;
                     field_index < input_fields->size(); ++field_index) {
                    const json::Value* input = input_fields->at(field_index);
                    if (input == nullptr || !input->is_object()) continue;
                    FormFieldSpec field;
                    field.id = string_member(*input, "field_id");
                    field.label = string_member(*input, "label");
                    field.type = action_field_type(string_member(*input, "type"));
                    field.required = bool_member(*input, "required");
                    field.default_value = string_member(*input, "default");
                    const json::Value* choices = input->find("choices");
                    if (choices != nullptr && choices->is_array()) {
                        for (std::size_t choice_index = 0U;
                             choice_index < choices->size(); ++choice_index) {
                            const json::Value* choice = choices->at(choice_index);
                            if (choice == nullptr || !choice->is_string()) continue;
                            auto decoded = choice->string_value();
                            if (decoded) field.choices.push_back(decoded.take_value());
                        }
                    }
                    if (!field.id.empty() && !field.label.empty()) {
                        action.input_fields.push_back(std::move(field));
                    }
                }
            }
            snapshot.actions.push_back(std::move(action));
        }
    }
    const json::Value* operations = root.find("active_operations");
    if (operations != nullptr && operations->is_array() && operations->size() != 0U) {
        const json::Value* operation = operations->at(0U);
        if (operation != nullptr && operation->is_object()) {
            snapshot.active_operation = first_string(*operation, {"status", "state", "operation_id"});
        }
    }
    return snapshot;
}

} // namespace facman::tui
