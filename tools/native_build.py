# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Construct native builds without relying on excluded MSBuild dependencies."""
from __future__ import annotations
import os
from pathlib import Path


def command(root: Path, configuration: str, targets: list[str],
            prerequisites: dict[str, str]) -> list[str]:
    args = ["cmake", "--build", str(root), "--config", configuration, "--parallel"]
    if targets and "*" not in targets:
        args.extend(["--target", *sorted({prerequisites.get(t, t) for t in targets})])
    cache = root / "CMakeCache.txt"
    generator = next((line.partition("=")[2] for line in cache.read_text(encoding="utf-8").splitlines()
                      if line.startswith("CMAKE_GENERATOR:INTERNAL=")), "") if cache.is_file() else ""
    if os.name == "nt" and generator.startswith("Visual Studio"):
        # FileTracker excludes AppData roots. Disabling it also removes header
        # dependencies; CMake does not replace MSBuild's C++ tracking. A clean
        # rebuild is therefore mandatory for this tracking-disabled invocation.
        args.extend(["--clean-first", "--", "/p:TrackFileAccess=false"])
    return args
