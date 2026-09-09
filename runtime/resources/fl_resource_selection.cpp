// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "fl_resource_pack.h"
#include "fl_resource_internal.h"
#include <cstdlib>
#include <exception>
#include <system_error>
namespace facman::resources {
namespace {

facman::core::Error error(
    std::string code,
    std::string message,
    facman::core::OutcomeKind kind = facman::core::OutcomeKind::invalid_argument)
{
    return {std::move(code), std::move(message), "$", kind};
}

} // namespace

facman::core::Result<StandaloneInspection> detail::inspect_open_standalone_pack(
    const std::filesystem::path& path)
{
    StandaloneInspection output;
    const auto status = facman::archive::inspect_archive(path, pack_limits(), output.plan);
    if (!status.ok()) {
        return facman::core::Result<StandaloneInspection>::failure(
            error(status.code, status.detail));
    }
    auto inspected = inspect_open_pack(path, output.plan);
    if (!inspected) return facman::core::Result<StandaloneInspection>::failure(inspected.error());
    output.inspection = inspected.take_value();
    return facman::core::Result<StandaloneInspection>::success(std::move(output));
}

facman::core::Result<void> detail::export_open_standalone_pack(
    const StandaloneInspection& inspection,
    const std::filesystem::path& destination,
    facman::archive::ExtractionObservation* observation,
    const facman::archive::ExtractionCheckpoint& checkpoint)
{
    std::error_code filesystem_error;
    if (std::filesystem::exists(destination, filesystem_error) || filesystem_error) {
        return facman::core::Result<void>::failure(error(
            "resource_export_destination_exists", "Resource export destination must not exist"));
    }
    std::exception_ptr checkpoint_exception;
    facman::archive::ExtractionCheckpoint guarded_checkpoint;
    if (checkpoint) {
        guarded_checkpoint = [&](std::uint32_t index, const char* phase) {
            try {
                return checkpoint(index, phase);
            } catch (...) {
                checkpoint_exception = std::current_exception();
                return false;
            }
        };
    }
    const auto status = facman::archive::extract_verified_to_new_retained_staging(
        inspection.plan, destination, pack_limits(), inspection.inspection.verified_entries,
        guarded_checkpoint, observation);
    if (checkpoint_exception) std::rethrow_exception(checkpoint_exception);
    if (!status.ok()) {
        return facman::core::Result<void>::failure(
            error(status.code, status.detail, facman::core::OutcomeKind::internal_error));
    }
    if (observation) observation->complete();
    return facman::core::Result<void>::success();
}

facman::core::Result<ResourceSelection> inspect_selected_resources(const std::string& explicit_pack)
{
    using Output = facman::core::Result<ResourceSelection>;
    const char* environment = std::getenv("FACMAN_RESOURCE_PACK");
    const std::string selected = !explicit_pack.empty() ? explicit_pack : environment ? environment : "";
    ResourceSelection result;
    if (!selected.empty()) {
        auto inspected = detail::inspect_open_standalone_pack(
            std::filesystem::u8path(selected));
        if (!inspected) return Output::failure(inspected.error());
        result.standalone.emplace(inspected.take_value());
        result.inspection = result.standalone->inspection;
    } else {
        auto inspected = inspect_runtime_resources();
        if (!inspected) return Output::failure(inspected.error());
        result.product.emplace(inspected.take_value());
        result.inspection = result.product->inspection;
    }
    return Output::success(std::move(result));
}
std::string absolute_export_destination_utf8(const std::string& destination)
{
    return std::filesystem::absolute(std::filesystem::u8path(destination)).u8string();
}
facman::core::Result<void> export_selected_resources(
    const ResourceSelection& selected, const std::string& destination,
    facman::archive::ExtractionObservation* observation,
    const facman::archive::ExtractionCheckpoint& checkpoint)
{
    if (selected.product) return export_product_resources(*selected.product, std::filesystem::u8path(destination), {}, checkpoint, observation);
    if (selected.standalone) return detail::export_open_standalone_pack(
        *selected.standalone, std::filesystem::u8path(destination), observation, checkpoint);
    return export_pack(selected.inspection.path, std::filesystem::u8path(destination), observation, checkpoint);
}
}
