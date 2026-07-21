// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_EXECUTION_H
#define FACMAN_FACTORIO_EXECUTION_H

#include "fl_process_supervisor.h"
#include "fl_result.h"
#include "fl_services.h"

#include <chrono>
#include <filesystem>
#include <functional>
#include <string>
#include <vector>

namespace facman::factorio::launch {

enum class ExecutionAuthority {
    none,
    foundation_test_process,
};

struct LaunchLifecycleEvent {
    std::string state;
    std::string occurred_at;
    std::string detail;
};

struct LaunchExecutionRequest {
    std::string instance_id;
    std::filesystem::path instance_root;
    std::filesystem::path executable;
    std::vector<std::string> arguments;
    std::filesystem::path working_directory;
    std::vector<facman::platform::ProcessEnvironmentEntry> environment;
    std::string execution_mode = "foundation_test";
    std::string immutable_plan_identity;
    ExecutionAuthority authority = ExecutionAuthority::none;
    std::chrono::milliseconds timeout {std::chrono::seconds(30)};
    std::size_t maximum_standard_output = 1024U * 1024U;
    std::size_t maximum_standard_error = 1024U * 1024U;
    std::function<bool()> cancellation_requested;
};

struct LaunchSessionResult {
    std::string session_id;
    std::string instance_id;
    std::string execution_mode;
    std::string immutable_plan_identity;
    std::filesystem::path journal_path;
    std::filesystem::path working_directory;
    std::vector<LaunchLifecycleEvent> lifecycle;
    facman::platform::ProcessResult process;
    std::string current_state;
    std::string recovered_from_state;
    bool successful = false;
    bool recovery_required = false;
    bool complete = false;
};

struct LaunchRecoveryReport {
    std::size_t examined = 0;
    std::size_t recovered = 0;
    std::size_t still_running = 0;
    std::size_t failed = 0;
};

class ProcessSupervisor {
public:
    virtual ~ProcessSupervisor() = default;
    virtual facman::platform::ProcessResult run(
        const facman::platform::ProcessRequest& request) = 0;
};

class PlatformProcessSupervisor final : public ProcessSupervisor {
public:
    facman::platform::ProcessResult run(
        const facman::platform::ProcessRequest& request) override;
};

class LaunchExecutionService {
public:
    LaunchExecutionService(
        ProcessSupervisor& supervisor,
        facman::core::Clock& clock,
        facman::core::IdGenerator& ids);

    facman::core::Result<LaunchSessionResult> execute(
        const LaunchExecutionRequest& request);

private:
    ProcessSupervisor& supervisor_;
    facman::core::Clock& clock_;
    facman::core::IdGenerator& ids_;
};

std::string launch_session_json(const LaunchSessionResult& session);

facman::core::Result<LaunchRecoveryReport> recover_interrupted_launch_sessions(
    const std::filesystem::path& instance_root,
    facman::core::Clock& clock,
    facman::core::IdGenerator& ids);

} // namespace facman::factorio::launch

#endif
