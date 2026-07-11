# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.validators.release import _common

TOOL = "release-frontend-bundle-check"


def main() -> int:
    try:
        problems = validate()
    except (OSError, ValueError) as exc:
        problems = [str(exc)]
    return _common.report(TOOL, problems)


def validate() -> list[str]:
    problems: list[str] = []
    for path, profile in _common.load_profiles():
        problems.extend(validate_profile(path, profile))
    return problems


def validate_profile(path: Path, profile: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    frontends = _common.table(profile.get("frontends"))
    entrypoints = _common.table(profile.get("entrypoints"))
    bundle = _common.expanded_bundle_for_profile(profile)
    destinations = _common.component_destinations(bundle)
    required_roles = required_frontend_roles(frontends)

    for role in sorted(required_roles):
        entrypoint = str(entrypoints.get(role, ""))
        if not entrypoint:
            problems.append(f"{relative(path)}: missing {role} entrypoint")
            continue
        if entrypoint not in destinations and bundle.get("package_type") not in {"appimage", "installer"}:
            problems.append(f"{relative(path)}: {role} entrypoint missing from bundle: {entrypoint}")

    selected_entrypoints = [str(entrypoints.get(role, "")) for role in required_roles]
    non_empty = [entrypoint for entrypoint in selected_entrypoints if entrypoint]
    if len(non_empty) != len(set(non_empty)):
        problems.append(f"{relative(path)}: frontend entrypoints must be separate executables")

    return problems


def required_frontend_roles(frontends: dict[str, Any]) -> set[str]:
    return set(frontends)


def relative(path: Path) -> str:
    return path.relative_to(_common.ROOT).as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
