// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#pragma once

#include <cstddef>
#include <string>

namespace facman::tui {

inline constexpr std::size_t kMinimumFullScreenColumns = 40U;
inline constexpr std::size_t kMinimumFullScreenRows = 12U;

enum class TerminalRendererMode { linear, full_screen };

struct TerminalObservation {
    bool input_tty = false;
    bool output_tty = false;
    bool error_tty = false;
    std::size_t columns = 0;
    std::size_t rows = 0;
    bool term_dumb = false;
    bool no_color = false;
    bool utf8 = false;
    bool vt_input = false;
    bool vt_output = false;
    bool conpty = false;
    bool force_plain = false;
    bool safe_mode = false;
    bool full_screen_adapter_available = false;
};

struct TerminalCapabilities {
    TerminalObservation observed;
    bool interactive_input = false;
    bool cursor_addressing = false;
    bool color = false;
    bool unicode = false;
    TerminalRendererMode selected_renderer = TerminalRendererMode::linear;
    std::string selection_reason;

    std::string json() const;
};

TerminalCapabilities select_terminal_capabilities(TerminalObservation observation);
TerminalCapabilities observe_terminal_capabilities(bool force_plain = false);
const char* renderer_mode_name(TerminalRendererMode mode) noexcept;

} // namespace facman::tui
