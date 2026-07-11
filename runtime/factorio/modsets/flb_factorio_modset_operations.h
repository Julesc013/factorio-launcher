// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_MODSET_OPERATIONS_H
#define FLB_FACTORIO_MODSET_OPERATIONS_H

#include "flb_factorio_modsets.h"

#include <filesystem>
#include <string>
#include <variant>
#include <vector>

namespace facman::factorio::modsets::operations {

struct Refusal {
    std::string command;
    std::string instance_id;
    std::string code;
    std::string reason;
    std::string detail;
    bool recoverable = true;
    std::filesystem::path source_path;
    std::string file_name;
    std::string metadata_source;
    std::string suggested_next_command;
};

struct ImportRequest {
    std::filesystem::path source_path;
    std::string instance_id;
};

struct InstanceRequest {
    std::string instance_id;
};

struct ExportRequest {
    std::string instance_id;
    std::filesystem::path output_path;
};

struct ImportResult {
    std::string instance_id;
    std::filesystem::path source_path;
    std::filesystem::path destination_path;
    ModRef mod;
};

struct LockResult {
    std::string instance_id;
    std::string factorio_version;
    std::filesystem::path instance_lock_path;
    std::filesystem::path workspace_lock_path;
    std::vector<ModRef> mods;
    std::string lock_json;
};

struct VerifyResult {
    std::string instance_id;
    std::vector<std::string> problems;
};

struct ExportResult {
    std::string instance_id;
    std::filesystem::path output_path;
    std::size_t file_count = 0;
};

using ImportOutcome = std::variant<ImportResult, Refusal>;
using LockOutcome = std::variant<LockResult, Refusal>;
using VerifyOutcome = std::variant<VerifyResult, Refusal>;
using ExportOutcome = std::variant<ExportResult, Refusal>;

ImportOutcome import_mod(const std::filesystem::path& workspace, const ImportRequest& request);
LockOutcome lock_modset(const std::filesystem::path& workspace, const InstanceRequest& request);
VerifyOutcome verify_modset(const std::filesystem::path& workspace, const InstanceRequest& request);
ExportOutcome export_modset(const std::filesystem::path& workspace, const ExportRequest& request);

std::string to_json(const ImportResult& result);
std::string to_json(const LockResult& result);
std::string to_json(const VerifyResult& result);
std::string to_json(const ExportResult& result);
std::string to_json(const Refusal& refusal);

} // namespace facman::factorio::modsets::operations

#endif
