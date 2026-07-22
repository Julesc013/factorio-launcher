// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "flb_factorio_candidate_manifest.h"

#include "fl_json.h"
#include "fl_path_safety.h"
#include "fl_sha256.h"

#include <algorithm>
#include <array>
#include <set>
#include <tuple>
#include <utility>

namespace facman::factorio::launch {
namespace {

namespace fs = std::filesystem;
namespace json = facman::core::json;

facman::core::Error manifest_error(
    std::string message,
    std::string path,
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::refused)
{
    return {"permit_wrong_evidence", std::move(message), std::move(path), kind};
}

std::string sha256_text(const std::string& value)
{
    return facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(value.data()), value.size());
}

const char* kind_name(facman::platform::PathObjectKind value) noexcept
{
    switch (value) {
    case facman::platform::PathObjectKind::absent: return "absent";
    case facman::platform::PathObjectKind::regular_file: return "file";
    case facman::platform::PathObjectKind::directory: return "directory";
    case facman::platform::PathObjectKind::other: return "other";
    }
    return "other";
}

std::string path_identity_json(const facman::platform::PathIdentity& identity)
{
    json::ObjectBuilder output;
    output.add_bool("exists", identity.exists);
    output.add_bool("reparse_or_link", identity.reparse_or_link);
    output.add_bool("fixed_local_volume", identity.fixed_local_volume);
    output.add_string("kind", kind_name(identity.kind));
    output.add_unsigned_integer("device", identity.device);
    output.add_unsigned_integer("object", identity.object);
    output.add_unsigned_integer("size", identity.size);
    output.add_unsigned_integer("last_write_ticks", identity.last_write_ticks);
    output.add_string("filesystem_name", identity.filesystem_name);
    return output.serialize();
}

std::string identity_digest(const facman::platform::PathIdentity& identity)
{
    return sha256_text(path_identity_json(identity));
}

bool hash_stable_file(
    const fs::path& path,
    std::uint64_t maximum_bytes,
    std::chrono::steady_clock::time_point deadline,
    std::string& digest,
    std::uint64_t& bytes,
    std::string& gap)
{
    facman::platform::StableInputFile input;
    const auto opened = input.open_no_follow(path);
    if (!opened.ok()) {
        gap = opened.code;
        return false;
    }
    if (input.size() > maximum_bytes) {
        gap = "byte_limit_exceeded";
        return false;
    }
    facman::base::Sha256Hasher hasher;
    std::array<unsigned char, 64U * 1024U> buffer {};
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        if (std::chrono::steady_clock::now() >= deadline) {
            gap = "elapsed_time_limit_exceeded";
            return false;
        }
        const std::size_t count = input.read_at(offset, buffer.data(), buffer.size());
        if (count == 0U) {
            gap = "stable_read_incomplete";
            return false;
        }
        hasher.update(buffer.data(), count);
        offset += count;
    }
    const auto current = input.revalidate();
    if (!current.ok()) {
        gap = current.code;
        return false;
    }
    bytes = offset;
    digest = hasher.finish();
    return true;
}

std::string manifest_json(const CandidateStableManifest& manifest, bool include_digest)
{
    std::vector<CandidateManifestEntry> entries = manifest.entries;
    std::sort(entries.begin(), entries.end(), [](const auto& left, const auto& right) {
        return std::tie(left.relative_path, left.kind) <
            std::tie(right.relative_path, right.kind);
    });
    json::ArrayBuilder values;
    for (const auto& value : entries) {
        json::ObjectBuilder item;
        item.add_string("relative_path", value.relative_path);
        item.add_string("kind", value.kind);
        item.add_string("identity_digest", value.identity_digest);
        item.add_string("content_digest", value.content_digest);
        item.add_unsigned_integer("size", value.size);
        values.add_object(item);
    }
    std::vector<std::string> gaps = manifest.gap_codes;
    std::sort(gaps.begin(), gaps.end());
    json::ArrayBuilder gap_values;
    for (const std::string& value : gaps) gap_values.add_string(value);
    json::ObjectBuilder output;
    output.add_string("schema", manifest.schema);
    output.add_string("canonicalization_version", "facman.sorted-json.v1");
    output.add_string("resource_id", manifest.resource_id);
    output.add_bool("root_present", manifest.root_present);
    output.add_bool("complete", manifest.complete);
    output.add_string("root_identity_digest", manifest.root_identity_digest);
    output.add_array("entries", values);
    output.add_array("gap_codes", gap_values);
    output.add_unsigned_integer("bytes_hashed", manifest.bytes_hashed);
    if (include_digest) output.add_string("manifest_digest", manifest.manifest_digest);
    return output.serialize();
}

} // namespace

std::string CandidateStableManifest::canonical_json() const
{
    return manifest_json(*this, true);
}

facman::core::Result<CandidateStableManifest> capture_candidate_stable_manifest(
    const std::string& resource_id,
    const fs::path& root,
    bool allow_absent,
    CandidateManifestLimits limits)
{
    if (resource_id.empty() || root.empty() || limits.maximum_entries == 0U ||
        limits.maximum_bytes == 0U || limits.maximum_elapsed.count() <= 0) {
        return facman::core::Result<CandidateStableManifest>::failure(manifest_error(
            "stable manifest request is incomplete", "$candidate.manifest"));
    }
    CandidateStableManifest output;
    output.resource_id = resource_id;
    const auto deadline = std::chrono::steady_clock::now() + limits.maximum_elapsed;
    std::string path_detail;
    if (facman::base::path_crosses_link_or_reparse_point(root, path_detail)) {
        output.gap_codes.push_back("root_link_or_reparse_refused");
        output.manifest_digest = sha256_text(manifest_json(output, false));
        return facman::core::Result<CandidateStableManifest>::success(std::move(output));
    }
    facman::platform::PathIdentity root_before;
    const auto root_status = facman::platform::inspect_path_no_follow(root, root_before);
    if (!root_status.ok()) {
        output.gap_codes.push_back(root_status.code);
        output.manifest_digest = sha256_text(manifest_json(output, false));
        return facman::core::Result<CandidateStableManifest>::success(std::move(output));
    }
    output.root_present = root_before.exists;
    output.root_identity_digest = identity_digest(root_before);
    if (!root_before.exists) {
        output.complete = allow_absent;
        if (!allow_absent) output.gap_codes.push_back("required_root_absent");
        output.manifest_digest = sha256_text(manifest_json(output, false));
        return facman::core::Result<CandidateStableManifest>::success(std::move(output));
    }
    if (root_before.reparse_or_link || root_before.kind == facman::platform::PathObjectKind::other) {
        output.gap_codes.push_back("root_link_or_unsupported_object_refused");
        output.manifest_digest = sha256_text(manifest_json(output, false));
        return facman::core::Result<CandidateStableManifest>::success(std::move(output));
    }

    std::vector<std::pair<fs::path, std::string>> pending;
    pending.emplace_back(root, std::string {});
    std::set<std::string> relative_paths;
    bool stopped = false;
    while (!pending.empty() && !stopped) {
        if (std::chrono::steady_clock::now() >= deadline) {
            output.gap_codes.push_back("elapsed_time_limit_exceeded");
            break;
        }
        const auto current = std::move(pending.back());
        pending.pop_back();
        facman::platform::PathIdentity directory_before;
        const auto directory_status = facman::platform::inspect_path_no_follow(
            current.first, directory_before);
        if (!directory_status.ok() || !directory_before.exists ||
            directory_before.kind != facman::platform::PathObjectKind::directory ||
            directory_before.reparse_or_link) {
            output.gap_codes.push_back(
                directory_status.ok() ? "directory_identity_invalid" : directory_status.code);
            continue;
        }
        std::error_code error;
        std::vector<fs::path> children;
        for (fs::directory_iterator iterator(
                 current.first, fs::directory_options::none, error), end;
             iterator != end && !error; iterator.increment(error)) {
            children.push_back(iterator->path());
        }
        if (error) {
            output.gap_codes.push_back("directory_read_failed");
            continue;
        }
        std::sort(children.begin(), children.end(), [](const fs::path& left, const fs::path& right) {
            return left.filename().generic_string() < right.filename().generic_string();
        });
        for (const fs::path& child : children) {
            if (output.entries.size() >= limits.maximum_entries) {
                output.gap_codes.push_back("entry_limit_exceeded");
                stopped = true;
                break;
            }
            const fs::path relative = child.lexically_relative(root);
            const std::string relative_text = relative.generic_string();
            if (relative_text.empty() || relative_text.rfind("..", 0) == 0 ||
                !relative_paths.insert(relative_text).second) {
                output.gap_codes.push_back("relative_path_invalid_or_duplicate");
                continue;
            }
            facman::platform::PathIdentity identity;
            const auto status = facman::platform::inspect_path_no_follow(child, identity);
            if (!status.ok() || !identity.exists || identity.reparse_or_link ||
                identity.kind == facman::platform::PathObjectKind::other) {
                output.gap_codes.push_back(
                    status.ok() ? "entry_link_or_unsupported_object_refused" : status.code);
                continue;
            }
            CandidateManifestEntry entry;
            entry.relative_path = relative_text;
            entry.kind = kind_name(identity.kind);
            entry.identity_digest = identity_digest(identity);
            entry.size = identity.size;
            if (identity.kind == facman::platform::PathObjectKind::regular_file) {
                std::string gap;
                std::uint64_t bytes = 0;
                if (output.bytes_hashed > limits.maximum_bytes ||
                    !hash_stable_file(
                        child, limits.maximum_bytes - output.bytes_hashed,
                        deadline, entry.content_digest, bytes, gap)) {
                    output.gap_codes.push_back(gap.empty() ? "file_hash_failed" : gap);
                    continue;
                }
                output.bytes_hashed += bytes;
            } else {
                pending.emplace_back(child, relative_text);
            }
            output.entries.push_back(std::move(entry));
        }
        facman::platform::PathIdentity directory_after;
        const auto after_status = facman::platform::inspect_path_no_follow(
            current.first, directory_after);
        if (!after_status.ok() || !directory_before.unchanged(directory_after)) {
            output.gap_codes.push_back("directory_changed_during_capture");
        }
    }
    facman::platform::PathIdentity root_after;
    const auto root_after_status = facman::platform::inspect_path_no_follow(root, root_after);
    if (!root_after_status.ok() || !root_before.unchanged(root_after)) {
        output.gap_codes.push_back("root_changed_during_capture");
    }
    std::sort(output.gap_codes.begin(), output.gap_codes.end());
    output.gap_codes.erase(
        std::unique(output.gap_codes.begin(), output.gap_codes.end()),
        output.gap_codes.end());
    output.complete = output.gap_codes.empty();
    output.manifest_digest = sha256_text(manifest_json(output, false));
    return facman::core::Result<CandidateStableManifest>::success(std::move(output));
}

facman::core::Result<ProtectedResourceComparison> compare_candidate_stable_manifests(
    const CandidateStableManifest& before,
    const CandidateStableManifest& after)
{
    if (before.resource_id.empty() || before.resource_id != after.resource_id ||
        before.manifest_digest.empty() || after.manifest_digest.empty()) {
        return facman::core::Result<ProtectedResourceComparison>::failure(manifest_error(
            "stable manifest comparison identities do not match",
            "$candidate.protected_comparison"));
    }
    if (before.manifest_digest != sha256_text(manifest_json(before, false)) ||
        after.manifest_digest != sha256_text(manifest_json(after, false))) {
        return facman::core::Result<ProtectedResourceComparison>::failure(manifest_error(
            "stable manifest digest is not canonical",
            "$candidate.protected_comparison"));
    }
    ProtectedResourceComparison output;
    output.resource_id = before.resource_id;
    output.before_digest = before.manifest_digest;
    output.after_digest = after.manifest_digest;
    output.complete = before.complete && after.complete;
    output.changed = output.complete &&
        (before.root_present != after.root_present ||
         before.root_identity_digest != after.root_identity_digest ||
         before.entries.size() != after.entries.size() ||
         before.manifest_digest != after.manifest_digest);
    return facman::core::Result<ProtectedResourceComparison>::success(std::move(output));
}

} // namespace facman::factorio::launch
