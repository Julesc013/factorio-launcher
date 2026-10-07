// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_APPS_CLI_CLI_TEXT_H
#define FACMAN_APPS_CLI_CLI_TEXT_H

#include <algorithm>
#include <cctype>
#include <string>
#include <vector>

namespace facman::cli {

inline bool flag(const std::vector<std::string>& args, const std::string& value)
{
    if (std::find(args.begin(), args.end(), value) != args.end()) return true;
    if (value != "--json") return false;
    for (std::size_t index = 0; index + 1 < args.size(); ++index) {
        if (args[index] == "--format" && args[index + 1] == "json") return true;
    }
    return false;
}

inline std::string option(const std::vector<std::string>& args, const std::string& name, const std::string& fallback = {})
{
    for (std::size_t index = 0; index + 1 < args.size(); ++index) if (args[index] == name) return args[index + 1];
    return fallback;
}

inline std::string slugify(const std::string& value)
{
    std::string output;
    bool dash = false;
    for (unsigned char ch : value) {
        if (std::isalnum(ch)) {
            output.push_back(static_cast<char>(std::tolower(ch)));
            dash = false;
        } else if (!output.empty() && !dash) {
            output.push_back('-');
            dash = true;
        }
    }
    while (!output.empty() && output.back() == '-') output.pop_back();
    return output.empty() ? "item" : output;
}

} // namespace facman::cli

#endif
