# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.validators.release import _common

TOOL = "release-system-workspace-check"

FORBIDDEN_SYSTEM_SEGMENTS = {
    "accounts",
    "audit",
    "cache",
    "diagnostics",
    "exports",
    "instances",
    "modsets",
    "profiles",
    "saves",
    "state",
    "workspace",
}


def main() -> int:
    try:
        problems = validate()
    except (OSError, ValueError) as exc:
        problems = [str(exc)]
    return _common.report(TOOL, problems)


def validate() -> list[str]:
    problems: list[str] = []
    for path, profile in _common.load_profiles():
        install_modes = set(_common.string_list(profile.get("install_modes")))
        if "system" not in install_modes:
            continue
        bundle = _common.expanded_bundle_for_profile(profile)
        for destination in sorted(_common.component_destinations(bundle)):
            bad_segments = set(PurePosixPath(destination).parts) & FORBIDDEN_SYSTEM_SEGMENTS
            for segment in sorted(bad_segments):
                problems.append(f"{relative(path)}: system package destination includes {segment}: {destination}")
    return problems


def relative(path: Path) -> str:
    return path.relative_to(_common.ROOT).as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
