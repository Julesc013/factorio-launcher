// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "tui_views.hpp"

#include "fl_json.h"
#include "generated_command_catalog.hpp"

#include <iostream>

namespace facman::tui {
namespace json = facman::core::json;
namespace {

void emit_transport_error(std::ostream& output, const facman::core::Error& failure, bool structured)
{
    if (!structured) {
        output << "TUI transport error [" << failure.code << "]: " << failure.message << '\n';
        return;
    }
    json::ObjectBuilder refusal;
    refusal.add_string("schema", "facman.tui_refusal.v1");
    refusal.add_string("outcome", facman::core::outcome_kind_name(failure.kind));
    refusal.add_string("code", failure.code);
    refusal.add_string("message", failure.message);
    output << refusal.serialize() << '\n';
}

}  // namespace

void render_catalog(std::ostream& output, bool structured)
{
    if (structured) {
        json::ArrayBuilder commands;
        for (const auto& command : kGeneratedCommands) {
            json::ObjectBuilder item;
            item.add_string("command_id", command.command_id);
            item.add_string("runtime_id", command.runtime_id);
            item.add_string("category", command.category);
            item.add_string("availability", command.availability);
            item.add_string("availability_reason", command.availability_reason);
            item.add_string("risk_tier", command.risk_tier);
            commands.add_object(item);
        }
        json::ObjectBuilder report;
        report.add_string("schema", "facman.tui_catalog.v1");
        report.add_array("commands", commands);
        output << report.serialize() << '\n';
        return;
    }
    output << "FacMan command catalog (" << kGeneratedCommandCount << " commands)\n";
    for (const auto& command : kGeneratedCommands) {
        output << "  " << command.command_id << " -> " << command.runtime_id
               << " [" << command.availability << ", " << command.risk_tier << "]";
        if (*command.availability_reason != '\0') output << " " << command.availability_reason;
        output << '\n';
    }
}

int render_response(
    std::ostream& output,
    std::ostream& error,
    const std::string& command,
    const facman::core::Result<facman::client::CommandResponse>& response,
    bool structured)
{
    if (!response) {
        emit_transport_error(structured ? output : error, response.error(), structured);
        return 1;
    }
    const auto& value = response.value();
    const std::string& body = value.payload.empty() ? value.envelope : value.payload;
    if (body.size() > kMaximumDisplayBytes) {
        error << "TUI output refused: response exceeds the 1 MiB display budget\n";
        return 1;
    }
    if (structured) {
        output << body << '\n';
    } else {
        output << command << "\nOutcome: " << value.outcome << '\n';
        if (!value.error_code.empty()) output << "Reason: [" << value.error_code << "] " << value.error_message << '\n';
        if (!body.empty()) output << "\n" << body << '\n';
    }
    return value.ok() ? 0 : 1;
}

}  // namespace facman::tui
