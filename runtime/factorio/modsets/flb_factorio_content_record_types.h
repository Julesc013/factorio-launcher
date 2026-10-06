// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_CONTENT_RECORD_TYPES_H
#define FLB_FACTORIO_CONTENT_RECORD_TYPES_H

#include <cstdint>
#include <string>
#include <vector>

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
    // Empty preserves the historical projection's unbound/sha256_bound choice.
    std::string startup_settings_state;
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

struct ModpackSetting {
    std::string path;
    bool present = false;
    BlobIdentity blob;
};

struct ModpackManifest {
    std::string name;
    ContentLock content_lock;
    std::vector<ModpackArtifact> artifacts;
    // Empty retains the original v1 serialization for existing record callers.
    std::vector<ModpackSetting> settings;
    BlobIdentity source_lock;
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

} // namespace facman::factorio::content

#endif
