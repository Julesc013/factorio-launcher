# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import ctypes
import os
import subprocess
import sys
from pathlib import Path

REQUIRED_EXPORTS = (
    "flb_abi_version_v1",
    "flb_abi_is_compatible_v1",
    "flb_command_execute_v1",
    "flb_context_create_v1",
    "flb_context_destroy_v1",
    "flb_required_ulk_abi_v1",
)


def validate_symbol_table(path: Path) -> list[str]:
    completed = subprocess.run(
        ["nm", "-D", "--defined-only", str(path)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        return [f"could not inspect shared library symbols: {completed.stderr.strip()}"]
    present = {line.split()[-1] for line in completed.stdout.splitlines() if line.split()}
    return [f"missing public ABI export: {name}" for name in REQUIRED_EXPORTS if name not in present]


def validate(path: Path, symbols_only: bool = False) -> list[str]:
    if not path.is_file():
        return [f"shared library does not exist: {path}"]
    if symbols_only:
        return validate_symbol_table(path)
    cookie = None
    if os.name == "nt":
        cookie = os.add_dll_directory(str(path.parent))
    try:
        library = ctypes.CDLL(str(path))
        missing = [name for name in REQUIRED_EXPORTS if not hasattr(library, name)]
        if missing:
            return [f"missing public ABI export: {name}" for name in missing]
        version = library.flb_abi_version_v1
        version.argtypes = []
        version.restype = ctypes.c_uint32
        if version() != 0x00010002:
            return ["flb_abi_version_v1 did not return ABI version 1.2"]
        required_ulk = library.flb_required_ulk_abi_v1
        required_ulk.argtypes = []
        required_ulk.restype = ctypes.c_uint32
        if required_ulk() != 0x00010001:
            return ["flb_required_ulk_abi_v1 did not return ULK ABI version 1.1"]
        compatible = library.flb_abi_is_compatible_v1
        compatible.argtypes = [ctypes.c_uint32]
        compatible.restype = ctypes.c_int
        if not compatible(0x00010001) or not compatible(0x00010002):
            return ["flb_abi_is_compatible_v1 rejected a compatible 1.x client"]
        if compatible(0x00010003) or compatible(0x00020000):
            return ["flb_abi_is_compatible_v1 accepted a newer minor or different major"]
        return []
    except OSError as error:
        return [f"could not load shared library: {error}"]
    finally:
        if cookie is not None:
            cookie.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the FacMan binding ABI symbol floor.")
    parser.add_argument("--library", required=True, type=Path)
    parser.add_argument("--symbols-only", action="store_true")
    args = parser.parse_args()
    problems = validate(args.library.resolve(), symbols_only=args.symbols_only)
    if problems:
        for problem in problems:
            print(f"abi-symbol-check: {problem}", file=sys.stderr)
        return 1
    print(f"abi-symbol-check: ok ({len(REQUIRED_EXPORTS)} exports)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
