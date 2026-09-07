// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#ifndef FACMAN_PRODUCT_RESOURCE_IDENTITY_H
#define FACMAN_PRODUCT_RESOURCE_IDENTITY_H
#include "fl_result.h"
#include <filesystem>
#include <memory>
#include <string>
namespace facman::package {
class ProductResourceSnapshot;
struct ProductResourceIdentity {
    std::filesystem::path root;
    std::string profile;
    std::string relative_path;
    std::string sha256;
    std::uint64_t bytes = 0;
    std::string source_revision;
    std::string source_tree;
    std::string manifest_sha256;
    std::string closure_sha256;
    // Internal retained metadata custody. This declaration becomes resource
    // evidence only when the resources layer verifies the same opened pack.
    std::shared_ptr<ProductResourceSnapshot> snapshot;
    facman::core::Result<void> revalidate() const;
};
// Explicit roots are for bounded tests and inspection; no environment search.
facman::core::Result<ProductResourceIdentity> inspect_product_resource_identity(
    const std::filesystem::path& root, const std::filesystem::path& executable);
// Production discovery uses the OS process image and exact supported layouts.
facman::core::Result<ProductResourceIdentity> discover_product_resource_identity();
}
#endif
