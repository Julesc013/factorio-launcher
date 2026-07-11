# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOTS = ("apps/", "runtime/", "include/", "tools/", "tests/", "cmake/")
EXCLUDED_PREFIXES = (
    "runtime/core/generated/",
    "tests/fixtures/",
    "tests/golden/",
)
LINE_PREFIX = {
    ".c": "//", ".cc": "//", ".cpp": "//", ".cxx": "//",
    ".h": "//", ".hh": "//", ".hpp": "//", ".m": "//", ".mm": "//",
    ".cs": "//", ".swift": "//", ".qml": "//", ".py": "#", ".cmake": "#",
}


def tracked_sources() -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files", *[root.rstrip("/") for root in ROOTS]],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    result = []
    for raw in completed.stdout.splitlines():
        relative = raw.strip().replace("\\", "/")
        if relative.startswith(EXCLUDED_PREFIXES):
            continue
        path = ROOT / relative
        if path.name == "CMakeLists.txt" or path.suffix.lower() in LINE_PREFIX:
            result.append(path)
    return sorted(result)


def prefix_for(path: Path) -> str:
    return "#" if path.name == "CMakeLists.txt" else LINE_PREFIX[path.suffix.lower()]


def expected_lines(path: Path) -> tuple[str, str]:
    prefix = prefix_for(path)
    return (
        f"{prefix} SPDX-FileCopyrightText: 2026 Jules C",
        f"{prefix} SPDX-License-Identifier: MIT",
    )


def apply(path: Path) -> bool:
    text = path.read_text(encoding="utf-8-sig")
    copyright_line, license_line = expected_lines(path)
    if copyright_line in text and license_line in text:
        return False
    lines = text.splitlines(keepends=True)
    newline = "\r\n" if "\r\n" in text else "\n"
    insertion = 1 if lines and lines[0].startswith("#!") else 0
    header = [copyright_line + newline, license_line + newline]
    if lines:
        header.append(newline)
    path.write_text("".join(lines[:insertion] + header + lines[insertion:]), encoding="utf-8", newline="")
    return True


def missing() -> list[str]:
    problems = []
    for path in tracked_sources():
        text = path.read_text(encoding="utf-8-sig")
        for line in expected_lines(path):
            if line not in text:
                problems.append(f"{path.relative_to(ROOT).as_posix()}: missing {line}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply or verify first-party SPDX headers.")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.write:
        changed = sum(1 for path in tracked_sources() if apply(path))
        print(f"spdx-headers: updated {changed} files")
    problems = missing()
    if problems:
        for problem in problems:
            print(f"spdx-headers: {problem}", file=sys.stderr)
        return 1
    print(f"spdx-headers: ok ({len(tracked_sources())} first-party source files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
