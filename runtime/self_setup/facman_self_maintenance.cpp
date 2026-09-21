// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_self_maintenance.h"

#include "fl_json.h"
#include "fl_local_operation_lock.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_file_io.h"
#include "fl_system_services.h"

#include <algorithm>
#include <cwchar>
#include <filesystem>
#include <initializer_list>
#include <limits>
#include <sstream>
#include <system_error>
#include <utility>
#include <vector>

namespace fs = std::filesystem;
namespace json = facman::core::json;

namespace facman::self_maintenance {
namespace {

testing::EpochRecordPinnedHook epoch_record_pinned_hook_for_testing = nullptr;
testing::EpochHandoffOperationPinnedHook epoch_handoff_operation_pinned_hook_for_testing = nullptr;

void notify_epoch_record_pinned(const fs::path &path) {
  if (epoch_record_pinned_hook_for_testing != nullptr)
    epoch_record_pinned_hook_for_testing(path);
}

void notify_epoch_handoff_operation_pinned(const fs::path &path) {
  if (epoch_handoff_operation_pinned_hook_for_testing != nullptr)
    epoch_handoff_operation_pinned_hook_for_testing(path);
}

facman::core::Error failure(std::string code, std::string message,
                            std::string detail = {}) {
  facman::core::Error result{std::move(code), std::move(message), ""};
  result.detail = std::move(detail);
  return result;
}

bool digest(const std::string &value) {
  return value.size() == 64U &&
      std::all_of(value.begin(), value.end(), [](unsigned char value) {
        return (value >= '0' && value <= '9') ||
            (value >= 'a' && value <= 'f');
      });
}

bool revision(const std::string &value) {
  return value.size() == 40U &&
      std::all_of(value.begin(), value.end(), [](unsigned char value) {
        return (value >= '0' && value <= '9') ||
            (value >= 'a' && value <= 'f');
      });
}

std::string hash(const std::string &value) {
  return facman::base::sha256_hex_bytes(
      reinterpret_cast<const unsigned char *>(value.data()), value.size());
}

struct SemverIdentifier {
  bool numeric = false;
  unsigned long long number = 0;
  std::string text;
};

struct Semver {
  unsigned long long major = 0;
  unsigned long long minor = 0;
  unsigned long long patch = 0;
  std::vector<SemverIdentifier> prerelease;
};

bool unsigned_number(const std::string &value, unsigned long long &result) {
  if (value.empty() || (value.size() > 1U && value.front() == '0')) return false;
  result = 0;
  for (const unsigned char character : value) {
    if (character < '0' || character > '9') return false;
    const unsigned digit = character - '0';
    if (result > (std::numeric_limits<unsigned long long>::max() - digit) / 10U)
      return false;
    result = result * 10U + digit;
  }
  return true;
}

std::vector<std::string> split(const std::string &value, char separator) {
  std::vector<std::string> result;
  std::size_t start = 0;
  while (start <= value.size()) {
    const std::size_t end = value.find(separator, start);
    result.push_back(value.substr(start, end == std::string::npos
        ? std::string::npos : end - start));
    if (end == std::string::npos) break;
    start = end + 1U;
  }
  return result;
}

bool semver_identifier_character(unsigned char character) {
  return (character >= '0' && character <= '9') ||
      (character >= 'A' && character <= 'Z') ||
      (character >= 'a' && character <= 'z') || character == '-';
}

bool semver(const std::string &value, Semver &result) {
  if (value.empty() || value.size() > 160U) return false;
  const std::size_t plus = value.find('+');
  if (plus != std::string::npos) {
    if (plus + 1U == value.size() ||
        value.find('+', plus + 1U) != std::string::npos)
      return false;
    for (const auto &part : split(value.substr(plus + 1U), '.')) {
      if (part.empty() ||
          !std::all_of(part.begin(), part.end(), [](unsigned char character) {
            return semver_identifier_character(character);
          })) return false;
    }
  }
  const std::string significant = value.substr(0, plus);
  const std::size_t dash = significant.find('-');
  const auto core = split(significant.substr(0, dash), '.');
  if (core.size() != 3U || !unsigned_number(core[0], result.major) ||
      !unsigned_number(core[1], result.minor) ||
      !unsigned_number(core[2], result.patch)) return false;
  result.prerelease.clear();
  if (dash == std::string::npos) return true;
  for (const auto &part : split(significant.substr(dash + 1U), '.')) {
    if (part.empty() || !std::all_of(part.begin(), part.end(), [](unsigned char c) {
          return semver_identifier_character(c);
        })) return false;
    SemverIdentifier identifier;
    identifier.text = part;
    const bool all_digits = std::all_of(
        part.begin(), part.end(), [](unsigned char character) {
          return character >= '0' && character <= '9';
        });
    identifier.numeric = all_digits && unsigned_number(part, identifier.number);
    if (all_digits && !identifier.numeric) return false;
    result.prerelease.push_back(std::move(identifier));
  }
  return !result.prerelease.empty();
}

int compare(const Semver &left, const Semver &right) {
  if (left.major != right.major) return left.major < right.major ? -1 : 1;
  if (left.minor != right.minor) return left.minor < right.minor ? -1 : 1;
  if (left.patch != right.patch) return left.patch < right.patch ? -1 : 1;
  if (left.prerelease.empty() != right.prerelease.empty())
    return left.prerelease.empty() ? 1 : -1;
  const std::size_t count = (std::min)(left.prerelease.size(),
                                       right.prerelease.size());
  for (std::size_t index = 0; index < count; ++index) {
    const auto &a = left.prerelease[index];
    const auto &b = right.prerelease[index];
    if (a.numeric != b.numeric) return a.numeric ? -1 : 1;
    if (a.numeric && a.number != b.number) return a.number < b.number ? -1 : 1;
    if (!a.numeric && a.text != b.text) return a.text < b.text ? -1 : 1;
  }
  if (left.prerelease.size() == right.prerelease.size()) return 0;
  return left.prerelease.size() < right.prerelease.size() ? -1 : 1;
}

std::string operation_name(Operation operation) {
  switch (operation) {
  case Operation::update: return "update";
  case Operation::downgrade: return "downgrade";
  case Operation::rollback: return "rollback";
  }
  return "update";
}

bool safe_relative(const std::string &value) {
  if (value.empty()) return false;
  const fs::path path = facman::platform::path_from_utf8(value);
  if (path.is_absolute() || path.has_root_path()) return false;
  return std::none_of(path.begin(), path.end(), [](const fs::path &part) {
    return part.empty() || part == "." || part == "..";
  });
}

bool safe_version_component(const std::string &value) {
  const fs::path path = facman::platform::path_from_utf8(value);
  return !value.empty() && !path.empty() && !path.is_absolute() &&
      !path.has_root_path() && path == path.filename() && path != "." &&
      path != "..";
}

std::string generation_identity(const PackageDescriptor &descriptor,
                                const std::string &package_sha256) {
  return hash("facman.self.generation.v1\n" + descriptor.product_id + "\n" +
      descriptor.product_version + "\n" + package_sha256 + "\n" +
      descriptor.facman_source_revision + "\n" +
      descriptor.universal_setup_revision + "\n" +
      descriptor.setup_protocol + "\n" + descriptor.package_layout + "\n" +
      descriptor.generation_relative_path + "\n" +
      descriptor.gui_relative_path + "\n" + descriptor.cli_relative_path +
      "\n" + descriptor.maintenance_relative_path + "\n");
}

std::string generation_install_id(const std::string &generation_id) {
  return "facman.self.generation." + generation_id;
}

std::string logical_root_identity(const fs::path &logical_root) {
  return hash("facman.self.logical-root.v1\n" +
      facman::platform::path_to_utf8(logical_root.lexically_normal()) + "\n");
}

std::string physical_generation_root_identity(const fs::path &logical_root,
                                              const std::string &generation_id) {
  return hash("facman.self.physical-generation-root.v1\n" +
      logical_root_identity(logical_root) + "\n" + generation_id + "\n");
}

fs::path generation_install_root(const fs::path &logical_root,
                                 const std::string &generation_id) {
  return logical_root.parent_path() / facman::platform::path_from_utf8(
      "FacMan.generation." +
      physical_generation_root_identity(logical_root, generation_id));
}

fs::path predecessor_generation_install_root(const fs::path &logical_root,
                                             const std::string &generation_id) {
  return logical_root.parent_path() / facman::platform::path_from_utf8(
      "FacMan.generation." + logical_root_identity(logical_root) + "." +
      generation_id);
}

PackageDescriptor generation_descriptor(const Generation &generation) {
  return {"facman", generation.product_version,
          "generations/" + generation.product_version,
          generation.facman_source_revision,
          generation.universal_setup_revision,
          "facman.self_maintenance.v1",
          "versioned_generation_with_maintenance_v1",
          "FacMan.exe", "bin/facman.exe", "maintenance/FacManSetup.exe",
          false};
}

bool same_descriptor(const PackageDescriptor &left,
                     const PackageDescriptor &right) {
  return left.product_id == right.product_id &&
      left.product_version == right.product_version &&
      left.generation_relative_path == right.generation_relative_path &&
      left.facman_source_revision == right.facman_source_revision &&
      left.universal_setup_revision == right.universal_setup_revision &&
      left.setup_protocol == right.setup_protocol &&
      left.package_layout == right.package_layout &&
      left.gui_relative_path == right.gui_relative_path &&
      left.cli_relative_path == right.cli_relative_path &&
      left.maintenance_relative_path == right.maintenance_relative_path &&
      left.automatic_update == right.automatic_update;
}

std::string serialize_generation(const Generation &generation) {
  json::ObjectBuilder object;
  object.add_string("schema", "facman.self_generation.v1");
  object.add_string("product_id", "facman");
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
  object.add_string("maintenance_launcher",
                    facman::platform::path_to_utf8(generation.maintenance_launcher));
  return object.serialize() + "\n";
}

std::string activation_json(const Plan &plan) {
  json::ObjectBuilder previous;
  previous.add_string("name", plan.previous_activation_name);
  previous.add_string("sha256", plan.previous_activation_sha256);
  json::ObjectBuilder object;
  object.add_string("schema", "facman.self_activation.v1");
  object.add_string("product_id", "facman");
  object.add_string("operation", plan.operation);
  object.add_string("operation_id", plan.operation_id);
  if (plan.operation == "migration") {
    object.add_string("generation_id", plan.target.generation_id);
  } else {
    object.add_string("source_generation_id", plan.source.generation_id);
    object.add_string("target_generation_id", plan.target.generation_id);
  }
  object.add_object("previous", previous);
  return object.serialize() + "\n";
}

std::string phase_json(const Plan &plan, const std::string &phase,
                       const std::string &receipt = {}) {
  json::ObjectBuilder object;
  object.add_string("schema", "facman.self_maintenance_phase.v1");
  object.add_string("product_id", "facman");
  object.add_string("operation", plan.operation);
  object.add_string("operation_id", plan.operation_id);
  object.add_string("phase", phase);
  object.add_string("source_generation_id", plan.source.generation_id);
  object.add_string("target_generation_id", plan.target.generation_id);
  object.add_string("package_sha256", plan.package_sha256);
  object.add_string("provider_operation", plan.provider_operation);
  object.add_string("state_root", facman::platform::path_to_utf8(plan.target.state_root));
  object.add_string("acceptance_root", facman::platform::path_to_utf8(plan.target.acceptance_root));
  object.add_string("receipt_sha256", receipt);
  return object.serialize() + "\n";
}

facman::core::Result<std::string> read_exact(const fs::path &path) {
  facman::platform::StableInputFile file;
  auto opened = file.open_no_follow_pinned(path);
  if (!opened.ok() || file.size() > 1024U * 1024U)
    return facman::core::Result<std::string>::failure(failure(
        "self_maintenance_record_unreadable", "maintenance record is unsafe",
        opened.detail));
  std::string bytes(static_cast<std::size_t>(file.size()), '\0');
  if (!bytes.empty() && file.read_at(0, bytes.data(), bytes.size()) != bytes.size())
    return facman::core::Result<std::string>::failure(failure(
        "self_maintenance_record_unreadable", "maintenance record changed while read"));
  const auto checked = file.revalidate_path();
  if (!checked.ok())
    return facman::core::Result<std::string>::failure(failure(
        "self_maintenance_record_unreadable", "maintenance record changed while read",
        checked.detail));
  return facman::core::Result<std::string>::success(std::move(bytes));
}

facman::core::Result<std::string> stable_digest(const fs::path &path) {
  facman::platform::StableInputFile file;
  auto opened = file.open_no_follow_pinned(path);
  if (!opened.ok() || file.size() == 0 || file.size() > 16ULL * 1024ULL * 1024ULL * 1024ULL)
    return facman::core::Result<std::string>::failure(failure(
        "self_maintenance_package_changed",
        "maintenance package is missing, empty, unsafe, or over budget",
        opened.detail));
  facman::base::Sha256Hasher hasher;
  std::vector<unsigned char> buffer(1024U * 1024U);
  for (std::uint64_t offset = 0; offset < file.size();) {
    const std::size_t count = static_cast<std::size_t>((std::min)(
        static_cast<std::uint64_t>(buffer.size()), file.size() - offset));
    if (file.read_at(offset, buffer.data(), count) != count)
      return facman::core::Result<std::string>::failure(failure(
          "self_maintenance_package_changed",
          "maintenance package changed while it was hashed"));
    hasher.update(buffer.data(), count);
    offset += count;
  }
  auto checked = file.revalidate_path();
  if (!checked.ok())
    return facman::core::Result<std::string>::failure(failure(
        "self_maintenance_package_changed",
        "maintenance package changed while it was hashed", checked.detail));
  return facman::core::Result<std::string>::success(hasher.finish());
}

facman::core::Result<std::string> stable_digest(
    facman::platform::StableInputFile &file) {
  if (file.size() == 0 || file.size() > 16ULL * 1024ULL * 1024ULL * 1024ULL)
    return facman::core::Result<std::string>::failure(failure(
        "self_maintenance_package_changed",
        "maintenance package is empty, unsafe, or over budget"));
  facman::base::Sha256Hasher hasher;
  std::vector<unsigned char> buffer(1024U * 1024U);
  for (std::uint64_t offset = 0; offset < file.size();) {
    const std::size_t count = static_cast<std::size_t>((std::min)(
        static_cast<std::uint64_t>(buffer.size()), file.size() - offset));
    if (file.read_at(offset, buffer.data(), count) != count)
      return facman::core::Result<std::string>::failure(failure(
          "self_maintenance_package_changed",
          "maintenance package changed while it was hashed"));
    hasher.update(buffer.data(), count);
    offset += count;
  }
  if (!file.revalidate().ok() || !file.revalidate_path().ok())
    return facman::core::Result<std::string>::failure(failure(
        "self_maintenance_package_changed",
        "maintenance package changed while it was hashed"));
  return facman::core::Result<std::string>::success(hasher.finish());
}

bool held_file_matches_bytes(facman::platform::StableInputFile &file,
                             const std::string &expected) {
  if (file.size() != expected.size()) return false;
  std::string observed(expected.size(), '\0');
  return (observed.empty() || file.read_at(0, observed.data(), observed.size()) ==
          observed.size()) && observed == expected && file.revalidate().ok() &&
      file.revalidate_path().ok();
}

std::string string_field(const json::Value &value, const char *name) {
  const json::Value *field = value.find(name);
  return field != nullptr && field->string_value()
      ? field->string_value().value() : std::string();
}

bool exact_keys(const json::Value &value,
                std::initializer_list<const char *> keys) {
  if (!value.is_object() || value.size() != keys.size()) return false;
  return std::all_of(keys.begin(), keys.end(),
                     [&](const char *key) { return value.find(key) != nullptr; });
}

bool activation_operation(const std::string &value) {
  return value == "migration" || value == "update" ||
      value == "downgrade" || value == "rollback";
}

struct ActivationHead {
  std::string name;
  std::string digest;
  std::string source_generation_id;
  std::string target_generation_id;
  std::string previous_name;
  std::string previous_digest;
  std::vector<std::string> generation_ids;
};

bool exact_generation_paths(const Generation &generation);

facman::core::Result<ActivationHead> validate_activation_head(
    const fs::path &coordinator_root, const std::string &expected_name,
    const std::string &expected_digest) {
  const fs::path directory = coordinator_root / "activations";
  std::error_code status;
  if (!fs::is_directory(directory, status) || status)
    return facman::core::Result<ActivationHead>::failure(failure(
        "self_maintenance_activation_changed",
        "activation chain directory is unavailable"));
  struct Node {
    std::string name;
    std::string digest;
    std::string operation;
    std::string operation_id;
    std::string source_generation_id;
    std::string target_generation_id;
    std::string previous_name;
    std::string previous_digest;
  };
  std::vector<Node> nodes;
  for (fs::directory_iterator iterator(directory, status), end;
       !status && iterator != end; iterator.increment(status)) {
    if (nodes.size() >= 256U)
      return facman::core::Result<ActivationHead>::failure(failure(
          "self_maintenance_activation_changed",
          "activation chain exceeds its entry limit"));
    const auto entry_status = iterator->symlink_status(status);
    if (status || entry_status.type() != fs::file_type::regular)
      return facman::core::Result<ActivationHead>::failure(failure(
          "self_maintenance_activation_changed",
          "activation chain contains a linked or non-file entry"));
    const std::string name = iterator->path().filename().string();
    std::string identifier_detail;
    if (!facman::base::validate_identifier(name, identifier_detail))
      return facman::core::Result<ActivationHead>::failure(failure(
          "self_maintenance_activation_changed",
          "activation chain contains an invalid filename"));
    auto bytes = read_exact(iterator->path());
    auto document = bytes ? json::parse(bytes.value())
                          : facman::core::Result<json::Value>::failure(
                                bytes.error());
    const json::Value *previous = document && document.value().is_object()
        ? document.value().find("previous") : nullptr;
    const std::string operation = document
        ? string_field(document.value(), "operation") : std::string();
    const std::string operation_id = document
        ? string_field(document.value(), "operation_id") : std::string();
    std::string source_generation_id = document
        ? string_field(document.value(), "source_generation_id") : std::string();
    std::string target_generation_id = document
        ? string_field(document.value(), "target_generation_id") : std::string();
    const std::string migration_generation_id = document
        ? string_field(document.value(), "generation_id") : std::string();
    if (operation == "migration") {
      source_generation_id = migration_generation_id;
      target_generation_id = migration_generation_id;
    }
    const std::string previous_name = previous != nullptr
        ? string_field(*previous, "name") : std::string();
    const std::string previous_digest = previous != nullptr
        ? string_field(*previous, "sha256") : std::string();
    const json::Value *previous_name_value = previous != nullptr
        ? previous->find("name") : nullptr;
    const json::Value *previous_digest_value = previous != nullptr
        ? previous->find("sha256") : nullptr;
    std::string operation_detail;
    const bool exact_shape = document && (operation == "migration"
        ? exact_keys(document.value(), {"schema", "product_id", "operation",
                                       "operation_id", "generation_id", "previous"})
        : exact_keys(document.value(), {"schema", "product_id", "operation",
                                       "operation_id", "source_generation_id",
                                       "target_generation_id", "previous"}));
    if (!document || !exact_shape ||
        string_field(document.value(), "schema") !=
            "facman.self_activation.v1" ||
        string_field(document.value(), "product_id") != "facman" ||
        !activation_operation(operation) ||
        !facman::base::validate_identifier(operation_id, operation_detail) ||
        name != "activation." + operation_id + ".v1.json" ||
        !digest(source_generation_id) || !digest(target_generation_id) ||
        previous == nullptr ||
        !exact_keys(*previous, {"name", "sha256"}) ||
        previous_name_value == nullptr || !previous_name_value->is_string() ||
        previous_digest_value == nullptr || !previous_digest_value->is_string() ||
        (previous_name.empty() != previous_digest.empty()) ||
        (operation == "migration" && !previous_name.empty()) ||
        (operation != "migration" && previous_name.empty()) ||
        (!previous_name.empty() &&
         (!facman::base::validate_identifier(previous_name, operation_detail) ||
          !digest(previous_digest))))
      return facman::core::Result<ActivationHead>::failure(failure(
          "self_maintenance_activation_changed",
          "activation chain contains an incompatible record"));
    nodes.push_back({name, hash(bytes.value()), operation, operation_id,
                     source_generation_id, target_generation_id,
                     previous_name, previous_digest});
  }
  if (status || nodes.empty())
    return facman::core::Result<ActivationHead>::failure(failure(
        "self_maintenance_activation_changed",
        "activation chain could not be enumerated"));

  std::size_t genesis_count = 0;
  const Node *genesis = nullptr;
  std::vector<const Node *> referenced;
  for (const auto &node : nodes) {
    if (node.previous_name.empty()) {
      ++genesis_count;
      genesis = &node;
      continue;
    }
    // Detect name cycles independently of record digests so a malformed cycle
    // cannot be reported as a mere missing predecessor.
    std::vector<std::string> ancestry{node.name};
    const Node *cursor = &node;
    while (!cursor->previous_name.empty()) {
      if (std::find(ancestry.begin(), ancestry.end(), cursor->previous_name) !=
          ancestry.end())
        return facman::core::Result<ActivationHead>::failure(failure(
            "self_maintenance_activation_changed",
            "activation chain contains a cycle"));
      ancestry.push_back(cursor->previous_name);
      const auto preceding = std::find_if(
          nodes.begin(), nodes.end(), [&](const Node &candidate) {
            return candidate.name == cursor->previous_name;
          });
      if (preceding == nodes.end()) break;
      cursor = &*preceding;
    }
    const auto parent = std::find_if(nodes.begin(), nodes.end(),
        [&](const Node &candidate) { return candidate.name == node.previous_name; });
    if (parent == nodes.end() || parent->digest != node.previous_digest ||
        parent->target_generation_id != node.source_generation_id ||
        std::find(referenced.begin(), referenced.end(), &*parent) !=
            referenced.end())
      return facman::core::Result<ActivationHead>::failure(failure(
          "self_maintenance_activation_changed",
          "activation chain is broken or forked"));
    referenced.push_back(&*parent);
  }
  if (genesis_count != 1U || genesis == nullptr)
    return facman::core::Result<ActivationHead>::failure(failure(
        "self_maintenance_activation_changed",
        "activation chain must contain exactly one genesis"));

  const Node *head = genesis;
  std::vector<const Node *> ordered{genesis};
  std::size_t visited = 1U;
  for (;;) {
    const auto child = std::find_if(nodes.begin(), nodes.end(),
        [&](const Node &candidate) {
          return candidate.previous_name == head->name;
        });
    if (child == nodes.end()) break;
    head = &*child;
    ordered.push_back(head);
    ++visited;
  }
  if (visited != nodes.size() ||
      (!expected_name.empty() && head->name != expected_name) ||
      (!expected_digest.empty() && head->digest != expected_digest))
    return facman::core::Result<ActivationHead>::failure(failure(
        "self_maintenance_activation_changed",
        "reviewed activation is not the unique current chain head"));
  std::vector<std::string> generation_ids;
  generation_ids.reserve(ordered.size());
  for (const Node *node : ordered)
    generation_ids.push_back(node->target_generation_id);
  return facman::core::Result<ActivationHead>::success(
      {head->name, head->digest, head->source_generation_id,
       head->target_generation_id, head->previous_name,
       head->previous_digest, std::move(generation_ids)});
}

facman::core::Result<Generation> parse_generation_record(
    const fs::path &coordinator_root, const std::string &generation_id) {
  if (!digest(generation_id))
    return facman::core::Result<Generation>::failure(failure(
        "self_maintenance_record_unreadable", "generation identity is invalid"));
  auto bytes = read_exact(coordinator_root / "generations" /
      ("generation." + generation_id + ".v1.json"));
  auto document = bytes ? json::parse(bytes.value())
                        : facman::core::Result<json::Value>::failure(bytes.error());
  if (!document || !exact_keys(document.value(),
          {"schema", "product_id", "generation_id", "product_version",
           "package_sha256", "facman_source_revision",
           "universal_setup_revision", "install_id", "install_root",
           "logical_root", "state_root", "acceptance_root", "gui",
           "maintenance_launcher"}) ||
      string_field(document.value(), "schema") != "facman.self_generation.v1" ||
      string_field(document.value(), "product_id") != "facman" ||
      string_field(document.value(), "generation_id") != generation_id)
    return facman::core::Result<Generation>::failure(failure(
        "self_maintenance_record_unreadable",
        "generation record has an incompatible exact schema"));
  Generation result;
  result.generation_id = generation_id;
  result.product_version = string_field(document.value(), "product_version");
  result.package_sha256 = string_field(document.value(), "package_sha256");
  result.facman_source_revision =
      string_field(document.value(), "facman_source_revision");
  result.universal_setup_revision =
      string_field(document.value(), "universal_setup_revision");
  result.install_id = string_field(document.value(), "install_id");
  result.install_root = facman::platform::path_from_utf8(
      string_field(document.value(), "install_root"));
  result.logical_root = facman::platform::path_from_utf8(
      string_field(document.value(), "logical_root"));
  result.state_root = facman::platform::path_from_utf8(
      string_field(document.value(), "state_root"));
  result.acceptance_root = facman::platform::path_from_utf8(
      string_field(document.value(), "acceptance_root"));
  result.gui = facman::platform::path_from_utf8(
      string_field(document.value(), "gui"));
  result.maintenance_launcher = facman::platform::path_from_utf8(
      string_field(document.value(), "maintenance_launcher"));
  Semver parsed_version;
  if (!digest(result.package_sha256) ||
      !revision(result.facman_source_revision) ||
      !revision(result.universal_setup_revision) ||
      (result.install_id != "facman.self" &&
       result.install_id != generation_install_id(result.generation_id)) ||
      generation_identity(generation_descriptor(result),
                          result.package_sha256) != result.generation_id ||
      !semver(result.product_version, parsed_version) ||
      !safe_version_component(result.product_version) ||
      !result.logical_root.is_absolute() || !result.state_root.is_absolute() ||
      !result.acceptance_root.is_absolute() || !exact_generation_paths(result) ||
      bytes.value() != serialize_generation(result))
    return facman::core::Result<Generation>::failure(failure(
        "self_maintenance_record_unreadable",
        "generation record identity is invalid"));
  return facman::core::Result<Generation>::success(std::move(result));
}

facman::core::Result<void> ensure_immutable(const fs::path &path,
                                            const std::string &bytes) {
  std::string unsafe_detail;
  if (facman::base::path_crosses_link_or_reparse_point(path.parent_path(),
                                                       unsafe_detail))
    return facman::core::Result<void>::failure(failure(
        "self_maintenance_record_unreadable",
        "maintenance record parent crosses a link or reparse point",
        unsafe_detail));
  std::error_code status;
  const bool exists = fs::exists(path, status);
  if (status)
    return facman::core::Result<void>::failure(failure(
        "self_maintenance_record_unreadable", "maintenance record could not be observed",
        status.message()));
  if (exists) {
    auto current = read_exact(path);
    if (!current || current.value() != bytes)
      return facman::core::Result<void>::failure(failure(
          "self_maintenance_record_changed", "immutable maintenance record changed",
          facman::platform::path_to_utf8(path)));
    return facman::core::Result<void>::success();
  }
  std::string detail;
  if (!facman::base::write_text_new_atomic(path, bytes, detail))
    return facman::core::Result<void>::failure(failure(
        "self_maintenance_record_write_failed", "maintenance record was not committed",
        detail));
  return facman::core::Result<void>::success();
}

bool exact_generation_record(const fs::path &coordinator_root,
                             const Generation &generation) {
  auto record = read_exact(coordinator_root / "generations" /
      ("generation." + generation.generation_id + ".v1.json"));
  return record && record.value() == serialize_generation(generation);
}

bool same_path(const fs::path &left, const fs::path &right) {
  const fs::path normalized_left = left.lexically_normal();
  const fs::path normalized_right = right.lexically_normal();
#ifdef _WIN32
  return _wcsicmp(normalized_left.native().c_str(),
                  normalized_right.native().c_str()) == 0;
#else
  return normalized_left == normalized_right;
#endif
}

bool exact_generation_paths(const Generation &generation) {
  if (!generation.install_root.is_absolute() || !generation.gui.is_absolute() ||
      !generation.logical_root.is_absolute() ||
      !generation.state_root.is_absolute() ||
      !generation.acceptance_root.is_absolute() ||
      !generation.maintenance_launcher.is_absolute()) return false;
  const fs::path expected_gui = generation.install_root / "generations" /
      facman::platform::path_from_utf8(generation.product_version) / "FacMan.exe";
  const fs::path expected_maintenance = generation.install_root /
      "maintenance" / "FacManSetup.exe";
  const bool exact_install_root = generation.install_id == "facman.self"
      ? same_path(generation.install_root, generation.logical_root)
      : same_path(generation.install_root,
                  generation_install_root(generation.logical_root,
                                          generation.generation_id)) ||
            same_path(generation.install_root,
                      predecessor_generation_install_root(
                          generation.logical_root, generation.generation_id));
  return exact_install_root && same_path(generation.gui, expected_gui) &&
      same_path(generation.maintenance_launcher, expected_maintenance);
}

struct CoordinatorAdmission {
  fs::path root;
  fs::path acceptance_root;
  facman::platform::StableDirectoryObject acceptance;
  facman::platform::StableDirectoryObject parent;
  facman::platform::StableDirectoryObject coordinator;
  bool coordinator_exists = false;

  bool revalidate(std::string &detail, bool allow_absent_root = false) const {
    const auto accepted = acceptance.revalidate();
    const auto parent_stable = parent.revalidate();
    const auto descendant = acceptance.validate_descendant(
        root, allow_absent_root && !coordinator_exists);
    if (!accepted.ok() || !parent_stable.ok() || !descendant.ok()) {
      detail = !accepted.ok() ? accepted.detail
          : !parent_stable.ok() ? parent_stable.detail : descendant.detail;
      return false;
    }
    if (coordinator_exists) {
      const auto stable = coordinator.revalidate();
      if (!stable.ok()) {
        detail = stable.detail;
        return false;
      }
    }
    if (facman::base::path_crosses_link_or_reparse_point(root, detail))
      return false;
    detail.clear();
    return true;
  }
};

facman::core::Result<CoordinatorAdmission> admit_coordinator(
    const fs::path &root, const fs::path &acceptance_root,
    bool allow_absent_root) {
  if (!root.is_absolute() || !acceptance_root.is_absolute() ||
      root.lexically_normal() == acceptance_root.lexically_normal())
    return facman::core::Result<CoordinatorAdmission>::failure(failure(
        "self_maintenance_lock_unsafe",
        "coordinator root must be a strict absolute acceptance descendant"));
  CoordinatorAdmission result;
  result.root = root.lexically_normal();
  result.acceptance_root = acceptance_root.lexically_normal();
  auto opened = result.acceptance.open_no_follow(result.acceptance_root);
  if (!opened.ok())
    return facman::core::Result<CoordinatorAdmission>::failure(failure(
        "self_maintenance_lock_unsafe",
        "coordinator acceptance root is unavailable", opened.detail));
  opened = result.acceptance.validate_descendant(result.root.parent_path(),
                                                  false);
  if (!opened.ok())
    return facman::core::Result<CoordinatorAdmission>::failure(failure(
        "self_maintenance_lock_unsafe",
        "coordinator parent is outside stable acceptance authority",
        opened.detail));
  opened = result.parent.open_no_follow(result.root.parent_path());
  if (!opened.ok())
    return facman::core::Result<CoordinatorAdmission>::failure(failure(
        "self_maintenance_lock_unsafe",
        "coordinator parent is not a stable plain directory", opened.detail));
  std::string unsafe_detail;
  if (!result.revalidate(unsafe_detail, true))
    return facman::core::Result<CoordinatorAdmission>::failure(failure(
        "self_maintenance_lock_unsafe",
        "coordinator ancestry is unsafe", unsafe_detail));
  facman::platform::PathIdentity identity;
  const auto observed = facman::platform::inspect_path_no_follow(result.root,
                                                                  identity);
  if (!observed.ok())
    return facman::core::Result<CoordinatorAdmission>::failure(failure(
        "self_maintenance_lock_unsafe",
        "coordinator root could not be observed", observed.detail));
  if (!identity.exists) {
    if (!allow_absent_root)
      return facman::core::Result<CoordinatorAdmission>::failure(failure(
          "self_maintenance_lock_unsafe",
          "coordinator root is absent after active-state discovery"));
    return facman::core::Result<CoordinatorAdmission>::success(
        std::move(result));
  }
  opened = result.coordinator.open_no_follow(result.root);
  if (!opened.ok() ||
      !result.acceptance.validate_descendant(result.root, false).ok() ||
      !result.parent.validate_descendant(result.root, false).ok())
    return facman::core::Result<CoordinatorAdmission>::failure(failure(
        "self_maintenance_lock_unsafe",
        "coordinator root is not a stable admitted directory", opened.detail));
  result.coordinator_exists = true;
  if (!result.revalidate(unsafe_detail))
    return facman::core::Result<CoordinatorAdmission>::failure(failure(
        "self_maintenance_lock_unsafe",
        "coordinator identity changed during admission", unsafe_detail));
  return facman::core::Result<CoordinatorAdmission>::success(std::move(result));
}

facman::core::Result<void> create_admitted_coordinator(
    CoordinatorAdmission &admission) {
  if (admission.coordinator_exists)
    return facman::core::Result<void>::success();
  std::string detail;
  if (!admission.revalidate(detail, true))
    return facman::core::Result<void>::failure(failure(
        "self_maintenance_lock_unsafe",
        "coordinator ancestry changed before creation", detail));
  std::error_code status;
  if (!fs::create_directory(admission.root, status) || status)
    return facman::core::Result<void>::failure(failure(
        "self_maintenance_lock_unsafe",
        "coordinator root could not be created under admitted authority",
        status.message()));
  auto opened = admission.coordinator.open_no_follow(admission.root);
  if (!opened.ok() ||
      !admission.acceptance.validate_descendant(admission.root, false).ok() ||
      !admission.parent.validate_descendant(admission.root, false).ok())
    return facman::core::Result<void>::failure(failure(
        "self_maintenance_lock_unsafe",
        "created coordinator root did not retain admitted authority",
        opened.detail));
  admission.coordinator_exists = true;
  if (!admission.revalidate(detail))
    return facman::core::Result<void>::failure(failure(
        "self_maintenance_lock_unsafe",
        "created coordinator identity could not be retained", detail));
  return facman::core::Result<void>::success();
}

struct Lock {
  facman::base::StableLocalLock value;
  CoordinatorAdmission admission;
  facman::platform::StableDirectoryObject operations;
  Lock() = default;
  Lock(const Lock &) = delete;
  Lock &operator=(const Lock &) = delete;
  Lock(Lock &&) noexcept = default;
  Lock &operator=(Lock &&) noexcept = default;
  ~Lock() {
    std::string ignored;
    if (value.open()) (void)value.remove_exact(ignored);
  }
};

facman::core::Result<Lock> acquire(CoordinatorAdmission admission,
                                   const std::string &operation_id) {
  if (!admission.coordinator_exists)
    return facman::core::Result<Lock>::failure(failure(
        "self_maintenance_lock_unsafe",
        "coordinator root was not admitted before lock acquisition"));
  std::string unsafe_detail;
  if (!admission.revalidate(unsafe_detail))
    return facman::core::Result<Lock>::failure(failure(
        "self_maintenance_lock_unsafe",
        "coordinator identity changed before lock acquisition",
        unsafe_detail));
  const fs::path operations = admission.root / "setup-operations";
  const auto admitted = admission.coordinator.validate_descendant(operations,
                                                                   true);
  if (!admitted.ok() ||
      facman::base::path_crosses_link_or_reparse_point(operations,
                                                       unsafe_detail))
    return facman::core::Result<Lock>::failure(failure(
        "self_maintenance_lock_unsafe",
        "global coordinator directory is outside stable authority",
        admitted.ok() ? unsafe_detail : admitted.detail));
  std::error_code status;
  if (!fs::exists(operations, status)) {
    if (status || !fs::create_directory(operations, status) || status)
      return facman::core::Result<Lock>::failure(failure(
          "self_maintenance_lock_unsafe",
          "global coordinator directory is unavailable", status.message()));
  } else if (status) {
    return facman::core::Result<Lock>::failure(failure(
        "self_maintenance_lock_unsafe", "global coordinator directory is unavailable",
        status.message()));
  }
  Lock lock;
  auto opened = lock.operations.open_no_follow(operations);
  if (!opened.ok() ||
      !admission.coordinator.validate_descendant(operations, false).ok() ||
      !admission.revalidate(unsafe_detail))
    return facman::core::Result<Lock>::failure(failure(
        "self_maintenance_lock_unsafe",
        "global coordinator directory identity changed after creation",
        opened.ok() ? unsafe_detail : opened.detail));
  lock.admission = std::move(admission);
  const fs::path path = global_lock_path(lock.admission.root);
  auto result = lock.value.create(path);
  if (result.code == facman::base::StableLockCode::exists) {
    std::string existing;
    result = lock.value.open_existing(path, 160U, existing);
    if (result.code == facman::base::StableLockCode::contended)
      return facman::core::Result<Lock>::failure(failure(
          "self_maintenance_lock_contended", "another FacMan maintenance operation is active"));
    std::string identifier_detail;
    if (!result.acquired() ||
        !facman::base::validate_identifier(existing, identifier_detail))
      return facman::core::Result<Lock>::failure(failure(
          "self_maintenance_lock_unsafe", "existing global maintenance lock is unsafe",
          result.detail));
    std::string removed;
    if (!lock.value.remove_exact(removed))
      return facman::core::Result<Lock>::failure(failure(
          "self_maintenance_lock_unsafe", "stale maintenance lock could not be removed",
          removed));
    result = lock.value.create(path);
  }
  if (!result.acquired())
    return facman::core::Result<Lock>::failure(failure(
        "self_maintenance_lock_unsafe", "global maintenance lock could not be acquired",
        result.detail));
  std::string written;
  if (!lock.value.write_text(operation_id, written))
    return facman::core::Result<Lock>::failure(failure(
        "self_maintenance_lock_unsafe", "global maintenance lock could not be written",
        written));
  return facman::core::Result<Lock>::success(std::move(lock));
}

fs::path phase_path(const Request &request, const std::string &phase) {
  return request.coordinator_root / "maintenance" / request.operation_id /
      (phase + ".v1.json");
}

bool phase_semantics(const Plan &plan, const std::string &phase,
                     const std::string &receipt) {
  const bool rollback = plan.operation == "rollback";
  const bool provider_phase = phase == "10-provider-entered" ||
      phase == "20-provider-receipt" || phase == "30-candidate-verified";
  const bool receipt_phase = phase == "20-provider-receipt" ||
      phase == "30-candidate-verified" || phase == "70-activation-recorded";
  if (rollback) {
    if (plan.provider_operation != "none" || !plan.package_sha256.empty() ||
        provider_phase) return false;
  } else if ((plan.operation != "update" && plan.operation != "downgrade") ||
             plan.provider_operation != "install_local" ||
             !digest(plan.package_sha256)) {
    return false;
  }
  return receipt_phase ? digest(receipt) : receipt.empty();
}

bool phase_exists(const Request &request, const std::string &phase) {
  std::error_code status;
  return fs::is_regular_file(phase_path(request, phase), status) && !status;
}

facman::core::Result<void> record_phase(const Request &request, const Plan &plan,
                                        const std::string &phase,
                                        const std::string &receipt = {}) {
  if (!phase_semantics(plan, phase, receipt))
    return facman::core::Result<void>::failure(failure(
        "self_maintenance_record_changed",
        "maintenance phase semantics are incompatible with the operation"));
  return ensure_immutable(phase_path(request, phase),
                          phase_json(plan, phase, receipt));
}

facman::core::Result<void> validate_operation_records(
    const Request &request, const Plan &plan) {
  const fs::path directory = request.coordinator_root / "maintenance" /
      request.operation_id;
  const std::vector<std::string> allowed{
      "00-intent", "10-provider-entered", "20-provider-receipt",
      "30-candidate-verified", "40-generation-recorded",
      "50-shortcut-cutover", "60-registration-cutover",
      "70-activation-recorded"};
  std::error_code status;
  std::size_t count = 0;
  for (fs::directory_iterator iterator(directory, status), end;
       !status && iterator != end; iterator.increment(status)) {
    if (++count > allowed.size() ||
        iterator->symlink_status(status).type() != fs::file_type::regular ||
        status)
      return facman::core::Result<void>::failure(failure(
          "self_maintenance_record_changed",
          "maintenance operation contains an unexpected object"));
    const std::string filename = iterator->path().filename().string();
    const auto match = std::find_if(allowed.begin(), allowed.end(),
        [&](const std::string &phase) {
          return filename == phase + ".v1.json";
        });
    auto bytes = match == allowed.end()
        ? facman::core::Result<std::string>::failure(failure(
              "self_maintenance_record_changed",
              "maintenance operation contains an unknown record"))
        : read_exact(iterator->path());
    auto document = bytes ? json::parse(bytes.value())
                          : facman::core::Result<json::Value>::failure(
                                bytes.error());
    const std::string receipt = document && document.value().is_object()
        ? string_field(document.value(), "receipt_sha256") : std::string();
    if (!bytes || !document ||
        !exact_keys(document.value(),
                    {"schema", "product_id", "operation", "operation_id",
                     "phase", "source_generation_id", "target_generation_id",
                     "package_sha256", "provider_operation", "state_root",
                     "acceptance_root", "receipt_sha256"}) ||
        !phase_semantics(plan, *match, receipt) ||
        bytes.value() != phase_json(plan, *match, receipt))
      return facman::core::Result<void>::failure(failure(
          "self_maintenance_record_changed",
          "immutable maintenance phase record changed"));
  }
  if (status)
    return facman::core::Result<void>::failure(failure(
        "self_maintenance_record_changed",
        "maintenance operation records changed during enumeration",
        status.message()));
  return facman::core::Result<void>::success();
}

facman::core::Result<void> effect_error(const char *code, const char *message,
                                        const EffectResult &effect) {
  return facman::core::Result<void>::failure(failure(
      effect.outcome_unknown ? "self_maintenance_outcome_unknown" : code,
      message, effect.detail));
}

std::string retirement_chain_digest(const ActivationChain &chain) {
  std::string value = "facman.self.retirement-chain.v1\n" +
      chain.activation_name + "\n" + chain.activation_sha256 + "\n";
  for (const auto &generation : chain.generations)
    value += generation.generation_id + "\n" + serialize_generation(generation);
  return hash(value);
}

std::vector<RetirementStep> retirement_steps(const ActivationChain &chain) {
  std::vector<RetirementStep> result;
  if (chain.generations.empty()) return result;
  const std::string active = chain.generations.back().generation_id;
  for (const auto &generation : chain.generations) {
    if (generation.generation_id == active) continue;
    const auto duplicate = std::find_if(result.begin(), result.end(),
        [&](const RetirementStep &step) {
          return step.generation.generation_id == generation.generation_id;
        });
    if (duplicate == result.end()) result.push_back({generation, false});
  }
  result.push_back({chain.generations.back(), true});
  return result;
}

fs::path retirement_directory(const fs::path &coordinator_root,
                              const ActivationChain &chain) {
  return coordinator_root / "retirements" /
      ("retirement." + chain.activation_sha256.substr(0, 32) + ".v1");
}

std::string retirement_intent_json(const ActivationChain &chain,
                                   const std::vector<RetirementStep> &steps) {
  json::ArrayBuilder ordered;
  for (const auto &step : steps) {
    json::ObjectBuilder item;
    item.add_string("generation_id", step.generation.generation_id);
    item.add_string("install_root",
                    facman::platform::path_to_utf8(step.generation.install_root));
    item.add_string("install_id", step.generation.install_id);
    item.add_bool("active", step.active);
    ordered.add_object(item);
  }
  json::ObjectBuilder document;
  document.add_string("schema", "facman.self_retirement_intent.v1");
  document.add_string("head_name", chain.activation_name);
  document.add_string("head_sha256", chain.activation_sha256);
  document.add_string("chain_digest", retirement_chain_digest(chain));
  document.add_array("steps", ordered);
  return document.serialize() + "\n";
}

std::string retirement_step_json(const RetirementStep &step,
                                 std::size_t sequence,
                                 const char *phase) {
  json::ObjectBuilder document;
  document.add_string("schema", "facman.self_retirement_step.v1");
  document.add_string("phase", phase);
  // ObjectBuilder has no anonymous values; use a stable numeric string to
  // avoid widening this durable format with a compatibility alias.
  document.add_string("sequence", std::to_string(sequence));
  document.add_string("generation_id", step.generation.generation_id);
  document.add_string("install_root",
                      facman::platform::path_to_utf8(step.generation.install_root));
  document.add_string("install_id", step.generation.install_id);
  document.add_bool("active", step.active);
  return document.serialize() + "\n";
}

std::string retirement_completed_json(const ActivationChain &chain,
                                      std::size_t count) {
  json::ObjectBuilder document;
  document.add_string("schema", "facman.self_retirement_completed.v1");
  document.add_string("head_name", chain.activation_name);
  document.add_string("head_sha256", chain.activation_sha256);
  document.add_string("chain_digest", retirement_chain_digest(chain));
  document.add_string("completed_steps", std::to_string(count));
  return document.serialize() + "\n";
}

fs::path retirement_step_path(const fs::path &directory, std::size_t sequence,
                              const char *phase) {
  return directory / ("step." + std::to_string(sequence) + "." + phase +
                      ".v1.json");
}

facman::core::Result<bool> exact_retirement_file(const fs::path &path,
                                                  const std::string &expected) {
  std::error_code status;
  if (!fs::exists(path, status)) {
    if (status) return facman::core::Result<bool>::failure(failure(
        "self_maintenance_retirement_recovery_required",
        "retirement marker could not be observed", status.message()));
    return facman::core::Result<bool>::success(false);
  }
  auto current = read_exact(path);
  if (!current || current.value() != expected)
    return facman::core::Result<bool>::failure(failure(
        "self_maintenance_retirement_recovery_required",
        "retirement marker is foreign, malformed, or changed",
        facman::platform::path_to_utf8(path)));
  return facman::core::Result<bool>::success(true);
}

facman::core::Result<void> validate_retirement_directory(
    const fs::path &directory, const ActivationChain &chain,
    const std::vector<RetirementStep> &steps, bool *completed) {
  *completed = false;
  std::error_code status;
  if (!fs::exists(directory, status)) {
    if (status) return facman::core::Result<void>::failure(failure(
        "self_maintenance_retirement_recovery_required",
        "retirement journal could not be observed", status.message()));
    return facman::core::Result<void>::success();
  }
  if (!fs::is_directory(directory, status) || status)
    return facman::core::Result<void>::failure(failure(
        "self_maintenance_retirement_recovery_required",
        "retirement journal path is not a directory"));
  const std::string intent = retirement_intent_json(chain, steps);
  auto exists = exact_retirement_file(directory / "00-intent.v1.json", intent);
  if (!exists) return facman::core::Result<void>::failure(exists.error());
  if (!exists.value()) return facman::core::Result<void>::failure(failure(
      "self_maintenance_retirement_recovery_required",
      "retirement journal is missing its immutable intent"));
  std::vector<std::string> allowed{"00-intent.v1.json",
      "99-completed.v1.json"};
  for (std::size_t index = 0; index < steps.size(); ++index) {
    allowed.push_back(retirement_step_path(directory, index, "entered").filename().string());
    allowed.push_back(retirement_step_path(directory, index, "completed").filename().string());
    auto entered = exact_retirement_file(retirement_step_path(directory, index, "entered"),
        retirement_step_json(steps[index], index, "entered"));
    auto done = exact_retirement_file(retirement_step_path(directory, index, "completed"),
        retirement_step_json(steps[index], index, "completed"));
    if (!entered || !done) return facman::core::Result<void>::failure(
        !entered ? entered.error() : done.error());
    if (done.value() && !entered.value()) return facman::core::Result<void>::failure(failure(
        "self_maintenance_retirement_recovery_required",
        "retirement step completed without an entered marker"));
  }
  for (fs::directory_iterator it(directory, status), end; !status && it != end;
       it.increment(status)) {
    const auto entry = it->symlink_status(status);
    if (status || entry.type() != fs::file_type::regular ||
        std::find(allowed.begin(), allowed.end(), it->path().filename().string()) ==
            allowed.end())
      return facman::core::Result<void>::failure(failure(
          "self_maintenance_retirement_recovery_required",
          "retirement journal contains a foreign or unknown record"));
  }
  if (status) return facman::core::Result<void>::failure(failure(
      "self_maintenance_retirement_recovery_required",
      "retirement journal changed during enumeration", status.message()));
  auto final = exact_retirement_file(directory / "99-completed.v1.json",
      retirement_completed_json(chain, steps.size()));
  if (!final) return facman::core::Result<void>::failure(final.error());
  if (final.value()) {
    for (std::size_t index = 0; index < steps.size(); ++index) {
      auto done = exact_retirement_file(retirement_step_path(directory, index, "completed"),
          retirement_step_json(steps[index], index, "completed"));
      if (!done || !done.value()) return facman::core::Result<void>::failure(failure(
          "self_maintenance_retirement_recovery_required",
          "retirement completion marker does not bind every step"));
    }
    *completed = true;
  }
  return facman::core::Result<void>::success();
}

constexpr std::size_t kMaximumLifecycleEpochs = 256U;
constexpr std::size_t kMaximumLifecycleManifestBytes = 64U * 1024U;
const std::string kCompatibilityEpochId(64U, '0');

facman::core::Error epoch_recovery(std::string message,
                                   std::string detail = {}) {
  return failure("self_maintenance_epoch_recovery_required", std::move(message),
                 std::move(detail));
}

std::string lifecycle_identity_bytes(const LifecycleEpoch &epoch) {
  json::ObjectBuilder object;
  object.add_string("acceptance_root", facman::platform::path_to_utf8(
      epoch.acceptance_root.lexically_normal()));
  object.add_string("genesis_generation_id", epoch.genesis_generation_id);
  object.add_string("logical_root", facman::platform::path_to_utf8(
      epoch.logical_root.lexically_normal()));
  object.add_string("predecessor_epoch_id", epoch.predecessor_epoch_id);
  object.add_string("predecessor_manifest_sha256", epoch.predecessor_manifest_sha256);
  object.add_string("predecessor_retirement_sha256", epoch.predecessor_retirement_sha256);
  object.add_string("product_id", "facman");
  object.add_string("schema", "facman.self_lifecycle_epoch_identity.v1");
  object.add_string("state_root", facman::platform::path_to_utf8(
      epoch.state_root.lexically_normal()));
  return object.serialize() + "\n";
}

std::string lifecycle_manifest_bytes(const LifecycleEpoch &epoch) {
  json::ObjectBuilder object;
  object.add_string("acceptance_root", facman::platform::path_to_utf8(
      epoch.acceptance_root.lexically_normal()));
  object.add_string("genesis_generation_id", epoch.genesis_generation_id);
  object.add_string("logical_root", facman::platform::path_to_utf8(
      epoch.logical_root.lexically_normal()));
  object.add_string("predecessor_epoch_id", epoch.predecessor_epoch_id);
  object.add_string("predecessor_manifest_sha256", epoch.predecessor_manifest_sha256);
  object.add_string("predecessor_retirement_sha256", epoch.predecessor_retirement_sha256);
  object.add_string("product_id", "facman");
  object.add_string("schema", "facman.self_lifecycle_epoch.v1");
  object.add_string("state_root", facman::platform::path_to_utf8(
      epoch.state_root.lexically_normal()));
  object.add_string("epoch_id", epoch.epoch_id);
  return object.serialize() + "\n";
}

std::string compatibility_manifest_bytes(const ActivationChain &chain) {
  json::ObjectBuilder object;
  object.add_string("activation_name", chain.activation_name);
  object.add_string("activation_sha256", chain.activation_sha256);
  object.add_string("chain_digest", retirement_chain_digest(chain));
  object.add_string("epoch_id", kCompatibilityEpochId);
  object.add_string("product_id", "facman");
  object.add_string("schema", "facman.self_lifecycle_epoch_v1_compat.v1");
  return object.serialize() + "\n";
}

bool lifecycle_string_fields(const json::Value &value,
                             std::initializer_list<const char *> names) {
  return std::all_of(names.begin(), names.end(), [&](const char *name) {
    const json::Value *field = value.find(name);
    return field != nullptr && field->is_string();
  });
}

facman::core::Result<std::string> read_epoch_manifest(
    const facman::platform::StableDirectoryObject &directory,
    const fs::path &leaf) {
  facman::platform::StableInputFile file;
  const auto opened = directory.open_child_file_no_follow_pinned(leaf, file);
  if (!opened.ok() || file.size() == 0 || file.size() > kMaximumLifecycleManifestBytes)
    return facman::core::Result<std::string>::failure(epoch_recovery(
        "epoch manifest is missing, unsafe, or over its byte limit", opened.detail));
  std::string bytes(static_cast<std::size_t>(file.size()), '\0');
  if (file.read_at(0, bytes.data(), bytes.size()) != bytes.size() ||
      !file.revalidate().ok() || !file.revalidate_path().ok() ||
      !directory.revalidate().ok())
    return facman::core::Result<std::string>::failure(epoch_recovery(
        "epoch manifest changed while it was read"));
  return facman::core::Result<std::string>::success(std::move(bytes));
}

facman::core::Result<LifecycleEpoch> parse_lifecycle_manifest(
    const std::string &bytes, const std::string &directory_name) {
  auto document = json::parse(bytes);
  const std::initializer_list<const char *> keys = {
      "acceptance_root", "genesis_generation_id", "logical_root",
      "predecessor_epoch_id", "predecessor_manifest_sha256",
      "predecessor_retirement_sha256", "product_id", "schema", "state_root",
      "epoch_id"};
  if (!document || !exact_keys(document.value(), keys) ||
      !lifecycle_string_fields(document.value(), keys) ||
      string_field(document.value(), "product_id") != "facman" ||
      string_field(document.value(), "schema") != "facman.self_lifecycle_epoch.v1")
    return facman::core::Result<LifecycleEpoch>::failure(epoch_recovery(
        "epoch manifest does not have the exact lifecycle schema"));
  LifecycleEpoch epoch;
  epoch.epoch_id = string_field(document.value(), "epoch_id");
  epoch.acceptance_root = facman::platform::path_from_utf8(
      string_field(document.value(), "acceptance_root"));
  epoch.genesis_generation_id = string_field(document.value(), "genesis_generation_id");
  epoch.logical_root = facman::platform::path_from_utf8(
      string_field(document.value(), "logical_root"));
  epoch.predecessor_epoch_id = string_field(document.value(), "predecessor_epoch_id");
  epoch.predecessor_manifest_sha256 = string_field(document.value(), "predecessor_manifest_sha256");
  epoch.predecessor_retirement_sha256 = string_field(document.value(), "predecessor_retirement_sha256");
  epoch.state_root = facman::platform::path_from_utf8(
      string_field(document.value(), "state_root"));
  if (!digest(epoch.epoch_id) || epoch.epoch_id == kCompatibilityEpochId ||
      epoch.epoch_id != directory_name ||
      !digest(epoch.genesis_generation_id) ||
      (epoch.predecessor_epoch_id.empty() != epoch.predecessor_manifest_sha256.empty()) ||
      (epoch.predecessor_epoch_id.empty() != epoch.predecessor_retirement_sha256.empty()) ||
      (!epoch.predecessor_epoch_id.empty() &&
       (!digest(epoch.predecessor_epoch_id) || !digest(epoch.predecessor_manifest_sha256) ||
        !digest(epoch.predecessor_retirement_sha256))) ||
      !epoch.acceptance_root.is_absolute() || !epoch.logical_root.is_absolute() ||
      !epoch.state_root.is_absolute() ||
      hash(lifecycle_identity_bytes(epoch)) != epoch.epoch_id ||
      bytes != lifecycle_manifest_bytes(epoch))
    return facman::core::Result<LifecycleEpoch>::failure(epoch_recovery(
        "epoch manifest identity, name, or canonical bytes are invalid"));
  epoch.manifest_sha256 = hash(bytes);
  return facman::core::Result<LifecycleEpoch>::success(std::move(epoch));
}

constexpr std::size_t kMaximumEpochGenesisRecordBytes = 64U * 1024U;
constexpr std::size_t kMaximumEpochActivationRecords = 256U;

std::string epoch_physical_generation_root_identity(const fs::path &logical_root,
                                                     const std::string &epoch_id,
                                                     const std::string &generation_id) {
  return hash("facman.self.physical-generation-root.v2\n" +
      logical_root_identity(logical_root) + "\n" + epoch_id + "\n" + generation_id + "\n");
}

fs::path epoch_generation_install_root(const fs::path &logical_root,
                                       const std::string &epoch_id,
                                       const std::string &generation_id) {
  return logical_root.parent_path() / facman::platform::path_from_utf8(
      "FacMan.generation." + epoch_physical_generation_root_identity(
          logical_root, epoch_id, generation_id));
}

std::string epoch_generation_bytes(const LifecycleEpoch &epoch,
                                   const Generation &generation) {
  json::ObjectBuilder object;
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

std::string epoch_activation_bytes(const LifecycleEpoch &epoch,
                                   const Generation &generation,
                                   const std::string &generation_sha256) {
  json::ObjectBuilder previous;
  previous.add_string("name", "");
  previous.add_string("sha256", "");
  json::ObjectBuilder object;
  object.add_string("schema", "facman.self_activation.v2");
  object.add_string("product_id", "facman");
  object.add_string("epoch_id", epoch.epoch_id);
  object.add_string("operation", "genesis");
  object.add_string("operation_id", "epoch.genesis." + generation.generation_id);
  object.add_string("generation_id", generation.generation_id);
  object.add_string("generation_record_sha256", generation_sha256);
  object.add_object("previous", previous);
  return object.serialize() + "\n";
}

std::string epoch_link_activation_bytes(
    const LifecycleEpoch &epoch, const std::string &operation,
    const std::string &operation_id, const std::string &source_generation_id,
    const std::string &target_generation_id,
    const std::string &target_generation_sha256,
    const std::string &previous_name, const std::string &previous_sha256) {
  json::ObjectBuilder previous;
  previous.add_string("name", previous_name);
  previous.add_string("sha256", previous_sha256);
  json::ObjectBuilder object;
  object.add_string("schema", "facman.self_activation.v2");
  object.add_string("product_id", "facman");
  object.add_string("epoch_id", epoch.epoch_id);
  object.add_string("operation", operation);
  object.add_string("operation_id", operation_id);
  object.add_string("source_generation_id", source_generation_id);
  object.add_string("target_generation_id", target_generation_id);
  object.add_string("generation_record_sha256", target_generation_sha256);
  object.add_object("previous", previous);
  return object.serialize() + "\n";
}

std::string epoch_generation_name(const std::string &generation_id) {
  return "generation." + generation_id + ".v2.json";
}

std::string epoch_activation_name(const std::string &generation_id) {
  return "activation.epoch.genesis." + generation_id + ".v2.json";
}

std::string epoch_generation_staging_name(const std::string &generation_id) {
  return "generation.staging." + generation_id + ".v2.json";
}

std::string epoch_activation_staging_name(const std::string &generation_id) {
  return "activation.staging.epoch.genesis." + generation_id + ".v2.json";
}

facman::core::Result<std::string> read_epoch_relative_bounded(
    const facman::platform::StableDirectoryObject &parent,
    const fs::path &leaf, std::size_t maximum_size) {
  facman::platform::StableInputFile first;
  const auto opened = parent.open_child_file_no_follow_pinned(leaf, first);
  if (!opened.ok() || first.size() == 0 || first.size() > maximum_size)
    return facman::core::Result<std::string>::failure(epoch_recovery(
        "epoch record is missing, unsafe, or over its byte limit", opened.detail));
  std::string bytes(static_cast<std::size_t>(first.size()), '\0');
  if (first.read_at(0, bytes.data(), bytes.size()) != bytes.size() || !first.revalidate().ok())
    return facman::core::Result<std::string>::failure(epoch_recovery(
        "epoch record changed while it was read"));
  facman::platform::StableInputFile reopened;
  if (!parent.open_child_file_no_follow_pinned(leaf, reopened).ok() ||
      !first.identity().unchanged(reopened.identity()) || !reopened.revalidate().ok() ||
      !parent.revalidate().ok())
    return facman::core::Result<std::string>::failure(epoch_recovery(
        "epoch record named identity changed while it was read"));
  return facman::core::Result<std::string>::success(std::move(bytes));
}

struct PinnedLifecycleEpochScope {
  facman::platform::StableDirectoryObject coordinator;
  facman::platform::StableDirectoryObject epochs;
  facman::platform::StableDirectoryObject epoch;

  facman::core::Result<void> open(const fs::path &root, const std::string &epoch_id,
                                  bool write_capable = false) {
    auto opened_root = write_capable ? coordinator.open_no_follow_for_relative_writes(root)
                                     : coordinator.open_no_follow(root);
    if (!opened_root.ok())
      return facman::core::Result<void>::failure(epoch_recovery(
          "epoch directory could not be opened from its held ancestors", opened_root.detail));
    auto opened_epochs = write_capable
        ? coordinator.open_child_directory_no_follow_for_relative_writes("epochs", epochs)
        : coordinator.open_child_directory_no_follow("epochs", epochs);
    if (!opened_epochs.ok())
      return facman::core::Result<void>::failure(epoch_recovery(
          "epoch directory could not be opened from its held ancestors", opened_epochs.detail));
    auto opened_epoch = write_capable
        ? epochs.open_child_directory_no_follow_for_relative_writes(epoch_id, epoch)
        : epochs.open_child_directory_no_follow(epoch_id, epoch);
    if (!opened_epoch.ok())
      return facman::core::Result<void>::failure(epoch_recovery(
          "epoch directory could not be opened from its held ancestors", opened_epoch.detail));
    auto bytes = read("epoch.v1.json");
    auto parsed = bytes ? parse_lifecycle_manifest(bytes.value(), epoch_id)
                        : facman::core::Result<LifecycleEpoch>::failure(bytes.error());
    if (!parsed) return facman::core::Result<void>::failure(parsed.error());
    return facman::core::Result<void>::success();
  }

  facman::core::Result<std::string> read(const fs::path &leaf) const {
    auto bytes = read_epoch_relative_bounded(epoch, leaf, kMaximumEpochGenesisRecordBytes);
    if (!bytes || !epoch.revalidate().ok() || !epochs.revalidate().ok() || !coordinator.revalidate().ok())
      return facman::core::Result<std::string>::failure(epoch_recovery(
          "epoch record named identity changed while it was read"));
    return bytes;
  }
};

bool exact_epoch_generation_paths(const LifecycleEpoch &epoch,
                                  const Generation &generation) {
  const fs::path root = epoch_generation_install_root(
      epoch.logical_root, epoch.epoch_id, generation.generation_id);
  return generation.install_id == "facman.self.epoch." + epoch.epoch_id +
          ".generation." + generation.generation_id &&
      same_path(generation.install_root, root) &&
      same_path(generation.gui, root / "generations" / generation.product_version / "FacMan.exe") &&
      same_path(generation.maintenance_launcher, root / "maintenance" / "FacManSetup.exe") &&
      same_path(generation.logical_root, epoch.logical_root) &&
      same_path(generation.state_root, epoch.state_root) &&
      same_path(generation.acceptance_root, epoch.acceptance_root);
}

facman::core::Result<Generation> parse_epoch_generation(
    const LifecycleEpoch &epoch, const PinnedLifecycleEpochScope &scope,
    const std::string &generation_id, std::string *bytes_out = nullptr) {
  if (!digest(generation_id)) return facman::core::Result<Generation>::failure(
      epoch_recovery("epoch generation id is invalid"));
  facman::platform::StableDirectoryObject generations;
  if (!scope.epoch.open_child_directory_no_follow("generations", generations).ok())
    return facman::core::Result<Generation>::failure(epoch_recovery(
        "epoch generations directory is unavailable"));
  auto read = read_epoch_relative_bounded(generations, epoch_generation_name(generation_id),
                                          kMaximumEpochGenesisRecordBytes);
  if (!read || !generations.revalidate().ok() || !scope.epoch.revalidate().ok() ||
      !scope.epochs.revalidate().ok() || !scope.coordinator.revalidate().ok())
    return facman::core::Result<Generation>::failure(read ? epoch_recovery(
        "epoch generation record changed while read") : read.error());
  std::string bytes = read.take_value();
  auto document = json::parse(bytes);
  const std::initializer_list<const char *> keys = {"schema", "product_id", "epoch_id",
      "generation_id", "product_version", "package_sha256", "facman_source_revision",
      "universal_setup_revision", "install_id", "install_root", "logical_root", "state_root",
      "acceptance_root", "gui", "maintenance_launcher"};
  if (!document || !exact_keys(document.value(), keys) ||
      !lifecycle_string_fields(document.value(), keys) ||
      string_field(document.value(), "schema") != "facman.self_generation.v2" ||
      string_field(document.value(), "product_id") != "facman" ||
      string_field(document.value(), "epoch_id") != epoch.epoch_id ||
      string_field(document.value(), "generation_id") != generation_id)
    return facman::core::Result<Generation>::failure(epoch_recovery(
        "epoch generation record has an incompatible exact schema"));
  Generation result;
  result.generation_id = generation_id;
  result.product_version = string_field(document.value(), "product_version");
  result.package_sha256 = string_field(document.value(), "package_sha256");
  result.facman_source_revision = string_field(document.value(), "facman_source_revision");
  result.universal_setup_revision = string_field(document.value(), "universal_setup_revision");
  result.install_id = string_field(document.value(), "install_id");
  result.install_root = facman::platform::path_from_utf8(string_field(document.value(), "install_root"));
  result.logical_root = facman::platform::path_from_utf8(string_field(document.value(), "logical_root"));
  result.state_root = facman::platform::path_from_utf8(string_field(document.value(), "state_root"));
  result.acceptance_root = facman::platform::path_from_utf8(string_field(document.value(), "acceptance_root"));
  result.gui = facman::platform::path_from_utf8(string_field(document.value(), "gui"));
  result.maintenance_launcher = facman::platform::path_from_utf8(string_field(document.value(), "maintenance_launcher"));
  Semver version;
  if (!digest(result.package_sha256) || !revision(result.facman_source_revision) ||
      !revision(result.universal_setup_revision) || !semver(result.product_version, version) ||
      generation_identity(generation_descriptor(result), result.package_sha256) != generation_id ||
      !exact_epoch_generation_paths(epoch, result) || bytes != epoch_generation_bytes(epoch, result))
    return facman::core::Result<Generation>::failure(epoch_recovery(
        "epoch generation identity or paths are invalid"));
  if (bytes_out != nullptr) *bytes_out = std::move(bytes);
  return facman::core::Result<Generation>::success(std::move(result));
}

facman::core::Result<std::optional<ActiveState>> discover_epoch_genesis_state(
    const LifecycleEpoch &epoch, const PinnedLifecycleEpochScope &scope,
    const Generation *expected = nullptr, bool allow_incomplete = false,
    const std::string *allowed_maintenance_operation = nullptr) {
  std::vector<fs::path> children;
  if (!scope.epoch.list_child_names_bounded(4U, children).ok())
    return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
        "epoch directory could not be enumerated through its held handle"));
  const auto has = [&](const char *name) {
    return std::find(children.begin(), children.end(), fs::path(name)) != children.end();
  };
  if (!has("epoch.v1.json")) return facman::core::Result<std::optional<ActiveState>>::failure(
      epoch_recovery("epoch is missing its immutable manifest"));
  for (const auto &child : children)
    if (child != "epoch.v1.json" && child != "generations" && child != "activations") {
      if (child == "maintenance" && allowed_maintenance_operation != nullptr) {
        facman::platform::StableDirectoryObject maintenance, operation;
        std::vector<fs::path> operation_names, records;
        if (!scope.epoch.open_child_directory_no_follow("maintenance", maintenance).ok() ||
            !maintenance.list_child_names_bounded(1U, operation_names).ok() ||
            operation_names.size() > 1U ||
            (!operation_names.empty() && operation_names.front().string() !=
                *allowed_maintenance_operation) ||
            (!operation_names.empty() && !maintenance.open_child_directory_no_follow(
                *allowed_maintenance_operation, operation).ok()) ||
             (!operation_names.empty() &&
              (!operation.list_child_names_bounded(6U, records).ok() ||
               records.size() > 5U ||
               ([&] {
                 const std::vector<fs::path> finals = {
                     "00-handoff-ready.v2.json", "10-provider-apply-bound.v2.json",
                     "20-provider-apply-entered.v2.json", "30-provider-outcome.v2.json",
                     "40-provider-verified.v2.json"};
                 for (std::size_t i = 0; i < records.size(); ++i) {
                   const fs::path staging = finals[i].string().substr(
                       0, finals[i].string().size() - 7U) + "staging.v2.json";
                   if (records[i] != finals[i] &&
                       !(i + 1U == records.size() && records[i] == staging)) return true;
                 }
                 return false;
               }()))))
          return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
              "epoch maintenance recovery state is not the exact targeted handoff"));
        continue;
      }
      return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
          child == "maintenance"
              ? "epoch maintenance recovery state requires targeted recovery"
              : "epoch contains a foreign or unsupported entry"));
    }
  if (!has("generations") && !has("activations")) {
    return facman::core::Result<std::optional<ActiveState>>::success({});
  }
  if (!has("generations") || !has("activations")) {
    if (!allow_incomplete || !has("generations"))
      return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
          "epoch contains partial genesis directories"));
    facman::platform::StableDirectoryObject generations;
    std::vector<fs::path> names;
    if (!scope.epoch.open_child_directory_no_follow("generations", generations).ok() ||
        !generations.list_child_names_bounded(2U, names).ok())
      return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
          "epoch generation-only state is foreign or mismatched"));
    if (names.empty()) return facman::core::Result<std::optional<ActiveState>>::success({});
    if (expected != nullptr && names.size() == 1U &&
        names.front() == epoch_generation_staging_name(expected->generation_id))
      return facman::core::Result<std::optional<ActiveState>>::success({});
    if (names.size() != 1U || names.front() != epoch_generation_name(epoch.genesis_generation_id))
      return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
          "epoch generation-only state is foreign or mismatched"));
    std::string bytes;
    auto generation = parse_epoch_generation(epoch, scope, epoch.genesis_generation_id, &bytes);
    if (!generation || (expected != nullptr && bytes != epoch_generation_bytes(epoch, *expected)))
      return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
          "epoch generation-only state does not match the requested genesis"));
    return facman::core::Result<std::optional<ActiveState>>::success({});
  }
  facman::platform::StableDirectoryObject generations, activations;
  if (!scope.epoch.open_child_directory_no_follow("generations", generations).ok() ||
      !scope.epoch.open_child_directory_no_follow("activations", activations).ok())
    return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
        "epoch genesis directories are not plain directories"));
  std::vector<fs::path> generation_names, activation_names;
  if (!generations.list_child_names_bounded(kMaximumEpochActivationRecords, generation_names).ok() ||
      !activations.list_child_names_bounded(kMaximumEpochActivationRecords, activation_names).ok())
    return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
        "epoch genesis directories could not be enumerated"));
  if (generation_names.empty() && activation_names.empty() && allow_incomplete)
    return facman::core::Result<std::optional<ActiveState>>::success({});
  if (allow_incomplete && expected != nullptr && generation_names.size() == 1U &&
      generation_names.front() == epoch_generation_staging_name(expected->generation_id) &&
      activation_names.empty())
    return facman::core::Result<std::optional<ActiveState>>::success({});
  if (activation_names.empty() && allow_incomplete && generation_names.size() == 1U &&
      generation_names.front() == epoch_generation_name(epoch.genesis_generation_id)) {
    std::string generation_bytes;
    auto generation = parse_epoch_generation(epoch, scope, epoch.genesis_generation_id,
                                             &generation_bytes);
    if (!generation || (expected != nullptr &&
        generation_bytes != epoch_generation_bytes(epoch, *expected)))
      return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
          "epoch generation-only state does not match the requested genesis"));
    return facman::core::Result<std::optional<ActiveState>>::success({});
  }
  if (allow_incomplete && expected != nullptr && generation_names.size() == 1U &&
      generation_names.front() == epoch_generation_name(expected->generation_id) &&
      activation_names.size() == 1U &&
      activation_names.front() == epoch_activation_staging_name(expected->generation_id))
    return facman::core::Result<std::optional<ActiveState>>::success({});

  struct Node {
    std::string name;
    std::string digest;
    std::string operation;
    std::string source_generation_id;
    std::string target_generation_id;
    std::string target_generation_sha256;
    std::string previous_name;
    std::string previous_sha256;
    bool genesis = false;
    Generation target;
  };
  struct HeldRecord {
    fs::path name;
    std::string bytes;
    facman::platform::StableInputFile file;
  };
  std::vector<HeldRecord> held_activations;
  std::vector<HeldRecord> held_generations;
  held_activations.reserve(activation_names.size());
  held_generations.reserve(activation_names.size());
  std::vector<Node> nodes;
  nodes.reserve(activation_names.size());
  for (const fs::path &entry : activation_names) {
    const std::string name = entry.string();
    std::string identifier_detail;
    if (name.empty() || entry != entry.filename())
      return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
          "epoch activation filename is invalid"));
    HeldRecord held{entry, {}, {}};
    if (!activations.open_child_file_no_follow_pinned(entry, held.file).ok() ||
        held.file.size() == 0 || held.file.size() > kMaximumEpochGenesisRecordBytes)
      return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
          "epoch activation record is missing, linked, or over budget"));
    held.bytes.resize(static_cast<std::size_t>(held.file.size()));
    if (held.file.read_at(0, held.bytes.data(), held.bytes.size()) != held.bytes.size() ||
        !held.file.revalidate().ok() || !held.file.revalidate_path().ok())
      return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
          "epoch activation record changed while it was read"));
    notify_epoch_record_pinned(activations.path() / entry);
    const std::string &activation = held.bytes;
    auto document = json::parse(activation);
    const json::Value *previous = document && document.value().is_object()
        ? document.value().find("previous") : nullptr;
    const bool genesis = document && string_field(document.value(), "operation") == "genesis";
    const std::initializer_list<const char *> genesis_keys = {"schema", "product_id", "epoch_id",
        "operation", "operation_id", "generation_id", "generation_record_sha256", "previous"};
    const std::initializer_list<const char *> link_keys = {"schema", "product_id", "epoch_id",
        "operation", "operation_id", "source_generation_id", "target_generation_id",
        "generation_record_sha256", "previous"};
    const bool shape = document && exact_keys(document.value(), genesis ? genesis_keys : link_keys);
    const bool previous_shape = previous != nullptr && exact_keys(*previous, {"name", "sha256"}) &&
        previous->find("name")->is_string() && previous->find("sha256")->is_string();
    const std::string operation = document ? string_field(document.value(), "operation") : std::string();
    const std::string operation_id = document ? string_field(document.value(), "operation_id") : std::string();
    const std::string source_id = genesis
        ? string_field(document.value(), "generation_id")
        : string_field(document.value(), "source_generation_id");
    const std::string target_id = genesis
        ? string_field(document.value(), "generation_id")
        : string_field(document.value(), "target_generation_id");
    const std::string target_sha = document
        ? string_field(document.value(), "generation_record_sha256") : std::string();
    const std::string previous_name = previous != nullptr ? string_field(*previous, "name") : std::string();
    const std::string previous_sha = previous != nullptr ? string_field(*previous, "sha256") : std::string();
    const bool linked_operation = operation == "update" || operation == "downgrade";
    Generation genesis_target;
    genesis_target.generation_id = target_id;
    if (!shape || !previous_shape || string_field(document.value(), "schema") !=
            "facman.self_activation.v2" || string_field(document.value(), "product_id") != "facman" ||
        string_field(document.value(), "epoch_id") != epoch.epoch_id ||
        (!genesis && !facman::base::validate_identifier(operation_id, identifier_detail)) ||
        !digest(source_id) ||
        !digest(target_id) || !digest(target_sha) || (previous_name.empty() != previous_sha.empty()) ||
        (!previous_name.empty() && (fs::path(previous_name) !=
            fs::path(previous_name).filename() || !digest(previous_sha))) ||
        (genesis && (operation_id != "epoch.genesis." + epoch.genesis_generation_id ||
            source_id != epoch.genesis_generation_id || target_id != epoch.genesis_generation_id ||
            !previous_name.empty() || name != epoch_activation_name(epoch.genesis_generation_id))) ||
        (!genesis && (!linked_operation || previous_name.empty() ||
            name != "activation." + operation_id + ".v2.json")) ||
        activation != (genesis
            ? epoch_activation_bytes(epoch, genesis_target, target_sha)
            : epoch_link_activation_bytes(epoch, operation, operation_id, source_id, target_id,
                                          target_sha, previous_name, previous_sha)))
      return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
          "epoch activation record has an incompatible exact schema"));
    nodes.push_back({name, hash(activation), operation, source_id, target_id, target_sha,
                     previous_name, previous_sha, genesis, {}});
    held_activations.push_back(std::move(held));
  }
  if (!activations.revalidate().ok() || !scope.epoch.revalidate().ok() ||
      !scope.epochs.revalidate().ok() || !scope.coordinator.revalidate().ok())
    return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
        "epoch activation records changed while read"));

  std::size_t genesis_count = 0;
  Node *genesis = nullptr;
  for (Node &node : nodes) {
    if (node.genesis) { ++genesis_count; genesis = &node; }
    std::string generation_bytes;
    auto target = parse_epoch_generation(epoch, scope, node.target_generation_id,
                                         &generation_bytes);
    if (!target || hash(generation_bytes) != node.target_generation_sha256)
      return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
          "epoch activation references a missing, changed, or foreign generation"));
    HeldRecord held{epoch_generation_name(node.target_generation_id), {}, {}};
    if (!generations.open_child_file_no_follow_pinned(held.name, held.file).ok() ||
        held.file.size() != generation_bytes.size())
      return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
          "epoch generation record changed while it was pinned"));
    held.bytes.resize(generation_bytes.size());
    if (held.file.read_at(0, held.bytes.data(), held.bytes.size()) != held.bytes.size() ||
        held.bytes != generation_bytes || !held.file.revalidate().ok() ||
        !held.file.revalidate_path().ok())
      return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
          "epoch generation record changed while it was pinned"));
    notify_epoch_record_pinned(generations.path() / held.name);
    held_generations.push_back(std::move(held));
    node.target = target.take_value();
  }
  if (genesis_count != 1U || genesis == nullptr)
    return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
        "epoch activation chain must contain exactly one reserved genesis"));
  if (expected != nullptr && (genesis->target_generation_id != expected->generation_id ||
      epoch_generation_bytes(epoch, genesis->target) != epoch_generation_bytes(epoch, *expected)))
    return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
        "epoch genesis generation does not match the requested genesis"));

  std::vector<Node *> ordered{genesis};
  Node *cursor = genesis;
  for (;;) {
    Node *child = nullptr;
    for (Node &candidate : nodes) {
      if (candidate.previous_name != cursor->name) continue;
      if (candidate.previous_sha256 != cursor->digest ||
          candidate.source_generation_id != cursor->target_generation_id)
        return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
            "epoch activation predecessor name, digest, or generation is invalid"));
      Semver source_version, target_version;
      if (!semver(cursor->target.product_version, source_version) ||
          !semver(candidate.target.product_version, target_version) ||
          (candidate.operation == "update" &&
           compare(target_version, source_version) <= 0) ||
          (candidate.operation == "downgrade" &&
           compare(target_version, source_version) >= 0))
        return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
            "epoch activation semantic version direction is invalid"));
      if (child != nullptr)
        return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
            "epoch activation chain contains a fork"));
      child = &candidate;
    }
    if (child == nullptr) break;
    if (std::find(ordered.begin(), ordered.end(), child) != ordered.end())
      return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
          "epoch activation chain contains a cycle"));
    ordered.push_back(child);
    cursor = child;
  }
  if (ordered.size() != nodes.size())
    return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
        "epoch activation chain contains an orphan, cycle, or broken predecessor"));
  std::vector<std::string> expected_generation_names;
  expected_generation_names.reserve(nodes.size());
  for (const Node &node : nodes) expected_generation_names.push_back(
      epoch_generation_name(node.target_generation_id));
  std::sort(expected_generation_names.begin(), expected_generation_names.end());
  expected_generation_names.erase(
      std::unique(expected_generation_names.begin(), expected_generation_names.end()),
      expected_generation_names.end());
  std::vector<std::string> observed_generation_names;
  observed_generation_names.reserve(generation_names.size());
  for (const fs::path &name : generation_names)
    observed_generation_names.push_back(name.string());
  std::sort(observed_generation_names.begin(), observed_generation_names.end());
  if (expected_generation_names != observed_generation_names)
    return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
        "epoch generation records contain duplicates, extras, or omissions"));
  std::vector<fs::path> final_generation_names, final_activation_names;
  if (!generations.list_child_names_bounded(kMaximumEpochActivationRecords,
                                             final_generation_names).ok() ||
      !activations.list_child_names_bounded(kMaximumEpochActivationRecords,
                                             final_activation_names).ok() ||
      final_generation_names != generation_names || final_activation_names != activation_names ||
      !generations.revalidate().ok() || !activations.revalidate().ok() ||
      !scope.epoch.revalidate().ok() || !scope.epochs.revalidate().ok() ||
      !scope.coordinator.revalidate().ok())
    return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
        "epoch activation or generation names changed during discovery"));
  for (HeldRecord &record : held_activations)
    if (!held_file_matches_bytes(record.file, record.bytes))
      return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
          "epoch activation record changed before discovery completed"));
  for (HeldRecord &record : held_generations)
    if (!held_file_matches_bytes(record.file, record.bytes))
      return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
          "epoch generation record changed before discovery completed"));
  ActiveState state{cursor->target, {}, cursor->name, cursor->digest};
  if (ordered.size() > 1U) state.previous = ordered[ordered.size() - 2U]->target;
  return facman::core::Result<std::optional<ActiveState>>::success(
      std::optional<ActiveState>(std::move(state)));
}

facman::core::Result<facman::platform::StableDirectoryObject> open_or_create_epoch_child(
    const facman::platform::StableDirectoryObject &parent, const char *name) {
  facman::platform::StableDirectoryObject child;
  auto opened = parent.open_child_directory_no_follow_for_relative_writes(name, child);
  if (!opened.ok()) opened = parent.create_child_directory_exclusive(name, child);
  if (!opened.ok()) return facman::core::Result<facman::platform::StableDirectoryObject>::failure(
      epoch_recovery("epoch child directory could not be opened or created", opened.detail));
  return facman::core::Result<facman::platform::StableDirectoryObject>::success(std::move(child));
}

facman::core::Result<void> publish_epoch_record(
    const facman::platform::StableDirectoryObject &directory,
    const std::string &staging_name, const std::string &final_name,
    const std::string &bytes) {
  facman::platform::StableInputFile existing;
  const auto opened = directory.open_child_file_no_follow_pinned(final_name, existing);
  if (opened.ok()) {
    auto current = read_epoch_relative_bounded(directory, final_name,
                                               kMaximumEpochGenesisRecordBytes);
    if (!current || current.value() != bytes || !directory.flush_metadata().ok())
      return facman::core::Result<void>::failure(epoch_recovery(
          "epoch immutable record already exists with different bytes"));
    return facman::core::Result<void>::success();
  }
  std::vector<fs::path> names;
  // A provider continuation may have four durable predecessors plus one
  // canonical staging tail; other epoch journals use fewer entries.
  if (!directory.list_child_names_bounded(6U, names).ok())
    return facman::core::Result<void>::failure(epoch_recovery(
        "epoch record directory could not be enumerated for recovery"));
  const auto present = [&](const std::string &name) {
    return std::find(names.begin(), names.end(), fs::path(name)) != names.end();
  };
  if (present(final_name)) return facman::core::Result<void>::failure(epoch_recovery(
      "epoch final record is unsafe or changed"));
  facman::platform::DurableOutputFile output;
  if (present(staging_name)) {
    facman::platform::FileIdentity staging_identity;
    std::string staged_bytes;
    bool staged_ok = false;
    {
      facman::platform::StableInputFile staging;
      const auto pinned = directory.open_child_file_no_follow_pinned(staging_name, staging);
      if (pinned.ok() && staging.size() != 0 &&
          staging.size() <= kMaximumEpochGenesisRecordBytes) {
        staged_bytes.resize(static_cast<std::size_t>(staging.size()));
        staged_ok = staging.read_at(0, staged_bytes.data(), staged_bytes.size()) ==
                staged_bytes.size() && staging.revalidate().ok() &&
            staging.revalidate_path().ok() && directory.revalidate().ok();
        if (staged_ok) staging_identity = staging.identity();
      }
    }
    if (!staged_ok || staged_bytes != bytes || !staging_identity.regular_file ||
        !directory.reopen_child_file_no_follow_for_relative_publish(staging_name,
            staging_identity, kMaximumEpochGenesisRecordBytes, output).ok())
      return facman::core::Result<void>::failure(epoch_recovery(
          "epoch staging record is partial, foreign, or substituted"));
  } else {
    const auto staged = directory.create_child_file_exclusive(staging_name,
        kMaximumEpochGenesisRecordBytes, output);
    if (!staged.ok() || output.write_at(0, bytes.data(), bytes.size()) != bytes.size())
      return facman::core::Result<void>::failure(epoch_recovery(
          "epoch record staging could not be completed", staged.detail));
  }
  const auto published = output.publish_sibling_no_replace(final_name);
  if (!published.ok()) {
    auto observed = read_epoch_relative_bounded(directory, final_name,
                                                kMaximumEpochGenesisRecordBytes);
    if (observed && observed.value() == bytes && directory.flush_metadata().ok())
        return facman::core::Result<void>::success();
    return facman::core::Result<void>::failure(epoch_recovery(
        "epoch record publication did not reach a verified state", published.detail));
  }
  if (!directory.flush_metadata().ok()) return facman::core::Result<void>::failure(
      epoch_recovery("epoch record directory could not be flushed"));
  auto final_bytes = read_epoch_relative_bounded(directory, final_name,
                                                 kMaximumEpochGenesisRecordBytes);
  if (!final_bytes || final_bytes.value() != bytes)
    return facman::core::Result<void>::failure(epoch_recovery(
        "epoch published record changed before its final identity was verified"));
  return facman::core::Result<void>::success();
}

facman::core::Result<void> validate_epoch_history(LifecycleEpoch &epoch,
                                                   const fs::path &root,
                                                   bool compatibility) {
  if (!compatibility)
    return digest(epoch.genesis_generation_id)
        ? facman::core::Result<void>::success()
        : facman::core::Result<void>::failure(epoch_recovery(
            "an initialized epoch must reserve one exact genesis generation"));
  auto chain = discover_activation_chain(root);
  if (!chain) return facman::core::Result<void>::failure(
      compatibility ? chain.error() : epoch_recovery("epoch activation history is invalid",
                                                       chain.error().message));
  if (!chain.value().has_value()) {
    for (const char *name : {"generations", "retirements", "maintenance"}) {
      std::error_code status;
      if (fs::exists(root / name, status) && !status)
        return facman::core::Result<void>::failure(epoch_recovery(
            "epoch has generation or retirement state without an activation history"));
      if (status) return facman::core::Result<void>::failure(epoch_recovery(
          "epoch state could not be observed", status.message()));
    }
    return facman::core::Result<void>::success();
  }
  const ActivationChain &history = *chain.value();
  if (epoch.genesis_generation_id != history.generations.front().generation_id)
    return facman::core::Result<void>::failure(epoch_recovery(
        "epoch genesis generation does not bind the activation genesis"));
  for (const Generation &generation : history.generations) {
    if (!same_path(generation.logical_root, epoch.logical_root) ||
        !same_path(generation.state_root, epoch.state_root) ||
        !same_path(generation.acceptance_root, epoch.acceptance_root))
      return facman::core::Result<void>::failure(epoch_recovery(
          "epoch activation generations do not share the epoch authority"));
  }
  auto active = discover_active(root);
  if (!active) return facman::core::Result<void>::failure(
      compatibility ? active.error() : epoch_recovery("epoch retirement is incomplete",
                                                       active.error().message));
  if (active.value().has_value()) return facman::core::Result<void>::success();
  const auto steps = retirement_steps(history);
  const fs::path complete = retirement_directory(root, history) / "99-completed.v1.json";
  auto marker = read_exact(complete);
  const std::string expected = retirement_completed_json(history, steps.size());
  if (!marker || marker.value() != expected)
    return facman::core::Result<void>::failure(epoch_recovery(
        "completed epoch retirement marker is unavailable or changed"));
  epoch.retirement_sha256 = hash(marker.value());
  return facman::core::Result<void>::success();
}

bool lifecycle_roots_equal(const LifecycleEpoch &left, const LifecycleEpoch &right) {
  return same_path(left.acceptance_root, right.acceptance_root) &&
      same_path(left.logical_root, right.logical_root) &&
      same_path(left.state_root, right.state_root);
}

facman::core::Result<LifecycleEpochChain> discover_lifecycle_epoch_chain_impl(
    const fs::path &coordinator_root, const std::string &recovery_epoch_id = {},
    const Generation *recovery_generation = nullptr,
    const std::string &allowed_maintenance_operation = {},
    const std::string &allowed_maintenance_epoch_id = {}) {
  if (!coordinator_root.is_absolute())
    return facman::core::Result<LifecycleEpochChain>::failure(failure(
        "self_maintenance_input_invalid", "coordinator root must be absolute"));
  LifecycleEpochChain result;
  std::error_code status;
  if (!fs::exists(coordinator_root, status)) {
    if (status) return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
        "coordinator root could not be observed", status.message()));
    return facman::core::Result<LifecycleEpochChain>::success(std::move(result));
  }
  facman::platform::StableDirectoryObject coordinator;
  if (!coordinator.open_no_follow(coordinator_root).ok())
    return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
        "coordinator root is not a plain directory"));

  // A real v1 activation chain becomes the non-persisted compatibility
  // predecessor only after the existing generation and retirement validators
  // have accepted the whole flat layout.
  auto flat = discover_activation_chain(coordinator_root);
  if (!flat) return facman::core::Result<LifecycleEpochChain>::failure(flat.error());
  if (flat.value().has_value()) {
    LifecycleEpoch sentinel;
    sentinel.epoch_id = kCompatibilityEpochId;
    sentinel.compatibility_epoch = true;
    sentinel.genesis_generation_id = flat.value()->generations.front().generation_id;
    sentinel.acceptance_root = flat.value()->generations.front().acceptance_root;
    sentinel.logical_root = flat.value()->generations.front().logical_root;
    sentinel.state_root = flat.value()->generations.front().state_root;
    auto validated = validate_epoch_history(sentinel, coordinator_root, true);
    if (!validated) return facman::core::Result<LifecycleEpochChain>::failure(validated.error());
    sentinel.manifest_sha256 = hash(compatibility_manifest_bytes(*flat.value()));
    result.epochs.push_back(std::move(sentinel));
  } else {
    for (const char *name : {"generations", "retirements", "maintenance"}) {
      if (fs::exists(coordinator_root / name, status) && !status)
        return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
            "flat coordinator has state without a valid activation history"));
      if (status) return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
          "flat coordinator state could not be observed", status.message()));
    }
  }

  const fs::path epochs_path = coordinator_root / "epochs";
  if (!fs::exists(epochs_path, status)) {
    if (status) return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
        "epoch root could not be observed", status.message()));
    return facman::core::Result<LifecycleEpochChain>::success(std::move(result));
  }
  facman::platform::StableDirectoryObject epochs;
  if (!coordinator.open_child_directory_no_follow( "epochs", epochs).ok())
    return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
        "epoch root is not a plain directory"));
  std::vector<fs::path> epoch_names;
  if (!epochs.list_child_names_bounded(kMaximumLifecycleEpochs, epoch_names).ok())
    return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
        "epoch root exceeds its entry limit or changed during enumeration"));
  for (const fs::path &entry : epoch_names) {
    const std::string name = entry.string();
    if (!digest(name) || name == kCompatibilityEpochId)
      return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
          "epoch root contains a non-epoch or linked entry"));
    facman::platform::StableDirectoryObject epoch_directory;
    if (!epochs.open_child_directory_no_follow(name, epoch_directory).ok())
      return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
          "epoch directory could not be pinned"));
    PinnedLifecycleEpochScope scope;
    auto pinned = scope.open(coordinator_root, name);
    if (!pinned) return facman::core::Result<LifecycleEpochChain>::failure(pinned.error());
    auto bytes = scope.read("epoch.v1.json");
    if (!bytes) return facman::core::Result<LifecycleEpochChain>::failure(bytes.error());
    auto epoch = parse_lifecycle_manifest(bytes.value(), name);
    if (!epoch) return facman::core::Result<LifecycleEpochChain>::failure(epoch.error());
    const bool recovery_tail = !recovery_epoch_id.empty() && name == recovery_epoch_id;
    auto genesis = discover_epoch_genesis_state(epoch.value(), scope,
        recovery_tail ? recovery_generation : nullptr, recovery_tail,
        (!allowed_maintenance_operation.empty() && name == allowed_maintenance_epoch_id)
            ? &allowed_maintenance_operation : nullptr);
    if (!genesis) return facman::core::Result<LifecycleEpochChain>::failure(genesis.error());
    if (!epoch_directory.revalidate().ok())
      return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
          "epoch state changed while its pinned children were validated"));
    result.epochs.push_back(epoch.take_value());
  }
  if (!epochs.revalidate().ok() || !coordinator.revalidate().ok())
    return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
        "epoch directories changed during discovery"));

  std::vector<const LifecycleEpoch *> real;
  for (const LifecycleEpoch &epoch : result.epochs)
    if (!epoch.compatibility_epoch) real.push_back(&epoch);
  if (real.empty()) return facman::core::Result<LifecycleEpochChain>::success(std::move(result));
  const LifecycleEpoch *root = nullptr;
  const bool has_sentinel = !result.epochs.empty() &&
      result.epochs.front().compatibility_epoch;
  std::vector<const LifecycleEpoch *> referenced;
  for (const LifecycleEpoch *epoch : real) {
    if (epoch->predecessor_epoch_id.empty() ||
        (has_sentinel && epoch->predecessor_epoch_id == kCompatibilityEpochId)) {
      if (root != nullptr) return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
          "lifecycle epoch graph has more than one genesis"));
      if (epoch->predecessor_epoch_id == kCompatibilityEpochId) {
        const LifecycleEpoch &sentinel = result.epochs.front();
        if (sentinel.retirement_sha256.empty() ||
            epoch->predecessor_manifest_sha256 != sentinel.manifest_sha256 ||
            epoch->predecessor_retirement_sha256 != sentinel.retirement_sha256)
          return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
              "compatibility predecessor digest or completed retirement is invalid"));
      }
      root = epoch;
      continue;
    }
    const LifecycleEpoch *parent = nullptr;
    for (const LifecycleEpoch &candidate : result.epochs)
      if (candidate.epoch_id == epoch->predecessor_epoch_id) parent = &candidate;
    if (parent == nullptr || parent->manifest_sha256 != epoch->predecessor_manifest_sha256 ||
        parent->retirement_sha256.empty() ||
        parent->retirement_sha256 != epoch->predecessor_retirement_sha256 ||
        std::find(referenced.begin(), referenced.end(), parent) != referenced.end())
      return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
          "lifecycle epoch predecessor is missing, active, changed, or forked"));
    referenced.push_back(parent);
  }
  if (root == nullptr) return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
      "lifecycle epoch graph has no genesis or contains a cycle"));
  if (has_sentinel) {
    if (root->predecessor_epoch_id != kCompatibilityEpochId) return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
        "the compatibility epoch must be the direct predecessor of the first real epoch"));
  } else if (!root->predecessor_epoch_id.empty()) {
    return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
        "a real lifecycle epoch genesis must not name a predecessor"));
  }
  const LifecycleEpoch *cursor = root;
  std::size_t visited = 1U;
  while (true) {
    const LifecycleEpoch *child = nullptr;
    for (const LifecycleEpoch *candidate : real)
      if (candidate->predecessor_epoch_id == cursor->epoch_id) child = candidate;
    if (child == nullptr) break;
    if (++visited > real.size()) return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
        "lifecycle epoch graph contains a cycle"));
    cursor = child;
  }
  if (visited != real.size()) return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
      "lifecycle epoch graph contains an orphan"));
  const LifecycleEpoch &authority = result.epochs.front().compatibility_epoch
      ? result.epochs.front() : *root;
  for (const LifecycleEpoch &epoch : result.epochs)
    if (!lifecycle_roots_equal(authority, epoch))
      return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
          "lifecycle epochs do not share one exact authority"));
  LifecycleEpochChain ordered;
  if (has_sentinel) ordered.epochs.push_back(result.epochs.front());
  cursor = root;
  for (;;) {
    ordered.epochs.push_back(*cursor);
    const LifecycleEpoch *child = nullptr;
    for (const LifecycleEpoch *candidate : real)
      if (candidate->predecessor_epoch_id == cursor->epoch_id) child = candidate;
    if (child == nullptr) break;
    cursor = child;
  }
  if (!recovery_epoch_id.empty() &&
      (ordered.epochs.empty() || ordered.epochs.back().compatibility_epoch ||
       ordered.epochs.back().epoch_id != recovery_epoch_id))
    return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
        "genesis recovery is permitted only for the unique current real epoch tail"));
  return facman::core::Result<LifecycleEpochChain>::success(std::move(ordered));
}

} // namespace

fs::path global_lock_path(const fs::path &coordinator_root) {
  return coordinator_root / "setup-operations" / "facman.self.lock";
}

std::string generation_record_bytes(const Generation &generation) {
  return serialize_generation(generation);
}

facman::core::Result<Generation> make_generation(
    const PackageDescriptor &descriptor, const std::string &package_sha256,
    const std::string &install_id, const fs::path &install_root,
    const fs::path &logical_root, const fs::path &state_root,
    const fs::path &acceptance_root) {
  Semver version;
  if (descriptor.product_id != "facman" || descriptor.automatic_update ||
      descriptor.setup_protocol != "facman.self_maintenance.v1" ||
      descriptor.package_layout !=
          "versioned_generation_with_maintenance_v1" ||
      descriptor.generation_relative_path !=
          "generations/" + descriptor.product_version ||
      descriptor.gui_relative_path != "FacMan.exe" ||
      descriptor.cli_relative_path != "bin/facman.exe" ||
      descriptor.maintenance_relative_path != "maintenance/FacManSetup.exe" ||
      !revision(descriptor.facman_source_revision) ||
      !revision(descriptor.universal_setup_revision) ||
      !semver(descriptor.product_version, version) ||
      !safe_version_component(descriptor.product_version) ||
      !safe_relative(descriptor.generation_relative_path) ||
      !digest(package_sha256) || !install_root.is_absolute() ||
      !logical_root.is_absolute() || !state_root.is_absolute() ||
      !acceptance_root.is_absolute())
    return facman::core::Result<Generation>::failure(failure(
        "self_maintenance_package_incompatible",
        "generation inputs are incomplete or incompatible"));
  Generation result;
  result.generation_id = generation_identity(descriptor, package_sha256);
  result.product_version = descriptor.product_version;
  result.package_sha256 = package_sha256;
  result.facman_source_revision = descriptor.facman_source_revision;
  result.universal_setup_revision = descriptor.universal_setup_revision;
  result.install_id = install_id;
  if (result.install_id.empty())
    result.install_id = generation_install_id(result.generation_id);
  if (result.install_id != "facman.self" &&
      result.install_id != generation_install_id(result.generation_id))
    return facman::core::Result<Generation>::failure(failure(
        "self_maintenance_input_invalid", "generation install id is invalid"));
  result.install_root = install_root.lexically_normal();
  result.logical_root = logical_root.lexically_normal();
  result.state_root = state_root.lexically_normal();
  result.acceptance_root = acceptance_root.lexically_normal();
  const fs::path generation = result.install_root /
      facman::platform::path_from_utf8(descriptor.generation_relative_path);
  result.gui = generation /
      facman::platform::path_from_utf8(descriptor.gui_relative_path);
  result.maintenance_launcher = result.install_root /
      facman::platform::path_from_utf8(descriptor.maintenance_relative_path);
  if (!exact_generation_paths(result) ||
      (result.install_id != "facman.self" &&
       !same_path(result.install_root,
                  generation_install_root(result.logical_root,
                                          result.generation_id))))
    return facman::core::Result<Generation>::failure(failure(
        "self_maintenance_input_invalid", "generation paths are invalid"));
  return facman::core::Result<Generation>::success(std::move(result));
}

facman::core::Result<Generation> make_epoch_genesis_generation(
    const LifecycleEpoch &epoch, const PackageDescriptor &descriptor,
    const std::string &package_sha256) {
  if (epoch.compatibility_epoch || !digest(epoch.epoch_id) ||
      epoch.epoch_id == kCompatibilityEpochId || !digest(epoch.genesis_generation_id) ||
      !epoch.logical_root.is_absolute() || !epoch.state_root.is_absolute() ||
      !epoch.acceptance_root.is_absolute() ||
      hash(lifecycle_identity_bytes(epoch)) != epoch.epoch_id)
    return facman::core::Result<Generation>::failure(failure(
        "self_maintenance_input_invalid", "epoch genesis inputs are incomplete"));
  auto base = make_generation(descriptor, package_sha256, "facman.self",
      epoch.logical_root, epoch.logical_root, epoch.state_root, epoch.acceptance_root);
  if (!base) return base;
  Generation result = base.take_value();
  if (result.generation_id != epoch.genesis_generation_id)
    return facman::core::Result<Generation>::failure(failure(
        "self_maintenance_input_invalid", "epoch genesis generation id is not reserved by its manifest"));
  result.install_id = "facman.self.epoch." + epoch.epoch_id + ".generation." +
      result.generation_id;
  result.install_root = epoch_generation_install_root(
      epoch.logical_root, epoch.epoch_id, result.generation_id);
  result.gui = result.install_root / "generations" / result.product_version / "FacMan.exe";
  result.maintenance_launcher = result.install_root / "maintenance" / "FacManSetup.exe";
  if (!exact_epoch_generation_paths(epoch, result))
    return facman::core::Result<Generation>::failure(failure(
        "self_maintenance_input_invalid", "epoch genesis generation paths are not exact"));
  return facman::core::Result<Generation>::success(std::move(result));
}

facman::core::Result<ActiveState> activate_lifecycle_epoch_genesis(
    const EpochGenesisRequest &request) {
  if (!request.coordinator_root.is_absolute() || !digest(request.epoch_id))
    return facman::core::Result<ActiveState>::failure(failure(
        "self_maintenance_input_invalid", "epoch genesis request is incomplete"));
  PinnedLifecycleEpochScope review_scope;
  auto opened = review_scope.open(request.coordinator_root, request.epoch_id);
  if (!opened) return facman::core::Result<ActiveState>::failure(opened.error());
  auto manifest = review_scope.read("epoch.v1.json");
  auto epoch = manifest ? parse_lifecycle_manifest(manifest.value(), request.epoch_id)
                        : facman::core::Result<LifecycleEpoch>::failure(manifest.error());
  if (!epoch) return facman::core::Result<ActiveState>::failure(epoch.error());
  const std::string reviewed_manifest = manifest.value();
  auto expected = make_epoch_genesis_generation(epoch.value(),
      generation_descriptor(request.generation), request.generation.package_sha256);
  if (!expected || epoch_generation_bytes(epoch.value(), expected.value()) !=
                       epoch_generation_bytes(epoch.value(), request.generation))
    return facman::core::Result<ActiveState>::failure(failure(
        "self_maintenance_input_invalid", "requested epoch genesis generation is not exact"));
  auto reviewed_chain = discover_lifecycle_epoch_chain_impl(request.coordinator_root,
      request.apply ? request.epoch_id : std::string(),
      request.apply ? &request.generation : nullptr);
  if (!reviewed_chain || reviewed_chain.value().epochs.empty() ||
      reviewed_chain.value().epochs.back().compatibility_epoch ||
      reviewed_chain.value().epochs.back().epoch_id != request.epoch_id ||
      reviewed_chain.value().epochs.back().manifest_sha256 != hash(reviewed_manifest))
    return facman::core::Result<ActiveState>::failure(!reviewed_chain ? reviewed_chain.error() :
        epoch_recovery("requested epoch is not the exact current lifecycle tail"));
  auto progress = discover_epoch_genesis_state(epoch.value(), review_scope,
                                               &request.generation, true);
  if (!progress) return facman::core::Result<ActiveState>::failure(progress.error());
  if (!request.apply) {
    if (progress.value().has_value()) return facman::core::Result<ActiveState>::success(
        *progress.value());
    return facman::core::Result<ActiveState>::success(
        {request.generation, {}, epoch_activation_name(request.generation.generation_id),
         hash(epoch_activation_bytes(epoch.value(), request.generation,
             hash(epoch_generation_bytes(epoch.value(), request.generation))))});
  }
  auto admission = admit_coordinator(request.coordinator_root,
                                     epoch.value().acceptance_root, false);
  if (!admission) return facman::core::Result<ActiveState>::failure(admission.error());
  auto lock = acquire(admission.take_value(), "epoch.genesis." + request.generation.generation_id);
  if (!lock) return facman::core::Result<ActiveState>::failure(lock.error());
  PinnedLifecycleEpochScope scope;
  opened = scope.open(request.coordinator_root, request.epoch_id, true);
  if (!opened) return facman::core::Result<ActiveState>::failure(opened.error());
  manifest = scope.read("epoch.v1.json");
  epoch = manifest ? parse_lifecycle_manifest(manifest.value(), request.epoch_id)
                   : facman::core::Result<LifecycleEpoch>::failure(manifest.error());
  if (!epoch || manifest.value() != reviewed_manifest)
    return facman::core::Result<ActiveState>::failure(epoch_recovery(
        "epoch manifest changed before genesis publication"));
  auto locked_chain = discover_lifecycle_epoch_chain_impl(request.coordinator_root,
      request.epoch_id, &request.generation);
  if (!locked_chain || locked_chain.value().epochs.empty() ||
      locked_chain.value().epochs.back().compatibility_epoch ||
      locked_chain.value().epochs.back().epoch_id != request.epoch_id ||
      locked_chain.value().epochs.back().manifest_sha256 != hash(reviewed_manifest))
    return facman::core::Result<ActiveState>::failure(!locked_chain ? locked_chain.error() :
        epoch_recovery("lifecycle epoch chain changed before genesis publication"));
  progress = discover_epoch_genesis_state(epoch.value(), scope, &request.generation, true);
  if (!progress) return facman::core::Result<ActiveState>::failure(progress.error());
  if (!progress.value().has_value()) {
    auto generations = open_or_create_epoch_child(scope.epoch, "generations");
    auto activations = open_or_create_epoch_child(scope.epoch, "activations");
    if (!generations || !activations) return facman::core::Result<ActiveState>::failure(
        !generations ? generations.error() : activations.error());
    const std::string generation_bytes = epoch_generation_bytes(epoch.value(), request.generation);
    auto written = publish_epoch_record(generations.value(),
        epoch_generation_staging_name(request.generation.generation_id),
        epoch_generation_name(request.generation.generation_id), generation_bytes);
    if (!written) return facman::core::Result<ActiveState>::failure(written.error());
    written = publish_epoch_record(activations.value(),
        epoch_activation_staging_name(request.generation.generation_id),
        epoch_activation_name(request.generation.generation_id),
        epoch_activation_bytes(epoch.value(), request.generation, hash(generation_bytes)));
    if (!written) return facman::core::Result<ActiveState>::failure(written.error());
  }
  PinnedLifecycleEpochScope final_scope;
  opened = final_scope.open(request.coordinator_root, request.epoch_id);
  if (!opened) return facman::core::Result<ActiveState>::failure(opened.error());
  auto final_manifest = final_scope.read("epoch.v1.json");
  auto final_epoch = final_manifest ? parse_lifecycle_manifest(final_manifest.value(), request.epoch_id)
                                    : facman::core::Result<LifecycleEpoch>::failure(final_manifest.error());
  auto active = final_epoch ? discover_epoch_genesis_state(final_epoch.value(), final_scope,
      &request.generation, false) : facman::core::Result<std::optional<ActiveState>>::failure(final_epoch.error());
  if (!active || !active.value().has_value()) return facman::core::Result<ActiveState>::failure(
      !active ? active.error() : epoch_recovery("epoch genesis is not committed"));
  facman::platform::StableDirectoryObject final_generations, final_activations;
  if (!final_scope.epoch.open_child_directory_no_follow("generations", final_generations).ok() ||
      !final_scope.epoch.open_child_directory_no_follow("activations", final_activations).ok() ||
      !final_generations.flush_metadata().ok() || !final_activations.flush_metadata().ok() ||
      !final_scope.epoch.flush_metadata().ok() || !final_scope.epochs.flush_metadata().ok() ||
      !final_scope.coordinator.flush_metadata().ok()) return facman::core::Result<ActiveState>::failure(
          epoch_recovery("epoch genesis directory hierarchy could not be flushed"));
  return facman::core::Result<ActiveState>::success(*active.value());
}

facman::core::Result<std::optional<ActivationChain>> discover_activation_chain(
    const fs::path &coordinator_root) {
  if (!coordinator_root.is_absolute())
    return facman::core::Result<std::optional<ActivationChain>>::failure(failure(
        "self_maintenance_input_invalid", "coordinator root must be absolute"));
  const fs::path directory = coordinator_root / "activations";
  std::error_code status;
  if (!fs::exists(directory, status)) {
    if (status)
      return facman::core::Result<std::optional<ActivationChain>>::failure(failure(
          "self_maintenance_activation_changed",
          "activation directory could not be observed", status.message()));
    return facman::core::Result<std::optional<ActivationChain>>::success({});
  }
  if (!fs::is_directory(directory, status) || status)
    return facman::core::Result<std::optional<ActivationChain>>::failure(failure(
        "self_maintenance_activation_changed",
        "activation path is not a directory"));
  auto first = fs::directory_iterator(directory, status);
  if (status)
    return facman::core::Result<std::optional<ActivationChain>>::failure(failure(
        "self_maintenance_activation_changed",
        "activation directory could not be enumerated", status.message()));
  if (first == fs::directory_iterator())
    return facman::core::Result<std::optional<ActivationChain>>::success({});
  auto head = validate_activation_head(coordinator_root, {}, {});
  if (!head)
    return facman::core::Result<std::optional<ActivationChain>>::failure(
        head.error());
  ActivationChain result;
  result.activation_name = head.value().name;
  result.activation_sha256 = head.value().digest;
  result.generations.reserve(head.value().generation_ids.size());
  for (const auto &generation_id : head.value().generation_ids) {
    auto generation = parse_generation_record(coordinator_root, generation_id);
    if (!generation)
      return facman::core::Result<std::optional<ActivationChain>>::failure(
          generation.error());
    result.generations.push_back(generation.take_value());
  }
  if (result.generations.empty())
    return facman::core::Result<std::optional<ActivationChain>>::failure(failure(
        "self_maintenance_activation_changed", "activation chain has no generation"));
  return facman::core::Result<std::optional<ActivationChain>>::success(
      std::optional<ActivationChain>(std::move(result)));
}

facman::core::Result<std::optional<ActiveState>> discover_active(
    const fs::path &coordinator_root) {
  auto chain = discover_activation_chain(coordinator_root);
  if (!chain)
    return facman::core::Result<std::optional<ActiveState>>::failure(chain.error());
  if (!chain.value().has_value())
    return facman::core::Result<std::optional<ActiveState>>::success({});
  const auto steps = retirement_steps(*chain.value());
  bool retired = false;
  auto journal = validate_retirement_directory(
      retirement_directory(coordinator_root, *chain.value()), *chain.value(),
      steps, &retired);
  if (!journal)
    return facman::core::Result<std::optional<ActiveState>>::failure(journal.error());
  if (retired)
    return facman::core::Result<std::optional<ActiveState>>::success({});
  std::error_code retirement_status;
  if (fs::exists(retirement_directory(coordinator_root, *chain.value()),
                 retirement_status))
    return facman::core::Result<std::optional<ActiveState>>::failure(failure(
        "self_maintenance_retirement_recovery_required",
        "activation-chain retirement is incomplete and must be resumed"));
  if (retirement_status)
    return facman::core::Result<std::optional<ActiveState>>::failure(failure(
        "self_maintenance_retirement_recovery_required",
        "retirement journal could not be observed",
        retirement_status.message()));
  ActiveState result;
  result.active = chain.value()->generations.back();
  result.activation_name = chain.value()->activation_name;
  result.activation_sha256 = chain.value()->activation_sha256;
  if (chain.value()->generations.size() > 1U)
    result.previous = chain.value()->generations[
        chain.value()->generations.size() - 2U];
  return facman::core::Result<std::optional<ActiveState>>::success(
      std::optional<ActiveState>(std::move(result)));
}

facman::core::Result<LifecycleEpochChain> discover_lifecycle_epoch_chain(
    const fs::path &coordinator_root) {
  return discover_lifecycle_epoch_chain_impl(coordinator_root);
}

facman::core::Result<EpochActiveState> discover_lifecycle_epoch_active(
    const fs::path &coordinator_root) {
  auto chain = discover_lifecycle_epoch_chain_impl(coordinator_root);
  if (!chain) return facman::core::Result<EpochActiveState>::failure(chain.error());
  if (chain.value().epochs.empty())
    return facman::core::Result<EpochActiveState>::failure(epoch_recovery(
        "lifecycle epoch discovery has no active epoch"));
  LifecycleEpoch epoch = chain.value().epochs.back();
  if (epoch.compatibility_epoch) {
    auto active = discover_active(coordinator_root);
    if (!active) return facman::core::Result<EpochActiveState>::failure(active.error());
    if (!active.value().has_value())
      return facman::core::Result<EpochActiveState>::failure(epoch_recovery(
          "compatibility lifecycle epoch has no active generation"));
    return facman::core::Result<EpochActiveState>::success(
        {std::move(epoch), std::move(*active.value())});
  }
  PinnedLifecycleEpochScope scope;
  auto opened = scope.open(coordinator_root, epoch.epoch_id);
  if (!opened) return facman::core::Result<EpochActiveState>::failure(opened.error());
  auto manifest = scope.read("epoch.v1.json");
  auto pinned_epoch = manifest
      ? parse_lifecycle_manifest(manifest.value(), epoch.epoch_id)
      : facman::core::Result<LifecycleEpoch>::failure(manifest.error());
  if (!pinned_epoch || pinned_epoch.value().manifest_sha256 != epoch.manifest_sha256)
    return facman::core::Result<EpochActiveState>::failure(!pinned_epoch
        ? pinned_epoch.error() : epoch_recovery("lifecycle epoch manifest changed during discovery"));
  auto active = discover_epoch_genesis_state(pinned_epoch.value(), scope);
  if (!active) return facman::core::Result<EpochActiveState>::failure(active.error());
  if (!active.value().has_value())
    return facman::core::Result<EpochActiveState>::failure(epoch_recovery(
        "lifecycle epoch has no committed activation chain"));
  return facman::core::Result<EpochActiveState>::success(
      {pinned_epoch.take_value(), std::move(*active.value())});
}

namespace {

struct EpochHandoff {
  std::string epoch_id;
  std::string manifest_sha256;
  std::string operation;
  std::string operation_id;
  std::string source_generation_id;
  std::string source_activation_name;
  std::string source_activation_sha256;
  std::string target_generation_id;
  RetainedMaintenanceInputs inputs;
  std::string provider_plan_sha256;
  std::string nonce;
};

std::string epoch_handoff_bytes(const EpochHandoff &value) {
  json::ObjectBuilder object;
  object.add_string("schema", "facman.self_epoch_handoff.v2");
  object.add_string("product_id", "facman");
  object.add_string("epoch_id", value.epoch_id);
  object.add_string("epoch_manifest_sha256", value.manifest_sha256);
  object.add_string("operation", value.operation);
  object.add_string("operation_id", value.operation_id);
  object.add_string("source_generation_id", value.source_generation_id);
  object.add_string("source_activation_name", value.source_activation_name);
  object.add_string("source_activation_sha256", value.source_activation_sha256);
  object.add_string("target_generation_id", value.target_generation_id);
  object.add_string("retained_package", facman::platform::path_to_utf8(value.inputs.package));
  object.add_string("retained_package_sha256", value.inputs.package_sha256);
  object.add_string("retained_helper", facman::platform::path_to_utf8(value.inputs.helper));
  object.add_string("retained_helper_sha256", value.inputs.helper_sha256);
  object.add_string("provider_plan_sha256", value.provider_plan_sha256);
  object.add_string("nonce", value.nonce);
  return object.serialize() + "\n";
}

facman::core::Result<EpochHandoff> parse_epoch_handoff(const std::string &bytes) {
  auto document = json::parse(bytes);
  const std::initializer_list<const char *> keys = {"schema", "product_id", "epoch_id",
      "epoch_manifest_sha256", "operation", "operation_id", "source_generation_id",
      "source_activation_name", "source_activation_sha256", "target_generation_id",
      "retained_package", "retained_package_sha256", "retained_helper",
      "retained_helper_sha256", "provider_plan_sha256", "nonce"};
  if (!document || !exact_keys(document.value(), keys) ||
      !lifecycle_string_fields(document.value(), keys))
    return facman::core::Result<EpochHandoff>::failure(epoch_recovery(
        "epoch handoff journal has an incompatible exact schema"));
  EpochHandoff result;
  result.epoch_id = string_field(document.value(), "epoch_id");
  result.manifest_sha256 = string_field(document.value(), "epoch_manifest_sha256");
  result.operation = string_field(document.value(), "operation");
  result.operation_id = string_field(document.value(), "operation_id");
  result.source_generation_id = string_field(document.value(), "source_generation_id");
  result.source_activation_name = string_field(document.value(), "source_activation_name");
  result.source_activation_sha256 = string_field(document.value(), "source_activation_sha256");
  result.target_generation_id = string_field(document.value(), "target_generation_id");
  result.inputs.package = facman::platform::path_from_utf8(string_field(document.value(), "retained_package"));
  result.inputs.package_sha256 = string_field(document.value(), "retained_package_sha256");
  result.inputs.helper = facman::platform::path_from_utf8(string_field(document.value(), "retained_helper"));
  result.inputs.helper_sha256 = string_field(document.value(), "retained_helper_sha256");
  result.provider_plan_sha256 = string_field(document.value(), "provider_plan_sha256");
  result.nonce = string_field(document.value(), "nonce");
  std::string detail;
  if (string_field(document.value(), "schema") != "facman.self_epoch_handoff.v2" ||
      string_field(document.value(), "product_id") != "facman" || !digest(result.epoch_id) ||
      !digest(result.manifest_sha256) || (result.operation != "update" &&
      result.operation != "downgrade") || !facman::base::validate_identifier(result.operation_id, detail) ||
      !digest(result.source_generation_id) || result.source_activation_name.empty() ||
      fs::path(result.source_activation_name) != fs::path(result.source_activation_name).filename() ||
      !digest(result.source_activation_sha256) ||
      !digest(result.target_generation_id) || !result.inputs.package.is_absolute() ||
      !digest(result.inputs.package_sha256) || !result.inputs.helper.is_absolute() ||
      !digest(result.inputs.helper_sha256) || !digest(result.provider_plan_sha256) ||
      !facman::base::validate_identifier(result.nonce, detail) ||
      bytes != epoch_handoff_bytes(result))
    return facman::core::Result<EpochHandoff>::failure(epoch_recovery(
        "epoch handoff journal identity or canonical bytes are invalid"));
  return facman::core::Result<EpochHandoff>::success(std::move(result));
}

bool state_descendant(const fs::path &state_root, const fs::path &path) {
  const fs::path relative = path.lexically_relative(state_root);
  return !relative.empty() && !relative.is_absolute() &&
      std::none_of(relative.begin(), relative.end(), [](const fs::path &part) {
        return part == "..";
      });
}

struct HeldRetainedInputs {
  RetainedMaintenanceInputs inputs;
  facman::platform::StableDirectoryObject state;
  facman::platform::StableDirectoryObject handoff_root;
  facman::platform::StableDirectoryObject operation;
  facman::platform::StableInputFile package;
  facman::platform::StableInputFile helper;
};

fs::path retained_handoff_directory(const LifecycleEpoch &epoch,
                                    const std::string &operation_id) {
  return epoch.state_root / "epoch-handoff" / operation_id;
}

bool exact_retained_operation_names(
    const facman::platform::StableDirectoryObject &operation) {
  std::vector<fs::path> names;
  return operation.list_child_names_bounded(3U, names).ok() && names.size() == 2U &&
      names[0] == fs::path("FacManSetup.exe") && names[1] == fs::path("package.zip");
}

bool revalidate_retained_inputs(HeldRetainedInputs &held) {
  auto package_hash = stable_digest(held.package);
  auto helper_hash = stable_digest(held.helper);
  return package_hash && helper_hash &&
      package_hash.value() == held.inputs.package_sha256 &&
      helper_hash.value() == held.inputs.helper_sha256 &&
      held.package.revalidate_path().ok() && held.helper.revalidate_path().ok() &&
      exact_retained_operation_names(held.operation) &&
      held.operation.revalidate().ok() && held.handoff_root.revalidate().ok() &&
      held.state.revalidate().ok();
}

void notify_retained_inputs_after_initial_validation(
    const HeldRetainedInputs &held) {
  // The test seam deliberately runs only after the held descriptors have been
  // hashed and package inspection has completed.  The immediately following
  // held-handle rehash is therefore an adversarial final-validation check.
  notify_epoch_record_pinned(held.inputs.package);
  notify_epoch_record_pinned(held.inputs.helper);
}

facman::core::Result<HeldRetainedInputs> validate_retained_inputs(
    const LifecycleEpoch &epoch, const std::string &operation_id,
    const RetainedMaintenanceInputs &inputs) {
  const fs::path retained_root = retained_handoff_directory(epoch, operation_id);
  if (inputs.package != retained_root / "package.zip" ||
      inputs.helper != retained_root / "FacManSetup.exe")
    return facman::core::Result<HeldRetainedInputs>::failure(epoch_recovery(
        "retained handoff inputs do not use the canonical custody paths"));
  if (inputs.package == inputs.helper || !state_descendant(epoch.state_root, inputs.package) ||
      !state_descendant(epoch.state_root, inputs.helper) || !digest(inputs.package_sha256) ||
      !digest(inputs.helper_sha256))
    return facman::core::Result<HeldRetainedInputs>::failure(epoch_recovery(
        "retained handoff inputs are outside the admitted epoch state root"));
  HeldRetainedInputs held{inputs, {}, {}, {}, {}, {}};
  std::vector<fs::path> names;
  if (!held.state.open_no_follow(epoch.state_root).ok() ||
      !held.state.open_child_directory_no_follow("epoch-handoff", held.handoff_root).ok() ||
      !held.handoff_root.open_child_directory_no_follow(operation_id, held.operation).ok() ||
      !held.operation.list_child_names_bounded(3U, names).ok() || names.size() != 2U ||
      names[0] != fs::path("FacManSetup.exe") || names[1] != fs::path("package.zip") ||
      !held.operation.open_child_file_no_follow_pinned("package.zip", held.package).ok())
    return facman::core::Result<HeldRetainedInputs>::failure(epoch_recovery(
        "retained handoff input is missing, linked, or outside the held state root"));
  notify_epoch_handoff_operation_pinned(held.operation.path());
  if (!held.operation.open_child_file_no_follow_pinned("FacManSetup.exe", held.helper).ok())
    return facman::core::Result<HeldRetainedInputs>::failure(epoch_recovery(
        "retained handoff helper is missing, linked, or outside the held state root"));
  auto package_hash = stable_digest(held.package);
  auto helper_hash = stable_digest(held.helper);
  if (!package_hash || !helper_hash || package_hash.value() != inputs.package_sha256 ||
      helper_hash.value() != inputs.helper_sha256 || !revalidate_retained_inputs(held))
    return facman::core::Result<HeldRetainedInputs>::failure(epoch_recovery(
        "retained handoff input changed while it was validated"));
  return facman::core::Result<HeldRetainedInputs>::success(std::move(held));
}

facman::core::Result<Plan> make_epoch_transition_plan(const LifecycleEpoch &epoch,
    const ActiveState &active, const EpochTransitionRequest &request) {
  if ((request.operation != Operation::update && request.operation != Operation::downgrade) ||
      request.package.package.empty() || !digest(request.package.package_sha256))
    return facman::core::Result<Plan>::failure(failure(
        "self_maintenance_input_invalid", "epoch transition request is incomplete"));
  auto actual_hash = stable_digest(request.package.package);
  if (!actual_hash || actual_hash.value() != request.package.package_sha256)
    return facman::core::Result<Plan>::failure(failure(
        "self_maintenance_package_changed", "reviewed epoch package changed before preparation"));
  auto base = make_generation(request.package.descriptor, request.package.package_sha256, "facman.self",
      epoch.logical_root, epoch.logical_root, epoch.state_root, epoch.acceptance_root);
  if (!base) return facman::core::Result<Plan>::failure(base.error());
  Generation target = base.take_value();
  target.install_id = "facman.self.epoch." + epoch.epoch_id + ".generation." + target.generation_id;
  target.install_root = epoch_generation_install_root(epoch.logical_root, epoch.epoch_id,
                                                       target.generation_id);
  target.gui = target.install_root / "generations" / target.product_version / "FacMan.exe";
  target.maintenance_launcher = target.install_root / "maintenance" / "FacManSetup.exe";
  Semver source_version, target_version;
  if (!exact_epoch_generation_paths(epoch, target) ||
      !semver(active.active.product_version, source_version) ||
      !semver(target.product_version, target_version) ||
      (request.operation == Operation::update && compare(target_version, source_version) <= 0) ||
      (request.operation == Operation::downgrade && compare(target_version, source_version) >= 0))
    return facman::core::Result<Plan>::failure(failure(
        "self_maintenance_version_direction_invalid", "epoch transition direction is invalid"));
  return facman::core::Result<Plan>::success({operation_name(request.operation), request.operation_id,
      active.active, target, request.package.package, request.package.package_sha256, "install_local",
      active.activation_name, active.activation_sha256});
}

} // namespace

facman::core::Result<EpochTransitionPreparation> prepare_lifecycle_epoch_transition(
    const EpochTransitionRequest &request, EpochPreparationEffects &effects) {
  std::string detail;
  if (!request.coordinator_root.is_absolute() || !digest(request.epoch_id) ||
      !facman::base::validate_identifier(request.operation_id, detail) ||
      (request.operation != Operation::update && request.operation != Operation::downgrade))
    return facman::core::Result<EpochTransitionPreparation>::failure(failure(
        "self_maintenance_input_invalid", "epoch transition identifiers are invalid"));
  const auto exact_request_package = [&](const PackageInspection &value) {
    return value.package == request.package.package.lexically_normal() &&
        value.package_sha256 == request.package.package_sha256 &&
        value.maintenance_launcher_sha256 == request.package.maintenance_launcher_sha256 &&
        same_descriptor(value.descriptor, request.package.descriptor);
  };
  const std::string permitted = request.apply ? request.operation_id : std::string();
  auto chain = discover_lifecycle_epoch_chain_impl(request.coordinator_root, {}, nullptr, permitted,
                                                   request.epoch_id);
  if (!chain || chain.value().epochs.empty() || chain.value().epochs.back().compatibility_epoch ||
      chain.value().epochs.back().epoch_id != request.epoch_id)
    return facman::core::Result<EpochTransitionPreparation>::failure(!chain ? chain.error() :
        epoch_recovery("requested epoch is not the unique real lifecycle tail"));
  LifecycleEpoch epoch = chain.value().epochs.back();
  PinnedLifecycleEpochScope scope;
  auto opened = scope.open(request.coordinator_root, epoch.epoch_id, request.apply);
  if (!opened) return facman::core::Result<EpochTransitionPreparation>::failure(opened.error());
  auto active = discover_epoch_genesis_state(epoch, scope, nullptr, false,
      permitted.empty() ? nullptr : &permitted);
  if (!active || !active.value().has_value())
    return facman::core::Result<EpochTransitionPreparation>::failure(!active ? active.error() :
        epoch_recovery("real epoch has no committed active generation"));
  if (!request.apply) {
    auto inspected = inspect_package(request.package.package);
    if (!inspected || !exact_request_package(inspected.value()))
      return facman::core::Result<EpochTransitionPreparation>::failure(!inspected ?
          inspected.error() : failure("self_maintenance_package_changed",
              "caller package inspection does not match the exact source package"));
    auto transition = make_epoch_transition_plan(epoch, *active.value(), request);
    if (!transition) return facman::core::Result<EpochTransitionPreparation>::failure(transition.error());
    if (effects.inspect_candidate(transition.value()) != CandidateState::absent)
      return facman::core::Result<EpochTransitionPreparation>::failure(failure(
          "self_maintenance_candidate_unsafe", "epoch target generation is not absent"));
    const EffectResult reviewed = effects.review_install_local(transition.value());
    if (!reviewed.ok || reviewed.outcome_unknown || !digest(reviewed.receipt_sha256))
      return facman::core::Result<EpochTransitionPreparation>::failure(failure(
          "self_maintenance_plan_failed", "provider review did not return an exact plan receipt"));
    return facman::core::Result<EpochTransitionPreparation>::success(
        {"plan", transition.take_value(), {}, {}, {}, {}});
  }

  auto authority = admit_coordinator(request.coordinator_root, epoch.acceptance_root, false);
  if (!authority) return facman::core::Result<EpochTransitionPreparation>::failure(authority.error());
  auto held = acquire(authority.take_value(), request.operation_id);
  if (!held) return facman::core::Result<EpochTransitionPreparation>::failure(held.error());
  auto locked_chain = discover_lifecycle_epoch_chain_impl(request.coordinator_root, {}, nullptr,
                                                          request.operation_id, epoch.epoch_id);
  if (!locked_chain || locked_chain.value().epochs.empty() ||
      locked_chain.value().epochs.back().epoch_id != epoch.epoch_id ||
      locked_chain.value().epochs.back().manifest_sha256 != epoch.manifest_sha256)
    return facman::core::Result<EpochTransitionPreparation>::failure(!locked_chain ?
        locked_chain.error() : epoch_recovery("epoch chain changed before handoff preparation"));
  PinnedLifecycleEpochScope locked_scope;
  opened = locked_scope.open(request.coordinator_root, epoch.epoch_id, true);
  if (!opened) return facman::core::Result<EpochTransitionPreparation>::failure(opened.error());
  auto locked_active = discover_epoch_genesis_state(epoch, locked_scope, nullptr, false,
                                                    &request.operation_id);
  if (!locked_active || !locked_active.value().has_value() ||
      locked_active.value()->activation_name != active.value()->activation_name ||
      locked_active.value()->activation_sha256 != active.value()->activation_sha256)
    return facman::core::Result<EpochTransitionPreparation>::failure(!locked_active ?
        locked_active.error() : epoch_recovery("epoch active head changed before handoff preparation"));
  auto maintenance = open_or_create_epoch_child(locked_scope.epoch, "maintenance");
  auto operation = maintenance ? open_or_create_epoch_child(maintenance.value(), request.operation_id.c_str())
                               : facman::core::Result<facman::platform::StableDirectoryObject>::failure(maintenance.error());
  if (!operation) return facman::core::Result<EpochTransitionPreparation>::failure(operation.error());
  const std::string final_name = "00-handoff-ready.v2.json";
  const std::string staging_name = "00-handoff-ready.staging.v2.json";
  std::vector<fs::path> names;
  if (!operation.value().list_child_names_bounded(2U, names).ok() || names.size() > 1U ||
      (!names.empty() && names.front() != final_name && names.front() != staging_name))
    return facman::core::Result<EpochTransitionPreparation>::failure(epoch_recovery(
        "epoch handoff directory contains a foreign or partial record"));
  EpochHandoff handoff;
  Plan transition;
  EffectResult reviewed;
  if (!names.empty()) {
    auto bytes = read_epoch_relative_bounded(operation.value(), names.front(),
                                             kMaximumEpochGenesisRecordBytes);
    auto parsed = bytes ? parse_epoch_handoff(bytes.value())
                        : facman::core::Result<EpochHandoff>::failure(bytes.error());
    if (!parsed) return facman::core::Result<EpochTransitionPreparation>::failure(parsed.error());
    handoff = parsed.take_value();
    auto checked = validate_retained_inputs(epoch, request.operation_id, handoff.inputs);
    if (!checked) return facman::core::Result<EpochTransitionPreparation>::failure(checked.error());
    auto retained_inspection = inspect_package(handoff.inputs.package);
    if (!retained_inspection || retained_inspection.value().package_sha256 != handoff.inputs.package_sha256 ||
        retained_inspection.value().maintenance_launcher_sha256 != handoff.inputs.helper_sha256)
      return facman::core::Result<EpochTransitionPreparation>::failure(!retained_inspection ?
          retained_inspection.error() : epoch_recovery("retained package helper provenance changed"));
    notify_retained_inputs_after_initial_validation(checked.value());
    if (!revalidate_retained_inputs(checked.value()))
      return facman::core::Result<EpochTransitionPreparation>::failure(epoch_recovery(
          "retained handoff input changed during preparation"));
    EpochTransitionRequest retained_request{request.coordinator_root, epoch.epoch_id, request.operation,
        request.operation_id, retained_inspection.take_value(), false};
    auto planned = make_epoch_transition_plan(epoch, *locked_active.value(), retained_request);
    if (!planned) return facman::core::Result<EpochTransitionPreparation>::failure(planned.error());
    transition = planned.take_value();
    if (effects.inspect_candidate(transition) != CandidateState::absent)
      return facman::core::Result<EpochTransitionPreparation>::failure(failure(
          "self_maintenance_candidate_unsafe", "epoch target generation is not absent"));
    reviewed = effects.review_install_local(transition);
    if (!reviewed.ok || reviewed.outcome_unknown || !digest(reviewed.receipt_sha256) ||
        reviewed.receipt_sha256 != handoff.provider_plan_sha256)
      return facman::core::Result<EpochTransitionPreparation>::failure(epoch_recovery(
          "retained provider plan receipt does not match immutable handoff"));
  } else {
    auto locked_inspection = inspect_package(request.package.package);
    if (!locked_inspection || !exact_request_package(locked_inspection.value()))
      return facman::core::Result<EpochTransitionPreparation>::failure(!locked_inspection ?
          locked_inspection.error() : failure("self_maintenance_package_changed",
              "source package inspection changed under coordinator lock"));
    auto source_plan = make_epoch_transition_plan(epoch, *locked_active.value(), request);
    if (!source_plan) return facman::core::Result<EpochTransitionPreparation>::failure(source_plan.error());
    if (effects.inspect_candidate(source_plan.value()) != CandidateState::absent)
      return facman::core::Result<EpochTransitionPreparation>::failure(failure(
          "self_maintenance_candidate_unsafe", "epoch target generation is not absent"));
    const EffectResult source_review = effects.review_install_local(source_plan.value());
    if (!source_review.ok || source_review.outcome_unknown || !digest(source_review.receipt_sha256))
      return facman::core::Result<EpochTransitionPreparation>::failure(failure(
          "self_maintenance_plan_failed", "provider review did not return an exact plan receipt"));
    auto retained = effects.retain_handoff_inputs(source_plan.value());
    if (!retained) return facman::core::Result<EpochTransitionPreparation>::failure(retained.error());
    auto checked = validate_retained_inputs(epoch, request.operation_id, retained.value());
    if (!checked || retained.value().package_sha256 != source_plan.value().package_sha256 ||
        retained.value().helper_sha256 != request.package.maintenance_launcher_sha256)
      return facman::core::Result<EpochTransitionPreparation>::failure(!checked ? checked.error() :
          epoch_recovery("retained package does not match the reviewed package identity"));
    auto retained_inspection = inspect_package(retained.value().package);
    if (!retained_inspection || retained_inspection.value().package_sha256 != retained.value().package_sha256 ||
        retained_inspection.value().maintenance_launcher_sha256 != retained.value().helper_sha256 ||
        !same_descriptor(retained_inspection.value().descriptor, request.package.descriptor))
      return facman::core::Result<EpochTransitionPreparation>::failure(!retained_inspection ?
          retained_inspection.error() : epoch_recovery("retained package provenance is not exact"));
    notify_retained_inputs_after_initial_validation(checked.value());
    if (!revalidate_retained_inputs(checked.value()))
      return facman::core::Result<EpochTransitionPreparation>::failure(epoch_recovery(
          "retained handoff input changed during preparation"));
    EpochTransitionRequest retained_request{request.coordinator_root, epoch.epoch_id, request.operation,
        request.operation_id, retained_inspection.take_value(), false};
    auto planned = make_epoch_transition_plan(epoch, *locked_active.value(), retained_request);
    if (!planned) return facman::core::Result<EpochTransitionPreparation>::failure(planned.error());
    transition = planned.take_value();
    reviewed = effects.review_install_local(transition);
    if (!reviewed.ok || reviewed.outcome_unknown || !digest(reviewed.receipt_sha256))
      return facman::core::Result<EpochTransitionPreparation>::failure(failure(
          "self_maintenance_plan_failed", "retained provider review did not return an exact plan receipt"));
    facman::platform::RandomIdGenerator generator;
    handoff = {epoch.epoch_id, epoch.manifest_sha256, transition.operation,
        transition.operation_id, transition.source.generation_id,
        transition.previous_activation_name, transition.previous_activation_sha256,
        transition.target.generation_id, retained.take_value(), reviewed.receipt_sha256,
        generator.next("epoch")};
  }
  if (handoff.epoch_id != epoch.epoch_id || handoff.manifest_sha256 != epoch.manifest_sha256 ||
      handoff.operation != transition.operation || handoff.operation_id != request.operation_id ||
      handoff.source_generation_id != transition.source.generation_id ||
      handoff.source_activation_name != transition.previous_activation_name ||
      handoff.source_activation_sha256 != transition.previous_activation_sha256 ||
      handoff.target_generation_id != transition.target.generation_id ||
      handoff.provider_plan_sha256 != reviewed.receipt_sha256)
    return facman::core::Result<EpochTransitionPreparation>::failure(epoch_recovery(
        "epoch handoff journal does not bind the exact current preparation"));
  auto checked = validate_retained_inputs(epoch, request.operation_id, handoff.inputs);
  if (!checked) return facman::core::Result<EpochTransitionPreparation>::failure(checked.error());
  const std::string journal = epoch_handoff_bytes(handoff);
  auto published = publish_epoch_record(operation.value(), staging_name, final_name, journal);
  if (!published) return facman::core::Result<EpochTransitionPreparation>::failure(published.error());
  facman::platform::StableInputFile final_journal;
  if (!operation.value().open_child_file_no_follow_pinned(final_name, final_journal).ok() ||
      final_journal.size() != journal.size())
    return facman::core::Result<EpochTransitionPreparation>::failure(epoch_recovery(
        "published epoch handoff journal is unavailable or changed"));
  std::string final_bytes(journal.size(), '\0');
  if (final_journal.read_at(0, final_bytes.data(), final_bytes.size()) != final_bytes.size() ||
      final_bytes != journal || !final_journal.revalidate().ok() ||
      !final_journal.revalidate_path().ok())
    return facman::core::Result<EpochTransitionPreparation>::failure(epoch_recovery(
        "published epoch handoff journal changed before preparation completed"));
  notify_epoch_record_pinned(request.coordinator_root / "epochs" / epoch.epoch_id /
                              "maintenance" / request.operation_id / final_name);
  if (!revalidate_retained_inputs(checked.value()) ||
      !held_file_matches_bytes(final_journal, journal) ||
      !operation.value().revalidate().ok())
    return facman::core::Result<EpochTransitionPreparation>::failure(epoch_recovery(
        "retained handoff input or published journal changed before return"));
  EpochTransitionPreparation response{"handoff_ready", std::move(transition), {}, {}, {}, {}};
  response.journal = request.coordinator_root / "epochs" / epoch.epoch_id / "maintenance" /
      request.operation_id / final_name;
  response.journal_sha256 = hash(journal);
  response.inputs = std::move(handoff.inputs);
  response.nonce = std::move(handoff.nonce);
  return facman::core::Result<EpochTransitionPreparation>::success(std::move(response));
}

facman::core::Result<Plan> admit_lifecycle_epoch_continuation(
    const fs::path &coordinator_root, const std::string &operation_id,
    const std::string &nonce, const std::string &journal_sha256) {
  std::string detail;
  if (!coordinator_root.is_absolute() || !facman::base::validate_identifier(operation_id, detail) ||
      !facman::base::validate_identifier(nonce, detail) || !digest(journal_sha256))
    return facman::core::Result<Plan>::failure(failure(
        "self_maintenance_input_invalid", "epoch continuation identifiers are invalid"));
  facman::platform::StableDirectoryObject coordinator, epochs;
  std::vector<fs::path> epoch_names;
  if (!coordinator.open_no_follow(coordinator_root).ok() ||
      !coordinator.open_child_directory_no_follow("epochs", epochs).ok() ||
      !epochs.list_child_names_bounded(kMaximumLifecycleEpochs, epoch_names).ok())
    return facman::core::Result<Plan>::failure(epoch_recovery(
        "epoch continuation could not enumerate the held epoch root"));
  std::string journal_epoch_id;
  for (const fs::path &name : epoch_names) {
    if (!digest(name.string())) continue;
    PinnedLifecycleEpochScope candidate;
    facman::platform::StableDirectoryObject maintenance, operation;
    if (!candidate.open(coordinator_root, name.string()).ok() ||
        !candidate.epoch.open_child_directory_no_follow("maintenance", maintenance).ok() ||
        !maintenance.open_child_directory_no_follow(operation_id, operation).ok())
      continue;
    facman::platform::StableInputFile final_record;
    if (operation.open_child_file_no_follow_pinned("00-handoff-ready.v2.json", final_record).ok()) {
      if (!journal_epoch_id.empty()) return facman::core::Result<Plan>::failure(epoch_recovery(
          "more than one lifecycle epoch exposes the requested continuation handoff"));
      journal_epoch_id = name.string();
    }
  }
  if (journal_epoch_id.empty()) return facman::core::Result<Plan>::failure(epoch_recovery(
      "epoch continuation handoff journal is unavailable"));
  auto chain = discover_lifecycle_epoch_chain_impl(coordinator_root, {}, nullptr, operation_id,
                                                   journal_epoch_id);
  if (!chain || chain.value().epochs.empty() || chain.value().epochs.back().compatibility_epoch)
    return facman::core::Result<Plan>::failure(!chain ? chain.error() : epoch_recovery(
        "epoch continuation has no real lifecycle tail"));
  LifecycleEpoch epoch = chain.value().epochs.back();
  if (epoch.epoch_id != journal_epoch_id)
    return facman::core::Result<Plan>::failure(epoch_recovery(
        "continuation handoff belongs to a non-tail lifecycle epoch"));
  auto authority = admit_coordinator(coordinator_root, epoch.acceptance_root, false);
  if (!authority) return facman::core::Result<Plan>::failure(authority.error());
  auto held = acquire(authority.take_value(), operation_id);
  if (!held) return facman::core::Result<Plan>::failure(held.error());
  auto locked_chain = discover_lifecycle_epoch_chain_impl(coordinator_root, {}, nullptr,
      operation_id, epoch.epoch_id);
  if (!locked_chain || locked_chain.value().epochs.empty() ||
      locked_chain.value().epochs.back().compatibility_epoch ||
      locked_chain.value().epochs.back().epoch_id != epoch.epoch_id ||
      locked_chain.value().epochs.back().manifest_sha256 != epoch.manifest_sha256)
    return facman::core::Result<Plan>::failure(!locked_chain ? locked_chain.error() :
        epoch_recovery("lifecycle epoch tail changed before continuation admission"));
  epoch = locked_chain.value().epochs.back();
  PinnedLifecycleEpochScope scope;
  auto opened = scope.open(coordinator_root, epoch.epoch_id);
  if (!opened) return facman::core::Result<Plan>::failure(opened.error());
  auto active = discover_epoch_genesis_state(epoch, scope, nullptr, false, &operation_id);
  if (!active || !active.value().has_value()) return facman::core::Result<Plan>::failure(
      !active ? active.error() : epoch_recovery("epoch continuation has no active head"));
  facman::platform::StableDirectoryObject maintenance, operation;
  if (!scope.epoch.open_child_directory_no_follow("maintenance", maintenance).ok() ||
      !maintenance.open_child_directory_no_follow(operation_id, operation).ok())
    return facman::core::Result<Plan>::failure(epoch_recovery("epoch handoff journal is unavailable"));
  facman::platform::StableInputFile final_journal;
  if (!operation.open_child_file_no_follow_pinned("00-handoff-ready.v2.json", final_journal).ok() ||
      final_journal.size() == 0 || final_journal.size() > kMaximumEpochGenesisRecordBytes)
    return facman::core::Result<Plan>::failure(epoch_recovery(
        "epoch continuation handoff journal is unavailable or unsafe"));
  std::string journal_bytes(static_cast<std::size_t>(final_journal.size()), '\0');
  if (final_journal.read_at(0, journal_bytes.data(), journal_bytes.size()) != journal_bytes.size() ||
      !final_journal.revalidate().ok() || !final_journal.revalidate_path().ok())
    return facman::core::Result<Plan>::failure(epoch_recovery(
        "epoch continuation handoff journal changed while read"));
  notify_epoch_record_pinned(scope.epoch.path() / "maintenance" / operation_id /
                              "00-handoff-ready.v2.json");
  auto handoff = parse_epoch_handoff(journal_bytes);
  if (!handoff || hash(journal_bytes) != journal_sha256 || handoff.value().nonce != nonce ||
      handoff.value().epoch_id != epoch.epoch_id || handoff.value().manifest_sha256 != epoch.manifest_sha256 ||
      handoff.value().operation_id != operation_id ||
      handoff.value().source_generation_id != active.value()->active.generation_id ||
      handoff.value().source_activation_name != active.value()->activation_name ||
      handoff.value().source_activation_sha256 != active.value()->activation_sha256)
    return facman::core::Result<Plan>::failure(!handoff ? handoff.error() : epoch_recovery(
        "epoch continuation journal, nonce, manifest, or active head changed"));
  auto retained = validate_retained_inputs(epoch, operation_id, handoff.value().inputs);
  if (!retained) return facman::core::Result<Plan>::failure(retained.error());
  auto inspected = inspect_package(handoff.value().inputs.package);
  if (!inspected || inspected.value().package_sha256 != handoff.value().inputs.package_sha256 ||
      inspected.value().maintenance_launcher_sha256 != handoff.value().inputs.helper_sha256)
    return facman::core::Result<Plan>::failure(!inspected ? inspected.error() : epoch_recovery(
        "retained package no longer has its journaled identity"));
  notify_retained_inputs_after_initial_validation(retained.value());
  if (!revalidate_retained_inputs(retained.value()))
    return facman::core::Result<Plan>::failure(epoch_recovery(
        "retained continuation input changed during admission"));
  EpochTransitionRequest request{coordinator_root, epoch.epoch_id,
      handoff.value().operation == "update" ? Operation::update : Operation::downgrade,
      operation_id, inspected.take_value(), false};
  auto plan = make_epoch_transition_plan(epoch, *active.value(), request);
  if (!plan || plan.value().target.generation_id != handoff.value().target_generation_id)
    return facman::core::Result<Plan>::failure(!plan ? plan.error() : epoch_recovery(
        "epoch continuation target changed from its immutable handoff journal"));
  if (!held_file_matches_bytes(final_journal, journal_bytes) ||
      !revalidate_retained_inputs(retained.value()) || !operation.revalidate().ok() ||
      !scope.epoch.revalidate().ok())
    return facman::core::Result<Plan>::failure(epoch_recovery(
        "epoch continuation journal or retained input changed before return"));
  return plan;
}

namespace {

constexpr std::size_t kMaximumEpochContinuationRecords = 5U;

std::string epoch_continuation_record_bytes(
    const LifecycleEpoch &epoch, const EpochHandoff &handoff,
    const std::string &handoff_sha256, const std::string &phase,
    const ProviderApplyBinding &provider, const std::string &receipt = {},
    const std::string &outcome = {}) {
  json::ObjectBuilder object;
  object.add_string("schema", "facman.self_epoch_provider_continuation.v2");
  object.add_string("product_id", "facman");
  object.add_string("epoch_id", epoch.epoch_id);
  object.add_string("epoch_manifest_sha256", epoch.manifest_sha256);
  object.add_string("handoff_sha256", handoff_sha256);
  object.add_string("operation_id", handoff.operation_id);
  object.add_string("source_generation_id", handoff.source_generation_id);
  object.add_string("target_generation_id", handoff.target_generation_id);
  object.add_string("phase", phase);
  object.add_string("provider_plan_sha256", provider.provider_plan_sha256);
  object.add_string("transaction_id", provider.transaction_id);
  object.add_string("apply_sha256", provider.apply_sha256);
  object.add_string("apply_payload", provider.apply_payload);
  object.add_string("semantic_digest", provider.semantic_digest);
  object.add_string("bridge_key", provider.bridge_key);
  object.add_string("reviewed_plan_id", provider.reviewed_plan_id);
  object.add_string("reviewed_plan_digest", provider.reviewed_plan_digest);
  object.add_string("plan_created_at", provider.plan_created_at);
  object.add_string("request_id", provider.request_id);
  object.add_string("receipt_sha256", receipt);
  object.add_string("outcome", outcome);
  return object.serialize() + "\n";
}

facman::core::Result<ProviderApplyBinding> parse_epoch_continuation_record(
    const std::string &bytes, const LifecycleEpoch &epoch,
    const EpochHandoff &handoff, const std::string &handoff_sha256,
    const std::string &phase, std::string *receipt = nullptr,
    std::string *outcome = nullptr) {
  auto document = json::parse(bytes);
  const std::initializer_list<const char *> keys = {
      "schema", "product_id", "epoch_id", "epoch_manifest_sha256",
      "handoff_sha256", "operation_id", "source_generation_id",
      "target_generation_id", "phase", "provider_plan_sha256",
      "transaction_id", "apply_sha256", "apply_payload", "semantic_digest", "bridge_key",
      "reviewed_plan_id", "reviewed_plan_digest", "plan_created_at", "request_id",
      "receipt_sha256", "outcome"};
  if (!document || !exact_keys(document.value(), keys) ||
      !lifecycle_string_fields(document.value(), keys))
    return facman::core::Result<ProviderApplyBinding>::failure(epoch_recovery(
        "epoch provider continuation record has an incompatible exact schema"));
  ProviderApplyBinding provider{string_field(document.value(), "provider_plan_sha256"),
      string_field(document.value(), "transaction_id"),
      string_field(document.value(), "apply_sha256"),
      string_field(document.value(), "apply_payload"),
      string_field(document.value(), "semantic_digest"), string_field(document.value(), "bridge_key"),
      string_field(document.value(), "reviewed_plan_id"),
      string_field(document.value(), "reviewed_plan_digest"),
      string_field(document.value(), "plan_created_at"), string_field(document.value(), "request_id")};
  const std::string observed_receipt = string_field(document.value(), "receipt_sha256");
  const std::string observed_outcome = string_field(document.value(), "outcome");
  std::string detail;
  const bool outcome_record = phase == "30-provider-outcome";
  const bool verified_record = phase == "40-provider-verified";
  const bool receipt_required = verified_record ||
      (outcome_record && observed_outcome == "installed");
  if (string_field(document.value(), "schema") !=
          "facman.self_epoch_provider_continuation.v2" ||
      string_field(document.value(), "product_id") != "facman" ||
      string_field(document.value(), "epoch_id") != epoch.epoch_id ||
      string_field(document.value(), "epoch_manifest_sha256") != epoch.manifest_sha256 ||
      string_field(document.value(), "handoff_sha256") != handoff_sha256 ||
      string_field(document.value(), "operation_id") != handoff.operation_id ||
      string_field(document.value(), "source_generation_id") != handoff.source_generation_id ||
      string_field(document.value(), "target_generation_id") != handoff.target_generation_id ||
      string_field(document.value(), "phase") != phase ||
      provider.provider_plan_sha256 != handoff.provider_plan_sha256 ||
      !digest(provider.provider_plan_sha256) || !digest(provider.apply_sha256) ||
      !digest(provider.semantic_digest) || !digest(provider.bridge_key) ||
      provider.reviewed_plan_id.empty() || !digest(provider.reviewed_plan_digest) ||
      provider.plan_created_at.empty() || provider.request_id.empty() ||
      provider.apply_payload.empty() || hash(provider.apply_payload) != provider.apply_sha256 ||
      !facman::base::validate_identifier(provider.transaction_id, detail) ||
      (receipt_required ? !digest(observed_receipt) : !observed_receipt.empty()) ||
      (!outcome_record && !verified_record && !observed_outcome.empty()) ||
      (outcome_record && observed_outcome != "installed" &&
       observed_outcome != "recovery_required") ||
      (verified_record && observed_outcome != "verified") ||
      bytes != epoch_continuation_record_bytes(epoch, handoff, handoff_sha256,
                                                phase, provider, observed_receipt, observed_outcome))
    return facman::core::Result<ProviderApplyBinding>::failure(epoch_recovery(
        "epoch provider continuation record identity or canonical bytes are invalid"));
  if (receipt != nullptr) *receipt = observed_receipt;
  if (outcome != nullptr) *outcome = observed_outcome;
  return facman::core::Result<ProviderApplyBinding>::success(std::move(provider));
}

facman::core::Result<void> validate_epoch_continuation_names(
    const facman::platform::StableDirectoryObject &operation,
    std::vector<fs::path> &names) {
  if (!operation.list_child_names_bounded(kMaximumEpochContinuationRecords + 1U,
                                          names).ok() || names.empty() ||
      names.size() > kMaximumEpochContinuationRecords)
    return facman::core::Result<void>::failure(epoch_recovery(
        "epoch continuation operation contains an unsafe record set"));
  const std::vector<fs::path> allowed = {
      "00-handoff-ready.v2.json", "10-provider-apply-bound.v2.json",
      "20-provider-apply-entered.v2.json", "30-provider-outcome.v2.json",
      "40-provider-verified.v2.json"};
  for (std::size_t index = 0; index < names.size(); ++index) {
    const std::string final_name = allowed[index].string();
    const std::string staging_name = final_name.substr(0, final_name.size() - 7U) +
        "staging.v2.json";
    if (names[index] != allowed[index] &&
        !(index + 1U == names.size() && names[index] == staging_name))
      return facman::core::Result<void>::failure(epoch_recovery(
          "epoch continuation operation contains an unexpected or out-of-order record"));
  }
  return facman::core::Result<void>::success();
}

bool epoch_continuation_has(const std::vector<fs::path> &names, const char *name) {
  return std::find(names.begin(), names.end(), fs::path(name)) != names.end();
}

bool same_provider_apply_binding(const ProviderApplyBinding &left,
                                 const ProviderApplyBinding &right) {
  return left.provider_plan_sha256 == right.provider_plan_sha256 &&
      left.transaction_id == right.transaction_id && left.apply_sha256 == right.apply_sha256 &&
      left.apply_payload == right.apply_payload && left.semantic_digest == right.semantic_digest &&
      left.bridge_key == right.bridge_key && left.reviewed_plan_id == right.reviewed_plan_id &&
      left.reviewed_plan_digest == right.reviewed_plan_digest &&
      left.plan_created_at == right.plan_created_at && left.request_id == right.request_id;
}

std::string epoch_continuation_staging_name(const char *final_name) {
  const std::string name(final_name);
  return name.substr(0, name.size() - 7U) + "staging.v2.json";
}

} // namespace

facman::core::Result<EpochContinuationResponse>
execute_lifecycle_epoch_continuation(const EpochContinuationRequest &request,
                                     EpochContinuationEffects &effects) {
  auto admitted = admit_lifecycle_epoch_continuation(request.coordinator_root,
      request.operation_id, request.nonce, request.journal_sha256);
  if (!admitted) return facman::core::Result<EpochContinuationResponse>::failure(admitted.error());
  Plan transition = admitted.take_value();
  const std::string install_prefix = "facman.self.epoch.";
  if (transition.target.install_id.compare(0, install_prefix.size(), install_prefix) != 0 ||
      transition.target.install_id.size() < install_prefix.size() + 64U + 12U ||
      transition.target.install_id.compare(install_prefix.size() + 64U, 12U,
          ".generation.") != 0)
    return facman::core::Result<EpochContinuationResponse>::failure(epoch_recovery(
        "admitted epoch continuation target has no exact epoch install identity"));
  const std::string admitted_epoch_id = transition.target.install_id.substr(
      install_prefix.size(), 64U);
  if (!digest(admitted_epoch_id)) return facman::core::Result<EpochContinuationResponse>::failure(
      epoch_recovery("admitted epoch continuation target has an invalid epoch identity"));
  auto chain = discover_lifecycle_epoch_chain_impl(request.coordinator_root, {}, nullptr,
      request.operation_id, admitted_epoch_id);
  if (!chain || chain.value().epochs.empty() || chain.value().epochs.back().compatibility_epoch)
    return facman::core::Result<EpochContinuationResponse>::failure(!chain ? chain.error() :
        epoch_recovery("epoch continuation has no real lifecycle tail"));
  const LifecycleEpoch epoch = chain.value().epochs.back();
  // Admission releases its read-side lock before returning. Reacquire the
  // global lock for durable continuation records, then prove that the epoch
  // tail did not move between those two boundaries.
  auto authority = admit_coordinator(request.coordinator_root, epoch.acceptance_root, false);
  if (!authority) return facman::core::Result<EpochContinuationResponse>::failure(authority.error());
  auto lock = acquire(authority.take_value(), request.operation_id);
  if (!lock) return facman::core::Result<EpochContinuationResponse>::failure(lock.error());
  auto locked_chain = discover_lifecycle_epoch_chain_impl(request.coordinator_root, {}, nullptr,
      request.operation_id, epoch.epoch_id);
  if (!locked_chain || locked_chain.value().epochs.empty() ||
      locked_chain.value().epochs.back().epoch_id != epoch.epoch_id ||
      locked_chain.value().epochs.back().manifest_sha256 != epoch.manifest_sha256)
    return facman::core::Result<EpochContinuationResponse>::failure(!locked_chain ?
        locked_chain.error() : epoch_recovery("epoch continuation tail changed after admission"));
  PinnedLifecycleEpochScope scope;
  auto opened = scope.open(request.coordinator_root, epoch.epoch_id, true);
  if (!opened) return facman::core::Result<EpochContinuationResponse>::failure(opened.error());
  auto manifest_bytes = read_epoch_relative_bounded(scope.epoch, "epoch.v1.json",
                                                    kMaximumEpochGenesisRecordBytes);
  facman::platform::StableInputFile held_manifest;
  if (!manifest_bytes || hash(manifest_bytes.value()) != epoch.manifest_sha256 ||
      !scope.epoch.open_child_file_no_follow_pinned("epoch.v1.json", held_manifest).ok() ||
      !held_file_matches_bytes(held_manifest, manifest_bytes.value()))
    return facman::core::Result<EpochContinuationResponse>::failure(epoch_recovery(
        "epoch manifest cannot be held through provider execution"));
  facman::platform::StableDirectoryObject maintenance, operation;
  if (!scope.epoch.open_child_directory_no_follow_for_relative_writes("maintenance", maintenance).ok() ||
      !maintenance.open_child_directory_no_follow_for_relative_writes(request.operation_id, operation).ok())
    return facman::core::Result<EpochContinuationResponse>::failure(epoch_recovery(
        "epoch continuation operation directory is unavailable through held ancestors"));
  std::vector<fs::path> names;
  auto valid_names = validate_epoch_continuation_names(operation, names);
  if (!valid_names) return facman::core::Result<EpochContinuationResponse>::failure(valid_names.error());
  const bool entered_final_at_start = epoch_continuation_has(
      names, "20-provider-apply-entered.v2.json");
  auto handoff_bytes = read_epoch_relative_bounded(operation, "00-handoff-ready.v2.json",
                                                   kMaximumEpochGenesisRecordBytes);
  auto handoff = handoff_bytes ? parse_epoch_handoff(handoff_bytes.value())
      : facman::core::Result<EpochHandoff>::failure(handoff_bytes.error());
  if (!handoff || hash(handoff_bytes.value()) != request.journal_sha256)
    return facman::core::Result<EpochContinuationResponse>::failure(!handoff ? handoff.error() :
        epoch_recovery("epoch continuation handoff changed before provider execution"));
  facman::platform::StableInputFile held_handoff;
  if (!operation.open_child_file_no_follow_pinned("00-handoff-ready.v2.json", held_handoff).ok() ||
      !held_file_matches_bytes(held_handoff, handoff_bytes.value()))
    return facman::core::Result<EpochContinuationResponse>::failure(epoch_recovery(
        "epoch continuation handoff cannot be held through provider execution"));
  auto active_after_lock = discover_epoch_genesis_state(epoch, scope, nullptr, false,
                                                        &request.operation_id);
  if (!active_after_lock || !active_after_lock.value() ||
      active_after_lock.value()->active.generation_id != handoff.value().source_generation_id ||
      active_after_lock.value()->active.generation_id != transition.source.generation_id ||
      active_after_lock.value()->activation_name != handoff.value().source_activation_name ||
      active_after_lock.value()->activation_sha256 != handoff.value().source_activation_sha256 ||
      transition.target.generation_id != handoff.value().target_generation_id)
    return facman::core::Result<EpochContinuationResponse>::failure(!active_after_lock ?
        active_after_lock.error() : epoch_recovery("active epoch head changed after admission"));
  facman::platform::StableDirectoryObject held_generations, held_activations;
  facman::platform::StableInputFile held_source_generation, held_source_activation;
  const fs::path source_generation_name = epoch_generation_name(
      handoff.value().source_generation_id);
  const fs::path source_activation_name = handoff.value().source_activation_name;
  if (!scope.epoch.open_child_directory_no_follow("generations", held_generations).ok() ||
      !scope.epoch.open_child_directory_no_follow("activations", held_activations).ok())
    return facman::core::Result<EpochContinuationResponse>::failure(epoch_recovery(
        "active epoch source ancestors cannot be held"));
  auto source_generation_bytes = read_epoch_relative_bounded(held_generations, source_generation_name,
      kMaximumEpochGenesisRecordBytes);
  auto source_activation_bytes = read_epoch_relative_bounded(held_activations, source_activation_name,
      kMaximumEpochGenesisRecordBytes);
  if (!source_generation_bytes || !source_activation_bytes ||
      hash(source_activation_bytes.value()) != handoff.value().source_activation_sha256 ||
      !held_generations.open_child_file_no_follow_pinned(source_generation_name, held_source_generation).ok() ||
      !held_activations.open_child_file_no_follow_pinned(source_activation_name, held_source_activation).ok() ||
      !held_file_matches_bytes(held_source_generation, source_generation_bytes.value()) ||
      !held_file_matches_bytes(held_source_activation, source_activation_bytes.value()))
    return facman::core::Result<EpochContinuationResponse>::failure(epoch_recovery(
        "active epoch source records cannot be held"));
  auto retained = validate_retained_inputs(epoch, request.operation_id, handoff.value().inputs);
  if (!retained || !revalidate_retained_inputs(retained.value()))
    return facman::core::Result<EpochContinuationResponse>::failure(!retained ? retained.error() :
        epoch_recovery("retained continuation input changed before provider execution"));
  struct HeldContinuationRecord {
    fs::path name;
    std::string bytes;
    facman::platform::StableInputFile file;
  };
  std::vector<HeldContinuationRecord> held_records;
  const auto refresh_held_records = [&]() {
    std::vector<fs::path> current;
    if (!validate_epoch_continuation_names(operation, current).ok()) return false;
    std::vector<HeldContinuationRecord> replacement;
    for (const auto &name : current) {
      if (name == "00-handoff-ready.v2.json") continue;
      auto bytes = read_epoch_relative_bounded(operation, name, kMaximumEpochGenesisRecordBytes);
      HeldContinuationRecord record;
      if (!bytes || !operation.open_child_file_no_follow_pinned(name, record.file).ok() ||
          !held_file_matches_bytes(record.file, bytes.value())) return false;
      record.name = name;
      record.bytes = bytes.take_value();
      replacement.push_back(std::move(record));
    }
    held_records = std::move(replacement);
    return true;
  };
  if (!refresh_held_records()) return facman::core::Result<EpochContinuationResponse>::failure(
      epoch_recovery("epoch continuation records cannot be held through provider execution"));
  const auto refresh_after_publish = [&]
      (const std::vector<std::pair<fs::path, std::string>> &prior,
       const fs::path &final_name, const std::string &final_bytes) {
    if (!refresh_held_records()) return false;
    if (held_records.size() != prior.size() + 1U) return false;
    for (const auto &expected : prior) {
      const auto found = std::find_if(held_records.begin(), held_records.end(),
          [&](const HeldContinuationRecord &record) { return record.name == expected.first; });
      if (found == held_records.end() || found->bytes != expected.second) return false;
    }
    const auto published = std::find_if(held_records.begin(), held_records.end(),
        [&](const HeldContinuationRecord &record) { return record.name == final_name; });
    return published != held_records.end() && published->bytes == final_bytes;
  };
  const auto held_snapshot = [&]() {
    std::vector<std::pair<fs::path, std::string>> result;
    for (const auto &record : held_records) result.emplace_back(record.name, record.bytes);
    return result;
  };
  const auto custody_valid = [&]() {
    std::vector<fs::path> exact_names;
    const bool names_exact = validate_epoch_continuation_names(operation, exact_names).ok();
    auto current_active = discover_epoch_genesis_state(epoch, scope, nullptr, false,
                                                       &request.operation_id);
    return names_exact && current_active && current_active.value() &&
        current_active.value()->active.generation_id == handoff.value().source_generation_id &&
        current_active.value()->activation_name == source_activation_name &&
        current_active.value()->activation_sha256 == handoff.value().source_activation_sha256 &&
        held_file_matches_bytes(held_manifest, manifest_bytes.value()) &&
        held_file_matches_bytes(held_source_generation, source_generation_bytes.value()) &&
        held_file_matches_bytes(held_source_activation, source_activation_bytes.value()) &&
        held_file_matches_bytes(held_handoff, handoff_bytes.value()) &&
        revalidate_retained_inputs(retained.value()) &&
        exact_names.size() == held_records.size() + 1U &&
        !exact_names.empty() && exact_names.front() == "00-handoff-ready.v2.json" &&
        std::equal(held_records.begin(), held_records.end(), exact_names.begin() + 1,
            [](const HeldContinuationRecord &record, const fs::path &name) {
              return record.name == name;
            }) &&
        held_generations.revalidate().ok() && held_activations.revalidate().ok() &&
        std::all_of(held_records.begin(), held_records.end(), [](HeldContinuationRecord &record) {
          return held_file_matches_bytes(record.file, record.bytes);
        }) && operation.revalidate().ok() &&
        maintenance.revalidate().ok() && scope.epoch.revalidate().ok() &&
        scope.epochs.revalidate().ok() && scope.coordinator.revalidate().ok();
  };
  const fs::path journal = scope.epoch.path() / "maintenance" / request.operation_id /
      "00-handoff-ready.v2.json";
  if (!request.apply) return facman::core::Result<EpochContinuationResponse>::success(
      {"plan", std::move(transition), journal, {}});

  ProviderApplyBinding binding;
  const char *bound_name = "10-provider-apply-bound.v2.json";
  const std::string bound_staging = epoch_continuation_staging_name(bound_name);
  if (epoch_continuation_has(names, bound_staging.c_str())) {
    auto bytes = read_epoch_relative_bounded(operation, bound_staging,
                                             kMaximumEpochGenesisRecordBytes);
    auto parsed = bytes ? parse_epoch_continuation_record(bytes.value(), epoch, handoff.value(),
        request.journal_sha256, "10-provider-apply-bound")
        : facman::core::Result<ProviderApplyBinding>::failure(bytes.error());
    if (!parsed || !custody_valid()) return facman::core::Result<EpochContinuationResponse>::failure(
        !parsed ? parsed.error() : epoch_recovery("epoch custody changed before staging recovery"));
    // Windows no-follow handles deliberately retain a sharing restriction; a
    // staging handle must be released only after its bytes were parsed before
    // atomically publishing that same identity.
    std::vector<std::pair<fs::path, std::string>> prior_bound_records;
    for (const auto &record : held_records)
      if (record.name != bound_staging)
        prior_bound_records.emplace_back(record.name, record.bytes);
    held_records.clear();
    auto published = publish_epoch_record(operation, bound_staging, bound_name, bytes.value());
    if (!published || !validate_epoch_continuation_names(operation, names).ok() ||
        !refresh_after_publish(prior_bound_records, bound_name, bytes.value()))
      return facman::core::Result<EpochContinuationResponse>::failure(!published ? published.error() :
          epoch_recovery("epoch bound staging recovery did not produce an exact record set"));
  }
  if (epoch_continuation_has(names, bound_name)) {
    auto bytes = read_epoch_relative_bounded(operation, bound_name, kMaximumEpochGenesisRecordBytes);
    auto parsed = bytes ? parse_epoch_continuation_record(bytes.value(), epoch, handoff.value(),
        request.journal_sha256, "10-provider-apply-bound")
        : facman::core::Result<ProviderApplyBinding>::failure(bytes.error());
    if (!parsed) return facman::core::Result<EpochContinuationResponse>::failure(parsed.error());
    binding = parsed.take_value();
    if (!custody_valid()) return facman::core::Result<EpochContinuationResponse>::failure(
        epoch_recovery("epoch custody changed before provider binding rehydration"));
    auto reconstructed = effects.rehydrate_install_local(transition, binding);
    if (!custody_valid()) return facman::core::Result<EpochContinuationResponse>::failure(
        epoch_recovery("epoch custody changed during provider binding rehydration"));
    if (!reconstructed)
      return facman::core::Result<EpochContinuationResponse>::failure(epoch_recovery(
          "provider apply identity could not be rehydrated from its durable binding"));
  } else {
    if (!custody_valid() || effects.inspect_candidate(transition) != CandidateState::absent ||
        !custody_valid())
      return facman::core::Result<EpochContinuationResponse>::failure(epoch_recovery(
          "epoch provider candidate is not absent before apply binding"));
    if (!custody_valid()) return facman::core::Result<EpochContinuationResponse>::failure(
        epoch_recovery("epoch custody changed before provider apply binding"));
    auto bound = effects.bind_install_local(transition, handoff.value().provider_plan_sha256);
    if (!custody_valid()) return facman::core::Result<EpochContinuationResponse>::failure(
        epoch_recovery("epoch custody changed during provider apply binding"));
    std::string binding_detail;
    if (!bound || bound.value().provider_plan_sha256 != handoff.value().provider_plan_sha256 ||
        !digest(bound.value().apply_sha256) || bound.value().apply_payload.empty() ||
        hash(bound.value().apply_payload) != bound.value().apply_sha256 ||
        !digest(bound.value().semantic_digest) || !digest(bound.value().bridge_key) ||
        bound.value().reviewed_plan_id.empty() || !digest(bound.value().reviewed_plan_digest) ||
        bound.value().plan_created_at.empty() || bound.value().request_id.empty() ||
        !facman::base::validate_identifier(bound.value().transaction_id, binding_detail))
      return facman::core::Result<EpochContinuationResponse>::failure(!bound ? bound.error() :
          epoch_recovery("provider binding does not match the immutable handoff"));
    binding = bound.take_value();
    const std::string bytes = epoch_continuation_record_bytes(epoch, handoff.value(),
        request.journal_sha256, "10-provider-apply-bound", binding);
    const auto prior_bound_records = held_snapshot();
    auto written = publish_epoch_record(operation, "10-provider-apply-bound.staging.v2.json",
        bound_name, bytes);
    if (!written) return facman::core::Result<EpochContinuationResponse>::failure(written.error());
    if (!written || !validate_epoch_continuation_names(operation, names).ok() ||
        !refresh_after_publish(prior_bound_records, bound_name, bytes))
      return facman::core::Result<EpochContinuationResponse>::failure(!written ? written.error() :
          epoch_recovery("epoch provider binding record set is not exact"));
  }
  std::string recorded_outcome_receipt, recorded_verified_receipt, recorded_outcome;
  for (const auto &record : std::vector<std::pair<const char *, const char *>>{
           {"20-provider-apply-entered.v2.json", "20-provider-apply-entered"},
           {"30-provider-outcome.v2.json", "30-provider-outcome"},
           {"40-provider-verified.v2.json", "40-provider-verified"}}) {
    const std::string staging = epoch_continuation_staging_name(record.first);
    const bool staged = epoch_continuation_has(names, staging.c_str());
    if (!epoch_continuation_has(names, record.first) && !staged) continue;
    const char *read_name = staged ? staging.c_str() : record.first;
    auto bytes = read_epoch_relative_bounded(operation, read_name,
                                             kMaximumEpochGenesisRecordBytes);
    std::string receipt, outcome;
    auto parsed = bytes ? parse_epoch_continuation_record(bytes.value(), epoch,
        handoff.value(), request.journal_sha256, record.second, &receipt, &outcome)
        : facman::core::Result<ProviderApplyBinding>::failure(bytes.error());
    if (!parsed || !same_provider_apply_binding(parsed.value(), binding))
      return facman::core::Result<EpochContinuationResponse>::failure(!parsed ? parsed.error() :
          epoch_recovery("epoch provider continuation record changed its durable binding"));
    if (staged) {
      if (!custody_valid()) return facman::core::Result<EpochContinuationResponse>::failure(
          epoch_recovery("epoch custody changed before staging recovery"));
      std::vector<std::pair<fs::path, std::string>> prior_staging_records;
      for (const auto &held : held_records)
        if (held.name != staging)
          prior_staging_records.emplace_back(held.name, held.bytes);
      held_records.clear();
      auto published = publish_epoch_record(operation, staging, record.first, bytes.value());
      if (!published || !validate_epoch_continuation_names(operation, names).ok() ||
          !refresh_after_publish(prior_staging_records, record.first, bytes.value()))
        return facman::core::Result<EpochContinuationResponse>::failure(!published ? published.error() :
            epoch_recovery("epoch staging recovery did not produce an exact record set"));
    }
    if (std::string(record.second) == "30-provider-outcome") {
      recorded_outcome_receipt = receipt;
      recorded_outcome = outcome;
    } else if (std::string(record.second) == "40-provider-verified") {
      recorded_verified_receipt = receipt;
    }
  }
  if (!entered_final_at_start) {
    if (!epoch_continuation_has(names, "20-provider-apply-entered.v2.json")) {
      const std::string bytes = epoch_continuation_record_bytes(epoch, handoff.value(),
          request.journal_sha256, "20-provider-apply-entered", binding);
      const auto prior_entered_records = held_snapshot();
      auto written = publish_epoch_record(operation, "20-provider-apply-entered.staging.v2.json",
          "20-provider-apply-entered.v2.json", bytes);
      if (!written || !validate_epoch_continuation_names(operation, names).ok() ||
          !refresh_after_publish(prior_entered_records, "20-provider-apply-entered.v2.json", bytes))
        return facman::core::Result<EpochContinuationResponse>::failure(!written ? written.error() :
            epoch_recovery("epoch apply-entered record set is not exact"));
    }
    if (!custody_valid()) return facman::core::Result<EpochContinuationResponse>::failure(
        epoch_recovery("epoch custody changed before provider apply"));
    const EffectResult applied = effects.apply_bound_install_local(transition, binding);
    if (!custody_valid()) return facman::core::Result<EpochContinuationResponse>::failure(
        epoch_recovery("epoch custody changed during provider apply"));
    if (!applied.ok || applied.outcome_unknown || !digest(applied.receipt_sha256))
      return facman::core::Result<EpochContinuationResponse>::failure(effect_error(
        "self_maintenance_install_failed", "epoch provider apply did not return an exact receipt", applied).error());
  }
  if (recorded_outcome == "recovery_required")
    return facman::core::Result<EpochContinuationResponse>::failure(epoch_recovery(
        "provider apply entered and requires external recovery inspection"));
  if (!custody_valid()) return facman::core::Result<EpochContinuationResponse>::failure(
      epoch_recovery("epoch custody changed before installed candidate inspection"));
  const CandidateState post_apply_candidate = effects.inspect_candidate(transition);
  if (!custody_valid()) return facman::core::Result<EpochContinuationResponse>::failure(
      epoch_recovery("epoch custody changed during installed candidate inspection"));
  if (post_apply_candidate != CandidateState::exact) {
    if (!epoch_continuation_has(names, "30-provider-outcome.v2.json")) {
      const std::string recovery_bytes = epoch_continuation_record_bytes(epoch, handoff.value(),
          request.journal_sha256, "30-provider-outcome", binding, {}, "recovery_required");
      const auto prior_recovery_records = held_snapshot();
      auto written = publish_epoch_record(operation, "30-provider-outcome.staging.v2.json",
          "30-provider-outcome.v2.json", recovery_bytes);
      if (!written || !refresh_after_publish(prior_recovery_records,
          "30-provider-outcome.v2.json", recovery_bytes)) return facman::core::Result<EpochContinuationResponse>::failure(
          !written ? written.error() : epoch_recovery("epoch recovery outcome cannot be held"));
    }
    return facman::core::Result<EpochContinuationResponse>::failure(epoch_recovery(
        "provider apply was entered but its exact installed outcome is not recoverable"));
  }
  if (!custody_valid()) return facman::core::Result<EpochContinuationResponse>::failure(
      epoch_recovery("epoch custody changed before installed inspection"));
  const EffectResult inspected = effects.inspect_installed(transition, binding);
  if (!custody_valid()) return facman::core::Result<EpochContinuationResponse>::failure(
      epoch_recovery("epoch custody changed during installed inspection"));
  if (!inspected.ok || inspected.outcome_unknown || !digest(inspected.receipt_sha256)) {
    if (!epoch_continuation_has(names, "30-provider-outcome.v2.json")) {
      const std::string recovery_bytes = epoch_continuation_record_bytes(epoch, handoff.value(),
          request.journal_sha256, "30-provider-outcome", binding, {}, "recovery_required");
      const auto prior_recovery_records = held_snapshot();
      auto written = publish_epoch_record(operation, "30-provider-outcome.staging.v2.json",
          "30-provider-outcome.v2.json", recovery_bytes);
      if (!written || !refresh_after_publish(prior_recovery_records,
          "30-provider-outcome.v2.json", recovery_bytes)) return facman::core::Result<EpochContinuationResponse>::failure(
          !written ? written.error() : epoch_recovery("epoch recovery outcome cannot be held"));
    }
    return facman::core::Result<EpochContinuationResponse>::failure(effect_error(
        "self_maintenance_inspect_failed", "epoch provider installed state is not exact", inspected).error());
  }
  if (!recorded_outcome_receipt.empty() && recorded_outcome_receipt != inspected.receipt_sha256)
    return facman::core::Result<EpochContinuationResponse>::failure(epoch_recovery(
        "installed inspection receipt differs from the durable outcome"));
  if (!epoch_continuation_has(names, "30-provider-outcome.v2.json")) {
    const std::string outcome_bytes = epoch_continuation_record_bytes(epoch, handoff.value(),
        request.journal_sha256, "30-provider-outcome", binding, inspected.receipt_sha256, "installed");
    const auto prior_outcome_records = held_snapshot();
    auto written = publish_epoch_record(operation, "30-provider-outcome.staging.v2.json",
        "30-provider-outcome.v2.json", outcome_bytes);
    if (!written || !refresh_after_publish(prior_outcome_records,
        "30-provider-outcome.v2.json", outcome_bytes)) return facman::core::Result<EpochContinuationResponse>::failure(
        !written ? written.error() : epoch_recovery("epoch provider outcome cannot be held"));
  }
  // 40 is terminal: its staging file was created only after a successful
  // verification callback.  Reproduce the transaction-bound installed
  // identity, then preserve that immutable verification receipt rather than
  // creating a fresh timestamped provider verification.
  if (!recorded_verified_receipt.empty()) {
    if (!custody_valid()) return facman::core::Result<EpochContinuationResponse>::failure(
        epoch_recovery("epoch custody changed before terminal continuation return"));
    const EffectResult terminal = effects.validate_terminal_verification(
        transition, binding, recorded_verified_receipt);
    if (!custody_valid()) return facman::core::Result<EpochContinuationResponse>::failure(
        epoch_recovery("epoch custody changed during terminal verification validation"));
    if (!terminal.ok || terminal.outcome_unknown ||
        terminal.receipt_sha256 != recorded_verified_receipt)
      return facman::core::Result<EpochContinuationResponse>::failure(effect_error(
          "self_maintenance_verify_failed", "durable provider verification is not reproducible",
          terminal).error());
    return facman::core::Result<EpochContinuationResponse>::success(
        {"provider_verified", std::move(transition), journal, std::move(binding)});
  }
  if (!custody_valid()) return facman::core::Result<EpochContinuationResponse>::failure(
      epoch_recovery("epoch custody changed before provider verification"));
  const EffectResult verified = effects.verify_installed(transition);
  if (!custody_valid()) return facman::core::Result<EpochContinuationResponse>::failure(
      epoch_recovery("epoch custody changed during provider verification"));
  if (!verified.ok || verified.outcome_unknown || !digest(verified.receipt_sha256))
    return facman::core::Result<EpochContinuationResponse>::failure(effect_error(
        "self_maintenance_verify_failed", "epoch provider installed state failed verification", verified).error());
  if (!recorded_verified_receipt.empty() && recorded_verified_receipt != verified.receipt_sha256)
    return facman::core::Result<EpochContinuationResponse>::failure(epoch_recovery(
        "provider verification receipt differs from the durable verification"));
  if (!epoch_continuation_has(names, "40-provider-verified.v2.json")) {
    const std::string verified_bytes = epoch_continuation_record_bytes(epoch, handoff.value(),
        request.journal_sha256, "40-provider-verified", binding, verified.receipt_sha256, "verified");
    const auto prior_verified_records = held_snapshot();
    auto written = publish_epoch_record(operation, "40-provider-verified.staging.v2.json",
        "40-provider-verified.v2.json", verified_bytes);
    if (!written || !refresh_after_publish(prior_verified_records,
        "40-provider-verified.v2.json", verified_bytes)) return facman::core::Result<EpochContinuationResponse>::failure(
        !written ? written.error() : epoch_recovery("epoch provider verification cannot be held"));
  }
  if (!custody_valid()) return facman::core::Result<EpochContinuationResponse>::failure(
      epoch_recovery("epoch custody changed before provider continuation return"));
  return facman::core::Result<EpochContinuationResponse>::success(
      {"provider_verified", std::move(transition), journal, std::move(binding)});
}

facman::core::Result<LifecycleEpochChain> publish_lifecycle_epoch(
    const fs::path &coordinator_root, const LifecycleEpoch &proposed,
    bool apply) {
  if (!coordinator_root.is_absolute() || !proposed.acceptance_root.is_absolute() ||
      !proposed.logical_root.is_absolute() || !proposed.state_root.is_absolute() ||
      (!proposed.genesis_generation_id.empty() && !digest(proposed.genesis_generation_id)))
    return facman::core::Result<LifecycleEpochChain>::failure(failure(
        "self_maintenance_input_invalid", "lifecycle epoch inputs are incomplete"));
  auto observed = discover_lifecycle_epoch_chain_impl(coordinator_root);
  if (!observed) return facman::core::Result<LifecycleEpochChain>::failure(observed.error());

  LifecycleEpoch next = proposed;
  next.compatibility_epoch = false;
  next.manifest_sha256.clear();
  next.retirement_sha256.clear();
  const std::string submitted_id = hash(lifecycle_identity_bytes(next));
  if (!next.epoch_id.empty() && next.epoch_id != submitted_id)
    return facman::core::Result<LifecycleEpochChain>::failure(failure(
        "self_maintenance_input_invalid", "proposed lifecycle epoch id is not canonical"));
  next.epoch_id = submitted_id;
  const std::string submitted_manifest = lifecycle_manifest_bytes(next);
  bool exact_existing = false;
  for (const LifecycleEpoch &existing : observed.value().epochs) {
    if (existing.epoch_id != next.epoch_id) continue;
    if (existing.compatibility_epoch || existing.manifest_sha256 != hash(submitted_manifest))
      return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
          "an existing lifecycle epoch id has different immutable bytes"));
    exact_existing = true;
  }
  if (exact_existing && !apply) return observed;
  if (exact_existing && apply) {
    auto admission = admit_coordinator(coordinator_root, next.acceptance_root, false);
    if (!admission) return facman::core::Result<LifecycleEpochChain>::failure(admission.error());
    auto lock = acquire(admission.take_value(), "lifecycle.epoch.publish");
    if (!lock) return facman::core::Result<LifecycleEpochChain>::failure(lock.error());
    auto rechecked = discover_lifecycle_epoch_chain_impl(coordinator_root);
    if (!rechecked) return facman::core::Result<LifecycleEpochChain>::failure(rechecked.error());
    facman::platform::StableDirectoryObject epochs, epoch_directory;
    if (!lock.value().admission.coordinator.open_child_directory_no_follow_for_relative_writes(
            "epochs", epochs).ok() ||
        !epochs.open_child_directory_no_follow_for_relative_writes(next.epoch_id,
            epoch_directory).ok() || !epoch_directory.flush_metadata().ok() ||
        !epochs.flush_metadata().ok() ||
        !lock.value().admission.coordinator.flush_metadata().ok())
      return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
          "exact epoch retry could not revalidate and flush its directory hierarchy"));
    return discover_lifecycle_epoch_chain_impl(coordinator_root);
  }
  const LifecycleEpoch *predecessor = observed.value().epochs.empty()
      ? nullptr : &observed.value().epochs.back();
  if (predecessor == nullptr) {
    if (!next.predecessor_epoch_id.empty() ||
        !next.predecessor_manifest_sha256.empty() ||
        !next.predecessor_retirement_sha256.empty())
      return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
          "the first lifecycle epoch must have empty predecessor bindings"));
  } else {
    if (!lifecycle_roots_equal(*predecessor, next) ||
        predecessor->retirement_sha256.empty())
      return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
          "a lifecycle epoch predecessor is active, incomplete, or has different roots"));
    if (next.predecessor_epoch_id != predecessor->epoch_id ||
        next.predecessor_manifest_sha256 != predecessor->manifest_sha256 ||
        next.predecessor_retirement_sha256 != predecessor->retirement_sha256)
      return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
          "lifecycle epoch predecessor bindings do not match the current head"));
  }
  // This layer only publishes the immutable boundary.  It does not route a
  // provider operation into the epoch yet, so a new epoch is initialized with
  // no activation history and consequently no genesis generation.
  if (!digest(next.genesis_generation_id))
    return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
        "manifest-only publication must reserve one exact genesis generation"));
  if (next.epoch_id == kCompatibilityEpochId)
    return facman::core::Result<LifecycleEpochChain>::failure(failure(
        "self_maintenance_input_invalid", "the compatibility epoch id cannot be persisted"));
  const std::string bytes = lifecycle_manifest_bytes(next);
  if (bytes.empty() || bytes.size() > kMaximumLifecycleManifestBytes)
    return facman::core::Result<LifecycleEpochChain>::failure(failure(
        "self_maintenance_input_invalid", "lifecycle epoch manifest exceeds its byte limit"));
  next.manifest_sha256 = hash(bytes);
  LifecycleEpochChain preview = observed.value();
  preview.epochs.push_back(next);
  if (!apply) return facman::core::Result<LifecycleEpochChain>::success(std::move(preview));

  auto admission = admit_coordinator(coordinator_root, next.acceptance_root, true);
  if (!admission) return facman::core::Result<LifecycleEpochChain>::failure(admission.error());
  auto created = create_admitted_coordinator(admission.value());
  if (!created) return facman::core::Result<LifecycleEpochChain>::failure(created.error());
  auto lock = acquire(admission.take_value(), "lifecycle.epoch.publish");
  if (!lock) return facman::core::Result<LifecycleEpochChain>::failure(lock.error());
  auto rechecked = discover_lifecycle_epoch_chain_impl(coordinator_root);
  if (!rechecked) return facman::core::Result<LifecycleEpochChain>::failure(rechecked.error());
  if (rechecked.value().epochs.size() != observed.value().epochs.size())
    return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
        "lifecycle epoch chain changed before publication"));
  for (std::size_t index = 0; index < observed.value().epochs.size(); ++index) {
    const LifecycleEpoch &before = observed.value().epochs[index];
    const LifecycleEpoch &after = rechecked.value().epochs[index];
    if (before.epoch_id != after.epoch_id ||
        before.manifest_sha256 != after.manifest_sha256 ||
        before.retirement_sha256 != after.retirement_sha256)
      return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
          "lifecycle epoch predecessor chain changed before publication"));
  }

  facman::platform::StableDirectoryObject epochs;
  auto opened = lock.value().admission.coordinator.open_child_directory_no_follow_for_relative_writes(
      "epochs", epochs);
  if (!opened.ok()) {
    facman::platform::PathIdentity identity;
    const auto inspected = facman::platform::inspect_path_no_follow(
        coordinator_root / "epochs", identity);
    if (inspected.ok() && !identity.exists)
      opened = lock.value().admission.coordinator.create_child_directory_exclusive(
          "epochs", epochs);
  }
  if (!opened.ok()) return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
      "epoch root could not be opened or created under the held coordinator", opened.detail));
  facman::platform::StableDirectoryObject epoch_directory;
  opened = epochs.create_child_directory_exclusive(next.epoch_id, epoch_directory);
  if (!opened.ok()) {
    opened = epochs.open_child_directory_no_follow_for_relative_writes(next.epoch_id,
                                                                         epoch_directory);
    if (!opened.ok()) return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
        "epoch directory could not be created or pinned", opened.detail));
    auto existing = read_epoch_manifest(epoch_directory, "epoch.v1.json");
    if (!existing || existing.value() != bytes)
      return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
          "existing epoch directory is missing its exact immutable manifest"));
    if (!epoch_directory.flush_metadata().ok() || !epochs.flush_metadata().ok() ||
        !lock.value().admission.coordinator.flush_metadata().ok())
      return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
          "existing epoch retry could not flush the directory hierarchy"));
    return discover_lifecycle_epoch_chain_impl(coordinator_root);
  }
  facman::platform::DurableOutputFile output;
  const auto staged = epoch_directory.create_child_file_exclusive(
      "epoch.staging.v1.json", kMaximumLifecycleManifestBytes, output);
  if (!staged.ok() || output.write_at(0, bytes.data(), bytes.size()) != bytes.size())
    return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
        "epoch manifest staging could not be completed", staged.detail));
  const auto published = output.publish_sibling_no_replace("epoch.v1.json");
  if (!published.ok()) return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
      "epoch manifest publication did not reach a verified durable state", published.detail));
  if (!epoch_directory.flush_metadata().ok() || !epochs.flush_metadata().ok() ||
      !lock.value().admission.coordinator.flush_metadata().ok())
    return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
        "epoch directory hierarchy could not be flushed"));
  return discover_lifecycle_epoch_chain_impl(coordinator_root);
}

facman::core::Result<RetirementResponse> retire_active(
    const RetirementRequest &request, RetirementEffects &effects) {
  auto reviewed = discover_activation_chain(request.coordinator_root);
  if (!reviewed)
    return facman::core::Result<RetirementResponse>::failure(reviewed.error());
  if (!reviewed.value().has_value())
    return facman::core::Result<RetirementResponse>::success(
        {"completed", {}, {}});
  const ActivationChain review = *reviewed.value();
  const auto reviewed_steps = retirement_steps(review);
  if (reviewed_steps.empty())
    return facman::core::Result<RetirementResponse>::failure(failure(
        "self_maintenance_retirement_recovery_required",
        "retirement has no validated generation steps"));
  const Generation &active = reviewed_steps.back().generation;
  for (const auto &step : reviewed_steps) {
    if (!same_path(step.generation.logical_root, active.logical_root) ||
        !same_path(step.generation.state_root, active.state_root) ||
        !same_path(step.generation.acceptance_root, active.acceptance_root))
      return facman::core::Result<RetirementResponse>::failure(failure(
          "self_maintenance_retirement_recovery_required",
          "activation chain generations do not share one exact authority"));
  }
  const fs::path directory = retirement_directory(request.coordinator_root,
                                                   review);
  if (!request.apply)
    return facman::core::Result<RetirementResponse>::success(
        {"planned", directory, reviewed_steps});

  auto authority = admit_coordinator(request.coordinator_root,
                                     active.acceptance_root, false);
  if (!authority)
    return facman::core::Result<RetirementResponse>::failure(authority.error());
  const std::string lock_operation =
      "retirement." + review.activation_sha256.substr(0, 32);
  auto held = acquire(authority.take_value(), lock_operation);
  if (!held)
    return facman::core::Result<RetirementResponse>::failure(held.error());
  const CoordinatorLockToken coordinator_lock(
      request.coordinator_root.lexically_normal(), lock_operation);

  // Re-read the complete chain under the global coordinator lock.  The
  // journal is intentionally bound to this exact head and all ordered
  // generation records, never to an inferred current install root.
  auto current = discover_activation_chain(request.coordinator_root);
  if (!current || !current.value().has_value() ||
      retirement_chain_digest(*current.value()) != retirement_chain_digest(review))
    return facman::core::Result<RetirementResponse>::failure(failure(
        "self_maintenance_retirement_recovery_required",
        "activation chain changed before retirement could begin"));
  const ActivationChain chain = *current.value();
  const auto steps = retirement_steps(chain);
  const fs::path retirement_root = request.coordinator_root / "retirements";
  std::error_code status;
  if (fs::exists(retirement_root, status)) {
    if (status || !fs::is_directory(retirement_root, status) || status)
      return facman::core::Result<RetirementResponse>::failure(failure(
          "self_maintenance_retirement_recovery_required",
          "retirement journal root is unavailable"));
    for (fs::directory_iterator it(retirement_root, status), end;
         !status && it != end; it.increment(status)) {
      if (it->symlink_status(status).type() != fs::file_type::directory || status ||
          it->path().lexically_normal() != directory.lexically_normal())
        return facman::core::Result<RetirementResponse>::failure(failure(
            "self_maintenance_retirement_recovery_required",
            "retirement journal root contains a stale, foreign, or unknown chain"));
    }
    if (status) return facman::core::Result<RetirementResponse>::failure(failure(
        "self_maintenance_retirement_recovery_required",
        "retirement journal root changed during enumeration", status.message()));
  } else if (status || !fs::create_directories(retirement_root, status) || status) {
    return facman::core::Result<RetirementResponse>::failure(failure(
        "self_maintenance_retirement_recovery_required",
        "retirement journal root could not be created", status.message()));
  }
  if (!fs::exists(directory, status) &&
      (!fs::create_directory(directory, status) || status))
    return facman::core::Result<RetirementResponse>::failure(failure(
        "self_maintenance_retirement_recovery_required",
        "retirement journal could not be created", status.message()));
  if (status || !fs::is_directory(directory, status) || status)
    return facman::core::Result<RetirementResponse>::failure(failure(
        "self_maintenance_retirement_recovery_required",
        "retirement journal path is unsafe"));
  auto intent = ensure_immutable(directory / "00-intent.v1.json",
                                 retirement_intent_json(chain, steps));
  if (!intent)
    return facman::core::Result<RetirementResponse>::failure(intent.error());
  bool completed = false;
  auto validated = validate_retirement_directory(directory, chain, steps,
                                                 &completed);
  if (!validated)
    return facman::core::Result<RetirementResponse>::failure(validated.error());
  if (completed)
    return facman::core::Result<RetirementResponse>::success(
        {"completed", directory, steps});

  for (std::size_t index = 0; index < steps.size(); ++index) {
    auto entered = exact_retirement_file(retirement_step_path(directory, index,
                                                               "entered"),
        retirement_step_json(steps[index], index, "entered"));
    auto done = exact_retirement_file(retirement_step_path(directory, index,
                                                            "completed"),
        retirement_step_json(steps[index], index, "completed"));
    if (!entered || !done)
      return facman::core::Result<RetirementResponse>::failure(
          !entered ? entered.error() : done.error());
    if (done.value()) continue;
    if (entered.value())
      return facman::core::Result<RetirementResponse>::failure(failure(
          "self_maintenance_retirement_recovery_required",
          "a retirement step entered its provider/native boundary without a completion receipt",
          steps[index].generation.install_id));
    current = discover_activation_chain(request.coordinator_root);
    if (!current || !current.value().has_value() ||
        retirement_chain_digest(*current.value()) != retirement_chain_digest(chain))
      return facman::core::Result<RetirementResponse>::failure(failure(
          "self_maintenance_retirement_recovery_required",
          "activation chain changed before a retirement effect"));
    auto inspected = effects.inspect_retirement_generation(
        steps[index].generation, steps[index].active);
    if (!inspected)
      return facman::core::Result<RetirementResponse>::failure(failure(
          "self_maintenance_retirement_recovery_required",
          "provider or native identity is ambiguous before retirement",
          inspected.error().code + ": " + inspected.error().message));
    auto marked = ensure_immutable(retirement_step_path(directory, index,
                                                         "entered"),
        retirement_step_json(steps[index], index, "entered"));
    if (!marked)
      return facman::core::Result<RetirementResponse>::failure(marked.error());
    auto removed = effects.uninstall_generation(
        steps[index].generation, steps[index].active, coordinator_lock);
    if (!removed)
      return facman::core::Result<RetirementResponse>::failure(failure(
          "self_maintenance_retirement_recovery_required",
          "retirement crossed a provider/native boundary without a completion receipt",
          removed.error().code + ": " + removed.error().message));
    marked = ensure_immutable(retirement_step_path(directory, index,
                                                    "completed"),
        retirement_step_json(steps[index], index, "completed"));
    if (!marked)
      return facman::core::Result<RetirementResponse>::failure(marked.error());
    if (index + 1U == steps.size()) {
      auto final = ensure_immutable(directory / "99-completed.v1.json",
          retirement_completed_json(chain, steps.size()));
      if (!final)
        return facman::core::Result<RetirementResponse>::failure(final.error());
      return facman::core::Result<RetirementResponse>::success(
          {"completed", directory, steps});
    }
    // Exactly one non-terminal step is entered per invocation.  A later call
    // resumes the first durable incomplete step after revalidating the same
    // chain.
    return facman::core::Result<RetirementResponse>::success(
        {"step_completed", directory, steps});
  }
  auto final = ensure_immutable(directory / "99-completed.v1.json",
      retirement_completed_json(chain, steps.size()));
  if (!final)
    return facman::core::Result<RetirementResponse>::failure(final.error());
  return facman::core::Result<RetirementResponse>::success(
      {"completed", directory, steps});
}

facman::core::Result<ActiveState> adopt_legacy(
    const fs::path &coordinator_root, const Generation &legacy, bool apply) {
  if (!coordinator_root.is_absolute() || legacy.install_id != "facman.self" ||
      !digest(legacy.generation_id) || !digest(legacy.package_sha256) ||
      !revision(legacy.facman_source_revision) ||
      !revision(legacy.universal_setup_revision) ||
      generation_identity(generation_descriptor(legacy),
                          legacy.package_sha256) != legacy.generation_id ||
      !exact_generation_paths(legacy))
    return facman::core::Result<ActiveState>::failure(failure(
        "self_maintenance_legacy_invalid",
        "legacy generation identity is incomplete"));
  const std::string operation_id =
      "migration." + legacy.generation_id.substr(0, 32);
  Plan migration;
  migration.operation = "migration";
  migration.operation_id = operation_id;
  migration.source = legacy;
  migration.target = legacy;
  const std::string activation = activation_json(migration);
  const std::string activation_name =
      "activation." + operation_id + ".v1.json";
  ActiveState result{legacy, {}, activation_name, hash(activation)};
  if (!apply)
    return facman::core::Result<ActiveState>::success(std::move(result));

  auto authority = admit_coordinator(coordinator_root, legacy.acceptance_root,
                                     true);
  if (!authority)
    return facman::core::Result<ActiveState>::failure(authority.error());
  auto created = create_admitted_coordinator(authority.value());
  if (!created)
    return facman::core::Result<ActiveState>::failure(created.error());
  auto held = acquire(authority.take_value(), operation_id);
  if (!held) return facman::core::Result<ActiveState>::failure(held.error());
  const fs::path activation_directory = coordinator_root / "activations";
  std::error_code status;
  bool has_activation = false;
  if (fs::exists(activation_directory, status)) {
    if (status || !fs::is_directory(activation_directory, status) || status)
      return facman::core::Result<ActiveState>::failure(failure(
          "self_maintenance_activation_changed",
          "activation directory is not a plain directory"));
    auto iterator = fs::directory_iterator(activation_directory, status);
    if (status)
      return facman::core::Result<ActiveState>::failure(failure(
          "self_maintenance_activation_changed",
          "activation directory could not be enumerated", status.message()));
    has_activation = iterator != fs::directory_iterator();
  } else if (status) {
    return facman::core::Result<ActiveState>::failure(failure(
        "self_maintenance_activation_changed",
        "activation directory could not be observed", status.message()));
  }
  if (has_activation) {
    auto current = discover_active(coordinator_root);
    if (!current || !current.value().has_value() ||
        current.value()->activation_name != activation_name ||
        current.value()->activation_sha256 != result.activation_sha256 ||
        current.value()->active.generation_id != legacy.generation_id)
      return facman::core::Result<ActiveState>::failure(failure(
          "self_maintenance_activation_changed",
          "a different active generation already exists"));
    return facman::core::Result<ActiveState>::success(*current.value());
  }
  fs::create_directories(coordinator_root / "generations", status);
  if (!status) fs::create_directories(activation_directory, status);
  if (status)
    return facman::core::Result<ActiveState>::failure(failure(
        "self_maintenance_record_write_failed",
        "legacy generation directories could not be created",
        status.message()));
  auto recorded = ensure_immutable(
      coordinator_root / "generations" /
          ("generation." + legacy.generation_id + ".v1.json"),
      serialize_generation(legacy));
  if (!recorded)
    return facman::core::Result<ActiveState>::failure(recorded.error());
  recorded = ensure_immutable(activation_directory / activation_name,
                              activation);
  if (!recorded)
    return facman::core::Result<ActiveState>::failure(recorded.error());
  auto observed = discover_active(coordinator_root);
  if (!observed || !observed.value().has_value() ||
      observed.value()->activation_name != activation_name ||
      observed.value()->activation_sha256 != result.activation_sha256)
    return facman::core::Result<ActiveState>::failure(failure(
        "self_maintenance_activation_changed",
        "legacy generation genesis could not be verified"));
  return facman::core::Result<ActiveState>::success(*observed.value());
}

facman::core::Result<Plan> plan(const Request &request) {
  std::string identifier_detail;
  Semver current_version;
  if (!facman::base::validate_identifier(request.operation_id, identifier_detail))
    return facman::core::Result<Plan>::failure(failure(
        "self_maintenance_input_invalid", "operation id is invalid", identifier_detail));
  if (!request.coordinator_root.is_absolute() || !request.logical_root.is_absolute() ||
      !request.state_root.is_absolute() || !request.acceptance_root.is_absolute() ||
      request.active.install_root.empty() || request.active.generation_id.empty() ||
      !digest(request.active.generation_id) || !digest(request.active.package_sha256) ||
      !revision(request.active.facman_source_revision) ||
      !revision(request.active.universal_setup_revision) ||
      (request.active.install_id != "facman.self" &&
       request.active.install_id !=
            generation_install_id(request.active.generation_id)) ||
      !semver(request.active.product_version, current_version) ||
      !safe_version_component(request.active.product_version) ||
      !exact_generation_paths(request.active) ||
      !same_path(request.active.logical_root, request.logical_root) ||
      !same_path(request.active.state_root, request.state_root) ||
      !same_path(request.active.acceptance_root, request.acceptance_root) ||
      !digest(request.previous_activation_sha256) ||
      !facman::base::validate_identifier(request.previous_activation_name,
                                         identifier_detail))
    return facman::core::Result<Plan>::failure(failure(
        "self_maintenance_input_invalid", "active generation identity is incomplete"));

  Plan result;
  result.operation = operation_name(request.operation);
  result.operation_id = request.operation_id;
  result.source = request.active;
  result.previous_activation_name = request.previous_activation_name;
  result.previous_activation_sha256 = request.previous_activation_sha256;

  if (request.operation == Operation::rollback) {
    result.target = request.rollback_target;
    Semver rollback_version;
    if (result.target.generation_id.empty() || !digest(result.target.generation_id) ||
        result.target.generation_id == result.source.generation_id ||
        !digest(result.target.package_sha256) ||
        !revision(result.target.facman_source_revision) ||
        !revision(result.target.universal_setup_revision) ||
        !exact_generation_paths(result.target) ||
        same_path(result.target.install_root, result.source.install_root) ||
        (result.target.install_id != "facman.self" &&
         result.target.install_id !=
             generation_install_id(result.target.generation_id)) ||
        !same_path(result.target.logical_root, result.source.logical_root) ||
        !same_path(result.target.state_root, result.source.state_root) ||
        !same_path(result.target.acceptance_root,
                   result.source.acceptance_root) ||
        !semver(result.target.product_version, rollback_version) ||
        !safe_version_component(result.target.product_version))
      return facman::core::Result<Plan>::failure(failure(
          "self_maintenance_rollback_invalid", "rollback target is not a distinct retained generation"));
    result.provider_operation = "none";
    return facman::core::Result<Plan>::success(std::move(result));
  }

  const PackageDescriptor &descriptor = request.package_descriptor;
  if (descriptor.product_id != "facman" || descriptor.automatic_update ||
      descriptor.setup_protocol != "facman.self_maintenance.v1" ||
      descriptor.package_layout != "versioned_generation_with_maintenance_v1" ||
      !revision(descriptor.facman_source_revision) ||
      !revision(descriptor.universal_setup_revision) ||
      !digest(request.package_sha256) || !request.package.is_absolute() ||
      descriptor.generation_relative_path !=
          "generations/" + descriptor.product_version ||
      descriptor.gui_relative_path != "FacMan.exe" ||
      descriptor.cli_relative_path != "bin/facman.exe" ||
      descriptor.maintenance_relative_path !=
          "maintenance/FacManSetup.exe" ||
      !safe_relative(descriptor.generation_relative_path))
    return facman::core::Result<Plan>::failure(failure(
        "self_maintenance_package_incompatible", "package descriptor is incomplete or incompatible"));
  Semver candidate;
  if (!semver(descriptor.product_version, candidate) ||
      !safe_version_component(descriptor.product_version))
    return facman::core::Result<Plan>::failure(failure(
        "self_maintenance_version_invalid", "source or target is not semantic version"));
  const int order = compare(candidate, current_version);
  if ((request.operation == Operation::update && order <= 0) ||
      (request.operation == Operation::downgrade && order >= 0))
    return facman::core::Result<Plan>::failure(failure(
        "self_maintenance_version_direction_invalid",
        request.operation == Operation::update
            ? "update requires a newer target version"
            : "downgrade requires an older target version"));

  const std::string id = generation_identity(descriptor,
                                             request.package_sha256);
  if (request.rollback_target.generation_id == id) {
    auto retained = discover_active(request.coordinator_root);
    if (!retained || !retained.value().has_value() ||
        !retained.value()->previous.has_value() ||
        serialize_generation(retained.value()->active) !=
            serialize_generation(request.active) ||
        serialize_generation(*retained.value()->previous) !=
            serialize_generation(request.rollback_target) ||
        !exact_generation_record(request.coordinator_root,
                                 request.rollback_target) ||
        request.rollback_target.generation_id ==
            request.active.generation_id ||
        request.rollback_target.package_sha256 != request.package_sha256 ||
        !same_descriptor(descriptor,
                         generation_descriptor(request.rollback_target)))
      return facman::core::Result<Plan>::failure(failure(
          "self_maintenance_retained_target_invalid",
          "package target does not match the immediate retained predecessor"));
    result.target = request.rollback_target;
    result.package = request.package;
    result.package_sha256 = request.package_sha256;
    result.provider_operation = "install_local";
    return facman::core::Result<Plan>::success(std::move(result));
  }
  const fs::path target_root = generation_install_root(request.logical_root, id);
  const fs::path generation = target_root /
      facman::platform::path_from_utf8(descriptor.generation_relative_path);
  result.target.generation_id = id;
  result.target.product_version = descriptor.product_version;
  result.target.package_sha256 = request.package_sha256;
  result.target.facman_source_revision = descriptor.facman_source_revision;
  result.target.universal_setup_revision = descriptor.universal_setup_revision;
  result.target.install_id = generation_install_id(id);
  result.target.install_root = target_root;
  result.target.logical_root = request.logical_root.lexically_normal();
  result.target.state_root = request.state_root.lexically_normal();
  result.target.acceptance_root = request.acceptance_root.lexically_normal();
  result.target.gui = generation /
      facman::platform::path_from_utf8(descriptor.gui_relative_path);
  result.target.maintenance_launcher = target_root /
      facman::platform::path_from_utf8(descriptor.maintenance_relative_path);
  if (same_path(result.source.install_root, result.target.install_root))
    return facman::core::Result<Plan>::failure(failure(
        "self_maintenance_package_incompatible",
        "candidate root must be distinct from the active generation root"));
  result.package = request.package;
  result.package_sha256 = request.package_sha256;
  result.provider_operation = "install_local";
  return facman::core::Result<Plan>::success(std::move(result));
}

facman::core::Result<Response> execute(const Request &request, Effects &effects) {
  auto prepared = plan(request);
  if (!prepared) return facman::core::Result<Response>::failure(prepared.error());
  Plan transition = prepared.take_value();
  auto authority = admit_coordinator(request.coordinator_root,
                                     request.acceptance_root,
                                     true);
  if (!authority)
    return facman::core::Result<Response>::failure(authority.error());
  CandidateState reviewed_candidate = CandidateState::absent;
  if (request.operation != Operation::rollback) {
    auto source = stable_digest(request.package);
    if (!source || source.value() != request.package_sha256)
      return facman::core::Result<Response>::failure(failure(
          "self_maintenance_package_changed",
          "maintenance package does not match its reviewed identity",
          source ? source.value() : source.error().detail));
    reviewed_candidate = effects.inspect_candidate(transition);
    if (reviewed_candidate == CandidateState::foreign ||
        reviewed_candidate == CandidateState::unreadable)
      return facman::core::Result<Response>::failure(failure(
          "self_maintenance_candidate_unsafe",
          "candidate root is foreign or unreadable"));
    if (reviewed_candidate == CandidateState::absent) {
      const auto reviewed_provider = effects.review_install_local(transition);
      if (!reviewed_provider.ok)
        return facman::core::Result<Response>::failure(effect_error(
            "self_maintenance_plan_failed",
            "candidate installation plan was refused", reviewed_provider).error());
    }
  }

  if (!request.apply)
    return facman::core::Result<Response>::success(
        {transition.operation, "plan", transition.operation_id,
         transition.source, {}, {}});

  // Plan review must remain effect-free.  A non-legacy transition needs the
  // immutable active chain already present; legacy adoption owns the only
  // coordinator-creation path and revalidates its held authority there.
  if (!authority.value().coordinator_exists)
    return facman::core::Result<Response>::failure(failure(
        "self_maintenance_lock_unsafe",
        "coordinator root remains absent after plan admission"));
  auto held = acquire(authority.take_value(), request.operation_id);
  if (!held) return facman::core::Result<Response>::failure(held.error());
  const std::string activation = activation_json(transition);
  const fs::path activation_record = request.coordinator_root / "activations" /
      ("activation." + transition.operation_id + ".v1.json");
  std::error_code activation_status;
  const bool activation_exists = fs::exists(activation_record,
                                             activation_status);
  if (activation_status)
    return facman::core::Result<Response>::failure(failure(
        "self_maintenance_activation_changed",
        "activation record could not be observed", activation_status.message()));
  if (activation_exists) {
    if (!fs::is_regular_file(activation_record, activation_status) ||
        activation_status)
      return facman::core::Result<Response>::failure(failure(
          "self_maintenance_activation_changed",
          "activation record is not a regular file"));
    auto existing = ensure_immutable(activation_record, activation);
    if (!existing)
      return facman::core::Result<Response>::failure(existing.error());
    auto completed_chain = validate_activation_head(
        request.coordinator_root, activation_record.filename().string(),
        hash(activation));
    if (!completed_chain ||
        completed_chain.value().target_generation_id !=
            transition.target.generation_id ||
        !exact_generation_record(request.coordinator_root,
                                 transition.source) ||
        !exact_generation_record(request.coordinator_root,
                                 transition.target))
      return facman::core::Result<Response>::failure(failure(
          "self_maintenance_activation_changed",
          "completed activation no longer matches the immutable chain"));
    auto completed_records = validate_operation_records(request, transition);
    if (!completed_records)
      return facman::core::Result<Response>::failure(completed_records.error());
    const auto completed_inspection = effects.inspect_installed(transition);
    if (!completed_inspection.ok ||
        !digest(completed_inspection.receipt_sha256))
      return facman::core::Result<Response>::failure(effect_error(
          "self_maintenance_inspect_failed",
          "completed target installed state is not exact",
          completed_inspection).error());
    const auto completed_verification = effects.verify_installed(transition);
    if (!completed_verification.ok ||
        !digest(completed_verification.receipt_sha256))
      return facman::core::Result<Response>::failure(effect_error(
          "self_maintenance_verify_failed",
          "completed target verification failed",
          completed_verification).error());
    if (effects.inspect_shortcut(transition) != ShellState::new_exact ||
        effects.inspect_registration(transition) != ShellState::new_exact)
      return facman::core::Result<Response>::failure(failure(
          "self_maintenance_activation_changed",
          "completed activation shell state is no longer exact"));
    auto final_phase = record_phase(request, transition,
                                    "70-activation-recorded", hash(activation));
    if (!final_phase)
      return facman::core::Result<Response>::failure(final_phase.error());
    const fs::path existing_generation = request.coordinator_root /
        "generations" /
        ("generation." + transition.target.generation_id + ".v1.json");
    return facman::core::Result<Response>::success(
        {transition.operation, "completed", transition.operation_id,
         transition.target, existing_generation, activation_record});
  }
  auto chain = validate_activation_head(
      request.coordinator_root, request.previous_activation_name,
      request.previous_activation_sha256);
  if (!chain) return facman::core::Result<Response>::failure(chain.error());
  if (chain.value().target_generation_id != transition.source.generation_id)
    return facman::core::Result<Response>::failure(failure(
        "self_maintenance_activation_changed",
        "reviewed activation does not identify the requested active generation"));
  const fs::path source_record = request.coordinator_root / "generations" /
      ("generation." + transition.source.generation_id + ".v1.json");
  auto source_generation = read_exact(source_record);
  if (!source_generation ||
      source_generation.value() != serialize_generation(transition.source))
    return facman::core::Result<Response>::failure(failure(
        "self_maintenance_source_changed",
        "active generation does not match its immutable generation record"));
  auto recorded = record_phase(request, transition, "00-intent");
  if (!recorded) return facman::core::Result<Response>::failure(recorded.error());
  recorded = validate_operation_records(request, transition);
  if (!recorded) return facman::core::Result<Response>::failure(recorded.error());

  if (request.operation != Operation::rollback) {
    CandidateState candidate = reviewed_candidate;
    if (candidate == CandidateState::foreign || candidate == CandidateState::unreadable)
      return facman::core::Result<Response>::failure(failure(
          "self_maintenance_candidate_unsafe", "candidate root is foreign or unreadable"));
    if (candidate == CandidateState::absent) {
      const bool provider_entered = phase_exists(request, "10-provider-entered");
      if (provider_entered) {
        recorded = record_phase(request, transition, "10-provider-entered");
        if (!recorded)
          return facman::core::Result<Response>::failure(recorded.error());
        return facman::core::Result<Response>::failure(failure(
            "self_maintenance_provider_recovery_required",
            "provider entry was recorded without an exact installed candidate"));
      }
      const auto prepared_provider = effects.prepare_install_local(transition);
      if (!prepared_provider.ok)
        return facman::core::Result<Response>::failure(effect_error(
            "self_maintenance_source_retention_failed",
            "candidate installation inputs could not be retained",
            prepared_provider).error());
      recorded = record_phase(request, transition, "10-provider-entered");
      if (!recorded) return facman::core::Result<Response>::failure(recorded.error());
      const auto installed = effects.install_local(transition);
      if (!installed.ok)
        return facman::core::Result<Response>::failure(effect_error(
            "self_maintenance_install_failed", "candidate installation failed",
            installed).error());
      if (!digest(installed.receipt_sha256))
        return facman::core::Result<Response>::failure(failure(
            "self_maintenance_provider_receipt_invalid",
            "candidate installation returned no exact receipt identity"));
      recorded = record_phase(request, transition, "20-provider-receipt",
                              installed.receipt_sha256);
      if (!recorded) return facman::core::Result<Response>::failure(recorded.error());
      candidate = effects.inspect_candidate(transition);
    } else if (phase_exists(request, "10-provider-entered")) {
      recorded = record_phase(request, transition, "10-provider-entered");
      if (!recorded)
        return facman::core::Result<Response>::failure(recorded.error());
    }
    if (candidate != CandidateState::exact)
      return facman::core::Result<Response>::failure(failure(
          "self_maintenance_candidate_unverified", "provider result does not bind the candidate root"));
    const auto inspected = effects.inspect_installed(transition);
    if (!inspected.ok || !digest(inspected.receipt_sha256))
      return facman::core::Result<Response>::failure(effect_error(
          "self_maintenance_inspect_failed", "candidate installed state is not exact",
          inspected).error());
    const auto verified = effects.verify_installed(transition);
    if (!verified.ok || !digest(verified.receipt_sha256))
      return facman::core::Result<Response>::failure(effect_error(
          "self_maintenance_verify_failed", "candidate verification failed",
          verified).error());
    recorded = record_phase(request, transition, "30-candidate-verified",
                            hash(inspected.receipt_sha256 + "\n" +
                                 verified.receipt_sha256));
    if (!recorded) return facman::core::Result<Response>::failure(recorded.error());
  }

  const fs::path generation_record = request.coordinator_root / "generations" /
      ("generation." + transition.target.generation_id + ".v1.json");
  if (request.operation == Operation::rollback) {
    auto retained = read_exact(generation_record);
    if (!retained || retained.value() != serialize_generation(transition.target))
      return facman::core::Result<Response>::failure(failure(
          "self_maintenance_rollback_invalid",
          "rollback target does not match an immutable retained generation"));
    recorded = facman::core::Result<void>::success();
    const auto inspected = effects.inspect_installed(transition);
    if (!inspected.ok || !digest(inspected.receipt_sha256))
      return facman::core::Result<Response>::failure(effect_error(
          "self_maintenance_inspect_failed",
          "rollback target installed state is not exact", inspected).error());
    const auto verified = effects.verify_installed(transition);
    if (!verified.ok || !digest(verified.receipt_sha256))
      return facman::core::Result<Response>::failure(effect_error(
          "self_maintenance_verify_failed",
          "rollback target verification failed", verified).error());
  } else {
    recorded = ensure_immutable(generation_record,
                                serialize_generation(transition.target));
  }
  if (!recorded) return facman::core::Result<Response>::failure(recorded.error());
  recorded = record_phase(request, transition, "40-generation-recorded");
  if (!recorded) return facman::core::Result<Response>::failure(recorded.error());

  // Provider work may be long-running. Revalidate all authority records at the
  // native-effect edge instead of treating the initial observation as a lock
  // against a process that does not honor the coordinator protocol.
  chain = validate_activation_head(
      request.coordinator_root, request.previous_activation_name,
      request.previous_activation_sha256);
  if (!chain ||
      chain.value().target_generation_id != transition.source.generation_id ||
      !exact_generation_record(request.coordinator_root, transition.source) ||
      !exact_generation_record(request.coordinator_root, transition.target))
    return facman::core::Result<Response>::failure(failure(
        "self_maintenance_identity_changed",
        "generation or activation identity changed before shell cutover"));
  if (request.operation != Operation::rollback &&
      effects.inspect_candidate(transition) != CandidateState::exact)
    return facman::core::Result<Response>::failure(failure(
        "self_maintenance_candidate_unverified",
        "candidate identity changed before shell cutover"));
  if (request.operation == Operation::rollback) {
    const auto inspected = effects.inspect_installed(transition);
    const auto verified = effects.verify_installed(transition);
    if (!inspected.ok || !digest(inspected.receipt_sha256) ||
        !verified.ok || !digest(verified.receipt_sha256))
      return facman::core::Result<Response>::failure(failure(
          "self_maintenance_rollback_invalid",
          "rollback target identity changed before shell cutover"));
  }

  ShellState shortcut = effects.inspect_shortcut(transition);
  if (shortcut == ShellState::foreign || shortcut == ShellState::unreadable ||
      shortcut == ShellState::absent)
    return facman::core::Result<Response>::failure(failure(
        "self_maintenance_shell_unsafe", "Start Menu shortcut is not the exact old or new FacMan object"));
  if (shortcut == ShellState::old_exact) {
    const auto changed = effects.cutover_shortcut(transition);
    if (!changed.ok)
      return facman::core::Result<Response>::failure(effect_error(
          "self_maintenance_shortcut_failed", "Start Menu cutover failed", changed).error());
    if (effects.inspect_shortcut(transition) != ShellState::new_exact)
      return facman::core::Result<Response>::failure(failure(
          "self_maintenance_shell_unsafe", "Start Menu cutover could not be verified"));
  }
  recorded = record_phase(request, transition, "50-shortcut-cutover");
  if (!recorded) return facman::core::Result<Response>::failure(recorded.error());

  ShellState registration = effects.inspect_registration(transition);
  if (registration == ShellState::foreign || registration == ShellState::unreadable ||
      registration == ShellState::absent)
    return facman::core::Result<Response>::failure(failure(
        "self_maintenance_shell_unsafe", "uninstall registration is not the exact old or new FacMan object"));
  if (registration == ShellState::old_exact) {
    const auto changed = effects.cutover_registration(transition);
    if (!changed.ok)
      return facman::core::Result<Response>::failure(effect_error(
          "self_maintenance_registration_failed", "registration cutover failed", changed).error());
    if (effects.inspect_registration(transition) != ShellState::new_exact)
      return facman::core::Result<Response>::failure(failure(
          "self_maintenance_shell_unsafe", "registration cutover could not be verified"));
  }
  recorded = record_phase(request, transition, "60-registration-cutover");
  if (!recorded) return facman::core::Result<Response>::failure(recorded.error());

  chain = validate_activation_head(
      request.coordinator_root, request.previous_activation_name,
      request.previous_activation_sha256);
  if (!chain ||
      chain.value().target_generation_id != transition.source.generation_id ||
      !exact_generation_record(request.coordinator_root, transition.source) ||
      !exact_generation_record(request.coordinator_root, transition.target))
    return facman::core::Result<Response>::failure(failure(
        "self_maintenance_identity_changed",
        "generation or activation identity changed before activation commit"));
  recorded = ensure_immutable(activation_record, activation);
  if (!recorded) return facman::core::Result<Response>::failure(recorded.error());
  recorded = record_phase(request, transition, "70-activation-recorded",
                          hash(activation));
  if (!recorded) return facman::core::Result<Response>::failure(recorded.error());
  auto committed_chain = validate_activation_head(
      request.coordinator_root, activation_record.filename().string(),
      hash(activation));
  if (!committed_chain)
    return facman::core::Result<Response>::failure(committed_chain.error());
  if (committed_chain.value().target_generation_id !=
      transition.target.generation_id)
    return facman::core::Result<Response>::failure(failure(
        "self_maintenance_activation_changed",
        "committed activation is not the unique current generation head"));
  return facman::core::Result<Response>::success(
      {transition.operation, "completed", transition.operation_id,
       transition.target, generation_record, activation_record});
}

namespace testing {

void set_epoch_record_pinned_hook(EpochRecordPinnedHook hook) noexcept {
  epoch_record_pinned_hook_for_testing = hook;
}

void set_epoch_handoff_operation_pinned_hook(
    EpochHandoffOperationPinnedHook hook) noexcept {
  epoch_handoff_operation_pinned_hook_for_testing = hook;
}

} // namespace testing

} // namespace facman::self_maintenance
