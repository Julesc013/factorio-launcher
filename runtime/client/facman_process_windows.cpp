// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_process.h"

#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#include <algorithm>
#include <atomic>
#include <thread>

namespace facman::client::detail {
namespace {

class Handle {
public:
    Handle() = default;
    explicit Handle(HANDLE value) : value_(value) {}
    ~Handle() { reset(); }
    Handle(const Handle&) = delete;
    Handle& operator=(const Handle&) = delete;
    Handle(Handle&& other) noexcept : value_(other.release()) {}
    Handle& operator=(Handle&& other) noexcept { if (this != &other) reset(other.release()); return *this; }
    HANDLE get() const noexcept { return value_; }
    HANDLE release() noexcept { HANDLE value = value_; value_ = nullptr; return value; }
    void reset(HANDLE value = nullptr) noexcept { if (value_ != nullptr && value_ != INVALID_HANDLE_VALUE) CloseHandle(value_); value_ = value; }
    explicit operator bool() const noexcept { return value_ != nullptr && value_ != INVALID_HANDLE_VALUE; }

private:
    HANDLE value_ = nullptr;
};

bool make_pipe(Handle& read, Handle& write, bool parent_reads)
{
    SECURITY_ATTRIBUTES attributes {sizeof(attributes), nullptr, TRUE};
    HANDLE read_value = nullptr;
    HANDLE write_value = nullptr;
    if (!CreatePipe(&read_value, &write_value, &attributes, 0)) return false;
    read.reset(read_value);
    write.reset(write_value);
    return SetHandleInformation(parent_reads ? read.get() : write.get(), HANDLE_FLAG_INHERIT, 0) != FALSE;
}

void read_bounded(HANDLE handle, std::string& output, std::size_t maximum, std::atomic<bool>& overflow)
{
    char buffer[8192];
    for (;;) {
        DWORD count = 0;
        if (!ReadFile(handle, buffer, sizeof(buffer), &count, nullptr) || count == 0) break;
        if (output.size() <= maximum && count <= maximum - output.size()) output.append(buffer, count);
        else overflow.store(true, std::memory_order_release);
    }
}

std::wstring command_line(const std::filesystem::path& executable)
{
    std::wstring value = L"\"" + executable.wstring() + L"\" rpc --stdio";
    return value;
}

} // namespace

ProcessResult run_cli_process(const ProcessRequest& request)
{
    ProcessResult result;
    Handle child_input_read, parent_input_write, parent_output_read, child_output_write;
    Handle parent_error_read, child_error_write;
    if (!make_pipe(child_input_read, parent_input_write, false) ||
        !make_pipe(parent_output_read, child_output_write, true) ||
        !make_pipe(parent_error_read, child_error_write, true)) {
        result.error = "CreatePipe failed";
        return result;
    }
    STARTUPINFOW startup {};
    startup.cb = sizeof(startup);
    startup.dwFlags = STARTF_USESTDHANDLES;
    startup.hStdInput = child_input_read.get();
    startup.hStdOutput = child_output_write.get();
    startup.hStdError = child_error_write.get();
    PROCESS_INFORMATION process {};
    std::wstring command = command_line(request.executable);
    Handle job(CreateJobObjectW(nullptr, nullptr));
    if (!job) { result.error = "CreateJobObject failed"; return result; }
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits {};
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    if (!SetInformationJobObject(job.get(), JobObjectExtendedLimitInformation, &limits, sizeof(limits))) {
        result.error = "SetInformationJobObject failed";
        return result;
    }
    if (!CreateProcessW(request.executable.c_str(), command.data(), nullptr, nullptr, TRUE,
            CREATE_NO_WINDOW | CREATE_SUSPENDED, nullptr, nullptr, &startup, &process)) {
        result.error = "CreateProcess failed";
        return result;
    }
    Handle process_handle(process.hProcess);
    Handle thread_handle(process.hThread);
    if (!AssignProcessToJobObject(job.get(), process_handle.get())) {
        TerminateProcess(process_handle.get(), 1);
        result.error = "AssignProcessToJobObject failed";
        return result;
    }
    child_input_read.reset();
    child_output_write.reset();
    child_error_write.reset();
    ResumeThread(thread_handle.get());

    DWORD written_total = 0;
    while (written_total < request.standard_input.size()) {
        DWORD written = 0;
        const DWORD remaining = static_cast<DWORD>(std::min<std::size_t>(
            request.standard_input.size() - written_total, static_cast<std::size_t>(MAXDWORD)));
        if (!WriteFile(parent_input_write.get(), request.standard_input.data() + written_total, remaining, &written, nullptr)) break;
        written_total += written;
    }
    parent_input_write.reset();

    std::atomic<bool> overflow {false};
    std::thread output_reader(read_bounded, parent_output_read.get(), std::ref(result.standard_output),
        request.maximum_standard_output, std::ref(overflow));
    std::thread error_reader(read_bounded, parent_error_read.get(), std::ref(result.standard_error),
        request.maximum_standard_error, std::ref(overflow));
    const auto deadline = std::chrono::steady_clock::now() + request.timeout;
    for (;;) {
        if (WaitForSingleObject(process_handle.get(), 10) == WAIT_OBJECT_0) break;
        if (request.cancellation_requested && request.cancellation_requested()) {
            result.cancelled = true;
            TerminateJobObject(job.get(), 2);
            break;
        }
        if (std::chrono::steady_clock::now() >= deadline) {
            result.timed_out = true;
            TerminateJobObject(job.get(), 3);
            break;
        }
        if (overflow.load(std::memory_order_acquire)) {
            result.output_too_large = true;
            TerminateJobObject(job.get(), 4);
            break;
        }
    }
    WaitForSingleObject(process_handle.get(), INFINITE);
    output_reader.join();
    error_reader.join();
    parent_output_read.reset();
    parent_error_read.reset();
    DWORD exit_code = 0;
    if (GetExitCodeProcess(process_handle.get(), &exit_code)) result.exit_code = static_cast<int>(exit_code);
    result.output_too_large = result.output_too_large || overflow.load(std::memory_order_acquire);
    return result;
}

} // namespace facman::client::detail
