// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_local_operation_lock.h"

#include "fl_path_safety.h"
#include "fl_windows_path.h"

#include <algorithm>
#include <cerrno>
#include <cstring>
#include <sstream>
#include <system_error>
#include <utility>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <fcntl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>
#if defined(__APPLE__)
#include <sys/mount.h>
#else
#include <sys/vfs.h>
#endif
#endif

namespace fs = std::filesystem;

namespace facman::base {
namespace {

std::string system_error_text(const std::string& prefix)
{
#ifdef _WIN32
    return prefix + ": Windows error " + std::to_string(GetLastError());
#else
    return prefix + ": " + std::strerror(errno);
#endif
}

StableLockResult supported_local_filesystem(const fs::path& path)
{
#ifdef _WIN32
    const std::wstring native_path = facman::platform::windows_extended_path(path);
    std::wstring volume_path(32768, L'\0');
    if (!GetVolumePathNameW(native_path.c_str(), volume_path.data(),
            static_cast<DWORD>(volume_path.size()))) {
        return {StableLockCode::unsupported_filesystem,
            system_error_text("cannot classify lock filesystem")};
    }
    const UINT type = GetDriveTypeW(volume_path.c_str());
    if (type == DRIVE_REMOTE || type == DRIVE_UNKNOWN || type == DRIVE_NO_ROOT_DIR) {
        return {StableLockCode::unsupported_filesystem,
            "lock path is on a remote or unclassified Windows filesystem"};
    }
    return {StableLockCode::acquired, {}};
#elif defined(__APPLE__)
    struct statfs value {};
    if (::statfs(path.c_str(), &value) != 0) {
        return {StableLockCode::unsupported_filesystem,
            system_error_text("cannot classify lock filesystem")};
    }
    if ((value.f_flags & MNT_LOCAL) == 0) {
        return {StableLockCode::unsupported_filesystem,
            "lock path is not on a local macOS filesystem"};
    }
    return {StableLockCode::acquired, {}};
#else
    struct statfs value {};
    if (::statfs(path.c_str(), &value) != 0) {
        return {StableLockCode::unsupported_filesystem,
            system_error_text("cannot classify lock filesystem")};
    }
    const unsigned long type = static_cast<unsigned long>(value.f_type);
    switch (type) {
    case 0xEF53UL:      // ext2/3/4
    case 0x58465342UL:  // XFS
    case 0x9123683EUL:  // Btrfs
    case 0x01021994UL:  // tmpfs
    case 0x858458F6UL:  // ramfs
    case 0x794C7630UL:  // overlayfs
    case 0x2FC12FC1UL:  // ZFS
    case 0xF2F52010UL:  // F2FS
    case 0xCA451A4EUL:  // bcachefs
        return {StableLockCode::acquired, {}};
    default:
        return {StableLockCode::unsupported_filesystem,
            "lock path uses an unreviewed Linux filesystem type 0x" + [&]() {
                std::ostringstream out;
                out << std::hex << type;
                return out.str();
            }()};
    }
#endif
}

#ifdef _WIN32
HANDLE native_handle(std::intptr_t value)
{
    return reinterpret_cast<HANDLE>(value);
}

bool regular_unlinked_handle(HANDLE handle, std::string& detail)
{
    FILE_ATTRIBUTE_TAG_INFO tag {};
    if (!GetFileInformationByHandleEx(handle, FileAttributeTagInfo, &tag, sizeof(tag))) {
        detail = system_error_text("cannot inspect lock attributes");
        return false;
    }
    if ((tag.FileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0 ||
        (tag.FileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0) {
        detail = "lock is a reparse point or directory";
        return false;
    }
    BY_HANDLE_FILE_INFORMATION info {};
    if (!GetFileInformationByHandle(handle, &info)) {
        detail = system_error_text("cannot inspect lock identity");
        return false;
    }
    if (info.nNumberOfLinks != 1) {
        detail = "lock must have exactly one filesystem link";
        return false;
    }
    return true;
}
#endif

} // namespace

StableLocalLock::~StableLocalLock()
{
    close();
}

StableLocalLock::StableLocalLock(StableLocalLock&& other) noexcept
{
    *this = std::move(other);
}

StableLocalLock& StableLocalLock::operator=(StableLocalLock&& other) noexcept
{
    if (this == &other) return *this;
    close();
    path_ = std::move(other.path_);
    native_handle_ = other.native_handle_;
    device_or_volume_ = other.device_or_volume_;
    file_or_inode_ = other.file_or_inode_;
    other.native_handle_ = invalid_handle();
    other.device_or_volume_ = 0;
    other.file_or_inode_ = 0;
    other.path_.clear();
    return *this;
}

StableLockResult StableLocalLock::create(const fs::path& path)
{
    close();
    std::string link_detail;
    if (path.empty() || !fs::is_directory(path.parent_path()) ||
        path_crosses_link_or_reparse_point(path.parent_path(), link_detail)) {
        return {StableLockCode::unsafe,
            link_detail.empty() ? "lock parent is missing" : link_detail};
    }
    StableLockResult filesystem = supported_local_filesystem(path.parent_path());
    if (!filesystem.acquired()) return filesystem;
#ifdef _WIN32
    const std::wstring native_path = facman::platform::windows_extended_path(path);
    HANDLE handle = CreateFileW(
        native_path.c_str(),
        GENERIC_READ | GENERIC_WRITE | DELETE,
        FILE_SHARE_READ,
        nullptr,
        CREATE_NEW,
        FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT,
        nullptr);
    if (handle == INVALID_HANDLE_VALUE) {
        const DWORD error = GetLastError();
        if (error == ERROR_FILE_EXISTS || error == ERROR_ALREADY_EXISTS) {
            return {StableLockCode::exists, "lock path already exists"};
        }
        return {StableLockCode::io_error, system_error_text("cannot create lock")};
    }
    native_handle_ = reinterpret_cast<std::intptr_t>(handle);
#else
    const int handle = ::open(path.c_str(), O_CREAT | O_EXCL | O_RDWR | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (handle < 0) {
        if (errno == EEXIST) return {StableLockCode::exists, "lock path already exists"};
        return {StableLockCode::io_error, system_error_text("cannot create lock")};
    }
    if (::flock(handle, LOCK_EX | LOCK_NB) != 0) {
        ::close(handle);
        return {StableLockCode::io_error, system_error_text("cannot own new lock")};
    }
    native_handle_ = static_cast<std::intptr_t>(handle);
#endif
    path_ = path;
    std::string detail;
    if (!capture_identity(detail)) {
        close();
        return {StableLockCode::unsafe, detail};
    }
    return {StableLockCode::acquired, {}};
}

StableLockResult StableLocalLock::open_existing(
    const fs::path& path,
    std::size_t maximum_bytes,
    std::string& content)
{
    close();
    content.clear();
    std::string link_detail;
    if (path.empty() || path_crosses_link_or_reparse_point(path, link_detail)) {
        return {StableLockCode::unsafe,
            link_detail.empty() ? "lock path is unsafe" : link_detail};
    }
    StableLockResult filesystem = supported_local_filesystem(path.parent_path());
    if (!filesystem.acquired()) return filesystem;
#ifdef _WIN32
    const std::wstring native_path = facman::platform::windows_extended_path(path);
    HANDLE handle = CreateFileW(
        native_path.c_str(),
        GENERIC_READ | GENERIC_WRITE | DELETE,
        FILE_SHARE_READ,
        nullptr,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT,
        nullptr);
    if (handle == INVALID_HANDLE_VALUE) {
        const DWORD error = GetLastError();
        if (error == ERROR_SHARING_VIOLATION || error == ERROR_LOCK_VIOLATION) {
            return {StableLockCode::contended, "another process holds the lock handle"};
        }
        return {StableLockCode::io_error, system_error_text("cannot open existing lock")};
    }
    native_handle_ = reinterpret_cast<std::intptr_t>(handle);
#else
    const int handle = ::open(path.c_str(), O_RDWR | O_NOFOLLOW | O_CLOEXEC);
    if (handle < 0) {
        return {StableLockCode::unsafe, system_error_text("cannot safely open existing lock")};
    }
    if (::flock(handle, LOCK_EX | LOCK_NB) != 0) {
        const int lock_error = errno;
        ::close(handle);
        errno = lock_error;
        if (errno == EWOULDBLOCK || errno == EAGAIN) {
            return {StableLockCode::contended, "another process holds the lock handle"};
        }
        return {StableLockCode::io_error, system_error_text("cannot own existing lock")};
    }
    native_handle_ = static_cast<std::intptr_t>(handle);
#endif
    path_ = path;
    std::string detail;
    if (!capture_identity(detail) || !read_text(maximum_bytes, content, detail)) {
        close();
        return {StableLockCode::unsafe, detail};
    }
    return {StableLockCode::acquired, {}};
}

bool StableLocalLock::capture_identity(std::string& detail)
{
    if (!open()) {
        detail = "lock handle is not open";
        return false;
    }
#ifdef _WIN32
    HANDLE handle = native_handle(native_handle_);
    if (!regular_unlinked_handle(handle, detail)) return false;
    BY_HANDLE_FILE_INFORMATION info {};
    if (!GetFileInformationByHandle(handle, &info)) {
        detail = system_error_text("cannot capture lock identity");
        return false;
    }
    device_or_volume_ = info.dwVolumeSerialNumber;
    file_or_inode_ = (static_cast<std::uint64_t>(info.nFileIndexHigh) << 32U) |
        info.nFileIndexLow;
#else
    struct stat info {};
    if (::fstat(static_cast<int>(native_handle_), &info) != 0) {
        detail = system_error_text("cannot capture lock identity");
        return false;
    }
    if (!S_ISREG(info.st_mode) || info.st_nlink != 1) {
        detail = "lock must be a regular file with exactly one link";
        return false;
    }
    device_or_volume_ = static_cast<std::uint64_t>(info.st_dev);
    file_or_inode_ = static_cast<std::uint64_t>(info.st_ino);
#endif
    if (device_or_volume_ == 0 || file_or_inode_ == 0) {
        detail = "lock filesystem did not provide a stable file identity";
        return false;
    }
    detail.clear();
    return true;
}

bool StableLocalLock::write_text(const std::string& content, std::string& detail)
{
    if (!open()) {
        detail = "lock handle is not open";
        return false;
    }
#ifdef _WIN32
    HANDLE handle = native_handle(native_handle_);
    LARGE_INTEGER start {};
    if (!SetFilePointerEx(handle, start, nullptr, FILE_BEGIN) || !SetEndOfFile(handle)) {
        detail = system_error_text("cannot reset lock content");
        return false;
    }
    std::size_t written = 0;
    while (written < content.size()) {
        DWORD chunk = 0;
        const DWORD wanted = static_cast<DWORD>(
            (std::min)(content.size() - written, static_cast<std::size_t>(1U << 20U)));
        if (!WriteFile(handle, content.data() + written, wanted, &chunk, nullptr) || chunk == 0) {
            detail = system_error_text("cannot write lock content");
            return false;
        }
        written += chunk;
    }
    if (!FlushFileBuffers(handle)) {
        detail = system_error_text("cannot flush lock content");
        return false;
    }
#else
    const int handle = static_cast<int>(native_handle_);
    if (::ftruncate(handle, 0) != 0 || ::lseek(handle, 0, SEEK_SET) < 0) {
        detail = system_error_text("cannot reset lock content");
        return false;
    }
    std::size_t written = 0;
    while (written < content.size()) {
        const ssize_t count = ::write(handle, content.data() + written, content.size() - written);
        if (count <= 0) {
            detail = system_error_text("cannot write lock content");
            return false;
        }
        written += static_cast<std::size_t>(count);
    }
    if (::fsync(handle) != 0) {
        detail = system_error_text("cannot flush lock content");
        return false;
    }
#endif
    detail.clear();
    return true;
}

bool StableLocalLock::read_text(
    std::size_t maximum_bytes,
    std::string& content,
    std::string& detail) const
{
    content.clear();
    if (!open()) {
        detail = "lock handle is not open";
        return false;
    }
#ifdef _WIN32
    HANDLE handle = native_handle(native_handle_);
    LARGE_INTEGER size {};
    if (!GetFileSizeEx(handle, &size) || size.QuadPart < 0 ||
        static_cast<std::uint64_t>(size.QuadPart) > maximum_bytes) {
        detail = "lock content exceeds its byte limit";
        return false;
    }
    LARGE_INTEGER start {};
    if (!SetFilePointerEx(handle, start, nullptr, FILE_BEGIN)) {
        detail = system_error_text("cannot seek lock content");
        return false;
    }
    content.resize(static_cast<std::size_t>(size.QuadPart));
    DWORD read = 0;
    if (!content.empty() &&
        (!ReadFile(handle, content.data(), static_cast<DWORD>(content.size()), &read, nullptr) ||
         read != content.size())) {
        detail = system_error_text("cannot read lock content");
        return false;
    }
#else
    const int handle = static_cast<int>(native_handle_);
    struct stat info {};
    if (::fstat(handle, &info) != 0 || info.st_size < 0 ||
        static_cast<std::uint64_t>(info.st_size) > maximum_bytes) {
        detail = "lock content exceeds its byte limit";
        return false;
    }
    content.resize(static_cast<std::size_t>(info.st_size));
    std::size_t offset = 0;
    while (offset < content.size()) {
        const ssize_t count = ::pread(handle, content.data() + offset, content.size() - offset,
            static_cast<off_t>(offset));
        if (count <= 0) {
            detail = system_error_text("cannot read lock content");
            return false;
        }
        offset += static_cast<std::size_t>(count);
    }
#endif
    detail.clear();
    return true;
}

bool StableLocalLock::current_identity_matches(std::string& detail) const
{
#ifdef _WIN32
    BY_HANDLE_FILE_INFORMATION info {};
    if (!GetFileInformationByHandle(native_handle(native_handle_), &info)) {
        detail = system_error_text("cannot revalidate lock handle identity");
        return false;
    }
    const std::uint64_t file = (static_cast<std::uint64_t>(info.nFileIndexHigh) << 32U) |
        info.nFileIndexLow;
    if (info.dwVolumeSerialNumber != device_or_volume_ || file != file_or_inode_) {
        detail = "open lock handle identity changed";
        return false;
    }
#else
    struct stat info {};
    if (::fstat(static_cast<int>(native_handle_), &info) != 0) {
        detail = system_error_text("cannot revalidate lock handle identity");
        return false;
    }
    if (static_cast<std::uint64_t>(info.st_dev) != device_or_volume_ ||
        static_cast<std::uint64_t>(info.st_ino) != file_or_inode_) {
        detail = "open lock handle identity changed";
        return false;
    }
#endif
    detail.clear();
    return true;
}

bool StableLocalLock::identity_matches_path(std::string& detail) const
{
    if (!open() || !current_identity_matches(detail)) return false;
#ifdef _WIN32
    const std::wstring native_path = facman::platform::windows_extended_path(path_);
    HANDLE path_handle = CreateFileW(
        native_path.c_str(),
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        nullptr,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT,
        nullptr);
    if (path_handle == INVALID_HANDLE_VALUE) {
        detail = system_error_text("lock path no longer names the open lock");
        return false;
    }
    BY_HANDLE_FILE_INFORMATION info {};
    const bool queried = GetFileInformationByHandle(path_handle, &info) != 0;
    CloseHandle(path_handle);
    const std::uint64_t file = (static_cast<std::uint64_t>(info.nFileIndexHigh) << 32U) |
        info.nFileIndexLow;
    if (!queried || info.dwVolumeSerialNumber != device_or_volume_ || file != file_or_inode_) {
        detail = "lock path identity differs from the held handle";
        return false;
    }
#else
    struct stat info {};
    if (::lstat(path_.c_str(), &info) != 0 || !S_ISREG(info.st_mode) || info.st_nlink != 1 ||
        static_cast<std::uint64_t>(info.st_dev) != device_or_volume_ ||
        static_cast<std::uint64_t>(info.st_ino) != file_or_inode_) {
        detail = "lock path identity differs from the held handle";
        return false;
    }
#endif
    detail.clear();
    return true;
}

bool StableLocalLock::remove_exact(std::string& detail)
{
    if (!identity_matches_path(detail)) return false;
#ifdef _WIN32
    FILE_DISPOSITION_INFO disposition {};
    disposition.DeleteFile = TRUE;
    if (!SetFileInformationByHandle(
            native_handle(native_handle_), FileDispositionInfo, &disposition, sizeof(disposition))) {
        detail = system_error_text("cannot delete held lock");
        return false;
    }
    close();
#else
    if (::unlink(path_.c_str()) != 0) {
        detail = system_error_text("cannot unlink held lock");
        return false;
    }
    const fs::path parent = path_.parent_path();
    close();
    const int directory = ::open(parent.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (directory >= 0) {
        (void)::fsync(directory);
        ::close(directory);
    }
#endif
    detail.clear();
    return true;
}

void StableLocalLock::close()
{
    if (!open()) return;
#ifdef _WIN32
    CloseHandle(native_handle(native_handle_));
#else
    (void)::flock(static_cast<int>(native_handle_), LOCK_UN);
    ::close(static_cast<int>(native_handle_));
#endif
    native_handle_ = invalid_handle();
    device_or_volume_ = 0;
    file_or_inode_ = 0;
    path_.clear();
}

std::string StableLocalLock::identity_text() const
{
    return std::to_string(device_or_volume_) + ":" + std::to_string(file_or_inode_);
}

} // namespace facman::base
