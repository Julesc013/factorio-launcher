// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_workspace_io_internal.h"

#include "fl_file_io.h"

#include <utility>

namespace facman::workspace::persistence_detail {
namespace fs = std::filesystem;
namespace json = facman::core::json;

namespace {

template <typename T>
facman::core::Result<T> failure(
    std::string code,
    std::string message,
    const fs::path& path = {})
{
    return facman::core::Result<T>::failure(
        {std::move(code), std::move(message), facman::platform::path_to_utf8(path)});
}

} // namespace

facman::core::Result<std::string> read_bounded(
    const fs::path& path,
    std::uint64_t maximum_bytes)
{
    facman::platform::StableInputFile input;
    const auto opened = input.open_no_follow(path);
    if (!opened.ok()) return failure<std::string>(opened.code, opened.detail, path);
    if (input.size() > maximum_bytes) {
        return failure<std::string>(
            "workspace_record_too_large",
            "persistent record exceeds its byte budget",
            path);
    }
    std::string text(static_cast<std::size_t>(input.size()), '\0');
    std::uint64_t offset = 0U;
    while (offset < input.size()) {
        const std::size_t read = input.read_at(
            offset,
            text.data() + static_cast<std::size_t>(offset),
            static_cast<std::size_t>(input.size() - offset));
        if (read == 0U) {
            return failure<std::string>(
                "workspace_record_read_failed", "short persistent record read", path);
        }
        offset += read;
    }
    const auto stable = input.revalidate();
    if (!stable.ok()) return failure<std::string>(stable.code, stable.detail, path);
    return facman::core::Result<std::string>::success(std::move(text));
}

facman::core::Result<fs::path> write_new_durable(
    const fs::path& path,
    const std::string& text)
{
    std::error_code error;
    fs::create_directories(path.parent_path(), error);
    if (error) {
        return failure<fs::path>(
            "workspace_directory_create_failed", error.message(), path.parent_path());
    }
    facman::platform::DurableOutputFile output;
    auto status = output.create_exclusive(path, 1024ULL * 1024ULL);
    if (!status.ok()) return failure<fs::path>(status.code, status.detail, path);
    if (output.write_at(0U, text.data(), text.size()) != text.size()) {
        output.close_without_flush();
        facman::platform::StableInputFile created;
        if (created.open_no_follow(path).ok()) {
            (void)facman::platform::remove_exact_object(path, created.identity());
        }
        return failure<fs::path>(
            "workspace_record_write_failed", "short persistent record write", path);
    }
    status = output.flush_file_and_parent();
    if (!status.ok()) {
        output.close_without_flush();
        facman::platform::StableInputFile created;
        if (created.open_no_follow(path).ok()) {
            (void)facman::platform::remove_exact_object(path, created.identity());
        }
        return failure<fs::path>(status.code, status.detail, path);
    }
    return facman::core::Result<fs::path>::success(path);
}

facman::core::Result<json::Value> parse_record(const fs::path& path)
{
    auto text = read_bounded(path);
    if (!text) return failure<json::Value>(text.error().code, text.error().message, path);
    json::Limits limits;
    limits.maximum_bytes = 1024U * 1024U;
    limits.maximum_depth = 24U;
    limits.maximum_nodes = 20000U;
    limits.maximum_string_bytes = 256U * 1024U;
    auto parsed = json::parse(text.value(), limits);
    if (!parsed) return failure<json::Value>(parsed.error().code, parsed.error().message, path);
    if (!parsed.value().is_object()) {
        return failure<json::Value>(
            "workspace_record_type", "persistent record must be a JSON object", path);
    }
    return parsed;
}

facman::core::Result<std::string> required_string(
    const json::Value& object,
    const char* key,
    const fs::path& path)
{
    const json::Value* value = object.find(key);
    if (value == nullptr) {
        return failure<std::string>(
            "workspace_record_missing_field", std::string("missing field: ") + key, path);
    }
    auto result = value->string_value();
    if (!result) {
        return failure<std::string>(
            "workspace_record_field_type", std::string("field must be a string: ") + key, path);
    }
    if (result.value().empty()) {
        return failure<std::string>(
            "workspace_record_empty_field", std::string("field must not be empty: ") + key, path);
    }
    return result;
}

std::string optional_string(
    const json::Value& object,
    const char* key,
    const std::string& fallback)
{
    const json::Value* value = object.find(key);
    if (value == nullptr || !value->is_string()) return fallback;
    auto result = value->string_value();
    return result ? result.value() : fallback;
}

} // namespace facman::workspace::persistence_detail
