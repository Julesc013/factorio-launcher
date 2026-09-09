// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_RUNTIME_RESOURCES_FL_RESOURCE_PACK_H
#define FACMAN_RUNTIME_RESOURCES_FL_RESOURCE_PACK_H

#include "fl_result.h"
#include "fl_archive.h"
#include "fl_product_resource_identity.h"
#include <functional>
#include <optional>

#include <filesystem>
#include <string>
#include <vector>

namespace facman::resources {

struct Inspection {
    std::filesystem::path path;
    std::string version;
    std::string content_sha256;
    std::uint64_t expanded_bytes = 0;
    std::vector<std::string> entries;
    std::vector<facman::archive::VerifiedEntry> verified_entries;
    std::string package_profile;
    std::string package_manifest_sha256;
    std::string pack_sha256;
};

struct ProductInspection {
    Inspection inspection;
    facman::package::ProductResourceIdentity identity;
    facman::archive::Plan plan;
};
using InspectionCheckpoint = std::function<void(const char*)>;
facman::core::Result<ProductInspection> inspect_product_resources(
    const std::filesystem::path& root, const std::filesystem::path& executable,
    const InspectionCheckpoint& checkpoint = {});
facman::core::Result<ProductInspection> inspect_runtime_resources();
// Canonical schema digest from the verified retained pack; no extraction or override.
facman::core::Result<std::string> product_contract_set_digest(const ProductInspection& inspection);
facman::core::Result<void> export_product_resources(
    const ProductInspection& inspection, const std::filesystem::path& destination,
    const InspectionCheckpoint& checkpoint = {},
    const facman::archive::ExtractionCheckpoint& extraction_checkpoint = {},
    facman::archive::ExtractionObservation* observation = nullptr);

struct ResourceSelection {
    Inspection inspection;
    std::optional<ProductInspection> product;
};
facman::core::Result<ResourceSelection> inspect_selected_resources(const std::string& explicit_pack);
// Preserve throwing absolute-path conversion before extraction; no relative fallback.
std::string absolute_export_destination_utf8(const std::string& destination);
facman::core::Result<void> export_selected_resources(
    const ResourceSelection& selected, const std::string& destination,
    facman::archive::ExtractionObservation* observation = nullptr,
    const facman::archive::ExtractionCheckpoint& checkpoint = {});

facman::core::Result<std::filesystem::path> locate_pack(
    const std::filesystem::path& executable_path);

facman::core::Result<Inspection> inspect_pack(
    const std::filesystem::path& pack_path);

facman::core::Result<void> export_pack(
    const std::filesystem::path& pack_path,
    const std::filesystem::path& destination,
    facman::archive::ExtractionObservation* observation = nullptr,
    const facman::archive::ExtractionCheckpoint& checkpoint = {});

std::string inspection_json(const Inspection& inspection);

facman::core::Result<std::string> locate_pack_utf8(
    const std::string& executable_path);

facman::core::Result<Inspection> inspect_pack_utf8(
    const std::string& pack_path);

facman::core::Result<void> export_pack_utf8(
    const std::string& pack_path,
    const std::string& destination);

std::string absolute_path_utf8(const std::string& path);

} // namespace facman::resources

#endif
