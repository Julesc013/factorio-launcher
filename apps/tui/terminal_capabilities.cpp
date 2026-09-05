// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "terminal_capabilities.hpp"

#include "fl_json.h"

#include <algorithm>
#include <cctype>
#include <clocale>
#include <cstdio>
#include <cstdlib>
#include <string>

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <io.h>
#else
#include <sys/ioctl.h>
#include <unistd.h>
#endif

namespace facman::tui {
namespace json = facman::core::json;

namespace {

bool environment_truthy(const char* name)
{
    const char* value = std::getenv(name);
    if (value == nullptr) return false;
    std::string text(value);
    std::transform(text.begin(), text.end(), text.begin(),
        [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
    return text.empty() || (text != "0" && text != "false" && text != "off" && text != "no");
}

bool environment_equals(const char* name, const char* expected)
{
    const char* value = std::getenv(name);
    return value != nullptr && std::string(value) == expected;
}

bool locale_is_utf8()
{
    const char* locale = std::setlocale(LC_CTYPE, nullptr);
    std::string value = locale == nullptr ? std::string() : std::string(locale);
    const char* language = std::getenv("LC_ALL");
    if (language == nullptr || *language == '\0') language = std::getenv("LC_CTYPE");
    if (language == nullptr || *language == '\0') language = std::getenv("LANG");
    if (language != nullptr) value += language;
    std::transform(value.begin(), value.end(), value.begin(),
        [](unsigned char ch) { return static_cast<char>(std::tolower(ch)); });
    return value.find("utf-8") != std::string::npos || value.find("utf8") != std::string::npos;
}

} // namespace

const char* renderer_mode_name(TerminalRendererMode mode) noexcept
{
    return mode == TerminalRendererMode::full_screen ? "full_screen" : "linear";
}

TerminalCapabilities select_terminal_capabilities(TerminalObservation observation)
{
    TerminalCapabilities result;
    result.observed = std::move(observation);
    result.interactive_input = result.observed.input_tty && result.observed.output_tty;
    result.cursor_addressing = result.interactive_input && result.observed.vt_output &&
        !result.observed.term_dumb;
    result.color = result.observed.output_tty && !result.observed.no_color &&
        !result.observed.force_plain && !result.observed.safe_mode;
    result.unicode = result.observed.utf8 && !result.observed.safe_mode;

    if (!result.interactive_input) result.selection_reason = "redirected_stream";
    else if (result.observed.force_plain) result.selection_reason = "plain_mode_requested";
    else if (result.observed.safe_mode) result.selection_reason = "safe_mode_requested";
    else if (result.observed.term_dumb) result.selection_reason = "term_dumb";
    else if (!result.cursor_addressing) result.selection_reason = "cursor_addressing_unavailable";
    else if (result.observed.columns < kMinimumFullScreenColumns ||
             result.observed.rows < kMinimumFullScreenRows) {
        result.selection_reason = "dimensions_below_full_screen_minimum";
    }
    else if (!result.observed.full_screen_adapter_available) {
        result.selection_reason = "full_screen_adapter_unadmitted";
    } else {
        result.selected_renderer = TerminalRendererMode::full_screen;
        result.selection_reason = "full_screen_capabilities_available";
    }
    return result;
}

TerminalCapabilities observe_terminal_capabilities(bool force_plain)
{
    TerminalObservation observation;
#ifdef _WIN32
    observation.input_tty = _isatty(_fileno(stdin)) != 0;
    observation.output_tty = _isatty(_fileno(stdout)) != 0;
    observation.error_tty = _isatty(_fileno(stderr)) != 0;
    DWORD input_mode = 0;
    DWORD output_mode = 0;
    const HANDLE input = GetStdHandle(STD_INPUT_HANDLE);
    const HANDLE output = GetStdHandle(STD_OUTPUT_HANDLE);
    observation.vt_input = input != INVALID_HANDLE_VALUE && GetConsoleMode(input, &input_mode) != 0 &&
        (input_mode & ENABLE_VIRTUAL_TERMINAL_INPUT) != 0;
    observation.vt_output = output != INVALID_HANDLE_VALUE && GetConsoleMode(output, &output_mode) != 0 &&
        (output_mode & ENABLE_VIRTUAL_TERMINAL_PROCESSING) != 0;
    CONSOLE_SCREEN_BUFFER_INFO info {};
    if (output != INVALID_HANDLE_VALUE && GetConsoleScreenBufferInfo(output, &info) != 0) {
        observation.columns = static_cast<std::size_t>(info.srWindow.Right - info.srWindow.Left + 1);
        observation.rows = static_cast<std::size_t>(info.srWindow.Bottom - info.srWindow.Top + 1);
    }
    observation.conpty = observation.output_tty &&
        (std::getenv("WT_SESSION") != nullptr || std::getenv("ConEmuPID") != nullptr);
    observation.utf8 = GetConsoleOutputCP() == CP_UTF8 || locale_is_utf8();
#else
    observation.input_tty = isatty(STDIN_FILENO) != 0;
    observation.output_tty = isatty(STDOUT_FILENO) != 0;
    observation.error_tty = isatty(STDERR_FILENO) != 0;
    struct winsize size {};
    if (observation.output_tty && ioctl(STDOUT_FILENO, TIOCGWINSZ, &size) == 0) {
        observation.columns = size.ws_col;
        observation.rows = size.ws_row;
    }
    observation.vt_input = observation.input_tty;
    observation.vt_output = observation.output_tty && !environment_equals("TERM", "dumb");
    observation.utf8 = locale_is_utf8();
#endif
    observation.term_dumb = environment_equals("TERM", "dumb");
    const char* no_color = std::getenv("NO_COLOR");
    observation.no_color = no_color != nullptr && *no_color != '\0';
    observation.force_plain = force_plain || environment_equals("FACMAN_UI", "plain");
    observation.safe_mode = environment_truthy("FACMAN_SAFE_MODE");
    // The project-owned ANSI/ConPTY adapter is part of the required binary.
    // Capability selection still keeps it dormant for redirected, dumb,
    // plain, safe-mode, and non-VT terminals.
    observation.full_screen_adapter_available = true;
    return select_terminal_capabilities(std::move(observation));
}

std::string TerminalCapabilities::json() const
{
    json::ObjectBuilder streams;
    streams.add_bool("stdin_tty", observed.input_tty);
    streams.add_bool("stdout_tty", observed.output_tty);
    streams.add_bool("stderr_tty", observed.error_tty);
    json::ObjectBuilder dimensions;
    dimensions.add_unsigned_integer("columns", observed.columns);
    dimensions.add_unsigned_integer("rows", observed.rows);
    json::ObjectBuilder terminal;
    terminal.add_bool("term_dumb", observed.term_dumb);
    terminal.add_bool("no_color", observed.no_color);
    terminal.add_bool("utf8", observed.utf8);
    terminal.add_bool("vt_input", observed.vt_input);
    terminal.add_bool("vt_output", observed.vt_output);
    terminal.add_bool("conpty", observed.conpty);
    terminal.add_bool("safe_mode", observed.safe_mode);
    terminal.add_bool("force_plain", observed.force_plain);
    terminal.add_bool("full_screen_adapter_available", observed.full_screen_adapter_available);
    json::ObjectBuilder output;
    output.add_string("schema", "facman.terminal_capabilities.v1");
    output.add_object("streams", streams);
    output.add_object("dimensions", dimensions);
    output.add_object("terminal", terminal);
    output.add_bool("interactive_input", interactive_input);
    output.add_bool("cursor_addressing", cursor_addressing);
    output.add_bool("color", color);
    output.add_bool("unicode", unicode);
    output.add_string("selected_renderer", renderer_mode_name(selected_renderer));
    output.add_string("selection_reason", selection_reason);
    return output.serialize();
}

} // namespace facman::tui
