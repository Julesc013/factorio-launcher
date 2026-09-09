// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#include "fl_resource_export_inspection.h"
#include <cerrno>
#include <chrono>
#include <cstring>
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
namespace facman::resources::detail {
namespace {
struct Directory {
    int fd = -1;
    ~Directory() { if (fd >= 0) ::close(fd); }
};
DestinationObservation error(int code)
{
    DestinationObservation result;
    result.state = code == ENOENT ? "absent" : (code == ELOOP || code == ENOTDIR) ? "unsafe" : "unavailable";
    result.kind = code == ENOENT ? "absent" : "unknown";
    result.detail = std::strerror(code);
    return result;
}
}
DestinationObservation observe_export_path(const std::filesystem::path& root,
    const std::vector<std::filesystem::path>& components)
{
    Directory parent;
    parent.fd = ::open(root.c_str(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (parent.fd < 0) return error(errno);
    const auto start = std::chrono::steady_clock::now();
    for (std::size_t i = 0; i < components.size(); ++i) {
        if (std::chrono::steady_clock::now() - start >= std::chrono::seconds(2))
            return {"unavailable", "unknown", 0, 0, "Observation time budget exhausted"};
        struct stat observed {};
        // A single name under the held parent: no intermediate pathname reopen.
        if (::fstatat(parent.fd, components[i].c_str(), &observed, AT_SYMLINK_NOFOLLOW) != 0)
            return error(errno);
        const bool directory = S_ISDIR(observed.st_mode);
        const bool file = S_ISREG(observed.st_mode);
        if (!directory && !file)
            return {"unsafe", S_ISLNK(observed.st_mode) ? "link" : "other", 0, 0,
                "Links and special objects are not traversed"};
        if (i + 1 == components.size())
            return {"present", directory ? "directory" : "regular_file",
                static_cast<std::uint64_t>(observed.st_dev), static_cast<std::uint64_t>(observed.st_ino),
                "Sequential destination observation; contents and ownership not inspected"};
        if (!directory) return {"unsafe", "regular_file", 0, 0, "Ancestor is not a directory"};
        Directory next;
        next.fd = ::openat(parent.fd, components[i].c_str(),
            O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        if (next.fd < 0) return error(errno);
        struct stat opened {};
        if (::fstat(next.fd, &opened) != 0) return error(errno);
        if (!S_ISDIR(opened.st_mode) || opened.st_dev != observed.st_dev || opened.st_ino != observed.st_ino)
            return {"unavailable", "unknown", 0, 0, "Ancestor changed during observation"};
        ::close(parent.fd);
        parent.fd = next.fd;
        next.fd = -1;
    }
    return {"unavailable", "unknown", 0, 0, "No destination component"};
}
}
