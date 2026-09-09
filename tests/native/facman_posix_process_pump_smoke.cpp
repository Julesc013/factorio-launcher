// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "../../runtime/platform/fl_process_supervisor_posix_pump.h"

#include <deque>
#include <iostream>
#include <map>
#include <optional>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>
#include <fcntl.h>
#include <unistd.h>

namespace {
using namespace facman::platform;
using namespace facman::platform::detail;

void require(bool value, const char* message)
{
    if (!value) throw std::runtime_error(message);
}

struct ReadAction {
    std::string bytes;
    int error = 0;
    std::optional<ssize_t> reported_count;
    ReadAction(std::string value, int failure = 0)
        : bytes(std::move(value)), error(failure) {}
    ReadAction(std::string value, int failure, ssize_t count)
        : bytes(std::move(value)), error(failure), reported_count(count) {}
};
struct FakePipes {
    std::map<int, std::deque<ReadAction>> pending;
    std::string supplied;
    std::vector<int> closed;
    std::size_t calls = 0;
    std::size_t write_limit = 4096;
    int next_write_error = 0;
    int next_poll_error = 0;
    bool close_ok = true;
    bool throw_read = false;
    PipePoll poll(pollfd* fds, std::size_t count, int timeout)
    {
        ++calls;
        require(timeout >= 0 && timeout <= 10, "unbounded production poll");
        if (next_poll_error != 0) {
            const int error = next_poll_error;
            next_poll_error = 0;
            return {-1, error};
        }
        int ready = 0;
        for (std::size_t index = 0; index < count; ++index) {
            if (fds[index].fd >= 0) {
                fds[index].revents = fds[index].events;
                ++ready;
            }
        }
        return {ready, 0};
    }
    PipeTransfer read(int fd, void* buffer, std::size_t maximum)
    {
        ++calls;
        if (throw_read) throw std::runtime_error("injected read exception");
        auto& queue = pending[fd];
        if (queue.empty()) return {-1, EAGAIN};
        auto& action = queue.front();
        if (action.error != 0) {
            const int error = action.error;
            queue.pop_front();
            return {-1, error};
        }
        const std::size_t count = std::min(maximum, action.bytes.size());
        std::memcpy(buffer, action.bytes.data(), count);
        const auto reported_count = action.reported_count;
        action.bytes.erase(0, count);
        if (action.bytes.empty()) queue.pop_front();
        return {reported_count.value_or(static_cast<ssize_t>(count)), 0};
    }
    PipeTransfer write(int, const void* bytes, std::size_t maximum)
    {
        ++calls;
        require(maximum <= 8192, "production input write lost its round cap");
        if (next_write_error != 0) {
            const int error = next_write_error;
            next_write_error = 0;
            return {-1, error};
        }
        const std::size_t count = std::min(maximum, write_limit);
        supplied.append(static_cast<const char*>(bytes), count);
        return {static_cast<ssize_t>(count), 0};
    }
    bool close(int& fd)
    {
        closed.push_back(fd);
        fd = -1;
        return close_ok;
    }
};

struct Fixture {
    int input = 3, output = 4, error = 5, exec = 6;
    ProcessRequest request;
    ProcessResult result;
    FakePipes operations;
    PosixProcessPump<FakePipes> pump;
    Fixture() : pump(operations, input, output, error, exec, request, result) {}
    void exec_success()
    {
        operations.pending[6].push_back({""});
        require(pump.step(0) && pump.exec_ready(), "empty closed exec status must admit exec");
    }
};

void fairness()
{
    Fixture f;
    f.request.standard_input.assign(100000, 'i');
    f.operations.pending[4].push_back({std::string(40000, 'o')});
    f.operations.pending[5].push_back({std::string(40000, 'e')});
    f.exec_success();
    for (int round = 0; round < 3; ++round) {
        const auto before = f.operations.calls;
        const auto out = f.result.standard_output.size();
        const auto err = f.result.standard_error.size();
        f.operations.next_write_error = EAGAIN;
        require(f.pump.step(10), "backpressure must return to the supervisor");
        require(f.operations.calls - before <= 5, "busy pipe starved the supervisor round");
        require(f.result.standard_output.size() > out && f.result.standard_error.size() > err,
            "input backpressure prevented concurrent output progress");
    }
    require(f.operations.supplied.empty(), "EAGAIN cannot claim input was accepted");
    for (int round = 0; round < 25; ++round)
        require(f.pump.step(0), "bounded input continuation failed");
    require(f.operations.supplied == f.request.standard_input && f.input < 0,
        "partial input writes lost bytes or failed to close stdin");
}

void malformed_exec()
{
    Fixture f;
    f.operations.pending[6].push_back({std::string(1, 'x')});
    require(f.pump.step(0) && !f.pump.exec_ready(), "partial status cannot announce a start");
    f.operations.pending[6].push_back({""});
    require(!f.pump.step(0) && f.pump.exec_failed(), "partial EOF must fail instead of successful exec");
    Fixture full;
    const int error = ENOENT;
    full.operations.pending[6].push_back({std::string(reinterpret_cast<const char*>(&error), sizeof(error))});
    require(!full.pump.step(0) && full.pump.exec_failed() && !full.pump.exec_ready(),
        "child setup failure was reported as started");

    Fixture oversized;
    oversized.operations.pending[6].push_back(
        {"", 0, static_cast<ssize_t>(sizeof(int) + 1U)});
    const auto calls_before = oversized.operations.calls;
    require(!oversized.pump.observe_exec_status() && oversized.pump.exec_failed() &&
        !oversized.pump.exec_ready() && oversized.pump.reliable_exec_error() == 0,
        "oversized exec status adapter result was admitted or treated as errno");
    require(oversized.operations.calls == calls_before + 1 &&
        oversized.pump.error().find("requested frame remainder") != std::string::npos,
        "oversized exec status result advanced or retried the bounded read");

    Fixture continued;
    const int continued_error = EACCES;
    const std::string frame(
        reinterpret_cast<const char*>(&continued_error), sizeof(continued_error));
    continued.operations.pending[6].push_back({frame.substr(0, 1)});
    require(continued.pump.observe_exec_status() && !continued.pump.exec_ready() &&
        !continued.pump.exec_failed(), "partial direct observation was not retained");
    continued.operations.pending[6].push_back({frame.substr(1)});
    require(!continued.pump.observe_exec_status() && continued.pump.exec_failed() &&
        continued.pump.reliable_exec_error() == EACCES,
        "bounded second direct observation lost the exact errno frame");
}

void limits_and_refusals()
{
    Fixture f;
    f.request.standard_input = "input";
    f.request.maximum_standard_output = 3;
    f.request.maximum_standard_error = 2;
    f.exec_success();
    f.operations.pending[4].push_back({"abcXYZ"});
    f.operations.pending[5].push_back({"efQ"});
    require(f.pump.step(0) && f.pump.overflow(), "actual over-limit bytes were not attributed");
    require(f.result.standard_output == "abc" && f.result.standard_error == "ef",
        "stream capture did not preserve exact bounded prefixes");

    Fixture interrupted;
    interrupted.operations.next_poll_error = EINTR;
    const auto before = interrupted.operations.calls;
    require(interrupted.pump.step(10), "poll EINTR should return to the deadline owner");
    require(interrupted.operations.calls == before + 1, "poll EINTR loop became unbounded");
    interrupted.operations.next_poll_error = EBADF;
    require(!interrupted.pump.step(0), "poll failure was ignored");

    Fixture closed;
    closed.request.standard_input = "unused";
    closed.exec_success();
    closed.operations.next_write_error = EPIPE;
    require(closed.pump.step(0) && closed.input < 0, "deliberately closed child stdin was not handled");

    Fixture read_error;
    read_error.operations.pending[4].push_back({"", EIO});
    require(!read_error.pump.step(0), "output I/O failure was silently accepted");

    Fixture bad_close;
    bad_close.operations.close_ok = false;
    require(!bad_close.pump.step(0), "uncertain descriptor close must not claim success");
}

struct SocketProbe {
    bool create_ok = true, option_ok = true;
    int option_calls = 0, last_flags = -1;
    bool socket_pair(int (&pair)[2]) { pair[0] = 20; pair[1] = 21; return create_ok; }
    bool no_sigpipe(int fd) { require(fd == 21, "option applied to wrong sender"); ++option_calls; return option_ok; }
    PipeTransfer send(int fd, const void*, std::size_t, int flags) {
        require(fd == 21, "send used foreign socket"); last_flags = flags; return {-1, EPIPE};
    }
};
struct CloseProbe {
    std::vector<int> calls;
    int failure = 0;
    int close_inherited(int fd) {
        calls.push_back(fd);
        if (fd == 5 && failure) return failure;
        return fd == 4 ? EBADF : 0;
    }
};
void socket_and_close_controls()
{
    SocketProbe probe; int pair[2] {-1, -1};
    require(create_stdin_socket(probe, pair, true) && probe.option_calls == 1,
        "checked Apple socket-local suppression not requested");
    probe.option_ok = false;
    require(!create_stdin_socket(probe, pair, true), "failed socket option must refuse before fork");
    require(create_stdin_socket(probe, pair, false), "Linux per-send admission failed");
    const auto sent = send_stdin_socket(probe, pair[1], "x", 1);
    require(sent.error == EPIPE, "suppressed SIGPIPE must preserve EPIPE");
#ifdef __APPLE__
    require(probe.last_flags == 0, "Apple send uses checked socket option");
#else
    require(probe.last_flags == MSG_NOSIGNAL, "Linux send must be per-call signal-safe");
#endif
    for (const int error : {EINTR, EIO}) {
        CloseProbe close; close.failure = error;
        require(close_inherited_descriptors(close, 8, 6) == error,
            "uncertain inherited close did not refuse exec");
        require(close.calls == std::vector<int>({3,4,5}),
            "uncertain close retried or dispatch continued");
    }
    CloseProbe close;
    require(close_inherited_descriptors(close, 8, 6) == 0 &&
        close.calls == std::vector<int>({3,4,5,7}), "EBADF/exec-status preservation control");
}

void post_fork_controls()
{
    const ProcessIdentity identity {45, "fixture", "fixture-start"};
    for (const auto reason : {ProcessTermination::cancelled, ProcessTermination::timed_out,
                             ProcessTermination::output_limit}) {
        for (const bool announced : {false, true}) {
            ProcessResult result; PosixProcessOutcome outcome(result); ProcessRequest request;
            if (announced) require(outcome.announce(true, request, identity), "no-op notification after exec");
            outcome.reason(reason, "requested stop");
            require(result.termination == (announced ? reason : ProcessTermination::pending),
                "unannounced post-fork reason laundered no-effects authority");
            outcome.finish(0, false, reason == ProcessTermination::output_limit, 0);
            require(result.termination == (announced ? reason : ProcessTermination::pending),
                "final overflow assignment erased pending");
        }
    }
    ProcessResult denied; PosixProcessOutcome not_started(denied); ProcessRequest request;
    bool called = false;
    request.started = [&](const ProcessIdentity&) { called = true; };
    require(!not_started.announce(false, request, identity) && !called,
        "missing exec proof must not announce or type a result");
    request.started = [&](const ProcessIdentity&) {
        require(denied.termination == ProcessTermination::pending, "start callback ran after typed authority");
        throw std::runtime_error("started failure");
    };
    require(!not_started.announce(true, request, identity), "throwing start callback counted as returned");
    not_started.finish(0, true, true, 0);
    require(denied.termination == ProcessTermination::pending && !denied.error.empty(),
        "started callback exception lost effects uncertainty");

    for (const bool announced : {false, true}) {
        Fixture fixture; PosixProcessOutcome outcome(fixture.result); ProcessRequest notification;
        if (announced) require(outcome.announce(true, notification, identity), "announced control");
        fixture.request.cancellation_requested = []() -> bool { throw 41; };
        require(outcome.cancelled(fixture.request) && fixture.result.termination == ProcessTermination::pending,
            "cancellation callback exception must remain uncertain");
        fixture.operations.next_poll_error = EBADF;
        require(!outcome.step(fixture.pump, 0), "actual pump poll error ignored");
        outcome.finish(0, true, true, 0);
        require(fixture.result.termination == ProcessTermination::pending, "poll error finalized as completed");
    }
    for (const bool throws : {false, true}) {
        Fixture fixture; PosixProcessOutcome outcome(fixture.result); ProcessRequest notification;
        require(outcome.announce(true, notification, identity), "drain control announced");
        outcome.reason(ProcessTermination::timed_out, "deadline");
        fixture.operations.throw_read = throws;
        if (!throws) fixture.operations.pending[4].push_back({"", EIO});
        require(!outcome.step(fixture.pump, 0, false), "actual drain error was ignored");
        outcome.finish(0, true, true, 0);
        require(fixture.result.termination == ProcessTermination::pending, "later drain failure lost pending");
    }
    for (const int number : {ENOENT, 0, -1}) {
        for (const int exit_code : {126,127,0}) {
            Fixture fixture; PosixProcessOutcome outcome(fixture.result);
            fixture.operations.pending[6].push_back(
                {std::string(reinterpret_cast<const char*>(&number), sizeof(number))});
            require(!outcome.step(fixture.pump, 0), "full exec error frame expected refusal");
            outcome.finish(exit_code << 8, false, false, fixture.pump.reliable_exec_error());
            const bool known = number > 0 && (exit_code == 126 || exit_code == 127);
            require(fixture.result.termination == (known ? ProcessTermination::start_failed : ProcessTermination::pending),
                "only positive complete frame plus reaped126/127 proves start failure");
        }
    }
    Fixture partial; PosixProcessOutcome partial_outcome(partial.result);
    partial.operations.pending[6].push_back({std::string(1, 'x')});
    require(partial_outcome.step(partial.pump, 0), "partial frame first round");
    partial.operations.pending[6].push_back({""});
    require(!partial_outcome.step(partial.pump, 0), "partial frame EOF must refuse");
    partial_outcome.finish(126 << 8, false, false, partial.pump.reliable_exec_error());
    require(partial.result.termination == ProcessTermination::pending, "partial frame cannot prove pre-exec");
    ProcessResult completed; PosixProcessOutcome success(completed); ProcessRequest no_callback;
    require(success.announce(true, no_callback, identity), "optional callback no-op control");
    success.finish(0, true, false, 0);
    require(completed.termination == ProcessTermination::exited && completed.exit_code == 0,
        "known announced completion regression");
    success.uncertain("late cleanup observation");
    success.finish(std::nullopt, true, true, 0);
    require(completed.termination == ProcessTermination::pending && completed.native_status == -1,
        "uncertain missing status cannot retain typed success");
}

void cancellation_exec_status_observation()
{
    for (const bool exec_confirmed : {false, true}) {
        Fixture fixture;
        fixture.request.cancellation_requested = []() { return true; };
        if (exec_confirmed) fixture.operations.pending[6].push_back({""});
        PosixProcessOutcome outcome(fixture.result);
        const auto calls_before = fixture.operations.calls;
        require(outcome.observe_exec_status(fixture.pump),
            "bounded exec-status observation failed");
        require(fixture.operations.calls == calls_before + 1,
            "exec-status observation waited or advanced another endpoint");
        if (fixture.pump.exec_ready()) {
            require(outcome.announce(true, fixture.request,
                ProcessIdentity {45, "fixture", "fixture-start"}),
                "confirmed exec was not announced before cancellation");
        }
        require(outcome.cancelled(fixture.request), "cancellation was not observed");
        require(fixture.result.termination == (exec_confirmed
                ? ProcessTermination::cancelled
                : ProcessTermination::pending) &&
            (fixture.result.identity.process_id != 0) == exec_confirmed,
            "pre-exec cancellation was confused with confirmed dispatch");
    }

    Fixture failed;
    const int exec_error = ENOENT;
    failed.operations.pending[6].push_back(
        {std::string(reinterpret_cast<const char*>(&exec_error), sizeof(exec_error))});
    PosixProcessOutcome failed_outcome(failed.result);
    require(!failed_outcome.observe_exec_status(failed.pump),
        "exec failure frame was treated as a successful observation");
    failed_outcome.finish(126 << 8, false, false, failed.pump.reliable_exec_error());
    require(failed.result.termination == ProcessTermination::start_failed &&
        failed.result.identity.process_id == 0,
        "reliable exec failure was relabelled as post-dispatch cancellation");
}

struct InterruptedWait {
    int consumes = 0, signals = 0;
    bool always = true;
    SignalDisposition disposition() { return {}; }
    ChildPoll observe(pid_t child, int options) {
        require((options & WNOWAIT) != 0, "test consumed during observation");
        ChildPoll result; result.info.si_pid = child; result.info.si_code = CLD_EXITED; return result;
    }
    ChildWait consume(pid_t child) {
        // This deterministic guard makes the original infinite loop fail the
        // assertion instead of hanging the test executable.
        if (++consumes > 33) throw std::runtime_error("unbounded consume");
        return always || consumes == 1 ? ChildWait {-1,EINTR,0} : ChildWait {child,0,0};
    }
    ChildSignal signal(pid_t, int) { ++signals; return {0,0,false,false}; }
    std::chrono::steady_clock::time_point now() { return {}; }
    void pause(std::chrono::milliseconds) {}
};
void finite_reap_control()
{
    InterruptedWait operations;
    PosixChildLifecycle<InterruptedWait> child(45, true, operations);
    require(child.observe() == ChildObservation::terminal, "unreaped terminal admission");
    require(!child.reap() && operations.consumes == 32 && child.reaping_started() &&
        child.phase() == ChildPhase::ownership_unknown && !child.status(),
        "always-EINTR must exhaust finite budget with permanently unknown status");
    bool requested = false; child.terminate(std::chrono::milliseconds(0), requested);
    require(!child.reap() && operations.consumes == 32 && operations.signals == 0,
        "EINTR exhaustion reacquired a numeric child/group");
    InterruptedWait once; once.always = false;
    PosixChildLifecycle<InterruptedWait> retry(46, true, once);
    require(retry.observe() == ChildObservation::terminal && retry.reap() &&
        once.consumes == 2 && retry.status().has_value(), "single EINTR retry positive control");
}

struct BoundaryClock : InterruptedWait {
    using Clock = std::chrono::steady_clock;
    Clock::time_point value {};
    Clock::time_point now() const { return value; }
    void pause(std::chrono::milliseconds) { value = Clock::time_point::max(); }
};
void deadline_range_controls()
{
    using Clock = std::chrono::steady_clock;
    for (const auto grace : {std::chrono::milliseconds(-1), std::chrono::milliseconds::max(),
                            std::chrono::milliseconds(2)}) {
        BoundaryClock ops; ops.value = Clock::time_point::max() - std::chrono::milliseconds(1);
        PosixChildLifecycle<BoundaryClock> child(45, true, ops); bool requested = false;
        child.terminate(grace, requested);
        require(ops.signals == 0 && !requested && !child.error().empty() && !child.reaping_started(),
            "out-of-range actual deadline must refuse before signal and consuming wait");
    }
    BoundaryClock boundary;
    boundary.value = Clock::time_point::max() - std::chrono::milliseconds(2);
    PosixChildLifecycle<BoundaryClock> exact(45, true, boundary); bool requested = false;
    exact.terminate(std::chrono::milliseconds(2), requested);
    require(boundary.signals == 3 && requested && exact.error().empty(),
        "exactly representable deadline should retain TERM/probe/KILL ordering");
    BoundaryClock zero; zero.value = Clock::time_point::max();
    PosixChildLifecycle<BoundaryClock> immediate(45, true, zero); requested = false;
    immediate.terminate(std::chrono::milliseconds(0), requested);
    require(zero.signals == 2 && requested && immediate.error().empty(), "zero grace at maximum clock is representable");
}

#ifndef _WIN32
// Explicit opt-in for a later reviewed native run. This opens only anonymous
// AF_UNIX socketpairs; it does not fork, alter signals or contact a network.
struct NativeSocketProbe {
    bool socket_pair(int (&pair)[2]) { return ::socketpair(AF_UNIX, SOCK_STREAM, 0, pair) == 0; }
    bool no_sigpipe(int fd) {
#ifdef __APPLE__
        int enabled = 1;
        return ::setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &enabled, sizeof(enabled)) == 0;
#else
        (void)fd; return false;
#endif
    }
    PipeTransfer send(int fd, const void* data, std::size_t size, int flags) {
        const auto count = ::send(fd, data, size, flags);
        return {count, count < 0 ? errno : 0};
    }
};
struct SocketOwner {
    int pair[2] {-1,-1};
    ~SocketOwner() { for (int fd : pair) if (fd >= 0) (void)::close(fd); }
    void close_sender() {
        const int fd = pair[1]; pair[1] = -1;
        require(::close(fd) == 0, "native sender closure uncertain");
    }
};
void native_socket_controls()
{
    struct sigaction action_before {}, action_after {};
    sigset_t mask_before {}, mask_after {}, pending_before {}, pending_after {};
    require(::sigaction(SIGPIPE, nullptr, &action_before) == 0 &&
        ::sigprocmask(SIG_SETMASK, nullptr, &mask_before) == 0 &&
        ::sigpending(&pending_before) == 0, "signal observation before socket controls");
    NativeSocketProbe ops; SocketOwner sockets;
#ifdef __APPLE__
    constexpr bool option = true;
#else
    constexpr bool option = false;
#endif
    require(create_stdin_socket(ops, sockets.pair, option), "native local socket admission");
    for (int fd : sockets.pair) {
        const int flags = ::fcntl(fd, F_GETFL);
        require(flags >= 0 && ::fcntl(fd, F_SETFL, flags | O_NONBLOCK) == 0, "native nonblocking setup");
    }
    const int small = 4096;
    require(::setsockopt(sockets.pair[1], SOL_SOCKET, SO_SNDBUF, &small, sizeof(small)) == 0,
        "bounded socket buffer setup");
    const std::string bytes(4096, 's'); std::size_t sent = 0; bool blocked = false;
    for (int attempt = 0; attempt < 1024; ++attempt) {
        const auto result = send_stdin_socket(ops, sockets.pair[1], bytes.data(), bytes.size());
        if (result.count > 0) sent += static_cast<std::size_t>(result.count);
        else if (result.error == EAGAIN || result.error == EWOULDBLOCK) { blocked = true; break; }
        else require(false, "unexpected native send error");
    }
    require(blocked && sent > 0, "bounded native backpressure was not observed");
    sockets.close_sender();
    std::size_t received = 0; bool eof = false;
    for (int attempt = 0; attempt < 2048; ++attempt) {
        char buffer[4096];
        const auto count = ::recv(sockets.pair[0], buffer, sizeof(buffer), 0);
        if (count == 0) { eof = true; break; }
        require(count > 0, "native EOF drain refused or exceeded its available stream");
        require(std::all_of(buffer, buffer + count, [](char byte) { return byte == 's'; }),
            "native stream bytes changed");
        received += static_cast<std::size_t>(count);
    }
    require(eof && received == sent, "sender close lost stream bytes or failed EOF");
    SocketOwner broken; require(create_stdin_socket(ops, broken.pair, option), "EPIPE pair admission");
    const int reader = broken.pair[0]; broken.pair[0] = -1;
    require(::close(reader) == 0, "EPIPE peer close");
    const auto result = send_stdin_socket(ops, broken.pair[1], "x", 1);
    require(result.count == -1 && result.error == EPIPE, "closed peer must report EPIPE without SIGPIPE");
    require(::sigaction(SIGPIPE, nullptr, &action_after) == 0 &&
        ::sigprocmask(SIG_SETMASK, nullptr, &mask_after) == 0 &&
        ::sigpending(&pending_after) == 0, "signal observation after socket controls");
    require(action_before.sa_handler == action_after.sa_handler &&
        action_before.sa_flags == action_after.sa_flags, "SIGPIPE disposition changed");
    for (int number = 1; number < NSIG; ++number)
        require(sigismember(&mask_before, number) == sigismember(&mask_after, number) &&
            sigismember(&pending_before, number) == sigismember(&pending_after, number) &&
            sigismember(&action_before.sa_mask, number) == sigismember(&action_after.sa_mask, number),
            "caller signal mask/pending/disposition mask changed");
}
#endif
} // namespace

int main(int argc, char** argv)
{
    try {
        if (argc == 2 && std::string(argv[1]) == "--native-sockets") {
            native_socket_controls();
            std::cout << "Native anonymous socket controls passed\n";
            return 0;
        }
        require(argc == 1, "unknown test mode");
        socket_and_close_controls();
        post_fork_controls();
        cancellation_exec_status_observation();
        finite_reap_control();
        deadline_range_controls();
        fairness();
        malformed_exec();
        limits_and_refusals();
        std::cout << "POSIX production nonblocking pump injected checks passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
