// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_evidence_io.h"

#include "fl_archive.h"
#include "fl_file_io.h"
#include "fl_json.h"
#include "fl_random.h"
#include "fl_sha256.h"
#include "usk_archive_inspect.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <chrono>
#include <filesystem>
#include <iomanip>
#include <limits>
#include <set>
#include <sstream>
#include <stdexcept>
#include <system_error>
#include <vector>

namespace facman::play_evidence {
namespace {

namespace fs = std::filesystem;
namespace json = facman::core::json;
namespace platform = facman::platform;

constexpr const char* kResultSchema = "facman.play_evidence_io_result.v1";
constexpr std::uint64_t kMaximumJsonBytes = 64ULL * 1024ULL * 1024ULL;

facman::core::Error io_error(
    std::string code,
    std::string message,
    std::string path,
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::unavailable)
{
    return {std::move(code), std::move(message), std::move(path), kind};
}

std::string digest_bytes(const std::string& value)
{
    return facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(value.data()), value.size());
}

std::string canonical(const std::string& value)
{
    json::Limits limits;
    limits.maximum_bytes = kMaximumJsonBytes;
    limits.maximum_depth = 128U;
    limits.maximum_nodes = 1000000U;
    limits.maximum_string_bytes = kMaximumJsonBytes;
    auto parsed = json::parse(value, limits);
    if (!parsed) {
        throw std::runtime_error(
            "native evidence JSON canonicalization failed: " +
            parsed.error().code + ": " + parsed.error().message);
    }
    return parsed.value().serialize();
}

std::string canonical_digest(const std::string& value)
{
    return digest_bytes(canonical(value));
}

std::string hex_id(std::uint64_t value)
{
    std::ostringstream output;
    output << std::hex << std::setfill('0') << std::setw(16) << value;
    return output.str();
}

const char* path_kind_name(platform::PathObjectKind kind)
{
    switch (kind) {
    case platform::PathObjectKind::absent:
        return "absent";
    case platform::PathObjectKind::regular_file:
        return "regular_file";
    case platform::PathObjectKind::directory:
        return "directory";
    case platform::PathObjectKind::other:
        return "other";
    }
    return "other";
}

json::ObjectBuilder path_identity_json(
    const platform::PathIdentity& value,
    std::uint64_t link_count = 0)
{
    json::ObjectBuilder output;
    output.add_string("filesystem_name", value.filesystem_name);
    output.add_bool("fixed_local_volume", value.fixed_local_volume);
    output.add_string("kind", path_kind_name(value.kind));
    (void)output.add_unsigned_integer("last_write_ticks", value.last_write_ticks);
    (void)output.add_unsigned_integer("link_count", link_count);
    output.add_string("object_id", hex_id(value.object));
    output.add_bool("present", value.exists);
    output.add_bool("reparse_or_link", value.reparse_or_link);
    (void)output.add_unsigned_integer("size", value.size);
    output.add_string("volume_id", hex_id(value.device));
    return output;
}

struct StableRead {
    fs::path path;
    platform::PathIdentity before;
    platform::PathIdentity after;
    std::uint64_t link_count = 0;
    std::uint64_t bytes_read = 0;
    std::string sha256;
    std::string text;
};

StableRead read_file_stable(
    const fs::path& raw_path,
    std::uint64_t maximum_bytes,
    bool retain_text)
{
    if (maximum_bytes == 0) {
        throw std::runtime_error("stable file read has no positive byte budget");
    }
    std::error_code absolute_error;
    const fs::path path =
        fs::absolute(raw_path, absolute_error).lexically_normal();
    if (absolute_error || path.empty()) {
        throw std::runtime_error("stable file path is not absolute");
    }
    StableRead output;
    output.path = path;
    auto observed = platform::inspect_path_no_follow(path, output.before);
    if (!observed.ok() || !output.before.exists ||
        output.before.kind != platform::PathObjectKind::regular_file ||
        output.before.reparse_or_link) {
        throw std::runtime_error(
            "stable file path is not one regular no-follow object: " +
            observed.code + ": " + observed.detail);
    }
    platform::StableInputFile input;
    const auto opened = input.open_no_follow(path);
    if (!opened.ok()) {
        throw std::runtime_error(
            "stable file handle could not be opened: " +
            opened.code + ": " + opened.detail);
    }
    if (!input.identity().same_object(
            {output.before.device, output.before.object, output.before.size,
             input.identity().link_count, true}) ||
        input.size() != output.before.size ||
        input.size() > maximum_bytes ||
        input.identity().link_count != 1U) {
        throw std::runtime_error(
            "stable file handle identity or byte budget is invalid");
    }
    output.link_count = input.identity().link_count;
    if (retain_text) {
        output.text.reserve(static_cast<std::size_t>(input.size()));
    }
    facman::base::Sha256Hasher digest;
    std::array<unsigned char, 64U * 1024U> buffer {};
    std::uint64_t offset = 0;
    while (offset < input.size()) {
        const std::size_t requested = static_cast<std::size_t>(
            std::min<std::uint64_t>(buffer.size(), input.size() - offset));
        const std::size_t count =
            input.read_at(offset, buffer.data(), requested);
        if (count == 0U) {
            throw std::runtime_error("stable file read was incomplete");
        }
        digest.update(buffer.data(), count);
        if (retain_text) {
            output.text.append(
                reinterpret_cast<const char*>(buffer.data()), count);
        }
        offset += count;
    }
    output.bytes_read = offset;
    output.sha256 = digest.finish();
    const auto revalidated = input.revalidate();
    if (!revalidated.ok()) {
        throw std::runtime_error(
            "stable file handle changed during read: " +
            revalidated.code + ": " + revalidated.detail);
    }
    observed = platform::inspect_path_no_follow(path, output.after);
    if (!observed.ok() || !output.before.unchanged(output.after) ||
        output.after.device != input.identity().device ||
        output.after.object != input.identity().object ||
        output.after.size != input.identity().size) {
        throw std::runtime_error(
            "stable file path was substituted during the handle-bound read");
    }
    return output;
}

std::string file_observation_json(const StableRead& value)
{
    json::ObjectBuilder output;
    output.add_object(
        "after_identity",
        path_identity_json(value.after, value.link_count));
    output.add_object(
        "before_identity",
        path_identity_json(value.before, value.link_count));
    (void)output.add_unsigned_integer("bytes_read", value.bytes_read);
    output.add_string("content_sha256", value.sha256);
    output.add_bool("identity_stable", true);
    output.add_string("path", platform::path_to_utf8(value.path));
    output.add_bool("read_complete", value.bytes_read == value.before.size);
    return output.serialize();
}

std::string close_success_record(
    const std::string& operation,
    const std::string& payload_json)
{
    auto payload = json::parse(payload_json, {
        kMaximumJsonBytes, 128U, 1000000U, kMaximumJsonBytes});
    if (!payload) {
        throw std::runtime_error("native evidence payload is not valid JSON");
    }
    json::ObjectBuilder core;
    core.add_string("operation", operation);
    core.add_value("payload", payload.value());
    core.add_string("schema", kResultSchema);
    core.add_string("status", "ok");
    const std::string core_text = core.serialize();
    json::ObjectBuilder output;
    output.add_string("operation", operation);
    output.add_value("payload", payload.value());
    output.add_string("record_digest", canonical_digest(core_text));
    output.add_string("schema", kResultSchema);
    output.add_string("status", "ok");
    return output.serialize();
}

std::string inspect_file_payload(
    const fs::path& path,
    std::uint64_t maximum_bytes,
    bool include_document)
{
    StableRead read = read_file_stable(path, maximum_bytes, include_document);
    json::ObjectBuilder output;
    if (include_document) {
        json::Limits limits;
        limits.maximum_bytes = static_cast<std::size_t>(
            std::min<std::uint64_t>(
                maximum_bytes,
                static_cast<std::uint64_t>(
                    std::numeric_limits<std::size_t>::max())));
        limits.maximum_depth = 128U;
        limits.maximum_nodes = 1000000U;
        limits.maximum_string_bytes = limits.maximum_bytes;
        auto document = json::parse(read.text, limits);
        if (!document) {
            throw std::runtime_error(
                "bounded stable input is not strict JSON: " +
                document.error().code + ": " + document.error().message);
        }
        output.add_value("document", document.value());
    }
    auto observation = json::parse(file_observation_json(read));
    if (!observation) {
        throw std::runtime_error("file observation encoding failed");
    }
    output.add_value("file", observation.value());
    return output.serialize();
}

std::string read_text_payload(
    const fs::path& path,
    std::uint64_t maximum_bytes)
{
    StableRead read = read_file_stable(path, maximum_bytes, true);
    json::ObjectBuilder output;
    output.add_value(
        "file", json::parse(file_observation_json(read)).value());
    output.add_string("text", read.text);
    return output.serialize();
}

struct ManifestCapture {
    std::string entries_json;
    std::string core_json;
    std::string digest;
};

std::string folded_ascii(std::string value)
{
    std::transform(
        value.begin(), value.end(), value.begin(),
        [](unsigned char character) {
            return static_cast<char>(std::tolower(character));
        });
    return value;
}

ManifestCapture capture_manifest_once(
    const fs::path& raw_path,
    const ProbeRequest& request)
{
    std::error_code absolute_error;
    const fs::path path =
        fs::absolute(raw_path, absolute_error).lexically_normal();
    if (absolute_error || path.empty()) {
        throw std::runtime_error("manifest root path is invalid");
    }
    platform::PathIdentity root_before;
    auto inspected = platform::inspect_path_no_follow(path, root_before);
    if (!inspected.ok()) {
        throw std::runtime_error(
            "manifest root could not be inspected: " + inspected.detail);
    }
    if (root_before.reparse_or_link ||
        (root_before.exists &&
         root_before.kind != platform::PathObjectKind::directory &&
         root_before.kind != platform::PathObjectKind::regular_file)) {
        throw std::runtime_error(
            "manifest root is a link, reparse point, or unsupported object");
    }

    std::vector<std::pair<std::string, std::string>> entries;
    std::uint64_t bytes_hashed = 0;
    auto add_file = [&](const fs::path& file, const std::string& relative) {
        if (entries.size() >= request.maximum_entries) {
            throw std::runtime_error("manifest entry budget exceeded");
        }
        const std::uint64_t remaining =
            request.maximum_total_bytes - bytes_hashed;
        const std::uint64_t budget =
            std::min(request.maximum_entry_bytes, remaining);
        StableRead read = read_file_stable(file, budget, false);
        bytes_hashed += read.bytes_read;
        json::ObjectBuilder entry;
        entry.add_string("content_sha256", read.sha256);
        entry.add_string(
            "identity_digest",
            canonical_digest(path_identity_json(
                read.before, read.link_count).serialize()));
        entry.add_string("kind", "file");
        entry.add_string("relative_path", relative);
        (void)entry.add_unsigned_integer("size", read.bytes_read);
        entries.emplace_back(relative, entry.serialize());
    };

    if (root_before.exists &&
        root_before.kind == platform::PathObjectKind::regular_file) {
        add_file(path, ".");
    } else if (root_before.exists) {
        platform::StableDirectoryObject root;
        const auto opened = root.open_no_follow(path);
        if (!opened.ok()) {
            throw std::runtime_error(
                "manifest root directory could not be held: " +
                opened.code + ": " + opened.detail);
        }
        std::error_code iterator_error;
        fs::recursive_directory_iterator iterator(
            path, fs::directory_options::none, iterator_error);
        const fs::recursive_directory_iterator end;
        while (!iterator_error && iterator != end) {
            if (entries.size() >= request.maximum_entries) {
                throw std::runtime_error("manifest entry budget exceeded");
            }
            if (static_cast<std::uint64_t>(iterator.depth() + 1) >
                request.maximum_depth) {
                throw std::runtime_error("manifest directory depth exceeded");
            }
            const fs::path entry_path = iterator->path();
            platform::PathIdentity identity;
            const auto status =
                platform::inspect_path_no_follow(entry_path, identity);
            if (!status.ok() || identity.reparse_or_link ||
                (identity.kind != platform::PathObjectKind::directory &&
                 identity.kind != platform::PathObjectKind::regular_file)) {
                throw std::runtime_error(
                    "manifest encountered an unstable or unsupported entry");
            }
            const std::string relative =
                entry_path.lexically_relative(path).generic_u8string();
            if (relative.empty() || relative == "." ||
                relative.rfind("../", 0U) == 0U) {
                throw std::runtime_error("manifest relative path escaped");
            }
            if (identity.kind == platform::PathObjectKind::directory) {
                json::ObjectBuilder entry;
                entry.add_string("content_sha256", "");
                entry.add_string(
                    "identity_digest",
                    canonical_digest(path_identity_json(identity).serialize()));
                entry.add_string("kind", "directory");
                entry.add_string("relative_path", relative);
                (void)entry.add_unsigned_integer("size", identity.size);
                entries.emplace_back(relative, entry.serialize());
            } else {
                add_file(entry_path, relative);
            }
            iterator.increment(iterator_error);
        }
        if (iterator_error) {
            throw std::runtime_error(
                "manifest directory enumeration failed: " +
                iterator_error.message());
        }
        const auto stable = root.revalidate();
        if (!stable.ok()) {
            throw std::runtime_error(
                "manifest root changed during enumeration: " +
                stable.code + ": " + stable.detail);
        }
    }
    std::sort(
        entries.begin(), entries.end(),
        [](const auto& left, const auto& right) {
            const std::string left_folded = folded_ascii(left.first);
            const std::string right_folded = folded_ascii(right.first);
            return left_folded == right_folded
                ? left.first < right.first
                : left_folded < right_folded;
        });
    for (std::size_t index = 1; index < entries.size(); ++index) {
        if (folded_ascii(entries[index - 1].first) ==
            folded_ascii(entries[index].first)) {
            throw std::runtime_error(
                "manifest contains a case-insensitive path collision");
        }
    }
    platform::PathIdentity root_after;
    inspected = platform::inspect_path_no_follow(path, root_after);
    if (!inspected.ok() || !root_before.unchanged(root_after)) {
        throw std::runtime_error(
            "manifest root identity changed during capture");
    }
    json::ArrayBuilder entry_array;
    for (const auto& entry : entries) {
        auto parsed = json::parse(entry.second);
        if (!parsed) {
            throw std::runtime_error("manifest entry encoding failed");
        }
        entry_array.add_value(parsed.value());
    }
    json::ObjectBuilder core;
    core.add_object("after_identity", path_identity_json(root_after));
    core.add_object("before_identity", path_identity_json(root_before));
    (void)core.add_unsigned_integer("bytes_hashed", bytes_hashed);
    core.add_bool("complete", true);
    core.add_array("entries", entry_array);
    core.add_bool("identity_stable", true);
    core.add_string("path", platform::path_to_utf8(path));
    core.add_bool("present", root_before.exists);
    return {
        entry_array.serialize(),
        core.serialize(),
        canonical_digest(core.serialize())};
}

std::string directory_manifest_payload(const ProbeRequest& request)
{
    if (request.maximum_entries == 0 ||
        request.maximum_total_bytes == 0 ||
        request.maximum_entry_bytes == 0 ||
        request.maximum_depth == 0) {
        throw std::runtime_error("directory manifest budgets are incomplete");
    }
    const ManifestCapture first =
        capture_manifest_once(request.source, request);
    const ManifestCapture second =
        capture_manifest_once(request.source, request);
    if (first.digest != second.digest ||
        canonical(first.core_json) != canonical(second.core_json)) {
        throw std::runtime_error(
            "directory manifest changed between stability passes");
    }
    auto core = json::parse(first.core_json);
    if (!core) {
        throw std::runtime_error("directory manifest encoding failed");
    }
    json::ObjectBuilder output;
    for (const std::string& key : core.value().object_keys()) {
        output.add_value(key, *core.value().find(key));
    }
    output.add_string("manifest_digest", first.digest);
    (void)output.add_unsigned_integer("stability_passes", 2U);
    return output.serialize();
}

std::string directory_inspection_payload(const fs::path& raw_path)
{
    std::error_code absolute_error;
    const fs::path path =
        fs::absolute(raw_path, absolute_error).lexically_normal();
    if (absolute_error || path.empty()) {
        throw std::runtime_error("directory inspection path is invalid");
    }
    platform::PathIdentity before;
    auto status = platform::inspect_path_no_follow(path, before);
    if (!status.ok() || before.reparse_or_link ||
        (before.exists &&
         before.kind != platform::PathObjectKind::directory)) {
        throw std::runtime_error(
            "directory inspection found an unsafe root object");
    }
    if (before.exists) {
        platform::StableDirectoryObject directory;
        status = directory.open_no_follow(path);
        if (!status.ok() || !directory.revalidate().ok()) {
            throw std::runtime_error(
                "directory inspection could not hold the root object");
        }
    }
    platform::PathIdentity after;
    status = platform::inspect_path_no_follow(path, after);
    if (!status.ok() || !before.unchanged(after)) {
        throw std::runtime_error(
            "directory identity changed during inspection");
    }
    json::ObjectBuilder output;
    output.add_object("after_identity", path_identity_json(after));
    output.add_object("before_identity", path_identity_json(before));
    output.add_string(
        "content_digest",
        canonical_digest(path_identity_json(before).serialize()));
    output.add_bool("identity_stable", true);
    output.add_string("path", platform::path_to_utf8(path));
    output.add_bool("read_complete", true);
    return output.serialize();
}

std::string random_suffix()
{
    std::array<unsigned char, 16> bytes {};
    platform::fill_secure_random(bytes.data(), bytes.size());
    std::ostringstream output;
    output << std::hex << std::setfill('0');
    for (unsigned char byte : bytes) {
        output << std::setw(2) << static_cast<unsigned int>(byte);
    }
    return output.str();
}

void write_all(
    platform::DurableOutputFile& output,
    const std::string& content)
{
    std::uint64_t offset = 0;
    while (offset < content.size()) {
        const std::size_t written = output.write_at(
            offset,
            content.data() + static_cast<std::size_t>(offset),
            content.size() - static_cast<std::size_t>(offset));
        if (written == 0U) {
            throw std::runtime_error("durable output write was incomplete");
        }
        offset += written;
    }
}

std::string write_payload(
    const ProbeRequest& request,
    const std::string& content,
    bool replace)
{
    if (request.maximum_bytes == 0 ||
        content.size() > request.maximum_bytes) {
        throw std::runtime_error("durable output exceeds its byte budget");
    }
    std::error_code absolute_error;
    const fs::path destination =
        fs::absolute(request.destination, absolute_error).lexically_normal();
    if (absolute_error || destination.empty() ||
        destination.parent_path().empty()) {
        throw std::runtime_error("durable output path is invalid");
    }
    platform::StableDirectoryObject parent;
    auto status = parent.open_no_follow(destination.parent_path());
    if (!status.ok() ||
        !parent.validate_descendant(destination, true).ok()) {
        throw std::runtime_error(
            "durable output parent is not one stable no-follow directory");
    }
    platform::PathIdentity destination_before;
    status =
        platform::inspect_path_no_follow(destination, destination_before);
    if (!status.ok() || destination_before.reparse_or_link ||
        (!replace && destination_before.exists) ||
        (replace &&
         (!destination_before.exists ||
          destination_before.kind !=
              platform::PathObjectKind::regular_file))) {
        throw std::runtime_error(
            replace
                ? "durable replacement target is not one existing regular file"
                : "durable new target already exists or is unsafe");
    }
    fs::path staging = destination;
    if (replace) {
        staging = destination.parent_path() /
            (destination.filename().u8string() + ".next-" + random_suffix());
    }
    platform::DurableOutputFile output;
    status = output.create_exclusive(staging, request.maximum_bytes);
    if (!status.ok()) {
        throw std::runtime_error(
            "durable output could not be created exclusively: " +
            status.code + ": " + status.detail);
    }
    try {
        write_all(output, content);
        status = output.flush_file_and_parent();
        if (!status.ok()) {
            throw std::runtime_error(
                "durable output flush failed: " +
                status.code + ": " + status.detail);
        }
        if (replace) {
            platform::PathIdentity destination_current;
            status = platform::inspect_path_no_follow(
                destination, destination_current);
            if (!status.ok() ||
                !destination_before.unchanged(destination_current) ||
                !parent.validate_descendant(destination, false).ok()) {
                throw std::runtime_error(
                    "durable replacement target changed before commit");
            }
            status =
                platform::replace_existing_durable(staging, destination);
            if (!status.ok()) {
                throw std::runtime_error(
                    "durable replacement commit failed: " +
                    status.code + ": " + status.detail);
            }
        }
    } catch (...) {
        output.close_without_flush();
        platform::StableInputFile created;
        if (created.open_no_follow(staging).ok()) {
            (void)platform::remove_exact_object(
                staging, created.identity());
        }
        throw;
    }
    if (!parent.revalidate().ok()) {
        throw std::runtime_error(
            "durable output parent changed during commit");
    }
    StableRead read =
        read_file_stable(destination, request.maximum_bytes, false);
    if (read.sha256 != digest_bytes(content) ||
        read.bytes_read != content.size()) {
        throw std::runtime_error(
            "durable output verification differs from supplied bytes");
    }
    json::ObjectBuilder payload;
    payload.add_object(
        "destination_before", path_identity_json(destination_before));
    payload.add_string(
        "durability",
#ifdef _WIN32
        "best_effort_platform_limit"
#else
        "file_and_directory_flushed"
#endif
    );
    auto observation = json::parse(file_observation_json(read));
    if (!observation) {
        throw std::runtime_error("durable output observation encoding failed");
    }
    payload.add_value("file", observation.value());
    payload.add_string("write_mode", replace ? "replace" : "new");
    return payload.serialize();
}

std::string copy_file_payload(const ProbeRequest& request)
{
    StableRead source =
        read_file_stable(request.source, request.maximum_bytes, true);
    const std::string destination =
        write_payload(request, source.text, false);
    auto destination_value = json::parse(destination);
    if (!destination_value) {
        throw std::runtime_error(
            "durable copy destination evidence is malformed");
    }
    json::ObjectBuilder output;
    output.add_value("destination", destination_value.value());
    output.add_value(
        "source", json::parse(
            file_observation_json(source)).value());
    return output.serialize();
}

std::string archive_request_json(const ProbeRequest& request)
{
    json::ObjectBuilder budgets;
    (void)budgets.add_unsigned_integer(
        "max_depth", request.maximum_depth);
    (void)budgets.add_unsigned_integer(
        "max_elapsed_ms", request.maximum_elapsed_ms);
    (void)budgets.add_unsigned_integer(
        "max_entries", request.maximum_entries);
    (void)budgets.add_unsigned_integer(
        "max_entry_bytes", request.maximum_entry_bytes);
    (void)budgets.add_unsigned_integer(
        "max_ratio", request.maximum_ratio);
    (void)budgets.add_unsigned_integer(
        "max_uncompressed_bytes", request.maximum_total_bytes);
    json::ObjectBuilder value;
    value.add_string("archive_format", "zip");
    value.add_string(
        "archive_path",
        platform::path_to_utf8(
            fs::absolute(request.source).lexically_normal()));
    value.add_object("budgets", budgets);
    value.add_string("schema", "usk.archive_inspect_request.v1");
    return value.serialize();
}

json::Value inspect_zip_value(const ProbeRequest& request)
{
    if (request.maximum_entries == 0 ||
        request.maximum_total_bytes == 0 ||
        request.maximum_entry_bytes == 0 ||
        request.maximum_depth == 0 ||
        request.maximum_ratio == 0 ||
        request.maximum_elapsed_ms == 0) {
        throw std::runtime_error("archive inspection budgets are incomplete");
    }
    const std::string encoded = archive_request_json(request);
    int command_status = 0;
    char* raw = usk_archive_inspect_command_json(
        encoded.data(), encoded.size(), &command_status);
    if (raw == nullptr) {
        throw std::runtime_error(
            "Universal Setup archive inspector returned no result");
    }
    const std::string response(raw);
    usk_archive_inspect_command_free(raw);
    auto parsed = json::parse(
        response,
        {kMaximumJsonBytes, 64U, 1000000U, kMaximumJsonBytes});
    if (!parsed || !parsed.value().is_object()) {
        throw std::runtime_error(
            "Universal Setup archive inspection response is malformed");
    }
    const json::Value* status = parsed.value().find("status");
    const json::Value* payload = parsed.value().find("payload");
    auto status_text = status == nullptr
        ? facman::core::Result<std::string>::failure(
              io_error("archive_status_missing", "", ""))
        : status->string_value();
    if (command_status != 0 || !status_text ||
        status_text.value() != "ok" || payload == nullptr ||
        !payload->is_object()) {
        const json::Value* error = parsed.value().find("error");
        throw std::runtime_error(
            "Universal Setup refused bounded archive inspection: " +
            (error == nullptr ? response : error->serialize()));
    }
    return *payload;
}

std::string string_member(
    const json::Value& object,
    const char* name)
{
    const json::Value* value = object.find(name);
    if (value == nullptr) {
        throw std::runtime_error(
            std::string("missing JSON string member: ") + name);
    }
    auto decoded = value->string_value();
    if (!decoded) {
        throw std::runtime_error(
            std::string("JSON member is not a string: ") + name);
    }
    return decoded.take_value();
}

std::uint64_t integer_member(
    const json::Value& object,
    const char* name)
{
    const json::Value* value = object.find(name);
    if (value == nullptr) {
        throw std::runtime_error(
            std::string("missing JSON integer member: ") + name);
    }
    auto decoded = value->unsigned_integer_value();
    if (!decoded) {
        throw std::runtime_error(
            std::string("JSON member is not an unsigned integer: ") + name);
    }
    return decoded.take_value();
}

std::string inspect_zip_payload(const ProbeRequest& request)
{
    const json::Value inspection = inspect_zip_value(request);
    json::ObjectBuilder output;
    output.add_value("inspection", inspection);
    output.add_string(
        "inspection_digest",
        canonical_digest(inspection.serialize()));
    return output.serialize();
}

bool source_identity_matches(
    const json::Value& inspection,
    const platform::PathIdentity& identity)
{
    const json::Value* source = inspection.find("source");
    const json::Value* filesystem_identity =
        source == nullptr ? nullptr : source->find("filesystem_identity");
    return filesystem_identity != nullptr &&
        filesystem_identity->is_object() &&
        string_member(*filesystem_identity, "volume_id") ==
            hex_id(identity.device) &&
        string_member(*filesystem_identity, "file_id") ==
            hex_id(identity.object) &&
        integer_member(*filesystem_identity, "size_bytes") ==
            identity.size;
}

struct ExactMemberPlan {
    json::Value inspection;
    platform::PathIdentity source_before;
    facman::archive::Limits limits;
    facman::archive::Plan plan;
    std::uint32_t entry_index = 0;
    std::uint64_t expanded_size = 0;
};

bool exact_member_path_is_safe(const std::string& value)
{
    if (value.empty() || value.front() == '/' ||
        value.back() == '/' ||
        value.find('\\') != std::string::npos ||
        value.find(':') != std::string::npos) {
        return false;
    }
    std::size_t begin = 0;
    while (begin < value.size()) {
        const std::size_t end = value.find('/', begin);
        const std::string component = value.substr(
            begin,
            end == std::string::npos
                ? std::string::npos
                : end - begin);
        if (component.empty() || component == "." ||
            component == "..") {
            return false;
        }
        if (end == std::string::npos) {
            break;
        }
        begin = end + 1;
    }
    return true;
}

ExactMemberPlan plan_exact_member(const ProbeRequest& request)
{
    if (!exact_member_path_is_safe(request.member)) {
        throw std::runtime_error("exact archive member is unsafe");
    }
    ExactMemberPlan output;
    output.inspection = inspect_zip_value(request);
    const json::Value* entries = output.inspection.find("entries");
    if (entries == nullptr || !entries->is_array()) {
        throw std::runtime_error("archive inspection has no entry inventory");
    }
    std::size_t exact_count = 0U;
    for (std::size_t index = 0; index < entries->size(); ++index) {
        const json::Value* entry = entries->at(index);
        if (entry != nullptr &&
            string_member(*entry, "normalized_path") == request.member &&
            string_member(*entry, "entry_type") == "file") {
            ++exact_count;
        }
    }
    if (exact_count != 1U) {
        throw std::runtime_error(
            "archive does not contain one exact requested member");
    }

    auto path_status =
        platform::inspect_path_no_follow(
            request.source, output.source_before);
    if (!path_status.ok() || !source_identity_matches(
            output.inspection, output.source_before)) {
        throw std::runtime_error(
            "archive source differs from the Universal Setup inspection");
    }
    output.limits.maximum_archive_bytes = request.maximum_bytes;
    output.limits.maximum_entry_count = request.maximum_entries;
    output.limits.maximum_entry_compressed_bytes =
        request.maximum_entry_bytes;
    output.limits.maximum_entry_expanded_bytes =
        request.maximum_entry_bytes;
    output.limits.maximum_total_expanded_bytes =
        request.maximum_total_bytes;
    output.limits.maximum_compression_ratio = request.maximum_ratio;
    output.limits.maximum_directory_depth =
        static_cast<std::size_t>(request.maximum_depth);
    output.limits.maximum_read_milliseconds =
        request.maximum_elapsed_ms;
    auto archive_status =
        facman::archive::inspect_archive(
            request.source, output.limits, output.plan);
    if (!archive_status.ok()) {
        throw std::runtime_error(
            "FacMan archive reader refused inspected source: " +
            archive_status.code + ": " + archive_status.detail);
    }
    const auto found = std::find_if(
        output.plan.entries.begin(), output.plan.entries.end(),
        [&](const facman::archive::Entry& entry) {
            return !entry.directory && entry.path == request.member;
        });
    if (found == output.plan.entries.end() ||
        std::count_if(
            output.plan.entries.begin(), output.plan.entries.end(),
            [&](const facman::archive::Entry& entry) {
                return !entry.directory && entry.path == request.member;
            }) != 1 ||
        found->expanded_size > request.maximum_entry_bytes) {
        throw std::runtime_error(
            "FacMan archive plan does not contain one bounded exact member");
    }
    const json::Value* source = output.inspection.find("source");
    if (source == nullptr ||
        string_member(*source, "sha256") !=
            read_file_stable(
                request.source, request.maximum_bytes, false).sha256) {
        throw std::runtime_error(
            "archive digest changed between native inspection providers");
    }
    output.entry_index = found->index;
    output.expanded_size = found->expanded_size;
    return output;
}

void revalidate_exact_member_source(
    const ProbeRequest& request,
    const ExactMemberPlan& exact)
{
    platform::PathIdentity source_after;
    const auto path_status =
        platform::inspect_path_no_follow(request.source, source_after);
    if (!path_status.ok() ||
        !exact.source_before.unchanged(source_after) ||
        !source_identity_matches(exact.inspection, source_after)) {
        throw std::runtime_error(
            "archive source changed during exact-member streaming");
    }
}

std::string inspect_member_payload(const ProbeRequest& request)
{
    ExactMemberPlan exact = plan_exact_member(request);
    facman::base::Sha256Hasher member_digest;
    std::uint64_t offset = 0;
    const auto archive_status = facman::archive::stream_entry(
        exact.plan, exact.entry_index, exact.limits,
        [&](const unsigned char* data, std::size_t size) {
            if (size > request.maximum_entry_bytes - offset) {
                return false;
            }
            member_digest.update(data, size);
            offset += size;
            return true;
        });
    if (!archive_status.ok() || offset != exact.expanded_size) {
        throw std::runtime_error(
            "exact archive member inspection failed: " +
            archive_status.code + ": " + archive_status.detail);
    }
    revalidate_exact_member_source(request, exact);
    json::ObjectBuilder member;
    member.add_string("content_sha256", member_digest.finish());
    member.add_string("path", request.member);
    (void)member.add_unsigned_integer("size", offset);
    json::ObjectBuilder payload;
    payload.add_value("archive_inspection", exact.inspection);
    payload.add_string(
        "archive_inspection_digest",
        canonical_digest(exact.inspection.serialize()));
    payload.add_object("member", member);
    return payload.serialize();
}

std::string extract_member_payload(const ProbeRequest& request)
{
    ExactMemberPlan exact = plan_exact_member(request);
    std::error_code absolute_error;
    const fs::path destination =
        fs::absolute(request.destination, absolute_error).lexically_normal();
    if (absolute_error || destination.parent_path().empty()) {
        throw std::runtime_error("exact member destination is invalid");
    }
    platform::StableDirectoryObject parent;
    auto io_status = parent.open_no_follow(destination.parent_path());
    if (!io_status.ok() ||
        !parent.validate_descendant(destination, true).ok()) {
        throw std::runtime_error(
            "exact member destination parent is unstable");
    }
    platform::DurableOutputFile output;
    io_status =
        output.create_exclusive(destination, exact.expanded_size);
    if (!io_status.ok()) {
        throw std::runtime_error(
            "exact member destination could not be created exclusively");
    }
    facman::base::Sha256Hasher member_digest;
    std::uint64_t offset = 0;
    auto archive_status = facman::archive::stream_entry(
        exact.plan, exact.entry_index, exact.limits,
        [&](const unsigned char* data, std::size_t size) {
            const std::size_t written =
                output.write_at(offset, data, size);
            if (written != size) {
                return false;
            }
            member_digest.update(data, size);
            offset += written;
            return offset <= request.maximum_entry_bytes;
        });
    if (!archive_status.ok() || offset != exact.expanded_size) {
        output.close_without_flush();
        platform::StableInputFile partial;
        if (partial.open_no_follow(destination).ok()) {
            (void)platform::remove_exact_object(
                destination, partial.identity());
        }
        throw std::runtime_error(
            "exact archive member extraction failed: " +
            archive_status.code + ": " + archive_status.detail);
    }
    io_status = output.flush_file_and_parent();
    if (!io_status.ok() || !parent.revalidate().ok()) {
        throw std::runtime_error(
            "exact member durable output could not be finalized");
    }
    const std::string extracted_digest = member_digest.finish();
    StableRead extracted =
        read_file_stable(destination, request.maximum_entry_bytes, false);
    revalidate_exact_member_source(request, exact);
    if (extracted.sha256 != extracted_digest) {
        throw std::runtime_error(
            "archive source or extracted member changed during extraction");
    }
    json::ObjectBuilder member;
    member.add_string("content_sha256", extracted_digest);
    member.add_string("path", request.member);
    (void)member.add_unsigned_integer("size", offset);
    json::ObjectBuilder payload;
    payload.add_value("archive_inspection", exact.inspection);
    payload.add_string(
        "archive_inspection_digest",
        canonical_digest(exact.inspection.serialize()));
    payload.add_object("member", member);
    auto output_observation =
        json::parse(file_observation_json(extracted));
    if (!output_observation) {
        throw std::runtime_error(
            "exact member output observation encoding failed");
    }
    payload.add_value("output", output_observation.value());
    return payload.serialize();
}

std::string canonical_without(
    const json::Value& object,
    const std::string& omitted)
{
    json::ObjectBuilder output;
    for (const std::string& key : object.object_keys()) {
        if (key != omitted) {
            output.add_value(key, *object.find(key));
        }
    }
    return canonical(output.serialize());
}

facman::core::Result<void> resource_error(
    const std::string& message,
    const std::string& path)
{
    return facman::core::Result<void>::failure(io_error(
        "permit_resource_stale",
        message,
        path,
        facman::core::OutcomeKind::refused));
}

bool identity_matches_json(
    const json::Value& expected,
    const platform::PathIdentity& current)
{
    const json::Value* present = expected.find("present");
    const json::Value* kind = expected.find("kind");
    const json::Value* reparse = expected.find("reparse_or_link");
    if (present == nullptr || kind == nullptr || reparse == nullptr) {
        return false;
    }
    auto expected_present = present->bool_value();
    auto expected_kind = kind->string_value();
    auto expected_reparse = reparse->bool_value();
    if (!expected_present || !expected_kind || !expected_reparse ||
        expected_present.value() != current.exists ||
        expected_kind.value() != path_kind_name(current.kind) ||
        expected_reparse.value() != current.reparse_or_link) {
        return false;
    }
    if (!current.exists) {
        return true;
    }
    return string_member(expected, "volume_id") == hex_id(current.device) &&
        string_member(expected, "object_id") == hex_id(current.object);
}

} // namespace

facman::core::Result<std::string> execute_probe_request(
    const ProbeRequest& request,
    const std::string& standard_input)
{
    try {
        std::string payload;
        if (request.operation == "inspect_file" ||
            request.operation == "hash_file") {
            payload = inspect_file_payload(
                request.source, request.maximum_bytes, false);
        } else if (request.operation == "read_bounded_json") {
            payload = inspect_file_payload(
                request.source, request.maximum_bytes, true);
        } else if (request.operation == "read_bounded_text") {
            payload = read_text_payload(
                request.source, request.maximum_bytes);
        } else if (request.operation == "inspect_directory") {
            payload = directory_inspection_payload(request.source);
        } else if (
            request.operation == "capture_directory_manifest") {
            payload = directory_manifest_payload(request);
        } else if (request.operation == "write_new_durable") {
            payload = write_payload(
                request, standard_input, false);
        } else if (request.operation == "replace_durable") {
            payload = write_payload(
                request, standard_input, true);
        } else if (request.operation == "copy_file_durable") {
            payload = copy_file_payload(request);
        } else if (
            request.operation == "revalidate_resource_specification") {
            const auto revalidated = revalidate_resource_specification(
                request.source,
                request.member,
                standard_input);
            if (!revalidated) {
                return facman::core::Result<std::string>::failure(
                    revalidated.error());
            }
            json::ObjectBuilder output;
            output.add_string(
                "preflight_digest", request.member);
            output.add_string(
                "resource_set_digest", standard_input);
            output.add_bool("valid", true);
            payload = output.serialize();
        } else if (request.operation == "inspect_zip") {
            payload = inspect_zip_payload(request);
        } else if (request.operation == "inspect_exact_member") {
            payload = inspect_member_payload(request);
        } else if (request.operation == "extract_exact_member") {
            payload = extract_member_payload(request);
        } else {
            return facman::core::Result<std::string>::failure(io_error(
                "evidence_io_operation_unsupported",
                "native evidence I/O operation is unsupported",
                request.operation,
                facman::core::OutcomeKind::invalid_argument));
        }
        return facman::core::Result<std::string>::success(
            close_success_record(request.operation, payload));
    } catch (const std::exception& exception) {
        return facman::core::Result<std::string>::failure(io_error(
            "evidence_io_refused",
            exception.what(),
            request.source.empty()
                ? platform::path_to_utf8(request.destination)
                : platform::path_to_utf8(request.source),
            facman::core::OutcomeKind::refused));
    }
}

std::string error_record_json(
    const std::string& operation,
    const facman::core::Error& error)
{
    json::ObjectBuilder error_value;
    error_value.add_string("code", error.code);
    error_value.add_string("message", error.message);
    error_value.add_string("path", error.path);
    json::ObjectBuilder core;
    core.add_object("error", error_value);
    core.add_string("operation", operation);
    core.add_string("schema", kResultSchema);
    core.add_string("status", "refused");
    const std::string core_text = core.serialize();
    json::ObjectBuilder output;
    output.add_object("error", error_value);
    output.add_string("operation", operation);
    output.add_string("record_digest", canonical_digest(core_text));
    output.add_string("schema", kResultSchema);
    output.add_string("status", "refused");
    return output.serialize();
}

facman::core::Result<void> revalidate_resource_specification(
    const fs::path& preflight_path,
    const std::string& expected_preflight_digest,
    const std::string& expected_resource_set_digest)
{
    try {
        StableRead read =
            read_file_stable(preflight_path, 64ULL * 1024ULL * 1024ULL, true);
        auto preflight = json::parse(
            read.text,
            {64U * 1024U * 1024U, 128U, 1000000U, 64U * 1024U * 1024U});
        if (!preflight || !preflight.value().is_object() ||
            string_member(preflight.value(), "preflight_digest") !=
                expected_preflight_digest ||
            digest_bytes(canonical_without(
                preflight.value(), "preflight_digest")) !=
                expected_preflight_digest) {
            return resource_error(
                "ready preflight digest changed before process creation",
                platform::path_to_utf8(preflight_path));
        }
        const json::Value* specification =
            preflight.value().find("resource_specification");
        if (specification == nullptr || !specification->is_object() ||
            string_member(*specification, "resource_set_digest") !=
                expected_resource_set_digest ||
            canonical_digest(canonical_without(
                *specification, "resource_set_digest")) !=
                expected_resource_set_digest) {
            return resource_error(
                "preflight resource-set digest changed before process creation",
                "$preflight.resource_specification");
        }
        for (const char* group_name :
             {"protected_resources", "writable_resources"}) {
            const json::Value* resources = specification->find(group_name);
            if (resources == nullptr || !resources->is_array()) {
                return resource_error(
                    "preflight resource specification is incomplete",
                    std::string("$preflight.resource_specification.") +
                        group_name);
            }
            for (std::size_t index = 0; index < resources->size(); ++index) {
                const json::Value* resource = resources->at(index);
                if (resource == nullptr || !resource->is_object()) {
                    return resource_error(
                        "preflight resource record is malformed",
                        std::string("$preflight.resource_specification.") +
                            group_name);
                }
                const std::string kind =
                    string_member(*resource, "kind");
                if (kind != "filesystem") {
                    if (std::string(group_name) ==
                            "writable_resources" ||
                        kind != "registry") {
                        return resource_error(
                            "preflight resource kind is unsupported",
                            std::string(
                                "$preflight.resource_specification.") +
                                group_name);
                    }
                    continue;
                }
                const json::Value* members =
                    resource->find("members");
                if (members == nullptr || !members->is_array()) {
                    return resource_error(
                        "preflight filesystem resource is malformed",
                        std::string("$preflight.resource_specification.") +
                            group_name);
                }
                for (std::size_t member_index = 0;
                     member_index < members->size();
                     ++member_index) {
                    const json::Value* member = members->at(member_index);
                    const json::Value* expected = member == nullptr
                        ? nullptr
                        : member->find("root_identity");
                    if (member == nullptr || expected == nullptr ||
                        !expected->is_object()) {
                        return resource_error(
                            "preflight filesystem root identity is missing",
                            std::string("$preflight.resource_specification.") +
                                group_name);
                    }
                    const fs::path path = platform::path_from_utf8(
                        string_member(*member, "path"));
                    platform::PathIdentity current;
                    const auto status =
                        platform::inspect_path_no_follow(path, current);
                    if (!status.ok() ||
                        !identity_matches_json(*expected, current)) {
                        return resource_error(
                            "preflight filesystem root object drifted before process creation",
                            platform::path_to_utf8(path));
                    }
                }
            }
        }
        return facman::core::Result<void>::success();
    } catch (const std::exception& exception) {
        return resource_error(
            exception.what(), platform::path_to_utf8(preflight_path));
    }
}

facman::core::Result<void> resource_revalidation_self_test(
    const fs::path& root)
{
    try {
        const fs::path resource = root / "resource-root";
        std::error_code error;
        fs::create_directory(resource, error);
        if (error) {
            return resource_error(
                "self-test resource root could not be created",
                platform::path_to_utf8(resource));
        }
        platform::PathIdentity identity;
        const auto inspected =
            platform::inspect_path_no_follow(resource, identity);
        if (!inspected.ok() || !identity.exists) {
            return resource_error(
                "self-test resource root could not be inspected",
                platform::path_to_utf8(resource));
        }
        json::ObjectBuilder member;
        member.add_string("path", platform::path_to_utf8(resource));
        member.add_object("root_identity", path_identity_json(identity));
        json::ArrayBuilder members;
        members.add_object(member);
        json::ObjectBuilder resource_value;
        resource_value.add_string("kind", "filesystem");
        resource_value.add_array("members", members);
        resource_value.add_string("resource_id", "self-test.protected");
        resource_value.add_string("source", "native_self_test");
        json::ArrayBuilder protected_resources;
        protected_resources.add_object(resource_value);
        json::ArrayBuilder writable_resources;
        json::ObjectBuilder specification_core;
        specification_core.add_array(
            "protected_resources", protected_resources);
        specification_core.add_string(
            "schema",
            "facman.play_evidence_resource_specification.v1");
        json::ObjectBuilder environment;
        environment.add_string(
            "provider", "facman.process_start_environment.v1");
        environment.add_string(
            "snapshot_digest", std::string(64U, '0'));
        json::ObjectBuilder values;
        environment.add_object("values", values);
        specification_core.add_object(
            "startup_environment", environment);
        specification_core.add_array(
            "writable_resources", writable_resources);
        const std::string resource_digest =
            canonical_digest(specification_core.serialize());
        auto parsed_specification =
            json::parse(specification_core.serialize());
        if (!parsed_specification) {
            return resource_error(
                "self-test resource specification could not be parsed",
                "$self-test.resource_specification");
        }
        json::ObjectBuilder specification;
        for (const std::string& key :
             parsed_specification.value().object_keys()) {
            specification.add_value(
                key, *parsed_specification.value().find(key));
        }
        specification.add_string(
            "resource_set_digest", resource_digest);
        json::ObjectBuilder preflight_core;
        preflight_core.add_object(
            "resource_specification", specification);
        preflight_core.add_string(
            "schema", "facman.play_evidence_preflight_self_test.v1");
        const std::string preflight_digest =
            canonical_digest(preflight_core.serialize());
        auto parsed_preflight = json::parse(preflight_core.serialize());
        if (!parsed_preflight) {
            return resource_error(
                "self-test preflight could not be parsed",
                "$self-test.preflight");
        }
        json::ObjectBuilder preflight;
        for (const std::string& key :
             parsed_preflight.value().object_keys()) {
            preflight.add_value(
                key, *parsed_preflight.value().find(key));
        }
        preflight.add_string(
            "preflight_digest", preflight_digest);
        ProbeRequest write;
        write.operation = "write_new_durable";
        write.destination = root / "resource-preflight.json";
        write.maximum_bytes = 1024U * 1024U;
        const auto written = execute_probe_request(
            write, preflight.serialize() + "\n");
        if (!written) {
            return facman::core::Result<void>::failure(
                written.error());
        }
        const auto accepted = revalidate_resource_specification(
            write.destination, preflight_digest, resource_digest);
        if (!accepted) {
            return accepted;
        }
        if (!fs::remove(resource, error) || error) {
            return resource_error(
                "self-test resource root could not be replaced",
                platform::path_to_utf8(resource));
        }
        fs::create_directory(resource, error);
        if (error) {
            return resource_error(
                "self-test replacement root could not be created",
                platform::path_to_utf8(resource));
        }
        const auto rejected = revalidate_resource_specification(
            write.destination, preflight_digest, resource_digest);
        if (rejected) {
            return resource_error(
                "resource root replacement was not refused",
                platform::path_to_utf8(resource));
        }
        return facman::core::Result<void>::success();
    } catch (const std::exception& exception) {
        return resource_error(
            exception.what(), platform::path_to_utf8(root));
    }
}

} // namespace facman::play_evidence
