// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FACMAN_RUNTIME_ARCHIVE_FL_ARCHIVE_PLATFORM_H
#define FACMAN_RUNTIME_ARCHIVE_FL_ARCHIVE_PLATFORM_H

#include "fl_archive.h"
#include "fl_file_io.h"

#include <cstdint>
#include <filesystem>
#include <string>

namespace facman::archive {

class RandomAccessFile {
public:
    Status open(const std::filesystem::path& path);
    std::size_t read(std::uint64_t offset, void* buffer, std::size_t size);
    std::uint64_t size() const { return file_.size(); }
    Status revalidate() const;
    const facman::platform::FileIdentity& identity() const { return file_.identity(); }

private:
    facman::platform::StableInputFile file_;
};

class SequentialOutputFile {
public:
    Status create(const std::filesystem::path& path, std::uint64_t maximum_size);
    std::size_t write(std::uint64_t offset, const void* buffer, std::size_t size);
    bool flush_and_close(std::string& detail);

private:
    facman::platform::DurableOutputFile file_;
};

Status create_owned_staging_root(const std::filesystem::path& staging_root);
Status cleanup_owned_staging_root(const std::filesystem::path& staging_root);

Status commit_owned_staged_file_no_clobber(
    const std::filesystem::path& staging_root,
    const std::filesystem::path& staged_file,
    const std::filesystem::path& destination);

} // namespace facman::archive

#endif
