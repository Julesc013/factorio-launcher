// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_PLATFORM_FILE_IO_H
#define FACMAN_PLATFORM_FILE_IO_H

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <memory>
#include <string>

namespace facman::platform {

class DurableOutputFile;

enum class DurabilityLevel {
    none,
    file_flushed,
    file_and_directory_flushed,
    best_effort_platform_limit,
    unsupported_filesystem,
};

struct IoStatus {
    std::string code;
    std::string detail;
    DurabilityLevel durability = DurabilityLevel::none;
    bool ok() const noexcept { return code.empty(); }
    static IoStatus success(DurabilityLevel durability = DurabilityLevel::none)
    {
        return {"", "", durability};
    }
    static IoStatus failure(std::string code, std::string detail)
    {
        return {std::move(code), std::move(detail)};
    }
};

struct FileIdentity {
    std::uint64_t device = 0;
    std::uint64_t object = 0;
    std::uint64_t size = 0;
    std::uint64_t link_count = 0;
    bool regular_file = false;

    bool same_object(const FileIdentity& other) const noexcept
    {
        return device == other.device && object == other.object;
    }
    bool unchanged(const FileIdentity& other) const noexcept
    {
        return same_object(other) && size == other.size && link_count == other.link_count &&
            regular_file == other.regular_file;
    }
};

enum class PathObjectKind {
    absent,
    regular_file,
    directory,
    other,
};

struct PathIdentity {
    bool exists = false;
    bool reparse_or_link = false;
    bool fixed_local_volume = false;
    PathObjectKind kind = PathObjectKind::absent;
    std::uint64_t device = 0;
    std::uint64_t object = 0;
    std::uint64_t size = 0;
    std::uint64_t last_write_ticks = 0;
    std::string filesystem_name;

    bool same_object(const PathIdentity& other) const noexcept
    {
        return exists == other.exists && kind == other.kind &&
            (!exists || (device == other.device && object == other.object));
    }
    bool unchanged(const PathIdentity& other) const noexcept
    {
        return same_object(other) && reparse_or_link == other.reparse_or_link &&
            fixed_local_volume == other.fixed_local_volume && size == other.size &&
            last_write_ticks == other.last_write_ticks &&
            filesystem_name == other.filesystem_name;
    }
};

class StableInputFile {
public:
    StableInputFile();
    StableInputFile(StableInputFile&&) noexcept;
    StableInputFile& operator=(StableInputFile&&) noexcept;
    ~StableInputFile();
    StableInputFile(const StableInputFile&) = delete;
    StableInputFile& operator=(const StableInputFile&) = delete;

    IoStatus open_no_follow(const std::filesystem::path& path);
    IoStatus open_no_follow_pinned(const std::filesystem::path& path);
    std::size_t read_at(std::uint64_t offset, void* buffer, std::size_t size) const;
    IoStatus revalidate() const;
    IoStatus revalidate_path() const;
    const FileIdentity& identity() const noexcept;
    std::uint64_t size() const noexcept;
    bool open() const noexcept;

private:
    friend class StableDirectoryObject;
    IoStatus open_no_follow_impl(const std::filesystem::path& path, bool pinned);
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

class StableDirectoryObject {
public:
    StableDirectoryObject();
    StableDirectoryObject(StableDirectoryObject&&) noexcept;
    StableDirectoryObject& operator=(StableDirectoryObject&&) noexcept;
    ~StableDirectoryObject();
    StableDirectoryObject(const StableDirectoryObject&) = delete;
    StableDirectoryObject& operator=(const StableDirectoryObject&) = delete;

    IoStatus open_no_follow(const std::filesystem::path& path);
    IoStatus open_no_follow_for_relative_writes(const std::filesystem::path& path);
    IoStatus revalidate() const;
    IoStatus validate_descendant(
        const std::filesystem::path& path,
        bool allow_absent_leaf = false) const;
    // These operations accept one conservative portable filename component and
    // resolve it from the held directory object, never from a reconstructed path.
    IoStatus open_child_directory_no_follow(
        const std::filesystem::path& leaf, StableDirectoryObject& child) const;
    // Opens an existing plain child directory with the capability required for
    // handle-relative exclusive child creation.
    IoStatus open_child_directory_no_follow_for_relative_writes(
        const std::filesystem::path& leaf, StableDirectoryObject& child) const;
    IoStatus create_child_directory_exclusive(
        const std::filesystem::path& leaf, StableDirectoryObject& child) const;
    IoStatus open_child_file_no_follow_pinned(
        const std::filesystem::path& leaf, StableInputFile& child) const;
    IoStatus create_child_file_exclusive(
        const std::filesystem::path& leaf,
        std::uint64_t maximum_size,
        DurableOutputFile& child) const;
    IoStatus flush_metadata() const;
    const PathIdentity& identity() const noexcept;
    const std::filesystem::path& path() const noexcept;
    bool open() const noexcept;

private:
    friend class DurableOutputFile;
    IoStatus open_no_follow_impl(const std::filesystem::path& path, bool relative_writes);
    IoStatus open_child_directory_no_follow_impl(
        const std::filesystem::path& leaf,
        StableDirectoryObject& child,
        bool relative_writes) const;
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

class DurableOutputFile {
public:
    DurableOutputFile();
    DurableOutputFile(DurableOutputFile&&) noexcept;
    DurableOutputFile& operator=(DurableOutputFile&&) noexcept;
    ~DurableOutputFile();
    DurableOutputFile(const DurableOutputFile&) = delete;
    DurableOutputFile& operator=(const DurableOutputFile&) = delete;

    IoStatus create_exclusive(const std::filesystem::path& path, std::uint64_t maximum_size);
    std::size_t write_at(std::uint64_t offset, const void* buffer, std::size_t size);
    IoStatus flush_file_and_parent();
    IoStatus publish_no_replace(const std::filesystem::path& destination);
    IoStatus publish_sibling_no_replace(const std::filesystem::path& destination_leaf);
    IoStatus discard_open();
    void close_without_flush() noexcept;
    const std::filesystem::path& path() const noexcept;

private:
    friend class StableDirectoryObject;
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

IoStatus commit_no_replace(
    const std::filesystem::path& source,
    const std::filesystem::path& destination);
IoStatus replace_existing_durable(
    const std::filesystem::path& source,
    const std::filesystem::path& destination);
IoStatus remove_exact_object(
    const std::filesystem::path& path,
    const FileIdentity& expected);
IoStatus inspect_path_no_follow(
    const std::filesystem::path& path,
    PathIdentity& identity);
std::filesystem::path path_from_utf8(const std::string& value);
std::string path_to_utf8(const std::filesystem::path& value);

namespace testing {

// Test-only, thread-local fault seam for the post-rename recovery boundary.
void set_relative_publish_post_rename_fault(bool enabled) noexcept;

} // namespace testing

} // namespace facman::platform

#endif
