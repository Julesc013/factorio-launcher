# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Run the production identity harness using retained external task outputs."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import tomllib
import uuid
from tools import development_layout
from tools.winforms_build import msbuild_executable

ROOT = Path(__file__).resolve().parents[1]


def run(package: Path, work: Path | None = None) -> int:
    if os.name != "nt":
        print("winforms-backend-identity-check: runtime unsupported on this host (Windows only)")
        return 0
    package = package.resolve(strict=True)
    origin = work.resolve() if work is not None else package
    task = next((p for p in (origin, *origin.parents)
                 if (p / development_layout.MARKER_NAME).is_file()), None)
    if task is None:
        raise ValueError("identity harness requires an existing marker-owned external task root")
    development_layout.read_marker(task, ROOT)
    work = work.resolve() if work is not None else task / "identity-harness" / uuid.uuid4().hex
    if not work.is_relative_to(task) or work == task or work.exists():
        raise ValueError("identity harness output must be a fresh child of the owned task root")
    with (package / "manifest/package.v1.toml").open("rb") as stream:
        profile = tomllib.load(stream)["profile_id"]
    frontend = package / ("FacMan.exe" if profile == "windows_product_x64" else "bin/FacMan.WinForms.exe")
    if not frontend.is_file():
        raise ValueError("the declared Windows profile frontend is missing")
    work.mkdir(parents=True)
    temporary = task / "t"
    temporary.mkdir(exist_ok=True)
    env = dict(os.environ, TEMP=str(temporary), TMP=str(temporary), PYTHONDONTWRITEBYTECODE="1")
    output, intermediate = work / "bin", work / "obj"
    output.mkdir()
    project = ROOT / "tests/winforms_backend_identity_harness/FacMan.BackendIdentity.Harness.csproj"
    commands = [
        ("build", [msbuild_executable(), str(project), "/t:Rebuild", "/p:Configuration=Release",
                   "/p:Platform=x64", "/warnaserror", "/nologo", "/verbosity:minimal", "/m:1",
                   "/p:UseSharedCompilation=false", f"/p:OutputPath={output}{os.sep}",
                   f"/p:IntermediateOutputPath={intermediate}{os.sep}"], 120),
        ("identity", [str(output / "FacMan.BackendIdentity.Harness.exe"),
                      str(frontend), str(package)], 180),
    ]
    rows: list[dict[str, object]] = []
    for name, argv, budget in commands:
        stdout, stderr = work / (name + ".stdout"), work / (name + ".stderr")
        start = time.monotonic()
        timed_out = False
        with stdout.open("xb") as out, stderr.open("xb") as err:
            try:
                result = subprocess.run(argv, cwd=ROOT, env=env, stdout=out, stderr=err, timeout=budget)
                code = result.returncode
            except subprocess.TimeoutExpired:
                code, timed_out = 1, True
        row = {"command": argv, "exit_code": code, "timed_out": timed_out,
               "seconds": time.monotonic() - start,
               "logs": [{"path": p.name, "bytes": p.stat().st_size,
                         "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                        for p in (stdout, stderr)]}
        rows.append(row)
        (work / "commands.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
        print(f"winforms-backend-identity-check: {name} exit={code}; retained {work}")
        if code:
            return code
    return 0
