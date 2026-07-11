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
    ".yaml",
    ".yml",
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

# Source-pinned third-party files retain upstream formatting. Their integrity
# is governed by the dependency lock and admission tests, not FacMan style.
VENDORED_SOURCE_PREFIXES = {
    "external/miniz/",
}

MINIFIED_ALLOWLIST_FILES: set[str] = set()

PHYSICAL_LINE_GUARD_SCOPES = {
    ".github/workflows/",
    "contracts/",
    "release/",
    "tools/",
}

PHYSICAL_LINE_GUARD_SUFFIXES = {
    ".py",
    ".toml",
    ".yaml",
    ".yml",
}

REVIEWABLE_REQUIRED_FILES = {
    ".github/workflows/ci.yml",
    ".github/workflows/security.yml",
    "contracts/command/frontend/frontend.required_commands.v1.toml",
    "tools/frontend_contract_check.py",
    "tools/frontend_parity_check.py",
    "tools/gui_surface_check.py",
    "tools/package_layout_check.py",
    "tools/package_manifest_check.py",
    "tools/package_skeleton_build.py",
    "tools/package_skeleton_check.py",
    "tools/source_format_check.py",
    "tools/strict_check.py",
}


def main() -> int:
    problems: list[str] = []
    for path in tracked_files():
        if path.suffix.lower() not in CHECKED_SUFFIXES:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if vendored_source(rel):
            continue
        problems.extend(validate_file(path, rel))

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


def validate_file(path: Path, rel: str) -> list[str]:
    problems: list[str] = []
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="ignore")
    lines = normalized_lines(text)
    physical_lines = physical_lf_line_count(text)
    size = len(raw)
    if cr_only_line_endings_present(text):
        problems.append(f"{rel}: uses CR-only line endings; use LF line breaks")
    if rel in REVIEWABLE_REQUIRED_FILES and physical_lines < MINIFIED_MIN_LINES:
        problems.append(
            f"{rel}: required reviewable file has only {physical_lines} physical LF lines"
        )
    if (
        size > MINIFIED_SIZE_LIMIT
        and physical_lines < MINIFIED_MIN_LINES
        and not minified_allowed(rel)
    ):
        problems.append(
            f"{rel}: looks minified or collapsed: {size} bytes across {physical_lines} physical LF lines"
        )
    if (
        requires_physical_line_guard(rel)
        and size > MINIFIED_SIZE_LIMIT
        and physical_lines < MINIFIED_MIN_LINES
        and not minified_allowed(rel)
    ):
        problems.append(
            f"{rel}: package/discovery tooling must stay physically reviewable "
            f"({size} bytes across {physical_lines} physical LF lines)"
        )
    if not long_lines_allowed(rel):
        for index, line in enumerate(lines, start=1):
            if len(line) > LONG_LINE_LIMIT:
                problems.append(
                    f"{rel}:{index}: line is {len(line)} chars; limit is {LONG_LINE_LIMIT}"
                )
    return problems


def normalized_lines(text: str) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.splitlines()


def physical_lf_line_count(text: str) -> int:
    if not text:
        return 0
    return text.count("\n") if text.endswith("\n") else text.count("\n") + 1


def cr_only_line_endings_present(text: str) -> bool:
    return "\r" in text.replace("\r\n", "")


def minified_allowed(rel: str) -> bool:
    return rel in MINIFIED_ALLOWLIST_FILES


def requires_physical_line_guard(rel: str) -> bool:
    path = Path(rel)
    if path.suffix.lower() not in PHYSICAL_LINE_GUARD_SUFFIXES:
        return False
    return any(rel.startswith(prefix) for prefix in PHYSICAL_LINE_GUARD_SCOPES)


def long_lines_allowed(rel: str) -> bool:
    if rel in LONG_LINE_ALLOWLIST_FILES:
        return True
    return any(rel.startswith(prefix) for prefix in LONG_LINE_ALLOWLIST_PREFIXES)


def vendored_source(rel: str) -> bool:
    return any(rel.startswith(prefix) for prefix in VENDORED_SOURCE_PREFIXES)


if __name__ == "__main__":
    raise SystemExit(main())
