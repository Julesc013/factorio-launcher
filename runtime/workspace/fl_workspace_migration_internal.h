// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_RUNTIME_WORKSPACE_FL_WORKSPACE_MIGRATION_INTERNAL_H
#define FACMAN_RUNTIME_WORKSPACE_FL_WORKSPACE_MIGRATION_INTERNAL_H

#include "fl_workspace_store.h"
#include "fl_workspace_root_authority.h"
#include "fl_local_operation_lock.h"

#include <filesystem>
#include <optional>
#include <string>
#include <vector>

namespace facman::workspace {

inline constexpr std::size_t kMaximumMigrationActions = 256U;

struct MigrationJournalAction {
    std::string step_id;
    std::string kind;
    std::string source;
    std::string target;
    std::string source_sha256;
    std::string target_sha256;
};

struct MigrationJournal {
    unsigned int format_version = 2U;
    std::string id;
    std::string migration_id;
    std::string operation_id;
    std::string attempt_id;
    std::string request_id;
    std::string idempotency_key;
    std::string plan_digest;
    std::string expected_workspace_revision;
    std::string expected_root_identity;
    std::string inventory_digest;
    std::string resulting_workspace_revision;
    std::string rollback_operation_id;
    std::string rollback_attempt_id;
    std::string rollback_request_id;
    std::string rollback_idempotency_key;
    std::string rollback_expected_workspace_revision;
    std::string state;
    std::size_t completed_actions = 0U;
    bool rollback_retained = true;
    std::vector<std::string> verification_results;
    std::vector<MigrationJournalAction> actions;
};

struct WorkspaceCreationJournal {
    std::string operation_id;
    std::string attempt_id;
    std::string request_id;
    std::string idempotency_key;
    std::string migration_id;
    std::string plan_digest;
    std::string expected_workspace_revision;
    std::string expected_root_identity;
    std::string inventory_digest;
    std::string target_sha256;
    std::string workspace_id;
    std::string state;
    std::string resulting_workspace_revision;
};

class ScopedMigrationLock {
public:
    Result<void> acquire(const std::filesystem::path& path);
    Result<void> release();
    ~ScopedMigrationLock();

private:
    facman::base::StableLocalLock lock_;
    bool acquired_ = false;
};

bool copy_migration_kind(const std::string& kind);
std::string sha256_text(const std::string& text);
std::string root_identity_digest(
    const WorkspaceLayout& layout,
    const WorkspaceRootInspection& inspection);
std::string random_workspace_uuid();
std::filesystem::path migration_root(const WorkspaceLayout& layout);
std::filesystem::path migration_journal_path(
    const WorkspaceLayout& layout,
    const std::string& id,
    unsigned int format_version = 2U);
std::filesystem::path migration_data_root(
    const WorkspaceLayout& layout,
    const std::string& id);
bool safe_relative_text(
    const std::filesystem::path& root,
    const std::filesystem::path& path,
    std::string& output);
Result<std::filesystem::path> resolve_relative_path(
    const WorkspaceLayout& layout,
    const std::string& value);
Result<void> ensure_owned_directory(
    const WorkspaceRootInspection& authority,
    const std::filesystem::path& path);
Result<void> write_replace_durable(
    const std::filesystem::path& path,
    const std::string& text);
Result<void> persist_journal(
    const WorkspaceLayout& layout,
    const MigrationJournal& journal,
    bool create);
std::string workspace_creation_journal_json(
    const MigrationApplyRequest& request,
    const std::string& workspace_id,
    const std::string& state,
    const std::string& resulting_workspace_revision,
    const std::string& migration_id,
    const std::string& inventory_digest,
    const std::string& target_sha256);
bool sha256_text_valid(const std::string& value);
bool workspace_migration_fault(
    const std::string& boundary,
    std::size_t completed_actions = 0U);
Result<MigrationJournal> load_migration_journal(
    const std::filesystem::path& path);
Result<WorkspaceCreationJournal> load_workspace_creation_journal(
    const std::filesystem::path& path);
Result<void> validate_legacy_install_document(
    const std::filesystem::path& source,
    const std::string& expected_id);
Result<std::string> canonical_instance_manifest(
    const std::filesystem::path& source,
    const std::string& expected_id);
Result<MigrationReport> build_migration_report(
    const WorkspaceLayout& layout,
    const char* operation);
Result<void> recover_incomplete_migrations(
    const WorkspaceLayout& layout,
    const WorkspaceRootInspection& authority);
Result<std::optional<MigrationReport>> replay_migration_operation(
    const WorkspaceLayout& layout,
    const MigrationApplyRequest& request);
Result<MigrationReport> rollback_migration_operation(
    const WorkspaceLayout& layout,
    const MigrationControlRequest& request);

} // namespace facman::workspace

namespace facman::workspace::migration_detail {

Result<MigrationReport> inspect(const WorkspaceLayout& layout);
Result<MigrationReport> plan(const WorkspaceLayout& layout);
Result<MigrationReport> apply(const WorkspaceLayout& layout, const MigrationApplyRequest& request);
std::string report_json(const MigrationReport& report);

} // namespace facman::workspace::migration_detail

#endif
