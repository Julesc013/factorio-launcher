#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the unified FacMan product-stage contract and runtime resource pack."""

from __future__ import annotations

import argparse
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import package_layout_check, resource_pack  # noqa: E402


PRODUCT_PROFILES = {
    "windows_product_x64": {
        "gui": "FacMan.exe",
        "terminal": "bin/facman.exe",
        "resources": "facman.resources",
    },
    "linux_product_x64": {
        "gui": "FacMan",
        "terminal": "facman",
        "resources": "share/facman/facman.resources",
    },
    "macos_product_x64": {
        "gui": "FacMan.app/Contents/MacOS/FacMan",
        "terminal": "FacMan.app/Contents/MacOS/facman",
        "resources": "FacMan.app/Contents/Resources/facman.resources",
    },
}
FORBIDDEN_PUBLIC_NAMES = {
    "facman-tui",
    "facman-tui.exe",
    "facmand",
    "facmand.exe",
    "facman-gui-gtk",
    "facman-gui-qt",
    "facman.winforms.exe",
}
FORBIDDEN_PRODUCT_ROOTS = {
    ".aide",
    ".github",
    "build",
    "contracts",
    "content",
    "evidence",
    "include",
    "tests",
    "tools",
}
SDK_MARKERS = {"cmake", "pkgconfig", "facman-flb.pc", "facmantargets.cmake"}


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def profile_problems(profile_id: str) -> list[str]:
    expected = PRODUCT_PROFILES[profile_id]
    path = ROOT / "release" / "profiles" / profile_id / "profile.toml"
    profile = load_toml(path)
    required = profile.get("required_components", {})
    entrypoints = profile.get("entrypoints", {})
    problems: list[str] = []
    if not isinstance(required, dict) or required.get("resources") != expected["resources"]:
        problems.append(f"{profile_id}: required facman.resources path is not canonical")
    if isinstance(required, dict) and ({"contracts", "content"} & set(required)):
        problems.append(f"{profile_id}: loose contracts/content requirements are forbidden")
    if not isinstance(entrypoints, dict):
        problems.append(f"{profile_id}: entrypoints table is missing")
    else:
        if entrypoints.get("gui") != expected["gui"]:
            problems.append(f"{profile_id}: public GUI entrypoint must be {expected['gui']}")
        if entrypoints.get("cli") != expected["terminal"] or entrypoints.get("tui") != expected["terminal"]:
            problems.append(f"{profile_id}: CLI and TUI must share {expected['terminal']}")
    manifest_path = ROOT / str(profile.get("package_manifest", ""))
    bundle = package_layout_check.expand_bundle_manifest(manifest_path, load_toml(manifest_path), [])
    names = {str(item.get("name", "")) for item in bundle.get("components", [])}
    if "runtime_resources" not in names or {"contracts_schema", "factorio_content"} & names:
        problems.append(f"{profile_id}: product bundle must use only runtime_resources")
    return problems


def stage_problems(stage: Path, profile_id: str) -> list[str]:
    expected = PRODUCT_PROFILES[profile_id]
    problems: list[str] = []
    stage = stage.resolve()
    if not stage.is_dir():
        return [f"{profile_id}: product stage does not exist: {stage}"]
    files = [path for path in stage.rglob("*") if path.is_file()]
    relative = [path.relative_to(stage).as_posix() for path in files]
    folded: dict[str, str] = {}
    for value in relative:
        key = value.casefold()
        if key in folded:
            problems.append(f"{profile_id}: case-fold collision: {folded[key]} and {value}")
        folded[key] = value
        leaf = Path(value).name.casefold()
        if leaf in FORBIDDEN_PUBLIC_NAMES:
            problems.append(f"{profile_id}: forbidden public executable: {value}")
        if any(part.casefold() in SDK_MARKERS for part in Path(value).parts):
            problems.append(f"{profile_id}: SDK payload is forbidden: {value}")
    top_levels = {path.name.casefold() for path in stage.iterdir()}
    for forbidden in sorted(FORBIDDEN_PRODUCT_ROOTS & top_levels):
        problems.append(f"{profile_id}: non-product root is forbidden: {forbidden}")
    for role in ("gui", "terminal", "resources"):
        if expected[role] not in relative:
            problems.append(f"{profile_id}: missing {role}: {expected[role]}")
    terminal_names = [
        value
        for value in relative
        if Path(value).name.casefold() in {"facman", "facman.exe"}
        and value != expected["gui"]
    ]
    if terminal_names != [expected["terminal"]]:
        problems.append(
            f"{profile_id}: product must expose exactly one terminal host, found {terminal_names}"
        )
    resource_path = stage / expected["resources"]
    if resource_path.is_file():
        try:
            resource_pack.verify(resource_path)
        except (OSError, ValueError) as exc:
            problems.append(f"{profile_id}: invalid facman.resources: {exc}")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=sorted(PRODUCT_PROFILES))
    parser.add_argument("--stage", type=Path)
    args = parser.parse_args(argv)
    problems: list[str] = []
    selected = [args.profile] if args.profile else sorted(PRODUCT_PROFILES)
    for profile_id in selected:
        assert profile_id is not None
        problems.extend(profile_problems(profile_id))
        if args.stage is not None:
            problems.extend(stage_problems(args.stage, profile_id))
    if problems:
        for problem in problems:
            print(f"package-contract-tck: {problem}", file=sys.stderr)
        return 1
    print(f"package-contract-tck: ok ({', '.join(selected)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
