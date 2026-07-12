// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#pragma once

#include "tui_command_client.hpp"

#include <cstddef>
#include <iosfwd>
#include <string>

namespace facman::tui {

struct GuidedOptions {
    std::size_t page_size = 25;
    bool page_results = true;
    bool color = false;
    bool plain = false;
};

int run_guided(
    CommandClient& client,
    std::istream& input,
    std::ostream& output,
    std::ostream& error,
    const GuidedOptions& options);

}  // namespace facman::tui
