# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIRST_PARTY = ("apps/", "runtime/", "tests/native/")
SUFFIXES = {".c", ".cc", ".cpp", ".cxx"}
WINDOWS_SOURCES = {
    "runtime/platform/fl_process_supervisor_windows.cpp",
    "runtime/platform/fl_random_windows.cpp",
    "runtime/platform/windows/fl_user_paths_windows.cpp",
}
POSIX_SOURCES = {"runtime/platform/fl_process_supervisor_posix.cpp"}
LINUX_SOURCES = {
    "runtime/platform/fl_random_linux.cpp",
    "runtime/platform/linux/fl_user_paths_linux.cpp",
}
MACOS_SOURCES = {
    "runtime/platform/fl_random_macos.cpp",
    "runtime/platform/macos/fl_user_paths_macos.cpp",
}


def changed_sources(base: str) -> list[Path]:
    completed = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    result = []
    for raw in completed.stdout.splitlines():
        relative = raw.strip().replace("\\", "/")
        path = ROOT / relative
        if relative.startswith(FIRST_PARTY) and path.suffix.lower() in SUFFIXES and path.is_file():
            result.append(path)
    return sorted(result)


def compilation_database_sources(database: Path) -> set[Path]:
    payload = json.loads(database.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("compile_commands.json must contain an array")
    result: set[Path] = set()
    for index, entry in enumerate(payload):
        if not isinstance(entry, dict) or not isinstance(entry.get("file"), str):
            raise ValueError(f"compile command {index} has no source file")
        source = Path(entry["file"])
        if not source.is_absolute():
            directory = entry.get("directory")
            if not isinstance(directory, str):
                raise ValueError(f"compile command {index} has no working directory")
            source = Path(directory) / source
        result.add(source.resolve())
    return result


def compilation_database_index(build_roots: list[Path]) -> dict[Path, Path]:
    """Map each compiled source to the build root that owns its command."""
    result: dict[Path, Path] = {}
    for build_root in build_roots:
        database = build_root / "compile_commands.json"
        for source in compilation_database_sources(database):
            result.setdefault(source, build_root)
    return result


def platform_omissions(platform: str = sys.platform) -> set[str]:
    if platform == "win32":
        return POSIX_SOURCES | LINUX_SOURCES | MACOS_SOURCES
    if platform == "darwin":
        return WINDOWS_SOURCES | LINUX_SOURCES
    if platform.startswith("linux"):
        return WINDOWS_SOURCES | MACOS_SOURCES
    return set()


def select_compiled_sources(
    sources: list[Path], compiled: set[Path], allowed_omissions: set[str] | None = None
) -> tuple[list[Path], list[Path], list[Path]]:
    if allowed_omissions is None:
        allowed_omissions = platform_omissions()
    selected: list[Path] = []
    platform_exclusive: list[Path] = []
    missing: list[Path] = []
    for source in sources:
        resolved = source.resolve()
        if resolved in compiled:
            selected.append(source)
            continue
        relative = resolved.relative_to(ROOT.resolve()).as_posix()
        if relative in allowed_omissions:
            platform_exclusive.append(source)
        else:
            missing.append(source)
    return selected, platform_exclusive, missing


def main() -> int:
    parser = argparse.ArgumentParser(description="Run clang-tidy on changed first-party translation units.")
    parser.add_argument("--base", default="HEAD^")
    parser.add_argument("--build-root", default="build/clang-tidy", type=Path)
    parser.add_argument(
        "--additional-build-root",
        action="append",
        default=[],
        type=Path,
        help="Additional build root containing compile_commands.json; may be repeated.",
    )
    parser.add_argument("--allow-unavailable", action="store_true")
    args = parser.parse_args()
    executable = shutil.which("clang-tidy")
    build_roots = [args.build_root, *args.additional_build_root]
    missing_databases = [
        build_root / "compile_commands.json"
        for build_root in build_roots
        if not (build_root / "compile_commands.json").is_file()
    ]
    if executable is None or missing_databases:
        missing = ", ".join(str(path) for path in missing_databases)
        message = "clang-tidy is unavailable" if executable is None else f"compile database is unavailable: {missing}"
        if args.allow_unavailable:
            print(f"clang-tidy-changed: skipped ({message})")
            return 0
        print(f"clang-tidy-changed: {message}", file=sys.stderr)
        return 1
    try:
        compiled_index = compilation_database_index(build_roots)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"clang-tidy-changed: invalid compilation database: {error}", file=sys.stderr)
        return 1
    changed = changed_sources(args.base)
    sources, platform_exclusive, missing = select_compiled_sources(changed, set(compiled_index))
    if missing:
        relative = ", ".join(path.relative_to(ROOT).as_posix() for path in missing)
        print(f"clang-tidy-changed: changed sources have no compile command: {relative}", file=sys.stderr)
        return 1
    for source in sources:
        completed = subprocess.run(
            [executable, "-p", str(compiled_index[source.resolve()]), str(source)],
            cwd=ROOT,
            check=False,
        )
        if completed.returncode:
            return completed.returncode
    print(
        "clang-tidy-changed: ok "
        f"({len(sources)} compiled changes; {len(platform_exclusive)} platform-exclusive changes skipped)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
