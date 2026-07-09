from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

CHECKED_SUFFIXES = {
    ".c",
    ".cpp",
    ".cs",
    ".csproj",
    ".h",
    ".hpp",
    ".m",
    ".md",
    ".mm",
    ".py",
    ".sln",
    ".swift",
    ".toml",
    ".vcxproj",
}

LONG_LINE_LIMIT = 240
MINIFIED_SIZE_LIMIT = 1200
MINIFIED_MIN_LINES = 4

LONG_LINE_ALLOWLIST_PREFIXES = {
    ".aide/",
    "docs/reference/",
}

LONG_LINE_ALLOWLIST_FILES = {
    "runtime/factorio/binding/flb_api.c",
}


def main() -> int:
    problems: list[str] = []
    for path in tracked_files():
        if path.suffix.lower() not in CHECKED_SUFFIXES:
            continue
        rel = path.relative_to(ROOT).as_posix()
        text = path.read_text(encoding="utf-8", errors="ignore")
        lines = text.splitlines()
        size = path.stat().st_size
        if size > MINIFIED_SIZE_LIMIT and len(lines) < MINIFIED_MIN_LINES:
            problems.append(
                f"{rel}: looks minified or collapsed: {size} bytes across {len(lines)} lines"
            )
        if not long_lines_allowed(rel):
            for index, line in enumerate(lines, start=1):
                if len(line) > LONG_LINE_LIMIT:
                    problems.append(
                        f"{rel}:{index}: line is {len(line)} chars; limit is {LONG_LINE_LIMIT}"
                    )

    if problems:
        for problem in problems:
            print(f"source-format-check: {problem}", file=sys.stderr)
        return 1
    print("source-format-check: ok")
    return 0


def tracked_files() -> list[Path]:
    completed = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
    )
    paths: list[Path] = []
    for line in completed.stdout.splitlines():
        path = ROOT / line
        if path.is_file():
            paths.append(path)
    return paths


def long_lines_allowed(rel: str) -> bool:
    if rel in LONG_LINE_ALLOWLIST_FILES:
        return True
    return any(rel.startswith(prefix) for prefix in LONG_LINE_ALLOWLIST_PREFIXES)


if __name__ == "__main__":
    raise SystemExit(main())
