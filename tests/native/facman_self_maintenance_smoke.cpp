// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_self_maintenance.h"
#include "facman_self_maintenance_provider.h"

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
unsigned epoch_hook_matching_calls = 0U;
unsigned epoch_hook_trigger_call = 1U;
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

void mutate_epoch_record_after_nth_matching_pin(const fs::path &path) {
  if (path != epoch_hook_watch) return;
  ++epoch_hook_matching_calls;
  if (epoch_hook_matching_calls != epoch_hook_trigger_call) return;
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

std::string canonical_handoff_with_field(
    const std::string &journal, const std::string &changed_field,
    const std::string &changed_value) {
  auto parsed = facman::core::json::parse(journal);
  if (!parsed || !parsed.value().is_object())
    throw std::runtime_error("could not parse canonical handoff fixture");
  const char *const fields[] = {
      "schema", "product_id", "epoch_id", "epoch_manifest_sha256", "operation",
      "operation_id", "source_generation_id", "source_activation_name",
      "source_activation_sha256", "target_generation_id", "retained_package",
      "retained_package_sha256", "continuation_helper",
      "continuation_helper_sha256", "provider_plan_sha256", "nonce",
      "shell_integration"};
  facman::core::json::ObjectBuilder rebuilt;
  for (const char *field : fields) {
    const std::string value = std::string(field) == changed_field
        ? changed_value
        : json_string_field(parsed.value(), field);
    if (!rebuilt.add_string(field, value))
      throw std::runtime_error(std::string("could not rebuild handoff field: ") + field);
  }
  return rebuilt.serialize() + "\n";
}

std::string canonical_handoff_with_retained_package(
    const std::string &journal, const fs::path &retained_package) {
  return canonical_handoff_with_field(
      journal, "retained_package",
      facman::platform::path_to_utf8(retained_package));
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
  bool fail_retire = false;
  unsigned review_calls = 0;
  unsigned prepare_calls = 0;
  bool fail_verify = false;
  unsigned install_calls = 0;
  unsigned inspect_calls = 0;
  unsigned verify_calls = 0;
  unsigned shortcut_calls = 0;
  unsigned registration_calls = 0;
  unsigned retire_calls = 0;
  std::string provider_operation;
  std::function<void()> after_review;
  std::function<void()> after_prepare;
  std::function<void()> after_install;
  std::function<void()> after_shortcut;

  CandidateState inspect_candidate(const Plan &) override { return candidate; }
  EffectResult review_install_local(const Plan &) override {
    ++review_calls;
    if (after_review) after_review();
    return {!fail_prepare, false, sha("review"),
            fail_prepare ? "plan refused" : ""};
  }
  EffectResult prepare_install_local(const Plan &) override {
    ++prepare_calls;
    if (after_prepare) after_prepare();
    return {true, false, sha("prepare"), ""};
  }
  EffectResult install_local(const Plan &plan) override {
    ++install_calls;
    provider_operation = plan.provider_operation;
    if (fail_install) return {false, true, {}, "lost receipt"};
    candidate = CandidateState::exact;
    if (after_install) after_install();
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
    if (after_shortcut) after_shortcut();
    return {true, false, sha("shortcut"), {}};
  }
  EffectResult cutover_registration(const Plan &) override {
    ++registration_calls;
    registration = ShellState::new_exact;
    return {true, false, sha("registration"), {}};
  }
  EffectResult retire_shortcut_backup(const Plan &) override {
    ++retire_calls;
    return fail_retire
        ? EffectResult{false, false, {}, "backup retirement failure"}
        : EffectResult{true, false, sha("shortcut backup retired"), {}};
  }
};

struct RetirementFakeEffects final : facman::self_maintenance::RetirementEffects {
  std::vector<std::string> inspected;
  std::vector<std::string> removed;
  bool reject_identity = false;
  bool interrupt_active = false;

  facman::core::Result<void> inspect_retirement_generation(
      const Generation &generation, bool,
      const facman::self_maintenance::CoordinatorLockToken &) override {
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
  fs::path acceptance_root;
  unsigned inspect_calls = 0;
  unsigned review_calls = 0;
  unsigned retain_calls = 0;
  bool retain_foreign_package = false;
  bool use_production_review = false;
  std::string helper_bytes;
  std::vector<fs::path> reviewed_packages;

  CandidateState inspect_candidate(const Plan &) override {
    ++inspect_calls;
    return CandidateState::absent;
  }
  EffectResult review_install_local(const Plan &plan) override {
    ++review_calls;
    reviewed_packages.push_back(plan.package);
    if (use_production_review) {
      facman::self_maintenance::ProviderBridge provider(state_root,
                                                        acceptance_root);
      return provider.review_install_local(plan);
    }
    return {true, false, sha("epoch-provider-review\n" +
        facman::platform::path_to_utf8(plan.package.lexically_normal())), {}};
  }
  facman::core::Result<facman::self_maintenance::RetainedMaintenanceInputs>
  retain_handoff_inputs(const Plan &plan, const fs::path &continuation_helper,
                        const std::string &continuation_helper_sha256) override {
    ++retain_calls;
    const fs::path retained = state_root / "epoch-handoff" / plan.operation_id;
    fs::create_directories(retained);
    const fs::path package = retained / "package.zip";
    const fs::path helper = retained / "FacManContinuation.exe";
    std::ofstream(package, std::ios::binary | std::ios::trunc) <<
        (retain_foreign_package ? "foreign-package" : bytes(plan.package));
    std::ofstream(helper, std::ios::binary | std::ios::trunc) <<
        bytes(continuation_helper);
    if (sha(bytes(helper)) != continuation_helper_sha256)
      return facman::core::Result<facman::self_maintenance::RetainedMaintenanceInputs>::failure(
          {"test_continuation_helper_changed", "continuation helper digest changed", {}});
    return facman::core::Result<facman::self_maintenance::RetainedMaintenanceInputs>::success(
        {package, sha(bytes(package)), helper, sha(bytes(helper))});
  }
};

struct EpochContinuationFakeEffects final
    : facman::self_maintenance::EpochContinuationEffects {
  CandidateState candidate = CandidateState::absent;
  unsigned bind_calls = 0;
  unsigned prepare_calls = 0;
  unsigned apply_calls = 0;
  unsigned inspect_calls = 0;
  unsigned verify_calls = 0;
  bool lose_apply_receipt = false;
  bool refuse_prepare = false;
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
  EffectResult prepare_install_local(const Plan &) override {
    ++prepare_calls;
    return refuse_prepare
        ? EffectResult{false, false, {}, "injected offline-retention refusal"}
        : EffectResult{true, false, {}, {}};
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

struct EpochPublicationFakeEffects final : facman::self_maintenance::EpochPublicationEffects {
  unsigned inspect_calls = 0;
  unsigned terminal_calls = 0;
  std::string installed_receipt = sha("epoch.inspect");
  std::function<void()> after_inspect;
  std::function<void()> after_terminal;
  EffectResult inspect_installed(
      const Plan &, const facman::self_maintenance::ProviderApplyBinding &) override {
    ++inspect_calls;
    if (after_inspect) after_inspect();
    return {true, false, installed_receipt, {}};
  }
  EffectResult validate_terminal_verification(
      const Plan &, const facman::self_maintenance::ProviderApplyBinding &,
      const std::string &receipt) override {
    ++terminal_calls;
    if (after_terminal) after_terminal();
    return receipt == sha("epoch.verify")
        ? EffectResult{true, false, receipt, {}}
        : EffectResult{false, false, {}, "terminal receipt changed"};
  }
};

struct EpochShellCutoverFakeEffects final : facman::self_maintenance::EpochShellCutoverEffects {
  ShellState shortcut = ShellState::old_exact;
  ShellState registration = ShellState::old_exact;
  unsigned terminal_calls = 0;
  unsigned shortcut_calls = 0;
  unsigned registration_calls = 0;
  unsigned retire_calls = 0;
  bool fail_retire = false;
  EffectResult inspect_installed(
      const Plan &, const facman::self_maintenance::ProviderApplyBinding &) override {
    return {true, false, sha("epoch.inspect"), {}};
  }
  EffectResult validate_terminal_verification(
      const Plan &, const facman::self_maintenance::ProviderApplyBinding &,
      const std::string &receipt) override {
    ++terminal_calls;
    return receipt == sha("epoch.verify")
        ? EffectResult{true, false, receipt, {}}
        : EffectResult{false, false, {}, "terminal receipt changed"};
  }
  ShellState inspect_shortcut(const Plan &) override { return shortcut; }
  ShellState inspect_registration(const Plan &) override { return registration; }
  EffectResult cutover_shortcut(const Plan &) override {
    ++shortcut_calls;
    shortcut = ShellState::new_exact;
    return {true, false, sha("epoch.shortcut"), {}};
  }
  EffectResult cutover_registration(const Plan &) override {
    ++registration_calls;
    registration = ShellState::new_exact;
    return {true, false, sha("epoch.registration"), {}};
  }
  EffectResult retire_shortcut_backup(const Plan &) override {
    ++retire_calls;
    return fail_retire
        ? EffectResult{false, false, {}, "epoch backup retirement failure"}
        : EffectResult{true, false, sha("epoch.shortcut backup retired"), {}};
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
  result.install_id = "facman.self.eg." +
      sha("facman.self.epoch-generation-install.v1\n" + epoch.epoch_id + "\n" +
          result.generation_id + "\n");
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

int emit_prehandoff_epoch_fixture(int argc, char **argv) {
  if (argc != 9) {
    std::cerr << "usage: facman_self_maintenance_smoke --emit-prehandoff-epoch "
                 "<coordinator> <logical-root> <state-root> <acceptance-root> "
                 "<source-package> <target-package> <operation>\n";
    return 2;
  }
  const fs::path coordinator = fs::absolute(fs::path(argv[2])).lexically_normal();
  const fs::path logical_root = fs::absolute(fs::path(argv[3])).lexically_normal();
  const fs::path state_root = fs::absolute(fs::path(argv[4])).lexically_normal();
  const fs::path acceptance_root = fs::absolute(fs::path(argv[5])).lexically_normal();
  const fs::path source_package = fs::absolute(fs::path(argv[6])).lexically_normal();
  const fs::path target_package = fs::absolute(fs::path(argv[7])).lexically_normal();
  const std::string operation = argv[8];
  if (operation != "update" && operation != "downgrade") {
    std::cerr << "fixture operation must be update or downgrade\n";
    return 2;
  }

  auto source = facman::self_maintenance::inspect_package(source_package);
  auto target = facman::self_maintenance::inspect_package(target_package);
  if (!source || !target) {
    const auto &error = !source ? source.error() : target.error();
    std::cerr << error.code << ": " << error.message << " (" << error.detail << ")\n";
    return 3;
  }
  auto seed = facman::self_maintenance::make_generation(
      source.value().descriptor, source.value().package_sha256, "facman.self",
      logical_root, logical_root, state_root, acceptance_root);
  if (!seed) {
    std::cerr << seed.error().code << ": " << seed.error().message << '\n';
    return 3;
  }

  facman::self_maintenance::LifecycleEpoch proposed;
  proposed.acceptance_root = acceptance_root;
  proposed.logical_root = logical_root;
  proposed.state_root = state_root;
  proposed.genesis_generation_id = seed.value().generation_id;
  auto published = facman::self_maintenance::publish_lifecycle_epoch(
      coordinator, proposed, true);
  if (!published || published.value().epochs.size() != 1U) {
    if (!published)
      std::cerr << published.error().code << ": " << published.error().message
                << " (" << published.error().detail << ")\n";
    else
      std::cerr << "fixture publication did not create exactly one epoch\n";
    return 3;
  }
  const auto &epoch = published.value().epochs.front();
  auto generation = facman::self_maintenance::make_epoch_genesis_generation(
      epoch, source.value().descriptor, source.value().package_sha256);
  if (!generation) {
    std::cerr << generation.error().code << ": " << generation.error().message << '\n';
    return 3;
  }
  facman::self_maintenance::EpochGenesisRequest genesis{
      coordinator, epoch.epoch_id, generation.value(), true};
  auto activated = facman::self_maintenance::activate_lifecycle_epoch_genesis(genesis);
  if (!activated) {
    std::cerr << activated.error().code << ": " << activated.error().message
              << " (" << activated.error().detail << ")\n";
    return 3;
  }
  const std::string operation_id = "maint." + operation + "." +
      generation.value().generation_id.substr(0, 8) + "." +
      target.value().package_sha256.substr(0, 20);
  std::error_code error;
  const fs::path operation_root = coordinator / "epochs" / epoch.epoch_id /
      "maintenance" / operation_id;
  if (!fs::create_directories(operation_root, error) || error) {
    std::cerr << "could not create empty pre-handoff operation: "
              << error.message() << '\n';
    return 3;
  }

  facman::core::json::ObjectBuilder output;
  output.add_string("schema", "facman.self_maintenance_test_epoch.v1");
  output.add_string("epoch_id", epoch.epoch_id);
  output.add_string("generation_id", generation.value().generation_id);
  output.add_string("install_id", generation.value().install_id);
  output.add_string("operation_id", operation_id);
  output.add_string("coordinator", facman::platform::path_to_utf8(coordinator));
  output.add_string("source_install_root",
                    facman::platform::path_to_utf8(generation.value().install_root));
  std::cout << output.serialize() << '\n';
  return 0;
}

int stage_existing_handoff_fixture(int argc, char **argv) {
  if (argc != 8) {
    std::cerr << "usage: facman_self_maintenance_smoke --stage-existing-handoff "
                 "<coordinator> <state-root> <acceptance-root> <target-package> "
                 "<operation> <continuation-helper>\n";
    return 2;
  }
  const fs::path coordinator = fs::absolute(fs::path(argv[2])).lexically_normal();
  const fs::path state_root = fs::absolute(fs::path(argv[3])).lexically_normal();
  const fs::path acceptance_root = fs::absolute(fs::path(argv[4])).lexically_normal();
  const fs::path target_package = fs::absolute(fs::path(argv[5])).lexically_normal();
  const std::string operation = argv[6];
  const fs::path continuation_helper =
      fs::absolute(fs::path(argv[7])).lexically_normal();
  if (operation != "update" && operation != "downgrade") {
    std::cerr << "fixture operation must be update or downgrade\n";
    return 2;
  }

  auto active = facman::self_maintenance::discover_lifecycle_epoch_active(
      coordinator);
  auto target = facman::self_maintenance::inspect_package(target_package);
  if (!active || !target) {
    const auto &failure = !active ? active.error() : target.error();
    std::cerr << failure.code << ": " << failure.message << " ("
              << failure.detail << ")\n";
    return 3;
  }
  const std::string operation_id = "maint." + operation + "." +
      active.value().active.active.generation_id.substr(0, 8) + "." +
      target.value().package_sha256.substr(0, 20);
  EpochPreparationFakeEffects effects;
  effects.state_root = state_root;
  effects.acceptance_root = acceptance_root;
  effects.use_production_review = true;
  facman::self_maintenance::EpochTransitionRequest request{
      coordinator, active.value().epoch.epoch_id,
      operation == "update" ? Operation::update : Operation::downgrade,
      operation_id, target.value(), true, continuation_helper,
      sha(bytes(continuation_helper)), false};
  auto prepared = facman::self_maintenance::prepare_lifecycle_epoch_transition(
      request, effects);
  if (!prepared) {
    std::cerr << prepared.error().code << ": " << prepared.error().message
              << " (" << prepared.error().detail << ")\n";
    return 3;
  }
  std::error_code error;
  const fs::path staged = prepared.value().journal.parent_path() /
      "00-handoff-ready.staging.v3.json";
  fs::rename(prepared.value().journal, staged, error);
  if (error) {
    std::cerr << "could not stage prepared handoff: " << error.message() << '\n';
    return 3;
  }

  facman::core::json::ObjectBuilder output;
  output.add_string("schema", "facman.self_maintenance_test_epoch.v1");
  output.add_string("epoch_id", active.value().epoch.epoch_id);
  output.add_string("generation_id",
                    active.value().active.active.generation_id);
  output.add_string("operation_id", operation_id);
  output.add_string("coordinator", facman::platform::path_to_utf8(coordinator));
  output.add_string("source_install_root", facman::platform::path_to_utf8(
      active.value().active.active.install_root));
  std::cout << output.serialize() << '\n';
  return 0;
}

} // namespace

int main(int argc, char **argv) {
  if (argc > 1 && std::string(argv[1]) == "--emit-prehandoff-epoch")
    return emit_prehandoff_epoch_fixture(argc, argv);
  if (argc > 1 && std::string(argv[1]) == "--stage-existing-handoff")
    return stage_existing_handoff_fixture(argc, argv);
  if (argc != 1) {
    std::cerr << "unexpected facman_self_maintenance_smoke arguments\n";
    return 2;
  }
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
                    update_effects.registration_calls == 1 &&
                    update_effects.retire_calls == 1,
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
                    update_effects.install_calls == completed_install_calls &&
                    update_effects.retire_calls == 2U,
                "completed update retry was not idempotent");

  auto retirement_failure = request(root / "retirement-failure",
                                    Operation::update);
  retirement_failure.apply = true;
  FakeEffects retirement_failure_effects;
  retirement_failure_effects.fail_retire = true;
  auto retirement_failed = facman::self_maintenance::execute(
      retirement_failure, retirement_failure_effects);
  const auto retirement_plan = facman::self_maintenance::plan(
      retirement_failure);
  const fs::path retirement_operation = retirement_failure.coordinator_root /
      "maintenance" /
      (retirement_plan ? retirement_plan.value().operation_id : "invalid");
  ok &= require(!retirement_failed &&
                    retirement_failed.error().code ==
                        "self_maintenance_shortcut_backup_retirement_failed" &&
                    retirement_failure_effects.shortcut_calls == 1U &&
                    retirement_failure_effects.registration_calls == 1U &&
                    retirement_failure_effects.retire_calls == 1U &&
                    fs::is_regular_file(retirement_operation /
                                        "70-activation-recorded.v1.json") &&
                    !fs::exists(retirement_operation /
                                "80-shortcut-backup-retired.v1.json"),
                "post-activation backup retirement failure was not recoverable");
  retirement_failure_effects.fail_retire = false;
  auto retirement_recovered = facman::self_maintenance::execute(
      retirement_failure, retirement_failure_effects);
  ok &= require(retirement_recovered &&
                    retirement_failure_effects.shortcut_calls == 1U &&
                    retirement_failure_effects.registration_calls == 1U &&
                    retirement_failure_effects.retire_calls == 2U &&
                    fs::is_regular_file(retirement_operation /
                                        "80-shortcut-backup-retired.v1.json"),
                "backup retirement retry repeated cutover or failed to close");

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

  // An inserted epoch namespace must fence every flat mutation boundary,
  // including an insertion after the provider or first native effect.
  auto epoch_before = request(root / "flat-epoch-before", Operation::update);
  epoch_before.apply = true;
  fs::create_directories(epoch_before.coordinator_root / "epochs");
  FakeEffects epoch_before_effects;
  auto epoch_before_result = facman::self_maintenance::execute(
      epoch_before, epoch_before_effects);
  ok &= require(!epoch_before_result &&
                    epoch_before_result.error().code ==
                        "self_maintenance_epoch_recovery_required" &&
                    epoch_before_effects.prepare_calls == 0 &&
                    epoch_before_effects.install_calls == 0,
                "flat update crossed an existing epoch namespace");

  auto epoch_after_retention = request(root / "flat-epoch-after-retention",
                                       Operation::update);
  epoch_after_retention.apply = true;
  FakeEffects epoch_after_retention_effects;
  epoch_after_retention_effects.after_prepare = [&] {
    fs::create_directories(epoch_after_retention.coordinator_root / "epochs");
  };
  auto epoch_after_retention_result = facman::self_maintenance::execute(
      epoch_after_retention, epoch_after_retention_effects);
  ok &= require(!epoch_after_retention_result &&
                    epoch_after_retention_result.error().code ==
                        "self_maintenance_epoch_recovery_required" &&
                    epoch_after_retention_effects.prepare_calls == 1 &&
                    epoch_after_retention_effects.install_calls == 0,
                "flat provider apply crossed an inserted epoch namespace");

  auto epoch_after_provider = request(root / "flat-epoch-after-provider",
                                      Operation::update);
  epoch_after_provider.apply = true;
  FakeEffects epoch_after_provider_effects;
  epoch_after_provider_effects.after_install = [&] {
    fs::create_directories(epoch_after_provider.coordinator_root / "epochs");
  };
  auto epoch_after_provider_result = facman::self_maintenance::execute(
      epoch_after_provider, epoch_after_provider_effects);
  ok &= require(!epoch_after_provider_result &&
                    epoch_after_provider_result.error().code ==
                        "self_maintenance_epoch_recovery_required" &&
                    epoch_after_provider_effects.install_calls == 1 &&
                    epoch_after_provider_effects.shortcut_calls == 0,
                "flat shell cutover crossed an inserted epoch namespace");

  auto epoch_after_shortcut = request(root / "flat-epoch-after-shortcut",
                                      Operation::update);
  epoch_after_shortcut.apply = true;
  FakeEffects epoch_after_shortcut_effects;
  epoch_after_shortcut_effects.after_shortcut = [&] {
    fs::create_directories(epoch_after_shortcut.coordinator_root / "epochs");
  };
  auto epoch_after_shortcut_result = facman::self_maintenance::execute(
      epoch_after_shortcut, epoch_after_shortcut_effects);
  ok &= require(!epoch_after_shortcut_result &&
                    epoch_after_shortcut_result.error().code ==
                        "self_maintenance_epoch_recovery_required" &&
                    epoch_after_shortcut_effects.shortcut_calls == 1 &&
                    epoch_after_shortcut_effects.registration_calls == 0,
                "flat registration cutover crossed an inserted epoch namespace");

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
  const bool identity_refusal_had_no_effect = identity_effects.removed.empty();
  identity_effects.reject_identity = false;
  auto identity_retry = facman::self_maintenance::retire_active(
      identity_request, identity_effects);
  ok &= require(!identity_result &&
                    identity_result.error().code ==
                        "self_maintenance_retirement_recovery_required" &&
                    identity_refusal_had_no_effect &&
                    identity_retry && identity_retry.value().phase == "completed" &&
                    identity_effects.removed.size() == 1U,
                "retirement identity refusal entered an irreversible step");

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
                    genesis_apply.value().active.install_id == "facman.self.eg." +
                        sha("facman.self.epoch-generation-install.v1\n" +
                            genesis_epoch_id + "\n" + epoch_generation.generation_id +
                            "\n") &&
                    genesis_apply.value().active.install_id.size() == 79U &&
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
  ok &= require(!linked_update && !linked_downgrade,
                "non-genesis epoch activations without immutable maintenance history were accepted");

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
                       "epoch.prepare.one", fixture.inspection, false, {}, {}, true};
    fixture.request.continuation_helper = root / name / "current-setup.exe";
    std::ofstream(fixture.request.continuation_helper,
                  std::ios::binary | std::ios::trunc)
        << "current-protocol-capable-continuation-helper";
    fixture.request.continuation_helper_sha256 =
        sha(bytes(fixture.request.continuation_helper));
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
  preparation.request.deadline_utc_ms = 2000000000000ULL;
  auto preparation_apply = facman::self_maintenance::prepare_lifecycle_epoch_transition(
      preparation.request, preparation.effects);
  // A restarted public caller may propose a later budget. The immutable
  // handoff must keep the first deadline and the same journal identity.
  preparation.request.deadline_utc_ms = 2000000600000ULL;
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
  auto pending_handoff =
      facman::self_maintenance::discover_lifecycle_epoch_pending_transition(
          preparation.coordinator);
  ok &= require(preparation_preview && preparation_preview.value().phase == "plan" && !preview_wrote &&
                    !fabricated_package_refusal && preparation.effects.retain_calls == 1U &&
                    preparation_apply && preparation_retry &&
                    preparation_apply.value().journal_sha256 == preparation_retry.value().journal_sha256 &&
                    preparation_apply.value().nonce == preparation_retry.value().nonce &&
                    preparation_apply.value().deadline_utc_ms == 2000000000000ULL &&
                    preparation_retry.value().deadline_utc_ms == 2000000000000ULL &&
                    !ordinary_during_handoff && exact_handoff &&
                    exact_handoff.value().package == preparation_apply.value().inputs.package &&
                    !wrong_handoff_nonce && !wrong_handoff_digest &&
                    pending_handoff && pending_handoff.value() &&
                    pending_handoff.value()->phase == "continuation_pending" &&
                    pending_handoff.value()->operation_id == "epoch.prepare.one" &&
                    pending_handoff.value()->target.generation_id ==
                        preparation_apply.value().transition.target.generation_id &&
                    pending_handoff.value()->nonce == preparation_apply.value().nonce &&
                    pending_handoff.value()->journal_sha256 == preparation_apply.value().journal_sha256 &&
                    pending_handoff.value()->deadline_utc_ms == 2000000000000ULL &&
                    pending_handoff.value()->retained_package.package_sha256 ==
                        preparation.inspection.package_sha256 &&
                    pending_handoff.value()->retained_package.maintenance_launcher_sha256 ==
                        preparation.inspection.maintenance_launcher_sha256 &&
                    pending_handoff.value()->retained_inputs.package ==
                        preparation_apply.value().inputs.package &&
                    pending_handoff.value()->retained_inputs.package_sha256 ==
                        preparation_apply.value().inputs.package_sha256 &&
                    pending_handoff.value()->retained_inputs.helper ==
                        preparation_apply.value().inputs.helper &&
                    pending_handoff.value()->retained_inputs.helper_sha256 ==
                        preparation_apply.value().inputs.helper_sha256 &&
                    pending_handoff.value()->retained_inputs.helper_sha256 ==
                        preparation.request.continuation_helper_sha256 &&
                    pending_handoff.value()->retained_inputs.helper_sha256 !=
                        preparation.inspection.maintenance_launcher_sha256 &&
                    pending_handoff.value()->shell_integration &&
                    pending_handoff.value()->retained_package.descriptor.package_layout ==
                        preparation.inspection.descriptor.package_layout &&
                    ordinary_during_handoff.error().code ==
                        "self_maintenance_epoch_recovery_required",
                "epoch preparation preview, exact handoff, and recovery boundary were not exact");
  auto no_shell_preparation = make_preparation_fixture(
      "epoch-transition-no-shell-binding");
  no_shell_preparation.request.apply = true;
  no_shell_preparation.request.shell_integration = false;
  auto no_shell_prepared = facman::self_maintenance::prepare_lifecycle_epoch_transition(
      no_shell_preparation.request, no_shell_preparation.effects);
  auto no_shell_pending =
      facman::self_maintenance::discover_lifecycle_epoch_pending_transition(
          no_shell_preparation.coordinator);
  no_shell_preparation.request.shell_integration = true;
  auto changed_shell_retry =
      facman::self_maintenance::prepare_lifecycle_epoch_transition(
          no_shell_preparation.request, no_shell_preparation.effects);
  ok &= require(no_shell_prepared && no_shell_pending &&
                    no_shell_pending.value().has_value() &&
                    !no_shell_pending.value()->shell_integration &&
                    !changed_shell_retry,
                "epoch handoff did not bind the exact shell integration choice");

  // Pending discovery must retain the unfinished operation's exact name set,
  // not merely the records that were present when the scan began.
  auto pending_name_insertion = prepare_fresh_epoch_fixture(
      "epoch-pending-name-insertion");
  const fs::path pending_name_operation =
      pending_name_insertion.handoff.journal.parent_path();
  const fs::path pending_foreign_record =
      pending_name_operation / "01-foreign.v2.json";
  epoch_hook_watch = pending_name_insertion.handoff.journal;
  epoch_hook_mutation = pending_foreign_record;
  epoch_hook_bytes = "{}\n";
  epoch_hook_called = false;
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(
      mutate_epoch_record_after_pin);
  auto pending_name_mutation =
      facman::self_maintenance::discover_lifecycle_epoch_pending_transition(
          pending_name_insertion.coordinator);
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(nullptr);
  const bool pending_foreign_inserted = fs::exists(pending_foreign_record);
  std::error_code pending_name_cleanup_error;
  fs::remove(pending_foreign_record, pending_name_cleanup_error);
  ok &= require(epoch_hook_called && pending_foreign_inserted &&
                    !pending_name_mutation,
                "pending discovery accepted a record name inserted during an unfinished operation scan");

  auto wrong_source_handoff = prepare_fresh_epoch_fixture(
      "epoch-pending-wrong-source");
  const std::string wrong_source_bytes = canonical_handoff_with_field(
      bytes(wrong_source_handoff.handoff.journal), "source_generation_id",
      std::string(64, 'f'));
  replace_file(wrong_source_handoff.handoff.journal, wrong_source_bytes);
  auto wrong_source_pending =
      facman::self_maintenance::discover_lifecycle_epoch_pending_transition(
          wrong_source_handoff.coordinator);
  ok &= require(!wrong_source_pending,
                "pending discovery accepted a canonical handoff for the wrong source generation");

  // The lifecycle-tail read happens after the first exact operation snapshot.
  // Mutating the operation from a later activation pin must still be caught by
  // the final repeated custody check.
  auto late_name_insertion = prepare_fresh_epoch_fixture(
      "epoch-pending-late-name-insertion");
  const fs::path late_operation = late_name_insertion.handoff.journal.parent_path();
  const fs::path late_foreign_record = late_operation / "01-late-foreign.v2.json";
  epoch_hook_watch = late_name_insertion.coordinator / "epochs" /
      late_name_insertion.epoch.epoch_id / "activations" /
      genesis_activation_name;
  epoch_hook_mutation = late_foreign_record;
  epoch_hook_bytes = "{}\n";
  epoch_hook_called = false;
  epoch_hook_matching_calls = 0U;
  epoch_hook_trigger_call = 2U;
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(
      mutate_epoch_record_after_nth_matching_pin);
  auto late_name_mutation =
      facman::self_maintenance::discover_lifecycle_epoch_pending_transition(
          late_name_insertion.coordinator);
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(nullptr);
  const bool late_foreign_inserted = fs::exists(late_foreign_record);
  pending_name_cleanup_error.clear();
  fs::remove(late_foreign_record, pending_name_cleanup_error);
  ok &= require(epoch_hook_called && epoch_hook_matching_calls >= 2U &&
                    late_foreign_inserted && !late_name_mutation,
                "pending discovery accepted a record inserted during final tail discovery");

  auto phase_ten_restart = prepare_fresh_epoch_fixture(
      "epoch-provider-phase-ten-restart");
  EpochContinuationFakeEffects phase_ten_effects;
  phase_ten_effects.refuse_prepare = true;
  facman::self_maintenance::EpochContinuationRequest phase_ten_request{
      phase_ten_restart.coordinator, "epoch.prepare.one",
      phase_ten_restart.handoff.nonce,
      phase_ten_restart.handoff.journal_sha256, true};
  auto phase_ten_interrupted =
      facman::self_maintenance::execute_lifecycle_epoch_continuation(
          phase_ten_request, phase_ten_effects);
  std::error_code phase_ten_remove_error;
  fs::remove(phase_ten_restart.source_package, phase_ten_remove_error);
  auto phase_ten_pending =
      facman::self_maintenance::discover_lifecycle_epoch_pending_transition(
          phase_ten_restart.coordinator);
  EpochContinuationFakeEffects phase_ten_restarted_effects;
  auto phase_ten_recovered =
      facman::self_maintenance::execute_lifecycle_epoch_continuation(
          phase_ten_request, phase_ten_restarted_effects);
  ok &= require(!phase_ten_interrupted && !phase_ten_remove_error &&
                    phase_ten_effects.bind_calls == 1U &&
                    phase_ten_effects.prepare_calls == 1U &&
                    phase_ten_effects.apply_calls == 0U &&
                    phase_ten_pending && phase_ten_pending.value() &&
                    phase_ten_pending.value()->phase == "continuation_pending" &&
                    phase_ten_pending.value()->retained_inputs.helper ==
                        phase_ten_restart.handoff.inputs.helper &&
                    phase_ten_pending.value()->retained_inputs.helper_sha256 ==
                        phase_ten_restart.handoff.inputs.helper_sha256 &&
                    phase_ten_recovered &&
                    phase_ten_restarted_effects.bind_calls == 0U &&
                    phase_ten_restarted_effects.prepare_calls == 1U &&
                    phase_ten_restarted_effects.apply_calls == 1U,
                "phase-10 restart did not recover from retained package and helper authority");

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
  auto pending_provider =
      facman::self_maintenance::discover_lifecycle_epoch_pending_transition(
          provider_continuation.coordinator);
  auto corrupt_pending_fixture = prepare_fresh_epoch_fixture("epoch-pending-corrupt-continuation");
  const fs::path corrupt_pending_record = corrupt_pending_fixture.coordinator / "epochs" /
      corrupt_pending_fixture.epoch.epoch_id / "maintenance" / "epoch.prepare.one" /
      "10-provider-apply-bound.v2.json";
  std::ofstream(corrupt_pending_record, std::ios::binary | std::ios::trunc) << "{}\n";
  auto corrupt_pending_discovery = facman::self_maintenance::discover_lifecycle_epoch_pending_transition(
      corrupt_pending_fixture.coordinator);
  ok &= require(!corrupt_pending_discovery,
                "read-only epoch pending discovery accepted corrupt continuation bytes");

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

  EpochPublicationFakeEffects publication_effects;
  facman::self_maintenance::EpochPublicationRequest publication_request{
      provider_continuation.coordinator, "epoch.prepare.one",
      provider_continuation.handoff.nonce, provider_continuation.handoff.journal_sha256, false};
  auto publication_preview = facman::self_maintenance::execute_lifecycle_epoch_publication(
      publication_request, publication_effects);
  const bool publication_preview_pure = publication_effects.inspect_calls == 0U &&
      publication_effects.terminal_calls == 0U &&
      !fs::exists(provider_operation / "50-generation-published.v2.json") &&
      !fs::exists(provider_operation / "60-activation-published.v2.json");
  publication_request.apply = true;
  auto publication_completed = facman::self_maintenance::execute_lifecycle_epoch_publication(
      publication_request, publication_effects);
  EpochPublicationFakeEffects publication_restarted_effects;
  auto publication_restarted = facman::self_maintenance::execute_lifecycle_epoch_publication(
      publication_request, publication_restarted_effects);
  auto pending_publication =
      facman::self_maintenance::discover_lifecycle_epoch_pending_transition(
          provider_continuation.coordinator);
  const fs::path publication_epoch = provider_continuation.coordinator / "epochs" /
      provider_continuation.epoch.epoch_id;
  const auto &publication_target = provider_completed ? provider_completed.value().transition.target
                                                       : Generation{};
  ok &= require(publication_preview && publication_preview.value().phase == "plan" &&
                    publication_preview_pure &&
                    publication_completed &&
                    publication_completed.value().phase == "epoch_activated" &&
                    publication_restarted &&
                    publication_restarted.value().phase == "epoch_activated" &&
                    fs::exists(publication_epoch / "generations" /
                        ("generation." + publication_target.generation_id + ".v2.json")) &&
                    fs::exists(publication_epoch / "activations" /
                        "activation.epoch.prepare.one.v2.json") &&
                    fs::exists(provider_operation / "50-generation-published.v2.json") &&
                    fs::exists(provider_operation / "60-activation-published.v2.json") &&
                    publication_effects.inspect_calls == 1U &&
                    publication_effects.terminal_calls == 1U &&
                    publication_restarted_effects.inspect_calls == 1U &&
                    publication_restarted_effects.terminal_calls == 1U &&
                    pending_provider && pending_provider.value() &&
                    pending_provider.value()->phase == "publication_pending" &&
                    pending_provider.value()->operation_id == "epoch.prepare.one" &&
                    pending_provider.value()->target.generation_id == publication_target.generation_id &&
                    pending_publication && pending_publication.value() &&
                    pending_publication.value()->phase == "shell_cutover_pending" &&
                    pending_publication.value()->target.generation_id == publication_target.generation_id,
                "epoch publication was not preview-pure, durable, or restart-idempotent");
  EpochShellCutoverFakeEffects shell_preview_effects;
  facman::self_maintenance::EpochShellCutoverRequest shell_request{
      provider_continuation.coordinator, "epoch.prepare.one",
      provider_continuation.handoff.nonce, provider_continuation.handoff.journal_sha256, false};
  auto shell_preview = facman::self_maintenance::execute_lifecycle_epoch_shell_cutover(
      shell_request, shell_preview_effects);
  const bool shell_preview_pure = shell_preview_effects.terminal_calls == 0U &&
      shell_preview_effects.shortcut_calls == 0U && shell_preview_effects.registration_calls == 0U &&
      !fs::exists(provider_operation / "70-shortcut-cutover.v2.json") &&
      !fs::exists(provider_operation / "80-registration-cutover.v2.json");
  shell_request.apply = true;
  EpochShellCutoverFakeEffects shell_effects;
  auto shell_completed = facman::self_maintenance::execute_lifecycle_epoch_shell_cutover(
      shell_request, shell_effects);
  auto shell_restarted = facman::self_maintenance::execute_lifecycle_epoch_shell_cutover(
      shell_request, shell_effects);
  auto ordinary_after_shell = facman::self_maintenance::discover_lifecycle_epoch_active(
      provider_continuation.coordinator);
  auto pending_after_shell =
      facman::self_maintenance::discover_lifecycle_epoch_terminal_transition(
          provider_continuation.coordinator);
  ok &= require(shell_preview && shell_preview.value().phase == "shortcut_pending" &&
                    shell_preview_pure && shell_completed && shell_restarted &&
                    shell_completed.value().phase == "shell_cutover_complete" &&
                    shell_restarted.value().phase == "shell_cutover_complete" &&
                    fs::exists(provider_operation / "70-shortcut-cutover.v2.json") &&
                    fs::exists(provider_operation / "80-registration-cutover.v2.json") &&
                    shell_effects.shortcut_calls == 1U &&
                    shell_effects.registration_calls == 1U &&
                    shell_effects.retire_calls == 2U,
                "epoch shell cutover was not preview-pure, durable, or idempotent");
  ok &= require(ordinary_after_shell &&
                    ordinary_after_shell.value().active.active.generation_id ==
                        publication_target.generation_id && pending_after_shell &&
                    pending_after_shell.value() &&
                    pending_after_shell.value()->completed &&
                    pending_after_shell.value()->phase == "shell_cutover_complete" &&
                    pending_after_shell.value()->operation_id == "epoch.prepare.one",
                "completed epoch shell cutover did not restore ordinary active discovery");

  const fs::path completed_maintenance = publication_epoch / "maintenance";
  const fs::path moved_completed_maintenance = publication_epoch / "maintenance.moved";
  std::error_code maintenance_history_error;
  fs::rename(completed_maintenance, moved_completed_maintenance, maintenance_history_error);
  auto missing_maintenance_history = maintenance_history_error
      ? facman::core::Result<facman::self_maintenance::EpochActiveState>::failure(
            {"test_rename_failed", maintenance_history_error.message(), {}})
      : facman::self_maintenance::discover_lifecycle_epoch_active(
            provider_continuation.coordinator);
  if (!maintenance_history_error) {
    maintenance_history_error.clear();
    fs::rename(moved_completed_maintenance, completed_maintenance, maintenance_history_error);
  }
  ok &= require(!maintenance_history_error && !missing_maintenance_history,
                "non-genesis epoch activation was accepted after maintenance history deletion");

  const fs::path eighty_final = provider_operation /
      "80-registration-cutover.v2.json";
  const fs::path eighty_staging = provider_operation /
      "80-registration-cutover.staging.v2.json";

  const Generation unauthorized_tail = make_epoch_update_generation(
      provider_continuation.epoch, "9.8.9", 'f');
  const std::string publication_activation_name =
      "activation.epoch.prepare.one.v2.json";
  const std::string publication_activation_sha = sha(bytes(
      publication_epoch / "activations" / publication_activation_name));
  write_epoch_link(provider_continuation.coordinator, provider_continuation.epoch,
      "update", "epoch.update.unauthorized", publication_target, unauthorized_tail,
      publication_activation_name, publication_activation_sha);
  auto unauthorized_tail_discovery =
      facman::self_maintenance::discover_lifecycle_epoch_active(
          provider_continuation.coordinator);
  std::error_code shell_negative_cleanup_error;
  fs::remove(publication_epoch / "activations" /
      "activation.epoch.update.unauthorized.v2.json", shell_negative_cleanup_error);
  shell_negative_cleanup_error.clear();
  fs::remove(publication_epoch / "generations" /
      ("generation." + unauthorized_tail.generation_id + ".v2.json"),
      shell_negative_cleanup_error);
  ok &= require(!unauthorized_tail_discovery,
                "ordinary discovery accepted an activation beyond the completed shell target");

  epoch_hook_watch = publication_epoch / "activations" /
      genesis_activation_name;
  epoch_hook_mutation = eighty_final;
  epoch_hook_bytes = "{}\n";
  epoch_hook_called = false;
  epoch_hook_mutated = false;
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(
      replace_epoch_record_after_pin);
  auto shell_record_substitution =
      facman::self_maintenance::discover_lifecycle_epoch_active(
          provider_continuation.coordinator);
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(nullptr);
  const bool shell_record_substitution_safe = epoch_hook_called &&
      equal_size_mutation_refused_or_denied(
          epoch_hook_mutated, static_cast<bool>(shell_record_substitution));
  const fs::path eighty_moved = provider_operation /
      "80-registration-cutover.v2.json.hook-moved";
  if (fs::exists(eighty_moved)) {
    shell_negative_cleanup_error.clear();
    fs::remove(eighty_final, shell_negative_cleanup_error);
    shell_negative_cleanup_error.clear();
    fs::rename(eighty_moved, eighty_final, shell_negative_cleanup_error);
  }
  ok &= require(shell_record_substitution_safe,
                "ordinary discovery accepted substituted shell custody during activation scan");

  const fs::path foreign_operation_record = provider_operation / "90-foreign.v2.json";
  epoch_hook_watch = provider_operation / "00-handoff-ready.v3.json";
  epoch_hook_mutation = foreign_operation_record;
  epoch_hook_bytes = "{}\n";
  epoch_hook_called = false;
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(
      mutate_epoch_record_after_pin);
  auto foreign_operation_discovery =
      facman::self_maintenance::discover_lifecycle_epoch_active(
          provider_continuation.coordinator);
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(nullptr);
  const bool foreign_operation_inserted = fs::exists(foreign_operation_record);
  shell_negative_cleanup_error.clear();
  fs::remove(foreign_operation_record, shell_negative_cleanup_error);
  ok &= require(epoch_hook_called && foreign_operation_inserted &&
                    !foreign_operation_discovery,
                "ordinary discovery accepted an operation record inserted during closure validation");

  std::error_code shell_staging_rename_error;
  fs::rename(eighty_final, eighty_staging, shell_staging_rename_error);
  EpochShellCutoverFakeEffects shell_staging_effects;
  shell_staging_effects.shortcut = ShellState::new_exact;
  shell_staging_effects.registration = ShellState::new_exact;
  auto shell_staging_recovered = shell_staging_rename_error
      ? facman::core::Result<facman::self_maintenance::EpochShellCutoverResponse>::failure(
            {"test_rename_failed", shell_staging_rename_error.message(), {}})
      : facman::self_maintenance::execute_lifecycle_epoch_shell_cutover(
            shell_request, shell_staging_effects);
  ok &= require(shell_staging_recovered && fs::exists(eighty_final) &&
                    !fs::exists(eighty_staging) &&
                    shell_staging_effects.terminal_calls == 1U &&
                    shell_staging_effects.shortcut_calls == 0U &&
                    shell_staging_effects.registration_calls == 0U,
                "canonical terminal shell staging was not promoted without effect replay");

  bool shell_boundary_recovered = true;
  for (unsigned phase = 1U; phase <= 2U; ++phase) {
    auto staged = prepare_fresh_epoch_fixture(
        "epoch-shell-staging-" + std::to_string(phase));
    EpochContinuationFakeEffects continuation_effects;
    facman::self_maintenance::EpochContinuationRequest staged_continuation_request{
        staged.coordinator, "epoch.prepare.one", staged.handoff.nonce,
        staged.handoff.journal_sha256, true};
    auto continued = facman::self_maintenance::execute_lifecycle_epoch_continuation(
        staged_continuation_request, continuation_effects);
    EpochPublicationFakeEffects publication_effects_for_shell;
    facman::self_maintenance::EpochPublicationRequest staged_publication_request{
        staged.coordinator, "epoch.prepare.one", staged.handoff.nonce,
        staged.handoff.journal_sha256, true};
    auto published = facman::self_maintenance::execute_lifecycle_epoch_publication(
        staged_publication_request, publication_effects_for_shell);
    EpochShellCutoverFakeEffects staged_shell_effects;
    facman::self_maintenance::EpochShellCutoverRequest staged_shell_request{
        staged.coordinator, "epoch.prepare.one", staged.handoff.nonce,
        staged.handoff.journal_sha256, true};
    facman::platform::testing::set_relative_publish_pre_rename_fault_countdown(phase);
    auto shell_interrupted = facman::self_maintenance::execute_lifecycle_epoch_shell_cutover(
        staged_shell_request, staged_shell_effects);
    facman::platform::testing::set_relative_publish_pre_rename_fault_countdown(0U);
    auto pending_shell =
        facman::self_maintenance::discover_lifecycle_epoch_pending_transition(
            staged.coordinator);
    auto shell_recovered = facman::self_maintenance::execute_lifecycle_epoch_shell_cutover(
        staged_shell_request, staged_shell_effects);
    const fs::path operation = staged.coordinator / "epochs" /
        staged.epoch.epoch_id / "maintenance" / "epoch.prepare.one";
    const bool phase_recovered = continued && published && !shell_interrupted &&
        shell_recovered && shell_recovered.value().phase == "shell_cutover_complete" &&
        fs::exists(operation / "70-shortcut-cutover.v2.json") &&
        fs::exists(operation / "80-registration-cutover.v2.json") &&
        !fs::exists(operation / "70-shortcut-cutover.staging.v2.json") &&
        !fs::exists(operation / "80-registration-cutover.staging.v2.json") &&
        pending_shell && pending_shell.value() &&
        pending_shell.value()->phase == "shell_cutover_pending" &&
        staged_shell_effects.shortcut_calls == 1U &&
        staged_shell_effects.registration_calls == 1U &&
        staged_shell_effects.terminal_calls == 2U;
    if (!phase_recovered) {
      std::cerr << "epoch shell recovery phase " << phase << " failed";
      if (shell_interrupted) std::cerr << ": injected fault did not interrupt";
      if (!shell_recovered)
        std::cerr << ": recovery=" << shell_recovered.error().code << " "
                  << shell_recovered.error().message;
      if (!pending_shell)
        std::cerr << ": pending=" << pending_shell.error().code << " "
                  << pending_shell.error().message;
      else if (!pending_shell.value())
        std::cerr << ": pending=none";
      else
        std::cerr << ": pending_phase=" << pending_shell.value()->phase;
      std::cerr << ": calls=" << staged_shell_effects.shortcut_calls << ","
                << staged_shell_effects.registration_calls << ","
                << staged_shell_effects.terminal_calls;
      std::cerr << '\n';
    }
    shell_boundary_recovered = shell_boundary_recovered && phase_recovered;
  }
  ok &= require(shell_boundary_recovered,
                "each durable epoch shell boundary was not recovered exactly");

  // A completed 80 record remains immutable history.  It admits an exact
  // phase-80 retry above, but a distinct package must be able to start the
  // next tail from the newly active generation without deleting that history.
  const fs::path second_package = epoch_package(root / "epoch-provider-continuation-second",
                                                 "9.8.9", preparation_helper);
  auto second_inspection = facman::self_maintenance::inspect_package(second_package);
  EpochPreparationFakeEffects second_preparation_effects;
  second_preparation_effects.state_root = provider_continuation.epoch.state_root;
  second_preparation_effects.helper_bytes = preparation_helper;
  facman::self_maintenance::EpochTransitionRequest second_preparation_request{
      provider_continuation.coordinator, provider_continuation.epoch.epoch_id,
      Operation::update, "epoch.prepare.two",
      second_inspection ? second_inspection.value() : facman::self_maintenance::PackageInspection{},
      true, {}, {}, true};
  second_preparation_request.continuation_helper =
      provider_continuation.request.continuation_helper;
  second_preparation_request.continuation_helper_sha256 =
      provider_continuation.request.continuation_helper_sha256;
  auto second_prepared = second_inspection
      ? facman::self_maintenance::prepare_lifecycle_epoch_transition(
            second_preparation_request, second_preparation_effects)
      : facman::core::Result<facman::self_maintenance::EpochTransitionPreparation>::failure(
            second_inspection.error());
  EpochContinuationFakeEffects second_continuation_effects;
  auto second_continued = second_prepared
      ? facman::self_maintenance::execute_lifecycle_epoch_continuation(
            {provider_continuation.coordinator, "epoch.prepare.two", second_prepared.value().nonce,
             second_prepared.value().journal_sha256, true}, second_continuation_effects)
      : facman::core::Result<facman::self_maintenance::EpochContinuationResponse>::failure(
            second_prepared.error());
  EpochPublicationFakeEffects second_publication_effects;
  auto second_published = second_prepared
      ? facman::self_maintenance::execute_lifecycle_epoch_publication(
            {provider_continuation.coordinator, "epoch.prepare.two", second_prepared.value().nonce,
             second_prepared.value().journal_sha256, true}, second_publication_effects)
      : facman::core::Result<facman::self_maintenance::EpochPublicationResponse>::failure(
            second_prepared.error());
  EpochShellCutoverFakeEffects second_shell_effects;
  auto second_shell = second_prepared
      ? facman::self_maintenance::execute_lifecycle_epoch_shell_cutover(
            {provider_continuation.coordinator, "epoch.prepare.two", second_prepared.value().nonce,
             second_prepared.value().journal_sha256, true}, second_shell_effects)
      : facman::core::Result<facman::self_maintenance::EpochShellCutoverResponse>::failure(
            second_prepared.error());
  auto second_active = facman::self_maintenance::discover_lifecycle_epoch_active(
      provider_continuation.coordinator);
  auto second_completion = facman::self_maintenance::discover_lifecycle_epoch_terminal_transition(
      provider_continuation.coordinator);
  ok &= require(second_inspection && second_prepared && second_continued && second_published &&
                    second_shell && second_active && second_completion && second_completion.value() &&
                    second_active.value().active.active.generation_id ==
                        second_shell.value().generation.generation_id &&
                    second_completion.value()->completed &&
                    second_completion.value()->operation_id == "epoch.prepare.two" &&
                    second_continuation_effects.apply_calls == 1U &&
                    fs::exists(provider_operation / "80-registration-cutover.v2.json"),
                "completed epoch history did not permit one exact successive transition");

  // Reactivate the first target generation through a new downgrade activation.
  // Terminal discovery must select the newest operation while retaining both
  // prior completions as immutable history.
  EpochPreparationFakeEffects third_preparation_effects;
  third_preparation_effects.state_root = provider_continuation.epoch.state_root;
  third_preparation_effects.helper_bytes = preparation_helper;
  facman::self_maintenance::EpochTransitionRequest third_preparation_request{
      provider_continuation.coordinator, provider_continuation.epoch.epoch_id,
      Operation::downgrade, "epoch.prepare.three",
      provider_continuation.inspection, true, {}, {}, true};
  third_preparation_request.continuation_helper =
      provider_continuation.request.continuation_helper;
  third_preparation_request.continuation_helper_sha256 =
      provider_continuation.request.continuation_helper_sha256;
  auto third_prepared = facman::self_maintenance::prepare_lifecycle_epoch_transition(
      third_preparation_request, third_preparation_effects);
  EpochContinuationFakeEffects third_continuation_effects;
  auto third_continued = third_prepared
      ? facman::self_maintenance::execute_lifecycle_epoch_continuation(
            {provider_continuation.coordinator, "epoch.prepare.three",
             third_prepared.value().nonce, third_prepared.value().journal_sha256, true},
            third_continuation_effects)
      : facman::core::Result<facman::self_maintenance::EpochContinuationResponse>::failure(
            third_prepared.error());
  EpochPublicationFakeEffects third_publication_effects;
  auto third_published = third_prepared
      ? facman::self_maintenance::execute_lifecycle_epoch_publication(
            {provider_continuation.coordinator, "epoch.prepare.three",
             third_prepared.value().nonce, third_prepared.value().journal_sha256, true},
            third_publication_effects)
      : facman::core::Result<facman::self_maintenance::EpochPublicationResponse>::failure(
            third_prepared.error());
  EpochShellCutoverFakeEffects third_shell_effects;
  auto third_shell = third_prepared
      ? facman::self_maintenance::execute_lifecycle_epoch_shell_cutover(
            {provider_continuation.coordinator, "epoch.prepare.three",
             third_prepared.value().nonce, third_prepared.value().journal_sha256, true},
            third_shell_effects)
      : facman::core::Result<facman::self_maintenance::EpochShellCutoverResponse>::failure(
            third_prepared.error());
  auto third_active = facman::self_maintenance::discover_lifecycle_epoch_active(
      provider_continuation.coordinator);
  auto third_lineage =
      facman::self_maintenance::discover_lifecycle_epoch_activation_chain(
          provider_continuation.coordinator);
  auto third_completion =
      facman::self_maintenance::discover_lifecycle_epoch_terminal_transition(
          provider_continuation.coordinator);
  ok &= require(third_prepared && third_continued && third_published && third_shell &&
                    third_active && third_completion && third_completion.value() &&
                    third_lineage && third_lineage.value().generations.size() == 4U &&
                    third_lineage.value().generations[1].generation_id ==
                        third_lineage.value().generations[3].generation_id &&
                    third_lineage.value().generations[1].generation_id !=
                        third_lineage.value().generations[2].generation_id &&
                    provider_completed &&
                    third_shell.value().generation.generation_id ==
                        provider_completed.value().transition.target.generation_id &&
                    third_active.value().active.active.generation_id ==
                        provider_completed.value().transition.target.generation_id &&
                    third_active.value().active.activation_name ==
                        "activation.epoch.prepare.three.v2.json" &&
                    third_completion.value()->operation_id == "epoch.prepare.three" &&
                    third_completion.value()->completed,
                "downgrade did not reactivate prior generation with the newest exact terminal history");


  bool publication_staging_recovered = true;
  for (unsigned phase = 1U; phase <= 4U; ++phase) {
    auto staged = prepare_fresh_epoch_fixture(
        "epoch-publication-staging-" + std::to_string(phase));
    EpochContinuationFakeEffects continuation_effects;
    facman::self_maintenance::EpochContinuationRequest staged_continuation_request{
        staged.coordinator, "epoch.prepare.one", staged.handoff.nonce,
        staged.handoff.journal_sha256, true};
    auto continued = facman::self_maintenance::execute_lifecycle_epoch_continuation(
        staged_continuation_request, continuation_effects);
    EpochPublicationFakeEffects publication_interrupted_effects;
    facman::self_maintenance::EpochPublicationRequest staged_publication_request{
        staged.coordinator, "epoch.prepare.one", staged.handoff.nonce,
        staged.handoff.journal_sha256, true};
    facman::platform::testing::set_relative_publish_pre_rename_fault_countdown(phase);
    auto publication_interrupted = facman::self_maintenance::execute_lifecycle_epoch_publication(
        staged_publication_request, publication_interrupted_effects);
    facman::platform::testing::set_relative_publish_pre_rename_fault_countdown(0U);
    auto pending_publication_staging =
        facman::self_maintenance::discover_lifecycle_epoch_pending_transition(
            staged.coordinator);
    EpochPublicationFakeEffects recovered_effects;
    auto publication_recovered = facman::self_maintenance::execute_lifecycle_epoch_publication(
        staged_publication_request, recovered_effects);
    const fs::path staged_epoch = staged.coordinator / "epochs" /
        staged.epoch.epoch_id;
    const fs::path staged_operation = staged_epoch / "maintenance" /
        "epoch.prepare.one";
    const bool phase_recovered = continued &&
        !publication_interrupted && publication_recovered &&
        publication_recovered.value().phase == "epoch_activated" &&
        fs::exists(staged_epoch / "generations" /
            ("generation." + publication_recovered.value().generation.generation_id +
             ".v2.json")) &&
        fs::exists(staged_epoch / "activations" /
            "activation.epoch.prepare.one.v2.json") &&
        fs::exists(staged_operation / "50-generation-published.v2.json") &&
        fs::exists(staged_operation / "60-activation-published.v2.json") &&
        pending_publication_staging && pending_publication_staging.value() &&
        pending_publication_staging.value()->phase == "publication_pending" &&
        publication_interrupted_effects.inspect_calls == 1U &&
        publication_interrupted_effects.terminal_calls == 1U &&
        recovered_effects.inspect_calls == 1U &&
        recovered_effects.terminal_calls == 1U;
    if (!phase_recovered) {
      std::cerr << "epoch publication recovery phase " << phase << " failed";
      if (publication_interrupted)
        std::cerr << ": injected fault did not interrupt";
      if (!publication_recovered)
        std::cerr << ": recovery=" << publication_recovered.error().code << " "
                  << publication_recovered.error().message;
      if (!pending_publication_staging)
        std::cerr << ": pending=" << pending_publication_staging.error().code << " "
                  << pending_publication_staging.error().message;
      else if (!pending_publication_staging.value())
        std::cerr << ": pending=none";
      else
        std::cerr << ": pending_phase=" << pending_publication_staging.value()->phase;
      std::cerr << ": calls=" << publication_interrupted_effects.inspect_calls << ","
                << publication_interrupted_effects.terminal_calls << ";"
                << recovered_effects.inspect_calls << ","
                << recovered_effects.terminal_calls;
      std::cerr << '\n';
    }
    publication_staging_recovered = publication_staging_recovered && phase_recovered;
  }
  ok &= require(publication_staging_recovered,
                "each durable epoch publication boundary was not recovered exactly");

  auto malformed_publication = prepare_fresh_epoch_fixture(
      "epoch-publication-malformed-phase-30");
  EpochContinuationFakeEffects malformed_continuation_effects;
  facman::self_maintenance::EpochContinuationRequest malformed_continuation_request{
      malformed_publication.coordinator, "epoch.prepare.one",
      malformed_publication.handoff.nonce,
      malformed_publication.handoff.journal_sha256, true};
  auto malformed_continued = facman::self_maintenance::execute_lifecycle_epoch_continuation(
      malformed_continuation_request, malformed_continuation_effects);
  const fs::path malformed_operation = malformed_publication.coordinator / "epochs" /
      malformed_publication.epoch.epoch_id / "maintenance" / "epoch.prepare.one";
  const fs::path malformed_outcome = malformed_operation / "30-provider-outcome.v2.json";
  std::string malformed_outcome_bytes = bytes(malformed_outcome);
  const std::string installed_field = "\"outcome\":\"installed\"";
  const auto installed_position = malformed_outcome_bytes.find(installed_field);
  if (installed_position != std::string::npos)
    malformed_outcome_bytes.replace(installed_position, installed_field.size(),
                                    "\"outcome\":\"failed\"");
  replace_file(malformed_outcome, malformed_outcome_bytes);
  EpochPublicationFakeEffects malformed_publication_effects;
  facman::self_maintenance::EpochPublicationRequest malformed_request{
      malformed_publication.coordinator, "epoch.prepare.one",
      malformed_publication.handoff.nonce,
      malformed_publication.handoff.journal_sha256, true};
  auto malformed_publication_result =
      facman::self_maintenance::execute_lifecycle_epoch_publication(
          malformed_request, malformed_publication_effects);
  ok &= require(malformed_continued && installed_position != std::string::npos &&
                    !malformed_publication_result &&
                    malformed_publication_effects.inspect_calls == 0U &&
                    malformed_publication_effects.terminal_calls == 0U &&
                    !fs::exists(malformed_operation / "50-generation-published.v2.json"),
                "foreign provider outcome entered epoch publication");

  auto substituted_receipt_publication = prepare_fresh_epoch_fixture(
      "epoch-publication-substituted-phase-30-receipt");
  EpochContinuationFakeEffects substituted_receipt_continuation_effects;
  facman::self_maintenance::EpochContinuationRequest
      substituted_receipt_continuation_request{
          substituted_receipt_publication.coordinator, "epoch.prepare.one",
          substituted_receipt_publication.handoff.nonce,
          substituted_receipt_publication.handoff.journal_sha256, true};
  auto substituted_receipt_continued =
      facman::self_maintenance::execute_lifecycle_epoch_continuation(
          substituted_receipt_continuation_request,
          substituted_receipt_continuation_effects);
  const fs::path substituted_receipt_operation =
      substituted_receipt_publication.coordinator / "epochs" /
      substituted_receipt_publication.epoch.epoch_id / "maintenance" /
      "epoch.prepare.one";
  const fs::path substituted_receipt_outcome = substituted_receipt_operation /
      "30-provider-outcome.v2.json";
  std::string substituted_receipt_bytes = bytes(substituted_receipt_outcome);
  const std::string exact_receipt_field =
      "\"receipt_sha256\":\"" + sha("epoch.inspect") + "\"";
  const std::string wrong_receipt_field =
      "\"receipt_sha256\":\"" + sha("foreign-epoch.inspect") + "\"";
  const auto receipt_position = substituted_receipt_bytes.find(
      exact_receipt_field);
  if (receipt_position != std::string::npos)
    substituted_receipt_bytes.replace(receipt_position,
        exact_receipt_field.size(), wrong_receipt_field);
  replace_file(substituted_receipt_outcome, substituted_receipt_bytes);
  EpochPublicationFakeEffects substituted_receipt_effects;
  facman::self_maintenance::EpochPublicationRequest substituted_receipt_request{
      substituted_receipt_publication.coordinator, "epoch.prepare.one",
      substituted_receipt_publication.handoff.nonce,
      substituted_receipt_publication.handoff.journal_sha256, true};
  auto substituted_receipt_result =
      facman::self_maintenance::execute_lifecycle_epoch_publication(
          substituted_receipt_request, substituted_receipt_effects);
  ok &= require(substituted_receipt_continued &&
                    receipt_position != std::string::npos &&
                    !substituted_receipt_result &&
                    substituted_receipt_effects.inspect_calls == 1U &&
                    substituted_receipt_effects.terminal_calls == 0U &&
                    !fs::exists(substituted_receipt_operation /
                                "50-generation-published.v2.json"),
                "canonical foreign phase-30 receipt entered epoch publication");

  auto preview_mutation_publication = prepare_fresh_epoch_fixture(
      "epoch-publication-preview-late-mutation");
  EpochContinuationFakeEffects preview_mutation_continuation_effects;
  facman::self_maintenance::EpochContinuationRequest
      preview_mutation_continuation_request{
          preview_mutation_publication.coordinator, "epoch.prepare.one",
          preview_mutation_publication.handoff.nonce,
          preview_mutation_publication.handoff.journal_sha256, true};
  auto preview_mutation_continued =
      facman::self_maintenance::execute_lifecycle_epoch_continuation(
          preview_mutation_continuation_request,
          preview_mutation_continuation_effects);
  const fs::path preview_mutation_epoch =
      preview_mutation_publication.coordinator / "epochs" /
      preview_mutation_publication.epoch.epoch_id;
  const fs::path preview_mutation_operation = preview_mutation_epoch /
      "maintenance" / "epoch.prepare.one";
  epoch_hook_watch = preview_mutation_epoch / "activations" /
      preview_mutation_publication.handoff.transition.previous_activation_name;
  epoch_hook_mutation = preview_mutation_operation /
      "30-provider-outcome.v2.json";
  epoch_hook_bytes = bytes(epoch_hook_mutation);
  const auto preview_receipt_position = epoch_hook_bytes.find(
      exact_receipt_field);
  if (preview_receipt_position != std::string::npos)
    epoch_hook_bytes.replace(preview_receipt_position,
        exact_receipt_field.size(), wrong_receipt_field);
  epoch_hook_called = false;
  epoch_hook_mutated = false;
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(
      replace_epoch_record_after_pin);
  EpochPublicationFakeEffects preview_mutation_effects;
  facman::self_maintenance::EpochPublicationRequest preview_mutation_request{
      preview_mutation_publication.coordinator, "epoch.prepare.one",
      preview_mutation_publication.handoff.nonce,
      preview_mutation_publication.handoff.journal_sha256, false};
  auto preview_mutation_result =
      facman::self_maintenance::execute_lifecycle_epoch_publication(
          preview_mutation_request, preview_mutation_effects);
  facman::self_maintenance::testing::set_epoch_record_pinned_hook(nullptr);
  ok &= require(preview_mutation_continued && epoch_hook_called &&
                    preview_receipt_position != std::string::npos &&
                    equal_size_mutation_refused_or_denied(
                        epoch_hook_mutated,
                        static_cast<bool>(preview_mutation_result)) &&
                    preview_mutation_effects.inspect_calls == 0U &&
                    preview_mutation_effects.terminal_calls == 0U &&
                    !fs::exists(preview_mutation_operation /
                                "50-generation-published.v2.json"),
                "late held-record mutation produced a successful publication preview");

  auto installed_callback_mutation = prepare_fresh_epoch_fixture(
      "epoch-publication-installed-callback-mutation");
  EpochContinuationFakeEffects installed_callback_continuation_effects;
  facman::self_maintenance::EpochContinuationRequest
      installed_callback_continuation_request{
          installed_callback_mutation.coordinator, "epoch.prepare.one",
          installed_callback_mutation.handoff.nonce,
          installed_callback_mutation.handoff.journal_sha256, true};
  auto installed_callback_continued =
      facman::self_maintenance::execute_lifecycle_epoch_continuation(
          installed_callback_continuation_request,
          installed_callback_continuation_effects);
  const fs::path installed_callback_operation =
      installed_callback_mutation.coordinator / "epochs" /
      installed_callback_mutation.epoch.epoch_id / "maintenance" /
      "epoch.prepare.one";
  bool installed_callback_opened = false;
  EpochPublicationFakeEffects installed_callback_effects;
  installed_callback_effects.after_inspect =
      [installed_callback_operation, exact_receipt_field,
       wrong_receipt_field, &installed_callback_opened] {
        const fs::path outcome = installed_callback_operation /
            "30-provider-outcome.v2.json";
        std::string content = bytes(outcome);
        const auto position = content.find(exact_receipt_field);
        if (position != std::string::npos)
          content.replace(position, exact_receipt_field.size(),
                          wrong_receipt_field);
        std::ofstream output(outcome, std::ios::binary | std::ios::trunc);
        installed_callback_opened = output.good();
        output << content;
      };
  facman::self_maintenance::EpochPublicationRequest installed_callback_request{
      installed_callback_mutation.coordinator, "epoch.prepare.one",
      installed_callback_mutation.handoff.nonce,
      installed_callback_mutation.handoff.journal_sha256, true};
  auto installed_callback_result =
      facman::self_maintenance::execute_lifecycle_epoch_publication(
          installed_callback_request, installed_callback_effects);
  ok &= require(installed_callback_continued &&
                    (!installed_callback_opened || !installed_callback_result) &&
                    installed_callback_effects.inspect_calls == 1U &&
                    (!installed_callback_opened ||
                     installed_callback_effects.terminal_calls == 0U) &&
                    (!installed_callback_opened ||
                     !fs::exists(installed_callback_operation /
                                 "50-generation-published.v2.json")),
                "installed-inspection mutation crossed the publication boundary");

  auto publication_callback_mutation = prepare_fresh_epoch_fixture(
      "epoch-publication-callback-mutation");
  EpochContinuationFakeEffects callback_continuation_effects;
  facman::self_maintenance::EpochContinuationRequest callback_continuation_request{
      publication_callback_mutation.coordinator, "epoch.prepare.one",
      publication_callback_mutation.handoff.nonce,
      publication_callback_mutation.handoff.journal_sha256, true};
  auto callback_continued = facman::self_maintenance::execute_lifecycle_epoch_continuation(
      callback_continuation_request, callback_continuation_effects);
  const fs::path callback_publication_operation =
      publication_callback_mutation.coordinator / "epochs" /
      publication_callback_mutation.epoch.epoch_id / "maintenance" /
      "epoch.prepare.one";
  bool publication_callback_opened = false;
  EpochPublicationFakeEffects callback_publication_effects;
  callback_publication_effects.after_terminal =
      [callback_publication_operation, &publication_callback_opened] {
        std::ofstream output(callback_publication_operation /
                                 "40-provider-verified.v2.json",
                             std::ios::binary | std::ios::trunc);
        publication_callback_opened = output.good();
        output << "foreign-verification\n";
      };
  facman::self_maintenance::EpochPublicationRequest callback_publication_request{
      publication_callback_mutation.coordinator, "epoch.prepare.one",
      publication_callback_mutation.handoff.nonce,
      publication_callback_mutation.handoff.journal_sha256, true};
  auto callback_publication_result =
      facman::self_maintenance::execute_lifecycle_epoch_publication(
          callback_publication_request, callback_publication_effects);
  ok &= require(callback_continued &&
                    (!publication_callback_opened || !callback_publication_result) &&
                    (!publication_callback_opened ||
                     !fs::exists(callback_publication_operation /
                                 "50-generation-published.v2.json")),
                "terminal callback mutation crossed the epoch publication boundary");

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
    auto pending_staging =
        facman::self_maintenance::discover_lifecycle_epoch_pending_transition(
            staged.coordinator);
    auto staging_recovered = facman::self_maintenance::execute_lifecycle_epoch_continuation(
        staged_request, staged_effects);
    continuation_staging_recovered = continuation_staging_recovered && !staging_interrupted && staging_recovered &&
        staged_effects.apply_calls == 1U &&
        pending_staging && pending_staging.value() &&
        pending_staging.value()->phase == "continuation_pending" &&
        pending_staging.value()->operation_id == "epoch.prepare.one" &&
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
  std::ofstream(epoch_operation_hook_outside / "FacManContinuation.exe", std::ios::binary | std::ios::trunc) <<
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
      "00-handoff-ready.staging.v3.json";
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
      "maintenance" / "epoch.prepare.one" / "00-handoff-ready.v3.json";
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
      "00-handoff-ready.v3.json");
  ok &= require(!retained_package_mismatch && !mismatch_journal_exists,
                "foreign retained package was accepted into a new handoff");

  auto empty_retry = make_preparation_fixture("epoch-transition-empty-retry");
  fs::create_directories(empty_retry.coordinator / "epochs" / empty_retry.epoch.epoch_id /
      "maintenance" / "epoch.prepare.one");
  empty_retry.request.apply = true;
  auto empty_operation_pending = facman::self_maintenance::discover_lifecycle_epoch_pending_transition(
      empty_retry.coordinator);
  auto empty_operation_retry = facman::self_maintenance::prepare_lifecycle_epoch_transition(
      empty_retry.request, empty_retry.effects);
  ok &= require(empty_operation_pending && empty_operation_pending.value() &&
                    empty_operation_pending.value()->pre_handoff &&
                    empty_operation_pending.value()->operation_id == "epoch.prepare.one" &&
                    empty_operation_pending.value()->target.generation_id ==
                        empty_retry.epoch.genesis_generation_id &&
                    static_cast<bool>(empty_operation_retry),
                "empty maintenance operation directory did not recover into a handoff");

  auto empty_parent = make_preparation_fixture("epoch-transition-empty-parent");
  fs::create_directories(empty_parent.coordinator / "epochs" / empty_parent.epoch.epoch_id /
      "maintenance");
  empty_parent.request.apply = true;
  auto empty_parent_pending = facman::self_maintenance::discover_lifecycle_epoch_pending_transition(
      empty_parent.coordinator);
  auto empty_parent_retry = facman::self_maintenance::prepare_lifecycle_epoch_transition(
      empty_parent.request, empty_parent.effects);
  ok &= require(empty_parent_pending && empty_parent_pending.value() &&
                    empty_parent_pending.value()->pre_handoff &&
                    empty_parent_pending.value()->operation_id.empty() &&
                    empty_parent_pending.value()->target.generation_id ==
                        empty_parent.epoch.genesis_generation_id &&
                    static_cast<bool>(empty_parent_retry),
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
      "00-handoff-ready.staging.v3.json";
  std::error_code provider_staging_rename_error;
  fs::rename(provider_staging.handoff.journal, provider_staging_journal,
             provider_staging_rename_error);
  auto pending_handoff_staging = provider_staging_rename_error
      ? facman::core::Result<std::optional<facman::self_maintenance::EpochPendingTransition>>::failure(
          {"test_rename_failed", provider_staging_rename_error.message(), {}})
      : facman::self_maintenance::discover_lifecycle_epoch_pending_transition(
          provider_staging.coordinator);
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
  std::string provider_staging_stored;
  if (!provider_staging_rename_error && provider_staging_retry) {
    auto provider_staging_document =
        facman::core::json::parse(bytes(provider_staging.handoff.journal));
    if (provider_staging_document)
      provider_staging_stored = json_string_field(
          provider_staging_document.value(), "provider_plan_sha256");
  }
  ok &= require(provider_final_retry && !provider_final_restart.reviewed_packages.empty() &&
                    provider_final_restart.reviewed_packages.back() == provider_final.handoff.inputs.package &&
                    provider_final_stored == provider_final_receipt && !provider_staging_rename_error &&
                    pending_handoff_staging && pending_handoff_staging.value() &&
                    pending_handoff_staging.value()->phase == "handoff_staging" &&
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
  ok &= require(state_before_routing && !active_before_routing &&
                    active_before_routing.error().code ==
                        "self_maintenance_epoch_recovery_required",
                "empty pre-handoff parent was not distinguishable from a committed epoch head");

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
