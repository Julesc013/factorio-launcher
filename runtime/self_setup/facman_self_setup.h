// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_SELF_SETUP_H
#define FACMAN_SELF_SETUP_H

#include "fl_result.h"

#include <filesystem>
#include <optional>
#include <string>

namespace facman::self_setup {

enum class Operation { install, verify, repair, uninstall };

// The setup coordinator owns the durable record; platform adapters own the
// authority to inspect and change native integration objects.
enum class NativeEffect { shortcut, registration };
enum class NativeOwnership { absent, owned, owned_stale, foreign, unreadable };

struct Response {
  std::string operation;
  std::string phase;
  std::string provider_json;
  std::string setup_operation_id;
};

struct NativeResult {
  bool ok = false;
  std::string detail;
  // Set only when the adapter observed a changed, substituted, or otherwise
  // unprovable object at its mutation edge.  The coordinator retains the
  // journal for operator recovery instead of retrying a blind mutation.
  bool recovery_required = false;
};

struct RetainedSourceResult {
  bool ok = false;
  std::filesystem::path path;
  std::string detail;
  bool recovery_required = false;
};

struct NativeContext {
  Operation operation = Operation::verify;
  std::filesystem::path install_root;
  std::filesystem::path state_root;
  std::filesystem::path acceptance_root;
  std::filesystem::path repair_source;
  std::string product_version;
};

class NativeEffects {
public:
  virtual ~NativeEffects() = default;
  virtual RetainedSourceResult retain_repair_source(
      const NativeContext &context,
      const std::filesystem::path &package,
      const std::string &expected_sha256) = 0;
  virtual RetainedSourceResult validate_repair_source(
      const NativeContext &context,
      const std::string &expected_sha256) = 0;
  virtual NativeOwnership inspect(const NativeContext &context,
                                  NativeEffect effect) = 0;
  virtual NativeResult apply(const NativeContext &context,
                             NativeEffect effect) = 0;
};

// Called only after a named durable journal boundary is successfully
// persisted. It is intentionally narrow so tests and embedders can model an
// interruption without modifying a journal behind the coordinator's back.
enum class DurableBoundary { files_applied, shortcut_applied };

class DurableBoundaryHook {
public:
  virtual ~DurableBoundaryHook() = default;
  virtual bool reached(DurableBoundary boundary) = 0;
};

// Qualification callers bind a one-use external permit to this immutable
// operation identity.  Recovery must not silently retarget that permit to a
// different unfinished journal.
struct QualificationClaims {
  Operation operation = Operation::verify;
  std::filesystem::path install_root;
  std::filesystem::path state_root;
  std::filesystem::path acceptance_root;
  std::string product_version;
  bool installed_mode = false;
  DurableBoundary boundary = DurableBoundary::files_applied;
};

// Narrow test/embedding seam for the provider command boundary.  Production
// uses the pinned USK API when this is null; its payload validation is unchanged.
class ProviderEffects {
public:
  virtual ~ProviderEffects() = default;
  virtual facman::core::Result<std::string> command(
      const std::string &name, const std::string &payload,
      const std::filesystem::path &state_root,
      const std::filesystem::path &acceptance_root, bool dry_run) = 0;
  // Test-only storage seam. Production never takes coordinator placement from
  // a request or from a provider authority root.
  virtual std::filesystem::path test_coordinator_root() const { return {}; }
};

struct Request {
  Operation operation = Operation::verify;
  std::filesystem::path package;
  std::filesystem::path install_root;
  std::filesystem::path state_root;
  std::filesystem::path acceptance_root;
  std::string product_version;
  bool apply = false;
  // A null adapter is the portable/no-shell-integration mode. It still
  // records native effects as not_applicable in the composite journal.
  NativeEffects *native_effects = nullptr;
  ProviderEffects *provider_effects = nullptr;
  DurableBoundaryHook *durable_boundary_hook = nullptr;
  std::optional<QualificationClaims> qualification_claims;
};

facman::core::Result<Response> execute(const Request &request);
std::string provider_revision();

} // namespace facman::self_setup

#endif
