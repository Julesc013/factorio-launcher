// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FL_RUNTIME_VERIFY_H
#define FL_RUNTIME_VERIFY_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* Configure package discovery from the running executable. On Windows the
 * module path is obtained from the operating system so Unicode installation
 * paths do not depend on the narrow argv encoding. */
void fl_runtime_set_executable_path(const char* executable_path);

/* Returns a borrowed package-root string valid until the next configure call. */
const char* fl_runtime_package_root(void);

/* Verify required package resources, hash-manifest closure, and SHA-256
 * content integrity. This proves consistency, not publisher authenticity. */
int fl_runtime_verify_package(
    char* detail,
    size_t detail_capacity,
    size_t* files_verified);

#ifdef __cplusplus
}
#endif

#endif
