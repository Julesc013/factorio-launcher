// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_CANDIDATE_MANIFEST_H
#define FLB_FACTORIO_CANDIDATE_MANIFEST_H

#include "fl_file_io.h"
#include "fl_result.h"
#include "flb_factorio_hermetic_candidate.h"

#include <chrono>
#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace facman::factorio::launch {

struct CandidateManifestLimits {
    std::size_t maximum_entries = 100000U;
    std::uint64_t maximum_bytes = 10ULL * 1024ULL * 1024ULL * 1024ULL;
    std::chrono::milliseconds maximum_elapsed {std::chrono::minutes(5)};
};

struct CandidateManifestEntry {
    std::string relative_path;
    std::string kind;
    std::string identity_digest;
    std::string content_digest;
    std::uint64_t size = 0;
};

struct CandidateStableManifest {
    std::string schema = "factorio.play_candidate_stable_manifest.v1";
    std::string resource_id;
    bool root_present = false;
    bool complete = false;
    std::string root_identity_digest;
    std::vector<CandidateManifestEntry> entries;
    std::vector<std::string> gap_codes;
    std::uint64_t bytes_hashed = 0;
    std::string manifest_digest;

    std::string canonical_json() const;
};

facman::core::Result<CandidateStableManifest> capture_candidate_stable_manifest(
    const std::string& resource_id,
    const std::filesystem::path& root,
    bool allow_absent,
    CandidateManifestLimits limits = {});

facman::core::Result<ProtectedResourceComparison> compare_candidate_stable_manifests(
    const CandidateStableManifest& before,
    const CandidateStableManifest& after);

} // namespace facman::factorio::launch

#endif
