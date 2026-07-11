from __future__ import annotations

import argparse
import ctypes
import os
import sys
from pathlib import Path

REQUIRED_EXPORTS = (
    "flb_abi_version_v1",
    "flb_command_execute_v1",
    "flb_context_create_v1",
    "flb_context_destroy_v1",
)


def validate(path: Path) -> list[str]:
    if not path.is_file():
        return [f"shared library does not exist: {path}"]
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
        if version() != 0x00010001:
            return ["flb_abi_version_v1 did not return ABI version 1.1"]
        return []
    except OSError as error:
        return [f"could not load shared library: {error}"]
    finally:
        if cookie is not None:
            cookie.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the FacMan binding ABI symbol floor.")
    parser.add_argument("--library", required=True, type=Path)
    args = parser.parse_args()
    problems = validate(args.library.resolve())
    if problems:
        for problem in problems:
            print(f"abi-symbol-check: {problem}", file=sys.stderr)
        return 1
    print(f"abi-symbol-check: ok ({len(REQUIRED_EXPORTS)} exports)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
