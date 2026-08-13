// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "tui_product_renderer.hpp"

#include <algorithm>
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
    output << "  Primary action: " << model.primary_action << "\n\n"
           << model.page_title << "\n";
    for (const auto& value : model.body) output << "  " << value << '\n';
    if (!model.problems.empty()) {
        output << "\nAttention\n";
        for (const auto& value : model.problems) output << "  - " << value << '\n';
    }
    output << "\nStatus: " << model.status << "\n"
           << model.footer << "\n"
           << "Command (1-8, j/k, enter, /text, r, help, q): " << std::flush;
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
    lines.push_back("Launch Deck");
    for (const auto& value : model.launch_deck) lines.push_back("  " + value);
    lines.push_back("  Primary action: " + model.primary_action);
    lines.push_back("");
    lines.push_back(model.page_title);
    for (const auto& value : model.body) lines.push_back("  " + value);
    if (!model.problems.empty()) {
        lines.push_back("");
        lines.push_back("Attention");
        for (const auto& value : model.problems) lines.push_back("  ! " + value);
    }
    const std::size_t reserved = 3U;
    if (lines.size() > height - reserved) {
        lines.resize(height - reserved);
        if (!lines.empty()) lines.back() = "  ... more content; refine search or use linear mode";
    }
    output << "\x1b[H";
    for (const auto& value : lines) line(output, value, width);
    for (std::size_t index = lines.size(); index < height - reserved; ++index) line(output, "", width);
    line(output, "Status: " + model.status, width);
    line(output, model.footer, width);
    output << "\x1b[K" << std::flush;
}

} // namespace facman::tui
