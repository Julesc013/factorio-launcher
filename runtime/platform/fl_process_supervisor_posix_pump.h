// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#ifndef FACMAN_PLATFORM_POSIX_PROCESS_PUMP_H
#define FACMAN_PLATFORM_POSIX_PROCESS_PUMP_H

#include "fl_process_supervisor.h"
#include "fl_process_supervisor_posix_lifecycle.h"

#include <algorithm>
#include <array>
#include <cerrno>
#include <cstring>
#include <poll.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <utility>

namespace facman::platform::detail {

struct PipeTransfer { ssize_t count = -1; int error = 0; };
struct PipePoll { int count = -1; int error = 0; };

// Stdin is a local stream socket. Suppression belongs to this socket/send,
// never to the caller's process/thread signal disposition, mask or pending set.
template<class Operations>
bool create_stdin_socket(Operations& operations, int (&pair)[2], bool require_socket_option)
{
    if (!operations.socket_pair(pair)) return false;
    return !require_socket_option || operations.no_sigpipe(pair[1]);
}
template<class Operations>
PipeTransfer send_stdin_socket(Operations& operations, int fd, const void* data, std::size_t size)
{
#ifdef __APPLE__
    constexpr int flags = 0; // SO_NOSIGPIPE was checked on this owned socket.
#else
    constexpr int flags = MSG_NOSIGNAL;
#endif
    return operations.send(fd, data, size, flags);
}
// The child calls this before exec. EBADF denotes an already absent entry;
// every other close failure is ambiguous and is reported once, never retried.
template<class Operations>
int close_inherited_descriptors(Operations& operations, int maximum, int keep)
{
    for (int fd = 3; fd < maximum; ++fd) {
        if (fd == keep) continue;
        const int error = operations.close_inherited(fd);
        if (error != 0 && error != EBADF) return error;
    }
    return 0;
}

// The driver and injected tests share this operation-authority boundary.
class PosixProcessOutcome {
public:
    explicit PosixProcessOutcome(ProcessResult& result) : result_(result)
    {
        result_.termination = ProcessTermination::pending;
    }
    bool announced() const { return announced_; }
    bool announce(bool exec_confirmed, const ProcessRequest& request, ProcessIdentity identity)
    {
        if (!exec_confirmed || announced_ || uncertain_) return false;
        try {
            result_.identity = std::move(identity);
            // No callback is an optional no-op notification, not no-effects
            // evidence. A supplied callback must actually return successfully.
            if (request.started) request.started(result_.identity);
            announced_ = true;
            return true;
        } catch (...) {
            uncertain("process started callback failed");
            return false;
        }
    }
    bool cancelled(const ProcessRequest& request)
    {
        try {
            if (!request.cancellation_requested || !request.cancellation_requested()) return false;
            reason(ProcessTermination::cancelled, "process cancellation requested");
        } catch (...) {
            uncertain("process cancellation callback failed");
        }
        return true;
    }
    template<class Pump>
    bool step(Pump& pump, int wait_ms, bool supply_input = true)
    {
        try {
            if (pump.step(wait_ms, supply_input)) return true;
            if (pump.reliable_exec_error() > 0)
                exec_error(pump.error() + " (errno " + std::to_string(pump.reliable_exec_error()) + ")");
            else uncertain(pump.error());
        } catch (...) {
            uncertain("process pipe processing threw");
        }
        return false;
    }
    template<class Pump>
    bool observe_exec_status(Pump& pump)
    {
        try {
            if (pump.observe_exec_status()) return true;
            if (pump.reliable_exec_error() > 0)
                exec_error(pump.error() + " (errno " +
                    std::to_string(pump.reliable_exec_error()) + ")");
            else
                uncertain(pump.error());
        } catch (...) {
            uncertain("process exec status observation threw");
        }
        return false;
    }
    void reason(ProcessTermination termination, const std::string& text)
    {
        result_.termination = announced_ && !uncertain_ ? termination : ProcessTermination::pending;
        note(text);
    }
    void uncertain(const std::string& text)
    {
        uncertain_ = true;
        result_.termination = ProcessTermination::pending; // Before diagnostic allocation.
        note(text);
    }
    void exec_error(const std::string& text) { note(text); }
    void finish(const std::optional<int>& status, bool terminal_observed,
        bool overflow, int reliable_exec_error)
    {
        const bool completed = announced_ && !uncertain_ && result_.error.empty() && terminal_observed;
        finish_child_result(result_, status, completed, false, "");
        if (!announced_ && !uncertain_ && reliable_exec_error > 0 && status && WIFEXITED(*status) &&
            (WEXITSTATUS(*status) == 126 || WEXITSTATUS(*status) == 127)) {
            result_.termination = ProcessTermination::start_failed;
            return;
        }
        if (!announced_ || uncertain_ || !status) {
            result_.termination = ProcessTermination::pending;
            return;
        }
        if (overflow) reason(ProcessTermination::output_limit, "process output limit exceeded");
    }
private:
    void note(const std::string& text)
    {
        if (text.empty()) return;
        if (!result_.error.empty()) result_.error += "; ";
        result_.error += text;
    }
    ProcessResult& result_;
    bool announced_ = false;
    bool uncertain_ = false;
};

// All four parent endpoints must be nonblocking before fork. One step performs
// at most one bounded operation per ready endpoint, so a busy stream cannot
// starve cancellation, child observation, another stream or the deadline.
template<class Operations>
class PosixProcessPump {
public:
    PosixProcessPump(Operations& operations, int& input, int& output, int& error,
        int& exec_status, const ProcessRequest& request, ProcessResult& result)
        : operations_(operations), input_(input), output_(output), error_(error),
          exec_status_(exec_status), request_(request), result_(result) {}

    bool step(int wait_ms, bool supply_input = true)
    {
        if (input_offset_ == request_.standard_input.size() || !supply_input)
            close_endpoint(input_);
        std::array<pollfd, 4> descriptors {{
            {output_, POLLIN, 0}, {error_, POLLIN, 0}, {exec_status_, POLLIN, 0},
            {supply_input && exec_ready_ ? input_ : -1, POLLOUT, 0}
        }};
        const auto polled = operations_.poll(descriptors.data(), descriptors.size(), wait_ms);
        if (polled.count < 0) {
            if (polled.error == EINTR) return error_text_.empty();
            fail("process pipe poll failed");
            return false;
        }
        if (polled.count == 0) return error_text_.empty();
        for (const auto& descriptor : descriptors) {
            if ((descriptor.revents & POLLNVAL) != 0) {
                fail("process pipe descriptor became invalid");
                return false;
            }
        }
        if (descriptors[0].revents != 0)
            read_stream(output_, result_.standard_output, request_.maximum_standard_output);
        if (descriptors[1].revents != 0)
            read_stream(error_, result_.standard_error, request_.maximum_standard_error);
        if (descriptors[2].revents != 0) read_exec_status();
        if (descriptors[3].revents != 0 && error_text_.empty()) write_input();
        return error_text_.empty();
    }

    bool exec_ready() const { return exec_ready_; }
    bool exec_failed() const { return exec_failed_; }
    bool has_io_failure() const { return io_failure_; }
    int reliable_exec_error() const {
        return exec_size_ == exec_bytes_.size() && exec_error_ > 0 && !io_failure_ ? exec_error_ : 0;
    }
    bool overflow() const { return overflow_; }
    bool output_closed() const { return output_ < 0 && error_ < 0; }
    const std::string& error() const { return error_text_; }
    void close_input() { close_endpoint(input_); }
    // The exec-status endpoint is nonblocking. One direct read observes only
    // the close-on-exec proof or bounded errno frame without advancing any
    // caller stream or waiting for a child that has not yet executed.
    bool observe_exec_status()
    {
        if (exec_status_ >= 0 && !exec_ready_ && !exec_failed_ && error_text_.empty())
            read_exec_status();
        return error_text_.empty();
    }

private:
    void fail(const char* text, bool io_failure = true)
    {
        if (io_failure) io_failure_ = true;
        if (error_text_.empty()) error_text_ = text;
    }
    void close_endpoint(int& descriptor)
    {
        if (descriptor >= 0 && !operations_.close(descriptor))
            fail("process pipe close outcome is uncertain");
    }
    static bool retry_later(int error)
    {
        return error == EINTR || error == EAGAIN || error == EWOULDBLOCK;
    }
    void read_stream(int& descriptor, std::string& output, std::size_t maximum)
    {
        char buffer[8192];
        const auto read = operations_.read(descriptor, buffer, sizeof(buffer));
        if (read.count > 0) {
            const auto count = static_cast<std::size_t>(read.count);
            const auto available = output.size() < maximum ? maximum - output.size() : 0;
            output.append(buffer, std::min(count, available));
            if (count > available) overflow_ = true;
        } else if (read.count == 0) {
            close_endpoint(descriptor);
        } else if (!retry_later(read.error)) {
            fail("process pipe read failed");
        }
    }
    void read_exec_status()
    {
        if (exec_size_ >= exec_bytes_.size()) {
            exec_failed_ = true;
            fail("process exec status frame exceeded its fixed size");
            return;
        }
        const auto remaining = exec_bytes_.size() - exec_size_;
        const auto read = operations_.read(
            exec_status_, exec_bytes_.data() + exec_size_, remaining);
        if (read.count > 0) {
            const auto count = static_cast<std::size_t>(read.count);
            if (count > remaining) {
                exec_failed_ = true;
                fail("process exec status read exceeded the requested frame remainder");
                return;
            }
            exec_size_ += count;
            if (exec_size_ == exec_bytes_.size()) {
                exec_failed_ = true;
                std::memcpy(&exec_error_, exec_bytes_.data(), sizeof(exec_error_));
                close_endpoint(exec_status_);
                if (exec_error_ > 0) fail("process child setup or execve failed", false);
                else fail("process exec error frame is not a positive errno");
            }
        } else if (read.count == 0) {
            close_endpoint(exec_status_);
            if (exec_size_ == 0) exec_ready_ = true;
            else {
                exec_failed_ = true;
                fail("process exec status ended with a partial error frame");
            }
        } else if (!retry_later(read.error)) {
            exec_failed_ = true;
            fail("process exec status read failed");
        }
    }
    void write_input()
    {
        const auto remaining = request_.standard_input.size() - input_offset_;
        const auto write = operations_.write(input_, request_.standard_input.data() + input_offset_,
            std::min<std::size_t>(remaining, 8192));
        if (write.count > 0) {
            input_offset_ += static_cast<std::size_t>(write.count);
            if (input_offset_ == request_.standard_input.size()) close_endpoint(input_);
        } else if (write.count < 0 && write.error == EPIPE) {
            // A child may deliberately close stdin and still produce a valid result.
            close_endpoint(input_);
        } else if (write.count == 0 || !retry_later(write.error)) {
            fail("process pipe write failed");
        }
    }

    Operations& operations_;
    int& input_;
    int& output_;
    int& error_;
    int& exec_status_;
    const ProcessRequest& request_;
    ProcessResult& result_;
    std::size_t input_offset_ = 0;
    std::array<unsigned char, sizeof(int)> exec_bytes_ {};
    std::size_t exec_size_ = 0;
    int exec_error_ = 0;
    bool exec_ready_ = false;
    bool exec_failed_ = false;
    bool overflow_ = false;
    bool io_failure_ = false;
    std::string error_text_;
};

} // namespace facman::platform::detail
#endif
