# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import os
import subprocess
import unittest
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@lru_cache(maxsize=16)
def _discover_facman_executable(root: Path, explicit: str) -> Path:
    if explicit:
        path = Path(explicit)
        if path.is_file():
            return path
        raise AssertionError(f"FACMAN_CLI_EXE does not point to a file: {path}")

    preferred = [
        root / "build" / "native-smoke" / "Debug" / "facman.exe",
        root / "build" / "native-smoke" / "facman",
        root / "build" / "Debug" / "facman.exe",
    ]
    candidates: list[Path] = []
    for pattern in ("build/**/facman.exe", "build/**/facman"):
        candidates.extend(path for path in root.glob(pattern) if path.is_file())
    if candidates:
        ranks = {path: index for index, path in enumerate(preferred)}
        unique = set(candidates)
        return max(
            unique,
            key=lambda path: (path.stat().st_mtime_ns, -ranks.get(path, len(preferred))),
        )

    raise unittest.SkipTest("native facman executable has not been built")


def facman_executable() -> Path:
    # Raw unittest discovery does not rebuild the native CLI. Cache the bounded
    # selection for the process so each CLI-backed case does not recursively
    # rescan a potentially large historical build tree.
    return _discover_facman_executable(ROOT, os.environ.get("FACMAN_CLI_EXE", ""))


def invoke(args: list[str], env: dict[str, str] | None = None) -> tuple[int, str, str]:
    completed = subprocess.run(
        [str(facman_executable()), *args],
        cwd=ROOT,
        check=False,
        encoding="utf-8",
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.returncode, completed.stdout, completed.stderr
