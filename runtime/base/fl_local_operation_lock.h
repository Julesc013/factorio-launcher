#ifndef FACMAN_RUNTIME_BASE_FL_LOCAL_OPERATION_LOCK_H
#define FACMAN_RUNTIME_BASE_FL_LOCAL_OPERATION_LOCK_H

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <string>

namespace facman::base {

enum class StableLockCode {
    acquired,
    exists,
    contended,
    unsafe,
    unsupported_filesystem,
    io_error,
};

struct StableLockResult {
    StableLockCode code = StableLockCode::io_error;
    std::string detail;

    bool acquired() const { return code == StableLockCode::acquired; }
};

class StableLocalLock {
public:
    StableLocalLock() = default;
    ~StableLocalLock();

    StableLocalLock(const StableLocalLock&) = delete;
    StableLocalLock& operator=(const StableLocalLock&) = delete;
    StableLocalLock(StableLocalLock&& other) noexcept;
    StableLocalLock& operator=(StableLocalLock&& other) noexcept;

    StableLockResult create(const std::filesystem::path& path);
    StableLockResult open_existing(
        const std::filesystem::path& path,
        std::size_t maximum_bytes,
        std::string& content);

    bool write_text(const std::string& content, std::string& detail);
    bool read_text(std::size_t maximum_bytes, std::string& content, std::string& detail) const;
    bool identity_matches_path(std::string& detail) const;
    bool remove_exact(std::string& detail);
    void close();

    bool open() const { return native_handle_ != invalid_handle(); }
    const std::filesystem::path& path() const { return path_; }
    std::string identity_text() const;

private:
    static std::intptr_t invalid_handle() { return static_cast<std::intptr_t>(-1); }
    bool capture_identity(std::string& detail);
    bool current_identity_matches(std::string& detail) const;

    std::filesystem::path path_;
    std::intptr_t native_handle_ = invalid_handle();
    std::uint64_t device_or_volume_ = 0;
    std::uint64_t file_or_inode_ = 0;
};

} // namespace facman::base

#endif
