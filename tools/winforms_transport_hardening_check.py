# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Build and execute the dependency-minimal WinForms transport behavior matrix."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / "tests" / "winforms_transport_harness"
WINFORMS = ROOT / "apps" / "gui" / "windows" / "winforms"


def resolve_msbuild() -> str | None:
    for candidate in ("MSBuild.exe", "msbuild"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    enterprise = Path(
        r"C:\Program Files\Microsoft Visual Studio\2022\Enterprise\MSBuild\Current\Bin\MSBuild.exe"
    )
    return str(enterprise) if enterprise.is_file() else None


def source_check() -> list[str]:
    problems: list[str] = []
    required = {
        "CliProcessClient.cs": (
            "RequestWriteStartedDispatchUncertain",
            "frontend_backend_output_exhausted",
            "workspace.recovery.inspect",
        ),
        "TransportOptions.cs": (
            "DefaultMaximumRequestBytes",
            "DefaultMaximumStdoutBytes",
            "DefaultMaximumStderrBytes",
        ),
        "StrictTransportJson.cs": ("duplicate member", "trailing data"),
        "TransportResponseDecoder.cs": (
            "facman.transport_response.v2",
            "ulk.operation_outcome.v1",
        ),
        "WindowsContainedProcess.cs": (
            "CreateSuspended",
            "JobObjectLimitKillOnJobClose",
            "AssignProcessToJobObject",
        ),
    }
    for name, anchors in required.items():
        path = WINFORMS / name
        if not path.is_file():
            problems.append(f"missing WinForms transport source: {path.relative_to(ROOT)}")
            continue
        text = path.read_text(encoding="utf-8")
        for anchor in anchors:
            if anchor not in text:
                problems.append(f"{name} missing transport anchor: {anchor}")
    return problems


def build(msbuild: str, project: Path) -> None:
    completed = subprocess.run(
        [
            msbuild,
            str(project),
            "/t:Rebuild",
            "/p:Configuration=Release",
            "/p:Platform=AnyCPU",
            "/warnaserror",
            "/nologo",
            "/verbosity:minimal",
        ],
        cwd=HARNESS,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode:
        print(completed.stdout)
        print(completed.stderr, file=sys.stderr)
        raise RuntimeError(f"MSBuild failed for {project.name}")


def main() -> int:
    problems = source_check()
    if problems:
        for problem in problems:
            print(f"winforms-transport-hardening-check: {problem}", file=sys.stderr)
        return 1
    if os.name != "nt":
        print("winforms-transport-hardening-check: source contract pass; runtime skipped (Windows only)")
        return 0
    msbuild = resolve_msbuild()
    if msbuild is None:
        print("winforms-transport-hardening-check: MSBuild unavailable", file=sys.stderr)
        return 1
    try:
        fake_project = HARNESS / "FacMan.Transport.FakeBackend.csproj"
        harness_project = HARNESS / "FacMan.Transport.Harness.csproj"
        build(msbuild, fake_project)
        build(msbuild, harness_project)
        fake = HARNESS / "bin" / "FakeBackend" / "FacMan.Transport.FakeBackend.exe"
        harness = HARNESS / "bin" / "Harness" / "FacMan.Transport.Harness.exe"
        with tempfile.TemporaryDirectory(prefix="facman-transport-harness-") as temp:
            completed = subprocess.run(
                [str(harness), str(fake), temp],
                cwd=temp,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=180,
            )
        print(completed.stdout, end="")
        if completed.stderr:
            print(completed.stderr, file=sys.stderr, end="")
        return completed.returncode
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        print(f"winforms-transport-hardening-check: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
