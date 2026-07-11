#ifndef FACMAN_PLATFORM_FILE_IO_H
#define FACMAN_PLATFORM_FILE_IO_H

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <memory>
#include <string>

namespace facman::platform {

struct IoStatus {
    std::string code;
    std::string detail;
    bool ok() const noexcept { return code.empty(); }
    static IoStatus success() { return {}; }
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

class StableInputFile {
public:
    StableInputFile();
    StableInputFile(StableInputFile&&) noexcept;
    StableInputFile& operator=(StableInputFile&&) noexcept;
    ~StableInputFile();
    StableInputFile(const StableInputFile&) = delete;
    StableInputFile& operator=(const StableInputFile&) = delete;

    IoStatus open_no_follow(const std::filesystem::path& path);
    std::size_t read_at(std::uint64_t offset, void* buffer, std::size_t size) const;
    IoStatus revalidate() const;
    const FileIdentity& identity() const noexcept;
    std::uint64_t size() const noexcept;
    bool open() const noexcept;

private:
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
    void close_without_flush() noexcept;
    const std::filesystem::path& path() const noexcept;

private:
    struct Impl;
    std::unique_ptr<Impl> impl_;
};

IoStatus commit_no_replace(
    const std::filesystem::path& source,
    const std::filesystem::path& destination);
IoStatus remove_exact_object(
    const std::filesystem::path& path,
    const FileIdentity& expected);
std::filesystem::path path_from_utf8(const std::string& value);
std::string path_to_utf8(const std::filesystem::path& value);

} // namespace facman::platform

#endif
