# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
import re
import shutil
import stat
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


def run(
    command: list[str], *, environment: dict[str, str] | None = None, log: Path | None = None
) -> None:
    if log is not None:
        run_logged(command, log, environment=environment)
        return
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


def run_logged(
    command: list[str], log: Path, *, environment: dict[str, str] | None = None
) -> None:
    """Keep exact child bytes; the outer lane supplies process/disk/time bounds."""
    record: dict[str, object] = {"argv": command, "exit_code": None}
    failure: BaseException | None = None
    # Reserve the receipt before dispatch, so a collision cannot mask a child failure.
    output = log.with_suffix(".json").open("x", encoding="utf-8", newline="\n")
    try:
        with log.with_suffix(".stdout.raw").open("xb") as stdout, log.with_suffix(".stderr.raw").open("xb") as stderr:
            completed = subprocess.run(
                command, check=False, stdout=stdout, stderr=stderr, env=environment
            )
        record["exit_code"] = completed.returncode
        if completed.returncode != 0:
            raise RuntimeError(
                f"command failed ({completed.returncode}): {' '.join(command)}; raw logs: {log}"
            )
    except BaseException as error:
        failure = error
        record["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        try:
            try:
                json.dump(record, output, indent=2)
                output.write("\n")
            finally:
                output.close()
        except Exception as log_error:
            if failure is None:
                raise
            failure.add_note(f"command receipt could not be completed: {log_error}")


@contextmanager
def fixture_root(work_root: Path | None):
    """Explicit roots are fresh and retained; ordinary CTest keeps its cleanup."""
    if work_root is None:
        with tempfile.TemporaryDirectory(prefix="facman installed sdk ") as temporary:
            yield Path(temporary)
        return
    if not work_root.is_absolute() or ".." in work_root.parts:
        raise ValueError("--work-root must be a fresh absolute path without parent components")
    for part in (work_root, *work_root.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            if part != work_root:
                raise ValueError("--work-root parent must already exist") from None
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("--work-root must not traverse a link or reparse point")
        if part == work_root:
            raise FileExistsError("--work-root already exists; retained fixtures cannot be reused")
    work_root.mkdir()
    yield work_root


def validate_abi_metadata(config: Path, compatibility: Path) -> None:
    """The installed contract and advertised consumer requirements must agree."""
    contract = json.loads(compatibility.read_text(encoding="utf-8"))
    text = config.read_text(encoding="utf-8")
    for key, variable in (("flb_abi", "FacMan_FLB_ABI_VERSION"),
                          ("required_ulk_abi", "FacMan_REQUIRED_ULK_ABI_VERSION")):
        version = contract.get(key) if isinstance(contract, dict) else None
        if not isinstance(version, dict):
            raise RuntimeError(f"installed SDK ABI contract is missing: {key}")
        major, minor, encoded = (version.get(field) for field in ("major", "minor", "encoded"))
        if (type(major) is not int or type(minor) is not int or type(encoded) is not int
                or not 0 <= major <= 65535 or not 0 <= minor <= 65535
                or encoded != (major << 16) | minor):
            raise RuntimeError(f"installed SDK ABI contract encoding is inconsistent: {key}")
        advertised = re.findall(rf'^[ \t]*set\({variable}[ \t]+"([0-9]+\.[0-9]+)"\)[ \t]*$',
                                text, re.MULTILINE)
        if advertised != [f"{major}.{minor}"]:
            raise RuntimeError(f"installed SDK ABI metadata disagrees with compatibility contract: {variable}")


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
    validate_abi_metadata(metadata[0], metadata[3])
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
    parser.add_argument("--work-root", type=Path, help="Fresh absolute fixture root retained on success or failure.")
    args = parser.parse_args()

    build_dir = args.build_dir.resolve()
    source_dir = args.source_dir.resolve()
    cache = build_dir / "CMakeCache.txt"
    if not cache.is_file():
        raise RuntimeError(f"configured build cache is missing: {cache}")

    with fixture_root(args.work_root) as root:
        logs = root / "commands" if args.work_root is not None else None
        if logs is not None:
            logs.mkdir()
        initial = root / "initial-sdk"
        relocated = root / "relocated-sdk"
        consumer_build = root / "consumer-build"
        run([args.cmake, "--install", str(build_dir), "--prefix", str(initial), "--config", args.config],
            log=logs / "01-install" if logs is not None else None)
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
        run(configure, log=logs / "02-configure" if logs is not None else None)
        run([args.cmake, "--build", str(consumer_build), "--config", args.config],
            log=logs / "03-build" if logs is not None else None)

        environment = os.environ.copy()
        environment["PATH"] = str(relocated / "bin") + os.pathsep + environment.get("PATH", "")
        environment["LD_LIBRARY_PATH"] = str(relocated / "lib") + os.pathsep + environment.get("LD_LIBRARY_PATH", "")
        environment["DYLD_LIBRARY_PATH"] = str(relocated / "lib") + os.pathsep + environment.get("DYLD_LIBRARY_PATH", "")

        suffix = ".exe" if os.name == "nt" else ""
        for index, name in enumerate(("facman_sdk_consumer", "facman_sdk_legacy_consumer"), 4):
            candidates = [
                consumer_build / args.config / f"{name}{suffix}",
                consumer_build / f"{name}{suffix}",
            ]
            executable = next((path for path in candidates if path.is_file()), None)
            if executable is None:
                raise RuntimeError(f"installed SDK consumer {name} was not built under {consumer_build}")
            run([str(executable)], environment=environment,
                log=logs / f"{index:02d}-{name}" if logs is not None else None)

    print("installed-sdk-smoke: ok (relocated current and legacy C consumers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
