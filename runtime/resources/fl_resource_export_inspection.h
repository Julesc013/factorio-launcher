// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#ifndef FACMAN_RESOURCE_EXPORT_INSPECTION_H
#define FACMAN_RESOURCE_EXPORT_INSPECTION_H
#include "fl_result.h"
#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>
namespace facman::resources {
namespace detail {
struct DestinationObservation {
    std::string state = "unavailable";
    std::string kind = "unknown";
    std::uint64_t device = 0;
    std::uint64_t object = 0;
    std::string detail;
};
// Components are validated once; implementations open each ancestor relative
// to its held parent, never enumerate directories or read file contents.
DestinationObservation observe_export_path(const std::filesystem::path& root,
    const std::vector<std::filesystem::path>& components);
}
facman::core::Result<std::string> inspect_export_destination(const std::string& destination);
}
#endif
