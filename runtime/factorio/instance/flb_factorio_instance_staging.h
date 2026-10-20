// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#ifndef FLB_FACTORIO_INSTANCE_STAGING_H
#define FLB_FACTORIO_INSTANCE_STAGING_H
#include "fl_workspace_store.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "flb_factorio_discovery.h"
#include <functional>
namespace facman::transaction { struct Record; }
namespace facman::factorio::instance {
std::string instance_manifest_json(const facman::workspace::InstanceRecord& instance);
std::string instance_effective_config(const facman::workspace::InstanceRecord& instance,
    const facman::factorio::discovery::InstallRef& install);
bool prepare_instance_layout(const std::filesystem::path& staging, std::string& detail);
struct ConfigurationGuard {
    std::string inputs_sha256, parent_before_identity, operation_id, attempt_id;
    std::function<facman::core::Result<std::string>(const facman::transaction::Record*)> observe_inputs;
};
struct ExistingConfigurationGuard {
    std::function<facman::core::Result<std::string>(const facman::transaction::Record&)> validate_owner;
    std::string inputs_sha256, parent_before_identity, operation_id, attempt_id;
    std::function<facman::core::Result<std::string>(const facman::transaction::Record*,
        const facman::platform::RetainedStreamRewriteFile*)> observe_inputs;
};
bool configuration_original_file_identity(const facman::core::json::Value& context,
    facman::platform::FileIdentity& file);
facman::core::Result<std::string> reconcile_existing_configuration(const std::filesystem::path& workspace,
    const facman::core::json::Value& plan, const ExistingConfigurationGuard& guard);
facman::core::Result<std::string> recover_existing_configuration(const std::filesystem::path& workspace,
    const std::string& transaction_id, const ExistingConfigurationGuard& guard);
bool configuration_publication_available() noexcept;
facman::core::Result<std::string> configuration_parent_identity(const std::filesystem::path& instance_root);
facman::core::Result<std::string> publish_missing_configuration(
    const std::filesystem::path& workspace, const std::filesystem::path& instance_root,
    const std::string& instance_id, const std::string& launch_intent, const std::string& bytes,
    const ConfigurationGuard& guard);
facman::core::Result<std::string> recover_missing_configuration(
    const std::filesystem::path& workspace, const std::string& transaction_id, const ConfigurationGuard& guard);
}
#endif
