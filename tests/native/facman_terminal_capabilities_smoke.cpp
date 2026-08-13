// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "terminal_capabilities.hpp"

#include <string>

int main()
{
    using facman::tui::TerminalObservation;
    using facman::tui::TerminalRendererMode;
    using facman::tui::select_terminal_capabilities;

    auto redirected = select_terminal_capabilities({});
    if (redirected.selected_renderer != TerminalRendererMode::linear ||
        redirected.selection_reason != "redirected_stream" ||
        redirected.interactive_input || redirected.color) return 2;

    TerminalObservation rich;
    rich.input_tty = true;
    rich.output_tty = true;
    rich.error_tty = true;
    rich.columns = 120;
    rich.rows = 40;
    rich.utf8 = true;
    rich.vt_input = true;
    rich.vt_output = true;
    rich.conpty = true;
    rich.full_screen_adapter_available = true;
    auto full = select_terminal_capabilities(rich);
    if (full.selected_renderer != TerminalRendererMode::full_screen ||
        full.selection_reason != "full_screen_capabilities_available" ||
        !full.cursor_addressing || !full.color || !full.unicode) return 3;

    rich.no_color = true;
    auto no_color = select_terminal_capabilities(rich);
    if (no_color.selected_renderer != TerminalRendererMode::linear ||
        no_color.selection_reason != "no_color_requested" || no_color.color) return 4;

    rich.no_color = false;
    rich.term_dumb = true;
    auto dumb = select_terminal_capabilities(rich);
    if (dumb.selection_reason != "term_dumb" || dumb.cursor_addressing) return 5;

    rich.term_dumb = false;
    rich.force_plain = true;
    auto plain = select_terminal_capabilities(rich);
    if (plain.selection_reason != "plain_mode_requested" || plain.color) return 6;

    const std::string document = plain.json();
    if (document.find("facman.terminal_capabilities.v1") == std::string::npos ||
        document.find("\"columns\":120") == std::string::npos ||
        document.find("\"conpty\":true") == std::string::npos ||
        document.find("\"selected_renderer\":\"linear\"") == std::string::npos) return 7;
    return 0;
}
