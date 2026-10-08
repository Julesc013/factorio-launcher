// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#ifndef FACMAN_FACTORIO_ROUTING_INI_DELTA_H
#define FACMAN_FACTORIO_ROUTING_INI_DELTA_H
#include <algorithm>
#include <cctype>
#include <string>
#include <utility>
#include <vector>

namespace facman::factorio::instance::detail {
struct RoutingIniDelta {
    bool ok = false;
    std::string bytes;
    std::string refusal;
};

inline std::string ini_trim(const std::string& value)
{
    const auto first = value.find_first_not_of(" \t\r\n");
    return first == std::string::npos ? std::string() : value.substr(first, value.find_last_not_of(" \t\r\n") - first + 1U);
}

inline std::string ini_lower(std::string value)
{
    for (char& byte : value) byte = static_cast<char>(std::tolower(static_cast<unsigned char>(byte)));
    return value;
}

// Plan only. Preserve every byte outside the two routing-value spans, or add
// missing exact keys at the end of the first [path] section. Ambiguous input
// remains unchanged for explicit repair; this function grants no file authority.
inline RoutingIniDelta routing_ini_delta(const std::string& original,
    const std::string& read_data, const std::string& write_data)
{
    const auto refuse = [&](const char* reason) { return RoutingIniDelta {false, original, reason}; };
    if (original.size() > 65536U || original.find('\0') != std::string::npos ||
        original.compare(0U, 3U, "\xEF\xBB\xBF") == 0 ||
        read_data.empty() || write_data.empty() || read_data.find_first_of("\r\n\0", 0U, 3U) != std::string::npos ||
        write_data.find_first_of("\r\n\0", 0U, 3U) != std::string::npos)
        return refuse("configuration_routing_bytes_unsupported");
    for (std::size_t i = 0U; i < original.size(); ++i) {
        if (original[i] == '\r' && (i + 1U == original.size() || original[i + 1U] != '\n'))
            return refuse("configuration_routing_bare_cr_unsupported");
    }
    struct Edit { std::size_t first, count; std::string bytes; bool addition = false; };
    std::vector<Edit> edits;
    bool in_path = false, first_path = false, found_read = false, found_write = false;
    bool insertion_bound = false;
    std::size_t insertion = original.size();
    std::string eol = "\n";
    for (std::size_t offset = 0U; offset < original.size();) {
        const auto newline = original.find('\n', offset);
        const auto end = newline == std::string::npos ? original.size() : newline + 1U;
        const std::string line = original.substr(offset, end - offset);
        const std::string current = ini_trim(line);
        if (!first_path && newline != std::string::npos)
            eol = newline > offset && original[newline - 1U] == '\r' ? "\r\n" : "\n";
        if (!current.empty() && current.front() != ';' && current.front() != '#') {
            if (current.front() == '[' && current.back() != ']')
                return refuse("configuration_routing_section_ambiguous");
            if (current.front() == '[' && current.back() == ']') {
                if (in_path && first_path && !insertion_bound) { insertion = offset; insertion_bound = true; }
                const std::string section = ini_trim(current.substr(1U, current.size() - 2U));
                if (section.empty() || section.find_first_of("[]") != std::string::npos)
                    return refuse("configuration_routing_section_ambiguous");
                if (section == "path" && first_path)
                    return refuse("configuration_routing_repeated_path_section");
                if (ini_lower(section) == "path" && section != "path") return refuse("configuration_routing_ambiguous_case");
                in_path = section == "path";
                if (in_path && !first_path) first_path = true;
            } else if (in_path) {
                const auto separator = line.find('=');
                if (separator == std::string::npos) return refuse("configuration_routing_malformed_path_section");
                const std::string key = ini_trim(line.substr(0U, separator));
                const std::string lower = ini_lower(key);
                if ((lower == "read-data" || lower == "write-data") && key != lower)
                    return refuse("configuration_routing_ambiguous_case");
                if (key == "read-data" || key == "write-data") {
                    bool& found = key == "read-data" ? found_read : found_write;
                    if (found) return refuse("configuration_routing_duplicate_key");
                    found = true;
                    const auto first = line.find_first_not_of(" \t\r\n", separator + 1U);
                    const auto last = line.find_last_not_of(" \t\r\n");
                    const auto value_start = first == std::string::npos ? separator + 1U : first;
                    const auto value_count = first == std::string::npos || last < first ? 0U : last - first + 1U;
                    const std::string prior_value = line.substr(value_start, value_count);
                    for (std::size_t i = 0U; i < prior_value.size(); ++i) {
                        if ((prior_value[i] == ';' || prior_value[i] == '#') &&
                            (i == 0U || prior_value[i - 1U] == ' ' || prior_value[i - 1U] == '\t'))
                            return refuse("configuration_routing_inline_comment_ambiguous");
                    }
                    edits.push_back({offset + value_start, value_count, key == "read-data" ? read_data : write_data});
                }
            }
        }
        offset = end;
    }
    std::string additions;
    if (!found_read) additions += "read-data=" + read_data + eol;
    if (!found_write) additions += "write-data=" + write_data + eol;
    if (!additions.empty()) {
        if (!first_path) additions = "[path]" + eol + additions;
        if (insertion != 0U && original[insertion - 1U] != '\n') additions = eol + additions;
        edits.push_back({insertion, 0U, additions, true});
    }
    std::sort(edits.begin(), edits.end(), [](const Edit& a, const Edit& b) { return a.first != b.first ? a.first > b.first : a.addition && !b.addition; });
    std::string result = original;
    for (const auto& edit : edits) result.replace(edit.first, edit.count, edit.bytes);
    if (result.size() > 65536U) return refuse("configuration_routing_result_limit");
    return {true, std::move(result), {}};
}
} // namespace facman::factorio::instance::detail
#endif
