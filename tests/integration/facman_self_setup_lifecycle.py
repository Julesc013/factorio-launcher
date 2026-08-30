#!/usr/bin/env python3
"""Exercise the real FacManSetup/USK lifecycle against a stored fixture payload."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path


def invoke(executable: Path, *arguments: object, expected: int = 0) -> dict[str, object]:
    command = [str(executable), *(str(value) for value in arguments), "--json"]
    result = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != expected:
        raise AssertionError(
            f"command returned {result.returncode}, expected {expected}: {command}\n"
            f"stdout={result.stdout[-8000:]}\nstderr={result.stderr[-8000:]}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"command did not return JSON: {command}\n{result.stdout[-8000:]}") from exc


def stored_payload(path: Path, executable: Path, version: str) -> None:
    files = {
        f"facman/generations/{version}/bin/facman.exe": b"synthetic-cli-v1\n",
        f"facman/generations/{version}/bin/FacMan.WinForms.exe": b"synthetic-gui-v1\n",
        "facman/maintenance/FacManSetup.exe": executable.read_bytes(),
        "facman/state/current-generation.v1.json": (
            json.dumps(
                {
                    "schema": "facman.current_generation.v1",
                    "version": version,
                    "workspace_preserved": True,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8"),
    }
    with zipfile.ZipFile(path, "w", allowZip64=True) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup-exe", type=Path, required=True)
    parser.add_argument(
        "--payload",
        type=Path,
        help="Exercise an exact produced self-setup payload instead of the synthetic fixture.",
    )
    args = parser.parse_args()
    executable = args.setup_exe.resolve(strict=True)
    version = subprocess.run(
        [str(executable), "--version"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()
    if not version.startswith("0.1.0-"):
        raise AssertionError(f"unexpected setup version: {version}")

    with tempfile.TemporaryDirectory(prefix="facman-self-setup-") as temporary:
        root = Path(temporary)
        programs = root / "Programs"
        programs.mkdir()
        install = programs / "FacMan"
        state = root / "SetupState"
        if args.payload is None:
            package = root / "setup-payload.zip"
            stored_payload(package, executable, version)
        else:
            package = args.payload.resolve(strict=True)

        plan = invoke(
            executable, "install", "--package", package, "--root", install,
            "--state-root", state, "--acceptance-root", root,
        )
        if plan.get("phase") != "plan" or install.exists():
            raise AssertionError("install preview changed the target or returned the wrong phase")

        installed = invoke(
            executable, "install", "--package", package, "--root", install,
            "--state-root", state, "--acceptance-root", root, "--yes",
        )
        if installed.get("phase") != "receipt":
            raise AssertionError("install did not return a receipt")
        gui = install / "generations" / version / "bin" / "FacMan.WinForms.exe"
        if not gui.is_file() or not (install / "maintenance/FacManSetup.exe").is_file():
            raise AssertionError("versioned generation or maintenance shell is missing")

        verified = invoke(
            executable, "verify", "--root", install, "--state-root", state,
            "--acceptance-root", root,
        )
        if verified["provider"]["payload"]["status"] != "pass":
            raise AssertionError("fresh install did not verify")

        gui.write_bytes(b"deliberate damage\n")
        damaged = invoke(
            executable, "verify", "--root", install, "--state-root", state,
            "--acceptance-root", root,
        )
        if damaged["provider"]["payload"]["status"] != "fail":
            raise AssertionError("owned-file damage was not detected")

        repaired = invoke(
            executable, "repair", "--package", package, "--root", install,
            "--state-root", state, "--acceptance-root", root, "--yes",
        )
        if repaired["provider"]["payload"]["status"] != "completed":
            raise AssertionError("repair did not complete")
        restored = invoke(
            executable, "verify", "--root", install, "--state-root", state,
            "--acceptance-root", root,
        )
        if restored["provider"]["payload"]["status"] != "pass":
            raise AssertionError("repair did not restore the exact closure")

        workspace = root / "FacManWorkspace"
        workspace.mkdir()
        keep = workspace / "keep.txt"
        keep.write_text("preserve\n", encoding="utf-8")
        unknown = install / "operator-note.txt"
        unknown.write_text("retain\n", encoding="utf-8")
        refusal = invoke(
            executable, "uninstall", "--root", install, "--state-root", state,
            "--acceptance-root", root, "--yes", expected=4,
        )
        if refusal.get("status") != "error" or not unknown.is_file() or not keep.is_file():
            raise AssertionError("foreign-content uninstall refusal did not preserve data")
        unknown.unlink()

        removed = invoke(
            executable, "uninstall", "--root", install, "--state-root", state,
            "--acceptance-root", root, "--yes",
        )
        if removed["provider"]["payload"]["status"] != "completed":
            raise AssertionError("clean uninstall did not complete")
        if install.exists() or not keep.is_file() or not state.is_dir():
            raise AssertionError("uninstall scope was not ownership bounded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
