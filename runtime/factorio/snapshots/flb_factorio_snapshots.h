// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_SNAPSHOTS_H
#define FLB_FACTORIO_SNAPSHOTS_H

#include "fl_result.h"

#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace facman::factorio::snapshots {

struct CreateRequest {
    std::string instance_id;
    std::string snapshot_id;
    std::vector<std::string> saves;
};
struct ListRequest { std::string instance_id; };
struct SnapshotRequest { std::string instance_id; std::string snapshot_id; };
struct DiffRequest { std::string instance_id; std::string left_snapshot_id; std::string right_snapshot_id; };
struct RestoreRequest { std::string snapshot_ref; std::string target_instance_id; };
struct RetentionRequest {
    std::string instance_id;
    std::uint32_t keep_last = 10;
    std::uint32_t keep_daily = 0;
    std::uint32_t keep_weekly = 0;
    std::uint64_t maximum_total_bytes = 0;
    std::uint32_t minimum_age_days = 0;
};

facman::core::Result<std::string> create(const std::filesystem::path& workspace, const CreateRequest& request);
facman::core::Result<std::string> list(const std::filesystem::path& workspace, const ListRequest& request);
facman::core::Result<std::string> inspect(const std::filesystem::path& workspace, const SnapshotRequest& request);
facman::core::Result<std::string> verify(const std::filesystem::path& workspace, const SnapshotRequest& request);
facman::core::Result<std::string> diff(const std::filesystem::path& workspace, const DiffRequest& request);
facman::core::Result<std::string> restore(const std::filesystem::path& workspace, const RestoreRequest& request);
facman::core::Result<std::string> retention_plan(const std::filesystem::path& workspace, const RetentionRequest& request);
facman::core::Result<std::string> retention_apply(const std::filesystem::path& workspace, const RetentionRequest& request);

} // namespace facman::factorio::snapshots

#endif
