// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_process_supervisor.h"

#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#include <algorithm>
#include <atomic>
#include <cwctype>
#include <thread>
#include <utility>

namespace facman::platform {
namespace {

class Handle {
public:
    Handle() = default;
    explicit Handle(HANDLE value) : value_(value) {}
    ~Handle() { reset(); }
    Handle(const Handle&) = delete;
    Handle& operator=(const Handle&) = delete;
    Handle(Handle&& other) noexcept : value_(other.release()) {}
    Handle& operator=(Handle&& other) noexcept
    {
        if (this != &other) reset(other.release());
        return *this;
    }
    HANDLE get() const noexcept { return value_; }
    HANDLE release() noexcept { HANDLE value = value_; value_ = nullptr; return value; }
    void reset(HANDLE value = nullptr) noexcept
    {
        if (value_ != nullptr && value_ != INVALID_HANDLE_VALUE) CloseHandle(value_);
        value_ = value;
    }
    explicit operator bool() const noexcept { return value_ != nullptr && value_ != INVALID_HANDLE_VALUE; }

private:
    HANDLE value_ = nullptr;
};

class AttributeList {
public:
    AttributeList()
    {
        SIZE_T bytes = 0;
        InitializeProcThreadAttributeList(nullptr, 1, 0, &bytes);
        storage_.resize(bytes);
        value_ = reinterpret_cast<LPPROC_THREAD_ATTRIBUTE_LIST>(storage_.data());
        if (!InitializeProcThreadAttributeList(value_, 1, 0, &bytes)) value_ = nullptr;
    }
    ~AttributeList() { if (value_ != nullptr) DeleteProcThreadAttributeList(value_); }
    AttributeList(const AttributeList&) = delete;
    AttributeList& operator=(const AttributeList&) = delete;
    LPPROC_THREAD_ATTRIBUTE_LIST get() const noexcept { return value_; }

private:
    std::vector<unsigned char> storage_;
    LPPROC_THREAD_ATTRIBUTE_LIST value_ = nullptr;
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

std::wstring utf8_to_wide(const std::string& value)
{
    if (value.empty()) return {};
    const int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(),
        static_cast<int>(value.size()), nullptr, 0);
    if (count <= 0) return {};
    std::wstring output(static_cast<std::size_t>(count), L'\0');
    if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(),
            static_cast<int>(value.size()), output.data(), count) != count) return {};
    return output;
}

std::wstring quote_argument(const std::wstring& value)
{
    if (!value.empty() && value.find_first_of(L" \t\n\v\"") == std::wstring::npos) return value;
    std::wstring output(1, L'\"');
    std::size_t backslashes = 0;
    for (wchar_t ch : value) {
        if (ch == L'\\') {
            ++backslashes;
        } else if (ch == L'\"') {
            output.append(backslashes * 2U + 1U, L'\\');
            output.push_back(L'\"');
            backslashes = 0;
        } else {
            output.append(backslashes, L'\\');
            backslashes = 0;
            output.push_back(ch);
        }
    }
    output.append(backslashes * 2U, L'\\');
    output.push_back(L'\"');
    return output;
}

std::vector<wchar_t> command_line(const ProcessRequest& request)
{
    std::wstring text = quote_argument(request.executable.wstring());
    for (const std::string& argument : request.arguments) {
        text.push_back(L' ');
        text += quote_argument(utf8_to_wide(argument));
    }
    std::vector<wchar_t> output(text.begin(), text.end());
    output.push_back(L'\0');
    return output;
}

bool same_environment_name(const std::wstring& entry, const std::wstring& name)
{
    const std::size_t equal = entry.find(L'=');
    if (equal == std::wstring::npos || equal != name.size()) return false;
    for (std::size_t index = 0; index < equal; ++index) {
        if (std::towlower(entry[index]) != std::towlower(name[index])) return false;
    }
    return true;
}

std::vector<wchar_t> environment_block(const ProcessRequest& request)
{
    if (request.inherit_environment && request.environment.empty()) return {};
    std::vector<std::wstring> entries;
    if (request.inherit_environment) {
        LPWCH block = GetEnvironmentStringsW();
        if (block != nullptr) {
            for (const wchar_t* item = block; *item != L'\0'; item += std::wcslen(item) + 1U) {
                entries.emplace_back(item);
            }
            FreeEnvironmentStringsW(block);
        }
    }
    for (const ProcessEnvironmentEntry& item : request.environment) {
        const std::wstring name = utf8_to_wide(item.name);
        const std::wstring value = utf8_to_wide(item.value);
        entries.erase(std::remove_if(entries.begin(), entries.end(), [&](const std::wstring& existing) {
            return same_environment_name(existing, name);
        }), entries.end());
        entries.push_back(name + L"=" + value);
    }
    std::sort(entries.begin(), entries.end(), [](const std::wstring& left, const std::wstring& right) {
        return _wcsicmp(left.c_str(), right.c_str()) < 0;
    });
    std::vector<wchar_t> block;
    for (const std::wstring& entry : entries) {
        block.insert(block.end(), entry.begin(), entry.end());
        block.push_back(L'\0');
    }
    block.push_back(L'\0');
    return block;
}

void read_bounded(HANDLE handle, std::string& output, std::size_t maximum, std::atomic<bool>& overflow)
{
    char buffer[8192];
    for (;;) {
        DWORD count = 0;
        if (!ReadFile(handle, buffer, sizeof(buffer), &count, nullptr) || count == 0) break;
        const std::size_t available = output.size() < maximum ? maximum - output.size() : 0;
        output.append(buffer, static_cast<std::size_t>(std::min<DWORD>(count, static_cast<DWORD>(available))));
        if (count > available) overflow.store(true, std::memory_order_release);
    }
}

void terminate_tree(HANDLE job, ProcessResult& result, unsigned int code)
{
    if (TerminateJobObject(job, code)) result.process_tree_terminated = true;
}

std::string windows_start_identity(HANDLE process, DWORD process_id) noexcept
{
    FILETIME creation {}, exit {}, kernel {}, user {};
    if (!GetProcessTimes(process, &creation, &exit, &kernel, &user)) return {};
    const std::uint64_t ticks =
        (static_cast<std::uint64_t>(creation.dwHighDateTime) << 32U) |
        static_cast<std::uint64_t>(creation.dwLowDateTime);
    return "windows-process-v1:" + std::to_string(process_id) + ":" +
        std::to_string(ticks);
}

} // namespace

ProcessResult supervise_process(const ProcessRequest& request)
{
    ProcessResult result;
    result.termination = ProcessTermination::start_failed;
    if (request.executable.empty() || request.timeout.count() <= 0) {
        result.error = "process request requires an executable and positive timeout";
        return result;
    }
    Handle child_input_read, parent_input_write, parent_output_read, child_output_write;
    Handle parent_error_read, child_error_write;
    if (!make_pipe(child_input_read, parent_input_write, false) ||
        !make_pipe(parent_output_read, child_output_write, true) ||
        !make_pipe(parent_error_read, child_error_write, true)) {
        result.error = "CreatePipe failed";
        return result;
    }

    STARTUPINFOEXW startup {};
    startup.StartupInfo.cb = sizeof(startup);
    startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
    startup.StartupInfo.hStdInput = child_input_read.get();
    startup.StartupInfo.hStdOutput = child_output_write.get();
    startup.StartupInfo.hStdError = child_error_write.get();
    AttributeList attributes;
    if (attributes.get() == nullptr) { result.error = "InitializeProcThreadAttributeList failed"; return result; }
    HANDLE inherited[] = {child_input_read.get(), child_output_write.get(), child_error_write.get()};
    if (!UpdateProcThreadAttribute(attributes.get(), 0, PROC_THREAD_ATTRIBUTE_HANDLE_LIST,
            inherited, sizeof(inherited), nullptr, nullptr)) {
        result.error = "UpdateProcThreadAttribute(handle list) failed";
        return result;
    }
    startup.lpAttributeList = attributes.get();

    Handle job(CreateJobObjectW(nullptr, nullptr));
    if (!job) { result.error = "CreateJobObject failed"; return result; }
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits {};
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    if (!SetInformationJobObject(job.get(), JobObjectExtendedLimitInformation, &limits, sizeof(limits))) {
        result.error = "SetInformationJobObject failed";
        return result;
    }

    std::vector<wchar_t> command = command_line(request);
    std::vector<wchar_t> environment = environment_block(request);
    const std::wstring working_directory = request.working_directory.empty()
        ? std::wstring()
        : request.working_directory.wstring();
    PROCESS_INFORMATION process {};
    const DWORD flags = CREATE_NO_WINDOW | CREATE_SUSPENDED | EXTENDED_STARTUPINFO_PRESENT |
        (environment.empty() ? 0U : CREATE_UNICODE_ENVIRONMENT);
    if (!CreateProcessW(request.executable.c_str(), command.data(), nullptr, nullptr, TRUE, flags,
            environment.empty() ? nullptr : environment.data(),
            working_directory.empty() ? nullptr : working_directory.c_str(),
            &startup.StartupInfo, &process)) {
        result.error = "CreateProcess failed (Windows error " + std::to_string(GetLastError()) + ")";
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
    result.identity = {
        static_cast<std::uint64_t>(process.dwProcessId),
        "windows-process-v1",
        windows_start_identity(process_handle.get(), process.dwProcessId)};
    if (request.validate_before_resume) {
        bool accepted = false;
        try {
            accepted = request.validate_before_resume(result.identity);
        } catch (...) {
            accepted = false;
        }
        if (!accepted) {
            terminate_tree(job.get(), result, 1);
            result.termination = ProcessTermination::start_failed;
            result.error =
                "process identity validation refused before primary-thread resume";
            return result;
        }
    }
    if (ResumeThread(thread_handle.get()) == static_cast<DWORD>(-1)) {
        terminate_tree(job.get(), result, 1);
        result.error = "ResumeThread failed";
        return result;
    }
    if (request.started) request.started(result.identity);

    std::size_t written_total = 0;
    while (written_total < request.standard_input.size()) {
        DWORD written = 0;
        const DWORD remaining = static_cast<DWORD>(std::min<std::size_t>(
            request.standard_input.size() - written_total, static_cast<std::size_t>(MAXDWORD)));
        if (!WriteFile(parent_input_write.get(), request.standard_input.data() + written_total,
                remaining, &written, nullptr)) break;
        written_total += written;
    }
    parent_input_write.reset();

    std::atomic<bool> overflow {false};
    std::thread output_reader(read_bounded, parent_output_read.get(), std::ref(result.standard_output),
        request.maximum_standard_output, std::ref(overflow));
    std::thread error_reader(read_bounded, parent_error_read.get(), std::ref(result.standard_error),
        request.maximum_standard_error, std::ref(overflow));
    const auto deadline = std::chrono::steady_clock::now() + request.timeout;
    bool primary_exited = false;
    for (;;) {
        if (WaitForSingleObject(process_handle.get(), 10) == WAIT_OBJECT_0) { primary_exited = true; break; }
        if (request.cancellation_requested && request.cancellation_requested()) {
            result.termination = ProcessTermination::cancelled;
            terminate_tree(job.get(), result, 2);
            break;
        }
        if (std::chrono::steady_clock::now() >= deadline) {
            result.termination = ProcessTermination::timed_out;
            terminate_tree(job.get(), result, 3);
            break;
        }
        if (overflow.load(std::memory_order_acquire)) {
            result.termination = ProcessTermination::output_limit;
            terminate_tree(job.get(), result, 4);
            break;
        }
    }
    if (primary_exited) terminate_tree(job.get(), result, 0);
    WaitForSingleObject(process_handle.get(), INFINITE);
    output_reader.join();
    error_reader.join();
    parent_output_read.reset();
    parent_error_read.reset();

    DWORD exit_code = 0;
    if (GetExitCodeProcess(process_handle.get(), &exit_code)) {
        result.native_status = static_cast<int>(exit_code);
        result.exit_code = static_cast<int>(exit_code);
    }
    if (primary_exited) {
        // A fast process can exit before the supervisor poll observes that a
        // pipe reader crossed its capture limit. The overflow is still the
        // authoritative outcome even when there is no live tree left to kill.
        result.termination = overflow.load(std::memory_order_acquire)
            ? ProcessTermination::output_limit
            : (exit_code >= 0x80000000UL
                ? ProcessTermination::crashed
                : ProcessTermination::exited);
    }
    return result;
}

bool process_identity_alive(std::uint64_t process_id) noexcept
{
    if (process_id == 0 || process_id > static_cast<std::uint64_t>(MAXDWORD)) return false;
    Handle process(OpenProcess(SYNCHRONIZE, FALSE, static_cast<DWORD>(process_id)));
    return process && WaitForSingleObject(process.get(), 0) == WAIT_TIMEOUT;
}

bool process_identity_alive(const ProcessIdentity& identity) noexcept
{
    if (identity.process_id == 0 ||
        identity.process_id > static_cast<std::uint64_t>(MAXDWORD) ||
        identity.stable_start_identity.empty()) return false;
    Handle process(OpenProcess(
        SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION,
        FALSE,
        static_cast<DWORD>(identity.process_id)));
    if (!process || WaitForSingleObject(process.get(), 0) != WAIT_TIMEOUT) return false;
    return windows_start_identity(
        process.get(), static_cast<DWORD>(identity.process_id)) ==
        identity.stable_start_identity;
}

} // namespace facman::platform
