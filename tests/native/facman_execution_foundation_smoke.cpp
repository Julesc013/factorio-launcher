// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_system_services.h"
#include "flb_factorio_execution.h"
#include "flb_factorio_launch_plan.h"
#include "last_run_provider.h"

#include <atomic>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>

namespace {
namespace fs = std::filesystem;
namespace launch = facman::factorio::launch;
namespace application = facman::factorio::application;

struct TemporaryTree {
    fs::path path;
    ~TemporaryTree() { std::error_code ignored; fs::remove_all(path, ignored); }
};

launch::LaunchExecutionRequest request_for(
    const fs::path& root,
    const std::string& mode,
    std::chrono::milliseconds timeout = std::chrono::seconds(5))
{
    launch::LaunchExecutionRequest request;
    request.instance_id = "foundation-test";
    request.instance_root = root;
    request.executable = fs::path(FACMAN_TEST_PROCESS_PROBE_PATH);
    request.arguments = {"--mode", mode};
    request.working_directory = root;
    request.authority = launch::ExecutionAuthority::foundation_test_process;
    request.timeout = timeout;
    return request;
}

void use_authoritative_journal(
    launch::LaunchExecutionRequest& request,
    const fs::path& workspace,
    const std::string& runnable)
{
    request.ulk_session_journal_root = application::ulk_session_journal_root(workspace);
    request.runnable_reference = runnable;
    request.relaunch_reference = "relaunch:" + request.instance_id;
}

class PendingSupervisor final : public launch::ProcessSupervisor {
public:
    facman::platform::ProcessResult run(
        const facman::platform::ProcessRequest& request) override
    {
        facman::platform::ProcessResult result;
        result.identity.process_id = 41001U;
        result.identity.platform = "fixture";
        result.identity.stable_start_identity = "pending-start";
        if (request.started) request.started(result.identity);
        result.termination = facman::platform::ProcessTermination::pending;
        result.error = "fixture transport lost after dispatch";
        return result;
    }
};

class PreDispatchSupervisor final : public launch::ProcessSupervisor {
public:
    explicit PreDispatchSupervisor(bool observe_cancellation)
        : observe_cancellation_(observe_cancellation) {}

    facman::platform::ProcessResult run(
        const facman::platform::ProcessRequest& request) override
    {
        facman::platform::ProcessResult result;
        if (observe_cancellation_ && request.cancellation_requested) {
            (void)request.cancellation_requested();
            result.termination = facman::platform::ProcessTermination::cancelled;
            result.error = "fixture cancelled before dispatch";
        } else {
            result.termination = facman::platform::ProcessTermination::start_failed;
            result.error = "fixture refused before effects";
        }
        return result;
    }

private:
    bool observe_cancellation_;
};

class RepairingSupervisor final : public launch::ProcessSupervisor {
public:
    explicit RepairingSupervisor(fs::path blocked_root)
        : blocked_root_(std::move(blocked_root)) {}

    facman::platform::ProcessResult run(
        const facman::platform::ProcessRequest& request) override
    {
        facman::platform::ProcessResult result;
        result.identity.process_id = 41002U;
        result.identity.platform = "fixture";
        result.identity.stable_start_identity = "recovery-start";
        std::error_code ignored;
        fs::create_directories(blocked_root_.parent_path(), ignored);
        {
            std::ofstream blocker(blocked_root_, std::ios::binary | std::ios::trunc);
            blocker << "block authoritative journal root\n";
        }
        if (request.started) request.started(result.identity);
        fs::remove(blocked_root_, ignored);
        result.termination = facman::platform::ProcessTermination::cancelled;
        result.process_tree_terminated = true;
        result.error = "fixture stopped after authoritative running write failure";
        return result;
    }

private:
    fs::path blocked_root_;
};

class SuccessfulSupervisor final : public launch::ProcessSupervisor {
public:
    facman::platform::ProcessResult run(
        const facman::platform::ProcessRequest& request) override
    {
        ++calls;
        facman::platform::ProcessResult result;
        result.identity = {42001U, "fixture-process-v1", "fixture-process-v1:42001:1"};
        if (request.started) request.started(result.identity);
        result.termination = facman::platform::ProcessTermination::exited;
        result.exit_code = 0;
        result.native_status = 0;
        return result;
    }

    std::size_t calls = 0;
};

bool has_state(const launch::LaunchSessionResult& session, const std::string& state)
{
    for (const auto& event : session.lifecycle) if (event.state == state) return true;
    return false;
}

std::string read_text(const fs::path& path)
{
    std::ifstream input(path, std::ios::binary);
    return std::string((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
}

fs::path write_interrupted_session(
    const fs::path& instance_root,
    const std::string& name,
    const std::string& state,
    facman::platform::ProcessIdentity identity)
{
    const fs::path journal_root = instance_root / "state" / "run-sessions";
    std::error_code error;
    fs::create_directories(journal_root, error);
    if (error) return {};
    launch::LaunchSessionResult session;
    session.session_id = name;
    session.operation_id = "operation-" + name;
    session.attempt_id = "attempt-" + name;
    session.runnable_reference = "facman.instance:" + name;
    session.relaunch_reference = "relaunch:" + name;
    session.instance_id = "foundation-test";
    session.execution_mode = "foundation_test";
    session.immutable_plan_identity = "plan-" + name;
    session.current_state = state;
    session.journal_path = journal_root / (name + ".launch-session.v1.json");
    session.working_directory = instance_root;
    session.lifecycle.push_back({"requested", "2026-09-10T00:00:00Z", "original lifecycle event"});
    if (state != "requested") {
        session.lifecycle.push_back({state, "2026-09-10T00:00:01Z", "interrupted lifecycle event"});
    }
    session.process.identity = std::move(identity);
    session.process.termination = facman::platform::ProcessTermination::pending;
    session.operation_outcome = "outcome_unknown";
    session.recovery_required = true;
    std::string detail;
    if (!facman::base::write_text_new_atomic(
            session.journal_path, launch::launch_session_json(session) + "\n", detail)) return {};
    return session.journal_path;
}

int process_failure(
    int code,
    const char* stage,
    const facman::core::Result<launch::LaunchSessionResult>& result)
{
    std::cerr << stage << " mismatch";
    if (!result) {
        std::cerr << ": refused=" << result.error().code << ": " << result.error().message
                  << " (" << result.error().detail << ")\n";
        return code;
    }
    std::cerr << ": termination="
              << facman::platform::process_termination_name(result.value().process.termination)
              << " exit=" << result.value().process.exit_code
              << " tree_terminated=" << result.value().process.process_tree_terminated
              << " complete=" << result.value().complete
              << " recovery=" << result.value().recovery_required
              << " state=" << result.value().current_state
              << " process_error=" << result.value().process.error << '\n';
    return code;
}

} // namespace

int main()
{
    facman::platform::RealClock clock;
    facman::platform::RandomIdGenerator ids;
    TemporaryTree tree {
        fs::temp_directory_path() / ids.next("facman-execution-foundation")};
    std::error_code error;
    fs::create_directories(tree.path, error);
    if (error) return 1;
    launch::PlatformProcessSupervisor supervisor;
    launch::LaunchExecutionService service(supervisor, clock, ids);

    auto success_request = request_for(tree.path, "success");
    use_authoritative_journal(
        success_request, tree.path, "facman.instance:foundation-success");
    success_request.arguments.push_back("value with space");
    success_request.arguments.push_back("&echo escaped>shell-escaped.txt");
    auto success = service.execute(success_request);
    if (!success) {
        std::cerr << "success launch refused: " << success.error().code << ": "
                  << success.error().message << " (" << success.error().detail << ")\n";
        return 2;
    }
    auto last_run = application::make_ulk_session_last_run_provider(tree.path);
    const auto successful_last_run = last_run->last_run(success_request.runnable_reference);
    if (successful_last_run.state !=
            application::LastRunAuthorityState::authoritative_record_available ||
        successful_last_run.record_json.find("\"outcome\":\"completed\"") ==
            std::string::npos ||
        !success.value().authoritative_running_recorded ||
        !success.value().authoritative_last_run_recorded ||
        success.value().operation_outcome != "completed") {
        std::cerr << "authoritative success mismatch: state="
                  << application::last_run_authority_state_name(successful_last_run.state)
                  << " detail=" << successful_last_run.detail
                  << " record=" << successful_last_run.record_json
                  << " running_recorded=" << success.value().authoritative_running_recorded
                  << " terminal_recorded=" << success.value().authoritative_last_run_recorded
                  << " outcome=" << success.value().operation_outcome
                  << " journal_error=" << success.value().authoritative_journal_error << '\n';
        return 16;
    }
    auto restarted_last_run = application::make_ulk_session_last_run_provider(tree.path);
    if (restarted_last_run->last_run(success_request.runnable_reference).state !=
        application::LastRunAuthorityState::authoritative_record_available) return 17;
    const bool restart_identity_missing =
        !success.value().process.identity.restart_safe();
    if (!success.value().successful || !success.value().complete ||
        success.value().recovery_required || success.value().current_state != "complete" ||
        restart_identity_missing ||
        success.value().process.standard_output.find("value with space") == std::string::npos ||
        success.value().process.standard_output.find("&echo escaped>shell-escaped.txt") == std::string::npos ||
        fs::exists(tree.path / "shell-escaped.txt") ||
        !has_state(success.value(), "requested") || !has_state(success.value(), "preflighted") ||
        !has_state(success.value(), "authorised") || !has_state(success.value(), "running") ||
        !has_state(success.value(), "exited") || !fs::is_regular_file(success.value().journal_path)) {
        std::cerr << "success launch mismatch: termination="
                  << facman::platform::process_termination_name(success.value().process.termination)
                  << " exit=" << success.value().process.exit_code
                  << " complete=" << success.value().complete
                  << " recovery=" << success.value().recovery_required
                  << " state=" << success.value().current_state
                  << " restart_safe=" << success.value().process.identity.restart_safe()
                  << " process_platform=" << success.value().process.identity.platform
                  << " process_id=" << success.value().process.identity.process_id
                  << " successful=" << success.value().successful
                  << " shell_file=" << fs::exists(tree.path / "shell-escaped.txt")
                  << " requested=" << has_state(success.value(), "requested")
                  << " preflighted=" << has_state(success.value(), "preflighted")
                  << " authorised=" << has_state(success.value(), "authorised")
                  << " running=" << has_state(success.value(), "running")
                  << " exited=" << has_state(success.value(), "exited")
                  << " journal=" << fs::is_regular_file(success.value().journal_path)
                  << " stdout=" << success.value().process.standard_output
                  << " stderr=" << success.value().process.standard_error
                  << " process_error=" << success.value().process.error << '\n';
        return 2;
    }
    auto success_json = facman::core::json::parse(read_text(success.value().journal_path));
    if (!success_json || success_json.value().find("current_state") == nullptr ||
        success_json.value().find("current_state")->string_value().value() != "complete") return 3;

    auto nonzero_request = request_for(tree.path, "nonzero");
    use_authoritative_journal(
        nonzero_request, tree.path, "facman.instance:foundation-nonzero");
    auto nonzero = service.execute(nonzero_request);
    if (!nonzero || nonzero.value().successful || !nonzero.value().complete ||
        nonzero.value().process.exit_code != 17 || !has_state(nonzero.value(), "exited"))
        return process_failure(4, "nonzero launch", nonzero);
    const auto nonzero_last_run = last_run->last_run(nonzero_request.runnable_reference);
    if (nonzero_last_run.state !=
            application::LastRunAuthorityState::authoritative_record_available ||
        nonzero_last_run.record_json.find("\"exit_code\":17") == std::string::npos ||
        nonzero_last_run.record_json.find("\"outcome\":\"completed\"") ==
            std::string::npos) return 18;

    auto timeout = service.execute(request_for(tree.path, "hang", std::chrono::milliseconds(100)));
    if (!timeout || timeout.value().process.termination != facman::platform::ProcessTermination::timed_out ||
        !timeout.value().complete || !has_state(timeout.value(), "timed_out"))
        return process_failure(5, "timeout launch", timeout);

    std::atomic<bool> cancel {false};
    auto cancelled_request = request_for(tree.path, "hang");
    use_authoritative_journal(
        cancelled_request, tree.path, "facman.instance:foundation-cancelled");
    cancelled_request.cancellation_requested = [&]() { return cancel.load(); };
    // Request cancellation only after the supervisor has confirmed exec and
    // published the process identity. A fixed delay can expire while a loaded
    // runner is still closing inherited descriptors before exec, where the
    // correct fail-closed result is pending rather than cancelled.
    bool live_identity_observed = false;
    cancelled_request.process_started = [&](const facman::platform::ProcessIdentity& identity) {
#if defined(_WIN32)
        const std::string expected_platform = "windows-process-v1";
#elif defined(__APPLE__)
        const std::string expected_platform = "darwin-process-v1";
#elif defined(__linux__)
        const std::string expected_platform = "linux-process-v1";
#else
        const std::string expected_platform;
#endif
        const std::string expected_prefix = expected_platform.empty()
            ? std::string {}
            : expected_platform + ":" + std::to_string(identity.process_id) + ":";
        live_identity_observed = !expected_platform.empty() &&
            identity.platform == expected_platform &&
            identity.stable_start_identity.rfind(expected_prefix, 0) == 0 &&
            facman::platform::observe_process_identity(identity) ==
                facman::platform::ProcessIdentityObservation::matching_alive;
        cancel.store(true);
    };
    auto cancelled = service.execute(cancelled_request);
    if (!cancelled || cancelled.value().process.termination != facman::platform::ProcessTermination::cancelled ||
        !cancelled.value().complete || !has_state(cancelled.value(), "cancelled") ||
        !live_identity_observed)
        return process_failure(6, "cancelled launch", cancelled);
    const auto cancelled_last_run = last_run->last_run(cancelled_request.runnable_reference);
    if (cancelled_last_run.state !=
            application::LastRunAuthorityState::authoritative_record_available ||
        cancelled_last_run.record_json.find(
            "\"outcome\":\"cancellation_requested_but_completed\"") ==
            std::string::npos) return 19;

    auto excessive_request = request_for(tree.path, "excessive-output");
    excessive_request.maximum_standard_output = 4096;
    auto excessive = service.execute(excessive_request);
    if (!excessive || excessive.value().process.termination != facman::platform::ProcessTermination::output_limit ||
        excessive.value().process.standard_output.size() != 4096 ||
        !has_state(excessive.value(), "killed"))
        return process_failure(7, "output-limit launch", excessive);

    auto ignored = service.execute(request_for(tree.path, "ignore-graceful", std::chrono::milliseconds(100)));
    if (!ignored || ignored.value().process.termination != facman::platform::ProcessTermination::timed_out ||
        !ignored.value().process.process_tree_terminated)
        return process_failure(8, "forced-kill launch", ignored);

    auto crashed = service.execute(request_for(tree.path, "crash"));
    if (!crashed || crashed.value().process.termination != facman::platform::ProcessTermination::crashed ||
        !has_state(crashed.value(), "crashed"))
        return process_failure(9, "crash launch", crashed);

    const fs::path child_marker = tree.path / "child-survivor.txt";
    auto child_request = request_for(tree.path, "spawn-child", std::chrono::milliseconds(100));
    child_request.environment.push_back({"FACMAN_PROCESS_PROBE_MARKER", child_marker.string()});
    auto child = service.execute(child_request);
    std::this_thread::sleep_for(std::chrono::milliseconds(1000));
    if (!child || child.value().process.termination != facman::platform::ProcessTermination::timed_out ||
        fs::exists(child_marker)) {
        if (fs::exists(child_marker)) std::cerr << "child-tree launch mismatch: survivor marker exists\n";
        return process_failure(10, "child-tree launch", child);
    }

    auto roots = service.execute(request_for(tree.path, "write-root"));
    if (!roots || !roots.value().successful || !fs::is_regular_file(tree.path / "probe-write.txt") ||
        !fs::is_regular_file(tree.path / "probe-working-directory.txt")) return 11;

    auto outside = request_for(tree.path, "success");
    outside.working_directory = tree.path.parent_path();
    auto escaped = service.execute(outside);
    if (escaped || escaped.error().code != "launch_working_directory_outside_instance") return 12;

    auto unauthorised = request_for(tree.path, "success");
    unauthorised.authority = launch::ExecutionAuthority::none;
    auto refused = service.execute(unauthorised);
    if (refused || refused.error().code != "real_play_authority_required") return 13;

    const fs::path unknown_workspace = tree.path / "unknown-workspace";
    fs::create_directories(unknown_workspace, error);
    PendingSupervisor pending_supervisor;
    launch::LaunchExecutionService pending_service(pending_supervisor, clock, ids);
    auto unknown_request = request_for(unknown_workspace, "success");
    use_authoritative_journal(
        unknown_request, unknown_workspace, "facman.instance:foundation-unknown");
    auto unknown = pending_service.execute(unknown_request);
    if (!unknown || unknown.value().operation_outcome != "outcome_unknown" ||
        !unknown.value().authoritative_running_recorded ||
        !unknown.value().authoritative_last_run_recorded) {
        return process_failure(20, "unknown-outcome launch", unknown);
    }
    auto unknown_provider = application::make_ulk_session_last_run_provider(unknown_workspace);
    if (unknown_provider->last_run(unknown_request.runnable_reference).state !=
        application::LastRunAuthorityState::outcome_unknown) return 21;
    auto restarted_unknown = application::make_ulk_session_last_run_provider(unknown_workspace);
    if (restarted_unknown->last_run(unknown_request.runnable_reference).state !=
        application::LastRunAuthorityState::outcome_unknown) return 22;

    const fs::path recovery_workspace = tree.path / "recovery-workspace";
    fs::create_directories(recovery_workspace, error);
    if (error) return 23;
    const fs::path blocked_root = application::ulk_session_journal_root(recovery_workspace);
    RepairingSupervisor repairing_supervisor(blocked_root);
    launch::LaunchExecutionService recovery_service(repairing_supervisor, clock, ids);
    auto recovery_request = request_for(recovery_workspace, "success");
    use_authoritative_journal(
        recovery_request, recovery_workspace, "facman.instance:foundation-recovery");
    auto recovery = recovery_service.execute(recovery_request);
    if (!recovery || recovery.value().operation_outcome != "recovery_required" ||
        recovery.value().authoritative_running_recorded ||
        !recovery.value().authoritative_last_run_recorded ||
        !recovery.value().recovery_required || recovery.value().complete) {
        return process_failure(24, "recovery-required launch", recovery);
    }
    auto recovery_provider = application::make_ulk_session_last_run_provider(recovery_workspace);
    if (recovery_provider->last_run(recovery_request.runnable_reference).state !=
        application::LastRunAuthorityState::recovery_required) return 25;

    const fs::path refused_workspace = tree.path / "refused-workspace";
    fs::create_directories(refused_workspace, error);
    if (error) return 26;
    PreDispatchSupervisor refused_supervisor(false);
    launch::LaunchExecutionService refused_service(refused_supervisor, clock, ids);
    auto refused_request = request_for(refused_workspace, "success");
    use_authoritative_journal(
        refused_request, refused_workspace, "facman.instance:foundation-refused");
    auto refused_dispatch = refused_service.execute(refused_request);
    if (!refused_dispatch || refused_dispatch.value().operation_outcome !=
            "refused_before_effects" ||
        refused_dispatch.value().authoritative_running_recorded ||
        !refused_dispatch.value().authoritative_last_run_recorded) {
        return process_failure(27, "refused-before-effects launch", refused_dispatch);
    }
    auto refused_provider = application::make_ulk_session_last_run_provider(refused_workspace);
    const auto refused_last_run = refused_provider->last_run(refused_request.runnable_reference);
    if (refused_last_run.state !=
            application::LastRunAuthorityState::authoritative_record_available ||
        refused_last_run.record_json.find("\"outcome\":\"refused_before_effects\"") ==
            std::string::npos) return 28;

    const fs::path pre_cancel_workspace = tree.path / "pre-cancel-workspace";
    fs::create_directories(pre_cancel_workspace, error);
    if (error) return 29;
    PreDispatchSupervisor pre_cancel_supervisor(true);
    launch::LaunchExecutionService pre_cancel_service(pre_cancel_supervisor, clock, ids);
    auto pre_cancel_request = request_for(pre_cancel_workspace, "success");
    pre_cancel_request.cancellation_requested = []() { return true; };
    use_authoritative_journal(
        pre_cancel_request, pre_cancel_workspace, "facman.instance:foundation-pre-cancel");
    auto pre_cancel = pre_cancel_service.execute(pre_cancel_request);
    if (!pre_cancel || pre_cancel.value().operation_outcome !=
            "cancelled_before_dispatch" ||
        pre_cancel.value().authoritative_running_recorded ||
        !pre_cancel.value().authoritative_last_run_recorded) {
        return process_failure(30, "cancelled-before-dispatch launch", pre_cancel);
    }
    auto pre_cancel_provider = application::make_ulk_session_last_run_provider(pre_cancel_workspace);
    const auto pre_cancel_last_run =
        pre_cancel_provider->last_run(pre_cancel_request.runnable_reference);
    if (pre_cancel_last_run.state !=
            application::LastRunAuthorityState::authoritative_record_available ||
        pre_cancel_last_run.record_json.find(
            "\"outcome\":\"cancelled_before_dispatch\"") == std::string::npos) return 31;

#if defined(FACMAN_ENABLE_ISOLATED_ENGINEERING_EXECUTION)
    const fs::path engineering_source = tree.path / "engineering-source";
    const fs::path engineering_instance = tree.path / "engineering-instance";
    fs::create_directories(engineering_source, error);
    fs::create_directories(engineering_instance, error);
    if (error) return 33;
    const fs::path engineering_executable =
        engineering_source / fs::path(FACMAN_TEST_PROCESS_PROBE_PATH).filename();
    fs::copy_file(
        fs::path(FACMAN_TEST_PROCESS_PROBE_PATH),
        engineering_executable,
        fs::copy_options::none,
        error);
    if (error) return 34;
    auto engineering = request_for(engineering_instance, "success");
    engineering.executable = engineering_executable;
    engineering.engineering_task_root = tree.path;
    engineering.engineering_source_root = engineering_source;
    engineering.execution_mode = "isolated_engineering";
    engineering.engineering_route_id =
        "facman.engineering.play.windows-x64.factorio-fixture.v1";
    engineering.expected_executable_sha256 =
        facman::base::sha256_hex_file(engineering_executable);
    engineering.authority = launch::ExecutionAuthority::isolated_engineering_process;
    auto engineering_result = service.execute(engineering);
    if (!engineering_result || !engineering_result.value().successful ||
        engineering_result.value().engineering_route_id !=
            engineering.engineering_route_id) {
        return process_failure(35, "isolated engineering launch", engineering_result);
    }
    engineering.expected_executable_sha256 = std::string(64U, '0');
    const auto wrong_engineering_identity = service.execute(engineering);
    if (wrong_engineering_identity ||
        wrong_engineering_identity.error().code !=
            "engineering_executable_identity_mismatch") return 36;
#endif

    auto invalid_contract = request_for(tree.path, "success");
    use_authoritative_journal(
        invalid_contract, tree.path, std::string(4097U, 'x'));
    const auto invalid = service.execute(invalid_contract);
    if (invalid || invalid.error().code != "ulk_session_contract_invalid") return 32;

    const facman::platform::ProcessIdentity interrupted_identity {
        4294967294U, "fixture-process-v1", "fixture-process-v1:4294967294:1"};

    const fs::path mismatch_root = tree.path / "recovery-pid-reuse";
    fs::create_directories(mismatch_root, error);
    const fs::path interrupted = write_interrupted_session(
        mismatch_root, "interrupted", "running", interrupted_identity);
    if (interrupted.empty()) return 14;
    bool mismatch_observed = false;
    auto recovered = launch::recover_interrupted_launch_sessions(
        mismatch_root, clock, ids,
        [&](const facman::platform::ProcessIdentity& identity) {
            mismatch_observed = identity.process_id == interrupted_identity.process_id &&
                identity.stable_start_identity == interrupted_identity.stable_start_identity;
            return facman::platform::ProcessIdentityObservation::not_matching_or_exited;
        });
    const std::string recovered_text = read_text(interrupted);
    if (!recovered || !mismatch_observed || recovered.value().recovered != 1 ||
        recovered.value().still_running != 0 || recovered.value().inconclusive != 0 ||
        recovered_text.find("\"current_state\":\"complete\"") == std::string::npos ||
        recovered_text.find("\"recovered_from_state\":\"running\"") == std::string::npos ||
        recovered_text.find("\"operation_id\":\"operation-interrupted\"") == std::string::npos ||
        recovered_text.find("original lifecycle event") == std::string::npos ||
        recovered_text.find(interrupted_identity.stable_start_identity) == std::string::npos) return 15;

    const fs::path live_root = tree.path / "recovery-live";
    fs::create_directories(live_root, error);
    const fs::path live = write_interrupted_session(
        live_root, "live", "running", interrupted_identity);
    const std::string live_before = read_text(live);
    auto live_report = launch::recover_interrupted_launch_sessions(
        live_root, clock, ids,
        [](const facman::platform::ProcessIdentity&) {
            return facman::platform::ProcessIdentityObservation::matching_alive;
        });
    if (!live_report || live_report.value().still_running != 1 ||
        live_report.value().recovered != 0 || read_text(live) != live_before) return 37;

    const fs::path unknown_root = tree.path / "recovery-inconclusive";
    fs::create_directories(unknown_root, error);
    const fs::path unknown_journal = write_interrupted_session(
        unknown_root, "unknown", "starting", interrupted_identity);
    const std::string unknown_before = read_text(unknown_journal);
    auto unknown_report = launch::recover_interrupted_launch_sessions(
        unknown_root, clock, ids,
        [](const facman::platform::ProcessIdentity&) {
            return facman::platform::ProcessIdentityObservation::inconclusive;
        });
    if (!unknown_report || unknown_report.value().inconclusive != 1 ||
        unknown_report.value().recovered != 0 || read_text(unknown_journal) != unknown_before) return 38;

    const fs::path legacy_root = tree.path / "recovery-legacy";
    fs::create_directories(legacy_root, error);
    auto legacy_identity = interrupted_identity;
    legacy_identity.stable_start_identity.clear();
    const fs::path legacy = write_interrupted_session(
        legacy_root, "legacy", "running", legacy_identity);
    const std::string legacy_before = read_text(legacy);
    bool legacy_observer_called = false;
    auto legacy_report = launch::recover_interrupted_launch_sessions(
        legacy_root, clock, ids,
        [&](const facman::platform::ProcessIdentity&) {
            legacy_observer_called = true;
            return facman::platform::ProcessIdentityObservation::not_matching_or_exited;
        });
    if (!legacy_report || legacy_observer_called || legacy_report.value().inconclusive != 1 ||
        read_text(legacy) != legacy_before) return 39;

    const fs::path predispatch_root = tree.path / "recovery-predispatch";
    fs::create_directories(predispatch_root, error);
    const fs::path predispatch = write_interrupted_session(
        predispatch_root, "predispatch", "authorised", {});
    auto predispatch_report = launch::recover_interrupted_launch_sessions(
        predispatch_root, clock, ids,
        [](const facman::platform::ProcessIdentity&) {
            return facman::platform::ProcessIdentityObservation::inconclusive;
        });
    const std::string predispatch_text = read_text(predispatch);
    if (!predispatch_report || predispatch_report.value().recovered != 1 ||
        predispatch_text.find("\"operation_outcome\":\"refused_before_effects\"") ==
            std::string::npos) return 40;

    const fs::path automatic_root = tree.path / "recovery-before-launch";
    fs::create_directories(automatic_root, error);
    const fs::path automatic = write_interrupted_session(
        automatic_root, "automatic", "running", interrupted_identity);
    SuccessfulSupervisor successful_supervisor;
    launch::LaunchExecutionService recovering_service(
        successful_supervisor, clock, ids,
        [](const facman::platform::ProcessIdentity&) {
            return facman::platform::ProcessIdentityObservation::not_matching_or_exited;
        });
    auto automatic_request = request_for(automatic_root, "success");
    auto automatic_result = recovering_service.execute(automatic_request);
    if (!automatic_result || !automatic_result.value().successful ||
        successful_supervisor.calls != 1 ||
        read_text(automatic).find("\"current_state\":\"complete\"") == std::string::npos) return 41;

    const fs::path blocked_recovery_root = tree.path / "recovery-blocked-launch";
    fs::create_directories(blocked_recovery_root, error);
    (void)write_interrupted_session(
        blocked_recovery_root, "blocked", "running", interrupted_identity);
    SuccessfulSupervisor blocked_supervisor;
    launch::LaunchExecutionService blocked_service(
        blocked_supervisor, clock, ids,
        [](const facman::platform::ProcessIdentity&) {
            return facman::platform::ProcessIdentityObservation::inconclusive;
        });
    auto blocked_launch = blocked_service.execute(request_for(blocked_recovery_root, "success"));
    if (blocked_launch || blocked_launch.error().code != "prior_launch_recovery_incomplete" ||
        blocked_supervisor.calls != 0) return 42;

    const fs::path locked_root = tree.path / "recovery-concurrent";
    fs::create_directories(locked_root, error);
    launch::InstanceRunLock held_lock;
    const auto held = launch::acquire_instance_run_lock(locked_root, 300, held_lock);
    if (!held.acquired) return 43;
    SuccessfulSupervisor concurrent_supervisor;
    launch::LaunchExecutionService concurrent_service(concurrent_supervisor, clock, ids);
    auto concurrent = concurrent_service.execute(request_for(locked_root, "success"));
    std::string release_detail;
    const bool released = launch::release_instance_run_lock(held_lock, release_detail);
    if (concurrent || concurrent.error().code != "run_lock_contended" ||
        concurrent_supervisor.calls != 0 || !released) return 44;

    const fs::path link_root = tree.path / "recovery-link";
    const fs::path link_target_root = tree.path / "recovery-link-target";
    fs::create_directories(link_root / "state" / "run-sessions", error);
    fs::create_directories(link_target_root, error);
    const fs::path link_target = write_interrupted_session(
        link_target_root, "target", "authorised", {});
    const fs::path link = link_root / "state" / "run-sessions" / "linked.launch-session.v1.json";
    fs::create_symlink(link_target, link, error);
    if (!error) {
        const std::string target_before = read_text(link_target);
        auto link_report = launch::recover_interrupted_launch_sessions(link_root, clock, ids);
        if (!link_report || link_report.value().failed != 1 ||
            link_report.value().recovered != 0 || read_text(link_target) != target_before) return 45;
    }

    for (int linked_component = 0; linked_component < 2; ++linked_component) {
        const fs::path root = tree.path /
            (linked_component == 0 ? "recovery-linked-state" : "recovery-linked-root");
        const fs::path target = tree.path /
            (linked_component == 0 ? "recovery-linked-state-target" : "recovery-linked-root-target");
        const fs::path target_journal = write_interrupted_session(
            target, "target", "authorised", {});
        const std::string target_before = read_text(target_journal);
        fs::create_directories(root, error);
        error.clear();
        if (linked_component == 0) {
            fs::create_directory_symlink(target / "state", root / "state", error);
        } else {
            fs::create_directories(root / "state", error);
            if (!error) {
                fs::create_directory_symlink(
                    target / "state" / "run-sessions",
                    root / "state" / "run-sessions",
                    error);
            }
        }
        if (!error) {
            auto linked_report = launch::recover_interrupted_launch_sessions(root, clock, ids);
            if (linked_report || linked_report.error().code != "launch_recovery_root_unsafe" ||
                read_text(target_journal) != target_before) return 46 + linked_component;
        }
        error.clear();
    }
    return 0;
}
