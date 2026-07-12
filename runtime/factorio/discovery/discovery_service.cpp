// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "discovery_service.h"

#include "fl_file_io.h"

#include <algorithm>
#include <cctype>
#include <cstdlib>

namespace facman::factorio::discovery::internal {
namespace fs = std::filesystem;

std::string comparison_key(const fs::path& path)
{
    std::string key = facman::platform::path_to_utf8(fs::absolute(path).lexically_normal());
#ifdef _WIN32
    std::transform(key.begin(), key.end(), key.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
#endif
    return key;
}

void append_unique_path(std::vector<fs::path>& paths, const fs::path& candidate)
{
    if (candidate.empty()) return;
    const fs::path normalized = fs::absolute(candidate).lexically_normal();
    for (const fs::path& existing : paths) {
        if (comparison_key(existing) == comparison_key(normalized)) return;
    }
    paths.push_back(normalized);
}

void append_search_root(
    std::vector<SearchRoot>& roots,
    const fs::path& path,
    std::string provider_id,
    std::string source,
    std::string ownership,
    std::vector<std::string> evidence)
{
    if (path.empty()) return;
    const std::string key = comparison_key(path);
    for (const SearchRoot& existing : roots) {
        if (comparison_key(existing.path) == key) return;
    }
    roots.push_back({
        fs::absolute(path).lexically_normal(),
        std::move(provider_id),
        std::move(source),
        std::move(ownership),
        std::move(evidence)});
}

std::vector<fs::path> environment_paths(const char* name)
{
    std::vector<fs::path> paths;
#ifdef _WIN32
    std::wstring wide_name;
    for (unsigned char ch : std::string(name)) wide_name.push_back(static_cast<wchar_t>(ch));
    const wchar_t* value = _wgetenv(wide_name.c_str());
    if (value == nullptr || *value == L'\0') return paths;
    const std::wstring text(value);
    std::size_t start = 0;
    for (;;) {
        const std::size_t end = text.find(L';', start);
        const std::wstring item = text.substr(start, end == std::wstring::npos ? std::wstring::npos : end - start);
        if (!item.empty()) append_unique_path(paths, fs::path(item));
        if (end == std::wstring::npos) break;
        start = end + 1;
    }
#else
    const char* value = std::getenv(name);
    if (value == nullptr || *value == '\0') return paths;
    const std::string text(value);
    std::size_t start = 0;
    for (;;) {
        const std::size_t end = text.find(':', start);
        const std::string item = text.substr(start, end == std::string::npos ? std::string::npos : end - start);
        if (!item.empty()) append_unique_path(paths, facman::platform::path_from_utf8(item));
        if (end == std::string::npos) break;
        start = end + 1;
    }
#endif
    return paths;
}

fs::path home_directory()
{
#ifdef _WIN32
    const wchar_t* value = _wgetenv(L"USERPROFILE");
    return value == nullptr ? fs::path() : fs::path(value);
#else
    const char* value = std::getenv("HOME");
    return value == nullptr ? fs::path() : facman::platform::path_from_utf8(value);
#endif
}

bool defaults_disabled()
{
    return std::getenv("FACMAN_DISCOVERY_DISABLE_DEFAULTS") != nullptr;
}

} // namespace facman::factorio::discovery::internal
