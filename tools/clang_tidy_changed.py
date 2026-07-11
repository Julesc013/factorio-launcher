# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIRST_PARTY = ("apps/", "runtime/", "tests/native/")
SUFFIXES = {".c", ".cc", ".cpp", ".cxx"}


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


def main() -> int:
    parser = argparse.ArgumentParser(description="Run clang-tidy on changed first-party translation units.")
    parser.add_argument("--base", default="HEAD^")
    parser.add_argument("--build-root", default="build/clang-tidy", type=Path)
    parser.add_argument("--allow-unavailable", action="store_true")
    args = parser.parse_args()
    executable = shutil.which("clang-tidy")
    database = args.build_root / "compile_commands.json"
    if executable is None or not database.is_file():
        message = "clang-tidy or compile_commands.json is unavailable"
        if args.allow_unavailable:
            print(f"clang-tidy-changed: skipped ({message})")
            return 0
        print(f"clang-tidy-changed: {message}", file=sys.stderr)
        return 1
    sources = changed_sources(args.base)
    for source in sources:
        completed = subprocess.run(
            [executable, "-p", str(args.build_root), str(source)], cwd=ROOT, check=False
        )
        if completed.returncode:
            return completed.returncode
    print(f"clang-tidy-changed: ok ({len(sources)} changed translation units)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
