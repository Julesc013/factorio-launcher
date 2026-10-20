// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "windows_maintenance_handoff.h"

#include "fl_file_io.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"

#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#include <algorithm>
#include <limits>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace facman::setup::handoff {
namespace {

bool lowercase_digest(const std::string &value) {
  return value.size() == 64U &&
      std::all_of(value.begin(), value.end(), [](unsigned char character) {
        return (character >= '0' && character <= '9') ||
            (character >= 'a' && character <= 'f');
      });
}

bool pin_exact_file_digest(facman::platform::StableInputFile &file,
                           const fs::path &path, std::string &digest,
                           std::string &detail) {
  const auto opened = file.open_no_follow_pinned(path);
  if (!opened.ok() || file.size() == 0) {
    detail = opened.detail.empty() ? "file is empty" : opened.detail;
    return false;
  }
  facman::base::Sha256Hasher hasher;
  std::vector<unsigned char> buffer(1024U * 1024U);
  for (std::uint64_t offset = 0; offset < file.size();) {
    const std::size_t count = static_cast<std::size_t>((std::min)(
        static_cast<std::uint64_t>(buffer.size()), file.size() - offset));
    if (file.read_at(offset, buffer.data(), count) != count) {
      detail = "file changed while hashing";
      return false;
    }
    hasher.update(buffer.data(), count);
    offset += count;
  }
  const auto checked = file.revalidate_path();
  if (!checked.ok()) {
    detail = checked.detail;
    return false;
  }
  digest = hasher.finish();
  return true;
}

std::wstring quote(const std::wstring &value) {
  std::wstring output(1, L'"');
  std::size_t slashes = 0;
  for (const wchar_t character : value) {
    if (character == L'\\') {
      ++slashes;
      continue;
    }
    if (character == L'"') {
      output.append(slashes * 2U + 1U, L'\\');
      output.push_back(character);
      slashes = 0;
      continue;
    }
    output.append(slashes, L'\\');
    slashes = 0;
    output.push_back(character);
  }
  output.append(slashes * 2U, L'\\');
  output.push_back(L'"');
  return output;
}

std::uint64_t ticks(const FILETIME &value) {
  return static_cast<std::uint64_t>(value.dwLowDateTime) |
      (static_cast<std::uint64_t>(value.dwHighDateTime) << 32U);
}

struct Handle {
  HANDLE value = nullptr;
  ~Handle() { if (value != nullptr && value != INVALID_HANDLE_VALUE) CloseHandle(value); }
};

} // namespace

Result launch(const LaunchRequest &request) {
  std::string detail;
  const std::uint64_t now = GetTickCount64();
  if (!request.helper.is_absolute() || !request.journal.is_absolute() ||
      !lowercase_digest(request.helper_sha256) ||
      !lowercase_digest(request.journal_sha256) ||
      !facman::base::validate_identifier(request.operation_id, detail) ||
      !facman::base::validate_identifier(request.nonce, detail) ||
      request.deadline_tick_ms <= now ||
      request.deadline_tick_ms - now > 600000U)
    return {false, "maintenance handoff identity is invalid"};
  // Both files remain open with FILE_SHARE_READ only through CreateProcessW.
  // This prevents content replacement, deletion, or a write between digest
  // verification and image creation.
  facman::platform::StableInputFile helper_pin;
  facman::platform::StableInputFile journal_pin;
  std::string observed;
  if (!pin_exact_file_digest(helper_pin, request.helper, observed, detail) ||
      observed != request.helper_sha256)
    return {false, "external helper does not match its expected identity: " + detail};
  if (!pin_exact_file_digest(journal_pin, request.journal, observed, detail) ||
      observed != request.journal_sha256)
    return {false, "handoff journal does not match its expected identity: " + detail};

  HANDLE inherited = nullptr;
  if (!DuplicateHandle(GetCurrentProcess(), GetCurrentProcess(),
                       GetCurrentProcess(), &inherited,
                       SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION,
                       TRUE, 0))
    return {false, "Windows could not duplicate the initiating process handle"};
  Handle inherited_owner{inherited};
  SECURITY_ATTRIBUTES inheritable{};
  inheritable.nLength = sizeof(inheritable);
  inheritable.bInheritHandle = TRUE;
  Handle null_input{CreateFileW(L"NUL", GENERIC_READ,
      FILE_SHARE_READ | FILE_SHARE_WRITE, &inheritable, OPEN_EXISTING,
      FILE_ATTRIBUTE_NORMAL, nullptr)};
  Handle null_output{CreateFileW(L"NUL", GENERIC_WRITE,
      FILE_SHARE_READ | FILE_SHARE_WRITE, &inheritable, OPEN_EXISTING,
      FILE_ATTRIBUTE_NORMAL, nullptr)};
  if (null_input.value == INVALID_HANDLE_VALUE ||
      null_output.value == INVALID_HANDLE_VALUE)
    return {false, "Windows could not isolate the external helper's standard handles"};
  FILETIME created{}, exited{}, kernel{}, user{};
  if (!GetProcessTimes(inherited, &created, &exited, &kernel, &user))
    return {false, "Windows could not bind initiating process creation time"};

  SIZE_T attributes_size = 0;
  InitializeProcThreadAttributeList(nullptr, 1, 0, &attributes_size);
  std::vector<unsigned char> attributes(attributes_size);
  STARTUPINFOEXW startup{};
  startup.StartupInfo.cb = sizeof(startup);
  // The continuation outlives this process.  Explicit null handles prevent it
  // from retaining redirected caller pipes and turning the asynchronous
  // handoff into a parent/child I/O wait cycle.
  startup.StartupInfo.dwFlags = STARTF_USESTDHANDLES;
  startup.StartupInfo.hStdInput = null_input.value;
  startup.StartupInfo.hStdOutput = null_output.value;
  startup.StartupInfo.hStdError = null_output.value;
  startup.lpAttributeList = reinterpret_cast<PPROC_THREAD_ATTRIBUTE_LIST>(
      attributes.data());
  if (!InitializeProcThreadAttributeList(startup.lpAttributeList, 1, 0,
                                         &attributes_size))
    return {false, "Windows could not initialize the handoff handle list"};
  const auto release_attributes = [&]() {
    DeleteProcThreadAttributeList(startup.lpAttributeList);
  };
  HANDLE inherited_handles[] = {
      inherited, null_input.value, null_output.value};
  if (!UpdateProcThreadAttribute(startup.lpAttributeList, 0,
          PROC_THREAD_ATTRIBUTE_HANDLE_LIST, inherited_handles,
          sizeof(inherited_handles),
          nullptr, nullptr)) {
    release_attributes();
    return {false, "Windows could not restrict the inherited handle list"};
  }

  const DWORD pid = GetCurrentProcessId();
  std::wstring command = quote(request.helper.wstring()) +
      L" continue-maintenance --operation-id " +
      quote(fs::path(request.operation_id).wstring()) +
      L" --handoff-nonce " + quote(fs::path(request.nonce).wstring()) +
      L" --handoff-journal " + quote(request.journal.wstring()) +
      L" --handoff-journal-sha256 " +
      quote(fs::path(request.journal_sha256).wstring()) +
      L" --parent-handle " +
      std::to_wstring(reinterpret_cast<std::uintptr_t>(inherited)) +
      L" --parent-pid " + std::to_wstring(pid) +
      L" --parent-created " + std::to_wstring(ticks(created)) +
      L" --deadline-tick-ms " + std::to_wstring(request.deadline_tick_ms);
  std::vector<wchar_t> mutable_command(command.begin(), command.end());
  mutable_command.push_back(L'\0');
  if (GetTickCount64() >= request.deadline_tick_ms) {
    release_attributes();
    return {false, "maintenance handoff deadline elapsed before helper launch"};
  }
  PROCESS_INFORMATION process{};
  const BOOL launched = CreateProcessW(
      request.helper.c_str(), mutable_command.data(), nullptr, nullptr, TRUE,
      EXTENDED_STARTUPINFO_PRESENT | CREATE_UNICODE_ENVIRONMENT |
          CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW | CREATE_SUSPENDED,
      nullptr, request.helper.parent_path().c_str(), &startup.StartupInfo,
      &process);
  release_attributes();
  if (!launched)
    return {false, "Windows could not launch the external maintenance helper"};
  const auto reject_suspended = [&](const std::string &message) {
    constexpr DWORD cleanup_wait_ms = 5000U;
    const BOOL termination_requested =
        TerminateProcess(process.hProcess, ERROR_FILE_INVALID);
    const DWORD waited = WaitForSingleObject(process.hProcess,
                                             cleanup_wait_ms);
    const DWORD spawned_pid = process.dwProcessId;
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    if (!termination_requested || waited != WAIT_OBJECT_0)
      return Result{
          false,
          message + "; suspended-child cleanup outcome is unknown",
          spawned_pid,
          CleanupOutcome::outcome_unknown};
    return Result{false, message, spawned_pid,
                  CleanupOutcome::exit_confirmed};
  };
  if (request.suspended_child_observer != nullptr &&
      !request.suspended_child_observer(request.observer_context))
    return reject_suspended(
        "external maintenance helper admission was refused after creation");
  const auto helper_checked = helper_pin.revalidate_path();
  const auto journal_checked = journal_pin.revalidate_path();
  if (!helper_checked.ok() || !journal_checked.ok())
    return reject_suspended(
        "maintenance handoff input changed during helper launch");
  if (GetTickCount64() >= request.deadline_tick_ms)
    return reject_suspended(
        "maintenance handoff deadline elapsed before helper admission");
  if (ResumeThread(process.hThread) == static_cast<DWORD>(-1))
    return reject_suspended(
        "Windows could not resume the admitted external maintenance helper");
  CloseHandle(process.hThread);
  CloseHandle(process.hProcess);
  return {true, "external maintenance helper launched", process.dwProcessId};
}

Result wait_for_initiator(const WaitRequest &request) {
  if (request.inherited_process_handle == 0 ||
      request.inherited_process_handle >
          static_cast<std::uintptr_t>((std::numeric_limits<std::intptr_t>::max)()) ||
      request.expected_process_id == 0 || request.expected_creation_ticks == 0 ||
      request.deadline_tick_ms == 0)
    return {false, "inherited process identity is invalid"};
  Handle process{reinterpret_cast<HANDLE>(request.inherited_process_handle)};
  const DWORD pid = GetProcessId(process.value);
  FILETIME created{}, exited{}, kernel{}, user{};
  if (pid != request.expected_process_id ||
      !GetProcessTimes(process.value, &created, &exited, &kernel, &user) ||
      ticks(created) != request.expected_creation_ticks)
    return {false, "inherited handle does not identify the initiating process"};
  const std::uint64_t now = GetTickCount64();
  if (now >= request.deadline_tick_ms)
    return {false, "initiating process did not exit before the handoff deadline"};
  const std::uint64_t remaining = request.deadline_tick_ms - now;
  if (remaining > 600000U)
    return {false, "inherited process deadline is outside the admitted window"};
  const DWORD waited = WaitForSingleObject(
      process.value, static_cast<DWORD>((std::min)(
                         remaining,
                         static_cast<std::uint64_t>((std::numeric_limits<DWORD>::max)() - 1U))));
  if (waited == WAIT_TIMEOUT)
    return {false, "initiating process did not exit before the handoff deadline"};
  if (waited != WAIT_OBJECT_0)
    return {false, "Windows could not wait for the initiating process"};
  return {true, "initiating process exited; maintenance may resume"};
}

} // namespace facman::setup::handoff
