// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "tui_guided_forms.hpp"

#include "fl_json.h"
#include "generated_command_catalog.hpp"
#include "tui_views.hpp"

#include <algorithm>
#include <cctype>
#include <iostream>
#include <map>
#include <set>
#include <sstream>
#include <vector>

namespace facman::tui {
namespace json = facman::core::json;
namespace {

struct Field {
    std::string name;
    std::string type;
    std::string request_field;
    bool required = false;
    bool repeatable = false;
    std::vector<std::string> choices;
};

std::string lower(std::string value)
{
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char item) {
        return static_cast<char>(std::tolower(item));
    });
    return value;
}

std::string string_member(const json::Value& object, const char* key)
{
    const json::Value* member = object.find(key);
    if (member == nullptr || !member->is_string()) return {};
    auto value = member->string_value();
    return value ? value.value() : std::string();
}

bool bool_member(const json::Value& object, const char* key)
{
    const json::Value* member = object.find(key);
    if (member == nullptr || !member->is_bool()) return false;
    auto value = member->bool_value();
    return value && value.value();
}

std::vector<Field> fields_for(const GeneratedCommand& command)
{
    std::vector<Field> fields;
    auto document = json::parse(command.request_fields_json);
    if (!document || !document.value().is_array()) return fields;
    for (std::size_t index = 0; index < document.value().size(); ++index) {
        const json::Value* item = document.value().at(index);
        if (item == nullptr || !item->is_object()) continue;
        Field field;
        field.name = string_member(*item, "name");
        field.type = string_member(*item, "type");
        field.request_field = string_member(*item, "request_field");
        field.required = bool_member(*item, "required");
        field.repeatable = bool_member(*item, "repeatable");
        const json::Value* choices = item->find("choices");
        if (choices != nullptr && choices->is_array()) {
            for (std::size_t choice = 0; choice < choices->size(); ++choice) {
                const json::Value* value = choices->at(choice);
                if (value == nullptr || !value->is_string()) continue;
                auto text = value->string_value();
                if (text) field.choices.push_back(text.take_value());
            }
        }
        if (!field.name.empty() && !field.request_field.empty()) fields.push_back(std::move(field));
    }
    return fields;
}

bool cancelled(const std::string& value)
{
    return value == ":cancel" || value == ":q";
}

std::string prompt_value(std::istream& input, std::ostream& output, const Field& field, bool& was_cancelled)
{
    for (;;) {
        output << field.name << " (" << (field.required ? "required" : "optional") << ", " << field.type;
        if (field.repeatable) output << ", repeatable";
        output << ")";
        if (!field.choices.empty()) {
            output << " [";
            for (std::size_t index = 0; index < field.choices.size(); ++index) {
                if (index != 0) output << '/';
                output << (index + 1) << ':' << field.choices[index];
            }
            output << ']';
        }
        output << ": " << std::flush;
        std::string value;
        if (!std::getline(input, value)) { was_cancelled = true; return {}; }
        if (cancelled(value)) { was_cancelled = true; return {}; }
        if (!field.choices.empty() && !value.empty()) {
            try {
                const std::size_t selection = static_cast<std::size_t>(std::stoul(value));
                if (selection > 0 && selection <= field.choices.size()) value = field.choices[selection - 1];
            } catch (...) {}
            if (std::find(field.choices.begin(), field.choices.end(), value) == field.choices.end()) {
                output << "Choose one of the listed values.\n";
                continue;
            }
        }
        if (field.required && value.empty()) {
            output << "A value is required; use :cancel to return.\n";
            continue;
        }
        return value;
    }
}

bool sensitive_name(const std::string& name)
{
    const std::string value = lower(name);
    return value.find("password") != std::string::npos || value.find("token") != std::string::npos ||
        value.find("secret") != std::string::npos;
}

bool build_payload(
    std::istream& input,
    std::ostream& output,
    const GeneratedCommand& command,
    std::string& payload)
{
    json::ObjectBuilder object;
    output << "\nFields are generated from the shared command grammar. Use :cancel at any prompt.\n";
    for (const Field& field : fields_for(command)) {
        if (field.repeatable) {
            json::ArrayBuilder values;
            std::size_t count = 0;
            for (;;) {
                bool was_cancelled = false;
                Field item = field;
                item.required = field.required && count == 0;
                std::string value = prompt_value(input, output, item, was_cancelled);
                if (was_cancelled) return false;
                if (value.empty()) break;
                values.add_string(value);
                ++count;
                output << "  Added " << field.name << " item " << count << ". Blank finishes the list.\n";
            }
            if (count > 0) object.add_array(field.request_field, values);
            continue;
        }
        bool was_cancelled = false;
        std::string value = prompt_value(input, output, field, was_cancelled);
        if (was_cancelled) return false;
        if (value.empty()) continue;
        if (field.type == "boolean") object.add_bool(field.request_field, value == "true" || value == "yes" || value == "1");
        else object.add_string(field.request_field, value);
    }
    payload = object.serialize();
    auto parsed = json::parse(payload);
    output << "\nReview\n------\nCommand: " << command.command_id
           << "\nAvailability: " << command.availability
           << "\nRisk: " << command.risk_tier
           << "\nEffects: " << command.effects_json << "\nPayload fields:\n";
    if (parsed && parsed.value().is_object()) {
        const auto fields = parsed.value().object_keys();
        if (fields.empty()) output << "  (none)\n";
        for (const std::string& key : fields) {
            const json::Value* value = parsed.value().find(key);
            output << "  " << key << " = " << (sensitive_name(key) ? "[redacted]" : value->serialize()) << '\n';
        }
    }
    return true;
}

void write_paged(std::istream& input, std::ostream& output, const std::string& text, const GuidedOptions& options)
{
    std::istringstream lines(text);
    std::string line;
    std::size_t count = 0;
    while (std::getline(lines, line)) {
        output << line << '\n';
        ++count;
        if (!options.page_results || options.page_size == 0 || count % options.page_size != 0 || lines.peek() == EOF) continue;
        output << "-- more (Enter continues, q stops paging) --" << std::flush;
        std::string action;
        if (!std::getline(input, action) || lower(action) == "q") { output << '\n'; break; }
    }
}

std::vector<const GeneratedCommand*> matching(const std::string& category, const std::string& query)
{
    std::vector<const GeneratedCommand*> result;
    const std::string needle = lower(query);
    for (const auto& command : kGeneratedCommands) {
        if (!category.empty() && category != command.category) continue;
        const std::string haystack = lower(std::string(command.command_id) + " " + command.runtime_id + " " + command.category);
        if (!needle.empty() && haystack.find(needle) == std::string::npos) continue;
        result.push_back(&command);
    }
    return result;
}

class TerminalProgress final : public facman::client::ProgressSink {
public:
    explicit TerminalProgress(std::ostream& output) : output_(output) {}
    void report(const facman::client::ProgressUpdate& update) noexcept override
    {
        output_ << "[progress] " << update.stage << " " << update.completed << '/' << update.total << '\n';
    }
private:
    std::ostream& output_;
};

}  // namespace

int run_guided(
    CommandClient& client,
    std::istream& input,
    std::ostream& output,
    std::ostream& error,
    const GuidedOptions& options)
{
    std::set<std::string> category_set;
    for (const auto& command : kGeneratedCommands) category_set.insert(command.category);
    const std::vector<std::string> categories(category_set.begin(), category_set.end());
    output << (options.color ? "\x1b[1;36m" : "") << "FacMan guided terminal"
           << (options.color ? "\x1b[0m" : "") << "\n";
    output << "Keyboard: number selects; /text searches; b goes back; q quits; :cancel cancels a form.\n";
    for (;;) {
        output << "\nCategories\n----------\n";
        for (std::size_t index = 0; index < categories.size(); ++index)
            output << "  " << (index + 1) << ". " << categories[index] << '\n';
        output << "Category number, /search, or q: " << std::flush;
        std::string selection;
        if (!std::getline(input, selection) || lower(selection) == "q") return 0;
        std::string category;
        std::string query;
        if (!selection.empty() && selection.front() == '/') query = selection.substr(1);
        else {
            try {
                const std::size_t number = static_cast<std::size_t>(std::stoul(selection));
                if (number == 0 || number > categories.size()) continue;
                category = categories[number - 1];
            } catch (...) { continue; }
        }
        if (category == "installs") {
            output << "\n" << kGeneratedSetupWorkflowText << "\n";
        }
        for (;;) {
            const auto commands = matching(category, query);
            output << "\nCommands" << (category.empty() ? " matching search" : " in " + category) << "\n--------\n";
            if (commands.empty()) output << "  No generated commands match.\n";
            for (std::size_t index = 0; index < commands.size(); ++index) {
                const auto& command = *commands[index];
                output << "  " << (index + 1) << ". " << command.command_id
                       << " [" << command.risk_tier << ", " << command.availability << "]\n";
            }
            output << "Command number, /new search, b, or q: " << std::flush;
            if (!std::getline(input, selection) || lower(selection) == "q") return 0;
            if (lower(selection) == "b") break;
            if (!selection.empty() && selection.front() == '/') { category.clear(); query = selection.substr(1); continue; }
            std::size_t number = 0;
            try { number = static_cast<std::size_t>(std::stoul(selection)); } catch (...) { continue; }
            if (number == 0 || number > commands.size()) continue;
            const GeneratedCommand& command = *commands[number - 1];
            if (std::string(command.availability) != "available") {
                output << "Refused [" << (*command.availability_reason ? command.availability_reason : command.availability)
                       << "]: command is " << command.availability << ".\n";
                continue;
            }
            std::string payload;
            if (!build_payload(input, output, command, payload)) { output << "Form cancelled.\n"; continue; }
            output << (command_writes(command) ? "Type APPLY to confirm this local write: " : "Run this read-only/preview command? [Y/n]: ") << std::flush;
            std::string confirmation;
            if (!std::getline(input, confirmation)) return 0;
            if ((command_writes(command) && confirmation != "APPLY") ||
                (!command_writes(command) && (lower(confirmation) == "n" || lower(confirmation) == "no"))) {
                output << "Command cancelled before dispatch.\n";
                continue;
            }
            auto progress = std::make_shared<TerminalProgress>(output);
            Invocation invocation;
            invocation.command = command.runtime_id;
            invocation.payload = payload;
            invocation.allow_write = command_writes(command);
            invocation.progress = progress;
            auto response = client.execute(invocation);
            std::ostringstream rendered;
            const int status = render_response(rendered, error, command.command_id, response, false);
            write_paged(input, output, rendered.str(), options);
            output << (status == 0 ? "Completed.\n" : "Completed with structured refusal or error.\n");
        }
    }
}

}  // namespace facman::tui
