# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from pathlib import Path


def install_tree(
    build_root: Path,
    destination: Path,
    configuration: str | None = None,
    components: Sequence[str] | None = None,
) -> Path:
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if configuration is None:
        release = any((build_root / "Release" / name).is_file() for name in ("facman", "facman.exe"))
        debug = any((build_root / "Debug" / name).is_file() for name in ("facman", "facman.exe"))
        configuration = "Release" if release or not debug else "Debug"
    selected = tuple(components) if components is not None else (None,)
    for component in selected:
        command = [
            "cmake",
            "--install",
            str(build_root),
            "--config",
            configuration,
            "--prefix",
            str(destination),
        ]
        if component is not None:
            command.extend(["--component", component])
        completed = subprocess.run(
            command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        if completed.returncode != 0:
            label = component or "all"
            raise ValueError(
                f"CMake install staging failed for component {label} "
                f"({completed.returncode}): {completed.stdout.strip()}"
            )
    return destination
