// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "tui_product_shell.hpp"

#include "tui_product_model.hpp"
#include "tui_product_renderer.hpp"

#include "fl_json.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <cerrno>
#include <csignal>
#include <iostream>
#include <string>

#ifdef _WIN32
#include <conio.h>
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
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
    case TuiPage::content: return "content";
    case TuiPage::saves: return "saves";
    case TuiPage::activity: return "activity_recovery";
    case TuiPage::settings: return "settings_support";
    case TuiPage::home:
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
        // Selection identity is frontend interaction state. All descriptive
        // attributes remain backend-owned and must be reprojected.
        snapshot.selected_instance_id = state.snapshot.selected_instance_id;
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

void select_action_relative(TuiState& state, int direction)
{
    if (state.snapshot.actions.empty()) return;
    std::size_t index = state.selected_action;
    if (direction < 0) index = index == 0U ? state.snapshot.actions.size() - 1U : index - 1U;
    else index = (index + 1U) % state.snapshot.actions.size();
    TuiEvent event;
    event.kind = TuiEventKind::select_action;
    event.index = index;
    state = reduce_tui_state(state, event);
}

void toggle_help(TuiState& state)
{
    state.help_visible = !state.help_visible;
    state.status = state.help_visible
        ? "Help: use numbered pages, j/k or arrows, Enter, Tab/Shift+Tab, Space, /, Ctrl+R, Esc, Ctrl+C, q"
        : "Help closed";
}

int open_selected_item(TuiState& state)
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
    state.status = state.snapshot.items.empty()
        ? "No item is available to open"
        : "The selected item has no ordinary detail view yet";
    return 0;
}

std::string doctor_feedback(const facman::client::CommandResponse& response)
{
    if (!response.parsed_payload) return {};
    const auto* action_payload = response.parsed_payload->find("action_payload");
    if (action_payload == nullptr || !action_payload->is_object()) return {};
    const auto* status = action_payload->find("status");
    if (status == nullptr || !status->is_string()) return {};
    auto decoded = status->string_value();
    if (!decoded) return {};
    std::string feedback = "Doctor completed: " + decoded.value();
    const auto append_first = [&feedback, action_payload](const char* key, const char* prefix) {
        const auto* values = action_payload->find(key);
        const auto* first = values != nullptr && values->is_array() ? values->at(0U) : nullptr;
        if (first == nullptr || !first->is_string()) return;
        auto value = first->string_value();
        if (value) feedback += std::string("; ") + prefix + value.value();
    };
    append_first("problems", "problem: ");
    append_first("suggested_fixes", "next: ");
    return feedback;
}

int activate_selected_action(CommandClient& client, TuiState& state)
{
    if (state.page == TuiPage::advanced) return kProductShellOpenAdvanced;
    if (state.snapshot.actions.empty()) {
        state.status = "No contextual action is available";
        return 0;
    }
    const std::size_t index = (std::min)(state.selected_action, state.snapshot.actions.size() - 1U);
    const TuiAction action = state.snapshot.actions[index];
    if (!action.available) {
        state.status = "Action refused before effects: " + action.blocker;
        return 0;
    }
    if (action.effect != "read_only") {
        state.status = "Action requires an admitted review and confirmation form: " + action.label;
        return 0;
    }

    const TuiActionIdentity identity = issue_action_identity(state, action.id);
    facman::core::json::ObjectBuilder payload;
    payload.add_string("action_id", action.id);
    payload.add_string("scope", scope_for(state.page));
    payload.add_string("expected_snapshot_revision", state.snapshot.revision);
    payload.add_string("request_id", identity.request_id);
    payload.add_string("idempotency_key", identity.idempotency_key);
    if (!state.snapshot.selected_instance_id.empty()) {
        payload.add_string("selected_instance_id", state.snapshot.selected_instance_id);
    }
    Invocation invocation;
    invocation.command = "presentation.action";
    invocation.payload = payload.serialize();
    const auto response = client.execute(invocation);
    if (!response) {
        state.status = "Action transport error: " + response.error().code;
        return 0;
    }
    if (!response.value().ok()) {
        state.status = "Action refused before effects: " + response.value().error_code;
        return 0;
    }

    TuiEvent event;
    event.kind = TuiEventKind::activate_action;
    event.name = action.id;
    state = reduce_tui_state(state, event);
    state.pending_action.clear();

    const std::string replacement_json =
        response.value().payload_member_json("replacement_snapshot");
    if (replacement_json != "null") {
        TuiSnapshot replacement = parse_presentation_snapshot(replacement_json);
        if (replacement.revision.empty() || replacement.scope != scope_for(state.page)) {
            state.status = "Action response invalid: replacement snapshot did not match the active scope";
            return 0;
        }
        TuiEvent received;
        received.kind = TuiEventKind::snapshot_received;
        received.snapshot = std::move(replacement);
        state = reduce_tui_state(state, received);
    }
    state.status = action.label + " completed";
    const std::string feedback = doctor_feedback(response.value());
    if (!feedback.empty()) state.status = feedback;

    if (response.value().payload_member_json("invalidation") != "null") {
        state.status += "; refreshing authoritative state";
        state.refresh_requested = true;
    }
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
    if (normalized == "tab" || normalized == "next-action") {
        select_action_relative(state, 1);
        return 0;
    }
    if (normalized == "shift-tab" || normalized == "previous-action") {
        select_action_relative(state, -1);
        return 0;
    }
    if (normalized == "space" || normalized == "run" || normalized == "action") {
        return activate_selected_action(client, state);
    }
    if (normalized == "enter" || normalized == "open" || normalized.empty()) {
        return open_selected_item(state);
    }
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

class FullScreenSession {
public:
    explicit FullScreenSession(std::ostream& output) : output_(output)
    {
        resume();
    }

    ~FullScreenSession() noexcept
    {
        try {
            suspend();
        } catch (...) {
            // Terminal restoration is best-effort during stack unwinding.
        }
    }

    void suspend()
    {
        if (!active_) return;
        ProductRenderer::leave_full_screen(output_);
        active_ = false;
    }

    void resume()
    {
        if (active_) return;
        ProductRenderer::enter_full_screen(output_);
        active_ = true;
    }

private:
    std::ostream& output_;
    bool active_ = false;
};

#ifndef _WIN32
volatile std::sig_atomic_t pending_terminal_signal = 0;
volatile std::sig_atomic_t terminal_continue_observed = 0;

void terminal_signal_handler(int signal_number)
{
    pending_terminal_signal = signal_number;
}

void terminal_continue_handler(int)
{
    terminal_continue_observed = 1;
}

class TerminalSignals {
public:
    TerminalSignals()
    {
        struct sigaction action {};
        action.sa_handler = terminal_signal_handler;
        sigemptyset(&action.sa_mask);
        action.sa_flags = 0;
        for (std::size_t index = 0U; index < signals_.size(); ++index) {
            sigaction(signals_[index], &action, &original_[index]);
        }
    }

    ~TerminalSignals()
    {
        for (std::size_t index = 0U; index < signals_.size(); ++index) {
            sigaction(signals_[index], &original_[index], nullptr);
        }
    }

    int take() noexcept
    {
        const int result = pending_terminal_signal;
        pending_terminal_signal = 0;
        return result;
    }

    void suspend_process()
    {
        struct sigaction action {};
        struct sigaction original_continue {};
        action.sa_handler = terminal_continue_handler;
        sigemptyset(&action.sa_mask);
        action.sa_flags = 0;
        sigaction(SIGCONT, &action, &original_continue);
        terminal_continue_observed = 0;

        action.sa_handler = SIG_DFL;
        sigemptyset(&action.sa_mask);
        sigaction(SIGTSTP, &action, nullptr);
        std::raise(SIGTSTP);
        // POSIX permits a job-control stop signal to be discarded for an
        // orphaned process group. Headless PTY hosts can therefore return
        // from SIGTSTP even though the user explicitly requested suspend.
        // SIGSTOP supplies the same resumable boundary in that environment;
        // an ordinary interactive shell observes SIGCONT before returning.
        if (terminal_continue_observed == 0) std::raise(SIGSTOP);

        sigaction(SIGCONT, &original_continue, nullptr);
        action.sa_handler = terminal_signal_handler;
        sigaction(SIGTSTP, &action, nullptr);
    }

private:
    const std::array<int, 4U> signals_ {SIGINT, SIGTERM, SIGHUP, SIGTSTP};
    std::array<struct sigaction, 4U> original_ {};
};
#else
class TerminalSignals {
public:
    int take() const noexcept { return 0; }
};
#endif

inline constexpr int kTerminalNoInput = -2;

class RawTerminal {
public:
    explicit RawTerminal(bool enabled) : enabled_(enabled)
    {
#ifdef _WIN32
        if (enabled_) {
            input_ = GetStdHandle(STD_INPUT_HANDLE);
            DWORD mode = 0;
            if (input_ != INVALID_HANDLE_VALUE && GetConsoleMode(input_, &mode) != 0) {
                original_mode_ = mode;
                const DWORD raw = mode & ~(ENABLE_LINE_INPUT | ENABLE_ECHO_INPUT | ENABLE_PROCESSED_INPUT);
                active_ = SetConsoleMode(input_, raw) != 0;
            }
        }
#else
        if (enabled_ && tcgetattr(STDIN_FILENO, &original_) == 0) {
            raw_ = original_;
            raw_.c_lflag &= static_cast<tcflag_t>(~(ICANON | ECHO | ISIG | IEXTEN));
            raw_.c_iflag &= static_cast<tcflag_t>(~(IXON | ICRNL));
            raw_.c_cc[VMIN] = 1;
            raw_.c_cc[VTIME] = 0;
            resume();
        }
#endif
    }

    ~RawTerminal()
    {
#ifdef _WIN32
        if (active_) SetConsoleMode(input_, original_mode_);
#else
        suspend();
#endif
    }

    void suspend()
    {
#ifndef _WIN32
        if (active_) {
            tcsetattr(STDIN_FILENO, TCSANOW, &original_);
            active_ = false;
        }
#endif
    }

    void resume()
    {
#ifndef _WIN32
        if (enabled_ && !active_) active_ = tcsetattr(STDIN_FILENO, TCSANOW, &raw_) == 0;
#endif
    }

    int read()
    {
#ifdef _WIN32
        if (!enabled_) return std::cin.get();
        return _getwch();
#else
        fd_set input;
        FD_ZERO(&input);
        FD_SET(STDIN_FILENO, &input);
        timeval timeout {0, 100000};
        const int ready = select(STDIN_FILENO + 1, &input, nullptr, nullptr, &timeout);
        if (ready == 0) return kTerminalNoInput;
        if (ready < 0) return EOF;
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
#ifdef _WIN32
    bool active_ = false;
    HANDLE input_ = INVALID_HANDLE_VALUE;
    DWORD original_mode_ = 0;
#else
    bool active_ = false;
    termios original_ {};
    termios raw_ {};
#endif
};

inline constexpr int kProductShellFallbackLinear = 65;

int run_full_screen(
    CommandClient& client,
    TuiState& state,
    std::ostream& output,
    std::ostream& error,
    const TerminalCapabilities& capabilities,
    bool unicode)
{
    TerminalSignals signals;
    FullScreenSession screen(output);
    RawTerminal terminal(true);
    TerminalCapabilities current_capabilities = capabilities;
    int result = 0;
    while (!state.quit_requested) {
        if (state.refresh_requested) refresh(client, state, error);
        current_capabilities = observe_terminal_capabilities(false);
        if (current_capabilities.selected_renderer != TerminalRendererMode::full_screen) {
            const std::string prior_status = state.status;
            state.status = "Switched to portable linear mode: " + current_capabilities.selection_reason;
            if (!prior_status.empty()) state.status += "; prior status: " + prior_status;
            return kProductShellFallbackLinear;
        }
        TuiEvent resized;
        resized.kind = TuiEventKind::resize;
        resized.columns = current_capabilities.observed.columns;
        resized.rows = current_capabilities.observed.rows;
        state = reduce_tui_state(state, resized);
        ProductRenderer::render_full_screen(
            output, make_tui_render_model(state, unicode), current_capabilities);
        int signal_number = signals.take();
        const int key = signal_number == 0 ? terminal.read() : kTerminalNoInput;
        if (signal_number == 0) signal_number = signals.take();
#ifndef _WIN32
        if (signal_number == SIGTSTP) {
            terminal.suspend();
            screen.suspend();
            signals.suspend_process();
            screen.resume();
            terminal.resume();
            if (refresh(client, state, error)) {
                state.status = "Terminal session resumed; authoritative state refreshed";
            }
            continue;
        }
        if (signal_number == SIGINT) {
            TuiEvent event;
            event.kind = TuiEventKind::cancel;
            state = reduce_tui_state(state, event);
            continue;
        }
        if (signal_number == SIGTERM || signal_number == SIGHUP) {
            result = 128 + signal_number;
            break;
        }
#else
        (void)signal_number;
#endif
        if (key == kTerminalNoInput) continue;
        if (key == EOF || key == 'q') break;
        if (key >= '1' && key <= '8') navigate(state, static_cast<std::size_t>(key - '1'));
        else if (key == 'j') select_relative(state, 1);
        else if (key == 'k') select_relative(state, -1);
        else if (key == '\t') select_action_relative(state, 1);
        else if (key == '\r' || key == '\n') {
            result = open_selected_item(state);
            if (result == kProductShellOpenAdvanced) break;
        } else if (key == ' ') {
            result = activate_selected_action(client, state);
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
#ifndef _WIN32
        } else if (key == 0x1a) {
            terminal.suspend();
            screen.suspend();
            signals.suspend_process();
            screen.resume();
            terminal.resume();
            if (refresh(client, state, error)) {
                state.status = "Terminal session resumed; authoritative state refreshed";
            }
#endif
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
            else if (bracket == '[' && direction == 'Z') select_action_relative(state, -1);
            else if ((bracket == 'O' || bracket == '[') && direction == 'P') toggle_help(state);
        }
#endif
    }
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
        const int result = run_full_screen(client, state, output, error, capabilities, options.unicode);
        if (result != kProductShellFallbackLinear) return result;
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
