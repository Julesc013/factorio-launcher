// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_CONTENT_RECORDS_H
#define FLB_FACTORIO_CONTENT_RECORDS_H

#include "fl_result.h"
#include "flb_factorio_content_record_types.h"


namespace facman::factorio::modsets::solver {
struct Request;
}

namespace facman::factorio::content {

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
