// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_path_safety.h"

#include <algorithm>
#include <atomic>
#include <cerrno>
#include <chrono>
#include <cctype>
#include <cstring>
#include <sstream>
#include <system_error>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <fcntl.h>
#include <unistd.h>
#ifdef __linux__
#include <sys/syscall.h>
#endif
#ifdef __APPLE__
#include <stdio.h>
#endif
#endif

namespace fs = std::filesystem;

namespace facman::base {
namespace {

bool relative_path_is_safe(const fs::path& path)
{
    if (path.empty() || path.is_absolute() || path.has_root_name() || path.has_root_directory()) {
        return false;
    }
    for (const fs::path& part : path) {
        if (part.empty() || part == "." || part == "..") {
            return false;
        }
    }
    return true;
}

bool path_is_below(const fs::path& root, const fs::path& candidate)
{
    fs::path relative = candidate.lexically_relative(root);
    if (relative.empty() || relative.is_absolute()) {
        return false;
    }
    for (const fs::path& part : relative) {
        if (part == "..") {
            return false;
        }
    }
    return true;
}

bool is_link_or_reparse_point(const fs::path& path)
{
    std::error_code error;
    fs::file_status status = fs::symlink_status(path, error);
    if (error) {
        return false;
    }
    if (fs::is_symlink(status)) {
        return true;
    }
#ifdef _WIN32
    DWORD attributes = GetFileAttributesW(path.c_str());
    return attributes != INVALID_FILE_ATTRIBUTES &&
        (attributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0;
#else
    return false;
#endif
}

bool existing_descendant_contains_link(
    const fs::path& root,
    const fs::path& candidate,
    std::string& detail)
{
    fs::path current = root;
    fs::path relative = candidate.lexically_relative(root);
    for (const fs::path& part : relative) {
        current /= part;
        std::error_code error;
        if (!fs::exists(current, error)) {
            break;
        }
        if (error) {
            detail = "could not inspect managed path component: " + current.string();
            return true;
        }
        if (is_link_or_reparse_point(current)) {
            detail = "managed path crosses a link or reparse point: " + current.string();
            return true;
        }
    }
    return false;
}

ManagedPathResult managed_path(
    const fs::path& workspace,
    const fs::path& area,
    const std::string& identifier,
    const std::string& suffix)
{
    ManagedPathResult result;
    if (!validate_identifier(identifier, result.detail)) {
        result.code = "invalid_identifier";
        return result;
    }
    if (!relative_path_is_safe(area)) {
        result.code = "unsafe_managed_path";
        result.detail = "internal managed area is not a safe relative path";
        return result;
    }

    std::error_code error;
    fs::path absolute_root = fs::absolute(workspace, error).lexically_normal();
    if (error) {
        result.code = "unsafe_managed_path";
        result.detail = "workspace root could not be resolved";
        return result;
    }
    fs::path candidate = (absolute_root / area / (identifier + suffix)).lexically_normal();
    if (!path_is_below(absolute_root, candidate)) {
        result.code = "unsafe_managed_path";
        result.detail = "managed path escaped the workspace root";
        return result;
    }

    fs::path canonical_root = fs::weakly_canonical(absolute_root, error);
    if (error) {
        canonical_root = absolute_root;
        error.clear();
    }
    fs::path canonical_candidate = fs::weakly_canonical(candidate, error);
    if (error || !path_is_below(canonical_root, canonical_candidate)) {
        result.code = "unsafe_managed_path";
        result.detail = "managed path does not remain below the canonical workspace root";
        return result;
    }
    if (existing_descendant_contains_link(absolute_root, candidate, result.detail)) {
        result.code = "unsafe_managed_path";
        return result;
    }

    result.path = candidate;
    return result;
}

std::string lowercase_ascii(std::string value)
{
    for (char& ch : value) {
        ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    }
    return value;
}

bool is_windows_reserved_name(const std::string& value)
{
    std::string base = lowercase_ascii(value.substr(0, value.find('.')));
    if (base == "con" || base == "prn" || base == "aux" || base == "nul") {
        return true;
    }
    if (base.size() == 4 && (base.rfind("com", 0) == 0 || base.rfind("lpt", 0) == 0)) {
        return base[3] >= '1' && base[3] <= '9';
    }
    return false;
}

std::string temporary_leaf(const fs::path& path)
{
    static std::atomic<unsigned long long> sequence {0};
    unsigned long long tick = static_cast<unsigned long long>(
        std::chrono::steady_clock::now().time_since_epoch().count());
    std::ostringstream out;
    out << "." << path.filename().string() << ".tmp-" << tick << "-" << sequence.fetch_add(1);
    return out.str();
}

std::string platform_error_message(unsigned long value)
{
#ifdef _WIN32
    return std::system_category().message(static_cast<int>(value));
#else
    return std::generic_category().message(static_cast<int>(value));
#endif
}

bool write_file_exclusive(
    const fs::path& path,
    const std::string& text,
    std::string& detail)
{
#ifdef _WIN32
    HANDLE handle = CreateFileW(
        path.c_str(),
        GENERIC_WRITE,
        0,
        nullptr,
        CREATE_NEW,
        FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT,
        nullptr);
    if (handle == INVALID_HANDLE_VALUE) {
        detail = "could not exclusively create temporary file: " +
            platform_error_message(GetLastError());
        return false;
    }
    std::size_t offset = 0;
    bool ok = true;
    while (offset < text.size()) {
        DWORD chunk = static_cast<DWORD>(std::min<std::size_t>(text.size() - offset, 0x7fffffff));
        DWORD written = 0;
        if (!WriteFile(handle, text.data() + offset, chunk, &written, nullptr) || written == 0) {
            detail = "could not write temporary file: " + platform_error_message(GetLastError());
            ok = false;
            break;
        }
        offset += written;
    }
    if (ok && !FlushFileBuffers(handle)) {
        detail = "could not flush temporary file: " + platform_error_message(GetLastError());
        ok = false;
    }
    if (!CloseHandle(handle) && ok) {
        detail = "could not close temporary file: " + platform_error_message(GetLastError());
        ok = false;
    }
    if (!ok) {
        DeleteFileW(path.c_str());
    }
    return ok;
#else
    int descriptor = ::open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
    if (descriptor < 0) {
        detail = "could not exclusively create temporary file: " +
            platform_error_message(static_cast<unsigned long>(errno));
        return false;
    }
    std::size_t offset = 0;
    bool ok = true;
    while (offset < text.size()) {
        ssize_t written = ::write(descriptor, text.data() + offset, text.size() - offset);
        if (written < 0 && errno == EINTR) continue;
        if (written <= 0) {
            detail = "could not write temporary file: " +
                platform_error_message(static_cast<unsigned long>(errno));
            ok = false;
            break;
        }
        offset += static_cast<std::size_t>(written);
    }
    if (ok && ::fsync(descriptor) != 0) {
        detail = "could not flush temporary file: " +
            platform_error_message(static_cast<unsigned long>(errno));
        ok = false;
    }
    if (::close(descriptor) != 0 && ok) {
        detail = "could not close temporary file: " +
            platform_error_message(static_cast<unsigned long>(errno));
        ok = false;
    }
    if (!ok) {
        ::unlink(path.c_str());
    }
    return ok;
#endif
}

bool rename_no_replace(
    const fs::path& source,
    const fs::path& destination,
    std::string& detail)
{
#ifdef _WIN32
    if (MoveFileExW(source.c_str(), destination.c_str(), MOVEFILE_WRITE_THROUGH)) {
        return true;
    }
    detail = "no-replace rename failed: " + platform_error_message(GetLastError());
    return false;
#elif defined(__APPLE__)
    if (::renamex_np(source.c_str(), destination.c_str(), RENAME_EXCL) == 0) {
        return true;
    }
    detail = "no-replace rename failed: " +
        platform_error_message(static_cast<unsigned long>(errno));
    return false;
#elif defined(__linux__) && defined(SYS_renameat2)
    constexpr unsigned int rename_no_replace_flag = 1;
    if (::syscall(
            SYS_renameat2,
            AT_FDCWD,
            source.c_str(),
            AT_FDCWD,
            destination.c_str(),
            rename_no_replace_flag) == 0) {
        return true;
    }
    int rename_error = errno;
    if (rename_error != ENOSYS && rename_error != EINVAL) {
        detail = "no-replace rename failed: " +
            platform_error_message(static_cast<unsigned long>(rename_error));
        return false;
    }
#endif

#ifndef _WIN32
    std::error_code status_error;
    if (fs::is_regular_file(source, status_error) && !status_error) {
        if (::link(source.c_str(), destination.c_str()) == 0) {
            if (::unlink(source.c_str()) == 0) {
                return true;
            }
            int unlink_error = errno;
            ::unlink(destination.c_str());
            detail = "could not remove temporary file after no-replace link: " +
                platform_error_message(static_cast<unsigned long>(unlink_error));
            return false;
        }
        detail = "no-replace link commit failed: " +
            platform_error_message(static_cast<unsigned long>(errno));
        return false;
    }
    detail = "atomic no-replace directory rename is unavailable on this platform/filesystem";
    return false;
#endif
}

} // namespace

bool validate_identifier(const std::string& value, std::string& detail)
{
    if (value.empty() || value.size() > 64) {
        detail = "identifier must contain between 1 and 64 ASCII characters";
        return false;
    }
    if (value == "." || value == ".." || value.back() == '.' || value.back() == ' ') {
        detail = "identifier contains an unsafe dot or trailing character";
        return false;
    }
    for (unsigned char ch : value) {
        bool allowed = (ch >= 'a' && ch <= 'z') ||
            (ch >= 'A' && ch <= 'Z') ||
            (ch >= '0' && ch <= '9') || ch == '-' || ch == '_' || ch == '.';
        if (!allowed) {
            detail = "identifier must use ASCII letters, digits, dot, underscore, or hyphen";
            return false;
        }
    }
    if (is_windows_reserved_name(value)) {
        detail = "identifier is a reserved Windows device name";
        return false;
    }
    detail.clear();
    return true;
}

ManagedPathResult managed_directory(
    const fs::path& workspace,
    const fs::path& area,
    const std::string& identifier)
{
    return managed_path(workspace, area, identifier, "");
}

ManagedPathResult managed_file(
    const fs::path& workspace,
    const fs::path& area,
    const std::string& identifier,
    const std::string& suffix)
{
    return managed_path(workspace, area, identifier, suffix);
}

bool write_text_new_atomic(const fs::path& path, const std::string& text, std::string& detail)
{
    std::error_code error;
    if (fs::exists(path, error)) {
        detail = "target already exists: " + path.string();
        return false;
    }
    fs::create_directories(path.parent_path(), error);
    if (error) {
        detail = "could not create target parent: " + error.message();
        return false;
    }

    fs::path temporary = path.parent_path() / temporary_leaf(path);
    if (!write_file_exclusive(temporary, text, detail)) {
        return false;
    }
    if (!rename_no_replace(temporary, path, detail)) {
        fs::remove(temporary, error);
        return false;
    }
    detail.clear();
    return true;
}

bool commit_directory_no_clobber(
    const fs::path& staging,
    const fs::path& destination,
    std::string& detail)
{
    std::error_code error;
    if (fs::exists(destination, error)) {
        detail = "target already exists: " + destination.string();
        return false;
    }
    if (!rename_no_replace(staging, destination, detail)) {
        return false;
    }
    detail.clear();
    return true;
}

bool remove_owned_staging_tree(
    const fs::path& staging,
    const std::string& marker_name,
    std::string& detail)
{
    if (!fs::is_regular_file(staging / marker_name)) {
        detail = "refusing to remove staging tree without ownership marker";
        return false;
    }
    std::error_code error;
    fs::remove_all(staging, error);
    if (error) {
        detail = "could not remove owned staging tree: " + error.message();
        return false;
    }
    detail.clear();
    return true;
}

bool path_crosses_link_or_reparse_point(const fs::path& path, std::string& detail)
{
    std::error_code error;
    fs::path absolute = fs::absolute(path, error).lexically_normal();
    if (error || absolute.empty()) {
        detail = "path could not be resolved for link inspection: " + path.string();
        return true;
    }
    fs::path current = absolute.root_path();
    for (const fs::path& part : absolute.relative_path()) {
        current /= part;
        if (!fs::exists(current, error)) {
            if (error) {
                detail = "path metadata could not be inspected: " + current.string();
                return true;
            }
            continue;
        }
        if (is_link_or_reparse_point(current)) {
            detail = "path crosses a link or reparse point: " + current.string();
            return true;
        }
    }
    detail.clear();
    return false;
}

} // namespace facman::base
