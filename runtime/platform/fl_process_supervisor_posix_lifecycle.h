// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#ifndef FACMAN_PLATFORM_POSIX_CHILD_LIFECYCLE_H
#define FACMAN_PLATFORM_POSIX_CHILD_LIFECYCLE_H

#include "fl_process_supervisor.h"

#include <algorithm>
#include <cstddef>
#include <cerrno>
#include <csignal>
#include <optional>
#include <sys/types.h>
#include <sys/wait.h>

namespace facman::platform::detail {

enum class ChildPhase {
    owned_running, terminal_observed_unreaped, reaping_started, reaped, ownership_unknown
};
enum class ChildObservation { running, terminal, unknown };
struct SignalDisposition { int error = 0; struct sigaction action {}; };
struct ChildPoll { int error = 0; siginfo_t info {}; };
struct ChildWait { pid_t process = -1; int error = 0; int status = 0; };
struct ChildGroupSnapshotRow {
    pid_t process = 0;
    pid_t group = 0;
    bool terminal = false;
};
struct ChildGroupSnapshot {
    // True only when the adapter obtained a complete, internally consistent
    // view of the addressed process group.
    bool complete = false;
    bool group_contains_only_target = false;
    bool group_has_no_live_members = false;
};
inline ChildGroupSnapshot classify_child_group_snapshot(
    pid_t expected_group, const ChildGroupSnapshotRow* rows, std::size_t count)
{
    if (expected_group <= 0 || (count != 0 && rows == nullptr)) return {};
    bool all_terminal = true;
    for (std::size_t index = 0; index < count; ++index) {
        if (rows[index].process <= 0 || rows[index].group != expected_group) return {};
        all_terminal = all_terminal && rows[index].terminal;
    }
    ChildGroupSnapshot result;
    result.complete = true;
    result.group_contains_only_target = count == 1 &&
        rows[0].process == expected_group && rows[0].terminal;
    result.group_has_no_live_members = all_terminal;
    return result;
}
struct ChildSignal {
    int result = -1;
    int error = 0;
};

// Per-invocation adapter, with no global hooks. Its native implementation must
// not reap except in consume(). The embedding must supply exclusive waiting
// ownership and keep SIGCHLD disposition stable for the entire child lifetime.
template<class Operations>
bool admits_child_waiting(Operations& operations, std::string& error)
{
    const auto disposition = operations.disposition();
    if (disposition.error != 0) {
        error = "SIGCHLD disposition query failed";
        return false;
    }
    if (disposition.action.sa_handler == SIG_IGN ||
        (disposition.action.sa_flags & SA_NOCLDWAIT) != 0) {
        error = "SIGCHLD automatic reaping prevents exclusive child waiting";
        return false;
    }
    return true;
}

template<class Operations>
class PosixChildLifecycle {
public:
    PosixChildLifecycle(pid_t child, bool group_established, Operations& operations)
        : child_(child), group_established_(group_established), operations_(operations)
    {
        if (child <= 0) unknown("invalid owned child");
    }
    PosixChildLifecycle(const PosixChildLifecycle&) = delete;
    PosixChildLifecycle& operator=(const PosixChildLifecycle&) = delete;
    // No destructor signals or waits. In particular, exception unwinding never
    // reacquires a numeric PID/group after a consuming wait has started.
    ChildPhase phase() const { return phase_; }
    bool reaping_started() const { return reaping_started_; }
    const std::optional<int>& status() const { return status_; }
    const std::string& error() const { return error_; }
    bool group_cleanup_pending() const
    {
        return group_cleanup_ == GroupCleanup::pending_eperm;
    }

    ChildObservation observe()
    {
        if (!can_signal()) return ChildObservation::unknown;
        try {
            const auto polled = operations_.observe(child_, WEXITED | WNOHANG | WNOWAIT);
            if (polled.error == EINTR) return ChildObservation::running;
            if (polled.error != 0) {
                unknown("waitid failed (errno " + std::to_string(polled.error) + ")");
                return ChildObservation::unknown;
            }
            if (polled.info.si_pid == 0) return ChildObservation::running;
            if (polled.info.si_pid != child_ ||
                (polled.info.si_code != CLD_EXITED && polled.info.si_code != CLD_KILLED &&
                 polled.info.si_code != CLD_DUMPED)) {
                unknown("waitid returned a foreign or nonterminal child observation");
                return ChildObservation::unknown;
            }
            phase_ = ChildPhase::terminal_observed_unreaped;
            return ChildObservation::terminal;
        } catch (...) {
            unknown("waitid adapter threw; child ownership unknown");
            return ChildObservation::unknown;
        }
    }

    static constexpr std::size_t maximum_consume_attempts = 32;

    bool reap()
    {
        if (!can_signal()) {
            materialize_group_cleanup_error();
            return false;
        }
        materialize_group_cleanup_error();
        // Set before entering ANY consuming operation. An interrupted, failed,
        // or throwing call cannot restore signal authority.
        reaping_started_ = true;
        phase_ = ChildPhase::reaping_started;
        try {
            ChildWait waited;
            for (std::size_t attempt = 0; attempt < maximum_consume_attempts; ++attempt) {
                waited = operations_.consume(child_);
                if (!(waited.process < 0 && waited.error == EINTR)) break;
                if (attempt + 1 == maximum_consume_attempts) {
                    unknown("waitpid EINTR retry budget exhausted after reaping started");
                    return false;
                }
            }
            if (waited.process != child_ || waited.error != 0 ||
                (!WIFEXITED(waited.status) && !WIFSIGNALED(waited.status))) {
                unknown("waitpid failed or returned unusable status (errno " +
                    std::to_string(waited.error) + ")");
                return false;
            }
            status_ = waited.status;
            phase_ = ChildPhase::reaped;
            return true;
        } catch (...) {
            unknown("waitpid adapter threw after reaping started");
            return false;
        }
    }

    bool finish(std::chrono::milliseconds grace, bool& tree_termination_requested)
    {
        terminate(grace, tree_termination_requested);
        return reap();
    }

    void terminate(std::chrono::milliseconds grace, bool& tree_termination_requested)
    {
        if (!can_signal()) return;
        if (!group_established_) note("child group unavailable; cleanup limited to owned child");
        try {
            // Validate at the actual addition point: elapsed preparation can
            // invalidate the caller's earlier near-maximum grace check.
            using Clock = std::chrono::steady_clock;
            static_assert(std::ratio_less_equal<Clock::period, std::milli>::value,
                "POSIX grace conversion requires clock ticks no coarser than milliseconds");
            const auto now = operations_.now();
            const auto maximum_grace = std::chrono::duration_cast<std::chrono::milliseconds>(
                Clock::duration::max());
            if (grace.count() < 0 || grace > maximum_grace) {
                note("termination grace is outside the monotonic clock range");
                return;
            }
            const auto delta = std::chrono::duration_cast<Clock::duration>(grace);
            if (now.time_since_epoch() > Clock::duration::max() - delta) {
                note("termination deadline exceeds the monotonic clock range");
                return;
            }
            const auto deadline = now + delta;
            if (!send(SIGTERM, tree_termination_requested)) return;
            while (can_signal() && operations_.now() < deadline) {
                if (!send(0, tree_termination_requested)) return;
                operations_.pause(std::chrono::milliseconds(10));
            }
            if (can_signal()) (void)send(SIGKILL, tree_termination_requested);
        } catch (...) {
            note("termination adapter threw before reaping");
        }
    }

    // Resolve a deferred Darwin group-signal refusal only after waitid has
    // proved the exact leader terminal and before waitpid consumes that proof.
    // The caller may retry this bounded operation while its existing cleanup
    // deadline remains. A complete final group view is required.
    bool resolve_group_cleanup()
    {
        if (!group_cleanup_pending()) return true;
        if (!can_signal() || phase_ != ChildPhase::terminal_observed_unreaped)
            return false;
        try {
            const auto snapshot = operations_.observe_group(child_);
            if (!snapshot.complete) return false;
            if (snapshot.group_contains_only_target) {
                group_cleanup_ = GroupCleanup::no_live_confirmed;
                return true;
            }
            if (snapshot.group_has_no_live_members && group_signal_succeeded_) {
                group_cleanup_ = GroupCleanup::no_live_confirmed;
                return true;
            }
        } catch (...) {
            // Retain the original EPERM classification and materialize it once
            // before reaping; adapter exceptions cannot grant cleanup proof.
        }
        return false;
    }

    void resolve_group_cleanup_until(std::chrono::steady_clock::time_point deadline)
    {
        while (group_cleanup_pending()) {
            const auto now = operations_.now();
            if (now >= deadline) return;
            if (resolve_group_cleanup()) return;
            const auto remaining = std::chrono::duration_cast<std::chrono::milliseconds>(
                deadline - operations_.now());
            if (remaining <= std::chrono::milliseconds::zero()) return;
            operations_.pause(std::min(std::chrono::milliseconds(10), remaining));
        }
    }

private:
    enum class GroupCleanup { clear, pending_eperm, no_live_confirmed, materialized_error };
    bool can_signal() const
    {
        return !reaping_started_ &&
            (phase_ == ChildPhase::owned_running ||
             phase_ == ChildPhase::terminal_observed_unreaped);
    }
    bool send(int signal, bool& tree_termination_requested)
    {
        if (!can_signal()) return false;
        const auto attempt = operations_.signal(group_established_ ? -child_ : child_, signal);
        if (attempt.result == 0) {
            if (signal != 0 && group_established_) {
                group_signal_succeeded_ = true;
                tree_termination_requested = true;
            }
            return true;
        }
        if (attempt.error == ESRCH) return false;
        // Darwin can transiently refuse a process-group probe after a group
        // signal. Keep cleanup moving, but do not turn leader status or the
        // signal result into proof that descendants are gone. That needs a
        // fresh complete group observation after the leader is terminal.
        if (attempt.error == EPERM && group_established_) {
            group_cleanup_ = GroupCleanup::pending_eperm;
            pending_group_error_ = attempt.error;
            if (phase_ == ChildPhase::terminal_observed_unreaped ||
                observe() == ChildObservation::terminal) {
                if (resolve_group_cleanup()) return false;
            }
            return true;
        }
        note("child termination/probe failed (errno " + std::to_string(attempt.error) + ")");
        return true;
    }
    void materialize_group_cleanup_error()
    {
        if (!group_cleanup_pending()) return;
        note("child termination/probe failed (errno " +
            std::to_string(pending_group_error_) + ")");
        group_cleanup_ = GroupCleanup::materialized_error;
    }
    void note(const std::string& text)
    {
        if (!error_.empty()) error_ += "; ";
        error_ += text;
    }
    void unknown(const std::string& text)
    {
        phase_ = ChildPhase::ownership_unknown;
        materialize_group_cleanup_error();
        note(text);
    }
    pid_t child_;
    bool group_established_;
    Operations& operations_;
    ChildPhase phase_ = ChildPhase::owned_running;
    bool reaping_started_ = false;
    bool group_signal_succeeded_ = false;
    GroupCleanup group_cleanup_ = GroupCleanup::clear;
    int pending_group_error_ = 0;
    std::optional<int> status_;
    std::string error_;
};

inline void finish_child_result(ProcessResult& result, const std::optional<int>& status,
    bool terminal_observed, bool drain_overflow, const std::string& cleanup_error)
{
    if (!cleanup_error.empty()) {
        if (!result.error.empty()) result.error += "; ";
        result.error += cleanup_error;
    }
    // A missing or unusable native wait result is never synthesized as exit 0.
    if (!status) {
        result.native_status = -1;
        return;
    }
    result.native_status = *status;
    if (WIFEXITED(*status)) {
        result.exit_code = WEXITSTATUS(*status);
        if (terminal_observed) result.termination = ProcessTermination::exited;
    } else if (WIFSIGNALED(*status)) {
        result.exit_code = 128 + WTERMSIG(*status);
        if (terminal_observed) result.termination = ProcessTermination::crashed;
    }
    if (terminal_observed && drain_overflow) result.termination = ProcessTermination::output_limit;
}

} // namespace facman::platform::detail
#endif
