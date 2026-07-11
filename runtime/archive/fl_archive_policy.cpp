// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_archive_policy.h"

#include <algorithm>
#include <cctype>
#include <limits>
#include <sstream>
#include <unordered_map>

namespace facman::archive {

Limits ModArchivePolicy::limits()
{
    Limits limits;
    limits.maximum_archive_bytes = 2ULL * 1024ULL * 1024ULL * 1024ULL;
    limits.maximum_entry_count = 4096;
    limits.maximum_entry_expanded_bytes = 2ULL * 1024ULL * 1024ULL * 1024ULL;
    limits.maximum_total_expanded_bytes = 4ULL * 1024ULL * 1024ULL * 1024ULL;
    limits.maximum_directory_depth = 32;
    return limits;
}

Limits SaveArchivePolicy::limits()
{
    Limits limits;
    limits.maximum_entry_count = 2048;
    limits.maximum_entry_compressed_bytes = 4ULL * 1024ULL * 1024ULL * 1024ULL;
    limits.maximum_entry_expanded_bytes = 8ULL * 1024ULL * 1024ULL * 1024ULL;
    limits.maximum_total_expanded_bytes = 8ULL * 1024ULL * 1024ULL * 1024ULL;
    limits.maximum_directory_depth = 32;
    return limits;
}

Limits InstanceTransferPolicy::limits()
{
    Limits limits;
    limits.maximum_entry_count = 20000;
    limits.maximum_total_expanded_bytes = 12ULL * 1024ULL * 1024ULL * 1024ULL;
    limits.maximum_read_milliseconds = 120000;
    return limits;
}

Limits DiagnosticBundlePolicy::limits()
{
    Limits limits;
    limits.maximum_archive_bytes = 32ULL * 1024ULL * 1024ULL;
    limits.maximum_entry_count = 512;
    limits.maximum_entry_compressed_bytes = 2ULL * 1024ULL * 1024ULL;
    limits.maximum_entry_expanded_bytes = 2ULL * 1024ULL * 1024ULL;
    limits.maximum_total_expanded_bytes = 24ULL * 1024ULL * 1024ULL;
    limits.maximum_compression_ratio = 200;
    limits.maximum_directory_depth = 16;
    limits.maximum_read_milliseconds = 10000;
    return limits;
}

Limits PackageArchivePolicy::limits()
{
    Limits limits;
    limits.maximum_entry_count = 100000;
    limits.maximum_path_bytes = 2048;
    limits.maximum_directory_depth = 128;
    limits.maximum_read_milliseconds = 120000;
    return limits;
}

namespace {

Status refuse(const char* code, const std::string& detail)
{
    return Status::failure(code, detail);
}

bool decode_utf8(const std::string& text, std::vector<std::uint32_t>& output)
{
    output.clear();
    for (std::size_t index = 0; index < text.size();) {
        const unsigned char first = static_cast<unsigned char>(text[index]);
        std::uint32_t value = 0;
        std::size_t count = 0;
        if (first <= 0x7f) {
            value = first;
            count = 1;
        } else if ((first & 0xe0) == 0xc0) {
            value = first & 0x1f;
            count = 2;
        } else if ((first & 0xf0) == 0xe0) {
            value = first & 0x0f;
            count = 3;
        } else if ((first & 0xf8) == 0xf0) {
            value = first & 0x07;
            count = 4;
        } else {
            return false;
        }
        if (index + count > text.size()) {
            return false;
        }
        for (std::size_t offset = 1; offset < count; ++offset) {
            const unsigned char next = static_cast<unsigned char>(text[index + offset]);
            if ((next & 0xc0) != 0x80) {
                return false;
            }
            value = (value << 6) | (next & 0x3f);
        }
        if ((count == 2 && value < 0x80) || (count == 3 && value < 0x800) ||
            (count == 4 && value < 0x10000) || value > 0x10ffff ||
            (value >= 0xd800 && value <= 0xdfff)) {
            return false;
        }
        output.push_back(value);
        index += count;
    }
    return true;
}

void append_key_codepoint(std::ostringstream& out, std::uint32_t value)
{
    out << std::hex << value << '/';
}

bool latin_decomposition(
    std::uint32_t value,
    std::uint32_t& base,
    std::uint32_t& mark)
{
    static const std::unordered_map<std::uint32_t, std::pair<std::uint32_t, std::uint32_t>> values = {
        {0x00c0, {'A', 0x0300}}, {0x00c1, {'A', 0x0301}},
        {0x00c4, {'A', 0x0308}}, {0x00c5, {'A', 0x030a}},
        {0x00c7, {'C', 0x0327}}, {0x00c8, {'E', 0x0300}},
        {0x00c9, {'E', 0x0301}}, {0x00cc, {'I', 0x0300}},
        {0x00cd, {'I', 0x0301}}, {0x00d1, {'N', 0x0303}},
        {0x00d2, {'O', 0x0300}}, {0x00d3, {'O', 0x0301}},
        {0x00d6, {'O', 0x0308}}, {0x00d9, {'U', 0x0300}},
        {0x00da, {'U', 0x0301}}, {0x00dc, {'U', 0x0308}},
        {0x00dd, {'Y', 0x0301}}, {0x00e0, {'a', 0x0300}},
        {0x00e1, {'a', 0x0301}}, {0x00e4, {'a', 0x0308}},
        {0x00e5, {'a', 0x030a}}, {0x00e7, {'c', 0x0327}},
        {0x00e8, {'e', 0x0300}}, {0x00e9, {'e', 0x0301}},
        {0x00ec, {'i', 0x0300}}, {0x00ed, {'i', 0x0301}},
        {0x00f1, {'n', 0x0303}}, {0x00f2, {'o', 0x0300}},
        {0x00f3, {'o', 0x0301}}, {0x00f6, {'o', 0x0308}},
        {0x00f9, {'u', 0x0300}}, {0x00fa, {'u', 0x0301}},
        {0x00fc, {'u', 0x0308}}, {0x00fd, {'y', 0x0301}},
        {0x00ff, {'y', 0x0308}},
    };
    const auto found = values.find(value);
    if (found == values.end()) {
        return false;
    }
    base = found->second.first;
    mark = found->second.second;
    return true;
}

std::uint32_t simple_case_fold(std::uint32_t value)
{
    if (value >= 'A' && value <= 'Z') {
        return value + ('a' - 'A');
    }
    if ((value >= 0x00c0 && value <= 0x00d6) ||
        (value >= 0x00d8 && value <= 0x00de)) {
        return value + 0x20;
    }
    return value;
}

std::string unicode_key(const std::vector<std::uint32_t>& points, bool normalize)
{
    std::ostringstream out;
    for (std::uint32_t point : points) {
        if (normalize) {
            std::uint32_t base = 0;
            std::uint32_t mark = 0;
            if (latin_decomposition(point, base, mark)) {
                append_key_codepoint(out, simple_case_fold(base));
                append_key_codepoint(out, mark);
                continue;
            }
        }
        append_key_codepoint(out, simple_case_fold(point));
    }
    return out.str();
}

std::string ascii_lower(std::string text)
{
    std::transform(text.begin(), text.end(), text.begin(), [](unsigned char value) {
        return static_cast<char>(std::tolower(value));
    });
    return text;
}

bool windows_reserved_segment(const std::string& segment)
{
    std::string lowered = ascii_lower(segment);
    const std::size_t dot = lowered.find('.');
    const std::string stem = lowered.substr(0, dot);
    if (stem == "con" || stem == "prn" || stem == "aux" || stem == "nul") {
        return true;
    }
    if (stem.size() == 4 && (stem.rfind("com", 0) == 0 || stem.rfind("lpt", 0) == 0) &&
        stem[3] >= '1' && stem[3] <= '9') {
        return true;
    }
    return false;
}

std::vector<std::string> split_segments(const std::string& path)
{
    std::vector<std::string> segments;
    std::size_t begin = 0;
    while (begin <= path.size()) {
        const std::size_t slash = path.find('/', begin);
        segments.push_back(path.substr(begin, slash == std::string::npos ? slash : slash - begin));
        if (slash == std::string::npos) {
            break;
        }
        begin = slash + 1;
    }
    return segments;
}

} // namespace

Status Status::failure(std::string code, std::string detail)
{
    Status status;
    status.code = std::move(code);
    status.detail = std::move(detail);
    return status;
}

Status validate_archive_path(
    const std::string& path,
    bool directory,
    const Limits& limits,
    PathKeys& keys)
{
    if (path.empty()) {
        return refuse("archive_path_empty", "archive entry path is empty");
    }
    if (path.size() > limits.maximum_path_bytes) {
        return refuse("archive_path_too_long", path);
    }
    if (path.front() == '/' || path.front() == '\\') {
        return refuse("archive_path_absolute", path);
    }
    if (path.find('\\') != std::string::npos) {
        return refuse("archive_path_backslash", path);
    }
    if (path.find(':') != std::string::npos) {
        return refuse("archive_path_ads_or_drive", path);
    }
    if (path.find('\0') != std::string::npos) {
        return refuse("archive_path_nul", path);
    }

    std::string canonical = path;
    if (directory && canonical.back() == '/') {
        canonical.pop_back();
    }
    if (canonical.empty() || (!directory && path.back() == '/')) {
        return refuse("archive_path_type_mismatch", path);
    }

    const std::vector<std::string> segments = split_segments(canonical);
    if (segments.size() > limits.maximum_directory_depth + 1) {
        return refuse("archive_path_depth_exceeded", path);
    }
    std::string parent;
    keys.parents.clear();
    for (const std::string& segment : segments) {
        if (segment.empty()) {
            return refuse("archive_path_empty_segment", path);
        }
        if (segment == "." || segment == "..") {
            return refuse("archive_path_dot_segment", path);
        }
        if (segment.back() == '.' || segment.back() == ' ') {
            return refuse("archive_path_windows_trailing_character", path);
        }
        if (windows_reserved_segment(segment)) {
            return refuse("archive_path_windows_reserved", path);
        }
        if (!parent.empty()) {
            parent += '/';
        }
        parent += segment;
        if (parent != canonical) {
            keys.parents.push_back(parent);
        }
    }

    std::vector<std::uint32_t> points;
    if (!decode_utf8(canonical, points)) {
        return refuse("archive_path_invalid_utf8", path);
    }
    keys.exact = canonical;
    keys.case_folded = unicode_key(points, false);
    keys.normalization_folded = unicode_key(points, true);
    return Status::success();
}

Status validate_external_attributes(
    const std::string& path,
    bool directory,
    std::uint16_t version_made_by,
    std::uint32_t external_attributes)
{
    const std::uint8_t host = static_cast<std::uint8_t>(version_made_by >> 8);
    if (host != 3 && host != 19) {
        return Status::success();
    }
    const std::uint32_t mode = external_attributes >> 16;
    const std::uint32_t kind = mode & 0170000U;
    if (kind == 0) {
        return Status::success();
    }
    if (kind == 0120000U) {
        return refuse("archive_entry_symlink", path);
    }
    if (kind != 0100000U && kind != 0040000U) {
        return refuse("archive_entry_unsupported_file_type", path);
    }
    if ((kind == 0040000U) != directory) {
        return refuse("archive_entry_file_directory_mismatch", path);
    }
    return Status::success();
}

Status CollisionTracker::add(const PathKeys& keys, bool directory)
{
    if (!exact_.insert(keys.exact).second) {
        return refuse("archive_path_duplicate", keys.exact);
    }
    if (!case_folded_.insert(keys.case_folded).second) {
        return refuse("archive_path_case_collision", keys.exact);
    }
    if (!normalization_folded_.insert(keys.normalization_folded).second) {
        return refuse("archive_path_unicode_normalization_collision", keys.exact);
    }
    for (const std::string& parent : keys.parents) {
        if (files_.count(parent) != 0) {
            return refuse("archive_path_file_directory_collision", keys.exact);
        }
        directories_.insert(parent);
    }
    if (directory) {
        if (files_.count(keys.exact) != 0) {
            return refuse("archive_path_file_directory_collision", keys.exact);
        }
        directories_.insert(keys.exact);
    } else {
        if (directories_.count(keys.exact) != 0) {
            return refuse("archive_path_file_directory_collision", keys.exact);
        }
        files_.insert(keys.exact);
    }
    return Status::success();
}

Status enforce_entry_limits(
    std::uint64_t compressed_size,
    std::uint64_t expanded_size,
    std::uint64_t& total_expanded_size,
    const Limits& limits)
{
    if (compressed_size > limits.maximum_entry_compressed_bytes) {
        return refuse("archive_entry_compressed_limit", std::to_string(compressed_size));
    }
    if (expanded_size > limits.maximum_entry_expanded_bytes) {
        return refuse("archive_entry_expanded_limit", std::to_string(expanded_size));
    }
    if (compressed_size == 0) {
        if (expanded_size != 0) {
            return refuse("archive_compression_ratio_limit", "non-empty entry has zero compressed size");
        }
    } else {
        const std::uint64_t quotient = expanded_size / compressed_size;
        const std::uint64_t remainder = expanded_size % compressed_size;
        if (quotient > limits.maximum_compression_ratio ||
            (quotient == limits.maximum_compression_ratio && remainder != 0)) {
            return refuse("archive_compression_ratio_limit", std::to_string(quotient));
        }
    }
    if (expanded_size > std::numeric_limits<std::uint64_t>::max() - total_expanded_size ||
        total_expanded_size + expanded_size > limits.maximum_total_expanded_bytes) {
        return refuse("archive_total_expanded_limit", std::to_string(expanded_size));
    }
    total_expanded_size += expanded_size;
    return Status::success();
}

} // namespace facman::archive
