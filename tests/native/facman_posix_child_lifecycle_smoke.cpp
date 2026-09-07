// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "../../runtime/platform/fl_process_supervisor_posix_lifecycle.h"

#include <deque>
#include <functional>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

using namespace facman::platform;
using namespace facman::platform::detail;
using Milliseconds = std::chrono::milliseconds;
constexpr pid_t child_id = 4312;

void require(bool value, const char* message)
{
    if (!value) throw std::runtime_error(message);
}

ChildPoll observation(pid_t pid = child_id, int code = CLD_EXITED, int error = 0)
{
    ChildPoll result;
    result.error = error;
    result.info.si_pid = pid;
    result.info.si_code = code;
    return result;
}

struct FakeOperations {
    SignalDisposition initial;
    std::deque<ChildPoll> observations;
    std::deque<ChildWait> waits;
    std::vector<std::string> trace;
    std::vector<pid_t> targets;
    std::function<void()> consuming_hook;
    std::chrono::steady_clock::time_point clock {};
    bool numeric_group_reused = false;
    bool throw_after_consume = false;
    bool throw_on_observe = false;
    bool signal_missing = false;
    int signal_error = 0;
    int unsafe_signals = 0;
    int dispositions = 0;

    SignalDisposition disposition() { ++dispositions; return initial; }
    ChildPoll observe(pid_t child, int options)
    {
        require(child == child_id, "poll must name the exact owned child");
        require(options == (WEXITED | WNOHANG | WNOWAIT), "poll must retain waitability");
        trace.emplace_back("observe-unreaped");
        if (throw_on_observe) throw std::runtime_error("injected poll failure");
        require(!observations.empty(), "unplanned poll");
        const auto value = observations.front(); observations.pop_front();
        return value;
    }
    ChildWait consume(pid_t child)
    {
        require(child == child_id, "consume must name exact child, never -1");
        trace.emplace_back("consume");
        if (consuming_hook) consuming_hook();
        // Independent adverse ownership model: even a failed/interrupted return
        // may no longer provide a usable original numeric group to the caller.
        numeric_group_reused = true;
        if (throw_after_consume) throw std::runtime_error("consumed before adapter threw");
        require(!waits.empty(), "unplanned consuming wait");
        const auto value = waits.front(); waits.pop_front();
        return value;
    }
    ChildSignal signal(pid_t target, int number)
    {
        if (numeric_group_reused) {
            ++unsafe_signals;
            throw std::runtime_error("signal reached a replacement group");
        }
        require(target == -child_id || target == child_id, "unrelated signal target");
        targets.push_back(target);
        trace.push_back("signal-" + std::to_string(number));
        if (signal_missing) return {-1, ESRCH};
        if (signal_error != 0) return {-1, signal_error};
        return {0, 0};
    }
    std::chrono::steady_clock::time_point now() const { return clock; }
    void pause(Milliseconds duration) { clock += duration; }
};

using Lifetime = PosixChildLifecycle<FakeOperations>;

void terminal_case(int native_status, int code, int exit_code, ProcessTermination termination)
{
    FakeOperations operations;
    operations.observations.push_back(observation(child_id, code));
    operations.waits.push_back({child_id, 0, native_status});
    Lifetime child(child_id, true, operations);
    bool tree = false;
    require(child.observe() == ChildObservation::terminal, "terminal observation required");
    require(child.phase() == ChildPhase::terminal_observed_unreaped, "poll consumed child");
    require(!child.reaping_started(), "poll entered consuming phase");
    operations.consuming_hook = [&] {
        require(child.reaping_started() && child.phase() == ChildPhase::reaping_started,
            "latch must precede first consuming syscall");
        child.terminate(Milliseconds(0), tree); // Reentrant cleanup is refused.
    };
    require(child.finish(Milliseconds(0), tree), "terminal child must be consumed once");
    const std::vector<std::string> expected {"observe-unreaped", "signal-" + std::to_string(SIGTERM),
        "signal-" + std::to_string(SIGKILL), "consume"};
    require(operations.trace == expected, "actual production finish ordering changed");
    require(tree && child.phase() == ChildPhase::reaped, "terminal ownership outcome");
    child.terminate(Milliseconds(20), tree);
    require(!child.reap() && child.observe() == ChildObservation::unknown, "closed child reused");
    require(operations.trace == expected && operations.unsafe_signals == 0, "post-reap numeric operation");
    ProcessResult result;
    finish_child_result(result, child.status(), true, false, child.error());
    require(result.native_status == native_status && result.exit_code == exit_code &&
        result.termination == termination, "genuine native status lost");
    finish_child_result(result, child.status(), true, true, child.error());
    require(result.termination == ProcessTermination::output_limit, "final drain overflow lost");
}

void consuming_failures()
{
    for (int failure : {ECHILD, EIO, EINVAL}) {
        FakeOperations operations;
        operations.waits.push_back({-1, failure, 0});
        Lifetime child(child_id, true, operations);
        bool tree = false;
        require(!child.finish(Milliseconds(0), tree), "failed consume reported success");
        const auto count = operations.trace.size();
        child.terminate(Milliseconds(100), tree);
        require(!child.reap() && child.reaping_started(), "failed wait restored authority");
        require(operations.trace.size() == count && operations.unsafe_signals == 0, "failure cleanup signaled reused ID");
        ProcessResult result;
        result.termination = ProcessTermination::timed_out;
        result.error = "primary timeout detail";
        finish_child_result(result, child.status(), false, true, child.error());
        require(result.termination == ProcessTermination::timed_out && result.exit_code == -1 &&
            result.native_status == -1, "cleanup error replaced primary reason or fabricated exit zero");
        require(result.error.find("primary timeout detail; waitpid") == 0, "cleanup error not appended");
    }
    for (bool thrown : {false, true}) {
        FakeOperations operations;
        operations.throw_after_consume = thrown;
        if (!thrown) operations.waits.push_back({child_id + 1, 0, 0});
        Lifetime child(child_id, true, operations);
        bool tree = false;
        require(!child.finish(Milliseconds(0), tree), "ambiguous consume accepted");
        child.terminate(Milliseconds(0), tree);
        require(!child.status() && child.reaping_started() &&
            child.phase() == ChildPhase::ownership_unknown && operations.unsafe_signals == 0,
            "consumed-then-threw/mismatched return restored ownership");
    }
}

void interruption_and_running_outcomes()
{
    for (auto reason : {ProcessTermination::cancelled, ProcessTermination::timed_out,
                        ProcessTermination::output_limit}) {
        FakeOperations operations;
        operations.observations.push_back(observation(0));
        operations.observations.push_back(observation(0, 0, EINTR));
        operations.waits.push_back({-1, EINTR, 0});
        operations.waits.push_back({child_id, 0, SIGKILL});
        Lifetime child(child_id, true, operations);
        bool tree = false;
        require(child.observe() == ChildObservation::running &&
            child.observe() == ChildObservation::running, "no status/EINTR must preserve running ownership");
        require(child.finish(Milliseconds(20), tree), "EINTR consuming retry lost real status");
        require(child.reaping_started() && operations.unsafe_signals == 0, "interruption reopened signaling");
        require(operations.trace[operations.trace.size()-2] == "consume" &&
            operations.trace.back() == "consume", "consume retry interleaved cleanup");
        ProcessResult result; result.termination = reason;
        finish_child_result(result, child.status(), false, true, child.error());
        require(result.termination == reason && result.exit_code == 128 + SIGKILL,
            "running termination primary reason changed");
    }
}

void unknown_observations()
{
    for (const auto& observed : {observation(0, 0, ECHILD), observation(0, 0, EIO),
             observation(child_id + 1), observation(child_id, CLD_STOPPED),
             observation(child_id, CLD_CONTINUED)}) {
        FakeOperations operations;
        operations.observations.push_back(observed);
        Lifetime child(child_id, true, operations);
        require(child.observe() == ChildObservation::unknown, "unknown observation admitted");
        bool tree = false;
        require(!child.finish(Milliseconds(0), tree), "unknown owner was consumed");
        require(operations.trace == std::vector<std::string>{"observe-unreaped"} &&
            !child.status() && !child.error().empty(), "unknown owner signaled or fabricated status");
    }
    FakeOperations operations; operations.throw_on_observe = true;
    Lifetime child(child_id, true, operations);
    require(child.observe() == ChildObservation::unknown, "throwing poll admitted");
    bool tree = false; child.terminate(Milliseconds(0), tree);
    require(operations.targets.empty(), "throwing poll retained signal authority");
}

void disposition_admission()
{
    for (int fault = 0; fault != 4; ++fault) {
        FakeOperations operations;
        if (fault == 1) operations.initial.action.sa_handler = SIG_IGN;
        if (fault == 2) operations.initial.action.sa_flags = SA_NOCLDWAIT;
        if (fault == 3) operations.initial.error = EIO;
        std::string error;
        require(admits_child_waiting(operations, error) == (fault == 0), "SIGCHLD admission");
        require(operations.dispositions == 1 && operations.trace.empty(), "admission performed child effect");
        require(error.empty() == (fault == 0), "admission error missing");
    }
}

void exec_failure_and_cleanup_limits()
{
    FakeOperations operations;
    operations.waits.push_back({child_id, 0, 127 << 8});
    Lifetime child(child_id, true, operations);
    require(child.reap(), "exec-error exact child wait failed");
    bool tree = false; child.terminate(Milliseconds(0), tree);
    require(operations.trace == std::vector<std::string>{"consume"}, "exec-error late signal");
    ProcessResult result; result.termination = ProcessTermination::start_failed;
    result.error = "execve failed: fixture";
    finish_child_result(result, child.status(), false, false, child.error());
    require(result.termination == ProcessTermination::start_failed && result.exit_code == 127,
        "exec-error status/primary result changed");

    FakeOperations fallback;
    fallback.waits.push_back({child_id, 0, SIGKILL});
    Lifetime ungrouped(child_id, false, fallback);
    require(ungrouped.finish(Milliseconds(0), tree), "owned-child fallback failed");
    require(!tree && fallback.targets == std::vector<pid_t>{child_id, child_id},
        "unconfirmed group signaled or tree termination claimed");
    require(!ungrouped.error().empty(), "unconfirmed group limitation hidden");

    FakeOperations missing;
    missing.signal_missing = true;
    missing.waits.push_back({child_id, 0, 0});
    Lifetime vanished(child_id, true, missing);
    require(vanished.finish(Milliseconds(0), tree) && !tree, "missing group status lost");
    require(missing.targets.size() == 1, "ESRCH issued unnecessary follow-up signal");

    FakeOperations denied;
    denied.signal_error = EPERM;
    denied.waits.push_back({child_id, 0, SIGKILL});
    Lifetime uncertain_cleanup(child_id, true, denied);
    require(uncertain_cleanup.finish(Milliseconds(0), tree) && !tree, "denied cleanup status");
    require(!uncertain_cleanup.error().empty(), "cleanup failure discarded");
}

int main()
{
    try {
        terminal_case(0, CLD_EXITED, 0, ProcessTermination::exited);
        terminal_case(23 << 8, CLD_EXITED, 23, ProcessTermination::exited);
        terminal_case(SIGKILL, CLD_KILLED, 128 + SIGKILL, ProcessTermination::crashed);
        terminal_case(SIGABRT | 0x80, CLD_DUMPED, 128 + SIGABRT, ProcessTermination::crashed);
        consuming_failures();
        interruption_and_running_outcomes();
        unknown_observations();
        disposition_admission();
        exec_failure_and_cleanup_limits();
        std::cout << "POSIX production child lifecycle injected checks passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
