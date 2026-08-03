// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FL_RUNTIME_VERIFY_H
#define FL_RUNTIME_VERIFY_H

#include <stddef.h>

#ifdef __cplusplus
#include <filesystem>
#include <string>

namespace facman::package {

struct RuntimePackageEvidence {
    bool packaged = false;
    bool verified = false;
    std::size_t files_verified = 0;
    std::string detail;
    std::string profile_id;
    std::string manifest_sha256;
    std::string closure_sha256;
    std::string contract_set_sha256;
    std::string backend_relative_path;
    std::string backend_sha256;
    std::string source_revision;
    bool source_dirty = false;
    bool source_dirty_known = false;
    std::string universal_launcher_revision;
    std::string universal_setup_revision;
};

/* Inspect an explicit root for bounded tests and package-aware consumers. The
 * executable path must identify the process image represented by the package. */
RuntimePackageEvidence inspect_package(
    const std::filesystem::path& package_root,
    const std::filesystem::path& executable_path);

/* Inspect the package configured from the running executable. */
RuntimePackageEvidence inspect_runtime_package(void);

} // namespace facman::package

extern "C" {
#endif

/* Configure package discovery from the running executable. On Windows the
 * module path is obtained from the operating system so Unicode installation
 * paths do not depend on the narrow argv encoding. */
void fl_runtime_set_executable_path(const char* executable_path);

/* Returns a borrowed package-root string valid until the next configure call. */
const char* fl_runtime_package_root(void);

/* Verify required package resources, hash-manifest closure, and SHA-256
 * content integrity. Returns 1 on success and 0 on failure. This proves
 * consistency, not publisher authenticity. */
int fl_runtime_verify_package(
    char* detail,
    size_t detail_capacity,
    size_t* files_verified);

#ifdef __cplusplus
}
#endif

#endif
