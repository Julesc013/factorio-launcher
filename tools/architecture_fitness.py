# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
EXCEPTIONS = ROOT / "contracts" / "policy" / "architecture_fitness_exceptions.v1.toml"
SOURCE_SUFFIXES = {".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp"}


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def first_party_sources(*roots: str) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        base = ROOT / root
        if not base.exists():
            continue
        files.extend(path for path in base.rglob("*") if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES)
    return sorted(files)


def load_exceptions(check_name: str) -> set[str]:
    with EXCEPTIONS.open("rb") as handle:
        data = tomllib.load(handle)
    if data.get("schema") != "facman.architecture_fitness_exceptions.v1":
        raise ValueError(f"{relative(EXCEPTIONS)}: invalid schema")
    checks = data.get("checks", {})
    values = checks.get(check_name, []) if isinstance(checks, dict) else []
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ValueError(f"{relative(EXCEPTIONS)}: checks.{check_name} must be a string array")
    return set(values)


def report(check_name: str, detected: set[str]) -> int:
    try:
        expected = load_exceptions(check_name)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"{check_name.replace('_', '-')}: {exc}", file=sys.stderr)
        return 1
    added = detected - expected
    stale = expected - detected
    if added or stale:
        for item in sorted(added):
            print(f"{check_name.replace('_', '-')}: unbudgeted violation: {item}", file=sys.stderr)
        for item in sorted(stale):
            print(f"{check_name.replace('_', '-')}: stale exception must be removed: {item}", file=sys.stderr)
        return 1
    print(f"{check_name.replace('_', '-')}: ok ({len(detected)} known exceptions)")
    return 0


def include_names(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    return set(re.findall(r'^\s*#\s*include\s*[<"]([^>"]+)[>"]', text, re.MULTILINE))


def cmake_target_links(target: str) -> list[str]:
    text = cmake_text()
    pattern = re.compile(rf"target_link_libraries\s*\(\s*{re.escape(target)}\s+(.*?)\)", re.DOTALL)
    match = pattern.search(text)
    if not match:
        return []
    tokens = re.findall(r"[A-Za-z0-9_:+.-]+", match.group(1))
    return [token for token in tokens if token not in {"PRIVATE", "PUBLIC", "INTERFACE"}]


def cmake_text() -> str:
    paths = [ROOT / "CMakeLists.txt", *sorted(ROOT.glob("cmake/*.cmake"))]
    paths.extend(sorted((ROOT / "runtime").glob("**/CMakeLists.txt")))
    paths.extend(sorted((ROOT / "apps").glob("**/CMakeLists.txt")))
    paths.extend(sorted((ROOT / "tests").glob("**/CMakeLists.txt")))
    return "\n".join(path.read_text(encoding="utf-8") for path in paths if path.is_file())


def run(check_name: str, detector: Callable[[], set[str]]) -> int:
    try:
        return report(check_name, detector())
    except OSError as exc:
        print(f"{check_name.replace('_', '-')}: {exc}", file=sys.stderr)
        return 1
