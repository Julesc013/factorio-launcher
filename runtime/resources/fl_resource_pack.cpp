// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_resource_pack.h"

#include "fl_archive.h"
#include "fl_json.h"
#include "fl_sha256.h"

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <map>
#include <set>
#include <system_error>

namespace facman::resources {
namespace {

constexpr const char* kManifestPath = "manifest/resource-pack.v1.json";
constexpr const char* kSchema = "facman.runtime_resource_pack.v1";

facman::core::Error error(
    std::string code,
    std::string message,
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::invalid_argument)
{
    return {std::move(code), std::move(message), "$", kind};
}

facman::archive::Limits resource_limits()
{
    facman::archive::Limits limits;
    limits.maximum_archive_bytes = 512ULL * 1024ULL * 1024ULL;
    limits.maximum_entry_count = 20001;
    limits.maximum_entry_compressed_bytes = 32ULL * 1024ULL * 1024ULL;
    limits.maximum_entry_expanded_bytes = 32ULL * 1024ULL * 1024ULL;
    limits.maximum_total_expanded_bytes = 512ULL * 1024ULL * 1024ULL;
    limits.maximum_compression_ratio = 1000;
    limits.maximum_path_bytes = 1024;
    limits.maximum_directory_depth = 64;
    limits.maximum_read_milliseconds = 30000;
    return limits;
}

facman::core::Result<std::string> entry_text(
    const facman::archive::Plan& plan,
    const facman::archive::Entry& entry,
    const facman::archive::Limits& limits)
{
    std::string output;
    output.reserve(static_cast<std::size_t>(entry.expanded_size));
    const auto status = facman::archive::stream_entry(
        plan, entry.index, limits,
        [&output](const unsigned char* data, std::size_t size) {
            output.append(reinterpret_cast<const char*>(data), size);
            return true;
        });
    if (!status.ok()) {
        return facman::core::Result<std::string>::failure(
            error(status.code, status.detail, facman::core::OutcomeKind::internal_error));
    }
    return facman::core::Result<std::string>::success(std::move(output));
}

facman::core::Result<std::string> required_string(
    const facman::core::json::Value& object,
    const char* key)
{
    const auto* value = object.find(key);
    if (value == nullptr) {
        return facman::core::Result<std::string>::failure(
            error("resource_manifest_invalid", std::string("Missing manifest field: ") + key));
    }
    auto result = value->string_value();
    if (!result) {
        return facman::core::Result<std::string>::failure(
            error("resource_manifest_invalid", std::string("Manifest field is not a string: ") + key));
    }
    return result;
}

facman::core::Result<std::uint64_t> required_unsigned(
    const facman::core::json::Value& object,
    const char* key)
{
    const auto* value = object.find(key);
    if (value == nullptr) {
        return facman::core::Result<std::uint64_t>::failure(
            error("resource_manifest_invalid", std::string("Missing manifest field: ") + key));
    }
    auto result = value->unsigned_integer_value();
    if (!result) {
        return facman::core::Result<std::uint64_t>::failure(
            error("resource_manifest_invalid", std::string("Manifest field is not an unsigned integer: ") + key));
    }
    return result;
}

std::string ascii_lower(std::string value)
{
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char character) {
        return static_cast<char>(std::tolower(character));
    });
    return value;
}

bool forbidden_executable(const std::string& path)
{
    static const std::set<std::string> suffixes = {
        ".bat", ".cmd", ".com", ".dll", ".dylib", ".exe", ".msi", ".ps1", ".sh", ".so"};
    const auto slash = path.find_last_of('/');
    const auto dot = path.find_last_of('.');
    return dot != std::string::npos && (slash == std::string::npos || dot > slash) &&
        suffixes.count(ascii_lower(path.substr(dot))) != 0;
}

} // namespace

facman::core::Result<std::filesystem::path> locate_pack(
    const std::filesystem::path& executable_path)
{
    std::vector<std::filesystem::path> candidates;
    if (const char* configured = std::getenv("FACMAN_RESOURCE_PACK")) {
        if (*configured != '\0') candidates.emplace_back(std::filesystem::u8path(configured));
    }
    std::error_code path_error;
    const auto executable = std::filesystem::absolute(executable_path, path_error);
    const auto directory = (path_error ? executable_path : executable).parent_path();
    candidates.push_back(directory / "facman.resources");
    candidates.push_back(directory.parent_path() / "facman.resources");
    candidates.push_back(directory.parent_path() / "Resources" / "facman.resources");
    for (const auto& candidate : candidates) {
        std::error_code file_error;
        if (std::filesystem::is_regular_file(candidate, file_error) && !file_error) {
            return facman::core::Result<std::filesystem::path>::success(
                std::filesystem::absolute(candidate, file_error).lexically_normal());
        }
    }
    return facman::core::Result<std::filesystem::path>::failure(error(
        "resource_pack_not_found",
        "facman.resources was not found beside the executable; set FACMAN_RESOURCE_PACK to inspect an explicit pack",
        facman::core::OutcomeKind::not_found));
}

facman::core::Result<Inspection> inspect_pack(const std::filesystem::path& pack_path)
{
    const auto limits = resource_limits();
    facman::archive::Plan plan;
    auto status = facman::archive::inspect_archive(pack_path, limits, plan);
    if (!status.ok()) {
        return facman::core::Result<Inspection>::failure(
            error(status.code, status.detail, facman::core::OutcomeKind::invalid_argument));
    }
    status = facman::archive::verify_all(plan, limits);
    if (!status.ok()) {
        return facman::core::Result<Inspection>::failure(
            error(status.code, status.detail, facman::core::OutcomeKind::invalid_argument));
    }

    const facman::archive::Entry* manifest_entry = nullptr;
    std::map<std::string, const facman::archive::Entry*> actual;
    std::set<std::string> folded;
    for (const auto& entry : plan.entries) {
        if (entry.directory || forbidden_executable(entry.path)) {
            return facman::core::Result<Inspection>::failure(error(
                "resource_pack_forbidden_entry", "Forbidden resource-pack entry: " + entry.path));
        }
        if (!folded.insert(ascii_lower(entry.path)).second) {
            return facman::core::Result<Inspection>::failure(error(
                "resource_pack_path_collision", "Case-insensitive resource-pack collision: " + entry.path));
        }
        if (entry.path == kManifestPath) manifest_entry = &entry;
        else actual.emplace(entry.path, &entry);
    }
    if (manifest_entry == nullptr) {
        return facman::core::Result<Inspection>::failure(
            error("resource_manifest_missing", std::string("Missing ") + kManifestPath));
    }
    auto manifest_text = entry_text(plan, *manifest_entry, limits);
    if (!manifest_text) return facman::core::Result<Inspection>::failure(manifest_text.error());
    auto parsed = facman::core::json::parse(manifest_text.value());
    if (!parsed || !parsed.value().is_object()) {
        return facman::core::Result<Inspection>::failure(
            error("resource_manifest_invalid", "Resource-pack manifest is not a valid JSON object"));
    }
    auto schema = required_string(parsed.value(), "schema");
    auto version = required_string(parsed.value(), "version");
    auto declared_digest = required_string(parsed.value(), "content_sha256");
    auto declared_count = required_unsigned(parsed.value(), "entry_count");
    auto declared_bytes = required_unsigned(parsed.value(), "expanded_bytes");
    if (!schema) return facman::core::Result<Inspection>::failure(schema.error());
    if (!version) return facman::core::Result<Inspection>::failure(version.error());
    if (!declared_digest) return facman::core::Result<Inspection>::failure(declared_digest.error());
    if (!declared_count) return facman::core::Result<Inspection>::failure(declared_count.error());
    if (!declared_bytes) return facman::core::Result<Inspection>::failure(declared_bytes.error());
    if (schema.value() != kSchema) {
        return facman::core::Result<Inspection>::failure(
            error("resource_manifest_schema_mismatch", "Unsupported resource-pack schema: " + schema.value()));
    }
    const auto* entries = parsed.value().find("entries");
    if (entries == nullptr || !entries->is_array() || entries->size() != actual.size() ||
        declared_count.value() != actual.size()) {
        return facman::core::Result<Inspection>::failure(
            error("resource_manifest_inventory_mismatch", "Manifest entry count does not match the archive"));
    }

    facman::base::Sha256Hasher content_hasher;
    std::uint64_t expanded_bytes = 0;
    std::set<std::string> declared_paths;
    Inspection inspection;
    inspection.path = std::filesystem::absolute(pack_path).lexically_normal();
    inspection.version = version.value();
    for (std::size_t index = 0; index < entries->size(); ++index) {
        const auto* item = entries->at(index);
        if (item == nullptr || !item->is_object()) {
            return facman::core::Result<Inspection>::failure(
                error("resource_manifest_invalid", "Manifest entry is not an object"));
        }
        auto path = required_string(*item, "path");
        auto bytes = required_unsigned(*item, "bytes");
        auto digest = required_string(*item, "sha256");
        if (!path) return facman::core::Result<Inspection>::failure(path.error());
        if (!bytes) return facman::core::Result<Inspection>::failure(bytes.error());
        if (!digest) return facman::core::Result<Inspection>::failure(digest.error());
        const auto found = actual.find(path.value());
        if (found == actual.end() || !declared_paths.insert(path.value()).second ||
            found->second->expanded_size != bytes.value()) {
            return facman::core::Result<Inspection>::failure(error(
                "resource_manifest_inventory_mismatch", "Manifest entry does not match archive: " + path.value()));
        }
        facman::base::Sha256Hasher entry_hasher;
        status = facman::archive::stream_entry(
            plan, found->second->index, limits,
            [&entry_hasher](const unsigned char* data, std::size_t size) {
                entry_hasher.update(data, size);
                return true;
            });
        if (!status.ok() || entry_hasher.finish() != digest.value()) {
            return facman::core::Result<Inspection>::failure(error(
                "resource_entry_digest_mismatch", "Resource entry digest mismatch: " + path.value()));
        }
        const std::string line = path.value() + '\0' + std::to_string(bytes.value()) + '\0' +
            digest.value() + "\n";
        content_hasher.update(reinterpret_cast<const unsigned char*>(line.data()), line.size());
        expanded_bytes += bytes.value();
        inspection.entries.push_back(path.value());
    }
    inspection.content_sha256 = content_hasher.finish();
    inspection.expanded_bytes = expanded_bytes;
    if (inspection.content_sha256 != declared_digest.value() ||
        expanded_bytes != declared_bytes.value()) {
        return facman::core::Result<Inspection>::failure(
            error("resource_content_digest_mismatch", "Resource-pack aggregate digest or byte count does not match"));
    }
    return facman::core::Result<Inspection>::success(std::move(inspection));
}

facman::core::Result<void> export_pack(
    const std::filesystem::path& pack_path,
    const std::filesystem::path& destination)
{
    auto inspected = inspect_pack(pack_path);
    if (!inspected) return facman::core::Result<void>::failure(inspected.error());
    std::error_code filesystem_error;
    if (std::filesystem::exists(destination, filesystem_error) || filesystem_error) {
        return facman::core::Result<void>::failure(error(
            "resource_export_destination_exists", "Resource export destination must not exist"));
    }
    facman::archive::Plan plan;
    const auto limits = resource_limits();
    auto status = facman::archive::inspect_archive(pack_path, limits, plan);
    if (status.ok()) status = facman::archive::extract_to_new_owned_staging(plan, destination, limits);
    if (!status.ok()) {
        return facman::core::Result<void>::failure(
            error(status.code, status.detail, facman::core::OutcomeKind::internal_error));
    }
    std::filesystem::remove(destination / facman::archive::owned_staging_marker_name(), filesystem_error);
    return facman::core::Result<void>::success();
}

std::string inspection_json(const Inspection& inspection)
{
    facman::core::json::ObjectBuilder output;
    output.add_string("schema", "facman.runtime_resource_pack_inventory.v1");
    output.add_string("status", "pass");
    output.add_string("path", inspection.path.u8string());
    output.add_string("version", inspection.version);
    output.add_string("content_sha256", inspection.content_sha256);
    output.add_unsigned_integer("expanded_bytes", inspection.expanded_bytes);
    output.add_unsigned_integer("entry_count", inspection.entries.size());
    facman::core::json::ArrayBuilder entries;
    for (const auto& entry : inspection.entries) entries.add_string(entry);
    output.add_array("entries", entries);
    return output.serialize();
}

facman::core::Result<std::string> locate_pack_utf8(const std::string& executable_path)
{
    auto located = locate_pack(std::filesystem::u8path(executable_path));
    if (!located) return facman::core::Result<std::string>::failure(located.error());
    return facman::core::Result<std::string>::success(located.value().u8string());
}

facman::core::Result<Inspection> inspect_pack_utf8(const std::string& pack_path)
{
    return inspect_pack(std::filesystem::u8path(pack_path));
}

facman::core::Result<void> export_pack_utf8(
    const std::string& pack_path,
    const std::string& destination)
{
    return export_pack(
        std::filesystem::u8path(pack_path), std::filesystem::u8path(destination));
}

std::string absolute_path_utf8(const std::string& path)
{
    std::error_code path_error;
    const auto absolute = std::filesystem::absolute(
        std::filesystem::u8path(path), path_error);
    return (path_error ? std::filesystem::u8path(path) : absolute).lexically_normal().u8string();
}

} // namespace facman::resources
