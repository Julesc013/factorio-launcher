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
#include <set>
#include <array>

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
    void adopt(facman::platform::StableDirectoryObject& retained, const Expected& expected,
        const std::vector<VerifiedEntry>& additional, const std::vector<std::string>& allowed)
    {
        if (!retained.open() || retained.path() != root ||
            expected.size() + additional.size() > limits_.maximum_entry_count ||
            allowed.size() > limits_.maximum_entry_count)
            fail("archive_retained_inventory_invalid", "A held bounded retained directory is required");
        check(retained.revalidate());
        std::string detail;
        if (facman::base::path_crosses_link_or_reparse_point(root, detail))
            fail("archive_retained_root_unsafe", detail);
        check(directory_.open_no_follow_for_relative_writes(root));
        if (directory_.identity().device != retained.identity().device ||
            directory_.identity().object != retained.identity().object)
            fail("archive_retained_root_changed", "Retained root differs from the held object");
        check(retained.revalidate());
        Expected files = expected;
        for (const auto& item : additional) {
            if (item.bytes > limits_.maximum_entry_expanded_bytes || item.sha256.size() != 64U ||
                !std::all_of(item.sha256.begin(), item.sha256.end(), [](char c) {
                    return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'); }) ||
                !files.emplace(item.path, item).second)
                fail("archive_retained_inventory_invalid", "Additional retained inventory is invalid");
        }
        std::uint64_t retained_bytes = 0;
        for (const auto& item : files) {
            if (item.second.bytes > limits_.maximum_entry_expanded_bytes ||
                item.second.bytes > limits_.maximum_total_expanded_bytes ||
                retained_bytes > limits_.maximum_total_expanded_bytes - item.second.bytes)
                fail("archive_retained_inventory_limit", "Retained bytes exceed the aggregate bound");
            retained_bytes += item.second.bytes;
        }
        CollisionTracker collisions;
        std::set<std::string> dirs;
        for (const auto& name : allowed) {
            PathKeys keys;
            check(validate_archive_path(name, true, limits_, keys));
            check(collisions.add(keys, true));
            dirs.insert(keys.exact);
            dirs.insert(keys.parents.begin(), keys.parents.end());
        }
        for (const auto& item : files) {
            PathKeys keys;
            check(validate_archive_path(item.first, false, limits_, keys));
            check(collisions.add(keys, false));
            dirs.insert(keys.parents.begin(), keys.parents.end());
        }
        // Validate the entire visible tree before the first create attempt. The
        // pinned inputs remain held until extraction finishes or refuses.
        std::function<void(facman::platform::StableDirectoryObject&, const std::string&)> scan;
        scan = [&](facman::platform::StableDirectoryObject& directory, const std::string& prefix) {
            guard();
            std::vector<fs::path> names;
            check(directory.list_child_names_bounded(files.size() + dirs.size(), names));
            for (const auto& leaf : names) {
                guard();
                const auto relative = prefix + leaf.u8string();
                if (dirs.count(relative)) {
                    auto child = std::make_unique<facman::platform::StableDirectoryObject>();
                    check(directory.open_child_directory_no_follow_for_relative_writes(leaf, *child));
                    auto* pointer = child.get();
                    if (!parents_.emplace(root / fs::u8path(relative), std::move(child)).second)
                        fail("archive_retained_inventory_invalid", "Duplicate retained directory");
                    scan(*pointer, relative + "/");
                    continue;
                }
                const auto found = files.find(relative);
                if (found == files.end()) fail("archive_retained_extra_entry", relative);
                auto input = std::make_unique<facman::platform::StableInputFile>();
                check(directory.open_child_file_no_follow_pinned(leaf, *input));
                if (!input->identity().regular_file || input->identity().link_count != 1U ||
                    input->size() != found->second.bytes)
                    fail("archive_retained_file_changed", relative);
                facman::base::Sha256Hasher hash;
                std::array<unsigned char, 65536> block {};
                for (std::uint64_t offset = 0; offset < input->size();) {
                    guard();
                    const auto count = static_cast<std::size_t>(std::min<std::uint64_t>(block.size(), input->size() - offset));
                    if (input->read_at(offset, block.data(), count) != count)
                        fail("archive_retained_short_read", relative);
                    hash.update(block.data(), count); offset += count;
                }
                if (hash.finish() != found->second.sha256)
                    fail("archive_retained_file_changed", relative);
                check(input->revalidate_path());
                if (!existing_.emplace(relative, std::move(input)).second)
                    fail("archive_retained_inventory_invalid", "Duplicate retained file");
            }
            check(directory.revalidate());
        };
        retained_expected_ = files; retained_directories_ = dirs;
        for (const auto& entry : expected) required_entries_.insert(entry.first);
        for (const auto& entry : additional) required_retained_.insert(entry.path);
        resumed_ = true;
        scan(directory_, "");
        for (const auto& name : required_retained_) {
            guard();
            if (!existing_.count(name)) fail("archive_retained_file_missing", name);
        }
        verify_retained();
        point(std::numeric_limits<std::uint32_t>::max(), "retained_ready");
    }
    bool retained_entry(const Entry& entry) const
    {
        const auto found = existing_.find(entry.path);
        if (found == existing_.end()) return false;
        point(entry.index, "before_retained_entry");
        check(found->second->revalidate_path());
        point(entry.index, "retained_entry_verified");
        return true;
    }
    void verify_retained() const
    {
        guard();
        for (const auto& item : parents_) { guard(); check(item.second->revalidate()); }
        for (const auto& item : existing_) { guard(); check(item.second->revalidate_path()); }
    }
    // Windows directory handles stabilize the object, but permit child
    // creation. Re-enumerate after callbacks and before creates, then hash the
    // final tree. This is an audit, never an atomic namespace absence lease.
    void verify_namespace(bool complete, bool hash_files) const
    {
        std::set<std::string> found;
        std::function<void(const facman::platform::StableDirectoryObject&, const std::string&)> scan;
        scan = [&](const facman::platform::StableDirectoryObject& directory, const std::string& prefix) {
            guard();
            std::vector<fs::path> names;
            check(directory.list_child_names_bounded(retained_expected_.size() + retained_directories_.size(), names));
            for (const auto& leaf : names) {
                guard();
                const auto relative = prefix + leaf.u8string();
                if (retained_directories_.count(relative)) {
                    const auto held = parents_.find(root / fs::u8path(relative));
                    if (held == parents_.end()) fail("archive_retained_untracked_directory", relative);
                    check(held->second->revalidate());
                    facman::platform::StableDirectoryObject child;
                    check(directory.open_child_directory_no_follow(leaf, child));
                    if (child.identity().device != held->second->identity().device ||
                        child.identity().object != held->second->identity().object)
                        fail("archive_retained_directory_changed", relative);
                    scan(child, relative + "/");
                    continue;
                }
                const auto expected = retained_expected_.find(relative);
                if (expected == retained_expected_.end()) fail("archive_retained_extra_entry", relative);
                if (!found.insert(relative).second) fail("archive_retained_inventory_invalid", relative);
                if (!existing_.count(relative) && !created_.count(relative))
                    fail("archive_retained_untracked_entry", relative);
                facman::platform::StableInputFile input;
                check(directory.open_child_file_no_follow_pinned(leaf, input));
                if (!input.identity().regular_file || input.identity().link_count != 1U || input.size() != expected->second.bytes)
                    fail("archive_retained_file_changed", relative);
                const auto created = created_.find(relative);
                if (created != created_.end() &&
                    (input.identity().device != created->second.device || input.identity().object != created->second.object))
                    fail("archive_retained_file_changed", relative);
                const auto pinned = existing_.find(relative);
                if (pinned != existing_.end() && !input.identity().unchanged(pinned->second->identity()))
                    fail("archive_retained_file_changed", relative);
                check(input.revalidate_path());
                if (!hash_files) continue;
                facman::base::Sha256Hasher hash;
                std::array<unsigned char, 65536> block {};
                for (std::uint64_t offset = 0; offset < input.size();) {
                    guard();
                    const auto count = static_cast<std::size_t>(std::min<std::uint64_t>(block.size(), input.size() - offset));
                    if (input.read_at(offset, block.data(), count) != count) fail("archive_retained_short_read", relative);
                    hash.update(block.data(), count); offset += count;
                }
                if (hash.finish() != expected->second.sha256) fail("archive_retained_file_changed", relative);
                check(input.revalidate_path());
            }
            check(directory.revalidate());
        };
        scan(directory_, "");
        for (const auto& name : required_retained_) {
            guard();
            if (!found.count(name)) fail("archive_retained_file_missing", name);
        }
        if (complete) for (const auto& name : required_entries_) {
            guard();
            if (!found.count(name)) fail("archive_retained_file_missing", name);
        }
        verify_retained();
    }
    void create_output(const Entry& entry, facman::platform::DurableOutputFile& output)
    {
        guard();
        if (resumed_) verify_namespace(false, false);
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
            if (observation_) observation_->begin_create_attempt();
            const auto created = parent->create_child_directory_exclusive_utf8(part.u8string(), *object);
            if (!created.ok()) fail("archive_extract_directory_collision", created.detail);
            parent = object.get();
            parents_.emplace(current, std::move(object));
            point(entry.index, "directory_created");
        }
        if (observation_) observation_->begin_create_attempt();
        check(parent->create_child_file_exclusive_utf8(fs::u8path(entry.path).filename().u8string(),
            entry.expanded_size, output));
        if (resumed_ && !created_.emplace(entry.path, output.identity()).second)
            fail("archive_retained_inventory_invalid", "Repeated missing-file creation");
        point(entry.index, "output_created");
    }
    fs::path root;
private:
    facman::platform::StableDirectoryObject parent_, directory_;
    std::map<fs::path, std::unique_ptr<facman::platform::StableDirectoryObject>> parents_;
    std::map<std::string, std::unique_ptr<facman::platform::StableInputFile>> existing_;
    Expected retained_expected_;
    std::set<std::string> retained_directories_, required_entries_, required_retained_;
    std::map<std::string, facman::platform::FileIdentity> created_;
    bool resumed_ = false;
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
Status extract_verified_missing_to_retained_staging(
    const Plan& plan, facman::platform::StableDirectoryObject& staging_root, const Limits& limits,
    const std::vector<VerifiedEntry>& expected, const std::vector<VerifiedEntry>& retained_files,
    const std::vector<std::string>& allowed_directories, const ExtractionCheckpoint& checkpoint,
    ExtractionObservation* observation)
{
    try {
        const auto entries = admit(plan, limits, expected);
        RetainedRoot root(staging_root.path(), limits, checkpoint, observation);
        root.adopt(staging_root, entries, retained_files, allowed_directories);
        root.verify_namespace(false, true);
        for (const auto& entry : plan.entries) {
            if (root.retained_entry(entry)) continue;
            extract_entry(plan, entry, entries.at(entry.path), limits, root);
        }
        root.verify_namespace(true, true);
        check(staging_root.revalidate());
        root.guard();
        if (observation) observation->complete();
        return Status::success();
    } catch (const Failure& failure) {
        auto status = failure.status;
        status.detail += "; no cleanup performed; retained destination " + staging_root.path().u8string();
        return status;
    } catch (const std::exception& error) {
        return Status::failure("archive_retained_extraction_failed",
            std::string(error.what()) + "; no cleanup performed; retained destination " + staging_root.path().u8string());
    } catch (...) {
        return Status::failure("archive_retained_extraction_failed", "Unknown failure; no cleanup performed");
    }
}
}
