# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Create a Windows directory junction without a shell or elevation helper."""

from __future__ import annotations

import ctypes
import os
import struct
from ctypes import wintypes
from pathlib import Path


_GENERIC_WRITE = 0x40000000
_OPEN_EXISTING = 3
_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
_FSCTL_SET_REPARSE_POINT = 0x000900A4
_IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003
_INVALID_HANDLE_VALUE = wintypes.HANDLE(-1).value


def create_junction(link: Path, target: Path) -> None:
    """Create ``link`` as a mount-point reparse record targeting ``target``."""

    if os.name != "nt":
        raise OSError("Windows directory junctions are unavailable on this host")
    target = target.resolve(strict=True)
    link = link.resolve(strict=False)
    if link.exists() or link.is_symlink():
        raise FileExistsError(link)

    substitute = ("\\??\\" + str(target)).encode("utf-16-le")
    display = str(target).encode("utf-16-le")
    path_buffer = substitute + b"\0\0" + display + b"\0\0"
    data_length = 8 + len(path_buffer)
    reparse = (
        struct.pack(
            "<LHHHHHH",
            _IO_REPARSE_TAG_MOUNT_POINT,
            data_length,
            0,
            0,
            len(substitute),
            len(substitute) + 2,
            len(display),
        )
        + path_buffer
    )

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = (
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    )
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.DeviceIoControl.argtypes = (
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    )
    kernel32.DeviceIoControl.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL

    link.mkdir()
    handle = kernel32.CreateFileW(
        str(link),
        _GENERIC_WRITE,
        0,
        None,
        _OPEN_EXISTING,
        _FILE_FLAG_OPEN_REPARSE_POINT | _FILE_FLAG_BACKUP_SEMANTICS,
        None,
    )
    if handle == _INVALID_HANDLE_VALUE:
        error = ctypes.get_last_error()
        link.rmdir()
        raise ctypes.WinError(error)
    payload = ctypes.create_string_buffer(reparse)
    returned = wintypes.DWORD()
    error = 0
    try:
        if not kernel32.DeviceIoControl(
            handle,
            _FSCTL_SET_REPARSE_POINT,
            payload,
            len(reparse),
            None,
            0,
            ctypes.byref(returned),
            None,
        ):
            error = ctypes.get_last_error()
    finally:
        kernel32.CloseHandle(handle)
    if error:
        link.rmdir()
        raise ctypes.WinError(error)
