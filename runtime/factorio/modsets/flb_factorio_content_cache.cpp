// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_content_cache.h"

#include "fl_file_io.h"
#include "fl_identity.h"
#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"
#include "fl_system_services.h"
#include "fl_transaction.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <map>
#include <set>
#include <system_error>
#include <utility>

namespace facman::factorio::content::cache {
namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace tx = facman::transaction;

namespace {

constexpr const char* kMarkerName = "facman-content-cache.v1.json";
constexpr const char* kMarker =
    "{\"schema\":\"factorio.local_content_cache.v1\","
    "\"layout\":\"sha256-fanout-v1\",\"local_only\":true,"
    "\"network_authority\":false}\n";

template <typename T>
facman::core::Result<T> failure(
    const std::string& code,
    const std::string& message,
    const fs::path& path = {},
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::refused)
{
    return facman::core::Result<T>::failure(
        {code, message, facman::platform::path_to_utf8(path), kind});
}

facman::core::Result<void> void_failure(
    const std::string& code,
    const std::string& message,
    const fs::path& path = {},
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::refused)
{
    return facman::core::Result<void>::failure(
        {code, message, facman::platform::path_to_utf8(path), kind});
}

bool lower_hex(const std::string& value)
{
    return std::all_of(value.begin(), value.end(), [](unsigned char byte) {
        return (byte >= '0' && byte <= '9') || (byte >= 'a' && byte <= 'f');
    });
}

fs::path objects_root(const fs::path& root)
{
    return root / "objects" / "sha256";
}

fs::path staging_root(const fs::path& root)
{
    return root / ".staging";
}

fs::path blob_path(const fs::path& root, const std::string& sha256)
{
    return objects_root(root) / sha256.substr(0U, 2U) / sha256;
}

facman::core::Result<std::string> normalized_digest(const std::string& value)
{
    auto digest = facman::core::Sha256Digest::parse(value);
    if (!digest) return failure<std::string>(
        "content_cache_digest_invalid", digest.error().message);
    return facman::core::Result<std::string>::success(digest.value().str());
}

facman::core::Result<std::string> stable_small_text(
    const fs::path& path,
    std::uint64_t maximum = 64U * 1024U)
{
    facman::platform::StableInputFile input;
    auto status = input.open_no_follow(path);
    if (!status.ok() || !input.identity().regular_file || input.identity().link_count != 1U ||
        input.size() > maximum) {
        return failure<std::string>(
            "content_cache_marker_invalid",
            status.ok() ? "Cache marker is not a bounded singly-linked regular file" : status.detail,
            path);
    }
    std::string text(static_cast<std::size_t>(input.size()), '\0');
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t count = input.read_at(
            offset, text.data() + static_cast<std::size_t>(offset),
            static_cast<std::size_t>(input.size() - offset));
        if (count == 0U) return failure<std::string>(
            "content_cache_marker_changed", "Cache marker produced a short stable read", path);
        offset += count;
    }
    status = input.revalidate();
    if (!status.ok()) return failure<std::string>(
        "content_cache_marker_changed", status.detail, path);
    return facman::core::Result<std::string>::success(std::move(text));
}

facman::core::Result<void> validate_root(const fs::path& root)
{
    if (root.empty() || !root.is_absolute() || root == root.root_path() || root.filename().empty()) {
        return void_failure(
            "content_cache_root_invalid", "Cache root must be a specific absolute non-root path", root);
    }
    std::error_code error;
    if (!fs::is_directory(root, error) || error) return void_failure(
        "content_cache_uninitialized", error ? error.message() : "Cache root is not a directory", root);
    std::string detail;
    if (facman::base::path_crosses_link_or_reparse_point(root, detail)) return void_failure(
        "content_cache_root_unsafe", detail, root);
    auto marker = stable_small_text(root / kMarkerName);
    if (!marker || marker.value() != kMarker) return void_failure(
        "content_cache_marker_invalid",
        marker ? "Cache marker does not match the owned layout" : marker.error().message,
        root / kMarkerName);
    for (const fs::path& directory : {objects_root(root), staging_root(root)}) {
        if (!fs::is_directory(directory, error) || error) return void_failure(
            "content_cache_layout_invalid",
            error ? error.message() : "Cache layout directory is missing", directory);
        if (facman::base::path_crosses_link_or_reparse_point(directory, detail)) return void_failure(
            "content_cache_root_unsafe", detail, directory);
    }
    return facman::core::Result<void>::success();
}

void remove_exact_file(const fs::path& path)
{
    facman::platform::StableInputFile file;
    if (file.open_no_follow(path).ok()) {
        (void)facman::platform::remove_exact_object(path, file.identity());
    }
}

facman::core::Result<BlobIdentity> stable_blob_identity(
    const fs::path& path,
    std::uint64_t maximum_bytes)
{
    facman::platform::StableInputFile input;
    auto status = input.open_no_follow(path);
    if (!status.ok() || !input.identity().regular_file || input.identity().link_count != 1U) {
        return failure<BlobIdentity>(
            "content_cache_blob_unsafe",
            status.ok() ? "Blob is not a singly-linked regular file" : status.detail,
            path);
    }
    if (input.size() == 0U || input.size() > maximum_bytes) return failure<BlobIdentity>(
        "content_cache_blob_budget_exceeded", "Blob size is outside the admitted bound", path);
    facman::base::Sha256Hasher hasher;
    std::array<unsigned char, 64U * 1024U> buffer {};
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t count = input.read_at(
            offset, buffer.data(), static_cast<std::size_t>(
                std::min<std::uint64_t>(buffer.size(), input.size() - offset)));
        if (count == 0U) return failure<BlobIdentity>(
            "content_cache_blob_changed", "Blob produced a short stable read", path);
        hasher.update(buffer.data(), count);
        offset += count;
    }
    status = input.revalidate();
    if (!status.ok()) return failure<BlobIdentity>(
        "content_cache_blob_changed", status.detail, path);
    return facman::core::Result<BlobIdentity>::success({hasher.finish(), input.size()});
}

facman::core::Result<Entry> verify_path(
    const fs::path& path,
    const BlobIdentity& expected,
    std::uint64_t maximum_bytes)
{
    auto actual = stable_blob_identity(path, maximum_bytes);
    if (!actual || actual.value().sha256 != expected.sha256 || actual.value().size != expected.size) {
        return failure<Entry>(
            "content_cache_collision_or_corruption",
            actual ? "Cached blob does not match its immutable digest and size identity" : actual.error().message,
            path,
            facman::core::OutcomeKind::conflict);
    }
    return facman::core::Result<Entry>::success({actual.value(), path});
}

json::ObjectBuilder entry_builder(const Entry& entry)
{
    json::ObjectBuilder output;
    output.add_string("sha256", entry.blob.sha256);
    (void)output.add_unsigned_integer("size", entry.blob.size);
    output.add_string("cache_ref", "sha256:" + entry.blob.sha256);
    return output;
}

} // namespace

LocalContentCache::LocalContentCache(fs::path root, Limits limits)
    : root_(std::move(root).lexically_normal()), limits_(limits)
{
}

const fs::path& LocalContentCache::root() const noexcept
{
    return root_;
}

facman::core::Result<void> LocalContentCache::initialize() const
{
    if (root_.empty() || !root_.is_absolute() || root_ == root_.root_path() || root_.filename().empty()) {
        return void_failure(
            "content_cache_root_invalid", "Cache root must be a specific absolute non-root path", root_);
    }
    if (limits_.maximum_blob_bytes == 0U || limits_.maximum_inventory_bytes == 0U ||
        limits_.maximum_inventory_entries == 0U) {
        return void_failure(
            "content_cache_limits_invalid", "All cache limits must be positive", root_);
    }
    std::error_code error;
    if (fs::exists(root_, error)) return error
        ? void_failure("content_cache_root_invalid", error.message(), root_)
        : validate_root(root_);
    if (error) return void_failure("content_cache_root_invalid", error.message(), root_);
    const fs::path parent = root_.parent_path();
    if (!fs::is_directory(parent, error) || error) return void_failure(
        "content_cache_parent_invalid",
        error ? error.message() : "Cache parent must already exist", parent);
    std::string detail;
    if (facman::base::path_crosses_link_or_reparse_point(parent, detail)) return void_failure(
        "content_cache_root_unsafe", detail, parent);
    facman::platform::RandomIdGenerator random;
    const fs::path staging = parent / (".facman-content-cache-" + random.next("stage"));
    if (!facman::base::write_text_new_atomic(staging / kMarkerName, kMarker, detail)) {
        return void_failure("content_cache_initialize_failed", detail, staging);
    }
    fs::create_directories(objects_root(staging), error);
    if (!error) fs::create_directories(staging_root(staging), error);
    if (error) {
        if (fs::is_regular_file(staging / kMarkerName)) {
            (void)facman::base::remove_owned_staging_tree(staging, kMarkerName, detail);
        }
        return void_failure("content_cache_initialize_failed", error.message(), staging);
    }
    if (!facman::base::commit_directory_no_clobber(staging, root_, detail)) {
        std::string cleanup;
        (void)facman::base::remove_owned_staging_tree(staging, kMarkerName, cleanup);
        auto raced = validate_root(root_);
        if (raced) return raced;
        return void_failure("content_cache_initialize_failed", detail, root_);
    }
    return validate_root(root_);
}

facman::core::Result<InsertResult> LocalContentCache::insert(
    const fs::path& source,
    const std::string& expected_sha256) const
{
    auto root_status = validate_root(root_);
    if (!root_status) return failure<InsertResult>(
        root_status.error().code, root_status.error().message, fs::u8path(root_status.error().path));
    std::string expected;
    if (!expected_sha256.empty()) {
        auto normalized = normalized_digest(expected_sha256);
        if (!normalized) return failure<InsertResult>(normalized.error().code, normalized.error().message);
        expected = normalized.take_value();
    }
    facman::platform::StableInputFile input;
    auto status = input.open_no_follow(source);
    if (!status.ok() || !input.identity().regular_file || input.identity().link_count != 1U) {
        return failure<InsertResult>(
            "content_cache_source_unsafe",
            status.ok() ? "Cache source is not a singly-linked regular file" : status.detail,
            source);
    }
    if (input.size() == 0U || input.size() > limits_.maximum_blob_bytes) return failure<InsertResult>(
        "content_cache_blob_budget_exceeded", "Cache source size is outside the admitted bound", source);
    facman::platform::RandomIdGenerator random;
    const fs::path staging = staging_root(root_) / ("blob-" + random.next("stage"));
    facman::platform::DurableOutputFile output;
    status = output.create_exclusive(staging, input.size());
    if (!status.ok()) return failure<InsertResult>(
        "content_cache_stage_failed", status.detail, staging);
    facman::base::Sha256Hasher hasher;
    std::array<unsigned char, 64U * 1024U> buffer {};
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t count = input.read_at(
            offset, buffer.data(), static_cast<std::size_t>(
                std::min<std::uint64_t>(buffer.size(), input.size() - offset)));
        if (count == 0U || output.write_at(offset, buffer.data(), count) != count) {
            output.close_without_flush();
            remove_exact_file(staging);
            return failure<InsertResult>(
                "content_cache_stage_failed", "Cache source copy produced a short read or write", source);
        }
        hasher.update(buffer.data(), count);
        offset += count;
    }
    status = input.revalidate();
    if (!status.ok()) {
        output.close_without_flush();
        remove_exact_file(staging);
        return failure<InsertResult>(
            "content_cache_source_changed", status.detail, source);
    }
    status = output.flush_file_and_parent();
    if (!status.ok()) {
        remove_exact_file(staging);
        return failure<InsertResult>(
            "content_cache_stage_failed", status.detail, staging);
    }
    BlobIdentity identity {hasher.finish(), input.size()};
    if (!expected.empty() && identity.sha256 != expected) {
        remove_exact_file(staging);
        return failure<InsertResult>(
            "content_cache_digest_mismatch", "Cache source does not match the expected SHA-256 identity", source,
            facman::core::OutcomeKind::conflict);
    }
    auto staged = verify_path(staging, identity, limits_.maximum_blob_bytes);
    if (!staged) {
        remove_exact_file(staging);
        return failure<InsertResult>(staged.error().code, staged.error().message, staging);
    }
    const fs::path destination = blob_path(root_, identity.sha256);
    std::error_code error;
    fs::create_directories(destination.parent_path(), error);
    std::string detail;
    if (error || facman::base::path_crosses_link_or_reparse_point(destination.parent_path(), detail)) {
        remove_exact_file(staging);
        return failure<InsertResult>(
            "content_cache_root_unsafe", error ? error.message() : detail, destination.parent_path());
    }
    facman::platform::PathIdentity current;
    status = facman::platform::inspect_path_no_follow(destination, current);
    if (!status.ok()) {
        remove_exact_file(staging);
        return failure<InsertResult>("content_cache_inspect_failed", status.detail, destination);
    }
    if (current.exists) {
        remove_exact_file(staging);
        auto existing = verify_path(destination, identity, limits_.maximum_blob_bytes);
        if (!existing) return failure<InsertResult>(
            existing.error().code, existing.error().message, destination,
            facman::core::OutcomeKind::conflict);
        return facman::core::Result<InsertResult>::success({existing.value(), false});
    }
    status = facman::platform::commit_no_replace(staging, destination);
    if (!status.ok()) {
        remove_exact_file(staging);
        auto existing = verify_path(destination, identity, limits_.maximum_blob_bytes);
        if (existing) return facman::core::Result<InsertResult>::success({existing.value(), false});
        return failure<InsertResult>(
            "content_cache_collision_or_corruption", status.detail, destination,
            facman::core::OutcomeKind::conflict);
    }
    auto committed = verify_path(destination, identity, limits_.maximum_blob_bytes);
    if (!committed) return failure<InsertResult>(
        committed.error().code, committed.error().message, destination,
        facman::core::OutcomeKind::outcome_unknown);
    return facman::core::Result<InsertResult>::success({committed.value(), true});
}

facman::core::Result<Entry> LocalContentCache::verify(const BlobIdentity& blob) const
{
    auto root_status = validate_root(root_);
    if (!root_status) return failure<Entry>(
        root_status.error().code, root_status.error().message, fs::u8path(root_status.error().path));
    auto digest = normalized_digest(blob.sha256);
    if (!digest || blob.size == 0U || blob.size > limits_.maximum_blob_bytes) return failure<Entry>(
        "content_cache_identity_invalid", "Requested cache blob identity is invalid");
    BlobIdentity expected {digest.value(), blob.size};
    return verify_path(blob_path(root_, expected.sha256), expected, limits_.maximum_blob_bytes);
}

facman::core::Result<Entry> LocalContentCache::materialize(
    const BlobIdentity& blob,
    const fs::path& target) const
{
    auto source = verify(blob);
    if (!source) return source;
    if (target.empty() || !target.is_absolute() || target.filename().empty()) return failure<Entry>(
        "content_cache_target_invalid", "Materialization target must be a specific absolute file", target);
    const fs::path parent_path = target.parent_path();
    facman::platform::StableDirectoryObject parent;
    auto status = parent.open_no_follow(parent_path);
    if (!status.ok()) return failure<Entry>(
        "content_cache_target_unsafe", status.detail, parent_path);
    status = parent.validate_descendant(target, true);
    if (!status.ok()) return failure<Entry>(
        "content_cache_target_unsafe", status.detail, target);
    facman::platform::PathIdentity target_identity;
    status = facman::platform::inspect_path_no_follow(target, target_identity);
    if (!status.ok() || target_identity.exists) return failure<Entry>(
        "content_cache_target_exists",
        status.ok() ? "Materialization never overwrites an existing target" : status.detail,
        target,
        facman::core::OutcomeKind::conflict);
    auto digest = facman::core::Sha256Digest::parse(source.value().blob.sha256);
    std::string detail;
    if (!digest || !tx::CrossVolumeCopyVerifyCommit::commit(
            source.value().path, target, digest.value(), source.value().blob.size, detail)) {
        return failure<Entry>(
            "content_cache_materialization_failed", detail, target,
            facman::core::OutcomeKind::conflict);
    }
    status = parent.revalidate();
    auto result = verify_path(target, source.value().blob, limits_.maximum_blob_bytes);
    if (!status.ok() || !result) return failure<Entry>(
        "content_cache_materialization_unknown",
        !status.ok() ? status.detail : result.error().message,
        target,
        facman::core::OutcomeKind::outcome_unknown);
    return result;
}

facman::core::Result<Inventory> LocalContentCache::inventory() const
{
    auto root_status = validate_root(root_);
    if (!root_status) return failure<Inventory>(
        root_status.error().code, root_status.error().message, fs::u8path(root_status.error().path));
    Inventory output;
    std::error_code error;
    for (fs::directory_iterator prefix(objects_root(root_), fs::directory_options::none, error), end;
         prefix != end && !error; prefix.increment(error)) {
        const std::string prefix_name = prefix->path().filename().string();
        if (!prefix->is_directory(error) || error || prefix_name.size() != 2U || !lower_hex(prefix_name)) {
            return failure<Inventory>(
                "content_cache_layout_invalid", "Cache object fanout contains an unexpected entry", prefix->path());
        }
        std::string detail;
        if (facman::base::path_crosses_link_or_reparse_point(prefix->path(), detail)) return failure<Inventory>(
            "content_cache_root_unsafe", detail, prefix->path());
        for (fs::directory_iterator item(prefix->path(), fs::directory_options::none, error), item_end;
             item != item_end && !error; item.increment(error)) {
            const std::string digest = item->path().filename().string();
            if (digest.size() != 64U || !lower_hex(digest) || digest.substr(0U, 2U) != prefix_name ||
                !item->is_regular_file(error) || error) {
                return failure<Inventory>(
                    "content_cache_layout_invalid", "Cache object directory contains an unexpected entry", item->path());
            }
            if (output.entries.size() >= limits_.maximum_inventory_entries) return failure<Inventory>(
                "content_cache_inventory_budget_exceeded", "Cache object count exceeds its inventory bound", root_);
            auto identity = stable_blob_identity(item->path(), limits_.maximum_blob_bytes);
            if (!identity || identity.value().sha256 != digest) return failure<Inventory>(
                "content_cache_collision_or_corruption",
                identity ? "Cached object digest does not match its path identity" : identity.error().message,
                item->path(),
                facman::core::OutcomeKind::conflict);
            if (identity.value().size > limits_.maximum_inventory_bytes - output.total_bytes) {
                return failure<Inventory>(
                    "content_cache_inventory_budget_exceeded", "Cache byte total exceeds its inventory bound", root_);
            }
            output.total_bytes += identity.value().size;
            output.entries.push_back({identity.value(), item->path()});
        }
        if (error) return failure<Inventory>(
            "content_cache_inventory_failed", error.message(), prefix->path());
    }
    if (error) return failure<Inventory>(
        "content_cache_inventory_failed", error.message(), objects_root(root_));
    for (fs::directory_iterator item(staging_root(root_), fs::directory_options::none, error), end;
         item != end && !error; item.increment(error)) {
        if (!item->is_regular_file(error) || error) return failure<Inventory>(
            "content_cache_layout_invalid", "Cache staging contains an unexpected entry", item->path());
        ++output.incomplete_staging_entries;
    }
    if (error) return failure<Inventory>(
        "content_cache_inventory_failed", error.message(), staging_root(root_));
    std::sort(output.entries.begin(), output.entries.end(), [](const Entry& left, const Entry& right) {
        return left.blob.sha256 < right.blob.sha256;
    });
    return facman::core::Result<Inventory>::success(std::move(output));
}

facman::core::Result<GcPlan> LocalContentCache::plan_gc(
    const std::vector<std::string>& retained_sha256) const
{
    std::set<std::string> retained_set;
    for (const std::string& value : retained_sha256) {
        auto digest = normalized_digest(value);
        if (!digest || !retained_set.insert(digest.value()).second) return failure<GcPlan>(
            "content_cache_gc_input_invalid", "Retained digest set is invalid or duplicated");
    }
    auto values = inventory();
    if (!values) return failure<GcPlan>(
        values.error().code, values.error().message, fs::u8path(values.error().path), values.error().kind);
    if (values.value().incomplete_staging_entries != 0U) return failure<GcPlan>(
        "content_cache_recovery_required",
        "GC planning is refused while incomplete cache staging entries exist",
        staging_root(root_),
        facman::core::OutcomeKind::recovery_required);
    GcPlan output;
    const std::string inventory_json = to_json(values.value());
    output.inventory_sha256 = facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(inventory_json.data()), inventory_json.size());
    for (const Entry& entry : values.value().entries) {
        if (retained_set.erase(entry.blob.sha256) != 0U) {
            output.retained.push_back(entry);
            output.retained_bytes += entry.blob.size;
        } else {
            output.candidates.push_back(entry);
            output.reclaimable_bytes += entry.blob.size;
        }
    }
    if (!retained_set.empty()) return failure<GcPlan>(
        "content_cache_retained_blob_missing",
        "A retained digest is absent from the verified cache inventory",
        blob_path(root_, *retained_set.begin()),
        facman::core::OutcomeKind::not_found);
    return facman::core::Result<GcPlan>::success(std::move(output));
}

std::string to_json(const Inventory& value)
{
    json::ArrayBuilder entries;
    for (const Entry& entry : value.entries) entries.add_object(entry_builder(entry));
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.content_cache_inventory.v1");
    output.add_string("algorithm", "sha256");
    output.add_string("layout", "sha256-fanout-v1");
    output.add_bool("local_only", true);
    output.add_bool("verified", true);
    output.add_bool("mutation_executed", false);
    (void)output.add_unsigned_integer("total_bytes", value.total_bytes);
    (void)output.add_unsigned_integer("incomplete_staging_entries", value.incomplete_staging_entries);
    output.add_array("entries", entries);
    return output.serialize();
}

std::string to_json(const GcPlan& value)
{
    json::ArrayBuilder retained;
    for (const Entry& entry : value.retained) retained.add_object(entry_builder(entry));
    json::ArrayBuilder candidates;
    for (const Entry& entry : value.candidates) candidates.add_object(entry_builder(entry));
    json::ObjectBuilder output;
    output.add_string("schema", "factorio.content_cache_gc_plan.v1");
    output.add_string("inventory_sha256", value.inventory_sha256);
    output.add_bool("plan_only", true);
    output.add_bool("mutation_executed", false);
    (void)output.add_unsigned_integer("retained_bytes", value.retained_bytes);
    (void)output.add_unsigned_integer("reclaimable_bytes", value.reclaimable_bytes);
    output.add_array("retained", retained);
    output.add_array("candidates", candidates);
    return output.serialize();
}

} // namespace facman::factorio::content::cache
