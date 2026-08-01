# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the bounded WinForms C1 shell, semantics, and ZIP prototype."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import build_winforms_c1_portable, facman_presentation_check

WINFORMS = ROOT / "apps/gui/windows/winforms"
PROJECT = WINFORMS / "FacMan.WinForms.csproj"
SHELL = WINFORMS / "C1ShellForm.cs"
PRESENTATION = WINFORMS / "C1Presentation.cs"
PROGRAM = WINFORMS / "Program.cs"
MANIFEST = WINFORMS / "app.manifest"


def validate() -> list[str]:
    problems: list[str] = []
    required = [PROJECT, SHELL, PRESENTATION, PROGRAM, MANIFEST]
    for path in required:
        if not path.is_file():
            problems.append(f"missing WinForms C1 source: {path.relative_to(ROOT)}")
    if problems:
        return problems

    project = PROJECT.read_text(encoding="utf-8")
    shell = SHELL.read_text(encoding="utf-8")
    presentation = PRESENTATION.read_text(encoding="utf-8")
    program = PROGRAM.read_text(encoding="utf-8")
    manifest = MANIFEST.read_text(encoding="utf-8")

    for anchor in (
        "<TargetFrameworkVersion>v4.8</TargetFrameworkVersion>",
        "<PlatformTarget>x64</PlatformTarget>",
        "<Prefer32Bit>false</Prefer32Bit>",
        "<ApplicationManifest>app.manifest</ApplicationManifest>",
        '<Compile Include="C1Presentation.cs" />',
        '<Compile Include="C1ShellForm.cs" />',
    ):
        if anchor not in project:
            problems.append(f"WinForms project missing C1 anchor: {anchor}")
    for state in facman_presentation_check.EXPECTED_STATES:
        resource = f"FacMan.WinForms.Fixtures.{state}.json"
        if resource not in project:
            problems.append(f"WinForms does not embed/load fixture state: {state}")
    if '"FacMan.WinForms.Fixtures." + state + ".json"' not in presentation:
        problems.append("WinForms presentation store does not load named embedded fixture resources")

    if "Application.Run(new C1ShellForm())" not in program:
        problems.append("C1 product shell is not the WinForms entrypoint")
    for page in ("Instances", "Installations", "Activity", "Settings / About"):
        if f'Page("{page}"' not in shell:
            problems.append(f"C1 product page is missing: {page}")
    if 'Page("Advanced"' not in shell or "new MainForm()" not in shell:
        problems.append("generated command explorer is not retained under Advanced")

    required_shell_anchors = (
        "Persistent Launch Deck",
        "stale_readiness",
        "Last Run",
        "recovery.apply",
        "activity.show_operation",
        "AutoScaleMode.Dpi",
        "AccessibleName",
        "AccessibleDescription",
        "AccessibilityNotifyClients",
        "Keys.Control | Keys.D1",
        '"&Play"',
        "SystemColors.Info",
        "SystemFonts.MessageBoxFont",
        "no live Play authority",
    )
    for anchor in required_shell_anchors:
        if anchor not in shell:
            problems.append(f"WinForms C1 shell missing semantic/accessibility anchor: {anchor}")
    for forbidden in (
        "Process.Start",
        "CreateProcess",
        "System.Diagnostics",
        "NamedPipe",
        "HttpClient",
        "DllImport",
    ):
        if forbidden in shell + presentation:
            problems.append(f"C1 presentation layer contains forbidden runtime/transport marker: {forbidden}")

    if "PerMonitorV2" not in manifest or "asInvoker" not in manifest:
        problems.append("WinForms manifest lacks per-monitor DPI or least-privilege identity")
    if "System.Windows.Forms" in presentation:
        problems.append("facman.presentation.v0 adapter contains toolkit types")
    if "facman.presentation.v0" not in presentation:
        problems.append("WinForms adapter does not bind the FacMan-local presentation contract")

    for state in facman_presentation_check.EXPECTED_STATES:
        snapshot = facman_presentation_check.load_json(
            facman_presentation_check.FIXTURE_ROOT / f"{state}.facman.presentation.v0.json"
        )
        problems.extend(facman_presentation_check.validate_snapshot(snapshot, state))

    problems.extend(validate_prototype_builder())
    if not (ROOT / "tools/winforms_c1_runtime_smoke.py").is_file():
        problems.append("WinForms C1 executable renderer smoke is missing")
    return problems


def validate_prototype_builder() -> list[str]:
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as raw:
        root = Path(raw)
        executable = root / "FacMan.WinForms.exe"
        executable.write_bytes(b"deterministic-winforms-fixture")
        first = build_winforms_c1_portable.build(executable, root / "first.zip")
        second = build_winforms_c1_portable.build(executable, root / "second.zip")
        if first.read_bytes() != second.read_bytes():
            problems.append("WinForms C1 prototype ZIP is not deterministic")
        with zipfile.ZipFile(first) as archive:
            names = set(archive.namelist())
            expected = {
                "bin/FacMan.WinForms.exe",
                "PROTOTYPE-NOTICE.txt",
                "manifest/facman.winforms-c1-prototype.v0.json",
            }
            if names != expected:
                problems.append(f"WinForms C1 prototype ZIP entries differ: {sorted(names)}")
            manifest = json.loads(archive.read("manifest/facman.winforms-c1-prototype.v0.json"))
            if manifest.get("live_play_authority") is not False:
                problems.append("WinForms C1 prototype incorrectly grants live Play authority")
            digest = hashlib.sha256(archive.read("bin/FacMan.WinForms.exe")).hexdigest()
            if manifest.get("files", {}).get("bin/FacMan.WinForms.exe") != digest:
                problems.append("WinForms C1 prototype executable digest is stale")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"facman-winforms-c1-check: {problem}", file=sys.stderr)
        return 1
    print("facman-winforms-c1-check: ok (5 states, x64 DPI shell, deterministic portable ZIP)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
