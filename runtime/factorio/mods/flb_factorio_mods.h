// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_MODS_H
#define FLB_FACTORIO_MODS_H

#include <filesystem>
#include <cstdint>
#include <string>
#include <vector>

#include "fl_result.h"

namespace facman::factorio::mods {

struct DependencyRef {
    std::string kind;
    std::string name;
    std::string oper;
    std::string version;
    std::string raw;
};

struct ModRef {
    std::string name;
    std::string title;
    std::string version;
    std::string factorio_version;
    std::string author;
    std::string description;
    std::filesystem::path file_path;
    std::string file_name;
    std::string sha1;
    std::string sha256;
    std::string source;
    std::string metadata_source;
    bool enabled;
    bool valid;
    std::string validation_status;
    std::string refusal_code;
    std::string refusal_reason;
    std::string refusal_detail;
    std::vector<DependencyRef> dependencies;
    std::vector<DependencyRef> optional_dependencies;
    std::vector<DependencyRef> hidden_optional_dependencies;
    std::vector<DependencyRef> incompatibilities;
    std::uint64_t archive_size = 0;
    std::uint64_t expanded_size = 0;
    std::string archive_policy_result;
    std::vector<std::string> instance_references;
    std::vector<std::string> lock_references;
    bool virtual_package = false;
};

struct InventoryRequest {
    std::vector<std::filesystem::path> roots;
    std::string identity;
};

ModRef inspect_mod_zip(const std::filesystem::path& path);

std::string mod_ref_json(const ModRef& mod);

std::string mod_refusal_json(
    const std::string& command,
    const std::string& instance_id,
    const std::filesystem::path& path,
    const ModRef& mod
);

std::string dependency_array_json(const std::vector<DependencyRef>& dependencies);

std::string sha1_hex_file(const std::filesystem::path& path);

std::string sha256_hex_file(const std::filesystem::path& path);

std::string factorio_minor_version(const std::string& version);

bool factorio_versions_compatible(const std::string& mod_factorio_version, const std::string& instance_version);

facman::core::Result<std::string> inventory_list(const std::filesystem::path& workspace);
facman::core::Result<std::string> inventory_index(const std::filesystem::path& workspace, const InventoryRequest& request);
facman::core::Result<std::string> inventory_inspect(const std::filesystem::path& workspace, const InventoryRequest& request);
facman::core::Result<std::string> inventory_verify(const std::filesystem::path& workspace, const InventoryRequest& request);
facman::core::Result<std::string> inventory_explain(const std::filesystem::path& workspace, const InventoryRequest& request);

} // namespace facman::factorio::mods

#endif
