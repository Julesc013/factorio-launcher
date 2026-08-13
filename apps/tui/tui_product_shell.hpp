// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#pragma once

#include "terminal_capabilities.hpp"
#include "tui_command_client.hpp"

#include <iosfwd>

namespace facman::tui {

struct ProductShellOptions {
    bool force_linear = false;
    bool unicode = false;
};

inline constexpr int kProductShellOpenAdvanced = 64;

int run_product_shell(
    CommandClient& client,
    std::istream& input,
    std::ostream& output,
    std::ostream& error,
    const TerminalCapabilities& capabilities,
    const ProductShellOptions& options);

} // namespace facman::tui
