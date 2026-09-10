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

enum class ProcessIdentityObservation {
    matching_alive,
    not_matching_or_exited,
    inconclusive,
};

struct ProcessRequest {
    std::filesystem::path executable;
    std::vector<std::string> arguments;
    std::filesystem::path working_directory;
    std::vector<ProcessEnvironmentEntry> environment;
    bool inherit_environment = true;
    // POSIX supplies this byte stream through a local AF_UNIX socket, then
    // closes its sending endpoint for EOF. It is not a seekable/regular file.
    // SIGPIPE suppression is socket/send-local; caller signal state is unchanged.
    std::string standard_input;
    std::chrono::milliseconds timeout {std::chrono::minutes(5)};
    std::chrono::milliseconds termination_grace_period {std::chrono::milliseconds(250)};
    std::size_t maximum_standard_output = 16U * 1024U * 1024U;
    std::size_t maximum_standard_error = 1024U * 1024U;
    // Callbacks must return promptly; the synchronous supervisor cannot impose
    // a deadline inside arbitrary caller code. Thrown callbacks trigger cleanup.
    std::function<bool()> cancellation_requested;
    // Windows invokes this after creating and job-binding the process in a
    // suspended state but before its primary thread can execute. Returning
    // false refuses the process boundary. Other platforms currently reject
    // requests that require this Windows-only guarantee.
    std::function<bool(const ProcessIdentity&)> validate_before_resume;
    std::function<void(const ProcessIdentity&)> started;
};

struct ProcessResult {
    // POSIX keeps pending after fork until start notification and completion
    // are known; uncertain callbacks/I/O/cleanup retain pending with a reason.
    ProcessTermination termination = ProcessTermination::pending;
    ProcessIdentity identity;
    int exit_code = -1;
    int native_status = 0;
    std::string standard_output;
    std::string standard_error;
    // True means a termination request to the owned process group/tree succeeded.
    // It is not a live-tree emptiness proof or deliberate-session-escape containment.
    bool process_tree_terminated = false;
    std::string error;
};

// POSIX requires exclusive wait ownership of its forked child for this call:
// no competing waiter, SIGCHLD handler that reaps it, or disposition changes.
// The supervisor rejects automatic reaping but cannot lease process-wide signal
// state. Its ordinary process group does not contain deliberate session escape.
ProcessResult supervise_process(const ProcessRequest& request);
bool process_identity_alive(std::uint64_t process_id) noexcept;
bool process_identity_alive(const ProcessIdentity& identity) noexcept;
ProcessIdentityObservation observe_process_identity(const ProcessIdentity& identity) noexcept;

} // namespace facman::platform

#endif
