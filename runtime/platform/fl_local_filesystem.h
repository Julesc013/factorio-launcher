// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT
#ifndef FACMAN_PLATFORM_LOCAL_FILESYSTEM_H
#define FACMAN_PLATFORM_LOCAL_FILESYSTEM_H

#ifndef _WIN32
#if defined(__APPLE__)
#include <sys/mount.h>
#else
#include <sys/vfs.h>
#endif

namespace facman::platform::detail {
// Shared policy for the local operation lock and held-FD rewrite admission.
// Classification is admission evidence, not a durability qualification.
inline bool supported_posix_local_filesystem(const struct statfs& value)
{
#if defined(__APPLE__)
    return (value.f_flags & MNT_LOCAL) != 0;
#else
    switch (static_cast<unsigned long>(value.f_type)) {
    case 0xEF53UL:      // ext2/3/4
    case 0x58465342UL:  // XFS
    case 0x9123683EUL:  // Btrfs
    case 0x01021994UL:  // tmpfs
    case 0x858458F6UL:  // ramfs
    case 0x794C7630UL:  // overlayfs
    case 0x2FC12FC1UL:  // ZFS
    case 0xF2F52010UL:  // F2FS
    case 0xCA451A4EUL:  // bcachefs
        return true;
    default:
        return false;
    }
#endif
}
} // namespace facman::platform::detail
#endif
#endif
