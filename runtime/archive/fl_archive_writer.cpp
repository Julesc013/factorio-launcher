// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_archive.h"

#include "fl_archive_platform.h"
#include "fl_archive_policy.h"
#include "miniz.h"

#include <algorithm>
#include <chrono>
#include <cstring>
#include <filesystem>
#include <limits>
#include <map>

namespace facman::archive {
namespace {

std::size_t miniz_write(void* opaque, mz_uint64 offset, const void* buffer, std::size_t size)
{
    return static_cast<SequentialOutputFile*>(opaque)->write(offset, buffer, size);
}

std::size_t miniz_read(void* opaque, mz_uint64 offset, void* buffer, std::size_t size)
{
    return static_cast<RandomAccessFile*>(opaque)->read(offset, buffer, size);
}

Status validate_write_entries(
    std::vector<WriteEntry>& entries,
    const WriteOptions& options,
    std::map<std::string, std::uint64_t>& expected_sizes,
    std::map<std::string, std::shared_ptr<RandomAccessFile>>& sources)
{
    if (entries.size() > options.limits.maximum_entry_count) {
        return Status::failure("archive_entry_count_limit", std::to_string(entries.size()));
    }
    for (WriteEntry& entry : entries) {
        if (entry.directory && (entry.archive_path.empty() || entry.archive_path.back() != '/')) {
            entry.archive_path += '/';
        }
    }
    std::sort(entries.begin(), entries.end(), [](const WriteEntry& left, const WriteEntry& right) {
        return left.archive_path < right.archive_path;
    });
    CollisionTracker collisions;
    std::uint64_t total_expanded = 0;
    for (const WriteEntry& entry : entries) {
        PathKeys keys;
        Status status = validate_archive_path(
            entry.archive_path,
            entry.directory,
            options.limits,
            keys);
        if (!status.ok()) return status;
        status = collisions.add(keys, entry.directory);
        if (!status.ok()) return status;
        if (entry.directory) continue;

        auto source = std::make_shared<RandomAccessFile>();
        status = source->open(entry.source_path);
        if (!status.ok()) return status;
        status = enforce_entry_limits(
            source->size(),
            source->size(),
            total_expanded,
            options.limits);
        if (!status.ok()) return status;
        expected_sizes[entry.archive_path] = source->size();
        sources[entry.archive_path] = std::move(source);
    }
    return Status::success();
}

Status abort_writer(
    mz_zip_archive& zip,
    SequentialOutputFile& output,
    const std::filesystem::path& staging_root,
    Status failure)
{
    if (zip.m_zip_mode != MZ_ZIP_MODE_INVALID) {
        mz_zip_writer_end(&zip);
    }
    std::string ignored;
    output.flush_and_close(ignored);
    const Status cleanup = cleanup_owned_staging_root(staging_root);
    if (!cleanup.ok()) {
        failure.detail += "; cleanup: " + cleanup.detail;
    }
    return failure;
}

} // namespace

Status write_to_new_owned_staging(
    const std::filesystem::path& staging_root,
    const std::string& archive_filename,
    std::vector<WriteEntry> entries,
    const WriteOptions& options,
    WriteResult& result)
{
    result = {};
    if (archive_filename.empty() || archive_filename.find('/') != std::string::npos ||
        archive_filename.find('\\') != std::string::npos ||
        std::filesystem::path(archive_filename).extension() != ".zip") {
        return Status::failure("archive_staging_filename_invalid", archive_filename);
    }
    PathKeys output_keys;
    Status status = validate_archive_path(archive_filename, false, options.limits, output_keys);
    if (!status.ok()) return status;
    std::map<std::string, std::uint64_t> expected_sizes;
    std::map<std::string, std::shared_ptr<RandomAccessFile>> sources;
    status = validate_write_entries(entries, options, expected_sizes, sources);
    if (!status.ok()) return status;
    if (options.checkpoint && !options.checkpoint("after_sources_opened")) {
        return Status::failure("archive_writer_checkpoint_refused", "after_sources_opened");
    }
    status = create_owned_staging_root(staging_root);
    if (!status.ok()) return status;

    const std::filesystem::path output_path = staging_root / archive_filename;
    SequentialOutputFile output;
    status = output.create(output_path, options.limits.maximum_archive_bytes);
    if (!status.ok()) {
        const Status cleanup = cleanup_owned_staging_root(staging_root);
        if (!cleanup.ok()) status.detail += "; cleanup: " + cleanup.detail;
        return status;
    }

    mz_zip_archive zip {};
    zip.m_pWrite = miniz_write;
    zip.m_pIO_opaque = &output;
    const mz_uint flags = options.force_zip64 ? MZ_ZIP_FLAG_WRITE_ZIP64 : 0;
    if (!mz_zip_writer_init_v2(&zip, 0, flags)) {
        return abort_writer(
            zip,
            output,
            staging_root,
            Status::failure("archive_writer_init_failed", mz_zip_get_error_string(zip.m_last_error)));
    }

    const MZ_TIME_T reproducible_time = static_cast<MZ_TIME_T>(315532800);
    for (const WriteEntry& entry : entries) {
        const MZ_TIME_T* timestamp = options.reproducible ? &reproducible_time : nullptr;
        if (entry.directory) {
            if (!mz_zip_writer_add_mem_ex_v2(
                    &zip,
                    entry.archive_path.c_str(),
                    nullptr,
                    0,
                    nullptr,
                    0,
                    MZ_NO_COMPRESSION,
                    0,
                    0,
                    const_cast<MZ_TIME_T*>(timestamp),
                    nullptr,
                    0,
                    nullptr,
                    0)) {
                return abort_writer(
                    zip,
                    output,
                    staging_root,
                    Status::failure("archive_writer_add_directory_failed", entry.archive_path));
            }
            continue;
        }

        RandomAccessFile& source = *sources.at(entry.archive_path);
        status = source.revalidate();
        if (!status.ok() || source.size() != expected_sizes[entry.archive_path]) {
            return abort_writer(
                zip,
                output,
                staging_root,
                Status::failure("archive_writer_source_changed", entry.archive_path));
        }
        const mz_uint level = options.method == CompressionMethod::stored ?
            MZ_NO_COMPRESSION : MZ_DEFAULT_LEVEL;
        if (!mz_zip_writer_add_read_buf_callback(
                &zip,
                entry.archive_path.c_str(),
                miniz_read,
                &source,
                source.size(),
                timestamp,
                nullptr,
                0,
                level,
                nullptr,
                0,
                nullptr,
                0)) {
            return abort_writer(
                zip,
                output,
                staging_root,
                Status::failure("archive_writer_add_file_failed", entry.archive_path));
        }
        status = source.revalidate();
        if (!status.ok()) {
            return abort_writer(zip, output, staging_root, status);
        }
    }
    if (!mz_zip_writer_finalize_archive(&zip)) {
        return abort_writer(
            zip,
            output,
            staging_root,
            Status::failure("archive_writer_finalize_failed", mz_zip_get_error_string(zip.m_last_error)));
    }
    if (!mz_zip_writer_end(&zip)) {
        return abort_writer(
            zip,
            output,
            staging_root,
            Status::failure("archive_writer_close_failed", "Miniz writer cleanup failed"));
    }
    std::string flush_detail;
    if (!output.flush_and_close(flush_detail)) {
        const Status cleanup = cleanup_owned_staging_root(staging_root);
        if (!cleanup.ok()) flush_detail += "; cleanup: " + cleanup.detail;
        return Status::failure("archive_writer_flush_failed", flush_detail);
    }

    Plan verified;
    status = inspect_archive(output_path, options.limits, verified);
    if (!status.ok()) {
        const Status cleanup = cleanup_owned_staging_root(staging_root);
        if (!cleanup.ok()) status.detail += "; cleanup: " + cleanup.detail;
        return status;
    }
    status = verify_all(verified, options.limits);
    if (!status.ok()) {
        const Status cleanup = cleanup_owned_staging_root(staging_root);
        if (!cleanup.ok()) status.detail += "; cleanup: " + cleanup.detail;
        return status;
    }
    result.staging_root = staging_root;
    result.archive_path = output_path;
    result.verified_plan = std::move(verified);
    return Status::success();
}

} // namespace facman::archive
