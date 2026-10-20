// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_self_maintenance.h"

#include "fl_archive.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"

#include <algorithm>
#include <filesystem>
#include <initializer_list>
#include <string>

namespace fs = std::filesystem;
namespace json = facman::core::json;

namespace facman::self_maintenance {
namespace {

facman::core::Error error(std::string code, std::string message,
                          std::string detail = {}) {
  facman::core::Error result{std::move(code), std::move(message), ""};
  result.detail = std::move(detail);
  return result;
}

bool exact_keys(const json::Value &value,
                std::initializer_list<const char *> keys) {
  if (!value.is_object() || value.size() != keys.size()) return false;
  return std::all_of(keys.begin(), keys.end(),
      [&](const char *key) { return value.find(key) != nullptr; });
}

std::string string_field(const json::Value &value, const char *key) {
  const json::Value *field = value.find(key);
  return field != nullptr && field->string_value()
      ? field->string_value().value() : std::string();
}

bool bool_field(const json::Value &value, const char *key, bool expected) {
  const json::Value *field = value.find(key);
  return field != nullptr && field->bool_value() &&
      field->bool_value().value() == expected;
}

bool lower_hex(const std::string &value, std::size_t size) {
  return value.size() == size &&
      std::all_of(value.begin(), value.end(), [](unsigned char character) {
        return (character >= '0' && character <= '9') ||
            (character >= 'a' && character <= 'f');
      });
}

facman::core::Result<std::string> read_stable(const fs::path &path,
                                               std::uint64_t maximum) {
  facman::platform::StableInputFile input;
  const auto opened = input.open_no_follow_pinned(path);
  if (!opened.ok() || input.size() == 0U || input.size() > maximum)
    return facman::core::Result<std::string>::failure(error(
        "self_maintenance_package_incompatible",
        "maintenance metadata is missing, unsafe, or over budget",
        opened.detail));
  std::string bytes(static_cast<std::size_t>(input.size()), '\0');
  if (input.read_at(0, bytes.data(), bytes.size()) != bytes.size() ||
      !input.revalidate_path().ok())
    return facman::core::Result<std::string>::failure(error(
        "self_maintenance_package_incompatible",
        "maintenance metadata changed while it was read"));
  return facman::core::Result<std::string>::success(std::move(bytes));
}

facman::core::Result<PackageDescriptor> parse_descriptor(
    const std::string &bytes) {
  json::Limits limits;
  limits.maximum_bytes = 64U * 1024U;
  limits.maximum_depth = 8U;
  limits.maximum_nodes = 64U;
  limits.maximum_string_bytes = 8192U;
  auto document = json::parse(bytes, limits);
  const json::Value *entrypoints = document && document.value().is_object()
      ? document.value().find("entrypoints") : nullptr;
  if (!document || !exact_keys(document.value(),
          {"schema", "product_id", "product_version",
           "generation_relative_path", "facman_source_revision",
           "universal_setup_revision", "setup_protocol", "package_layout",
           "entrypoints", "automatic_update"}) ||
      entrypoints == nullptr ||
      !exact_keys(*entrypoints, {"gui_relative_path", "cli_relative_path",
                                "maintenance_relative_path"}) ||
      string_field(document.value(), "schema") !=
          "facman.self_maintenance_package.v1" ||
      !bool_field(document.value(), "automatic_update", false))
    return facman::core::Result<PackageDescriptor>::failure(error(
        "self_maintenance_package_incompatible",
        "maintenance descriptor has an incompatible exact schema"));
  PackageDescriptor result;
  result.product_id = string_field(document.value(), "product_id");
  result.product_version = string_field(document.value(), "product_version");
  result.generation_relative_path =
      string_field(document.value(), "generation_relative_path");
  result.facman_source_revision =
      string_field(document.value(), "facman_source_revision");
  result.universal_setup_revision =
      string_field(document.value(), "universal_setup_revision");
  result.setup_protocol = string_field(document.value(), "setup_protocol");
  result.package_layout = string_field(document.value(), "package_layout");
  result.gui_relative_path = string_field(*entrypoints, "gui_relative_path");
  result.cli_relative_path = string_field(*entrypoints, "cli_relative_path");
  result.maintenance_relative_path =
      string_field(*entrypoints, "maintenance_relative_path");
  result.automatic_update = false;
  return facman::core::Result<PackageDescriptor>::success(std::move(result));
}

facman::core::Result<PackageDescriptor> parse_current_generation(
    const std::string &bytes) {
  json::Limits limits;
  limits.maximum_bytes = 64U * 1024U;
  limits.maximum_depth = 4U;
  limits.maximum_nodes = 32U;
  limits.maximum_string_bytes = 8192U;
  auto document = json::parse(bytes, limits);
  if (!document || !exact_keys(document.value(),
          {"schema", "product_id", "version", "generation",
           "portable_package", "portable_sha256", "facman_source_revision",
           "universal_setup_revision", "workspace_preserved",
           "automatic_update"}) ||
      string_field(document.value(), "schema") !=
          "facman.current_generation.v1" ||
      string_field(document.value(), "product_id") != "facman" ||
      !bool_field(document.value(), "workspace_preserved", true) ||
      !bool_field(document.value(), "automatic_update", false) ||
      !lower_hex(string_field(document.value(), "portable_sha256"), 64U) ||
      !lower_hex(string_field(document.value(), "facman_source_revision"), 40U) ||
      !lower_hex(string_field(document.value(), "universal_setup_revision"), 40U))
    return facman::core::Result<PackageDescriptor>::failure(error(
        "self_maintenance_package_incompatible",
        "current-generation metadata has an incompatible exact schema"));
  const std::string version = string_field(document.value(), "version");
  const std::string portable = string_field(document.value(), "portable_package");
  const fs::path portable_path = facman::platform::path_from_utf8(portable);
  if (version.empty() || version.size() > 160U ||
      string_field(document.value(), "generation") !=
          "generations/" + version || portable.empty() ||
      portable_path != portable_path.filename())
    return facman::core::Result<PackageDescriptor>::failure(error(
        "self_maintenance_package_incompatible",
        "current-generation identity is invalid"));
  PackageDescriptor result;
  result.product_id = "facman";
  result.product_version = version;
  result.generation_relative_path = "generations/" + version;
  result.facman_source_revision =
      string_field(document.value(), "facman_source_revision");
  result.universal_setup_revision =
      string_field(document.value(), "universal_setup_revision");
  result.setup_protocol = "facman.self_maintenance.v1";
  result.package_layout = "versioned_generation_with_maintenance_v1";
  result.gui_relative_path = "FacMan.exe";
  result.cli_relative_path = "bin/facman.exe";
  result.maintenance_relative_path = "maintenance/FacManSetup.exe";
  return facman::core::Result<PackageDescriptor>::success(std::move(result));
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

} // namespace

facman::core::Result<bool> has_self_maintenance_metadata(
    const fs::path &package) {
  if (!package.is_absolute())
    return facman::core::Result<bool>::failure(error(
        "self_maintenance_package_incompatible",
        "maintenance package path must be absolute"));
  archive::Limits limits = archive::PackageArchivePolicy::limits();
  limits.maximum_archive_bytes = 16ULL * 1024ULL * 1024ULL * 1024ULL;
  archive::Plan plan;
  const auto inspected = archive::inspect_archive(package, limits, plan);
  if (!inspected.ok())
    return facman::core::Result<bool>::failure(error(
        "self_maintenance_package_incompatible",
        "maintenance package archive is unsafe", inspected.detail));
  for (const auto &entry : plan.entries)
    if (entry.path == "facman/state/self-maintenance-package.v1.json")
      return facman::core::Result<bool>::success(true);
  return facman::core::Result<bool>::success(false);
}

facman::core::Result<PackageInspection> inspect_package(
    const fs::path &package) {
  if (!package.is_absolute())
    return facman::core::Result<PackageInspection>::failure(error(
        "self_maintenance_package_incompatible",
        "maintenance package path must be absolute"));
  archive::Limits limits = archive::PackageArchivePolicy::limits();
  limits.maximum_archive_bytes = 16ULL * 1024ULL * 1024ULL * 1024ULL;
  archive::Plan archive_plan;
  const auto inspected = archive::inspect_archive(package, limits, archive_plan);
  if (!inspected.ok())
    return facman::core::Result<PackageInspection>::failure(error(
        "self_maintenance_package_incompatible",
        "maintenance package archive is unsafe", inspected.detail));
  constexpr char descriptor_name[] =
      "facman/state/self-maintenance-package.v1.json";
  constexpr char generation_name[] =
      "facman/state/current-generation.v1.json";
  const archive::Entry *descriptor_entry = nullptr;
  const archive::Entry *generation_entry = nullptr;
  for (const auto &entry : archive_plan.entries) {
    if (entry.path == descriptor_name) {
      if (descriptor_entry != nullptr || entry.directory ||
          entry.expanded_size == 0U || entry.expanded_size > 64U * 1024U)
        return facman::core::Result<PackageInspection>::failure(error(
            "self_maintenance_package_incompatible",
            "maintenance descriptor is duplicated or over budget"));
      descriptor_entry = &entry;
    }
    if (entry.path == generation_name) {
      if (generation_entry != nullptr || entry.directory ||
          entry.expanded_size == 0U || entry.expanded_size > 64U * 1024U)
        return facman::core::Result<PackageInspection>::failure(error(
            "self_maintenance_package_incompatible",
            "current-generation metadata is duplicated or over budget"));
      generation_entry = &entry;
    }
  }
  if (descriptor_entry == nullptr || generation_entry == nullptr)
    return facman::core::Result<PackageInspection>::failure(error(
        "self_maintenance_package_incompatible",
        "maintenance package metadata is missing"));
  auto stream = [&](const archive::Entry &entry,
                    std::string &bytes) -> archive::Status {
    bytes.reserve(static_cast<std::size_t>(entry.expanded_size));
    return archive::stream_entry(archive_plan, entry.index, limits,
        [&](const unsigned char *data, std::size_t count) {
          bytes.append(reinterpret_cast<const char *>(data), count);
          return bytes.size() <= 64U * 1024U;
        });
  };
  std::string descriptor_bytes;
  std::string generation_bytes;
  const auto descriptor_status = stream(*descriptor_entry, descriptor_bytes);
  const auto generation_status = stream(*generation_entry, generation_bytes);
  if (!descriptor_status.ok() || !generation_status.ok())
    return facman::core::Result<PackageInspection>::failure(error(
        "self_maintenance_package_incompatible",
        "maintenance package metadata could not be verified",
        !descriptor_status.ok() ? descriptor_status.detail
                                : generation_status.detail));
  auto descriptor = parse_descriptor(descriptor_bytes);
  auto generation = parse_current_generation(generation_bytes);
  if (!descriptor || !generation ||
      !same_descriptor(descriptor.value(), generation.value()))
    return facman::core::Result<PackageInspection>::failure(error(
        "self_maintenance_package_incompatible",
        "maintenance descriptor and current-generation identity differ",
        !descriptor ? descriptor.error().message
                    : !generation ? generation.error().message : std::string()));
  const std::string prefix = "facman/" +
      descriptor.value().generation_relative_path + "/";
  const std::string gui = prefix + descriptor.value().gui_relative_path;
  const std::string cli = prefix + descriptor.value().cli_relative_path;
  const std::string maintenance =
      "facman/" + descriptor.value().maintenance_relative_path;
  auto exact_regular = [&](const std::string &path) {
    return std::count_if(archive_plan.entries.begin(), archive_plan.entries.end(),
        [&](const archive::Entry &entry) {
          return entry.path == path && !entry.directory &&
              entry.expanded_size != 0U;
        }) == 1;
  };
  if (!exact_regular(gui) || !exact_regular(cli) ||
      !exact_regular(maintenance))
    return facman::core::Result<PackageInspection>::failure(error(
        "self_maintenance_package_incompatible",
        "maintenance package does not contain every exact entrypoint"));
  const archive::Entry *maintenance_entry = nullptr;
  for (const auto &entry : archive_plan.entries)
    if (entry.path == maintenance && !entry.directory) maintenance_entry = &entry;
  facman::base::Sha256Hasher maintenance_hasher;
  const auto maintenance_status = archive::stream_entry(archive_plan,
      maintenance_entry->index, limits, [&](const unsigned char *data, std::size_t count) {
        maintenance_hasher.update(data, count);
        return true;
      });
  if (!maintenance_status.ok())
    return facman::core::Result<PackageInspection>::failure(error(
        "self_maintenance_package_changed", "maintenance launcher could not be identified",
        maintenance_status.detail));
  const std::string maintenance_digest = maintenance_hasher.finish();
  std::string digest;
  const auto hashed = archive::archive_sha256(archive_plan, limits, digest);
  if (!hashed.ok() || !lower_hex(digest, 64U))
    return facman::core::Result<PackageInspection>::failure(error(
        "self_maintenance_package_changed",
        "maintenance package could not be identified", hashed.detail));
  return facman::core::Result<PackageInspection>::success(
      {package.lexically_normal(), std::move(digest), maintenance_digest,
       descriptor.take_value()});
}

facman::core::Result<void> extract_maintenance_launcher(
    const PackageInspection &package, const fs::path &destination) {
  if (!package.package.is_absolute() || !destination.is_absolute())
    return facman::core::Result<void>::failure(error(
        "self_maintenance_package_incompatible",
        "maintenance launcher extraction paths must be absolute"));
  archive::Limits limits = archive::PackageArchivePolicy::limits();
  limits.maximum_archive_bytes = 16ULL * 1024ULL * 1024ULL * 1024ULL;
  archive::Plan plan;
  auto status = archive::inspect_archive(package.package, limits, plan);
  std::string digest;
  if (status.ok()) status = archive::archive_sha256(plan, limits, digest);
  if (!status.ok() || digest != package.package_sha256)
    return facman::core::Result<void>::failure(error(
        "self_maintenance_package_changed",
        "maintenance package changed before launcher extraction",
        status.detail));
  const archive::Entry *launcher = nullptr;
  for (const auto &entry : plan.entries) {
    if (entry.path != "facman/maintenance/FacManSetup.exe") continue;
    if (launcher != nullptr || entry.directory || entry.expanded_size == 0U ||
        entry.expanded_size > 256ULL * 1024ULL * 1024ULL)
      return facman::core::Result<void>::failure(error(
          "self_maintenance_package_incompatible",
          "maintenance launcher is duplicated or over budget"));
    launcher = &entry;
  }
  if (launcher == nullptr)
    return facman::core::Result<void>::failure(error(
        "self_maintenance_package_incompatible",
        "maintenance launcher is missing from the package"));
  const fs::path pending = destination.parent_path() /
      facman::platform::path_from_utf8(
          "." + facman::platform::path_to_utf8(destination.filename()) +
          ".pending");
  facman::platform::DurableOutputFile output;
  const auto created = output.create_exclusive(pending, launcher->expanded_size);
  if (!created.ok())
    return facman::core::Result<void>::failure(error(
        "self_maintenance_package_incompatible",
        "maintenance launcher staging file could not be created",
        created.detail));
  std::uint64_t offset = 0U;
  status = archive::stream_entry(plan, launcher->index, limits,
      [&](const unsigned char *data, std::size_t count) {
        const bool written = output.write_at(offset, data, count) == count;
        offset += written ? count : 0U;
        return written;
      });
  if (!status.ok() || offset != launcher->expanded_size) {
    const auto discarded = output.discard_open();
    return facman::core::Result<void>::failure(error(
        "self_maintenance_package_incompatible",
        "maintenance launcher could not be extracted",
        status.detail + (discarded.ok() ? std::string()
                                        : "; cleanup: " + discarded.detail)));
  }
  const auto published = output.publish_no_replace(destination);
  if (!published.ok()) {
    const auto discarded = output.discard_open();
    return facman::core::Result<void>::failure(error(
        "self_maintenance_package_incompatible",
        "maintenance launcher could not be published",
        published.detail + (discarded.ok() ? std::string()
                                           : "; cleanup: " + discarded.detail)));
  }
  return facman::core::Result<void>::success();
}

facman::core::Result<PackageDescriptor> inspect_legacy_descriptor(
    const fs::path &install_root) {
  if (!install_root.is_absolute())
    return facman::core::Result<PackageDescriptor>::failure(error(
        "self_maintenance_legacy_invalid",
        "legacy install root must be absolute"));
  auto bytes = read_stable(
      install_root / "state" / "current-generation.v1.json", 64U * 1024U);
  if (!bytes)
    return facman::core::Result<PackageDescriptor>::failure(bytes.error());
  return parse_current_generation(bytes.value());
}

} // namespace facman::self_maintenance
