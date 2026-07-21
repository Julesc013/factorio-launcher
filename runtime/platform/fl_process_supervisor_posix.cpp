// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_process_supervisor.h"
#include "fl_file_io.h"

#include <algorithm>
#include <atomic>
#include <cerrno>
#include <csignal>
#include <cstring>
#include <fcntl.h>
#include <limits>
#include <pthread.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <thread>
#include <unistd.h>

extern char** environ;

namespace facman::platform {
namespace {

class ScopedSigpipeBlock {
public:
    ScopedSigpipeBlock()
    {
        sigemptyset(&set_);
        sigaddset(&set_, SIGPIPE);
        active_ = pthread_sigmask(SIG_BLOCK, &set_, &previous_) == 0;
    }
    ~ScopedSigpipeBlock()
    {
        if (!active_) return;
        if (sigismember(&previous_, SIGPIPE) == 0) {
            sigset_t pending {};
            if (sigpending(&pending) == 0 && sigismember(&pending, SIGPIPE) == 1) {
                int received = 0;
                (void)sigwait(&set_, &received);
            }
        }
        (void)pthread_sigmask(SIG_SETMASK, &previous_, nullptr);
    }

private:
    sigset_t set_ {};
    sigset_t previous_ {};
    bool active_ = false;
};

void close_fd(int& value) noexcept { if (value >= 0) close(value); value = -1; }

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

void read_bounded(int descriptor, std::string& output, std::size_t maximum, std::atomic<bool>& overflow)
{
    char buffer[8192];
    for (;;) {
        const ssize_t count = read(descriptor, buffer, sizeof(buffer));
        if (count > 0) {
            const std::size_t size = static_cast<std::size_t>(count);
            const std::size_t available = output.size() < maximum ? maximum - output.size() : 0;
            output.append(buffer, std::min(size, available));
            if (size > available) overflow.store(true, std::memory_order_release);
        } else if (count == 0) break;
        else if (errno != EINTR) break;
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

void terminate_group(pid_t child, std::chrono::milliseconds grace, bool& process_tree_terminated)
{
    if (kill(-child, SIGTERM) == 0) process_tree_terminated = true;
    const auto deadline = std::chrono::steady_clock::now() + grace;
    while (std::chrono::steady_clock::now() < deadline) {
        if (kill(-child, 0) != 0 && errno == ESRCH) return;
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    if (kill(-child, SIGKILL) == 0) process_tree_terminated = true;
}

} // namespace

ProcessResult supervise_process(const ProcessRequest& request)
{
    ProcessResult result;
    result.termination = ProcessTermination::start_failed;
    if (request.executable.empty() || request.timeout.count() <= 0) {
        result.error = "process request requires an executable and positive timeout";
        return result;
    }
    int input[2] {-1, -1};
    int output[2] {-1, -1};
    int error[2] {-1, -1};
    int exec_status[2] {-1, -1};
    if (pipe(input) != 0 || pipe(output) != 0 || pipe(error) != 0 || pipe(exec_status) != 0) {
        close_fd(input[0]); close_fd(input[1]); close_fd(output[0]); close_fd(output[1]);
        close_fd(error[0]); close_fd(error[1]); close_fd(exec_status[0]); close_fd(exec_status[1]);
        result.error = "pipe failed";
        return result;
    }
    (void)fcntl(exec_status[1], F_SETFD, FD_CLOEXEC);

    std::vector<std::string> argument_storage;
    argument_storage.push_back(path_to_utf8(request.executable));
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

    const pid_t child = fork();
    if (child == 0) {
        (void)setpgid(0, 0);
        close_fd(exec_status[0]);
        if (!working_directory.empty() && chdir(working_directory.c_str()) != 0) {
            const int child_error = errno;
            write_exec_error(exec_status[1], child_error);
            _exit(126);
        }
        (void)dup2(input[0], STDIN_FILENO);
        (void)dup2(output[1], STDOUT_FILENO);
        (void)dup2(error[1], STDERR_FILENO);
        close_fd(input[0]); close_fd(input[1]); close_fd(output[0]); close_fd(output[1]);
        close_fd(error[0]); close_fd(error[1]);
        long maximum = sysconf(_SC_OPEN_MAX);
        if (maximum < 0 || maximum > 65536) maximum = 65536;
        for (int descriptor = 3; descriptor < maximum; ++descriptor) {
            if (descriptor != exec_status[1]) close(descriptor);
        }
        execve(executable.c_str(), arguments.data(), environment_values.data());
        const int child_error = errno;
        write_exec_error(exec_status[1], child_error);
        _exit(127);
    }
    if (child < 0) {
        result.error = "fork failed";
        close_fd(input[0]); close_fd(input[1]); close_fd(output[0]); close_fd(output[1]);
        close_fd(error[0]); close_fd(error[1]); close_fd(exec_status[0]); close_fd(exec_status[1]);
        return result;
    }
    (void)setpgid(child, child);
    close_fd(exec_status[1]);
    int child_error = 0;
    ssize_t exec_read = -1;
    do { exec_read = read(exec_status[0], &child_error, sizeof(child_error)); } while (exec_read < 0 && errno == EINTR);
    close_fd(exec_status[0]);
    if (exec_read > 0) {
        int status = 0;
        while (waitpid(child, &status, 0) < 0 && errno == EINTR) {}
        close_fd(input[0]); close_fd(input[1]); close_fd(output[0]); close_fd(output[1]);
        close_fd(error[0]); close_fd(error[1]);
        result.error = "execve failed: " + std::string(std::strerror(child_error));
        return result;
    }

    close_fd(input[0]); close_fd(output[1]); close_fd(error[1]);
    result.identity = {static_cast<std::uint64_t>(child), "posix-pid"};
    if (request.started) request.started(result.identity);
    {
        ScopedSigpipeBlock sigpipe;
        std::size_t offset = 0;
        while (offset < request.standard_input.size()) {
            const ssize_t count = write(input[1], request.standard_input.data() + offset,
                request.standard_input.size() - offset);
            if (count > 0) offset += static_cast<std::size_t>(count);
            else if (count < 0 && errno != EINTR) break;
        }
    }
    close_fd(input[1]);

    std::atomic<bool> overflow {false};
    std::thread output_reader(read_bounded, output[0], std::ref(result.standard_output),
        request.maximum_standard_output, std::ref(overflow));
    std::thread error_reader(read_bounded, error[0], std::ref(result.standard_error),
        request.maximum_standard_error, std::ref(overflow));
    const auto deadline = std::chrono::steady_clock::now() + request.timeout;
    int status = 0;
    bool primary_exited = false;
    for (;;) {
        const pid_t waited = waitpid(child, &status, WNOHANG);
        if (waited == child) { primary_exited = true; break; }
        if (waited < 0 && errno != EINTR) { result.error = "waitpid failed"; break; }
        if (request.cancellation_requested && request.cancellation_requested()) {
            result.termination = ProcessTermination::cancelled;
        } else if (std::chrono::steady_clock::now() >= deadline) {
            result.termination = ProcessTermination::timed_out;
        } else if (overflow.load(std::memory_order_acquire)) {
            result.termination = ProcessTermination::output_limit;
        } else {
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            continue;
        }
        terminate_group(child, request.termination_grace_period, result.process_tree_terminated);
        while (waitpid(child, &status, 0) < 0 && errno == EINTR) {}
        break;
    }
    if (primary_exited) terminate_group(child, std::chrono::milliseconds(0), result.process_tree_terminated);
    output_reader.join();
    error_reader.join();
    close_fd(output[0]); close_fd(error[0]);
    result.native_status = status;
    if (WIFEXITED(status)) {
        result.exit_code = WEXITSTATUS(status);
        if (primary_exited) result.termination = ProcessTermination::exited;
    } else if (WIFSIGNALED(status)) {
        result.exit_code = 128 + WTERMSIG(status);
        if (primary_exited) result.termination = ProcessTermination::crashed;
    }
    if (primary_exited && overflow.load(std::memory_order_acquire)) {
        // The reader can observe the limit after the process has exited but
        // before its pipe is drained. Preserve the safety outcome instead of
        // reporting that a process with truncated output completed cleanly.
        result.termination = ProcessTermination::output_limit;
    }
    return result;
}

bool process_identity_alive(std::uint64_t process_id) noexcept
{
    if (process_id == 0 || process_id > static_cast<std::uint64_t>(std::numeric_limits<pid_t>::max())) return false;
    const int status = kill(static_cast<pid_t>(process_id), 0);
    return status == 0 || errno == EPERM;
}

} // namespace facman::platform
