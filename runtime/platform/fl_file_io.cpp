// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_file_io.h"

#include "fl_windows_path.h"

#include <algorithm>
#include <cerrno>
#include <cctype>
#include <cstdio>
#include <cstring>
#include <cwchar>
#include <limits>
#include <vector>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <winternl.h>
#else
#include <dirent.h>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#if defined(__linux__)
#include <sys/syscall.h>
#endif
#endif

namespace facman::platform {
namespace {

thread_local bool relative_publish_post_rename_fault_for_testing = false;
thread_local unsigned relative_publish_pre_rename_fault_countdown_for_testing = 0U;
thread_local testing::RelativePublishBeforeReopenHook
    relative_publish_before_reopen_hook_for_testing = nullptr;

IoStatus published_unverified_failure(const IoStatus& underlying)
{
    return IoStatus::failure(
        "output_published_unverified",
        underlying.code + ": " + underlying.detail);
}

bool portable_leaf(const std::filesystem::path& leaf, std::string& value)
{
    value = leaf.generic_u8string();
    if (value.empty() || value.size() > 255U || value == "." || value == ".." || leaf.has_root_path() ||
        leaf.has_parent_path() || value.find_first_of("\\\\/:") != std::string::npos ||
        value.back() == '.' || value.back() == ' ') return false;
    for (const unsigned char character : value) {
        if (character < 0x21U || character > 0x7eU ||
            std::strchr("<>\"|?*", static_cast<int>(character)) != nullptr) return false;
    }
    std::string base = value.substr(0, value.find('.'));
    std::transform(base.begin(), base.end(), base.begin(), [](unsigned char character) {
        return static_cast<char>(std::toupper(character));
    });
    if (base == "CON" || base == "PRN" || base == "AUX" || base == "NUL") return false;
    return base.size() == 4U &&
        (base.rfind("COM", 0U) == 0U || base.rfind("LPT", 0U) == 0U) &&
        base[3] >= '1' && base[3] <= '9' ? false : true;
}

#ifdef _WIN32
using NativeHandle = HANDLE;
const NativeHandle kInvalidHandle = INVALID_HANDLE_VALUE;
using OpenRelative = NTSTATUS (NTAPI*)(PHANDLE, ACCESS_MASK, POBJECT_ATTRIBUTES,
    PIO_STATUS_BLOCK, PLARGE_INTEGER, ULONG, ULONG, ULONG, ULONG, PVOID, ULONG);
using SetRelativeInformation = NTSTATUS (NTAPI*)(HANDLE, PIO_STATUS_BLOCK, PVOID, ULONG,
    FILE_INFORMATION_CLASS);

OpenRelative nt_create_file()
{
    const HMODULE module = GetModuleHandleW(L"ntdll.dll");
    const FARPROC address = module ? GetProcAddress(module, "NtCreateFile") : nullptr;
    OpenRelative result = nullptr;
    static_assert(sizeof(result) == sizeof(address));
    std::memcpy(&result, &address, sizeof(address));
    return result;
}

SetRelativeInformation nt_set_information_file()
{
    const HMODULE module = GetModuleHandleW(L"ntdll.dll");
    const FARPROC address = module ? GetProcAddress(module, "NtSetInformationFile") : nullptr;
    SetRelativeInformation result = nullptr;
    static_assert(sizeof(result) == sizeof(address));
    std::memcpy(&result, &address, sizeof(address));
    return result;
}

IoStatus nt_rename_status(NTSTATUS status)
{
    const ULONG value = static_cast<ULONG>(status);
    if (value == 0xc0000035UL) return IoStatus::failure("commit_no_replace_collision", "destination exists");
    if (value == 0xc000000dUL) return IoStatus::failure("relative_publish_unavailable", "NtSetInformationFile rejected relative rename");
    if (value == 0xc00000d4UL) return IoStatus::failure("commit_cross_device", "relative rename crossed devices");
    if (value == 0xc000050bUL) return IoStatus::failure("commit_reparse_refused", "reparse encountered during relative rename");
    char detail[32] {};
    std::snprintf(detail, sizeof(detail), "NtSetInformationFile status 0x%08lx", value);
    return IoStatus::failure("commit_no_replace_failed", detail);
}

IoStatus open_relative_windows(
    HANDLE parent, const std::string& leaf, ACCESS_MASK access, ULONG disposition,
    ULONG options, HANDLE& result,
    ULONG share = FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE)
{
    const OpenRelative open_relative = nt_create_file();
    if (!open_relative) return IoStatus::failure("relative_open_unavailable", "NtCreateFile unavailable");
    std::wstring name(leaf.begin(), leaf.end());
    UNICODE_STRING unicode {};
    unicode.Buffer = name.data();
    unicode.Length = static_cast<USHORT>(name.size() * sizeof(wchar_t));
    unicode.MaximumLength = unicode.Length;
    OBJECT_ATTRIBUTES attributes {};
    attributes.Length = sizeof(attributes);
    attributes.RootDirectory = parent;
    attributes.ObjectName = &unicode;
    attributes.Attributes = 0x1040; // OBJ_DONT_REPARSE | OBJ_CASE_INSENSITIVE
    IO_STATUS_BLOCK io {};
    result = kInvalidHandle;
    const NTSTATUS status = open_relative(&result, access | SYNCHRONIZE, &attributes, &io,
        nullptr, FILE_ATTRIBUTE_NORMAL, share,
        disposition, options | 0x00000020, nullptr, 0);
    if (status < 0) {
        result = kInvalidHandle;
        return IoStatus::failure("relative_open_failed", "NtCreateFile failed with status " +
            std::to_string(static_cast<ULONG>(status)));
    }
    return IoStatus::success();
}

bool duplicate_handle(HANDLE source, HANDLE& target)
{
    return DuplicateHandle(GetCurrentProcess(), source, GetCurrentProcess(), &target, 0,
        FALSE, DUPLICATE_SAME_ACCESS) != 0;
}

std::string windows_error(const char* operation)
{
    return std::string(operation) + " failed with error " + std::to_string(GetLastError());
}

FileIdentity identity_from_info(const BY_HANDLE_FILE_INFORMATION& info)
{
    FileIdentity identity;
    identity.device = info.dwVolumeSerialNumber;
    identity.object = (static_cast<std::uint64_t>(info.nFileIndexHigh) << 32) | info.nFileIndexLow;
    identity.size = (static_cast<std::uint64_t>(info.nFileSizeHigh) << 32) | info.nFileSizeLow;
    identity.link_count = info.nNumberOfLinks;
    identity.regular_file = (info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) == 0 &&
        (info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) == 0;
    return identity;
}

PathIdentity path_identity_from_info(
    const std::filesystem::path& path,
    HANDLE handle,
    const BY_HANDLE_FILE_INFORMATION& info)
{
    PathIdentity identity;
    identity.exists = true;
    identity.reparse_or_link =
        (info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT) != 0;
    identity.kind = (info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) != 0
        ? PathObjectKind::directory
        : (identity.reparse_or_link ? PathObjectKind::other : PathObjectKind::regular_file);
    identity.device = info.dwVolumeSerialNumber;
    identity.object =
        (static_cast<std::uint64_t>(info.nFileIndexHigh) << 32U) |
        static_cast<std::uint64_t>(info.nFileIndexLow);
    identity.size =
        (static_cast<std::uint64_t>(info.nFileSizeHigh) << 32U) |
        static_cast<std::uint64_t>(info.nFileSizeLow);
    identity.last_write_ticks =
        (static_cast<std::uint64_t>(info.ftLastWriteTime.dwHighDateTime) << 32U) |
        static_cast<std::uint64_t>(info.ftLastWriteTime.dwLowDateTime);
    wchar_t filesystem[64] {};
    if (GetVolumeInformationByHandleW(
            handle, nullptr, 0, nullptr, nullptr, nullptr,
            filesystem, static_cast<DWORD>(sizeof(filesystem) / sizeof(filesystem[0])))) {
        const int characters = static_cast<int>(std::wcslen(filesystem));
        const int bytes = WideCharToMultiByte(
            CP_UTF8, WC_ERR_INVALID_CHARS, filesystem, characters,
            nullptr, 0, nullptr, nullptr);
        if (bytes > 0) {
            identity.filesystem_name.resize(static_cast<std::size_t>(bytes));
            (void)WideCharToMultiByte(
                CP_UTF8, WC_ERR_INVALID_CHARS, filesystem, characters,
                identity.filesystem_name.data(), bytes, nullptr, nullptr);
        }
    }
    const std::filesystem::path root = std::filesystem::absolute(path).root_path();
    identity.fixed_local_volume = !root.empty() &&
        GetDriveTypeW(root.c_str()) == DRIVE_FIXED;
    return identity;
}
#else
using NativeHandle = int;
constexpr NativeHandle kInvalidHandle = -1;

FileIdentity identity_from_stat(const struct stat& info)
{
    FileIdentity identity;
    identity.device = static_cast<std::uint64_t>(info.st_dev);
    identity.object = static_cast<std::uint64_t>(info.st_ino);
    identity.size = static_cast<std::uint64_t>(info.st_size);
    identity.link_count = static_cast<std::uint64_t>(info.st_nlink);
    identity.regular_file = S_ISREG(info.st_mode);
    return identity;
}

PathIdentity path_identity_from_stat(const struct stat& info)
{
    PathIdentity identity;
    identity.exists = true;
    identity.reparse_or_link = S_ISLNK(info.st_mode);
    identity.kind = S_ISREG(info.st_mode)
        ? PathObjectKind::regular_file
        : (S_ISDIR(info.st_mode) ? PathObjectKind::directory : PathObjectKind::other);
    identity.device = static_cast<std::uint64_t>(info.st_dev);
    identity.object = static_cast<std::uint64_t>(info.st_ino);
    identity.size = static_cast<std::uint64_t>(info.st_size);
#if defined(__APPLE__)
    identity.last_write_ticks =
        static_cast<std::uint64_t>(info.st_mtimespec.tv_sec) * 1000000000ULL +
        static_cast<std::uint64_t>(info.st_mtimespec.tv_nsec);
#else
    identity.last_write_ticks =
        static_cast<std::uint64_t>(info.st_mtim.tv_sec) * 1000000000ULL +
        static_cast<std::uint64_t>(info.st_mtim.tv_nsec);
#endif
    identity.filesystem_name = "posix";
    return identity;
}

IoStatus flush_directory(const std::filesystem::path& directory)
{
    const int handle = ::open(directory.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (handle < 0) return IoStatus::failure("directory_open_failed", std::strerror(errno));
    const int result = ::fsync(handle);
    const int error = errno;
    ::close(handle);
    return result == 0
        ? IoStatus::success(DurabilityLevel::file_and_directory_flushed)
        : IoStatus::failure("directory_flush_failed", std::strerror(error));
}

bool duplicate_handle(int source, int& target)
{
    target = ::fcntl(source, F_DUPFD_CLOEXEC, 0);
    return target >= 0;
}

IoStatus flush_directory_handle(int handle)
{
    if (::fsync(handle) != 0) return IoStatus::failure("directory_flush_failed", std::strerror(errno));
    return IoStatus::success(DurabilityLevel::file_and_directory_flushed);
}
#endif

IoStatus close_native_handle(NativeHandle& handle, const char* code)
{
    if (handle == kInvalidHandle) return IoStatus::success();
#ifdef _WIN32
    if (!CloseHandle(handle)) {
        handle = kInvalidHandle;
        return IoStatus::failure(code, windows_error("CloseHandle"));
    }
#else
    if (::close(handle) != 0) {
        const std::string detail = std::strerror(errno);
        handle = kInvalidHandle;
        return IoStatus::failure(code, detail);
    }
#endif
    handle = kInvalidHandle;
    return IoStatus::success();
}

void close_native_handle_noexcept(NativeHandle& handle) noexcept
{
    if (handle == kInvalidHandle) return;
#ifdef _WIN32
    (void)CloseHandle(handle);
#else
    (void)::close(handle);
#endif
    handle = kInvalidHandle;
}

} // namespace

namespace testing {

void set_relative_publish_post_rename_fault(bool enabled) noexcept
{
    relative_publish_post_rename_fault_for_testing = enabled;
}

void set_relative_publish_pre_rename_fault_countdown(unsigned count) noexcept
{
    relative_publish_pre_rename_fault_countdown_for_testing = count;
}

void set_relative_publish_before_reopen_hook(RelativePublishBeforeReopenHook hook) noexcept
{
    relative_publish_before_reopen_hook_for_testing = hook;
}

} // namespace testing

struct StableInputFile::Impl {
    NativeHandle handle = kInvalidHandle;
    FileIdentity identity;
    std::filesystem::path path;
    ~Impl()
    {
#ifdef _WIN32
        if (handle != kInvalidHandle) CloseHandle(handle);
#else
        if (handle != kInvalidHandle) ::close(handle);
#endif
    }
};

StableInputFile::StableInputFile() : impl_(std::make_unique<Impl>()) {}
StableInputFile::StableInputFile(StableInputFile&&) noexcept = default;
StableInputFile& StableInputFile::operator=(StableInputFile&&) noexcept = default;
StableInputFile::~StableInputFile() = default;

IoStatus StableInputFile::open_no_follow(const std::filesystem::path& path)
{
    return open_no_follow_impl(path, false);
}

IoStatus StableInputFile::open_no_follow_pinned(const std::filesystem::path& path)
{
    return open_no_follow_impl(path, true);
}

IoStatus StableInputFile::open_no_follow_impl(
    const std::filesystem::path& path,
    bool pinned)
{
    if (open()) return IoStatus::failure("input_already_open", path_to_utf8(path));
#ifdef _WIN32
    const std::wstring native_path = windows_extended_path(path);
    impl_->handle = CreateFileW(
        native_path.c_str(), GENERIC_READ,
        pinned ? FILE_SHARE_READ : FILE_SHARE_READ | FILE_SHARE_DELETE,
        nullptr, OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_RANDOM_ACCESS, nullptr);
    if (impl_->handle == kInvalidHandle) return IoStatus::failure("input_open_failed", windows_error("CreateFileW"));
    BY_HANDLE_FILE_INFORMATION info {};
    if (!GetFileInformationByHandle(impl_->handle, &info)) {
        const std::string detail = windows_error("GetFileInformationByHandle");
        CloseHandle(impl_->handle);
        impl_->handle = kInvalidHandle;
        return IoStatus::failure("input_identity_failed", detail);
    }
    impl_->identity = identity_from_info(info);
#else
    impl_->handle = ::open(path.c_str(), O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    if (impl_->handle < 0) return IoStatus::failure("input_open_failed", std::strerror(errno));
    struct stat info {};
    if (::fstat(impl_->handle, &info) != 0) {
        const std::string detail = std::strerror(errno);
        ::close(impl_->handle);
        impl_->handle = kInvalidHandle;
        return IoStatus::failure("input_identity_failed", detail);
    }
    impl_->identity = identity_from_stat(info);
#endif
    if (!impl_->identity.regular_file || (pinned && impl_->identity.link_count != 1U)) {
#ifdef _WIN32
        CloseHandle(impl_->handle);
#else
        ::close(impl_->handle);
#endif
        impl_->handle = kInvalidHandle;
        return IoStatus::failure(
            impl_->identity.regular_file ? "input_multiple_links" : "input_not_regular",
            path_to_utf8(path));
    }
    impl_->path = path;
    return IoStatus::success();
}

std::size_t StableInputFile::read_at(std::uint64_t offset, void* buffer, std::size_t size) const
{
    if (!open() || offset >= impl_->identity.size) return 0;
    size = static_cast<std::size_t>(std::min<std::uint64_t>(size, impl_->identity.size - offset));
#ifdef _WIN32
    LARGE_INTEGER position {};
    position.QuadPart = static_cast<LONGLONG>(offset);
    if (!SetFilePointerEx(impl_->handle, position, nullptr, FILE_BEGIN)) return 0;
    DWORD read = 0;
    const DWORD requested = static_cast<DWORD>(std::min<std::size_t>(size, std::numeric_limits<DWORD>::max()));
    if (!ReadFile(impl_->handle, buffer, requested, &read, nullptr)) return 0;
    return read;
#else
    const ssize_t count = ::pread(impl_->handle, buffer, size, static_cast<off_t>(offset));
    return count > 0 ? static_cast<std::size_t>(count) : 0;
#endif
}

IoStatus StableInputFile::revalidate() const
{
    if (!open()) return IoStatus::failure("input_not_open", "");
    FileIdentity current;
#ifdef _WIN32
    BY_HANDLE_FILE_INFORMATION info {};
    if (!GetFileInformationByHandle(impl_->handle, &info)) return IoStatus::failure("input_revalidate_failed", windows_error("GetFileInformationByHandle"));
    current = identity_from_info(info);
#else
    struct stat info {};
    if (::fstat(impl_->handle, &info) != 0) return IoStatus::failure("input_revalidate_failed", std::strerror(errno));
    current = identity_from_stat(info);
#endif
    return impl_->identity.unchanged(current) ? IoStatus::success() : IoStatus::failure("input_identity_changed", "stable input identity changed while open");
}

IoStatus StableInputFile::revalidate_path() const
{
    const IoStatus held = revalidate();
    if (!held.ok()) return held;
    PathIdentity current;
    const IoStatus observed = inspect_path_no_follow(impl_->path, current);
    if (!observed.ok()) return observed;
    if (!current.exists || current.reparse_or_link ||
        current.kind != PathObjectKind::regular_file ||
        current.device != impl_->identity.device ||
        current.object != impl_->identity.object ||
        current.size != impl_->identity.size) {
        return IoStatus::failure(
            "input_path_identity_changed", path_to_utf8(impl_->path));
    }
    return IoStatus::success();
}
const FileIdentity& StableInputFile::identity() const noexcept { return impl_->identity; }
std::uint64_t StableInputFile::size() const noexcept { return impl_->identity.size; }
bool StableInputFile::open() const noexcept { return impl_ && impl_->handle != kInvalidHandle; }

struct StableDirectoryObject::Impl {
    NativeHandle handle = kInvalidHandle;
    PathIdentity identity;
    std::filesystem::path path;
    ~Impl()
    {
#ifdef _WIN32
        if (handle != kInvalidHandle) CloseHandle(handle);
#else
        if (handle != kInvalidHandle) ::close(handle);
#endif
    }
};

StableDirectoryObject::StableDirectoryObject() : impl_(std::make_unique<Impl>()) {}
StableDirectoryObject::StableDirectoryObject(StableDirectoryObject&&) noexcept = default;
StableDirectoryObject& StableDirectoryObject::operator=(StableDirectoryObject&&) noexcept = default;

StableDirectoryObject::~StableDirectoryObject() = default;

IoStatus StableDirectoryObject::open_no_follow(const std::filesystem::path& path)
{
    return open_no_follow_impl(path, false);
}

IoStatus StableDirectoryObject::open_no_follow_for_relative_writes(const std::filesystem::path& path)
{
    return open_no_follow_impl(path, true);
}

IoStatus StableDirectoryObject::open_no_follow_impl(
    const std::filesystem::path& path, bool relative_writes)
{
    if (!impl_ || impl_->handle != kInvalidHandle) {
        return IoStatus::failure("directory_object_already_open", path_to_utf8(path));
    }
    std::error_code absolute_error;
    const std::filesystem::path absolute =
        std::filesystem::absolute(path, absolute_error).lexically_normal();
    if (absolute_error || absolute.empty()) {
        return IoStatus::failure("directory_object_path_invalid", path_to_utf8(path));
    }
#ifndef _WIN32
    (void)relative_writes;
#endif
#ifdef _WIN32
    const std::wstring native_path = windows_extended_path(absolute);
    impl_->handle = CreateFileW(
        native_path.c_str(), FILE_READ_ATTRIBUTES | FILE_LIST_DIRECTORY |
            (relative_writes ? FILE_ADD_FILE | FILE_ADD_SUBDIRECTORY | FILE_TRAVERSE | SYNCHRONIZE : 0),
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr, OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
        nullptr);
    if (impl_->handle == kInvalidHandle) {
        return IoStatus::failure(
            "directory_object_open_failed", windows_error("CreateFileW"));
    }
    BY_HANDLE_FILE_INFORMATION info {};
    if (!GetFileInformationByHandle(impl_->handle, &info)) {
        const std::string detail = windows_error("GetFileInformationByHandle");
        CloseHandle(impl_->handle);
        impl_->handle = kInvalidHandle;
        return IoStatus::failure("directory_object_identity_failed", detail);
    }
    impl_->identity = path_identity_from_info(absolute, impl_->handle, info);
#else
    impl_->handle =
        ::open(absolute.c_str(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (impl_->handle == kInvalidHandle) {
        return IoStatus::failure("directory_object_open_failed", std::strerror(errno));
    }
    struct stat info {};
    if (::fstat(impl_->handle, &info) != 0) {
        const std::string detail = std::strerror(errno);
        ::close(impl_->handle);
        impl_->handle = kInvalidHandle;
        return IoStatus::failure("directory_object_identity_failed", detail);
    }
    impl_->identity = path_identity_from_stat(info);
#endif
    if (!impl_->identity.exists ||
        impl_->identity.kind != PathObjectKind::directory ||
        impl_->identity.reparse_or_link) {
#ifdef _WIN32
        CloseHandle(impl_->handle);
#else
        ::close(impl_->handle);
#endif
        impl_->handle = kInvalidHandle;
        impl_->identity = {};
        return IoStatus::failure(
            "directory_object_not_plain_directory", path_to_utf8(absolute));
    }
    impl_->path = absolute;
    return IoStatus::success();
}

IoStatus StableDirectoryObject::revalidate() const
{
    if (!open()) return IoStatus::failure("directory_object_not_open", "");
    PathIdentity held;
#ifdef _WIN32
    BY_HANDLE_FILE_INFORMATION info {};
    if (!GetFileInformationByHandle(impl_->handle, &info)) {
        return IoStatus::failure(
            "directory_object_revalidate_failed",
            windows_error("GetFileInformationByHandle"));
    }
    held = path_identity_from_info(impl_->path, impl_->handle, info);
#else
    struct stat info {};
    if (::fstat(impl_->handle, &info) != 0) {
        return IoStatus::failure(
            "directory_object_revalidate_failed", std::strerror(errno));
    }
    held = path_identity_from_stat(info);
#endif
    if (!held.same_object(impl_->identity) ||
        held.kind != PathObjectKind::directory ||
        held.reparse_or_link) {
        return IoStatus::failure(
            "directory_object_handle_identity_changed", path_to_utf8(impl_->path));
    }
    PathIdentity current;
    const IoStatus observed = inspect_path_no_follow(impl_->path, current);
    if (!observed.ok()) return observed;
    if (!current.same_object(impl_->identity) ||
        current.kind != PathObjectKind::directory ||
        current.reparse_or_link) {
        return IoStatus::failure(
            "directory_object_path_identity_changed", path_to_utf8(impl_->path));
    }
    return IoStatus::success();
}

IoStatus StableDirectoryObject::validate_descendant(
    const std::filesystem::path& path,
    bool allow_absent_leaf) const
{
    const IoStatus before = revalidate();
    if (!before.ok()) return before;
    std::error_code absolute_error;
    const std::filesystem::path absolute =
        std::filesystem::absolute(path, absolute_error).lexically_normal();
    if (absolute_error || absolute.empty()) {
        return IoStatus::failure("directory_descendant_path_invalid", path_to_utf8(path));
    }
    const std::filesystem::path relative = absolute.lexically_relative(impl_->path);
    if (relative.empty() || relative.is_absolute()) {
        return IoStatus::failure(
            "directory_descendant_escape", path_to_utf8(absolute));
    }
    const std::string relative_text = relative.generic_string();
    if (relative_text == ".." || relative_text.rfind("../", 0U) == 0U) {
        return IoStatus::failure(
            "directory_descendant_escape", path_to_utf8(absolute));
    }
    std::filesystem::path current = impl_->path;
    std::size_t index = 0U;
    const std::size_t component_count =
        static_cast<std::size_t>(std::distance(relative.begin(), relative.end()));
    for (const auto& component : relative) {
        if (component == "." || component.empty()) continue;
        if (component == "..") {
            return IoStatus::failure(
                "directory_descendant_escape", path_to_utf8(absolute));
        }
        current /= component;
        PathIdentity identity;
        const IoStatus observed = inspect_path_no_follow(current, identity);
        if (!observed.ok()) return observed;
        const bool final_component = ++index == component_count;
        if (!identity.exists) {
            if (allow_absent_leaf && final_component) break;
            return IoStatus::failure(
                "directory_descendant_missing", path_to_utf8(current));
        }
        if (identity.reparse_or_link || identity.kind == PathObjectKind::other) {
            return IoStatus::failure(
                "directory_descendant_reparse_refused", path_to_utf8(current));
        }
        if (!final_component && identity.kind != PathObjectKind::directory) {
            return IoStatus::failure(
                "directory_descendant_ancestor_not_directory", path_to_utf8(current));
        }
    }
    return revalidate();
}

const PathIdentity& StableDirectoryObject::identity() const noexcept
{
    return impl_->identity;
}

const std::filesystem::path& StableDirectoryObject::path() const noexcept
{
    return impl_->path;
}

bool StableDirectoryObject::open() const noexcept
{
    return impl_ && impl_->handle != kInvalidHandle;
}

IoStatus StableDirectoryObject::flush_metadata() const
{
    const IoStatus valid = revalidate();
    if (!valid.ok()) return valid;
#ifdef _WIN32
    // Windows does not provide a supported directory-flush contract.
    return IoStatus::success(DurabilityLevel::best_effort_platform_limit);
#else
    return flush_directory_handle(impl_->handle);
#endif
}

IoStatus StableDirectoryObject::open_child_directory_no_follow(
    const std::filesystem::path& leaf, StableDirectoryObject& child) const
{
    return open_child_directory_no_follow_impl(leaf, child, false);
}

IoStatus StableDirectoryObject::open_child_directory_no_follow_for_relative_writes(
    const std::filesystem::path& leaf, StableDirectoryObject& child) const
{
    return open_child_directory_no_follow_impl(leaf, child, true);
}

IoStatus StableDirectoryObject::open_child_directory_no_follow_impl(
    const std::filesystem::path& leaf,
    StableDirectoryObject& child,
    bool relative_writes) const
{
    std::string name;
    if (!portable_leaf(leaf, name)) return IoStatus::failure("relative_leaf_invalid", path_to_utf8(leaf));
    if (!child.impl_ || child.open()) return IoStatus::failure("directory_object_already_open", name);
    const IoStatus valid = revalidate();
    if (!valid.ok()) return valid;
    NativeHandle handle = kInvalidHandle;
#ifndef _WIN32
    (void)relative_writes;
#endif
#ifdef _WIN32
    IoStatus status = open_relative_windows(impl_->handle, name,
        FILE_READ_ATTRIBUTES | FILE_LIST_DIRECTORY |
            (relative_writes ? FILE_ADD_FILE | FILE_ADD_SUBDIRECTORY | FILE_TRAVERSE : 0),
        1, 0x00200001, handle,
        FILE_SHARE_READ | FILE_SHARE_WRITE);
    if (!status.ok()) return status;
    BY_HANDLE_FILE_INFORMATION info {};
    if (!GetFileInformationByHandle(handle, &info)) {
        const std::string detail = windows_error("GetFileInformationByHandle");
        CloseHandle(handle);
        return IoStatus::failure("directory_object_identity_failed", detail);
    }
    child.impl_->identity = path_identity_from_info(impl_->path / leaf, handle, info);
#else
    handle = ::openat(impl_->handle, name.c_str(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (handle < 0) return IoStatus::failure("relative_open_failed", std::strerror(errno));
    struct stat info {};
    if (::fstat(handle, &info) != 0) {
        const std::string detail = std::strerror(errno);
        ::close(handle);
        return IoStatus::failure("directory_object_identity_failed", detail);
    }
    child.impl_->identity = path_identity_from_stat(info);
#endif
    if (child.impl_->identity.kind != PathObjectKind::directory || child.impl_->identity.reparse_or_link) {
#ifdef _WIN32
        CloseHandle(handle);
#else
        ::close(handle);
#endif
        child.impl_->identity = {};
        return IoStatus::failure("relative_child_not_plain_directory", name);
    }
    child.impl_->handle = handle;
    child.impl_->path = impl_->path / leaf;
    return IoStatus::success();
}

IoStatus StableDirectoryObject::create_child_directory_exclusive(
    const std::filesystem::path& leaf, StableDirectoryObject& child) const
{
    std::string name;
    if (!portable_leaf(leaf, name)) return IoStatus::failure("relative_leaf_invalid", path_to_utf8(leaf));
    if (!child.impl_ || child.open()) return IoStatus::failure("directory_object_already_open", name);
    const IoStatus valid = revalidate();
    if (!valid.ok()) return valid;
#ifdef _WIN32
    HANDLE created = kInvalidHandle;
    IoStatus status = open_relative_windows(impl_->handle, name,
        FILE_READ_ATTRIBUTES | FILE_LIST_DIRECTORY | FILE_ADD_FILE | FILE_ADD_SUBDIRECTORY |
            FILE_TRAVERSE,
        2, 0x00200001, created, FILE_SHARE_READ | FILE_SHARE_WRITE);
    if (!status.ok()) return IoStatus::failure("relative_directory_create_failed", status.detail);
    child.impl_->handle = created;
    BY_HANDLE_FILE_INFORMATION info {};
    if (!GetFileInformationByHandle(created, &info)) {
        const std::string detail = windows_error("GetFileInformationByHandle");
        CloseHandle(created);
        child.impl_->handle = kInvalidHandle;
        return IoStatus::failure("directory_object_identity_failed", detail);
    }
    child.impl_->identity = path_identity_from_info(impl_->path / leaf, created, info);
#else
    if (::mkdirat(impl_->handle, name.c_str(), 0700) != 0)
        return IoStatus::failure("relative_directory_create_failed", std::strerror(errno));
    const int opened = ::openat(impl_->handle, name.c_str(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (opened < 0) return IoStatus::failure("relative_directory_open_failed", std::strerror(errno));
    child.impl_->handle = opened;
    struct stat info {};
    if (::fstat(opened, &info) != 0) {
        const std::string detail = std::strerror(errno);
        ::close(opened);
        child.impl_->handle = kInvalidHandle;
        return IoStatus::failure("directory_object_identity_failed", detail);
    }
    child.impl_->identity = path_identity_from_stat(info);
#endif
    child.impl_->path = impl_->path / leaf;
    return child.revalidate();
}

IoStatus StableDirectoryObject::open_child_file_no_follow_pinned(
    const std::filesystem::path& leaf, StableInputFile& child) const
{
    std::string name;
    if (!portable_leaf(leaf, name)) return IoStatus::failure("relative_leaf_invalid", path_to_utf8(leaf));
    if (!child.impl_ || child.open()) return IoStatus::failure("input_already_open", name);
    const IoStatus valid = revalidate();
    if (!valid.ok()) return valid;
    NativeHandle handle = kInvalidHandle;
#ifdef _WIN32
    IoStatus status = open_relative_windows(impl_->handle, name, GENERIC_READ, 1, 0x00200040, handle,
        FILE_SHARE_READ);
    if (!status.ok()) return status;
    BY_HANDLE_FILE_INFORMATION info {};
    if (!GetFileInformationByHandle(handle, &info)) {
        const std::string detail = windows_error("GetFileInformationByHandle");
        CloseHandle(handle);
        return IoStatus::failure("input_identity_failed", detail);
    }
    child.impl_->identity = identity_from_info(info);
#else
    handle = ::openat(impl_->handle, name.c_str(), O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    if (handle < 0) return IoStatus::failure("relative_open_failed", std::strerror(errno));
    struct stat info {};
    if (::fstat(handle, &info) != 0) {
        const std::string detail = std::strerror(errno);
        ::close(handle);
        return IoStatus::failure("input_identity_failed", detail);
    }
    child.impl_->identity = identity_from_stat(info);
#endif
    if (!child.impl_->identity.regular_file || child.impl_->identity.link_count != 1U) {
#ifdef _WIN32
        CloseHandle(handle);
#else
        ::close(handle);
#endif
        return IoStatus::failure(child.impl_->identity.regular_file ? "input_multiple_links" : "input_not_regular", name);
    }
    child.impl_->handle = handle;
    child.impl_->path = impl_->path / leaf;
    return IoStatus::success();
}

IoStatus StableDirectoryObject::list_child_names_bounded(
    std::size_t maximum_entries,
    std::vector<std::filesystem::path>& names) const
{
    names.clear();
    const IoStatus before = revalidate();
    if (!before.ok()) return before;
#ifdef _WIN32
    HANDLE duplicate = kInvalidHandle;
    if (!duplicate_handle(impl_->handle, duplicate))
        return IoStatus::failure("directory_enumerate_failed", windows_error("DuplicateHandle"));
    std::vector<unsigned char> buffer(64U * 1024U);
    bool more = true;
    bool restart = true;
    while (more) {
        if (!GetFileInformationByHandleEx(duplicate,
                restart ? FileIdBothDirectoryRestartInfo : FileIdBothDirectoryInfo,
                buffer.data(), static_cast<DWORD>(buffer.size()))) {
            const DWORD error = GetLastError();
            if (error == ERROR_NO_MORE_FILES) break;
            CloseHandle(duplicate);
            names.clear();
            return IoStatus::failure("directory_enumerate_failed", windows_error("GetFileInformationByHandleEx"));
        }
        restart = false;
        std::size_t offset = 0U;
        for (;;) {
            const auto* entry = reinterpret_cast<const FILE_ID_BOTH_DIR_INFO*>(buffer.data() + offset);
            const std::size_t chars = entry->FileNameLength / sizeof(wchar_t);
            const std::wstring value(entry->FileName, chars);
            if (value != L"." && value != L"..") {
                const std::filesystem::path leaf(value);
                std::string portable;
                if (!portable_leaf(leaf, portable) || names.size() >= maximum_entries) {
                    CloseHandle(duplicate);
                    names.clear();
                    return IoStatus::failure("directory_enumerate_invalid", "directory contains an invalid or excessive leaf");
                }
                names.push_back(leaf);
            }
            if (entry->NextEntryOffset == 0U) break;
            offset += entry->NextEntryOffset;
            if (offset >= buffer.size()) {
                CloseHandle(duplicate);
                names.clear();
                return IoStatus::failure("directory_enumerate_failed", "directory entry offset is invalid");
            }
        }
    }
    CloseHandle(duplicate);
#else
    const int duplicate = ::openat(impl_->handle, ".", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (duplicate < 0) return IoStatus::failure("directory_enumerate_failed", std::strerror(errno));
    DIR* directory = ::fdopendir(duplicate);
    if (directory == nullptr) {
        const std::string detail = std::strerror(errno);
        ::close(duplicate);
        return IoStatus::failure("directory_enumerate_failed", detail);
    }
    errno = 0;
    while (dirent* entry = ::readdir(directory)) {
        const std::string value(entry->d_name);
        if (value == "." || value == "..") continue;
        std::string portable;
        if (!portable_leaf(std::filesystem::path(value), portable) ||
            names.size() >= maximum_entries) {
            ::closedir(directory);
            names.clear();
            return IoStatus::failure("directory_enumerate_invalid", "directory contains an invalid or excessive leaf");
        }
        names.emplace_back(value);
    }
    const int enumeration_error = errno;
    if (::closedir(directory) != 0 && enumeration_error == 0) {
        names.clear();
        return IoStatus::failure("directory_enumerate_failed", std::strerror(errno));
    }
    if (enumeration_error != 0) {
        names.clear();
        return IoStatus::failure("directory_enumerate_failed", std::strerror(enumeration_error));
    }
#endif
    std::sort(names.begin(), names.end(), [](const auto& left, const auto& right) {
        return left.generic_u8string() < right.generic_u8string();
    });
    const IoStatus after = revalidate();
    if (!after.ok()) names.clear();
    return after;
}

struct DurableOutputFile::Impl {
    enum class RelativeNamespaceState { none, staging, published_unverified };
    NativeHandle handle = kInvalidHandle;
    NativeHandle parent_handle = kInvalidHandle;
    std::filesystem::path path;
    std::string staging_leaf;
    FileIdentity identity;
    bool relative_created = false;
    RelativeNamespaceState relative_state = RelativeNamespaceState::none;
    std::uint64_t next_offset = 0;
    std::uint64_t maximum_size = 0;
    void reset_relative_state() noexcept
    {
        relative_created = false;
        relative_state = RelativeNamespaceState::none;
        staging_leaf.clear();
        parent_handle = kInvalidHandle;
        identity = {};
        next_offset = 0;
        maximum_size = 0;
    }
    void close_owned_handles_noexcept() noexcept
    {
        close_native_handle_noexcept(handle);
        close_native_handle_noexcept(parent_handle);
    }
    ~Impl()
    {
#ifdef _WIN32
        if (handle != kInvalidHandle) CloseHandle(handle);
        if (parent_handle != kInvalidHandle) CloseHandle(parent_handle);
#else
        if (handle != kInvalidHandle) ::close(handle);
        if (parent_handle != kInvalidHandle) ::close(parent_handle);
#endif
    }
};

DurableOutputFile::DurableOutputFile() : impl_(std::make_unique<Impl>()) {}
DurableOutputFile::DurableOutputFile(DurableOutputFile&&) noexcept = default;
DurableOutputFile& DurableOutputFile::operator=(DurableOutputFile&&) noexcept = default;
DurableOutputFile::~DurableOutputFile() = default;

IoStatus testing_close_relative_staging_for_recovery(DurableOutputFile& output)
{
    auto& state = *output.impl_;
    if (state.handle == kInvalidHandle || state.parent_handle == kInvalidHandle ||
        !state.relative_created ||
        state.relative_state != DurableOutputFile::Impl::RelativeNamespaceState::staging)
        return IoStatus::failure("relative_recovery_not_staging", "");
#ifdef _WIN32
    if (!FlushFileBuffers(state.handle))
        return IoStatus::failure("output_flush_failed", windows_error("FlushFileBuffers"));
#else
    if (::fsync(state.handle) != 0)
        return IoStatus::failure("output_flush_failed", std::strerror(errno));
    const IoStatus flushed = flush_directory_handle(state.parent_handle);
    if (!flushed.ok()) return flushed;
#endif
    const IoStatus file_closed = close_native_handle(state.handle, "output_close_failed");
    if (!file_closed.ok()) return file_closed;
    return close_native_handle(state.parent_handle, "output_parent_close_failed");
}

IoStatus DurableOutputFile::create_exclusive(const std::filesystem::path& path, std::uint64_t maximum_size)
{
    if (impl_->handle != kInvalidHandle || impl_->parent_handle != kInvalidHandle ||
        impl_->relative_state != Impl::RelativeNamespaceState::none)
        return IoStatus::failure("output_already_open", path_to_utf8(path));
#ifdef _WIN32
    const std::wstring native_path = windows_extended_path(path);
    impl_->handle = CreateFileW(native_path.c_str(), GENERIC_WRITE | DELETE, 0,
        nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (impl_->handle == kInvalidHandle) return IoStatus::failure("output_create_failed", windows_error("CreateFileW"));
#else
    impl_->handle = ::open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (impl_->handle < 0) return IoStatus::failure("output_create_failed", std::strerror(errno));
#endif
    impl_->path = path;
    impl_->identity = {};
    impl_->next_offset = 0;
    impl_->maximum_size = maximum_size;
    return IoStatus::success();
}

IoStatus StableDirectoryObject::create_child_file_exclusive(
    const std::filesystem::path& leaf,
    std::uint64_t maximum_size,
    DurableOutputFile& child) const
{
    std::string name;
    if (!portable_leaf(leaf, name)) return IoStatus::failure("relative_leaf_invalid", path_to_utf8(leaf));
    if (!child.impl_ || child.impl_->handle != kInvalidHandle ||
        child.impl_->parent_handle != kInvalidHandle ||
        child.impl_->relative_state != DurableOutputFile::Impl::RelativeNamespaceState::none)
        return IoStatus::failure("output_already_open", name);
    const IoStatus valid = revalidate();
    if (!valid.ok()) return valid;
    NativeHandle parent = kInvalidHandle;
    if (!duplicate_handle(impl_->handle, parent)) {
#ifdef _WIN32
        return IoStatus::failure("relative_parent_duplicate_failed", windows_error("DuplicateHandle"));
#else
        return IoStatus::failure("relative_parent_duplicate_failed", std::strerror(errno));
#endif
    }
    NativeHandle file = kInvalidHandle;
#ifdef _WIN32
    IoStatus status = open_relative_windows(parent, name,
        GENERIC_WRITE | DELETE | FILE_READ_ATTRIBUTES, 2, 0x00200040, file, 0);
    if (!status.ok()) {
        CloseHandle(parent);
        return IoStatus::failure("relative_file_create_failed", status.detail);
    }
    BY_HANDLE_FILE_INFORMATION info {};
    if (!GetFileInformationByHandle(file, &info)) {
        const std::string detail = windows_error("GetFileInformationByHandle");
        CloseHandle(file);
        CloseHandle(parent);
        return IoStatus::failure("output_identity_failed", detail);
    }
    child.impl_->identity = identity_from_info(info);
#else
    file = ::openat(parent, name.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (file < 0) {
        const std::string detail = std::strerror(errno);
        ::close(parent);
        return IoStatus::failure("relative_file_create_failed", detail);
    }
    struct stat info {};
    if (::fstat(file, &info) != 0) {
        const std::string detail = std::strerror(errno);
        ::close(file);
        ::close(parent);
        return IoStatus::failure("output_identity_failed", detail);
    }
    child.impl_->identity = identity_from_stat(info);
#endif
    if (!child.impl_->identity.regular_file || child.impl_->identity.link_count != 1U) {
#ifdef _WIN32
        CloseHandle(file);
        CloseHandle(parent);
#else
        ::close(file);
        ::close(parent);
#endif
        return IoStatus::failure("output_not_regular", name);
    }
    child.impl_->handle = file;
    child.impl_->parent_handle = parent;
    child.impl_->path = impl_->path / leaf;
    child.impl_->staging_leaf = name;
    child.impl_->next_offset = 0;
    child.impl_->maximum_size = maximum_size;
    child.impl_->relative_created = true;
    child.impl_->relative_state = DurableOutputFile::Impl::RelativeNamespaceState::staging;
    return IoStatus::success();
}

IoStatus StableDirectoryObject::reopen_child_file_no_follow_for_relative_publish(
    const std::filesystem::path& leaf, const FileIdentity& expected,
    std::uint64_t maximum_size, DurableOutputFile& child) const
{
    std::string name;
    if (!portable_leaf(leaf, name)) return IoStatus::failure("relative_leaf_invalid", path_to_utf8(leaf));
    if (!expected.regular_file || expected.link_count != 1U || expected.size > maximum_size)
        return IoStatus::failure("relative_publish_identity_invalid", name);
    if (!child.impl_ || child.impl_->handle != kInvalidHandle ||
        child.impl_->parent_handle != kInvalidHandle ||
        child.impl_->relative_state != DurableOutputFile::Impl::RelativeNamespaceState::none)
        return IoStatus::failure("output_already_open", name);
    const IoStatus valid = revalidate();
    if (!valid.ok()) return valid;
    if (relative_publish_before_reopen_hook_for_testing != nullptr)
        relative_publish_before_reopen_hook_for_testing(impl_->path / leaf);
    NativeHandle parent = kInvalidHandle;
    if (!duplicate_handle(impl_->handle, parent)) {
#ifdef _WIN32
        return IoStatus::failure("relative_parent_duplicate_failed", windows_error("DuplicateHandle"));
#else
        return IoStatus::failure("relative_parent_duplicate_failed", std::strerror(errno));
#endif
    }
    NativeHandle file = kInvalidHandle;
    FileIdentity actual;
#ifdef _WIN32
    IoStatus opened = open_relative_windows(parent, name,
        GENERIC_WRITE | DELETE | FILE_READ_ATTRIBUTES | SYNCHRONIZE,
        1, 0x00200040, file, 0);
    if (!opened.ok()) { CloseHandle(parent); return IoStatus::failure("relative_publish_reopen_failed", opened.detail); }
    BY_HANDLE_FILE_INFORMATION info {};
    if (!GetFileInformationByHandle(file, &info)) {
        const std::string detail = windows_error("GetFileInformationByHandle");
        CloseHandle(file); CloseHandle(parent);
        return IoStatus::failure("relative_publish_identity_failed", detail);
    }
    actual = identity_from_info(info);
#else
    file = ::openat(parent, name.c_str(), O_WRONLY | O_NOFOLLOW | O_CLOEXEC);
    if (file < 0) { const std::string detail = std::strerror(errno); ::close(parent);
        return IoStatus::failure("relative_publish_reopen_failed", detail); }
    struct stat info {};
    if (::fstat(file, &info) != 0) { const std::string detail = std::strerror(errno);
        ::close(file); ::close(parent); return IoStatus::failure("relative_publish_identity_failed", detail); }
    actual = identity_from_stat(info);
#endif
    if (!expected.unchanged(actual) || !actual.regular_file || actual.link_count != 1U ||
        actual.size > maximum_size) {
#ifdef _WIN32
        CloseHandle(file); CloseHandle(parent);
#else
        ::close(file); ::close(parent);
#endif
        return IoStatus::failure("relative_publish_identity_changed", name);
    }
    // write_at tracks a logical offset; the reopened native handle must start
    // at the same offset before an interrupted relative copy can append.
    if (actual.size > static_cast<std::uint64_t>(
            std::numeric_limits<std::int64_t>::max())) {
#ifdef _WIN32
        CloseHandle(file); CloseHandle(parent);
#else
        ::close(file); ::close(parent);
#endif
        return IoStatus::failure("relative_publish_size_invalid", name);
    }
#ifdef _WIN32
    LARGE_INTEGER position {};
    position.QuadPart = static_cast<LONGLONG>(actual.size);
    if (!SetFilePointerEx(file, position, nullptr, FILE_BEGIN)) {
        const std::string detail = windows_error("SetFilePointerEx");
        CloseHandle(file); CloseHandle(parent);
        return IoStatus::failure("relative_publish_seek_failed", detail);
    }
#else
    if (::lseek(file, static_cast<off_t>(actual.size), SEEK_SET) < 0) {
        const std::string detail = std::strerror(errno);
        ::close(file); ::close(parent);
        return IoStatus::failure("relative_publish_seek_failed", detail);
    }
#endif
    child.impl_->handle = file;
    child.impl_->parent_handle = parent;
    child.impl_->path = impl_->path / leaf;
    child.impl_->staging_leaf = name;
    child.impl_->identity = actual;
    child.impl_->next_offset = actual.size;
    child.impl_->maximum_size = maximum_size;
    child.impl_->relative_created = true;
    child.impl_->relative_state = DurableOutputFile::Impl::RelativeNamespaceState::staging;
    return IoStatus::success();
}

std::size_t DurableOutputFile::write_at(std::uint64_t offset, const void* buffer, std::size_t size)
{
    if (impl_->handle == kInvalidHandle || offset != impl_->next_offset ||
        offset > impl_->maximum_size || size > impl_->maximum_size - offset) return 0;
#ifdef _WIN32
    DWORD written = 0;
    const DWORD requested = static_cast<DWORD>(std::min<std::size_t>(size, std::numeric_limits<DWORD>::max()));
    if (!WriteFile(impl_->handle, buffer, requested, &written, nullptr)) return 0;
    impl_->next_offset += written;
    return written;
#else
    const ssize_t written = ::write(impl_->handle, buffer, size);
    if (written <= 0) return 0;
    impl_->next_offset += static_cast<std::size_t>(written);
    return static_cast<std::size_t>(written);
#endif
}

IoStatus DurableOutputFile::flush_file_and_parent()
{
    if (impl_->handle == kInvalidHandle) {
        if (impl_->relative_created &&
            impl_->relative_state != Impl::RelativeNamespaceState::published_unverified) {
            const IoStatus parent_closed =
                close_native_handle(impl_->parent_handle, "output_parent_close_failed");
            impl_->reset_relative_state();
            if (!parent_closed.ok()) return parent_closed;
        }
        return IoStatus::failure("output_not_open", "");
    }
    IoStatus status;
#ifdef _WIN32
    if (!FlushFileBuffers(impl_->handle)) {
        status = IoStatus::failure("output_flush_failed", windows_error("FlushFileBuffers"));
    } else {
        status = IoStatus::success(DurabilityLevel::best_effort_platform_limit);
    }
#else
    if (::fsync(impl_->handle) != 0) {
        status = IoStatus::failure("output_flush_failed", std::strerror(errno));
    } else {
        status = IoStatus::success(DurabilityLevel::file_flushed);
    }
#endif
    const IoStatus file_closed = close_native_handle(impl_->handle, "output_close_failed");
    if (status.ok() && !file_closed.ok()) status = file_closed;

    if (impl_->relative_created) {
#ifndef _WIN32
        if (status.ok() && impl_->parent_handle != kInvalidHandle) {
            const IoStatus parent_flushed = flush_directory_handle(impl_->parent_handle);
            if (!parent_flushed.ok()) status = parent_flushed;
            else status = parent_flushed;
        }
#endif
        const IoStatus parent_closed = close_native_handle(impl_->parent_handle, "output_parent_close_failed");
        if (status.ok() && !parent_closed.ok()) status = parent_closed;
        impl_->reset_relative_state();
        return status;
    }
#ifdef _WIN32
    return status;
#else
    if (!status.ok()) return status;
    return flush_directory(impl_->path.parent_path());
#endif
}

IoStatus DurableOutputFile::publish_no_replace(
    const std::filesystem::path& destination)
{
    if (impl_->handle == kInvalidHandle) return IoStatus::failure("output_not_open", "");
#ifdef _WIN32
    if (!FlushFileBuffers(impl_->handle)) {
        return IoStatus::failure("output_flush_failed", windows_error("FlushFileBuffers"));
    }
    const std::wstring native_destination = windows_extended_path(destination);
    const std::size_t name_bytes = native_destination.size() * sizeof(wchar_t);
    std::vector<unsigned char> storage(sizeof(FILE_RENAME_INFO) + name_bytes, 0U);
    auto* rename = reinterpret_cast<FILE_RENAME_INFO*>(storage.data());
    rename->ReplaceIfExists = FALSE;
    rename->RootDirectory = nullptr;
    rename->FileNameLength = static_cast<DWORD>(name_bytes);
    std::memcpy(rename->FileName, native_destination.data(), name_bytes);
    if (!SetFileInformationByHandle(
            impl_->handle, FileRenameInfo, rename,
            static_cast<DWORD>(storage.size()))) {
        return IoStatus::failure(
            "commit_no_replace_failed",
            windows_error("SetFileInformationByHandle(FileRenameInfo)"));
    }
    if (!CloseHandle(impl_->handle)) {
        return IoStatus::failure("output_close_failed", windows_error("CloseHandle"));
    }
    impl_->handle = kInvalidHandle;
    impl_->path = destination;
    return IoStatus::success(DurabilityLevel::best_effort_platform_limit);
#else
    if (::fsync(impl_->handle) != 0) {
        return IoStatus::failure("output_flush_failed", std::strerror(errno));
    }
    struct stat held {};
    struct stat named {};
    if (::fstat(impl_->handle, &held) != 0 || ::lstat(impl_->path.c_str(), &named) != 0 ||
        held.st_dev != named.st_dev || held.st_ino != named.st_ino) {
        return IoStatus::failure(
            "commit_source_identity_changed", path_to_utf8(impl_->path));
    }
    if (::link(impl_->path.c_str(), destination.c_str()) != 0) {
        return IoStatus::failure("commit_no_replace_failed", std::strerror(errno));
    }
    struct stat published {};
    if (::fstat(impl_->handle, &held) != 0 || ::lstat(destination.c_str(), &published) != 0 ||
        held.st_dev != published.st_dev || held.st_ino != published.st_ino) {
        return IoStatus::failure(
            "commit_destination_identity_changed", path_to_utf8(destination));
    }
    if (::unlink(impl_->path.c_str()) != 0) {
        return IoStatus::failure("commit_source_remove_failed", std::strerror(errno));
    }
    if (::close(impl_->handle) != 0) {
        return IoStatus::failure("output_close_failed", std::strerror(errno));
    }
    impl_->handle = kInvalidHandle;
    const std::filesystem::path source_parent = impl_->path.parent_path();
    IoStatus source_flush = flush_directory(source_parent);
    if (!source_flush.ok()) return source_flush;
    impl_->path = destination;
    if (destination.parent_path() != source_parent) {
        return flush_directory(destination.parent_path());
    }
    return source_flush;
#endif
}

IoStatus DurableOutputFile::publish_sibling_no_replace(
    const std::filesystem::path& destination_leaf)
{
    std::string destination;
    if (!portable_leaf(destination_leaf, destination))
        return IoStatus::failure("relative_leaf_invalid", path_to_utf8(destination_leaf));
    if (impl_->handle == kInvalidHandle || !impl_->relative_created ||
        impl_->relative_state != Impl::RelativeNamespaceState::staging ||
        impl_->parent_handle == kInvalidHandle)
        return IoStatus::failure("relative_output_not_open", destination);
#ifdef _WIN32
    if (!FlushFileBuffers(impl_->handle))
        return IoStatus::failure("output_flush_failed", windows_error("FlushFileBuffers"));
    if (relative_publish_pre_rename_fault_countdown_for_testing != 0U &&
        --relative_publish_pre_rename_fault_countdown_for_testing == 0U)
        return IoStatus::failure("output_pre_rename_fault_injected", "test seam");
    BY_HANDLE_FILE_INFORMATION source_info {};
    if (!GetFileInformationByHandle(impl_->handle, &source_info) ||
        !impl_->identity.same_object(identity_from_info(source_info)) ||
        !identity_from_info(source_info).regular_file || source_info.nNumberOfLinks != 1U)
        return IoStatus::failure("commit_source_identity_changed", impl_->staging_leaf);
    std::wstring name(destination.begin(), destination.end());
    const std::size_t name_bytes = name.size() * sizeof(wchar_t);
    std::vector<unsigned char> storage(sizeof(FILE_RENAME_INFO) + name_bytes, 0U);
    auto* rename = reinterpret_cast<FILE_RENAME_INFO*>(storage.data());
    rename->ReplaceIfExists = FALSE;
    rename->RootDirectory = impl_->parent_handle;
    if (name_bytes > std::numeric_limits<DWORD>::max())
        return IoStatus::failure("relative_publish_unavailable", "destination leaf is too large");
    rename->FileNameLength = static_cast<DWORD>(name_bytes);
    std::memcpy(rename->FileName, name.data(), name_bytes);
    if (storage.size() > std::numeric_limits<ULONG>::max())
        return IoStatus::failure("relative_publish_unavailable", "rename information is too large");
    const SetRelativeInformation set_information = nt_set_information_file();
    if (!set_information)
        return IoStatus::failure("relative_publish_unavailable", "NtSetInformationFile unavailable");
    IO_STATUS_BLOCK rename_io {};
    const NTSTATUS rename_status = set_information(
        impl_->handle, &rename_io, rename, static_cast<ULONG>(storage.size()),
        static_cast<FILE_INFORMATION_CLASS>(10)); // FileRenameInformation
    if (rename_status < 0) return nt_rename_status(rename_status);
    impl_->relative_state = Impl::RelativeNamespaceState::published_unverified;
    impl_->staging_leaf = destination;
    impl_->path = impl_->path.parent_path() / destination_leaf;
    const auto fail_after_namespace_rename = [&](IoStatus failure) {
        impl_->close_owned_handles_noexcept();
        return published_unverified_failure(failure);
    };
    if (relative_publish_post_rename_fault_for_testing) {
        return fail_after_namespace_rename(
            IoStatus::failure("output_post_rename_fault_injected", "test seam"));
    }
    if (!FlushFileBuffers(impl_->handle)) {
        return fail_after_namespace_rename(
            IoStatus::failure("output_flush_failed", windows_error("FlushFileBuffers")));
    }
    const IoStatus file_closed = close_native_handle(impl_->handle, "output_close_failed");
    if (!file_closed.ok()) return fail_after_namespace_rename(file_closed);
    HANDLE published = kInvalidHandle;
    IoStatus published_status = open_relative_windows(impl_->parent_handle, destination,
        FILE_READ_ATTRIBUTES, 1, 0x00200040, published);
    if (!published_status.ok()) return fail_after_namespace_rename(published_status);
    BY_HANDLE_FILE_INFORMATION published_info {};
    const bool published_ok = GetFileInformationByHandle(published, &published_info) != 0;
    const IoStatus published_closed = close_native_handle(published, "output_close_failed");
    const FileIdentity published_identity = identity_from_info(published_info);
    if (!published_ok || !impl_->identity.same_object(published_identity) ||
        !published_identity.regular_file || published_identity.link_count != 1U) {
        return fail_after_namespace_rename(
            IoStatus::failure("commit_destination_identity_changed", destination));
    }
    if (!published_closed.ok()) return fail_after_namespace_rename(published_closed);
    const IoStatus parent_closed = close_native_handle(impl_->parent_handle, "output_parent_close_failed");
    if (!parent_closed.ok()) return fail_after_namespace_rename(parent_closed);
    impl_->reset_relative_state();
    return IoStatus::success(DurabilityLevel::best_effort_platform_limit);
#else
    if (::fsync(impl_->handle) != 0)
        return IoStatus::failure("output_flush_failed", std::strerror(errno));
    if (relative_publish_pre_rename_fault_countdown_for_testing != 0U &&
        --relative_publish_pre_rename_fault_countdown_for_testing == 0U)
        return IoStatus::failure("output_pre_rename_fault_injected", "test seam");
    struct stat held {};
    struct stat named {};
    if (::fstat(impl_->handle, &held) != 0 ||
        ::fstatat(impl_->parent_handle, impl_->staging_leaf.c_str(), &named, AT_SYMLINK_NOFOLLOW) != 0 ||
        held.st_dev != named.st_dev || held.st_ino != named.st_ino || !S_ISREG(named.st_mode) ||
        held.st_nlink != 1 || named.st_nlink != 1)
        return IoStatus::failure("commit_source_identity_changed", impl_->staging_leaf);
#if defined(__linux__) && defined(SYS_renameat2)
    if (::syscall(SYS_renameat2, impl_->parent_handle, impl_->staging_leaf.c_str(),
            impl_->parent_handle, destination.c_str(), 1U) != 0)
        return IoStatus::failure("commit_no_replace_failed", std::strerror(errno));
#elif defined(__APPLE__)
    if (::renameatx_np(impl_->parent_handle, impl_->staging_leaf.c_str(),
            impl_->parent_handle, destination.c_str(), RENAME_EXCL) != 0)
        return IoStatus::failure("commit_no_replace_failed", std::strerror(errno));
#else
    return IoStatus::failure("commit_no_replace_unsupported", "atomic relative no-replace rename unavailable");
#endif
    impl_->relative_state = Impl::RelativeNamespaceState::published_unverified;
    impl_->staging_leaf = destination;
    impl_->path = impl_->path.parent_path() / destination_leaf;
    const auto fail_after_namespace_rename = [&](IoStatus failure) {
        impl_->close_owned_handles_noexcept();
        return published_unverified_failure(failure);
    };
    if (relative_publish_post_rename_fault_for_testing) {
        return fail_after_namespace_rename(
            IoStatus::failure("output_post_rename_fault_injected", "test seam"));
    }
    struct stat published {};
    if (::fstatat(impl_->parent_handle, destination.c_str(), &published, AT_SYMLINK_NOFOLLOW) != 0 ||
        held.st_dev != published.st_dev || held.st_ino != published.st_ino || !S_ISREG(published.st_mode) ||
        published.st_nlink != 1) {
        return fail_after_namespace_rename(
            IoStatus::failure("commit_destination_identity_changed", destination));
    }
    const IoStatus file_closed = close_native_handle(impl_->handle, "output_close_failed");
    if (!file_closed.ok()) return fail_after_namespace_rename(file_closed);
    IoStatus flushed = flush_directory_handle(impl_->parent_handle);
    if (!flushed.ok()) return fail_after_namespace_rename(flushed);
    const IoStatus parent_closed = close_native_handle(impl_->parent_handle, "output_parent_close_failed");
    if (!parent_closed.ok()) return fail_after_namespace_rename(parent_closed);
    impl_->reset_relative_state();
    return flushed;
#endif
}

IoStatus DurableOutputFile::discard_open()
{
    if (impl_->relative_state == Impl::RelativeNamespaceState::published_unverified) {
        impl_->close_owned_handles_noexcept();
        return IoStatus::failure("output_published_unverified", "published output requires manual recovery");
    }
    if (impl_->handle == kInvalidHandle && impl_->parent_handle == kInvalidHandle) {
        impl_->reset_relative_state();
        return IoStatus::success();
    }
    IoStatus status = IoStatus::success();
#ifdef _WIN32
    FILE_DISPOSITION_INFO disposition {};
    disposition.DeleteFile = TRUE;
    if (impl_->handle != kInvalidHandle && !SetFileInformationByHandle(
            impl_->handle, FileDispositionInfo, &disposition,
            static_cast<DWORD>(sizeof(disposition)))) {
        status = IoStatus::failure(
            "output_discard_failed",
            windows_error("SetFileInformationByHandle(FileDispositionInfo)"));
    }
    const IoStatus file_closed = close_native_handle(impl_->handle, "output_close_failed");
    if (status.ok() && !file_closed.ok()) status = file_closed;
    if (status.ok()) status = IoStatus::success(DurabilityLevel::best_effort_platform_limit);
#else
    const IoStatus file_closed = close_native_handle(impl_->handle, "output_close_failed");
    if (!file_closed.ok()) status = file_closed;
    if (status.ok()) status = IoStatus::failure(
        "output_discard_preserved",
        impl_->relative_created
            ? "relative staging file is preserved for recovery"
            : "open temporary is preserved because handle-owned unlink is unavailable");
#endif
    const IoStatus parent_closed = close_native_handle(impl_->parent_handle, "output_parent_close_failed");
    if (status.ok() && !parent_closed.ok()) status = parent_closed;
    impl_->reset_relative_state();
    return status;
}
void DurableOutputFile::close_without_flush() noexcept
{
    impl_->close_owned_handles_noexcept();
    if (impl_->relative_state != Impl::RelativeNamespaceState::published_unverified)
        impl_->reset_relative_state();
}
const std::filesystem::path& DurableOutputFile::path() const noexcept { return impl_->path; }
const FileIdentity& DurableOutputFile::identity() const noexcept { return impl_->identity; }

IoStatus commit_no_replace(const std::filesystem::path& source, const std::filesystem::path& destination)
{
#ifdef _WIN32
    const std::wstring native_source = windows_extended_path(source);
    const std::wstring native_destination = windows_extended_path(destination);
    if (!MoveFileExW(native_source.c_str(), native_destination.c_str(), MOVEFILE_WRITE_THROUGH)) {
        return IoStatus::failure("commit_no_replace_failed", windows_error("MoveFileExW"));
    }
    return IoStatus::success(DurabilityLevel::best_effort_platform_limit);
#else
    if (::link(source.c_str(), destination.c_str()) != 0) return IoStatus::failure("commit_no_replace_failed", std::strerror(errno));
    if (::unlink(source.c_str()) != 0) return IoStatus::failure("commit_source_remove_failed", std::strerror(errno));
    IoStatus source_flush = flush_directory(source.parent_path());
    if (!source_flush.ok()) return source_flush;
    if (destination.parent_path() != source.parent_path()) return flush_directory(destination.parent_path());
    return source_flush;
#endif
}

IoStatus replace_existing_durable(const std::filesystem::path& source, const std::filesystem::path& destination)
{
#ifdef _WIN32
    const std::wstring native_source = windows_extended_path(source);
    const std::wstring native_destination = windows_extended_path(destination);
    if (!MoveFileExW(native_source.c_str(), native_destination.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        return IoStatus::failure("replace_existing_failed", windows_error("MoveFileExW"));
    }
    return IoStatus::success(DurabilityLevel::best_effort_platform_limit);
#else
    if (::rename(source.c_str(), destination.c_str()) != 0) {
        return IoStatus::failure("replace_existing_failed", std::strerror(errno));
    }
    IoStatus source_flush = flush_directory(source.parent_path());
    if (!source_flush.ok()) return source_flush;
    if (destination.parent_path() != source.parent_path()) return flush_directory(destination.parent_path());
    return source_flush;
#endif
}

IoStatus remove_exact_object(const std::filesystem::path& path, const FileIdentity& expected)
{
    StableInputFile current;
    IoStatus status = current.open_no_follow(path);
    if (!status.ok()) return status;
    if (!current.identity().same_object(expected)) return IoStatus::failure("remove_identity_mismatch", path_to_utf8(path));
#ifdef _WIN32
    const std::wstring native_path = windows_extended_path(path);
    if (!DeleteFileW(native_path.c_str())) return IoStatus::failure("remove_failed", windows_error("DeleteFileW"));
#else
    if (::unlink(path.c_str()) != 0) return IoStatus::failure("remove_failed", std::strerror(errno));
    return flush_directory(path.parent_path());
#endif
    return IoStatus::success(DurabilityLevel::best_effort_platform_limit);
}

IoStatus inspect_path_no_follow(
    const std::filesystem::path& path,
    PathIdentity& identity)
{
    identity = {};
#ifdef _WIN32
    const std::wstring native_path = windows_extended_path(path);
    HANDLE handle = CreateFileW(
        native_path.c_str(), FILE_READ_ATTRIBUTES,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        nullptr, OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
        nullptr);
    if (handle == INVALID_HANDLE_VALUE) {
        const DWORD error = GetLastError();
        if (error == ERROR_FILE_NOT_FOUND || error == ERROR_PATH_NOT_FOUND) {
            identity.kind = PathObjectKind::absent;
            return IoStatus::success();
        }
        return IoStatus::failure("path_identity_failed", windows_error("CreateFileW"));
    }
    BY_HANDLE_FILE_INFORMATION info {};
    if (!GetFileInformationByHandle(handle, &info)) {
        const std::string detail = windows_error("GetFileInformationByHandle");
        CloseHandle(handle);
        return IoStatus::failure("path_identity_failed", detail);
    }
    identity = path_identity_from_info(path, handle, info);
    CloseHandle(handle);
#else
    struct stat info {};
    if (::lstat(path.c_str(), &info) != 0) {
        if (errno == ENOENT || errno == ENOTDIR) {
            identity.kind = PathObjectKind::absent;
            return IoStatus::success();
        }
        return IoStatus::failure("path_identity_failed", std::strerror(errno));
    }
    identity = path_identity_from_stat(info);
#endif
    return IoStatus::success();
}

std::filesystem::path path_from_utf8(const std::string& value) { return std::filesystem::u8path(value); }
std::string path_to_utf8(const std::filesystem::path& value) { return value.u8string(); }

} // namespace facman::platform
