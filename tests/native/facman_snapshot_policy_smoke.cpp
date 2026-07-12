// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_snapshots.h"

#include <cstdint>
#include <string>
#include <vector>

int main()
{
    using facman::factorio::snapshots::RetentionRequest;
    using facman::factorio::snapshots::RetentionSample;
    constexpr std::uint64_t gib = 1024ULL * 1024ULL * 1024ULL;
    std::vector<RetentionSample> samples;
    for (int index = 0; index < 100; ++index) {
        samples.push_back({
            "snapshot-" + std::to_string(index),
            "2020-01-01T00:00:00Z",
            (index == 0 ? 4ULL * gib : 6ULL * gib / 99ULL),
        });
    }
    RetentionRequest request;
    request.keep_last = 1;
    request.maximum_total_bytes = 5ULL * gib;
    const auto candidates = facman::factorio::snapshots::retention_candidate_ids(samples, request);
    if (candidates.empty() || candidates.size() >= samples.size()) return 1;
    for (const std::string& id : candidates) if (id == "snapshot-0") return 2;
    return 0;
}
