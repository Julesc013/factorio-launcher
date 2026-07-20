// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_PLATFORM_PROCESS_SUPERVISOR_H
#define FACMAN_PLATFORM_PROCESS_SUPERVISOR_H

#include <chrono>
#include <cstdint>
#include <filesystem>
#include <functional>
#include <string>
#include <vector>

namespace facman::platform {

struct ProcessEnvironmentEntry {
    std::string name;
    std::string value;
};

enum class ProcessTermination {
    pending,
    exited,
    cancelled,
    timed_out,
    output_limit,
    crashed,
    start_failed,
};

const char* process_termination_name(ProcessTermination value) noexcept;

struct ProcessIdentity {
    std::uint64_t process_id = 0;
    std::string platform;
};

struct ProcessRequest {
    std::filesystem::path executable;
    std::vector<std::string> arguments;
    std::filesystem::path working_directory;
    std::vector<ProcessEnvironmentEntry> environment;
    bool inherit_environment = true;
    std::string standard_input;
    std::chrono::milliseconds timeout {std::chrono::minutes(5)};
    std::chrono::milliseconds termination_grace_period {std::chrono::milliseconds(250)};
    std::size_t maximum_standard_output = 16U * 1024U * 1024U;
    std::size_t maximum_standard_error = 1024U * 1024U;
    std::function<bool()> cancellation_requested;
    std::function<void(const ProcessIdentity&)> started;
};

struct ProcessResult {
    ProcessTermination termination = ProcessTermination::pending;
    ProcessIdentity identity;
    int exit_code = -1;
    int native_status = 0;
    std::string standard_output;
    std::string standard_error;
    bool process_tree_terminated = false;
    std::string error;
};

ProcessResult supervise_process(const ProcessRequest& request);
bool process_identity_alive(std::uint64_t process_id) noexcept;

} // namespace facman::platform

#endif
