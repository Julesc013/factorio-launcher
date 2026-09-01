# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Build the Windows GUI into the marker-owned development task root."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]


def msbuild_executable() -> str:
    discovered = shutil.which("msbuild")
    if discovered:
        return discovered
    candidates: list[Path] = []
    for variable in ("ProgramFiles", "ProgramFiles(x86)"):
        root = os.environ.get(variable, "").strip()
        if root:
            candidates.extend(
                Path(root).glob(
                    "Microsoft Visual Studio/*/*/MSBuild/Current/Bin/MSBuild.exe"
                )
            )
    if not candidates:
        raise ValueError("MSBuild could not be located for the WinForms product build")
    return str(sorted(candidates)[-1])


def build(task_root: Path, runner: Callable[[list[str]], None]) -> Path:
    product_root = task_root.resolve() / "winforms-product"
    output = product_root / "Release"
    intermediate = product_root / "obj" / "Release"
    output.mkdir(parents=True, exist_ok=True)
    intermediate.mkdir(parents=True, exist_ok=True)
    runner(
        [
            msbuild_executable(),
            str(ROOT / "apps/gui/windows/winforms/FacMan.WinForms.csproj"),
            "/p:Configuration=Release",
            "/p:Platform=x64",
            f"/p:OutputPath={output}{os.sep}",
            f"/p:IntermediateOutputPath={intermediate}{os.sep}",
        ]
    )
    executable = output / "FacMan.exe"
    if not executable.is_file():
        raise ValueError(f"WinForms product build did not create {executable}")
    return output
