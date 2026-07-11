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
    std::error_code error;
    const auto status = std::filesystem::symlink_status(path, error);
    if (error || !std::filesystem::is_regular_file(status)) {
        return Status::failure("archive_source_not_regular", path.u8string());
    }
    size_ = std::filesystem::file_size(path, error);
    if (error) {
        return Status::failure("archive_source_size_failed", error.message());
    }
    stream_.open(path, std::ios::binary);
    if (!stream_) {
        return Status::failure("archive_source_open_failed", path.u8string());
    }
    return Status::success();
}

std::size_t RandomAccessFile::read(
    std::uint64_t offset,
    void* buffer,
    std::size_t size)
{
    std::lock_guard<std::mutex> guard(mutex_);
    if (offset >= size_) {
        return 0;
    }
    size = static_cast<std::size_t>(std::min<std::uint64_t>(size, size_ - offset));
    stream_.clear();
    stream_.seekg(static_cast<std::streamoff>(offset), std::ios::beg);
    if (!stream_) {
        return 0;
    }
    stream_.read(static_cast<char*>(buffer), static_cast<std::streamsize>(size));
    return static_cast<std::size_t>(stream_.gcount());
}

Status SequentialOutputFile::create(
    const std::filesystem::path& path,
    std::uint64_t maximum_size)
{
    std::error_code error;
    if (std::filesystem::exists(path, error)) {
        return Status::failure("archive_staging_output_exists", path.u8string());
    }
    stream_.open(path, std::ios::binary | std::ios::out);
    if (!stream_) {
        return Status::failure("archive_staging_output_create_failed", path.u8string());
    }
    next_offset_ = 0;
    maximum_size_ = maximum_size;
    return Status::success();
}

std::size_t SequentialOutputFile::write(
    std::uint64_t offset,
    const void* buffer,
    std::size_t size)
{
    if (offset != next_offset_ || next_offset_ > maximum_size_ ||
        size > maximum_size_ - next_offset_) {
        return 0;
    }
    stream_.write(static_cast<const char*>(buffer), static_cast<std::streamsize>(size));
    if (!stream_) {
        return 0;
    }
    next_offset_ += size;
    return size;
}

bool SequentialOutputFile::flush_and_close(std::string& detail)
{
    stream_.flush();
    if (!stream_) {
        detail = "archive staging output flush failed";
        stream_.close();
        return false;
    }
    stream_.close();
    if (stream_.fail()) {
        detail = "archive staging output close failed";
        return false;
    }
    detail.clear();
    return true;
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
#ifdef _WIN32
    if (!MoveFileW(staged_file.c_str(), destination.c_str())) {
        return Status::failure(
            "archive_commit_no_clobber_failed",
            "MoveFileW failed with error " + std::to_string(GetLastError()));
    }
#else
    if (::link(staged_file.c_str(), destination.c_str()) != 0) {
        return Status::failure("archive_commit_no_clobber_failed", std::strerror(errno));
    }
    if (::unlink(staged_file.c_str()) != 0) {
        const int unlink_error = errno;
        if (::unlink(destination.c_str()) == 0) {
            return Status::failure(
                "archive_commit_staging_unlink_failed",
                std::string(std::strerror(unlink_error)) + "; destination rollback succeeded");
        }
        return Status::failure(
            "archive_commit_state_uncertain",
            std::string("staging unlink failed: ") + std::strerror(unlink_error) +
                "; destination rollback failed: " + std::strerror(errno));
    }
#endif
    return Status::success();
}

} // namespace facman::archive
