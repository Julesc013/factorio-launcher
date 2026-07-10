from __future__ import annotations

import os
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def facman_executable() -> Path:
    explicit = os.environ.get("FACMAN_CLI_EXE")
    if explicit:
        path = Path(explicit)
        if path.is_file():
            return path
        raise AssertionError(f"FACMAN_CLI_EXE does not point to a file: {path}")

    preferred = [
        ROOT / "build" / "Debug" / "facman.exe",
        ROOT / "build" / "native-smoke" / "Debug" / "facman.exe",
        ROOT / "build" / "native-smoke" / "facman",
    ]
    candidates: list[Path] = []
    for path in preferred:
        if path.is_file():
            candidates.append(path)
    for pattern in ("build/**/facman.exe", "build/**/facman"):
        candidates.extend(path for path in ROOT.glob(pattern) if path.is_file() and path not in candidates)
    if candidates:
        return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)[0]

    raise unittest.SkipTest("native facman executable has not been built")


def invoke(args: list[str]) -> tuple[int, str, str]:
    completed = subprocess.run(
        [str(facman_executable()), *args],
        cwd=ROOT,
        check=False,
        encoding="utf-8",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.returncode, completed.stdout, completed.stderr
