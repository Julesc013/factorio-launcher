// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_self_maintenance.h"

#include "fl_archive.h"
#include "fl_file_io.h"
#include "fl_json.h"
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
#include <vector>

namespace fs = std::filesystem;
using facman::self_maintenance::CandidateState;
using facman::self_maintenance::EffectResult;
using facman::self_maintenance::Generation;
using facman::self_maintenance::Operation;
using facman::self_maintenance::Plan;
using facman::self_maintenance::Request;
using facman::self_maintenance::ShellState;

namespace {

fs::path before_reopen_source;
fs::path before_reopen_moved;
fs::path epoch_hook_watch;
fs::path epoch_hook_mutation;
fs::path epoch_hook_second_mutation;
std::string epoch_hook_bytes;
std::string epoch_hook_second_bytes;
bool epoch_hook_called = false;
bool epoch_hook_mutated = false;
bool epoch_hook_mutation_attempted = false;
bool epoch_hook_second_mutated = false;
bool epoch_hook_second_mutation_attempted = false;
fs::path epoch_operation_hook_watch;
fs::path epoch_operation_hook_outside;
bool epoch_operation_hook_called = false;
bool epoch_operation_hook_rename_succeeded = false;
bool epoch_operation_hook_symlink_succeeded = false;
std::string bytes(const fs::path &path);

void substitute_before_reopen(const fs::path &path) {
  if (path != before_reopen_source) return;
  std::error_code error;
  fs::rename(path, before_reopen_moved, error);
  if (error) return;
  std::ofstream(path, std::ios::binary | std::ios::trunc) << "foreign staging bytes";
}

void mutate_epoch_record_after_pin(const fs::path &path) {
  if (path != epoch_hook_watch) return;
  epoch_hook_called = true;
  std::ofstream output(epoch_hook_mutation, std::ios::binary | std::ios::trunc);
  output << epoch_hook_bytes;
}

void replace_epoch_record_after_pin(const fs::path &path) {
  if (path != epoch_hook_watch) return;
  epoch_hook_called = true;
  std::error_code error;
  const fs::path moved = epoch_hook_mutation.parent_path() /
      (epoch_hook_mutation.filename().string() + ".hook-moved");
  fs::rename(epoch_hook_mutation, moved, error);
  if (error) return;
  std::ofstream output(epoch_hook_mutation, std::ios::binary | std::ios::trunc);
  output << epoch_hook_bytes;
  epoch_hook_mutated = static_cast<bool>(output);
}

void replace_epoch_record_and_retained_input_after_pin(const fs::path &path) {
  if (path != epoch_hook_watch) return;
  epoch_hook_called = true;
  const auto replace = [](const fs::path &target, const std::string &content,
                          const std::string &suffix, bool &attempted,
                          bool &mutated) {
    attempted = true;
    std::error_code error;
    const fs::path moved = target.parent_path() /
        (target.filename().string() + suffix);
    fs::rename(target, moved, error);
    if (error) return;
    std::ofstream output(target, std::ios::binary | std::ios::trunc);
    output << content;
    mutated = static_cast<bool>(output);
  };
  replace(epoch_hook_mutation, epoch_hook_bytes, ".hook-moved",
          epoch_hook_mutation_attempted, epoch_hook_mutated);
  replace(epoch_hook_second_mutation, epoch_hook_second_bytes, ".hook-moved",
          epoch_hook_second_mutation_attempted, epoch_hook_second_mutated);
}

void overwrite_epoch_record_in_place_after_pin(const fs::path &path) {
  if (path != epoch_hook_watch) return;
  epoch_hook_called = true;
  std::string original = bytes(path);
  if (original.empty()) return;
  original[0] = original[0] == '{' ? '[' : '{';
  std::ofstream output(path, std::ios::binary | std::ios::trunc);
  output << original;
  epoch_hook_mutated = static_cast<bool>(output);
}

void swap_epoch_handoff_operation_after_pin(const fs::path &path) {
  if (path != epoch_operation_hook_watch) return;
  epoch_operation_hook_called = true;
  std::error_code error;
  const fs::path moved = path.parent_path() / (path.filename().string() + ".hook-moved");
  fs::rename(path, moved, error);
  epoch_operation_hook_rename_succeeded = !error;
  if (error) return;
  fs::create_directory_symlink(epoch_operation_hook_outside, path, error);
  epoch_operation_hook_symlink_succeeded = !error;
}

bool equal_size_mutation_refused_or_denied(bool mutated, bool admitted) {
#ifdef _WIN32
  return !mutated || !admitted;
#else
  return mutated && !admitted;
#endif
}

std::string sha(const std::string &value) {
  return facman::base::sha256_hex_bytes(
      reinterpret_cast<const unsigned char *>(value.data()), value.size());
}

std::string json_string_field(const facman::core::json::Value &document,
                              const char *name) {
  const auto *field = document.find(name);
  if (field == nullptr || !field->is_string())
    throw std::runtime_error(std::string("missing JSON string field: ") + name);
  auto value = field->string_value();
  if (!value) throw std::runtime_error(value.error().message);
  return value.take_value();
}

std::string canonical_handoff_with_retained_package(
    const std::string &journal, const fs::path &retained_package) {
  auto parsed = facman::core::json::parse(journal);
  if (!parsed || !parsed.value().is_object())
    throw std::runtime_error("could not parse canonical handoff fixture");
  const char *const fields[] = {
      "schema", "product_id", "epoch_id", "epoch_manifest_sha256", "operation",
      "operation_id", "source_generation_id", "source_activation_name",
      "source_activation_sha256", "target_generation_id", "retained_package",
      "retained_package_sha256", "retained_helper", "retained_helper_sha256",
      "provider_plan_sha256", "nonce"};
  facman::core::json::ObjectBuilder rebuilt;
  for (const char *field : fields) {
    const std::string value = std::string(field) == "retained_package"
        ? facman::platform::path_to_utf8(retained_package)
        : json_string_field(parsed.value(), field);
    if (!rebuilt.add_string(field, value))
      throw std::runtime_error(std::string("could not rebuild handoff field: ") + field);
  }
  return rebuilt.serialize() + "\n";
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

std::string package_descriptor_bytes(const std::string &version) {
  return "{\"automatic_update\":false,\"entrypoints\":{"
      "\"cli_relative_path\":\"bin/facman.exe\","
      "\"gui_relative_path\":\"FacMan.exe\","
      "\"maintenance_relative_path\":\"maintenance/FacManSetup.exe\"},"
      "\"facman_source_revision\":\"" + std::string(40, 'd') +
      "\",\"generation_relative_path\":\"generations/" + version +
      "\",\"package_layout\":\"versioned_generation_with_maintenance_v1\","
      "\"product_id\":\"facman\",\"product_version\":\"" + version +
      "\",\"schema\":\"facman.self_maintenance_package.v1\","
      "\"setup_protocol\":\"facman.self_maintenance.v1\","
      "\"universal_setup_revision\":\"" + std::string(40, 'd') + "\"}";
}

std::string package_current_bytes(const std::string &version) {
  return "{\"automatic_update\":false,\"facman_source_revision\":\"" +
      std::string(40, 'd') + "\",\"generation\":\"generations/" + version +
      "\",\"portable_package\":\"facman.zip\",\"portable_sha256\":\"" +
      std::string(64, 'c') + "\",\"product_id\":\"facman\",\"schema\":"
      "\"facman.current_generation.v1\",\"universal_setup_revision\":\"" +
      std::string(40, 'd') + "\",\"version\":\"" + version +
      "\",\"workspace_preserved\":true}";
}

fs::path epoch_package(const fs::path &root, const std::string &version,
                       const std::string &helper) {
  const fs::path source = root / "epoch-package-source";
  fs::create_directories(source);
  std::ofstream(source / "descriptor.json", std::ios::binary | std::ios::trunc) <<
      package_descriptor_bytes(version);
  std::ofstream(source / "current.json", std::ios::binary | std::ios::trunc) <<
      package_current_bytes(version);
  std::ofstream(source / "binary", std::ios::binary | std::ios::trunc) << "binary";
  std::ofstream(source / "helper", std::ios::binary | std::ios::trunc) << helper;
  std::vector<facman::archive::WriteEntry> entries{
      {"facman/state/self-maintenance-package.v1.json", source / "descriptor.json", false},
      {"facman/state/current-generation.v1.json", source / "current.json", false},
      {"facman/generations/" + version + "/FacMan.exe", source / "binary", false},
      {"facman/generations/" + version + "/bin/facman.exe", source / "binary", false},
      {"facman/maintenance/FacManSetup.exe", source / "helper", false}};
  facman::archive::WriteOptions options;
  options.method = facman::archive::CompressionMethod::stored;
  options.limits = facman::archive::PackageArchivePolicy::limits();
  facman::archive::WriteResult result;
  const auto status = facman::archive::write_to_new_owned_staging(
      root / "epoch-package-staging", "candidate.zip", entries, options, result);
  return status.ok() ? result.archive_path : fs::path();
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

struct RetirementFakeEffects final : facman::self_maintenance::RetirementEffects {
  std::vector<std::string> inspected;
  std::vector<std::string> removed;
  bool reject_identity = false;
  bool interrupt_active = false;

  facman::core::Result<void> inspect_retirement_generation(
      const Generation &generation, bool) override {
    inspected.push_back(generation.install_id);
    if (reject_identity)
      return facman::core::Result<void>::failure(
          {"provider_identity_mismatch", "different install identity", {}});
    return facman::core::Result<void>::success();
  }

  facman::core::Result<void> uninstall_generation(
      const Generation &generation, bool active,
      const facman::self_maintenance::CoordinatorLockToken &) override {
    removed.push_back(generation.install_id);
    if (active && interrupt_active)
      return facman::core::Result<void>::failure(
          {"self_setup_interrupted", "active native boundary interrupted", {}});
    return facman::core::Result<void>::success();
  }
};

struct EpochPreparationFakeEffects final
    : facman::self_maintenance::EpochPreparationEffects {
  fs::path state_root;
  unsigned inspect_calls = 0;
  unsigned review_calls = 0;
  unsigned retain_calls = 0;
  bool retain_foreign_package = false;
  std::string helper_bytes;
  std::vector<fs::path> reviewed_packages;

  CandidateState inspect_candidate(const Plan &) override {
    ++inspect_calls;
    return CandidateState::absent;
  }
  EffectResult review_install_local(const Plan &plan) override {
    ++review_calls;
    reviewed_packages.push_back(plan.package);
    return {true, false, sha("epoch-provider-review\n" +
        facman::platform::path_to_utf8(plan.package.lexically_normal())), {}};
  }
  facman::core::Result<facman::self_maintenance::RetainedMaintenanceInputs>
  retain_handoff_inputs(const Plan &plan) override {
    ++retain_calls;
    const fs::path retained = state_root / "epoch-handoff" / plan.operation_id;
    fs::create_directories(retained);
    const fs::path package = retained / "package.zip";
    const fs::path helper = retained / "FacManSetup.exe";
    std::ofstream(package, std::ios::binary | std::ios::trunc) <<
        (retain_foreign_package ? "foreign-package" : bytes(plan.package));
    std::ofstream(helper, std::ios::binary | std::ios::trunc) << helper_bytes;
    return facman::core::Result<facman::self_maintenance::RetainedMaintenanceInputs>::success(
        {package, sha(bytes(package)), helper, sha(bytes(helper))});
  }
};

struct EpochContinuationFakeEffects final
    : facman::self_maintenance::EpochContinuationEffects {
  CandidateState candidate = CandidateState::absent;
  unsigned bind_calls = 0;
  unsigned apply_calls = 0;
  unsigned inspect_calls = 0;
  unsigned verify_calls = 0;
  bool lose_apply_receipt = false;
  bool wrong_binding = false;
  bool invalid_transaction = false;
  bool contradictory_inspect = false;
  bool contradictory_verify = false;
  std::function<void()> after_apply;

  CandidateState inspect_candidate(const Plan &) override { return candidate; }
  facman::core::Result<facman::self_maintenance::ProviderApplyBinding>
  bind_install_local(const Plan &, const std::string &expected) override {
    ++bind_calls;
    return facman::core::Result<facman::self_maintenance::ProviderApplyBinding>::success(
        {wrong_binding ? sha("wrong-plan") : expected,
         invalid_transaction ? std::string() : "epoch.provider.tx",
         sha("epoch.apply"), "epoch.apply", sha("epoch.semantic"), sha("epoch.bridge"),
         "epoch-plan", sha("epoch.plan"), "2026-01-01T00:00:00Z", "epoch-request"});
  }
  facman::core::Result<void> rehydrate_install_local(
      const Plan &, const facman::self_maintenance::ProviderApplyBinding &binding) override {
    return binding.apply_payload == "epoch.apply" && binding.apply_sha256 == sha("epoch.apply")
        ? facman::core::Result<void>::success()
        : facman::core::Result<void>::failure({"test", "binding changed", {}});
  }
  EffectResult apply_bound_install_local(
      const Plan &, const facman::self_maintenance::ProviderApplyBinding &) override {
    ++apply_calls;
    if (lose_apply_receipt) return {false, true, {}, "receipt lost"};
    candidate = CandidateState::exact;
    if (after_apply) after_apply();
    return {true, false, sha("epoch.apply.receipt"), {}};
  }
  EffectResult inspect_installed(const Plan &, const facman::self_maintenance::ProviderApplyBinding &) override {
    ++inspect_calls;
    if (contradictory_inspect) return {true, true, sha("epoch.inspect"), "contradictory"};
    return candidate == CandidateState::exact
        ? EffectResult{true, false, sha("epoch.inspect"), {}}
        : EffectResult{false, true, {}, "candidate not exact"};
  }
  EffectResult verify_installed(const Plan &) override {
    ++verify_calls;
    if (contradictory_verify) return {true, true, sha("epoch.verify"), "contradictory"};
    return candidate == CandidateState::exact
        ? EffectResult{true, false, sha("epoch.verify"), {}}
        : EffectResult{false, true, {}, "candidate not exact"};
  }
  EffectResult validate_terminal_verification(
      const Plan &, const facman::self_maintenance::ProviderApplyBinding &,
      const std::string &receipt) override {
    return receipt == sha("epoch.verify") && candidate == CandidateState::exact
        ? EffectResult{true, false, receipt, {}}
        : EffectResult{false, false, {}, "terminal verification differs"};
  }
};

struct EpochPreparationFixture {
  fs::path coordinator;
  facman::self_maintenance::LifecycleEpoch epoch;
  fs::path source_package;
  facman::self_maintenance::PackageInspection inspection;
  facman::self_maintenance::EpochTransitionRequest request;
  EpochPreparationFakeEffects effects;
  facman::self_maintenance::EpochTransitionPreparation handoff;
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

fs::path epoch_generation_root(const fs::path &logical_root,
                               const std::string &epoch_id,
                               const std::string &generation_id) {
  const std::string logical_identity = sha("facman.self.logical-root.v1\n" +
      facman::platform::path_to_utf8(logical_root.lexically_normal()) + "\n");
  return logical_root.parent_path() / facman::platform::path_from_utf8(
      "FacMan.generation." + sha("facman.self.physical-generation-root.v2\n" +
          logical_identity + "\n" + epoch_id + "\n" + generation_id + "\n"));
}

std::string epoch_generation_bytes(const facman::self_maintenance::LifecycleEpoch &epoch,
                                   const Generation &generation) {
  facman::core::json::ObjectBuilder object;
  object.add_string("schema", "facman.self_generation.v2");
  object.add_string("product_id", "facman");
  object.add_string("epoch_id", epoch.epoch_id);
  object.add_string("generation_id", generation.generation_id);
  object.add_string("product_version", generation.product_version);
  object.add_string("package_sha256", generation.package_sha256);
  object.add_string("facman_source_revision", generation.facman_source_revision);
  object.add_string("universal_setup_revision", generation.universal_setup_revision);
  object.add_string("install_id", generation.install_id);
  object.add_string("install_root", facman::platform::path_to_utf8(generation.install_root));
  object.add_string("logical_root", facman::platform::path_to_utf8(generation.logical_root));
  object.add_string("state_root", facman::platform::path_to_utf8(generation.state_root));
  object.add_string("acceptance_root", facman::platform::path_to_utf8(generation.acceptance_root));
  object.add_string("gui", facman::platform::path_to_utf8(generation.gui));
  object.add_string("maintenance_launcher", facman::platform::path_to_utf8(generation.maintenance_launcher));
  return object.serialize() + "\n";
}

std::string epoch_link_bytes(const facman::self_maintenance::LifecycleEpoch &epoch,
                             const std::string &operation,
                             const std::string &operation_id,
                             const std::string &source_id,
                             const std::string &target_id,
                             const std::string &target_sha,
                             const std::string &previous_name,
                             const std::string &previous_sha) {
  facman::core::json::ObjectBuilder previous;
  previous.add_string("name", previous_name);
  previous.add_string("sha256", previous_sha);
  facman::core::json::ObjectBuilder object;
  object.add_string("schema", "facman.self_activation.v2");
  object.add_string("product_id", "facman");
  object.add_string("epoch_id", epoch.epoch_id);
  object.add_string("operation", operation);
  object.add_string("operation_id", operation_id);
  object.add_string("source_generation_id", source_id);
  object.add_string("target_generation_id", target_id);
  object.add_string("generation_record_sha256", target_sha);
  object.add_object("previous", previous);
  return object.serialize() + "\n";
}

Generation make_epoch_update_generation(const facman::self_maintenance::LifecycleEpoch &epoch,
                                        const std::string &version, char fill) {
  const facman::self_maintenance::PackageDescriptor descriptor{
      "facman", version, "generations/" + version, std::string(40, fill),
      std::string(40, fill), "facman.self_maintenance.v1",
      "versioned_generation_with_maintenance_v1", "FacMan.exe", "bin/facman.exe",
      "maintenance/FacManSetup.exe", false};
  auto made = facman::self_maintenance::make_generation(
      descriptor, std::string(64, fill), "facman.self", epoch.logical_root,
      epoch.logical_root, epoch.state_root, epoch.acceptance_root);
  if (!made) throw std::runtime_error("could not make epoch generation");
  Generation result = made.take_value();
  result.install_id = "facman.self.epoch." + epoch.epoch_id + ".generation." +
      result.generation_id;
  result.install_root = epoch_generation_root(epoch.logical_root, epoch.epoch_id,
                                              result.generation_id);
  result.gui = result.install_root / "generations" / result.product_version / "FacMan.exe";
  result.maintenance_launcher = result.install_root / "maintenance" / "FacManSetup.exe";
  return result;
}

void write_new_record(const fs::path &path, const std::string &content) {
  std::string detail;
  if (!facman::base::write_text_new_atomic(path, content, detail))
    throw std::runtime_error(detail);
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
  auto legacy_epoch_active = facman::self_maintenance::discover_lifecycle_epoch_active(
      legacy_coordinator);
  ok &= require(legacy_adopted && legacy_repeated && legacy_discovered &&
                    legacy_epoch_active && legacy_epoch_active.value().epoch.compatibility_epoch &&
                    legacy_epoch_active.value().active.active.install_id == "facman.self" &&
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

  // Retiring A -> B -> A must retain the immutable activation history while
  // deduplicating effects to B, then the active A.  A durable completed
  // retained step is the only resume point; an entered active native step is
  // deliberately recovery-required instead of being replayed.
  auto retirement_chain = request(root / "retirement-chain", Operation::update);
  const Generation retired_b = generation(root / "retirement-chain" / "b",
                                          "0.1.0-alpha.4", 'b');
  std::string retirement_detail;
  if (!facman::base::write_text_new_atomic(
          retirement_chain.coordinator_root / "generations" /
              ("generation." + retired_b.generation_id + ".v1.json"),
          facman::self_maintenance::generation_record_bytes(retired_b),
          retirement_detail))
    throw std::runtime_error(retirement_detail);
  const fs::path first_activation = retirement_chain.coordinator_root /
      "activations" / "activation.update.one.v1.json";
  const std::string first_activation_bytes = activation_bytes(
      "update.one", retirement_chain.active.generation_id,
      retired_b.generation_id, retirement_chain.previous_activation_name,
      retirement_chain.previous_activation_sha256);
  if (!facman::base::write_text_new_atomic(first_activation,
                                            first_activation_bytes,
                                            retirement_detail))
    throw std::runtime_error(retirement_detail);
  const fs::path second_activation = retirement_chain.coordinator_root /
      "activations" / "activation.update.two.v1.json";
  const std::string second_activation_bytes = activation_bytes(
      "update.two", retired_b.generation_id,
      retirement_chain.active.generation_id,
      first_activation.filename().string(), sha(first_activation_bytes));
  if (!facman::base::write_text_new_atomic(second_activation,
                                            second_activation_bytes,
                                            retirement_detail))
    throw std::runtime_error(retirement_detail);
  auto full_chain = facman::self_maintenance::discover_activation_chain(
      retirement_chain.coordinator_root);
  ok &= require(full_chain && full_chain.value().has_value() &&
                    full_chain.value()->generations.size() == 3U &&
                    full_chain.value()->generations.front().generation_id ==
                        retirement_chain.active.generation_id &&
                    full_chain.value()->generations[1].generation_id ==
                        retired_b.generation_id &&
                    full_chain.value()->generations.back().generation_id ==
                        retirement_chain.active.generation_id,
                "full A-to-B-to-A activation chain was not exposed exactly");
  facman::self_maintenance::RetirementRequest retirement_request;
  retirement_request.coordinator_root = retirement_chain.coordinator_root;
  retirement_request.apply = false;
  RetirementFakeEffects retirement_preview_effects;
  auto retirement_preview = facman::self_maintenance::retire_active(
      retirement_request, retirement_preview_effects);
  ok &= require(retirement_preview && retirement_preview.value().phase == "planned" &&
                    retirement_preview.value().steps.size() == 2U &&
                    retirement_preview.value().steps[0].generation.install_id ==
                        retired_b.install_id &&
                    !retirement_preview.value().steps[0].active &&
                    retirement_preview.value().steps[1].generation.install_id ==
                        retirement_chain.active.install_id &&
                    retirement_preview.value().steps[1].active,
                "retirement order did not deduplicate retained B before active A");
  retirement_request.apply = true;
  RetirementFakeEffects retained_effects;
  auto retained_result = facman::self_maintenance::retire_active(
      retirement_request, retained_effects);
  ok &= require(retained_result && retained_result.value().phase == "step_completed" &&
                    retained_effects.removed.size() == 1U &&
                    retained_effects.removed[0] == retired_b.install_id,
                "retirement did not complete only the retained generation step");
  auto blocked_transition = facman::self_maintenance::discover_active(
      retirement_chain.coordinator_root);
  ok &= require(!blocked_transition &&
                    blocked_transition.error().code ==
                        "self_maintenance_retirement_recovery_required",
                "incomplete retirement remained eligible for another transition");
  RetirementFakeEffects interrupted_active;
  interrupted_active.interrupt_active = true;
  auto interrupted_result = facman::self_maintenance::retire_active(
      retirement_request, interrupted_active);
  ok &= require(!interrupted_result &&
                    interrupted_result.error().code ==
                        "self_maintenance_retirement_recovery_required" &&
                    interrupted_active.removed.size() == 1U &&
                    interrupted_active.removed[0] ==
                        retirement_chain.active.install_id,
                "active retirement interruption was not recovery-required");
  RetirementFakeEffects blocked_active_retry;
  auto blocked_active_retry_result = facman::self_maintenance::retire_active(
      retirement_request, blocked_active_retry);
  ok &= require(!blocked_active_retry_result &&
                    blocked_active_retry.removed.empty(),
                "entered active retirement step was retried blindly");

  auto identity_chain = request(root / "retirement-identity", Operation::update);
  RetirementFakeEffects identity_effects;
  identity_effects.reject_identity = true;
  facman::self_maintenance::RetirementRequest identity_request;
  identity_request.coordinator_root = identity_chain.coordinator_root;
  identity_request.apply = true;
  auto identity_result = facman::self_maintenance::retire_active(
      identity_request, identity_effects);
  ok &= require(!identity_result &&
                    identity_result.error().code ==
                        "self_maintenance_retirement_recovery_required" &&
                    identity_effects.removed.empty(),
                "retirement accepted a mismatched provider identity");

  auto foreign_chain = request(root / "retirement-foreign", Operation::update);
  fs::create_directories(foreign_chain.coordinator_root / "retirements" /
                         "retirement.foreign.v1");
  RetirementFakeEffects foreign_effects;
  facman::self_maintenance::RetirementRequest foreign_request;
  foreign_request.coordinator_root = foreign_chain.coordinator_root;
  foreign_request.apply = true;
  auto foreign_result = facman::self_maintenance::retire_active(
      foreign_request, foreign_effects);
  ok &= require(!foreign_result &&
                    foreign_result.error().code ==
                        "self_maintenance_retirement_recovery_required" &&
                    foreign_effects.removed.empty(),
                "stale or foreign retirement journal was accepted");

  auto completed_chain = request(root / "retirement-completed", Operation::update);
  RetirementFakeEffects completed_effects;
  facman::self_maintenance::RetirementRequest completed_request;
  completed_request.coordinator_root = completed_chain.coordinator_root;
  completed_request.apply = true;
  auto completed_result = facman::self_maintenance::retire_active(
      completed_request, completed_effects);
  auto no_active_after_retirement = facman::self_maintenance::discover_active(
      completed_chain.coordinator_root);
  auto retained_history = facman::self_maintenance::discover_activation_chain(
      completed_chain.coordinator_root);
  ok &= require(completed_result && completed_result.value().phase == "completed" &&
                    no_active_after_retirement &&
                    !no_active_after_retirement.value().has_value() &&
                    retained_history && retained_history.value().has_value() &&
                    retained_history.value()->generations.size() == 1U,
                "completed retirement did not hide active state while retaining history");

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

  // Epoch manifests are a separate immutable chain.  The initial publication
  // intentionally has no activation history; the next lifecycle operation
  // will own routing an activation into this epoch.
  const fs::path epoch_root = root / "epoch-manifest";
  facman::self_maintenance::LifecycleEpoch first_epoch;
  first_epoch.acceptance_root = epoch_root;
  first_epoch.genesis_generation_id = std::string(64, 'a');
  first_epoch.logical_root = epoch_root / "FacMan";
  first_epoch.state_root = epoch_root / "state";
  const fs::path epoch_coordinator = epoch_root / "coordinator";
  fs::create_directories(epoch_root);
  auto epoch_preview = facman::self_maintenance::publish_lifecycle_epoch(
      epoch_coordinator, first_epoch, false);
  const bool preview_left_coordinator_absent = !fs::exists(epoch_coordinator);
  auto epoch_published = facman::self_maintenance::publish_lifecycle_epoch(
      epoch_coordinator, first_epoch, true);
  auto epoch_chain = facman::self_maintenance::discover_lifecycle_epoch_chain(
      epoch_coordinator);
  auto epoch_retry = facman::self_maintenance::publish_lifecycle_epoch(
      epoch_coordinator, first_epoch, true);
  const auto json_path = [](std::string value) {
    std::string escaped;
    for (const char character : value) {
      if (character == '\\') escaped += "\\\\";
      else if (character == '/') escaped += "\\/";
      else escaped += character;
    }
    return escaped;
  };
  const std::string expected_epoch_identity =
      "{\"acceptance_root\":\"" +
      json_path(facman::platform::path_to_utf8(epoch_root.lexically_normal())) +
      "\",\"genesis_generation_id\":\"" + std::string(64, 'a') +
      "\",\"logical_root\":\"" +
      json_path(facman::platform::path_to_utf8((epoch_root / "FacMan").lexically_normal())) +
      "\",\"predecessor_epoch_id\":\"\",\"predecessor_manifest_sha256\":\"\","
      "\"predecessor_retirement_sha256\":\"\",\"product_id\":\"facman\","
      "\"schema\":\"facman.self_lifecycle_epoch_identity.v1\",\"state_root\":\"" +
      json_path(facman::platform::path_to_utf8((epoch_root / "state").lexically_normal())) +
      "\"}\n";
  if (!epoch_preview)
    std::cerr << "epoch preview error: " << epoch_preview.error().code << ": "
              << epoch_preview.error().message << '\n';
  if (!epoch_published)
    std::cerr << "epoch publish error: " << epoch_published.error().code << ": "
              << epoch_published.error().message << " ("
              << epoch_published.error().detail << ")\n";
  if (!epoch_chain)
    std::cerr << "epoch discovery error: " << epoch_chain.error().code << ": "
              << epoch_chain.error().message << '\n';
  if (!epoch_retry)
    std::cerr << "epoch retry error: " << epoch_retry.error().code << ": "
              << epoch_retry.error().message << '\n';
  if (epoch_chain && (!preview_left_coordinator_absent ||
                      epoch_chain.value().epochs.size() != 1U ||
                      epoch_chain.value().epochs.front().epoch_id !=
                          sha(expected_epoch_identity))) {
    std::cerr << "epoch canonical mismatch: preview_absent="
              << preview_left_coordinator_absent << " count="
              << epoch_chain.value().epochs.size();
    if (!epoch_chain.value().epochs.empty())
      std::cerr << " actual_id=" << epoch_chain.value().epochs.front().epoch_id
                << " expected_id=" << sha(expected_epoch_identity);
    std::cerr << '\n';
  }
  if (epoch_retry && epoch_retry.value().epochs.size() != 1U)
    std::cerr << "epoch retry count=" << epoch_retry.value().epochs.size() << '\n';
  ok &= require(epoch_preview && preview_left_coordinator_absent &&
                    epoch_published && epoch_chain && epoch_retry &&
                    epoch_chain.value().epochs.size() == 1U &&
                    epoch_chain.value().epochs.front().epoch_id ==
                        sha(expected_epoch_identity) &&
                    epoch_retry.value().epochs.size() == 1U,
                "epoch manifest publication was not canonical, durable, or idempotent");

  // A real epoch has one v2 genesis activation.  Its content id deliberately
  // remains the v1 package identity while its install root includes the epoch.
  const fs::path genesis_root = root / "epoch-genesis";
  facman::self_maintenance::PackageDescriptor genesis_descriptor{
      "facman", "9.8.7", "generations/9.8.7", std::string(40, 'c'),
      std::string(40, 'c'), "facman.self_maintenance.v1",
      "versioned_generation_with_maintenance_v1", "FacMan.exe", "bin/facman.exe",
      "maintenance/FacManSetup.exe", false};
  const std::string genesis_package(64, 'd');
  facman::self_maintenance::LifecycleEpoch genesis_epoch;
  genesis_epoch.acceptance_root = genesis_root;
  genesis_epoch.logical_root = genesis_root / "FacMan";
  genesis_epoch.state_root = genesis_root / "state";
  genesis_epoch.genesis_generation_id = generation_identity("9.8.7", genesis_package, 'c');
  fs::create_directories(genesis_root);
  const fs::path genesis_coordinator = genesis_root / "coordinator";
  auto genesis_manifest = facman::self_maintenance::publish_lifecycle_epoch(
      genesis_coordinator, genesis_epoch, true);
  Generation epoch_generation;
  if (genesis_manifest && genesis_manifest.value().epochs.size() == 1U) {
    auto made = facman::self_maintenance::make_epoch_genesis_generation(
        genesis_manifest.value().epochs.front(), genesis_descriptor, genesis_package);
    if (made) epoch_generation = made.take_value();
  }
  facman::self_maintenance::EpochGenesisRequest genesis_request{
      genesis_coordinator,
      genesis_manifest && !genesis_manifest.value().epochs.empty()
          ? genesis_manifest.value().epochs.front().epoch_id : std::string(),
      epoch_generation, false};
  auto genesis_preview = facman::self_maintenance::activate_lifecycle_epoch_genesis(genesis_request);
  auto mismatched_generation = epoch_generation;
  mismatched_generation.install_id = "facman.self.epoch.mismatch";
  auto mismatch_request = genesis_request;
  mismatch_request.generation = mismatched_generation;
  auto genesis_mismatch = facman::self_maintenance::activate_lifecycle_epoch_genesis(mismatch_request);
  auto peer_epoch = genesis_epoch;
  peer_epoch.logical_root = genesis_root / "PeerFacMan";
  auto peer_preview = facman::self_maintenance::publish_lifecycle_epoch(
      genesis_root / "peer-coordinator", peer_epoch, false);
  auto peer_generation = peer_preview && !peer_preview.value().epochs.empty()
      ? facman::self_maintenance::make_epoch_genesis_generation(
            peer_preview.value().epochs.front(), genesis_descriptor, genesis_package)
      : facman::core::Result<Generation>::failure({"test", "peer epoch was not canonical", ""});
  fs::create_directories(genesis_coordinator / "epochs" / genesis_request.epoch_id / "generations");
  genesis_request.apply = true;
  facman::platform::testing::set_relative_publish_pre_rename_fault_countdown(1U);
  auto genesis_staging = facman::self_maintenance::activate_lifecycle_epoch_genesis(genesis_request);
  facman::platform::testing::set_relative_publish_pre_rename_fault_countdown(0U);
  const bool generation_staging_present = fs::exists(genesis_coordinator / "epochs" /
      genesis_request.epoch_id / "generations" /
      ("generation.staging." + epoch_generation.generation_id + ".v2.json"));
  auto genesis_apply = facman::self_maintenance::activate_lifecycle_epoch_genesis(genesis_request);
  auto genesis_retry = facman::self_maintenance::activate_lifecycle_epoch_genesis(genesis_request);
  auto genesis_discovery = facman::self_maintenance::discover_lifecycle_epoch_chain(genesis_coordinator);
  const std::string genesis_epoch_id = genesis_request.epoch_id;
  const std::string logical_identity = sha("facman.self.logical-root.v1\n" +
      facman::platform::path_to_utf8((genesis_root / "FacMan").lexically_normal()) + "\n");
  const fs::path expected_epoch_root = genesis_root /
      facman::platform::path_from_utf8("FacMan.generation." + sha(
          "facman.self.physical-generation-root.v2\n" + logical_identity + "\n" +
          genesis_epoch_id + "\n" + epoch_generation.generation_id + "\n"));
  ok &= require(genesis_manifest && !epoch_generation.generation_id.empty() &&
                    genesis_preview && !genesis_mismatch && peer_generation && !genesis_staging && generation_staging_present && genesis_apply && genesis_retry && genesis_discovery &&
                    genesis_apply.value().active.install_id == "facman.self.epoch." +
                        genesis_epoch_id + ".generation." + epoch_generation.generation_id &&
                    genesis_apply.value().active.install_root == expected_epoch_root &&
                    peer_generation.value().generation_id == epoch_generation.generation_id &&
                    peer_generation.value().install_root != epoch_generation.install_root &&
                    fs::exists(genesis_coordinator / "epochs" / genesis_epoch_id /
                        "generations" / ("generation." + epoch_generation.generation_id + ".v2.json")) &&
                    fs::exists(genesis_coordinator / "epochs" / genesis_epoch_id /
                        "activations" / ("activation.epoch.genesis." + epoch_generation.generation_id + ".v2.json")),
                "epoch genesis preview, activation, retry, or v2 identity was not exact");

  // Epoch records use the same immutable publish helper as genesis.  These
  // focused fixtures exercise discovery only; routing a real transition is a
  // later slice.
  const auto epoch_fixture = [&](const std::string &name) {
    const fs::path fixture_root = root / name;
    const fs::path coordinator = fixture_root / "coordinator";
    fs::create_directories(fixture_root);
    facman::self_maintenance::LifecycleEpoch proposed;
    proposed.acceptance_root = fixture_root;
    proposed.logical_root = fixture_root / "FacMan";
    proposed.state_root = fixture_root / "state";
    proposed.genesis_generation_id = generation_identity("9.8.7", genesis_package, 'c');
    auto published = facman::self_maintenance::publish_lifecycle_epoch(
        coordinator, proposed, true);
    if (!published || published.value().epochs.empty())
      throw std::runtime_error("could not publish epoch fixture");
    const auto &epoch = published.value().epochs.back();
    auto generation = facman::self_maintenance::make_epoch_genesis_generation(
        epoch, genesis_descriptor, genesis_package);
    if (!generation) throw std::runtime_error("could not make epoch fixture genesis");
    auto activated = facman::self_maintenance::activate_lifecycle_epoch_genesis(
        {coordinator, epoch.epoch_id, generation.take_value(), true});
    if (!activated) throw std::runtime_error("could not activate epoch fixture genesis");
    return coordinator;
  };
  const auto write_epoch_generation = [&](const fs::path &coordinator,
                                          const facman::self_maintenance::LifecycleEpoch &epoch,
                                          const Generation &value) {
    write_new_record(coordinator / "epochs" / epoch.epoch_id / "generations" /
        ("generation." + value.generation_id + ".v2.json"),
        epoch_generation_bytes(epoch, value));
  };
  const auto write_epoch_link = [&](const fs::path &coordinator,
                                    const facman::self_maintenance::LifecycleEpoch &epoch,
                                    const std::string &operation,
                                    const std::string &operation_id,
                                    const Generation &source,
                                    const Generation &target,
                                    const std::string &previous_name,
                                    const std::string &previous_sha) {
    const std::string record = epoch_generation_bytes(epoch, target);
    write_epoch_generation(coordinator, epoch, target);
    write_new_record(coordinator / "epochs" / epoch.epoch_id / "activations" /
        ("activation." + operation_id + ".v2.json"),
        epoch_link_bytes(epoch, operation, operation_id, source.generation_id,
            target.generation_id, sha(record), previous_name, previous_sha));
  };
  const auto epoch_from = [&](const fs::path &coordinator) {
    auto chain = facman::self_maintenance::discover_lifecycle_epoch_chain(coordinator);
    return chain.value().epochs.back();
  };
  const std::string genesis_activation_name =
      "activation.epoch.genesis." + epoch_generation.generation_id + ".v2.json";
  const std::string genesis_activation_sha = sha(bytes(genesis_coordinator / "epochs" /
      genesis_epoch_id / "activations" / genesis_activation_name));
  const auto genesis_sha_for = [&](const fs::path &coordinator,
                                   const facman::self_maintenance::LifecycleEpoch &epoch) {
    return sha(bytes(coordinator / "epochs" / epoch.epoch_id / "activations" /
        genesis_activation_name));
  };

  const fs::path update_coordinator = epoch_fixture("epoch-linked-update");
  const auto update_epoch = epoch_from(update_coordinator);
  const Generation update_generation = make_epoch_update_generation(update_epoch, "9.8.8", 'd');
  write_epoch_link(update_coordinator, update_epoch, "update", "epoch.update.one",
      epoch_generation, update_generation, genesis_activation_name,
      genesis_sha_for(update_coordinator, update_epoch));
  auto linked_update = facman::self_maintenance::discover_lifecycle_epoch_active(update_coordinator);

  const fs::path downgrade_coordinator = epoch_fixture("epoch-linked-downgrade");
  const auto downgrade_epoch = epoch_from(downgrade_coordinator);
  const Generation upgrade_generation = make_epoch_update_generation(downgrade_epoch, "9.8.8", 'd');
  write_epoch_link(downgrade_coordinator, downgrade_epoch, "update", "epoch.update.one",
      epoch_generation, upgrade_generation, genesis_activation_name,
      genesis_sha_for(downgrade_coordinator, downgrade_epoch));
  const std::string update_name = "activation.epoch.update.one.v2.json";
  const std::string update_sha = sha(bytes(downgrade_coordinator / "epochs" /
      downgrade_epoch.epoch_id / "activations" / update_name));
  const Generation downgrade_generation = make_epoch_update_generation(downgrade_epoch, "9.8.6", 'e');
  write_epoch_link(downgrade_coordinator, downgrade_epoch, "downgrade", "epoch.downgrade.one",
      upgrade_generation, downgrade_generation, update_name, update_sha);
  auto linked_downgrade = facman::self_maintenance::discover_lifecycle_epoch_active(
      downgrade_coordinator);
  ok &= require(linked_update && linked_update.value().active.active.generation_id ==
                    update_generation.generation_id && linked_update.value().active.previous &&
                    linked_update.value().active.previous->generation_id == epoch_generation.generation_id &&
                    linked_update.value().active.activation_name == "activation.epoch.update.one.v2.json" &&
                    linked_downgrade && linked_downgrade.value().active.active.generation_id ==
                    downgrade_generation.generation_id && linked_downgrade.value().active.previous &&
                    linked_downgrade.value().active.previous->generation_id == upgrade_generation.generation_id,
                "linked epoch update or downgrade head discovery was not exact");

  const fs::path activation_substitution_coordinator = epoch_fixture("epoch-pinned-activation");
  const auto activation_substitution_epoch = epoch_from(activation_substitution_coordinator);
  const Generation activation_substitution_target = make_epoch_update_generation(
      activation_substitution_epoch, "9.8.8", 'd');
  write_epoch_link(activation_substitution_coordinator, activation_substitution_epoch, "update",
      "epoch.update.one", epoch_generation, activation_substitution_target,
      genesis_activation_name, genesis_sha_for(activation_substitution_coordinator,
                                                activation_substitution_epoch));
  epoch_hook_watch = activation_substitution_coordinator / "epochs" /
      activation_substitution_epoch.epoch_id / "activations" / genesis_activation_name;
  epoch_hook_mutation = activation_substitution_coordinator / "epochs" /
      activation_substitution_epoch.epoch_id / "activations" /
      "activation.epoch.update.one.v2.json";
  epoch_hook_bytes = "{}\n";
  epoch_hook_called = false;
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(
      mutate_epoch_record_after_pin);
  auto activation_substitution = facman::self_maintenance::discover_lifecycle_epoch_active(
      activation_substitution_coordinator);
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(nullptr);
  const bool activation_substitution_hook_called = epoch_hook_called;
  const fs::path generation_substitution_coordinator = epoch_fixture("epoch-pinned-generation");
  const auto generation_substitution_epoch = epoch_from(generation_substitution_coordinator);
  const Generation generation_substitution_target = make_epoch_update_generation(
      generation_substitution_epoch, "9.8.8", 'd');
  write_epoch_link(generation_substitution_coordinator, generation_substitution_epoch, "update",
      "epoch.update.one", epoch_generation, generation_substitution_target,
      genesis_activation_name, genesis_sha_for(generation_substitution_coordinator,
                                                generation_substitution_epoch));
  epoch_hook_watch = generation_substitution_coordinator / "epochs" /
      generation_substitution_epoch.epoch_id / "activations" / genesis_activation_name;
  epoch_hook_mutation = generation_substitution_coordinator / "epochs" /
      generation_substitution_epoch.epoch_id / "generations" /
      ("generation." + generation_substitution_target.generation_id + ".v2.json");
  epoch_hook_called = false;
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(
      mutate_epoch_record_after_pin);
  auto generation_substitution = facman::self_maintenance::discover_lifecycle_epoch_active(
      generation_substitution_coordinator);
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(nullptr);
  const bool generation_substitution_hook_called = epoch_hook_called;
  ok &= require(activation_substitution_hook_called && generation_substitution_hook_called &&
                    !activation_substitution && !generation_substitution,
                "same-name epoch record substitution during a multi-record scan was accepted");

  const fs::path equal_size_scanner_coordinator = epoch_fixture("epoch-equal-size-scanner");
  const auto equal_size_scanner_epoch = epoch_from(equal_size_scanner_coordinator);
  epoch_hook_watch = equal_size_scanner_coordinator / "epochs" /
      equal_size_scanner_epoch.epoch_id / "activations" / genesis_activation_name;
  epoch_hook_called = false;
  epoch_hook_mutated = false;
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(
      overwrite_epoch_record_in_place_after_pin);
  auto equal_size_scanner = facman::self_maintenance::discover_lifecycle_epoch_active(
      equal_size_scanner_coordinator);
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(nullptr);
  ok &= require(epoch_hook_called && equal_size_mutation_refused_or_denied(
                    epoch_hook_mutated, static_cast<bool>(equal_size_scanner)),
                "equal-size in-place activation record mutation after pin was accepted");

  const fs::path equal_size_generation_coordinator = epoch_fixture("epoch-equal-size-generation");
  const auto equal_size_generation_epoch = epoch_from(equal_size_generation_coordinator);
  const Generation equal_size_generation_target = make_epoch_update_generation(
      equal_size_generation_epoch, "9.8.8", 'd');
  write_epoch_link(equal_size_generation_coordinator, equal_size_generation_epoch, "update",
      "epoch.update.one", epoch_generation, equal_size_generation_target,
      genesis_activation_name,
      genesis_sha_for(equal_size_generation_coordinator, equal_size_generation_epoch));
  epoch_hook_watch = equal_size_generation_coordinator / "epochs" /
      equal_size_generation_epoch.epoch_id / "generations" /
      ("generation." + equal_size_generation_target.generation_id + ".v2.json");
  epoch_hook_called = false;
  epoch_hook_mutated = false;
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(
      overwrite_epoch_record_in_place_after_pin);
  auto equal_size_generation = facman::self_maintenance::discover_lifecycle_epoch_active(
      equal_size_generation_coordinator);
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(nullptr);
  ok &= require(epoch_hook_called && equal_size_mutation_refused_or_denied(
                    epoch_hook_mutated, static_cast<bool>(equal_size_generation)),
                "equal-size in-place generation record mutation after pin was accepted");

  const std::string preparation_helper = "epoch-maintenance-helper";
  const auto make_preparation_fixture = [&](const std::string &name) {
    EpochPreparationFixture fixture;
    fixture.coordinator = epoch_fixture(name);
    fixture.epoch = epoch_from(fixture.coordinator);
    fixture.source_package = epoch_package(root / name, "9.8.8", preparation_helper);
    auto inspected = facman::self_maintenance::inspect_package(fixture.source_package);
    if (!inspected) throw std::runtime_error("could not construct valid epoch transition package");
    fixture.inspection = inspected.take_value();
    fixture.request = {fixture.coordinator, fixture.epoch.epoch_id, Operation::update,
                       "epoch.prepare.one", fixture.inspection, false};
    fixture.effects.state_root = fixture.epoch.state_root;
    fixture.effects.helper_bytes = preparation_helper;
    return fixture;
  };
  const auto prepare_fresh_epoch_fixture = [&](const std::string &name) {
    auto fixture = make_preparation_fixture(name);
    fixture.request.apply = true;
    auto prepared = facman::self_maintenance::prepare_lifecycle_epoch_transition(
        fixture.request, fixture.effects);
    if (!prepared) throw std::runtime_error("could not publish prepared epoch handoff");
    fixture.handoff = prepared.take_value();
    return fixture;
  };

  auto preparation = make_preparation_fixture("epoch-transition-preparation");
  auto preparation_preview = facman::self_maintenance::prepare_lifecycle_epoch_transition(
      preparation.request, preparation.effects);
  const fs::path fabricated_package = root / "epoch-transition-preparation" / "fabricated.zip";
  std::ofstream(fabricated_package, std::ios::binary | std::ios::trunc) << "not-an-archive";
  auto fabricated_request = preparation.request;
  fabricated_request.package.package = fabricated_package;
  fabricated_request.package.package_sha256 = sha("not-an-archive");
  auto fabricated_package_refusal = facman::self_maintenance::prepare_lifecycle_epoch_transition(
      fabricated_request, preparation.effects);
  const bool preview_wrote = fs::exists(preparation.coordinator / "epochs" /
      preparation.epoch.epoch_id / "maintenance") || preparation.effects.retain_calls != 0U;
  preparation.request.apply = true;
  auto preparation_apply = facman::self_maintenance::prepare_lifecycle_epoch_transition(
      preparation.request, preparation.effects);
  auto preparation_retry = facman::self_maintenance::prepare_lifecycle_epoch_transition(
      preparation.request, preparation.effects);
  auto ordinary_during_handoff = facman::self_maintenance::discover_lifecycle_epoch_active(
      preparation.coordinator);
  auto wrong_handoff_nonce = facman::self_maintenance::admit_lifecycle_epoch_continuation(
      preparation.coordinator, "epoch.prepare.one", "wrong-nonce",
      preparation_apply ? preparation_apply.value().journal_sha256 : std::string(64, 'a'));
  auto wrong_handoff_digest = facman::self_maintenance::admit_lifecycle_epoch_continuation(
      preparation.coordinator, "epoch.prepare.one",
      preparation_apply ? preparation_apply.value().nonce : "epoch-nonce", std::string(64, 'a'));
  auto exact_handoff = facman::self_maintenance::admit_lifecycle_epoch_continuation(
      preparation.coordinator, "epoch.prepare.one",
      preparation_apply ? preparation_apply.value().nonce : "epoch-nonce",
      preparation_apply ? preparation_apply.value().journal_sha256 : std::string(64, 'a'));
  ok &= require(preparation_preview && preparation_preview.value().phase == "plan" && !preview_wrote &&
                    !fabricated_package_refusal && preparation.effects.retain_calls == 1U &&
                    preparation_apply && preparation_retry &&
                    preparation_apply.value().journal_sha256 == preparation_retry.value().journal_sha256 &&
                    preparation_apply.value().nonce == preparation_retry.value().nonce &&
                    !ordinary_during_handoff && exact_handoff &&
                    exact_handoff.value().package == preparation_apply.value().inputs.package &&
                    !wrong_handoff_nonce && !wrong_handoff_digest &&
                    ordinary_during_handoff.error().code ==
                        "self_maintenance_epoch_recovery_required",
                "epoch preparation preview, exact handoff, and recovery boundary were not exact");

  // Provider continuation is intentionally a library-only boundary: it may
  // install and verify the candidate, but it must not publish a generation or
  // move the epoch activation head.
  auto provider_continuation = prepare_fresh_epoch_fixture("epoch-provider-continuation");
  EpochContinuationFakeEffects provider_continuation_effects;
  facman::self_maintenance::EpochContinuationRequest continuation_request{
      provider_continuation.coordinator, "epoch.prepare.one",
      provider_continuation.handoff.nonce, provider_continuation.handoff.journal_sha256, true};
  auto provider_completed = facman::self_maintenance::execute_lifecycle_epoch_continuation(
      continuation_request, provider_continuation_effects);
  // A process-equivalent restart has only durable provider state: it must
  // rehydrate the immutable request and never replay the entered apply.
  EpochContinuationFakeEffects provider_restarted_effects;
  provider_restarted_effects.candidate = CandidateState::exact;
  auto provider_restarted = facman::self_maintenance::execute_lifecycle_epoch_continuation(
      continuation_request, provider_restarted_effects);
  const fs::path provider_operation = provider_continuation.coordinator / "epochs" /
      provider_continuation.epoch.epoch_id / "maintenance" / "epoch.prepare.one";
  const bool provider_only = !fs::exists(provider_continuation.coordinator / "generations") &&
      fs::exists(provider_operation / "10-provider-apply-bound.v2.json") &&
      fs::exists(provider_operation / "20-provider-apply-entered.v2.json") &&
      fs::exists(provider_operation / "30-provider-outcome.v2.json") &&
      fs::exists(provider_operation / "40-provider-verified.v2.json") &&
      !fs::exists(provider_continuation.coordinator / "epochs" /
          provider_continuation.epoch.epoch_id / "generations" /
          ("generation." + provider_continuation.handoff.transition.target.generation_id + ".v2.json"));
  ok &= require(provider_completed && provider_restarted &&
                    provider_completed.value().phase == "provider_verified" &&
                    provider_restarted.value().phase == "provider_verified" &&
                    provider_continuation_effects.apply_calls == 1U &&
                    provider_restarted_effects.apply_calls == 0U && provider_only,
                "epoch provider continuation was not durable, idempotent, or publication-free");

  bool continuation_staging_recovered = true;
  for (unsigned phase = 1U; phase <= 4U; ++phase) {
    auto staged = prepare_fresh_epoch_fixture("epoch-provider-staging-" + std::to_string(phase));
    EpochContinuationFakeEffects staged_effects;
    facman::self_maintenance::EpochContinuationRequest staged_request{
        staged.coordinator, "epoch.prepare.one", staged.handoff.nonce,
        staged.handoff.journal_sha256, true};
    facman::platform::testing::set_relative_publish_pre_rename_fault_countdown(phase);
    auto staging_interrupted = facman::self_maintenance::execute_lifecycle_epoch_continuation(
        staged_request, staged_effects);
    facman::platform::testing::set_relative_publish_pre_rename_fault_countdown(0U);
    auto staging_recovered = facman::self_maintenance::execute_lifecycle_epoch_continuation(
        staged_request, staged_effects);
    continuation_staging_recovered = continuation_staging_recovered && !staging_interrupted && staging_recovered &&
        staged_effects.apply_calls == 1U &&
        fs::exists(staged.coordinator / "epochs" / staged.epoch.epoch_id / "maintenance" /
                   "epoch.prepare.one" / "40-provider-verified.v2.json");
  }
  ok &= require(continuation_staging_recovered,
                "each canonical epoch provider staging tail was not recovered exactly");

  auto uncertain_continuation = prepare_fresh_epoch_fixture("epoch-provider-uncertain");
  EpochContinuationFakeEffects uncertain_effects;
  uncertain_effects.lose_apply_receipt = true;
  facman::self_maintenance::EpochContinuationRequest uncertain_request{
      uncertain_continuation.coordinator, "epoch.prepare.one",
      uncertain_continuation.handoff.nonce, uncertain_continuation.handoff.journal_sha256, true};
  auto uncertain_first = facman::self_maintenance::execute_lifecycle_epoch_continuation(
      uncertain_request, uncertain_effects);
  auto uncertain_restart = facman::self_maintenance::execute_lifecycle_epoch_continuation(
      uncertain_request, uncertain_effects);
  ok &= require(!uncertain_first && !uncertain_restart && uncertain_effects.apply_calls == 1U &&
                    fs::exists(uncertain_continuation.coordinator / "epochs" /
                        uncertain_continuation.epoch.epoch_id / "maintenance" /
                        "epoch.prepare.one" / "20-provider-apply-entered.v2.json"),
                "entered epoch provider apply was repeated after an uncertain outcome");

  auto wrong_binding_continuation = prepare_fresh_epoch_fixture("epoch-provider-wrong-binding");
  EpochContinuationFakeEffects wrong_binding_effects;
  wrong_binding_effects.wrong_binding = true;
  facman::self_maintenance::EpochContinuationRequest wrong_binding_request{
      wrong_binding_continuation.coordinator, "epoch.prepare.one",
      wrong_binding_continuation.handoff.nonce,
      wrong_binding_continuation.handoff.journal_sha256, true};
  auto wrong_binding = facman::self_maintenance::execute_lifecycle_epoch_continuation(
      wrong_binding_request, wrong_binding_effects);
  ok &= require(!wrong_binding && wrong_binding_effects.apply_calls == 0U,
                "mismatched epoch provider binding entered apply");

  auto invalid_transaction_continuation = prepare_fresh_epoch_fixture(
      "epoch-provider-invalid-transaction");
  EpochContinuationFakeEffects invalid_transaction_effects;
  invalid_transaction_effects.invalid_transaction = true;
  facman::self_maintenance::EpochContinuationRequest invalid_transaction_request{
      invalid_transaction_continuation.coordinator, "epoch.prepare.one",
      invalid_transaction_continuation.handoff.nonce,
      invalid_transaction_continuation.handoff.journal_sha256, true};
  auto invalid_transaction = facman::self_maintenance::execute_lifecycle_epoch_continuation(
      invalid_transaction_request, invalid_transaction_effects);
  ok &= require(!invalid_transaction && invalid_transaction_effects.apply_calls == 0U,
                "empty epoch provider transaction entered apply");

  auto contradictory_continuation = prepare_fresh_epoch_fixture(
      "epoch-provider-contradictory-outcome");
  EpochContinuationFakeEffects contradictory_effects;
  contradictory_effects.contradictory_inspect = true;
  facman::self_maintenance::EpochContinuationRequest contradictory_request{
      contradictory_continuation.coordinator, "epoch.prepare.one",
      contradictory_continuation.handoff.nonce,
      contradictory_continuation.handoff.journal_sha256, true};
  auto contradictory_result = facman::self_maintenance::execute_lifecycle_epoch_continuation(
      contradictory_request, contradictory_effects);
  ok &= require(!contradictory_result && contradictory_effects.apply_calls == 1U &&
                    !fs::exists(contradictory_continuation.coordinator / "generations") &&
                    !fs::exists(contradictory_continuation.coordinator / "activations"),
                "contradictory provider outcome crossed the epoch publication boundary");

  auto callback_mutation_continuation = prepare_fresh_epoch_fixture(
      "epoch-provider-callback-record-mutation");
  EpochContinuationFakeEffects callback_mutation_effects;
  const fs::path callback_operation = callback_mutation_continuation.coordinator / "epochs" /
      callback_mutation_continuation.epoch.epoch_id / "maintenance" / "epoch.prepare.one";
  bool callback_mutation_opened = false;
  callback_mutation_effects.after_apply = [callback_operation, &callback_mutation_opened] {
    std::ofstream output(callback_operation / "10-provider-apply-bound.v2.json",
                         std::ios::binary | std::ios::trunc);
    callback_mutation_opened = output.good();
    output << "foreign-binding\n";
  };
  facman::self_maintenance::EpochContinuationRequest callback_mutation_request{
      callback_mutation_continuation.coordinator, "epoch.prepare.one",
      callback_mutation_continuation.handoff.nonce,
      callback_mutation_continuation.handoff.journal_sha256, true};
  auto callback_mutation_result = facman::self_maintenance::execute_lifecycle_epoch_continuation(
      callback_mutation_request, callback_mutation_effects);
  ok &= require((!callback_mutation_opened || !callback_mutation_result) &&
                    callback_mutation_effects.apply_calls == 1U &&
                    (!callback_mutation_opened ||
                     !fs::exists(callback_operation / "30-provider-outcome.v2.json")),
                "provider callback mutation of a held binding reached a later durable phase");

  auto foreign_record_continuation = prepare_fresh_epoch_fixture("epoch-provider-foreign-record");
  const fs::path foreign_continuation_record = foreign_record_continuation.coordinator / "epochs" /
      foreign_record_continuation.epoch.epoch_id / "maintenance" / "epoch.prepare.one" /
      "01-foreign.v2.json";
  std::ofstream(foreign_continuation_record, std::ios::binary | std::ios::trunc) << "foreign\n";
  EpochContinuationFakeEffects foreign_record_effects;
  facman::self_maintenance::EpochContinuationRequest foreign_record_request{
      foreign_record_continuation.coordinator, "epoch.prepare.one",
      foreign_record_continuation.handoff.nonce,
      foreign_record_continuation.handoff.journal_sha256, true};
  auto foreign_record_result = facman::self_maintenance::execute_lifecycle_epoch_continuation(
      foreign_record_request, foreign_record_effects);
  ok &= require(!foreign_record_result && foreign_record_effects.apply_calls == 0U,
                "foreign epoch continuation record entered provider apply");

  auto continuation_replacement = prepare_fresh_epoch_fixture(
      "epoch-transition-pinned-continuation");
  epoch_hook_watch = continuation_replacement.handoff.journal;
  epoch_hook_mutation = continuation_replacement.handoff.journal;
  epoch_hook_bytes = "foreign-journal-bytes\n";
  epoch_hook_called = false;
  epoch_hook_mutated = false;
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(
      replace_epoch_record_after_pin);
  auto mutated_journal_continuation = facman::self_maintenance::admit_lifecycle_epoch_continuation(
      continuation_replacement.coordinator, "epoch.prepare.one",
      continuation_replacement.handoff.nonce, continuation_replacement.handoff.journal_sha256);
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(nullptr);
  ok &= require(epoch_hook_called &&
                    (!epoch_hook_mutated || !mutated_journal_continuation),
                "same-name journal replacement after pin during continuation was accepted");

  auto equal_size_journal = prepare_fresh_epoch_fixture(
      "epoch-transition-equal-size-journal");
  epoch_hook_watch = equal_size_journal.handoff.journal;
  epoch_hook_called = false;
  epoch_hook_mutated = false;
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(
      overwrite_epoch_record_in_place_after_pin);
  auto equal_size_journal_continuation = facman::self_maintenance::admit_lifecycle_epoch_continuation(
      equal_size_journal.coordinator, "epoch.prepare.one", equal_size_journal.handoff.nonce,
      equal_size_journal.handoff.journal_sha256);
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(nullptr);
  ok &= require(epoch_hook_called && equal_size_mutation_refused_or_denied(
                    epoch_hook_mutated, static_cast<bool>(equal_size_journal_continuation)),
                "equal-size in-place continuation journal mutation after pin was accepted");

  auto equal_size_package = prepare_fresh_epoch_fixture(
      "epoch-transition-equal-size-package");
  epoch_hook_watch = equal_size_package.handoff.inputs.package;
  epoch_hook_called = false;
  epoch_hook_mutated = false;
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(
      overwrite_epoch_record_in_place_after_pin);
  auto equal_size_package_continuation = facman::self_maintenance::admit_lifecycle_epoch_continuation(
      equal_size_package.coordinator, "epoch.prepare.one", equal_size_package.handoff.nonce,
      equal_size_package.handoff.journal_sha256);
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(nullptr);
  ok &= require(epoch_hook_called && equal_size_mutation_refused_or_denied(
                    epoch_hook_mutated, static_cast<bool>(equal_size_package_continuation)),
                "equal-size in-place retained package mutation after pin was accepted");

  auto equal_size_helper = prepare_fresh_epoch_fixture(
      "epoch-transition-equal-size-helper");
  epoch_hook_watch = equal_size_helper.handoff.inputs.helper;
  epoch_hook_called = false;
  epoch_hook_mutated = false;
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(
      overwrite_epoch_record_in_place_after_pin);
  auto equal_size_helper_continuation = facman::self_maintenance::admit_lifecycle_epoch_continuation(
      equal_size_helper.coordinator, "epoch.prepare.one", equal_size_helper.handoff.nonce,
      equal_size_helper.handoff.journal_sha256);
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(nullptr);
  ok &= require(epoch_hook_called && equal_size_mutation_refused_or_denied(
                    epoch_hook_mutated, static_cast<bool>(equal_size_helper_continuation)),
                "equal-size in-place retained helper mutation after pin was accepted");

  auto retained_ancestor_swap = prepare_fresh_epoch_fixture(
      "epoch-transition-retained-ancestor-swap");
  epoch_operation_hook_watch = retained_ancestor_swap.handoff.inputs.package.parent_path();
  epoch_operation_hook_outside = retained_ancestor_swap.epoch.acceptance_root / "outside-handoff";
  fs::create_directories(epoch_operation_hook_outside);
  std::ofstream(epoch_operation_hook_outside / "package.zip", std::ios::binary | std::ios::trunc) <<
      bytes(retained_ancestor_swap.handoff.inputs.package);
  std::ofstream(epoch_operation_hook_outside / "FacManSetup.exe", std::ios::binary | std::ios::trunc) <<
      bytes(retained_ancestor_swap.handoff.inputs.helper);
  epoch_operation_hook_called = false;
  epoch_operation_hook_rename_succeeded = false;
  epoch_operation_hook_symlink_succeeded = false;
  facman::self_maintenance::testing::set_epoch_handoff_operation_pinned_hook(
      swap_epoch_handoff_operation_after_pin);
  auto retained_ancestor_swap_continuation = facman::self_maintenance::admit_lifecycle_epoch_continuation(
      retained_ancestor_swap.coordinator, "epoch.prepare.one", retained_ancestor_swap.handoff.nonce,
      retained_ancestor_swap.handoff.journal_sha256);
  facman::self_maintenance::testing::set_epoch_handoff_operation_pinned_hook(nullptr);
  ok &= require(epoch_operation_hook_called &&
#ifdef _WIN32
                    ((!epoch_operation_hook_rename_succeeded &&
                      !epoch_operation_hook_symlink_succeeded) ||
                     (epoch_operation_hook_rename_succeeded &&
                      epoch_operation_hook_symlink_succeeded &&
                      !retained_ancestor_swap_continuation)),
#else
                    epoch_operation_hook_rename_succeeded &&
                    epoch_operation_hook_symlink_succeeded &&
                    !retained_ancestor_swap_continuation,
#endif
                "retained custody ancestor swap after operation-directory pin was accepted");

  auto foreign_final_fixture = prepare_fresh_epoch_fixture("epoch-transition-foreign-final");
  const fs::path foreign_final_package = foreign_final_fixture.epoch.acceptance_root /
      "foreign-retained-package.zip";
  std::ofstream(foreign_final_package, std::ios::binary | std::ios::trunc) <<
      bytes(foreign_final_fixture.handoff.inputs.package);
  const std::string foreign_final_original = bytes(foreign_final_fixture.handoff.journal);
  const std::string foreign_final_bytes = canonical_handoff_with_retained_package(
      foreign_final_original, foreign_final_package);
  replace_file(foreign_final_fixture.handoff.journal, foreign_final_bytes);
  auto foreign_final = facman::self_maintenance::prepare_lifecycle_epoch_transition(
      foreign_final_fixture.request, foreign_final_fixture.effects);
  ok &= require(foreign_final_bytes != foreign_final_original &&
                    json_string_field(facman::core::json::parse(foreign_final_bytes).value(),
                                      "retained_package") ==
                        facman::platform::path_to_utf8(foreign_final_package) &&
                    !foreign_final && bytes(foreign_final_fixture.handoff.journal) == foreign_final_bytes,
                "canonical-but-foreign FINAL handoff was not refused and preserved");

  auto foreign_staging_fixture = prepare_fresh_epoch_fixture("epoch-transition-foreign-staging");
  const fs::path foreign_staging_package = foreign_staging_fixture.epoch.acceptance_root /
      "foreign-retained-package.zip";
  std::ofstream(foreign_staging_package, std::ios::binary | std::ios::trunc) <<
      bytes(foreign_staging_fixture.handoff.inputs.package);
  const std::string foreign_staging_original = bytes(foreign_staging_fixture.handoff.journal);
  const std::string foreign_staging_bytes = canonical_handoff_with_retained_package(
      foreign_staging_original, foreign_staging_package);
  const fs::path foreign_staging_journal = foreign_staging_fixture.handoff.journal.parent_path() /
      "00-handoff-ready.staging.v2.json";
  std::error_code foreign_staging_error;
  fs::rename(foreign_staging_fixture.handoff.journal, foreign_staging_journal,
             foreign_staging_error);
  if (!foreign_staging_error) replace_file(foreign_staging_journal, foreign_staging_bytes);
  auto foreign_staging = foreign_staging_error
      ? facman::core::Result<facman::self_maintenance::EpochTransitionPreparation>::failure(
          {"test_rename_failed", foreign_staging_error.message(), {}})
      : facman::self_maintenance::prepare_lifecycle_epoch_transition(
          foreign_staging_fixture.request, foreign_staging_fixture.effects);
  ok &= require(!foreign_staging_error && foreign_staging_bytes != foreign_staging_original &&
                    json_string_field(facman::core::json::parse(foreign_staging_bytes).value(),
                                      "retained_package") ==
                        facman::platform::path_to_utf8(foreign_staging_package) &&
                    !foreign_staging && bytes(foreign_staging_journal) == foreign_staging_bytes,
                "canonical-but-foreign STAGING handoff was not refused and preserved");

  auto post_publication = make_preparation_fixture("epoch-transition-post-publication");
  post_publication.request.apply = true;
  epoch_hook_watch = post_publication.coordinator / "epochs" / post_publication.epoch.epoch_id /
      "maintenance" / "epoch.prepare.one" / "00-handoff-ready.v2.json";
  epoch_hook_mutation = epoch_hook_watch;
  epoch_hook_second_mutation = post_publication.epoch.state_root / "epoch-handoff" /
      "epoch.prepare.one" / "package.zip";
  epoch_hook_bytes = "foreign-post-publication-journal\n";
  epoch_hook_second_bytes = "foreign-post-publication-package\n";
  epoch_hook_called = false;
  epoch_hook_mutated = false;
  epoch_hook_second_mutated = false;
  epoch_hook_mutation_attempted = false;
  epoch_hook_second_mutation_attempted = false;
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(
      replace_epoch_record_and_retained_input_after_pin);
  auto post_publication_result = facman::self_maintenance::prepare_lifecycle_epoch_transition(
      post_publication.request, post_publication.effects);
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(nullptr);
  const bool post_publication_replaced = epoch_hook_mutated || epoch_hook_second_mutated;
  ok &= require(epoch_hook_called && epoch_hook_mutation_attempted &&
                    epoch_hook_second_mutation_attempted &&
                    (!post_publication_replaced || !post_publication_result)
#ifdef _WIN32
                    && (post_publication_replaced ||
                        (!epoch_hook_mutated && !epoch_hook_second_mutated))
#else
                    && epoch_hook_mutated && epoch_hook_second_mutated && !post_publication_result
#endif
                    , "post-publication journal and retained-input replacement was not rejected or denied while pinned");
  auto retained_mismatch = make_preparation_fixture("epoch-transition-retained-mismatch");
  retained_mismatch.request.apply = true;
  retained_mismatch.effects.retain_foreign_package = true;
  auto retained_package_mismatch = facman::self_maintenance::prepare_lifecycle_epoch_transition(
      retained_mismatch.request, retained_mismatch.effects);
  const bool mismatch_journal_exists = fs::exists(retained_mismatch.coordinator / "epochs" /
      retained_mismatch.epoch.epoch_id / "maintenance" / "epoch.prepare.one" /
      "00-handoff-ready.v2.json");
  ok &= require(!retained_package_mismatch && !mismatch_journal_exists,
                "foreign retained package was accepted into a new handoff");

  auto empty_retry = make_preparation_fixture("epoch-transition-empty-retry");
  fs::create_directories(empty_retry.coordinator / "epochs" / empty_retry.epoch.epoch_id /
      "maintenance" / "epoch.prepare.one");
  empty_retry.request.apply = true;
  auto empty_operation_retry = facman::self_maintenance::prepare_lifecycle_epoch_transition(
      empty_retry.request, empty_retry.effects);
  ok &= require(static_cast<bool>(empty_operation_retry),
                "empty maintenance operation directory did not recover into a handoff");

  auto empty_parent = make_preparation_fixture("epoch-transition-empty-parent");
  fs::create_directories(empty_parent.coordinator / "epochs" / empty_parent.epoch.epoch_id /
      "maintenance");
  empty_parent.request.apply = true;
  auto empty_parent_retry = facman::self_maintenance::prepare_lifecycle_epoch_transition(
      empty_parent.request, empty_parent.effects);
  ok &= require(static_cast<bool>(empty_parent_retry),
                "empty maintenance parent alone did not recover into a handoff");

  auto source_removed = prepare_fresh_epoch_fixture("epoch-transition-source-removed-retry");
  fs::remove(source_removed.source_package);
  EpochPreparationFakeEffects source_removed_restart;
  source_removed_restart.state_root = source_removed.epoch.state_root;
  source_removed_restart.helper_bytes = preparation_helper;
  auto source_removed_retry = facman::self_maintenance::prepare_lifecycle_epoch_transition(
      source_removed.request, source_removed_restart);
  ok &= require(source_removed_retry &&
                    source_removed_retry.value().journal_sha256 == source_removed.handoff.journal_sha256 &&
                    !source_removed_restart.reviewed_packages.empty() &&
                    source_removed_restart.reviewed_packages.back() == source_removed.handoff.inputs.package,
                "retry after source removal did not use its retained handoff input");

  auto provider_final = prepare_fresh_epoch_fixture("epoch-transition-provider-final-retry");
  EpochPreparationFakeEffects provider_final_restart;
  provider_final_restart.state_root = provider_final.epoch.state_root;
  provider_final_restart.helper_bytes = preparation_helper;
  auto provider_final_retry = facman::self_maintenance::prepare_lifecycle_epoch_transition(
      provider_final.request, provider_final_restart);
  const std::string provider_final_receipt = sha("epoch-provider-review\n" +
      facman::platform::path_to_utf8(provider_final.handoff.inputs.package.lexically_normal()));
  const std::string provider_final_stored = json_string_field(
      facman::core::json::parse(bytes(provider_final.handoff.journal)).value(),
      "provider_plan_sha256");

  auto provider_staging = prepare_fresh_epoch_fixture("epoch-transition-provider-staging-retry");
  const fs::path provider_staging_journal = provider_staging.handoff.journal.parent_path() /
      "00-handoff-ready.staging.v2.json";
  std::error_code provider_staging_rename_error;
  fs::rename(provider_staging.handoff.journal, provider_staging_journal,
             provider_staging_rename_error);
  EpochPreparationFakeEffects provider_staging_restart;
  provider_staging_restart.state_root = provider_staging.epoch.state_root;
  provider_staging_restart.helper_bytes = preparation_helper;
  auto provider_staging_retry = provider_staging_rename_error
      ? facman::core::Result<facman::self_maintenance::EpochTransitionPreparation>::failure(
          {"test_rename_failed", provider_staging_rename_error.message(), {}})
      : facman::self_maintenance::prepare_lifecycle_epoch_transition(
          provider_staging.request, provider_staging_restart);
  const std::string provider_staging_receipt = sha("epoch-provider-review\n" +
      facman::platform::path_to_utf8(provider_staging.handoff.inputs.package.lexically_normal()));
  const std::string provider_staging_stored = provider_staging_rename_error ? std::string() :
      json_string_field(facman::core::json::parse(bytes(provider_staging.handoff.journal)).value(),
                        "provider_plan_sha256");
  ok &= require(provider_final_retry && !provider_final_restart.reviewed_packages.empty() &&
                    provider_final_restart.reviewed_packages.back() == provider_final.handoff.inputs.package &&
                    provider_final_stored == provider_final_receipt && !provider_staging_rename_error &&
                    provider_staging_retry && !provider_staging_restart.reviewed_packages.empty() &&
                    provider_staging_restart.reviewed_packages.back() == provider_staging.handoff.inputs.package &&
                    provider_staging_stored == provider_staging_receipt &&
                    provider_final_receipt != provider_staging_receipt,
                "provider restart, final retry, or staging retry did not bind a path-derived retained receipt");

  const fs::path fork_coordinator = epoch_fixture("epoch-linked-fork");
  const auto fork_epoch = epoch_from(fork_coordinator);
  const Generation fork_a = make_epoch_update_generation(fork_epoch, "9.8.8", 'd');
  const Generation fork_b = make_epoch_update_generation(fork_epoch, "9.8.9", 'e');
  write_epoch_link(fork_coordinator, fork_epoch, "update", "epoch.update.one", epoch_generation,
      fork_a, genesis_activation_name, genesis_sha_for(fork_coordinator, fork_epoch));
  write_epoch_link(fork_coordinator, fork_epoch, "update", "epoch.update.two", epoch_generation,
      fork_b, genesis_activation_name, genesis_sha_for(fork_coordinator, fork_epoch));
  auto forked_epoch = facman::self_maintenance::discover_lifecycle_epoch_active(fork_coordinator);

  const fs::path direction_coordinator = epoch_fixture("epoch-linked-invalid-direction");
  const auto direction_epoch = epoch_from(direction_coordinator);
  const Generation direction_target = make_epoch_update_generation(direction_epoch, "9.8.6", 'd');
  write_epoch_link(direction_coordinator, direction_epoch, "update", "epoch.update.one",
      epoch_generation, direction_target, genesis_activation_name,
      genesis_sha_for(direction_coordinator, direction_epoch));
  auto invalid_link_direction = facman::self_maintenance::discover_lifecycle_epoch_active(
      direction_coordinator);
  const fs::path downgrade_direction_coordinator = epoch_fixture(
      "epoch-linked-invalid-downgrade-direction");
  const auto downgrade_direction_epoch = epoch_from(downgrade_direction_coordinator);
  const Generation downgrade_direction_target = make_epoch_update_generation(
      downgrade_direction_epoch, "9.8.8", 'd');
  write_epoch_link(downgrade_direction_coordinator, downgrade_direction_epoch, "downgrade",
      "epoch.update.one", epoch_generation, downgrade_direction_target,
      genesis_activation_name,
      genesis_sha_for(downgrade_direction_coordinator, downgrade_direction_epoch));
  auto invalid_downgrade_direction = facman::self_maintenance::discover_lifecycle_epoch_active(
      downgrade_direction_coordinator);
  const fs::path malformed_link_coordinator = epoch_fixture("epoch-linked-malformed-operation");
  const auto malformed_link_epoch = epoch_from(malformed_link_coordinator);
  const Generation malformed_link_target = make_epoch_update_generation(malformed_link_epoch, "9.8.8", 'd');
  write_epoch_link(malformed_link_coordinator, malformed_link_epoch, "rollback", "epoch.update.one",
      epoch_generation, malformed_link_target, genesis_activation_name,
      genesis_sha_for(malformed_link_coordinator, malformed_link_epoch));
  auto malformed_link_operation = facman::self_maintenance::discover_lifecycle_epoch_active(
      malformed_link_coordinator);
  ok &= require(!malformed_link_operation,
                "unsupported or malformed v2 linked activation operation was accepted");
  ok &= require(!invalid_link_direction && !invalid_downgrade_direction,
                "semver-invalid v2 update or downgrade direction was accepted");

  const fs::path broken_coordinator = epoch_fixture("epoch-linked-broken");
  const auto broken_epoch = epoch_from(broken_coordinator);
  const Generation broken_target = make_epoch_update_generation(broken_epoch, "9.8.8", 'd');
  write_epoch_link(broken_coordinator, broken_epoch, "update", "epoch.update.one", epoch_generation,
      broken_target, "activation.epoch.update.one.v2.json", std::string(64, 'a'));
  auto broken_epoch_result = facman::self_maintenance::discover_lifecycle_epoch_active(
      broken_coordinator);

  const fs::path mismatch_coordinator = epoch_fixture("epoch-linked-mismatch");
  const auto mismatch_epoch = epoch_from(mismatch_coordinator);
  const Generation mismatch_target = make_epoch_update_generation(mismatch_epoch, "9.8.8", 'd');
  Generation mismatched_source = make_epoch_update_generation(mismatch_epoch, "9.8.7", 'f');
  write_epoch_link(mismatch_coordinator, mismatch_epoch, "update", "epoch.update.one",
      mismatched_source, mismatch_target, genesis_activation_name,
      genesis_sha_for(mismatch_coordinator, mismatch_epoch));
  auto mismatch_epoch_result = facman::self_maintenance::discover_lifecycle_epoch_active(
      mismatch_coordinator);

  const fs::path missing_coordinator = epoch_fixture("epoch-linked-missing");
  const auto missing_epoch = epoch_from(missing_coordinator);
  const Generation missing_target = make_epoch_update_generation(missing_epoch, "9.8.8", 'd');
  write_new_record(missing_coordinator / "epochs" / missing_epoch.epoch_id / "activations" /
      "activation.epoch.update.one.v2.json", epoch_link_bytes(missing_epoch, "update",
      "epoch.update.one", epoch_generation.generation_id, missing_target.generation_id,
      std::string(64, 'a'), genesis_activation_name,
      genesis_sha_for(missing_coordinator, missing_epoch)));
  auto missing_epoch_result = facman::self_maintenance::discover_lifecycle_epoch_active(
      missing_coordinator);

  const fs::path noncanonical_coordinator = epoch_fixture("epoch-linked-noncanonical");
  const auto noncanonical_epoch = epoch_from(noncanonical_coordinator);
  const Generation noncanonical_target = make_epoch_update_generation(noncanonical_epoch, "9.8.8", 'd');
  write_new_record(noncanonical_coordinator / "epochs" / noncanonical_epoch.epoch_id /
      "generations" / ("generation." + noncanonical_target.generation_id + ".v2.json"), "{}\n");
  write_new_record(noncanonical_coordinator / "epochs" / noncanonical_epoch.epoch_id /
      "activations" / "activation.epoch.update.one.v2.json", epoch_link_bytes(noncanonical_epoch,
      "update", "epoch.update.one", epoch_generation.generation_id,
      noncanonical_target.generation_id, sha("{}\n"), genesis_activation_name,
      genesis_sha_for(noncanonical_coordinator, noncanonical_epoch)));
  auto noncanonical_epoch_result = facman::self_maintenance::discover_lifecycle_epoch_active(
      noncanonical_coordinator);

  const fs::path cycle_coordinator = epoch_fixture("epoch-linked-cycle");
  const auto cycle_epoch = epoch_from(cycle_coordinator);
  const Generation cycle_target = make_epoch_update_generation(cycle_epoch, "9.8.8", 'd');
  write_epoch_link(cycle_coordinator, cycle_epoch, "update", "epoch.update.one", cycle_target,
      cycle_target, "activation.epoch.update.one.v2.json", std::string(64, 'a'));
  auto cycle_epoch_result = facman::self_maintenance::discover_lifecycle_epoch_active(
      cycle_coordinator);

  const fs::path wrong_epoch_coordinator = epoch_fixture("epoch-linked-wrong-epoch");
  const auto wrong_epoch = epoch_from(wrong_epoch_coordinator);
  auto foreign_epoch = wrong_epoch;
  foreign_epoch.epoch_id = std::string(64, 'a');
  const Generation foreign_target = make_epoch_update_generation(foreign_epoch, "9.8.8", 'd');
  const std::string foreign_record = epoch_generation_bytes(foreign_epoch, foreign_target);
  write_new_record(wrong_epoch_coordinator / "epochs" / wrong_epoch.epoch_id / "generations" /
      ("generation." + foreign_target.generation_id + ".v2.json"), foreign_record);
  write_new_record(wrong_epoch_coordinator / "epochs" / wrong_epoch.epoch_id / "activations" /
      "activation.epoch.update.one.v2.json", epoch_link_bytes(wrong_epoch, "update",
      "epoch.update.one", epoch_generation.generation_id, foreign_target.generation_id,
      sha(foreign_record), genesis_activation_name,
      genesis_sha_for(wrong_epoch_coordinator, wrong_epoch)));
  auto wrong_epoch_result = facman::self_maintenance::discover_lifecycle_epoch_active(
      wrong_epoch_coordinator);

  const fs::path extras_coordinator = epoch_fixture("epoch-linked-extras");
  const auto extras_epoch = epoch_from(extras_coordinator);
  const Generation extras_target = make_epoch_update_generation(extras_epoch, "9.8.8", 'd');
  const Generation extras_unused = make_epoch_update_generation(extras_epoch, "9.8.9", 'e');
  write_epoch_link(extras_coordinator, extras_epoch, "update", "epoch.update.one", epoch_generation,
      extras_target, genesis_activation_name, genesis_sha_for(extras_coordinator, extras_epoch));
  write_epoch_generation(extras_coordinator, extras_epoch, extras_unused);
  auto extras_epoch_result = facman::self_maintenance::discover_lifecycle_epoch_active(
      extras_coordinator);
  ok &= require(!forked_epoch && !broken_epoch_result && !mismatch_epoch_result &&
                    !missing_epoch_result && !noncanonical_epoch_result && !cycle_epoch_result &&
                    !wrong_epoch_result && !extras_epoch_result &&
                    forked_epoch.error().code == "self_maintenance_epoch_recovery_required" &&
                    broken_epoch_result.error().code == "self_maintenance_epoch_recovery_required" &&
                    mismatch_epoch_result.error().code == "self_maintenance_epoch_recovery_required" &&
                    missing_epoch_result.error().code == "self_maintenance_epoch_recovery_required" &&
                    noncanonical_epoch_result.error().code == "self_maintenance_epoch_recovery_required" &&
                    cycle_epoch_result.error().code == "self_maintenance_epoch_recovery_required" &&
                    wrong_epoch_result.error().code == "self_maintenance_epoch_recovery_required" &&
                    extras_epoch_result.error().code == "self_maintenance_epoch_recovery_required",
                "epoch activation fork, broken predecessor, generation binding, or extras were admitted");

  const fs::path activation_staging_root = root / "epoch-activation-staging";
  facman::self_maintenance::LifecycleEpoch activation_staging_epoch;
  activation_staging_epoch.acceptance_root = activation_staging_root;
  activation_staging_epoch.logical_root = activation_staging_root / "FacMan";
  activation_staging_epoch.state_root = activation_staging_root / "state";
  activation_staging_epoch.genesis_generation_id = generation_identity("9.8.7", genesis_package, 'c');
  fs::create_directories(activation_staging_root);
  const fs::path activation_staging_coordinator = activation_staging_root / "coordinator";
  auto activation_staging_manifest = facman::self_maintenance::publish_lifecycle_epoch(
      activation_staging_coordinator, activation_staging_epoch, true);
  Generation activation_staging_generation;
  if (activation_staging_manifest && !activation_staging_manifest.value().epochs.empty()) {
    auto made = facman::self_maintenance::make_epoch_genesis_generation(
        activation_staging_manifest.value().epochs.front(), genesis_descriptor, genesis_package);
    if (made) activation_staging_generation = made.take_value();
  }
  facman::self_maintenance::EpochGenesisRequest activation_staging_request{
      activation_staging_coordinator,
      activation_staging_manifest && !activation_staging_manifest.value().epochs.empty()
          ? activation_staging_manifest.value().epochs.front().epoch_id : std::string(),
      activation_staging_generation, true};
  facman::platform::testing::set_relative_publish_pre_rename_fault_countdown(2U);
  auto activation_staging_fault = facman::self_maintenance::activate_lifecycle_epoch_genesis(
      activation_staging_request);
  facman::platform::testing::set_relative_publish_pre_rename_fault_countdown(0U);
  const bool activation_staging_present = fs::exists(activation_staging_coordinator / "epochs" /
      activation_staging_request.epoch_id / "activations" /
      ("activation.staging.epoch.genesis." + activation_staging_generation.generation_id + ".v2.json"));
  auto activation_staging_retry = facman::self_maintenance::activate_lifecycle_epoch_genesis(
      activation_staging_request);
  ok &= require(activation_staging_manifest && !activation_staging_fault &&
                    activation_staging_present && activation_staging_retry,
                "activation staging recovery was not exact and resumable");

  struct GenesisFixture {
    fs::path coordinator;
    facman::self_maintenance::EpochGenesisRequest request;
    bool valid = false;
  };
  const auto make_genesis_fixture = [&](const fs::path &fixture_root) {
    GenesisFixture fixture;
    facman::self_maintenance::LifecycleEpoch fixture_epoch;
    fixture_epoch.acceptance_root = fixture_root;
    fixture_epoch.logical_root = fixture_root / "FacMan";
    fixture_epoch.state_root = fixture_root / "state";
    fixture_epoch.genesis_generation_id = generation_identity("9.8.7", genesis_package, 'c');
    fs::create_directories(fixture_root);
    fixture.coordinator = fixture_root / "coordinator";
    auto manifest = facman::self_maintenance::publish_lifecycle_epoch(
        fixture.coordinator, fixture_epoch, true);
    if (!manifest || manifest.value().epochs.empty()) return fixture;
    auto generation = facman::self_maintenance::make_epoch_genesis_generation(
        manifest.value().epochs.front(), genesis_descriptor, genesis_package);
    if (!generation) return fixture;
    fixture.request = {fixture.coordinator, manifest.value().epochs.front().epoch_id,
                       generation.take_value(), true};
    fixture.valid = true;
    return fixture;
  };
  auto partial_fixture = make_genesis_fixture(root / "epoch-partial-staging");
  facman::platform::testing::set_relative_publish_pre_rename_fault_countdown(1U);
  auto partial_fault = partial_fixture.valid
      ? facman::self_maintenance::activate_lifecycle_epoch_genesis(partial_fixture.request)
      : facman::core::Result<facman::self_maintenance::ActiveState>::failure(
          {"test", "partial fixture unavailable", ""});
  facman::platform::testing::set_relative_publish_pre_rename_fault_countdown(0U);
  const fs::path partial_staging = partial_fixture.coordinator / "epochs" /
      partial_fixture.request.epoch_id / "generations" /
      ("generation.staging." + partial_fixture.request.generation.generation_id + ".v2.json");
  std::ofstream(partial_staging, std::ios::binary | std::ios::trunc) << "partial staging bytes";
  auto partial_retry = facman::self_maintenance::activate_lifecycle_epoch_genesis(
      partial_fixture.request);
  std::ifstream partial_staging_input(partial_staging, std::ios::binary);
  const std::string partial_staging_bytes{std::istreambuf_iterator<char>(partial_staging_input), {}};

  auto substitution_fixture = make_genesis_fixture(root / "epoch-substitution-staging");
  facman::platform::testing::set_relative_publish_pre_rename_fault_countdown(1U);
  auto substitution_fault = substitution_fixture.valid
      ? facman::self_maintenance::activate_lifecycle_epoch_genesis(substitution_fixture.request)
      : facman::core::Result<facman::self_maintenance::ActiveState>::failure(
          {"test", "substitution fixture unavailable", ""});
  facman::platform::testing::set_relative_publish_pre_rename_fault_countdown(0U);
  before_reopen_source = substitution_fixture.coordinator / "epochs" /
      substitution_fixture.request.epoch_id / "generations" /
      ("generation.staging." + substitution_fixture.request.generation.generation_id + ".v2.json");
  before_reopen_moved = before_reopen_source.parent_path() / "generation.validated-moved.v2.json";
  facman::platform::testing::set_relative_publish_before_reopen_hook(substitute_before_reopen);
  auto substitution_retry = facman::self_maintenance::activate_lifecycle_epoch_genesis(
      substitution_fixture.request);
  facman::platform::testing::set_relative_publish_before_reopen_hook(nullptr);
  std::ifstream substitution_input(before_reopen_source, std::ios::binary);
  const std::string substitution_bytes{std::istreambuf_iterator<char>(substitution_input), {}};
  const bool substitution_preserved = fs::exists(before_reopen_source) &&
      fs::exists(before_reopen_moved) && substitution_bytes == "foreign staging bytes";
  before_reopen_source.clear();
  before_reopen_moved.clear();
  ok &= require(partial_fixture.valid && !partial_fault && !partial_retry &&
                    partial_staging_bytes == "partial staging bytes" &&
                    substitution_fixture.valid && !substitution_fault &&
                    !substitution_retry && substitution_preserved,
                "partial or substituted genesis staging was not refused and preserved");

  auto invalid_epoch = first_epoch;
  invalid_epoch.epoch_id = std::string(64, '0');
  auto invalid_epoch_result = facman::self_maintenance::publish_lifecycle_epoch(
      epoch_coordinator, invalid_epoch, false);
  const fs::path incomplete_epoch_root = root / "epoch-incomplete" / "coordinator" /
      "epochs" / std::string(64, 'a');
  fs::create_directories(incomplete_epoch_root);
  auto incomplete_epoch = facman::self_maintenance::discover_lifecycle_epoch_chain(
      root / "epoch-incomplete" / "coordinator");
  ok &= require(!invalid_epoch_result && !incomplete_epoch &&
                    incomplete_epoch.error().code ==
                        "self_maintenance_epoch_recovery_required",
                "epoch id refusal or incomplete manifest recovery was not enforced");

  const fs::path forbidden_epoch_state = epoch_coordinator / "epochs" /
      epoch_chain.value().epochs.front().epoch_id / "maintenance";
  fs::create_directories(forbidden_epoch_state);
  auto state_before_routing = facman::self_maintenance::discover_lifecycle_epoch_chain(
      epoch_coordinator);
  auto active_before_routing = facman::self_maintenance::discover_lifecycle_epoch_active(
      epoch_coordinator);
  fs::remove_all(forbidden_epoch_state, ignored);
  ok &= require(!state_before_routing && !active_before_routing &&
                    state_before_routing.error().code ==
                        "self_maintenance_epoch_recovery_required" &&
                    active_before_routing.error().code ==
                        "self_maintenance_epoch_recovery_required",
                "real epoch state was admitted before epoch routing exists");

  // A completed flat v1 retirement is represented by the synthesized all-zero
  // predecessor and can seed the first real epoch without changing routing.
  auto v1_chain = facman::self_maintenance::discover_lifecycle_epoch_chain(
      completed_chain.coordinator_root);
  facman::self_maintenance::LifecycleEpoch successor_epoch;
  if (v1_chain && !v1_chain.value().epochs.empty()) {
    const auto &compatibility = v1_chain.value().epochs.back();
    successor_epoch.acceptance_root = compatibility.acceptance_root;
    successor_epoch.genesis_generation_id = std::string(64, 'b');
    successor_epoch.logical_root = compatibility.logical_root;
    successor_epoch.state_root = compatibility.state_root;
    successor_epoch.predecessor_epoch_id = compatibility.epoch_id;
    successor_epoch.predecessor_manifest_sha256 = compatibility.manifest_sha256;
    successor_epoch.predecessor_retirement_sha256 = compatibility.retirement_sha256;
  }
  auto v1_successor = facman::self_maintenance::publish_lifecycle_epoch(
      completed_chain.coordinator_root, successor_epoch, true);
  ok &= require(v1_chain && v1_chain.value().epochs.size() == 1U &&
                    v1_chain.value().epochs.front().compatibility_epoch &&
                    !v1_chain.value().epochs.front().retirement_sha256.empty() &&
                    v1_successor && v1_successor.value().epochs.size() == 2U,
                "completed flat v1 history did not seed its first epoch");

  fs::remove_all(root, ignored);
  return ok ? 0 : 1;
}
