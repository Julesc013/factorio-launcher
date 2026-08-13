// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "linear_renderer.hpp"

#include <ostream>

namespace facman::tui {

void LinearAccessibleRenderer::render_landing(
    std::ostream& output,
    const TerminalCapabilities& capabilities,
    std::size_t command_count) const
{
    output << "FacMan terminal UI (linear mode)\n"
           << "Renderer: " << renderer_mode_name(capabilities.selected_renderer)
           << " (" << capabilities.selection_reason << ")\n"
           << "Advanced commands: " << command_count << "\n"
           << "Use 'facman tui --advanced' in an interactive terminal,\n"
           << "or 'facman tui --list' for the bounded command catalogue.\n";
}

void LinearAccessibleRenderer::render_capabilities(
    std::ostream& output,
    const TerminalCapabilities& capabilities,
    bool structured) const
{
    if (structured) {
        output << capabilities.json() << '\n';
        return;
    }
    output << "Terminal capabilities\n"
           << "Input: " << (capabilities.interactive_input ? "interactive" : "redirected") << '\n'
           << "Size: " << capabilities.observed.columns << 'x' << capabilities.observed.rows << '\n'
           << "Unicode: " << (capabilities.unicode ? "available" : "fallback") << '\n'
           << "Color: " << (capabilities.color ? "available" : "disabled") << '\n'
           << "Renderer: " << renderer_mode_name(capabilities.selected_renderer)
           << " (" << capabilities.selection_reason << ")\n";
}

} // namespace facman::tui
