// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_WINDOWS_MAINTENANCE_HANDOFF_H
#define FACMAN_WINDOWS_MAINTENANCE_HANDOFF_H

#include <cstdint>
#include <filesystem>
#include <string>

namespace facman::setup::handoff {

using SuspendedChildObserver = bool (*)(void *context) noexcept;

enum class CleanupOutcome {
  none,
  exit_confirmed,
  outcome_unknown,
};

struct Result {
  bool ok = false;
  std::string detail;
  unsigned long process_id = 0;
  CleanupOutcome cleanup_outcome = CleanupOutcome::none;
};

struct LaunchRequest {
  std::filesystem::path helper;
  std::string helper_sha256;
  std::filesystem::path journal;
  std::string journal_sha256;
  std::string operation_id;
  std::string nonce;
  // Absolute GetTickCount64 deadline. The launcher and helper share this one
  // budget; the helper must not reset it after process creation.
  std::uint64_t deadline_tick_ms = 0;
  // Test/diagnostic seam invoked while the primary thread is still suspended
  // and before either pinned path is revalidated. False forces a post-create
  // admission refusal and exercises suspended-child cleanup.
  SuspendedChildObserver suspended_child_observer = nullptr;
  void *observer_context = nullptr;
};

struct WaitRequest {
  std::uintptr_t inherited_process_handle = 0;
  unsigned long expected_process_id = 0;
  std::uint64_t expected_creation_ticks = 0;
  std::uint64_t deadline_tick_ms = 0;
};

// Creates an exact external helper suspended with only a duplicate of the
// initiating process handle inherited. The primary thread is resumed only
// after both pinned input paths pass post-create revalidation. No Job object is
// used: the helper must survive the initiating executable so it can update or
// activate a side-by-side root.
Result launch(const LaunchRequest &request);

// The helper calls this before acquiring the global coordinator lock. It
// validates the inherited handle's PID and creation time, waits for the exact
// initiating process, and closes the handle. It never reopens a process by PID.
Result wait_for_initiator(const WaitRequest &request);

} // namespace facman::setup::handoff

#endif
