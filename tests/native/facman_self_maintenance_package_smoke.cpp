// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_self_maintenance.h"

#include "fl_archive.h"

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <vector>

namespace fs = std::filesystem;

namespace {

bool write(const fs::path &path, const std::string &bytes) {
  fs::create_directories(path.parent_path());
  std::ofstream output(path, std::ios::binary | std::ios::trunc);
  output << bytes;
  return static_cast<bool>(output);
}

std::string descriptor(const std::string &version) {
  return "{\"automatic_update\":false,\"entrypoints\":{"
      "\"cli_relative_path\":\"bin/facman.exe\","
      "\"gui_relative_path\":\"FacMan.exe\","
      "\"maintenance_relative_path\":\"maintenance/FacManSetup.exe\"},"
      "\"facman_source_revision\":\"" + std::string(40, 'a') +
      "\",\"generation_relative_path\":\"generations/" + version +
      "\",\"package_layout\":\"versioned_generation_with_maintenance_v1\","
      "\"product_id\":\"facman\",\"product_version\":\"" + version +
      "\",\"schema\":\"facman.self_maintenance_package.v1\","
      "\"setup_protocol\":\"facman.self_maintenance.v1\","
      "\"universal_setup_revision\":\"" + std::string(40, 'b') + "\"}";
}

std::string current(const std::string &version) {
  return "{\"automatic_update\":false,\"facman_source_revision\":\"" +
      std::string(40, 'a') + "\",\"generation\":\"generations/" + version +
      "\",\"portable_package\":\"facman.zip\",\"portable_sha256\":\"" +
      std::string(64, 'c') +
      "\",\"product_id\":\"facman\",\"schema\":"
      "\"facman.current_generation.v1\",\"universal_setup_revision\":\"" +
      std::string(40, 'b') + "\",\"version\":\"" + version +
      "\",\"workspace_preserved\":true}";
}

fs::path package(const fs::path &root, const std::string &name,
                 const std::string &descriptor_version,
                 const std::string &current_version) {
  const fs::path source = root / (name + "-source");
  const fs::path descriptor_path = source / "descriptor.json";
  const fs::path current_path = source / "current.json";
  const fs::path binary_path = source / "binary";
  if (!write(descriptor_path, descriptor(descriptor_version)) ||
      !write(current_path, current(current_version)) ||
      !write(binary_path, "synthetic binary"))
    return {};
  std::vector<facman::archive::WriteEntry> entries{
      {"facman/state/self-maintenance-package.v1.json", descriptor_path, false},
      {"facman/state/current-generation.v1.json", current_path, false},
      {"facman/generations/" + descriptor_version + "/FacMan.exe",
       binary_path, false},
      {"facman/generations/" + descriptor_version + "/bin/facman.exe",
       binary_path, false},
      {"facman/maintenance/FacManSetup.exe", binary_path, false}};
  facman::archive::WriteOptions options;
  options.method = facman::archive::CompressionMethod::stored;
  options.limits = facman::archive::PackageArchivePolicy::limits();
  facman::archive::WriteResult result;
  const auto status = facman::archive::write_to_new_owned_staging(
      root / (name + "-staging"), name + ".zip", entries, options, result);
  return status.ok() ? result.archive_path : fs::path();
}

bool require(bool condition, const char *message) {
  if (!condition) std::cerr << message << '\n';
  return condition;
}

} // namespace

int main() {
  const fs::path root = fs::temp_directory_path() /
      ("facman-maintenance-package-" + std::to_string(
          static_cast<unsigned long long>(std::chrono::steady_clock::now()
              .time_since_epoch().count())));
  std::error_code ignored;
  fs::remove_all(root, ignored);
  fs::create_directories(root);
  bool ok = true;
  const fs::path valid = package(root, "valid", "0.1.0-alpha.6",
                                 "0.1.0-alpha.6");
  auto inspected = facman::self_maintenance::inspect_package(valid);
  ok &= require(inspected && inspected.value().package_sha256.size() == 64U &&
                    inspected.value().maintenance_launcher_sha256.size() == 64U &&
                    inspected.value().descriptor.product_version ==
                        "0.1.0-alpha.6",
                "strict maintenance package was not accepted");
  const fs::path launcher = root / "extracted" / "FacManSetup.exe";
  fs::create_directories(launcher.parent_path());
  ok &= require(inspected &&
                    facman::self_maintenance::extract_maintenance_launcher(
                        inspected.value(), launcher) &&
                    fs::is_regular_file(launcher),
                "package maintenance launcher was not extracted safely");
  const fs::path mismatch = package(root, "mismatch", "0.1.0-alpha.6",
                                    "0.1.0-alpha.5");
  ok &= require(!facman::self_maintenance::inspect_package(mismatch),
                "mismatched package metadata was accepted");
  const fs::path legacy = root / "legacy";
  write(legacy / "state" / "current-generation.v1.json",
        current("0.1.0-alpha.5"));
  auto legacy_descriptor =
      facman::self_maintenance::inspect_legacy_descriptor(legacy);
  ok &= require(legacy_descriptor &&
                    legacy_descriptor.value().product_version ==
                        "0.1.0-alpha.5" &&
                    legacy_descriptor.value().setup_protocol ==
                        "facman.self_maintenance.v1",
                "legacy current-generation metadata was not reconstructed");
  fs::remove_all(root, ignored);
  return ok ? 0 : 1;
}
