// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "windows_maintenance_handoff.h"

#include "fl_sha256.h"

#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>

#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>
#include <vector>

namespace fs = std::filesystem;

namespace {

std::uint64_t ticks(const FILETIME &value) {
  return static_cast<std::uint64_t>(value.dwLowDateTime) |
      (static_cast<std::uint64_t>(value.dwHighDateTime) << 32U);
}

std::string digest(const fs::path &path) {
  std::ifstream input(path, std::ios::binary);
  facman::base::Sha256Hasher hash;
  std::vector<unsigned char> buffer(1024U * 1024U);
  while (input) {
    input.read(reinterpret_cast<char *>(buffer.data()),
               static_cast<std::streamsize>(buffer.size()));
    if (input.gcount() > 0)
      hash.update(buffer.data(), static_cast<std::size_t>(input.gcount()));
  }
  return hash.finish();
}

std::wstring quote(const fs::path &path) {
  return L"\"" + path.wstring() + L"\"";
}

fs::path executable() {
  std::vector<wchar_t> buffer(32768U, L'\0');
  const DWORD size = GetModuleFileNameW(nullptr, buffer.data(),
                                       static_cast<DWORD>(buffer.size()));
  return size == 0 || size >= buffer.size()
      ? fs::path() : fs::path(std::wstring(buffer.data(), size));
}

std::wstring value(int argc, wchar_t **argv, const wchar_t *name) {
  for (int index = 2; index + 1 < argc; index += 2) {
    if (std::wstring(argv[index]) == name) return argv[index + 1];
  }
  return {};
}

struct AdmissionProbe {
  fs::path child_entered;
  bool remained_quiescent = false;
};

bool observe_suspended_child(void *context) noexcept {
  auto *probe = static_cast<AdmissionProbe *>(context);
  Sleep(100);
  std::error_code status;
  probe->remained_quiescent = !fs::exists(probe->child_entered, status) &&
      !status;
  return true;
}

bool refuse_suspended_child(void *context) noexcept {
  auto *probe = static_cast<AdmissionProbe *>(context);
  Sleep(100);
  std::error_code status;
  probe->remained_quiescent = !fs::exists(probe->child_entered, status) &&
      !status;
  return false;
}

int continuation(int argc, wchar_t **argv) {
  try {
    const fs::path journal(value(argc, argv, L"--handoff-journal"));
    std::ofstream(journal.parent_path() / "child-entered", std::ios::binary)
        << "entered\n";
    const std::string expected_digest =
        fs::path(value(argc, argv, L"--handoff-journal-sha256")).string();
    if (value(argc, argv, L"--operation-id") != L"maintenance.test" ||
        value(argc, argv, L"--handoff-nonce") != L"nonce.test" ||
        !fs::is_regular_file(journal) || digest(journal) != expected_digest)
      return 10;
    facman::setup::handoff::WaitRequest request{
        static_cast<std::uintptr_t>(std::stoull(
            value(argc, argv, L"--parent-handle"))),
        static_cast<unsigned long>(std::stoul(
            value(argc, argv, L"--parent-pid"))),
        std::stoull(value(argc, argv, L"--parent-created")),
        std::stoull(value(argc, argv, L"--deadline-tick-ms"))};
    auto waited = facman::setup::handoff::wait_for_initiator(request);
    if (!waited.ok) return 11;
    std::ofstream(journal.parent_path() / "continuation.completed",
                  std::ios::binary) << "completed\n";
    return 0;
  } catch (...) {
    return 12;
  }
}

int intermediate(int argc, wchar_t **argv) {
  if (argc != 5) return 20;
  const fs::path root(argv[2]);
  const fs::path self = executable();
  facman::setup::handoff::LaunchRequest request{
      self, fs::path(argv[3]).string(), root / "handoff.v1.json",
      fs::path(argv[4]).string(), "maintenance.test", "nonce.test",
      GetTickCount64() + 10000U};
  AdmissionProbe probe{root / "child-entered"};
  request.suspended_child_observer = observe_suspended_child;
  request.observer_context = &probe;
  const auto launched = facman::setup::handoff::launch(request);
  return launched.ok && launched.process_id != 0 && probe.remained_quiescent
      ? 0 : 21;
}

bool launch_intermediate(const fs::path &self, const fs::path &root,
                         const std::string &helper_digest,
                         const std::string &journal_digest) {
  std::wstring command = quote(self) + L" --intermediate " + quote(root) +
      L" " + fs::path(helper_digest).wstring() + L" " +
      fs::path(journal_digest).wstring();
  std::vector<wchar_t> mutable_command(command.begin(), command.end());
  mutable_command.push_back(L'\0');
  STARTUPINFOW startup{};
  startup.cb = sizeof(startup);
  PROCESS_INFORMATION process{};
  if (!CreateProcessW(self.c_str(), mutable_command.data(), nullptr, nullptr,
                      FALSE, CREATE_UNICODE_ENVIRONMENT, nullptr,
                      self.parent_path().c_str(), &startup, &process))
    return false;
  CloseHandle(process.hThread);
  const DWORD waited = WaitForSingleObject(process.hProcess, 10000);
  DWORD exit_code = 1;
  const BOOL observed = GetExitCodeProcess(process.hProcess, &exit_code);
  CloseHandle(process.hProcess);
  return waited == WAIT_OBJECT_0 && observed && exit_code == 0;
}

int root_test() {
  const fs::path self = executable();
  if (self.empty()) return 1;
  const fs::path root = fs::path(FACMAN_TEST_TEMP_ROOT) /
      ("handoff-" + std::to_string(GetCurrentProcessId()));
  std::error_code status;
  fs::remove_all(root, status);
  if (!fs::create_directories(root, status) || status) return 1;
  const fs::path journal = root / "handoff.v1.json";
  std::ofstream(journal, std::ios::binary) <<
      "{\"operation_id\":\"maintenance.test\",\"product_id\":\"facman\"}\n";
  if (!launch_intermediate(self, root, digest(self), digest(journal))) {
    std::cerr << "external helper was not launched by the intermediate process\n";
    return 1;
  }
  const fs::path completed = root / "continuation.completed";
  for (unsigned attempt = 0; attempt < 100U && !fs::is_regular_file(completed);
       ++attempt)
    std::this_thread::sleep_for(std::chrono::milliseconds(20));
  if (!fs::is_regular_file(completed)) {
    std::cerr << "external helper did not survive and observe parent exit\n";
    return 1;
  }
  if (!fs::is_regular_file(root / "child-entered")) {
    std::cerr << "admitted child did not execute after its primary thread resumed\n";
    return 1;
  }

  const fs::path refusal_root = root / "post-create-refusal";
  if (!fs::create_directories(refusal_root, status) || status) return 1;
  const fs::path refusal_journal = refusal_root / "handoff.v1.json";
  std::ofstream(refusal_journal, std::ios::binary) <<
      "{\"operation_id\":\"maintenance.test\",\"product_id\":\"facman\"}\n";
  AdmissionProbe refusal_probe{refusal_root / "child-entered"};
  facman::setup::handoff::LaunchRequest refused_request{
      self, digest(self), refusal_journal, digest(refusal_journal),
      "maintenance.test", "nonce.test", GetTickCount64() + 10000U};
  refused_request.suspended_child_observer = refuse_suspended_child;
  refused_request.observer_context = &refusal_probe;
  const auto refused = facman::setup::handoff::launch(refused_request);
  const bool closed = refused.cleanup_outcome ==
      facman::setup::handoff::CleanupOutcome::exit_confirmed;
  const bool explicitly_unresolved = refused.cleanup_outcome ==
          facman::setup::handoff::CleanupOutcome::outcome_unknown &&
      refused.detail.find("cleanup outcome is unknown") != std::string::npos;
  if (refused.ok || refused.process_id == 0 ||
      !refusal_probe.remained_quiescent ||
      fs::exists(refusal_probe.child_entered) ||
      (!closed && !explicitly_unresolved)) {
    std::cerr << "post-create refusal lost suspended-child cleanup accounting\n";
    return 1;
  }

  HANDLE duplicate = nullptr;
  if (!DuplicateHandle(GetCurrentProcess(), GetCurrentProcess(),
                       GetCurrentProcess(), &duplicate,
                       SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION,
                       TRUE, 0)) return 1;
  FILETIME created{}, exited{}, kernel{}, user{};
  if (!GetProcessTimes(duplicate, &created, &exited, &kernel, &user)) {
    CloseHandle(duplicate);
    return 1;
  }
  facman::setup::handoff::WaitRequest substituted{
      reinterpret_cast<std::uintptr_t>(duplicate), GetCurrentProcessId() + 1U,
      ticks(created), GetTickCount64() + 1000U};
  const auto rejected =
      facman::setup::handoff::wait_for_initiator(substituted);
  if (rejected.ok || rejected.detail.find("does not identify") ==
                         std::string::npos) {
    std::cerr << "substituted process identity was accepted\n";
    return 1;
  }

  HANDLE live = nullptr;
  if (!DuplicateHandle(GetCurrentProcess(), GetCurrentProcess(),
                       GetCurrentProcess(), &live,
                       SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION,
                       TRUE, 0)) return 1;
  facman::setup::handoff::WaitRequest timeout{
      reinterpret_cast<std::uintptr_t>(live), GetCurrentProcessId(),
      ticks(created), GetTickCount64() + 20U};
  const auto timed_out = facman::setup::handoff::wait_for_initiator(timeout);
  if (timed_out.ok || timed_out.detail.find("handoff deadline") ==
                          std::string::npos) {
    std::cerr << "live valid process handle did not consume the absolute deadline\n";
    return 1;
  }
  fs::remove_all(root, status);
  return status ? 1 : 0;
}

} // namespace

int wmain(int argc, wchar_t **argv) {
  if (argc > 1 && std::wstring(argv[1]) == L"continue-maintenance")
    return continuation(argc, argv);
  if (argc > 1 && std::wstring(argv[1]) == L"--intermediate")
    return intermediate(argc, argv);
  return root_test();
}
