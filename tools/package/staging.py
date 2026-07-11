from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def install_tree(build_root: Path, destination: Path, configuration: str | None = None) -> Path:
    if destination.exists():
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if configuration is None:
        release = any((build_root / "Release" / name).is_file() for name in ("facman", "facman.exe"))
        debug = any((build_root / "Debug" / name).is_file() for name in ("facman", "facman.exe"))
        configuration = "Release" if release or not debug else "Debug"
    completed = subprocess.run(
        ["cmake", "--install", str(build_root), "--config", configuration, "--prefix", str(destination)],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.returncode != 0:
        raise ValueError(f"CMake install staging failed ({completed.returncode}): {completed.stdout.strip()}")
    return destination
