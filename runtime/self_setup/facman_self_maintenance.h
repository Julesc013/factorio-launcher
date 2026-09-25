// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_SELF_MAINTENANCE_H
#define FACMAN_SELF_MAINTENANCE_H

#include "fl_result.h"

#include <filesystem>
#include <cstdint>
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
  std::string maintenance_launcher_sha256;
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
  std::string retirement_journal_name;
  std::optional<ActiveState> compatibility_active;
  bool compatibility_handoff = false;
  bool compatibility_epoch = false;
};

struct LifecycleEpochChain {
  std::vector<LifecycleEpoch> epochs;
};

struct EpochActiveState {
  LifecycleEpoch epoch;
  ActiveState active;
};

// One read-only answer for public state selection.  A real lifecycle epoch
// takes precedence over the synthesized compatibility view of flat v1
// activation history.  `epoch` is empty only when the selected state is flat.
struct AuthoritativeActiveState {
  std::optional<LifecycleEpoch> epoch;
  ActiveState active;
};

struct EpochGenesisRequest {
  std::filesystem::path coordinator_root;
  std::string epoch_id;
  Generation generation;
  bool apply = false;
};

struct EffectResult;

// A bootstrap moves authority from the compatibility activation history to the
// first epoch without uninstalling that history.  The provider owns the clone
// operation: the coordinator records an entered edge before it is called and
// accepts a retry only after the provider can prove the exact epoch target.
struct CompatibilityAuthorityBootstrapRequest {
  std::filesystem::path coordinator_root;
  PackageDescriptor package_descriptor;
  std::string package_sha256;
  bool shell_integration = true;
  bool apply = false;
};

struct CompatibilityAuthorityBootstrapResponse {
  std::string phase;
  LifecycleEpoch epoch;
  ActiveState active;
  std::filesystem::path journal_directory;
};

// Exact read-only target for reinstall after a completed real-epoch removal.
// The source is retained immutable history; the provider identity is retired.
struct RetiredEpochSuccessorPlan {
  LifecycleEpoch epoch;
  Generation source;
  Generation target;
  bool manifest_published = false;
  bool manifest_staging = false;
};

class CompatibilityAuthorityBootstrapEffects {
public:
  virtual ~CompatibilityAuthorityBootstrapEffects() = default;
  virtual EffectResult inspect_epoch_clone(const Generation &source,
                                           const Generation &target) = 0;
  virtual EffectResult review_epoch_clone(const Generation &source,
                                          const Generation &target) = 0;
  virtual EffectResult clone_epoch(const Generation &source,
                                   const Generation &target) = 0;
  virtual ShellState inspect_epoch_shortcut(const Generation &source,
                                            const Generation &target) = 0;
  virtual ShellState inspect_epoch_registration(const Generation &source,
                                                const Generation &target) = 0;
  virtual EffectResult cutover_epoch_shortcut(const Generation &source,
                                              const Generation &target) = 0;
  virtual EffectResult cutover_epoch_registration(const Generation &source,
                                                  const Generation &target) = 0;
};

struct RetirementStep {
  Generation generation;
  bool active = false;
};

struct RetirementRequest {
  std::filesystem::path coordinator_root;
  bool apply = false;
  bool epoch_mode = false;
  std::filesystem::path logical_root;
  std::filesystem::path state_root;
  std::filesystem::path acceptance_root;
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

// The application supplies the provider/native edge. Its inspection runs
// under the coordinator lock and must reject a foreign provider uninstall
// plan or ambiguous installed identity before entering a step. The
// coordinator persists an entered marker before calling uninstall_generation,
// which makes an interrupted edge recovery-required rather than replayable.
class RetirementEffects {
public:
  virtual ~RetirementEffects() = default;
  virtual facman::core::Result<void> inspect_retirement_generation(
      const Generation &generation, bool active,
      const CoordinatorLockToken &coordinator_lock) = 0;
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

struct RetainedMaintenanceInputs {
  std::filesystem::path package;
  std::string package_sha256;
  std::filesystem::path helper;
  std::string helper_sha256;
};

struct EpochTransitionRequest {
  std::filesystem::path coordinator_root;
  std::string epoch_id;
  Operation operation = Operation::update;
  std::string operation_id;
  PackageInspection package;
  bool apply = false;
  // The exact currently executing setup binary is retained separately from
  // the target package's maintenance launcher.  A downgrade must continue in
  // the newer, protocol-capable process even though it installs an older
  // target launcher for later repair.
  std::filesystem::path continuation_helper;
  std::string continuation_helper_sha256;
  bool shell_integration = true;
  // An absolute UTC deadline supplied by the production caller before the
  // handoff is first published. Zero retains older journal compatibility.
  std::uint64_t deadline_utc_ms = 0;
};

struct EpochTransitionPreparation {
  std::string phase;
  Plan transition;
  std::filesystem::path journal;
  std::string journal_sha256;
  RetainedMaintenanceInputs inputs;
  std::string nonce;
  std::uint64_t deadline_utc_ms = 0;
};

// The provider review receipt in the handoff is insufficient to replay an
// external apply after a process exit.  This immutable binding records the
// exact transaction and canonical apply request chosen by the provider.
struct ProviderApplyBinding {
  std::string provider_plan_sha256;
  std::string transaction_id;
  std::string apply_sha256;
  std::string apply_payload;
  std::string semantic_digest;
  std::string bridge_key;
  std::string reviewed_plan_id;
  std::string reviewed_plan_digest;
  std::string plan_created_at;
  std::string request_id;
};

struct EpochContinuationRequest {
  std::filesystem::path coordinator_root;
  std::string operation_id;
  std::string nonce;
  std::string journal_sha256;
  bool apply = false;
};

struct EpochContinuationResponse {
  std::string phase;
  Plan transition;
  std::filesystem::path journal;
  ProviderApplyBinding provider;
};

struct EpochPublicationRequest {
  std::filesystem::path coordinator_root;
  std::string operation_id;
  std::string nonce;
  std::string journal_sha256;
  bool apply = false;
};

struct EpochPublicationResponse {
  std::string phase;
  Generation generation;
  std::filesystem::path journal;
};

// Completes only the native ownership hand-off for an already published epoch
// genesis.  It deliberately has no generation, activation, or provider-apply
// authority.
struct EpochShellCutoverRequest {
  std::filesystem::path coordinator_root;
  std::string operation_id;
  std::string nonce;
  std::string journal_sha256;
  bool apply = false;
};

struct EpochShellCutoverResponse {
  std::string phase;
  Generation generation;
  std::filesystem::path journal;
};

// Read-only recovery discovery for the one exact, unfinished maintenance
// transition at the lifecycle tail.  It deliberately exposes only immutable
// handoff identity, never a caller-supplied filesystem path.
struct EpochPendingTransition {
  std::string epoch_id;
  std::string epoch_manifest_sha256;
  Operation operation = Operation::update;
  std::string operation_id;
  std::string nonce;
  std::string journal_sha256;
  PackageInspection retained_package;
  RetainedMaintenanceInputs retained_inputs;
  Generation target;
  std::string source_activation_name;
  std::string source_activation_sha256;
  std::string target_activation_name;
  std::string target_activation_sha256;
  bool completed = false;
  bool pre_handoff = false;
  bool shell_integration = true;
  std::uint64_t deadline_utc_ms = 0;
  // pre_handoff, handoff_staging, continuation_pending, publication_pending,
  // shell_cutover_pending, or shell_cutover_complete when completed is true.
  std::string phase;
};

class EpochPublicationEffects {
public:
  virtual ~EpochPublicationEffects() = default;
  virtual EffectResult inspect_installed(
      const Plan &plan, const ProviderApplyBinding &binding) = 0;
  virtual EffectResult validate_terminal_verification(
      const Plan &plan, const ProviderApplyBinding &binding,
      const std::string &receipt_sha256) = 0;
};

class EpochShellCutoverEffects : public EpochPublicationEffects {
public:
  virtual ~EpochShellCutoverEffects() = default;
  virtual ShellState inspect_shortcut(const Plan &plan) = 0;
  virtual ShellState inspect_registration(const Plan &plan) = 0;
  virtual EffectResult cutover_shortcut(const Plan &plan) = 0;
  virtual EffectResult cutover_registration(const Plan &plan) = 0;
  virtual EffectResult retire_shortcut_backup(const Plan &plan) = 0;
};

class EpochPreparationEffects {
public:
  virtual ~EpochPreparationEffects() = default;
  virtual CandidateState inspect_candidate(const Plan &plan) = 0;
  virtual EffectResult review_install_local(const Plan &plan) = 0;
  virtual facman::core::Result<RetainedMaintenanceInputs> retain_handoff_inputs(
      const Plan &plan, const std::filesystem::path &continuation_helper,
      const std::string &continuation_helper_sha256) = 0;
};

// This deliberately stops at an exact provider-verified candidate.  A later
// slice owns generation publication, activation, and native shell cutover.
class EpochContinuationEffects : public EpochPublicationEffects {
public:
  virtual ~EpochContinuationEffects() = default;
  virtual CandidateState inspect_candidate(const Plan &plan) = 0;
  virtual facman::core::Result<ProviderApplyBinding> bind_install_local(
      const Plan &plan, const std::string &expected_provider_plan_sha256) = 0;
  virtual facman::core::Result<void> rehydrate_install_local(
      const Plan &plan, const ProviderApplyBinding &binding) = 0;
  // Retains the already admitted handoff package and maintenance helper in
  // the generation-independent offline repair cache.  This is idempotent and
  // must complete before the provider apply-entered record is published.
  virtual EffectResult prepare_install_local(const Plan &plan) = 0;
  virtual EffectResult apply_bound_install_local(
      const Plan &plan, const ProviderApplyBinding &binding) = 0;
  virtual EffectResult inspect_installed(
      const Plan &plan, const ProviderApplyBinding &binding) override = 0;
  virtual EffectResult verify_installed(const Plan &plan) = 0;
  // Revalidates an already durable provider verification receipt by replaying
  // its deterministic read-only verification identity.
  virtual EffectResult validate_terminal_verification(
      const Plan &plan, const ProviderApplyBinding &binding,
      const std::string &receipt_sha256) override = 0;
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
  virtual EffectResult retire_shortcut_backup(const Plan &plan) = 0;
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
// The maintenance descriptor opts a package into strict epoch bootstrap.
// Current-generation-only archives remain on the compatibility Setup path.
// A malformed or partial descriptor is inspected strictly and rejected.
facman::core::Result<bool> has_self_maintenance_metadata(
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
facman::core::Result<EpochActiveState> discover_lifecycle_epoch_active(
    const std::filesystem::path &coordinator_root);
// Returns every validated activation target in the authoritative real epoch,
// including repeated retained generations. Retirement and rollback must use
// this lineage rather than infer ownership from only the active predecessor.
facman::core::Result<ActivationChain> discover_lifecycle_epoch_activation_chain(
    const std::filesystem::path &coordinator_root);
facman::core::Result<std::optional<AuthoritativeActiveState>>
resolve_authoritative_active_state(const std::filesystem::path &coordinator_root);
facman::core::Result<std::optional<EpochPendingTransition>>
discover_lifecycle_epoch_pending_transition(
    const std::filesystem::path &coordinator_root);
// Matches only the exact completed shell cutover at the current active head.
// Callers use it for an idempotent terminal retry after unfinished discovery
// has returned no tail.
facman::core::Result<std::optional<EpochPendingTransition>>
discover_lifecycle_epoch_terminal_transition(
    const std::filesystem::path &coordinator_root);
facman::core::Result<EpochTransitionPreparation> prepare_lifecycle_epoch_transition(
    const EpochTransitionRequest &request, EpochPreparationEffects &effects);
// Read-only admission for an exact immediate predecessor. The existing
// provider installation remains owned and is verified before native cutover.
facman::core::Result<Plan> review_lifecycle_epoch_reactivation(
    const EpochTransitionRequest &request, EpochContinuationEffects &effects);
facman::core::Result<Plan> admit_lifecycle_epoch_continuation(
    const std::filesystem::path &coordinator_root,
    const std::string &operation_id, const std::string &nonce,
    const std::string &journal_sha256);
facman::core::Result<EpochContinuationResponse>
execute_lifecycle_epoch_continuation(const EpochContinuationRequest &request,
                                     EpochContinuationEffects &effects);
facman::core::Result<EpochPublicationResponse>
execute_lifecycle_epoch_publication(const EpochPublicationRequest &request,
                                    EpochPublicationEffects &effects);
facman::core::Result<EpochShellCutoverResponse>
execute_lifecycle_epoch_shell_cutover(const EpochShellCutoverRequest &request,
                                      EpochShellCutoverEffects &effects);
facman::core::Result<LifecycleEpochChain> publish_lifecycle_epoch(
    const std::filesystem::path &coordinator_root,
    const LifecycleEpoch &proposed, bool apply);
facman::core::Result<Generation> make_epoch_genesis_generation(
    const LifecycleEpoch &epoch, const PackageDescriptor &descriptor,
    const std::string &package_sha256);
facman::core::Result<ActiveState> activate_lifecycle_epoch_genesis(
    const EpochGenesisRequest &request);
facman::core::Result<CompatibilityAuthorityBootstrapResponse>
bootstrap_compatibility_authority(
    const CompatibilityAuthorityBootstrapRequest &request,
    CompatibilityAuthorityBootstrapEffects &effects);
facman::core::Result<RetiredEpochSuccessorPlan> plan_retired_epoch_successor(
    const std::filesystem::path &coordinator_root,
    const PackageDescriptor &descriptor, const std::string &package_sha256);
facman::core::Result<void> recover_retired_successor_manifest(
    const std::filesystem::path &coordinator_root,
    const RetiredEpochSuccessorPlan &plan);
facman::core::Result<RetirementResponse> retire_active(
    const RetirementRequest &request, RetirementEffects &effects);
facman::core::Result<ActiveState> adopt_legacy(
    const std::filesystem::path &coordinator_root,
    const Generation &legacy, bool apply);

namespace testing {

// Test-only seam called after an epoch record has been pinned and read.
using EpochRecordPinnedHook = void (*)(const std::filesystem::path &);
void set_epoch_record_pinned_hook(EpochRecordPinnedHook hook) noexcept;
// Test-only seam called after the canonical retained-input operation directory
// has been opened through its held state-root ancestors.
using EpochHandoffOperationPinnedHook = void (*)(const std::filesystem::path &);
void set_epoch_handoff_operation_pinned_hook(
    EpochHandoffOperationPinnedHook hook) noexcept;

} // namespace testing

// Stable names used by every setup root and every transition kind.
std::filesystem::path global_lock_path(
    const std::filesystem::path &coordinator_root);
std::string generation_record_bytes(const Generation &generation);

} // namespace facman::self_maintenance

#endif
