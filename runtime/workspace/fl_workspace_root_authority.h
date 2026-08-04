// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_RUNTIME_WORKSPACE_FL_WORKSPACE_ROOT_AUTHORITY_H
#define FACMAN_RUNTIME_WORKSPACE_FL_WORKSPACE_ROOT_AUTHORITY_H

#include "fl_file_io.h"
#include "fl_result.h"

#include <filesystem>
#include <memory>
#include <string>

namespace facman::workspace {

enum class WorkspaceRootState {
    missing,
    empty_unowned,
    facman_owned,
    legacy_facman,
    foreign_nonempty,
    link_or_reparse,
    inspection_failed,
};

struct WorkspaceRootInspection {
    WorkspaceRootState state = WorkspaceRootState::inspection_failed;
    std::filesystem::path requested_root;
    std::filesystem::path canonical_root;
    std::string workspace_id;
    std::string ownership_mode;
    std::string detail;
    std::string recovery_action;
    bool mutation_allowed = false;
    std::shared_ptr<facman::platform::StableDirectoryObject> root_authority;
    std::shared_ptr<facman::platform::StableInputFile> marker_authority;
};

const char* workspace_root_state_name(WorkspaceRootState state) noexcept;
std::filesystem::path workspace_root_marker(const std::filesystem::path& root);

facman::core::Result<WorkspaceRootInspection> inspect_workspace_root(
    const std::filesystem::path& root);

facman::core::Result<WorkspaceRootInspection> claim_workspace_root(
    const std::filesystem::path& root,
    const std::string& workspace_id);

facman::core::Result<WorkspaceRootInspection> adopt_legacy_workspace_root(
    const std::filesystem::path& root);

facman::core::Result<void> rollback_legacy_workspace_root_adoption(
    const WorkspaceRootInspection& authority);

facman::core::Result<void> revalidate_workspace_root(
    const WorkspaceRootInspection& authority);

} // namespace facman::workspace

#endif
