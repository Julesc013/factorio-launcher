// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_RUNTIME_WORKSPACE_FL_WORKSPACE_IO_INTERNAL_H
#define FACMAN_RUNTIME_WORKSPACE_FL_WORKSPACE_IO_INTERNAL_H

#include "fl_json.h"
#include "fl_result.h"

#include <cstdint>
#include <filesystem>
#include <string>

namespace facman::workspace::persistence_detail {

facman::core::Result<std::string> read_bounded(
    const std::filesystem::path& path,
    std::uint64_t maximum_bytes = 1024ULL * 1024ULL);

facman::core::Result<std::filesystem::path> write_new_durable(
    const std::filesystem::path& path,
    const std::string& text);

facman::core::Result<facman::core::json::Value> parse_record(
    const std::filesystem::path& path);

facman::core::Result<std::string> required_string(
    const facman::core::json::Value& object,
    const char* key,
    const std::filesystem::path& path);

std::string optional_string(
    const facman::core::json::Value& object,
    const char* key,
    const std::string& fallback = {});

} // namespace facman::workspace::persistence_detail

#endif
