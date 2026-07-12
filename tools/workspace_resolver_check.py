# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate() -> list[str]:
    resolver = (ROOT / "runtime/client/workspace_resolver.cpp").read_text(encoding="utf-8")
    cli = (ROOT / "apps/cli/command_dispatch.cpp").read_text(encoding="utf-8")
    tui = (ROOT / "apps/tui/tui_main.cpp").read_text(encoding="utf-8")
    winforms = (ROOT / "apps/gui/windows/winforms/MainForm.cs").read_text(encoding="utf-8")
    appkit = (ROOT / "apps/gui/macos/appkit/MainWindowController.m").read_text(encoding="utf-8")
    problems: list[str] = []
    resolution_body = resolver.split("resolve_workspace_from_inputs", 1)[1]
    precedence = [
        "inputs.explicit_workspace",
        "inputs.facman_workspace",
        "inputs.compatibility_workspace",
        "inputs.preferred_workspace",
        "inputs.legacy_state == LegacyWorkspaceState::directory",
        'inputs.user_paths.data / "facman" / "workspace"',
    ]
    positions = [resolution_body.find(anchor) for anchor in precedence]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        problems.append("shared workspace resolver does not preserve the reviewed precedence")
    for name, source in (("CLI", cli), ("TUI", tui)):
        if "facman::client::resolve_workspace(" not in source:
            problems.append(f"{name} does not consume the shared workspace resolver")
        for duplicate in ("FACTORIO_LAUNCHER_WORKSPACE", '"/.facman/workspace"', '"factorio_workspace"'):
            if duplicate in source:
                problems.append(f"{name} retains duplicated workspace fallback logic: {duplicate}")
    if 'GetEnvironmentVariable("FACMAN_WORKSPACE")' in winforms:
        problems.append("WinForms duplicates FACMAN_WORKSPACE resolution")
    if 'objectForKey:@"FACMAN_WORKSPACE"' in appkit:
        problems.append("AppKit duplicates FACMAN_WORKSPACE resolution")
    if "workspace_default_unavailable" not in resolver or "workspace_legacy_unsafe" not in resolver:
        problems.append("shared resolver is missing fail-closed default or legacy refusals")
    return problems


def main() -> int:
    problems = validate()
    for problem in problems:
        print(f"workspace-resolver-check: {problem}")
    if problems:
        return 1
    print("workspace-resolver-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
