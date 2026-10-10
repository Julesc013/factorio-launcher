// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "fl_archive.h"
#include "fl_archive_policy.h"
#include "fl_file_io.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include <algorithm>
#include <chrono>
#include <limits>
#include <map>
#include <stdexcept>

namespace facman::archive {
namespace {
namespace fs = std::filesystem;
struct Failure { Status status; };
[[noreturn]] void fail(const char* code, const std::string& detail)
{
    throw Failure {Status::failure(code, detail)};
}
void check(const Status& status) { if (!status.ok()) throw Failure {status}; }
void check(const facman::platform::IoStatus& status)
{
    if (!status.ok()) throw Failure {Status::failure(status.code, status.detail)};
}
using Expected = std::map<std::string, VerifiedEntry>;
Expected admit(const Plan& plan, const Limits& limits, const std::vector<VerifiedEntry>& expected)
{
    if (!plan.reader || plan.entries.empty() || plan.entries.size() > limits.maximum_entry_count ||
        expected.size() != plan.entries.size())
        fail("archive_expected_inventory_invalid", "A complete bounded verified inventory is required");
    Expected result;
    for (const auto& entry : expected) {
        if (entry.sha256.size() != 64 || !std::all_of(entry.sha256.begin(), entry.sha256.end(), [](char c) {
                return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'); }) ||
            !result.emplace(entry.path, entry).second)
            fail("archive_expected_inventory_invalid", "Duplicate or invalid expected entry");
    }
    CollisionTracker collisions;
    std::uint64_t total = 0;
    for (std::size_t i = 0; i < plan.entries.size(); ++i) {
        const auto& entry = plan.entries[i];
        const auto found = result.find(entry.path);
        if (entry.directory || entry.index != i || found == result.end() || found->second.bytes != entry.expanded_size)
            fail("archive_expected_inventory_mismatch", entry.path);
        PathKeys keys;
        check(validate_archive_path(entry.path, false, limits, keys));
        check(collisions.add(keys, false));
        check(enforce_entry_limits(entry.compressed_size, entry.expanded_size, total, limits));
    }
    return result;
}

class RetainedRoot {
public:
    RetainedRoot(fs::path path, const Limits& limits, const ExtractionCheckpoint& callback,
                 ExtractionObservation* observation)
        : root(std::move(path)), limits_(limits), checkpoint_(callback),
          started_(std::chrono::steady_clock::now()), observation_(observation) {}
    void guard() const
    {
        if (std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now() - started_).count() >=
            static_cast<long long>(limits_.maximum_read_milliseconds))
            fail("archive_read_limit_or_sink_failed", "Retained extraction time budget exhausted");
        check(directory_.revalidate());
    }
    void point(std::uint32_t index, const char* name) const
    {
        if (checkpoint_ && !checkpoint_(index, name))
            fail("archive_extract_fault_injected", name);
        guard();
    }
    void create()
    {
        std::error_code error;
        if (root.empty() || fs::exists(root, error))
            fail("archive_staging_root_exists", root.u8string());
        const auto parent = root.parent_path();
        std::string detail;
        if (parent.empty() || !fs::is_directory(parent, error) || error)
            fail("archive_staging_parent_invalid", parent.u8string());
        if (facman::base::path_crosses_link_or_reparse_point(parent, detail))
            fail("archive_staging_parent_link_refused", detail);
        check(parent_.open_no_follow_for_relative_writes(parent));
        if (observation_) observation_->begin_create_attempt();
        const auto created = parent_.create_child_directory_exclusive_utf8(root.filename().u8string(), directory_);
        if (!created.ok()) fail("archive_staging_create_failed", created.detail);
        // The existing directory capability returns the created handle atomically
        // on Windows. POSIX creation/reopen still has its documented namespace
        // window; this does not qualify an uncooperative POSIX namespace writer.
        // From here onward even marker/handle/exception failures retain state.
        point(std::numeric_limits<std::uint32_t>::max(), "root_created");
        facman::platform::DurableOutputFile output;
        const std::string bytes = "schema=facman.archive_staging.v1\n";
        check(directory_.create_child_file_exclusive(owned_staging_marker_name(), bytes.size(), output));
        if (output.write_at(0, bytes.data(), bytes.size()) != bytes.size())
            fail("archive_staging_marker_failed", "Retained marker write failed");
        check(output.flush_file_and_parent());
        point(std::numeric_limits<std::uint32_t>::max(), "root_ready");
    }
    void create_output(const Entry& entry, facman::platform::DurableOutputFile& output)
    {
        guard();
        auto* parent = &directory_;
        fs::path current = root;
        for (const auto& part : fs::u8path(entry.path).parent_path()) {
            current /= part;
            const auto held = parents_.find(current);
            if (held != parents_.end()) {
                check(held->second->revalidate());
                parent = held->second.get();
                continue;
            }
            auto object = std::make_unique<facman::platform::StableDirectoryObject>();
            const auto created = parent->create_child_directory_exclusive_utf8(part.u8string(), *object);
            if (!created.ok()) fail("archive_extract_directory_collision", created.detail);
            parent = object.get();
            parents_.emplace(current, std::move(object));
            point(entry.index, "directory_created");
        }
        check(parent->create_child_file_exclusive_utf8(fs::u8path(entry.path).filename().u8string(),
            entry.expanded_size, output));
        point(entry.index, "output_created");
    }
    fs::path root;
private:
    facman::platform::StableDirectoryObject parent_, directory_;
    std::map<fs::path, std::unique_ptr<facman::platform::StableDirectoryObject>> parents_;
    const Limits& limits_;
    const ExtractionCheckpoint& checkpoint_;
    std::chrono::steady_clock::time_point started_;
    ExtractionObservation* observation_;
};

void extract_entry(const Plan& plan, const Entry& entry, const VerifiedEntry& expected,
                   const Limits& limits, RetainedRoot& root)
{
    root.point(entry.index, "before_entry");
    facman::platform::DurableOutputFile output;
    root.create_output(entry, output);
    std::uint64_t offset = 0;
    facman::base::Sha256Hasher hash;
    Status sink_failure;
    const auto status = stream_entry(plan, entry.index, limits, [&](const unsigned char* data, std::size_t size) {
        // Never unwind through the archive iterator: returning false lets its
        // normal close path release decompressor memory before reporting failure.
        try {
            root.guard();
            const auto written = output.write_at(offset, data, size);
            if (written != size) return false;
            hash.update(data, size); offset += size;
            root.point(entry.index, "after_chunk");
            return true;
        } catch (const Failure& failure) {
            sink_failure = failure.status;
        } catch (const std::exception& error) {
            sink_failure = Status::failure("archive_retained_sink_failed", error.what());
        } catch (...) {
            sink_failure = Status::failure("archive_retained_sink_failed", "Unknown callback failure");
        }
        return false;
    });
    check(sink_failure);
    check(status);
    if (offset != expected.bytes || hash.finish() != expected.sha256)
        fail("archive_consumed_digest_mismatch", entry.path);
    check(output.flush_file_and_parent());
    root.point(entry.index, "after_entry");
}
}
Status extract_verified_to_new_retained_staging(
    const Plan& plan, const fs::path& staging_root, const Limits& limits,
    const std::vector<VerifiedEntry>& expected, const ExtractionCheckpoint& checkpoint,
    ExtractionObservation* observation)
{
    try {
        const auto entries = admit(plan, limits, expected);
        if (staging_root.empty()) fail("archive_staging_root_invalid", "Empty retained destination");
        RetainedRoot root(fs::absolute(staging_root).lexically_normal(), limits, checkpoint, observation);
        root.create();
        for (const auto& entry : plan.entries) extract_entry(plan, entry, entries.at(entry.path), limits, root);
        root.guard();
        return Status::success();
    } catch (const Failure& failure) {
        auto status = failure.status;
        status.detail += "; no cleanup performed; inspect retained destination " + staging_root.u8string();
        return status;
    } catch (const std::exception& error) {
        return Status::failure("archive_retained_extraction_failed",
            std::string(error.what()) + "; no cleanup performed; inspect retained destination " + staging_root.u8string());
    } catch (...) {
        return Status::failure("archive_retained_extraction_failed",
            "Unknown callback failure; no cleanup performed; inspect retained destination " + staging_root.u8string());
    }
}
}
