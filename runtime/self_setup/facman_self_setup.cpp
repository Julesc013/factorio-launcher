// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_self_setup.h"

#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_sha256.h"
#include "usk/usk_api.h"

#include <atomic>
#include <chrono>
#include <ctime>
#include <filesystem>
#include <iomanip>
#include <sstream>
#include <system_error>
#include <thread>

#ifndef FACMAN_SELF_SETUP_PROVIDER_REVISION
#define FACMAN_SELF_SETUP_PROVIDER_REVISION "unknown"
#endif

namespace fs = std::filesystem;
namespace json = facman::core::json;

namespace facman::self_setup {
namespace {

std::atomic<unsigned long long> sequence{0};

facman::core::Error error(std::string code, std::string message,
                          std::string detail = {}) {
  facman::core::Error result{std::move(code), std::move(message), ""};
  result.detail = std::move(detail);
  return result;
}

facman::core::Result<fs::path> absolute_path(const fs::path &value,
                                             const char *field) {
  if (value.empty()) {
    return facman::core::Result<fs::path>::failure(
        error("self_setup_input_missing", std::string(field) + " is required"));
  }
  std::error_code status;
  const fs::path absolute = fs::absolute(value, status);
  if (status || !absolute.is_absolute()) {
    return facman::core::Result<fs::path>::failure(
        error("self_setup_path_invalid",
              std::string(field) + " is not an absolute usable path"));
  }
  return facman::core::Result<fs::path>::success(absolute.lexically_normal());
}

std::string timestamp() {
  const std::time_t now = std::time(nullptr);
  std::tm utc{};
#ifdef _WIN32
  gmtime_s(&utc, &now);
#else
  gmtime_r(&now, &utc);
#endif
  std::ostringstream output;
  output << std::put_time(&utc, "%Y-%m-%dT%H:%M:%SZ");
  return output.str();
}

std::string timestamp_after(const std::string &lower_bound) {
  for (;;) {
    const std::string current = timestamp();
    if (current > lower_bound)
      return current;
    std::this_thread::sleep_for(std::chrono::milliseconds(25));
  }
}

std::string identifier(const char *prefix) {
  const auto ticks =
      std::chrono::steady_clock::now().time_since_epoch().count();
  const auto index = sequence.fetch_add(1, std::memory_order_relaxed);
  std::ostringstream output;
  output << prefix << '.' << ticks << '.' << index;
  return output.str();
}

std::string string_field(const json::Value &object, const char *key) {
  const json::Value *value = object.find(key);
  if (value == nullptr)
    return {};
  auto decoded = value->string_value();
  return decoded ? decoded.take_value() : std::string();
}

facman::core::Result<std::string> command(const std::string &name,
                                          const std::string &payload,
                                          const fs::path &state_root,
                                          const fs::path &acceptance_root,
                                          bool dry_run) {
  const std::string state = facman::platform::path_to_utf8(state_root);
  const std::string acceptance =
      facman::platform::path_to_utf8(acceptance_root);
  usk_config_v1 config{};
  config.struct_size = sizeof(config);
  config.state_root = state.c_str();
  config.authorized_acceptance_root = acceptance.c_str();
  config.target_policy_activation = "operator_acceptance_candidate";

  usk_context *context = nullptr;
  if (usk_context_create_v1(&config, &context) != USK_STATUS_OK ||
      context == nullptr) {
    return facman::core::Result<std::string>::failure(
        error("self_setup_context_failed",
              "Universal Setup context creation failed"));
  }

  usk_command_request_v1 request{};
  usk_command_response_v1 response{};
  request.struct_size = sizeof(request);
  request.command_name = {name.data(), static_cast<usk_size>(name.size())};
  request.json_payload = {payload.data(),
                          static_cast<usk_size>(payload.size())};
  request.dry_run = dry_run ? 1 : 0;
  response.struct_size = sizeof(response);
  const int status = usk_command_execute_v1(context, &request, &response);
  std::string output;
  if (response.json_payload.data != nullptr) {
    output.assign(response.json_payload.data, response.json_payload.size);
  }
  usk_context_destroy_v1(context);
  if (status != USK_STATUS_OK) {
    return facman::core::Result<std::string>::failure(
        error("self_setup_provider_refused",
              "Universal Setup refused the operation", output));
  }
  return facman::core::Result<std::string>::success(std::move(output));
}

facman::core::Result<std::string> plan_digest(const std::string &response) {
  auto document = json::parse(response);
  if (!document || !document.value().is_object() ||
      string_field(document.value(), "status") != "ok") {
    return facman::core::Result<std::string>::failure(
        error("self_setup_response_invalid",
              "Universal Setup returned an invalid plan envelope", response));
  }
  const json::Value *payload = document.value().find("payload");
  const std::string digest = payload != nullptr && payload->is_object()
                                 ? string_field(*payload, "plan_digest")
                                 : std::string();
  if (digest.size() != 64) {
    return facman::core::Result<std::string>::failure(
        error("self_setup_response_invalid",
              "Universal Setup plan has no valid digest", response));
  }
  return facman::core::Result<std::string>::success(digest);
}

json::ObjectBuilder archive(const fs::path &package, const std::string &digest,
                            bool budgets) {
  json::ObjectBuilder result;
  result.add_string("path", facman::platform::path_to_utf8(package));
  result.add_string("format", "zip");
  result.add_string("expected_sha256", digest);
  result.add_string("strip_prefix", "facman");
  if (budgets) {
    json::ObjectBuilder limits;
    limits.add_unsigned_integer("max_entries", 100000);
    limits.add_unsigned_integer("max_uncompressed_bytes",
                                16ULL * 1024ULL * 1024ULL * 1024ULL);
    limits.add_unsigned_integer("max_entry_bytes",
                                8ULL * 1024ULL * 1024ULL * 1024ULL);
    limits.add_unsigned_integer("max_depth", 64);
    limits.add_unsigned_integer("max_ratio", 1000);
    limits.add_unsigned_integer("max_elapsed_ms", 600000);
    result.add_object("budgets", limits);
  }
  return result;
}

std::string recipe_digest(const Request &request,
                          const std::string &source_digest) {
  json::ObjectBuilder recipe;
  recipe.add_string("schema", "facman.self_setup_recipe.v1");
  recipe.add_string("product_id", "facman");
  recipe.add_string("product_version", request.product_version);
  recipe.add_string("provider_revision", provider_revision());
  recipe.add_string("source_sha256", source_digest);
  recipe.add_string("target_layout",
                    "versioned_generation_with_maintenance_v1");
  const std::string serialized = recipe.serialize();
  return facman::base::sha256_hex_bytes(
      reinterpret_cast<const unsigned char *>(serialized.data()),
      serialized.size());
}

json::ObjectBuilder
install_plan(const Request &request, const fs::path &package,
             const fs::path &install_root, const std::string &source_digest,
             const std::string &created_at, const std::string &request_id,
             const std::string &plan_id) {
  json::ArrayBuilder components;
  components.add_string("facman.product");
  components.add_string("facman.maintenance");

  const std::string generation = "generations/" + request.product_version + "/";
  json::ObjectBuilder gui;
  gui.add_string("entrypoint_id", "facman.gui");
  gui.add_string("kind", "application");
  gui.add_string("relative_path", generation + "FacMan.exe");
  json::ObjectBuilder cli;
  cli.add_string("entrypoint_id", "facman.cli");
  cli.add_string("kind", "tool");
  cli.add_string("relative_path", generation + "bin/facman.exe");
  json::ObjectBuilder maintenance;
  maintenance.add_string("entrypoint_id", "facman.setup");
  maintenance.add_string("kind", "tool");
  maintenance.add_string("relative_path", "maintenance/FacManSetup.exe");
  json::ArrayBuilder entrypoints;
  entrypoints.add_object(gui);
  entrypoints.add_object(cli);
  entrypoints.add_object(maintenance);

  json::ObjectBuilder recipe;
  recipe.add_string("product_id", "facman");
  recipe.add_string("product_version", request.product_version);
  recipe.add_string("recipe_digest", recipe_digest(request, source_digest));
  recipe.add_string("provider_revision", provider_revision());
  recipe.add_array("components", components);
  recipe.add_array("entrypoints", entrypoints);

  json::ObjectBuilder target;
  target.add_string("root", facman::platform::path_to_utf8(install_root));
  target.add_string("class", "operator_acceptance");

  json::ObjectBuilder plan;
  plan.add_string("schema", "usk.install_local_plan_request.v1");
  plan.add_string("request_id", request_id);
  plan.add_string("created_at", created_at);
  plan.add_string("install_id", "facman.self");
  plan.add_object("archive", archive(package, source_digest, true));
  plan.add_object("target", target);
  plan.add_object("recipe", recipe);
  (void)plan_id;
  return plan;
}

json::ObjectBuilder apply_request(const char *schema,
                                  const json::ObjectBuilder &plan,
                                  const std::string &plan_id,
                                  const std::string &digest,
                                  const std::string &plan_created_at) {
  auto parsed_plan = json::parse(plan.serialize());
  json::ObjectBuilder apply;
  apply.add_string("schema", schema);
  apply.add_string("transaction_id", identifier("tx.facman.self"));
  // USK preserves second-resolution immutable lifecycle timestamps and
  // requires every mutating result to advance them.  Waiting here keeps the
  // receipt truthful even when plan and apply occur within the same second.
  apply.add_string("applied_at", timestamp_after(plan_created_at));
  apply.add_string("confirmation", "APPLY");
  apply.add_string("reviewed_plan_id", plan_id);
  apply.add_string("reviewed_plan_digest", digest);
  if (parsed_plan)
    apply.add_value("plan_request", parsed_plan.value());
  return apply;
}

facman::core::Result<Response>
install_or_repair(const Request &request, const fs::path &package,
                  const fs::path &install_root, const fs::path &state_root,
                  const fs::path &acceptance_root) {
  std::error_code status;
  if (!fs::is_regular_file(package, status) || status) {
    return facman::core::Result<Response>::failure(error(
        "self_setup_package_missing", "The setup payload is not a regular file",
        facman::platform::path_to_utf8(package)));
  }
  const std::string source_digest = facman::base::sha256_hex_file(package);
  if (source_digest.size() != 64) {
    return facman::core::Result<Response>::failure(
        error("self_setup_package_hash_failed",
              "The setup payload could not be hashed"));
  }
  const std::string created_at = timestamp();
  const std::string request_id = identifier(
      request.operation == Operation::install ? "request.facman.install"
                                              : "request.facman.repair");
  const std::string plan_id = request.operation == Operation::install
                                  ? request_id
                                  : identifier("plan.facman.repair");
  json::ObjectBuilder plan;
  std::string plan_command;
  std::string apply_command;
  const char *apply_schema = nullptr;
  if (request.operation == Operation::install) {
    plan = install_plan(request, package, install_root, source_digest,
                        created_at, request_id, plan_id);
    plan_command = "install_local.plan";
    apply_command = "install_local.apply";
    apply_schema = "usk.install_local_apply_request.v1";
  } else {
    plan.add_string("schema", "usk.repair_plan_request.v1");
    plan.add_string("request_id", request_id);
    plan.add_string("plan_id", plan_id);
    plan.add_string("install_id", "facman.self");
    plan.add_string("created_at", created_at);
    plan.add_object("archive", archive(package, source_digest, false));
    plan_command = "repair.plan";
    apply_command = "repair.apply";
    apply_schema = "usk.repair_apply_request.v1";
  }

  auto planned = command(plan_command, plan.serialize(), state_root,
                         acceptance_root, true);
  if (!planned)
    return facman::core::Result<Response>::failure(planned.error());
  if (!request.apply) {
    return facman::core::Result<Response>::success(
        {request.operation == Operation::install ? "install" : "repair", "plan",
         planned.take_value()});
  }
  auto digest = plan_digest(planned.value());
  if (!digest)
    return facman::core::Result<Response>::failure(digest.error());
  json::ObjectBuilder apply =
      apply_request(apply_schema, plan, plan_id, digest.value(), created_at);
  auto applied = command(apply_command, apply.serialize(), state_root,
                         acceptance_root, false);
  if (!applied)
    return facman::core::Result<Response>::failure(applied.error());
  return facman::core::Result<Response>::success(
      {request.operation == Operation::install ? "install" : "repair",
       "receipt", applied.take_value()});
}

facman::core::Result<Response> verify(const fs::path &state_root,
                                      const fs::path &acceptance_root) {
  json::ObjectBuilder payload;
  payload.add_string("schema", "usk.installed_verify_request.v1");
  payload.add_string("request_id", identifier("request.facman.verify"));
  payload.add_string("install_id", "facman.self");
  payload.add_string("report_id", identifier("report.facman.verify"));
  payload.add_string("verified_at", timestamp());
  auto response = command("installed.verify", payload.serialize(), state_root,
                          acceptance_root, true);
  if (!response)
    return facman::core::Result<Response>::failure(response.error());
  return facman::core::Result<Response>::success(
      {"verify", "receipt", response.take_value()});
}

facman::core::Result<Response> uninstall(const Request &request,
                                         const fs::path &state_root,
                                         const fs::path &acceptance_root) {
  const std::string plan_id = identifier("plan.facman.uninstall");
  const std::string created_at = timestamp();
  json::ObjectBuilder plan;
  plan.add_string("schema", "usk.uninstall_plan_request.v1");
  plan.add_string("request_id", identifier("request.facman.uninstall"));
  plan.add_string("plan_id", plan_id);
  plan.add_string("install_id", "facman.self");
  plan.add_string("created_at", created_at);
  auto planned = command("uninstall.plan", plan.serialize(), state_root,
                         acceptance_root, true);
  if (!planned)
    return facman::core::Result<Response>::failure(planned.error());
  if (!request.apply) {
    return facman::core::Result<Response>::success(
        {"uninstall", "plan", planned.take_value()});
  }
  auto digest = plan_digest(planned.value());
  if (!digest)
    return facman::core::Result<Response>::failure(digest.error());
  json::ObjectBuilder apply =
      apply_request("usk.uninstall_apply_request.v1", plan, plan_id,
                    digest.value(), created_at);
  auto applied = command("uninstall.apply", apply.serialize(), state_root,
                         acceptance_root, false);
  if (!applied)
    return facman::core::Result<Response>::failure(applied.error());
  return facman::core::Result<Response>::success(
      {"uninstall", "receipt", applied.take_value()});
}

} // namespace

facman::core::Result<Response> execute(const Request &request) {
  auto install_root = absolute_path(request.install_root, "install root");
  auto state_root = absolute_path(request.state_root, "state root");
  auto acceptance_root =
      absolute_path(request.acceptance_root, "acceptance root");
  if (!install_root || !state_root || !acceptance_root) {
    const auto &problem = !install_root ? install_root.error()
                          : !state_root ? state_root.error()
                                        : acceptance_root.error();
    return facman::core::Result<Response>::failure(problem);
  }
  if (request.product_version.empty()) {
    return facman::core::Result<Response>::failure(
        error("self_setup_version_missing",
              "The FacMan product version is required"));
  }
  if (request.operation == Operation::verify) {
    return verify(state_root.value(), acceptance_root.value());
  }
  if (request.operation == Operation::uninstall) {
    return uninstall(request, state_root.value(), acceptance_root.value());
  }
  auto package = absolute_path(request.package, "setup payload");
  if (!package)
    return facman::core::Result<Response>::failure(package.error());
  return install_or_repair(request, package.value(), install_root.value(),
                           state_root.value(), acceptance_root.value());
}

std::string provider_revision() { return FACMAN_SELF_SETUP_PROVIDER_REVISION; }

} // namespace facman::self_setup
