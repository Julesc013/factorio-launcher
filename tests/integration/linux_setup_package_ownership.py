# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Exercise ownership refusal using the produced Linux Setup package."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        raise SystemExit("usage: linux_setup_package_ownership.py SETUP HOME")
    setup = Path(sys.argv[1]).resolve(strict=True)
    home = Path(sys.argv[2]).resolve(strict=True)
    subprocess.run(
        [sys.executable, "-m", "unittest", "-q", "tests.test_linux_self_setup_ownership"],
        check=True,
    )
    environment = os.environ.copy()
    environment["HOME"] = str(home)
    subprocess.run([str(setup), "repair", "--yes", "--quiet"],
                   env=environment, check=True)

    current = home / ".local/opt/facman/current"
    original = current.readlink()
    foreign = home / "foreign-generation"
    foreign.mkdir()
    sentinel = foreign / "sentinel"
    sentinel.write_bytes(b"preserve foreign bytes\n")
    current.unlink()
    current.symlink_to(foreign, target_is_directory=True)
    refused = subprocess.run(
        [str(setup), "uninstall", "--yes", "--quiet"],
        env=environment, capture_output=True, text=True, check=False,
    )
    if refused.returncode == 0:
        raise SystemExit("produced Setup removed a foreign current pointer")
    if not current.is_symlink() or current.readlink() != foreign:
        raise SystemExit("produced Setup changed a foreign current pointer")
    if sentinel.read_bytes() != b"preserve foreign bytes\n":
        raise SystemExit("produced Setup changed foreign generation bytes")
    current.unlink()
    current.symlink_to(original, target_is_directory=True)
    print("produced Linux Setup refused foreign ownership and preserved bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
