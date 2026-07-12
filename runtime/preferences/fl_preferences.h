// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_RUNTIME_PREFERENCES_H
#define FACMAN_RUNTIME_PREFERENCES_H

#include "fl_result.h"

#include <cstdint>
#include <filesystem>
#include <string>
#include <vector>

namespace facman::preferences {

struct Preferences {
    std::string preferred_workspace;
    std::string preferred_transport;
    std::string default_instance_template;
    std::string default_launch_profile;
    std::string display_color_policy;
    std::uint32_t tui_page_size = 0;
    std::uint32_t command_timeout_seconds = 0;
    std::string backup_destination;
    std::uint32_t backup_keep_last = 0;
    std::vector<std::string> discovery_providers;
    std::vector<std::string> discovery_roots;
};

struct Document {
    std::filesystem::path path;
    Preferences values;
    bool present = false;
};

facman::core::Result<std::filesystem::path> preferences_path();
facman::core::Result<Document> inspect();
facman::core::Result<Document> inspect_at(const std::filesystem::path& path);
facman::core::Result<Preferences> decode(const std::string& text);
facman::core::Result<void> validate(const Preferences& preferences);
std::string encode(const Preferences& preferences);
facman::core::Result<std::string> report(
    const char* operation,
    const Preferences* proposed = nullptr,
    bool reset = false);
facman::core::Result<std::string> report_at(
    const std::filesystem::path& path,
    const char* operation,
    const Preferences* proposed = nullptr,
    bool reset = false);
facman::core::Result<std::string> apply(
    const std::filesystem::path& workspace,
    const Preferences* proposed,
    bool reset);
facman::core::Result<std::string> apply_at(
    const std::filesystem::path& workspace,
    const std::filesystem::path& path,
    const Preferences* proposed,
    bool reset);

} // namespace facman::preferences

#endif
