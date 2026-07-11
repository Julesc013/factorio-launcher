// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_file_io.h"

#include <algorithm>
#include <cerrno>
#include <cstring>
#include <limits>

#ifdef _WIN32
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#endif

namespace facman::platform {
namespace {

#ifdef _WIN32
using NativeHandle = HANDLE;
const NativeHandle kInvalidHandle = INVALID_HANDLE_VALUE;

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

IoStatus flush_directory(const std::filesystem::path& directory)
{
    const int handle = ::open(directory.c_str(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
    if (handle < 0) return IoStatus::failure("directory_open_failed", std::strerror(errno));
    const int result = ::fsync(handle);
    const int error = errno;
    ::close(handle);
    return result == 0 ? IoStatus::success() : IoStatus::failure("directory_flush_failed", std::strerror(error));
}
#endif

} // namespace

struct StableInputFile::Impl {
    NativeHandle handle = kInvalidHandle;
    FileIdentity identity;
};

StableInputFile::StableInputFile() : impl_(std::make_unique<Impl>()) {}
StableInputFile::StableInputFile(StableInputFile&&) noexcept = default;
StableInputFile& StableInputFile::operator=(StableInputFile&&) noexcept = default;
StableInputFile::~StableInputFile()
{
#ifdef _WIN32
    if (impl_ && impl_->handle != kInvalidHandle) CloseHandle(impl_->handle);
#else
    if (impl_ && impl_->handle != kInvalidHandle) ::close(impl_->handle);
#endif
}

IoStatus StableInputFile::open_no_follow(const std::filesystem::path& path)
{
    if (open()) return IoStatus::failure("input_already_open", path_to_utf8(path));
#ifdef _WIN32
    impl_->handle = CreateFileW(
        path.c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_DELETE, nullptr, OPEN_EXISTING,
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
    if (!impl_->identity.regular_file) {
#ifdef _WIN32
        CloseHandle(impl_->handle);
#else
        ::close(impl_->handle);
#endif
        impl_->handle = kInvalidHandle;
        return IoStatus::failure("input_not_regular", path_to_utf8(path));
    }
    return IoStatus::success();
}

std::size_t StableInputFile::read_at(std::uint64_t offset, void* buffer, std::size_t size) const
{
    if (!open() || offset >= impl_->identity.size) return 0;
    size = static_cast<std::size_t>(std::min<std::uint64_t>(size, impl_->identity.size - offset));
#ifdef _WIN32
    OVERLAPPED operation {};
    operation.Offset = static_cast<DWORD>(offset);
    operation.OffsetHigh = static_cast<DWORD>(offset >> 32);
    DWORD read = 0;
    const DWORD requested = static_cast<DWORD>(std::min<std::size_t>(size, std::numeric_limits<DWORD>::max()));
    if (!ReadFile(impl_->handle, buffer, requested, &read, &operation)) return 0;
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
const FileIdentity& StableInputFile::identity() const noexcept { return impl_->identity; }
std::uint64_t StableInputFile::size() const noexcept { return impl_->identity.size; }
bool StableInputFile::open() const noexcept { return impl_ && impl_->handle != kInvalidHandle; }

struct DurableOutputFile::Impl {
    NativeHandle handle = kInvalidHandle;
    std::filesystem::path path;
    std::uint64_t next_offset = 0;
    std::uint64_t maximum_size = 0;
};

DurableOutputFile::DurableOutputFile() : impl_(std::make_unique<Impl>()) {}
DurableOutputFile::DurableOutputFile(DurableOutputFile&&) noexcept = default;
DurableOutputFile& DurableOutputFile::operator=(DurableOutputFile&&) noexcept = default;
DurableOutputFile::~DurableOutputFile()
{
#ifdef _WIN32
    if (impl_ && impl_->handle != kInvalidHandle) CloseHandle(impl_->handle);
#else
    if (impl_ && impl_->handle != kInvalidHandle) ::close(impl_->handle);
#endif
}

IoStatus DurableOutputFile::create_exclusive(const std::filesystem::path& path, std::uint64_t maximum_size)
{
    if (impl_->handle != kInvalidHandle) return IoStatus::failure("output_already_open", path_to_utf8(path));
#ifdef _WIN32
    impl_->handle = CreateFileW(path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (impl_->handle == kInvalidHandle) return IoStatus::failure("output_create_failed", windows_error("CreateFileW"));
#else
    impl_->handle = ::open(path.c_str(), O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (impl_->handle < 0) return IoStatus::failure("output_create_failed", std::strerror(errno));
#endif
    impl_->path = path;
    impl_->maximum_size = maximum_size;
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
    if (impl_->handle == kInvalidHandle) return IoStatus::failure("output_not_open", "");
#ifdef _WIN32
    if (!FlushFileBuffers(impl_->handle)) return IoStatus::failure("output_flush_failed", windows_error("FlushFileBuffers"));
    if (!CloseHandle(impl_->handle)) return IoStatus::failure("output_close_failed", windows_error("CloseHandle"));
    impl_->handle = kInvalidHandle;
    return IoStatus::success();
#else
    if (::fsync(impl_->handle) != 0) return IoStatus::failure("output_flush_failed", std::strerror(errno));
    if (::close(impl_->handle) != 0) return IoStatus::failure("output_close_failed", std::strerror(errno));
    impl_->handle = kInvalidHandle;
    return flush_directory(impl_->path.parent_path());
#endif
}
void DurableOutputFile::close_without_flush() noexcept
{
    if (impl_->handle == kInvalidHandle) return;
#ifdef _WIN32
    CloseHandle(impl_->handle);
#else
    ::close(impl_->handle);
#endif
    impl_->handle = kInvalidHandle;
}
const std::filesystem::path& DurableOutputFile::path() const noexcept { return impl_->path; }

IoStatus commit_no_replace(const std::filesystem::path& source, const std::filesystem::path& destination)
{
#ifdef _WIN32
    if (!MoveFileExW(source.c_str(), destination.c_str(), MOVEFILE_WRITE_THROUGH)) {
        return IoStatus::failure("commit_no_replace_failed", windows_error("MoveFileExW"));
    }
    return IoStatus::success();
#else
    if (::link(source.c_str(), destination.c_str()) != 0) return IoStatus::failure("commit_no_replace_failed", std::strerror(errno));
    if (::unlink(source.c_str()) != 0) return IoStatus::failure("commit_source_remove_failed", std::strerror(errno));
    IoStatus source_flush = flush_directory(source.parent_path());
    if (!source_flush.ok()) return source_flush;
    if (destination.parent_path() != source.parent_path()) return flush_directory(destination.parent_path());
    return IoStatus::success();
#endif
}

IoStatus replace_existing_durable(const std::filesystem::path& source, const std::filesystem::path& destination)
{
#ifdef _WIN32
    if (!MoveFileExW(source.c_str(), destination.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)) {
        return IoStatus::failure("replace_existing_failed", windows_error("MoveFileExW"));
    }
    return IoStatus::success();
#else
    if (::rename(source.c_str(), destination.c_str()) != 0) {
        return IoStatus::failure("replace_existing_failed", std::strerror(errno));
    }
    IoStatus source_flush = flush_directory(source.parent_path());
    if (!source_flush.ok()) return source_flush;
    if (destination.parent_path() != source.parent_path()) return flush_directory(destination.parent_path());
    return IoStatus::success();
#endif
}

IoStatus remove_exact_object(const std::filesystem::path& path, const FileIdentity& expected)
{
    StableInputFile current;
    IoStatus status = current.open_no_follow(path);
    if (!status.ok()) return status;
    if (!current.identity().same_object(expected)) return IoStatus::failure("remove_identity_mismatch", path_to_utf8(path));
#ifdef _WIN32
    if (!DeleteFileW(path.c_str())) return IoStatus::failure("remove_failed", windows_error("DeleteFileW"));
#else
    if (::unlink(path.c_str()) != 0) return IoStatus::failure("remove_failed", std::strerror(errno));
    return flush_directory(path.parent_path());
#endif
    return IoStatus::success();
}

std::filesystem::path path_from_utf8(const std::string& value) { return std::filesystem::u8path(value); }
std::string path_to_utf8(const std::filesystem::path& value) { return value.u8string(); }

} // namespace facman::platform
