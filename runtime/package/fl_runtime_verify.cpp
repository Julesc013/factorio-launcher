#include "fl_runtime_verify.h"

#include "fl_runtime_locator.h"
#include "fl_sha256.h"

#include <algorithm>
#include <cctype>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <set>
#include <sstream>
#include <string>

#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#endif

namespace fs = std::filesystem;

namespace {

fs::path g_package_root;
std::string g_package_root_text;

void set_detail(char* detail, size_t capacity, const std::string& value)
{
    if (detail == nullptr || capacity == 0) {
        return;
    }
    const size_t count = std::min(capacity - 1, value.size());
    std::memcpy(detail, value.data(), count);
    detail[count] = '\0';
}

bool is_hex_digest(const std::string& value)
{
    return value.size() == 64 && std::all_of(value.begin(), value.end(), [](unsigned char ch) {
        return std::isxdigit(ch) != 0;
    });
}

bool is_safe_relative(const std::string& value)
{
    if (value.empty() || value.find('\\') != std::string::npos || value.find(':') != std::string::npos) {
        return false;
    }
    fs::path path = fs::u8path(value);
    if (path.is_absolute()) {
        return false;
    }
    for (const fs::path& part : path) {
        if (part == "." || part == ".." || part.empty()) {
            return false;
        }
    }
    return true;
}

bool is_reparse_or_symlink(const fs::path& path)
{
    std::error_code error;
    if (fs::is_symlink(fs::symlink_status(path, error))) {
        return true;
    }
#ifdef _WIN32
    DWORD attributes = GetFileAttributesW(path.c_str());
    return attributes != INVALID_FILE_ATTRIBUTES && (attributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0;
#else
    return false;
#endif
}

bool is_within(const fs::path& root, const fs::path& candidate)
{
    std::error_code error;
    fs::path relative = fs::relative(candidate, root, error);
    if (error || relative.empty() || relative.is_absolute()) {
        return false;
    }
    for (const fs::path& part : relative) {
        if (part == "..") {
            return false;
        }
    }
    return true;
}

bool collect_package_files(
    const fs::path& root,
    std::set<std::string>& files,
    std::string& error)
{
    std::error_code walk_error;
    for (fs::recursive_directory_iterator iterator(root, walk_error), end; iterator != end; iterator.increment(walk_error)) {
        if (walk_error) {
            error = "cannot enumerate package root: " + walk_error.message();
            return false;
        }
        const fs::path path = iterator->path();
        if (is_reparse_or_symlink(path)) {
            error = "package contains a link or reparse point: " + path.filename().string();
            return false;
        }
        if (!iterator->is_regular_file()) {
            continue;
        }
        std::string relative = path.lexically_relative(root).generic_string();
        if (relative == "manifest/hashes.sha256" || path.extension() == ".sig") {
            continue;
        }
        files.insert(relative);
    }
    if (walk_error) {
        error = "cannot enumerate package root: " + walk_error.message();
        return false;
    }
    return true;
}

std::string manifest_string(const fs::path& path, const std::string& key)
{
    std::ifstream input(path, std::ios::binary);
    std::string line;
    const std::string prefix = key + " = \"";
    while (std::getline(input, line)) {
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }
        if (line.rfind(prefix, 0) == 0 && line.size() > prefix.size() && line.back() == '"') {
            return line.substr(prefix.size(), line.size() - prefix.size() - 1);
        }
    }
    return {};
}

bool target_identity_matches(const fs::path& manifest, std::string& error)
{
    const std::string profile = manifest_string(manifest, "profile_id");
    const std::string target_os = manifest_string(manifest, "target_os");
    const std::string target_arch = manifest_string(manifest, "target_arch");
    const std::string linkage = manifest_string(manifest, "linkage_model");
    if (profile == "windows_portable_cli_x64") {
        if (target_os != "windows" || target_arch != "x64" || linkage != "static_first") {
            error = "package target or linkage identity does not match windows_portable_cli_x64";
            return false;
        }
#ifndef _WIN32
        error = "Windows package cannot run on this operating system";
        return false;
#endif
#if !defined(_M_X64) && !defined(__x86_64__)
        error = "x64 package cannot run on this architecture";
        return false;
#endif
    }
    return true;
}

fs::path running_executable(const char* executable_path)
{
#ifdef _WIN32
    std::wstring buffer(32768, L'\0');
    DWORD length = GetModuleFileNameW(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    if (length > 0 && length < buffer.size()) {
        buffer.resize(length);
        return fs::path(buffer);
    }
#endif
    if (executable_path == nullptr || executable_path[0] == '\0') {
        return {};
    }
    std::error_code error;
    fs::path absolute = fs::absolute(fs::u8path(executable_path), error);
    return error ? fs::u8path(executable_path) : absolute;
}

} // namespace

extern "C" void fl_runtime_set_executable_path(const char* executable_path)
{
    fs::path executable = running_executable(executable_path);
    g_package_root = executable.empty() ? fs::path() : executable.parent_path().parent_path();
    g_package_root_text = g_package_root.empty() ? std::string() : g_package_root.u8string();
}

extern "C" const char* fl_runtime_package_root(void)
{
    return g_package_root_text.c_str();
}

extern "C" int fl_runtime_is_packaged(void)
{
    return !g_package_root.empty() && fs::is_regular_file(g_package_root / "manifest" / "package.v1.toml");
}

extern "C" int fl_runtime_verify_package(
    char* detail,
    size_t detail_capacity,
    size_t* files_verified)
{
    try {
    if (files_verified != nullptr) {
        *files_verified = 0;
    }
    if (g_package_root.empty()) {
        set_detail(detail, detail_capacity, "package root is not configured");
        return 0;
    }

    const fs::path required[] = {
        g_package_root / "manifest" / "package.v1.toml",
        g_package_root / "manifest" / "components.v1.json",
        g_package_root / "manifest" / "hashes.sha256",
        g_package_root / "contracts" / "schema",
        g_package_root / "content" / "factorio",
    };
    for (const fs::path& path : required) {
        if (!fs::exists(path)) {
            set_detail(detail, detail_capacity, "missing required package path: " + path.lexically_relative(g_package_root).generic_string());
            return 0;
        }
    }
    std::string identity_error;
    if (!target_identity_matches(required[0], identity_error)) {
        set_detail(detail, detail_capacity, identity_error);
        return 0;
    }

    std::error_code error;
    const fs::path canonical_root = fs::canonical(g_package_root, error);
    if (error) {
        set_detail(detail, detail_capacity, "cannot resolve package root: " + error.message());
        return 0;
    }

    std::ifstream input(g_package_root / "manifest" / "hashes.sha256", std::ios::binary);
    if (!input) {
        set_detail(detail, detail_capacity, "cannot open manifest/hashes.sha256");
        return 0;
    }

    std::set<std::string> declared;
    std::string line;
    size_t line_number = 0;
    while (std::getline(input, line)) {
        ++line_number;
        if (!line.empty() && line.back() == '\r') {
            line.pop_back();
        }
        if (line.size() < 67 || line.substr(64, 2) != "  ") {
            set_detail(detail, detail_capacity, "invalid hash manifest line " + std::to_string(line_number));
            return 0;
        }
        std::string expected = line.substr(0, 64);
        std::string relative = line.substr(66);
        if (!is_hex_digest(expected) || !is_safe_relative(relative) || relative == "manifest/hashes.sha256") {
            set_detail(detail, detail_capacity, "unsafe or invalid hash manifest line " + std::to_string(line_number));
            return 0;
        }
        if (!declared.insert(relative).second) {
            set_detail(detail, detail_capacity, "duplicate hash manifest path: " + relative);
            return 0;
        }

        const fs::path candidate = g_package_root / fs::u8path(relative);
        if (!fs::is_regular_file(candidate) || is_reparse_or_symlink(candidate)) {
            set_detail(detail, detail_capacity, "missing or unsafe hashed file: " + relative);
            return 0;
        }
        const fs::path canonical_candidate = fs::canonical(candidate, error);
        if (error || !is_within(canonical_root, canonical_candidate)) {
            set_detail(detail, detail_capacity, "hashed file escapes package root: " + relative);
            return 0;
        }
        std::string actual = facman::base::sha256_hex_file(candidate);
        std::transform(expected.begin(), expected.end(), expected.begin(), [](unsigned char ch) {
            return static_cast<char>(std::tolower(ch));
        });
        if (actual != expected) {
            set_detail(detail, detail_capacity, "SHA-256 mismatch: " + relative);
            return 0;
        }
    }

    std::set<std::string> actual_files;
    std::string collect_error;
    if (!collect_package_files(g_package_root, actual_files, collect_error)) {
        set_detail(detail, detail_capacity, collect_error);
        return 0;
    }
    if (actual_files != declared) {
        set_detail(detail, detail_capacity, "hash manifest does not close over the package file set");
        return 0;
    }
    if (files_verified != nullptr) {
        *files_verified = declared.size();
    }
    set_detail(detail, detail_capacity, "package contents match the unsigned SHA-256 manifest");
    return 1;
    } catch (const std::exception& error) {
        set_detail(detail, detail_capacity, std::string("package verification error: ") + error.what());
        return 0;
    } catch (...) {
        set_detail(detail, detail_capacity, "package verification error: unknown failure");
        return 0;
    }
}
