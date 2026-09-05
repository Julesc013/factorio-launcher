// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_APPS_CLI_CLI_TEXT_H
#define FACMAN_APPS_CLI_CLI_TEXT_H

#include <cctype>
#include <string>

namespace facman::cli {

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
