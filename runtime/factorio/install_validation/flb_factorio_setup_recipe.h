// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_SETUP_RECIPE_H
#define FLB_FACTORIO_SETUP_RECIPE_H

#include "fl_result.h"

#include <cstdint>
#include <string>
#include <vector>

namespace facman::factorio::setup {

struct Recipe {
    std::string recipe_id;
    std::string recipe_digest;
    std::string product_id;
    std::string source_kind;
    std::string archive_format;
    std::string archive_digest_binding;
    std::string distribution_origin;
    std::vector<std::string> required_paths;
    std::vector<std::string> forbidden_path_prefixes;
    std::string entrypoint;
    std::string base_marker;
    std::string expansion_marker;
    std::string target_scope;
    std::string installed_state_schema;
    std::string strict_isolation_classification;
};

struct ArchiveEntry {
    std::string normalized_path;
    std::string entry_type;
};

struct ArchiveInspection {
    std::string archive_sha256;
    std::string entry_set_digest;
    std::uint64_t file_count = 0;
    std::uint64_t directory_count = 0;
    std::uint64_t uncompressed_bytes = 0;
    std::vector<ArchiveEntry> entries;
};

struct ArchiveAssessment {
    std::string recipe_id;
    std::string recipe_digest;
    std::string product_id;
    std::string requested_version;
    std::string archive_sha256;
    std::string entry_set_digest;
    std::string application_root_prefix;
    std::string strip_prefix_policy;
    std::string entrypoint;
    std::string distribution_origin;
    std::string strict_isolation_classification;
    std::string version_verification;
    std::uint64_t file_count = 0;
    std::uint64_t directory_count = 0;
    std::uint64_t uncompressed_bytes = 0;
    std::vector<std::string> capabilities;
    bool layout_verified = false;
    bool publisher_authenticity_proven = false;
    bool mutation_executed = false;
};

facman::core::Result<Recipe> portable_windows_zip_recipe();

std::string portable_windows_zip_recipe_json();

facman::core::Result<ArchiveAssessment> assess_portable_archive(
    const Recipe& recipe,
    const std::string& requested_version,
    const ArchiveInspection& inspection);

std::string archive_assessment_json(const ArchiveAssessment& assessment);

} // namespace facman::factorio::setup

#endif
