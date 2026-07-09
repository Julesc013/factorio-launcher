from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.validators.release import _common

TOOL = "release-artifact-name-check"

REQUIRED_PHASE_1 = {
    "facman-<version>-windows-winforms-x64-portable.zip",
    "facman-<version>-windows-winforms-x64-setup.exe",
    "facman-<version>-macos-appkit-x64.dmg",
    "facman-<version>-linux-gtk-x64.tar.zst",
    "facman-<version>-source.tar.gz",
    "facman-<version>-release_manifest.json",
}

ALLOWED_EXTENSIONS = (
    ".zip",
    ".exe",
    ".msi",
    ".msix",
    ".dmg",
    ".pkg",
    ".tar.zst",
    ".tar.gz",
    ".AppImage",
    ".deb",
    ".rpm",
    ".json",
    ".txt",
)


def main() -> int:
    try:
        problems = validate()
    except (OSError, ValueError) as exc:
        problems = [str(exc)]
    return _common.report(TOOL, problems)


def validate() -> list[str]:
    path = _common.index_path("artifact_matrix")
    data = _common.load_toml(path)
    problems: list[str] = []
    if data.get("schema") != "facman.artifact_matrix.v1":
        problems.append(f"{relative(path)}: schema must be facman.artifact_matrix.v1")

    catalog = _common.load_profile_catalog()
    allowed_profile_ids = set(catalog) | {"release_metadata"}
    artifacts = data.get("artifact", [])
    if not isinstance(artifacts, list) or not artifacts:
        return [f"{relative(path)}: artifact entries are required"]

    phase_1_patterns: set[str] = set()
    seen: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            problems.append(f"{relative(path)}: artifact entry must be a table")
            continue
        pattern = str(artifact.get("pattern", ""))
        profile_id = str(artifact.get("profile_id", ""))
        if pattern in seen:
            problems.append(f"{relative(path)}: duplicate artifact pattern {pattern}")
        seen.add(pattern)
        problems.extend(validate_pattern(path, pattern))
        if profile_id not in allowed_profile_ids:
            problems.append(f"{relative(path)}: unknown profile_id {profile_id}")
        if int_value(artifact.get("phase")) == 1:
            phase_1_patterns.add(pattern)

    missing = REQUIRED_PHASE_1 - phase_1_patterns
    for pattern in sorted(missing):
        problems.append(f"{relative(path)}: missing phase 1 artifact {pattern}")
    return problems


def validate_pattern(path: Path, pattern: str) -> list[str]:
    problems: list[str] = []
    if not pattern:
        return [f"{relative(path)}: artifact pattern is empty"]
    if " " in pattern:
        problems.append(f"{relative(path)}: artifact pattern contains spaces: {pattern}")
    if "\\" in pattern or "/" in pattern:
        problems.append(f"{relative(path)}: artifact pattern must be a filename: {pattern}")
    if not pattern.startswith("facman-<version>-"):
        problems.append(f"{relative(path)}: artifact pattern must start with facman-<version>-: {pattern}")
    if "+" in pattern:
        problems.append(f"{relative(path)}: artifact filename must not contain '+': {pattern}")
    if pattern.lower() != pattern and not pattern.endswith(".AppImage"):
        problems.append(f"{relative(path)}: artifact pattern should be lowercase: {pattern}")
    if not pattern.endswith(ALLOWED_EXTENSIONS):
        problems.append(f"{relative(path)}: unsupported artifact extension: {pattern}")
    if not re.fullmatch(r"[A-Za-z0-9._<>-]+", pattern):
        problems.append(f"{relative(path)}: artifact pattern has unsupported characters: {pattern}")
    return problems


def int_value(value: Any) -> int:
    return value if isinstance(value, int) else -1


def relative(path: Path) -> str:
    return path.relative_to(_common.ROOT).as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
