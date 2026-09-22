// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_self_maintenance.h"

#include <chrono>
#include <filesystem>
#include <iostream>
#include <stdexcept>
#include <string>

namespace fs = std::filesystem;
using facman::self_maintenance::ActiveState;
using facman::self_maintenance::Generation;
using facman::self_maintenance::LifecycleEpoch;
using facman::self_maintenance::PackageDescriptor;

namespace {

bool require(bool condition, const char *message) {
  if (!condition) std::cerr << message << '\n';
  return condition;
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
      const Generation &, bool) override {
    return facman::core::Result<void>::success();
  }
  facman::core::Result<void> uninstall_generation(
      const Generation &, bool,
      const facman::self_maintenance::CoordinatorLockToken &) override {
    return facman::core::Result<void>::success();
  }
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
  auto retired = facman::self_maintenance::retire_active(
      {flat_coordinator, true}, retirement_effects);
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
