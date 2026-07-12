// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_process.h"

#include <atomic>
#include <cerrno>
#include <csignal>
#include <sys/types.h>
#include <sys/wait.h>
#include <thread>
#include <unistd.h>

namespace facman::client::detail {
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

void read_bounded(int descriptor, std::string& output, std::size_t maximum, std::atomic<bool>& overflow)
{
    char buffer[8192];
    for (;;) {
        const ssize_t count = read(descriptor, buffer, sizeof(buffer));
        if (count > 0) {
            const std::size_t size = static_cast<std::size_t>(count);
            if (output.size() <= maximum && size <= maximum - output.size()) output.append(buffer, size);
            else overflow.store(true, std::memory_order_release);
        } else if (count == 0) break;
        else if (errno != EINTR) break;
    }
}

} // namespace

ProcessResult run_cli_process(const ProcessRequest& request)
{
    ProcessResult result;
    int input[2] {-1, -1};
    int output[2] {-1, -1};
    int error[2] {-1, -1};
    if (pipe(input) != 0 || pipe(output) != 0 || pipe(error) != 0) {
        close_fd(input[0]); close_fd(input[1]); close_fd(output[0]); close_fd(output[1]); close_fd(error[0]); close_fd(error[1]);
        result.error = "pipe failed";
        return result;
    }
    const pid_t child = fork();
    if (child == 0) {
        (void)setpgid(0, 0);
        dup2(input[0], STDIN_FILENO);
        dup2(output[1], STDOUT_FILENO);
        dup2(error[1], STDERR_FILENO);
        close_fd(input[0]); close_fd(input[1]); close_fd(output[0]); close_fd(output[1]); close_fd(error[0]); close_fd(error[1]);
        const std::string executable = request.executable.string();
        execl(executable.c_str(), executable.c_str(), "rpc", "--stdio", static_cast<char*>(nullptr));
        _exit(127);
    }
    if (child < 0) {
        result.error = "fork failed";
        close_fd(input[0]); close_fd(input[1]); close_fd(output[0]); close_fd(output[1]); close_fd(error[0]); close_fd(error[1]);
        return result;
    }
    (void)setpgid(child, child);
    close_fd(input[0]); close_fd(output[1]); close_fd(error[1]);
    {
        ScopedSigpipeBlock sigpipe;
        std::size_t offset = 0;
        while (offset < request.standard_input.size()) {
            const ssize_t count = write(input[1], request.standard_input.data() + offset, request.standard_input.size() - offset);
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
    for (;;) {
        const pid_t waited = waitpid(child, &status, WNOHANG);
        if (waited == child) break;
        if (waited < 0 && errno != EINTR) { result.error = "waitpid failed"; break; }
        if (request.cancellation_requested && request.cancellation_requested()) {
            result.cancelled = true;
            kill(-child, SIGKILL);
        } else if (std::chrono::steady_clock::now() >= deadline) {
            result.timed_out = true;
            kill(-child, SIGKILL);
        } else if (overflow.load(std::memory_order_acquire)) {
            result.output_too_large = true;
            kill(-child, SIGKILL);
        } else {
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            continue;
        }
        while (waitpid(child, &status, 0) < 0 && errno == EINTR) {}
        break;
    }
    output_reader.join();
    error_reader.join();
    close_fd(output[0]); close_fd(error[0]);
    if (WIFEXITED(status)) result.exit_code = WEXITSTATUS(status);
    else if (WIFSIGNALED(status)) result.exit_code = 128 + WTERMSIG(status);
    result.output_too_large = result.output_too_large || overflow.load(std::memory_order_acquire);
    return result;
}

} // namespace facman::client::detail
