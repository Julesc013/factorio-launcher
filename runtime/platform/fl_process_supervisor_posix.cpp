// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_process_supervisor.h"
#include "fl_process_supervisor_posix_lifecycle.h"
#include "fl_process_supervisor_posix_pump.h"
#include "fl_file_io.h"

#include <algorithm>
#include <cerrno>
#include <csignal>
#include <cstring>
#include <fcntl.h>
#include <fstream>
#include <limits>
#include <sys/socket.h>
#ifdef __APPLE__
#include <sys/proc.h>
#include <sys/sysctl.h>
#endif
#include <sstream>
#include <sys/types.h>
#include <sys/wait.h>
#include <thread>
#include <unistd.h>

extern char** environ;

namespace facman::platform {
namespace {

void write_exec_error(int descriptor, int child_error) noexcept
{
    const auto* bytes = reinterpret_cast<const unsigned char*>(&child_error);
    std::size_t offset = 0;
    while (offset < sizeof(child_error)) {
        const ssize_t count = write(descriptor, bytes + offset, sizeof(child_error) - offset);
        if (count > 0) {
            offset += static_cast<std::size_t>(count);
        } else if (count < 0 && errno == EINTR) {
            continue;
        } else {
            break;
        }
    }
}

std::vector<std::string> environment(const ProcessRequest& request)
{
    std::vector<std::string> output;
    if (request.inherit_environment) {
        for (char** item = environ; item != nullptr && *item != nullptr; ++item) output.emplace_back(*item);
    }
    for (const ProcessEnvironmentEntry& entry : request.environment) {
        const std::string prefix = entry.name + "=";
        output.erase(std::remove_if(output.begin(), output.end(), [&](const std::string& current) {
            return current.rfind(prefix, 0) == 0;
        }), output.end());
        output.push_back(prefix + entry.value);
    }
    return output;
}

struct NativeChildOperations {
    detail::SignalDisposition disposition() const
    {
        detail::SignalDisposition result;
        if (sigaction(SIGCHLD, nullptr, &result.action) != 0) result.error = errno;
        return result;
    }
    detail::ChildPoll observe(pid_t child, int options) const
    {
        detail::ChildPoll result; // Zero siginfo: si_pid == 0 means no pending status.
        if (waitid(P_PID, static_cast<id_t>(child), &result.info, options) != 0)
            result.error = errno;
        return result;
    }
    detail::ChildWait consume(pid_t child) const
    {
        detail::ChildWait result;
        result.process = waitpid(child, &result.status, WNOHANG);
        if (result.process < 0) result.error = errno;
        return result;
    }
    detail::ChildSignal signal(pid_t target, int number) const
    {
        detail::ChildSignal result;
        result.result = kill(target, number);
        if (result.result != 0) result.error = errno;
        return result;
    }
    detail::ChildGroupSnapshot observe_group(pid_t group) const
    {
        detail::ChildGroupSnapshot result;
#ifdef __APPLE__
        if (group > 0) {
            int query[4] {CTL_KERN, KERN_PROC, KERN_PROC_PGRP, group};
            std::size_t required = 0;
            if (sysctl(query, 4, nullptr, &required, nullptr, 0) == 0 &&
                required <= std::numeric_limits<std::size_t>::max() -
                    2U * sizeof(kinfo_proc)) {
                // Always make a second query, including after a zero-size
                // estimate. This binds the decision to returned rows and leaves
                // room to detect a small process-count race without truncation.
                const std::size_t count = required / sizeof(kinfo_proc) + 2U;
                std::vector<kinfo_proc> processes(count);
                std::size_t received = processes.size() * sizeof(kinfo_proc);
                if (sysctl(query, 4, processes.data(), &received, nullptr, 0) == 0 &&
                    received <= processes.size() * sizeof(kinfo_proc) &&
                    received % sizeof(kinfo_proc) == 0) {
                    const std::size_t returned = received / sizeof(kinfo_proc);
                    std::vector<detail::ChildGroupSnapshotRow> rows;
                    rows.reserve(returned);
                    for (std::size_t index = 0; index < returned; ++index) {
                        const auto& process = processes[index];
                        rows.push_back({process.kp_proc.p_pid, process.kp_eproc.e_pgid,
                            process.kp_proc.p_stat == SZOMB});
                    }
                    const auto snapshot = detail::classify_child_group_snapshot(
                        group, rows.data(), rows.size());
                    result = snapshot;
                }
            }
        }
#else
        (void)group;
#endif
        return result;
    }
    std::chrono::steady_clock::time_point now() const { return std::chrono::steady_clock::now(); }
    void pause(std::chrono::milliseconds duration) const { std::this_thread::sleep_for(duration); }
};


bool checked_close(int& descriptor) noexcept
{
    if (descriptor < 0) return true;
    const int owned = descriptor;
    descriptor = -1; // Never retry close on a potentially recycled descriptor.
    return ::close(owned) == 0;
}

struct NativeSocketOperations {
    bool socket_pair(int (&pair)[2]) const noexcept
    {
        return ::socketpair(AF_UNIX, SOCK_STREAM, 0, pair) == 0;
    }
    bool no_sigpipe(int fd) const noexcept
    {
#ifdef __APPLE__
        const int enabled = 1;
        return ::setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &enabled, sizeof(enabled)) == 0;
#else
        (void)fd;
        return false; // Linux admission uses per-send MSG_NOSIGNAL instead.
#endif
    }
    detail::PipeTransfer send(int fd, const void* bytes, std::size_t size, int flags) const noexcept
    {
        const auto count = ::send(fd, bytes, size, flags);
        return {count, count < 0 ? errno : 0};
    }
    int close_inherited(int fd) const noexcept
    {
        return ::close(fd) == 0 ? 0 : errno;
    }
};

struct NativePipeOperations {
    detail::PipeTransfer read(int fd, void* buffer, std::size_t size) const
    {
        const auto count = ::read(fd, buffer, size);
        return {count, count < 0 ? errno : 0};
    }
    detail::PipeTransfer write(int fd, const void* buffer, std::size_t size) const
    {
        NativeSocketOperations sockets;
        return detail::send_stdin_socket(sockets, fd, buffer, size);
    }
    detail::PipePoll poll(pollfd* descriptors, std::size_t count, int timeout) const
    {
        const int ready = ::poll(descriptors, static_cast<nfds_t>(count), timeout);
        return {ready, ready < 0 ? errno : 0};
    }
    bool close(int& fd) const noexcept { return checked_close(fd); }
};

struct ProcessPipes {
    int input[2] {-1, -1};
    int output[2] {-1, -1};
    int error[2] {-1, -1};
    int exec_status[2] {-1, -1};
    ~ProcessPipes() { (void)close_all(); }
    bool close_all() noexcept
    {
        bool ok = true;
        for (auto* pair : {input, output, error, exec_status}) {
            for (int index = 0; index < 2; ++index)
                if (!checked_close(pair[index])) ok = false;
        }
        return ok;
    }
    bool create()
    {
        NativeSocketOperations sockets;
#ifdef __APPLE__
        constexpr bool socket_option_required = true;
#else
        constexpr bool socket_option_required = false;
#endif
        for (auto* pair : {input, output, error, exec_status}) {
            const bool created = pair == input
                ? detail::create_stdin_socket(sockets, input, socket_option_required)
                : ::pipe(pair) == 0;
            if (!created) return false;
            for (int index = 0; index < 2; ++index) {
                // Closed caller standard descriptors must not alias a pipe end.
                if (pair[index] < 3) {
                    const int duplicate = fcntl(pair[index], F_DUPFD_CLOEXEC, 3);
                    if (duplicate < 0) return false;
                    if (!checked_close(pair[index])) {
                        (void)::close(duplicate);
                        return false;
                    }
                    pair[index] = duplicate;
                }
                const int flags = fcntl(pair[index], F_GETFD);
                if (flags < 0 || fcntl(pair[index], F_SETFD, flags | FD_CLOEXEC) != 0)
                    return false;
            }
        }
        for (const int fd : {input[1], output[0], error[0], exec_status[0]}) {
            const int flags = fcntl(fd, F_GETFL);
            if (flags < 0 || fcntl(fd, F_SETFL, flags | O_NONBLOCK) != 0) return false;
        }
        return true;
    }
    bool close_child_endpoints() noexcept
    {
        bool ok = true;
        for (int* fd : {&input[0], &output[1], &error[1], &exec_status[1]})
            if (!checked_close(*fd)) ok = false;
        return ok;
    }
};

void add_error(ProcessResult& result, const std::string& text)
{
    if (text.empty()) return;
    if (!result.error.empty()) result.error += "; ";
    result.error += text;
}

class OwnedChild {
public:
    OwnedChild(pid_t child, bool group, NativeChildOperations& operations,
        ProcessResult& result)
        : lifecycle(child, group, operations), operations_(operations), result_(result) {}
    ~OwnedChild() { shutdown(std::chrono::milliseconds(0)); }

    void shutdown(std::chrono::milliseconds grace) noexcept
    {
        if (closed_) return;
        try {
            lifecycle.terminate(grace, result_.process_tree_terminated);
            if (!lifecycle.error().empty()) uncertain_ = true;
            // A non-consuming observation has to prove termination before reap.
            // This also bounds cleanup when a kill request fails or is delayed.
            const auto deadline = operations_.now() + std::chrono::seconds(1);
            auto state = lifecycle.observe();
            while (state == detail::ChildObservation::running && operations_.now() < deadline) {
                operations_.pause(std::chrono::milliseconds(10));
                state = lifecycle.observe();
            }
            if (state == detail::ChildObservation::terminal) {
                lifecycle.resolve_group_cleanup_until(deadline);
                (void)lifecycle.reap();
            } else {
                uncertain_ = true;
                add_error(result_, "child cleanup did not confirm a terminal wait status");
            }
            if (!lifecycle.status() || !lifecycle.error().empty()) uncertain_ = true;
            add_error(result_, lifecycle.error());
        } catch (...) {
            uncertain_ = true; // Independent of diagnostic allocation.
            // No second consuming wait or signal is allowed after the lifecycle
            // latch. Descriptor cleanup is independent and still runs.
            try { add_error(result_, "child cleanup failed; completion is unconfirmed"); }
            catch (...) {}
        }
        closed_ = true;
    }

    bool certain() const { return !uncertain_ && lifecycle.status().has_value(); }
    detail::PosixChildLifecycle<NativeChildOperations> lifecycle;

private:
    NativeChildOperations& operations_;
    ProcessResult& result_;
    bool closed_ = false;
    bool uncertain_ = false;
};

std::string posix_start_identity(pid_t process_id) noexcept
{
#ifdef __linux__
    try {
        std::ifstream input("/proc/" + std::to_string(process_id) + "/stat");
        std::string text;
        std::getline(input, text);
        const std::size_t command_end = text.rfind(')');
        if (!input && text.empty()) return {};
        if (command_end == std::string::npos || command_end + 2U >= text.size()) return {};
        std::istringstream fields(text.substr(command_end + 2U));
        std::string value;
        for (std::size_t index = 0; index <= 19U; ++index) {
            if (!(fields >> value)) return {};
        }
        return "linux-process-v1:" + std::to_string(process_id) + ":" + value;
    } catch (...) {
        return {};
    }
#elif defined(__APPLE__)
    try {
        kinfo_proc process {};
        std::size_t size = sizeof(process);
        int query[4] {CTL_KERN, KERN_PROC, KERN_PROC_PID, process_id};
        if (sysctl(query, 4, &process, &size, nullptr, 0) != 0 ||
            size != sizeof(process) || process.kp_proc.p_pid != process_id) return {};
        return "darwin-process-v1:" + std::to_string(process_id) + ":" +
            std::to_string(process.kp_proc.p_starttime.tv_sec) + ":" +
            std::to_string(process.kp_proc.p_starttime.tv_usec);
    } catch (...) {
        return {};
    }
#else
    (void)process_id;
    return {};
#endif
}

} // namespace

ProcessResult supervise_process(const ProcessRequest& request)
{
    ProcessResult result;
    result.native_status = -1;
    result.termination = ProcessTermination::start_failed;
    bool dispatched = false;
    if (request.validate_before_resume) {
        result.error = "pre-resume process validation is unavailable on this platform";
        return result;
    }
    if (request.executable.empty() || request.timeout.count() <= 0 ||
        request.termination_grace_period.count() < 0) {
        result.error = "process request requires an executable and finite positive timeout";
        return result;
    }
    const auto start = std::chrono::steady_clock::now();
    const auto room = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::time_point::max() - start);
    if (request.timeout >= room || request.termination_grace_period >= room) {
        result.error = "process deadline exceeds the monotonic clock range";
        return result;
    }
    const auto deadline = start + request.timeout;
    try {
        NativeChildOperations child_operations;
        if (!detail::admits_child_waiting(child_operations, result.error)) return result;
        std::vector<std::string> argument_storage {path_to_utf8(request.executable)};
        argument_storage.insert(argument_storage.end(), request.arguments.begin(), request.arguments.end());
        std::vector<char*> arguments;
        for (std::string& item : argument_storage) arguments.push_back(item.data());
        arguments.push_back(nullptr);
        std::vector<std::string> environment_storage = environment(request);
        std::vector<char*> environment_values;
        for (std::string& item : environment_storage) environment_values.push_back(item.data());
        environment_values.push_back(nullptr);
        const std::string executable = path_to_utf8(request.executable);
        const std::string working_directory = path_to_utf8(request.working_directory);
        const long maximum = sysconf(_SC_OPEN_MAX);
        if (maximum < 3 || maximum > std::numeric_limits<int>::max()) {
            result.error = "cannot bound inherited descriptor closure";
            return result;
        }
        ProcessPipes pipes;
        if (!pipes.create()) {
            result.error = "process pipe creation or descriptor flag setup failed";
            return result;
        }
        if (std::chrono::steady_clock::now() >= deadline) {
            result.termination = ProcessTermination::timed_out;
            result.error = "process deadline elapsed before dispatch";
            return result;
        }
        const pid_t child = fork();
        if (child > 0) {
            dispatched = true;
            result.termination = ProcessTermination::pending;
        }
        if (child == 0) {
            if (setpgid(0, 0) != 0 ||
                (!working_directory.empty() && chdir(working_directory.c_str()) != 0) ||
                dup2(pipes.input[0], STDIN_FILENO) < 0 ||
                dup2(pipes.output[1], STDOUT_FILENO) < 0 ||
                dup2(pipes.error[1], STDERR_FILENO) < 0) {
                const int child_error = errno;
                write_exec_error(pipes.exec_status[1], child_error);
                _exit(126);
            }
            NativeSocketOperations sockets;
            const int close_error = detail::close_inherited_descriptors(
                sockets, static_cast<int>(maximum), pipes.exec_status[1]);
            if (close_error != 0) {
                write_exec_error(pipes.exec_status[1], close_error);
                _exit(126);
            }
            execve(executable.c_str(), arguments.data(), environment_values.data());
            const int child_error = errno;
            write_exec_error(pipes.exec_status[1], child_error);
            _exit(127);
        }
        if (child < 0) {
            result.error = "fork failed";
            return result;
        }
        detail::PosixProcessOutcome outcome(result);
        const bool group_established = setpgid(child, child) == 0 || getpgid(child) == child;
        OwnedChild owned(child, group_established, child_operations, result);
        NativePipeOperations pipe_operations;
        detail::PosixProcessPump<NativePipeOperations> pump(pipe_operations,
            pipes.input[1], pipes.output[0], pipes.error[0], pipes.exec_status[0], request, result);
        bool terminal_observed = false;
        const auto announce_if_ready = [&]() {
            if (!pump.exec_ready() || outcome.announced()) return true;
            ProcessIdentity identity {
                static_cast<std::uint64_t>(child),
#ifdef __linux__
                "linux-process-v1",
#elif defined(__APPLE__)
                "darwin-process-v1",
#else
                "posix-pid",
#endif
                posix_start_identity(child)};
            return outcome.announce(true, request, std::move(identity));
        };
        if (!pipes.close_child_endpoints()) {
            outcome.uncertain("parent could not confirm closure of child pipe endpoints");
        } else {
            try {
                for (;;) {
                    if (std::chrono::steady_clock::now() >= deadline) {
                        outcome.reason(ProcessTermination::timed_out, "process deadline elapsed");
                        break;
                    }
                    // Close-on-exec may already prove dispatch when cancellation
                    // races the first ordinary pump round. Observe that one
                    // nonblocking endpoint before typing the cancellation.
                    if (!outcome.observe_exec_status(pump)) break;
                    if (!announce_if_ready()) break;
                    if (outcome.cancelled(request)) break;
                    if (!outcome.step(pump, 10)) break;
                    if (!announce_if_ready()) break;
                    if (pump.overflow()) {
                        outcome.reason(ProcessTermination::output_limit, "process output limit exceeded");
                        break;
                    }
                    const auto state = owned.lifecycle.observe();
                    if (state == detail::ChildObservation::unknown) {
                        outcome.uncertain("child ownership or wait observation is unknown");
                        break;
                    }
                    if (state == detail::ChildObservation::terminal) {
                        if (!pump.exec_ready() && !pump.exec_failed()) continue;
                        terminal_observed = pump.exec_ready() && outcome.announced() && result.error.empty();
                        break;
                    }
                }
            } catch (...) {
                outcome.uncertain("process cancellation callback or pipe processing threw");
            }
        }
        pump.close_input();
        owned.shutdown(terminal_observed ? std::chrono::milliseconds(0) :
            request.termination_grace_period);
        if (!owned.certain()) outcome.uncertain("child cleanup outcome is uncertain");
        // Successful group signal requests do not prove the tree is empty.
        // A bounded drain never reacquires numeric signal authority after reap.
        const auto drain_deadline = std::chrono::steady_clock::now() + std::chrono::seconds(1);
        while (!pump.output_closed() && !pump.overflow() &&
            std::chrono::steady_clock::now() < drain_deadline) {
            if (!outcome.step(pump, 10, false)) break;
        }
        if (pump.has_io_failure()) outcome.uncertain(pump.error());
        else if (!pump.error().empty() && result.error.empty()) outcome.exec_error(pump.error());
        if (!pump.output_closed() && !pump.overflow())
            outcome.uncertain("process output did not close within the drain deadline");
        if (!pipes.close_all()) outcome.uncertain("process descriptor close outcome is uncertain");
        outcome.finish(owned.lifecycle.status(), terminal_observed, pump.overflow(), pump.reliable_exec_error());
    } catch (...) {
        // A post-fork exception cannot reuse a typed earlier reason as proof
        // of no effects. Set pending before any diagnostic allocation.
        if (dispatched) result.termination = ProcessTermination::pending;
        // OwnedChild and ProcessPipes have already performed independent cleanup.
        add_error(result, "process preparation or supervision threw");
    }
    return result;
}

bool process_identity_alive(std::uint64_t process_id) noexcept
{
    if (process_id == 0 || process_id > static_cast<std::uint64_t>(std::numeric_limits<pid_t>::max())) return false;
    const int status = kill(static_cast<pid_t>(process_id), 0);
    return status == 0 || errno == EPERM;
}


bool process_identity_alive(const ProcessIdentity& identity) noexcept
{
    return observe_process_identity(identity) == ProcessIdentityObservation::matching_alive;
}

ProcessIdentityObservation observe_process_identity(const ProcessIdentity& identity) noexcept
{
    if (identity.process_id == 0 ||
        identity.process_id > static_cast<std::uint64_t>(std::numeric_limits<pid_t>::max()) ||
        identity.platform.empty() || identity.stable_start_identity.empty()) {
        return ProcessIdentityObservation::inconclusive;
    }
#ifdef __linux__
    constexpr const char* expected_platform = "linux-process-v1";
#elif defined(__APPLE__)
    constexpr const char* expected_platform = "darwin-process-v1";
#else
    constexpr const char* expected_platform = "posix-pid";
#endif
    const std::string expected_prefix = std::string(expected_platform) + ":" +
        std::to_string(identity.process_id) + ":";
    if (identity.platform != expected_platform ||
        identity.stable_start_identity.rfind(expected_prefix, 0) != 0) {
        return ProcessIdentityObservation::inconclusive;
    }
    const pid_t process_id = static_cast<pid_t>(identity.process_id);
    const int status = kill(process_id, 0);
    if (status != 0 && errno == ESRCH) return ProcessIdentityObservation::not_matching_or_exited;
    if (status != 0 && errno != EPERM) return ProcessIdentityObservation::inconclusive;
    const std::string observed = posix_start_identity(process_id);
    if (observed.empty()) return ProcessIdentityObservation::inconclusive;
    return observed == identity.stable_start_identity
        ? ProcessIdentityObservation::matching_alive
        : ProcessIdentityObservation::not_matching_or_exited;
}

} // namespace facman::platform
