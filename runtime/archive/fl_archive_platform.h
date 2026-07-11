#ifndef FACMAN_RUNTIME_ARCHIVE_FL_ARCHIVE_PLATFORM_H
#define FACMAN_RUNTIME_ARCHIVE_FL_ARCHIVE_PLATFORM_H

#include "fl_archive.h"

#include <cstdint>
#include <filesystem>
#include <fstream>
#include <mutex>
#include <string>

namespace facman::archive {

class RandomAccessFile {
public:
    Status open(const std::filesystem::path& path);
    std::size_t read(std::uint64_t offset, void* buffer, std::size_t size);
    std::uint64_t size() const { return size_; }

private:
    std::ifstream stream_;
    std::uint64_t size_ = 0;
    std::mutex mutex_;
};

class SequentialOutputFile {
public:
    Status create(const std::filesystem::path& path, std::uint64_t maximum_size);
    std::size_t write(std::uint64_t offset, const void* buffer, std::size_t size);
    bool flush_and_close(std::string& detail);

private:
    std::ofstream stream_;
    std::uint64_t next_offset_ = 0;
    std::uint64_t maximum_size_ = 0;
};

Status create_owned_staging_root(const std::filesystem::path& staging_root);
Status cleanup_owned_staging_root(const std::filesystem::path& staging_root);

} // namespace facman::archive

#endif
