# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_toml(relative: str) -> dict:
    with (ROOT / relative).open("rb") as handle:
        return tomllib.load(handle)


def validate() -> list[str]:
    problems: list[str] = []
    winforms = ROOT / "apps/gui/windows/winforms"
    appkit = ROOT / "apps/gui/macos/appkit"
    for retired in (
        winforms / "JsonRpcClient.cs",
        appkit / "JsonRpcClient.h",
        appkit / "JsonRpcClient.mm",
    ):
        if retired.exists():
            problems.append(f"misnamed JSON-RPC client remains: {retired.relative_to(ROOT)}")

    windows_transport = (winforms / "CliProcessClient.cs").read_text(encoding="utf-8")
    windows_form = (winforms / "MainForm.cs").read_text(encoding="utf-8")
    for anchor in (
        "class CliProcessClient",
        "ArgumentList",
        "ReadToEndAsync()",
        "Task.WhenAny(",
        "CancellationToken",
        "frontend_backend_timeout",
        "frontend_backend_cancelled",
        "JavaScriptSerializer",
    ):
        if anchor not in windows_transport:
            problems.append(f"WinForms CLI process transport missing: {anchor}")
    if "StandardOutput.ReadToEnd()" in windows_transport or "StandardError.ReadToEnd()" in windows_transport:
        problems.append("WinForms transport retains sequential blocking pipe reads")
    if "async void RunCommand" not in windows_form or "await commandClient.ExecuteAsync(" not in windows_form:
        problems.append("WinForms command execution can block the UI thread")

    appkit_transport = (appkit / "CliProcessClient.mm").read_text(encoding="utf-8")
    appkit_window = (appkit / "MainWindowController.m").read_text(encoding="utf-8")
    for anchor in (
        "FacManCliProcessClient",
        "dispatch_group_async(",
        "setTerminationHandler:",
        "dispatch_after(",
        "NSJSONSerialization",
        "frontend_backend_timeout",
    ):
        if anchor not in appkit_transport:
            problems.append(f"AppKit CLI process transport missing: {anchor}")
    if "waitUntilExit" in appkit_transport:
        problems.append("AppKit transport waits before draining pipes")
    if "completion:^(FacManCommandResult *result)" not in appkit_window:
        problems.append("AppKit window does not render command completion asynchronously")

    cmake = (ROOT / "cmake/FacManOptions.cmake").read_text(encoding="utf-8")
    apps_cmake = (ROOT / "apps/CMakeLists.txt").read_text(encoding="utf-8")
    default_off = (
        "set(_facman_tui_default OFF)" in cmake
        and "set(_facman_daemon_default OFF)" in cmake
        and 'option(FACMAN_BUILD_TUI "Build the experimental TUI" ${_facman_tui_default})' in cmake
        and 'option(FACMAN_BUILD_DAEMON "Build the experimental daemon" ${_facman_daemon_default})' in cmake
    )
    if not default_off:
        problems.append("experimental frontend build option is not default-off")
    if "if(FACMAN_BUILD_TUI)" not in apps_cmake or "if(FACMAN_BUILD_DAEMON)" not in apps_cmake:
        problems.append("TUI and daemon targets are not guarded as experiments")

    for relative in (
        "release/profiles/windows_legacy_winforms_x64/profile.toml",
        "release/profiles/macos_legacy_appkit_x64/profile.toml",
    ):
        profile = load_toml(relative)
        entrypoints = profile.get("entrypoints", {})
        if "tui" in entrypoints or "daemon" in entrypoints:
            problems.append(f"{relative} claims experimental TUI or daemon entrypoints")
    appkit_profile = load_toml("release/profiles/macos_legacy_appkit_x64/profile.toml")
    if appkit_profile.get("runtime_claim") != "compile_only_no_bundle_runtime_proof":
        problems.append("AppKit profile overclaims runtime proof")
    tui_profile = load_toml("release/profiles/portable_tui_x64/profile.toml")
    if tui_profile.get("publication") is not False or tui_profile.get("required_cmake_option") != "FACMAN_BUILD_EXPERIMENTAL_FRONTENDS=ON":
        problems.append("portable TUI profile is not explicitly opt-in and unpublished")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"frontend-transport-truth-check: {problem}", file=sys.stderr)
        return 1
    print("frontend-transport-truth-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
