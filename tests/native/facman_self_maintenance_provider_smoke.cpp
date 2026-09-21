// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_self_maintenance_provider.h"

#include "fl_json.h"
#include "fl_file_io.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"

#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <tuple>
#include <vector>

namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace maintenance = facman::self_maintenance;

namespace {

std::string member(const std::string &text, const char *key) {
  auto value = json::parse(text);
  const json::Value *field = value ? value.value().find(key) : nullptr;
  return field != nullptr && field->string_value()
      ? field->string_value().value() : std::string();
}

std::string nested(const std::string &text, const char *object,
                   const char *key) {
  auto value = json::parse(text);
  const json::Value *parent = value ? value.value().find(object) : nullptr;
  const json::Value *field = parent != nullptr ? parent->find(key) : nullptr;
  return field != nullptr && field->string_value()
      ? field->string_value().value() : std::string();
}

struct Clock final : facman::self_setup::Clock {
  unsigned int second = 0;
  std::string after(const std::string &) override {
    ++second;
    return "2027-01-01T00:00:" +
        std::string(second < 10U ? "0" : "") + std::to_string(second) + "Z";
  }
};

struct Provider final : facman::self_setup::ProviderEffects {
  maintenance::Plan expected;
  bool refuse_plan = false;
  bool replay_plan = false;
  bool empty_apply_payload = false;
  bool wrong_apply_transaction = false;
  bool wrong_recipe = false;
  bool wrong_verify_report = false;
  bool stale_verify_time = false;
  bool wrong_verify_ownership = false;
  bool bad_verify_summary = false;
  bool wrong_verify_digest = false;
  bool alternate_allowed_effect = false;
  bool alternate_plan_digest = false;
  bool add_response_padding = false;
  std::string last_plan_created_at;
  std::string last_plan_digest;
  std::string last_plan_response;
  std::string transaction_id;
  std::string inspected_state_digest;
  std::string ownership_digest = std::string(64, '2');
  std::string last_verification_digest = std::string(64, '1');
  std::string last_verification_status = "pass";
  std::vector<std::string> commands;

  std::string recipe_digest() const {
    json::ObjectBuilder identity;
    identity.add_string("schema", "facman.self_setup_recipe.v1");
    identity.add_string("product_id", "facman");
    identity.add_string("product_version", expected.target.product_version);
    identity.add_string("provider_revision",
                        facman::self_setup::provider_revision());
    identity.add_string("source_sha256", expected.target.package_sha256);
    identity.add_string("target_layout",
                        "versioned_generation_with_maintenance_v1");
    const std::string bytes = identity.serialize();
    return facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char *>(bytes.data()), bytes.size());
  }

  json::ObjectBuilder installed(const std::string &transaction) {
    json::ArrayBuilder components;
    components.add_string("facman.product");
    components.add_string("facman.maintenance");
    json::ArrayBuilder entrypoints;
    for (const auto &entry : std::vector<std::tuple<std::string, std::string,
                                                   std::string>>{
             {"facman.gui", "application", "generations/" +
                  expected.target.product_version + "/FacMan.exe"},
             {"facman.cli", "tool", "generations/" +
                  expected.target.product_version + "/bin/facman.exe"},
             {"facman.setup", "tool", "maintenance/FacManSetup.exe"}}) {
      json::ObjectBuilder item;
      item.add_string("entrypoint_id", std::get<0>(entry));
      item.add_string("kind", std::get<1>(entry));
      item.add_string("relative_path", std::get<2>(entry));
      entrypoints.add_object(item);
    }
    json::ObjectBuilder verification;
    verification.add_string("report_digest", last_verification_digest);
    verification.add_string("report_id", "report.previous");
    verification.add_string("status", last_verification_status);
    verification.add_string("verified_at", "2026-09-16T00:00:00Z");
    json::ObjectBuilder abi;
    abi.add_unsigned_integer("major", 1U);
    abi.add_unsigned_integer("minor", 0U);
    abi.add_string("provider_revision",
                   facman::self_setup::provider_revision());
    json::ObjectBuilder value;
    value.add_string("audit_chain_id", "audit.maintenance");
    value.add_array("component_selection", components);
    value.add_string("created_at", "2026-09-16T00:00:00Z");
    value.add_array("entrypoints", entrypoints);
    value.add_string("install_id", expected.target.install_id);
    value.add_object("last_verification", verification);
    value.add_string("lifecycle_status", "installed");
    value.add_string("ownership_manifest_digest", ownership_digest);
    value.add_string("ownership_manifest_ref", "ownership/test.json");
    value.add_string("product_id", "facman");
    value.add_string("product_version", expected.target.product_version);
    value.add_string("recipe_digest", wrong_recipe
        ? std::string(64, '4') : recipe_digest());
    value.add_string("schema", "usk.installed_state.v1");
    value.add_object("setup_abi", abi);
    value.add_string("source_archive_digest", expected.target.package_sha256);
    value.add_string("target_root",
        facman::platform::path_to_utf8(expected.target.install_root));
    value.add_string("target_scope", "portable");
    value.add_string("transaction_id", transaction);
    return value;
  }

  std::string envelope(json::ObjectBuilder &payload) {
    json::ObjectBuilder result;
    result.add_null("error");
    result.add_object("payload", payload);
    result.add_string("schema", "usk.command_response.v1");
    result.add_string("status", "ok");
    return result.serialize();
  }

  facman::core::Result<std::string> command(
      const std::string &name, const std::string &payload,
      const fs::path &, const fs::path &, bool) override {
    commands.push_back(name);
    if (name == "install_local.plan") {
      if (refuse_plan)
        return facman::core::Result<std::string>::failure(
            {"refused", "injected plan refusal", ""});
      const std::string request_id = member(payload, "request_id");
      last_plan_created_at = member(payload, "created_at");
      if (member(payload, "install_id") != expected.target.install_id ||
          nested(payload, "target", "root") !=
              facman::platform::path_to_utf8(expected.target.install_root) ||
          nested(payload, "archive", "expected_sha256") !=
              expected.package_sha256)
        return facman::core::Result<std::string>::failure(
            {"wrong_plan", "maintenance plan identity differs", ""});
      json::ObjectBuilder input;
      input.add_string("policy_digest", std::string(64, '9'));
      input.add_string("provider_revision",
                       facman::self_setup::provider_revision());
      input.add_string("recipe_digest", nested(payload, "recipe", "recipe_digest"));
      input.add_string("source_digest", expected.package_sha256);
      json::ObjectBuilder source;
      source.add_string("filesystem_identity_digest", std::string(64, '8'));
      source.add_string("path", facman::platform::path_to_utf8(expected.package));
      source.add_string("path_identity_digest", std::string(64, '7'));
      source.add_string("sha256", expected.package_sha256);
      source.add_unsigned_integer("size_bytes", 7U);
      source.add_string("source_id", "source." + expected.target.install_id);
      json::ObjectBuilder capabilities;
      capabilities.add_bool("local", true);
      capabilities.add_bool("no_mount_redirection", true);
      capabilities.add_bool("no_replace_commit", true);
      capabilities.add_bool("stable_ancestors", true);
      json::ObjectBuilder filesystem;
      filesystem.add_object("capabilities", capabilities);
      filesystem.add_string("identity_digest", std::string(64, '6'));
      filesystem.add_string("kind", "ntfs");
      json::ObjectBuilder target;
      target.add_string("classification", "operator_selected_owned_target");
      target.add_object("filesystem", filesystem);
      target.add_string("identity_digest", std::string(64, '5'));
      target.add_bool("must_not_exist", true);
      target.add_string("path_identity_digest", std::string(64, '4'));
      target.add_string("pre_snapshot_digest", std::string(64, '3'));
      target.add_string("root", facman::platform::path_to_utf8(
          replay_plan ? expected.target.install_root.parent_path()
                      : expected.target.install_root));
      target.add_string("scope", "portable");
      target.add_string("volume_id", std::string(64, '6'));
      json::ArrayBuilder components;
      components.add_string("facman.product");
      components.add_string("facman.maintenance");
      json::ObjectBuilder entry;
      entry.add_string("entry_type", "file");
      entry.add_string("relative_path", "FacMan.exe");
      entry.add_string("sha256", std::string(64, '2'));
      entry.add_unsigned_integer("size_bytes", 1U);
      json::ArrayBuilder entries;
      entries.add_object(entry);
      json::ObjectBuilder effect;
      effect.add_string("effect_id", "effect.0");
      effect.add_string("kind", "write_file");
      effect.add_string("relative_path", alternate_allowed_effect
          ? "FacMan-revised.exe" : "FacMan.exe");
      effect.add_string("root_class", "owned_target");
      json::ArrayBuilder effects;
      effects.add_object(effect);
      json::ObjectBuilder totals;
      totals.add_unsigned_integer("directory_count", 0U);
      totals.add_unsigned_integer("file_count", 1U);
      totals.add_unsigned_integer("uncompressed_bytes", 1U);
      json::ArrayBuilder invalidations;
      invalidations.add_string("source");
      invalidations.add_string("recipe");
      invalidations.add_string("target");
      invalidations.add_string("policy");
      invalidations.add_string("provider_revision");
      json::ObjectBuilder revalidation;
      revalidation.add_bool("immediately_before_apply", true);
      revalidation.add_array("invalidate_on", invalidations);
      json::ObjectBuilder refusal;
      refusal.add_bool("refuse_elevation", true);
      refusal.add_bool("refuse_existing_target", true);
      refusal.add_bool("refuse_installer_execution", true);
      refusal.add_bool("refuse_network", true);
      refusal.add_bool("refuse_package_manager", true);
      refusal.add_bool("refuse_registry", true);
      json::ObjectBuilder plan;
      plan.add_array("component_selection", components);
      plan.add_string("created_at", member(payload, "created_at"));
      plan.add_array("effects", effects);
      plan.add_object("input_identity", input);
      plan.add_string("operation", "install_local");
      last_plan_digest = std::string(64, alternate_plan_digest ? 'b' : 'a');
      plan.add_string("plan_digest", last_plan_digest);
      plan.add_string("plan_id", request_id);
      plan.add_array("planned_entries", entries);
      plan.add_object("refusal_policy", refusal);
      plan.add_object("revalidation", revalidation);
      plan.add_string("schema", "usk.install_plan.v1");
      plan.add_object("source", source);
      plan.add_string("status", "planned");
      plan.add_object("target", target);
      plan.add_object("totals", totals);
      std::string response = envelope(plan);
      if (add_response_padding) response += "\n";
      last_plan_response = response;
      return facman::core::Result<std::string>::success(std::move(response));
    }
    if (name == "install_local.apply") {
      if (empty_apply_payload)
        return facman::core::Result<std::string>::success(
            "{\"error\":null,\"payload\":{},\"schema\":"
            "\"usk.command_response.v1\",\"status\":\"ok\"}");
      transaction_id = member(payload, "transaction_id");
      auto value = installed(wrong_apply_transaction
          ? "tx.replayed" : transaction_id);
      return facman::core::Result<std::string>::success(envelope(value));
    }
    if (name == "installed.inspect") {
      auto value = installed(transaction_id.empty()
          ? "tx.maintenance.existing" : transaction_id);
      const std::string installed_bytes = value.serialize();
      auto parsed_installed = json::parse(installed_bytes);
      json::ObjectBuilder digest_projection;
      for (const char *key : {
               "audit_chain_id", "component_selection", "created_at",
               "entrypoints", "install_id", "lifecycle_status",
               "ownership_manifest_digest", "ownership_manifest_ref",
               "product_id", "product_version", "recipe_digest", "setup_abi",
               "source_archive_digest", "target_root", "target_scope",
               "transaction_id"})
        digest_projection.add_value(key, *parsed_installed.value().find(key));
      auto parsed_projection = json::parse(digest_projection.serialize());
      auto canonical_installed = parsed_projection
          ? json::canonical_integer_json(parsed_projection.value())
          : facman::core::Result<std::string>::failure(
                {"test", "installed fixture could not be parsed", ""});
      inspected_state_digest = facman::base::sha256_hex_bytes(
          reinterpret_cast<const unsigned char *>(
              canonical_installed.value().data()),
          canonical_installed.value().size());
      return facman::core::Result<std::string>::success(envelope(value));
    }
    if (name == "installed.verify") {
      json::ArrayBuilder empty;
      json::ObjectBuilder summary;
      summary.add_unsigned_integer("owned_files", bad_verify_summary ? 1U : 0U);
      summary.add_unsigned_integer("missing_files", 0U);
      summary.add_unsigned_integer("modified_files", 0U);
      summary.add_unsigned_integer("unknown_paths", 0U);
      const std::string report_id = wrong_verify_report
          ? "report.replayed" : member(payload, "report_id");
      const std::string verified_at = stale_verify_time
          ? "2026-09-15T00:00:00Z" : member(payload, "verified_at");
      const std::string report_ownership = wrong_verify_ownership
          ? std::string(64, '5') : ownership_digest;
      json::ObjectBuilder report_projection;
      report_projection.add_array("directories", empty);
      report_projection.add_array("files", empty);
      report_projection.add_string("install_id", expected.target.install_id);
      report_projection.add_string("installed_state_digest",
                                   inspected_state_digest);
      report_projection.add_string("ownership_manifest_digest",
                                   report_ownership);
      report_projection.add_string("report_id", report_id);
      report_projection.add_string("status", "pass");
      report_projection.add_object("summary", summary);
      report_projection.add_array("unknown_paths", empty);
      report_projection.add_string("verified_at", verified_at);
      auto projection = json::parse(report_projection.serialize());
      auto canonical = json::canonical_integer_json(projection.value());
      const std::string report_digest = facman::base::sha256_hex_bytes(
          reinterpret_cast<const unsigned char *>(canonical.value().data()),
          canonical.value().size());
      json::ObjectBuilder report;
      report.add_array("directories", empty);
      report.add_array("files", empty);
      report.add_string("install_id", expected.target.install_id);
      report.add_string("installed_state_digest", inspected_state_digest);
      report.add_string("ownership_manifest_digest", report_ownership);
      report.add_string("report_digest", wrong_verify_digest
          ? std::string(64, '6') : report_digest);
      report.add_string("report_id", report_id);
      report.add_string("schema", "usk.verification_report.v1");
      report.add_string("status", "pass");
      report.add_object("summary", summary);
      report.add_array("unknown_paths", empty);
      report.add_string("verified_at", verified_at);
      json::ObjectBuilder envelope;
      envelope.add_null("error");
      envelope.add_object("payload", report);
      envelope.add_string("schema", "usk.command_response.v1");
      envelope.add_string("status", "ok");
      return facman::core::Result<std::string>::success(envelope.serialize());
    }
    return facman::core::Result<std::string>::failure(
        {"unexpected", "unexpected provider command", name});
  }
};

bool require(bool condition, const char *message) {
  if (!condition) std::cerr << message << '\n';
  return condition;
}

} // namespace

int main() {
  const fs::path root = fs::temp_directory_path() /
      ("facman-provider-bridge-" + std::to_string(
          static_cast<unsigned long long>(std::chrono::steady_clock::now()
                                              .time_since_epoch().count())));
  fs::create_directories(root / "state");
  maintenance::Plan plan;
  plan.operation = "update";
  plan.operation_id = "maintenance.provider.smoke";
  plan.package = root / "package.zip";
  plan.package_sha256 = std::string(64, 'a');
  plan.provider_operation = "install_local";
  plan.target.generation_id = std::string(64, 'b');
  plan.target.product_version = "0.1.0-alpha.6";
  plan.target.package_sha256 = plan.package_sha256;
  plan.target.facman_source_revision = std::string(40, 'c');
  plan.target.universal_setup_revision =
      facman::self_setup::provider_revision();
  plan.target.install_id =
      "facman.self.generation." + plan.target.generation_id;
  plan.target.install_root = root / "generation";
  plan.target.logical_root = root / "FacMan";
  plan.target.state_root = root / "state";
  plan.target.acceptance_root = root;
  plan.target.gui = plan.target.install_root / "generations" /
      plan.target.product_version / "FacMan.exe";
  plan.target.maintenance_launcher =
      plan.target.install_root / "maintenance" / "FacManSetup.exe";
  std::ofstream(plan.package, std::ios::binary) << "package";

  Provider effects;
  effects.expected = plan;
  Clock clock;
  maintenance::ProviderBridge bridge(root / "state", root, &effects, &clock);
  bool ok = true;
  const auto prepared = bridge.review_install_local(plan);
  const auto prepared_retry = bridge.review_install_local(plan);
  Provider restarted_effects;
  restarted_effects.expected = plan;
  // A restart receives a newly serialized response (and may receive a new
  // created_at); its provider byte digest is intentionally different although
  // every validated effect semantic is identical.
  restarted_effects.alternate_plan_digest = true;
  restarted_effects.add_response_padding = true;
  maintenance::ProviderBridge restarted_bridge(
      root / "state", root, &restarted_effects, &clock);
  const auto restarted_prepared = restarted_bridge.review_install_local(plan);
  Provider changed_effect_effects;
  changed_effect_effects.expected = plan;
  changed_effect_effects.alternate_allowed_effect = true;
  changed_effect_effects.alternate_plan_digest = true;
  maintenance::ProviderBridge changed_effect_bridge(
      root / "state", root, &changed_effect_effects, &clock);
  const auto changed_effect_prepared = changed_effect_bridge.review_install_local(plan);
  const fs::path retained_package = root / "state" / "epoch-handoff" /
      "maintenance.provider.smoke" / "package.zip";
  fs::create_directories(retained_package.parent_path());
  fs::copy_file(plan.package, retained_package,
                fs::copy_options::overwrite_existing);
  auto retained_plan = plan;
  retained_plan.package = retained_package;
  Provider retained_final_effects;
  retained_final_effects.expected = retained_plan;
  maintenance::ProviderBridge retained_final_bridge(
      root / "state", root, &retained_final_effects, &clock);
  const auto retained_final_prepared = retained_final_bridge.review_install_local(retained_plan);
  Provider retained_staging_effects;
  retained_staging_effects.expected = retained_plan;
  maintenance::ProviderBridge retained_staging_bridge(
      root / "state", root, &retained_staging_effects, &clock);
  const auto retained_staging_prepared = retained_staging_bridge.review_install_local(retained_plan);
  ok &= require(prepared.ok, "install_local plan was not prepared");
  ok &= require(prepared_retry.ok && restarted_prepared.ok &&
                    changed_effect_prepared.ok &&
                    retained_final_prepared.ok && retained_staging_prepared.ok &&
                    prepared.receipt_sha256 == prepared_retry.receipt_sha256 &&
                    prepared.receipt_sha256 == restarted_prepared.receipt_sha256 &&
                    retained_final_prepared.receipt_sha256 ==
                        retained_staging_prepared.receipt_sha256 &&
                    prepared.receipt_sha256 != retained_final_prepared.receipt_sha256,
                "provider review receipt was not stable across retry/restart or distinct by retained path");
  ok &= require(!effects.last_plan_created_at.empty() &&
                    !restarted_effects.last_plan_created_at.empty() &&
                    effects.last_plan_created_at != restarted_effects.last_plan_created_at &&
                    effects.last_plan_digest != restarted_effects.last_plan_digest &&
                    effects.last_plan_response != restarted_effects.last_plan_response &&
                    prepared.receipt_sha256 != changed_effect_prepared.receipt_sha256,
                "provider review receipt did not bind a changed allowed effect for handoff retry refusal");
  const auto bound = bridge.bind_install_local(plan, prepared.receipt_sha256);
  Provider fresh_binding_effects;
  fresh_binding_effects.expected = plan;
  maintenance::ProviderBridge fresh_binding_bridge(
      root / "state", root, &fresh_binding_effects, &clock);
  const auto rehydrated = bound
      ? fresh_binding_bridge.rehydrate_install_local(plan, bound.value())
      : facman::core::Result<void>::failure({"test", "binding unavailable", {}});
  const auto bound_applied = rehydrated
      ? fresh_binding_bridge.apply_bound_install_local(plan, bound.value())
      : maintenance::EffectResult{false, false, {}, "rehydration failed"};
  const auto bound_inspected = bound_applied.ok
      ? fresh_binding_bridge.inspect_installed(plan, bound.value())
      : maintenance::EffectResult{false, false, {}, "bound apply failed"};
  const auto terminal_verified = bound_applied.ok
      ? fresh_binding_bridge.validate_terminal_verification(
          plan, bound.value(), std::string(64, '1'))
      : maintenance::EffectResult{false, false, {}, "bound apply failed"};
  auto wrong_terminal_transaction = bound ? bound.value() : maintenance::ProviderApplyBinding{};
  wrong_terminal_transaction.transaction_id = "tx.m.wrong";
  const auto terminal_wrong_transaction = bound_applied.ok
      ? fresh_binding_bridge.validate_terminal_verification(
          plan, wrong_terminal_transaction, std::string(64, '1'))
      : maintenance::EffectResult{true, false, {}, {}};
  Provider terminal_status_effects;
  terminal_status_effects.expected = plan;
  terminal_status_effects.transaction_id = bound ? bound.value().transaction_id : std::string();
  terminal_status_effects.last_verification_status = "warn";
  maintenance::ProviderBridge terminal_status_bridge(root / "state", root,
                                                       &terminal_status_effects, &clock);
  const auto terminal_wrong_status = bound
      ? terminal_status_bridge.validate_terminal_verification(plan, bound.value(),
                                                               std::string(64, '1'))
      : maintenance::EffectResult{true, false, {}, {}};
  Provider terminal_digest_effects;
  terminal_digest_effects.expected = plan;
  terminal_digest_effects.transaction_id = bound ? bound.value().transaction_id : std::string();
  terminal_digest_effects.last_verification_digest = std::string(64, '8');
  maintenance::ProviderBridge terminal_digest_bridge(root / "state", root,
                                                       &terminal_digest_effects, &clock);
  const auto terminal_wrong_digest = bound
      ? terminal_digest_bridge.validate_terminal_verification(plan, bound.value(),
                                                               std::string(64, '1'))
      : maintenance::EffectResult{true, false, {}, {}};
  const auto rejects_cached_binding_mutation = [&](auto mutate) {
    if (!bound) return false;
    Provider mutation_effects;
    mutation_effects.expected = plan;
    maintenance::ProviderBridge mutation_bridge(root / "state", root,
                                                  &mutation_effects, &clock);
    if (!mutation_bridge.rehydrate_install_local(plan, bound.value())) return false;
    auto altered = bound.value();
    mutate(altered);
    const auto rejected = mutation_bridge.apply_bound_install_local(plan, altered);
    return !rejected.ok && mutation_effects.commands ==
        std::vector<std::string>{"install_local.plan"};
  };
  const bool all_cached_binding_fields_refused =
      rejects_cached_binding_mutation([](auto &value) { value.provider_plan_sha256[0] = '0'; }) &&
      rejects_cached_binding_mutation([](auto &value) { value.transaction_id += ".x"; }) &&
      rejects_cached_binding_mutation([](auto &value) { value.apply_sha256[0] = '0'; }) &&
      rejects_cached_binding_mutation([](auto &value) { value.apply_payload += "x"; }) &&
      rejects_cached_binding_mutation([](auto &value) { value.semantic_digest[0] = '0'; }) &&
      rejects_cached_binding_mutation([](auto &value) { value.bridge_key[0] = '0'; }) &&
      rejects_cached_binding_mutation([](auto &value) { value.reviewed_plan_id += ".x"; }) &&
      rejects_cached_binding_mutation([](auto &value) { value.reviewed_plan_digest[0] = '0'; }) &&
      rejects_cached_binding_mutation([](auto &value) { value.plan_created_at = "2026-01-01T00:00:00Z"; }) &&
      rejects_cached_binding_mutation([](auto &value) { value.request_id += ".x"; });
  auto tampered_binding = bound ? bound.value() : maintenance::ProviderApplyBinding{};
  tampered_binding.apply_payload += "x";
  Provider tampered_binding_effects;
  tampered_binding_effects.expected = plan;
  maintenance::ProviderBridge tampered_binding_bridge(
      root / "state", root, &tampered_binding_effects, &clock);
  auto foreign_binding = bound ? bound.value() : maintenance::ProviderApplyBinding{};
  foreign_binding.bridge_key = std::string(64, 'f');
  Provider foreign_binding_effects;
  foreign_binding_effects.expected = plan;
  maintenance::ProviderBridge foreign_binding_bridge(
      root / "state", root, &foreign_binding_effects, &clock);
  ok &= require(bound && rehydrated && bound_applied.ok && bound_inspected.ok &&
                    terminal_verified.ok && !terminal_wrong_transaction.ok &&
                    !terminal_wrong_status.ok && !terminal_wrong_digest.ok &&
                    all_cached_binding_fields_refused &&
                    terminal_status_effects.commands == std::vector<std::string>{"installed.inspect"} &&
                    terminal_digest_effects.commands == std::vector<std::string>{"installed.inspect"} &&
                    fresh_binding_effects.commands == std::vector<std::string>{
                        "install_local.plan", "install_local.apply", "installed.inspect",
                        "installed.inspect", "installed.inspect"} &&
                    !tampered_binding_bridge.rehydrate_install_local(plan, tampered_binding) &&
                    tampered_binding_effects.commands.empty() &&
                    !foreign_binding_bridge.rehydrate_install_local(plan, foreign_binding) &&
                    foreign_binding_effects.commands.empty(),
                "fresh bridge did not exactly rehydrate or refuse a foreign provider binding");
  Provider alternate_binding_effects;
  alternate_binding_effects.expected = plan;
  alternate_binding_effects.alternate_allowed_effect = true;
  maintenance::ProviderBridge alternate_binding_bridge(
      root / "state", root, &alternate_binding_effects, &clock);
  const auto alternate_binding = alternate_binding_bridge.bind_install_local(
      plan, alternate_binding_bridge.review_install_local(plan).receipt_sha256);
  auto mixed_binding = alternate_binding ? alternate_binding.value()
                                         : maintenance::ProviderApplyBinding{};
  if (bound) {
    mixed_binding.provider_plan_sha256 = bound.value().provider_plan_sha256;
    mixed_binding.semantic_digest = bound.value().semantic_digest;
  }
  Provider mixed_binding_effects;
  mixed_binding_effects.expected = plan;
  mixed_binding_effects.alternate_allowed_effect = true;
  maintenance::ProviderBridge mixed_binding_bridge(
      root / "state", root, &mixed_binding_effects, &clock);
  ok &= require(alternate_binding && bound &&
                    !mixed_binding_bridge.rehydrate_install_local(plan, mixed_binding) &&
                    mixed_binding_effects.commands == std::vector<std::string>{"install_local.plan"},
                "mixed provider semantic digest and alternate allowed effect reached apply");
  const auto restarted_applied = restarted_bridge.install_local(plan);
  ok &= require(restarted_applied.ok,
                "fresh bridge did not retain its exact reviewed apply payload");
  const auto applied = bridge.install_local(plan);
  ok &= require(applied.ok, "reviewed install_local plan was not applied");
  const auto inspected = bridge.inspect_installed(plan);
  ok &= require(inspected.ok, "installed state was not validated");
  const auto verified = bridge.verify_installed(plan);
  ok &= require(verified.ok, "installed files were not verified");
  ok &= require(std::none_of(effects.commands.begin(), effects.commands.end(),
                    [](const std::string &command) {
                      return command.rfind("update.", 0) == 0;
                    }),
                "provider bridge invoked whole-root update authority");
  ok &= require(effects.commands == std::vector<std::string>{
                    "install_local.plan", "install_local.apply",
                    "installed.inspect", "installed.verify"},
                "provider bridge command surface changed");

  Provider refusal;
  refusal.expected = plan;
  refusal.refuse_plan = true;
  maintenance::ProviderBridge refused(root / "state", root, &refusal, &clock);
  ok &= require(!refused.review_install_local(plan).ok &&
                    refusal.commands ==
                        std::vector<std::string>{"install_local.plan"},
                "plan refusal crossed the provider apply boundary");

  const fs::path accepted = root / "accepted";
  const fs::path outside = root / "outside";
  fs::create_directories(accepted);
  fs::create_directories(outside);
  auto outside_plan = plan;
  outside_plan.target.acceptance_root = accepted;
  outside_plan.target.state_root = outside;
  Provider outside_effects;
  outside_effects.expected = outside_plan;
  maintenance::ProviderBridge outside_bridge(
      outside, accepted, &outside_effects, &clock);
  ok &= require(!outside_bridge.review_install_local(outside_plan).ok &&
                    outside_effects.commands.empty() &&
                    fs::is_empty(outside),
                "out-of-authority provider roots produced effects");

  Provider replay;
  replay.expected = plan;
  replay.replay_plan = true;
  maintenance::ProviderBridge replayed(root / "state", root, &replay, &clock);
  ok &= require(!replayed.review_install_local(plan).ok,
                "replayed plan target identity was accepted");

  Provider empty_apply;
  empty_apply.expected = plan;
  empty_apply.empty_apply_payload = true;
  maintenance::ProviderBridge empty_bridge(
      root / "state", root, &empty_apply, &clock);
  ok &= require(empty_bridge.review_install_local(plan).ok &&
                    !empty_bridge.install_local(plan).ok,
                "empty apply payload was accepted");

  Provider wrong_transaction;
  wrong_transaction.expected = plan;
  wrong_transaction.wrong_apply_transaction = true;
  maintenance::ProviderBridge transaction_bridge(
      root / "state", root, &wrong_transaction, &clock);
  ok &= require(transaction_bridge.review_install_local(plan).ok &&
                    !transaction_bridge.install_local(plan).ok,
                "mismatched apply transaction was accepted");

  Provider wrong_apply_recipe;
  wrong_apply_recipe.expected = plan;
  wrong_apply_recipe.wrong_recipe = true;
  maintenance::ProviderBridge apply_recipe_bridge(
      root / "state", root, &wrong_apply_recipe, &clock);
  ok &= require(apply_recipe_bridge.review_install_local(plan).ok &&
                    !apply_recipe_bridge.install_local(plan).ok,
                "mismatched apply recipe was accepted");

  Provider wrong_inspect_recipe;
  wrong_inspect_recipe.expected = plan;
  wrong_inspect_recipe.wrong_recipe = true;
  maintenance::ProviderBridge inspect_recipe_bridge(
      root / "state", root, &wrong_inspect_recipe, &clock);
  ok &= require(!inspect_recipe_bridge.inspect_installed(plan).ok,
                "mismatched installed recipe was accepted");

  for (int mutation = 0; mutation < 5; ++mutation) {
    Provider invalid;
    invalid.expected = plan;
    invalid.wrong_verify_report = mutation == 0;
    invalid.stale_verify_time = mutation == 1;
    invalid.wrong_verify_ownership = mutation == 2;
    invalid.bad_verify_summary = mutation == 3;
    invalid.wrong_verify_digest = mutation == 4;
    maintenance::ProviderBridge invalid_bridge(
        root / "state", root, &invalid, &clock);
    ok &= require(invalid_bridge.inspect_installed(plan).ok &&
                      !invalid_bridge.verify_installed(plan).ok,
                  "mismatched verification response was accepted");
  }
  std::error_code ignored;
  fs::remove_all(root, ignored);
  return ok ? 0 : 1;
}
