// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_self_setup.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_sha256.h"

#include <array>
#include <condition_variable>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <iostream>
#include <mutex>
#include <thread>
#include <vector>

namespace fs = std::filesystem;
namespace setup = facman::self_setup;
namespace json = facman::core::json;

namespace {
int checks = 0;
void require(bool value, const char *message) {
  ++checks;
  if (!value) { std::cerr << "FAIL: " << message << '\n'; std::exit(1); }
}

std::string string_member(const std::string &payload, const char *name) {
  auto document = json::parse(payload);
  const json::Value *value = document ? document.value().find(name) : nullptr;
  return value != nullptr && value->string_value() ? value->string_value().value() : std::string();
}

std::string nested_string_member(const std::string &payload,
                                 const char *parent, const char *name) {
  auto document = json::parse(payload);
  const json::Value *object = document ? document.value().find(parent) : nullptr;
  const json::Value *value = object != nullptr && object->is_object()
      ? object->find(name) : nullptr;
  return value != nullptr && value->string_value()
      ? value->string_value().value() : std::string();
}

std::string payload_install_id(const std::string &payload) {
  auto document = json::parse(payload);
  if (!document || !document.value().is_object()) return {};
  const std::string direct = string_member(payload, "install_id");
  if (!direct.empty()) return direct;
  const json::Value *plan = document.value().find("plan_request");
  const json::Value *install_id = plan != nullptr && plan->is_object()
      ? plan->find("install_id") : nullptr;
  return install_id != nullptr && install_id->string_value()
      ? install_id->string_value().value() : std::string();
}

std::string sha256_text(const std::string &value) {
  return facman::base::sha256_hex_bytes(
      reinterpret_cast<const unsigned char *>(value.data()), value.size());
}

struct Clock final : setup::Clock {
  bool advance = true;
  std::string after(const std::string &lower_bound) override {
    return advance ? "9999-12-31T23:59:59Z" : lower_bound;
  }
};

struct Provider final : setup::ProviderEffects {
  Clock clock;
  fs::path coordinator_root;
  int apply_calls = 0;
  bool lose_apply_receipt = false;
  bool rollback_available = false;
  bool recovery_applied = false;
  bool recovery_identity_valid = false;
  bool fail_plan = false;
  bool foreign_content_refusal = false;
  bool generic_provider_refusal = false;
  bool block_apply = false;
  bool apply_entered = false;
  bool release_apply = false;
  bool installed_envelope_valid = true;
  bool installed_identity_mismatch = false;
  bool plan_identity_mismatch = false;
  std::string installed_lifecycle_status = "installed";
  std::string installed_source_digest = std::string(64, 'd');
  std::string plan_source_digest = std::string(64, 'd');
  std::mutex apply_mutex;
  std::condition_variable apply_condition;
  std::string last_transaction_id;
  fs::path recovery_state_root;
  std::vector<std::string> apply_transaction_ids;
  std::vector<std::pair<std::string, std::string>> command_install_ids;
  std::vector<std::string> *events = nullptr;
  fs::path test_coordinator_root() const override { return coordinator_root; }
  facman::core::Result<std::string> command(const std::string &name,
      const std::string &payload, const fs::path &state_root, const fs::path &, bool) override {
    const std::string requested_install_id = payload_install_id(payload);
    if (!requested_install_id.empty())
      command_install_ids.emplace_back(name, requested_install_id);
    if (name == "installed.inspect") {
      json::ArrayBuilder components;
      components.add_string("facman.product");
      json::ArrayBuilder entrypoints;
      json::ObjectBuilder verification;
      verification.add_string("report_digest", std::string(64, '1'));
      verification.add_string("report_id", "verify.facman.self");
      verification.add_string("status", "pass");
      verification.add_string("verified_at", "2026-09-15T00:00:00Z");
      json::ObjectBuilder abi;
      abi.add_unsigned_integer("major", 1U);
      abi.add_unsigned_integer("minor", 0U);
      abi.add_string("provider_revision", setup::provider_revision());
      json::ObjectBuilder installed;
      installed.add_string("audit_chain_id", "audit.facman.self");
      installed.add_array("component_selection", components);
      installed.add_string("created_at", "2026-09-15T00:00:00Z");
      installed.add_array("entrypoints", entrypoints);
      installed.add_string("install_id", installed_identity_mismatch
          ? "facman.self.mismatched" : requested_install_id);
      installed.add_object("last_verification", verification);
      installed.add_string("lifecycle_status", installed_lifecycle_status);
      installed.add_string("ownership_manifest_digest", std::string(64, '2'));
      installed.add_string("ownership_manifest_ref", "ownership/facman.self.json");
      installed.add_string("product_id", "facman");
      installed.add_string("product_version", "1.0.0");
      installed.add_string("recipe_digest", std::string(64, '3'));
      installed.add_string("schema", "usk.installed_state.v1");
      installed.add_object("setup_abi", abi);
      installed.add_string("source_archive_digest", installed_source_digest);
      installed.add_string("target_root", facman::platform::path_to_utf8(
          coordinator_root.parent_path() / "install"));
      installed.add_string("target_scope", "portable");
      installed.add_string("transaction_id", "tx.facman.self.installed");
      json::ObjectBuilder envelope;
      if (installed_envelope_valid) {
        envelope.add_null("error");
        envelope.add_string("schema", "usk.command_response.v1");
      }
      envelope.add_string("status", "ok");
      envelope.add_object("payload", installed);
      return facman::core::Result<std::string>::success(envelope.serialize());
    }
    if (name == "install_local.plan" || name == "repair.plan" || name == "uninstall.plan") {
      if (fail_plan) return facman::core::Result<std::string>::failure({"plan_refused", "injected pre-apply refusal", ""});
      const std::string id = name == "install_local.plan" ? string_member(payload, "request_id") :
          string_member(payload, "plan_id");
      const std::string response_install_id = plan_identity_mismatch
          ? std::string("facman.self.mismatched") : requested_install_id;
      if (name == "install_local.plan")
        return facman::core::Result<std::string>::success(
            "{\"status\":\"ok\",\"payload\":{\"schema\":\"usk.install_plan.v1\","
            "\"status\":\"planned\",\"source\":{\"source_id\":\"source." +
            response_install_id + "\"},\"plan_id\":\"" + id +
            "\",\"plan_digest\":\"" + std::string(64, 'a') + "\"}}");
      return facman::core::Result<std::string>::success(
          "{\"status\":\"ok\",\"payload\":{\"schema\":\"usk.operation_plan.v1\","
          "\"operation\":\"" +
          (name == "uninstall.plan" ? std::string("uninstall") :
           name == "repair.plan" ? std::string("repair") : std::string("install")) +
          "\",\"status\":\"planned\",\"install_id\":\"" +
          response_install_id + "\",\"plan_id\":\"" + id +
          "\",\"plan_digest\":\"" + std::string(64, 'a') +
          "\",\"input_identity\":{\"source_digest\":\"" +
          plan_source_digest + "\",\"provider_revision\":\"" +
          setup::provider_revision() + "\"}}}");
    }
    if (name == "install_local.apply" || name == "repair.apply" || name == "uninstall.apply") {
      if (events != nullptr) events->push_back("provider_apply");
      ++apply_calls;
      last_transaction_id = string_member(payload, "transaction_id");
      apply_transaction_ids.push_back(string_member(payload, "transaction_id"));
      if (block_apply) {
        std::unique_lock<std::mutex> lock(apply_mutex);
        apply_entered = true;
        apply_condition.notify_all();
        apply_condition.wait(lock, [&] { return release_apply; });
      }
      if (foreign_content_refusal) return facman::core::Result<std::string>::failure(
          {"self_setup_provider_refused", "injected refusal", "{\"schema\":\"usk.command_response.v1\",\"status\":\"refused\",\"error\":{\"code\":\"foreign_content_review_required\"}}"});
      if (generic_provider_refusal) return facman::core::Result<std::string>::failure(
          {"self_setup_provider_refused", "injected refusal", "{\"schema\":\"usk.command_response.v1\",\"status\":\"refused\",\"error\":{\"code\":\"lifecycle_refused\"}}"});
      if (lose_apply_receipt)
        return facman::core::Result<std::string>::failure({"lost_receipt", "injected provider receipt loss", ""});
      return facman::core::Result<std::string>::success("{\"status\":\"ok\",\"payload\":{}}");
    }
    if (name == "recovery.inspect") {
      recovery_state_root = state_root;
      recovery_identity_valid = string_member(payload, "schema") == "usk.recovery_inspect_request.v1" &&
          !string_member(payload, "install_id").empty() &&
          !string_member(payload, "transaction_id").empty() &&
          !string_member(payload, "plan_id").empty() && string_member(payload, "plan_digest").size() == 64;
      return facman::core::Result<std::string>::success(
          std::string("{\"status\":\"ok\",\"payload\":{\"schema\":\"usk.recovery_report.v1\",\"status\":\"inspection_only\",\"transaction_id\":\"") + last_transaction_id +
          "\",\"report_digest\":\"" + std::string(64, 'e') + "\",\"journal_digest\":\"" + std::string(64, 'f') + "\",\"available_actions\":[" +
          (rollback_available ? "\"rollback\"" : "\"resume\"") + "]}}");
    }
    if (name == "recovery.plan")
      return facman::core::Result<std::string>::success(
          "{\"status\":\"ok\",\"payload\":{\"plan_id\":\"" + string_member(payload, "recovery_plan_id") + "\",\"plan_digest\":\"" + std::string(64, 'b') + "\"}}");
    if (name == "recovery.apply") {
      recovery_applied = string_member(payload, "selected_action") == "rollback" && recovery_identity_valid;
      return facman::core::Result<std::string>::success(
          "{\"status\":\"ok\",\"payload\":{\"schema\":\"usk.recovery_report.v1\","
          "\"status\":\"rolled_back\",\"selected_action\":\"rollback\","
          "\"transaction_id\":\"" + last_transaction_id +
          "\",\"report_digest\":\"" + std::string(64, 'c') +
          "\",\"journal_digest\":\"" + std::string(64, 'd') + "\"}}");
    }
    return facman::core::Result<std::string>::failure({"unexpected", name, ""});
  }
};

struct Native final : setup::NativeEffects {
  std::array<setup::NativeOwnership, 2> state{setup::NativeOwnership::absent, setup::NativeOwnership::absent};
  std::array<int, 2> inspect_calls{0, 0};
  std::array<int, 2> apply_calls{0, 0};
  std::vector<fs::path> inspect_roots;
  std::vector<fs::path> apply_roots;
  std::vector<fs::path> apply_repair_sources;
  int lose_receipt = -1;
  int require_recovery = -1;
  int retain_calls = 0;
  int validate_calls = 0;
  int validate_launcher_calls = 0;
  bool retain_fails = false;
  bool retain_requires_recovery = false;
  bool validation_fails = false;
  bool launcher_validation_fails = false;
  std::vector<std::string> *events = nullptr;
  setup::RetainedSourceResult retain_repair_source(
      const setup::NativeContext &context, const fs::path &package,
      const fs::path &maintenance_launcher,
      const std::string &) override {
    ++retain_calls;
    if (events != nullptr) events->push_back("retain");
    if (!retain_fails) {
      std::error_code status;
      fs::create_directories(context.repair_source.parent_path(), status);
      if (!status && package != context.repair_source)
        fs::copy_file(package, context.repair_source,
                      fs::copy_options::skip_existing, status);
      const fs::path launcher = context.repair_source.parent_path() /
          fs::path(context.repair_source.stem().wstring() + L".FacManSetup.exe");
      if (!status && maintenance_launcher != launcher)
        fs::copy_file(maintenance_launcher, launcher,
                      fs::copy_options::skip_existing, status);
      if (status)
        return {false, {}, "fake retention copy failed: " + status.message()};
    }
    return retain_fails
        ? setup::RetainedSourceResult{false, {}, "injected retain failure",
                                      retain_requires_recovery}
        : setup::RetainedSourceResult{true, context.repair_source, "retained"};
  }
  setup::RetainedSourceResult validate_repair_source(
      const setup::NativeContext &context, const std::string &) override {
    ++validate_calls;
    return validation_fails
        ? setup::RetainedSourceResult{false, {}, "injected validation failure", true}
        : setup::RetainedSourceResult{true, context.repair_source, "validated"};
  }
  setup::RetainedSourceResult validate_maintenance_launcher(
      const setup::NativeContext &context, const std::string &) override {
    ++validate_launcher_calls;
    const fs::path launcher = context.repair_source.parent_path() /
        fs::path(context.repair_source.stem().wstring() + L".FacManSetup.exe");
    return launcher_validation_fails
        ? setup::RetainedSourceResult{
              false, {}, "injected launcher validation failure", true}
        : setup::RetainedSourceResult{true, launcher, "launcher validated"};
  }
  setup::NativeOwnership inspect(const setup::NativeContext &context,
                                 setup::NativeEffect effect) override {
    const int index = static_cast<int>(effect);
    ++inspect_calls[index]; inspect_roots.push_back(context.install_root);
    return state[index];
  }
  setup::NativeResult apply(const setup::NativeContext &context,
                            setup::NativeEffect effect) override {
    const int index = static_cast<int>(effect); ++apply_calls[index];
    apply_roots.push_back(context.install_root);
    apply_repair_sources.push_back(context.repair_source);
    state[index] = context.operation == setup::Operation::uninstall
        ? setup::NativeOwnership::absent : setup::NativeOwnership::owned;
    if (index == require_recovery) return {false, "native substitution", true};
    return index == lose_receipt ? setup::NativeResult{false, "lost native receipt"} : setup::NativeResult{true, {}};
  }
};

struct InterruptAt final : setup::DurableBoundaryHook {
  explicit InterruptAt(setup::DurableBoundary target) : target(target) {}
  setup::DurableBoundary target;
  int calls = 0;
  bool reached(setup::DurableBoundary boundary) override {
    ++calls;
    return boundary != target;
  }
};

struct Tree { fs::path root; ~Tree() { std::error_code ignored; fs::remove_all(root, ignored); } };

fs::path active_journal_path(const Tree &tree);

std::string active_journal(const Tree &tree) {
  const fs::path path = active_journal_path(tree);
  if (path.empty()) return {};
  std::ifstream input(path, std::ios::binary);
  return {std::istreambuf_iterator<char>(input), {}};
}

fs::path active_journal_path(const Tree &tree) {
  const fs::path directory = tree.root / "coordinator" / "setup-operations";
  std::vector<fs::path> candidates;
  std::error_code status;
  for (fs::directory_iterator iterator(directory, status), end;
       !status && iterator != end; iterator.increment(status)) {
    if (iterator->is_regular_file(status) && !status)
      candidates.push_back(iterator->path());
  }
  return status || candidates.size() != 1U ? fs::path{} : candidates.front();
}

setup::Request request_for(const Tree &tree, Provider &provider, Native *native,
                           setup::Operation operation = setup::Operation::install) {
  setup::Request request;
  request.operation = operation; request.install_root = tree.root / "install";
  request.state_root = tree.root / "state"; request.acceptance_root = tree.root;
  request.package = tree.root / "payload.zip"; request.product_version = "1.0.0";
  request.maintenance_launcher = tree.root / "FacManSetup.exe";
  if (!fs::exists(request.maintenance_launcher))
    std::ofstream(request.maintenance_launcher, std::ios::binary) << "launcher";
  provider.coordinator_root = tree.root / "coordinator";
  request.apply = true; request.provider_effects = &provider; request.native_effects = native;
  request.clock = &provider.clock;
  return request;
}

void cases() {
  Tree epoch_guard{fs::temp_directory_path() /
                   "facman-self-setup-epoch-install-guard"};
  std::error_code ignored;
  fs::remove_all(epoch_guard.root, ignored);
  fs::create_directories(epoch_guard.root / "coordinator" / "epochs");
  std::ofstream(epoch_guard.root / "payload.zip", std::ios::binary) << "fixture";
  Provider guarded_provider;
  Native guarded_native;
  auto blocked_install = setup::execute(request_for(
      epoch_guard, guarded_provider, &guarded_native));
  require(!blocked_install && blocked_install.error().code ==
              "self_maintenance_epoch_recovery_required" &&
              guarded_provider.apply_calls == 0 &&
              guarded_native.retain_calls == 0,
          "direct compatibility install did not stop at an epoch namespace");

  Tree tree{fs::temp_directory_path() / "facman-self-setup-recovery-smoke"};
  fs::remove_all(tree.root, ignored); fs::create_directories(tree.root);
  std::ofstream(tree.root / "payload.zip", std::ios::binary) << "fixture";
  Provider provider; Native native;
  std::vector<std::string> initial_events;
  provider.events = &initial_events;
  native.events = &initial_events;
  auto first = setup::execute(request_for(tree, provider, &native));
  require(first && native.retain_calls == 1 &&
              native.apply_calls == std::array<int, 2>{1, 1} &&
              initial_events.size() >= 2U && initial_events[0] == "retain" &&
              initial_events[1] == "provider_apply",
          "install retains its repair inputs before provider and native effects");
  require(fs::is_regular_file(tree.root / "state" / "repair-sources" /
              (sha256_text("fixture") + ".zip")),
          "installed setup keeps the exact repair package before provider mutation");
  require(fs::exists(tree.root / "coordinator"), "injected coordinator uses its isolated app-owned test root");
  auto repeated = setup::execute(request_for(tree, provider, &native));
  require(repeated && provider.apply_calls == 2 && native.retain_calls == 2,
          "completed attempt is archived and a later request has a fresh provider transaction");
  auto repair_request = request_for(tree, provider, &native, setup::Operation::repair);
  require(setup::execute(repair_request) && provider.apply_calls == 3 &&
              native.retain_calls == 3,
          "later same-version repair has a distinct durable operation identity");
  require(provider.apply_transaction_ids.size() == 3 &&
              provider.apply_transaction_ids[0].size() == 33 &&
              provider.apply_transaction_ids[1].size() == 33 &&
              provider.apply_transaction_ids[2].size() == 33 &&
              provider.apply_transaction_ids[0].rfind("tx.setup.", 0) == 0 &&
              provider.apply_transaction_ids[1].rfind("tx.setup.", 0) == 0 &&
              provider.apply_transaction_ids[2].rfind("tx.setup.", 0) == 0 &&
              provider.apply_transaction_ids[0] != provider.apply_transaction_ids[1] &&
              provider.apply_transaction_ids[1] != provider.apply_transaction_ids[2] &&
              provider.apply_transaction_ids[0] != provider.apply_transaction_ids[2],
          "provider transaction identities are unique and bounded for Windows staging paths");
  Tree generation_repair{
      fs::temp_directory_path() / "facman-self-setup-recovery-smoke-generation-repair"};
  fs::remove_all(generation_repair.root, ignored);
  fs::create_directories(generation_repair.root);
  std::ofstream(generation_repair.root / "payload.zip", std::ios::binary)
      << "fixture";
  Provider generation_provider;
  Native generation_native;
  auto generation_request = request_for(
      generation_repair, generation_provider, &generation_native,
      setup::Operation::repair);
  generation_request.install_id =
      "facman.self.generation." + std::string(64, 'a');
  auto generation_result = setup::execute(generation_request);
  require(generation_result &&
              generation_provider.apply_transaction_ids.size() == 1U &&
              generation_provider.apply_transaction_ids.front().size() == 27U &&
              generation_provider.apply_transaction_ids.front().rfind("tx.", 0) == 0 &&
              ("ownership." + generation_request.install_id + "." +
               generation_provider.apply_transaction_ids.front()).size() <= 128U,
          "generation repair compacts its transaction before the provider-derived ownership limit");
  Tree contention{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-contention"};
  fs::remove_all(contention.root, ignored); fs::create_directories(contention.root);
  std::ofstream(contention.root / "payload.zip", std::ios::binary) << "fixture";
  Provider holding_provider; holding_provider.block_apply = true; Native holding_native;
  bool holding_succeeded = false;
  std::thread holding([&] {
    holding_succeeded = static_cast<bool>(
        setup::execute(request_for(contention, holding_provider, &holding_native)));
  });
  {
    std::unique_lock<std::mutex> lock(holding_provider.apply_mutex);
    holding_provider.apply_condition.wait(lock, [&] { return holding_provider.apply_entered; });
  }
  Provider contending_provider; Native contending_native;
  auto contending_request = request_for(contention, contending_provider, &contending_native);
#ifdef _WIN32
  contending_request.install_root = contention.root / "INSTALL";
#else
  const fs::path contention_alias = contention.root / "root-alias";
  fs::create_directory_symlink(contention.root, contention_alias, ignored);
  require(!ignored, "POSIX contention fixture creates a canonical directory alias");
  contending_request.install_root = contention_alias / "install";
#endif
  contending_request.state_root = contention.root / "different-provider-state";
  auto contended = setup::execute(contending_request);
  require(!contended && contended.error().code == "self_setup_lock_contended" &&
              contending_provider.apply_calls == 0,
          "canonical root lock rejects an alias using a different provider state root");
  {
    std::lock_guard<std::mutex> lock(holding_provider.apply_mutex);
    holding_provider.release_apply = true;
  }
  holding_provider.apply_condition.notify_all();
  holding.join();
  require(holding_succeeded, "root lock holder completes after contention is refused");
  Tree interrupted{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-interrupted"};
  fs::remove_all(interrupted.root, ignored); fs::create_directories(interrupted.root);
  std::ofstream(interrupted.root / "payload.zip", std::ios::binary) << "fixture";
  Provider native_provider; Native lost; lost.lose_receipt = 0;
  auto failed = setup::execute(request_for(interrupted, native_provider, &lost));
  require(!failed && lost.state[0] == setup::NativeOwnership::owned, "shortcut receipt loss leaves observed effect");
  lost.lose_receipt = -1;
  auto resumed = setup::execute(request_for(interrupted, native_provider, &lost));
  require(resumed && lost.apply_calls[0] == 1 && lost.apply_calls[1] == 1, "restart reconciles lost shortcut receipt without duplicate effect");
  Tree pre_entry{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-pre-entry"};
  fs::remove_all(pre_entry.root, ignored); fs::create_directories(pre_entry.root);
  std::ofstream(pre_entry.root / "payload.zip", std::ios::binary) << "fixture";
  Provider pre_entry_provider; Native pre_entry_native;
  InterruptAt after_plan(setup::DurableBoundary::provider_plan_reviewed);
  auto pre_entry_request = request_for(
      pre_entry, pre_entry_provider, &pre_entry_native, setup::Operation::repair);
  pre_entry_request.durable_boundary_hook = &after_plan;
  auto pre_entry_interrupted = setup::execute(pre_entry_request);
  require(!pre_entry_interrupted &&
              pre_entry_interrupted.error().code == "self_setup_interrupted" &&
              pre_entry_provider.apply_calls == 0 &&
              pre_entry_native.retain_calls == 1 && after_plan.calls == 1 &&
              nested_string_member(active_journal(pre_entry), "provider", "phase") ==
                  "plan_reviewed",
          "provider plan-review interruption is durably distinct from apply entry");
  fs::remove(pre_entry.root / "payload.zip", ignored);
  auto missing_original = request_for(
      pre_entry, pre_entry_provider, &pre_entry_native, setup::Operation::repair);
  missing_original.package = pre_entry.root / "payload.zip";
  require(setup::execute(missing_original) &&
              pre_entry_provider.apply_calls == 1 &&
              pre_entry_native.retain_calls == 1 &&
              pre_entry_native.validate_calls == 1,
          "pre-entry repair resumes from its retained package when the caller source is gone");
  Tree fresh_missing{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-fresh-missing"};
  fs::remove_all(fresh_missing.root, ignored); fs::create_directories(fresh_missing.root);
  Provider fresh_missing_provider; Native fresh_missing_native;
  auto fresh_missing_request = request_for(
      fresh_missing, fresh_missing_provider, &fresh_missing_native,
      setup::Operation::repair);
  auto fresh_missing_result = setup::execute(fresh_missing_request);
  require(!fresh_missing_result &&
              fresh_missing_result.error().code == "self_setup_package_missing" &&
              fresh_missing_provider.apply_calls == 0 &&
              fresh_missing_native.retain_calls == 0 &&
              active_journal(fresh_missing).empty(),
          "fresh repair with a missing package is a typed no-effect refusal");
  Tree files_boundary{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-files-boundary"};
  fs::remove_all(files_boundary.root, ignored); fs::create_directories(files_boundary.root);
  std::ofstream(files_boundary.root / "payload.zip", std::ios::binary) << "fixture";
  Provider files_provider; Native files_native;
  InterruptAt after_files(setup::DurableBoundary::files_applied);
  auto files_request = request_for(files_boundary, files_provider, &files_native);
  files_request.durable_boundary_hook = &after_files;
  auto files_interrupted = setup::execute(files_request);
  require(!files_interrupted && files_interrupted.error().code == "self_setup_interrupted" &&
              after_files.calls == 2 && files_native.apply_calls == std::array<int, 2>{0, 0},
          "installed files boundary interruption occurs after persistence and before native effects");
  auto crossed_claim = request_for(files_boundary, files_provider, &files_native);
  setup::QualificationClaims crossed;
  crossed.operation = crossed_claim.operation;
  crossed.install_root = crossed_claim.install_root;
  crossed.state_root = crossed_claim.state_root;
  crossed.acceptance_root = crossed_claim.acceptance_root;
  crossed.product_version = crossed_claim.product_version;
  crossed.installed_mode = true;
  crossed.boundary = setup::DurableBoundary::files_applied;
  crossed_claim.qualification_claims = crossed;
  auto crossed_result = setup::execute(crossed_claim);
  require(!crossed_result && crossed_result.error().code == "self_setup_qualification_interrupt_invalid" &&
              files_provider.apply_calls == 1 && files_native.apply_calls == std::array<int, 2>{0, 0},
          "a consumed qualification permit cannot silently target an already crossed boundary");
  auto mismatched_claim = request_for(files_boundary, files_provider, &files_native);
  mismatched_claim.state_root = files_boundary.root / "other-state";
  auto mismatched = crossed;
  mismatched.state_root = mismatched_claim.state_root;
  mismatched_claim.qualification_claims = mismatched;
  auto mismatch_result = setup::execute(mismatched_claim);
  require(!mismatch_result && mismatch_result.error().code == "self_setup_qualification_interrupt_invalid" &&
              files_provider.apply_calls == 1 && files_native.apply_calls == std::array<int, 2>{0, 0},
          "qualification claims reject a pending journal with a mismatched provider authority before effects");
  auto files_retry = request_for(files_boundary, files_provider, &files_native);
#ifdef _WIN32
  files_retry.install_root = files_boundary.root / "INSTALL";
#else
  const fs::path files_alias = files_boundary.root / "root-alias";
  fs::create_directory_symlink(files_boundary.root, files_alias, ignored);
  require(!ignored, "POSIX files-boundary fixture creates a canonical directory alias");
  files_retry.install_root = files_alias / "install";
#endif
  const fs::path durable_install_root = files_boundary.root / "install";
  require(setup::execute(files_retry) && files_provider.apply_calls == 1 &&
              files_native.apply_calls == std::array<int, 2>{1, 1} &&
              files_native.inspect_roots == std::vector<fs::path>{durable_install_root, durable_install_root} &&
              files_native.apply_roots == std::vector<fs::path>{durable_install_root, durable_install_root},
          "files-boundary resume uses the journal install root despite a caller alias");
  Tree shortcut_boundary{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-shortcut-boundary"};
  fs::remove_all(shortcut_boundary.root, ignored); fs::create_directories(shortcut_boundary.root);
  std::ofstream(shortcut_boundary.root / "payload.zip", std::ios::binary) << "fixture";
  Provider shortcut_provider; Native shortcut_native;
  InterruptAt after_shortcut(setup::DurableBoundary::shortcut_applied);
  auto shortcut_request = request_for(shortcut_boundary, shortcut_provider, &shortcut_native);
  shortcut_request.durable_boundary_hook = &after_shortcut;
  auto shortcut_interrupted = setup::execute(shortcut_request);
  require(!shortcut_interrupted && shortcut_interrupted.error().code == "self_setup_interrupted" &&
              after_shortcut.calls == 3 && shortcut_native.apply_calls == std::array<int, 2>{1, 0},
          "shortcut boundary interruption leaves exactly one durable native effect");
  require(setup::execute(request_for(shortcut_boundary, shortcut_provider, &shortcut_native)) &&
              shortcut_provider.apply_calls == 1 && shortcut_native.apply_calls == std::array<int, 2>{1, 1},
          "shortcut-boundary resume inspects the durable shortcut and only applies registration");
  Tree hosted_sequence{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-hosted-sequence"};
  fs::remove_all(hosted_sequence.root, ignored); fs::create_directories(hosted_sequence.root);
  std::ofstream(hosted_sequence.root / "payload.zip", std::ios::binary) << "fixture";
  Provider hosted_provider; Native hosted_native;
  InterruptAt hosted_after_files(setup::DurableBoundary::files_applied);
  auto hosted_files_request = request_for(hosted_sequence, hosted_provider, &hosted_native);
  hosted_files_request.durable_boundary_hook = &hosted_after_files;
  auto hosted_files_interrupted = setup::execute(hosted_files_request);
  require(!hosted_files_interrupted && hosted_files_interrupted.error().code == "self_setup_interrupted" &&
              hosted_native.apply_calls == std::array<int, 2>{0, 0},
          "hosted sequence interrupts at files-applied before native effects");
  require(setup::execute(request_for(hosted_sequence, hosted_provider, &hosted_native)) &&
              hosted_native.apply_calls == std::array<int, 2>{1, 1},
          "hosted sequence resumes the files-applied install");
  auto hosted_uninstall = setup::execute(request_for(
      hosted_sequence, hosted_provider, &hosted_native,
      setup::Operation::uninstall));
  if (!hosted_uninstall)
    std::cerr << "hosted uninstall: " << hosted_uninstall.error().code << ": "
              << hosted_uninstall.error().message << ": "
              << hosted_uninstall.error().detail << '\n';
  require(hosted_uninstall &&
              hosted_native.apply_calls == std::array<int, 2>{2, 2},
          "hosted sequence completes uninstall before the fresh install");
  InterruptAt hosted_after_shortcut(setup::DurableBoundary::shortcut_applied);
  auto hosted_shortcut_request = request_for(hosted_sequence, hosted_provider, &hosted_native);
  hosted_shortcut_request.durable_boundary_hook = &hosted_after_shortcut;
  auto hosted_shortcut_interrupted = setup::execute(hosted_shortcut_request);
  require(!hosted_shortcut_interrupted &&
              hosted_shortcut_interrupted.error().code == "self_setup_interrupted" &&
              hosted_after_shortcut.calls == 3 &&
              hosted_native.apply_calls == std::array<int, 2>{3, 2},
          "fresh same-intent install interrupts at shortcut-applied with exactly one native effect");
  const fs::path hosted_history = hosted_sequence.root / "coordinator" /
      "setup-operations" / "history";
  std::vector<fs::path> hosted_archives;
  for (fs::directory_iterator iterator(hosted_history, ignored), end;
       !ignored && iterator != end; iterator.increment(ignored)) {
    if (iterator->is_regular_file(ignored) && !ignored)
      hosted_archives.push_back(iterator->path());
  }
  require(!ignored && hosted_archives.size() == 1,
          "fresh same-intent install archives exactly one completed terminal journal");
  std::ifstream hosted_archive_input(hosted_archives.front(), std::ios::binary);
  const std::string hosted_archive_json{std::istreambuf_iterator<char>(hosted_archive_input), {}};
  const std::string hosted_operation_id = string_member(hosted_archive_json, "operation_id");
  const std::string hosted_intent_digest = string_member(hosted_archive_json, "intent_digest");
  const std::string hosted_root_identity = string_member(hosted_archive_json, "install_root_identity");
  const std::string hosted_operation = string_member(hosted_archive_json, "operation");
  const std::string expected_hosted_history = "facman." + sha256_text(
      "facman.setup.history.v1\n" + hosted_operation_id + "\n" + hosted_intent_digest + "\n" +
      hosted_root_identity + "\n" + hosted_operation) + ".setup-history.v2.json";
  require(hosted_operation == "install" && string_member(hosted_archive_json, "state") == "completed" &&
              hosted_archives.front().filename().string() == expected_hosted_history &&
              expected_hosted_history.size() <= 96U,
          "completed install terminal journal has the bounded expected history archive name");
  const auto applied_effect_changed = [&](const char *suffix,
                                          setup::NativeOwnership replacement,
                                          setup::Operation operation) {
    Tree changed{fs::temp_directory_path() / (std::string("facman-self-setup-recovery-smoke-applied-") + suffix)};
    fs::remove_all(changed.root, ignored); fs::create_directories(changed.root);
    std::ofstream(changed.root / "payload.zip", std::ios::binary) << "fixture";
    Provider changed_provider; Native changed_native;
    if (operation == setup::Operation::uninstall)
      changed_native.state = {setup::NativeOwnership::owned, setup::NativeOwnership::owned};
    InterruptAt after_applied(setup::DurableBoundary::shortcut_applied);
    auto changed_request = request_for(changed, changed_provider, &changed_native, operation);
    changed_request.durable_boundary_hook = &after_applied;
    auto interrupted_change = setup::execute(changed_request);
    require(!interrupted_change && interrupted_change.error().code == "self_setup_interrupted" &&
                changed_native.apply_calls == std::array<int, 2>{1, 0},
            "shortcut durable boundary is reachable before an applied-state substitution");
    changed_native.state[0] = replacement;
    auto recovered_change = setup::execute(request_for(changed, changed_provider, &changed_native, operation));
    require(!recovered_change && recovered_change.error().code == "self_setup_recovery_required" &&
                changed_provider.apply_calls == 1 && changed_native.apply_calls == std::array<int, 2>{1, 0},
            "changed durable native effect is retained for manual recovery without another apply");
  };
  applied_effect_changed("absent", setup::NativeOwnership::absent, setup::Operation::install);
  applied_effect_changed("stale", setup::NativeOwnership::owned_stale, setup::Operation::install);
  applied_effect_changed("foreign", setup::NativeOwnership::foreign, setup::Operation::install);
  applied_effect_changed("unreadable", setup::NativeOwnership::unreadable, setup::Operation::install);
  applied_effect_changed("uninstall-owned", setup::NativeOwnership::owned, setup::Operation::uninstall);
  Tree provider_crash{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-provider"};
  fs::remove_all(provider_crash.root, ignored); fs::create_directories(provider_crash.root);
  std::ofstream(provider_crash.root / "payload.zip", std::ios::binary) << "fixture";
  Provider crash; crash.lose_apply_receipt = true; crash.rollback_available = true; Native crash_native;
  require(!setup::execute(request_for(provider_crash, crash, &crash_native)), "provider receipt loss is not replayed as apply");
  crash.lose_apply_receipt = false;
  auto recovered = setup::execute(request_for(provider_crash, crash, &crash_native));
  require(!recovered && !crash.recovery_applied && crash.apply_calls == 1,
          "restart refuses a generic apply before a reviewed recovery plan exists");
  auto review_request = request_for(provider_crash, crash, &crash_native, setup::Operation::repair);
  review_request.product_version = "9.9.9";
  review_request.package = provider_crash.root / "missing.zip";
  review_request.state_root = provider_crash.root / "other-provider-state";
  review_request.apply = false;
  auto review = setup::execute(review_request);
  require(review && review.value().phase == "recovery_plan" && crash.recovery_identity_valid,
          "preview persists an exact rollback recovery plan");
  require(crash.recovery_state_root == provider_crash.root / "state",
          "changed provider roots still recover through the journal authority");
  review_request.apply = true;
  auto rolled_back = setup::execute(review_request);
  require(!rolled_back && crash.recovery_applied && crash.apply_calls == 1,
          "reviewed rollback is applied without replaying the original transaction");
  auto fresh_after_rollback = setup::execute(request_for(provider_crash, crash, &crash_native));
  require(fresh_after_rollback && crash.apply_calls == 2,
          "terminal rollback is archived before a fresh provider transaction");
  Tree preapply{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-preapply"};
  fs::remove_all(preapply.root, ignored); fs::create_directories(preapply.root);
  std::ofstream(preapply.root / "payload.zip", std::ios::binary) << "fixture";
  Provider preapply_provider; preapply_provider.fail_plan = true; Native preapply_native;
  require(!setup::execute(request_for(preapply, preapply_provider, &preapply_native)) &&
              string_member(active_journal(preapply), "state") == "abandoned",
          "pre-apply plan refusal is durably retired without an apply boundary");
  preapply_provider.fail_plan = false;
  auto changed_preapply = request_for(preapply, preapply_provider, &preapply_native, setup::Operation::repair);
  changed_preapply.product_version = "2.0.0";
  require(setup::execute(changed_preapply) && preapply_provider.apply_calls == 1,
          "a changed request starts after the prior pre-effect refusal was retired");
  Tree clock_failure{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-clock"};
  fs::remove_all(clock_failure.root, ignored); fs::create_directories(clock_failure.root);
  std::ofstream(clock_failure.root / "payload.zip", std::ios::binary) << "fixture";
  Provider clock_provider; Native clock_native;
  clock_provider.clock.advance = false;
  auto clock_result = setup::execute(request_for(clock_failure, clock_provider, &clock_native));
  require(!clock_result && clock_result.error().code == "self_setup_clock_unusable" &&
              clock_provider.apply_calls == 0 &&
              clock_native.apply_calls == std::array<int, 2>{0, 0},
          "a non-advancing injected timestamp is refused before provider apply");
  Tree visible{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-visible"};
  fs::remove_all(visible.root, ignored); fs::create_directories(visible.root);
  std::ofstream(visible.root / "payload.zip", std::ios::binary) << "fixture";
  Provider visible_provider; visible_provider.lose_apply_receipt = true; Native visible_native;
  require(!setup::execute(request_for(visible, visible_provider, &visible_native)), "visible provider receipt loss records durable intent");
  visible_provider.lose_apply_receipt = false;
  auto visible_result = setup::execute(request_for(visible, visible_provider, &visible_native));
  require(!visible_result && !visible_provider.recovery_applied && visible_provider.apply_calls == 1,
          "visible provider resume remains operator recovery and never replays apply");
  Tree blocked{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-blocked"};
  fs::remove_all(blocked.root, ignored); fs::create_directories(blocked.root);
  std::ofstream(blocked.root / "payload.zip", std::ios::binary) << "fixture";
  Provider blocked_provider; Native foreign; foreign.state[0] = setup::NativeOwnership::foreign;
  require(!setup::execute(request_for(blocked, blocked_provider, &foreign)) && foreign.apply_calls[0] == 0,
          "foreign native ownership is preserved without an apply call");
  Tree retain_retry{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-retain-retry"};
  fs::remove_all(retain_retry.root, ignored); fs::create_directories(retain_retry.root);
  std::ofstream(retain_retry.root / "payload.zip", std::ios::binary) << "fixture";
  Provider retain_provider; Native retryable_retain; retryable_retain.retain_fails = true;
  auto retain_failed = setup::execute(request_for(retain_retry, retain_provider, &retryable_retain));
  require(!retain_failed &&
              retain_failed.error().code == "self_setup_windows_integration_failed" &&
              retain_provider.apply_calls == 0 && retryable_retain.retain_calls == 1 &&
              retryable_retain.apply_calls == std::array<int, 2>{0, 0},
          "retryable retained-source failure stops before provider and native effects");
  retryable_retain.retain_fails = false;
  require(setup::execute(request_for(retain_retry, retain_provider, &retryable_retain)) &&
              retain_provider.apply_calls == 1 && retryable_retain.retain_calls == 2 &&
              retryable_retain.apply_calls == std::array<int, 2>{1, 1},
          "retained-source retry proceeds through its first provider apply");
  Tree retain_frozen{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-retain-frozen"};
  fs::remove_all(retain_frozen.root, ignored); fs::create_directories(retain_frozen.root);
  std::ofstream(retain_frozen.root / "payload.zip", std::ios::binary) << "fixture";
  Provider frozen_provider; Native frozen_retain;
  frozen_retain.retain_fails = true; frozen_retain.retain_requires_recovery = true;
  auto frozen_result = setup::execute(request_for(retain_frozen, frozen_provider, &frozen_retain));
  require(!frozen_result && frozen_result.error().code == "self_setup_recovery_required" &&
              frozen_provider.apply_calls == 0 &&
              frozen_retain.apply_calls == std::array<int, 2>{0, 0},
          "foreign retained-source identity freezes recovery before provider and native effects");
  Tree adapter{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-adapter"};
  fs::remove_all(adapter.root, ignored); fs::create_directories(adapter.root);
  std::ofstream(adapter.root / "payload.zip", std::ios::binary) << "fixture";
  Provider adapter_provider; Native substituted; substituted.require_recovery = 0;
  auto substituted_result = setup::execute(request_for(adapter, adapter_provider, &substituted));
  require(!substituted_result && substituted_result.error().code == "self_setup_recovery_required",
          "adapter mutation-edge substitution propagates recovery_required");
  Tree dynamic_uninstall{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-dynamic-id"};
  fs::remove_all(dynamic_uninstall.root, ignored); fs::create_directories(dynamic_uninstall.root);
  Provider dynamic_provider; Native dynamic_native;
  dynamic_native.state = {setup::NativeOwnership::owned, setup::NativeOwnership::owned};
  auto dynamic_request = request_for(
      dynamic_uninstall, dynamic_provider, &dynamic_native, setup::Operation::uninstall);
  dynamic_request.install_id = "facman.self.generation.dynamic";
  require(setup::execute(dynamic_request) &&
              string_member(active_journal(dynamic_uninstall), "schema") ==
                  "facman.setup_operation_journal.v2" &&
              string_member(active_journal(dynamic_uninstall), "install_id") ==
                  dynamic_request.install_id &&
              dynamic_provider.command_install_ids ==
                  std::vector<std::pair<std::string, std::string>>{
                      {"installed.inspect", dynamic_request.install_id},
                      {"uninstall.plan", dynamic_request.install_id},
                      {"uninstall.apply", dynamic_request.install_id}},
          "dynamic install identity reaches inspection, uninstall planning and apply");
  Tree identity_mismatch{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-identity-mismatch"};
  fs::remove_all(identity_mismatch.root, ignored); fs::create_directories(identity_mismatch.root);
  Provider identity_mismatch_provider; Native identity_mismatch_native;
  identity_mismatch_provider.installed_identity_mismatch = true;
  auto identity_mismatch_request = request_for(
      identity_mismatch, identity_mismatch_provider, &identity_mismatch_native,
      setup::Operation::uninstall);
  identity_mismatch_request.install_id = "facman.self.generation.expected";
  auto identity_mismatch_result = setup::execute(identity_mismatch_request);
  require(!identity_mismatch_result &&
              identity_mismatch_result.error().code == "self_setup_response_invalid" &&
              identity_mismatch_provider.apply_calls == 0 &&
              string_member(active_journal(identity_mismatch), "state") == "abandoned",
          "installed inspection response identity must match the exact request install id");
  Tree plan_identity_mismatch{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-plan-identity-mismatch"};
  fs::remove_all(plan_identity_mismatch.root, ignored); fs::create_directories(plan_identity_mismatch.root);
  std::ofstream(plan_identity_mismatch.root / "payload.zip", std::ios::binary) << "fixture";
  Provider plan_identity_mismatch_provider; Native plan_identity_mismatch_native;
  plan_identity_mismatch_provider.plan_identity_mismatch = true;
  auto plan_identity_mismatch_request = request_for(
      plan_identity_mismatch, plan_identity_mismatch_provider, &plan_identity_mismatch_native);
  plan_identity_mismatch_request.install_id = "facman.self.generation.plan-expected";
  auto plan_identity_mismatch_result = setup::execute(plan_identity_mismatch_request);
  require(!plan_identity_mismatch_result &&
              plan_identity_mismatch_result.error().code == "self_setup_response_invalid" &&
              plan_identity_mismatch_provider.apply_calls == 0 &&
              string_member(active_journal(plan_identity_mismatch), "state") == "abandoned",
          "provider plan response identity must match the exact request install id");
  Tree dynamic_recovery{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-dynamic-recovery-id"};
  fs::remove_all(dynamic_recovery.root, ignored); fs::create_directories(dynamic_recovery.root);
  std::ofstream(dynamic_recovery.root / "payload.zip", std::ios::binary) << "fixture";
  Provider dynamic_recovery_provider; Native dynamic_recovery_native;
  dynamic_recovery_provider.lose_apply_receipt = true;
  dynamic_recovery_provider.rollback_available = true;
  auto dynamic_recovery_request = request_for(
      dynamic_recovery, dynamic_recovery_provider, &dynamic_recovery_native);
  dynamic_recovery_request.install_id = "facman.self.generation.recovery";
  require(!setup::execute(dynamic_recovery_request),
          "dynamic install receipt loss leaves a recoverable journal");
  dynamic_recovery_provider.lose_apply_receipt = false;
  auto dynamic_recovery_preview = request_for(
      dynamic_recovery, dynamic_recovery_provider, &dynamic_recovery_native,
      setup::Operation::repair);
  dynamic_recovery_preview.install_id = "facman.self.generation.wrong-caller";
  dynamic_recovery_preview.apply = false;
  auto dynamic_recovery_result = setup::execute(dynamic_recovery_preview);
  require(dynamic_recovery_result && dynamic_recovery_result.value().phase == "recovery_plan" &&
              !dynamic_recovery_provider.command_install_ids.empty() &&
              dynamic_recovery_provider.command_install_ids.back() ==
                  std::pair<std::string, std::string>{
                      "recovery.inspect", dynamic_recovery_request.install_id},
          "recovery restores the journal-bound dynamic install identity");
  Tree removal{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-uninstall"};
  fs::remove_all(removal.root, ignored); fs::create_directories(removal.root);
  Provider removal_provider;
  removal_provider.installed_lifecycle_status = "verified";
  Native stale; stale.state = {setup::NativeOwnership::owned_stale, setup::NativeOwnership::owned_stale};
  stale.validation_fails = true;
  auto uninstall_request = request_for(removal, removal_provider, &stale, setup::Operation::uninstall);
  const fs::path expected_removal_source = removal.root / "state" / "repair-sources" /
      (std::string(64, 'd') + ".zip");
  require(setup::execute(uninstall_request) && stale.retain_calls == 0 &&
              stale.validate_calls == 0 && stale.validate_launcher_calls == 1 &&
              stale.apply_calls == std::array<int, 2>{1, 1} &&
              stale.apply_repair_sources ==
                  std::vector<fs::path>{expected_removal_source, expected_removal_source},
          "uninstall removes owned stale native effects without repair-package validation");
  Tree invalid_uninstall_cache{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-uninstall-cache"};
  fs::remove_all(invalid_uninstall_cache.root, ignored);
  fs::create_directories(invalid_uninstall_cache.root);
  Provider invalid_cache_provider; Native invalid_cache_native;
  invalid_cache_native.state = {setup::NativeOwnership::owned, setup::NativeOwnership::owned};
  invalid_cache_native.launcher_validation_fails = true;
  auto invalid_cache_request = request_for(
      invalid_uninstall_cache, invalid_cache_provider, &invalid_cache_native,
      setup::Operation::uninstall);
  auto invalid_cache_result = setup::execute(invalid_cache_request);
  const std::string invalid_cache_journal = active_journal(invalid_uninstall_cache);
  require(!invalid_cache_result &&
              invalid_cache_result.error().code == "self_setup_recovery_required" &&
              invalid_cache_provider.apply_calls == 0 &&
              invalid_cache_native.validate_launcher_calls == 1 &&
              invalid_cache_native.apply_calls == std::array<int, 2>{0, 0} &&
              string_member(invalid_cache_journal, "state") == "recovery_required" &&
              string_member(invalid_cache_journal, "recovery_boundary") ==
                  "maintenance_launcher_ownership_unproven",
          "uninstall persists invalid retained maintenance identity as recovery-required before provider effects");
  auto invalid_cache_retry = setup::execute(invalid_cache_request);
  require(!invalid_cache_retry &&
              invalid_cache_retry.error().code == "self_setup_recovery_required" &&
              invalid_cache_provider.apply_calls == 0 &&
              invalid_cache_native.validate_launcher_calls == 1,
          "invalid retained maintenance identity cannot be auto-abandoned on restart");
  Tree mismatched_uninstall{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-uninstall-source"};
  fs::remove_all(mismatched_uninstall.root, ignored);
  fs::create_directories(mismatched_uninstall.root);
  Provider mismatched_provider; Native mismatched_native;
  mismatched_provider.plan_source_digest = std::string(64, 'e');
  auto mismatched_uninstall_request = request_for(
      mismatched_uninstall, mismatched_provider, &mismatched_native,
      setup::Operation::uninstall);
  auto mismatched_uninstall_result = setup::execute(mismatched_uninstall_request);
  require(!mismatched_uninstall_result &&
              mismatched_uninstall_result.error().code == "self_setup_response_invalid" &&
              mismatched_provider.apply_calls == 0 &&
              mismatched_native.validate_launcher_calls == 0,
          "uninstall plan source must match authoritative installed-state inspection");
  require(string_member(active_journal(mismatched_uninstall), "state") == "abandoned",
          "proven pre-effect uninstall plan mismatch is durably retired");
  mismatched_provider.plan_source_digest = mismatched_provider.installed_source_digest;
  require(setup::execute(mismatched_uninstall_request) &&
              mismatched_provider.apply_calls == 1,
          "retired pre-effect uninstall mismatch permits a clean successor request");
  Tree invalid_inspection{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-uninstall-inspect"};
  fs::remove_all(invalid_inspection.root, ignored);
  fs::create_directories(invalid_inspection.root);
  Provider invalid_inspection_provider; Native invalid_inspection_native;
  invalid_inspection_provider.installed_envelope_valid = false;
  auto invalid_inspection_request = request_for(
      invalid_inspection, invalid_inspection_provider, &invalid_inspection_native,
      setup::Operation::uninstall);
  auto invalid_inspection_result = setup::execute(invalid_inspection_request);
  require(!invalid_inspection_result &&
              invalid_inspection_result.error().code == "self_setup_response_invalid" &&
              invalid_inspection_provider.apply_calls == 0 &&
              invalid_inspection_native.validate_launcher_calls == 0 &&
              string_member(active_journal(invalid_inspection), "state") == "abandoned",
          "malformed installed-state envelope is rejected and retired before provider effects");
  Tree refusal{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-refusal"};
  fs::remove_all(refusal.root, ignored); fs::create_directories(refusal.root);
  Provider refusal_provider; refusal_provider.foreign_content_refusal = true; Native refusal_native;
  auto refusal_request = request_for(refusal, refusal_provider, &refusal_native, setup::Operation::uninstall);
  require(!setup::execute(refusal_request), "exact foreign-content refusal is retained as the primary result");
  refusal_provider.foreign_content_refusal = false;
  Tree generic_refusal{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-generic-refusal"};
  fs::remove_all(generic_refusal.root, ignored); fs::create_directories(generic_refusal.root);
  Provider generic_provider; generic_provider.generic_provider_refusal = true; Native generic_native;
  auto generic_request = request_for(generic_refusal, generic_provider, &generic_native, setup::Operation::uninstall);
  require(!setup::execute(generic_request), "generic provider refusal remains uncertain");
  generic_provider.generic_provider_refusal = false;
  auto generic_retry = setup::execute(generic_request);
  require(!generic_retry && generic_retry.error().code == "self_setup_recovery_preview_required",
          "generic refusal cannot bypass reviewed recovery");
  Tree legacy_journal{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-legacy-journal"};
  fs::remove_all(legacy_journal.root, ignored); fs::create_directories(legacy_journal.root);
  std::ofstream(legacy_journal.root / "payload.zip", std::ios::binary) << "fixture";
  Provider legacy_provider; Native legacy_native;
  InterruptAt legacy_after_plan(setup::DurableBoundary::provider_plan_reviewed);
  auto legacy_request = request_for(legacy_journal, legacy_provider, &legacy_native);
  legacy_request.durable_boundary_hook = &legacy_after_plan;
  require(!setup::execute(legacy_request), "v2 fixture journal reaches provider plan boundary");
  const fs::path v2_legacy_path = active_journal_path(legacy_journal);
  const std::string v2_legacy_json = active_journal(legacy_journal);
  const std::string legacy_intent = sha256_text(
      string_member(v2_legacy_json, "operation") + "\n" +
      string_member(v2_legacy_json, "install_root_identity") + "\n" +
      string_member(v2_legacy_json, "product_version") + "\n" +
      string_member(v2_legacy_json, "mode") + "\n" +
      nested_string_member(v2_legacy_json, "provider", "source_digest") + "\n" +
      nested_string_member(v2_legacy_json, "provider", "state_root") + "\n" +
      nested_string_member(v2_legacy_json, "provider", "acceptance_root"));
  std::string v1_legacy_json = v2_legacy_json;
  const auto replace_once = [](std::string &value, const std::string &from,
                               const std::string &to) {
    const std::size_t offset = value.find(from);
    if (offset == std::string::npos) return false;
    value.replace(offset, from.size(), to);
    return true;
  };
  Tree legacy_generation_uninstall{
      fs::temp_directory_path() /
      "facman-self-setup-recovery-smoke-legacy-generation-uninstall"};
  fs::remove_all(legacy_generation_uninstall.root, ignored);
  fs::create_directories(legacy_generation_uninstall.root);
  Provider legacy_generation_provider;
  Native legacy_generation_native;
  InterruptAt legacy_generation_after_plan(
      setup::DurableBoundary::provider_plan_reviewed);
  auto legacy_generation_request = request_for(
      legacy_generation_uninstall, legacy_generation_provider,
      &legacy_generation_native, setup::Operation::uninstall);
  legacy_generation_request.install_id =
      "facman.self.generation." + std::string(64, 'b');
  legacy_generation_request.durable_boundary_hook =
      &legacy_generation_after_plan;
  require(!setup::execute(legacy_generation_request) &&
              nested_string_member(active_journal(legacy_generation_uninstall),
                                   "provider", "phase") == "plan_reviewed",
          "generation uninstall fixture reaches a durable pre-apply phase");
  const fs::path legacy_generation_path =
      active_journal_path(legacy_generation_uninstall);
  std::string legacy_generation_json =
      active_journal(legacy_generation_uninstall);
  const std::string legacy_generation_operation_id =
      string_member(legacy_generation_json, "operation_id");
  const std::string compact_generation_transaction = nested_string_member(
      legacy_generation_json, "provider", "transaction_id");
  const std::string direct_generation_transaction =
      "tx." + legacy_generation_operation_id;
  require(compact_generation_transaction != direct_generation_transaction &&
              replace_once(
                  legacy_generation_json,
                  "\"transaction_id\":\"" +
                      compact_generation_transaction + "\"",
                  "\"transaction_id\":\"" +
                      direct_generation_transaction + "\""),
          "pre-compaction generation uninstall fixture keeps its direct transaction");
  {
    std::ofstream output(legacy_generation_path,
                         std::ios::binary | std::ios::trunc);
    output << legacy_generation_json;
  }
  auto legacy_generation_resume = request_for(
      legacy_generation_uninstall, legacy_generation_provider,
      &legacy_generation_native, setup::Operation::uninstall);
  legacy_generation_resume.install_id = legacy_generation_request.install_id;
  require(setup::execute(legacy_generation_resume) &&
              legacy_generation_provider.apply_transaction_ids.size() == 1U &&
              legacy_generation_provider.apply_transaction_ids.front() ==
                  direct_generation_transaction,
          "pre-compaction generation uninstall resumes with its recorded transaction");
  const std::string v2_intent = string_member(v2_legacy_json, "intent_digest");
  require(replace_once(v1_legacy_json, "facman.setup_operation_journal.v2",
                       "facman.setup_operation_journal.v1") &&
              replace_once(v1_legacy_json,
                           "\"intent_digest\":\"" + v2_intent + "\"",
                           "\"intent_digest\":\"" + legacy_intent + "\"") &&
              replace_once(v1_legacy_json, ",\"install_id\":\"facman.self\"", ""),
          "legacy fixture conversion preserves the v1 journal shape");
  const std::string legacy_root_identity =
      string_member(v2_legacy_json, "install_root_identity");
  const fs::path v1_legacy_path = v2_legacy_path.parent_path() /
      ("facman.install." + legacy_root_identity.substr(0, 32) + "." +
       legacy_intent.substr(0, 32) + ".setup-operation.v1.json");
  { std::ofstream output(v2_legacy_path, std::ios::binary | std::ios::trunc); output << v1_legacy_json; }
  fs::rename(v2_legacy_path, v1_legacy_path, ignored);
  require(!ignored && setup::execute(request_for(legacy_journal, legacy_provider, &legacy_native)) &&
              string_member(active_journal(legacy_journal), "schema") ==
                  "facman.setup_operation_journal.v1" &&
              legacy_provider.command_install_ids.back() ==
                  std::pair<std::string, std::string>{"install_local.apply", "facman.self"},
          "legacy v1 journals resume with the implicit facman.self identity and old digest");
  Tree portable{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-portable"};
  fs::remove_all(portable.root, ignored); fs::create_directories(portable.root);
  std::ofstream(portable.root / "payload.zip", std::ios::binary) << "fixture";
  Provider portable_provider; Native portable_native;
  InterruptAt portable_after_files(setup::DurableBoundary::files_applied);
  auto portable_request = request_for(portable, portable_provider, nullptr);
  portable_request.durable_boundary_hook = &portable_after_files;
  auto portable_interrupted = setup::execute(portable_request);
  require(!portable_interrupted && portable_interrupted.error().code == "self_setup_interrupted" &&
              portable_native.apply_calls == std::array<int, 2>{0, 0},
          "portable files boundary interruption makes no native calls");
  const int portable_provider_calls = portable_provider.apply_calls;
  auto portable_retry = request_for(portable, portable_provider, &portable_native);
  require(setup::execute(portable_retry) && portable_native.apply_calls == std::array<int, 2>{0, 0} &&
              portable_provider.apply_calls == portable_provider_calls,
          "portable files-applied recovery ignores a newly supplied native adapter without provider replay");
}
} // namespace

int main() { cases(); std::cout << "PASS: " << checks << " self setup recovery checks\n"; }
