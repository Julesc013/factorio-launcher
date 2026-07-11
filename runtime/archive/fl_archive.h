#ifndef FACMAN_RUNTIME_ARCHIVE_FL_ARCHIVE_H
#define FACMAN_RUNTIME_ARCHIVE_FL_ARCHIVE_H

#include <cstdint>
#include <filesystem>
#include <functional>
#include <string>
#include <vector>

namespace facman::archive {

enum class CompressionMethod {
    stored,
    deflate,
};

struct Limits {
    std::uint64_t maximum_archive_bytes = 4ULL * 1024ULL * 1024ULL * 1024ULL;
    std::uint64_t maximum_entry_count = 10000;
    std::uint64_t maximum_entry_compressed_bytes = 1024ULL * 1024ULL * 1024ULL;
    std::uint64_t maximum_entry_expanded_bytes = 4ULL * 1024ULL * 1024ULL * 1024ULL;
    std::uint64_t maximum_total_expanded_bytes = 8ULL * 1024ULL * 1024ULL * 1024ULL;
    std::uint64_t maximum_compression_ratio = 1000;
    std::size_t maximum_path_bytes = 1024;
    std::size_t maximum_directory_depth = 64;
    std::uint64_t maximum_read_milliseconds = 30000;
};

struct Status {
    std::string code;
    std::string detail;

    bool ok() const { return code.empty(); }
    static Status success() { return {}; }
    static Status failure(std::string code, std::string detail);
};

struct Entry {
    std::uint32_t index = 0;
    std::string path;
    bool directory = false;
    CompressionMethod method = CompressionMethod::stored;
    std::uint32_t crc32 = 0;
    std::uint64_t compressed_size = 0;
    std::uint64_t expanded_size = 0;
    std::uint64_t local_header_offset = 0;
    std::uint64_t data_offset = 0;
    std::uint64_t occupied_end = 0;
    std::uint32_t external_attributes = 0;
};

struct Plan {
    std::filesystem::path archive_path;
    std::uint64_t archive_size = 0;
    std::uint64_t central_directory_offset = 0;
    std::uint64_t central_directory_size = 0;
    std::uint64_t total_expanded_size = 0;
    bool zip64 = false;
    std::vector<Entry> entries;
};

using DataSink = std::function<bool(const unsigned char*, std::size_t)>;
using ExtractionCheckpoint = std::function<bool(std::uint32_t, const char*)>;

Status inspect_archive(
    const std::filesystem::path& archive_path,
    const Limits& limits,
    Plan& plan);

Status stream_entry(
    const Plan& plan,
    std::uint32_t entry_index,
    const Limits& limits,
    const DataSink& sink);

Status extract_to_new_owned_staging(
    const Plan& plan,
    const std::filesystem::path& staging_root,
    const Limits& limits,
    const ExtractionCheckpoint& checkpoint = {});

struct WriteEntry {
    std::string archive_path;
    std::filesystem::path source_path;
    bool directory = false;
};

struct WriteOptions {
    CompressionMethod method = CompressionMethod::deflate;
    bool reproducible = true;
    bool force_zip64 = false;
    Limits limits;
};

struct WriteResult {
    std::filesystem::path staging_root;
    std::filesystem::path archive_path;
    Plan verified_plan;
};

Status write_to_new_owned_staging(
    const std::filesystem::path& staging_root,
    const std::string& archive_filename,
    std::vector<WriteEntry> entries,
    const WriteOptions& options,
    WriteResult& result);

const char* owned_staging_marker_name();

} // namespace facman::archive

#endif
