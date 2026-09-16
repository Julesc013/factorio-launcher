// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_SELF_MAINTENANCE_PROVIDER_H
#define FACMAN_SELF_MAINTENANCE_PROVIDER_H

#include "facman_self_maintenance.h"
#include "facman_self_setup.h"

#include <filesystem>
#include <memory>
#include <string>

namespace facman::self_maintenance {

struct InstalledIdentity {
  std::string install_id;
  std::string product_version;
  std::string source_archive_sha256;
  std::string recipe_digest;
  std::string provider_revision;
  std::string transaction_id;
  std::string ownership_manifest_digest;
  std::string installed_state_digest;
  std::filesystem::path install_root;
  std::string gui_relative_path;
  std::string cli_relative_path;
  std::string maintenance_relative_path;
};

class ProviderBridge {
public:
  ProviderBridge(std::filesystem::path state_root,
                 std::filesystem::path acceptance_root,
                 facman::self_setup::ProviderEffects *effects = nullptr,
                 facman::self_setup::Clock *clock = nullptr);
  ~ProviderBridge();
  ProviderBridge(ProviderBridge &&) noexcept;
  ProviderBridge &operator=(ProviderBridge &&) noexcept;
  ProviderBridge(const ProviderBridge &) = delete;
  ProviderBridge &operator=(const ProviderBridge &) = delete;

  facman::core::Result<InstalledIdentity> inspect_identity(
      const std::string &install_id);
  CandidateState inspect_candidate(const Plan &plan);
  EffectResult review_install_local(const Plan &plan);
  EffectResult install_local(const Plan &plan);
  EffectResult inspect_installed(const Plan &plan);
  EffectResult verify_installed(const Plan &plan);

private:
  struct Impl;
  std::unique_ptr<Impl> impl_;
};

} // namespace facman::self_maintenance

#endif
