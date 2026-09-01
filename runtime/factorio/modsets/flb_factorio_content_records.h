// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_CONTENT_RECORDS_H
#define FLB_FACTORIO_CONTENT_RECORDS_H

#include "fl_result.h"

#include <cstdint>
#include <string>
#include <vector>

namespace facman::factorio::modsets::solver {
struct Request;
}

namespace facman::factorio::content {

// These records are additive, portable projections over the implemented
// modset and snapshot records. They do not replace either persistence model.
struct ContentRequirement {
    std::string name;
    std::string desired_state;
    std::string version_constraint;
};

struct ContentSetSpec {
    std::string instance_id;
    std::string factorio_version_requirement;
    std::string compatibility_policy;
    std::vector<ContentRequirement> requirements;
};

struct ContentLockEntry {
    std::string name;
    std::string version;
    std::string file_name;
    std::string sha256;
    std::string source;
    bool enabled = true;
    bool virtual_package = false;
    std::vector<std::string> required_dependencies;
};

struct ContentLock {
    std::string instance_id;
    std::string factorio_version;
    std::string startup_settings_sha256;
    std::string source_lock_sha256;
    std::vector<ContentLockEntry> entries;
};

struct BlobIdentity {
    std::string sha256;
    std::uint64_t size = 0;
};

struct ModpackArtifact {
    std::string name;
    std::string file_name;
    BlobIdentity blob;
};

struct ModpackManifest {
    std::string name;
    ContentLock content_lock;
    std::vector<ModpackArtifact> artifacts;
};

struct WorldFile {
    std::string path;
    std::uint64_t size = 0;
    std::string sha256;
};

struct WorldBundle {
    std::string bundle_id;
    std::string source_instance_id;
    std::string factorio_version;
    std::string content_lock_blob_sha256;
    std::string source_snapshot_manifest_sha256;
    std::vector<std::string> selected_saves;
    std::vector<WorldFile> world_files;
    std::vector<WorldFile> support_files;
};

facman::core::Result<ContentSetSpec> content_set_spec_from_modset_request(
    const facman::factorio::modsets::solver::Request& request,
    std::string factorio_version_requirement,
    std::string compatibility_policy = "factorio_minor_and_declared_dependencies");

facman::core::Result<ContentLock> content_lock_from_modset_lock_json(
    const std::string& modset_lock_json);

facman::core::Result<ModpackManifest> modpack_manifest_from_content_lock(
    std::string name,
    const ContentLock& lock,
    const std::vector<BlobIdentity>& available_blobs);

facman::core::Result<WorldBundle> world_bundle_from_snapshot_manifest_json(
    const std::string& snapshot_manifest_json);

std::string to_json(const ContentSetSpec& value);
std::string to_json(const ContentLock& value);
std::string to_json(const ModpackManifest& value);
std::string to_json(const WorldBundle& value);

std::string content_set_spec_identity(const ContentSetSpec& value);
std::string content_lock_identity(const ContentLock& value);
std::string modpack_manifest_identity(const ModpackManifest& value);
std::string world_bundle_identity(const WorldBundle& value);

} // namespace facman::factorio::content

#endif
