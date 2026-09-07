// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "fl_resource_pack.h"
#include <cstdlib>
namespace facman::resources {
facman::core::Result<ResourceSelection> inspect_selected_resources(const std::string& explicit_pack)
{
    using Output = facman::core::Result<ResourceSelection>;
    const char* environment = std::getenv("FACMAN_RESOURCE_PACK");
    const std::string selected = !explicit_pack.empty() ? explicit_pack : environment ? environment : "";
    ResourceSelection result;
    if (!selected.empty()) {
        auto inspected = inspect_pack_utf8(selected);
        if (!inspected) return Output::failure(inspected.error());
        result.inspection = inspected.take_value();
    } else {
        auto inspected = inspect_runtime_resources();
        if (!inspected) return Output::failure(inspected.error());
        result.product.emplace(inspected.take_value());
        result.inspection = result.product->inspection;
    }
    return Output::success(std::move(result));
}
facman::core::Result<void> export_selected_resources(
    const ResourceSelection& selected, const std::string& destination)
{
    if (selected.product) return export_product_resources(*selected.product, std::filesystem::u8path(destination));
    return export_pack(selected.inspection.path, std::filesystem::u8path(destination));
}
}
