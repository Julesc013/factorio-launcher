// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "tui_product_renderer.hpp"

#include <algorithm>
#include <cstddef>
#include <ostream>
#include <string>
#include <vector>

namespace facman::tui {
namespace {

std::string clipped(const std::string& text, std::size_t width)
{
    return clip_terminal_text(text, width);
}

void line(std::ostream& output, const std::string& text, std::size_t width)
{
    output << clipped(text, width) << "\x1b[K\n";
}

} // namespace

void ProductRenderer::render_linear(std::ostream& output, const TuiRenderModel& model)
{
    output << "\n" << model.title << "\nPages:";
    for (std::size_t index = 0; index < model.navigation.size(); ++index) {
        output << (index == model.active_navigation ? " [" : " ")
               << model.navigation[index]
               << (index == model.active_navigation ? "]" : "");
    }
    output << "\n\nLaunch Deck\n";
    for (const auto& value : model.launch_deck) output << "  " << value << '\n';
    output << "\n" << model.page_title << "\n";
    for (const auto& value : model.body) output << "  " << value << '\n';
    if (!model.actions.empty()) {
        output << "\nActions\n";
        for (std::size_t index = 0; index < model.actions.size(); ++index) {
            output << (index == model.active_action ? "  > " : "    ")
                   << model.actions[index] << '\n';
        }
    }
    if (!model.problems.empty()) {
        output << "\nAttention\n";
        for (const auto& value : model.problems) output << "  - " << value << '\n';
    }
    output << "\nFocus: " << model.focus << "\n"
           << "Status: " << model.status << "\n"
           << model.footer << "\n"
           << "Command (1-8, j/k, tab, enter, space, /text, r, help, q): " << std::flush;
}

void ProductRenderer::enter_full_screen(std::ostream& output)
{
    output << "\x1b[?1049h\x1b[?25l" << std::flush;
}

void ProductRenderer::leave_full_screen(std::ostream& output)
{
    output << "\x1b[?25h\x1b[?1049l" << std::flush;
}

void ProductRenderer::render_full_screen(
    std::ostream& output,
    const TuiRenderModel& model,
    const TerminalCapabilities& capabilities)
{
    const std::size_t width = capabilities.observed.columns;
    const std::size_t height = capabilities.observed.rows;
    if (width < kMinimumFullScreenColumns || height < kMinimumFullScreenRows) {
        render_linear(output, model);
        return;
    }
    std::vector<std::string> lines;
    lines.push_back(model.title);
    std::string navigation;
    for (std::size_t index = 0; index < model.navigation.size(); ++index) {
        if (!navigation.empty()) navigation += "  ";
        navigation += index == model.active_navigation
            ? "[" + model.navigation[index] + "]"
            : model.navigation[index];
    }
    lines.push_back(navigation);
    lines.push_back(std::string(std::min<std::size_t>(width, 80U), '-'));
    if (height < 20U) {
        std::string compact = "Launch Deck";
        for (const std::size_t index : {0U, 3U, 5U}) {
            if (index < model.launch_deck.size()) compact += " | " + model.launch_deck[index];
        }
        lines.push_back(std::move(compact));
    } else {
        lines.push_back("Launch Deck");
        for (const auto& value : model.launch_deck) lines.push_back("  " + value);
    }
    lines.push_back(model.page_title);

    std::vector<std::string> content;
    std::size_t focus_line = 0U;
    bool has_focus_line = false;
    for (std::size_t index = 0; index < model.body.size(); ++index) {
        if (model.focus_region == TuiFocusRegion::items &&
            model.has_active_body_line && index == model.active_body_line) {
            focus_line = content.size();
            has_focus_line = true;
        }
        content.push_back("  " + model.body[index]);
    }
    if (!model.actions.empty()) {
        content.push_back("");
        content.push_back("Actions");
        for (std::size_t index = 0; index < model.actions.size(); ++index) {
            if (model.focus_region == TuiFocusRegion::actions && index == model.active_action) {
                focus_line = content.size();
                has_focus_line = true;
            }
            content.push_back(index == model.active_action
                ? "  > " + model.actions[index]
                : "    " + model.actions[index]);
        }
    }
    if (!model.problems.empty()) {
        content.push_back("");
        content.push_back("Attention");
        for (const auto& value : model.problems) content.push_back("  ! " + value);
    }

    const std::size_t reserved = 3U;
    const std::size_t content_rows = height - reserved > lines.size()
        ? height - reserved - lines.size() : 0U;
    if (content.size() <= content_rows) {
        lines.insert(lines.end(), content.begin(), content.end());
    } else if (content_rows != 0U) {
        std::size_t start = 0U;
        if (has_focus_line && focus_line >= content_rows / 2U) {
            start = focus_line - content_rows / 2U;
        }
        if (start + content_rows > content.size()) start = content.size() - content_rows;
        for (std::size_t index = 0; index < content_rows; ++index) {
            lines.push_back(content[start + index]);
        }
        if (start != 0U) lines[lines.size() - content_rows] = "  ... earlier content ...";
        if (start + content_rows < content.size()) lines.back() = "  ... later content ...";
    }
    output << "\x1b[H";
    for (const auto& value : lines) line(output, value, width);
    for (std::size_t index = lines.size(); index < height - reserved; ++index) line(output, "", width);
    line(output, "Status: " + model.status, width);
    line(output, "Focus: " + model.focus, width);
    line(output, model.footer, width);
    output << std::flush;
}

} // namespace facman::tui
