// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#pragma once

#include "terminal_capabilities.hpp"
#include "terminal_text.hpp"
#include "tui_product_model.hpp"

#include <iosfwd>

namespace facman::tui {

class ProductRenderer {
public:
    static void render_linear(std::ostream& output, const TuiRenderModel& model);
    static void enter_full_screen(std::ostream& output);
    static void leave_full_screen(std::ostream& output);
    static void render_full_screen(
        std::ostream& output,
        const TuiRenderModel& model,
        const TerminalCapabilities& capabilities);
};

} // namespace facman::tui
