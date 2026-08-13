// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#pragma once

#include "terminal_capabilities.hpp"

#include <iosfwd>

namespace facman::tui {

class LinearAccessibleRenderer {
public:
    void render_landing(
        std::ostream& output,
        const TerminalCapabilities& capabilities,
        std::size_t command_count) const;
    void render_capabilities(
        std::ostream& output,
        const TerminalCapabilities& capabilities,
        bool structured) const;
};

} // namespace facman::tui
