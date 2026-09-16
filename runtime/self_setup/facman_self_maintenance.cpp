// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_self_maintenance.h"

#include "fl_json.h"
#include "fl_local_operation_lock.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_file_io.h"

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
  std::size_t visited = 1U;
  for (;;) {
    const auto child = std::find_if(nodes.begin(), nodes.end(),
        [&](const Node &candidate) {
          return candidate.previous_name == head->name;
        });
    if (child == nodes.end()) break;
    head = &*child;
    ++visited;
  }
  if (visited != nodes.size() ||
      (!expected_name.empty() && head->name != expected_name) ||
      (!expected_digest.empty() && head->digest != expected_digest))
    return facman::core::Result<ActivationHead>::failure(failure(
        "self_maintenance_activation_changed",
        "reviewed activation is not the unique current chain head"));
  return facman::core::Result<ActivationHead>::success(
      {head->name, head->digest, head->source_generation_id,
       head->target_generation_id, head->previous_name,
       head->previous_digest});
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
  return same_path(generation.gui, expected_gui) &&
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
  if (!exact_generation_paths(result))
    return facman::core::Result<Generation>::failure(failure(
        "self_maintenance_input_invalid", "generation paths are invalid"));
  return facman::core::Result<Generation>::success(std::move(result));
}

facman::core::Result<std::optional<ActiveState>> discover_active(
    const fs::path &coordinator_root) {
  if (!coordinator_root.is_absolute())
    return facman::core::Result<std::optional<ActiveState>>::failure(failure(
        "self_maintenance_input_invalid", "coordinator root must be absolute"));
  const fs::path directory = coordinator_root / "activations";
  std::error_code status;
  if (!fs::exists(directory, status)) {
    if (status)
      return facman::core::Result<std::optional<ActiveState>>::failure(failure(
          "self_maintenance_activation_changed",
          "activation directory could not be observed", status.message()));
    return facman::core::Result<std::optional<ActiveState>>::success({});
  }
  if (!fs::is_directory(directory, status) || status)
    return facman::core::Result<std::optional<ActiveState>>::failure(failure(
        "self_maintenance_activation_changed",
        "activation path is not a directory"));
  auto first = fs::directory_iterator(directory, status);
  if (status)
    return facman::core::Result<std::optional<ActiveState>>::failure(failure(
        "self_maintenance_activation_changed",
        "activation directory could not be enumerated", status.message()));
  if (first == fs::directory_iterator())
    return facman::core::Result<std::optional<ActiveState>>::success({});
  auto head = validate_activation_head(coordinator_root, {}, {});
  if (!head)
    return facman::core::Result<std::optional<ActiveState>>::failure(
        head.error());
  auto active = parse_generation_record(coordinator_root,
                                        head.value().target_generation_id);
  if (!active)
    return facman::core::Result<std::optional<ActiveState>>::failure(
        active.error());
  ActiveState result;
  result.active = active.take_value();
  result.activation_name = head.value().name;
  result.activation_sha256 = head.value().digest;
  if (head.value().source_generation_id !=
      head.value().target_generation_id) {
    auto previous = parse_generation_record(
        coordinator_root, head.value().source_generation_id);
    if (!previous)
      return facman::core::Result<std::optional<ActiveState>>::failure(
          previous.error());
    result.previous = previous.take_value();
  }
  return facman::core::Result<std::optional<ActiveState>>::success(
      std::optional<ActiveState>(std::move(result)));
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
  const std::string logical_identity = hash(
      "facman.self.logical-root.v1\n" +
      facman::platform::path_to_utf8(request.logical_root.lexically_normal()) + "\n");
  const fs::path target_root = request.logical_root.parent_path() /
      facman::platform::path_from_utf8("FacMan.generation." +
          logical_identity + "." + id);
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

} // namespace facman::self_maintenance
