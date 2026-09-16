// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_self_maintenance.h"

#include "fl_file_io.h"
#include "fl_local_operation_lock.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"

#include <filesystem>
#include <chrono>
#include <fstream>
#include <functional>
#include <iostream>
#include <iterator>
#include <stdexcept>
#include <string>

namespace fs = std::filesystem;
using facman::self_maintenance::CandidateState;
using facman::self_maintenance::EffectResult;
using facman::self_maintenance::Generation;
using facman::self_maintenance::Operation;
using facman::self_maintenance::Plan;
using facman::self_maintenance::Request;
using facman::self_maintenance::ShellState;

namespace {

std::string sha(const std::string &value) {
  return facman::base::sha256_hex_bytes(
      reinterpret_cast<const unsigned char *>(value.data()), value.size());
}

fs::path physical_generation_root(const fs::path &logical_root,
                                  const std::string &generation_id) {
  const std::string logical_identity = sha("facman.self.logical-root.v1\n" +
      facman::platform::path_to_utf8(logical_root.lexically_normal()) + "\n");
  const std::string physical_identity = sha(
      "facman.self.physical-generation-root.v1\n" + logical_identity + "\n" +
      generation_id + "\n");
  return logical_root.parent_path() /
      facman::platform::path_from_utf8("FacMan.generation." +
                                        physical_identity);
}

fs::path predecessor_physical_generation_root(
    const fs::path &logical_root, const std::string &generation_id) {
  const std::string logical_identity = sha("facman.self.logical-root.v1\n" +
      facman::platform::path_to_utf8(logical_root.lexically_normal()) + "\n");
  return logical_root.parent_path() / facman::platform::path_from_utf8(
      "FacMan.generation." + logical_identity + "." + generation_id);
}

std::string generation_identity(const std::string &version,
                                const std::string &package_sha256,
                                char fill) {
  const std::string revision(40, fill);
  return sha("facman.self.generation.v1\nfacman\n" + version + "\n" +
      package_sha256 + "\n" + revision + "\n" + revision + "\n" +
      "facman.self_maintenance.v1\n"
      "versioned_generation_with_maintenance_v1\n" +
      "generations/" + version + "\nFacMan.exe\nbin/facman.exe\n"
      "maintenance/FacManSetup.exe\n");
}

struct FakeEffects final : facman::self_maintenance::Effects {
  CandidateState candidate = CandidateState::absent;
  ShellState shortcut = ShellState::old_exact;
  ShellState registration = ShellState::old_exact;
  bool fail_install = false;
  bool fail_prepare = false;
  unsigned review_calls = 0;
  unsigned prepare_calls = 0;
  bool fail_verify = false;
  unsigned install_calls = 0;
  unsigned inspect_calls = 0;
  unsigned verify_calls = 0;
  unsigned shortcut_calls = 0;
  unsigned registration_calls = 0;
  std::string provider_operation;
  std::function<void()> after_review;

  CandidateState inspect_candidate(const Plan &) override { return candidate; }
  EffectResult review_install_local(const Plan &) override {
    ++review_calls;
    if (after_review) after_review();
    return {!fail_prepare, false, sha("review"),
            fail_prepare ? "plan refused" : ""};
  }
  EffectResult prepare_install_local(const Plan &) override {
    ++prepare_calls;
    return {true, false, sha("prepare"), ""};
  }
  EffectResult install_local(const Plan &plan) override {
    ++install_calls;
    provider_operation = plan.provider_operation;
    if (fail_install) return {false, true, {}, "lost receipt"};
    candidate = CandidateState::exact;
    return {true, false, sha("install"), {}};
  }
  EffectResult inspect_installed(const Plan &) override {
    ++inspect_calls;
    return {candidate == CandidateState::exact, false, sha("inspect"), {}};
  }
  EffectResult verify_installed(const Plan &) override {
    ++verify_calls;
    return {!fail_verify, false, sha("verify"), "verification failure"};
  }
  ShellState inspect_shortcut(const Plan &) override { return shortcut; }
  ShellState inspect_registration(const Plan &) override { return registration; }
  EffectResult cutover_shortcut(const Plan &) override {
    ++shortcut_calls;
    shortcut = ShellState::new_exact;
    return {true, false, sha("shortcut"), {}};
  }
  EffectResult cutover_registration(const Plan &) override {
    ++registration_calls;
    registration = ShellState::new_exact;
    return {true, false, sha("registration"), {}};
  }
};

Generation generation(const fs::path &root, const std::string &version,
                      char fill) {
  const std::string package_sha256(64, fill);
  const std::string digest = generation_identity(version, package_sha256, fill);
  const fs::path logical_root = root.parent_path() / "FacMan";
  const fs::path install_root = physical_generation_root(logical_root, digest);
  return {digest, version, package_sha256, std::string(40, fill),
          std::string(40, fill), "facman.self.generation." + digest,
          install_root, logical_root,
          root.parent_path() / "state", root.parent_path(),
          install_root / "generations" / version / "FacMan.exe",
          install_root / "maintenance" / "FacManSetup.exe"};
}

Request request(const fs::path &root, Operation operation,
                const std::string &version = "0.1.0-alpha.6") {
  Request value;
  value.operation = operation;
  value.operation_id = operation == Operation::update ? "maintenance.update.one"
      : operation == Operation::downgrade ? "maintenance.downgrade.one"
                                          : "maintenance.rollback.one";
  value.coordinator_root = root / "coordinator";
  value.logical_root = root / "FacMan";
  value.state_root = root / "state";
  value.acceptance_root = root;
  value.package = root / "FacManSetup.zip";
  value.package_sha256 = sha("package");
  value.package_descriptor = {
      "facman", version, "generations/" + version,
      std::string(40, 'c'), std::string(40, 'd'),
      "facman.self_maintenance.v1",
      "versioned_generation_with_maintenance_v1",
      "FacMan.exe", "bin/facman.exe", "maintenance/FacManSetup.exe", false};
  value.active = generation(root / "legacy", "0.1.0-alpha.5", 'a');
  value.rollback_target = generation(root / "older", "0.1.0-alpha.4", 'b');
  value.previous_activation_name =
      "activation.migration.genesis.v1.json";
  const std::string previous =
      "{\"operation\":\"migration\",\"operation_id\":\"migration.genesis\","
      "\"previous\":{\"name\":\"\",\"sha256\":\"\"},"
      "\"generation_id\":\"" + value.active.generation_id +
      "\",\"product_id\":\"facman\",\"schema\":"
      "\"facman.self_activation.v1\"}\n";
  value.previous_activation_sha256 = sha(previous);
  std::string detail;
  if (!facman::base::write_text_new_atomic(
          value.coordinator_root / "activations" /
              value.previous_activation_name,
          previous, detail) &&
      !fs::is_regular_file(value.coordinator_root / "activations" /
                           value.previous_activation_name))
    throw std::runtime_error(detail);
  if (!facman::base::write_text_new_atomic(
          value.coordinator_root / "generations" /
              ("generation." + value.active.generation_id + ".v1.json"),
          facman::self_maintenance::generation_record_bytes(value.active),
          detail) &&
      !fs::is_regular_file(value.coordinator_root / "generations" /
                           ("generation." + value.active.generation_id +
                            ".v1.json")))
    throw std::runtime_error(detail);
  fs::create_directories(value.package.parent_path());
  std::ofstream(value.package, std::ios::binary) << "package";
  return value;
}

bool require(bool condition, const char *message) {
  if (!condition) std::cerr << message << '\n';
  return condition;
}

std::string bytes(const fs::path &path) {
  std::ifstream input(path, std::ios::binary);
  return {std::istreambuf_iterator<char>(input),
          std::istreambuf_iterator<char>()};
}

std::string activation_bytes(const std::string &operation_id,
                             const std::string &source,
                             const std::string &target,
                             const std::string &previous_name,
                             const std::string &previous_sha256) {
  return "{\"operation\":\"update\",\"operation_id\":\"" + operation_id +
      "\",\"previous\":{\"name\":\"" + previous_name +
      "\",\"sha256\":\"" + previous_sha256 +
      "\"},\"product_id\":\"facman\",\"schema\":"
      "\"facman.self_activation.v1\",\"source_generation_id\":\"" +
      source + "\",\"target_generation_id\":\"" + target + "\"}\n";
}

void replace_file(const fs::path &path, const std::string &content) {
  std::ofstream output(path, std::ios::binary | std::ios::trunc);
  output << content;
  if (!output) throw std::runtime_error("could not replace test record");
}

} // namespace

int main() {
  const fs::path root = fs::temp_directory_path() /
      ("facman-self-maintenance-" + std::to_string(
          static_cast<unsigned long long>(std::chrono::steady_clock::now()
                                              .time_since_epoch().count())));
  std::error_code ignored;
  fs::remove_all(root, ignored);
  fs::create_directories(root);
  bool ok = true;

  const facman::self_maintenance::PackageDescriptor legacy_descriptor{
      "facman", "0.1.0-alpha.5", "generations/0.1.0-alpha.5",
      std::string(40, '9'), std::string(40, '8'),
      "facman.self_maintenance.v1",
      "versioned_generation_with_maintenance_v1", "FacMan.exe",
      "bin/facman.exe", "maintenance/FacManSetup.exe", false};
  auto legacy_result = facman::self_maintenance::make_generation(
      legacy_descriptor, std::string(64, '7'), "facman.self",
      root / "legacy-adoption" / "FacMan",
      root / "legacy-adoption" / "FacMan",
      root / "legacy-adoption" / "state",
      root / "legacy-adoption");
  if (!legacy_result) throw std::runtime_error(legacy_result.error().message);
  auto legacy = legacy_result.take_value();
  const fs::path legacy_coordinator =
      root / "legacy-adoption" / "coordinator";
  auto legacy_preview = facman::self_maintenance::adopt_legacy(
      legacy_coordinator, legacy, false);
  ok &= require(legacy_preview &&
                    !fs::exists(legacy_coordinator / "activations"),
                "legacy migration preview wrote coordinator state");
  fs::create_directories(legacy_coordinator / "activations");
  fs::create_directories(legacy_coordinator / "generations");
  std::string partial_detail;
  if (!facman::base::write_text_new_atomic(
          legacy_coordinator / "generations" /
              ("generation." + legacy.generation_id + ".v1.json"),
          facman::self_maintenance::generation_record_bytes(legacy),
          partial_detail))
    throw std::runtime_error(partial_detail);
  auto legacy_adopted = facman::self_maintenance::adopt_legacy(
      legacy_coordinator, legacy, true);
  auto legacy_repeated = facman::self_maintenance::adopt_legacy(
      legacy_coordinator, legacy, true);
  auto legacy_discovered = facman::self_maintenance::discover_active(
      legacy_coordinator);
  ok &= require(legacy_adopted && legacy_repeated && legacy_discovered &&
                    legacy_discovered.value().has_value() &&
                    legacy_discovered.value()->active.install_id ==
                        "facman.self" &&
                    !legacy_discovered.value()->previous.has_value() &&
                    bytes(legacy_adopted.value().activation_name.empty()
                        ? fs::path()
                        : legacy_coordinator / "activations" /
                            legacy_adopted.value().activation_name)
                            .find("\"operation\":\"migration\"") !=
                        std::string::npos,
                "legacy genesis adoption was not deterministic and idempotent");

  const fs::path legacy_sequence = root / "legacy-sequence";
  const fs::path legacy_sequence_coordinator =
      legacy_sequence / "coordinator";
  fs::create_directories(legacy_sequence_coordinator / "activations");
  fs::create_directories(legacy_sequence_coordinator / "generations");
  const fs::path legacy_sequence_package = legacy_sequence / "baseline.zip";
  fs::create_directories(legacy_sequence_package.parent_path());
  std::ofstream(legacy_sequence_package, std::ios::binary)
      << "legacy sequence baseline";
  const std::string legacy_sequence_package_sha =
      sha("legacy sequence baseline");
  const facman::self_maintenance::PackageDescriptor
      legacy_sequence_descriptor{
          "facman", "0.1.0-alpha.5", "generations/0.1.0-alpha.5",
          std::string(40, '5'), std::string(40, '6'),
          "facman.self_maintenance.v1",
          "versioned_generation_with_maintenance_v1", "FacMan.exe",
          "bin/facman.exe", "maintenance/FacManSetup.exe", false};
  auto legacy_sequence_generation = facman::self_maintenance::make_generation(
      legacy_sequence_descriptor, legacy_sequence_package_sha, "facman.self",
      legacy_sequence / "FacMan", legacy_sequence / "FacMan",
      legacy_sequence / "state", legacy_sequence);
  if (!legacy_sequence_generation)
    throw std::runtime_error(legacy_sequence_generation.error().message);
  auto legacy_sequence_adopted = facman::self_maintenance::adopt_legacy(
      legacy_sequence_coordinator, legacy_sequence_generation.value(), true);
  if (!legacy_sequence_adopted)
    throw std::runtime_error(legacy_sequence_adopted.error().message);

  auto legacy_sequence_update = request(
      root / "legacy-sequence-update-input", Operation::update,
      "0.1.0-alpha.6");
  legacy_sequence_update.operation_id = "maintenance.legacy.update";
  legacy_sequence_update.coordinator_root = legacy_sequence_coordinator;
  legacy_sequence_update.logical_root = legacy_sequence / "FacMan";
  legacy_sequence_update.state_root = legacy_sequence / "state";
  legacy_sequence_update.acceptance_root = legacy_sequence;
  legacy_sequence_update.active = legacy_sequence_adopted.value().active;
  legacy_sequence_update.previous_activation_name =
      legacy_sequence_adopted.value().activation_name;
  legacy_sequence_update.previous_activation_sha256 =
      legacy_sequence_adopted.value().activation_sha256;
  legacy_sequence_update.rollback_target = {};
  legacy_sequence_update.apply = true;
  FakeEffects legacy_sequence_update_effects;
  auto legacy_sequence_updated = facman::self_maintenance::execute(
      legacy_sequence_update, legacy_sequence_update_effects);
  auto legacy_sequence_after_update = facman::self_maintenance::discover_active(
      legacy_sequence_coordinator);
  ok &= require(legacy_sequence_updated && legacy_sequence_after_update &&
                    legacy_sequence_after_update.value().has_value() &&
                    legacy_sequence_after_update.value()->previous.has_value() &&
                    legacy_sequence_after_update.value()->previous->install_id ==
                        "facman.self",
                "legacy A to side-by-side B update did not retain exact A");

  auto legacy_sequence_downgrade = request(
      root / "legacy-sequence-downgrade-input", Operation::downgrade,
      "0.1.0-alpha.5");
  legacy_sequence_downgrade.operation_id = "maintenance.legacy.downgrade";
  legacy_sequence_downgrade.coordinator_root = legacy_sequence_coordinator;
  legacy_sequence_downgrade.logical_root = legacy_sequence / "FacMan";
  legacy_sequence_downgrade.state_root = legacy_sequence / "state";
  legacy_sequence_downgrade.acceptance_root = legacy_sequence;
  legacy_sequence_downgrade.package = legacy_sequence_package;
  legacy_sequence_downgrade.package_sha256 = legacy_sequence_package_sha;
  legacy_sequence_downgrade.package_descriptor = legacy_sequence_descriptor;
  legacy_sequence_downgrade.active =
      legacy_sequence_after_update.value()->active;
  legacy_sequence_downgrade.rollback_target =
      *legacy_sequence_after_update.value()->previous;
  legacy_sequence_downgrade.previous_activation_name =
      legacy_sequence_after_update.value()->activation_name;
  legacy_sequence_downgrade.previous_activation_sha256 =
      legacy_sequence_after_update.value()->activation_sha256;
  legacy_sequence_downgrade.apply = true;
  FakeEffects legacy_sequence_downgrade_effects;
  legacy_sequence_downgrade_effects.candidate = CandidateState::exact;
  auto retained_downgrade_plan = facman::self_maintenance::plan(
      legacy_sequence_downgrade);
  auto substituted_retained_downgrade = legacy_sequence_downgrade;
  substituted_retained_downgrade.rollback_target.install_root =
      legacy_sequence / "substituted-retained-root";
  substituted_retained_downgrade.rollback_target.gui =
      substituted_retained_downgrade.rollback_target.install_root /
      "generations" / "0.1.0-alpha.5" / "FacMan.exe";
  substituted_retained_downgrade.rollback_target.maintenance_launcher =
      substituted_retained_downgrade.rollback_target.install_root /
      "maintenance" / "FacManSetup.exe";
  const auto substituted_retained_plan = facman::self_maintenance::plan(
      substituted_retained_downgrade);
  auto legacy_sequence_downgraded = facman::self_maintenance::execute(
      legacy_sequence_downgrade, legacy_sequence_downgrade_effects);
  auto legacy_sequence_after_downgrade =
      facman::self_maintenance::discover_active(legacy_sequence_coordinator);
  ok &= require(retained_downgrade_plan && legacy_sequence_downgraded &&
                    retained_downgrade_plan.value().target.install_id ==
                        "facman.self" &&
                    retained_downgrade_plan.value().target.install_root ==
                        legacy_sequence / "FacMan" &&
                    legacy_sequence_downgrade_effects.review_calls == 0U &&
                    legacy_sequence_downgrade_effects.install_calls == 0U &&
                    legacy_sequence_downgrade_effects.inspect_calls == 1U &&
                    legacy_sequence_downgrade_effects.verify_calls == 1U &&
                    !substituted_retained_plan &&
                    substituted_retained_plan.error().code ==
                        "self_maintenance_retained_target_invalid" &&
                    legacy_sequence_after_downgrade &&
                    legacy_sequence_after_downgrade.value().has_value() &&
                    legacy_sequence_after_downgrade.value()->previous.has_value(),
                "downgrade did not reuse and verify the immediate retained legacy A");

  auto legacy_sequence_rollback = request(
      root / "legacy-sequence-rollback-input", Operation::rollback);
  legacy_sequence_rollback.operation_id = "maintenance.legacy.rollback";
  legacy_sequence_rollback.coordinator_root = legacy_sequence_coordinator;
  legacy_sequence_rollback.logical_root = legacy_sequence / "FacMan";
  legacy_sequence_rollback.state_root = legacy_sequence / "state";
  legacy_sequence_rollback.acceptance_root = legacy_sequence;
  legacy_sequence_rollback.active =
      legacy_sequence_after_downgrade.value()->active;
  legacy_sequence_rollback.rollback_target =
      *legacy_sequence_after_downgrade.value()->previous;
  legacy_sequence_rollback.previous_activation_name =
      legacy_sequence_after_downgrade.value()->activation_name;
  legacy_sequence_rollback.previous_activation_sha256 =
      legacy_sequence_after_downgrade.value()->activation_sha256;
  legacy_sequence_rollback.apply = true;
  FakeEffects legacy_sequence_rollback_effects;
  legacy_sequence_rollback_effects.candidate = CandidateState::exact;
  auto legacy_sequence_rolled_back = facman::self_maintenance::execute(
      legacy_sequence_rollback, legacy_sequence_rollback_effects);
  ok &= require(legacy_sequence_rolled_back &&
                    legacy_sequence_rolled_back.value().active.generation_id ==
                        legacy_sequence_updated.value().active.generation_id,
                "retained legacy downgrade did not roll back from A to B");

  auto update = request(root / "update", Operation::update);
  FakeEffects update_effects;
  auto updated = facman::self_maintenance::execute(update, update_effects);
  ok &= require(updated && updated.value().phase == "plan",
                "preview did not remain effect-free");
  ok &= require(update_effects.install_calls == 0 &&
                    update_effects.review_calls == 1 &&
                    update_effects.prepare_calls == 0 &&
                    !fs::exists(update.coordinator_root / "maintenance"),
                "preview produced an effect");
  update.apply = true;
  const auto reviewed_update = facman::self_maintenance::plan(update);
  ok &= require(reviewed_update &&
                    reviewed_update.value().target.install_root !=
                        update.active.install_root &&
                    reviewed_update.value().target.install_id ==
                        "facman.self.generation." +
                            reviewed_update.value().target.generation_id &&
                    reviewed_update.value().target.install_root.filename()
                            .string().size() ==
                        std::string("FacMan.generation.").size() + 64U &&
                    reviewed_update.value().target.install_root.filename()
                            .string().find(
                                reviewed_update.value().target.generation_id) ==
                        std::string::npos &&
                    reviewed_update.value().target.install_root.filename()
                            .string() == "FacMan.generation." +
                                sha("facman.self.physical-generation-root.v1\n" +
                                    sha("facman.self.logical-root.v1\n" +
                                        facman::platform::path_to_utf8(
                                            update.logical_root.lexically_normal()) +
                                        "\n") + "\n" +
                                    reviewed_update.value().target.generation_id +
                                    "\n"),
                "update did not derive a distinct root and install id");
  auto repeated_physical_plan = facman::self_maintenance::plan(update);
  auto different_generation = update;
  different_generation.package_sha256 = sha("different package");
  const auto different_physical_plan =
      facman::self_maintenance::plan(different_generation);
  ok &= require(repeated_physical_plan && different_physical_plan &&
                    repeated_physical_plan.value().target.install_root ==
                        reviewed_update.value().target.install_root &&
                    different_physical_plan.value().target.generation_id !=
                        reviewed_update.value().target.generation_id &&
                    different_physical_plan.value().target.install_root !=
                        reviewed_update.value().target.install_root,
                "physical generation root was not deterministic and collision-resistant");

#ifdef _WIN32
  auto ci_length = update;
  const fs::path ci_root = fs::path(
      "C:/Users/RUNNER~1/AppData/Local/Temp/facman-self-setup-oq9k_8n0");
  ci_length.logical_root = ci_root / "Programs" / "FacMan";
  ci_length.state_root = ci_root / "SetupState";
  ci_length.acceptance_root = ci_root;
  ci_length.active.logical_root = ci_length.logical_root;
  ci_length.active.state_root = ci_length.state_root;
  ci_length.active.acceptance_root = ci_length.acceptance_root;
  ci_length.active.install_root = physical_generation_root(
      ci_length.logical_root, ci_length.active.generation_id);
  ci_length.active.gui = ci_length.active.install_root / "generations" /
      ci_length.active.product_version / "FacMan.exe";
  ci_length.active.maintenance_launcher = ci_length.active.install_root /
      "maintenance" / "FacManSetup.exe";
  const auto ci_plan = facman::self_maintenance::plan(ci_length);
  ok &= require(ci_plan &&
                    ci_plan.value().target.install_root.filename().string().size() ==
                        std::string("FacMan.generation.").size() + 64U &&
                    ci_plan.value().target.install_root.native().size() < 259U &&
                    ci_plan.value().target.gui.native().size() < 259U,
                "CI-length logical root did not produce a provider-admissible target");
#endif
  updated = facman::self_maintenance::execute(update, update_effects);
  if (!updated) std::cerr << "update error: " << updated.error().code << ": "
                          << updated.error().message << ": "
                          << updated.error().detail << '\n';
  ok &= require(updated && updated.value().phase == "completed",
                "update did not complete");
  ok &= require(update_effects.provider_operation == "install_local" &&
                    update_effects.install_calls == 1 &&
                    update_effects.inspect_calls == 1 &&
                    update_effects.verify_calls == 1,
                "update did not install, inspect, and verify through install_local");
  ok &= require(update_effects.shortcut_calls == 1 &&
                    update_effects.registration_calls == 1,
                "update did not cut over both exact shell objects");
  ok &= require(fs::is_regular_file(updated.value().generation_record) &&
                    fs::is_regular_file(updated.value().activation_record),
                "update did not append generation and activation records");
  const auto discovered_after_update =
      facman::self_maintenance::discover_active(update.coordinator_root);
  ok &= require(discovered_after_update &&
                    discovered_after_update.value().has_value() &&
                    discovered_after_update.value()->active.install_root ==
                        reviewed_update.value().target.install_root &&
                    discovered_after_update.value()->previous.has_value() &&
                    discovered_after_update.value()->previous->install_root ==
                        update.active.install_root,
                "update discovery did not retain the exact physical root mapping");
  const unsigned completed_install_calls = update_effects.install_calls;
  const std::string completed_activation = bytes(updated.value().activation_record);
  const std::string completed_generation = bytes(updated.value().generation_record);
  update_effects.fail_verify = true;
  auto refused_completed = facman::self_maintenance::execute(update,
                                                              update_effects);
  ok &= require(!refused_completed &&
                    refused_completed.error().code ==
                        "self_maintenance_verify_failed" &&
                    bytes(updated.value().activation_record) ==
                        completed_activation &&
                    bytes(updated.value().generation_record) ==
                        completed_generation &&
                    update_effects.install_calls == completed_install_calls &&
                    update_effects.shortcut_calls == 1U &&
                    update_effects.registration_calls == 1U,
                "completed retry accepted failed provider verification or wrote state");
  update_effects.fail_verify = false;
  auto repeated_update = facman::self_maintenance::execute(update, update_effects);
  ok &= require(repeated_update &&
                    update_effects.install_calls == completed_install_calls,
                "completed update retry was not idempotent");

  auto outside_authority = request(root / "outside-authority",
                                   Operation::update);
  outside_authority.apply = true;
  const fs::path outside_coordinator =
      root.parent_path() / (root.filename().string() + "-outside-coordinator");
  fs::remove_all(outside_coordinator, ignored);
  outside_authority.coordinator_root = outside_coordinator;
  FakeEffects outside_authority_effects;
  auto outside_authority_result = facman::self_maintenance::execute(
      outside_authority, outside_authority_effects);
  ok &= require(!outside_authority_result &&
                    outside_authority_result.error().code ==
                        "self_maintenance_lock_unsafe" &&
                    outside_authority_effects.review_calls == 0U &&
                    !fs::exists(outside_coordinator),
                "out-of-authority coordinator admission produced a write");

  auto substituted_coordinator = request(root / "coordinator-substitution",
                                         Operation::update);
  substituted_coordinator.apply = true;
  const fs::path original_coordinator =
      substituted_coordinator.coordinator_root;
  const fs::path moved_coordinator =
      original_coordinator.parent_path() / "moved-coordinator";
  bool coordinator_substituted = false;
  FakeEffects substituted_coordinator_effects;
  substituted_coordinator_effects.after_review = [&] {
    std::error_code move_error;
    fs::rename(original_coordinator, moved_coordinator, move_error);
    if (!move_error) {
      coordinator_substituted = true;
      std::error_code create_error;
      fs::create_directory(original_coordinator, create_error);
      if (create_error)
        throw std::runtime_error("could not create coordinator substitute");
    }
  };
  auto substituted_coordinator_result = facman::self_maintenance::execute(
      substituted_coordinator, substituted_coordinator_effects);
  ok &= require(coordinator_substituted
          ? (!substituted_coordinator_result &&
             substituted_coordinator_result.error().code ==
                 "self_maintenance_lock_unsafe" &&
             !fs::exists(original_coordinator / "setup-operations") &&
             !fs::exists(moved_coordinator / "setup-operations"))
          : (substituted_coordinator_result &&
             !fs::exists(moved_coordinator)),
      "coordinator substitution was neither pinned nor refused before writes");

  auto inactive = request(root / "inactive", Operation::update);
  inactive.apply = true;
  inactive.active = generation(root / "inactive" / "different-active",
                               "0.1.0-alpha.5", 'e');
  FakeEffects inactive_effects;
  auto inactive_result = facman::self_maintenance::execute(
      inactive, inactive_effects);
  ok &= require(!inactive_result && inactive_result.error().code ==
                    "self_maintenance_activation_changed" &&
                    inactive_effects.install_calls == 0,
                "activation head accepted a caller-selected inactive generation");

  auto malformed = request(root / "malformed-activation", Operation::update);
  malformed.apply = true;
  const fs::path malformed_path = malformed.coordinator_root / "activations" /
      malformed.previous_activation_name;
  const std::string malformed_record =
      "{\"schema\":\"facman.self_activation.v1\",\"previous\":{} }\n";
  replace_file(malformed_path, malformed_record);
  malformed.previous_activation_sha256 = sha(malformed_record);
  FakeEffects malformed_effects;
  auto malformed_result = facman::self_maintenance::execute(
      malformed, malformed_effects);
  ok &= require(!malformed_result && malformed_result.error().code ==
                    "self_maintenance_activation_changed",
                "malformed activation record was accepted");

  auto cyclic = request(root / "cyclic-activation", Operation::update);
  cyclic.apply = true;
  const std::string cycle_name = "activation.cycle.v1.json";
  replace_file(cyclic.coordinator_root / "activations" / cycle_name,
               activation_bytes("maintenance.cycle", std::string(64, 'a'),
                                std::string(64, 'a'), cycle_name,
                                std::string(64, 'c')));
  FakeEffects cyclic_effects;
  auto cyclic_result = facman::self_maintenance::execute(cyclic,
                                                         cyclic_effects);
  ok &= require(!cyclic_result && cyclic_result.error().code ==
                    "self_maintenance_activation_changed",
                "activation cycle was accepted");

  auto two_genesis = request(root / "two-genesis", Operation::update);
  two_genesis.apply = true;
  replace_file(two_genesis.coordinator_root / "activations" /
                   "activation.second-genesis.v1.json",
               activation_bytes("maintenance.second-genesis",
                                std::string(64, 'a'), std::string(64, 'a'),
                                "", ""));
  FakeEffects two_genesis_effects;
  auto two_genesis_result = facman::self_maintenance::execute(
      two_genesis, two_genesis_effects);
  ok &= require(!two_genesis_result && two_genesis_result.error().code ==
                    "self_maintenance_activation_changed",
                "multiple activation genesis records were accepted");

  auto mismatched_link = request(root / "mismatched-link", Operation::update);
  mismatched_link.apply = true;
  replace_file(mismatched_link.coordinator_root / "activations" /
                   "activation.mismatched-link.v1.json",
               activation_bytes("maintenance.mismatched-link",
                                std::string(64, 'b'), std::string(64, 'b'),
                                mismatched_link.previous_activation_name,
                                mismatched_link.previous_activation_sha256));
  FakeEffects mismatched_link_effects;
  auto mismatched_link_result = facman::self_maintenance::execute(
      mismatched_link, mismatched_link_effects);
  ok &= require(!mismatched_link_result && mismatched_link_result.error().code ==
                    "self_maintenance_activation_changed",
                "activation child source did not match its parent target");

  auto wrong = request(root / "wrong-direction", Operation::update,
                       "0.1.0-alpha.4");
  auto wrong_plan = facman::self_maintenance::plan(wrong);
  ok &= require(!wrong_plan &&
                    wrong_plan.error().code ==
                        "self_maintenance_version_direction_invalid",
                "update accepted an older version");
  auto downgrade = request(root / "downgrade", Operation::downgrade,
                           "0.1.0-alpha.4");
  auto downgrade_plan = facman::self_maintenance::plan(downgrade);
  ok &= require(downgrade_plan &&
                    downgrade_plan.value().provider_operation == "install_local",
                "downgrade did not accept an older package through install_local");

  Request rollback_success = update;
  rollback_success.operation = Operation::rollback;
  rollback_success.operation_id = "maintenance.rollback.completed-update";
  rollback_success.active = updated.value().active;
  rollback_success.rollback_target = update.active;
  rollback_success.previous_activation_name =
      updated.value().activation_record.filename().string();
  rollback_success.previous_activation_sha256 =
      sha(bytes(updated.value().activation_record));
  rollback_success.package.clear();
  rollback_success.package_sha256.clear();
  FakeEffects rollback_success_effects;
  rollback_success_effects.candidate = CandidateState::exact;
  auto rolled_back = facman::self_maintenance::execute(
      rollback_success, rollback_success_effects);
  ok &= require(rolled_back && rollback_success_effects.install_calls == 0 &&
                    rolled_back.value().active.generation_id ==
                        update.active.generation_id &&
                    updated.value().active.install_root ==
                        reviewed_update.value().target.install_root &&
                    rolled_back.value().active.install_root ==
                        update.active.install_root,
                "rollback did not activate a retained generation without provider mutation");

  auto predecessor_compat = request(root / "predecessor-compat",
                                    Operation::update);
  predecessor_compat.apply = true;
  Generation predecessor = predecessor_compat.active;
  predecessor.install_root = predecessor_physical_generation_root(
      predecessor.logical_root, predecessor.generation_id);
  predecessor.gui = predecessor.install_root / "generations" /
      predecessor.product_version / "FacMan.exe";
  predecessor.maintenance_launcher = predecessor.install_root /
      "maintenance" / "FacManSetup.exe";
  replace_file(predecessor_compat.coordinator_root / "generations" /
                   ("generation." + predecessor.generation_id + ".v1.json"),
               facman::self_maintenance::generation_record_bytes(predecessor));
  predecessor_compat.active = predecessor;
  const auto predecessor_discovered = facman::self_maintenance::discover_active(
      predecessor_compat.coordinator_root);
  ok &= require(predecessor_discovered &&
                    predecessor_discovered.value().has_value() &&
                    predecessor_discovered.value()->active.install_root ==
                        predecessor.install_root,
                "exact predecessor generation root was not discovered");
  FakeEffects predecessor_effects;
  const auto predecessor_updated = facman::self_maintenance::execute(
      predecessor_compat, predecessor_effects);
  ok &= require(predecessor_updated &&
                    predecessor_updated.value().active.install_root !=
                        predecessor.install_root &&
                    predecessor_updated.value().active.install_root.filename()
                        .string().size() ==
                        std::string("FacMan.generation.").size() + 64U,
                "predecessor generation did not update into the current root mapping");
  Request predecessor_rollback = predecessor_compat;
  predecessor_rollback.operation = Operation::rollback;
  predecessor_rollback.operation_id = "maintenance.rollback.predecessor";
  predecessor_rollback.active = predecessor_updated.value().active;
  predecessor_rollback.rollback_target = predecessor;
  predecessor_rollback.previous_activation_name =
      predecessor_updated.value().activation_record.filename().string();
  predecessor_rollback.previous_activation_sha256 =
      sha(bytes(predecessor_updated.value().activation_record));
  predecessor_rollback.package.clear();
  predecessor_rollback.package_sha256.clear();
  FakeEffects predecessor_rollback_effects;
  predecessor_rollback_effects.candidate = CandidateState::exact;
  const auto predecessor_rolled_back = facman::self_maintenance::execute(
      predecessor_rollback, predecessor_rollback_effects);
  ok &= require(predecessor_rolled_back &&
                    predecessor_rolled_back.value().active.install_root ==
                        predecessor.install_root,
                "rollback did not retain the exact predecessor physical root");

  auto interrupted = request(root / "interrupted", Operation::update);
  interrupted.apply = true;
  FakeEffects interrupted_effects;
  interrupted_effects.fail_install = true;
  auto first = facman::self_maintenance::execute(interrupted,
                                                 interrupted_effects);
  ok &= require(!first && first.error().code ==
                    "self_maintenance_outcome_unknown" &&
                    interrupted_effects.shortcut_calls == 0,
                "unknown provider result reached shell cutover");
  interrupted_effects.fail_install = false;
  interrupted_effects.candidate = CandidateState::exact;
  auto recovered = facman::self_maintenance::execute(interrupted,
                                                     interrupted_effects);
  ok &= require(recovered && interrupted_effects.install_calls == 1,
                "exact candidate was not recovered without provider replay");

  auto plan_refused = request(root / "plan-refused", Operation::update);
  plan_refused.apply = true;
  fs::remove_all(plan_refused.coordinator_root, ignored);
  FakeEffects plan_refused_effects;
  plan_refused_effects.fail_prepare = true;
  auto refused_plan = facman::self_maintenance::execute(
      plan_refused, plan_refused_effects);
  ok &= require(!refused_plan &&
                    refused_plan.error().code ==
                        "self_maintenance_plan_failed" &&
                    plan_refused_effects.install_calls == 0 &&
                    plan_refused_effects.prepare_calls == 0 &&
                    !fs::exists(plan_refused.coordinator_root),
                "provider plan refusal created coordinator state or recorded provider entry");

  auto wrong_authority = request(root / "wrong-authority", Operation::update);
  wrong_authority.apply = true;
  wrong_authority.state_root = root / "unreviewed-state";
  FakeEffects authority_effects;
  auto authority_result = facman::self_maintenance::execute(
      wrong_authority, authority_effects);
  ok &= require(!authority_result && authority_effects.review_calls == 0 &&
                    !fs::exists(wrong_authority.coordinator_root /
                                "maintenance"),
                "mismatched lineage authority produced durable writes");

  auto failed_verify = request(root / "failed-verify", Operation::update);
  failed_verify.apply = true;
  FakeEffects failed_effects;
  failed_effects.fail_verify = true;
  auto rejected = facman::self_maintenance::execute(failed_verify,
                                                    failed_effects);
  ok &= require(!rejected && failed_effects.shortcut_calls == 0 &&
                    failed_effects.registration_calls == 0,
                "failed verification reached shell cutover");

  auto rollback = request(root / "rollback", Operation::rollback);
  rollback.apply = true;
  const auto rollback_plan = facman::self_maintenance::plan(rollback);
  ok &= require(rollback_plan && rollback_plan.value().provider_operation == "none",
                "rollback requested a provider mutation");
  if (rollback_plan) {
    const fs::path record = rollback.coordinator_root / "generations" /
        ("generation." + rollback.rollback_target.generation_id + ".v1.json");
    // A rollback may never synthesize a retained-generation record.
    FakeEffects rollback_effects;
    auto missing = facman::self_maintenance::execute(rollback, rollback_effects);
    ok &= require(!missing && !fs::exists(record),
                  "rollback accepted a missing retained generation");
  }

  auto same_root = request(root / "same-root", Operation::rollback);
  same_root.rollback_target = generation(root / "same-root" / "older",
                                         "0.1.0-alpha.4", 'b');
  same_root.rollback_target.install_root = same_root.active.install_root;
  same_root.rollback_target.gui = same_root.active.install_root /
      "generations" / same_root.rollback_target.product_version / "FacMan.exe";
  same_root.rollback_target.maintenance_launcher =
      same_root.active.install_root / "maintenance" / "FacManSetup.exe";
  ok &= require(!facman::self_maintenance::plan(same_root),
                "rollback accepted identical source and target roots");
  auto inconsistent_side_by_side = request(
      root / "inconsistent-side-by-side", Operation::rollback);
  inconsistent_side_by_side.active.install_root =
      inconsistent_side_by_side.active.install_root.parent_path() /
      "FacMan.generation.unrelated";
  inconsistent_side_by_side.active.gui =
      inconsistent_side_by_side.active.install_root / "generations" /
      inconsistent_side_by_side.active.product_version / "FacMan.exe";
  inconsistent_side_by_side.active.maintenance_launcher =
      inconsistent_side_by_side.active.install_root / "maintenance" /
      "FacManSetup.exe";
  ok &= require(!facman::self_maintenance::plan(inconsistent_side_by_side),
                "rollback accepted an inconsistent absolute side-by-side root");
  auto legacy_alternate_root = request(root / "legacy-alternate",
                                       Operation::rollback);
  legacy_alternate_root.active.install_id = "facman.self";
  legacy_alternate_root.active.install_root =
      root / "legacy-alternate" / "alternate";
  legacy_alternate_root.active.gui =
      legacy_alternate_root.active.install_root / "generations" /
      legacy_alternate_root.active.product_version / "FacMan.exe";
  legacy_alternate_root.active.maintenance_launcher =
      legacy_alternate_root.active.install_root / "maintenance" /
      "FacManSetup.exe";
  ok &= require(!facman::self_maintenance::plan(legacy_alternate_root),
                "rollback accepted a legacy record rooted away from its logical root");
  auto relative_rollback = request(root / "relative-rollback",
                                   Operation::rollback);
  relative_rollback.rollback_target = generation(fs::path("relative-root"),
                                                  "0.1.0-alpha.4", 'b');
  ok &= require(!facman::self_maintenance::plan(relative_rollback),
                "rollback accepted relative retained-generation paths");

  auto source_traversal = request(root / "source-traversal",
                                  Operation::rollback);
  source_traversal.active = generation(
      root / "source-traversal" / "legacy", "0.1.0/../../escape", 'a');
  ok &= require(!facman::self_maintenance::plan(source_traversal),
                "rollback accepted a traversal-bearing source version");
  auto source_bad_metadata = request(root / "source-bad-metadata",
                                     Operation::rollback);
  source_bad_metadata.active = generation(
      root / "source-bad-metadata" / "legacy",
      "0.1.0-alpha.5+build..broken", 'a');
  ok &= require(!facman::self_maintenance::plan(source_bad_metadata),
                "rollback accepted malformed source build metadata");
  auto target_traversal = request(root / "target-traversal",
                                  Operation::rollback);
  target_traversal.rollback_target = generation(
      root / "target-traversal" / "older", "0.1.0/../../escape", 'b');
  ok &= require(!facman::self_maintenance::plan(target_traversal),
                "rollback accepted a traversal-bearing target version");
  auto target_bad_metadata = request(root / "target-bad-metadata",
                                     Operation::rollback);
  target_bad_metadata.rollback_target = generation(
      root / "target-bad-metadata" / "older",
      "0.1.0-alpha.4+build..broken", 'b');
  ok &= require(!facman::self_maintenance::plan(target_bad_metadata),
                "rollback accepted malformed target build metadata");
  auto valid_metadata = request(root / "valid-metadata", Operation::rollback);
  valid_metadata.rollback_target = generation(
      root / "valid-metadata" / "older",
      "0.1.0-alpha.4+build.01", 'b');
  ok &= require(facman::self_maintenance::plan(valid_metadata).ok(),
                "rollback rejected valid build metadata");

  auto invalid_phase = request(root / "invalid-phase", Operation::rollback);
  invalid_phase.apply = true;
  const fs::path invalid_phase_directory = invalid_phase.coordinator_root /
      "maintenance" / invalid_phase.operation_id;
  fs::create_directories(invalid_phase_directory);
  const std::string invalid_phase_bytes =
      "{\"operation\":\"rollback\",\"operation_id\":\"" +
      invalid_phase.operation_id +
      "\",\"package_sha256\":\"\",\"phase\":\"20-provider-receipt\","
      "\"product_id\":\"facman\",\"provider_operation\":\"none\","
      "\"receipt_sha256\":\"" + std::string(64, 'd') +
      "\",\"schema\":\"facman.self_maintenance_phase.v1\","
      "\"source_generation_id\":\"" + invalid_phase.active.generation_id +
      "\",\"target_generation_id\":\"" +
      invalid_phase.rollback_target.generation_id + "\"}\n";
  replace_file(invalid_phase_directory / "20-provider-receipt.v1.json",
               invalid_phase_bytes);
  FakeEffects invalid_phase_effects;
  auto invalid_phase_result = facman::self_maintenance::execute(
      invalid_phase, invalid_phase_effects);
  ok &= require(!invalid_phase_result && invalid_phase_result.error().code ==
                    "self_maintenance_record_changed",
                "rollback accepted a provider phase record");

  auto contended = request(root / "contended", Operation::update);
  contended.apply = true;
  fs::create_directories(
      facman::self_maintenance::global_lock_path(contended.coordinator_root)
          .parent_path());
  facman::base::StableLocalLock external;
  auto acquired = external.create(
      facman::self_maintenance::global_lock_path(contended.coordinator_root));
  std::string lock_detail;
  if (acquired.acquired()) external.write_text("external.operation", lock_detail);
  FakeEffects contended_effects;
  auto blocked = facman::self_maintenance::execute(contended,
                                                   contended_effects);
  ok &= require(!blocked && blocked.error().code ==
                    "self_maintenance_lock_contended",
                "global coordinator lock did not serialize roots");
  external.remove_exact(lock_detail);

  fs::remove_all(root, ignored);
  return ok ? 0 : 1;
}
