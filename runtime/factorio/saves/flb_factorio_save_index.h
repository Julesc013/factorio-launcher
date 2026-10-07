// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_SAVE_INDEX_H
#define FLB_FACTORIO_SAVE_INDEX_H

#include "fl_result.h"

#include <cstdint>
#include <filesystem>
#include <string>

namespace facman::factorio::saves::index {

struct Request {
    std::string instance_id;
    std::string save;
    std::string other_save;
    std::string profile_id;
    std::string source_operation;
    std::uint32_t keep_last = 10;
    std::uint32_t keep_daily = 0;
    std::uint32_t keep_weekly = 0;
    std::uint64_t maximum_total_bytes = 0;
    std::uint32_t minimum_age_days = 0;
};

struct OwnedBackup {
    std::filesystem::path path;
    std::string original_save;
    std::string sha256;
    std::uint64_t size = 0;
};

facman::core::Result<OwnedBackup> resolve_owned_backup(
    const std::filesystem::path& workspace,
    const std::string& instance_id,
    const std::string& backup_name);

facman::core::Result<std::string> list(const std::filesystem::path& workspace, const Request& request);
facman::core::Result<std::string> inspect(const std::filesystem::path& workspace, const Request& request);
// Internal readiness observation only; public save commands retain legacy selection.
facman::core::Result<std::string> inspect_exact_filename(
    const std::filesystem::path& workspace, const Request& request);
facman::core::Result<std::string> verify(const std::filesystem::path& workspace, const Request& request);
facman::core::Result<std::string> associate(const std::filesystem::path& workspace, const Request& request);
facman::core::Result<std::string> diff(const std::filesystem::path& workspace, const Request& request);
facman::core::Result<std::string> retention_plan(const std::filesystem::path& workspace, const Request& request);
facman::core::Result<std::string> retention_apply(const std::filesystem::path& workspace, const Request& request);

} // namespace facman::factorio::saves::index

#endif
