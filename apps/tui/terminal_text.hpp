// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#pragma once

#include <cstddef>
#include <string>

namespace facman::tui {

// Terminal text is measured in display cells, never UTF-8 bytes. Invalid
// sequences are replaced and grapheme-like joined sequences are kept intact.
std::size_t terminal_display_width(const std::string& text) noexcept;
std::string clip_terminal_text(const std::string& text, std::size_t width);

} // namespace facman::tui
