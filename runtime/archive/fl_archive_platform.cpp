#include "fl_archive_platform.h"

#include "fl_path_safety.h"

#include <algorithm>
#include <cerrno>
#include <cstring>
#include <system_error>

#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#else
#include <unistd.h>
#endif

namespace facman::archive {

const char* owned_staging_marker_name()
{
    return ".facman-archive-staging.v1";
}

Status RandomAccessFile::open(const std::filesystem::path& path)
{
    std::string link_detail;
    if (facman::base::path_crosses_link_or_reparse_point(path, link_detail)) {
        return Status::failure("archive_source_link_refused", link_detail);
    }
    const auto opened = file_.open_no_follow(path);
    if (!opened.ok()) return Status::failure("archive_source_open_failed", opened.detail);
    return Status::success();
}

std::size_t RandomAccessFile::read(
    std::uint64_t offset,
    void* buffer,
    std::size_t size)
{
    return file_.read_at(offset, buffer, size);
}

Status RandomAccessFile::revalidate() const
{
    const auto status = file_.revalidate();
    return status.ok() ? Status::success() : Status::failure("archive_source_changed", status.detail);
}

Status SequentialOutputFile::create(
    const std::filesystem::path& path,
    std::uint64_t maximum_size)
{
    const auto status = file_.create_exclusive(path, maximum_size);
    return status.ok() ? Status::success() : Status::failure("archive_staging_output_create_failed", status.detail);
}

std::size_t SequentialOutputFile::write(
    std::uint64_t offset,
    const void* buffer,
    std::size_t size)
{
    return file_.write_at(offset, buffer, size);
}

bool SequentialOutputFile::flush_and_close(std::string& detail)
{
    const auto status = file_.flush_file_and_parent();
    detail = status.detail;
    return status.ok();
}

Status create_owned_staging_root(const std::filesystem::path& staging_root)
{
    std::error_code error;
    if (staging_root.empty() || std::filesystem::exists(staging_root, error)) {
        return Status::failure("archive_staging_root_exists", staging_root.u8string());
    }
    const std::filesystem::path parent = staging_root.parent_path();
    if (parent.empty() || !std::filesystem::is_directory(parent, error) || error) {
        return Status::failure("archive_staging_parent_invalid", parent.u8string());
    }
    std::string link_detail;
    if (facman::base::path_crosses_link_or_reparse_point(parent, link_detail)) {
        return Status::failure("archive_staging_parent_link_refused", link_detail);
    }
    if (!std::filesystem::create_directory(staging_root, error) || error) {
        return Status::failure("archive_staging_create_failed", error.message());
    }
    std::string write_detail;
    if (!facman::base::write_text_new_atomic(
            staging_root / owned_staging_marker_name(),
            "schema=facman.archive_staging.v1\n",
            write_detail)) {
        std::filesystem::remove(staging_root, error);
        return Status::failure("archive_staging_marker_failed", write_detail);
    }
    return Status::success();
}

Status cleanup_owned_staging_root(const std::filesystem::path& staging_root)
{
    std::string detail;
    if (!facman::base::remove_owned_staging_tree(
            staging_root,
            owned_staging_marker_name(),
            detail)) {
        return Status::failure("archive_staging_cleanup_failed", detail);
    }
    return Status::success();
}

Status commit_owned_staged_file_no_clobber(
    const std::filesystem::path& staging_root,
    const std::filesystem::path& staged_file,
    const std::filesystem::path& destination)
{
    std::error_code error;
    if (!std::filesystem::is_regular_file(staging_root / owned_staging_marker_name(), error) ||
        !std::filesystem::is_regular_file(staged_file, error) ||
        staged_file.parent_path().lexically_normal() != staging_root.lexically_normal()) {
        return Status::failure("archive_staged_file_not_owned", staged_file.u8string());
    }
    if (std::filesystem::exists(destination, error)) {
        return Status::failure("archive_commit_target_exists", destination.u8string());
    }
    std::string link_detail;
    if (facman::base::path_crosses_link_or_reparse_point(destination.parent_path(), link_detail)) {
        return Status::failure("archive_commit_parent_link_refused", link_detail);
    }
    const auto committed = facman::platform::commit_no_replace(staged_file, destination);
    return committed.ok() ? Status::success() : Status::failure("archive_commit_no_clobber_failed", committed.detail);
}

} // namespace facman::archive
