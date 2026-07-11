# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import package_layout_check

RELEASE_INDEX = ROOT / "release" / "index" / "release_index.v1.toml"
PROFILE_CATALOG = ROOT / "release" / "profiles" / "profile_catalog.v1.toml"

REQUIRED_INSTALL_MODES = {"portable", "user", "system"}


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def release_index() -> dict[str, Any]:
    return load_toml(RELEASE_INDEX)


def index_path(key: str) -> Path:
    value = str(release_index().get(key, ""))
    if not value:
        raise ValueError(f"{RELEASE_INDEX}: missing {key}")
    return ROOT / value


def profile_paths() -> list[Path]:
    values = release_index().get("profiles", [])
    if not isinstance(values, list):
        raise ValueError(f"{RELEASE_INDEX}: profiles must be an array")
    return [ROOT / str(value) for value in values]


def load_profiles() -> list[tuple[Path, dict[str, Any]]]:
    return [(path, load_toml(path)) for path in profile_paths()]


def load_profile_catalog() -> dict[str, dict[str, Any]]:
    data = load_toml(PROFILE_CATALOG)
    profiles = data.get("profile", [])
    if not isinstance(profiles, list):
        raise ValueError(f"{PROFILE_CATALOG}: profile must be an array")
    catalog: dict[str, dict[str, Any]] = {}
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        profile_id = str(profile.get("id", ""))
        if profile_id:
            catalog[profile_id] = profile
    return catalog


def expanded_bundle_for_profile(profile: dict[str, Any]) -> dict[str, Any]:
    bundle_path = ROOT / str(profile.get("package_manifest", ""))
    return package_layout_check.expand_bundle_manifest(bundle_path, load_toml(bundle_path), [])


def component_destinations(bundle: dict[str, Any]) -> set[str]:
    destinations: set[str] = set()
    components = bundle.get("components", [])
    if not isinstance(components, list):
        return destinations
    for component in components:
        if isinstance(component, dict):
            destinations.add(package_layout_check.normalize_layout_path(str(component.get("destination", ""))))
    return destinations


def string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def table(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def report(tool_name: str, problems: list[str]) -> int:
    if problems:
        for problem in problems:
            print(f"{tool_name}: {problem}", file=sys.stderr)
        return 1
    print(f"{tool_name}: ok")
    return 0
