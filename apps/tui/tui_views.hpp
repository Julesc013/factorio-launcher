// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#pragma once

#include "facman_client.h"

#include <iosfwd>
#include <string>

namespace facman::tui {

constexpr std::size_t kMaximumDisplayBytes = 1024U * 1024U;

void render_catalog(std::ostream& output, bool structured);
int render_response(
    std::ostream& output,
    std::ostream& error,
    const std::string& command,
    const facman::core::Result<facman::client::CommandResponse>& response,
    bool structured);
}  // namespace facman::tui
