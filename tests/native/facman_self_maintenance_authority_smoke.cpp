// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_self_maintenance.h"

#include "fl_json.h"
#include "fl_file_io.h"
#include "fl_sha256.h"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

namespace fs = std::filesystem;
using facman::self_maintenance::ActiveState;
using facman::self_maintenance::ActivationChain;
using facman::self_maintenance::Generation;
using facman::self_maintenance::LifecycleEpoch;
using facman::self_maintenance::PackageDescriptor;

namespace {

bool require(bool condition, const char *message) {
  if (!condition) std::cerr << message << '\n';
  return condition;
}

std::string digest(const std::string &value) {
  return facman::base::sha256_hex_bytes(
      reinterpret_cast<const unsigned char *>(value.data()), value.size());
}

std::string authority_handoff_bytes(const ActivationChain &chain) {
  std::string chain_identity = "facman.self.retirement-chain.v1\n" +
      chain.activation_name + "\n" + chain.activation_sha256 + "\n";
  for (const Generation &generation : chain.generations)
    chain_identity += generation.generation_id + "\n" +
        facman::self_maintenance::generation_record_bytes(generation);
  facman::core::json::ObjectBuilder record;
  record.add_string("schema", "facman.self_compatibility_authority_handoff.v1");
  record.add_string("product_id", "facman");
  record.add_string("head_name", chain.activation_name);
  record.add_string("head_sha256", chain.activation_sha256);
  record.add_string("chain_digest", digest(chain_identity));
  record.add_string("source_generation_id", chain.generations.back().generation_id);
  record.add_string("source_package_sha256", chain.generations.back().package_sha256);
  return record.serialize() + "\n";
}

PackageDescriptor descriptor() {
  return {"facman", "9.8.7", "generations/9.8.7", std::string(40, 'a'),
          std::string(40, 'b'), "facman.self_maintenance.v1",
          "versioned_generation_with_maintenance_v1", "FacMan.exe",
          "bin/facman.exe", "maintenance/FacManSetup.exe", false};
}

Generation flat_generation(const fs::path &root) {
  auto made = facman::self_maintenance::make_generation(
      descriptor(), std::string(64, 'c'), "facman.self", root / "FacMan",
      root / "FacMan", root / "state", root);
  if (!made) throw std::runtime_error(made.error().message);
  return made.take_value();
}

class RetirementEffects final : public facman::self_maintenance::RetirementEffects {
public:
  facman::core::Result<void> inspect_retirement_generation(
      const Generation &, bool,
      const facman::self_maintenance::CoordinatorLockToken &) override {
    return facman::core::Result<void>::success();
  }
  facman::core::Result<void> uninstall_generation(
      const Generation &generation, bool active,
      const facman::self_maintenance::CoordinatorLockToken &) override {
    removed_install_ids.push_back(generation.install_id);
    active_flags.push_back(active);
    return facman::core::Result<void>::success();
  }
  std::vector<std::string> removed_install_ids;
  std::vector<bool> active_flags;
};

class BootstrapEffects final
    : public facman::self_maintenance::CompatibilityAuthorityBootstrapEffects {
public:
  facman::self_maintenance::EffectResult inspect_epoch_clone(
      const Generation &, const Generation &) override {
    return installed
        ? facman::self_maintenance::EffectResult{true, false,
            digest("exact-epoch-clone\n"), {}}
        : facman::self_maintenance::EffectResult{false, false, {},
            "epoch clone is absent"};
  }
  facman::self_maintenance::EffectResult clone_epoch(
      const Generation &, const Generation &) override {
    ++clone_calls;
    installed = true;
    if (interrupt_clone) {
      interrupt_clone = false;
      return {false, true, {}, "simulated process loss after provider apply"};
    }
    return {true, false, digest("clone-applied\n"), {}};
  }
  facman::self_maintenance::ShellState inspect_epoch_shortcut(
      const Generation &, const Generation &) override {
    return shortcut ? facman::self_maintenance::ShellState::new_exact
        : facman::self_maintenance::ShellState::old_exact;
  }
  facman::self_maintenance::ShellState inspect_epoch_registration(
      const Generation &, const Generation &) override {
    return registration ? facman::self_maintenance::ShellState::new_exact
        : facman::self_maintenance::ShellState::old_exact;
  }
  facman::self_maintenance::EffectResult cutover_epoch_shortcut(
      const Generation &, const Generation &) override {
    shortcut = true;
    return {true, false, digest("shortcut-cutover\n"), {}};
  }
  facman::self_maintenance::EffectResult cutover_epoch_registration(
      const Generation &, const Generation &) override {
    registration = true;
    if (interrupt_registration) {
      interrupt_registration = false;
      return {false, true, {}, "simulated process loss after registration cutover"};
    }
    return {true, false, digest("registration-cutover\n"), {}};
  }
  bool interrupt_clone = true;
  bool interrupt_registration = true;
  bool installed = false;
  bool shortcut = false;
  bool registration = false;
  int clone_calls = 0;
};

LifecycleEpoch publish_epoch(const fs::path &root, const Generation &source,
                             const fs::path &coordinator) {
  LifecycleEpoch proposed;
  proposed.acceptance_root = root;
  proposed.logical_root = source.logical_root;
  proposed.state_root = source.state_root;
  proposed.genesis_generation_id = source.generation_id;
  auto published = facman::self_maintenance::publish_lifecycle_epoch(
      coordinator, proposed, true);
  if (!published || published.value().epochs.empty())
    throw std::runtime_error(!published
        ? published.error().code + ": " + published.error().message
        : "could not publish epoch fixture");
  return published.value().epochs.back();
}

ActiveState activate_epoch(const fs::path &coordinator, const LifecycleEpoch &epoch,
                           const Generation &source) {
  auto generation = facman::self_maintenance::make_epoch_genesis_generation(
      epoch, descriptor(), source.package_sha256);
  if (!generation) throw std::runtime_error(generation.error().message);
  auto active = facman::self_maintenance::activate_lifecycle_epoch_genesis(
      {coordinator, epoch.epoch_id, generation.take_value(), true});
  if (!active) throw std::runtime_error(active.error().message);
  return active.take_value();
}

} // namespace

int main() {
  const fs::path root = fs::temp_directory_path() /
      ("facman-self-maintenance-authority-" + std::to_string(
          static_cast<unsigned long long>(std::chrono::steady_clock::now()
              .time_since_epoch().count())));
  std::error_code ignored;
  fs::remove_all(root, ignored);
  fs::create_directories(root);
  bool ok = true;
  {

  auto empty = facman::self_maintenance::resolve_authoritative_active_state(
      root / "empty" / "coordinator");
  ok &= require(empty && !empty.value().has_value(),
                "empty coordinator exposed authoritative state");

  const fs::path flat_root = root / "flat";
  fs::create_directories(flat_root);
  const fs::path flat_coordinator = flat_root / "coordinator";
  const Generation flat = flat_generation(flat_root);
  auto adopted = facman::self_maintenance::adopt_legacy(
      flat_coordinator, flat, true);
  auto flat_selected = facman::self_maintenance::resolve_authoritative_active_state(
      flat_coordinator);
  ok &= require(adopted && flat_selected && flat_selected.value().has_value() &&
                    !flat_selected.value()->epoch.has_value() &&
                    flat_selected.value()->active.active.install_id == "facman.self",
                "flat active state was not selected exactly");

  const fs::path guarded_root = root / "adoption-epoch-guard";
  const fs::path guarded_coordinator = guarded_root / "coordinator";
  fs::create_directories(guarded_coordinator / "epochs");
  auto guarded_adoption = facman::self_maintenance::adopt_legacy(
      guarded_coordinator, flat_generation(guarded_root), true);
  ok &= require(!guarded_adoption &&
                    guarded_adoption.error().code ==
                        "self_maintenance_epoch_recovery_required" &&
                    !fs::exists(guarded_coordinator / "activations"),
                "direct flat adoption wrote through an epoch namespace");

  const fs::path orphan_coordinator = root / "orphan-retirement" / "coordinator";
  fs::create_directories(orphan_coordinator / "epoch-retirements");
  auto orphan_selected =
      facman::self_maintenance::resolve_authoritative_active_state(
          orphan_coordinator);
  ok &= require(!orphan_selected &&
                    orphan_selected.error().code ==
                        "self_maintenance_epoch_recovery_required",
                "orphan epoch retirement root was treated as empty state");

  // Core persistence only: the production Setup adapter and package are
  // qualified separately. A replay must inspect an entered clone, not apply
  // the provider a second time after an unknown outcome.
  const fs::path handoff_root = root / "authority-handoff";
  const fs::path handoff_coordinator = handoff_root / "coordinator";
  fs::create_directories(handoff_root);
  const Generation handoff_source = flat_generation(handoff_root);
  auto handoff_adopted = facman::self_maintenance::adopt_legacy(
      handoff_coordinator, handoff_source, true);
  auto handoff_chain = facman::self_maintenance::discover_activation_chain(
      handoff_coordinator);
  const std::string handoff_record =
      handoff_chain && handoff_chain.value().has_value()
          ? authority_handoff_bytes(*handoff_chain.value()) : std::string();
  BootstrapEffects bootstrap_effects;
  const facman::self_maintenance::CompatibilityAuthorityBootstrapRequest
      bootstrap_request{handoff_coordinator, descriptor(),
                        handoff_source.package_sha256, true, true};
  auto interrupted = facman::self_maintenance::bootstrap_compatibility_authority(
      bootstrap_request, bootstrap_effects);
  auto pending_handoff =
      facman::self_maintenance::resolve_authoritative_active_state(
          handoff_coordinator);
  auto pending_chain = facman::self_maintenance::discover_lifecycle_epoch_chain(
      handoff_coordinator);
  RetirementEffects handoff_retirement_effects;
  facman::self_maintenance::RetirementRequest handoff_retirement_request;
  handoff_retirement_request.coordinator_root = handoff_coordinator;
  handoff_retirement_request.apply = true;
  auto blocked_retirement = facman::self_maintenance::retire_active(
      handoff_retirement_request, handoff_retirement_effects);
  ok &= require(handoff_adopted && handoff_chain &&
                    handoff_chain.value().has_value() && !handoff_record.empty() &&
                    !pending_handoff &&
                    pending_handoff.error().code ==
                        "self_maintenance_epoch_recovery_required" &&
                    !interrupted && bootstrap_effects.clone_calls == 1 &&
                    pending_chain && pending_chain.value().epochs.size() == 1U &&
                    !pending_chain.value().epochs.front().compatibility_handoff &&
                    !fs::exists(handoff_coordinator / "authority-handoff.v1.json") &&
                    !blocked_retirement &&
                    blocked_retirement.error().code ==
                        "self_maintenance_epoch_recovery_required",
                "interrupted clone did not close flat authority safely");

  auto interrupted_cutover =
      facman::self_maintenance::bootstrap_compatibility_authority(
          bootstrap_request, bootstrap_effects);
  auto pending_cutover =
      facman::self_maintenance::resolve_authoritative_active_state(
          handoff_coordinator);
  ok &= require(!interrupted_cutover && !pending_cutover &&
                    pending_cutover.error().code ==
                        "self_maintenance_epoch_recovery_required" &&
                    bootstrap_effects.clone_calls == 1,
                "interrupted native cutover became authoritative");
  auto handoff_completed =
      facman::self_maintenance::bootstrap_compatibility_authority(
          bootstrap_request, bootstrap_effects);
  auto completed_chain = facman::self_maintenance::discover_lifecycle_epoch_chain(
      handoff_coordinator);
  auto handoff_selected =
      facman::self_maintenance::resolve_authoritative_active_state(
          handoff_coordinator);
  auto handoff_lineage =
      facman::self_maintenance::discover_lifecycle_epoch_activation_chain(
          handoff_coordinator);
  ok &= require(handoff_completed && bootstrap_effects.clone_calls == 1 &&
                    completed_chain && completed_chain.value().epochs.size() == 2U &&
                    completed_chain.value().epochs.front().compatibility_handoff &&
                    completed_chain.value().epochs.front().retirement_sha256 ==
                        digest(handoff_record) &&
                    handoff_selected && handoff_selected.value().has_value() &&
                    handoff_selected.value()->epoch.has_value() &&
                    handoff_selected.value()->active.active.install_id ==
                        handoff_completed.value().active.active.install_id &&
                    handoff_lineage && handoff_lineage.value().generations.size() == 1U &&
                    handoff_lineage.value().generations.front().install_id ==
                        handoff_completed.value().active.active.install_id &&
                    fs::exists(handoff_coordinator / "authority-handoff.v1.json") &&
                    !fs::exists(handoff_coordinator / "retirements"),
                "real epoch did not inherit non-destructive compatibility handoff");
  auto exact_retry = facman::self_maintenance::bootstrap_compatibility_authority(
      bootstrap_request, bootstrap_effects);
  ok &= require(exact_retry && exact_retry.value().phase == "complete" &&
                    bootstrap_effects.clone_calls == 1,
                "completed bootstrap retry called the provider again");

  facman::self_maintenance::RetirementRequest epoch_retirement;
  epoch_retirement.coordinator_root = handoff_coordinator;
  epoch_retirement.epoch_mode = true;
  epoch_retirement.logical_root = handoff_source.logical_root;
  epoch_retirement.state_root = handoff_source.state_root;
  epoch_retirement.acceptance_root = handoff_source.acceptance_root;
  RetirementEffects epoch_retirement_effects;
  auto epoch_retirement_preview = facman::self_maintenance::retire_active(
      epoch_retirement, epoch_retirement_effects);
  epoch_retirement.apply = true;
  auto epoch_retirement_first = facman::self_maintenance::retire_active(
      epoch_retirement, epoch_retirement_effects);
  auto retiring_selected =
      facman::self_maintenance::resolve_authoritative_active_state(
          handoff_coordinator);
  auto epoch_retirement_final = facman::self_maintenance::retire_active(
      epoch_retirement, epoch_retirement_effects);
  auto epoch_retired_selected =
      facman::self_maintenance::resolve_authoritative_active_state(
          handoff_coordinator);
  auto epoch_retirement_repeat = facman::self_maintenance::retire_active(
      epoch_retirement, epoch_retirement_effects);
  ok &= require(epoch_retirement_preview &&
                    epoch_retirement_preview.value().phase == "planned" &&
                    epoch_retirement_preview.value().steps.size() == 2U &&
                    epoch_retirement_preview.value().steps[0].generation.generation_id ==
                        epoch_retirement_preview.value().steps[1].generation.generation_id &&
                    epoch_retirement_preview.value().steps[0].generation.install_id ==
                        "facman.self" &&
                    epoch_retirement_preview.value().steps[1].generation.install_id !=
                        "facman.self" &&
                    epoch_retirement_first &&
                    epoch_retirement_first.value().phase == "step_completed" &&
                    !retiring_selected &&
                    retiring_selected.error().code ==
                        "self_maintenance_retirement_recovery_required" &&
                    epoch_retirement_final &&
                    epoch_retirement_final.value().phase == "completed" &&
                    epoch_retired_selected &&
                    !epoch_retired_selected.value().has_value() &&
                    epoch_retirement_repeat &&
                    epoch_retirement_repeat.value().phase == "completed" &&
                    epoch_retirement_effects.removed_install_ids.size() == 2U &&
                    epoch_retirement_effects.active_flags ==
                        std::vector<bool>({false, true}) &&
                    fs::exists(handoff_coordinator / "authority-handoff.v1.json"),
                "epoch retirement lost a provider identity or repeated an effect");

  auto retired_epochs = facman::self_maintenance::discover_lifecycle_epoch_chain(
      handoff_coordinator);
  auto planned_successor = facman::self_maintenance::plan_retired_epoch_successor(
      handoff_coordinator, descriptor(), handoff_source.package_sha256);
  LifecycleEpoch epoch_successor;
  if (retired_epochs && retired_epochs.value().epochs.size() == 2U) {
    const LifecycleEpoch &predecessor = retired_epochs.value().epochs.back();
    epoch_successor.acceptance_root = predecessor.acceptance_root;
    epoch_successor.logical_root = predecessor.logical_root;
    epoch_successor.state_root = predecessor.state_root;
    epoch_successor.genesis_generation_id = handoff_source.generation_id;
    epoch_successor.predecessor_epoch_id = predecessor.epoch_id;
    epoch_successor.predecessor_manifest_sha256 = predecessor.manifest_sha256;
    epoch_successor.predecessor_retirement_sha256 =
        predecessor.retirement_sha256;
  }
  if (planned_successor)
    epoch_successor.epoch_id = planned_successor.value().epoch.epoch_id;
  auto published_successor = facman::self_maintenance::publish_lifecycle_epoch(
      handoff_coordinator, epoch_successor, true);
  auto published_successor_plan =
      facman::self_maintenance::plan_retired_epoch_successor(
          handoff_coordinator, descriptor(), handoff_source.package_sha256);
  ActiveState successor_activation;
  if (published_successor && published_successor.value().epochs.size() == 3U)
    successor_activation = activate_epoch(handoff_coordinator,
        published_successor.value().epochs.back(), handoff_source);
  auto selected_successor =
      facman::self_maintenance::resolve_authoritative_active_state(
          handoff_coordinator);
  ok &= require(retired_epochs && retired_epochs.value().epochs.size() == 2U &&
                    !retired_epochs.value().epochs.back().retirement_sha256.empty() &&
                    planned_successor &&
                    !planned_successor.value().manifest_published &&
                    planned_successor.value().epoch.epoch_id ==
                        epoch_successor.epoch_id &&
                    planned_successor.value().source.install_id ==
                        epoch_retirement_preview.value().steps.back().generation.install_id &&
                    published_successor &&
                    published_successor.value().epochs.size() == 3U &&
                    published_successor_plan &&
                    published_successor_plan.value().manifest_published &&
                    published_successor_plan.value().epoch.epoch_id ==
                        published_successor.value().epochs.back().epoch_id &&
                    selected_successor &&
                    selected_successor.value().has_value() &&
                    selected_successor.value()->epoch.has_value() &&
                    selected_successor.value()->epoch->epoch_id ==
                        published_successor.value().epochs.back().epoch_id &&
                    selected_successor.value()->active.active.install_id ==
                        successor_activation.active.install_id,
                "completed real epoch retirement did not admit an active successor");

  const fs::path partial_root = root / "partial-bootstrap-manifest";
  const fs::path partial_coordinator = partial_root / "coordinator";
  fs::create_directories(partial_root);
  const Generation partial_source = flat_generation(partial_root);
  auto partial_adopted = facman::self_maintenance::adopt_legacy(
      partial_coordinator, partial_source, true);
  BootstrapEffects partial_effects;
  partial_effects.interrupt_clone = false;
  partial_effects.interrupt_registration = false;
  facman::self_maintenance::CompatibilityAuthorityBootstrapRequest
      partial_request{partial_coordinator, descriptor(),
                      partial_source.package_sha256, true, false};
  auto partial_preview = facman::self_maintenance::bootstrap_compatibility_authority(
      partial_request, partial_effects);
  partial_request.apply = true;
  // The fourth immutable publication is the first epoch manifest. Its
  // flushed staging file must survive the injected pre-rename interruption.
  facman::platform::testing::set_relative_publish_pre_rename_fault_countdown(4U);
  auto partial_interrupted = facman::self_maintenance::bootstrap_compatibility_authority(
      partial_request, partial_effects);
  facman::platform::testing::set_relative_publish_pre_rename_fault_countdown(0U);
  const fs::path partial_epoch = partial_preview
      ? partial_coordinator / "epochs" / partial_preview.value().epoch.epoch_id
      : fs::path();
  const bool staged_manifest = partial_preview && !partial_interrupted &&
      fs::exists(partial_epoch / "epoch.staging.v1.json") &&
      !fs::exists(partial_epoch / "epoch.v1.json");
  auto partial_recovered = facman::self_maintenance::bootstrap_compatibility_authority(
      partial_request, partial_effects);
  auto partial_selected = facman::self_maintenance::resolve_authoritative_active_state(
      partial_coordinator);
  ok &= require(partial_adopted && staged_manifest && partial_recovered &&
                    partial_recovered.value().phase == "complete" &&
                    partial_effects.clone_calls == 1 && partial_selected &&
                    partial_selected.value().has_value() &&
                    partial_selected.value()->epoch.has_value() &&
                    fs::exists(partial_epoch / "epoch.v1.json") &&
                    !fs::exists(partial_epoch / "epoch.staging.v1.json"),
                "interrupted epoch manifest did not recover from its verified handoff");

  const fs::path foreign_root = root / "foreign-handoff";
  const fs::path foreign_coordinator = foreign_root / "coordinator";
  fs::create_directories(foreign_root);
  auto foreign_adopted = facman::self_maintenance::adopt_legacy(
      foreign_coordinator, flat_generation(foreign_root), true);
  std::ofstream(foreign_coordinator / "authority-handoff.v1.json",
                std::ios::binary) << "{}\n";
  auto foreign_selected =
      facman::self_maintenance::resolve_authoritative_active_state(
          foreign_coordinator);
  ok &= require(foreign_adopted && !foreign_selected &&
                    foreign_selected.error().code ==
                        "self_maintenance_epoch_recovery_required",
                "foreign compatibility handoff became authoritative");

  const fs::path unproven_root = root / "unproven-handoff";
  const fs::path unproven_coordinator = unproven_root / "coordinator";
  fs::create_directories(unproven_root);
  auto unproven_adopted = facman::self_maintenance::adopt_legacy(
      unproven_coordinator, flat_generation(unproven_root), true);
  auto unproven_chain = facman::self_maintenance::discover_activation_chain(
      unproven_coordinator);
  if (unproven_chain && unproven_chain.value().has_value())
    std::ofstream(unproven_coordinator / "authority-handoff.v1.json",
                  std::ios::binary) <<
        authority_handoff_bytes(*unproven_chain.value());
  auto unproven_selected =
      facman::self_maintenance::resolve_authoritative_active_state(
          unproven_coordinator);
  ok &= require(unproven_adopted && unproven_chain &&
                    unproven_chain.value().has_value() && !unproven_selected &&
                    unproven_selected.error().code ==
                        "self_maintenance_epoch_recovery_required",
                "valid handoff bytes without clone journal became authoritative");

  const fs::path epoch_root = root / "epoch";
  fs::create_directories(epoch_root);
  const fs::path epoch_coordinator = epoch_root / "coordinator";
  const Generation epoch_source = flat_generation(epoch_root);
  const LifecycleEpoch epoch = publish_epoch(epoch_root, epoch_source, epoch_coordinator);
  const ActiveState epoch_active = activate_epoch(
      epoch_coordinator, epoch, epoch_source);
  auto epoch_selected = facman::self_maintenance::resolve_authoritative_active_state(
      epoch_coordinator);
  ok &= require(epoch_selected && epoch_selected.value().has_value() &&
                    epoch_selected.value()->epoch.has_value() &&
                    epoch_selected.value()->epoch->epoch_id == epoch.epoch_id &&
                    epoch_selected.value()->active.active.install_root ==
                        epoch_active.active.install_root,
                "real epoch active state was not selected exactly");

  const fs::path malformed = root / "malformed" / "coordinator" / "epochs" /
      std::string(64, 'd');
  fs::create_directories(malformed);
  auto malformed_selected =
      facman::self_maintenance::resolve_authoritative_active_state(
          malformed.parent_path().parent_path());
  ok &= require(!malformed_selected &&
                    malformed_selected.error().code ==
                        "self_maintenance_epoch_recovery_required",
                "incomplete epoch did not refuse authoritative selection");

  RetirementEffects retirement_effects;
  facman::self_maintenance::RetirementRequest flat_retirement_request;
  flat_retirement_request.coordinator_root = flat_coordinator;
  flat_retirement_request.apply = true;
  auto retired = facman::self_maintenance::retire_active(
      flat_retirement_request, retirement_effects);
  auto retired_selected =
      facman::self_maintenance::resolve_authoritative_active_state(
          flat_coordinator);
  auto compatibility = facman::self_maintenance::discover_lifecycle_epoch_chain(
      flat_coordinator);
  LifecycleEpoch successor;
  if (compatibility && compatibility.value().epochs.size() == 1U) {
    const auto &predecessor = compatibility.value().epochs.back();
    successor.acceptance_root = predecessor.acceptance_root;
    successor.logical_root = predecessor.logical_root;
    successor.state_root = predecessor.state_root;
    successor.genesis_generation_id = flat.generation_id;
    successor.predecessor_epoch_id = predecessor.epoch_id;
    successor.predecessor_manifest_sha256 = predecessor.manifest_sha256;
    successor.predecessor_retirement_sha256 = predecessor.retirement_sha256;
  }
  auto successor_chain = facman::self_maintenance::publish_lifecycle_epoch(
      flat_coordinator, successor, true);
  ActiveState successor_active;
  if (successor_chain && successor_chain.value().epochs.size() == 2U)
    successor_active = activate_epoch(flat_coordinator,
        successor_chain.value().epochs.back(), flat);
  auto successor_selected =
      facman::self_maintenance::resolve_authoritative_active_state(flat_coordinator);
  ok &= require(retired && retired.value().phase == "completed" &&
                    retired_selected && !retired_selected.value().has_value() &&
                    compatibility &&
                    compatibility.value().epochs.size() == 1U &&
                    compatibility.value().epochs.front().compatibility_epoch &&
                    successor_chain && successor_chain.value().epochs.size() == 2U &&
                    !successor_active.active.install_id.empty() && successor_selected &&
                    successor_selected.value().has_value() &&
                    successor_selected.value()->epoch.has_value() &&
                    successor_selected.value()->epoch->epoch_id ==
                        successor_chain.value().epochs.back().epoch_id &&
                    successor_selected.value()->active.active.install_root ==
                        successor_active.active.install_root &&
                    successor_selected.value()->active.active.install_root !=
                        flat.install_root,
                "real epoch tail did not replace the retired compatibility head");
  }

  fs::remove_all(root, ignored);
  return ok ? 0 : 1;
}
