// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "fl_directory_publication.h"
#include "fl_windows_path.h"
#include <cstring>
#include <vector>
#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <winternl.h>
#else
#include <cerrno>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#ifdef __linux__
#include <sys/syscall.h>
#elif defined(__APPLE__)
#include <stdio.h>
#endif
#endif
namespace facman::platform {
namespace {
#ifdef _WIN32
struct Directory {
    HANDLE handle = INVALID_HANDLE_VALUE;
    ~Directory() { if (handle != INVALID_HANDLE_VALUE) CloseHandle(handle); }
    bool open(const std::filesystem::path& path, bool source)
    {
        handle = CreateFileW(windows_extended_path(path).c_str(), FILE_READ_ATTRIBUTES | FILE_LIST_DIRECTORY |
            SYNCHRONIZE | (source ? DELETE : FILE_ADD_SUBDIRECTORY | FILE_TRAVERSE), FILE_SHARE_READ | FILE_SHARE_WRITE,
            nullptr, OPEN_EXISTING, FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT, nullptr);
        return handle != INVALID_HANDLE_VALUE;
    }
    std::string identity() const
    {
        BY_HANDLE_FILE_INFORMATION info {};
        if (!GetFileInformationByHandle(handle, &info) || !(info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) ||
            (info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT)) return {};
        const auto object = (static_cast<std::uint64_t>(info.nFileIndexHigh) << 32U) | info.nFileIndexLow;
        return std::to_string(info.dwVolumeSerialNumber) + ":" + std::to_string(object);
    }
};
#else
struct Directory {
    int handle = -1;
    ~Directory() { if (handle >= 0) ::close(handle); }
    bool open(const std::filesystem::path& path, bool)
    {
        handle = ::open(path.c_str(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        return handle >= 0;
    }
    std::string identity() const
    {
        struct stat info {};
        if (::fstat(handle, &info) || !S_ISDIR(info.st_mode)) return {};
        return std::to_string(static_cast<std::uint64_t>(info.st_dev)) + ":" +
            std::to_string(static_cast<std::uint64_t>(info.st_ino));
    }
};
#endif
std::string path_identity(const std::filesystem::path& path)
{
    PathIdentity value;
    if (!inspect_path_no_follow(path, value).ok() || !value.exists || value.reparse_or_link ||
        value.kind != PathObjectKind::directory) return {};
    return std::to_string(value.device) + ":" + std::to_string(value.object);
}
}
IoStatus publish_directory_no_replace_if_matches(const std::filesystem::path& source,
    const std::filesystem::path& destination, const std::string& expected_source,
    const std::string& expected_parent, const std::function<bool(std::string&)>& verify)
{
    const auto parent_path = destination.parent_path();
    const auto leaf = destination.filename();
    if (expected_source.empty() || expected_parent.empty() || leaf.empty() || leaf == "." || leaf == "..")
        return IoStatus::failure("directory_publish_unsafe", "Publication requires exact object identities");
    Directory root, parent;
    if (!root.open(source, true) || !parent.open(parent_path, false) ||
        root.identity() != expected_source || parent.identity() != expected_parent)
        return IoStatus::failure("directory_publish_changed", "Publication source or parent changed");
    std::string detail;
    if (!verify(detail) || path_identity(source) != expected_source || path_identity(parent_path) != expected_parent ||
        root.identity() != expected_source || parent.identity() != expected_parent)
        return IoStatus::failure("directory_publish_changed", detail.empty() ? "Publication inventory changed" : detail);
#ifdef _WIN32
    using SetInformation = NTSTATUS (NTAPI*)(HANDLE, PIO_STATUS_BLOCK, PVOID, ULONG, FILE_INFORMATION_CLASS);
    const HMODULE module = GetModuleHandleW(L"ntdll.dll");
    const FARPROC address = module ? GetProcAddress(module, "NtSetInformationFile") : nullptr;
    SetInformation set_information = nullptr;
    static_assert(sizeof(set_information) == sizeof(address));
    std::memcpy(&set_information, &address, sizeof(address));
    if (!set_information) return IoStatus::failure("directory_publish_unsupported", "Native relative rename unavailable");
    const auto name = leaf.native();
    const auto name_bytes = name.size() * sizeof(wchar_t);
    std::vector<unsigned char> storage(sizeof(FILE_RENAME_INFO) + name_bytes, 0U);
    auto* rename = reinterpret_cast<FILE_RENAME_INFO*>(storage.data());
    rename->ReplaceIfExists = FALSE;
    rename->RootDirectory = parent.handle;
    rename->FileNameLength = static_cast<DWORD>(name_bytes);
    std::memcpy(rename->FileName, name.data(), name_bytes);
    IO_STATUS_BLOCK io {};
    const NTSTATUS status = set_information(root.handle, &io, rename, static_cast<ULONG>(storage.size()),
        static_cast<FILE_INFORMATION_CLASS>(10));
    if (status < 0) return IoStatus::failure("directory_publish_refused", "Native no-replace rename failed: " +
        std::to_string(static_cast<ULONG>(status)));
#elif defined(__linux__)
    Directory source_parent;
    if (!source_parent.open(source.parent_path(), false))
        return IoStatus::failure("directory_publish_changed", "Source parent unavailable");
    struct stat visible {};
    if (::fstatat(source_parent.handle, source.filename().c_str(), &visible, AT_SYMLINK_NOFOLLOW) ||
        std::to_string(static_cast<std::uint64_t>(visible.st_dev)) + ":" +
            std::to_string(static_cast<std::uint64_t>(visible.st_ino)) != expected_source)
        return IoStatus::failure("directory_publish_changed", "Source leaf changed");
    if (::syscall(SYS_renameat2, source_parent.handle, source.filename().c_str(), parent.handle, leaf.c_str(), 1U))
        return IoStatus::failure("directory_publish_refused", std::strerror(errno));
#elif defined(__APPLE__)
    if (::renamex_np(source.c_str(), destination.c_str(), RENAME_EXCL))
        return IoStatus::failure("directory_publish_refused", std::strerror(errno));
#else
    return IoStatus::failure("directory_publish_unsupported", "No atomic no-replace directory rename");
#endif
    // Namespace publication has happened. Any inability to verify it is
    // explicitly uncertain and must go through owned import recovery.
    if (path_identity(destination) != expected_source)
        return IoStatus::failure("directory_published_unverified", "Published directory identity differs");
    return IoStatus::success(DurabilityLevel::best_effort_platform_limit);
}
}
