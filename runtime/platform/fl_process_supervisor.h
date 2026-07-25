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
    // Opaque provider-produced start identity. On the Windows candidate this
    // binds the PID to the process creation FILETIME so a recycled PID cannot
    // satisfy a recovery or observation check.
    std::string stable_start_identity;

    bool restart_safe() const noexcept { return !stable_start_identity.empty(); }
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
    // Windows invokes this after creating and job-binding the process in a
    // suspended state but before its primary thread can execute. Returning
    // false refuses the process boundary. Other platforms currently reject
    // requests that require this Windows-only guarantee.
    std::function<bool(const ProcessIdentity&)> validate_before_resume;
    std::function<void(const ProcessIdentity&)> started;
};

struct ProcessResult {
    ProcessTermination termination = ProcessTermination::pending;
    ProcessIdentity identity;
    int exit_code = -1;
    int native_status = 0;
    std::string standard_output;
    std::string standard_error;
    // True only when the supervisor successfully requested termination of a
    // live process tree; false is valid when a limited process already exited.
    bool process_tree_terminated = false;
    std::string error;
};

ProcessResult supervise_process(const ProcessRequest& request);
bool process_identity_alive(std::uint64_t process_id) noexcept;
bool process_identity_alive(const ProcessIdentity& identity) noexcept;

} // namespace facman::platform

#endif
