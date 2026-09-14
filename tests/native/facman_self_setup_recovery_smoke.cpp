// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_self_setup.h"
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

std::string sha256_text(const std::string &value) {
  return facman::base::sha256_hex_bytes(
      reinterpret_cast<const unsigned char *>(value.data()), value.size());
}

struct Provider final : setup::ProviderEffects {
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
  std::mutex apply_mutex;
  std::condition_variable apply_condition;
  std::string last_transaction_id;
  fs::path recovery_state_root;
  std::vector<std::string> apply_transaction_ids;
  fs::path test_coordinator_root() const override { return coordinator_root; }
  facman::core::Result<std::string> command(const std::string &name,
      const std::string &payload, const fs::path &state_root, const fs::path &, bool) override {
    if (name == "install_local.plan" || name == "repair.plan" || name == "uninstall.plan") {
      if (fail_plan) return facman::core::Result<std::string>::failure({"plan_refused", "injected pre-apply refusal", ""});
      const std::string id = name == "install_local.plan" ? string_member(payload, "request_id") :
          string_member(payload, "plan_id");
      return facman::core::Result<std::string>::success(
          "{\"status\":\"ok\",\"payload\":{\"plan_id\":\"" + id +
          "\",\"plan_digest\":\"" + std::string(64, 'a') + "\"}}");
    }
    if (name == "install_local.apply" || name == "repair.apply" || name == "uninstall.apply") {
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
  int lose_receipt = -1;
  int require_recovery = -1;
  setup::NativeOwnership inspect(const fs::path &install_root, setup::NativeEffect effect,
                                 const std::string &) override {
    const int index = static_cast<int>(effect);
    ++inspect_calls[index]; inspect_roots.push_back(install_root);
    return state[index];
  }
  setup::NativeResult apply(const fs::path &install_root, setup::NativeEffect effect,
                            setup::Operation operation, const std::string &) override {
    const int index = static_cast<int>(effect); ++apply_calls[index];
    apply_roots.push_back(install_root);
    state[index] = operation == setup::Operation::uninstall ? setup::NativeOwnership::absent : setup::NativeOwnership::owned;
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

setup::Request request_for(const Tree &tree, Provider &provider, Native *native,
                           setup::Operation operation = setup::Operation::install) {
  setup::Request request;
  request.operation = operation; request.install_root = tree.root / "install";
  request.state_root = tree.root / "state"; request.acceptance_root = tree.root;
  request.package = tree.root / "payload.zip"; request.product_version = "1.0.0";
  provider.coordinator_root = tree.root / "coordinator";
  request.apply = true; request.provider_effects = &provider; request.native_effects = native;
  return request;
}

void cases() {
  Tree tree{fs::temp_directory_path() / "facman-self-setup-recovery-smoke"};
  std::error_code ignored; fs::remove_all(tree.root, ignored); fs::create_directories(tree.root);
  std::ofstream(tree.root / "payload.zip", std::ios::binary) << "fixture";
  Provider provider; Native native;
  auto first = setup::execute(request_for(tree, provider, &native));
  require(first && native.apply_calls == std::array<int, 2>{1, 1}, "install applies injected native effects once");
  require(!fs::exists(tree.root / "state"), "coordinator does not pre-create the USK provider state root");
  require(fs::exists(tree.root / "coordinator"), "injected coordinator uses its isolated app-owned test root");
  auto repeated = setup::execute(request_for(tree, provider, &native));
  require(repeated && provider.apply_calls == 2, "completed attempt is archived and a later request has a fresh provider transaction");
  auto repair_request = request_for(tree, provider, &native, setup::Operation::repair);
  require(setup::execute(repair_request) && provider.apply_calls == 3,
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
  Tree files_boundary{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-files-boundary"};
  fs::remove_all(files_boundary.root, ignored); fs::create_directories(files_boundary.root);
  std::ofstream(files_boundary.root / "payload.zip", std::ios::binary) << "fixture";
  Provider files_provider; Native files_native;
  InterruptAt after_files(setup::DurableBoundary::files_applied);
  auto files_request = request_for(files_boundary, files_provider, &files_native);
  files_request.durable_boundary_hook = &after_files;
  auto files_interrupted = setup::execute(files_request);
  require(!files_interrupted && files_interrupted.error().code == "self_setup_interrupted" &&
              after_files.calls == 1 && files_native.apply_calls == std::array<int, 2>{0, 0},
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
              after_shortcut.calls == 2 && shortcut_native.apply_calls == std::array<int, 2>{1, 0},
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
  require(setup::execute(request_for(hosted_sequence, hosted_provider, &hosted_native,
                                     setup::Operation::uninstall)) &&
              hosted_native.apply_calls == std::array<int, 2>{2, 2},
          "hosted sequence completes uninstall before the fresh install");
  InterruptAt hosted_after_shortcut(setup::DurableBoundary::shortcut_applied);
  auto hosted_shortcut_request = request_for(hosted_sequence, hosted_provider, &hosted_native);
  hosted_shortcut_request.durable_boundary_hook = &hosted_after_shortcut;
  auto hosted_shortcut_interrupted = setup::execute(hosted_shortcut_request);
  require(!hosted_shortcut_interrupted &&
              hosted_shortcut_interrupted.error().code == "self_setup_interrupted" &&
              hosted_after_shortcut.calls == 2 &&
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
      hosted_root_identity + "\n" + hosted_operation) + ".setup-history.v1.json";
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
  require(!setup::execute(request_for(preapply, preapply_provider, &preapply_native)),
          "pre-apply plan refusal leaves a durable intent without an apply boundary");
  preapply_provider.fail_plan = false;
  auto changed_preapply = request_for(preapply, preapply_provider, &preapply_native, setup::Operation::repair);
  changed_preapply.product_version = "2.0.0";
  require(!setup::execute(changed_preapply),
          "a no-plan intent is retired before the changed request can begin");
  require(setup::execute(changed_preapply) && preapply_provider.apply_calls == 1,
          "the next invocation starts the changed request after pre-apply retirement");
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
  Tree adapter{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-adapter"};
  fs::remove_all(adapter.root, ignored); fs::create_directories(adapter.root);
  std::ofstream(adapter.root / "payload.zip", std::ios::binary) << "fixture";
  Provider adapter_provider; Native substituted; substituted.require_recovery = 0;
  auto substituted_result = setup::execute(request_for(adapter, adapter_provider, &substituted));
  require(!substituted_result && substituted_result.error().code == "self_setup_recovery_required",
          "adapter mutation-edge substitution propagates recovery_required");
  Tree removal{fs::temp_directory_path() / "facman-self-setup-recovery-smoke-uninstall"};
  fs::remove_all(removal.root, ignored); fs::create_directories(removal.root);
  Provider removal_provider; Native stale; stale.state = {setup::NativeOwnership::owned_stale, setup::NativeOwnership::owned_stale};
  auto uninstall_request = request_for(removal, removal_provider, &stale, setup::Operation::uninstall);
  require(setup::execute(uninstall_request) && stale.apply_calls == std::array<int, 2>{1, 1},
          "uninstall removes owned stale native effects after provider file removal");
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
