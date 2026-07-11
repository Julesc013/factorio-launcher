// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_RUNTIME_WORKSPACE_FL_WORKSPACE_STORE_H
#define FACMAN_RUNTIME_WORKSPACE_FL_WORKSPACE_STORE_H

#include "fl_identity.h"
#include "fl_result.h"

#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace facman::workspace {

using facman::core::InstanceId;
using facman::core::InstallId;
using facman::core::Result;
using facman::core::TransactionId;
using facman::core::WorkspaceId;

class WorkspaceLayout {
public:
    explicit WorkspaceLayout(std::filesystem::path root);

    const std::filesystem::path& root() const noexcept;
    std::filesystem::path manifest() const;
    std::filesystem::path installs_refs_dir() const;
    std::filesystem::path legacy_installs_dir() const;
    Result<std::filesystem::path> install_ref(const InstallId& id) const;
    Result<std::filesystem::path> legacy_install_ref(const InstallId& id) const;
    Result<std::filesystem::path> instance_root(const InstanceId& id) const;
    Result<std::filesystem::path> instance_manifest(const InstanceId& id) const;
    Result<std::filesystem::path> legacy_instance_manifest(const InstanceId& id) const;
    Result<std::filesystem::path> modset_lock(const InstanceId& id) const;
    Result<std::filesystem::path> instance_modset_lock(const InstanceId& id) const;
    Result<std::filesystem::path> transaction_journal(const TransactionId& id) const;
    Result<std::filesystem::path> diagnostic_output(const std::string& file_name) const;

private:
    std::filesystem::path root_;
};

struct InstallRecord {
    InstallId id;
    std::filesystem::path root;
    std::filesystem::path executable;
    std::string version;
    std::string ownership;
    std::string source;
    std::string platform;
    std::string verification_status;
    std::string schema;
    bool legacy_path = false;
    std::filesystem::path source_path;
};

struct InstanceRecord {
    InstanceId id;
    std::string display_name;
    InstallId install_ref;
    std::string factorio_version;
    std::string profile = "gui";
    std::string template_id = "vanilla";
    std::filesystem::path root;
    std::string schema;
    bool legacy_path = false;
    std::filesystem::path source_path;
};

struct WorkspaceRecord {
    WorkspaceId id;
    std::uint64_t layout_version = 1;
    std::string schema;
    bool legacy_local_identity = false;
};

class InstallRepository {
public:
    explicit InstallRepository(WorkspaceLayout layout);
    Result<InstallRecord> load(const InstallId& id) const;
    Result<std::vector<InstallRecord>> list() const;
    Result<std::filesystem::path> create(const InstallRecord& record, const std::string& json) const;

private:
    WorkspaceLayout layout_;
};

class InstanceRepository {
public:
    explicit InstanceRepository(WorkspaceLayout layout);
    Result<InstanceRecord> load(const InstanceId& id) const;
    Result<std::vector<InstanceRecord>> list() const;

private:
    WorkspaceLayout layout_;
};

class ModsetRepository {
public:
    explicit ModsetRepository(WorkspaceLayout layout);
    Result<std::string> load_lock(const InstanceId& id) const;
    Result<std::filesystem::path> canonical_lock(const InstanceId& id) const;

private:
    WorkspaceLayout layout_;
};

class TransactionRepository {
public:
    explicit TransactionRepository(WorkspaceLayout layout);
    Result<std::string> load_journal(const TransactionId& id) const;
    Result<std::filesystem::path> journal(const TransactionId& id) const;

private:
    WorkspaceLayout layout_;
};

struct MigrationAction {
    std::string kind;
    std::filesystem::path source;
    std::filesystem::path target;
    bool backup_required = true;
    bool journal_required = true;
};

struct MigrationReport {
    std::string operation;
    std::vector<MigrationAction> actions;
    bool apply_enabled = false;
};

class WorkspaceRepository {
public:
    explicit WorkspaceRepository(WorkspaceLayout layout);
    Result<WorkspaceRecord> load() const;
    Result<WorkspaceRecord> ensure() const;
    Result<MigrationReport> inspect_migration() const;
    Result<MigrationReport> plan_migration() const;
    Result<MigrationReport> apply_migration() const;

private:
    WorkspaceLayout layout_;
};

std::string migration_report_json(const MigrationReport& report);

} // namespace facman::workspace

#endif
