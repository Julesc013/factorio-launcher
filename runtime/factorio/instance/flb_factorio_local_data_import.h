// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_LOCAL_DATA_IMPORT_H
#define FLB_FACTORIO_LOCAL_DATA_IMPORT_H

#include "fl_result.h"

#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace facman::factorio::instance {

struct LocalDataImportReport {
    std::uint64_t file_count = 0;
    std::uint64_t byte_count = 0;
    std::vector<std::string> imported_domains;
    std::vector<std::string> preserved_but_inactive_domains;
    std::vector<std::string> skipped_volatile_domains;
};

facman::core::Result<LocalDataImportReport> import_local_player_data(
    const std::filesystem::path& source_install_root,
    const std::filesystem::path& staging_instance_root);

facman::core::Result<std::string> merge_imported_config_settings(
    const std::filesystem::path& source_config,
    const std::string& required_effective_config);

} // namespace facman::factorio::instance

#endif
