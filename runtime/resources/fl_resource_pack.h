// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_RUNTIME_RESOURCES_FL_RESOURCE_PACK_H
#define FACMAN_RUNTIME_RESOURCES_FL_RESOURCE_PACK_H

#include "fl_result.h"

#include <filesystem>
#include <string>
#include <vector>

namespace facman::resources {

struct Inspection {
    std::filesystem::path path;
    std::string version;
    std::string content_sha256;
    std::uint64_t expanded_bytes = 0;
    std::vector<std::string> entries;
};

facman::core::Result<std::filesystem::path> locate_pack(
    const std::filesystem::path& executable_path);

facman::core::Result<Inspection> inspect_pack(
    const std::filesystem::path& pack_path);

facman::core::Result<void> export_pack(
    const std::filesystem::path& pack_path,
    const std::filesystem::path& destination);

std::string inspection_json(const Inspection& inspection);

facman::core::Result<std::string> locate_pack_utf8(
    const std::string& executable_path);

facman::core::Result<Inspection> inspect_pack_utf8(
    const std::string& pack_path);

facman::core::Result<void> export_pack_utf8(
    const std::string& pack_path,
    const std::string& destination);

std::string absolute_path_utf8(const std::string& path);

} // namespace facman::resources

#endif
