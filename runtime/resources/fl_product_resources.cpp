// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "fl_resource_internal.h"
namespace facman::resources {
namespace {
facman::core::Error error(std::string code, std::string message)
{
    return {std::move(code), std::move(message), "$", facman::core::OutcomeKind::refused};
}
}
static facman::core::Result<ProductInspection> inspect_product_declaration(
    facman::package::ProductResourceIdentity identity, const InspectionCheckpoint& checkpoint)
{
    using Output = facman::core::Result<ProductInspection>;
    if (checkpoint) checkpoint("after_package_identity");
    ProductInspection output; output.identity = std::move(identity);
    const auto path = output.identity.root / std::filesystem::u8path(output.identity.relative_path);
    auto status = facman::archive::inspect_archive(path, detail::pack_limits(), output.plan);
    if (!status.ok()) return Output::failure(error(status.code, status.detail));
    if (checkpoint) checkpoint("after_resource_open");
    std::string raw_digest;
    status = facman::archive::archive_sha256(output.plan, detail::pack_limits(), raw_digest);
    if (!status.ok()) return Output::failure(error(status.code, status.detail));
    if (raw_digest != output.identity.sha256 || output.plan.archive_size != output.identity.bytes)
        return Output::failure(error("resource_package_digest_mismatch", "Resource bytes do not match the captured product identity"));
    auto inspected = detail::inspect_open_pack(path, output.plan);
    if (!inspected) return Output::failure(inspected.error());
    // In-place edits on a platform that permits them must not combine a valid
    // initial compressed hash with later, different resource entries.
    status = facman::archive::archive_sha256(output.plan, detail::pack_limits(), raw_digest);
    if (!status.ok()) return Output::failure(error(status.code, status.detail));
    if (raw_digest != output.identity.sha256) return Output::failure(error("resource_package_changed", "Resource changed during inspection"));
    auto valid = output.identity.revalidate(); if (!valid) return Output::failure(valid.error());
    output.inspection = inspected.take_value();
    output.inspection.package_profile = output.identity.profile;
    output.inspection.package_manifest_sha256 = output.identity.manifest_sha256;
    output.inspection.pack_sha256 = raw_digest;
    return Output::success(std::move(output));
}

facman::core::Result<ProductInspection> inspect_product_resources(
    const std::filesystem::path& root, const std::filesystem::path& executable,
    const InspectionCheckpoint& checkpoint)
{
    auto identity = facman::package::inspect_product_resource_identity(root, executable);
    if (!identity) return facman::core::Result<ProductInspection>::failure(identity.error());
    return inspect_product_declaration(identity.take_value(), checkpoint);
}

facman::core::Result<ProductInspection> inspect_runtime_resources()
{
    auto identity = facman::package::discover_product_resource_identity();
    if (!identity) return facman::core::Result<ProductInspection>::failure(identity.error());
    return inspect_product_declaration(identity.take_value(), {});
}

facman::core::Result<void> export_product_resources(
    const ProductInspection& inspection, const std::filesystem::path& destination,
    const InspectionCheckpoint& checkpoint,
    const facman::archive::ExtractionCheckpoint& extraction_checkpoint)
{
    if (checkpoint) checkpoint("before_product_export");
    auto valid = inspection.identity.revalidate(); if (!valid) return valid;
    std::string raw_digest;
    auto status = facman::archive::archive_sha256(inspection.plan, detail::pack_limits(), raw_digest);
    if (!status.ok()) return facman::core::Result<void>::failure(error(status.code, status.detail));
    if (raw_digest != inspection.identity.sha256)
        return facman::core::Result<void>::failure(error("resource_package_changed", "Resource changed before export"));
    status = facman::archive::extract_verified_to_new_retained_staging(inspection.plan, destination,
        detail::pack_limits(), inspection.inspection.verified_entries, extraction_checkpoint);
    if (!status.ok()) return facman::core::Result<void>::failure(error(status.code, status.detail));
    // Retain the ownership marker as evidence. Removing it by pathname would
    // grant deletion authority over a marker substituted after extraction.
    return facman::core::Result<void>::success();
}

}
