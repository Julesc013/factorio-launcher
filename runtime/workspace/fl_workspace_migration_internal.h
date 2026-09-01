// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_RUNTIME_WORKSPACE_FL_WORKSPACE_MIGRATION_INTERNAL_H
#define FACMAN_RUNTIME_WORKSPACE_FL_WORKSPACE_MIGRATION_INTERNAL_H

#include "fl_workspace_store.h"

namespace facman::workspace::migration_detail {

Result<MigrationReport> inspect(const WorkspaceLayout& layout);
Result<MigrationReport> plan(const WorkspaceLayout& layout);
Result<MigrationReport> apply(const WorkspaceLayout& layout);
std::string report_json(const MigrationReport& report);

} // namespace facman::workspace::migration_detail

#endif
