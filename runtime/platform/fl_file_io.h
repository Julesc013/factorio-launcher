// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_PLATFORM_FILE_IO_H
#define FACMAN_PLATFORM_FILE_IO_H

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <functional>
#include <memory>
#include <string>
#include <vector>

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

// Distinct existing-file capability; read-only inputs retain their original rights.
class RetainedStreamRewriteFile;
enum class RetainedStreamRewriteState { original_only, mutation_authorized, terminal_verify_only };

class RetainedStreamRewriteFile {
public:
    RetainedStreamRewriteFile();
    RetainedStreamRewriteFile(RetainedStreamRewriteFile&&) noexcept;
    RetainedStreamRewriteFile& operator=(RetainedStreamRewriteFile&&) noexcept;
    ~RetainedStreamRewriteFile();
    RetainedStreamRewriteFile(const RetainedStreamRewriteFile&) = delete;
    RetainedStreamRewriteFile& operator=(const RetainedStreamRewriteFile&) = delete;

    // Reads through the exact retained writer, without another path open.
    IoStatus observe(std::string& bytes, FileIdentity& identity) const;
    // Caller must durably admit mutation before opening as mutation_authorized.
    // First write, recovery, and terminal verification remain domain authority.
    IoStatus rewrite_to_intended();
    // Caller must first persist its domain pre-write checkpoint. Keeps the
    // same original-only handle; no release/reopen or file effect here.
    IoStatus admit_durable_mutation();
    IoStatus readable_metadata_identity(std::string& identity) const;
    const std::filesystem::path& path() const noexcept;
    IoStatus verify_intended() const;
    bool open() const noexcept;

private:
    friend class StableDirectoryObject;
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
    // Read-only verification while a separate publication handle owns DELETE.
    // Existing opens retain their original deny-delete sharing policy.
    IoStatus open_no_follow_for_publication_verification(const std::filesystem::path& path);
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
    // Distinct single-component UTF-8 creation. Rejects namespace escapes and
    // malformed UTF-8; preserves code points, spaces and platform name limits.
    // Callers still admit complete paths/collisions under their domain policy.
    IoStatus create_child_directory_exclusive_utf8(
        const std::string& leaf, StableDirectoryObject& child) const;
    IoStatus open_child_file_no_follow_pinned(
        const std::filesystem::path& leaf, StableInputFile& child) const;
    IoStatus open_child_file_no_follow_for_retained_rewrite(
        const std::filesystem::path& leaf, const FileIdentity& original_identity,
        const std::string& original, const std::string& intended,
        RetainedStreamRewriteState state, RetainedStreamRewriteFile& file) const;
    // Re-adopts an already pinned, exact staging sibling for a no-replace
    // handle-relative publication after process-loss recovery.
    IoStatus reopen_child_file_no_follow_for_relative_publish(
        const std::filesystem::path& leaf,
        const FileIdentity& expected,
        std::uint64_t maximum_size,
        DurableOutputFile& child) const;
    // Returns the conservative leaf names currently visible through this held
    // directory object.  The result is cleared before every attempt and on
    // failure, is sorted bytewise, and never follows a child.
    IoStatus list_child_names_bounded(
        std::size_t maximum_entries,
        std::vector<std::filesystem::path>& names) const;
    // Windows deletes through the same exclusive child handle used for identity
    // and content verification. POSIX removes only the recorded leaf relative
    // to the held parent after verification; its final-leaf replacement window
    // remains because the platform has no atomic compare-and-unlink operation.
    IoStatus remove_child_file_no_follow_if_matches(
        const std::filesystem::path& leaf, const FileIdentity& expected,
        const std::function<bool(const StableInputFile&)>& verify_content) const;
    IoStatus remove_child_empty_directory_no_follow_if_matches(
        const std::filesystem::path& leaf, const PathIdentity& expected) const;
    IoStatus create_child_file_exclusive(
        const std::filesystem::path& leaf,
        std::uint64_t maximum_size,
        DurableOutputFile& child) const;
    IoStatus create_child_file_exclusive_utf8(
        const std::string& leaf, std::uint64_t maximum_size,
        DurableOutputFile& child) const;
    IoStatus flush_metadata() const;
    const PathIdentity& identity() const noexcept;
    const std::filesystem::path& path() const noexcept;
    bool open() const noexcept;

private:
    friend class DurableOutputFile;
    friend class PrivatePublicationFile;
    IoStatus open_no_follow_impl(const std::filesystem::path& path, bool relative_writes,
        bool allow_publication_handle = false);
    IoStatus open_child_directory_no_follow_impl(
        const std::filesystem::path& leaf,
        StableDirectoryObject& child,
        bool relative_writes) const;
    IoStatus create_child_directory_exclusive_impl(
        const std::filesystem::path& leaf, const std::string& name,
        StableDirectoryObject& child) const;
    IoStatus create_child_file_exclusive_impl(
        const std::filesystem::path& leaf, const std::string& name,
        std::uint64_t maximum_size, DurableOutputFile& child) const;
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

#ifndef _WIN32
// An unpublished, pathname-free copy of verified bytes. Publication is a
// no-replace link (Linux) or descriptor-source clone (macOS).
class PrivatePublicationFile {
public:
    PrivatePublicationFile();
    ~PrivatePublicationFile();
    PrivatePublicationFile(const PrivatePublicationFile&) = delete;
    PrivatePublicationFile& operator=(const PrivatePublicationFile&) = delete;

    IoStatus create(const StableDirectoryObject& staging_parent,
        const StableDirectoryObject& destination_parent,
        std::uint64_t maximum_size);
    std::size_t write_at(std::uint64_t offset, const void* data, std::size_t size);
    IoStatus publish_no_replace(const std::filesystem::path& destination_leaf);

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};
#endif

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
    IoStatus publish_in_directory_no_replace(
        const StableDirectoryObject& destination_parent,
        const std::filesystem::path& destination_leaf);
    IoStatus discard_open();
    void close_without_flush() noexcept;
    const std::filesystem::path& path() const noexcept;
    const FileIdentity& identity() const noexcept;

private:
    friend class StableDirectoryObject;
    friend IoStatus testing_close_relative_staging_for_recovery(DurableOutputFile& output);
    IoStatus publish_relative_no_replace(
        const StableDirectoryObject* destination_parent,
        const std::filesystem::path& destination_leaf);
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

// Test seam: durably closes a relative staging file without namespace cleanup,
// simulating a process that exits between staging and publication.
IoStatus testing_close_relative_staging_for_recovery(DurableOutputFile& output);

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
// Test-only one-shot countdown fault before namespace rename.  A value of one
// faults the next relative publication and leaves its staging leaf in place.
void set_relative_publish_pre_rename_fault_countdown(unsigned count) noexcept;
using RelativePublishBeforeReopenHook = void (*)(const std::filesystem::path&);
void set_relative_publish_before_reopen_hook(RelativePublishBeforeReopenHook hook) noexcept;

} // namespace testing

namespace testing { void set_retained_stream_rewrite_phase_hook(void (*hook)(const char*)); void set_retained_stream_rewrite_flush_fault(bool enabled); }
} // namespace facman::platform

#endif
