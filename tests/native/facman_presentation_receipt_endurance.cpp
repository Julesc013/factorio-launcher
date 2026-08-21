// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "presentation_service.h"

#include "fl_json.h"
#include "fl_sha256.h"

#include <atomic>
#include <chrono>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <memory>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

namespace fs = std::filesystem;
namespace json = facman::core::json;
using facman::factorio::application::PresentationActionLedger;
using facman::factorio::application::SemanticActionRequest;

namespace {

struct Options {
  fs::path workspace;
  fs::path output;
  std::uint64_t operations = 50000U;
  std::uint64_t replays = 5000U;
  std::uint64_t conflicts = 5000U;
  std::uint64_t restarts = 1000U;
  unsigned int workers = 4U;
  unsigned int minimum_seconds = 5400U;
};

bool parse_unsigned(const char *value, std::uint64_t &output) {
  try {
    std::size_t consumed = 0U;
    const std::string text(value);
    output = std::stoull(text, &consumed, 10);
    return consumed == text.size();
  } catch (...) {
    return false;
  }
}

bool parse_arguments(int argc, char **argv, Options &options) {
  for (int index = 1; index < argc; ++index) {
    const std::string argument(argv[index]);
    if (index + 1 >= argc)
      return false;
    const char *value = argv[++index];
    std::uint64_t number = 0U;
    if (argument == "--workspace")
      options.workspace = fs::u8path(value);
    else if (argument == "--output")
      options.output = fs::u8path(value);
    else if (!parse_unsigned(value, number))
      return false;
    else if (argument == "--operations")
      options.operations = number;
    else if (argument == "--replays")
      options.replays = number;
    else if (argument == "--conflicts")
      options.conflicts = number;
    else if (argument == "--restarts")
      options.restarts = number;
    else if (argument == "--workers")
      options.workers = static_cast<unsigned int>(number);
    else if (argument == "--minimum-seconds")
      options.minimum_seconds = static_cast<unsigned int>(number);
    else
      return false;
  }
  return !options.workspace.empty() && !options.output.empty() &&
         options.operations != 0U && options.workers >= 2U;
}

std::string identity(const char *prefix, std::uint64_t index) {
  std::ostringstream value;
  value << prefix << '-' << std::setw(12) << std::setfill('0') << index;
  return value.str();
}

SemanticActionRequest action_request(std::uint64_t index) {
  SemanticActionRequest request;
  request.action_id = "launch.execute";
  request.scope = "workspace";
  request.expected_snapshot_revision = "snapshot-revision";
  request.request_id = identity("request", index);
  request.selected_instance_id = identity("instance", index);
  request.idempotency_key = identity("idempotency", index);
  request.durable_operation_id = identity("operation", index);
  request.attempt_id = identity("attempt", index);
  request.installation_id = identity("installation", index);
  return request;
}

std::string request_fingerprint(const SemanticActionRequest &request) {
  json::ObjectBuilder input;
  input.add_string("action_id", request.action_id);
  input.add_string("scope", request.scope);
  input.add_string("expected_snapshot_revision",
                   request.expected_snapshot_revision);
  input.add_string("request_id", request.request_id);
  input.add_string("selected_instance_id", request.selected_instance_id);
  input.add_string("durable_operation_id", request.durable_operation_id);
  input.add_string("attempt_id", request.attempt_id);
  input.add_string("confirmation", request.confirmation);
  input.add_string("installation_id", request.installation_id);
  input.add_string("installation_path", request.installation_path);
  input.add_string("new_instance_id", request.new_instance_id);
  input.add_string("display_name", request.display_name);
  input.add_string("template_id", request.template_id);
  input.add_string("source_data_root", request.source_data_root);
  input.add_string("transaction_id", request.transaction_id);
  json::ArrayBuilder roots;
  for (const auto &root : request.roots)
    roots.add_string(root);
  input.add_array("roots", roots);
  const std::string serialized = input.serialize();
  return facman::base::sha256_hex_bytes(
      reinterpret_cast<const unsigned char *>(serialized.data()),
      serialized.size());
}

std::string semantic_result(const SemanticActionRequest &request,
                            const char *outcome) {
  return "{\"schema\":\"facman.semantic_action_result.v1\","
         "\"command\":\"presentation.action\","
         "\"action_id\":\"" +
         request.action_id + "\",\"request_id\":\"" + request.request_id +
         "\",\"outcome\":\"" + outcome +
         "\",\"operation\":{\"request_id\":\"" + request.request_id +
         "\",\"operation_id\":\"" + request.durable_operation_id +
         "\",\"durable_operation_id\":\"" +
         request.durable_operation_id + "\",\"attempt_id\":\"" +
         request.attempt_id + "\",\"target_instance_id\":\"" +
         request.selected_instance_id +
         "\",\"target_installation_id\":\"" + request.installation_id +
         "\",\"outcome\":\"" + outcome +
         "\"},\"effects\":[],\"diagnostics\":[],\"problems\":[],"
         "\"replacement_snapshot\":null,\"action_payload\":null,"
         "\"invalidation\":null}";
}

std::pair<std::uint64_t, std::uint64_t>
receipt_inventory(const fs::path &workspace) {
  const fs::path root = workspace / ".facman" / "action-receipts-v2";
  std::uint64_t files = 0U;
  std::uint64_t bytes = 0U;
  std::error_code error;
  if (!fs::exists(root, error))
    return {0U, 0U};
  for (const fs::directory_entry &entry :
       fs::recursive_directory_iterator(root, error)) {
    if (error)
      break;
    if (!entry.is_regular_file())
      continue;
    ++files;
    bytes += entry.file_size(error);
    if (error)
      break;
  }
  return {files, bytes};
}

} // namespace

int main(int argc, char **argv) {
  Options options;
  if (!parse_arguments(argc, argv, options)) {
    std::cerr
        << "usage: facman_presentation_receipt_endurance --workspace PATH "
           "--output PATH "
           "[--operations N] [--replays N] [--conflicts N] [--restarts N] "
           "[--workers N] [--minimum-seconds N]\n";
    return 2;
  }
  std::error_code error;
  fs::remove_all(options.workspace, error);
  error.clear();
  fs::create_directories(options.workspace, error);
  fs::create_directories(options.output.parent_path(), error);
  if (error)
    return 3;

  const auto started = std::chrono::steady_clock::now();
  const auto deadline = started + std::chrono::seconds(options.minimum_seconds);
  std::atomic<std::uint64_t> next_operation{0U};
  std::atomic<std::uint64_t> successful_operations{0U};
  std::atomic<std::uint64_t> successful_replays{0U};
  std::atomic<std::uint64_t> successful_conflicts{0U};
  std::atomic<std::uint64_t> restart_cycles{0U};
  std::atomic<std::uint64_t> failures{0U};
  std::mutex failure_mutex;
  std::string first_failure;
  PresentationActionLedger ledger;

  std::vector<std::thread> workers;
  for (unsigned int worker = 0U; worker < options.workers; ++worker) {
    workers.emplace_back([&] {
      for (;;) {
        const std::uint64_t index = next_operation.fetch_add(1U);
        if (index >= options.operations)
          break;
        const SemanticActionRequest request = action_request(index);
        const std::string fingerprint_value = request_fingerprint(request);
        const std::string pending = semantic_result(request, "outcome_unknown");
        const std::string completed = semantic_result(request, "completed");
        std::string detail;
        std::string result;
        if (!ledger.claim(options.workspace, request, fingerprint_value, pending,
                          detail) ||
            !ledger.remember(options.workspace, request, fingerprint_value,
                             completed, true, detail) ||
            ledger.lookup(options.workspace, request, fingerprint_value, true,
                          result,
                          detail) != PresentationActionLedger::Lookup::match ||
            result != completed) {
          ++failures;
          std::lock_guard<std::mutex> guard(failure_mutex);
          if (first_failure.empty())
            first_failure =
                detail.empty() ? "receipt round trip failed" : detail;
          continue;
        }
        ++successful_operations;
        if (index < options.replays) {
          if (ledger.lookup(options.workspace, request, fingerprint_value, true,
                            result, detail) ==
                  PresentationActionLedger::Lookup::match &&
              result == completed) {
            ++successful_replays;
          } else {
            ++failures;
          }
        }
        if (index < options.conflicts) {
          if (ledger.lookup(options.workspace, request,
                            request_fingerprint(
                                action_request(index + options.operations)),
                            true,
                            result, detail) ==
              PresentationActionLedger::Lookup::conflict) {
            ++successful_conflicts;
          } else {
            ++failures;
          }
        }
      }
    });
  }
  for (std::thread &worker : workers)
    worker.join();

  for (std::uint64_t cycle = 0U; cycle < options.restarts; ++cycle) {
    PresentationActionLedger reopened;
    const std::uint64_t index = cycle % options.operations;
    const SemanticActionRequest request = action_request(index);
    const std::string fingerprint_value = request_fingerprint(request);
    std::string result;
    std::string detail;
    if (reopened.lookup(options.workspace, request, fingerprint_value, true,
                        result, detail) !=
        PresentationActionLedger::Lookup::match) {
      ++failures;
      std::lock_guard<std::mutex> guard(failure_mutex);
      if (first_failure.empty())
        first_failure = detail.empty() ? "restart lookup failed" : detail;
    } else {
      ++restart_cycles;
    }
  }

  std::uint64_t active_index = 0U;
  while (std::chrono::steady_clock::now() < deadline) {
    PresentationActionLedger reopened;
    const std::uint64_t index = active_index++ % options.operations;
    const SemanticActionRequest request = action_request(index);
    const std::string fingerprint_value = request_fingerprint(request);
    std::string result;
    std::string detail;
    if (reopened.lookup(options.workspace, request, fingerprint_value, true,
                        result, detail) !=
        PresentationActionLedger::Lookup::match)
      ++failures;
  }

  const auto ended = std::chrono::steady_clock::now();
  const double elapsed = std::chrono::duration<double>(ended - started).count();
  const auto [receipt_files, receipt_bytes] =
      receipt_inventory(options.workspace);
  const bool passed = elapsed >= static_cast<double>(options.minimum_seconds) &&
                      successful_operations >= options.operations &&
                      successful_replays >= options.replays &&
                      successful_conflicts >= options.conflicts &&
                      restart_cycles >= options.restarts && failures == 0U &&
                      receipt_files == options.operations;

  std::ofstream output(options.output, std::ios::binary | std::ios::trunc);
  output << "{\n"
         << "  \"schema\": \"facman.presentation_receipt_endurance.v1\",\n"
         << "  \"status\": \"" << (passed ? "pass" : "fail") << "\",\n"
         << "  \"elapsed_seconds\": " << std::fixed << std::setprecision(3)
         << elapsed << ",\n"
         << "  \"workers\": " << options.workers << ",\n"
         << "  \"durable_operations\": " << successful_operations.load()
         << ",\n"
         << "  \"idempotent_replays\": " << successful_replays.load() << ",\n"
         << "  \"conflict_controls\": " << successful_conflicts.load() << ",\n"
         << "  \"restart_cycles\": " << restart_cycles.load() << ",\n"
         << "  \"failures\": " << failures.load() << ",\n"
         << "  \"first_failure\": \"" << first_failure << "\",\n"
         << "  \"receipt_files\": " << receipt_files << ",\n"
         << "  \"receipt_bytes\": " << receipt_bytes << "\n"
         << "}\n";
  output.close();
  fs::remove_all(options.workspace, error);
  return passed ? 0 : 1;
}
