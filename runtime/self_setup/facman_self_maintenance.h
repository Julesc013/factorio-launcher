// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_SELF_MAINTENANCE_H
#define FACMAN_SELF_MAINTENANCE_H

#include "fl_result.h"

#include <filesystem>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace facman::self_maintenance {

enum class Operation { update, downgrade, rollback };
enum class CandidateState { absent, exact, foreign, unreadable };
enum class ShellState { absent, old_exact, new_exact, foreign, unreadable };

struct PackageDescriptor {
  std::string product_id;
  std::string product_version;
  std::string generation_relative_path;
  std::string facman_source_revision;
  std::string universal_setup_revision;
  std::string setup_protocol;
  std::string package_layout;
  std::string gui_relative_path;
  std::string cli_relative_path;
  std::string maintenance_relative_path;
  bool automatic_update = false;
};

struct Generation {
  std::string generation_id;
  std::string product_version;
  std::string package_sha256;
  std::string facman_source_revision;
  std::string universal_setup_revision;
  std::string install_id;
  std::filesystem::path install_root;
  std::filesystem::path logical_root;
  std::filesystem::path state_root;
  std::filesystem::path acceptance_root;
  std::filesystem::path gui;
  std::filesystem::path maintenance_launcher;
};

struct PackageInspection {
  std::filesystem::path package;
  std::string package_sha256;
  PackageDescriptor descriptor;
};

struct ActiveState {
  Generation active;
  std::optional<Generation> previous;
  std::string activation_name;
  std::string activation_sha256;
};

// The activation records are immutable history.  This view exposes their
// complete, validated generation sequence (including repeated generations)
// so a coordinator can make a bounded retirement decision without inferring
// lineage from only the current head.
struct ActivationChain {
  std::vector<Generation> generations;
  std::string activation_name;
  std::string activation_sha256;
};

// A lifecycle epoch is an immutable, content-addressed boundary around a
// self-maintenance activation history.  The all-zero epoch id is reserved for
// the synthesized compatibility view of the pre-epoch (v1) layout and is
// never persisted beneath coordinator/epochs.
struct LifecycleEpoch {
  std::string epoch_id;
  std::filesystem::path acceptance_root;
  std::string genesis_generation_id;
  std::filesystem::path logical_root;
  std::string predecessor_epoch_id;
  std::string predecessor_manifest_sha256;
  std::string predecessor_retirement_sha256;
  std::filesystem::path state_root;

  // Observed immutable bytes, populated by discovery.  They are not members
  // of the persisted epoch identity document.
  std::string manifest_sha256;
  std::string retirement_sha256;
  bool compatibility_epoch = false;
};

struct LifecycleEpochChain {
  std::vector<LifecycleEpoch> epochs;
};

struct RetirementStep {
  Generation generation;
  bool active = false;
};

struct RetirementRequest {
  std::filesystem::path coordinator_root;
  bool apply = false;
};

struct RetirementResponse {
  std::string phase;
  std::filesystem::path journal_directory;
  std::vector<RetirementStep> steps;
};

class RetirementEffects;

// An unforgeable, call-scoped proof that retire_active owns the exact global
// coordinator lock.  The setup runtime accepts this proof only for the same
// coordinator, avoiding a recursive acquisition without trusting a caller-set
// boolean.
class CoordinatorLockToken {
public:
  CoordinatorLockToken(const CoordinatorLockToken &) = delete;
  CoordinatorLockToken &operator=(const CoordinatorLockToken &) = delete;
  const std::filesystem::path &coordinator_root() const {
    return coordinator_root_;
  }
  const std::string &operation_id() const { return operation_id_; }

private:
  CoordinatorLockToken(std::filesystem::path coordinator_root,
                       std::string operation_id)
      : coordinator_root_(std::move(coordinator_root)),
        operation_id_(std::move(operation_id)) {}
  friend facman::core::Result<RetirementResponse> retire_active(
      const RetirementRequest &request, RetirementEffects &effects);

  std::filesystem::path coordinator_root_;
  std::string operation_id_;
};

// The application supplies the provider/native edge.  It must reject any
// foreign or ambiguous installed identity before uninstalling a step.  The
// coordinator persists an entered marker before calling uninstall_generation,
// which makes an interrupted edge recovery-required rather than replayable.
class RetirementEffects {
public:
  virtual ~RetirementEffects() = default;
  virtual facman::core::Result<void> inspect_retirement_generation(
      const Generation &generation, bool active) = 0;
  virtual facman::core::Result<void> uninstall_generation(
      const Generation &generation, bool active,
      const CoordinatorLockToken &coordinator_lock) = 0;
};

struct Request {
  Operation operation = Operation::update;
  std::string operation_id;
  std::filesystem::path coordinator_root;
  std::filesystem::path logical_root;
  std::filesystem::path state_root;
  std::filesystem::path acceptance_root;
  std::filesystem::path package;
  std::string package_sha256;
  PackageDescriptor package_descriptor;
  Generation active;
  Generation rollback_target;
  std::string previous_activation_name;
  std::string previous_activation_sha256;
  bool apply = false;
};

struct Plan {
  std::string operation;
  std::string operation_id;
  Generation source;
  Generation target;
  std::filesystem::path package;
  std::string package_sha256;
  std::string provider_operation;
  std::string previous_activation_name;
  std::string previous_activation_sha256;
};

struct EffectResult {
  bool ok = false;
  bool outcome_unknown = false;
  std::string receipt_sha256;
  std::string detail;
};

// The provider surface deliberately exposes only install_local. FacMan never
// requests USK's whole-root update primitive; rollback is a shell activation
// of an already retained, independently owned generation.
class Effects {
public:
  virtual ~Effects() = default;
  virtual CandidateState inspect_candidate(const Plan &plan) = 0;
  // Performs the exact read-only provider plan admission. Preview and apply
  // both cross this boundary before any durable FacMan state is written.
  virtual EffectResult review_install_local(const Plan &plan) = 0;
  // Retains local inputs after provider plan admission and before provider
  // entry. install_local() may only enter the exact reviewed apply call.
  virtual EffectResult prepare_install_local(const Plan &plan) = 0;
  virtual EffectResult install_local(const Plan &plan) = 0;
  virtual EffectResult inspect_installed(const Plan &plan) = 0;
  virtual EffectResult verify_installed(const Plan &plan) = 0;
  virtual ShellState inspect_shortcut(const Plan &plan) = 0;
  virtual ShellState inspect_registration(const Plan &plan) = 0;
  virtual EffectResult cutover_shortcut(const Plan &plan) = 0;
  virtual EffectResult cutover_registration(const Plan &plan) = 0;
};

struct Response {
  std::string operation;
  std::string phase;
  std::string operation_id;
  Generation active;
  std::filesystem::path generation_record;
  std::filesystem::path activation_record;
};

facman::core::Result<Plan> plan(const Request &request);
facman::core::Result<Response> execute(const Request &request, Effects &effects);
facman::core::Result<PackageInspection> inspect_package(
    const std::filesystem::path &package);
facman::core::Result<void> extract_maintenance_launcher(
    const PackageInspection &package,
    const std::filesystem::path &destination);
facman::core::Result<PackageDescriptor> inspect_legacy_descriptor(
    const std::filesystem::path &install_root);
facman::core::Result<Generation> make_generation(
    const PackageDescriptor &descriptor, const std::string &package_sha256,
    const std::string &install_id, const std::filesystem::path &install_root,
    const std::filesystem::path &logical_root,
    const std::filesystem::path &state_root,
    const std::filesystem::path &acceptance_root);
facman::core::Result<std::optional<ActiveState>> discover_active(
    const std::filesystem::path &coordinator_root);
facman::core::Result<std::optional<ActivationChain>> discover_activation_chain(
    const std::filesystem::path &coordinator_root);
facman::core::Result<LifecycleEpochChain> discover_lifecycle_epoch_chain(
    const std::filesystem::path &coordinator_root);
facman::core::Result<LifecycleEpochChain> publish_lifecycle_epoch(
    const std::filesystem::path &coordinator_root,
    const LifecycleEpoch &proposed, bool apply);
facman::core::Result<RetirementResponse> retire_active(
    const RetirementRequest &request, RetirementEffects &effects);
facman::core::Result<ActiveState> adopt_legacy(
    const std::filesystem::path &coordinator_root,
    const Generation &legacy, bool apply);

// Stable names used by every setup root and every transition kind.
std::filesystem::path global_lock_path(
    const std::filesystem::path &coordinator_root);
std::string generation_record_bytes(const Generation &generation);

} // namespace facman::self_maintenance

#endif
