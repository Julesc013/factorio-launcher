# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Build and exercise the production WinForms gallery in an owned task root."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import control_gallery_fixtures, development_layout, winforms_build


def source_inputs() -> dict[str, str]:
    paths = list((ROOT / "apps/gui/windows/winforms").glob("*.cs"))
    paths += list((ROOT / "tests/winforms_control_gallery").glob("*"))
    paths += list((ROOT / "tests/fixtures/presentation").glob("*.facman.presentation.v0.json"))
    paths.append(ROOT / "apps/gui/windows/winforms/branding/FacMan.ico")
    paths += [ROOT / path for path in (
        "apps/gui/windows/winforms/FacMan.WinForms.csproj",
        "apps/gui/windows/winforms/app.manifest",
        "apps/gui/windows/winforms/provider_identity.tracked.v1.txt",
        "tools/control_gallery_fixtures.py", "tools/native_control_gallery.py",
        "tools/winforms_build.py", "tests/golden/commands/presentation.query.success.json",
        "contracts/schema/presentation/presentation_snapshot.v1.schema.json",
    )]
    return {path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(paths) if path.is_file()}


def run(task_root: Path, *, show: str | None = None) -> dict:
    if os.name != "nt":
        raise ValueError("The WinForms gallery requires a Windows host; GTK remains pending.")
    task_root = development_layout.ensure_task_root(
        task_root, ROOT, development_layout.current_task_id(ROOT)
    )
    gallery_root = task_root / "control-gallery"
    gallery_root.mkdir(exist_ok=True)
    log = gallery_root / "build.log"
    source = source_inputs()
    attempt = gallery_root / "runs" / uuid.uuid4().hex
    attempt.mkdir(parents=True)

    def command(args: list[str]) -> None:
        result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, check=False,
                                timeout=None if show else 120)
        with log.open("a", encoding="utf-8") as stream:
            stream.write(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(f"Gallery command failed ({result.returncode}); see {log}")

    product = winforms_build.build(task_root, command)
    binary_root = gallery_root / "bin"
    command([
        winforms_build.msbuild_executable(),
        str(ROOT / "tests/winforms_control_gallery/FacMan.ControlGallery.csproj"),
        "/p:Configuration=Release", "/p:Platform=x64",
        f"/p:FacManProductAssembly={product / 'FacMan.exe'}",
        f"/p:OutputPath={binary_root}{os.sep}",
        f"/p:IntermediateOutputPath={gallery_root / 'obj'}{os.sep}",
    ])
    fixtures = attempt / "fixtures"
    fixtures.mkdir(exist_ok=True)
    hashes = {}
    for name, case in control_gallery_fixtures.cases().items():
        payload = (json.dumps(case, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        (fixtures / f"{name}.json").write_bytes(payload)
        hashes[name] = hashlib.sha256(payload).hexdigest()
    executable = binary_root / "FacMan.ControlGallery.exe"
    if show is not None:
        if show not in hashes:
            raise ValueError("Unknown gallery scenario: " + show)
        command([str(executable), "--show", str(fixtures / f"{show}.json")])
        return {"mode": "interactive", "scenario": show}
    command([str(executable), "--check", str(fixtures), str(attempt / "evidence")])
    if source != source_inputs():
        raise RuntimeError("Gallery source changed during validation; this attempt cannot qualify it.")
    receipt = json.loads((attempt / "evidence/control-gallery.v1.json").read_text(encoding="utf-8"))
    receipt["source_files"] = source
    receipt["fixture_sha256"] = hashes
    receipt["product_sha256"] = hashlib.sha256((product / "FacMan.exe").read_bytes()).hexdigest()
    receipt["source_head"] = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    receipt["source_dirty"] = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip())
    (attempt / "evidence/validation.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"gallery receipt: {attempt / 'evidence/validation.json'}")
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task-root", type=Path, default=development_layout.task_root(ROOT))
    parser.add_argument("--show", choices=tuple(control_gallery_fixtures.cases()))
    args = parser.parse_args()
    try:
        result = run(args.task_root, show=args.show)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"native-control-gallery: {error}", file=sys.stderr)
        return 1
    print("native-control-gallery: " + (result.get("result") or result["mode"]))
    if "assertions" in result:
        print(f"assertions: {result['assertions']}; render cells: {len(result['rows'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
