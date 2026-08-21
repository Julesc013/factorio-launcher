# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Run Windows build commands through one collision-safe logical root.

MSVC derives anonymous-namespace symbols from the resolved compiler input path
before ``/pathmap`` and ``/d1trimfile`` are applied. A clean checkout in a
different physical root can therefore produce different native binaries. This
tool gives sequential clean builds the same short-lived logical root without
moving or modifying their physical checkout.

The mapping is process-global Windows state, so it is guarded by a named mutex,
must use an otherwise unused drive, and is removed in ``finally``. It grants no
release, signing, provider, or execution authority.
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path, PureWindowsPath
from typing import Iterator, Sequence


TOKEN = "@FACMAN_STABLE_ROOT@"
FILE_ATTRIBUTE_REPARSE_POINT = 0x400
WAIT_OBJECT_0 = 0
WAIT_ABANDONED = 0x80


class StableBuildRootError(RuntimeError):
    """The requested logical build root could not be established safely."""


def normalize_drive(value: str) -> str:
    candidate = value.strip().upper().rstrip(":")
    if re.fullmatch(r"[D-Z]", candidate) is None:
        raise ValueError("stable build drive must be one letter from D through Z")
    return candidate


def require_physical_root(value: Path) -> Path:
    root = Path(os.path.abspath(value))
    if not root.is_dir():
        raise ValueError(f"physical build root is not a directory: {root}")
    attributes = getattr(root.lstat(), "st_file_attributes", 0)
    if attributes & FILE_ATTRIBUTE_REPARSE_POINT:
        raise ValueError(f"physical build root must not be a reparse point: {root}")
    return root


def require_relative_working_directory(root: Path, value: str) -> Path:
    if not value.strip():
        raise ValueError("working directory must not be empty")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("working directory must be a non-traversing relative path")
    physical = root.joinpath(*relative.parts) if relative.parts else root
    if not physical.is_dir():
        raise ValueError(f"working directory is not inside the physical root: {value}")
    return relative if relative.parts else Path(".")


def logical_drive_present(drive: str) -> bool:
    if os.name != "nt":
        raise StableBuildRootError("stable logical build roots require Windows")
    mask = ctypes.WinDLL("kernel32", use_last_error=True).GetLogicalDrives()
    if mask == 0:
        raise StableBuildRootError(
            f"GetLogicalDrives failed with Windows error {ctypes.get_last_error()}"
        )
    return bool(mask & (1 << (ord(drive) - ord("A"))))


@contextlib.contextmanager
def exclusive_drive(drive: str) -> Iterator[None]:
    if os.name != "nt":
        raise StableBuildRootError("stable logical build roots require Windows")
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = (ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.WaitForSingleObject.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
    kernel32.WaitForSingleObject.restype = ctypes.c_uint32
    kernel32.ReleaseMutex.argtypes = (ctypes.c_void_p,)
    kernel32.ReleaseMutex.restype = ctypes.c_int
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel32.CloseHandle.restype = ctypes.c_int

    handle = kernel32.CreateMutexW(None, False, f"Local\\FacManStableBuildRoot_{drive}")
    if not handle:
        raise StableBuildRootError(
            f"cannot create stable-build mutex: Windows error {ctypes.get_last_error()}"
        )
    acquired = False
    try:
        wait = kernel32.WaitForSingleObject(handle, 0)
        if wait not in (WAIT_OBJECT_0, WAIT_ABANDONED):
            raise StableBuildRootError(
                f"stable build drive {drive}: is already leased by another process"
            )
        acquired = True
        yield
    finally:
        if acquired:
            kernel32.ReleaseMutex(handle)
        kernel32.CloseHandle(handle)


def run_subst(drive: str, target: Path | None) -> None:
    command = ["subst.exe", f"{drive}:"]
    if target is None:
        command.append("/D")
    else:
        command.append(str(target))
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode:
        detail = (completed.stderr or completed.stdout).strip()
        raise StableBuildRootError(
            f"subst failed for {drive}: ({completed.returncode})"
            + (f": {detail}" if detail else "")
        )


@contextlib.contextmanager
def stable_build_root(physical_root: Path, drive: str) -> Iterator[str]:
    """Temporarily map *physical_root* and yield a ``Q:\\``-style root."""

    root = require_physical_root(physical_root)
    drive = normalize_drive(drive)
    logical_root = f"{drive}:\\"
    with exclusive_drive(drive):
        if logical_drive_present(drive):
            raise StableBuildRootError(
                f"stable build drive {drive}: is already present; refusing substitution"
            )
        mapped = False
        try:
            run_subst(drive, root)
            mapped = True
            if not logical_drive_present(drive):
                raise StableBuildRootError(f"stable build drive {drive}: did not appear")
            if not os.path.samefile(logical_root, root):
                raise StableBuildRootError(
                    f"stable build drive {drive}: does not resolve to the requested root"
                )
            yield logical_root
        finally:
            if mapped:
                run_subst(drive, None)
                if logical_drive_present(drive):
                    raise StableBuildRootError(
                        f"stable build drive {drive}: remained present after cleanup"
                    )


def logical_working_directory(logical_root: str, relative: Path) -> str:
    return str(PureWindowsPath(logical_root).joinpath(*relative.parts))


def rewrite_command(command: Sequence[str], logical_root: str) -> list[str]:
    replacement = logical_root.rstrip("\\")
    return [value.replace(TOKEN, replacement) for value in command]


def atomic_report(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    os.replace(temporary, path)


def execute(
    physical_root: Path,
    drive: str,
    working_directory: str,
    command: Sequence[str],
    *,
    report_path: Path | None = None,
) -> int:
    root = require_physical_root(physical_root)
    relative = require_relative_working_directory(root, working_directory)
    if not command:
        raise ValueError("a command is required after --")
    started = time.monotonic()
    with stable_build_root(root, drive) as logical_root:
        rewritten = rewrite_command(command, logical_root)
        completed = subprocess.run(
            rewritten,
            cwd=logical_working_directory(logical_root, relative),
            check=False,
        )
    if report_path is not None:
        atomic_report(
            report_path.resolve(),
            {
                "schema": "facman.windows_stable_build_root.v1",
                "status": "pass" if completed.returncode == 0 else "fail",
                "physical_root": str(root),
                "logical_drive": normalize_drive(drive),
                "working_directory": relative.as_posix(),
                "command": rewritten,
                "exit_code": completed.returncode,
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "mapping_removed": True,
                "authority": "build_path_normalization_only",
            },
        )
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--physical-root", required=True, type=Path)
    parser.add_argument("--drive", default="Q")
    parser.add_argument("--working-directory", default=".")
    parser.add_argument("--report", type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    command = list(args.command)
    if command and command[0] == "--":
        command.pop(0)
    try:
        return execute(
            args.physical_root,
            args.drive,
            args.working_directory,
            command,
            report_path=args.report,
        )
    except (OSError, StableBuildRootError, ValueError) as exc:
        print(f"windows-stable-build-root: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
