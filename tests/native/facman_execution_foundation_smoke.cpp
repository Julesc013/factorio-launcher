// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_system_services.h"
#include "flb_factorio_execution.h"

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
    TemporaryTree tree {fs::temp_directory_path() / ids.next("facman-execution-foundation")};
    std::error_code error;
    fs::create_directories(tree.path, error);
    if (error) return 1;
    launch::PlatformProcessSupervisor supervisor;
    launch::LaunchExecutionService service(supervisor, clock, ids);

    auto success_request = request_for(tree.path, "success");
    success_request.arguments.push_back("value with space");
    success_request.arguments.push_back("&echo escaped>shell-escaped.txt");
    auto success = service.execute(success_request);
    if (!success) {
        std::cerr << "success launch refused: " << success.error().code << ": "
                  << success.error().message << " (" << success.error().detail << ")\n";
        return 2;
    }
    if (!success.value().successful || !success.value().complete ||
        success.value().recovery_required || success.value().current_state != "complete" ||
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
                  << " stdout=" << success.value().process.standard_output
                  << " stderr=" << success.value().process.standard_error
                  << " process_error=" << success.value().process.error << '\n';
        return 2;
    }
    auto success_json = facman::core::json::parse(read_text(success.value().journal_path));
    if (!success_json || success_json.value().find("current_state") == nullptr ||
        success_json.value().find("current_state")->string_value().value() != "complete") return 3;

    auto nonzero = service.execute(request_for(tree.path, "nonzero"));
    if (!nonzero || nonzero.value().successful || !nonzero.value().complete ||
        nonzero.value().process.exit_code != 17 || !has_state(nonzero.value(), "exited"))
        return process_failure(4, "nonzero launch", nonzero);

    auto timeout = service.execute(request_for(tree.path, "hang", std::chrono::milliseconds(100)));
    if (!timeout || timeout.value().process.termination != facman::platform::ProcessTermination::timed_out ||
        !timeout.value().complete || !has_state(timeout.value(), "timed_out"))
        return process_failure(5, "timeout launch", timeout);

    std::atomic<bool> cancel {false};
    auto cancelled_request = request_for(tree.path, "hang");
    cancelled_request.cancellation_requested = [&]() { return cancel.load(); };
    std::thread canceller([&]() {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        cancel.store(true);
    });
    auto cancelled = service.execute(cancelled_request);
    canceller.join();
    if (!cancelled || cancelled.value().process.termination != facman::platform::ProcessTermination::cancelled ||
        !cancelled.value().complete || !has_state(cancelled.value(), "cancelled"))
        return process_failure(6, "cancelled launch", cancelled);

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

    const fs::path interrupted_root = tree.path / "state" / "run-sessions";
    fs::create_directories(interrupted_root, error);
    const fs::path interrupted = interrupted_root / "interrupted.launch-session.v1.json";
    const std::string interrupted_text =
        "{\"schema\":\"factorio.launch_session.v1\",\"session_id\":\"interrupted\","
        "\"instance_id\":\"foundation-test\",\"execution_mode\":\"foundation_test\","
        "\"immutable_plan_identity\":\"test\",\"current_state\":\"running\","
        "\"working_directory\":" + facman::core::json::quote_string(tree.path.string()) + ","
        "\"process\":{\"identity\":{\"process_id\":4294967294,\"platform\":\"test\"}}}";
    std::string detail;
    if (!facman::base::write_text_new_atomic(interrupted, interrupted_text, detail)) return 14;
    auto recovered = launch::recover_interrupted_launch_sessions(tree.path, clock, ids);
    if (!recovered || recovered.value().recovered != 1 || recovered.value().still_running != 0 ||
        read_text(interrupted).find("\"current_state\":\"complete\"") == std::string::npos ||
        read_text(interrupted).find("\"recovered_from_state\":\"running\"") == std::string::npos) return 15;
    return 0;
}
