// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "tui_product_shell.hpp"

#include "tui_product_model.hpp"
#include "tui_product_renderer.hpp"

#include "fl_json.h"

#include <algorithm>
#include <cctype>
#include <iostream>
#include <string>

#ifdef _WIN32
#include <conio.h>
#else
#include <sys/select.h>
#include <termios.h>
#include <unistd.h>
#endif

namespace facman::tui {
namespace {

std::string scope_for(TuiPage page)
{
    switch (page) {
    case TuiPage::instances: return "instances";
    case TuiPage::installations: return "installations";
    case TuiPage::activity: return "activity_recovery";
    case TuiPage::home:
    case TuiPage::content:
    case TuiPage::saves:
    case TuiPage::settings:
    case TuiPage::advanced: return "launch_deck";
    }
    return "launch_deck";
}

std::string lower(std::string value)
{
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return value;
}

bool refresh(CommandClient& client, TuiState& state, std::ostream& error)
{
    const std::string scope = scope_for(state.page);
    auto identity = client.negotiate(scope, state.snapshot.selected_instance_id, state.search);
    if (!identity) {
        TuiEvent event;
        event.kind = TuiEventKind::transport_disconnected;
        event.value = identity.error().code + ": " + identity.error().message;
        state = reduce_tui_state(state, event);
        error << "Presentation refresh refused: " << event.value << '\n';
        return false;
    }
    TuiSnapshot snapshot = parse_presentation_snapshot(identity.value().raw_snapshot);
    if (snapshot.revision.empty()) {
        TuiEvent event;
        event.kind = TuiEventKind::transport_disconnected;
        event.value = "Presentation snapshot could not be decoded";
        state = reduce_tui_state(state, event);
        error << event.value << '\n';
        return false;
    }
    if (snapshot.selected_instance_id.empty() && !state.snapshot.selected_instance_id.empty()) {
        snapshot.selected_instance_id = state.snapshot.selected_instance_id;
        snapshot.selected_instance_name = state.snapshot.selected_instance_name;
        snapshot.factorio_version = state.snapshot.factorio_version;
        snapshot.profile = state.snapshot.profile;
    }
    if (snapshot.selected_instance_id.empty() && !snapshot.items.empty() &&
        (state.page == TuiPage::home || state.page == TuiPage::instances)) {
        const std::string selection = snapshot.items.front().id;
        auto selected = client.negotiate(scope, selection, state.search);
        if (selected) snapshot = parse_presentation_snapshot(selected.value().raw_snapshot);
    }
    TuiEvent event;
    event.kind = TuiEventKind::snapshot_received;
    event.snapshot = std::move(snapshot);
    state = reduce_tui_state(state, event);
    return true;
}

void navigate(TuiState& state, std::size_t index)
{
    TuiEvent event;
    event.kind = TuiEventKind::navigate;
    event.page = tui_page_at(index);
    state = reduce_tui_state(state, event);
}

void navigate_relative(TuiState& state, int direction)
{
    const std::size_t current = tui_page_index(state.page);
    const std::size_t index = direction < 0
        ? (current == 0U ? 7U : current - 1U)
        : (current + 1U) % 8U;
    navigate(state, index);
}

void select_relative(TuiState& state, int direction)
{
    if (state.snapshot.items.empty()) return;
    std::size_t index = state.selected_item;
    if (direction < 0) index = index == 0U ? state.snapshot.items.size() - 1U : index - 1U;
    else index = (index + 1U) % state.snapshot.items.size();
    TuiEvent event;
    event.kind = TuiEventKind::select;
    event.index = index;
    state = reduce_tui_state(state, event);
}

void toggle_help(TuiState& state)
{
    state.help_visible = !state.help_visible;
    state.status = state.help_visible
        ? "Help: use numbered pages, j/k or arrows, Enter/Space, /, Ctrl+R, Esc, Ctrl+C, q"
        : "Help closed";
}

int activate(CommandClient& client, TuiState& state)
{
    if (state.page == TuiPage::advanced) return kProductShellOpenAdvanced;
    if ((state.page == TuiPage::instances || state.page == TuiPage::home) &&
        !state.snapshot.items.empty()) {
        TuiEvent event;
        event.kind = TuiEventKind::select;
        event.index = state.selected_item;
        state = reduce_tui_state(state, event);
        return 0;
    }
    const std::string target = state.page == TuiPage::installations
        ? "installations.scan"
        : (state.page == TuiPage::activity ? "recovery.inspect" : "launch.play");
    auto action = std::find_if(state.snapshot.actions.begin(), state.snapshot.actions.end(),
        [&target](const TuiAction& candidate) { return candidate.id == target; });
    TuiEvent event;
    event.kind = TuiEventKind::activate_action;
    if (action == state.snapshot.actions.end()) {
        event.name = {};
    } else if (!action->available) {
        state.status = "Action refused before effects: " + action->blocker;
        return 0;
    } else if (action->id == "installations.scan") {
        facman::core::json::ObjectBuilder payload;
        payload.add_string("action_id", action->id);
        payload.add_string("scope", "installations");
        payload.add_string("expected_snapshot_revision", state.snapshot.revision);
        payload.add_string("request_id", "tui-scan-" + state.snapshot.revision.substr(0U, 16U));
        payload.add_string("idempotency_key", "tui-scan-" + state.snapshot.revision);
        Invocation invocation;
        invocation.command = "presentation.action";
        invocation.payload = payload.serialize();
        const auto response = client.execute(invocation);
        if (!response) {
            state.status = "Action transport error: " + response.error().code;
        } else if (!response.value().ok()) {
            state.status = "Action refused before effects: " + response.value().error_code;
        } else {
            state.status = "Installation scan completed; refreshing authoritative state";
            state.refresh_requested = true;
        }
        return 0;
    } else {
        event.name = action->id;
    }
    state = reduce_tui_state(state, event);
    return 0;
}

int process_line(CommandClient& client, TuiState& state, std::string command)
{
    if (!command.empty() && command.back() == '\r') command.pop_back();
    const std::string normalized = lower(command);
    if (normalized == "q" || normalized == "quit" || normalized == "exit") {
        state.quit_requested = true;
        return 0;
    }
    if (normalized == "help" || normalized == "f1" || normalized == "?") {
        toggle_help(state);
        return 0;
    }
    if (normalized == "r" || normalized == "refresh") {
        TuiEvent event;
        event.kind = TuiEventKind::refresh;
        state = reduce_tui_state(state, event);
        return 0;
    }
    if (normalized == "j" || normalized == "down") {
        select_relative(state, 1);
        return 0;
    }
    if (normalized == "k" || normalized == "up") {
        select_relative(state, -1);
        return 0;
    }
    if (normalized == "enter" || normalized == "open" || normalized.empty()) return activate(client, state);
    if (normalized == "a" || normalized == "advanced") {
        navigate(state, 7U);
        return kProductShellOpenAdvanced;
    }
    if (command.front() == '/') {
        TuiEvent event;
        event.kind = TuiEventKind::search;
        event.value = command.substr(1U);
        state = reduce_tui_state(state, event);
        return 0;
    }
    if (command.size() == 1U && command[0] >= '1' && command[0] <= '8') {
        navigate(state, static_cast<std::size_t>(command[0] - '1'));
        return 0;
    }
    state.status = "Unknown input; use help for portable keys";
    return 0;
}

class RawTerminal {
public:
    explicit RawTerminal(bool enabled) : enabled_(enabled)
    {
#ifndef _WIN32
        if (enabled_ && tcgetattr(STDIN_FILENO, &original_) == 0) {
            termios raw = original_;
            raw.c_lflag &= static_cast<tcflag_t>(~(ICANON | ECHO));
            raw.c_cc[VMIN] = 1;
            raw.c_cc[VTIME] = 0;
            active_ = tcsetattr(STDIN_FILENO, TCSANOW, &raw) == 0;
        }
#endif
    }

    ~RawTerminal()
    {
#ifndef _WIN32
        if (active_) tcsetattr(STDIN_FILENO, TCSANOW, &original_);
#endif
    }

    int read()
    {
#ifdef _WIN32
        if (!enabled_) return std::cin.get();
        return _getwch();
#else
        unsigned char value = 0;
        return ::read(STDIN_FILENO, &value, 1U) == 1 ? static_cast<int>(value) : EOF;
#endif
    }

    int read_continuation()
    {
#ifdef _WIN32
        return read();
#else
        fd_set input;
        FD_ZERO(&input);
        FD_SET(STDIN_FILENO, &input);
        timeval timeout {0, 30000};
        if (select(STDIN_FILENO + 1, &input, nullptr, nullptr, &timeout) <= 0) return EOF;
        return read();
#endif
    }

private:
    bool enabled_ = false;
#ifndef _WIN32
    bool active_ = false;
    termios original_ {};
#endif
};

int run_full_screen(
    CommandClient& client,
    TuiState& state,
    std::ostream& output,
    std::ostream& error,
    const TerminalCapabilities& capabilities,
    bool unicode)
{
    ProductRenderer::enter_full_screen(output);
    RawTerminal terminal(true);
    TerminalCapabilities current_capabilities = capabilities;
    int result = 0;
    while (!state.quit_requested) {
        if (state.refresh_requested) refresh(client, state, error);
        current_capabilities = observe_terminal_capabilities(false);
        TuiEvent resized;
        resized.kind = TuiEventKind::resize;
        resized.columns = current_capabilities.observed.columns;
        resized.rows = current_capabilities.observed.rows;
        state = reduce_tui_state(state, resized);
        ProductRenderer::render_full_screen(
            output, make_tui_render_model(state, unicode), current_capabilities);
        const int key = terminal.read();
        if (key == EOF || key == 'q') break;
        if (key >= '1' && key <= '8') navigate(state, static_cast<std::size_t>(key - '1'));
        else if (key == 'j') select_relative(state, 1);
        else if (key == 'k') select_relative(state, -1);
        else if (key == '\t') select_relative(state, 1);
        else if (key == '\r' || key == '\n' || key == ' ') {
            result = activate(client, state);
            if (result == kProductShellOpenAdvanced) break;
        } else if (key == 0x10) {
            state.command_palette_visible = !state.command_palette_visible;
            state.status = state.command_palette_visible
                ? "Command palette: choose Advanced for the full generated catalogue"
                : "Command palette closed";
        } else if (key == 0x12) {
            TuiEvent event;
            event.kind = TuiEventKind::refresh;
            state = reduce_tui_state(state, event);
        } else if (key == 0x03) {
            TuiEvent event;
            event.kind = TuiEventKind::cancel;
            state = reduce_tui_state(state, event);
        } else if (key == '/') {
            std::string query;
            output << "\x1b[" << current_capabilities.observed.rows << ";1H\x1b[KSearch: " << std::flush;
            for (;;) {
                const int item = terminal.read();
                if (item == EOF || item == '\r' || item == '\n') break;
                if (item == 27) { query.clear(); break; }
                if ((item == 8 || item == 127) && !query.empty()) query.pop_back();
                else if (item >= 32 && item <= 126) query.push_back(static_cast<char>(item));
                output << "\r\x1b[KSearch: " << query << std::flush;
            }
            TuiEvent event;
            event.kind = TuiEventKind::search;
            event.value = std::move(query);
            state = reduce_tui_state(state, event);
        }
#ifdef _WIN32
        else if (key == 0 || key == 224) {
            const int extended = terminal.read();
            if (extended == 72) select_relative(state, -1);
            else if (extended == 80) select_relative(state, 1);
            else if (extended == 59) toggle_help(state);
        }
        else if (key == 27) {
            TuiEvent event;
            event.kind = TuiEventKind::cancel;
            state = reduce_tui_state(state, event);
        }
#else
        else if (key == 0x1b) {
            const int bracket = terminal.read_continuation();
            if (bracket == EOF) {
                TuiEvent event;
                event.kind = TuiEventKind::cancel;
                state = reduce_tui_state(state, event);
                continue;
            }
            const int direction = terminal.read_continuation();
            if (bracket == '[' && direction == 'A') select_relative(state, -1);
            else if (bracket == '[' && direction == 'B') select_relative(state, 1);
            else if (bracket == '[' && direction == 'C') navigate_relative(state, 1);
            else if (bracket == '[' && direction == 'D') navigate_relative(state, -1);
            else if (bracket == '[' && direction == 'Z') select_relative(state, -1);
            else if ((bracket == 'O' || bracket == '[') && direction == 'P') toggle_help(state);
        }
#endif
    }
    ProductRenderer::leave_full_screen(output);
    return result;
}

} // namespace

int run_product_shell(
    CommandClient& client,
    std::istream& input,
    std::ostream& output,
    std::ostream& error,
    const TerminalCapabilities& capabilities,
    const ProductShellOptions& options)
{
    TuiState state;
    state.columns = capabilities.observed.columns == 0U ? 80U : capabilities.observed.columns;
    state.rows = capabilities.observed.rows == 0U ? 24U : capabilities.observed.rows;
    const bool full_screen = !options.force_linear &&
        capabilities.selected_renderer == TerminalRendererMode::full_screen &&
        &input == &std::cin && &output == &std::cout;
    if (full_screen) {
        return run_full_screen(client, state, output, error, capabilities, options.unicode);
    }
    while (!state.quit_requested) {
        if (state.refresh_requested) refresh(client, state, error);
        ProductRenderer::render_linear(output, make_tui_render_model(state, options.unicode));
        std::string command;
        if (!std::getline(input, command)) break;
        const int result = process_line(client, state, std::move(command));
        if (result == kProductShellOpenAdvanced) return result;
    }
    return 0;
}

} // namespace facman::tui
