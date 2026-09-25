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

facman::core::Result<void> require_flat_retirement_epoch_absence(
    const Lock &lock) {
  std::string detail;
  if (!lock.admission.revalidate(detail))
    return facman::core::Result<void>::failure(failure(
        "self_maintenance_lock_unsafe",
        "coordinator authority changed during flat retirement", detail));
  const fs::path epochs = lock.admission.root / "epochs";
  const auto descendant =
      lock.admission.coordinator.validate_descendant(epochs, true);
  facman::platform::PathIdentity identity;
  const auto observed = facman::platform::inspect_path_no_follow(epochs, identity);
  if (!descendant.ok() || !observed.ok())
    return facman::core::Result<void>::failure(failure(
        "self_maintenance_epoch_recovery_required",
        "lifecycle epoch namespace could not be excluded before flat retirement",
        !descendant.ok() ? descendant.detail : observed.detail));
  if (identity.exists)
    return facman::core::Result<void>::failure(failure(
        "self_maintenance_epoch_recovery_required",
        "lifecycle epoch namespace blocks flat retirement"));
  const fs::path epoch_retirements =
      lock.admission.root / "epoch-retirements";
  const auto retirement_descendant =
      lock.admission.coordinator.validate_descendant(epoch_retirements, true);
  facman::platform::PathIdentity retirement_identity;
  const auto retirement_observed = facman::platform::inspect_path_no_follow(
      epoch_retirements, retirement_identity);
  if (!retirement_descendant.ok() || !retirement_observed.ok() ||
      retirement_identity.exists)
    return facman::core::Result<void>::failure(failure(
        "self_maintenance_epoch_recovery_required",
        "epoch retirement namespace blocks flat retirement"));
  const fs::path handoff = lock.admission.root / "authority-handoff.v1.json";
  const auto handoff_descendant =
      lock.admission.coordinator.validate_descendant(handoff, true);
  facman::platform::PathIdentity handoff_identity;
  const auto handoff_observed = facman::platform::inspect_path_no_follow(
      handoff, handoff_identity);
  if (!handoff_descendant.ok() || !handoff_observed.ok() ||
      handoff_identity.exists)
    return facman::core::Result<void>::failure(failure(
        "self_maintenance_epoch_recovery_required",
        "compatibility authority handoff blocks flat maintenance"));
  const fs::path bootstrap = lock.admission.root / "authority-bootstrap.v1";
  const auto bootstrap_descendant =
      lock.admission.coordinator.validate_descendant(bootstrap, true);
  facman::platform::PathIdentity bootstrap_identity;
  const auto bootstrap_observed = facman::platform::inspect_path_no_follow(
      bootstrap, bootstrap_identity);
  if (!bootstrap_descendant.ok() || !bootstrap_observed.ok() ||
      bootstrap_identity.exists)
    return facman::core::Result<void>::failure(failure(
        "self_maintenance_epoch_recovery_required",
        "compatibility bootstrap journal blocks flat maintenance"));
  if (!lock.admission.revalidate(detail))
    return facman::core::Result<void>::failure(failure(
        "self_maintenance_lock_unsafe",
        "coordinator authority changed after epoch absence inspection", detail));
  return facman::core::Result<void>::success();
}

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
      phase == "30-candidate-verified" || phase == "70-activation-recorded" ||
      phase == "80-shortcut-backup-retired";
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
      "70-activation-recorded", "80-shortcut-backup-retired"};
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
  const Generation &active = chain.generations.back();
  for (const auto &generation : chain.generations) {
    if (generation.install_id == active.install_id &&
        same_path(generation.install_root, active.install_root)) continue;
    const auto duplicate = std::find_if(result.begin(), result.end(),
        [&](const RetirementStep &step) {
          return step.generation.install_id == generation.install_id &&
              same_path(step.generation.install_root, generation.install_root);
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
  bool unfinished_predecessor = false;
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
    if (unfinished_predecessor && (entered.value() || done.value()))
      return facman::core::Result<void>::failure(failure(
          "self_maintenance_retirement_recovery_required",
          "retirement steps are not in durable execution order"));
    if (!done.value()) unfinished_predecessor = true;
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

// Relinquishing the flat chain's authority does not mean its provider files or
// native objects were uninstalled. This record has a distinct schema and path
// from the destructive retirement receipt, while binding the same exact head.
std::string compatibility_authority_handoff_bytes(
    const ActivationChain &chain) {
  json::ObjectBuilder object;
  object.add_string("schema", "facman.self_compatibility_authority_handoff.v1");
  object.add_string("product_id", "facman");
  object.add_string("head_name", chain.activation_name);
  object.add_string("head_sha256", chain.activation_sha256);
  object.add_string("chain_digest", retirement_chain_digest(chain));
  object.add_string("source_generation_id", chain.generations.back().generation_id);
  object.add_string("source_package_sha256", chain.generations.back().package_sha256);
  return object.serialize() + "\n";
}

std::string compatibility_bootstrap_entered_bytes(
    const ActivationChain &chain, const LifecycleEpoch &epoch,
    const Generation &target, bool shell_integration) {
  json::ObjectBuilder object;
  object.add_string("schema", "facman.self_compatibility_bootstrap_entered.v1");
  object.add_string("source_head_name", chain.activation_name);
  object.add_string("source_head_sha256", chain.activation_sha256);
  object.add_string("source_generation_id", chain.generations.back().generation_id);
  object.add_string("source_package_sha256", chain.generations.back().package_sha256);
  object.add_string("epoch_id", epoch.epoch_id);
  object.add_string("target_install_id", target.install_id);
  object.add_string("target_install_root", facman::platform::path_to_utf8(target.install_root));
  object.add_bool("shell_integration", shell_integration);
  return object.serialize() + "\n";
}

std::string compatibility_bootstrap_phase_bytes(
    const char *phase, const std::string &entered_sha256,
    const std::string &receipt_sha256) {
  json::ObjectBuilder object;
  object.add_string("schema", "facman.self_compatibility_bootstrap_phase.v1");
  object.add_string("phase", phase);
  object.add_string("entered_sha256", entered_sha256);
  object.add_string("receipt_sha256", receipt_sha256);
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

std::string epoch_generation_install_id(const std::string &epoch_id,
                                        const std::string &generation_id) {
  // Universal Setup derives audit and ownership identifiers from install_id,
  // so the source identifier must leave room for those durable prefixes and
  // the transaction id.  The domain-separated digest binds the complete epoch
  // and generation without truncating either identity.
  return "facman.self.eg." +
      hash("facman.self.epoch-generation-install.v1\n" + epoch_id + "\n" +
           generation_id + "\n");
}

bool exact_epoch_generation_paths(const LifecycleEpoch &epoch,
                                  const Generation &generation) {
  const fs::path root = epoch_generation_install_root(
      epoch.logical_root, epoch.epoch_id, generation.generation_id);
  return generation.install_id == epoch_generation_install_id(
          epoch.epoch_id, generation.generation_id) &&
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

struct PendingEpochTransitionState {
  Generation target;
  fs::path generation_staging_name;
  fs::path activation_name;
  fs::path activation_staging_name;
  std::string activation_bytes;
};

struct HeldPublicationRecord {
  fs::path name;
  std::string bytes;
  facman::platform::StableInputFile file;
};

struct CompletedEpochShellCutover {
  std::string operation_id;
  std::string activation_name;
  std::string activation_sha256;
  std::string source_activation_name;
  std::string source_activation_sha256;
  std::string source_generation_id;
  std::string generation_id;
  bool reactivation = false;
  std::vector<fs::path> operation_names;
  std::vector<fs::path> record_names;
  facman::platform::StableDirectoryObject maintenance;
  facman::platform::StableDirectoryObject operation;
  std::vector<HeldPublicationRecord> records;
};

struct EpochReactivationIntent {
  std::string epoch_id;
  std::string epoch_manifest_sha256;
  std::string operation;
  std::string operation_id;
  std::string source_generation_id;
  std::string source_activation_name;
  std::string source_activation_sha256;
  std::string target_generation_id;
  std::string target_generation_sha256;
  std::string target_package_sha256;
  std::string target_installed_identity_sha256;
  std::string target_activation_name;
  std::string target_activation_sha256;
  bool shell_integration = true;
};

std::string epoch_reactivation_intent_bytes(const EpochReactivationIntent &intent) {
  json::ObjectBuilder record;
  record.add_string("schema", "facman.self_epoch_reactivation_intent.v1");
  record.add_string("product_id", "facman");
  record.add_string("epoch_id", intent.epoch_id);
  record.add_string("epoch_manifest_sha256", intent.epoch_manifest_sha256);
  record.add_string("operation", intent.operation);
  record.add_string("operation_id", intent.operation_id);
  record.add_string("source_generation_id", intent.source_generation_id);
  record.add_string("source_activation_name", intent.source_activation_name);
  record.add_string("source_activation_sha256", intent.source_activation_sha256);
  record.add_string("target_generation_id", intent.target_generation_id);
  record.add_string("target_generation_sha256", intent.target_generation_sha256);
  record.add_string("target_package_sha256", intent.target_package_sha256);
  record.add_string("target_installed_identity_sha256",
                    intent.target_installed_identity_sha256);
  record.add_string("target_activation_name", intent.target_activation_name);
  record.add_string("target_activation_sha256", intent.target_activation_sha256);
  record.add_bool("shell_integration", intent.shell_integration);
  return record.serialize() + "\n";
}

facman::core::Result<EpochReactivationIntent> parse_epoch_reactivation_intent(
    const std::string &bytes, const LifecycleEpoch &epoch,
    const fs::path &operation_name) {
  auto document = json::parse(bytes);
  if (!document || !exact_keys(document.value(), {"schema", "product_id", "epoch_id",
          "epoch_manifest_sha256", "operation", "operation_id",
          "source_generation_id", "source_activation_name", "source_activation_sha256",
          "target_generation_id", "target_generation_sha256", "target_package_sha256",
          "target_installed_identity_sha256",
          "target_activation_name", "target_activation_sha256", "shell_integration"}))
    return facman::core::Result<EpochReactivationIntent>::failure(epoch_recovery(
        "epoch reactivation intent has a foreign schema"));
  const json::Value *shell = document.value().find("shell_integration");
  auto shell_value = shell && shell->is_bool() ? shell->bool_value()
      : facman::core::Result<bool>::failure(epoch_recovery(
          "epoch reactivation shell choice is invalid"));
  if (!shell_value) return facman::core::Result<EpochReactivationIntent>::failure(
      shell_value.error());
  EpochReactivationIntent intent;
  intent.epoch_id = string_field(document.value(), "epoch_id");
  intent.epoch_manifest_sha256 = string_field(document.value(), "epoch_manifest_sha256");
  intent.operation = string_field(document.value(), "operation");
  intent.operation_id = string_field(document.value(), "operation_id");
  intent.source_generation_id = string_field(document.value(), "source_generation_id");
  intent.source_activation_name = string_field(document.value(), "source_activation_name");
  intent.source_activation_sha256 = string_field(document.value(), "source_activation_sha256");
  intent.target_generation_id = string_field(document.value(), "target_generation_id");
  intent.target_generation_sha256 = string_field(document.value(), "target_generation_sha256");
  intent.target_package_sha256 = string_field(document.value(), "target_package_sha256");
  intent.target_installed_identity_sha256 =
      string_field(document.value(), "target_installed_identity_sha256");
  intent.target_activation_name = string_field(document.value(), "target_activation_name");
  intent.target_activation_sha256 = string_field(document.value(), "target_activation_sha256");
  intent.shell_integration = shell_value.value();
  std::string identifier_detail;
  if (string_field(document.value(), "schema") !=
          "facman.self_epoch_reactivation_intent.v1" ||
      string_field(document.value(), "product_id") != "facman" ||
      intent.epoch_id != epoch.epoch_id ||
      intent.epoch_manifest_sha256 != epoch.manifest_sha256 ||
      intent.operation_id != operation_name.string() ||
      !facman::base::validate_identifier(intent.operation_id, identifier_detail) ||
      (intent.operation != "update" && intent.operation != "downgrade" &&
       intent.operation != "rollback") ||
      !digest(intent.source_generation_id) || !digest(intent.source_activation_sha256) ||
      !digest(intent.target_generation_id) || !digest(intent.target_generation_sha256) ||
      !digest(intent.target_package_sha256) || !digest(intent.target_activation_sha256) ||
      !digest(intent.target_installed_identity_sha256) ||
      intent.source_activation_name.empty() ||
      fs::path(intent.source_activation_name) !=
          fs::path(intent.source_activation_name).filename() ||
      intent.target_activation_name !=
          "activation." + intent.operation_id + ".v2.json" ||
      bytes != epoch_reactivation_intent_bytes(intent))
    return facman::core::Result<EpochReactivationIntent>::failure(epoch_recovery(
        "epoch reactivation intent does not bind an exact lifecycle operation"));
  return facman::core::Result<EpochReactivationIntent>::success(std::move(intent));
}

std::string epoch_reactivation_cutover_bytes(
    const EpochReactivationIntent &intent, const std::string &phase,
    const std::string &previous_record_sha256, const std::string &effect) {
  const std::string ownership_receipt = hash(
      "facman.self_epoch_reactivation_ownership.v1\n" + intent.epoch_id + "\n" +
      intent.operation_id + "\n" + intent.source_activation_sha256 + "\n" +
      intent.target_activation_sha256 + "\n" + effect + "\nnew_exact\n");
  json::ObjectBuilder record;
  record.add_string("schema", "facman.self_epoch_reactivation_cutover.v1");
  record.add_string("product_id", "facman");
  record.add_string("phase", phase);
  record.add_string("epoch_id", intent.epoch_id);
  record.add_string("operation_id", intent.operation_id);
  record.add_string("intent_sha256", hash(epoch_reactivation_intent_bytes(intent)));
  record.add_string("previous_record_sha256", previous_record_sha256);
  record.add_string("effect", effect);
  record.add_string("target_generation_id", intent.target_generation_id);
  record.add_string("target_activation_name", intent.target_activation_name);
  record.add_string("target_activation_sha256", intent.target_activation_sha256);
  record.add_string("ownership", "new_exact");
  record.add_string("ownership_receipt_sha256", ownership_receipt);
  return record.serialize() + "\n";
}

bool epoch_reactivation_record_names(const std::vector<fs::path> &names) {
  const std::vector<fs::path> finals = {
      "00-reactivation-intent.v1.json", "10-shortcut-cutover.v1.json",
      "20-registration-cutover.v1.json"};
  const std::vector<fs::path> staging = {
      "00-reactivation-intent.staging.v1.json",
      "10-shortcut-cutover.staging.v1.json",
      "20-registration-cutover.staging.v1.json"};
  if (names.empty() || names.size() > finals.size()) return false;
  for (std::size_t index = 0; index < names.size(); ++index)
    if (names[index] != finals[index] &&
        !(index + 1U == names.size() && names[index] == staging[index]))
      return false;
  return true;
}

// Defined with the phase-70/80 record parsers below.  Ordinary discovery may
// pass a maintenance directory only after the complete, immutable shell
// closure is present; all intermediate tails stay targeted-recovery-only.
bool completed_epoch_shell_cutover(const LifecycleEpoch &epoch,
    const PinnedLifecycleEpochScope &scope,
    const fs::path &operation_name,
    CompletedEpochShellCutover &completed);
bool revalidate_completed_epoch_shell_cutover(
    CompletedEpochShellCutover &completed,
    const PinnedLifecycleEpochScope &scope);

facman::core::Result<std::optional<ActiveState>> discover_epoch_genesis_state(
    const LifecycleEpoch &epoch, const PinnedLifecycleEpochScope &scope,
    const Generation *expected = nullptr, bool allow_incomplete = false,
    const std::string *allowed_maintenance_operation = nullptr,
    const PendingEpochTransitionState *pending_transition = nullptr,
    std::vector<Generation> *validated_history = nullptr) {
  std::vector<CompletedEpochShellCutover> completed_shell_cutovers;
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
        facman::platform::StableDirectoryObject maintenance;
        std::vector<fs::path> operation_names;
        if (!scope.epoch.open_child_directory_no_follow("maintenance", maintenance).ok() ||
            !maintenance.list_child_names_bounded(kMaximumEpochActivationRecords + 1U,
                                                   operation_names).ok())
          return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
              "epoch maintenance recovery history is oversized or unsafe"));
        const std::vector<fs::path> finals = {
            "00-handoff-ready.v3.json", "10-provider-apply-bound.v2.json",
            "20-provider-apply-entered.v2.json", "30-provider-outcome.v2.json",
            "40-provider-verified.v2.json", "50-generation-published.v2.json",
            "60-activation-published.v2.json", "70-shortcut-cutover.v2.json",
            "80-registration-cutover.v2.json"};
        for (const fs::path &operation_name : operation_names) {
          if (operation_name != fs::path(*allowed_maintenance_operation)) {
            CompletedEpochShellCutover completed;
            if (!completed_epoch_shell_cutover(epoch, scope, operation_name, completed))
              return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
                  "epoch maintenance history contains an incomplete or foreign sibling"));
            completed_shell_cutovers.push_back(std::move(completed));
            continue;
          }
          facman::platform::StableDirectoryObject operation;
          std::vector<fs::path> records;
          if (!maintenance.open_child_directory_no_follow(operation_name, operation).ok() ||
              !operation.list_child_names_bounded(10U, records).ok() || records.size() > 9U)
            return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
                "epoch maintenance recovery state is not the exact targeted handoff"));
          if (!records.empty() && (records.front() ==
                  fs::path("00-reactivation-intent.v1.json") ||
              records.front() ==
                  fs::path("00-reactivation-intent.staging.v1.json"))) {
            if (pending_transition == nullptr ||
                !epoch_reactivation_record_names(records))
              return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
                  "targeted epoch reactivation has foreign or out-of-order records"));
            continue;
          }
          for (std::size_t i = 0; i < records.size(); ++i) {
            const std::string final_text = finals[i].string();
            const std::size_t version = final_text.rfind(".v");
            const fs::path staging = final_text.substr(0, version) + ".staging" +
                final_text.substr(version);
            if (records[i] != finals[i] &&
                !(i + 1U == records.size() && records[i] == staging))
              return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
                  "epoch maintenance recovery state is not the exact targeted handoff"));
          }
          if (records == finals) {
            CompletedEpochShellCutover completed;
            if (!completed_epoch_shell_cutover(epoch, scope, operation_name, completed))
              return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
                  "completed targeted epoch shell cutover is not exact"));
            completed_shell_cutovers.push_back(std::move(completed));
          }
        }
        continue;
      }
      if (child == "maintenance" && allowed_maintenance_operation == nullptr) {
        facman::platform::StableDirectoryObject maintenance;
        std::vector<fs::path> operation_names;
        if (!scope.epoch.open_child_directory_no_follow("maintenance", maintenance).ok() ||
            !maintenance.list_child_names_bounded(kMaximumEpochActivationRecords + 1U,
                                                   operation_names).ok())
          return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
              "epoch maintenance history is oversized or unsafe"));
        std::size_t empty_operations = 0U;
        for (const fs::path &operation_name : operation_names) {
          facman::platform::StableDirectoryObject operation;
          std::vector<fs::path> records;
          if (!maintenance.open_child_directory_no_follow(operation_name, operation).ok() ||
              !operation.list_child_names_bounded(10U, records).ok())
            return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
                "epoch maintenance history contains an unsafe operation"));
          if (records.empty()) {
            if (++empty_operations != 1U)
              return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
                  "epoch maintenance history has more than one pre-handoff operation"));
            continue;
          }
          CompletedEpochShellCutover completed;
          if (!completed_epoch_shell_cutover(epoch, scope, operation_name, completed))
            return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
                "epoch maintenance history contains an incomplete or foreign operation"));
          completed_shell_cutovers.push_back(std::move(completed));
        }
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
  const std::vector<fs::path> raw_generation_names = generation_names;
  const std::vector<fs::path> raw_activation_names = activation_names;
  bool pending_generation_staged = false;
  bool pending_generation_final = false;
  bool pending_activation_staged = false;
  bool pending_activation_final = false;
  if (pending_transition != nullptr) {
    const fs::path generation_final = epoch_generation_name(
        pending_transition->target.generation_id);
    pending_generation_staged = std::find(generation_names.begin(), generation_names.end(),
        pending_transition->generation_staging_name) != generation_names.end();
    pending_generation_final = std::find(generation_names.begin(), generation_names.end(),
        generation_final) != generation_names.end();
    pending_activation_staged = std::find(activation_names.begin(), activation_names.end(),
        pending_transition->activation_staging_name) != activation_names.end();
    pending_activation_final = std::find(activation_names.begin(), activation_names.end(),
        pending_transition->activation_name) != activation_names.end();
    if ((pending_generation_staged && pending_generation_final) ||
        (pending_activation_staged && pending_activation_final) ||
        ((pending_activation_staged || pending_activation_final) && !pending_generation_final))
      return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
          "epoch transition contains conflicting or out-of-order staged records"));
    if (pending_generation_staged) {
      auto bytes = read_epoch_relative_bounded(generations,
          pending_transition->generation_staging_name, kMaximumEpochGenesisRecordBytes);
      if (!bytes || bytes.value() != epoch_generation_bytes(epoch, pending_transition->target))
        return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
            "epoch transition generation staging is partial or foreign"));
      generation_names.erase(std::remove(generation_names.begin(), generation_names.end(),
          pending_transition->generation_staging_name), generation_names.end());
    }
    if (pending_activation_staged) {
      auto bytes = read_epoch_relative_bounded(activations,
          pending_transition->activation_staging_name, kMaximumEpochGenesisRecordBytes);
      if (!bytes || bytes.value() != pending_transition->activation_bytes)
        return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
            "epoch transition activation staging is partial or foreign"));
      activation_names.erase(std::remove(activation_names.begin(), activation_names.end(),
          pending_transition->activation_staging_name), activation_names.end());
    }
    if (pending_generation_final) {
      std::string bytes;
      auto parsed = parse_epoch_generation(epoch, scope,
          pending_transition->target.generation_id, &bytes);
      if (!parsed || bytes != epoch_generation_bytes(epoch, pending_transition->target))
        return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
            "epoch transition target generation is foreign or changed"));
    }
  }
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
    const bool linked_operation = operation == "update" || operation == "downgrade" ||
        operation == "rollback";
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
          "epoch activation record has an incompatible exact schema: " + name));
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
  std::vector<std::string> allowed_generation_names = expected_generation_names;
  if (pending_transition != nullptr && pending_generation_final &&
      !pending_activation_final)
    allowed_generation_names.push_back(epoch_generation_name(
        pending_transition->target.generation_id));
  std::sort(allowed_generation_names.begin(), allowed_generation_names.end());
  allowed_generation_names.erase(
      std::unique(allowed_generation_names.begin(), allowed_generation_names.end()),
      allowed_generation_names.end());
  if (allowed_generation_names != observed_generation_names)
    return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
        "epoch generation records contain duplicates, extras, or omissions (expected " +
        std::to_string(allowed_generation_names.size()) + ", observed " +
        std::to_string(observed_generation_names.size()) + ")"));
  std::vector<fs::path> final_generation_names, final_activation_names;
  if (!generations.list_child_names_bounded(kMaximumEpochActivationRecords,
                                             final_generation_names).ok() ||
      !activations.list_child_names_bounded(kMaximumEpochActivationRecords,
                                             final_activation_names).ok() ||
      final_generation_names != raw_generation_names ||
      final_activation_names != raw_activation_names ||
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
  // Every non-genesis activation is either the immutable completion of one
  // historical maintenance operation or the exact target activation of the
  // one targeted operation currently being published.  The latter is allowed
  // only while the targeted 60 record has not yet closed at 80.
  const bool targeted_activation = pending_transition != nullptr && pending_activation_final &&
      (allowed_maintenance_operation == nullptr || !std::any_of(
          completed_shell_cutovers.begin(), completed_shell_cutovers.end(),
          [&](const CompletedEpochShellCutover &completed) {
            return completed.operation_id == *allowed_maintenance_operation;
          }));
  if (ordered.size() > 1U || !completed_shell_cutovers.empty() || targeted_activation) {
    if (ordered.size() < 2U || completed_shell_cutovers.size() +
            (targeted_activation ? 1U : 0U) != ordered.size() - 1U)
      return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
          "epoch maintenance history is not bijective with activation history (activations " +
          std::to_string(ordered.size()) + ", completed " +
          std::to_string(completed_shell_cutovers.size()) + ", pending " +
          (targeted_activation ? "1" : "0") + ")"));
    for (std::size_t index = 1U; index < ordered.size(); ++index) {
      const auto matches = std::count_if(completed_shell_cutovers.begin(),
          completed_shell_cutovers.end(), [&](const CompletedEpochShellCutover &completed) {
            const bool appeared_earlier = std::any_of(ordered.begin(),
                ordered.begin() + index,
                [&](const Node *node) {
                  return node->target_generation_id == completed.generation_id;
                });
            return ordered[index]->name == completed.activation_name &&
                ordered[index]->digest == completed.activation_sha256 &&
                ordered[index]->target_generation_id == completed.generation_id &&
                ordered[index - 1U]->name == completed.source_activation_name &&
                ordered[index - 1U]->digest == completed.source_activation_sha256 &&
                ordered[index - 1U]->target_generation_id ==
                    completed.source_generation_id &&
                (completed.reactivation
                    ? index >= 2U &&
                      ordered[index - 2U]->target_generation_id ==
                          completed.generation_id &&
                      epoch_generation_bytes(epoch, ordered[index - 2U]->target) ==
                          epoch_generation_bytes(epoch, ordered[index]->target)
                    : !appeared_earlier);
          });
      const bool pending_match = targeted_activation &&
          ordered[index]->name == pending_transition->activation_name &&
          ordered[index]->digest == hash(pending_transition->activation_bytes) &&
          ordered[index]->target_generation_id == pending_transition->target.generation_id;
      if (matches + (pending_match ? 1 : 0) != 1)
        return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
            "epoch maintenance history does not exactly bind activation history"));
    }
  }
  if (!std::all_of(completed_shell_cutovers.begin(), completed_shell_cutovers.end(),
          [&](CompletedEpochShellCutover &completed) {
            return revalidate_completed_epoch_shell_cutover(completed, scope);
          }))
    return facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
        "completed epoch shell cutover changed during active discovery"));
  ActiveState state{cursor->target, {}, cursor->name, cursor->digest};
  if (ordered.size() > 1U) state.previous = ordered[ordered.size() - 2U]->target;
  if (validated_history != nullptr) {
    validated_history->clear();
    validated_history->reserve(ordered.size());
    for (const Node *node : ordered)
      validated_history->push_back(node->target);
  }
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
    const std::string &bytes,
    std::size_t maximum_final_records = 5U) {
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
  if (maximum_final_records == 0U ||
      !directory.list_child_names_bounded(maximum_final_records + 1U, names).ok() ||
      names.size() > maximum_final_records)
    return facman::core::Result<void>::failure(epoch_recovery(
        "epoch record directory could not be enumerated for recovery"));
  const auto present = [&](const std::string &name) {
    return std::find(names.begin(), names.end(), fs::path(name)) != names.end();
  };
  if (present(final_name)) return facman::core::Result<void>::failure(epoch_recovery(
      "epoch final record is unsafe or changed"));
  if (!present(staging_name) && names.size() >= maximum_final_records)
    return facman::core::Result<void>::failure(epoch_recovery(
        "epoch record directory has reached its bounded final-record limit"));
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

facman::core::Result<std::optional<std::string>> read_optional_bootstrap_record(
    const facman::platform::StableDirectoryObject &directory,
    const std::string &name) {
  const fs::path path = directory.path() / name;
  facman::platform::PathIdentity identity;
  if (!directory.validate_descendant(path, true).ok() ||
      !facman::platform::inspect_path_no_follow(path, identity).ok())
    return facman::core::Result<std::optional<std::string>>::failure(
        epoch_recovery("bootstrap record could not be safely observed", name));
  if (!identity.exists)
    return facman::core::Result<std::optional<std::string>>::success({});
  if (identity.reparse_or_link ||
      identity.kind != facman::platform::PathObjectKind::regular_file)
    return facman::core::Result<std::optional<std::string>>::failure(
        epoch_recovery("bootstrap record is not a plain file", name));
  auto bytes = read_epoch_relative_bounded(
      directory, name, kMaximumEpochGenesisRecordBytes);
  return bytes
      ? facman::core::Result<std::optional<std::string>>::success(
            std::optional<std::string>(bytes.take_value()))
      : facman::core::Result<std::optional<std::string>>::failure(bytes.error());
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
  if (compatibility) {
    facman::platform::StableDirectoryObject coordinator;
    const fs::path marker = root / "authority-handoff.v1.json";
    facman::platform::PathIdentity identity;
    const auto opened = coordinator.open_no_follow(root);
    if (!opened.ok())
      return facman::core::Result<void>::failure(epoch_recovery(
          "compatibility authority handoff could not be safely observed"));
    const auto admitted = coordinator.validate_descendant(marker, true);
    const auto inspected = admitted.ok()
        ? facman::platform::inspect_path_no_follow(marker, identity)
        : admitted;
    if (!admitted.ok() || !inspected.ok())
      return facman::core::Result<void>::failure(epoch_recovery(
          "compatibility authority handoff could not be safely observed"));
    if (identity.exists) {
      if (!active.value().has_value() || identity.reparse_or_link ||
          identity.kind != facman::platform::PathObjectKind::regular_file)
        return facman::core::Result<void>::failure(epoch_recovery(
            "compatibility authority handoff conflicts with flat retirement or an unsafe object"));
      auto bytes = read_epoch_relative_bounded(coordinator,
          "authority-handoff.v1.json", kMaximumEpochGenesisRecordBytes);
      if (!bytes || bytes.value() != compatibility_authority_handoff_bytes(history) ||
          !coordinator.revalidate().ok())
        return facman::core::Result<void>::failure(epoch_recovery(
            "compatibility authority handoff is foreign, incomplete, or changed"));
      LifecycleEpoch successor;
      successor.acceptance_root = epoch.acceptance_root;
      successor.genesis_generation_id = history.generations.back().generation_id;
      successor.logical_root = epoch.logical_root;
      successor.predecessor_epoch_id = kCompatibilityEpochId;
      successor.predecessor_manifest_sha256 = hash(compatibility_manifest_bytes(history));
      successor.predecessor_retirement_sha256 = hash(bytes.value());
      successor.state_root = epoch.state_root;
      successor.epoch_id = hash(lifecycle_identity_bytes(successor));
      const Generation &source = history.generations.back();
      auto target = make_epoch_genesis_generation(successor,
          generation_descriptor(source), source.package_sha256);
      facman::platform::StableDirectoryObject bootstrap;
      if (!target || !coordinator.open_child_directory_no_follow(
              "authority-bootstrap.v1", bootstrap).ok())
        return facman::core::Result<void>::failure(epoch_recovery(
            "compatibility authority handoff lacks its exact bootstrap journal"));
      auto entered = read_epoch_relative_bounded(bootstrap,
          "10-clone-entered.v1.json", kMaximumEpochGenesisRecordBytes);
      if (!entered ||
          (entered.value() != compatibility_bootstrap_entered_bytes(
              history, successor, target.value(), true) &&
           entered.value() != compatibility_bootstrap_entered_bytes(
              history, successor, target.value(), false)))
        return facman::core::Result<void>::failure(epoch_recovery(
            "compatibility bootstrap entry does not bind the exact epoch clone"));
      auto verified = read_epoch_relative_bounded(bootstrap,
          "20-clone-verified.v1.json", kMaximumEpochGenesisRecordBytes);
      auto document = verified ? json::parse(verified.value())
          : facman::core::Result<json::Value>::failure(verified.error());
      const std::string receipt = document
          ? string_field(document.value(), "receipt_sha256") : std::string();
      if (!digest(receipt) || !verified ||
          verified.value() != compatibility_bootstrap_phase_bytes(
              "clone_verified", hash(entered.value()), receipt) ||
          !bootstrap.revalidate().ok())
        return facman::core::Result<void>::failure(epoch_recovery(
            "compatibility authority handoff lacks exact clone verification"));
      epoch.retirement_sha256 = hash(bytes.value());
      epoch.compatibility_handoff = true;
      return facman::core::Result<void>::success();
    }
  }
  if (active.value().has_value()) {
    epoch.compatibility_active = std::move(*active.value());
    return facman::core::Result<void>::success();
  }
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

facman::core::Result<void> validate_real_epoch_retirement(
    LifecycleEpoch &epoch, const fs::path &coordinator_root,
    const ActiveState &active, const std::vector<Generation> &history,
    const LifecycleEpoch *compatibility) {
  if (history.empty() || epoch.compatibility_epoch)
    return facman::core::Result<void>::failure(epoch_recovery(
        "real epoch retirement has no validated activation history"));
  ActivationChain combined;
  if (epoch.predecessor_epoch_id == kCompatibilityEpochId) {
    if (compatibility == nullptr || !compatibility->compatibility_epoch)
      return facman::core::Result<void>::failure(epoch_recovery(
          "real epoch retirement has no compatibility predecessor"));
    if (compatibility->compatibility_handoff) {
      auto flat = discover_activation_chain(coordinator_root);
      if (!flat || !flat.value().has_value())
        return facman::core::Result<void>::failure(!flat ? flat.error() :
            epoch_recovery("retained compatibility history is unavailable"));
      combined.generations = flat.value()->generations;
    } else if (compatibility->retirement_sha256.empty() ||
               compatibility->compatibility_active.has_value()) {
      return facman::core::Result<void>::failure(epoch_recovery(
          "compatibility predecessor is active or incompletely retired"));
    }
  }
  combined.generations.insert(combined.generations.end(),
      history.begin(), history.end());
  for (std::size_t index = 0; index < combined.generations.size(); ++index) {
    const Generation &generation = combined.generations[index];
    if (!same_path(generation.logical_root, epoch.logical_root) ||
        !same_path(generation.state_root, epoch.state_root) ||
        !same_path(generation.acceptance_root, epoch.acceptance_root))
      return facman::core::Result<void>::failure(epoch_recovery(
          "real epoch retirement generations have different roots"));
    for (std::size_t earlier = 0; earlier < index; ++earlier)
      if (combined.generations[earlier].install_id == generation.install_id &&
          (combined.generations[earlier].generation_id != generation.generation_id ||
           !same_path(combined.generations[earlier].install_root,
                      generation.install_root)))
        return facman::core::Result<void>::failure(epoch_recovery(
            "real epoch retirement has a conflicting provider identity"));
  }
  combined.activation_name = "epoch." + epoch.epoch_id + "." +
      active.activation_name;
  combined.activation_sha256 = hash("facman.epoch.retirement-head.v1\n" +
      epoch.epoch_id + "\n" + epoch.manifest_sha256 + "\n" +
      active.activation_name + "\n" + active.activation_sha256 + "\n");
  const fs::path root = coordinator_root / "epoch-retirements";
  facman::platform::PathIdentity root_identity;
  const auto observed_root = facman::platform::inspect_path_no_follow(
      root, root_identity);
  if (!observed_root.ok() ||
      (root_identity.exists &&
       (root_identity.reparse_or_link ||
        root_identity.kind != facman::platform::PathObjectKind::directory)))
    return facman::core::Result<void>::failure(epoch_recovery(
        "real epoch retirement root is unsafe"));
  if (!root_identity.exists) return facman::core::Result<void>::success();
  const fs::path journal = root /
      ("retirement." + combined.activation_sha256.substr(0, 32) + ".v1");
  facman::platform::PathIdentity journal_identity;
  const auto observed_journal = facman::platform::inspect_path_no_follow(
      journal, journal_identity);
  if (!observed_journal.ok() ||
      (journal_identity.exists &&
       (journal_identity.reparse_or_link ||
        journal_identity.kind != facman::platform::PathObjectKind::directory)))
    return facman::core::Result<void>::failure(epoch_recovery(
        "real epoch retirement journal is unsafe"));
  if (!journal_identity.exists) return facman::core::Result<void>::success();
  epoch.retirement_journal_name = journal.filename().string();
  facman::platform::StableDirectoryObject pinned_root, pinned_journal;
  if (!pinned_root.open_no_follow(root).ok() ||
      !pinned_root.open_child_directory_no_follow(
          journal.filename().string(), pinned_journal).ok())
    return facman::core::Result<void>::failure(epoch_recovery(
        "real epoch retirement journal could not be pinned"));
  std::error_code status;
  const auto first = fs::directory_iterator(journal, status);
  if (status)
    return facman::core::Result<void>::failure(epoch_recovery(
        "real epoch retirement journal cannot be enumerated", status.message()));
  if (first == fs::directory_iterator()) {
    if (!pinned_journal.revalidate().ok() || !pinned_root.revalidate().ok())
      return facman::core::Result<void>::failure(epoch_recovery(
          "empty real epoch retirement journal changed during validation"));
    return facman::core::Result<void>::success();
  }
  const auto steps = retirement_steps(combined);
  bool completed = false;
  auto validated = validate_retirement_directory(journal, combined, steps,
                                                 &completed);
  if (!validated) return validated;
  if (!pinned_journal.revalidate().ok() || !pinned_root.revalidate().ok())
    return facman::core::Result<void>::failure(epoch_recovery(
        "real epoch retirement journal changed during validation"));
  if (completed)
    epoch.retirement_sha256 = hash(retirement_completed_json(combined,
                                                            steps.size()));
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
    const std::string &allowed_maintenance_epoch_id = {},
    const PendingEpochTransitionState *pending_transition = nullptr,
    const std::string &ignored_unpublished_epoch_id = {}) {
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
    for (const char *name : {"generations", "retirements", "maintenance",
                             "authority-handoff.v1.json", "authority-bootstrap.v1"}) {
      facman::platform::PathIdentity identity;
      if (!coordinator.validate_descendant(coordinator_root / name, true).ok() ||
          !facman::platform::inspect_path_no_follow(
              coordinator_root / name, identity).ok())
        return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
            "flat coordinator state could not be safely observed"));
      if (identity.exists)
        return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
            "flat coordinator has state without a valid activation history"));
    }
  }

  const fs::path epochs_path = coordinator_root / "epochs";
  if (!fs::exists(epochs_path, status)) {
    if (status) return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
        "epoch root could not be observed", status.message()));
    facman::platform::PathIdentity orphan_retirements;
    const auto orphan = facman::platform::inspect_path_no_follow(
        coordinator_root / "epoch-retirements", orphan_retirements);
    if (!orphan.ok() || orphan_retirements.exists)
      return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
          "epoch retirement state exists without an epoch namespace"));
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
  bool ignored_unpublished_epoch = false;
  for (const fs::path &entry : epoch_names) {
    const std::string name = entry.string();
    if (!digest(name) || name == kCompatibilityEpochId)
      return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
          "epoch root contains a non-epoch or linked entry"));
    facman::platform::StableDirectoryObject epoch_directory;
    if (!epochs.open_child_directory_no_follow(name, epoch_directory).ok())
      return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
          "epoch directory could not be pinned"));
    if (!ignored_unpublished_epoch_id.empty() &&
        name == ignored_unpublished_epoch_id) {
      std::vector<fs::path> partial_names;
      if (ignored_unpublished_epoch ||
          !epoch_directory.list_child_names_bounded(2U, partial_names).ok() ||
          partial_names.size() > 1U ||
          (!partial_names.empty() &&
           partial_names.front() != fs::path("epoch.staging.v1.json")) ||
          !epoch_directory.revalidate().ok())
        return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
            "unpublished successor epoch contains foreign or changed state"));
      ignored_unpublished_epoch = true;
      continue;
    }
    PinnedLifecycleEpochScope scope;
    auto pinned = scope.open(coordinator_root, name);
    if (!pinned) return facman::core::Result<LifecycleEpochChain>::failure(pinned.error());
    auto bytes = scope.read("epoch.v1.json");
    if (!bytes) return facman::core::Result<LifecycleEpochChain>::failure(bytes.error());
    auto epoch = parse_lifecycle_manifest(bytes.value(), name);
    if (!epoch) return facman::core::Result<LifecycleEpochChain>::failure(epoch.error());
    const bool recovery_tail = !recovery_epoch_id.empty() && name == recovery_epoch_id;
    std::vector<Generation> epoch_history;
    auto genesis = discover_epoch_genesis_state(epoch.value(), scope,
        recovery_tail ? recovery_generation : nullptr, recovery_tail,
        (!allowed_maintenance_operation.empty() && name == allowed_maintenance_epoch_id)
            ? &allowed_maintenance_operation : nullptr,
        name == allowed_maintenance_epoch_id ? pending_transition : nullptr,
        &epoch_history);
    if (!genesis) return facman::core::Result<LifecycleEpochChain>::failure(genesis.error());
    if (genesis.value().has_value()) {
      const LifecycleEpoch *compatibility = !result.epochs.empty() &&
          result.epochs.front().compatibility_epoch
          ? &result.epochs.front() : nullptr;
      auto retirement = validate_real_epoch_retirement(epoch.value(),
          coordinator_root, *genesis.value(), epoch_history, compatibility);
      if (!retirement)
        return facman::core::Result<LifecycleEpochChain>::failure(
            retirement.error());
    }
    if (!epoch_directory.revalidate().ok())
      return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
          "epoch state changed while its pinned children were validated"));
    result.epochs.push_back(epoch.take_value());
  }
  if (!epochs.revalidate().ok() || !coordinator.revalidate().ok())
    return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
        "epoch directories changed during discovery"));
  if (!ignored_unpublished_epoch_id.empty() && !ignored_unpublished_epoch)
    return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
        "requested unpublished successor epoch is unavailable"));

  facman::platform::PathIdentity retirement_identity;
  const fs::path retirement_root = coordinator_root / "epoch-retirements";
  const auto retirement_observed = facman::platform::inspect_path_no_follow(
      retirement_root, retirement_identity);
  if (!retirement_observed.ok() ||
      (retirement_identity.exists &&
       (retirement_identity.reparse_or_link ||
        retirement_identity.kind != facman::platform::PathObjectKind::directory)))
    return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
        "epoch retirement root is unsafe during lifecycle discovery"));
  if (retirement_identity.exists) {
    facman::platform::StableDirectoryObject retirements;
    std::vector<fs::path> names;
    if (!coordinator.open_child_directory_no_follow(
            "epoch-retirements", retirements).ok() ||
        !retirements.list_child_names_bounded(kMaximumLifecycleEpochs, names).ok())
      return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
          "epoch retirement history cannot be pinned or is oversized"));
    for (const fs::path &name : names) {
      const auto matching = std::count_if(result.epochs.begin(),
          result.epochs.end(), [&](const LifecycleEpoch &epoch) {
            return !epoch.compatibility_epoch &&
                epoch.retirement_journal_name == name.string();
          });
      if (matching != 1U)
        return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
            "epoch retirement root contains foreign or conflicting history"));
    }
    if (!retirements.revalidate().ok() || !coordinator.revalidate().ok())
      return facman::core::Result<LifecycleEpochChain>::failure(epoch_recovery(
          "epoch retirement history changed during discovery"));
  }

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
  result.install_id = epoch_generation_install_id(epoch.epoch_id,
                                                   result.generation_id);
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
        epoch_generation_name(request.generation.generation_id), generation_bytes,
        kMaximumEpochActivationRecords);
    if (!written) return facman::core::Result<ActiveState>::failure(written.error());
    written = publish_epoch_record(activations.value(),
        epoch_activation_staging_name(request.generation.generation_id),
        epoch_activation_name(request.generation.generation_id),
        epoch_activation_bytes(epoch.value(), request.generation, hash(generation_bytes)),
        kMaximumEpochActivationRecords);
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

namespace {

facman::core::Result<EpochActiveState> discover_lifecycle_epoch_active_from_chain(
    const fs::path &coordinator_root, const LifecycleEpochChain &chain) {
  if (chain.epochs.empty())
    return facman::core::Result<EpochActiveState>::failure(epoch_recovery(
        "lifecycle epoch discovery has no active epoch"));
  LifecycleEpoch epoch = chain.epochs.back();
  if (epoch.compatibility_epoch) {
    if (!epoch.compatibility_active.has_value())
      return facman::core::Result<EpochActiveState>::failure(epoch_recovery(
          "compatibility lifecycle epoch has no active generation"));
    ActiveState active = std::move(*epoch.compatibility_active);
    return facman::core::Result<EpochActiveState>::success(
        {std::move(epoch), std::move(active)});
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

facman::core::Result<ActivationChain> discover_epoch_retirement_chain(
    const fs::path &coordinator_root) {
  auto epochs = discover_lifecycle_epoch_chain_impl(coordinator_root);
  if (!epochs || epochs.value().epochs.empty() ||
      epochs.value().epochs.back().compatibility_epoch)
    return facman::core::Result<ActivationChain>::failure(!epochs
        ? epochs.error() : epoch_recovery(
            "epoch retirement requires one authoritative real lifecycle tail"));
  const LifecycleEpoch &tail = epochs.value().epochs.back();
  auto selected = discover_lifecycle_epoch_active_from_chain(
      coordinator_root, epochs.value());
  if (!selected) return facman::core::Result<ActivationChain>::failure(
      selected.error());
  PinnedLifecycleEpochScope scope;
  auto opened = scope.open(coordinator_root, tail.epoch_id);
  if (!opened) return facman::core::Result<ActivationChain>::failure(opened.error());
  std::vector<Generation> epoch_history;
  auto active = discover_epoch_genesis_state(tail, scope, nullptr, false,
      nullptr, nullptr, &epoch_history);
  if (!active || !active.value().has_value() || epoch_history.empty() ||
      active.value()->activation_sha256 !=
          selected.value().active.activation_sha256)
    return facman::core::Result<ActivationChain>::failure(!active
        ? active.error() : epoch_recovery(
            "epoch retirement lineage changed during discovery"));
  ActivationChain combined;
  if (tail.predecessor_epoch_id == kCompatibilityEpochId &&
      epochs.value().epochs.front().compatibility_epoch) {
    const LifecycleEpoch &compatibility = epochs.value().epochs.front();
    if (compatibility.compatibility_handoff) {
      auto flat = discover_activation_chain(coordinator_root);
      if (!flat || !flat.value().has_value())
        return facman::core::Result<ActivationChain>::failure(!flat
            ? flat.error() : epoch_recovery(
                "epoch retirement lacks its retained compatibility lineage"));
      combined.generations = flat.value()->generations;
    } else if (compatibility.retirement_sha256.empty() ||
               compatibility.compatibility_active.has_value()) {
      return facman::core::Result<ActivationChain>::failure(epoch_recovery(
          "epoch retirement has an active or incomplete compatibility predecessor"));
    }
  }
  combined.generations.insert(combined.generations.end(),
      epoch_history.begin(), epoch_history.end());
  for (std::size_t index = 0; index < combined.generations.size(); ++index) {
    const Generation &generation = combined.generations[index];
    if (!same_path(generation.logical_root, tail.logical_root) ||
        !same_path(generation.state_root, tail.state_root) ||
        !same_path(generation.acceptance_root, tail.acceptance_root))
      return facman::core::Result<ActivationChain>::failure(epoch_recovery(
          "epoch retirement generations do not share one exact authority"));
    for (std::size_t earlier = 0; earlier < index; ++earlier)
      if (combined.generations[earlier].install_id == generation.install_id &&
          (combined.generations[earlier].generation_id != generation.generation_id ||
           !same_path(combined.generations[earlier].install_root,
                      generation.install_root)))
        return facman::core::Result<ActivationChain>::failure(epoch_recovery(
            "epoch retirement contains a conflicting provider installation identity"));
  }
  combined.activation_name = "epoch." + tail.epoch_id + "." +
      active.value()->activation_name;
  combined.activation_sha256 = hash("facman.epoch.retirement-head.v1\n" +
      tail.epoch_id + "\n" + tail.manifest_sha256 + "\n" +
      active.value()->activation_name + "\n" +
      active.value()->activation_sha256 + "\n");
  return facman::core::Result<ActivationChain>::success(std::move(combined));
}

fs::path epoch_retirement_directory(const fs::path &coordinator_root,
                                    const ActivationChain &chain) {
  return coordinator_root / "epoch-retirements" /
      ("retirement." + chain.activation_sha256.substr(0, 32) + ".v1");
}

facman::core::Result<std::optional<bool>> epoch_retirement_status(
    const fs::path &coordinator_root, const ActivationChain &chain,
    const std::vector<RetirementStep> &steps,
    const LifecycleEpochChain &epochs) {
  const fs::path root = coordinator_root / "epoch-retirements";
  const fs::path journal = epoch_retirement_directory(coordinator_root, chain);
  std::error_code status;
  if (!fs::exists(root, status)) {
    if (status) return facman::core::Result<std::optional<bool>>::failure(
        epoch_recovery("epoch retirement root could not be observed", status.message()));
    return facman::core::Result<std::optional<bool>>::success({});
  }
  if (status || fs::symlink_status(root, status).type() !=
                    fs::file_type::directory || status)
    return facman::core::Result<std::optional<bool>>::failure(epoch_recovery(
        "epoch retirement root is not a plain directory"));
  bool found = false;
  for (fs::directory_iterator it(root, status), end; !status && it != end;
       it.increment(status)) {
    const bool current = it->path().lexically_normal() ==
        journal.lexically_normal();
    const bool historical = std::any_of(epochs.epochs.begin(),
        epochs.epochs.end(), [&](const LifecycleEpoch &epoch) {
          return !epoch.compatibility_epoch &&
              !epoch.retirement_sha256.empty() &&
              epoch.retirement_journal_name == it->path().filename().string();
        });
    if (it->symlink_status(status).type() != fs::file_type::directory ||
        status || (!current && !historical) || (current && found))
      return facman::core::Result<std::optional<bool>>::failure(epoch_recovery(
          "epoch retirement root contains foreign or conflicting history"));
    if (current) found = true;
  }
  if (status) return facman::core::Result<std::optional<bool>>::failure(
      epoch_recovery("epoch retirement root changed during enumeration",
                     status.message()));
  if (!found)
    return facman::core::Result<std::optional<bool>>::success({});
  const auto first = fs::directory_iterator(journal, status);
  if (status) return facman::core::Result<std::optional<bool>>::failure(
      epoch_recovery("epoch retirement journal could not be enumerated",
                     status.message()));
  if (first == fs::directory_iterator())
    return facman::core::Result<std::optional<bool>>::success(false);
  bool completed = false;
  auto checked = validate_retirement_directory(journal, chain, steps,
                                               &completed);
  if (!checked) return facman::core::Result<std::optional<bool>>::failure(
      checked.error());
  return facman::core::Result<std::optional<bool>>::success(completed);
}

} // namespace

facman::core::Result<EpochActiveState> discover_lifecycle_epoch_active(
    const fs::path &coordinator_root) {
  auto selected = resolve_authoritative_active_state(coordinator_root);
  if (!selected || !selected.value().has_value())
    return facman::core::Result<EpochActiveState>::failure(!selected
        ? selected.error() : epoch_recovery(
            "no authoritative lifecycle epoch is active"));
  if (selected.value()->epoch.has_value())
    return facman::core::Result<EpochActiveState>::success(
        {*selected.value()->epoch, selected.value()->active});
  // Preserve the public compatibility-epoch view when flat history is still
  // authoritative. Resolver failure above continues to withhold it during
  // an entered or incomplete bootstrap.
  auto chain = discover_lifecycle_epoch_chain_impl(coordinator_root);
  if (!chain || chain.value().epochs.size() != 1U ||
      !chain.value().epochs.front().compatibility_epoch ||
      !chain.value().epochs.front().compatibility_active.has_value())
    return facman::core::Result<EpochActiveState>::failure(!chain
        ? chain.error() : epoch_recovery(
            "authoritative compatibility epoch changed during discovery"));
  const LifecycleEpoch &compatibility = chain.value().epochs.front();
  if (compatibility.compatibility_active->activation_sha256 !=
          selected.value()->active.activation_sha256 ||
      compatibility.compatibility_active->active.install_id !=
          selected.value()->active.active.install_id)
    return facman::core::Result<EpochActiveState>::failure(epoch_recovery(
        "compatibility activation changed during epoch discovery"));
  return facman::core::Result<EpochActiveState>::success(
      {compatibility, selected.value()->active});
}

facman::core::Result<ActivationChain> discover_lifecycle_epoch_activation_chain(
    const fs::path &coordinator_root) {
  auto selected = discover_lifecycle_epoch_active(coordinator_root);
  if (!selected) return facman::core::Result<ActivationChain>::failure(
      selected.error());
  if (selected.value().epoch.compatibility_epoch)
    return facman::core::Result<ActivationChain>::failure(epoch_recovery(
        "no authoritative real lifecycle epoch is active"));
  PinnedLifecycleEpochScope scope;
  auto opened = scope.open(coordinator_root, selected.value().epoch.epoch_id);
  if (!opened) return facman::core::Result<ActivationChain>::failure(opened.error());
  auto manifest = scope.read("epoch.v1.json");
  auto epoch = manifest
      ? parse_lifecycle_manifest(manifest.value(), selected.value().epoch.epoch_id)
      : facman::core::Result<LifecycleEpoch>::failure(manifest.error());
  if (!epoch || epoch.value().manifest_sha256 !=
                    selected.value().epoch.manifest_sha256)
    return facman::core::Result<ActivationChain>::failure(!epoch ? epoch.error() :
        epoch_recovery("epoch manifest changed during lineage discovery"));
  std::vector<Generation> history;
  auto active = discover_epoch_genesis_state(epoch.value(), scope, nullptr,
      false, nullptr, nullptr, &history);
  if (!active || !active.value().has_value() || history.empty() ||
      active.value()->activation_name != selected.value().active.activation_name ||
      active.value()->activation_sha256 != selected.value().active.activation_sha256 ||
      history.back().install_id != selected.value().active.active.install_id)
    return facman::core::Result<ActivationChain>::failure(!active ? active.error() :
        epoch_recovery("authoritative epoch lineage changed during discovery"));
  return facman::core::Result<ActivationChain>::success(
      {std::move(history), active.value()->activation_name,
       active.value()->activation_sha256});
}

facman::core::Result<std::optional<AuthoritativeActiveState>>
resolve_authoritative_active_state(const fs::path &coordinator_root) {
  auto chain = discover_lifecycle_epoch_chain_impl(coordinator_root);
  if (!chain)
    return facman::core::Result<std::optional<AuthoritativeActiveState>>::failure(
        chain.error());
  if (chain.value().epochs.empty()) {
    auto flat = discover_active(coordinator_root);
    if (!flat)
      return facman::core::Result<std::optional<AuthoritativeActiveState>>::failure(
          flat.error());
    if (!flat.value().has_value())
      return facman::core::Result<std::optional<AuthoritativeActiveState>>::success({});
    return facman::core::Result<std::optional<AuthoritativeActiveState>>::success(
        AuthoritativeActiveState{{}, std::move(*flat.value())});
  }
  const LifecycleEpoch &tail = chain.value().epochs.back();
  if (tail.compatibility_epoch) {
    facman::platform::PathIdentity bootstrap;
    const auto observed = facman::platform::inspect_path_no_follow(
        coordinator_root / "authority-bootstrap.v1", bootstrap);
    if (!observed.ok() || bootstrap.exists)
      return facman::core::Result<std::optional<AuthoritativeActiveState>>::failure(
          epoch_recovery("compatibility bootstrap requires recovery"));
  }
  if (tail.compatibility_epoch && tail.compatibility_handoff)
    return facman::core::Result<std::optional<AuthoritativeActiveState>>::failure(
        epoch_recovery("compatibility authority handoff awaits its real epoch genesis"));
  if (tail.compatibility_epoch && !tail.compatibility_active.has_value() &&
      !tail.retirement_sha256.empty())
    return facman::core::Result<std::optional<AuthoritativeActiveState>>::success({});
  auto epoch = discover_lifecycle_epoch_active_from_chain(
      coordinator_root, chain.value());
  if (!epoch)
    return facman::core::Result<std::optional<AuthoritativeActiveState>>::failure(
        epoch.error());
  if (!epoch.value().epoch.compatibility_epoch &&
      epoch.value().epoch.predecessor_epoch_id == kCompatibilityEpochId &&
      chain.value().epochs.front().compatibility_handoff) {
    auto flat = discover_activation_chain(coordinator_root);
    PinnedLifecycleEpochScope genesis_scope;
    auto opened = genesis_scope.open(coordinator_root, epoch.value().epoch.epoch_id);
    auto manifest = opened ? genesis_scope.read("epoch.v1.json")
        : facman::core::Result<std::string>::failure(opened.error());
    auto pinned_epoch = manifest ? parse_lifecycle_manifest(
        manifest.value(), epoch.value().epoch.epoch_id)
        : facman::core::Result<LifecycleEpoch>::failure(manifest.error());
    std::vector<Generation> history;
    auto selected = pinned_epoch && pinned_epoch.value().manifest_sha256 ==
            epoch.value().epoch.manifest_sha256
        ? discover_epoch_genesis_state(pinned_epoch.value(), genesis_scope,
            nullptr, false, nullptr, nullptr, &history)
        : facman::core::Result<std::optional<ActiveState>>::failure(epoch_recovery(
            "bootstrap epoch manifest changed during completion review"));
    facman::platform::StableDirectoryObject coordinator, bootstrap;
    if (!flat || !flat.value().has_value() || !selected ||
        !selected.value().has_value() || history.empty() ||
        history.front().generation_id != epoch.value().epoch.genesis_generation_id ||
        selected.value()->activation_name != epoch.value().active.activation_name ||
        selected.value()->activation_sha256 != epoch.value().active.activation_sha256 ||
        !coordinator.open_no_follow(coordinator_root).ok() ||
        !coordinator.open_child_directory_no_follow(
            "authority-bootstrap.v1", bootstrap).ok())
      return facman::core::Result<std::optional<AuthoritativeActiveState>>::failure(
          epoch_recovery("bootstrap completion cannot be safely observed"));
    // The bootstrap journal binds the immutable genesis clone. Later epoch
    // activations change the selected head but cannot rewrite that handoff.
    const Generation &target = history.front();
    std::string genesis_generation_bytes;
    auto genesis_generation = parse_epoch_generation(pinned_epoch.value(),
        genesis_scope, target.generation_id, &genesis_generation_bytes);
    if (!genesis_generation || genesis_generation_bytes !=
            epoch_generation_bytes(pinned_epoch.value(), target))
      return facman::core::Result<std::optional<AuthoritativeActiveState>>::failure(
          epoch_recovery("bootstrap genesis generation changed during completion review"));
    const std::string genesis_activation_sha256 = hash(epoch_activation_bytes(
        pinned_epoch.value(), target, hash(genesis_generation_bytes)));
    auto entered = read_epoch_relative_bounded(bootstrap,
        "10-clone-entered.v1.json", kMaximumEpochGenesisRecordBytes);
    const std::string enabled = compatibility_bootstrap_entered_bytes(
        *flat.value(), epoch.value().epoch, target, true);
    const std::string disabled = compatibility_bootstrap_entered_bytes(
        *flat.value(), epoch.value().epoch, target, false);
    if (!entered || (entered.value() != enabled && entered.value() != disabled))
      return facman::core::Result<std::optional<AuthoritativeActiveState>>::failure(
          epoch_recovery("bootstrap completion has a different entered identity"));
    const bool shell = entered.value() == enabled;
    const std::string entered_sha256 = hash(entered.value());
    const std::string genesis_bytes = compatibility_bootstrap_phase_bytes(
        "genesis_activated", entered_sha256, genesis_activation_sha256);
    const std::string shortcut_receipt = hash("facman.bootstrap.shortcut.v1\n" +
        target.install_id + "\n" + (shell ? "cutover\n" : "disabled\n"));
    const std::string registration_receipt = hash(
        "facman.bootstrap.registration.v1\n" + target.install_id + "\n" +
        (shell ? "cutover\n" : "disabled\n"));
    const std::string registration_bytes = compatibility_bootstrap_phase_bytes(
        "registration_cutover", entered_sha256, registration_receipt);
    const std::vector<std::pair<std::string, std::string>> required = {
        {"30-genesis-activated.v1.json", genesis_bytes},
        {"40-shortcut-cutover.v1.json", compatibility_bootstrap_phase_bytes(
            "shortcut_cutover", entered_sha256, shortcut_receipt)},
        {"50-registration-cutover.v1.json", registration_bytes},
        {"60-complete.v1.json", compatibility_bootstrap_phase_bytes(
            "complete", entered_sha256, hash(registration_bytes))}};
    for (const auto &record : required) {
      auto bytes = read_epoch_relative_bounded(
          bootstrap, record.first, kMaximumEpochGenesisRecordBytes);
      if (!bytes || bytes.value() != record.second)
        return facman::core::Result<std::optional<AuthoritativeActiveState>>::failure(
            epoch_recovery("bootstrap native cutover is incomplete or changed",
                           record.first));
    }
    std::vector<fs::path> names;
    const std::vector<fs::path> complete_names = {
        "10-clone-entered.v1.json", "20-clone-verified.v1.json",
        "30-genesis-activated.v1.json", "40-shortcut-cutover.v1.json",
        "50-registration-cutover.v1.json", "60-complete.v1.json"};
    if (!bootstrap.list_child_names_bounded(6U, names).ok() ||
        names != complete_names)
      return facman::core::Result<std::optional<AuthoritativeActiveState>>::failure(
          epoch_recovery("bootstrap completion journal has an unexpected entry"));
    if (!bootstrap.revalidate().ok() || !coordinator.revalidate().ok() ||
        !genesis_scope.epoch.revalidate().ok() ||
        !genesis_scope.epochs.revalidate().ok() ||
        !genesis_scope.coordinator.revalidate().ok())
      return facman::core::Result<std::optional<AuthoritativeActiveState>>::failure(
          epoch_recovery("bootstrap completion changed during selection"));
  }
  if (epoch.value().epoch.compatibility_epoch)
    return facman::core::Result<std::optional<AuthoritativeActiveState>>::success(
        AuthoritativeActiveState{{}, std::move(epoch.value().active)});
  auto retirement = discover_epoch_retirement_chain(coordinator_root);
  if (!retirement)
    return facman::core::Result<std::optional<AuthoritativeActiveState>>::failure(
        retirement.error());
  auto retirement_state = epoch_retirement_status(coordinator_root,
      retirement.value(), retirement_steps(retirement.value()), chain.value());
  if (!retirement_state)
    return facman::core::Result<std::optional<AuthoritativeActiveState>>::failure(
        retirement_state.error());
  if (retirement_state.value().has_value()) {
    if (*retirement_state.value())
      return facman::core::Result<std::optional<AuthoritativeActiveState>>::success({});
    return facman::core::Result<std::optional<AuthoritativeActiveState>>::failure(
        failure("self_maintenance_retirement_recovery_required",
                "epoch retirement is incomplete and must be resumed"));
  }
  return facman::core::Result<std::optional<AuthoritativeActiveState>>::success(
      AuthoritativeActiveState{std::move(epoch.value().epoch),
                               std::move(epoch.value().active)});
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
  bool shell_integration = true;
  std::uint64_t deadline_utc_ms = 0;
};

std::string epoch_handoff_bytes(const EpochHandoff &value) {
  json::ObjectBuilder object;
  object.add_string("schema", "facman.self_epoch_handoff.v3");
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
  object.add_string("continuation_helper", facman::platform::path_to_utf8(value.inputs.helper));
  object.add_string("continuation_helper_sha256", value.inputs.helper_sha256);
  object.add_string("provider_plan_sha256", value.provider_plan_sha256);
  object.add_string("nonce", value.nonce);
  object.add_string("shell_integration", value.shell_integration ? "enabled" : "disabled");
  if (value.deadline_utc_ms != 0)
    object.add_string("deadline_utc_ms", std::to_string(value.deadline_utc_ms));
  return object.serialize() + "\n";
}

facman::core::Result<EpochHandoff> parse_epoch_handoff(const std::string &bytes) {
  auto document = json::parse(bytes);
  const std::initializer_list<const char *> keys = {"schema", "product_id", "epoch_id",
      "epoch_manifest_sha256", "operation", "operation_id", "source_generation_id",
      "source_activation_name", "source_activation_sha256", "target_generation_id",
      "retained_package", "retained_package_sha256", "continuation_helper",
      "continuation_helper_sha256", "provider_plan_sha256", "nonce",
      "shell_integration"};
  const std::initializer_list<const char *> deadline_keys = {"schema", "product_id", "epoch_id",
      "epoch_manifest_sha256", "operation", "operation_id", "source_generation_id",
      "source_activation_name", "source_activation_sha256", "target_generation_id",
      "retained_package", "retained_package_sha256", "continuation_helper",
      "continuation_helper_sha256", "provider_plan_sha256", "nonce",
      "shell_integration", "deadline_utc_ms"};
  const bool has_deadline = document && document.value().find("deadline_utc_ms") != nullptr;
  if (!document || !(has_deadline ? exact_keys(document.value(), deadline_keys)
                                   : exact_keys(document.value(), keys)) ||
      !(has_deadline ? lifecycle_string_fields(document.value(), deadline_keys)
                     : lifecycle_string_fields(document.value(), keys)))
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
  result.inputs.helper = facman::platform::path_from_utf8(string_field(document.value(), "continuation_helper"));
  result.inputs.helper_sha256 = string_field(document.value(), "continuation_helper_sha256");
  result.provider_plan_sha256 = string_field(document.value(), "provider_plan_sha256");
  result.nonce = string_field(document.value(), "nonce");
  const std::string shell_integration = string_field(document.value(), "shell_integration");
  result.shell_integration = shell_integration == "enabled";
  if (has_deadline) {
    const std::string deadline = string_field(document.value(), "deadline_utc_ms");
    try {
      result.deadline_utc_ms = std::stoull(deadline);
      if (result.deadline_utc_ms == 0 ||
          std::to_string(result.deadline_utc_ms) != deadline)
        return facman::core::Result<EpochHandoff>::failure(epoch_recovery(
            "epoch handoff deadline is not canonical"));
    } catch (...) {
      return facman::core::Result<EpochHandoff>::failure(epoch_recovery(
          "epoch handoff deadline is not canonical"));
    }
  }
  std::string detail;
  if (string_field(document.value(), "schema") != "facman.self_epoch_handoff.v3" ||
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
      (shell_integration != "enabled" && shell_integration != "disabled") ||
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
      names[0] == fs::path("FacManContinuation.exe") &&
      names[1] == fs::path("package.zip");
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
      inputs.helper != retained_root / "FacManContinuation.exe")
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
      names[0] != fs::path("FacManContinuation.exe") || names[1] != fs::path("package.zip") ||
      !held.operation.open_child_file_no_follow_pinned("package.zip", held.package).ok())
    return facman::core::Result<HeldRetainedInputs>::failure(epoch_recovery(
        "retained handoff input is missing, linked, or outside the held state root"));
  notify_epoch_handoff_operation_pinned(held.operation.path());
  if (!held.operation.open_child_file_no_follow_pinned("FacManContinuation.exe", held.helper).ok())
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
  if ((request.operation != Operation::update && request.operation != Operation::downgrade &&
       request.operation != Operation::rollback) ||
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
  target.install_id = epoch_generation_install_id(epoch.epoch_id,
                                                   target.generation_id);
  target.install_root = epoch_generation_install_root(epoch.logical_root, epoch.epoch_id,
                                                        target.generation_id);
  target.gui = target.install_root / "generations" / target.product_version / "FacMan.exe";
  target.maintenance_launcher = target.install_root / "maintenance" / "FacManSetup.exe";
  const bool retained_predecessor = active.previous.has_value() &&
      active.previous->generation_id == target.generation_id;
  if (retained_predecessor &&
      epoch_generation_bytes(epoch, *active.previous) != epoch_generation_bytes(epoch, target))
    return facman::core::Result<Plan>::failure(failure(
        "self_maintenance_retained_target_invalid",
        "epoch package does not match the exact immediate retained predecessor"));
  Semver source_version, target_version;
  if (!exact_epoch_generation_paths(epoch, target) ||
      !semver(active.active.product_version, source_version) ||
      !semver(target.product_version, target_version) ||
      (request.operation == Operation::update && compare(target_version, source_version) <= 0) ||
      (request.operation == Operation::downgrade && compare(target_version, source_version) >= 0) ||
      (request.operation == Operation::rollback &&
       (!retained_predecessor || target.generation_id == active.active.generation_id)))
    return facman::core::Result<Plan>::failure(failure(
        "self_maintenance_version_direction_invalid", "epoch transition direction is invalid"));
  return facman::core::Result<Plan>::success({operation_name(request.operation), request.operation_id,
      active.active, target, request.package.package, request.package.package_sha256,
      retained_predecessor ? "reactivate" : "install_local",
      active.activation_name, active.activation_sha256});
}

} // namespace

facman::core::Result<Plan> review_lifecycle_epoch_reactivation(
    const EpochTransitionRequest &request, EpochContinuationEffects &effects) {
  std::string detail;
  if (request.apply || !request.coordinator_root.is_absolute() ||
      !digest(request.epoch_id) ||
      !facman::base::validate_identifier(request.operation_id, detail) ||
      (request.operation != Operation::update && request.operation != Operation::downgrade &&
       request.operation != Operation::rollback))
    return facman::core::Result<Plan>::failure(failure(
        "self_maintenance_input_invalid", "epoch reactivation review identifiers are invalid"));
  auto chain = discover_lifecycle_epoch_chain_impl(request.coordinator_root);
  if (!chain || chain.value().epochs.empty() ||
      chain.value().epochs.back().compatibility_epoch ||
      chain.value().epochs.back().epoch_id != request.epoch_id)
    return facman::core::Result<Plan>::failure(!chain ? chain.error() :
        epoch_recovery("reactivation requires the authoritative real lifecycle tail"));
  const LifecycleEpoch &epoch = chain.value().epochs.back();
  PinnedLifecycleEpochScope scope;
  auto opened = scope.open(request.coordinator_root, epoch.epoch_id);
  if (!opened) return facman::core::Result<Plan>::failure(opened.error());
  auto active = discover_epoch_genesis_state(epoch, scope);
  if (!active || !active.value().has_value())
    return facman::core::Result<Plan>::failure(!active ? active.error() :
        epoch_recovery("reactivation has no committed active generation"));
  auto inspected = inspect_package(request.package.package);
  if (!inspected || inspected.value().package_sha256 != request.package.package_sha256 ||
      inspected.value().maintenance_launcher_sha256 !=
          request.package.maintenance_launcher_sha256 ||
      !same_descriptor(inspected.value().descriptor, request.package.descriptor))
    return facman::core::Result<Plan>::failure(!inspected ? inspected.error() :
        failure("self_maintenance_package_changed",
                "reactivation source package changed after caller inspection"));
  auto planned = make_epoch_transition_plan(epoch, *active.value(), request);
  if (!planned || planned.value().provider_operation != "reactivate")
    return facman::core::Result<Plan>::failure(!planned ? planned.error() :
        failure("self_maintenance_retained_target_invalid",
                "package does not identify the exact immediate retained predecessor"));
  const CandidateState candidate = effects.inspect_candidate(planned.value());
  if (candidate != CandidateState::exact)
    return facman::core::Result<Plan>::failure(failure(
        "self_maintenance_candidate_unsafe",
        "retained epoch installation is absent, foreign, or unreadable"));
  const EffectResult installed =
      effects.inspect_retained_installed(planned.value());
  if (!installed.ok || installed.outcome_unknown ||
      !digest(installed.receipt_sha256))
    return facman::core::Result<Plan>::failure(effect_error(
        "self_maintenance_verify_failed",
        "retained epoch installed identity is not exact", installed).error());
  const EffectResult verified = effects.verify_installed(planned.value());
  if (!verified.ok || verified.outcome_unknown || !digest(verified.receipt_sha256))
    return facman::core::Result<Plan>::failure(effect_error(
        "self_maintenance_verify_failed",
        "retained epoch installation did not verify exactly", verified).error());
  if (effects.inspect_candidate(planned.value()) != CandidateState::exact)
    return facman::core::Result<Plan>::failure(epoch_recovery(
        "retained epoch installation changed during verification"));
  const EffectResult final_installed =
      effects.inspect_retained_installed(planned.value());
  if (!final_installed.ok || final_installed.outcome_unknown ||
      final_installed.receipt_sha256 != installed.receipt_sha256)
    return facman::core::Result<Plan>::failure(epoch_recovery(
        "retained epoch installed identity changed during review"));
  auto final_package = inspect_package(request.package.package);
  if (!final_package || final_package.value().package_sha256 !=
          request.package.package_sha256)
    return facman::core::Result<Plan>::failure(!final_package ? final_package.error() :
        failure("self_maintenance_package_changed",
                "reactivation source package changed during verification"));
  auto latest = discover_epoch_genesis_state(epoch, scope);
  if (!latest || !latest.value().has_value() ||
      latest.value()->activation_name != active.value()->activation_name ||
      latest.value()->activation_sha256 != active.value()->activation_sha256)
    return facman::core::Result<Plan>::failure(!latest ? latest.error() :
        epoch_recovery("reactivation source changed during read-only review"));
  return planned;
}

facman::core::Result<EpochShellCutoverResponse> execute_lifecycle_epoch_reactivation(
    const EpochTransitionRequest &request, EpochContinuationEffects &provider_effects,
    EpochShellCutoverEffects &shell_effects) {
  using Result = facman::core::Result<EpochShellCutoverResponse>;
  std::string identifier_detail;
  if (!request.coordinator_root.is_absolute() || !digest(request.epoch_id) ||
      !facman::base::validate_identifier(request.operation_id,
                                          identifier_detail) ||
      (request.operation != Operation::update &&
       request.operation != Operation::downgrade &&
       request.operation != Operation::rollback) ||
      !request.package.package.is_absolute() ||
      !digest(request.package.package_sha256))
    return Result::failure(failure("self_maintenance_input_invalid",
        "epoch reactivation request is incomplete"));
  auto pending = discover_lifecycle_epoch_pending_transition(request.coordinator_root);
  if (!pending) return Result::failure(pending.error());
  if (pending.value().has_value() &&
      pending.value()->phase != "pre_handoff" &&
      pending.value()->phase != "reactivation_pending")
    return Result::failure(epoch_recovery(
        "a different epoch maintenance transition requires recovery"));
  if (pending.value().has_value() &&
      (pending.value()->epoch_id != request.epoch_id ||
       (!pending.value()->operation_id.empty() &&
        pending.value()->operation_id != request.operation_id)))
    return Result::failure(epoch_recovery(
        "epoch reactivation request does not match the pending operation"));
  if (!request.apply && pending.value().has_value() &&
      pending.value()->phase == "reactivation_pending") {
    if (pending.value()->operation != request.operation ||
        pending.value()->retained_package.package_sha256 !=
            request.package.package_sha256 ||
        pending.value()->shell_integration != request.shell_integration)
      return Result::failure(epoch_recovery(
          "reactivation preview differs from its pending intent"));
    return Result::success({"reactivation_pending", pending.value()->target,
        request.coordinator_root / "epochs" / request.epoch_id / "maintenance" /
        request.operation_id / "00-reactivation-intent.v1.json"});
  }
  if (!request.apply && !pending.value().has_value()) {
    auto terminal = discover_lifecycle_epoch_terminal_transition(
        request.coordinator_root);
    if (!terminal) return Result::failure(terminal.error());
    if (terminal.value().has_value() &&
        terminal.value()->phase == "reactivation_complete" &&
        terminal.value()->epoch_id == request.epoch_id &&
        terminal.value()->operation_id == request.operation_id &&
        terminal.value()->operation == request.operation &&
        terminal.value()->retained_package.package_sha256 ==
            request.package.package_sha256 &&
        terminal.value()->shell_integration == request.shell_integration)
      return Result::success({"reactivation_complete",
          terminal.value()->target,
          request.coordinator_root / "epochs" / request.epoch_id / "maintenance" /
          request.operation_id / "00-reactivation-intent.v1.json"});
  }
  LifecycleEpoch epoch;
  if (pending.value().has_value() &&
      pending.value()->phase == "reactivation_pending") {
    PinnedLifecycleEpochScope pending_scope;
    auto opened_pending = pending_scope.open(request.coordinator_root,
                                             request.epoch_id);
    if (!opened_pending) return Result::failure(opened_pending.error());
    auto bytes = pending_scope.read("epoch.v1.json");
    auto parsed = bytes ? parse_lifecycle_manifest(bytes.value(), request.epoch_id)
        : facman::core::Result<LifecycleEpoch>::failure(bytes.error());
    if (!parsed || parsed.value().manifest_sha256 !=
            pending.value()->epoch_manifest_sha256)
      return Result::failure(!parsed ? parsed.error() : epoch_recovery(
          "pending reactivation epoch manifest changed"));
    epoch = parsed.take_value();
  } else {
    auto chain = discover_lifecycle_epoch_chain_impl(request.coordinator_root);
    if (!chain || chain.value().epochs.empty() ||
        chain.value().epochs.back().compatibility_epoch ||
        chain.value().epochs.back().epoch_id != request.epoch_id)
      return Result::failure(!chain ? chain.error() : epoch_recovery(
          "reactivation does not name the authoritative real epoch"));
    epoch = chain.value().epochs.back();
  }
  if (!request.apply) {
    auto reviewed = review_lifecycle_epoch_reactivation(request, provider_effects);
    if (!reviewed) return Result::failure(reviewed.error());
    return Result::success({"plan", reviewed.value().target, {}});
  }
  auto authority = admit_coordinator(request.coordinator_root,
                                     epoch.acceptance_root, false);
  if (!authority) return Result::failure(authority.error());
  auto lock = acquire(authority.take_value(), request.operation_id);
  if (!lock) return Result::failure(lock.error());
  auto locked_pending = discover_lifecycle_epoch_pending_transition(
      request.coordinator_root);
  if (!locked_pending) return Result::failure(locked_pending.error());
  if (locked_pending.value().has_value() &&
      (locked_pending.value()->epoch_id != request.epoch_id ||
       (!locked_pending.value()->operation_id.empty() &&
        locked_pending.value()->operation_id != request.operation_id) ||
       (locked_pending.value()->phase != "pre_handoff" &&
        locked_pending.value()->phase != "reactivation_pending")))
    return Result::failure(epoch_recovery(
        "epoch reactivation pending identity changed under coordinator lock"));
  PinnedLifecycleEpochScope scope;
  auto opened = scope.open(request.coordinator_root, request.epoch_id, true);
  if (!opened) return Result::failure(opened.error());
  auto maintenance = open_or_create_epoch_child(scope.epoch, "maintenance");
  if (!maintenance) return Result::failure(maintenance.error());
  auto operation = open_or_create_epoch_child(maintenance.value(),
      request.operation_id.c_str());
  if (!operation) return Result::failure(operation.error());
  const fs::path journal = operation.value().path() /
      "00-reactivation-intent.v1.json";
  std::vector<fs::path> names;
  if (!operation.value().list_child_names_bounded(4U, names).ok() ||
      (!names.empty() && !epoch_reactivation_record_names(names)))
    return Result::failure(epoch_recovery(
        "reactivation operation contains foreign or out-of-order records"));
  EpochReactivationIntent intent;
  Plan transition;
  if (names.empty()) {
    auto preview = request;
    preview.apply = false;
    auto reviewed = review_lifecycle_epoch_reactivation(preview, provider_effects);
    if (!reviewed) return Result::failure(reviewed.error());
    transition = reviewed.take_value();
    if (provider_effects.inspect_candidate(transition) != CandidateState::exact)
      return Result::failure(epoch_recovery(
          "retained provider ownership changed before reactivation intent"));
    const EffectResult installed =
        provider_effects.inspect_retained_installed(transition);
    if (!installed.ok || installed.outcome_unknown ||
        !digest(installed.receipt_sha256))
      return Result::failure(effect_error("self_maintenance_verify_failed",
          "retained installed identity changed before reactivation intent",
          installed).error());
    const EffectResult verified = provider_effects.verify_installed(transition);
    if (!verified.ok || verified.outcome_unknown ||
        !digest(verified.receipt_sha256) ||
        provider_effects.inspect_candidate(transition) != CandidateState::exact)
      return Result::failure(effect_error("self_maintenance_verify_failed",
          "retained generation changed before reactivation intent", verified).error());
    const ShellState shortcut = shell_effects.inspect_shortcut(transition);
    const ShellState registration = shell_effects.inspect_registration(transition);
    if (request.shell_integration
            ? (shortcut != ShellState::old_exact ||
               registration != ShellState::old_exact)
            : (shortcut != ShellState::new_exact ||
               registration != ShellState::new_exact))
      return Result::failure(epoch_recovery(
          "reactivation native ownership is not the exact source before intent"));
    intent.epoch_id = epoch.epoch_id;
    intent.epoch_manifest_sha256 = epoch.manifest_sha256;
    intent.operation = transition.operation;
    intent.operation_id = request.operation_id;
    intent.source_generation_id = transition.source.generation_id;
    intent.source_activation_name = transition.previous_activation_name;
    intent.source_activation_sha256 = transition.previous_activation_sha256;
    intent.target_generation_id = transition.target.generation_id;
    intent.target_generation_sha256 = hash(epoch_generation_bytes(epoch,
        transition.target));
    intent.target_package_sha256 = transition.target.package_sha256;
    intent.target_installed_identity_sha256 = installed.receipt_sha256;
    intent.target_activation_name = "activation." + request.operation_id +
        ".v2.json";
    intent.target_activation_sha256 = hash(epoch_link_activation_bytes(epoch,
        intent.operation, intent.operation_id, intent.source_generation_id,
        intent.target_generation_id, intent.target_generation_sha256,
        intent.source_activation_name, intent.source_activation_sha256));
    intent.shell_integration = request.shell_integration;
    auto written = publish_epoch_record(operation.value(),
        "00-reactivation-intent.staging.v1.json",
        "00-reactivation-intent.v1.json",
        epoch_reactivation_intent_bytes(intent), 3U);
    if (!written) return Result::failure(written.error());
  } else {
    auto bytes = read_epoch_relative_bounded(operation.value(), names.front(),
                                             kMaximumEpochGenesisRecordBytes);
    auto parsed = bytes ? parse_epoch_reactivation_intent(bytes.value(), epoch,
        request.operation_id) :
        facman::core::Result<EpochReactivationIntent>::failure(bytes.error());
    if (!parsed) return Result::failure(parsed.error());
    intent = parsed.take_value();
    if (intent.operation != operation_name(request.operation) ||
        intent.target_package_sha256 != request.package.package_sha256 ||
        intent.shell_integration != request.shell_integration)
      return Result::failure(epoch_recovery(
          "reactivation retry does not match its immutable intent"));
    auto source = parse_epoch_generation(epoch, scope,
        intent.source_generation_id);
    std::string target_bytes;
    auto target = parse_epoch_generation(epoch, scope,
        intent.target_generation_id, &target_bytes);
    if (!source || !target || hash(target_bytes) !=
            intent.target_generation_sha256 ||
        target.value().package_sha256 != intent.target_package_sha256)
      return Result::failure(!source ? source.error() : !target ? target.error() :
          epoch_recovery("reactivation generation changed after intent"));
    transition = {intent.operation, intent.operation_id, source.take_value(),
        target.take_value(), request.package.package, request.package.package_sha256,
        "reactivate", intent.source_activation_name,
        intent.source_activation_sha256};
    auto inspected = inspect_package(request.package.package);
    if (!inspected || inspected.value().package_sha256 !=
            intent.target_package_sha256 ||
        inspected.value().maintenance_launcher_sha256 !=
            request.package.maintenance_launcher_sha256 ||
        !same_descriptor(inspected.value().descriptor,
                         request.package.descriptor) ||
        !same_descriptor(inspected.value().descriptor,
                         generation_descriptor(transition.target)))
      return Result::failure(!inspected ? inspected.error() : epoch_recovery(
          "reactivation retry package changed after intent"));
    auto written = publish_epoch_record(operation.value(),
        "00-reactivation-intent.staging.v1.json",
        "00-reactivation-intent.v1.json",
        epoch_reactivation_intent_bytes(intent), 3U);
    if (!written) return Result::failure(written.error());
  }
  const auto exact_custody = [&]() {
    auto current = read_epoch_relative_bounded(operation.value(),
        "00-reactivation-intent.v1.json", kMaximumEpochGenesisRecordBytes);
    std::vector<fs::path> current_names;
    const std::string expected_shortcut = epoch_reactivation_cutover_bytes(
        intent, "10-shortcut-cutover", hash(epoch_reactivation_intent_bytes(intent)),
        "shortcut");
    const std::string expected_registration = epoch_reactivation_cutover_bytes(
        intent, "20-registration-cutover", hash(expected_shortcut), "registration");
    if (!operation.value().list_child_names_bounded(4U, current_names).ok() ||
        !epoch_reactivation_record_names(current_names)) return false;
    if (current_names.size() >= 2U) {
      auto marker = read_epoch_relative_bounded(operation.value(), current_names[1],
          kMaximumEpochGenesisRecordBytes);
      if (!marker || marker.value() != expected_shortcut) return false;
    }
    if (current_names.size() >= 3U) {
      auto marker = read_epoch_relative_bounded(operation.value(), current_names[2],
          kMaximumEpochGenesisRecordBytes);
      if (!marker || marker.value() != expected_registration) return false;
    }
    if (!current || current.value() != epoch_reactivation_intent_bytes(intent) ||
        provider_effects.inspect_candidate(transition) != CandidateState::exact)
      return false;
    const EffectResult installed =
        provider_effects.inspect_retained_installed(transition);
    if (!installed.ok || installed.outcome_unknown ||
        installed.receipt_sha256 != intent.target_installed_identity_sha256)
      return false;
    const EffectResult verified = provider_effects.verify_installed(transition);
    return verified.ok && !verified.outcome_unknown &&
        digest(verified.receipt_sha256) &&
        provider_effects.inspect_candidate(transition) == CandidateState::exact &&
        operation.value().revalidate().ok() && maintenance.value().revalidate().ok() &&
        scope.epoch.revalidate().ok() && scope.epochs.revalidate().ok() &&
        scope.coordinator.revalidate().ok();
  };
  if (!exact_custody()) return Result::failure(epoch_recovery(
      "reactivation provider or intent custody changed before native cutover"));
  const std::string shortcut_bytes = epoch_reactivation_cutover_bytes(intent,
      "10-shortcut-cutover", hash(epoch_reactivation_intent_bytes(intent)),
      "shortcut");
  const std::string registration_bytes = epoch_reactivation_cutover_bytes(intent,
      "20-registration-cutover", hash(shortcut_bytes), "registration");
  auto refreshed = operation.value().list_child_names_bounded(4U, names);
  if (!refreshed.ok() || !epoch_reactivation_record_names(names))
    return Result::failure(epoch_recovery(
        "reactivation records changed before native cutover"));
  if (names.size() < 2U || names[1] != fs::path("10-shortcut-cutover.v1.json")) {
    const ShellState shell = shell_effects.inspect_shortcut(transition);
    if (!exact_custody()) return Result::failure(epoch_recovery(
        "reactivation custody changed before shortcut cutover"));
    if (shell == ShellState::old_exact) {
      const EffectResult changed = shell_effects.cutover_shortcut(transition);
      if (!changed.ok || changed.outcome_unknown || !exact_custody())
        return Result::failure(effect_error("self_maintenance_shortcut_failed",
            "reactivation shortcut cutover failed", changed).error());
    } else if (shell != ShellState::new_exact) {
      return Result::failure(epoch_recovery(
          "reactivation shortcut is not exactly source or target owned"));
    }
    if (shell_effects.inspect_shortcut(transition) != ShellState::new_exact ||
        !exact_custody())
      return Result::failure(epoch_recovery(
          "reactivation shortcut did not reach exact target ownership"));
    auto written = publish_epoch_record(operation.value(),
        "10-shortcut-cutover.staging.v1.json",
        "10-shortcut-cutover.v1.json", shortcut_bytes, 3U);
    if (!written) return Result::failure(written.error());
  }
  if (shell_effects.inspect_shortcut(transition) != ShellState::new_exact ||
      !exact_custody())
    return Result::failure(epoch_recovery(
        "reactivation shortcut changed before registration cutover"));
  if (!operation.value().list_child_names_bounded(4U, names).ok() ||
      !epoch_reactivation_record_names(names))
    return Result::failure(epoch_recovery(
        "reactivation records changed before registration cutover"));
  if (names.size() < 3U || names[2] !=
          fs::path("20-registration-cutover.v1.json")) {
    const ShellState shell = shell_effects.inspect_registration(transition);
    if (!exact_custody()) return Result::failure(epoch_recovery(
        "reactivation custody changed before registration cutover"));
    if (shell == ShellState::old_exact) {
      const EffectResult changed = shell_effects.cutover_registration(transition);
      if (!changed.ok || changed.outcome_unknown || !exact_custody())
        return Result::failure(effect_error("self_maintenance_registration_failed",
            "reactivation registration cutover failed", changed).error());
    } else if (shell != ShellState::new_exact) {
      return Result::failure(epoch_recovery(
          "reactivation registration is not exactly source or target owned"));
    }
    if (shell_effects.inspect_registration(transition) != ShellState::new_exact ||
        !exact_custody())
      return Result::failure(epoch_recovery(
          "reactivation registration did not reach exact target ownership"));
    auto written = publish_epoch_record(operation.value(),
        "20-registration-cutover.staging.v1.json",
        "20-registration-cutover.v1.json", registration_bytes, 3U);
    if (!written) return Result::failure(written.error());
  }
  if (shell_effects.inspect_shortcut(transition) != ShellState::new_exact ||
      shell_effects.inspect_registration(transition) != ShellState::new_exact ||
      !exact_custody())
    return Result::failure(epoch_recovery(
        "reactivation native ownership changed before activation"));
  auto activations = open_or_create_epoch_child(scope.epoch, "activations");
  if (!activations) return Result::failure(activations.error());
  const std::string activation_bytes = epoch_link_activation_bytes(epoch,
      intent.operation, intent.operation_id, intent.source_generation_id,
      intent.target_generation_id, intent.target_generation_sha256,
      intent.source_activation_name, intent.source_activation_sha256);
  if (hash(activation_bytes) != intent.target_activation_sha256)
    return Result::failure(epoch_recovery(
        "reactivation activation bytes changed after native cutover"));
  auto written = publish_epoch_record(activations.value(),
      "activation." + intent.operation_id + ".staging.v2.json",
      intent.target_activation_name, activation_bytes,
      kMaximumEpochActivationRecords);
  if (!written) return Result::failure(written.error());
  auto active = discover_lifecycle_epoch_active(request.coordinator_root);
  if (!active || active.value().active.activation_name !=
          intent.target_activation_name ||
      active.value().active.activation_sha256 != intent.target_activation_sha256 ||
      active.value().active.active.generation_id != intent.target_generation_id)
    return Result::failure(!active ? active.error() : epoch_recovery(
        "reactivation did not publish an exact active head"));
  const EffectResult retired = shell_effects.retire_shortcut_backup(transition);
  if (!retired.ok || retired.outcome_unknown || !digest(retired.receipt_sha256) ||
      !exact_custody())
    return Result::failure(effect_error(
        "self_maintenance_shortcut_backup_retirement_failed",
        "reactivation shortcut backup retirement failed", retired).error());
  return Result::success({"reactivation_complete", transition.target, journal});
}

facman::core::Result<EpochTransitionPreparation> prepare_lifecycle_epoch_transition(
    const EpochTransitionRequest &request, EpochPreparationEffects &effects) {
  std::string detail;
  if (!request.coordinator_root.is_absolute() || !digest(request.epoch_id) ||
      !facman::base::validate_identifier(request.operation_id, detail) ||
      (request.operation != Operation::update && request.operation != Operation::downgrade))
    return facman::core::Result<EpochTransitionPreparation>::failure(failure(
        "self_maintenance_input_invalid", "epoch transition identifiers are invalid"));
  if (request.apply && (!request.continuation_helper.is_absolute() ||
      !digest(request.continuation_helper_sha256)))
    return facman::core::Result<EpochTransitionPreparation>::failure(failure(
        "self_maintenance_input_invalid",
        "epoch transition requires an exact current continuation helper"));
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
    if (transition.value().provider_operation != "install_local")
      return facman::core::Result<EpochTransitionPreparation>::failure(failure(
          "self_maintenance_candidate_unsafe",
          "retained predecessor requires verified reactivation, not provider installation"));
    if (effects.inspect_candidate(transition.value()) != CandidateState::absent)
      return facman::core::Result<EpochTransitionPreparation>::failure(failure(
          "self_maintenance_candidate_unsafe", "epoch target generation is not absent"));
    const EffectResult reviewed = effects.review_install_local(transition.value());
    if (!reviewed.ok || reviewed.outcome_unknown || !digest(reviewed.receipt_sha256))
      return facman::core::Result<EpochTransitionPreparation>::failure(failure(
          "self_maintenance_plan_failed", "provider review did not return an exact plan receipt",
          reviewed.detail));
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
  const std::string final_name = "00-handoff-ready.v3.json";
  const std::string staging_name = "00-handoff-ready.staging.v3.json";
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
    if (!retained_inspection ||
        retained_inspection.value().package_sha256 != handoff.inputs.package_sha256)
      return facman::core::Result<EpochTransitionPreparation>::failure(!retained_inspection ?
          retained_inspection.error() : epoch_recovery("retained package provenance changed"));
    notify_retained_inputs_after_initial_validation(checked.value());
    if (!revalidate_retained_inputs(checked.value()))
      return facman::core::Result<EpochTransitionPreparation>::failure(epoch_recovery(
          "retained handoff input changed during preparation"));
    EpochTransitionRequest retained_request{request.coordinator_root, epoch.epoch_id, request.operation,
        request.operation_id, retained_inspection.take_value(), false, {}, {}, true};
    auto planned = make_epoch_transition_plan(epoch, *locked_active.value(), retained_request);
    if (!planned) return facman::core::Result<EpochTransitionPreparation>::failure(planned.error());
    transition = planned.take_value();
    if (transition.provider_operation != "install_local")
      return facman::core::Result<EpochTransitionPreparation>::failure(epoch_recovery(
          "retained handoff changed into a reactivation request"));
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
    if (source_plan.value().provider_operation != "install_local")
      return facman::core::Result<EpochTransitionPreparation>::failure(failure(
          "self_maintenance_candidate_unsafe",
          "retained predecessor requires verified reactivation, not provider installation"));
    if (effects.inspect_candidate(source_plan.value()) != CandidateState::absent)
      return facman::core::Result<EpochTransitionPreparation>::failure(failure(
          "self_maintenance_candidate_unsafe", "epoch target generation is not absent"));
    const EffectResult source_review = effects.review_install_local(source_plan.value());
    if (!source_review.ok || source_review.outcome_unknown || !digest(source_review.receipt_sha256))
      return facman::core::Result<EpochTransitionPreparation>::failure(failure(
          "self_maintenance_plan_failed", "provider review did not return an exact plan receipt",
          source_review.detail));
    auto retained = effects.retain_handoff_inputs(source_plan.value(),
        request.continuation_helper, request.continuation_helper_sha256);
    if (!retained) return facman::core::Result<EpochTransitionPreparation>::failure(retained.error());
    auto checked = validate_retained_inputs(epoch, request.operation_id, retained.value());
    if (!checked || retained.value().package_sha256 != source_plan.value().package_sha256 ||
        retained.value().helper_sha256 != request.continuation_helper_sha256)
      return facman::core::Result<EpochTransitionPreparation>::failure(!checked ? checked.error() :
          epoch_recovery("retained package does not match the reviewed package identity"));
    auto retained_inspection = inspect_package(retained.value().package);
    if (!retained_inspection ||
        retained_inspection.value().package_sha256 != retained.value().package_sha256 ||
        !same_descriptor(retained_inspection.value().descriptor, request.package.descriptor))
      return facman::core::Result<EpochTransitionPreparation>::failure(!retained_inspection ?
          retained_inspection.error() : epoch_recovery("retained package provenance is not exact"));
    notify_retained_inputs_after_initial_validation(checked.value());
    if (!revalidate_retained_inputs(checked.value()))
      return facman::core::Result<EpochTransitionPreparation>::failure(epoch_recovery(
          "retained handoff input changed during preparation"));
    EpochTransitionRequest retained_request{request.coordinator_root, epoch.epoch_id, request.operation,
        request.operation_id, retained_inspection.take_value(), false, {}, {}, true};
    auto planned = make_epoch_transition_plan(epoch, *locked_active.value(), retained_request);
    if (!planned) return facman::core::Result<EpochTransitionPreparation>::failure(planned.error());
    transition = planned.take_value();
    if (transition.provider_operation != "install_local")
      return facman::core::Result<EpochTransitionPreparation>::failure(epoch_recovery(
          "retained package changed into a reactivation request"));
    reviewed = effects.review_install_local(transition);
    if (!reviewed.ok || reviewed.outcome_unknown || !digest(reviewed.receipt_sha256))
      return facman::core::Result<EpochTransitionPreparation>::failure(failure(
          "self_maintenance_plan_failed", "retained provider review did not return an exact plan receipt",
          reviewed.detail));
    facman::platform::RandomIdGenerator generator;
    handoff = {epoch.epoch_id, epoch.manifest_sha256, transition.operation,
        transition.operation_id, transition.source.generation_id,
        transition.previous_activation_name, transition.previous_activation_sha256,
        transition.target.generation_id, retained.take_value(), reviewed.receipt_sha256,
        generator.next("epoch"), request.shell_integration,
        request.deadline_utc_ms};
  }
  if (handoff.epoch_id != epoch.epoch_id || handoff.manifest_sha256 != epoch.manifest_sha256 ||
      handoff.operation != transition.operation || handoff.operation_id != request.operation_id ||
      handoff.source_generation_id != transition.source.generation_id ||
      handoff.source_activation_name != transition.previous_activation_name ||
      handoff.source_activation_sha256 != transition.previous_activation_sha256 ||
      handoff.target_generation_id != transition.target.generation_id ||
      handoff.provider_plan_sha256 != reviewed.receipt_sha256 ||
      handoff.shell_integration != request.shell_integration)
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
  response.deadline_utc_ms = handoff.deadline_utc_ms;
  return facman::core::Result<EpochTransitionPreparation>::success(std::move(response));
}

namespace {

facman::core::Result<Plan> admit_lifecycle_epoch_continuation_impl(
    const fs::path &coordinator_root, const std::string &operation_id,
    const std::string &nonce, const std::string &journal_sha256,
    std::string *admitted_epoch_id) {
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
    if (operation.open_child_file_no_follow_pinned("00-handoff-ready.v3.json", final_record).ok()) {
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
  if (!operation.open_child_file_no_follow_pinned("00-handoff-ready.v3.json", final_journal).ok() ||
      final_journal.size() == 0 || final_journal.size() > kMaximumEpochGenesisRecordBytes)
    return facman::core::Result<Plan>::failure(epoch_recovery(
        "epoch continuation handoff journal is unavailable or unsafe"));
  std::string journal_bytes(static_cast<std::size_t>(final_journal.size()), '\0');
  if (final_journal.read_at(0, journal_bytes.data(), journal_bytes.size()) != journal_bytes.size() ||
      !final_journal.revalidate().ok() || !final_journal.revalidate_path().ok())
    return facman::core::Result<Plan>::failure(epoch_recovery(
        "epoch continuation handoff journal changed while read"));
  notify_epoch_record_pinned(scope.epoch.path() / "maintenance" / operation_id /
                              "00-handoff-ready.v3.json");
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
  if (!inspected ||
      inspected.value().package_sha256 != handoff.value().inputs.package_sha256)
    return facman::core::Result<Plan>::failure(!inspected ? inspected.error() : epoch_recovery(
        "retained package no longer has its journaled identity"));
  notify_retained_inputs_after_initial_validation(retained.value());
  if (!revalidate_retained_inputs(retained.value()))
    return facman::core::Result<Plan>::failure(epoch_recovery(
        "retained continuation input changed during admission"));
  EpochTransitionRequest request{coordinator_root, epoch.epoch_id,
      handoff.value().operation == "update" ? Operation::update : Operation::downgrade,
      operation_id, inspected.take_value(), false, {}, {}, true};
  auto plan = make_epoch_transition_plan(epoch, *active.value(), request);
  if (!plan || plan.value().target.generation_id != handoff.value().target_generation_id)
    return facman::core::Result<Plan>::failure(!plan ? plan.error() : epoch_recovery(
        "epoch continuation target changed from its immutable handoff journal"));
  if (!held_file_matches_bytes(final_journal, journal_bytes) ||
      !revalidate_retained_inputs(retained.value()) || !operation.revalidate().ok() ||
      !scope.epoch.revalidate().ok())
    return facman::core::Result<Plan>::failure(epoch_recovery(
        "epoch continuation journal or retained input changed before return"));
  if (admitted_epoch_id != nullptr) *admitted_epoch_id = epoch.epoch_id;
  return plan;
}

} // namespace

facman::core::Result<Plan> admit_lifecycle_epoch_continuation(
    const fs::path &coordinator_root, const std::string &operation_id,
    const std::string &nonce, const std::string &journal_sha256) {
  return admit_lifecycle_epoch_continuation_impl(coordinator_root, operation_id,
      nonce, journal_sha256, nullptr);
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
      "00-handoff-ready.v3.json", "10-provider-apply-bound.v2.json",
      "20-provider-apply-entered.v2.json", "30-provider-outcome.v2.json",
      "40-provider-verified.v2.json"};
  for (std::size_t index = 0; index < names.size(); ++index) {
    const std::string final_name = allowed[index].string();
    const std::size_t version = final_name.rfind(".v");
    const std::string staging_name = final_name.substr(0, version) + ".staging" +
        final_name.substr(version);
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
  std::string admitted_epoch_id;
  auto admitted = admit_lifecycle_epoch_continuation_impl(request.coordinator_root,
      request.operation_id, request.nonce, request.journal_sha256,
      &admitted_epoch_id);
  if (!admitted) return facman::core::Result<EpochContinuationResponse>::failure(admitted.error());
  Plan transition = admitted.take_value();
  if (!digest(admitted_epoch_id) || transition.target.install_id !=
          epoch_generation_install_id(admitted_epoch_id,
                                      transition.target.generation_id))
    return facman::core::Result<EpochContinuationResponse>::failure(
      epoch_recovery("admitted epoch continuation target has no exact epoch install identity"));
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
  auto handoff_bytes = read_epoch_relative_bounded(operation, "00-handoff-ready.v3.json",
                                                   kMaximumEpochGenesisRecordBytes);
  auto handoff = handoff_bytes ? parse_epoch_handoff(handoff_bytes.value())
      : facman::core::Result<EpochHandoff>::failure(handoff_bytes.error());
  if (!handoff || hash(handoff_bytes.value()) != request.journal_sha256)
    return facman::core::Result<EpochContinuationResponse>::failure(!handoff ? handoff.error() :
        epoch_recovery("epoch continuation handoff changed before provider execution"));
  facman::platform::StableInputFile held_handoff;
  if (!operation.open_child_file_no_follow_pinned("00-handoff-ready.v3.json", held_handoff).ok() ||
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
      if (name == "00-handoff-ready.v3.json") continue;
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
        !exact_names.empty() && exact_names.front() == "00-handoff-ready.v3.json" &&
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
      "00-handoff-ready.v3.json";
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
    if (!custody_valid() ||
        effects.inspect_candidate(transition) != CandidateState::absent ||
        !custody_valid())
      return facman::core::Result<EpochContinuationResponse>::failure(
          epoch_recovery(
              "epoch provider candidate is not absent before input retention"));
    const EffectResult prepared = effects.prepare_install_local(transition);
    if (!custody_valid())
      return facman::core::Result<EpochContinuationResponse>::failure(
          epoch_recovery(
              "epoch custody changed during offline repair input retention"));
    if (!prepared.ok || prepared.outcome_unknown)
      return facman::core::Result<EpochContinuationResponse>::failure(
          effect_error("self_maintenance_source_retention_failed",
                       "epoch candidate installation inputs could not be retained",
                       prepared)
              .error());
    if (effects.inspect_candidate(transition) != CandidateState::absent ||
        !custody_valid())
      return facman::core::Result<EpochContinuationResponse>::failure(
          epoch_recovery(
              "offline repair input retention changed the provider candidate"));
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

namespace {

constexpr std::size_t kMaximumEpochPublicationRecords = 9U;

struct EpochPublicationIdentity {
  std::string epoch_id;
  std::string manifest_sha256;
  std::string handoff_bytes;
  std::string source_generation_bytes;
  std::string source_activation_bytes;
  std::string generation_bytes;
  std::string activation_name;
  std::string activation_bytes;
  std::string binding_bytes;
  std::string outcome_bytes;
  std::string outcome_receipt;
  std::string verified_bytes;
  std::string fifty_bytes;
  std::string sixty_bytes;
  std::string terminal_receipt;
  ProviderApplyBinding binding;
};

struct EpochPublicationAdmission {
  LifecycleEpoch epoch;
  EpochHandoff handoff;
  Plan transition;
  ProviderApplyBinding binding;
  std::string terminal_receipt;
  std::string manifest_bytes;
  std::string handoff_bytes;
  std::string source_generation_bytes;
  std::string source_activation_bytes;
  std::string generation_bytes;
  std::string activation_name;
  std::string activation_staging_name;
  std::string activation_bytes;
  std::string binding_bytes;
  std::string outcome_bytes;
  std::string outcome_receipt;
  std::string verified_bytes;
  std::string fifty_bytes;
  std::string sixty_bytes;
  fs::path journal;
  bool generation_staged = false;
  bool generation_final = false;
  bool fifty_staged = false;
  bool fifty_final = false;
  bool activation_staged = false;
  bool activation_final = false;
  bool sixty_staged = false;
  bool sixty_final = false;
  std::vector<fs::path> operation_names;
  std::vector<fs::path> generation_names;
  std::vector<fs::path> activation_names;
  PinnedLifecycleEpochScope scope;
  facman::platform::StableDirectoryObject maintenance;
  facman::platform::StableDirectoryObject operation;
  facman::platform::StableDirectoryObject generations;
  facman::platform::StableDirectoryObject activations;
  facman::platform::StableInputFile manifest_file;
  facman::platform::StableInputFile handoff_file;
  facman::platform::StableInputFile source_generation_file;
  facman::platform::StableInputFile source_activation_file;
  HeldRetainedInputs retained;
  std::vector<HeldPublicationRecord> operation_records;
  std::vector<HeldPublicationRecord> generation_records;
  std::vector<HeldPublicationRecord> activation_records;
};

bool publication_has(const std::vector<fs::path> &names,
                     const fs::path &name) {
  return std::find(names.begin(), names.end(), name) != names.end();
}

facman::core::Result<void> validate_epoch_publication_names(
    const facman::platform::StableDirectoryObject &operation,
    std::vector<fs::path> &names) {
  if (!operation.list_child_names_bounded(
          kMaximumEpochPublicationRecords + 1U, names).ok() ||
      names.size() < kMaximumEpochContinuationRecords ||
      names.size() > kMaximumEpochPublicationRecords)
    return facman::core::Result<void>::failure(epoch_recovery(
        "epoch publication operation exceeds its exact record bounds"));
  const std::vector<fs::path> finals = {
      "00-handoff-ready.v3.json", "10-provider-apply-bound.v2.json",
      "20-provider-apply-entered.v2.json", "30-provider-outcome.v2.json",
      "40-provider-verified.v2.json", "50-generation-published.v2.json",
      "60-activation-published.v2.json", "70-shortcut-cutover.v2.json",
      "80-registration-cutover.v2.json"};
  for (std::size_t index = 0; index < names.size(); ++index) {
    const fs::path staging = epoch_continuation_staging_name(
        finals[index].string().c_str());
    if (names[index] != finals[index] &&
        !(index + 1U == names.size() && names[index] == staging))
      return facman::core::Result<void>::failure(epoch_recovery(
          "epoch publication operation contains a foreign or out-of-order record"));
  }
  return facman::core::Result<void>::success();
}

std::string epoch_publication_marker_bytes(
    const LifecycleEpoch &epoch, const std::string &handoff_sha256,
    const std::string &phase, const std::string &previous_record_sha256,
    const std::string &record_name, const std::string &record_sha256,
    const std::string &provider_binding_record_sha256,
    const std::string &provider_outcome_record_sha256,
    const std::string &provider_verified_record_sha256,
    const std::string &terminal_receipt_sha256) {
  json::ObjectBuilder marker;
  marker.add_string("schema", "facman.self_epoch_publication.v2");
  marker.add_string("product_id", "facman");
  marker.add_string("phase", phase);
  marker.add_string("epoch_id", epoch.epoch_id);
  marker.add_string("epoch_manifest_sha256", epoch.manifest_sha256);
  marker.add_string("handoff_sha256", handoff_sha256);
  marker.add_string("previous_record_sha256", previous_record_sha256);
  marker.add_string("record_name", record_name);
  marker.add_string("record_sha256", record_sha256);
  marker.add_string("provider_binding_record_sha256",
                    provider_binding_record_sha256);
  marker.add_string("provider_outcome_record_sha256",
                    provider_outcome_record_sha256);
  marker.add_string("provider_verified_record_sha256",
                    provider_verified_record_sha256);
  marker.add_string("terminal_receipt_sha256", terminal_receipt_sha256);
  return marker.serialize() + "\n";
}

facman::core::Result<std::string> locate_epoch_publication(
    const EpochPublicationRequest &request) {
  std::string detail;
  if (!request.coordinator_root.is_absolute() ||
      !facman::base::validate_identifier(request.operation_id, detail) ||
      !facman::base::validate_identifier(request.nonce, detail) ||
      !digest(request.journal_sha256))
    return facman::core::Result<std::string>::failure(failure(
        "self_maintenance_input_invalid",
        "epoch publication identifiers are invalid"));
  facman::platform::StableDirectoryObject coordinator, epochs;
  std::vector<fs::path> epoch_names;
  if (!coordinator.open_no_follow(request.coordinator_root).ok() ||
      !coordinator.open_child_directory_no_follow("epochs", epochs).ok() ||
      !epochs.list_child_names_bounded(kMaximumLifecycleEpochs, epoch_names).ok())
    return facman::core::Result<std::string>::failure(epoch_recovery(
        "epoch publication could not enumerate the held epoch root"));
  std::string found;
  for (const fs::path &entry : epoch_names) {
    if (!digest(entry.string())) continue;
    PinnedLifecycleEpochScope candidate;
    facman::platform::StableDirectoryObject maintenance, operation;
    if (!candidate.open(request.coordinator_root, entry.string()).ok() ||
        !candidate.epoch.open_child_directory_no_follow(
            "maintenance", maintenance).ok() ||
        !maintenance.open_child_directory_no_follow(
            request.operation_id, operation).ok())
      continue;
    facman::platform::StableInputFile handoff;
    if (!operation.open_child_file_no_follow_pinned(
            "00-handoff-ready.v3.json", handoff).ok())
      continue;
    if (!found.empty()) return facman::core::Result<std::string>::failure(
        epoch_recovery("more than one epoch exposes the requested publication"));
    found = entry.string();
  }
  if (found.empty()) return facman::core::Result<std::string>::failure(
      epoch_recovery("epoch publication handoff is unavailable"));
  if (!epochs.revalidate().ok() || !coordinator.revalidate().ok())
    return facman::core::Result<std::string>::failure(epoch_recovery(
        "epoch root changed during publication discovery"));
  return facman::core::Result<std::string>::success(std::move(found));
}

facman::core::Result<HeldPublicationRecord> hold_publication_record(
    const facman::platform::StableDirectoryObject &directory,
    const fs::path &name) {
  HeldPublicationRecord result{name, {}, {}};
  if (!directory.open_child_file_no_follow_pinned(name, result.file).ok() ||
      result.file.size() == 0 ||
      result.file.size() > kMaximumEpochGenesisRecordBytes)
    return facman::core::Result<HeldPublicationRecord>::failure(epoch_recovery(
        "epoch publication record is missing, linked, or over budget"));
  result.bytes.resize(static_cast<std::size_t>(result.file.size()));
  if (result.file.read_at(0, result.bytes.data(), result.bytes.size()) !=
          result.bytes.size() ||
      !result.file.revalidate().ok() || !result.file.revalidate_path().ok())
    return facman::core::Result<HeldPublicationRecord>::failure(epoch_recovery(
        "epoch publication record changed while pinned"));
  return facman::core::Result<HeldPublicationRecord>::success(std::move(result));
}

EpochPublicationIdentity publication_identity(
    const EpochPublicationAdmission &state) {
  return {state.epoch.epoch_id, state.epoch.manifest_sha256,
      state.handoff_bytes, state.source_generation_bytes,
      state.source_activation_bytes, state.generation_bytes,
      state.activation_name, state.activation_bytes, state.binding_bytes,
      state.outcome_bytes, state.outcome_receipt, state.verified_bytes, state.fifty_bytes,
      state.sixty_bytes, state.terminal_receipt, state.binding};
}

bool same_publication_identity(const EpochPublicationIdentity &left,
                               const EpochPublicationIdentity &right) {
  return left.epoch_id == right.epoch_id &&
      left.manifest_sha256 == right.manifest_sha256 &&
      left.handoff_bytes == right.handoff_bytes &&
      left.source_generation_bytes == right.source_generation_bytes &&
      left.source_activation_bytes == right.source_activation_bytes &&
      left.generation_bytes == right.generation_bytes &&
      left.activation_name == right.activation_name &&
      left.activation_bytes == right.activation_bytes &&
      left.binding_bytes == right.binding_bytes &&
      left.outcome_bytes == right.outcome_bytes &&
      left.outcome_receipt == right.outcome_receipt &&
      left.verified_bytes == right.verified_bytes &&
      left.fifty_bytes == right.fifty_bytes &&
      left.sixty_bytes == right.sixty_bytes &&
      left.terminal_receipt == right.terminal_receipt &&
      same_provider_apply_binding(left.binding, right.binding);
}

facman::core::Result<EpochPublicationAdmission> load_epoch_publication(
    const EpochPublicationRequest &request, bool write_capable) {
  auto located = locate_epoch_publication(request);
  if (!located) return facman::core::Result<EpochPublicationAdmission>::failure(
      located.error());
  EpochPublicationAdmission state;
  auto opened = state.scope.open(request.coordinator_root, located.value(),
                                 write_capable);
  if (!opened) return facman::core::Result<EpochPublicationAdmission>::failure(
      opened.error());
  auto manifest = state.scope.read("epoch.v1.json");
  auto epoch = manifest ? parse_lifecycle_manifest(manifest.value(), located.value())
                        : facman::core::Result<LifecycleEpoch>::failure(
                              manifest.error());
  if (!epoch ||
      !state.scope.epoch.open_child_file_no_follow_pinned(
          "epoch.v1.json", state.manifest_file).ok() ||
      !held_file_matches_bytes(state.manifest_file, manifest.value()))
    return facman::core::Result<EpochPublicationAdmission>::failure(!epoch
        ? epoch.error() : epoch_recovery("epoch publication manifest cannot be held"));
  state.epoch = epoch.take_value();
  state.manifest_bytes = manifest.take_value();
  auto open_maintenance = write_capable
      ? state.scope.epoch.open_child_directory_no_follow_for_relative_writes(
            "maintenance", state.maintenance)
      : state.scope.epoch.open_child_directory_no_follow(
            "maintenance", state.maintenance);
  if (!open_maintenance.ok())
    return facman::core::Result<EpochPublicationAdmission>::failure(epoch_recovery(
        "epoch publication maintenance directory is unavailable"));
  auto open_operation = write_capable
      ? state.maintenance.open_child_directory_no_follow_for_relative_writes(
            request.operation_id, state.operation)
      : state.maintenance.open_child_directory_no_follow(
            request.operation_id, state.operation);
  auto open_generations = write_capable
      ? state.scope.epoch.open_child_directory_no_follow_for_relative_writes(
            "generations", state.generations)
      : state.scope.epoch.open_child_directory_no_follow(
            "generations", state.generations);
  auto open_activations = write_capable
      ? state.scope.epoch.open_child_directory_no_follow_for_relative_writes(
            "activations", state.activations)
      : state.scope.epoch.open_child_directory_no_follow(
            "activations", state.activations);
  if (!open_operation.ok() || !open_generations.ok() || !open_activations.ok())
    return facman::core::Result<EpochPublicationAdmission>::failure(epoch_recovery(
        "epoch publication directories are unavailable through held ancestors"));
  auto valid_names = validate_epoch_publication_names(
      state.operation, state.operation_names);
  if (!valid_names)
    return facman::core::Result<EpochPublicationAdmission>::failure(
        valid_names.error());
  if (!state.generations.list_child_names_bounded(
          kMaximumEpochActivationRecords + 1U, state.generation_names).ok() ||
      !state.activations.list_child_names_bounded(
          kMaximumEpochActivationRecords + 1U, state.activation_names).ok())
    return facman::core::Result<EpochPublicationAdmission>::failure(epoch_recovery(
        "epoch publication generation or activation set exceeds its bound"));

  auto handoff = hold_publication_record(
      state.operation, "00-handoff-ready.v3.json");
  auto parsed_handoff = handoff ? parse_epoch_handoff(handoff.value().bytes)
      : facman::core::Result<EpochHandoff>::failure(handoff.error());
  if (!parsed_handoff ||
      hash(handoff.value().bytes) != request.journal_sha256 ||
      parsed_handoff.value().nonce != request.nonce ||
      parsed_handoff.value().operation_id != request.operation_id ||
      parsed_handoff.value().epoch_id != state.epoch.epoch_id ||
      parsed_handoff.value().manifest_sha256 != state.epoch.manifest_sha256)
    return facman::core::Result<EpochPublicationAdmission>::failure(
        !parsed_handoff ? parsed_handoff.error() : epoch_recovery(
            "epoch publication handoff identity changed"));
  state.handoff = parsed_handoff.take_value();
  state.handoff_bytes = handoff.value().bytes;
  state.handoff_file = std::move(handoff.value().file);
  state.journal = state.scope.epoch.path() / "maintenance" /
      request.operation_id / "00-handoff-ready.v3.json";

  auto source = parse_epoch_generation(state.epoch, state.scope,
      state.handoff.source_generation_id, &state.source_generation_bytes);
  auto source_activation = read_epoch_relative_bounded(state.activations,
      state.handoff.source_activation_name, kMaximumEpochGenesisRecordBytes);
  if (!source || !source_activation ||
      hash(source_activation.value()) != state.handoff.source_activation_sha256 ||
      !state.generations.open_child_file_no_follow_pinned(
          epoch_generation_name(state.handoff.source_generation_id),
          state.source_generation_file).ok() ||
      !state.activations.open_child_file_no_follow_pinned(
          state.handoff.source_activation_name,
          state.source_activation_file).ok() ||
      !held_file_matches_bytes(state.source_generation_file,
                               state.source_generation_bytes) ||
      !held_file_matches_bytes(state.source_activation_file,
                               source_activation.value()))
    return facman::core::Result<EpochPublicationAdmission>::failure(!source
        ? source.error() : epoch_recovery(
            "epoch publication source records cannot be held"));
  state.source_activation_bytes = source_activation.take_value();

  auto retained = validate_retained_inputs(
      state.epoch, request.operation_id, state.handoff.inputs);
  auto package = retained ? inspect_package(state.handoff.inputs.package)
                          : facman::core::Result<PackageInspection>::failure(
                                retained.error());
  if (!retained || !package ||
      package.value().package_sha256 != state.handoff.inputs.package_sha256)
    return facman::core::Result<EpochPublicationAdmission>::failure(!retained
        ? retained.error() : (!package ? package.error() : epoch_recovery(
            "epoch publication retained package identity changed")));
  ActiveState source_state{source.take_value(), {},
      state.handoff.source_activation_name,
      state.handoff.source_activation_sha256};
  EpochTransitionRequest transition_request{request.coordinator_root,
      state.epoch.epoch_id,
      state.handoff.operation == "update" ? Operation::update
                                           : Operation::downgrade,
      request.operation_id, package.take_value(), false, {}, {}, true};
  auto transition = make_epoch_transition_plan(
      state.epoch, source_state, transition_request);
  if (!transition ||
      transition.value().target.generation_id !=
          state.handoff.target_generation_id ||
      transition.value().source.generation_id !=
          state.handoff.source_generation_id ||
      transition.value().previous_activation_name !=
          state.handoff.source_activation_name ||
      transition.value().previous_activation_sha256 !=
          state.handoff.source_activation_sha256)
    return facman::core::Result<EpochPublicationAdmission>::failure(!transition
        ? transition.error() : epoch_recovery(
            "epoch publication target changed from its immutable handoff"));
  state.transition = transition.take_value();
  state.retained = retained.take_value();
  notify_retained_inputs_after_initial_validation(state.retained);
  if (!revalidate_retained_inputs(state.retained))
    return facman::core::Result<EpochPublicationAdmission>::failure(epoch_recovery(
        "epoch publication retained inputs changed during admission"));

  std::string outcome, verified_receipt;
  std::string bound_record_bytes, verified_record_bytes;
  for (const auto &entry : std::vector<std::pair<const char *, const char *>>{
           {"10-provider-apply-bound.v2.json", "10-provider-apply-bound"},
           {"20-provider-apply-entered.v2.json", "20-provider-apply-entered"},
           {"30-provider-outcome.v2.json", "30-provider-outcome"},
           {"40-provider-verified.v2.json", "40-provider-verified"}}) {
    auto held = hold_publication_record(state.operation, entry.first);
    std::string receipt, recorded_outcome;
    auto parsed = held ? parse_epoch_continuation_record(held.value().bytes,
        state.epoch, state.handoff, request.journal_sha256, entry.second,
        &receipt, &recorded_outcome)
        : facman::core::Result<ProviderApplyBinding>::failure(held.error());
    if (!parsed || (!state.binding.transaction_id.empty() &&
        !same_provider_apply_binding(state.binding, parsed.value())))
      return facman::core::Result<EpochPublicationAdmission>::failure(!parsed
          ? parsed.error() : epoch_recovery(
              "epoch publication provider binding changed between phases"));
    state.binding = parsed.take_value();
    if (std::string(entry.second) == "10-provider-apply-bound")
      bound_record_bytes = held.value().bytes;
    if (std::string(entry.second) == "30-provider-outcome") {
      state.outcome_receipt = receipt;
      state.outcome_bytes = held.value().bytes;
      outcome = recorded_outcome;
    }
    if (std::string(entry.second) == "40-provider-verified") {
      verified_receipt = receipt;
      verified_record_bytes = held.value().bytes;
    }
    state.operation_records.push_back(held.take_value());
  }
  if (outcome != "installed" || !digest(state.outcome_receipt) ||
      !digest(verified_receipt))
    return facman::core::Result<EpochPublicationAdmission>::failure(epoch_recovery(
        "epoch publication requires exact installed and verified provider outcomes"));
  state.terminal_receipt = verified_receipt;
  state.binding_bytes = bound_record_bytes;
  state.verified_bytes = verified_record_bytes;
  state.generation_bytes = epoch_generation_bytes(
      state.epoch, state.transition.target);
  state.activation_name = "activation." + request.operation_id + ".v2.json";
  state.activation_staging_name =
      "activation." + request.operation_id + ".staging.v2.json";
  state.activation_bytes = epoch_link_activation_bytes(state.epoch,
      state.transition.operation, request.operation_id,
      state.handoff.source_generation_id,
      state.transition.target.generation_id,
      hash(state.generation_bytes), state.handoff.source_activation_name,
      state.handoff.source_activation_sha256);
  const std::string binding_record_sha256 = hash(bound_record_bytes);
  const std::string outcome_record_sha256 = hash(state.outcome_bytes);
  const std::string verified_record_sha256 = hash(verified_record_bytes);
  state.fifty_bytes = epoch_publication_marker_bytes(state.epoch,
      request.journal_sha256, "50-generation-published",
      verified_record_sha256,
      epoch_generation_name(state.transition.target.generation_id),
      hash(state.generation_bytes), binding_record_sha256,
      outcome_record_sha256, verified_record_sha256, state.terminal_receipt);
  state.sixty_bytes = epoch_publication_marker_bytes(state.epoch,
      request.journal_sha256, "60-activation-published",
      hash(state.fifty_bytes), state.activation_name,
      hash(state.activation_bytes), binding_record_sha256,
      outcome_record_sha256, verified_record_sha256, state.terminal_receipt);

  const fs::path generation_final = epoch_generation_name(
      state.transition.target.generation_id);
  const fs::path generation_staging = epoch_generation_staging_name(
      state.transition.target.generation_id);
  state.generation_staged = publication_has(
      state.generation_names, generation_staging);
  state.generation_final = publication_has(
      state.generation_names, generation_final);
  state.fifty_staged = publication_has(state.operation_names,
      "50-generation-published.staging.v2.json");
  state.fifty_final = publication_has(state.operation_names,
      "50-generation-published.v2.json");
  state.activation_staged = publication_has(state.activation_names,
      state.activation_staging_name);
  state.activation_final = publication_has(state.activation_names,
      state.activation_name);
  state.sixty_staged = publication_has(state.operation_names,
      "60-activation-published.staging.v2.json");
  state.sixty_final = publication_has(state.operation_names,
      "60-activation-published.v2.json");
  if ((state.generation_staged && state.generation_final) ||
      (state.fifty_staged && state.fifty_final) ||
      (state.activation_staged && state.activation_final) ||
      (state.sixty_staged && state.sixty_final) ||
      ((state.fifty_staged || state.fifty_final ||
        state.activation_staged || state.activation_final ||
        state.sixty_staged || state.sixty_final) &&
       !state.generation_final) ||
      ((state.activation_staged || state.activation_final ||
        state.sixty_staged || state.sixty_final) &&
       !state.fifty_final) ||
      ((state.sixty_staged || state.sixty_final) &&
       !state.activation_final))
    return facman::core::Result<EpochPublicationAdmission>::failure(epoch_recovery(
        "epoch publication records are conflicting or out of order"));
  if (state.generation_staged) {
    auto bytes = read_epoch_relative_bounded(state.generations,
        generation_staging, kMaximumEpochGenesisRecordBytes);
    if (!bytes || bytes.value() != state.generation_bytes)
      return facman::core::Result<EpochPublicationAdmission>::failure(epoch_recovery(
          "epoch publication generation staging is partial or foreign"));
  }
  if (state.generation_final) {
    auto bytes = read_epoch_relative_bounded(state.generations,
        generation_final, kMaximumEpochGenesisRecordBytes);
    if (!bytes || bytes.value() != state.generation_bytes)
      return facman::core::Result<EpochPublicationAdmission>::failure(epoch_recovery(
          "epoch publication generation record is foreign"));
  }
  const auto exact_operation_record = [&](const fs::path &name,
                                          const std::string &bytes) {
    auto observed = read_epoch_relative_bounded(
        state.operation, name, kMaximumEpochGenesisRecordBytes);
    return observed && observed.value() == bytes;
  };
  const auto exact_activation_record = [&](const fs::path &name,
                                           const std::string &bytes) {
    auto observed = read_epoch_relative_bounded(
        state.activations, name, kMaximumEpochGenesisRecordBytes);
    return observed && observed.value() == bytes;
  };
  if ((state.fifty_staged && !exact_operation_record(
          "50-generation-published.staging.v2.json", state.fifty_bytes)) ||
      (state.fifty_final && !exact_operation_record(
          "50-generation-published.v2.json", state.fifty_bytes)) ||
      (state.activation_staged && !exact_activation_record(
          state.activation_staging_name, state.activation_bytes)) ||
      (state.activation_final && !exact_activation_record(
          state.activation_name, state.activation_bytes)) ||
      (state.sixty_staged && !exact_operation_record(
          "60-activation-published.staging.v2.json", state.sixty_bytes)) ||
      (state.sixty_final && !exact_operation_record(
          "60-activation-published.v2.json", state.sixty_bytes)))
    return facman::core::Result<EpochPublicationAdmission>::failure(epoch_recovery(
        "epoch publication marker or target record has foreign bytes"));

  PendingEpochTransitionState pending{state.transition.target,
      generation_staging, state.activation_name,
      state.activation_staging_name, state.activation_bytes};
  auto chain = discover_lifecycle_epoch_chain_impl(request.coordinator_root,
      {}, nullptr, request.operation_id, state.epoch.epoch_id, &pending);
  auto active = chain ? discover_epoch_genesis_state(state.epoch, state.scope,
      nullptr, false, &request.operation_id, &pending)
      : facman::core::Result<std::optional<ActiveState>>::failure(chain.error());
  if (!chain || chain.value().epochs.empty() ||
      chain.value().epochs.back().epoch_id != state.epoch.epoch_id ||
      chain.value().epochs.back().manifest_sha256 != state.epoch.manifest_sha256 ||
      !active || !active.value().has_value())
    return facman::core::Result<EpochPublicationAdmission>::failure(!chain
        ? chain.error() : (!active ? active.error() : epoch_recovery(
            "epoch publication has no exact active lifecycle head")));
  const ActiveState &head = *active.value();
  if ((state.activation_final &&
       (head.active.generation_id != state.transition.target.generation_id ||
        head.activation_name != state.activation_name ||
        head.activation_sha256 != hash(state.activation_bytes))) ||
      (!state.activation_final &&
       (head.active.generation_id != state.handoff.source_generation_id ||
        head.activation_name != state.handoff.source_activation_name ||
        head.activation_sha256 != state.handoff.source_activation_sha256)))
    return facman::core::Result<EpochPublicationAdmission>::failure(epoch_recovery(
        "epoch publication active head is not the exact source or target phase"));

  for (const fs::path &name : state.operation_names) {
    if (name == "00-handoff-ready.v3.json" ||
        (name >= fs::path("10-provider-apply-bound.v2.json") &&
         name <= fs::path("40-provider-verified.v2.json")))
      continue;
    auto held = hold_publication_record(state.operation, name);
    if (!held) return facman::core::Result<EpochPublicationAdmission>::failure(
        held.error());
    state.operation_records.push_back(held.take_value());
  }
  for (const fs::path &name : state.generation_names) {
    auto held = hold_publication_record(state.generations, name);
    if (!held) return facman::core::Result<EpochPublicationAdmission>::failure(
        held.error());
    state.generation_records.push_back(held.take_value());
  }
  for (const fs::path &name : state.activation_names) {
    auto held = hold_publication_record(state.activations, name);
    if (!held) return facman::core::Result<EpochPublicationAdmission>::failure(
        held.error());
    state.activation_records.push_back(held.take_value());
  }
  if (!revalidate_retained_inputs(state.retained) ||
      !state.operation.revalidate().ok() ||
      !state.generations.revalidate().ok() ||
      !state.activations.revalidate().ok() ||
      !state.maintenance.revalidate().ok() ||
      !state.scope.epoch.revalidate().ok() ||
      !state.scope.epochs.revalidate().ok() ||
      !state.scope.coordinator.revalidate().ok())
    return facman::core::Result<EpochPublicationAdmission>::failure(epoch_recovery(
        "epoch publication custody changed during admission"));
  return facman::core::Result<EpochPublicationAdmission>::success(
      std::move(state));
}

bool publication_custody_valid(EpochPublicationAdmission &state,
                               const EpochPublicationRequest &request) {
  std::vector<fs::path> operation_names, generation_names, activation_names;
  PendingEpochTransitionState pending{state.transition.target,
      epoch_generation_staging_name(state.transition.target.generation_id),
      state.activation_name, state.activation_staging_name,
      state.activation_bytes};
  auto chain = discover_lifecycle_epoch_chain_impl(request.coordinator_root,
      {}, nullptr, request.operation_id, state.epoch.epoch_id, &pending);
  auto active = chain ? discover_epoch_genesis_state(state.epoch, state.scope,
      nullptr, false, &request.operation_id, &pending)
      : facman::core::Result<std::optional<ActiveState>>::failure(chain.error());
  const bool expected_head = active && active.value() &&
      (state.activation_final
          ? (active.value()->active.generation_id ==
                 state.transition.target.generation_id &&
             active.value()->activation_name == state.activation_name &&
             active.value()->activation_sha256 == hash(state.activation_bytes))
          : (active.value()->active.generation_id ==
                 state.handoff.source_generation_id &&
             active.value()->activation_name ==
                 state.handoff.source_activation_name &&
             active.value()->activation_sha256 ==
                 state.handoff.source_activation_sha256));
  return chain && !chain.value().epochs.empty() &&
      chain.value().epochs.back().epoch_id == state.epoch.epoch_id &&
      chain.value().epochs.back().manifest_sha256 ==
          state.epoch.manifest_sha256 && expected_head &&
      validate_epoch_publication_names(state.operation, operation_names).ok() &&
      operation_names == state.operation_names &&
      state.generations.list_child_names_bounded(
          kMaximumEpochActivationRecords + 1U, generation_names).ok() &&
      generation_names == state.generation_names &&
      state.activations.list_child_names_bounded(
          kMaximumEpochActivationRecords + 1U, activation_names).ok() &&
      activation_names == state.activation_names &&
      held_file_matches_bytes(state.manifest_file, state.manifest_bytes) &&
      held_file_matches_bytes(state.handoff_file, state.handoff_bytes) &&
      held_file_matches_bytes(state.source_generation_file,
                              state.source_generation_bytes) &&
      held_file_matches_bytes(state.source_activation_file,
                              state.source_activation_bytes) &&
      std::all_of(state.operation_records.begin(),
                  state.operation_records.end(),
          [](HeldPublicationRecord &record) {
            return held_file_matches_bytes(record.file, record.bytes);
          }) &&
      std::all_of(state.generation_records.begin(),
                  state.generation_records.end(),
          [](HeldPublicationRecord &record) {
            return held_file_matches_bytes(record.file, record.bytes);
          }) &&
      std::all_of(state.activation_records.begin(),
                  state.activation_records.end(),
          [](HeldPublicationRecord &record) {
            return held_file_matches_bytes(record.file, record.bytes);
          }) &&
      revalidate_retained_inputs(state.retained) &&
      state.operation.revalidate().ok() &&
      state.generations.revalidate().ok() &&
      state.activations.revalidate().ok() &&
      state.maintenance.revalidate().ok() &&
      state.scope.epoch.revalidate().ok() &&
      state.scope.epochs.revalidate().ok() &&
      state.scope.coordinator.revalidate().ok();
}

std::string epoch_publication_phase(const EpochPublicationAdmission &state) {
  if (state.sixty_final) return "epoch_activated";
  if (state.sixty_staged || state.activation_final || state.activation_staged)
    return "activation_pending";
  if (state.fifty_final || state.fifty_staged || state.generation_final ||
      state.generation_staged)
    return "generation_pending";
  return "plan";
}

} // namespace

facman::core::Result<EpochPublicationResponse>
execute_lifecycle_epoch_publication(const EpochPublicationRequest &request,
                                    EpochPublicationEffects &effects) {
  EpochPublicationIdentity observed_identity;
  fs::path observed_acceptance_root;
  {
    auto observed = load_epoch_publication(request, false);
    if (!observed)
      return facman::core::Result<EpochPublicationResponse>::failure(
          observed.error());
    if (!request.apply) {
      if (!publication_custody_valid(observed.value(), request))
        return facman::core::Result<EpochPublicationResponse>::failure(
            epoch_recovery("epoch publication custody changed during preview"));
      return facman::core::Result<EpochPublicationResponse>::success(
          {epoch_publication_phase(observed.value()),
           observed.value().transition.target, observed.value().journal});
    }
    observed_identity = publication_identity(observed.value());
    observed_acceptance_root = observed.value().epoch.acceptance_root;
  }
  auto authority = admit_coordinator(request.coordinator_root,
      observed_acceptance_root, false);
  if (!authority)
    return facman::core::Result<EpochPublicationResponse>::failure(
        authority.error());
  auto lock = acquire(authority.take_value(), request.operation_id);
  if (!lock)
    return facman::core::Result<EpochPublicationResponse>::failure(lock.error());
  auto locked = load_epoch_publication(request, true);
  if (!locked || !same_publication_identity(
          observed_identity, publication_identity(locked.value())))
    return facman::core::Result<EpochPublicationResponse>::failure(!locked
        ? locked.error() : epoch_recovery(
            "epoch publication identity changed across lock acquisition"));
  EpochPublicationAdmission state = locked.take_value();
  const EpochPublicationIdentity immutable = publication_identity(state);
  if (!publication_custody_valid(state, request))
    return facman::core::Result<EpochPublicationResponse>::failure(epoch_recovery(
        "epoch publication custody changed before installed inspection"));
  const EffectResult installed = effects.inspect_installed(
      state.transition, state.binding);
  if (!publication_custody_valid(state, request))
    return facman::core::Result<EpochPublicationResponse>::failure(epoch_recovery(
        "epoch publication custody changed during installed inspection"));
  if (!installed.ok || installed.outcome_unknown ||
      installed.receipt_sha256 != state.outcome_receipt)
    return facman::core::Result<EpochPublicationResponse>::failure(effect_error(
        "self_maintenance_inspect_failed",
        "durable provider outcome is not reproducible before publication",
        installed).error());
  if (!publication_custody_valid(state, request))
    return facman::core::Result<EpochPublicationResponse>::failure(epoch_recovery(
        "epoch publication custody changed before terminal verification"));
  const EffectResult terminal = effects.validate_terminal_verification(
      state.transition, state.binding, state.terminal_receipt);
  if (!publication_custody_valid(state, request))
    return facman::core::Result<EpochPublicationResponse>::failure(epoch_recovery(
        "epoch publication custody changed during terminal verification"));
  if (!terminal.ok || terminal.outcome_unknown ||
      terminal.receipt_sha256 != state.terminal_receipt)
    return facman::core::Result<EpochPublicationResponse>::failure(effect_error(
        "self_maintenance_verify_failed",
        "epoch terminal verification changed before publication",
        terminal).error());

  const auto reload = [&]() -> facman::core::Result<void> {
    auto refreshed = load_epoch_publication(request, true);
    if (!refreshed || !same_publication_identity(
            immutable, publication_identity(refreshed.value())))
      return facman::core::Result<void>::failure(!refreshed
          ? refreshed.error() : epoch_recovery(
              "epoch publication identity changed after a durable boundary"));
    state = refreshed.take_value();
    return facman::core::Result<void>::success();
  };

  if (!state.generation_final) {
    if (!publication_custody_valid(state, request))
      return facman::core::Result<EpochPublicationResponse>::failure(
          epoch_recovery("epoch custody changed before generation publication"));
    state.generation_records.clear();
    auto written = publish_epoch_record(state.generations,
        epoch_generation_staging_name(state.transition.target.generation_id),
        epoch_generation_name(state.transition.target.generation_id),
        state.generation_bytes, kMaximumEpochActivationRecords);
    if (!written)
      return facman::core::Result<EpochPublicationResponse>::failure(
          written.error());
    auto refreshed = reload();
    if (!refreshed || !state.generation_final)
      return facman::core::Result<EpochPublicationResponse>::failure(!refreshed
          ? refreshed.error() : epoch_recovery(
              "epoch generation did not reach its exact final state"));
  }
  if (!state.fifty_final) {
    if (!publication_custody_valid(state, request))
      return facman::core::Result<EpochPublicationResponse>::failure(
          epoch_recovery("epoch custody changed before phase 50"));
    state.operation_records.clear();
    auto written = publish_epoch_record(state.operation,
        "50-generation-published.staging.v2.json",
        "50-generation-published.v2.json", state.fifty_bytes,
        kMaximumEpochPublicationRecords);
    if (!written)
      return facman::core::Result<EpochPublicationResponse>::failure(
          written.error());
    auto refreshed = reload();
    if (!refreshed || !state.fifty_final)
      return facman::core::Result<EpochPublicationResponse>::failure(!refreshed
          ? refreshed.error() : epoch_recovery(
              "epoch phase 50 did not reach its exact final state"));
  }
  if (!state.activation_final) {
    if (!publication_custody_valid(state, request))
      return facman::core::Result<EpochPublicationResponse>::failure(
          epoch_recovery("epoch custody changed before activation publication"));
    state.activation_records.clear();
    auto written = publish_epoch_record(state.activations,
        state.activation_staging_name, state.activation_name,
        state.activation_bytes, kMaximumEpochActivationRecords);
    if (!written)
      return facman::core::Result<EpochPublicationResponse>::failure(
          written.error());
    auto refreshed = reload();
    if (!refreshed || !state.activation_final)
      return facman::core::Result<EpochPublicationResponse>::failure(!refreshed
          ? refreshed.error() : epoch_recovery(
              "epoch activation did not reach its exact final state"));
  }
  if (!state.sixty_final) {
    if (!publication_custody_valid(state, request))
      return facman::core::Result<EpochPublicationResponse>::failure(
          epoch_recovery("epoch custody changed before phase 60"));
    state.operation_records.clear();
    auto written = publish_epoch_record(state.operation,
        "60-activation-published.staging.v2.json",
        "60-activation-published.v2.json", state.sixty_bytes,
        kMaximumEpochPublicationRecords);
    if (!written)
      return facman::core::Result<EpochPublicationResponse>::failure(
          written.error());
    auto refreshed = reload();
    if (!refreshed || !state.sixty_final)
      return facman::core::Result<EpochPublicationResponse>::failure(!refreshed
          ? refreshed.error() : epoch_recovery(
              "epoch phase 60 did not reach its exact final state"));
  }
  if (!publication_custody_valid(state, request) ||
      !state.generations.flush_metadata().ok() ||
      !state.activations.flush_metadata().ok() ||
      !state.operation.flush_metadata().ok() ||
      !state.maintenance.flush_metadata().ok() ||
      !state.scope.epoch.flush_metadata().ok() ||
      !state.scope.epochs.flush_metadata().ok() ||
      !state.scope.coordinator.flush_metadata().ok())
    return facman::core::Result<EpochPublicationResponse>::failure(epoch_recovery(
        "epoch publication final custody or directory flush failed"));
  return facman::core::Result<EpochPublicationResponse>::success(
      {"epoch_activated", state.transition.target, state.journal});
}

namespace {

std::string epoch_shell_cutover_marker_bytes(
    const EpochPublicationAdmission &state, const std::string &phase,
    const std::string &previous_record_sha256, const std::string &effect) {
  const std::string ownership_receipt = hash(
      "facman.self_epoch_shell_ownership.v1\n" + state.epoch.epoch_id + "\n" +
      hash(state.handoff_bytes) + "\n" +
      epoch_generation_name(state.transition.target.generation_id) + "\n" +
      hash(state.generation_bytes) + "\n" + state.activation_name + "\n" +
      hash(state.activation_bytes) + "\n" + effect + "\nnew_exact\n");
  json::ObjectBuilder marker;
  marker.add_string("schema", "facman.self_epoch_shell_cutover.v2");
  marker.add_string("product_id", "facman");
  marker.add_string("phase", phase);
  marker.add_string("epoch_id", state.epoch.epoch_id);
  marker.add_string("epoch_manifest_sha256", state.epoch.manifest_sha256);
  marker.add_string("handoff_sha256", hash(state.handoff_bytes));
  marker.add_string("operation_id", state.handoff.operation_id);
  marker.add_string("previous_record_sha256", previous_record_sha256);
  marker.add_string("effect", effect);
  marker.add_string("target_generation_id", state.transition.target.generation_id);
  marker.add_string("target_generation_name",
                    epoch_generation_name(state.transition.target.generation_id));
  marker.add_string("target_generation_sha256", hash(state.generation_bytes));
  marker.add_string("target_activation_name", state.activation_name);
  marker.add_string("target_activation_sha256", hash(state.activation_bytes));
  marker.add_string("provider_binding_record_sha256", hash(state.binding_bytes));
  marker.add_string("provider_outcome_record_sha256", hash(state.outcome_bytes));
  marker.add_string("provider_verified_record_sha256", hash(state.verified_bytes));
  marker.add_string("provider_terminal_receipt_sha256", state.terminal_receipt);
  marker.add_string("ownership", "new_exact");
  marker.add_string("ownership_receipt_sha256", ownership_receipt);
  return marker.serialize() + "\n";
}

bool completed_epoch_shell_cutover(const LifecycleEpoch &epoch,
    const PinnedLifecycleEpochScope &scope,
    const fs::path &operation_name,
    CompletedEpochShellCutover &completed) {
  CompletedEpochShellCutover candidate;
  if (!scope.epoch.open_child_directory_no_follow(
          "maintenance", candidate.maintenance).ok() ||
      !candidate.maintenance.list_child_names_bounded(
          kMaximumEpochActivationRecords + 1U, candidate.operation_names).ok() ||
      std::find(candidate.operation_names.begin(), candidate.operation_names.end(),
                operation_name) == candidate.operation_names.end()) return false;
  if (!candidate.maintenance.open_child_directory_no_follow(
          operation_name, candidate.operation).ok() ||
      !candidate.operation.list_child_names_bounded(
          10U, candidate.record_names).ok()) return false;
  const std::vector<fs::path> reactivation_names = {
      "00-reactivation-intent.v1.json", "10-shortcut-cutover.v1.json",
      "20-registration-cutover.v1.json"};
  if (candidate.record_names == reactivation_names) {
    candidate.records.reserve(reactivation_names.size());
    for (const fs::path &name : reactivation_names) {
      auto held = hold_publication_record(candidate.operation, name);
      if (!held) return false;
      notify_epoch_record_pinned(candidate.operation.path() / name);
      candidate.records.push_back(held.take_value());
    }
    const std::string &intent_bytes = candidate.records[0].bytes;
    auto intent = parse_epoch_reactivation_intent(intent_bytes, epoch, operation_name);
    if (!intent) return false;
    std::string target_bytes;
    auto target = parse_epoch_generation(epoch, scope,
        intent.value().target_generation_id, &target_bytes);
    if (!target || hash(target_bytes) != intent.value().target_generation_sha256 ||
        target.value().package_sha256 != intent.value().target_package_sha256)
      return false;
    std::string source_bytes;
    auto source = parse_epoch_generation(epoch, scope,
        intent.value().source_generation_id, &source_bytes);
    Semver source_version, target_version;
    if (!source || !semver(source.value().product_version, source_version) ||
        !semver(target.value().product_version, target_version) ||
        (intent.value().operation == "update" &&
            compare(target_version, source_version) <= 0) ||
        (intent.value().operation == "downgrade" &&
            compare(target_version, source_version) >= 0) ||
        (intent.value().operation == "rollback" &&
            intent.value().source_generation_id == intent.value().target_generation_id))
      return false;
    facman::platform::StableDirectoryObject activations;
    if (!scope.epoch.open_child_directory_no_follow("activations", activations).ok())
      return false;
    auto source_activation = read_epoch_relative_bounded(activations,
        intent.value().source_activation_name, kMaximumEpochGenesisRecordBytes);
    if (!source_activation || hash(source_activation.value()) !=
            intent.value().source_activation_sha256) return false;
    const std::string activation_bytes = epoch_link_activation_bytes(epoch,
        intent.value().operation, intent.value().operation_id,
        intent.value().source_generation_id, intent.value().target_generation_id,
        intent.value().target_generation_sha256,
        intent.value().source_activation_name,
        intent.value().source_activation_sha256);
    auto target_activation = read_epoch_relative_bounded(activations,
        intent.value().target_activation_name, kMaximumEpochGenesisRecordBytes);
    if (!target_activation || target_activation.value() != activation_bytes ||
        hash(activation_bytes) != intent.value().target_activation_sha256 ||
        !activations.revalidate().ok())
      return false;
    const std::string shortcut_bytes = epoch_reactivation_cutover_bytes(
        intent.value(), "10-shortcut-cutover", hash(intent_bytes), "shortcut");
    const std::string registration_bytes = epoch_reactivation_cutover_bytes(
        intent.value(), "20-registration-cutover", hash(shortcut_bytes), "registration");
    if (candidate.records[1].bytes != shortcut_bytes ||
        candidate.records[2].bytes != registration_bytes) return false;
    candidate.operation_id = intent.value().operation_id;
    candidate.activation_name = intent.value().target_activation_name;
    candidate.activation_sha256 = intent.value().target_activation_sha256;
    candidate.source_activation_name = intent.value().source_activation_name;
    candidate.source_activation_sha256 = intent.value().source_activation_sha256;
    candidate.source_generation_id = intent.value().source_generation_id;
    candidate.generation_id = intent.value().target_generation_id;
    candidate.reactivation = true;
    if (!revalidate_completed_epoch_shell_cutover(candidate, scope)) return false;
    completed = std::move(candidate);
    return true;
  }
  const std::vector<fs::path> expected_names = {
      "00-handoff-ready.v3.json", "10-provider-apply-bound.v2.json",
      "20-provider-apply-entered.v2.json", "30-provider-outcome.v2.json",
      "40-provider-verified.v2.json", "50-generation-published.v2.json",
      "60-activation-published.v2.json", "70-shortcut-cutover.v2.json",
      "80-registration-cutover.v2.json"};
  if (candidate.record_names != expected_names) return false;
  candidate.records.reserve(expected_names.size());
  for (const fs::path &name : expected_names) {
    auto held = hold_publication_record(candidate.operation, name);
    if (!held) return false;
    notify_epoch_record_pinned(candidate.operation.path() / name);
    candidate.records.push_back(held.take_value());
  }
  const auto read = [&](const char *name) {
    for (const auto &record : candidate.records)
      if (record.name == fs::path(name))
        return facman::core::Result<std::string>::success(record.bytes);
    return facman::core::Result<std::string>::failure(epoch_recovery(
        "completed epoch shell record is unavailable"));
  };
  auto handoff_bytes = read("00-handoff-ready.v3.json");
  auto handoff = handoff_bytes ? parse_epoch_handoff(handoff_bytes.value())
      : facman::core::Result<EpochHandoff>::failure(handoff_bytes.error());
  if (!handoff || handoff.value().epoch_id != epoch.epoch_id ||
      handoff.value().manifest_sha256 != epoch.manifest_sha256 ||
      handoff.value().operation_id != operation_name.string()) return false;
  const std::string handoff_sha = hash(handoff_bytes.value());
  ProviderApplyBinding binding;
  std::string outcome, outcome_receipt, terminal_receipt;
  std::string bound_bytes, outcome_bytes, verified_bytes;
  for (const auto &entry : std::vector<std::pair<const char *, const char *>>{
           {"10-provider-apply-bound.v2.json", "10-provider-apply-bound"},
           {"20-provider-apply-entered.v2.json", "20-provider-apply-entered"},
           {"30-provider-outcome.v2.json", "30-provider-outcome"},
           {"40-provider-verified.v2.json", "40-provider-verified"}}) {
    auto bytes = read(entry.first);
    std::string receipt, recorded_outcome;
    auto parsed = bytes ? parse_epoch_continuation_record(bytes.value(), epoch,
        handoff.value(), handoff_sha, entry.second, &receipt, &recorded_outcome)
        : facman::core::Result<ProviderApplyBinding>::failure(bytes.error());
    if (!parsed || (!binding.transaction_id.empty() &&
        !same_provider_apply_binding(binding, parsed.value()))) return false;
    binding = parsed.take_value();
    if (std::string(entry.second) == "10-provider-apply-bound") bound_bytes = bytes.value();
    if (std::string(entry.second) == "30-provider-outcome") {
      outcome = recorded_outcome; outcome_receipt = receipt; outcome_bytes = bytes.value();
    }
    if (std::string(entry.second) == "40-provider-verified") {
      terminal_receipt = receipt; verified_bytes = bytes.value();
    }
  }
  if (outcome != "installed" || !digest(outcome_receipt) || !digest(terminal_receipt)) return false;
  std::string generation_bytes;
  auto target = parse_epoch_generation(epoch, scope, handoff.value().target_generation_id,
                                       &generation_bytes);
  if (!target || hash(generation_bytes).empty()) return false;
  const std::string activation_name = "activation." + handoff.value().operation_id + ".v2.json";
  const std::string activation_bytes = epoch_link_activation_bytes(epoch,
      handoff.value().operation,
      handoff.value().operation_id, handoff.value().source_generation_id,
      target.value().generation_id, hash(generation_bytes), handoff.value().source_activation_name,
      handoff.value().source_activation_sha256);
  const std::string fifty = epoch_publication_marker_bytes(epoch, handoff_sha,
      "50-generation-published", hash(verified_bytes),
      epoch_generation_name(target.value().generation_id), hash(generation_bytes),
      hash(bound_bytes), hash(outcome_bytes), hash(verified_bytes), terminal_receipt);
  const std::string sixty = epoch_publication_marker_bytes(epoch, handoff_sha,
      "60-activation-published", hash(fifty), activation_name, hash(activation_bytes),
      hash(bound_bytes), hash(outcome_bytes), hash(verified_bytes), terminal_receipt);
  auto fifty_bytes = read("50-generation-published.v2.json");
  auto sixty_bytes = read("60-activation-published.v2.json");
  if (!fifty_bytes || !sixty_bytes || fifty_bytes.value() != fifty || sixty_bytes.value() != sixty)
    return false;
  EpochPublicationAdmission marker_state;
  marker_state.epoch = epoch;
  marker_state.handoff = handoff.value();
  marker_state.handoff_bytes = handoff_bytes.value();
  marker_state.transition.target = target.value();
  marker_state.generation_bytes = generation_bytes;
  marker_state.activation_name = activation_name;
  marker_state.activation_bytes = activation_bytes;
  marker_state.binding_bytes = bound_bytes;
  marker_state.outcome_bytes = outcome_bytes;
  marker_state.verified_bytes = verified_bytes;
  marker_state.terminal_receipt = terminal_receipt;
  marker_state.sixty_bytes = sixty;
  const std::string seventy = epoch_shell_cutover_marker_bytes(marker_state,
      "70-shortcut-cutover", hash(sixty), "shortcut");
  const std::string eighty = epoch_shell_cutover_marker_bytes(marker_state,
      "80-registration-cutover", hash(seventy), "registration");
  auto seventy_bytes = read("70-shortcut-cutover.v2.json");
  auto eighty_bytes = read("80-registration-cutover.v2.json");
  if (!seventy_bytes || !eighty_bytes || seventy_bytes.value() != seventy ||
      eighty_bytes.value() != eighty) return false;
  candidate.operation_id = handoff.value().operation_id;
  candidate.activation_name = activation_name;
  candidate.activation_sha256 = hash(activation_bytes);
  candidate.source_activation_name = handoff.value().source_activation_name;
  candidate.source_activation_sha256 = handoff.value().source_activation_sha256;
  candidate.source_generation_id = handoff.value().source_generation_id;
  candidate.generation_id = target.value().generation_id;
  if (!revalidate_completed_epoch_shell_cutover(candidate, scope)) return false;
  completed = std::move(candidate);
  return true;
}

bool revalidate_completed_epoch_shell_cutover(
    CompletedEpochShellCutover &completed,
    const PinnedLifecycleEpochScope &scope) {
  std::vector<fs::path> operation_names, record_names;
  return completed.maintenance.list_child_names_bounded(
             kMaximumEpochActivationRecords + 1U, operation_names).ok() &&
      operation_names == completed.operation_names &&
      completed.operation.list_child_names_bounded(10U, record_names).ok() &&
      record_names == completed.record_names &&
      std::all_of(completed.records.begin(), completed.records.end(),
          [](HeldPublicationRecord &record) {
            return held_file_matches_bytes(record.file, record.bytes);
          }) && completed.operation.revalidate().ok() &&
      completed.maintenance.revalidate().ok() && scope.epoch.revalidate().ok() &&
      scope.epochs.revalidate().ok() && scope.coordinator.revalidate().ok();
}

struct EpochShellAdmission {
  EpochPublicationAdmission publication;
  std::string seventy_bytes;
  std::string eighty_bytes;
  bool seventy_staged = false;
  bool seventy_final = false;
  bool eighty_staged = false;
  bool eighty_final = false;
};

struct EpochShellIdentity {
  EpochPublicationIdentity publication;
  std::string seventy_bytes;
  std::string eighty_bytes;
  bool seventy_staged = false;
  bool seventy_final = false;
  bool eighty_staged = false;
  bool eighty_final = false;
  std::vector<fs::path> operation_names;
};

facman::core::Result<EpochShellAdmission> load_epoch_shell_cutover(
    const EpochShellCutoverRequest &request, bool write_capable) {
  EpochPublicationRequest publication_request{request.coordinator_root,
      request.operation_id, request.nonce, request.journal_sha256, request.apply};
  auto loaded = load_epoch_publication(publication_request, write_capable);
  if (!loaded) return facman::core::Result<EpochShellAdmission>::failure(loaded.error());
  EpochShellAdmission result;
  result.publication = loaded.take_value();
  auto &state = result.publication;
  if (!state.generation_final || !state.fifty_final || !state.activation_final ||
      !state.sixty_final || state.generation_staged || state.fifty_staged ||
      state.activation_staged || state.sixty_staged)
    return facman::core::Result<EpochShellAdmission>::failure(epoch_recovery(
        "epoch shell cutover requires a fully published target genesis"));
  result.seventy_staged = publication_has(state.operation_names,
      "70-shortcut-cutover.staging.v2.json");
  result.seventy_final = publication_has(state.operation_names,
      "70-shortcut-cutover.v2.json");
  result.eighty_staged = publication_has(state.operation_names,
      "80-registration-cutover.staging.v2.json");
  result.eighty_final = publication_has(state.operation_names,
      "80-registration-cutover.v2.json");
  if ((result.seventy_staged && result.seventy_final) ||
      (result.eighty_staged && result.eighty_final) ||
      ((result.eighty_staged || result.eighty_final) && !result.seventy_final))
    return facman::core::Result<EpochShellAdmission>::failure(epoch_recovery(
        "epoch shell cutover records are conflicting or out of order"));
  result.seventy_bytes = epoch_shell_cutover_marker_bytes(state,
      "70-shortcut-cutover", hash(state.sixty_bytes), "shortcut");
  result.eighty_bytes = epoch_shell_cutover_marker_bytes(state,
      "80-registration-cutover", hash(result.seventy_bytes), "registration");
  const auto exact = [&](const char *name, const std::string &expected) {
    auto bytes = read_epoch_relative_bounded(state.operation, name,
        kMaximumEpochGenesisRecordBytes);
    return bytes && bytes.value() == expected;
  };
  if ((result.seventy_staged && !exact("70-shortcut-cutover.staging.v2.json",
                                       result.seventy_bytes)) ||
      (result.seventy_final && !exact("70-shortcut-cutover.v2.json",
                                      result.seventy_bytes)) ||
      (result.eighty_staged && !exact("80-registration-cutover.staging.v2.json",
                                      result.eighty_bytes)) ||
      (result.eighty_final && !exact("80-registration-cutover.v2.json",
                                     result.eighty_bytes)))
    return facman::core::Result<EpochShellAdmission>::failure(epoch_recovery(
        "epoch shell cutover marker has foreign or noncanonical bytes"));
  if (!publication_custody_valid(state, publication_request))
    return facman::core::Result<EpochShellAdmission>::failure(epoch_recovery(
        "epoch shell cutover custody changed during admission"));
  return facman::core::Result<EpochShellAdmission>::success(std::move(result));
}

EpochShellIdentity shell_identity(const EpochShellAdmission &state) {
  return {publication_identity(state.publication), state.seventy_bytes,
      state.eighty_bytes, state.seventy_staged, state.seventy_final,
      state.eighty_staged, state.eighty_final,
      state.publication.operation_names};
}

bool same_shell_identity(const EpochShellIdentity &left,
                         const EpochShellIdentity &right) {
  return same_publication_identity(left.publication, right.publication) &&
      left.seventy_bytes == right.seventy_bytes && left.eighty_bytes == right.eighty_bytes &&
      left.seventy_staged == right.seventy_staged && left.seventy_final == right.seventy_final &&
      left.eighty_staged == right.eighty_staged && left.eighty_final == right.eighty_final &&
      left.operation_names == right.operation_names;
}

std::string epoch_shell_phase(const EpochShellAdmission &state) {
  if (state.eighty_final) return "shell_cutover_complete";
  if (state.eighty_staged || state.seventy_final) return "registration_pending";
  return "shortcut_pending";
}

} // namespace

facman::core::Result<EpochShellCutoverResponse>
execute_lifecycle_epoch_shell_cutover(const EpochShellCutoverRequest &request,
                                      EpochShellCutoverEffects &effects) {
  EpochShellIdentity observed_identity;
  fs::path observed_acceptance_root;
  {
    auto observed = load_epoch_shell_cutover(request, false);
    if (!observed)
      return facman::core::Result<EpochShellCutoverResponse>::failure(
          observed.error());
    if (!request.apply)
      return facman::core::Result<EpochShellCutoverResponse>::success(
          {epoch_shell_phase(observed.value()),
           observed.value().publication.transition.target,
           observed.value().publication.journal});
    observed_identity = shell_identity(observed.value());
    observed_acceptance_root = observed.value().publication.epoch.acceptance_root;
  }
  auto authority = admit_coordinator(request.coordinator_root,
      observed_acceptance_root, false);
  if (!authority) return facman::core::Result<EpochShellCutoverResponse>::failure(authority.error());
  auto lock = acquire(authority.take_value(), request.operation_id);
  if (!lock) return facman::core::Result<EpochShellCutoverResponse>::failure(lock.error());
  auto locked = load_epoch_shell_cutover(request, true);
  if (!locked || !same_shell_identity(observed_identity,
                                      shell_identity(locked.value())))
    return facman::core::Result<EpochShellCutoverResponse>::failure(!locked ? locked.error() :
        epoch_recovery("epoch shell cutover identity changed across lock acquisition"));
  EpochShellAdmission state = locked.take_value();
  const EpochPublicationIdentity immutable =
      publication_identity(state.publication);
  const std::string immutable_seventy = state.seventy_bytes;
  const std::string immutable_eighty = state.eighty_bytes;
  const auto reload_unchanged = [&]() -> facman::core::Result<void> {
    auto refreshed = load_epoch_shell_cutover(request, true);
    if (!refreshed || !same_shell_identity(shell_identity(state),
                                           shell_identity(refreshed.value())))
      return facman::core::Result<void>::failure(!refreshed ? refreshed.error() :
          epoch_recovery("epoch shell cutover custody changed across callback"));
    state = refreshed.take_value();
    return facman::core::Result<void>::success();
  };
  const auto reload_after_write = [&]() -> facman::core::Result<void> {
    auto refreshed = load_epoch_shell_cutover(request, true);
    if (!refreshed || !same_publication_identity(
            immutable, publication_identity(refreshed.value().publication)) ||
        refreshed.value().seventy_bytes != immutable_seventy ||
        refreshed.value().eighty_bytes != immutable_eighty)
      return facman::core::Result<void>::failure(!refreshed
          ? refreshed.error() : epoch_recovery(
              "epoch shell cutover identity changed after a durable boundary"));
    state = refreshed.take_value();
    return facman::core::Result<void>::success();
  };
  if (!state.eighty_final) {
    const EffectResult terminal = effects.validate_terminal_verification(
        state.publication.transition, state.publication.binding,
        state.publication.terminal_receipt);
    auto revalidated = reload_unchanged();
    if (!revalidated) return facman::core::Result<EpochShellCutoverResponse>::failure(revalidated.error());
    if (!terminal.ok || terminal.outcome_unknown ||
        terminal.receipt_sha256 != state.publication.terminal_receipt)
      return facman::core::Result<EpochShellCutoverResponse>::failure(effect_error(
          "self_maintenance_verify_failed", "terminal provider verification changed before shell cutover",
          terminal).error());
  }
  if (!state.seventy_final) {
    const ShellState shell = effects.inspect_shortcut(state.publication.transition);
    auto revalidated = reload_unchanged();
    if (!revalidated) return facman::core::Result<EpochShellCutoverResponse>::failure(revalidated.error());
    if (shell == ShellState::old_exact) {
      const EffectResult changed = effects.cutover_shortcut(state.publication.transition);
      revalidated = reload_unchanged();
      if (!revalidated) return facman::core::Result<EpochShellCutoverResponse>::failure(revalidated.error());
      if (!changed.ok || changed.outcome_unknown)
        return facman::core::Result<EpochShellCutoverResponse>::failure(effect_error(
            "self_maintenance_shortcut_failed", "epoch shortcut cutover failed", changed).error());
      if (effects.inspect_shortcut(state.publication.transition) != ShellState::new_exact)
        return facman::core::Result<EpochShellCutoverResponse>::failure(epoch_recovery(
            "epoch shortcut cutover did not reach exact target ownership"));
      revalidated = reload_unchanged();
      if (!revalidated) return facman::core::Result<EpochShellCutoverResponse>::failure(revalidated.error());
    } else if (shell != ShellState::new_exact) {
      return facman::core::Result<EpochShellCutoverResponse>::failure(epoch_recovery(
          "epoch shortcut is not the exact source or target object"));
    }
    // Release pinned operation records before reopening an existing staging
    // file for durable promotion on Windows. Their exact bytes remain bound by
    // immutable and are reloaded immediately after publication.
    state.publication.operation_records.clear();
    auto written = publish_epoch_record(state.publication.operation,
        "70-shortcut-cutover.staging.v2.json", "70-shortcut-cutover.v2.json",
        state.seventy_bytes, kMaximumEpochPublicationRecords);
    if (!written) return facman::core::Result<EpochShellCutoverResponse>::failure(written.error());
    auto refreshed = reload_after_write();
    if (!refreshed || !state.seventy_final)
      return facman::core::Result<EpochShellCutoverResponse>::failure(!refreshed ? refreshed.error() :
          epoch_recovery("epoch shortcut marker did not reach its exact final state"));
  }
  if (!state.eighty_final) {
    if (effects.inspect_shortcut(state.publication.transition) != ShellState::new_exact)
      return facman::core::Result<EpochShellCutoverResponse>::failure(epoch_recovery(
          "durable shortcut cutover no longer has exact target ownership"));
    auto revalidated = reload_unchanged();
    if (!revalidated) return facman::core::Result<EpochShellCutoverResponse>::failure(revalidated.error());
    const ShellState shell = effects.inspect_registration(state.publication.transition);
    revalidated = reload_unchanged();
    if (!revalidated) return facman::core::Result<EpochShellCutoverResponse>::failure(revalidated.error());
    if (shell == ShellState::old_exact) {
      const EffectResult changed = effects.cutover_registration(state.publication.transition);
      revalidated = reload_unchanged();
      if (!revalidated) return facman::core::Result<EpochShellCutoverResponse>::failure(revalidated.error());
      if (!changed.ok || changed.outcome_unknown)
        return facman::core::Result<EpochShellCutoverResponse>::failure(effect_error(
            "self_maintenance_registration_failed", "epoch registration cutover failed", changed).error());
      if (effects.inspect_registration(state.publication.transition) != ShellState::new_exact)
        return facman::core::Result<EpochShellCutoverResponse>::failure(epoch_recovery(
            "epoch registration cutover did not reach exact target ownership"));
      revalidated = reload_unchanged();
      if (!revalidated) return facman::core::Result<EpochShellCutoverResponse>::failure(revalidated.error());
    } else if (shell != ShellState::new_exact) {
      return facman::core::Result<EpochShellCutoverResponse>::failure(epoch_recovery(
          "epoch registration is not the exact source or target object"));
    }
    state.publication.operation_records.clear();
    auto written = publish_epoch_record(state.publication.operation,
        "80-registration-cutover.staging.v2.json", "80-registration-cutover.v2.json",
        state.eighty_bytes, kMaximumEpochPublicationRecords);
    if (!written) return facman::core::Result<EpochShellCutoverResponse>::failure(written.error());
    auto refreshed = reload_after_write();
    if (!refreshed || !state.eighty_final)
      return facman::core::Result<EpochShellCutoverResponse>::failure(!refreshed ? refreshed.error() :
          epoch_recovery("epoch registration marker did not reach its exact final state"));
  }
  if (effects.inspect_shortcut(state.publication.transition) != ShellState::new_exact ||
      effects.inspect_registration(state.publication.transition) != ShellState::new_exact ||
      !publication_custody_valid(state.publication,
          EpochPublicationRequest{request.coordinator_root, request.operation_id,
              request.nonce, request.journal_sha256, true}))
    return facman::core::Result<EpochShellCutoverResponse>::failure(epoch_recovery(
        "epoch shell cutover final custody or ownership is not exact"));
  const EffectResult retired =
      effects.retire_shortcut_backup(state.publication.transition);
  auto revalidated = reload_unchanged();
  if (!revalidated)
    return facman::core::Result<EpochShellCutoverResponse>::failure(
        revalidated.error());
  if (!retired.ok || retired.outcome_unknown ||
      !digest(retired.receipt_sha256))
    return facman::core::Result<EpochShellCutoverResponse>::failure(effect_error(
        "self_maintenance_shortcut_backup_retirement_failed",
        "epoch shortcut backup retirement failed", retired).error());
  return facman::core::Result<EpochShellCutoverResponse>::success(
      {"shell_cutover_complete", state.publication.transition.target, state.publication.journal});
}

namespace {
facman::core::Result<std::optional<EpochPendingTransition>>
discover_epoch_transition_scan(const fs::path &coordinator_root) {
  if (!coordinator_root.is_absolute())
    return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
        failure("self_maintenance_input_invalid",
                "coordinator root must be absolute"));
  facman::platform::PathIdentity coordinator_identity;
  const auto inspected_coordinator = facman::platform::inspect_path_no_follow(
      coordinator_root, coordinator_identity);
  if (!inspected_coordinator.ok())
    return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
        epoch_recovery("epoch pending discovery could not inspect the coordinator root",
                       inspected_coordinator.detail));
  if (!coordinator_identity.exists)
    return facman::core::Result<std::optional<EpochPendingTransition>>::success({});
  facman::platform::StableDirectoryObject coordinator, epochs;
  if (!coordinator.open_no_follow(coordinator_root).ok())
    return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
        epoch_recovery("epoch pending discovery could not open the coordinator root"));
  facman::platform::PathIdentity epochs_identity;
  const auto inspected_epochs = facman::platform::inspect_path_no_follow(
      coordinator_root / "epochs", epochs_identity);
  if (!inspected_epochs.ok())
    return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
        epoch_recovery("epoch pending discovery could not inspect the epoch namespace",
                       inspected_epochs.detail));
  if (!epochs_identity.exists)
    return facman::core::Result<std::optional<EpochPendingTransition>>::success({});
  if (!coordinator.open_child_directory_no_follow("epochs", epochs).ok())
    return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
        epoch_recovery("epoch namespace is not a plain directory"));
  std::vector<fs::path> epoch_names;
  if (!epochs.list_child_names_bounded(kMaximumLifecycleEpochs, epoch_names).ok() ||
      epoch_names.empty())
    return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
        epoch_recovery("epoch namespace is empty, oversized, or changed"));

  std::optional<EpochPendingTransition> unfinished;
  std::optional<PendingEpochTransitionState> unfinished_pending_state;
  std::vector<EpochPendingTransition> completions;
  std::vector<HeldRetainedInputs> held_retained_inputs;
  std::vector<CompletedEpochShellCutover> held_completed_records;
  struct ScanOperationSnapshot {
    facman::platform::StableDirectoryObject maintenance;
    facman::platform::StableDirectoryObject operation;
    bool operation_present = false;
    std::vector<fs::path> operation_names;
    std::vector<fs::path> record_names;
    std::vector<HeldPublicationRecord> records;
  };
  std::vector<ScanOperationSnapshot> held_unfinished_records;
  for (const fs::path &name : epoch_names) {
    if (!digest(name.string()))
      return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
          epoch_recovery("epoch namespace contains a foreign entry"));
    PinnedLifecycleEpochScope scope;
    auto opened = scope.open(coordinator_root, name.string());
    auto manifest = opened ? scope.read("epoch.v1.json")
                           : facman::core::Result<std::string>::failure(opened.error());
    auto epoch = manifest ? parse_lifecycle_manifest(manifest.value(), name.string())
                          : facman::core::Result<LifecycleEpoch>::failure(manifest.error());
    if (!epoch)
      return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
          epoch.error());
    std::vector<fs::path> epoch_children;
    if (!scope.epoch.list_child_names_bounded(4U, epoch_children).ok())
      return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
          epoch_recovery("epoch pending discovery could not enumerate held children"));
    if (std::find(epoch_children.begin(), epoch_children.end(), fs::path("maintenance")) ==
        epoch_children.end()) {
      if (!scope.epoch.revalidate().ok())
        return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
            epoch_recovery("epoch changed during pending discovery"));
      continue;
    }
    facman::platform::StableDirectoryObject maintenance;
    std::vector<fs::path> operations;
    if (!scope.epoch.open_child_directory_no_follow("maintenance", maintenance).ok() ||
        !maintenance.list_child_names_bounded(kMaximumEpochActivationRecords + 1U,
                                              operations).ok())
      return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
          epoch_recovery("epoch maintenance directory is incomplete or foreign"));
    // Preparation creates the parent and, on an interrupted first write, may
    // create the deterministic operation directory before any handoff bytes.
    // This is a bounded pre-handoff state: expose the held source head only;
    // main recomputes the operation id from its exact caller package before
    // it can enter preparation.
    if (operations.empty()) {
      auto source = discover_epoch_genesis_state(epoch.value(), scope);
      if (!source || !source.value().has_value())
        return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
            !source ? source.error() : epoch_recovery("pre-handoff epoch has no source head"));
      EpochPendingTransition candidate;
      candidate.epoch_id = epoch.value().epoch_id;
      candidate.epoch_manifest_sha256 = epoch.value().manifest_sha256;
      candidate.target = source.value()->active;
      candidate.source_activation_name = source.value()->activation_name;
      candidate.source_activation_sha256 = source.value()->activation_sha256;
      candidate.phase = "pre_handoff";
      candidate.pre_handoff = true;
      if (unfinished.has_value())
        return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
            epoch_recovery("more than one unfinished epoch maintenance transition exists"));
      unfinished = std::move(candidate);
      ScanOperationSnapshot snapshot;
      if (!scope.epoch.open_child_directory_no_follow("maintenance", snapshot.maintenance).ok() ||
          !snapshot.maintenance.list_child_names_bounded(
              kMaximumEpochActivationRecords + 1U, snapshot.operation_names).ok() ||
          snapshot.operation_names != operations)
        return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
            epoch_recovery("empty epoch maintenance namespace changed during pending discovery"));
      held_unfinished_records.push_back(std::move(snapshot));
    }
    for (const fs::path &operation_name : operations) {
      facman::platform::StableDirectoryObject operation;
      std::vector<fs::path> records;
      std::string operation_detail;
      if (!facman::base::validate_identifier(operation_name.string(), operation_detail) ||
          !maintenance.open_child_directory_no_follow(operation_name, operation).ok() ||
          !operation.list_child_names_bounded(kMaximumEpochPublicationRecords + 1U,
                                              records).ok())
        return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
            epoch_recovery("epoch maintenance operation is incomplete or foreign"));
      if (records.empty()) {
        auto source = discover_epoch_genesis_state(epoch.value(), scope);
        if (!source || !source.value().has_value())
          return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
              !source ? source.error() : epoch_recovery("pre-handoff epoch has no source head"));
        EpochPendingTransition candidate;
        candidate.epoch_id = epoch.value().epoch_id;
        candidate.epoch_manifest_sha256 = epoch.value().manifest_sha256;
        candidate.operation_id = operation_name.string();
        candidate.target = source.value()->active;
        candidate.source_activation_name = source.value()->activation_name;
        candidate.source_activation_sha256 = source.value()->activation_sha256;
        candidate.phase = "pre_handoff";
        candidate.pre_handoff = true;
        if (unfinished.has_value())
          return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
              epoch_recovery("more than one unfinished epoch maintenance transition exists"));
        unfinished = std::move(candidate);
        ScanOperationSnapshot snapshot;
        if (!scope.epoch.open_child_directory_no_follow("maintenance", snapshot.maintenance).ok() ||
            !snapshot.maintenance.list_child_names_bounded(
                kMaximumEpochActivationRecords + 1U, snapshot.operation_names).ok() ||
            snapshot.operation_names != operations ||
            !snapshot.maintenance.open_child_directory_no_follow(
                operation_name, snapshot.operation).ok() ||
            !snapshot.operation.list_child_names_bounded(
                kMaximumEpochPublicationRecords + 1U, snapshot.record_names).ok() ||
            !snapshot.record_names.empty())
          return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
              epoch_recovery("empty epoch operation changed during pending discovery"));
        snapshot.operation_present = true;
        held_unfinished_records.push_back(std::move(snapshot));
        continue;
      }
    if (records.front() == fs::path("00-reactivation-intent.v1.json") ||
        records.front() == fs::path("00-reactivation-intent.staging.v1.json")) {
      if (!epoch_reactivation_record_names(records))
        return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
            epoch_recovery("epoch reactivation records are foreign or out of order"));
      std::vector<HeldPublicationRecord> held_records;
      for (const fs::path &record_name : records) {
        auto held = hold_publication_record(operation, record_name);
        if (!held)
          return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
              held.error());
        notify_epoch_record_pinned(operation.path() / record_name);
        held_records.push_back(held.take_value());
      }
      auto intent = parse_epoch_reactivation_intent(held_records.front().bytes,
          epoch.value(), operation_name);
      if (!intent)
        return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
            intent.error());
      const std::string shortcut_bytes = epoch_reactivation_cutover_bytes(
          intent.value(), "10-shortcut-cutover", hash(held_records.front().bytes),
          "shortcut");
      const std::string registration_bytes = epoch_reactivation_cutover_bytes(
          intent.value(), "20-registration-cutover", hash(shortcut_bytes),
          "registration");
      if ((held_records.size() >= 2U && held_records[1].bytes != shortcut_bytes) ||
          (held_records.size() >= 3U && held_records[2].bytes != registration_bytes) ||
          !std::all_of(held_records.begin(), held_records.end(),
              [](HeldPublicationRecord &held) {
                return held_file_matches_bytes(held.file, held.bytes);
              }))
        return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
            epoch_recovery("epoch reactivation cutover records changed or are foreign"));
      std::string target_bytes;
      auto target = parse_epoch_generation(epoch.value(), scope,
          intent.value().target_generation_id, &target_bytes);
      if (!target || hash(target_bytes) !=
              intent.value().target_generation_sha256 ||
          target.value().package_sha256 != intent.value().target_package_sha256)
        return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
            !target ? target.error() : epoch_recovery(
                "reactivation target generation changed after intent"));
      const fs::path repair_package = epoch.value().state_root / "repair-sources" /
          (intent.value().target_package_sha256 + ".zip");
      auto retained_package = inspect_package(repair_package);
      if (!retained_package || retained_package.value().package_sha256 !=
              intent.value().target_package_sha256 ||
          !same_descriptor(retained_package.value().descriptor,
                           generation_descriptor(target.value())))
        return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
            !retained_package ? retained_package.error() : epoch_recovery(
                "reactivation retained package changed after intent"));
      const std::string activation_bytes = epoch_link_activation_bytes(
          epoch.value(), intent.value().operation, intent.value().operation_id,
          intent.value().source_generation_id,
          intent.value().target_generation_id,
          intent.value().target_generation_sha256,
          intent.value().source_activation_name,
          intent.value().source_activation_sha256);
      if (hash(activation_bytes) != intent.value().target_activation_sha256)
        return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
            epoch_recovery("reactivation intent does not bind its activation"));
      EpochPendingTransition candidate;
      candidate.epoch_id = epoch.value().epoch_id;
      candidate.epoch_manifest_sha256 = epoch.value().manifest_sha256;
      candidate.operation = intent.value().operation == "update"
          ? Operation::update : intent.value().operation == "rollback"
              ? Operation::rollback : Operation::downgrade;
      candidate.operation_id = intent.value().operation_id;
      candidate.journal_sha256 = hash(held_records.front().bytes);
      candidate.retained_package = retained_package.take_value();
      candidate.shell_integration = intent.value().shell_integration;
      candidate.source_activation_name = intent.value().source_activation_name;
      candidate.source_activation_sha256 = intent.value().source_activation_sha256;
      candidate.target = target.take_value();
      candidate.target_activation_name = intent.value().target_activation_name;
      candidate.target_activation_sha256 = intent.value().target_activation_sha256;
      const bool cutover_final = records.size() == 3U &&
          records.back() == fs::path("20-registration-cutover.v1.json");
      if (cutover_final) {
        // A historical completion belongs to its recorded source activation,
        // not necessarily to today's head. The completed record and final
        // activation are checked here; chain discovery checks their order.
        CompletedEpochShellCutover completed;
        if (!completed_epoch_shell_cutover(epoch.value(), scope,
                                           operation_name, completed))
          return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
              epoch_recovery("completed epoch reactivation is not exact"));
        candidate.completed = true;
        candidate.phase = "reactivation_complete";
        held_completed_records.push_back(std::move(completed));
        completions.push_back(std::move(candidate));
      } else {
        PendingEpochTransitionState pending_state{candidate.target,
            epoch_generation_staging_name(candidate.target.generation_id),
            intent.value().target_activation_name,
            "activation." + intent.value().operation_id + ".staging.v2.json",
            activation_bytes};
        auto active = discover_epoch_genesis_state(epoch.value(), scope, nullptr,
            false, &intent.value().operation_id, &pending_state);
        if (!active || !active.value().has_value() ||
            active.value()->activation_name != intent.value().source_activation_name ||
            active.value()->activation_sha256 != intent.value().source_activation_sha256 ||
            !active.value()->previous.has_value() ||
            active.value()->previous->generation_id !=
                intent.value().target_generation_id)
          return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
              !active ? active.error() : epoch_recovery(
                  "pending reactivation is not the immediate predecessor transition"));
        candidate.phase = "reactivation_pending";
        if (unfinished.has_value())
          return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
              epoch_recovery("more than one unfinished epoch transition exists"));
        ScanOperationSnapshot snapshot;
        if (!scope.epoch.open_child_directory_no_follow("maintenance",
                snapshot.maintenance).ok() ||
            !snapshot.maintenance.list_child_names_bounded(
                kMaximumEpochActivationRecords + 1U,
                snapshot.operation_names).ok() ||
            snapshot.operation_names != operations ||
            !snapshot.maintenance.open_child_directory_no_follow(operation_name,
                snapshot.operation).ok() ||
            !snapshot.operation.list_child_names_bounded(
                kMaximumEpochPublicationRecords + 1U,
                snapshot.record_names).ok() ||
            snapshot.record_names != records)
          return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
              epoch_recovery("pending reactivation custody changed"));
        snapshot.operation_present = true;
        snapshot.records = std::move(held_records);
        held_unfinished_records.push_back(std::move(snapshot));
        unfinished_pending_state = std::move(pending_state);
        unfinished = std::move(candidate);
      }
      continue;
    }
    const bool continuation_records = records.size() <= kMaximumEpochContinuationRecords;
    const auto valid_records = continuation_records
        ? validate_epoch_continuation_names(operation, records)
        : validate_epoch_publication_names(operation, records);
    if (!valid_records)
      return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
          valid_records.error());
    const bool handoff_staged = records.front() ==
        fs::path("00-handoff-ready.staging.v3.json");
    auto handoff_bytes = read_epoch_relative_bounded(operation, records.front(),
                                                     kMaximumEpochGenesisRecordBytes);
    auto handoff = handoff_bytes ? parse_epoch_handoff(handoff_bytes.value())
                                 : facman::core::Result<EpochHandoff>::failure(
                                       handoff_bytes.error());
    if (!handoff || handoff.value().epoch_id != epoch.value().epoch_id ||
        handoff.value().manifest_sha256 != epoch.value().manifest_sha256 ||
        handoff.value().operation_id != operation_name.string())
      return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
          !handoff ? handoff.error() : epoch_recovery(
              "epoch handoff does not bind its held manifest and operation"));
    // Names alone never admit a provider tail.  Pin, parse, and compare every
    // durable continuation binding before a preview can report it recoverable.
    std::vector<HeldPublicationRecord> held_continuations;
    ProviderApplyBinding continuation_binding;
    const std::vector<std::pair<const char *, const char *>> continuation_phases = {
        {"10-provider-apply-bound.v2.json", "10-provider-apply-bound"},
        {"20-provider-apply-entered.v2.json", "20-provider-apply-entered"},
        {"30-provider-outcome.v2.json", "30-provider-outcome"},
        {"40-provider-verified.v2.json", "40-provider-verified"}};
    for (std::size_t index = 0; index < continuation_phases.size() && index + 1U < records.size(); ++index) {
      const fs::path expected = continuation_phases[index].first;
      const fs::path staged = expected.string().substr(0, expected.string().size() - 7U) +
          "staging.v2.json";
      if (records[index + 1U] != expected && records[index + 1U] != staged) break;
      auto held = hold_publication_record(operation, records[index + 1U]);
      auto parsed = held ? parse_epoch_continuation_record(held.value().bytes, epoch.value(),
          handoff.value(), hash(handoff_bytes.value()), continuation_phases[index].second)
          : facman::core::Result<ProviderApplyBinding>::failure(held.error());
      if (!parsed || (!continuation_binding.transaction_id.empty() &&
          !same_provider_apply_binding(continuation_binding, parsed.value())))
        return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
            !parsed ? parsed.error() : epoch_recovery(
                "epoch continuation records do not share one immutable binding"));
      continuation_binding = parsed.take_value();
      held_continuations.push_back(held.take_value());
    }
    if (!std::all_of(held_continuations.begin(), held_continuations.end(),
          [](HeldPublicationRecord &held) {
            return held_file_matches_bytes(held.file, held.bytes);
          }))
      return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
          epoch_recovery("epoch continuation record changed during pending discovery"));
    EpochPendingTransition candidate;
    std::optional<PendingEpochTransitionState> candidate_pending_state;
    candidate.epoch_id = epoch.value().epoch_id;
    candidate.epoch_manifest_sha256 = epoch.value().manifest_sha256;
    candidate.operation = handoff.value().operation == "update" ? Operation::update
                                                                    : Operation::downgrade;
    candidate.operation_id = handoff.value().operation_id;
    candidate.nonce = handoff.value().nonce;
    candidate.journal_sha256 = hash(handoff_bytes.value());
    auto retained = validate_retained_inputs(epoch.value(), candidate.operation_id,
                                             handoff.value().inputs);
    auto retained_package = retained ? inspect_package(handoff.value().inputs.package)
                                     : facman::core::Result<PackageInspection>::failure(
                                           retained.error());
    if (!retained || !retained_package ||
        retained_package.value().package_sha256 != handoff.value().inputs.package_sha256 ||
        !revalidate_retained_inputs(retained.value()))
      return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
          !retained ? retained.error() : (!retained_package ? retained_package.error() :
              epoch_recovery("pending epoch retained package identity changed")));
    candidate.retained_package = retained_package.take_value();
    candidate.retained_inputs = handoff.value().inputs;
    candidate.shell_integration = handoff.value().shell_integration;
    candidate.deadline_utc_ms = handoff.value().deadline_utc_ms;
    held_retained_inputs.push_back(std::move(retained.take_value()));
    candidate.source_activation_name = handoff.value().source_activation_name;
    candidate.source_activation_sha256 = handoff.value().source_activation_sha256;
    const bool continuation_phase = handoff_staged || (continuation_records &&
          (records.size() < kMaximumEpochContinuationRecords ||
              records.back() == fs::path("40-provider-verified.staging.v2.json")))
        ;
    candidate.phase = handoff_staged ? "handoff_staging"
        : continuation_phase
            ? "continuation_pending"
        : (records.size() < 7U || records.back() ==
              fs::path("60-activation-published.staging.v2.json"))
            ? "publication_pending" : "shell_cutover_pending";
    if (continuation_phase) {
      // Pending discovery is read-only. Reconstruct both sides from the held
      // active head and retained package; the handoff may not nominate a
      // different source even when its target happens to be canonical.
      auto source = discover_epoch_genesis_state(epoch.value(), scope, nullptr, false,
                                                 &candidate.operation_id);
      if (!source || !source.value().has_value())
        return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
            !source ? source.error() : epoch_recovery(
                handoff_staged ? "staged handoff has no exact source head"
                               : "pending continuation has no exact source head"));
      if (handoff.value().source_generation_id !=
              source.value()->active.generation_id ||
          handoff.value().source_activation_name !=
              source.value()->activation_name ||
          handoff.value().source_activation_sha256 !=
              source.value()->activation_sha256)
        return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
            epoch_recovery("pending epoch handoff does not bind the exact source head"));
      EpochTransitionRequest target_request{coordinator_root, epoch.value().epoch_id,
          candidate.operation, candidate.operation_id, candidate.retained_package,
          false, {}, {}, true};
      auto target_plan = make_epoch_transition_plan(
          epoch.value(), *source.value(), target_request);
      if (!target_plan || target_plan.value().target.generation_id !=
              handoff.value().target_generation_id)
        return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
            !target_plan ? target_plan.error() : epoch_recovery(
                "pending epoch handoff target does not match its retained package"));
      candidate.target = target_plan.take_value().target;
    }

    const bool terminal = records.size() == kMaximumEpochPublicationRecords &&
        records.back() == fs::path("80-registration-cutover.v2.json");
    if (terminal) {
      // Historical 80 records are checked without asking the publication
      // loader to regard their old target as the current head.  The loader is
      // intentionally head-sensitive for a live retry; this scan must retain
      // older immutable completions while a later operation is active.
      CompletedEpochShellCutover completed;
      std::string target_bytes;
      auto target = completed_epoch_shell_cutover(epoch.value(), scope, operation_name,
                                                  completed)
          ? parse_epoch_generation(epoch.value(), scope,
              handoff.value().target_generation_id, &target_bytes)
          : facman::core::Result<Generation>::failure(epoch_recovery(
              "terminal epoch shell cutover is not exact"));
      if (!target)
        return facman::core::Result<std::optional<EpochPendingTransition>>::failure(target.error());
      candidate.phase = "shell_cutover_complete";
      candidate.target = target.take_value();
      candidate.target_activation_name = completed.activation_name;
      candidate.target_activation_sha256 = completed.activation_sha256;
      candidate.source_activation_name = completed.source_activation_name;
      candidate.source_activation_sha256 = completed.source_activation_sha256;
      candidate.completed = true;
      held_completed_records.push_back(std::move(completed));
      completions.push_back(std::move(candidate));
      continue;
    }
    if (continuation_phase) {
      auto chain = discover_lifecycle_epoch_chain_impl(coordinator_root, {}, nullptr,
          candidate.operation_id, candidate.epoch_id);
      if (!chain || chain.value().epochs.empty() ||
          chain.value().epochs.back().epoch_id != candidate.epoch_id ||
          chain.value().epochs.back().manifest_sha256 != epoch.value().manifest_sha256)
        return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
            !chain ? chain.error() : epoch_recovery(
                "pending continuation is not the exact lifecycle tail"));
    } else if (candidate.phase == "shell_cutover_pending") {
      EpochShellCutoverRequest request{coordinator_root, candidate.operation_id,
          candidate.nonce, candidate.journal_sha256, false};
      auto shell = load_epoch_shell_cutover(request, false);
      if (!shell)
        return facman::core::Result<std::optional<EpochPendingTransition>>::failure(shell.error());
      const EpochPublicationAdmission &publication = shell.value().publication;
      candidate.target = publication.transition.target;
      candidate.target_activation_name = publication.activation_name;
      candidate.target_activation_sha256 = hash(publication.activation_bytes);
      candidate_pending_state.emplace(PendingEpochTransitionState{
          publication.transition.target,
          epoch_generation_staging_name(publication.transition.target.generation_id),
          publication.activation_name, publication.activation_staging_name,
          publication.activation_bytes});
    } else {
      EpochPublicationRequest request{coordinator_root, candidate.operation_id,
          candidate.nonce, candidate.journal_sha256, false};
      auto publication = load_epoch_publication(request, false);
      if (!publication)
        return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
            publication.error());
      candidate.target = publication.value().transition.target;
      candidate.target_activation_name = publication.value().activation_name;
      candidate.target_activation_sha256 = hash(publication.value().activation_bytes);
      candidate_pending_state.emplace(PendingEpochTransitionState{
          publication.value().transition.target,
          epoch_generation_staging_name(
              publication.value().transition.target.generation_id),
          publication.value().activation_name,
          publication.value().activation_staging_name,
          publication.value().activation_bytes});
    }
    if (unfinished.has_value())
      return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
          epoch_recovery("more than one unfinished epoch maintenance transition exists"));
    ScanOperationSnapshot snapshot;
    if (!scope.epoch.open_child_directory_no_follow("maintenance", snapshot.maintenance).ok() ||
        !snapshot.maintenance.list_child_names_bounded(kMaximumEpochActivationRecords + 1U,
                                                       snapshot.operation_names).ok() ||
        snapshot.operation_names != operations ||
        !snapshot.maintenance.open_child_directory_no_follow(operation_name, snapshot.operation).ok() ||
        !snapshot.operation.list_child_names_bounded(kMaximumEpochPublicationRecords + 1U,
                                                     snapshot.record_names).ok() ||
        snapshot.record_names != records)
      return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
          epoch_recovery("unfinished epoch operation names changed during pending discovery"));
    snapshot.operation_present = true;
    for (const fs::path &record_name : snapshot.record_names) {
      auto held = hold_publication_record(snapshot.operation, record_name);
      if (!held)
        return facman::core::Result<std::optional<EpochPendingTransition>>::failure(held.error());
      notify_epoch_record_pinned(snapshot.operation.path() / record_name);
      snapshot.records.push_back(held.take_value());
    }
    held_unfinished_records.push_back(std::move(snapshot));
    unfinished_pending_state = std::move(candidate_pending_state);
    unfinished = std::move(candidate);
    }
    if (!maintenance.revalidate().ok() || !scope.epoch.revalidate().ok() ||
        !scope.epochs.revalidate().ok() || !scope.coordinator.revalidate().ok())
      return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
          epoch_recovery("epoch maintenance history changed during pending discovery"));
  }
  const auto held_complete_valid = [](CompletedEpochShellCutover &completed) {
    std::vector<fs::path> names, records;
    return completed.maintenance.list_child_names_bounded(
               kMaximumEpochActivationRecords + 1U, names).ok() &&
        names == completed.operation_names &&
        completed.operation.list_child_names_bounded(10U, records).ok() &&
        records == completed.record_names &&
        std::all_of(completed.records.begin(), completed.records.end(),
            [](HeldPublicationRecord &record) {
              return held_file_matches_bytes(record.file, record.bytes);
            }) && completed.operation.revalidate().ok() && completed.maintenance.revalidate().ok();
  };
  const auto held_unfinished_valid = [](ScanOperationSnapshot &snapshot) {
    std::vector<fs::path> operations, records;
    if (!snapshot.maintenance.list_child_names_bounded(
            kMaximumEpochActivationRecords + 1U, operations).ok() ||
        operations != snapshot.operation_names || !snapshot.maintenance.revalidate().ok())
      return false;
    if (!snapshot.operation_present)
      return true;
    return snapshot.operation.list_child_names_bounded(
               kMaximumEpochPublicationRecords + 1U, records).ok() &&
        records == snapshot.record_names &&
        std::all_of(snapshot.records.begin(), snapshot.records.end(),
            [](HeldPublicationRecord &record) {
              return held_file_matches_bytes(record.file, record.bytes);
            }) && snapshot.operation.revalidate().ok();
  };
  const auto exact_scan_custody = [&] {
    std::vector<fs::path> current_epoch_names;
    return epochs.list_child_names_bounded(
               kMaximumLifecycleEpochs, current_epoch_names).ok() &&
        current_epoch_names == epoch_names &&
        std::all_of(held_retained_inputs.begin(), held_retained_inputs.end(),
            [](HeldRetainedInputs &held) { return revalidate_retained_inputs(held); }) &&
        std::all_of(held_completed_records.begin(), held_completed_records.end(),
            held_complete_valid) &&
        std::all_of(held_unfinished_records.begin(), held_unfinished_records.end(),
            held_unfinished_valid) && epochs.revalidate().ok() && coordinator.revalidate().ok();
  };
  if (!exact_scan_custody())
    return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
        epoch_recovery("epoch namespace, retained input, or completed record changed during pending discovery"));
  if (unfinished.has_value()) {
    auto tail = discover_lifecycle_epoch_chain_impl(coordinator_root, {}, nullptr,
        unfinished->operation_id, unfinished->epoch_id,
        unfinished_pending_state ? &*unfinished_pending_state : nullptr);
    if (!tail || tail.value().epochs.empty() ||
        tail.value().epochs.back().epoch_id != unfinished->epoch_id ||
        tail.value().epochs.back().manifest_sha256 !=
            unfinished->epoch_manifest_sha256)
      return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
          !tail ? tail.error() : epoch_recovery(
              "unfinished epoch operation is not at the lifecycle tail"));
    if (!exact_scan_custody())
      return facman::core::Result<std::optional<EpochPendingTransition>>::failure(
          epoch_recovery("unfinished epoch custody changed during final tail discovery"));
    return facman::core::Result<std::optional<EpochPendingTransition>>::success(
        std::move(unfinished));
  }
  if (completions.empty())
    return facman::core::Result<std::optional<EpochPendingTransition>>::success({});
  // A completed operation is useful only for an exact retry on the current
  // active epoch head.  Older immutable operation directories remain history.
  auto active = discover_lifecycle_epoch_active(coordinator_root);
  if (!active)
    return facman::core::Result<std::optional<EpochPendingTransition>>::failure(active.error());
  std::optional<EpochPendingTransition> head_completion;
  for (const EpochPendingTransition &completion : completions) {
    if (completion.epoch_id != active.value().epoch.epoch_id ||
        completion.target.generation_id != active.value().active.active.generation_id ||
        completion.target_activation_name != active.value().active.activation_name ||
        completion.target_activation_sha256 != active.value().active.activation_sha256)
      continue;
    if (head_completion.has_value())
      return facman::core::Result<std::optional<EpochPendingTransition>>::failure(epoch_recovery(
          "more than one completed epoch operation binds the active head"));
    head_completion = completion;
  }
  if (!head_completion.has_value())
    return facman::core::Result<std::optional<EpochPendingTransition>>::failure(epoch_recovery(
        "epoch maintenance history does not bind the active lifecycle head"));
  return facman::core::Result<std::optional<EpochPendingTransition>>::success(
      std::move(head_completion));
}

}  // namespace

facman::core::Result<std::optional<EpochPendingTransition>>
discover_lifecycle_epoch_pending_transition(const fs::path &coordinator_root) {
  auto scanned = discover_epoch_transition_scan(coordinator_root);
  if (!scanned || !scanned.value().has_value() || scanned.value()->completed)
    return !scanned
        ? facman::core::Result<std::optional<EpochPendingTransition>>::failure(scanned.error())
        : facman::core::Result<std::optional<EpochPendingTransition>>::success({});
  return scanned;
}

facman::core::Result<std::optional<EpochPendingTransition>>
discover_lifecycle_epoch_terminal_transition(const fs::path &coordinator_root) {
  auto scanned = discover_epoch_transition_scan(coordinator_root);
  if (!scanned || !scanned.value().has_value() || !scanned.value()->completed)
    return !scanned
        ? facman::core::Result<std::optional<EpochPendingTransition>>::failure(scanned.error())
        : facman::core::Result<std::optional<EpochPendingTransition>>::success({});
  return scanned;
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
  next.compatibility_active.reset();
  next.manifest_sha256.clear();
  next.retirement_sha256.clear();
  next.retirement_journal_name.clear();
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

// An interruption between creating the first epoch directory and publishing
// its manifest leaves discovery deliberately fail-closed. Only the exact
// bootstrap that durably verified the clone may finish that publication.
facman::core::Result<void> recover_bootstrap_epoch_manifest(
    const fs::path &coordinator_root, const LifecycleEpoch &epoch,
    const ActivationChain &reviewed_flat) {
  auto admission = admit_coordinator(coordinator_root, epoch.acceptance_root, false);
  if (!admission) return facman::core::Result<void>::failure(admission.error());
  auto lock = acquire(admission.take_value(), "compatibility.bootstrap.manifest");
  if (!lock) return facman::core::Result<void>::failure(lock.error());
  facman::platform::StableDirectoryObject epochs;
  const auto opened_epochs = lock.value().admission.coordinator
      .open_child_directory_no_follow_for_relative_writes("epochs", epochs);
  if (!opened_epochs.ok()) {
    facman::platform::PathIdentity identity;
    if (!facman::platform::inspect_path_no_follow(
            coordinator_root / "epochs", identity).ok() || identity.exists)
      return facman::core::Result<void>::failure(epoch_recovery(
          "bootstrap epoch root is unsafe during manifest recovery"));
    return facman::core::Result<void>::success();
  }
  std::vector<fs::path> epoch_names;
  if (!epochs.list_child_names_bounded(kMaximumLifecycleEpochs, epoch_names).ok())
    return facman::core::Result<void>::failure(epoch_recovery(
        "bootstrap epoch root changed during manifest recovery"));
  if (epoch_names.empty()) return facman::core::Result<void>::success();
  if (epoch_names.size() != 1U || epoch_names.front() != fs::path(epoch.epoch_id))
    return facman::core::Result<void>::failure(epoch_recovery(
        "bootstrap manifest recovery found an ambiguous epoch namespace"));
  facman::platform::StableDirectoryObject epoch_directory;
  if (!epochs.open_child_directory_no_follow_for_relative_writes(
          epoch.epoch_id, epoch_directory).ok())
    return facman::core::Result<void>::failure(epoch_recovery(
        "bootstrap epoch directory is unsafe during manifest recovery"));
  std::vector<fs::path> names;
  if (!epoch_directory.list_child_names_bounded(8U, names).ok())
    return facman::core::Result<void>::failure(epoch_recovery(
        "bootstrap epoch directory changed during manifest recovery"));
  if (std::find(names.begin(), names.end(), fs::path("epoch.v1.json")) !=
      names.end()) {
    auto existing = read_epoch_manifest(epoch_directory, "epoch.v1.json");
    if (!existing || existing.value() != lifecycle_manifest_bytes(epoch))
      return facman::core::Result<void>::failure(epoch_recovery(
          "bootstrap epoch manifest has different immutable bytes"));
    return facman::core::Result<void>::success();
  }
  if (names.size() > 1U ||
      (!names.empty() && names.front() != fs::path("epoch.staging.v1.json") &&
       names.front() != fs::path("epoch.v1.json")))
    return facman::core::Result<void>::failure(epoch_recovery(
        "bootstrap epoch directory contains unexpected state before its manifest"));

  auto flat = discover_activation_chain(coordinator_root);
  if (!flat || !flat.value().has_value() ||
      retirement_chain_digest(*flat.value()) !=
          retirement_chain_digest(reviewed_flat))
    return facman::core::Result<void>::failure(!flat ? flat.error() : epoch_recovery(
        "flat authority changed before bootstrap manifest recovery"));
  LifecycleEpoch compatibility;
  compatibility.epoch_id = kCompatibilityEpochId;
  compatibility.compatibility_epoch = true;
  compatibility.genesis_generation_id = flat.value()->generations.front().generation_id;
  compatibility.acceptance_root = epoch.acceptance_root;
  compatibility.logical_root = epoch.logical_root;
  compatibility.state_root = epoch.state_root;
  auto validated = validate_epoch_history(compatibility, coordinator_root, true);
  if (!validated || !compatibility.compatibility_handoff ||
      compatibility.retirement_sha256 != epoch.predecessor_retirement_sha256 ||
      hash(compatibility_manifest_bytes(*flat.value())) !=
          epoch.predecessor_manifest_sha256)
    return facman::core::Result<void>::failure(!validated ? validated.error() :
        epoch_recovery("partial epoch manifest lacks its exact verified authority handoff"));
  std::string lock_detail;
  if (!lock.value().admission.revalidate(lock_detail) ||
      !epochs.revalidate().ok() || !epoch_directory.revalidate().ok())
    return facman::core::Result<void>::failure(epoch_recovery(
        "bootstrap authority changed before manifest recovery", lock_detail));
  const std::string bytes = lifecycle_manifest_bytes(epoch);
  auto published = publish_epoch_record(epoch_directory,
      "epoch.staging.v1.json", "epoch.v1.json", bytes, 1U);
  if (!published || !epoch_directory.flush_metadata().ok() ||
      !epochs.flush_metadata().ok() ||
      !lock.value().admission.coordinator.flush_metadata().ok())
    return facman::core::Result<void>::failure(!published ? published.error() :
        epoch_recovery("recovered bootstrap epoch manifest was not flushed"));
  return facman::core::Result<void>::success();
}

facman::core::Result<CompatibilityAuthorityBootstrapResponse>
bootstrap_compatibility_authority(
    const CompatibilityAuthorityBootstrapRequest &request,
    CompatibilityAuthorityBootstrapEffects &effects) {
  using Result = facman::core::Result<CompatibilityAuthorityBootstrapResponse>;
  const auto fail = [](facman::core::Error error) {
    return Result::failure(std::move(error));
  };
  if (!request.coordinator_root.is_absolute() ||
      !digest(request.package_sha256))
    return fail(failure("self_maintenance_input_invalid",
        "compatibility bootstrap inputs are incomplete"));
  auto flat = discover_activation_chain(request.coordinator_root);
  auto active = flat ? discover_active(request.coordinator_root)
      : facman::core::Result<std::optional<ActiveState>>::failure(flat.error());
  if (!active || !flat.value().has_value() || !active.value().has_value())
    return fail(!active ? active.error() : epoch_recovery(
        "bootstrap requires one active compatibility activation history"));
  const Generation source = active.value()->active;
  if (source.generation_id != flat.value()->generations.back().generation_id ||
      source.package_sha256 != request.package_sha256 ||
      !same_descriptor(generation_descriptor(source), request.package_descriptor))
    return fail(failure("self_maintenance_package_incompatible",
        "bootstrap package does not exactly match the active flat generation"));
  const std::string handoff_bytes =
      compatibility_authority_handoff_bytes(*flat.value());
  LifecycleEpoch epoch;
  epoch.acceptance_root = source.acceptance_root;
  epoch.genesis_generation_id = source.generation_id;
  epoch.logical_root = source.logical_root;
  epoch.predecessor_epoch_id = kCompatibilityEpochId;
  epoch.predecessor_manifest_sha256 =
      hash(compatibility_manifest_bytes(*flat.value()));
  epoch.predecessor_retirement_sha256 = hash(handoff_bytes);
  epoch.state_root = source.state_root;
  epoch.epoch_id = hash(lifecycle_identity_bytes(epoch));
  auto target = make_epoch_genesis_generation(epoch,
      request.package_descriptor, request.package_sha256);
  if (!target) return fail(target.error());
  // The provider owns the Windows path limit and recipe admission. Run its
  // read-only plan before publishing even the first bootstrap reservation.
  // An exact clone on retry has already crossed that boundary and must not
  // be asked to plan a second install over its existing provider identity.
  const EffectResult preexisting_clone = effects.inspect_epoch_clone(
      source, target.value());
  if (preexisting_clone.outcome_unknown)
    return fail(epoch_recovery("epoch clone identity is ambiguous before bootstrap",
                               preexisting_clone.detail));
  if (!preexisting_clone.ok) {
    const EffectResult reviewed = effects.review_epoch_clone(
        source, target.value());
    if (!reviewed.ok || reviewed.outcome_unknown ||
        !digest(reviewed.receipt_sha256))
      return fail(failure("self_maintenance_plan_failed",
                          "epoch clone provider plan was refused",
                          reviewed.detail));
  }
  if (request.apply) {
    auto recovered = recover_bootstrap_epoch_manifest(
        request.coordinator_root, epoch, *flat.value());
    if (!recovered) return fail(recovered.error());
  }
  auto chain = discover_lifecycle_epoch_chain_impl(request.coordinator_root);
  if (!chain || chain.value().epochs.empty() ||
      !chain.value().epochs.front().compatibility_epoch ||
      chain.value().epochs.front().manifest_sha256 !=
          epoch.predecessor_manifest_sha256)
    return fail(!chain ? chain.error() : epoch_recovery(
        "bootstrap requires one active compatibility activation history"));
  if (chain.value().epochs.size() > 2U ||
      (chain.value().epochs.size() == 2U &&
       chain.value().epochs.back().epoch_id != epoch.epoch_id))
    return fail(epoch_recovery("a different real lifecycle epoch is already present"));
  const fs::path journal_path = request.coordinator_root / "authority-bootstrap.v1";
  const std::string entered_bytes = compatibility_bootstrap_entered_bytes(
      *flat.value(), epoch, target.value(), request.shell_integration);
  const std::string entered_sha256 = hash(entered_bytes);
  ActiveState preview{target.value(), {},
      epoch_activation_name(target.value().generation_id), {}};
  if (!request.apply)
    return Result::success({"planned", epoch, std::move(preview), journal_path});
  if (chain.value().epochs.size() == 2U) {
    auto selected = resolve_authoritative_active_state(request.coordinator_root);
    if (selected && selected.value().has_value() &&
        selected.value()->epoch.has_value() &&
        selected.value()->epoch->epoch_id == epoch.epoch_id)
      return Result::success({"complete", epoch,
          selected.value()->active, journal_path});
  }

  {
    auto admission = admit_coordinator(request.coordinator_root,
                                       source.acceptance_root, false);
    if (!admission) return fail(admission.error());
    auto lock = acquire(admission.take_value(), "compatibility.bootstrap");
    if (!lock) return fail(lock.error());
    auto current = discover_activation_chain(request.coordinator_root);
    if (!current || !current.value().has_value() ||
        current.value()->activation_name != flat.value()->activation_name ||
        current.value()->activation_sha256 != flat.value()->activation_sha256)
      return fail(!current ? current.error() : epoch_recovery(
          "flat activation head changed before bootstrap entry"));
    auto current_active = discover_active(request.coordinator_root);
    auto current_epochs = current_active
        ? discover_lifecycle_epoch_chain_impl(request.coordinator_root)
        : facman::core::Result<LifecycleEpochChain>::failure(current_active.error());
    if (!current_epochs || !current_active.value().has_value() ||
        current_active.value()->active.install_id != source.install_id ||
        current_epochs.value().epochs.empty() ||
        current_epochs.value().epochs.size() > 2U ||
        (current_epochs.value().epochs.size() == 2U &&
         current_epochs.value().epochs.back().epoch_id != epoch.epoch_id))
      return fail(!current_epochs ? current_epochs.error() : epoch_recovery(
          "compatibility authority changed before bootstrap entry"));
    auto journal = open_or_create_epoch_child(
        lock.value().admission.coordinator, "authority-bootstrap.v1");
    if (!journal) return fail(journal.error());
    std::vector<fs::path> names;
    if (!journal.value().list_child_names_bounded(7U, names).ok())
      return fail(epoch_recovery("bootstrap journal exceeds its record bound"));
    const std::vector<std::string> phases = {
        "10-clone-entered.v1.json", "20-clone-verified.v1.json",
        "30-genesis-activated.v1.json", "40-shortcut-cutover.v1.json",
        "50-registration-cutover.v1.json", "60-complete.v1.json"};
    for (std::size_t index = 0; index < names.size(); ++index) {
      if (index >= phases.size())
        return fail(epoch_recovery("bootstrap journal exceeds its phase bound"));
      const std::string staging = phases[index].substr(
          0, phases[index].size() - 8U) + ".staging.v1.json";
      if (names[index] != phases[index] &&
          !(index + 1U == names.size() && names[index] == staging))
        return fail(epoch_recovery(
            "bootstrap journal contains a foreign or out-of-order entry"));
    }
    auto entered = read_optional_bootstrap_record(
        journal.value(), phases[0]);
    if (!entered) return fail(entered.error());
    if (entered.value().has_value() && *entered.value() != entered_bytes)
      return fail(epoch_recovery("bootstrap entry belongs to another authority"));
    if (!entered.value().has_value()) {
      const EffectResult preexisting = effects.inspect_epoch_clone(
          source, target.value());
      if (preexisting.ok || preexisting.outcome_unknown)
        return fail(epoch_recovery(
            "epoch clone already exists without a durable bootstrap entry",
            preexisting.detail));
      const EffectResult reviewed = effects.review_epoch_clone(
          source, target.value());
      if (!reviewed.ok || reviewed.outcome_unknown ||
          !digest(reviewed.receipt_sha256))
        return fail(failure("self_maintenance_plan_failed",
                            "epoch clone provider plan changed before entry",
                            reviewed.detail));
      const auto published = publish_epoch_record(journal.value(),
          "10-clone-entered.staging.v1.json", phases[0], entered_bytes, 6U);
      if (!published) return fail(published.error());
      const EffectResult cloned = effects.clone_epoch(source, target.value());
      if (!cloned.ok || cloned.outcome_unknown)
        return fail(epoch_recovery("epoch clone entered but its outcome is unknown",
                                   cloned.detail));
    }
    std::string lock_detail;
    if (!lock.value().admission.revalidate(lock_detail))
      return fail(epoch_recovery("bootstrap authority changed during clone",
                                 lock_detail));
    const EffectResult inspected = effects.inspect_epoch_clone(
        source, target.value());
    if (!inspected.ok || inspected.outcome_unknown ||
        !digest(inspected.receipt_sha256))
      return fail(epoch_recovery("entered epoch clone is not exactly installed",
                                 inspected.detail));
    if (!lock.value().admission.revalidate(lock_detail) ||
        !journal.value().revalidate().ok())
      return fail(epoch_recovery("bootstrap authority changed during clone inspection",
                                 lock_detail));
    const std::string verified_bytes = compatibility_bootstrap_phase_bytes(
        "clone_verified", entered_sha256, inspected.receipt_sha256);
    const auto verified = publish_epoch_record(journal.value(),
        "20-clone-verified.staging.v1.json", phases[1], verified_bytes, 6U);
    if (!verified) return fail(verified.error());
    const auto handoff = publish_epoch_record(
        lock.value().admission.coordinator,
        "authority-handoff.staging.v1.json", "authority-handoff.v1.json",
        handoff_bytes, 256U);
    if (!handoff) return fail(handoff.error());
    if (!journal.value().flush_metadata().ok() ||
        !lock.value().admission.coordinator.flush_metadata().ok())
      return fail(epoch_recovery("bootstrap handoff directory was not flushed"));
  }

  auto published = publish_lifecycle_epoch(request.coordinator_root, epoch, true);
  if (!published) return fail(published.error());
  auto genesis = activate_lifecycle_epoch_genesis(
      {request.coordinator_root, epoch.epoch_id, target.value(), true});
  if (!genesis) return fail(genesis.error());

  auto admission = admit_coordinator(request.coordinator_root,
                                     source.acceptance_root, false);
  if (!admission) return fail(admission.error());
  auto lock = acquire(admission.take_value(), "compatibility.bootstrap.cutover");
  if (!lock) return fail(lock.error());
  facman::platform::StableDirectoryObject journal;
  if (!lock.value().admission.coordinator.open_child_directory_no_follow_for_relative_writes(
          "authority-bootstrap.v1", journal).ok())
    return fail(epoch_recovery("bootstrap journal changed before native cutover"));
  const std::string genesis_bytes = compatibility_bootstrap_phase_bytes(
      "genesis_activated", entered_sha256, genesis.value().activation_sha256);
  auto recorded = publish_epoch_record(journal,
      "30-genesis-activated.staging.v1.json", "30-genesis-activated.v1.json",
      genesis_bytes, 6U);
  if (!recorded) return fail(recorded.error());
  const std::string shortcut_receipt = hash("facman.bootstrap.shortcut.v1\n" +
      target.value().install_id + "\n" +
      (request.shell_integration ? "cutover\n" : "disabled\n"));
  const std::string shortcut_bytes = compatibility_bootstrap_phase_bytes(
      "shortcut_cutover", entered_sha256, shortcut_receipt);
  auto prior_shortcut = read_optional_bootstrap_record(
      journal, "40-shortcut-cutover.v1.json");
  if (!prior_shortcut || (prior_shortcut.value().has_value() &&
                          *prior_shortcut.value() != shortcut_bytes))
    return fail(!prior_shortcut ? prior_shortcut.error() : epoch_recovery(
        "durable shortcut cutover belongs to another bootstrap"));
  std::string cutover_detail;
  if (!lock.value().admission.revalidate(cutover_detail) ||
      !journal.revalidate().ok())
    return fail(epoch_recovery("bootstrap authority changed before shortcut cutover",
                               cutover_detail));
  const auto shortcut = effects.inspect_epoch_shortcut(source, target.value());
  if (request.shell_integration) {
    if (shortcut == ShellState::old_exact || shortcut == ShellState::absent) {
      if (prior_shortcut.value().has_value())
        return fail(epoch_recovery("completed epoch shortcut is no longer exact"));
      auto changed = effects.cutover_epoch_shortcut(source, target.value());
      if (!changed.ok || changed.outcome_unknown)
        return fail(epoch_recovery("epoch shortcut cutover is unresolved", changed.detail));
    } else if (shortcut != ShellState::new_exact) {
      return fail(epoch_recovery("epoch shortcut is foreign or unreadable"));
    }
    if (effects.inspect_epoch_shortcut(source, target.value()) != ShellState::new_exact)
      return fail(epoch_recovery("epoch shortcut cutover was not verified"));
  }
  if (!lock.value().admission.revalidate(cutover_detail) ||
      !journal.revalidate().ok())
    return fail(epoch_recovery("bootstrap authority changed during shortcut cutover",
                               cutover_detail));
  recorded = publish_epoch_record(journal,
      "40-shortcut-cutover.staging.v1.json", "40-shortcut-cutover.v1.json",
      shortcut_bytes, 6U);
  if (!recorded) return fail(recorded.error());
  const std::string registration_receipt = hash("facman.bootstrap.registration.v1\n" +
      target.value().install_id + "\n" +
      (request.shell_integration ? "cutover\n" : "disabled\n"));
  const std::string registration_bytes = compatibility_bootstrap_phase_bytes(
      "registration_cutover", entered_sha256, registration_receipt);
  auto prior_registration = read_optional_bootstrap_record(
      journal, "50-registration-cutover.v1.json");
  if (!prior_registration || (prior_registration.value().has_value() &&
                              *prior_registration.value() != registration_bytes))
    return fail(!prior_registration ? prior_registration.error() : epoch_recovery(
        "durable registration cutover belongs to another bootstrap"));
  if (!lock.value().admission.revalidate(cutover_detail) ||
      !journal.revalidate().ok())
    return fail(epoch_recovery("bootstrap authority changed before registration cutover",
                               cutover_detail));
  const auto registration = effects.inspect_epoch_registration(source, target.value());
  if (request.shell_integration) {
    if (registration == ShellState::old_exact || registration == ShellState::absent) {
      if (prior_registration.value().has_value())
        return fail(epoch_recovery("completed epoch registration is no longer exact"));
      auto changed = effects.cutover_epoch_registration(source, target.value());
      if (!changed.ok || changed.outcome_unknown)
        return fail(epoch_recovery("epoch registration cutover is unresolved", changed.detail));
    } else if (registration != ShellState::new_exact) {
      return fail(epoch_recovery("epoch registration is foreign or unreadable"));
    }
    if (effects.inspect_epoch_registration(source, target.value()) != ShellState::new_exact)
      return fail(epoch_recovery("epoch registration cutover was not verified"));
  }
  if (!lock.value().admission.revalidate(cutover_detail) ||
      !journal.revalidate().ok())
    return fail(epoch_recovery("bootstrap authority changed during registration cutover",
                               cutover_detail));
  recorded = publish_epoch_record(journal,
      "50-registration-cutover.staging.v1.json", "50-registration-cutover.v1.json",
      registration_bytes, 6U);
  if (!recorded) return fail(recorded.error());
  const std::string complete_bytes = compatibility_bootstrap_phase_bytes(
      "complete", entered_sha256, hash(registration_bytes));
  recorded = publish_epoch_record(journal,
      "60-complete.staging.v1.json", "60-complete.v1.json",
      complete_bytes, 6U);
  if (!recorded || !journal.flush_metadata().ok() ||
      !lock.value().admission.coordinator.flush_metadata().ok())
    return fail(recorded ? epoch_recovery("bootstrap completion was not flushed")
                         : recorded.error());
  return Result::success({"complete", epoch, genesis.take_value(), journal_path});
}

namespace {

facman::core::Result<std::optional<std::string>>
find_unpublished_successor_directory(const fs::path &coordinator_root) {
  facman::platform::StableDirectoryObject coordinator, epochs;
  if (!coordinator.open_no_follow(coordinator_root).ok() ||
      !coordinator.open_child_directory_no_follow("epochs", epochs).ok())
    return facman::core::Result<std::optional<std::string>>::failure(
        epoch_recovery("unpublished successor epoch root cannot be pinned"));
  std::vector<fs::path> names;
  if (!epochs.list_child_names_bounded(kMaximumLifecycleEpochs, names).ok())
    return facman::core::Result<std::optional<std::string>>::failure(
        epoch_recovery("unpublished successor epoch namespace is oversized"));
  std::optional<std::string> missing;
  for (const fs::path &name : names) {
    if (!digest(name.string()))
      return facman::core::Result<std::optional<std::string>>::failure(
          epoch_recovery("epoch namespace contains a foreign entry"));
    facman::platform::StableDirectoryObject epoch;
    if (!epochs.open_child_directory_no_follow(name.string(), epoch).ok())
      return facman::core::Result<std::optional<std::string>>::failure(
          epoch_recovery("epoch namespace contains an unsafe directory"));
    facman::platform::PathIdentity manifest;
    const auto inspected = facman::platform::inspect_path_no_follow(
        coordinator_root / "epochs" / name / "epoch.v1.json", manifest);
    if (!inspected.ok() ||
        (manifest.exists && (manifest.reparse_or_link ||
                             manifest.kind !=
                                 facman::platform::PathObjectKind::regular_file)))
      return facman::core::Result<std::optional<std::string>>::failure(
          epoch_recovery("epoch manifest is unsafe during successor recovery"));
    if (!manifest.exists) {
      if (missing.has_value())
        return facman::core::Result<std::optional<std::string>>::failure(
            epoch_recovery("more than one unpublished successor directory exists"));
      missing = name.string();
    }
    if (!epoch.revalidate().ok())
      return facman::core::Result<std::optional<std::string>>::failure(
          epoch_recovery("epoch directory changed during successor inspection"));
  }
  if (!epochs.revalidate().ok() || !coordinator.revalidate().ok())
    return facman::core::Result<std::optional<std::string>>::failure(
        epoch_recovery("epoch namespace changed during successor inspection"));
  return facman::core::Result<std::optional<std::string>>::success(
      std::move(missing));
}

} // namespace

facman::core::Result<RetiredEpochSuccessorPlan> plan_retired_epoch_successor(
    const fs::path &coordinator_root, const PackageDescriptor &descriptor,
    const std::string &package_sha256) {
  using Result = facman::core::Result<RetiredEpochSuccessorPlan>;
  if (!coordinator_root.is_absolute() || !digest(package_sha256))
    return Result::failure(failure("self_maintenance_input_invalid",
        "retired epoch successor inputs are incomplete"));
  auto discovered = discover_lifecycle_epoch_chain_impl(coordinator_root);
  std::optional<std::string> staging_epoch_id;
  if (!discovered &&
      discovered.error().code == "self_maintenance_epoch_recovery_required") {
    auto partial = find_unpublished_successor_directory(coordinator_root);
    if (!partial) return Result::failure(partial.error());
    if (partial.value().has_value()) {
      staging_epoch_id = *partial.value();
      discovered = discover_lifecycle_epoch_chain_impl(
          coordinator_root, {}, nullptr, {}, {}, nullptr, *staging_epoch_id);
    }
  }
  if (!discovered || discovered.value().epochs.empty())
    return Result::failure(!discovered ? discovered.error() : epoch_recovery(
        "successor install requires a completed real lifecycle epoch"));
  LifecycleEpochChain predecessor_chain = discovered.value();
  const LifecycleEpoch tail = predecessor_chain.epochs.back();
  bool published = false;
  if (tail.retirement_sha256.empty()) {
    if (tail.compatibility_epoch || predecessor_chain.epochs.size() < 2U)
      return Result::failure(epoch_recovery(
          "successor install has no completed real-epoch predecessor"));
    predecessor_chain.epochs.pop_back();
    published = true;
  }
  const LifecycleEpoch &predecessor = predecessor_chain.epochs.back();
  if (predecessor.compatibility_epoch ||
      predecessor.retirement_sha256.empty())
    return Result::failure(epoch_recovery(
        "successor install predecessor is active or incompletely retired"));
  auto source = discover_lifecycle_epoch_active_from_chain(
      coordinator_root, predecessor_chain);
  if (!source || source.value().epoch.epoch_id != predecessor.epoch_id)
    return Result::failure(!source ? source.error() : epoch_recovery(
        "retired predecessor activation changed during successor planning"));
  auto seed = make_generation(descriptor, package_sha256, "facman.self",
      predecessor.logical_root, predecessor.logical_root,
      predecessor.state_root, predecessor.acceptance_root);
  if (!seed) return Result::failure(seed.error());
  LifecycleEpoch epoch;
  epoch.acceptance_root = predecessor.acceptance_root;
  epoch.genesis_generation_id = seed.value().generation_id;
  epoch.logical_root = predecessor.logical_root;
  epoch.predecessor_epoch_id = predecessor.epoch_id;
  epoch.predecessor_manifest_sha256 = predecessor.manifest_sha256;
  epoch.predecessor_retirement_sha256 = predecessor.retirement_sha256;
  epoch.state_root = predecessor.state_root;
  epoch.epoch_id = hash(lifecycle_identity_bytes(epoch));
  epoch.manifest_sha256 = hash(lifecycle_manifest_bytes(epoch));
  if (staging_epoch_id.has_value() && *staging_epoch_id != epoch.epoch_id)
    return Result::failure(epoch_recovery(
        "unpublished successor directory does not bind the supplied package"));
  if (published &&
      (tail.epoch_id != epoch.epoch_id ||
       tail.manifest_sha256 != epoch.manifest_sha256))
    return Result::failure(epoch_recovery(
        "published successor epoch does not match the supplied exact package"));
  auto target = make_epoch_genesis_generation(epoch, descriptor,
                                              package_sha256);
  if (!target) return Result::failure(target.error());
  if (target.value().install_id == source.value().active.active.install_id)
    return Result::failure(epoch_recovery(
        "successor provider identity collides with its retired predecessor"));
  return Result::success({std::move(epoch),
      source.value().active.active, target.take_value(), published,
      staging_epoch_id.has_value()});
}

facman::core::Result<void> recover_retired_successor_manifest(
    const fs::path &coordinator_root,
    const RetiredEpochSuccessorPlan &plan) {
  if (!plan.manifest_staging || plan.manifest_published ||
      !digest(plan.epoch.epoch_id) ||
      !same_path(plan.epoch.acceptance_root, plan.target.acceptance_root))
    return facman::core::Result<void>::failure(epoch_recovery(
        "successor manifest recovery requires one exact unpublished epoch"));
  auto admission = admit_coordinator(
      coordinator_root, plan.epoch.acceptance_root, false);
  if (!admission) return facman::core::Result<void>::failure(admission.error());
  auto lock = acquire(admission.take_value(), "successor.epoch.manifest");
  if (!lock) return facman::core::Result<void>::failure(lock.error());
  auto rechecked = plan_retired_epoch_successor(coordinator_root,
      generation_descriptor(plan.target), plan.target.package_sha256);
  if (!rechecked ||
      rechecked.value().epoch.epoch_id != plan.epoch.epoch_id ||
      rechecked.value().epoch.manifest_sha256 != plan.epoch.manifest_sha256 ||
      rechecked.value().target.install_id != plan.target.install_id ||
      !same_path(rechecked.value().target.install_root,
                 plan.target.install_root))
    return facman::core::Result<void>::failure(!rechecked ? rechecked.error() :
        epoch_recovery("successor predecessor changed before manifest recovery"));
  if (rechecked.value().manifest_published)
    return facman::core::Result<void>::success();
  if (!rechecked.value().manifest_staging)
    return facman::core::Result<void>::failure(epoch_recovery(
        "successor manifest staging disappeared before recovery"));
  facman::platform::StableDirectoryObject epochs, epoch_directory;
  if (!lock.value().admission.coordinator
           .open_child_directory_no_follow_for_relative_writes(
               "epochs", epochs).ok() ||
      !epochs.open_child_directory_no_follow_for_relative_writes(
          plan.epoch.epoch_id, epoch_directory).ok())
    return facman::core::Result<void>::failure(epoch_recovery(
        "successor manifest directory cannot be pinned for recovery"));
  std::vector<fs::path> names;
  if (!epoch_directory.list_child_names_bounded(2U, names).ok() ||
      names.size() > 1U ||
      (!names.empty() &&
       names.front() != fs::path("epoch.staging.v1.json")))
    return facman::core::Result<void>::failure(epoch_recovery(
        "successor manifest directory contains foreign state"));
  const std::string bytes = lifecycle_manifest_bytes(plan.epoch);
  if (hash(bytes) != plan.epoch.manifest_sha256 ||
      !lock.value().admission.coordinator.revalidate().ok() ||
      !epochs.revalidate().ok() || !epoch_directory.revalidate().ok())
    return facman::core::Result<void>::failure(epoch_recovery(
        "successor manifest identity changed before recovery"));
  auto published = publish_epoch_record(epoch_directory,
      "epoch.staging.v1.json", "epoch.v1.json", bytes, 1U);
  if (!published || !epoch_directory.flush_metadata().ok() ||
      !epochs.flush_metadata().ok() ||
      !lock.value().admission.coordinator.flush_metadata().ok())
    return facman::core::Result<void>::failure(!published ? published.error() :
        epoch_recovery("successor manifest recovery was not flushed"));
  return facman::core::Result<void>::success();
}

facman::core::Result<RetirementResponse> retire_active(
    const RetirementRequest &request, RetirementEffects &effects) {
  if (request.epoch_mode) {
    auto selected = resolve_authoritative_active_state(request.coordinator_root);
    if (!selected && selected.error().code !=
                         "self_maintenance_retirement_recovery_required")
      return facman::core::Result<RetirementResponse>::failure(selected.error());
    if (selected && selected.value().has_value() &&
        !selected.value()->epoch.has_value())
      return facman::core::Result<RetirementResponse>::failure(epoch_recovery(
          "epoch retirement cannot consume flat compatibility authority"));
  }
  const auto inspect_chain = [&]()
      -> facman::core::Result<std::optional<ActivationChain>> {
    if (!request.epoch_mode)
      return discover_activation_chain(request.coordinator_root);
    auto epoch = discover_epoch_retirement_chain(request.coordinator_root);
    if (!epoch)
      return facman::core::Result<std::optional<ActivationChain>>::failure(
          epoch.error());
    return facman::core::Result<std::optional<ActivationChain>>::success(
        std::optional<ActivationChain>(epoch.take_value()));
  };
  auto reviewed = inspect_chain();
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
  if (request.epoch_mode &&
      (!request.logical_root.is_absolute() ||
       !request.state_root.is_absolute() ||
       !request.acceptance_root.is_absolute() ||
       (!same_path(request.logical_root, active.logical_root) &&
        !same_path(request.logical_root, active.install_root)) ||
       !same_path(request.state_root, active.state_root) ||
       !same_path(request.acceptance_root, active.acceptance_root)))
    return facman::core::Result<RetirementResponse>::failure(failure(
        "self_maintenance_lineage_mismatch",
        "epoch retirement roots do not bind its authoritative generation"));
  for (const auto &step : reviewed_steps) {
    if (!same_path(step.generation.logical_root, active.logical_root) ||
        !same_path(step.generation.state_root, active.state_root) ||
        !same_path(step.generation.acceptance_root, active.acceptance_root))
      return facman::core::Result<RetirementResponse>::failure(failure(
          "self_maintenance_retirement_recovery_required",
          "activation chain generations do not share one exact authority"));
  }
  const fs::path directory = request.epoch_mode
      ? epoch_retirement_directory(request.coordinator_root, review)
      : retirement_directory(request.coordinator_root, review);
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
  const auto require_authority = [&]() -> facman::core::Result<void> {
    if (!request.epoch_mode)
      return require_flat_retirement_epoch_absence(held.value());
    auto current_epoch = discover_epoch_retirement_chain(request.coordinator_root);
    if (!current_epoch ||
        retirement_chain_digest(current_epoch.value()) !=
            retirement_chain_digest(review))
      return facman::core::Result<void>::failure(!current_epoch
          ? current_epoch.error() : epoch_recovery(
              "authoritative epoch lineage changed during retirement"));
    std::string detail;
    if (!held.value().admission.revalidate(detail))
      return facman::core::Result<void>::failure(epoch_recovery(
          "epoch retirement authority changed at its effect boundary", detail));
    return facman::core::Result<void>::success();
  };
  auto authority_ready = require_authority();
  if (!authority_ready)
    return facman::core::Result<RetirementResponse>::failure(
        authority_ready.error());

  // Re-read the complete chain under the global coordinator lock.  The
  // journal is intentionally bound to this exact head and all ordered
  // generation records, never to an inferred current install root.
  auto current = inspect_chain();
  if (!current || !current.value().has_value() ||
      retirement_chain_digest(*current.value()) != retirement_chain_digest(review))
    return facman::core::Result<RetirementResponse>::failure(failure(
        "self_maintenance_retirement_recovery_required",
        "activation chain changed before retirement could begin"));
  const ActivationChain chain = *current.value();
  const auto steps = retirement_steps(chain);
  std::error_code preflight_status;
  const bool existing_journal = fs::exists(directory, preflight_status);
  if (preflight_status)
    return facman::core::Result<RetirementResponse>::failure(failure(
        "self_maintenance_retirement_recovery_required",
        "retirement journal could not be observed before preflight",
        preflight_status.message()));
  if (!existing_journal) {
    // A foreign file in any retained generation must refuse the entire
    // uninstall before the first durable retirement intent or provider effect.
    // Per-step inspection below still revalidates at the actual effect edge.
    for (const auto &step : steps) {
      auto ready = require_authority();
      if (!ready)
        return facman::core::Result<RetirementResponse>::failure(ready.error());
      auto inspected = effects.inspect_retirement_generation(
          step.generation, step.active, coordinator_lock);
      if (!inspected)
        return facman::core::Result<RetirementResponse>::failure(
            inspected.error().code == "self_setup_provider_refused"
                ? inspected.error()
                : failure("self_maintenance_retirement_recovery_required",
                    "provider or native identity is ambiguous before retirement",
                    inspected.error().code + ": " + inspected.error().message));
    }
  }
  const fs::path retirement_root = request.coordinator_root /
      (request.epoch_mode ? "epoch-retirements" : "retirements");
  LifecycleEpochChain validated_epochs;
  if (request.epoch_mode) {
    auto observed = discover_lifecycle_epoch_chain_impl(request.coordinator_root);
    if (!observed)
      return facman::core::Result<RetirementResponse>::failure(
          observed.error());
    validated_epochs = observed.take_value();
  }
  std::error_code status;
  if (fs::exists(retirement_root, status)) {
    if (status || fs::symlink_status(retirement_root, status).type() !=
                      fs::file_type::directory || status)
      return facman::core::Result<RetirementResponse>::failure(failure(
          "self_maintenance_retirement_recovery_required",
          "retirement journal root is unavailable"));
    for (fs::directory_iterator it(retirement_root, status), end;
         !status && it != end; it.increment(status)) {
      const bool current_journal = it->path().lexically_normal() ==
          directory.lexically_normal();
      const bool historical = request.epoch_mode &&
          std::any_of(validated_epochs.epochs.begin(),
              validated_epochs.epochs.end(),
              [&](const LifecycleEpoch &epoch) {
                return !epoch.compatibility_epoch &&
                    !epoch.retirement_sha256.empty() &&
                    epoch.retirement_journal_name ==
                        it->path().filename().string();
              });
      if (it->symlink_status(status).type() != fs::file_type::directory || status ||
          (!current_journal && !historical))
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
    current = inspect_chain();
    if (!current || !current.value().has_value() ||
        retirement_chain_digest(*current.value()) != retirement_chain_digest(chain))
      return facman::core::Result<RetirementResponse>::failure(failure(
          "self_maintenance_retirement_recovery_required",
          "activation chain changed before a retirement effect"));
    authority_ready = require_authority();
    if (!authority_ready)
      return facman::core::Result<RetirementResponse>::failure(
          authority_ready.error());
    auto inspected = effects.inspect_retirement_generation(
        steps[index].generation, steps[index].active, coordinator_lock);
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
    authority_ready = require_authority();
    if (!authority_ready)
      return facman::core::Result<RetirementResponse>::failure(
          authority_ready.error());
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
  // A direct legacy-adoption caller must not write flat history after an
  // epoch namespace has appeared, even if it bypasses the public Setup route.
  auto epochs_absent = require_flat_retirement_epoch_absence(held.value());
  if (!epochs_absent)
    return facman::core::Result<ActiveState>::failure(epochs_absent.error());
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
  // Public routing selects the real epoch first, but this older flat entry
  // point is callable directly. Fence it under the same coordinator lock.
  auto epochs_absent = require_flat_retirement_epoch_absence(held.value());
  if (!epochs_absent)
    return facman::core::Result<Response>::failure(epochs_absent.error());
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
    epochs_absent = require_flat_retirement_epoch_absence(held.value());
    if (!epochs_absent)
      return facman::core::Result<Response>::failure(epochs_absent.error());
    auto final_phase = record_phase(request, transition,
                                    "70-activation-recorded", hash(activation));
    if (!final_phase)
      return facman::core::Result<Response>::failure(final_phase.error());
    const auto retired = effects.retire_shortcut_backup(transition);
    if (!retired.ok || retired.outcome_unknown ||
        !digest(retired.receipt_sha256))
      return facman::core::Result<Response>::failure(effect_error(
          "self_maintenance_shortcut_backup_retirement_failed",
          "completed activation shortcut backup retirement failed",
          retired).error());
    final_phase = record_phase(request, transition,
                               "80-shortcut-backup-retired",
                               retired.receipt_sha256);
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
      epochs_absent = require_flat_retirement_epoch_absence(held.value());
      if (!epochs_absent)
        return facman::core::Result<Response>::failure(epochs_absent.error());
      const auto prepared_provider = effects.prepare_install_local(transition);
      if (!prepared_provider.ok)
        return facman::core::Result<Response>::failure(effect_error(
            "self_maintenance_source_retention_failed",
            "candidate installation inputs could not be retained",
            prepared_provider).error());
      recorded = record_phase(request, transition, "10-provider-entered");
      if (!recorded) return facman::core::Result<Response>::failure(recorded.error());
      epochs_absent = require_flat_retirement_epoch_absence(held.value());
      if (!epochs_absent)
        return facman::core::Result<Response>::failure(epochs_absent.error());
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
    epochs_absent = require_flat_retirement_epoch_absence(held.value());
    if (!epochs_absent)
      return facman::core::Result<Response>::failure(epochs_absent.error());
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
  epochs_absent = require_flat_retirement_epoch_absence(held.value());
  if (!epochs_absent)
    return facman::core::Result<Response>::failure(epochs_absent.error());

  ShellState shortcut = effects.inspect_shortcut(transition);
  if (shortcut == ShellState::foreign || shortcut == ShellState::unreadable ||
      shortcut == ShellState::absent)
    return facman::core::Result<Response>::failure(failure(
        "self_maintenance_shell_unsafe", "Start Menu shortcut is not the exact old or new FacMan object"));
  if (shortcut == ShellState::old_exact) {
    epochs_absent = require_flat_retirement_epoch_absence(held.value());
    if (!epochs_absent)
      return facman::core::Result<Response>::failure(epochs_absent.error());
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
    epochs_absent = require_flat_retirement_epoch_absence(held.value());
    if (!epochs_absent)
      return facman::core::Result<Response>::failure(epochs_absent.error());
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
  epochs_absent = require_flat_retirement_epoch_absence(held.value());
  if (!epochs_absent)
    return facman::core::Result<Response>::failure(epochs_absent.error());
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
  epochs_absent = require_flat_retirement_epoch_absence(held.value());
  if (!epochs_absent)
    return facman::core::Result<Response>::failure(epochs_absent.error());
  const auto retired = effects.retire_shortcut_backup(transition);
  if (!retired.ok || retired.outcome_unknown ||
      !digest(retired.receipt_sha256))
    return facman::core::Result<Response>::failure(effect_error(
        "self_maintenance_shortcut_backup_retirement_failed",
        "shortcut backup retirement failed after activation commit",
        retired).error());
  recorded = record_phase(request, transition,
                          "80-shortcut-backup-retired",
                          retired.receipt_sha256);
  if (!recorded)
    return facman::core::Result<Response>::failure(recorded.error());
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
