// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_runtime_verify.h"

#include "fl_runtime_component.h"
#include "fl_runtime_locator.h"
#include "fl_json.h"
#include "fl_sha256.h"

#include <algorithm>
#include <array>
#include <cctype>
#include <cstring>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <map>
#include <set>
#include <sstream>
#include <string>
#include <vector>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#endif

namespace fs = std::filesystem;

namespace {

fs::path g_package_root;
fs::path g_executable_path;
std::string g_package_root_text;

namespace json = facman::core::json;

constexpr std::size_t kMaximumManifestBytes = 16U * 1024U * 1024U;
constexpr std::size_t kMaximumPackageEntries = 100000U;
constexpr const char* kStageManifestRelative = "manifest/stage.v1.json";
constexpr const char* kResolutionSetRelative =
    "manifest/resolution/release-resolution-set.v1.json";
constexpr const char* kRuntimeMetadataRelative =
    "manifest/resolution/runtime-release-metadata.v1.json";
constexpr const char* kTechnicalPreviewTarget =
    "windows_winforms_technical_preview_x64";
constexpr const char* kTechnicalPreviewArtifact =
    "windows_winforms_technical_preview_zip";

void set_detail(char* detail, size_t capacity, const std::string& value)
{
    if (detail == nullptr || capacity == 0) {
        return;
    }
    const size_t count = std::min(capacity - 1, value.size());
    std::memcpy(detail, value.data(), count);
    detail[count] = '\0';
}

bool read_bounded_text(const fs::path& path, std::string& text, std::string& error)
{
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        error = "cannot open " + path.filename().string();
        return false;
    }
    input.seekg(0, std::ios::end);
    const std::streamoff length = input.tellg();
    if (length < 0 || static_cast<std::uintmax_t>(length) > kMaximumManifestBytes) {
        error = "manifest exceeds its byte budget: " + path.filename().string();
        return false;
    }
    input.seekg(0, std::ios::beg);
    text.assign(
        std::istreambuf_iterator<char>(input),
        std::istreambuf_iterator<char>());
    if (!input.eof() && input.fail()) {
        error = "cannot read " + path.filename().string();
        return false;
    }
    return true;
}

bool load_json_document(
    const fs::path& path,
    json::Value& document,
    std::string& source,
    std::string& error)
{
    if (!read_bounded_text(path, source, error)) return false;
    json::Limits limits;
    limits.maximum_bytes = kMaximumManifestBytes;
    limits.maximum_depth = 32U;
    limits.maximum_nodes = 1000000U;
    limits.maximum_string_bytes = kMaximumManifestBytes;
    auto parsed = json::parse(source, limits);
    if (!parsed || !parsed.value().is_object()) {
        error = "invalid JSON object: " + path.filename().string();
        return false;
    }
    document = parsed.take_value();
    return true;
}

bool exact_members(
    const json::Value& value,
    const std::set<std::string>& expected,
    const std::string& label,
    std::string& error)
{
    if (!value.is_object()) {
        error = label + " must be an object";
        return false;
    }
    const std::vector<std::string> keys = value.object_keys();
    const std::set<std::string> actual(keys.begin(), keys.end());
    if (actual != expected) {
        error = label + " has missing or unknown members";
        return false;
    }
    return true;
}

bool required_text(
    const json::Value& object,
    const char* key,
    std::string& output,
    const std::string& label,
    std::string& error,
    bool allow_empty = false)
{
    const json::Value* field = object.find(key);
    auto value = field == nullptr
        ? facman::core::Result<std::string>::failure(
              {"package_manifest_invalid", "field is missing", key})
        : field->string_value();
    if (!value || (!allow_empty && value.value().empty())) {
        error = label + " member '" + key + "' must be a string";
        return false;
    }
    output = value.take_value();
    return true;
}

bool required_fixed_text(
    const json::Value& object,
    const char* key,
    const char* expected,
    const std::string& label,
    std::string& error)
{
    std::string actual;
    if (!required_text(object, key, actual, label, error)) return false;
    if (actual != expected) {
        error = label + " member '" + key + "' does not match the target";
        return false;
    }
    return true;
}

bool required_boolean(
    const json::Value& object,
    const char* key,
    bool& output,
    const std::string& label,
    std::string& error)
{
    const json::Value* field = object.find(key);
    auto value = field == nullptr
        ? facman::core::Result<bool>::failure(
              {"package_manifest_invalid", "field is missing", key})
        : field->bool_value();
    if (!value) {
        error = label + " member '" + key + "' must be Boolean";
        return false;
    }
    output = value.value();
    return true;
}

bool required_unsigned(
    const json::Value& object,
    const char* key,
    std::uint64_t& output,
    const std::string& label,
    std::string& error)
{
    const json::Value* field = object.find(key);
    auto value = field == nullptr
        ? facman::core::Result<std::uint64_t>::failure(
              {"package_manifest_invalid", "field is missing", key})
        : field->unsigned_integer_value();
    if (!value) {
        error = label + " member '" + key + "' must be a nonnegative integer";
        return false;
    }
    output = value.value();
    return true;
}

bool is_hex_value(const std::string& value, std::size_t size)
{
    return value.size() == size && std::all_of(value.begin(), value.end(), [](unsigned char ch) {
        return std::isxdigit(ch) != 0;
    });
}

bool is_hex_digest(const std::string& value)
{
    return is_hex_value(value, 64);
}

bool is_hex_revision(const std::string& value)
{
    return is_hex_value(value, 40);
}

bool is_safe_relative(const std::string& value)
{
    if (value.empty() || value.find('\\') != std::string::npos || value.find(':') != std::string::npos) {
        return false;
    }
    fs::path path = fs::u8path(value);
    if (path.is_absolute()) {
        return false;
    }
    for (const fs::path& part : path) {
        if (part == "." || part == ".." || part.empty()) {
            return false;
        }
    }
    return true;
}

bool is_reparse_or_symlink(const fs::path& path)
{
    std::error_code error;
    if (fs::is_symlink(fs::symlink_status(path, error))) {
        return true;
    }
#ifdef _WIN32
    DWORD attributes = GetFileAttributesW(path.c_str());
    return attributes != INVALID_FILE_ATTRIBUTES && (attributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0;
#else
    return false;
#endif
}

bool is_within(const fs::path& root, const fs::path& candidate)
{
    std::error_code error;
    fs::path relative = fs::relative(candidate, root, error);
    if (error || relative.empty() || relative.is_absolute()) {
        return false;
    }
    for (const fs::path& part : relative) {
        if (part == "..") {
            return false;
        }
    }
    return true;
}

bool collect_package_files(
    const fs::path& root,
    const std::string& excluded_manifest,
    std::set<std::string>& files,
    std::string& error)
{
    std::error_code walk_error;
    for (fs::recursive_directory_iterator iterator(root, walk_error), end; iterator != end; iterator.increment(walk_error)) {
        if (walk_error) {
            error = "cannot enumerate package root: " + walk_error.message();
            return false;
        }
        const fs::path path = iterator->path();
        if (is_reparse_or_symlink(path)) {
            error = "package contains a link or reparse point: " + path.filename().string();
            return false;
        }
        if (!iterator->is_regular_file()) {
            continue;
        }
        std::string relative = path.lexically_relative(root).generic_string();
        if (relative == excluded_manifest || path.extension() == ".sig") {
            continue;
        }
        files.insert(relative);
    }
    if (walk_error) {
        error = "cannot enumerate package root: " + walk_error.message();
        return false;
    }
    return true;
}

std::string trim(std::string value)
{
    while (!value.empty() && std::isspace(static_cast<unsigned char>(value.front()))) value.erase(value.begin());
    while (!value.empty() && std::isspace(static_cast<unsigned char>(value.back()))) value.pop_back();
    return value;
}

bool parse_flat_manifest(
    const fs::path& path,
    const std::set<std::string>& allowed,
    std::map<std::string, std::string>& values,
    std::string& error)
{
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        error = "cannot open " + path.filename().string();
        return false;
    }
    std::string line;
    std::size_t line_number = 0;
    while (std::getline(input, line)) {
        ++line_number;
        if (!line.empty() && line.back() == '\r') line.pop_back();
        line = trim(line);
        if (line.empty()) continue;
        std::size_t equals = line.find('=');
        if (equals == std::string::npos) {
            error = "invalid flat package manifest line " + std::to_string(line_number);
            return false;
        }
        std::string key = trim(line.substr(0, equals));
        std::string encoded = trim(line.substr(equals + 1));
        if (allowed.count(key) == 0) {
            error = "unsupported package manifest field: " + key;
            return false;
        }
        if (values.count(key) != 0) {
            error = "duplicate package manifest field: " + key;
            return false;
        }
        std::string value;
        if (encoded == "true" || encoded == "false") {
            value = encoded;
        } else if (encoded.size() >= 2 && encoded.front() == '"' && encoded.back() == '"') {
            value = encoded.substr(1, encoded.size() - 2);
            if (value.find('"') != std::string::npos || value.find('\\') != std::string::npos) {
                error = "package manifest string contains unsupported escaping: " + key;
                return false;
            }
        } else {
            error = "package manifest value is not a supported scalar: " + key;
            return false;
        }
        values.emplace(std::move(key), std::move(value));
    }
    return true;
}

struct PackageIdentity {
    std::string profile;
    std::string target_os;
    std::string target_arch;
    std::string linkage;
    std::string entrypoint;
    std::string source_revision;
    bool source_dirty = false;
    std::string universal_launcher_revision;
    std::string universal_setup_revision;
};

bool load_package_identity(
    const fs::path& manifest,
    PackageIdentity& identity,
    std::map<std::string, std::string>& values,
    std::string& error)
{
    const std::set<std::string> required = {
        "schema", "profile_id", "lane", "target_os", "target_arch", "package_type",
        "entrypoint", "linkage_model", "release_profile", "package_manifest", "workspace_lock",
        "source_revision", "proof_baseline_revision", "universal_launcher_revision",
        "universal_setup_revision", "artifact_level", "signed", "published", "source_dirty",
        "python_runtime", "bundles_factorio_binaries"};
    if (!parse_flat_manifest(manifest, required, values, error)) return false;
    for (const std::string& key : required) {
        if (values.count(key) == 0) {
            error = "package manifest is missing required field: " + key;
            return false;
        }
    }
    if (values["schema"] != "facman.built_package.v1" ||
        values["artifact_level"] != "built-artifact" ||
        values["signed"] != "false" || values["published"] != "false" ||
        values["python_runtime"] != "false" || values["bundles_factorio_binaries"] != "false" ||
        (values["source_dirty"] != "true" && values["source_dirty"] != "false") ||
        values["workspace_lock"] != "release/index/workspace_lock.v1.toml" ||
        (values["package_type"] != "portable_zip" && values["package_type"] != "tarball")) {
        error = "package manifest fixed policy fields are invalid";
        return false;
    }
    for (const std::string key : {
             "source_revision", "proof_baseline_revision", "universal_launcher_revision",
             "universal_setup_revision"}) {
        if (!is_hex_revision(values[key])) {
            error = "package manifest revision is not a 40-character hex SHA: " + key;
            return false;
        }
    }

    identity.profile = values["profile_id"];
    identity.target_os = values["target_os"];
    identity.target_arch = values["target_arch"];
    identity.linkage = values["linkage_model"];
    identity.entrypoint = values["entrypoint"];
    identity.source_revision = values["source_revision"];
    identity.source_dirty = values["source_dirty"] == "true";
    identity.universal_launcher_revision = values["universal_launcher_revision"];
    identity.universal_setup_revision = values["universal_setup_revision"];

    struct Expected {
        const char* profile;
        const char* target_os;
        const char* package_type;
        const char* linkage;
        const char* entrypoint;
    };
    const Expected profiles[] = {
        {"windows_portable_cli_x64", "windows", "portable_zip", "static_first", "bin/facman.exe"},
        {"linux_portable_cli_x64", "linux", "tarball", "static_first", "bin/facman"},
        {"macos_portable_cli_x64", "macos", "tarball", "static_first", "bin/facman"},
        {"windows_portable_tui_x64", "windows", "portable_zip", "static_first", "bin/facman-tui.exe"},
        {"linux_portable_tui_x64", "linux", "tarball", "static_first", "bin/facman-tui"},
        {"macos_portable_tui_x64", "macos", "tarball", "static_first", "bin/facman-tui"},
        {"portable_cli_x64", "portable", "portable_zip", "static_first_with_reference_components", "bin/facman"},
        {"portable_tui_x64", "portable", "portable_zip", "static_first_with_reference_components", "bin/facman-tui"},
        {"windows_legacy_winforms_x64", "windows", "portable_zip", "compatibility_bundle", "bin/FacMan.WinForms.exe"},
    };
    const Expected* expected = nullptr;
    for (const Expected& candidate : profiles) {
        if (identity.profile == candidate.profile) expected = &candidate;
    }
    if (expected == nullptr) {
        error = "unknown built package profile: " + identity.profile;
        return false;
    }
    if (identity.target_os != expected->target_os || identity.target_arch != "x64" ||
        values["package_type"] != expected->package_type ||
        identity.linkage != expected->linkage || identity.entrypoint != expected->entrypoint) {
        error = "package target, linkage, or entrypoint identity does not match profile " + identity.profile;
        return false;
    }
    if (identity.target_os == "windows") {
#ifndef _WIN32
        error = "Windows package cannot run on this operating system";
        return false;
#endif
    }
    if (identity.target_os == "linux") {
#ifndef __linux__
        error = "Linux package cannot run on this operating system";
        return false;
#endif
    }
    if (identity.target_os == "macos") {
#ifndef __APPLE__
        error = "macOS package cannot run on this operating system";
        return false;
#endif
    }
#if !defined(_M_X64) && !defined(__x86_64__)
    error = "x64 package cannot run on this architecture";
    return false;
#endif
    return true;
}

bool load_workspace_pins(
    const fs::path& path,
    std::map<std::string, std::string>& pins,
    std::string& error)
{
    std::ifstream input(path, std::ios::binary);
    if (!input) {
        error = "cannot open release/index/workspace_lock.v1.toml";
        return false;
    }
    std::string current_id;
    std::string current_pin;
    auto commit = [&]() -> bool {
        if (current_id.empty() && current_pin.empty()) return true;
        if (current_id.empty() || !is_hex_revision(current_pin) || pins.count(current_id) != 0) {
            error = "workspace lock contains an invalid or duplicate component record";
            return false;
        }
        pins.emplace(current_id, current_pin);
        current_id.clear();
        current_pin.clear();
        return true;
    };
    bool inside_component = false;
    std::string line;
    while (std::getline(input, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        line = trim(line);
        if (line == "[[component]]") {
            if (inside_component && !commit()) return false;
            inside_component = true;
            continue;
        }
        if (!inside_component) continue;
        auto read_string = [&](const std::string& key, std::string& output) {
            const std::string prefix = key + " = \"";
            if (line.rfind(prefix, 0) == 0 && line.size() > prefix.size() && line.back() == '"') {
                output = line.substr(prefix.size(), line.size() - prefix.size() - 1);
                return true;
            }
            return false;
        };
        (void)(read_string("id", current_id) || read_string("pin", current_pin));
    }
    if (!inside_component || !commit()) return false;
    const std::set<std::string> expected = {"factorio_binding", "universal_launcher", "universal_setup"};
    std::set<std::string> actual;
    for (const auto& entry : pins) actual.insert(entry.first);
    if (actual != expected) {
        error = "workspace lock component set is incomplete or unexpected";
        return false;
    }
    return true;
}

struct StageIdentity {
    PackageIdentity package;
    std::map<std::string, std::string> declared;
    std::map<std::string, std::uint64_t> sizes;
    std::string manifest_sha256;
    std::string stage_digest;
};

bool validate_stage_authority(const json::Value& document, std::string& error)
{
    const json::Value* authority = document.find("authority");
    if (authority == nullptr || !authority->is_object()) {
        error = "runtime release metadata authority is missing";
        return false;
    }
    bool product_authority = true;
    if (!required_boolean(
            *authority,
            "product_authority_granted",
            product_authority,
            "runtime release authority",
            error) ||
        product_authority) {
        if (error.empty()) error = "runtime release metadata grants product authority";
        return false;
    }
    const json::Value* artifacts = authority->find("artifacts");
    if (artifacts == nullptr || !artifacts->is_array() || artifacts->size() != 1U) {
        error = "runtime release authority must describe exactly one artifact";
        return false;
    }
    const json::Value* artifact = artifacts->at(0U);
    if (artifact == nullptr || !artifact->is_object() ||
        !required_fixed_text(
            *artifact,
            "artifact_id",
            kTechnicalPreviewArtifact,
            "runtime release authority artifact",
            error)) {
        return false;
    }
    const json::Value* capabilities = artifact->find("capabilities");
    if (capabilities == nullptr || !capabilities->is_array() || capabilities->size() == 0U) {
        error = "runtime release authority capability set is empty";
        return false;
    }
    for (std::size_t index = 0; index < capabilities->size(); ++index) {
        const json::Value* capability = capabilities->at(index);
        bool authorized = true;
        bool enabled = true;
        if (capability == nullptr || !capability->is_object() ||
            !required_boolean(
                *capability,
                "currently_authorized",
                authorized,
                "runtime release capability",
                error) ||
            !required_boolean(
                *capability,
                "enabled_by_default",
                enabled,
                "runtime release capability",
                error)) {
            return false;
        }
        if (authorized || enabled) {
            error = "runtime release capability is authorized or enabled";
            return false;
        }
    }
    return true;
}

bool load_stage_source_identity(
    const fs::path& package_root,
    const std::string& resolution_root_digest,
    const std::string& source_observation_digest,
    PackageIdentity& identity,
    std::string& error)
{
    json::Value resolution;
    std::string source_text;
    if (!load_json_document(
            package_root / fs::u8path(kResolutionSetRelative),
            resolution,
            source_text,
            error)) {
        return false;
    }
    const std::set<std::string> resolution_members = {
        "canonicalization", "compiler_contract", "input_set_digest", "product_id",
        "product_version", "records", "root_digest", "schema", "source",
        "source_observation_digest", "target_id", "toolchain_observation"};
    if (!exact_members(resolution, resolution_members, "release resolution set", error) ||
        !required_fixed_text(
            resolution,
            "schema",
            "facman.release_resolution_set.v1",
            "release resolution set",
            error) ||
        !required_fixed_text(
            resolution,
            "target_id",
            kTechnicalPreviewTarget,
            "release resolution set",
            error)) {
        return false;
    }
    std::string value;
    if (!required_text(resolution, "root_digest", value, "release resolution set", error) ||
        value != resolution_root_digest ||
        !required_text(
            resolution,
            "source_observation_digest",
            value,
            "release resolution set",
            error) ||
        value != source_observation_digest) {
        if (error.empty()) error = "release resolution custody digests disagree with the stage";
        return false;
    }

    const json::Value* source = resolution.find("source");
    const std::set<std::string> source_members = {
        "build_tree", "dirty", "implementation_revision", "providers",
        "release_eligible", "reviewed_base_revision"};
    if (source == nullptr ||
        !exact_members(*source, source_members, "release source observation", error)) {
        return false;
    }
    bool dirty = true;
    bool release_eligible = false;
    if (!required_text(
            *source,
            "implementation_revision",
            identity.source_revision,
            "release source observation",
            error) ||
        !is_hex_revision(identity.source_revision) ||
        !required_boolean(*source, "dirty", dirty, "release source observation", error) ||
        !required_boolean(
            *source,
            "release_eligible",
            release_eligible,
            "release source observation",
            error) ||
        dirty || !release_eligible) {
        if (error.empty()) error = "release source observation is dirty or ineligible";
        return false;
    }
    identity.source_dirty = dirty;

    const json::Value* providers = source->find("providers");
    if (providers == nullptr || !providers->is_array() || providers->size() != 2U) {
        error = "release source observation provider set is incomplete";
        return false;
    }
    std::map<std::string, std::string> provider_revisions;
    for (std::size_t index = 0; index < providers->size(); ++index) {
        const json::Value* provider = providers->at(index);
        const std::set<std::string> provider_members = {
            "commit", "dirty", "id", "observation_digest", "tree"};
        if (provider == nullptr ||
            !exact_members(*provider, provider_members, "release source provider", error)) {
            return false;
        }
        std::string id;
        std::string revision;
        bool provider_dirty = true;
        if (!required_text(*provider, "id", id, "release source provider", error) ||
            !required_text(*provider, "commit", revision, "release source provider", error) ||
            !is_hex_revision(revision) ||
            !required_boolean(
                *provider,
                "dirty",
                provider_dirty,
                "release source provider",
                error) ||
            provider_dirty || !provider_revisions.emplace(id, revision).second) {
            if (error.empty()) error = "release source provider record is invalid";
            return false;
        }
    }
    if (provider_revisions.count("universal_launcher") != 1U ||
        provider_revisions.count("universal_setup") != 1U ||
        provider_revisions.size() != 2U) {
        error = "release source provider identities are unexpected";
        return false;
    }

    json::Value runtime;
    std::string runtime_text;
    if (!load_json_document(
            package_root / fs::u8path(kRuntimeMetadataRelative),
            runtime,
            runtime_text,
            error)) {
        return false;
    }
    const std::set<std::string> runtime_members = {
        "authority", "claims", "compatibility", "entrypoints", "licence_paths",
        "metadata_digest", "product_id", "product_version", "provider_locks",
        "release_eligible", "resolution_root_digest", "schema",
        "source_observation_digest", "target_id"};
    bool runtime_eligible = false;
    if (!exact_members(runtime, runtime_members, "runtime release metadata", error) ||
        !required_fixed_text(
            runtime,
            "schema",
            "facman.runtime_release_metadata.v1",
            "runtime release metadata",
            error) ||
        !required_fixed_text(
            runtime,
            "target_id",
            kTechnicalPreviewTarget,
            "runtime release metadata",
            error) ||
        !required_text(
            runtime,
            "resolution_root_digest",
            value,
            "runtime release metadata",
            error) ||
        value != resolution_root_digest ||
        !required_text(
            runtime,
            "source_observation_digest",
            value,
            "runtime release metadata",
            error) ||
        value != source_observation_digest ||
        !required_boolean(
            runtime,
            "release_eligible",
            runtime_eligible,
            "runtime release metadata",
            error) ||
        !runtime_eligible || !validate_stage_authority(runtime, error)) {
        if (error.empty()) error = "runtime release metadata custody is invalid";
        return false;
    }

    const json::Value* locks = runtime.find("provider_locks");
    if (locks == nullptr || !locks->is_array() || locks->size() != 2U) {
        error = "runtime release metadata provider locks are incomplete";
        return false;
    }
    std::map<std::string, std::string> locked_revisions;
    for (std::size_t index = 0; index < locks->size(); ++index) {
        const json::Value* lock = locks->at(index);
        if (lock == nullptr || !lock->is_object()) {
            error = "runtime release provider lock is not an object";
            return false;
        }
        std::string id;
        std::string revision;
        if (!required_text(*lock, "id", id, "runtime release provider lock", error) ||
            !required_text(
                *lock,
                "source_revision",
                revision,
                "runtime release provider lock",
                error) ||
            !is_hex_revision(revision) ||
            !locked_revisions.emplace(id, revision).second) {
            if (error.empty()) error = "runtime release provider lock is invalid";
            return false;
        }
    }
    if (locked_revisions != provider_revisions) {
        error = "runtime provider locks disagree with the release source observation";
        return false;
    }
    identity.universal_launcher_revision = provider_revisions["universal_launcher"];
    identity.universal_setup_revision = provider_revisions["universal_setup"];
    return true;
}

bool load_stage_identity(
    const fs::path& package_root,
    StageIdentity& output,
    std::string& error)
{
    const fs::path manifest_path = package_root / fs::u8path(kStageManifestRelative);
    json::Value manifest;
    std::string manifest_text;
    if (!load_json_document(manifest_path, manifest, manifest_text, error)) return false;
    const std::set<std::string> manifest_members = {
        "adapter", "artifact_id", "declarations", "entries", "product_id",
        "product_version", "resolution_digest", "resolution_root_digest", "schema",
        "setup_mutation_authorized", "source_observation_digest",
        "source_release_eligible", "stage_digest", "staging_domain", "target_id"};
    bool setup_authorized = true;
    bool source_eligible = false;
    if (!exact_members(manifest, manifest_members, "stage manifest", error) ||
        !required_fixed_text(
            manifest, "schema", "facman.stage_manifest.v1", "stage manifest", error) ||
        !required_fixed_text(
            manifest, "target_id", kTechnicalPreviewTarget, "stage manifest", error) ||
        !required_fixed_text(
            manifest, "artifact_id", kTechnicalPreviewArtifact, "stage manifest", error) ||
        !required_fixed_text(manifest, "adapter", "portable_zip", "stage manifest", error) ||
        !required_fixed_text(manifest, "product_id", "facman", "stage manifest", error) ||
        !required_fixed_text(
            manifest,
            "staging_domain",
            "release_build_output",
            "stage manifest",
            error) ||
        !required_boolean(
            manifest,
            "setup_mutation_authorized",
            setup_authorized,
            "stage manifest",
            error) ||
        !required_boolean(
            manifest,
            "source_release_eligible",
            source_eligible,
            "stage manifest",
            error) ||
        setup_authorized || !source_eligible) {
        if (error.empty()) error = "stage manifest enables mutation or uses ineligible source";
        return false;
    }

    std::string resolution_root_digest;
    std::string source_observation_digest;
    if (!required_text(
            manifest,
            "resolution_root_digest",
            resolution_root_digest,
            "stage manifest",
            error) ||
        !is_hex_digest(resolution_root_digest) ||
        !required_text(
            manifest,
            "source_observation_digest",
            source_observation_digest,
            "stage manifest",
            error) ||
        !is_hex_digest(source_observation_digest) ||
        !required_text(
            manifest,
            "stage_digest",
            output.stage_digest,
            "stage manifest",
            error) ||
        !is_hex_digest(output.stage_digest)) {
        if (error.empty()) error = "stage manifest custody digest is invalid";
        return false;
    }

    auto canonical_result = json::canonical_integer_object_without(
        manifest, "stage_digest");
    if (!canonical_result) {
        error = canonical_result.error().message;
        return false;
    }
    const std::string canonical = canonical_result.take_value();
    const std::string computed_digest = facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(canonical.data()), canonical.size());
    if (computed_digest != output.stage_digest) {
        error = "stage manifest digest does not match its canonical content";
        return false;
    }

    const json::Value* declarations = manifest.find("declarations");
    if (declarations == nullptr || !declarations->is_array() || declarations->size() == 0U ||
        declarations->size() > kMaximumPackageEntries) {
        error = "stage manifest declarations are missing or excessive";
        return false;
    }
    std::set<std::string> declaration_ids;
    for (std::size_t index = 0; index < declarations->size(); ++index) {
        const json::Value* declaration = declarations->at(index);
        const std::set<std::string> members = {
            "component_owner", "destination", "id", "source_kind"};
        std::string id;
        std::string destination;
        if (declaration == nullptr ||
            !exact_members(*declaration, members, "stage declaration", error) ||
            !required_text(*declaration, "id", id, "stage declaration", error) ||
            !required_text(
                *declaration,
                "destination",
                destination,
                "stage declaration",
                error) ||
            !is_safe_relative(destination) || !declaration_ids.insert(id).second) {
            if (error.empty()) error = "stage declaration is unsafe or duplicated";
            return false;
        }
    }

    const json::Value* entries = manifest.find("entries");
    if (entries == nullptr || !entries->is_array() || entries->size() == 0U ||
        entries->size() > kMaximumPackageEntries) {
        error = "stage manifest entries are missing or excessive";
        return false;
    }
    bool selected_cli = false;
    bool selected_winforms = false;
    for (std::size_t index = 0; index < entries->size(); ++index) {
        const json::Value* entry = entries->at(index);
        const std::set<std::string> members = {
            "mode", "owner", "ownership_class", "path", "sha256", "size", "source"};
        std::string path;
        std::string digest;
        std::string owner;
        std::uint64_t size = 0U;
        std::uint64_t mode = 0U;
        if (entry == nullptr || !exact_members(*entry, members, "stage entry", error) ||
            !required_text(*entry, "path", path, "stage entry", error) ||
            !required_text(*entry, "sha256", digest, "stage entry", error) ||
            !required_text(*entry, "owner", owner, "stage entry", error) ||
            !required_unsigned(*entry, "size", size, "stage entry", error) ||
            !required_unsigned(*entry, "mode", mode, "stage entry", error) ||
            !is_safe_relative(path) || path == kStageManifestRelative ||
            !is_hex_digest(digest) || mode > 0777U ||
            !output.declared.emplace(path, digest).second ||
            !output.sizes.emplace(path, size).second) {
            if (error.empty()) error = "stage entry is unsafe or duplicated";
            return false;
        }
        if (path == "bin/facman.exe" && owner == "facman_cli") selected_cli = true;
        if (path == "bin/FacMan.WinForms.exe" && owner == "facman_winforms") {
            selected_winforms = true;
        }
    }
    if (!selected_cli || !selected_winforms ||
        output.declared.count(kResolutionSetRelative) != 1U ||
        output.declared.count(kRuntimeMetadataRelative) != 1U) {
        error = "stage manifest omits the required WinForms, CLI, or custody records";
        return false;
    }

    output.package.profile = kTechnicalPreviewTarget;
    output.package.target_os = "windows";
    output.package.target_arch = "x64";
    output.package.linkage = "embedded_static";
    output.package.entrypoint = "bin/FacMan.WinForms.exe";
    if (!load_stage_source_identity(
            package_root,
            resolution_root_digest,
            source_observation_digest,
            output.package,
            error)) {
        return false;
    }
    output.manifest_sha256 = facman::base::sha256_hex_file(manifest_path);
    return true;
}

bool component_semantics_match(
    const fs::path& root,
    const PackageIdentity& identity,
    const std::map<std::string, std::string>& declared,
    std::string& error)
{
    std::vector<facman::package::ComponentRecord> components;
    if (!facman::package::load_component_manifest(root / "manifest" / "components.v1.json", components, error)) {
        return false;
    }
    std::set<std::string> names;
    std::set<std::string> destinations;
    std::size_t runtime_required = 0;
    bool selected_cli = false;
    bool selected_contracts = false;
    bool selected_content = false;
    const bool target_static_profile =
        identity.profile == "windows_portable_cli_x64" ||
        identity.profile == "linux_portable_cli_x64" ||
        identity.profile == "macos_portable_cli_x64" ||
        identity.profile == "windows_portable_tui_x64" ||
        identity.profile == "linux_portable_tui_x64" ||
        identity.profile == "macos_portable_tui_x64";
    for (const facman::package::ComponentRecord& component : components) {
        if (!names.insert(component.name).second || !destinations.insert(component.destination).second) {
            error = "component manifest contains duplicate names or destinations";
            return false;
        }
        if (!is_safe_relative(component.destination)) {
            error = "component manifest contains an unsafe destination: " + component.destination;
            return false;
        }
        auto hash = declared.find(component.destination);
        if (hash == declared.end() || hash->second != component.sha256) {
            error = "component digest disagrees with hash manifest: " + component.destination;
            return false;
        }
        std::error_code size_error;
        std::uintmax_t actual_size = fs::file_size(root / fs::u8path(component.destination), size_error);
        if (size_error || actual_size != component.size) {
            error = "component size disagrees with package file: " + component.destination;
            return false;
        }
        if (component.runtime_role == "runtime_required") ++runtime_required;
        if (target_static_profile) {
            const std::string& selected_entrypoint = identity.entrypoint;
            if (component.kind == "runtime_library") {
                error = "static-first CLI package declares a shared project runtime library";
                return false;
            }
            if (component.destination == selected_entrypoint &&
                component.runtime_role == "runtime_required") {
                selected_cli = true;
            }
            if (component.destination.rfind("contracts/schema/", 0) == 0 &&
                component.runtime_role == "compatibility_reference") selected_contracts = true;
            if (component.destination.rfind("content/factorio/", 0) == 0 &&
                component.runtime_role == "compatibility_reference") selected_content = true;
        }
    }
    if (runtime_required == 0) {
        error = "component manifest has no runtime_required component";
        return false;
    }
    if (target_static_profile && (!selected_cli || !selected_contracts || !selected_content)) {
        error = "static-first CLI/TUI package component roles are incomplete";
        return false;
    }
    return true;
}

bool contract_set_digest(
    const fs::path& root,
    const std::map<std::string, std::string>& declared,
    std::string& digest,
    std::string& error)
{
    facman::base::Sha256Hasher hasher;
    const unsigned char separator = 0;
    std::size_t contract_count = 0;
    for (const auto& entry : declared) {
        const std::string& relative = entry.first;
        if (relative.rfind("contracts/schema/", 0) != 0) {
            continue;
        }
        ++contract_count;
        hasher.update(
            reinterpret_cast<const unsigned char*>(relative.data()),
            relative.size());
        hasher.update(&separator, 1);

        std::ifstream input(root / fs::u8path(relative), std::ios::binary);
        if (!input) {
            error = "cannot open packaged contract schema: " + relative;
            return false;
        }
        std::array<char, 8192> buffer {};
        bool pending_carriage_return = false;
        while (input) {
            input.read(buffer.data(), static_cast<std::streamsize>(buffer.size()));
            const std::streamsize count = input.gcount();
            std::vector<unsigned char> normalized;
            normalized.reserve(static_cast<std::size_t>(count) + 1U);
            for (std::streamsize index = 0; index < count; ++index) {
                const unsigned char byte = static_cast<unsigned char>(buffer[static_cast<std::size_t>(index)]);
                if (byte == '\r') {
                    if (pending_carriage_return) normalized.push_back('\n');
                    pending_carriage_return = true;
                    continue;
                }
                if (byte == '\n') {
                    normalized.push_back('\n');
                    pending_carriage_return = false;
                    continue;
                }
                if (pending_carriage_return) {
                    normalized.push_back('\n');
                    pending_carriage_return = false;
                }
                normalized.push_back(byte);
            }
            if (!normalized.empty()) hasher.update(normalized.data(), normalized.size());
        }
        if (input.bad()) {
            error = "cannot read packaged contract schema: " + relative;
            return false;
        }
        if (pending_carriage_return) {
            const unsigned char newline = '\n';
            hasher.update(&newline, 1);
        }
        hasher.update(&separator, 1);
    }
    if (contract_count == 0) {
        error = "package contains no contract schemas";
        return false;
    }
    digest = hasher.finish();
    return true;
}

bool executable_identity(
    const fs::path& root,
    const fs::path& executable,
    const std::map<std::string, std::string>& declared,
    std::string& relative,
    std::string& digest,
    std::string& error)
{
    if (executable.empty()) {
        error = "running executable path is not configured";
        return false;
    }
    std::error_code relative_error;
    const fs::path relative_path = fs::relative(executable, root, relative_error);
    relative = relative_error ? std::string() : relative_path.generic_string();
    if (relative_error || !is_safe_relative(relative)) {
        error = "running executable is outside the package root";
        return false;
    }
    const auto declared_digest = declared.find(relative);
    if (declared_digest == declared.end()) {
        error = "running executable is absent from the package hash closure: " + relative;
        return false;
    }
    digest = declared_digest->second;
    return true;
}

fs::path running_executable(const char* executable_path)
{
#ifdef _WIN32
    std::wstring buffer(32768, L'\0');
    DWORD length = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (length > 0 && length < buffer.size()) {
        buffer.resize(length);
        return fs::path(buffer);
    }
#endif
    if (executable_path == nullptr || executable_path[0] == '\0') {
        return {};
    }
    std::error_code error;
    fs::path absolute = fs::absolute(fs::u8path(executable_path), error);
    return error ? fs::u8path(executable_path) : absolute;
}

facman::package::RuntimePackageEvidence inspect_stage_package_impl(
    const fs::path& package_root,
    const fs::path& executable_path)
{
    facman::package::RuntimePackageEvidence evidence;
    evidence.packaged = true;
#ifndef _WIN32
    evidence.detail = "Windows Technical Preview package cannot run on this operating system";
    return evidence;
#endif
#if !defined(_M_X64) && !defined(__x86_64__)
    evidence.detail = "Windows Technical Preview package requires x64";
    return evidence;
#endif

    StageIdentity stage;
    std::string identity_error;
    if (!load_stage_identity(package_root, stage, identity_error)) {
        evidence.detail = identity_error;
        return evidence;
    }
    evidence.profile_id = stage.package.profile;
    evidence.manifest_sha256 = stage.manifest_sha256;
    evidence.closure_sha256 = stage.stage_digest;
    evidence.source_revision = stage.package.source_revision;
    evidence.source_dirty = stage.package.source_dirty;
    evidence.source_dirty_known = true;
    evidence.universal_launcher_revision = stage.package.universal_launcher_revision;
    evidence.universal_setup_revision = stage.package.universal_setup_revision;

    std::error_code error;
    const fs::path canonical_root = fs::canonical(package_root, error);
    if (error) {
        evidence.detail = "cannot resolve package root: " + error.message();
        return evidence;
    }
    for (const auto& entry : stage.declared) {
        const fs::path candidate = package_root / fs::u8path(entry.first);
        if (!fs::is_regular_file(candidate) || is_reparse_or_symlink(candidate)) {
            evidence.detail = "missing or unsafe staged file: " + entry.first;
            return evidence;
        }
        const fs::path canonical_candidate = fs::canonical(candidate, error);
        if (error || !is_within(canonical_root, canonical_candidate)) {
            evidence.detail = "staged file escapes package root: " + entry.first;
            return evidence;
        }
        std::error_code size_error;
        const std::uintmax_t actual_size = fs::file_size(candidate, size_error);
        if (size_error || actual_size != stage.sizes[entry.first]) {
            evidence.detail = "staged file size mismatch: " + entry.first;
            return evidence;
        }
        if (facman::base::sha256_hex_file(candidate) != entry.second) {
            evidence.detail = "staged file SHA-256 mismatch: " + entry.first;
            return evidence;
        }
    }

    std::set<std::string> actual_files;
    std::string collect_error;
    if (!collect_package_files(
            package_root,
            kStageManifestRelative,
            actual_files,
            collect_error)) {
        evidence.detail = collect_error;
        return evidence;
    }
    std::set<std::string> declared_files;
    for (const auto& entry : stage.declared) declared_files.insert(entry.first);
    if (actual_files != declared_files) {
        evidence.detail = "stage manifest does not close over the package file set";
        return evidence;
    }
    if (!executable_identity(
            package_root,
            executable_path,
            stage.declared,
            evidence.backend_relative_path,
            evidence.backend_sha256,
            identity_error)) {
        evidence.detail = identity_error;
        return evidence;
    }
    if (evidence.backend_relative_path != "bin/facman.exe") {
        evidence.detail = "Technical Preview backend is not bin/facman.exe";
        return evidence;
    }
    if (!contract_set_digest(
            package_root,
            stage.declared,
            evidence.contract_set_sha256,
            identity_error)) {
        evidence.detail = identity_error;
        return evidence;
    }

    evidence.files_verified = stage.declared.size();
    evidence.verified = true;
    evidence.detail =
        "Technical Preview stage matches its unsigned canonical SHA-256 manifest";
    return evidence;
}

facman::package::RuntimePackageEvidence inspect_package_impl(
    const fs::path& package_root,
    const fs::path& executable_path)
{
    facman::package::RuntimePackageEvidence evidence;
    if (package_root.empty()) {
        evidence.detail = "package root is not configured";
        return evidence;
    }

    const fs::path stage_manifest_path =
        package_root / fs::u8path(kStageManifestRelative);
    std::error_code stage_error;
    if (fs::is_regular_file(stage_manifest_path, stage_error) && !stage_error) {
        return inspect_stage_package_impl(package_root, executable_path);
    }

    const fs::path manifest_path = package_root / "manifest" / "package.v1.toml";
    std::error_code packaged_error;
    evidence.packaged = fs::is_regular_file(manifest_path, packaged_error);
    if (!evidence.packaged) {
        evidence.detail = "running executable is not in a built package";
        return evidence;
    }

    const fs::path required[] = {
        manifest_path,
        package_root / "manifest" / "build_info.v1.json",
        package_root / "manifest" / "components.v1.json",
        package_root / "manifest" / "hashes.sha256",
        package_root / "release" / "index" / "workspace_lock.v1.toml",
    };
    for (const fs::path& path : required) {
        if (!fs::exists(path)) {
            evidence.detail = "missing required package path: " +
                path.lexically_relative(package_root).generic_string();
            return evidence;
        }
    }
    evidence.manifest_sha256 = facman::base::sha256_hex_file(required[0]);
    evidence.closure_sha256 = facman::base::sha256_hex_file(required[3]);

    PackageIdentity identity;
    std::map<std::string, std::string> manifest_values;
    std::string identity_error;
    if (!load_package_identity(required[0], identity, manifest_values, identity_error)) {
        evidence.detail = identity_error;
        return evidence;
    }
    evidence.profile_id = identity.profile;
    evidence.source_revision = identity.source_revision;
    evidence.source_dirty = identity.source_dirty;
    evidence.source_dirty_known = true;
    evidence.universal_launcher_revision = identity.universal_launcher_revision;
    evidence.universal_setup_revision = identity.universal_setup_revision;

    std::map<std::string, std::string> workspace_pins;
    if (!load_workspace_pins(required[4], workspace_pins, identity_error)) {
        evidence.detail = identity_error;
        return evidence;
    }
    if (manifest_values["proof_baseline_revision"] != workspace_pins["factorio_binding"] ||
        manifest_values["universal_launcher_revision"] != workspace_pins["universal_launcher"] ||
        manifest_values["universal_setup_revision"] != workspace_pins["universal_setup"]) {
        evidence.detail = "package source revisions disagree with workspace lock";
        return evidence;
    }

    std::error_code error;
    const fs::path canonical_root = fs::canonical(package_root, error);
    if (error) {
        evidence.detail = "cannot resolve package root: " + error.message();
        return evidence;
    }

    std::ifstream input(required[3], std::ios::binary);
    if (!input) {
        evidence.detail = "cannot open manifest/hashes.sha256";
        return evidence;
    }

    std::map<std::string, std::string> declared;
    std::string line;
    size_t line_number = 0;
    while (std::getline(input, line)) {
        ++line_number;
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.size() < 67 || line.substr(64, 2) != "  ") {
            evidence.detail = "invalid hash manifest line " + std::to_string(line_number);
            return evidence;
        }
        std::string expected = line.substr(0, 64);
        std::string relative = line.substr(66);
        if (!is_hex_digest(expected) || !is_safe_relative(relative) ||
            relative == "manifest/hashes.sha256") {
            evidence.detail = "unsafe or invalid hash manifest line " + std::to_string(line_number);
            return evidence;
        }
        std::transform(expected.begin(), expected.end(), expected.begin(), [](unsigned char ch) {
            return static_cast<char>(std::tolower(ch));
        });
        if (!declared.emplace(relative, expected).second) {
            evidence.detail = "duplicate hash manifest path: " + relative;
            return evidence;
        }

        const fs::path candidate = package_root / fs::u8path(relative);
        if (!fs::is_regular_file(candidate) || is_reparse_or_symlink(candidate)) {
            evidence.detail = "missing or unsafe hashed file: " + relative;
            return evidence;
        }
        const fs::path canonical_candidate = fs::canonical(candidate, error);
        if (error || !is_within(canonical_root, canonical_candidate)) {
            evidence.detail = "hashed file escapes package root: " + relative;
            return evidence;
        }
        const std::string actual = facman::base::sha256_hex_file(candidate);
        if (actual != expected) {
            evidence.detail = "SHA-256 mismatch: " + relative;
            return evidence;
        }
    }
    if (!input.eof()) {
        evidence.detail = "cannot read manifest/hashes.sha256";
        return evidence;
    }

    std::set<std::string> actual_files;
    std::string collect_error;
    if (!collect_package_files(
            package_root,
            "manifest/hashes.sha256",
            actual_files,
            collect_error)) {
        evidence.detail = collect_error;
        return evidence;
    }
    std::set<std::string> declared_files;
    for (const auto& entry : declared) declared_files.insert(entry.first);
    if (actual_files != declared_files) {
        evidence.detail = "hash manifest does not close over the package file set";
        return evidence;
    }
    std::string component_error;
    if (!component_semantics_match(package_root, identity, declared, component_error)) {
        evidence.detail = component_error;
        return evidence;
    }
    if (!executable_identity(
            package_root,
            executable_path,
            declared,
            evidence.backend_relative_path,
            evidence.backend_sha256,
            component_error)) {
        evidence.detail = component_error;
        return evidence;
    }
    if (!contract_set_digest(
            package_root,
            declared,
            evidence.contract_set_sha256,
            component_error)) {
        evidence.detail = component_error;
        return evidence;
    }

    evidence.files_verified = declared.size();
    evidence.verified = true;
    evidence.detail = "package contents match the unsigned SHA-256 manifest";
    return evidence;
}

} // namespace

extern "C" void fl_runtime_set_executable_path(const char* executable_path)
{
    g_executable_path = running_executable(executable_path);
    g_package_root = g_executable_path.empty()
        ? fs::path()
        : g_executable_path.parent_path().parent_path();
    g_package_root_text = g_package_root.empty() ? std::string() : g_package_root.u8string();
}

extern "C" const char* fl_runtime_package_root(void)
{
    return g_package_root_text.c_str();
}

extern "C" int fl_runtime_is_packaged(void)
{
    std::error_code error;
    if (g_package_root.empty()) return 0;
    if (fs::is_regular_file(g_package_root / "manifest" / "package.v1.toml", error) &&
        !error) {
        return 1;
    }
    error.clear();
    return fs::is_regular_file(
               g_package_root / fs::u8path(kStageManifestRelative), error) &&
        !error;
}

facman::package::RuntimePackageEvidence facman::package::inspect_package(
    const std::filesystem::path& package_root,
    const std::filesystem::path& executable_path)
{
    try {
        return inspect_package_impl(package_root, executable_path);
    } catch (const std::exception& error) {
        RuntimePackageEvidence evidence;
        evidence.packaged = !package_root.empty();
        evidence.detail = std::string("package verification error: ") + error.what();
        return evidence;
    } catch (...) {
        RuntimePackageEvidence evidence;
        evidence.packaged = !package_root.empty();
        evidence.detail = "package verification error: unknown failure";
        return evidence;
    }
}

facman::package::RuntimePackageEvidence facman::package::inspect_runtime_package(void)
{
    return inspect_package(g_package_root, g_executable_path);
}

extern "C" int fl_runtime_verify_package(
    char* detail,
    size_t detail_capacity,
    size_t* files_verified)
{
    const facman::package::RuntimePackageEvidence evidence =
        facman::package::inspect_runtime_package();
    if (files_verified != nullptr) *files_verified = evidence.files_verified;
    set_detail(detail, detail_capacity, evidence.detail);
    return evidence.verified ? 1 : 0;
}
