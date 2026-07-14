# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GRAMMAR = ROOT / "contracts/generated-index/command_cli_grammar.v2.json"
TUI_MAIN = ROOT / "apps/tui/tui_main.cpp"
TUI_FORMS = ROOT / "apps/tui/tui_guided_forms.cpp"
WINFORMS = ROOT / "apps/gui/windows/winforms/MainForm.cs"
WINFORMS_VIEW = ROOT / "apps/gui/windows/winforms/OperationalVisualization.cs"
APPKIT = ROOT / "apps/gui/macos/appkit/MainWindowController.m"


def validate() -> list[str]:
    problems: list[str] = []
    grammar = json.loads(GRAMMAR.read_text(encoding="utf-8"))
    commands = grammar.get("commands", [])
    enum_fields = {
        field["name"]: field.get("choices", [])
        for command in commands
        for field in command.get("request_fields", [])
        if field.get("type") == "enum"
    }
    expected_choices = {
        "preferred_transport": ["direct", "process", "daemon"],
        "display_color_policy": ["auto", "always", "never"],
        "window_mode": ["windowed", "fullscreen"],
        "graphics_quality": ["low", "medium", "high"],
        "audio": ["enabled", "disabled"],
        "selection_mode": ["none", "load-save", "benchmark-save"],
        "launch_mode": ["gui", "headless-plan", "benchmark-preview"],
        "confirmation": ["APPLY"],
    }
    for name, choices in expected_choices.items():
        if enum_fields.get(name) != choices:
            problems.append(f"generated enum choices are incomplete for {name}")

    tui_main = TUI_MAIN.read_text(encoding="utf-8")
    tui_forms = TUI_FORMS.read_text(encoding="utf-8")
    for option in ("--color", "--plain", "--page-size", "--transport"):
        if option not in tui_main:
            problems.append(f"TUI operational option is missing: {option}")
    for anchor in (
        "Categories", "matching", "required", "optional", "repeatable", "Review", "Type APPLY",
        "structured refusal or error", "[progress]", "write_paged", ":cancel", "request_fields_json",
    ):
        if anchor not in tui_forms:
            problems.append(f"generated guided-form behavior is missing: {anchor}")
    if "JSON payload (empty" in tui_main + tui_forms:
        problems.append("interactive TUI still asks for raw JSON")
    if "NO_COLOR" not in tui_main or "terminal_output()" not in tui_main:
        problems.append("TUI redirected/plain accessibility boundary is missing")
    if "DaemonTransport" not in (ROOT / "apps/tui/tui_command_client.cpp").read_text(encoding="utf-8"):
        problems.append("TUI daemon selection does not preserve the explicit unavailable transport")

    winforms = WINFORMS.read_text(encoding="utf-8") + WINFORMS_VIEW.read_text(encoding="utf-8")
    appkit = APPKIT.read_text(encoding="utf-8")
    for category in ("Snapshots", "Profiles", "Servers"):
        if category not in winforms or category not in appkit:
            problems.append(f"desktop generated category is missing: {category}")
    for view in (
        "Instance diff", "Snapshot list or diff", "Modset plan graph", "Save index or retention plan",
        "Server plan", "Transaction and recovery state",
    ):
        if view not in winforms or view not in appkit:
            problems.append(f"desktop generic visualization is missing: {view}")
    for anchor in ("AccessibleName", "AccessibleDescription", "AutoScaleMode.Dpi"):
        if anchor not in winforms:
            problems.append(f"WinForms accessibility anchor is missing: {anchor}")
    for anchor in ("setAccessibilityLabel", "setAccessibilityHelp", "NSAccessibilityPostNotification"):
        if anchor not in appkit:
            problems.append(f"AppKit accessibility anchor is missing: {anchor}")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"operational-ux-check: {problem}", file=sys.stderr)
        return 1
    print("operational-ux-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
