// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "../../runtime/platform/fl_process_supervisor_posix_lifecycle.h"

#include <algorithm>
#include <array>
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
    bool throw_on_group_observe = false;
    bool signal_missing = false;
    int signal_error = 0;
    std::deque<ChildSignal> signal_results;
    std::deque<ChildGroupSnapshot> group_snapshots;
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
        if (!signal_results.empty()) {
            const auto result = signal_results.front();
            signal_results.pop_front();
            return result;
        }
        if (signal_missing) return {-1, ESRCH};
        if (signal_error != 0) return {-1, signal_error};
        return {0, 0};
    }
    ChildGroupSnapshot observe_group(pid_t group)
    {
        if (numeric_group_reused) {
            ++unsafe_signals;
            throw std::runtime_error("group observation reached a replacement group");
        }
        require(group == child_id, "group observation must name the owned group");
        trace.emplace_back("observe-group");
        if (throw_on_group_observe) throw std::runtime_error("injected group observation failure");
        require(!group_snapshots.empty(), "unplanned group observation");
        const auto value = group_snapshots.front(); group_snapshots.pop_front();
        return value;
    }
    std::chrono::steady_clock::time_point now() const { return clock; }
    void pause(Milliseconds duration) { clock += duration; }
};

using Lifetime = PosixChildLifecycle<FakeOperations>;

void group_snapshot_classification()
{
    const std::array<ChildGroupSnapshotRow, 2> terminal {{
        {child_id, child_id, true}, {child_id + 1, child_id, true}
    }};
    auto snapshot = classify_child_group_snapshot(
        child_id, terminal.data(), terminal.size());
    require(snapshot.complete && snapshot.group_has_no_live_members &&
        !snapshot.group_contains_only_target,
        "terminal multirow owned group was not classified as quiescent");

    const std::array<ChildGroupSnapshotRow, 1> leader {{{child_id, child_id, true}}};
    snapshot = classify_child_group_snapshot(child_id, leader.data(), leader.size());
    require(snapshot.complete && snapshot.group_has_no_live_members &&
        snapshot.group_contains_only_target,
        "exact terminal leader snapshot lost its narrow classification");

    const std::array<ChildGroupSnapshotRow, 2> live {{
        {child_id, child_id, true}, {child_id + 1, child_id, false}
    }};
    snapshot = classify_child_group_snapshot(child_id, live.data(), live.size());
    require(snapshot.complete && !snapshot.group_has_no_live_members &&
        !snapshot.group_contains_only_target,
        "live descendant was classified as a terminal group");

    const std::array<ChildGroupSnapshotRow, 2> foreign {{
        {child_id, child_id, true}, {child_id + 1, child_id + 1, true}
    }};
    snapshot = classify_child_group_snapshot(child_id, foreign.data(), foreign.size());
    require(!snapshot.complete && !snapshot.group_has_no_live_members &&
        !snapshot.group_contains_only_target,
        "foreign process-group row was admitted");

    snapshot = classify_child_group_snapshot(child_id, nullptr, 0);
    require(snapshot.complete && snapshot.group_has_no_live_members &&
        !snapshot.group_contains_only_target,
        "complete empty snapshot lost its no-live-members classification");
}

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

}

void deferred_group_cleanup_outcomes()
{
    const ChildGroupSnapshot incomplete {};
    const ChildGroupSnapshot empty {true, false, true};
    const ChildGroupSnapshot sole_terminal_leader {true, true, true};
    const ChildGroupSnapshot live {true, false, false};
    const std::array<ChildGroupSnapshotRow, 2> foreign_rows {{
        {child_id, child_id, true}, {child_id + 1, child_id + 1, true}
    }};
    const auto foreign = classify_child_group_snapshot(
        child_id, foreign_rows.data(), foreign_rows.size());

    // The hosted macOS race: an admitted group termination is followed by a
    // refused probe while the leader is still running. A later group SIGKILL,
    // exact terminal leader observation and fresh empty group view close it.
    FakeOperations recovered;
    recovered.signal_results.push_back({0, 0});
    recovered.signal_results.push_back({-1, EPERM});
    recovered.signal_results.push_back({0, 0});
    recovered.observations.push_back(observation(0));
    recovered.observations.push_back(observation());
    recovered.group_snapshots.push_back(empty);
    recovered.waits.push_back({child_id, 0, SIGKILL});
    Lifetime recovered_child(child_id, true, recovered);
    bool tree = false;
    recovered_child.terminate(Milliseconds(10), tree);
    require(recovered_child.group_cleanup_pending() && tree,
        "transient group EPERM was not deferred through SIGKILL");
    require(recovered_child.observe() == ChildObservation::terminal &&
        recovered_child.resolve_group_cleanup() && recovered_child.reap(),
        "fresh post-terminal empty group proof did not close cleanup");
    require(recovered_child.error().empty() && recovered.unsafe_signals == 0 &&
        recovered.trace == std::vector<std::string>{
            "signal-" + std::to_string(SIGTERM), "signal-0", "observe-unreaped",
            "signal-" + std::to_string(SIGKILL), "observe-unreaped",
            "observe-group", "consume"},
        "recovered group cleanup ordering changed");

    for (const auto unresolved : {incomplete, live, foreign}) {
        FakeOperations operations;
        operations.signal_results.push_back({0, 0});
        operations.signal_results.push_back({-1, EPERM});
        operations.signal_results.push_back({0, 0});
        operations.observations.push_back(observation(0));
        operations.observations.push_back(observation());
        operations.group_snapshots.push_back(unresolved);
        operations.waits.push_back({child_id, 0, SIGKILL});
        Lifetime child(child_id, true, operations);
        tree = false;
        child.terminate(Milliseconds(10), tree);
        require(child.observe() == ChildObservation::terminal &&
            !child.resolve_group_cleanup() && child.reap(),
            "unresolved group proof prevented exact leader reap");
        require(tree && !child.error().empty() && operations.trace.back() == "consume" &&
            operations.unsafe_signals == 0,
            "live/incomplete final group observation was admitted");
    }

    // No final group observation is also fail-closed even after a successful
    // SIGKILL and exact leader reap.
    FakeOperations no_final;
    no_final.signal_results.push_back({0, 0});
    no_final.signal_results.push_back({-1, EPERM});
    no_final.signal_results.push_back({0, 0});
    no_final.observations.push_back(observation(0));
    no_final.observations.push_back(observation());
    no_final.waits.push_back({child_id, 0, SIGKILL});
    Lifetime no_final_child(child_id, true, no_final);
    tree = false;
    no_final_child.terminate(Milliseconds(10), tree);
    require(no_final_child.observe() == ChildObservation::terminal && no_final_child.reap() &&
        tree && !no_final_child.error().empty() &&
        std::find(no_final.trace.begin(), no_final.trace.end(), "observe-group") ==
            no_final.trace.end(),
        "missing final group observation was treated as proof");

    // A pre-terminal caller cannot inspect or clear the group state. Only a
    // fresh query after exact leader termination may resolve the pending EPERM.
    FakeOperations delayed;
    delayed.signal_results.push_back({0, 0});
    delayed.signal_results.push_back({-1, EPERM});
    delayed.signal_results.push_back({0, 0});
    delayed.observations.push_back(observation(0));
    delayed.observations.push_back(observation());
    delayed.group_snapshots.push_back(empty);
    delayed.waits.push_back({child_id, 0, SIGKILL});
    Lifetime delayed_child(child_id, true, delayed);
    tree = false;
    delayed_child.terminate(Milliseconds(10), tree);
    const auto before_group = delayed.trace.size();
    require(!delayed_child.resolve_group_cleanup() && delayed.trace.size() == before_group,
        "pre-terminal group observation was attempted");
    require(delayed_child.observe() == ChildObservation::terminal &&
        delayed_child.resolve_group_cleanup() && delayed_child.reap() &&
        delayed_child.error().empty(),
        "post-terminal group observation did not recover deferred cleanup");

    FakeOperations running;
    running.signal_results.push_back({0, 0});
    running.signal_results.push_back({-1, EPERM});
    running.signal_results.push_back({0, 0});
    running.observations.push_back(observation(0));
    running.group_snapshots.push_back(empty);
    running.waits.push_back({child_id, 0, SIGKILL});
    Lifetime running_child(child_id, true, running);
    tree = false;
    running_child.terminate(Milliseconds(10), tree);
    require(!running_child.resolve_group_cleanup() && running_child.reap() &&
        !running_child.error().empty() && !running.group_snapshots.empty(),
        "empty group view bypassed terminal leader admission");

    FakeOperations deadline_limited;
    deadline_limited.signal_results.push_back({0, 0});
    deadline_limited.signal_results.push_back({-1, EPERM});
    deadline_limited.signal_results.push_back({0, 0});
    deadline_limited.observations.push_back(observation(0));
    deadline_limited.observations.push_back(observation());
    deadline_limited.group_snapshots.push_back(incomplete);
    deadline_limited.group_snapshots.push_back(empty);
    deadline_limited.waits.push_back({child_id, 0, SIGKILL});
    Lifetime deadline_child(child_id, true, deadline_limited);
    tree = false;
    deadline_child.terminate(Milliseconds(10), tree);
    require(deadline_child.observe() == ChildObservation::terminal,
        "deadline regression terminal precondition missing");
    deadline_child.resolve_group_cleanup_until(
        deadline_limited.clock + Milliseconds(10));
    require(deadline_child.group_cleanup_pending() &&
        deadline_limited.group_snapshots.size() == 1 &&
        deadline_limited.clock == std::chrono::steady_clock::time_point {} + Milliseconds(20),
        "group cleanup query crossed the shared deadline");
    require(deadline_child.reap() && deadline_limited.group_snapshots.size() == 1 &&
        deadline_limited.trace.back() == "consume" && deadline_limited.unsafe_signals == 0,
        "reap retried group cleanup after deadline or consumption");

    // An exact sole terminal leader is the existing narrow exception. An empty
    // or multirow terminal group without a successful group signal is not.
    FakeOperations sole;
    sole.signal_results.push_back({-1, EPERM});
    sole.observations.push_back(observation());
    sole.group_snapshots.push_back(sole_terminal_leader);
    sole.waits.push_back({child_id, 0, 0});
    Lifetime sole_child(child_id, true, sole);
    require(sole_child.observe() == ChildObservation::terminal,
        "sole-terminal leader precondition missing");
    tree = false;
    require(sole_child.finish(Milliseconds(0), tree) && !tree && sole_child.error().empty(),
        "sole-terminal leader exception changed tree accounting");

    const std::array<ChildGroupSnapshotRow, 2> terminal_rows {{
        {child_id, child_id, true}, {child_id + 1, child_id, true}
    }};
    for (const auto unsignalled : {empty, classify_child_group_snapshot(
             child_id, terminal_rows.data(), terminal_rows.size())}) {
        FakeOperations operations;
        operations.signal_results.push_back({-1, EPERM});
        operations.signal_results.push_back({-1, ESRCH});
        operations.observations.push_back(observation());
        operations.group_snapshots.push_back(unsignalled);
        operations.waits.push_back({child_id, 0, 0});
        Lifetime child(child_id, true, operations);
        require(child.observe() == ChildObservation::terminal,
            "unsignalled terminal precondition missing");
        tree = false;
        require(child.finish(Milliseconds(0), tree) && !tree && !child.error().empty(),
            "group without a successful signal was admitted");
    }

    FakeOperations repeated;
    repeated.signal_results.push_back({-1, EPERM});
    repeated.signal_results.push_back({-1, EPERM});
    repeated.observations.push_back(observation(0));
    repeated.observations.push_back(observation(0));
    repeated.waits.push_back({child_id, 0, SIGKILL});
    Lifetime repeated_child(child_id, true, repeated);
    tree = false;
    require(repeated_child.finish(Milliseconds(0), tree),
        "repeated EPERM lost exact leader reap");
    const std::string marker = "child termination/probe failed (errno " +
        std::to_string(EPERM) + ")";
    require(repeated_child.error().find(marker) != std::string::npos &&
        repeated_child.error().find(marker, repeated_child.error().find(marker) + 1) ==
            std::string::npos,
        "multiple EPERMs emitted duplicate final diagnostics");
    require(repeated.trace.back() == "consume" && repeated.unsafe_signals == 0,
        "group operation occurred after exact wait consumption began");
}

int main()
{
    try {
        terminal_case(0, CLD_EXITED, 0, ProcessTermination::exited);
        terminal_case(23 << 8, CLD_EXITED, 23, ProcessTermination::exited);
        terminal_case(SIGKILL, CLD_KILLED, 128 + SIGKILL, ProcessTermination::crashed);
        terminal_case(SIGABRT | 0x80, CLD_DUMPED, 128 + SIGABRT, ProcessTermination::crashed);
        group_snapshot_classification();
        consuming_failures();
        interruption_and_running_outcomes();
        unknown_observations();
        disposition_admission();
        exec_failure_and_cleanup_limits();
        deferred_group_cleanup_outcomes();
        std::cout << "POSIX production child lifecycle injected checks passed\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
