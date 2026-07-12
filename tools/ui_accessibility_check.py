# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import re
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STRINGS = ROOT / "content" / "factorio" / "strings" / "en-US.toml"
CATALOG = ROOT / "contracts" / "generated-index" / "frontend_command_catalog.v1.json"
THEMES = [
    ROOT / "content" / "factorio" / "ui" / "themes" / "default.toml",
    ROOT / "content" / "factorio" / "ui" / "themes" / "high_contrast.toml",
]
HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")

REQUIRED_STRINGS = {
    "app_name",
    "screen_dashboard",
    "screen_doctor",
    "screen_installs",
    "screen_instances",
    "screen_launch_plan",
    "screen_diagnostics",
    "screen_settings_about",
    "refusal_generic",
    "risk_read_only",
    "risk_workspace_write",
    "risk_external",
    "risk_setup_mutation",
    "risk_blocked",
}

REQUIRED_COLORS = {"background", "foreground", "accent", "warning", "danger", "focus"}
REQUIRED_ACCESSIBILITY_TRUE = {
    "keyboard_navigation",
    "screen_reader_labels",
    "font_scaling",
    "high_contrast_ready",
    "reduced_motion",
}


def main() -> int:
    problems: list[str] = []
    problems.extend(validate_strings())
    for theme in THEMES:
        problems.extend(validate_theme(theme))

    if problems:
        for problem in problems:
            print(f"ui-accessibility-check: {problem}", file=sys.stderr)
        return 1
    print("ui-accessibility-check: ok")
    return 0


def load_toml(path: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle), []
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return {}, [f"{path.relative_to(ROOT)}: {exc}"]


def validate_strings() -> list[str]:
    data, problems = load_toml(STRINGS)
    if problems:
        return problems
    if data.get("schema") != "facman.ui.strings.v1":
        problems.append(f"{STRINGS.relative_to(ROOT)}: invalid schema")
    if data.get("locale") != "en-US":
        problems.append(f"{STRINGS.relative_to(ROOT)}: locale must be en-US")
    strings = data.get("strings", {})
    if not isinstance(strings, dict):
        return problems + [f"{STRINGS.relative_to(ROOT)}: strings must be a table"]
    missing = sorted(REQUIRED_STRINGS - set(strings))
    if missing:
        problems.append(f"{STRINGS.relative_to(ROOT)}: missing strings {missing}")
    try:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return problems + [f"{CATALOG.relative_to(ROOT)}: {exc}"]
    expected_command_keys = {
        str(key)
        for command in catalog.get("commands", [])
        for key in command.get("localization_keys", [])
    }
    missing_command_keys = sorted(expected_command_keys - set(strings))
    if missing_command_keys:
        problems.append(f"{STRINGS.relative_to(ROOT)}: missing generated command strings {missing_command_keys}")
    unused_command_keys = sorted(
        key for key in strings if key.startswith("command.") and key not in expected_command_keys
    )
    if unused_command_keys:
        problems.append(f"{STRINGS.relative_to(ROOT)}: unused generated command strings {unused_command_keys}")
    return problems


def validate_theme(path: Path) -> list[str]:
    data, problems = load_toml(path)
    if problems:
        return problems
    if data.get("schema") != "facman.ui.theme.v1":
        problems.append(f"{path.relative_to(ROOT)}: invalid schema")
    colors = data.get("colors", {})
    if not isinstance(colors, dict):
        return problems + [f"{path.relative_to(ROOT)}: colors must be a table"]
    for key in sorted(REQUIRED_COLORS):
        value = colors.get(key)
        if not isinstance(value, str) or not HEX_COLOR.match(value):
            problems.append(f"{path.relative_to(ROOT)}: color {key} must be #RRGGBB")
    accessibility = data.get("accessibility", {})
    if not isinstance(accessibility, dict):
        return problems + [f"{path.relative_to(ROOT)}: accessibility must be a table"]
    for key in sorted(REQUIRED_ACCESSIBILITY_TRUE):
        if accessibility.get(key) is not True:
            problems.append(f"{path.relative_to(ROOT)}: accessibility {key} must be true")
    if accessibility.get("color_only_semantics") is not False:
        problems.append(f"{path.relative_to(ROOT)}: color_only_semantics must be false")
    if path.name == "high_contrast.toml" and data.get("high_contrast") is not True:
        problems.append(f"{path.relative_to(ROOT)}: high_contrast theme must declare high_contrast = true")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
