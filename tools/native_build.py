# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Construct native builds without relying on excluded MSBuild dependencies."""
from __future__ import annotations
import os
import shutil
from pathlib import Path


def require_disk_reserve(path: Path) -> None:
    minimum = float(os.environ.get("FACMAN_MIN_FREE_GIB", "8"))
    if not 0 <= minimum < float("inf"):
        raise ValueError("FACMAN_MIN_FREE_GIB must be finite and nonnegative")
    existing = path.resolve()
    while not existing.exists():
        existing = existing.parent
    free = shutil.disk_usage(existing).free / (1024 ** 3)
    if free < minimum:
        raise ValueError(f"development output drive has {free:.2f} GiB free; "
                         f"{minimum:g} GiB reserve required before build or package: {path}")


def command(root: Path, configuration: str, targets: list[str],
            prerequisites: dict[str, str]) -> list[str]:
    jobs = int(os.environ.get("CMAKE_BUILD_PARALLEL_LEVEL", "2"))
    if jobs < 1:
        raise ValueError("CMAKE_BUILD_PARALLEL_LEVEL must be positive")
    args = ["cmake", "--build", str(root), "--config", configuration, "--parallel", str(jobs)]
    if targets and "*" not in targets:
        args.extend(["--target", *sorted({prerequisites.get(t, t) for t in targets})])
    cache = root / "CMakeCache.txt"
    generator = next((line.partition("=")[2] for line in cache.read_text(encoding="utf-8").splitlines()
                      if line.startswith("CMAKE_GENERATOR:INTERNAL=")), "") if cache.is_file() else ""
    if os.name == "nt" and generator.startswith("Visual Studio"):
        # FileTracker excludes AppData roots. Disabling it also removes header
        # dependencies; CMake does not replace MSBuild's C++ tracking. A clean
        # rebuild is therefore mandatory for this tracking-disabled invocation.
        args.extend(["--clean-first", "--", "/p:TrackFileAccess=false", "/nr:false"])
    return args
