// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_CONTENT_CACHE_H
#define FLB_FACTORIO_CONTENT_CACHE_H

#include "fl_result.h"
#include "flb_factorio_content_records.h"

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace facman::factorio::content::cache {

struct Limits {
    std::uint64_t maximum_blob_bytes = 4ULL * 1024ULL * 1024ULL * 1024ULL;
    std::uint64_t maximum_inventory_bytes = 1024ULL * 1024ULL * 1024ULL * 1024ULL;
    std::size_t maximum_inventory_entries = 100000U;
};

struct Entry {
    BlobIdentity blob;
    std::filesystem::path path;
};

struct InsertResult {
    Entry entry;
    bool inserted = false;
};

struct Inventory {
    std::vector<Entry> entries;
    std::uint64_t total_bytes = 0;
    std::size_t incomplete_staging_entries = 0;
};

struct GcPlan {
    std::vector<Entry> retained;
    std::vector<Entry> candidates;
    std::uint64_t retained_bytes = 0;
    std::uint64_t reclaimable_bytes = 0;
    std::string inventory_sha256;
};

class LocalContentCache {
public:
    explicit LocalContentCache(std::filesystem::path root, Limits limits = {});

    const std::filesystem::path& root() const noexcept;

    // Initialization adopts nothing. An existing unmarked directory is
    // refused, while an absent root is created as one marker-owned tree.
    facman::core::Result<void> initialize() const;

    facman::core::Result<InsertResult> insert(
        const std::filesystem::path& source,
        const std::string& expected_sha256 = {}) const;

    facman::core::Result<Entry> verify(const BlobIdentity& blob) const;

    // Materialization creates one exact absent file in an existing safe
    // directory. It never overwrites or creates a foreign directory tree.
    facman::core::Result<Entry> materialize(
        const BlobIdentity& blob,
        const std::filesystem::path& target) const;

    facman::core::Result<Inventory> inventory() const;

    // GC is deliberately plan-only at this boundary. Callers must separately
    // admit any mutation and revalidate the returned inventory identity.
    facman::core::Result<GcPlan> plan_gc(
        const std::vector<std::string>& retained_sha256) const;

private:
    std::filesystem::path root_;
    Limits limits_;
};

std::string to_json(const Inventory& value);
std::string to_json(const GcPlan& value);

} // namespace facman::factorio::content::cache

#endif
