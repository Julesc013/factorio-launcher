// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_FACTORIO_DISCOVERY_SERVICE_H
#define FACMAN_FACTORIO_DISCOVERY_SERVICE_H

#include <filesystem>
#include <string>
#include <vector>

namespace facman::factorio::discovery::internal {

struct SearchRoot {
    std::filesystem::path path;
    std::string provider_id;
    std::string source;
    std::string ownership;
    std::vector<std::string> evidence;
};

std::string comparison_key(const std::filesystem::path& path);
void append_unique_path(std::vector<std::filesystem::path>& paths, const std::filesystem::path& candidate);
void append_search_root(
    std::vector<SearchRoot>& roots,
    const std::filesystem::path& path,
    std::string provider_id,
    std::string source,
    std::string ownership,
    std::vector<std::string> evidence = {});
std::vector<std::filesystem::path> environment_paths(const char* name);
std::filesystem::path home_directory();
bool defaults_disabled();

void add_explicit_provider_roots(
    std::vector<SearchRoot>& roots,
    const std::vector<std::filesystem::path>& explicit_roots);
void add_windows_provider_roots(std::vector<SearchRoot>& roots);
void add_linux_provider_roots(std::vector<SearchRoot>& roots);
void add_macos_provider_roots(std::vector<SearchRoot>& roots);

std::vector<std::filesystem::path> steam_library_roots(const std::filesystem::path& steam_root);

} // namespace facman::factorio::discovery::internal

#endif
