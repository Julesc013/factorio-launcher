# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def cache_value(cache: Path, key: str) -> str:
    prefix = f"{key}:"
    for line in cache.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith(prefix) and "=" in line:
            return line.split("=", 1)[1]
    return ""


def consumer_parent_configuration(cache: Path) -> list[str]:
    arguments: list[str] = []
    sanitizers = cache_value(cache, "FACMAN_ENABLE_SANITIZERS").upper()
    if sanitizers in {"1", "ON", "TRUE", "YES"}:
        arguments.append("-DFACMAN_CONSUMER_SANITIZERS=ON")
    return arguments


def run(command: list[str], *, environment: dict[str, str] | None = None) -> None:
    completed = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=environment,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"command failed ({completed.returncode}): {' '.join(command)}\n{completed.stdout}")


def validate_metadata(relocated: Path, build_dir: Path, initial: Path) -> None:
    metadata = (
        relocated / "lib" / "cmake" / "FacMan" / "FacManConfig.cmake",
        relocated / "lib" / "cmake" / "FacMan" / "FacManTargets.cmake",
        relocated / "lib" / "pkgconfig" / "facman-flb.pc",
        relocated / "share" / "facman" / "abi" / "compatibility.v1.json",
    )
    for path in metadata:
        if not path.is_file():
            raise RuntimeError(f"installed SDK metadata is missing: {path}")
    pkg_config = metadata[2].read_text(encoding="utf-8")
    if "prefix=${pcfiledir}/../.." not in pkg_config:
        raise RuntimeError("installed pkg-config metadata is not relocatable")
    forbidden_paths = (ROOT, build_dir, initial)
    forbidden = tuple(
        representation
        for path in forbidden_paths
        for representation in (str(path), path.as_posix())
    )
    for path in metadata[:3]:
        text = path.read_text(encoding="utf-8", errors="replace")
        for fragment in forbidden:
            if fragment in text:
                raise RuntimeError(f"installed SDK metadata leaks a source or staging path: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and run a C consumer against a relocated installed FacMan SDK.")
    parser.add_argument("--cmake", required=True)
    parser.add_argument("--build-dir", required=True, type=Path)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--config", default="Release")
    args = parser.parse_args()

    build_dir = args.build_dir.resolve()
    source_dir = args.source_dir.resolve()
    cache = build_dir / "CMakeCache.txt"
    if not cache.is_file():
        raise RuntimeError(f"configured build cache is missing: {cache}")

    with tempfile.TemporaryDirectory(prefix="facman installed sdk ") as temporary:
        root = Path(temporary)
        initial = root / "initial-sdk"
        relocated = root / "relocated-sdk"
        consumer_build = root / "consumer-build"
        run([args.cmake, "--install", str(build_dir), "--prefix", str(initial), "--config", args.config])
        shutil.move(str(initial), str(relocated))
        validate_metadata(relocated, build_dir, initial)

        configure = [args.cmake, "-S", str(source_dir), "-B", str(consumer_build)]
        generator = cache_value(cache, "CMAKE_GENERATOR")
        platform = cache_value(cache, "CMAKE_GENERATOR_PLATFORM")
        toolset = cache_value(cache, "CMAKE_GENERATOR_TOOLSET")
        if generator:
            configure.extend(["-G", generator])
        if platform:
            configure.extend(["-A", platform])
        if toolset:
            configure.extend(["-T", toolset])
        configure.append(f"-DCMAKE_PREFIX_PATH={relocated}")
        configure.extend(consumer_parent_configuration(cache))
        run(configure)
        run([args.cmake, "--build", str(consumer_build), "--config", args.config])

        environment = os.environ.copy()
        environment["PATH"] = str(relocated / "bin") + os.pathsep + environment.get("PATH", "")
        environment["LD_LIBRARY_PATH"] = str(relocated / "lib") + os.pathsep + environment.get("LD_LIBRARY_PATH", "")
        environment["DYLD_LIBRARY_PATH"] = str(relocated / "lib") + os.pathsep + environment.get("DYLD_LIBRARY_PATH", "")

        suffix = ".exe" if os.name == "nt" else ""
        for name in ("facman_sdk_consumer", "facman_sdk_legacy_consumer"):
            candidates = [
                consumer_build / args.config / f"{name}{suffix}",
                consumer_build / f"{name}{suffix}",
            ]
            executable = next((path for path in candidates if path.is_file()), None)
            if executable is None:
                raise RuntimeError(f"installed SDK consumer {name} was not built under {consumer_build}")
            run([str(executable)], environment=environment)

    print("installed-sdk-smoke: ok (relocated current and legacy C consumers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
