#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Exercise the real FacManSetup/USK lifecycle against a stored fixture payload."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import struct
import json
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CALL_EVIDENCE: Path | None = None
CALL_COUNT = 0


def invoke(executable: Path, *arguments: object, expected: int = 0) -> dict[str, object]:
    command = [
        str(executable),
        *(str(value) for value in arguments),
        "--no-shell-integration",
        "--json",
    ]
    result = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8")
    global CALL_COUNT
    if CALL_EVIDENCE is not None:
        CALL_COUNT += 1
        prefix = CALL_EVIDENCE / f"{CALL_COUNT:03d}"
        prefix.with_suffix(".stdout").write_text(result.stdout, encoding="utf-8")
        prefix.with_suffix(".stderr").write_text(result.stderr, encoding="utf-8")
        prefix.with_suffix(".json").write_text(json.dumps(
            {"command": command, "exit_code": result.returncode}, indent=2) + "\n", encoding="utf-8")
    if result.returncode != expected:
        raise AssertionError(
            f"command returned {result.returncode}, expected {expected}: {command}\n"
            f"stdout={result.stdout[-8000:]}\nstderr={result.stderr[-8000:]}"
        )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(f"command did not return JSON: {command}\n{result.stdout[-8000:]}") from exc


def stored_payload(path: Path, executable: Path, version: str, compression: int = zipfile.ZIP_STORED) -> None:
    files = {
        f"facman/generations/{version}/bin/facman.exe": b"synthetic-cli-v1\n",
        f"facman/generations/{version}/FacMan.exe": b"synthetic-gui-v1\n",
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
            info.compress_type = compression
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)


def damaged_archive_controls(root: Path, executable: Path, package: Path) -> None:
    """Exercise a consistent but wrong CRC and a truncated archive via real apply."""
    original = package.read_bytes()
    crc_bytes = bytearray(original)
    with zipfile.ZipFile(package) as archive:
        first = archive.infolist()[0]
        local = first.header_offset
        central = archive.start_dir
    # Both header records agree; decoded payload integrity must detect this.
    wrong_crc = first.CRC ^ 1
    struct.pack_into("<I", crc_bytes, local + 14, wrong_crc)
    struct.pack_into("<I", crc_bytes, central + 16, wrong_crc)
    for name, raw in (("bad-crc", bytes(crc_bytes)), ("truncated", original[:-8])):
        case = root / name
        case.mkdir()
        broken = case / "payload.zip"
        broken.write_bytes(raw)
        sentinel = case / "foreign.txt"
        sentinel.write_bytes(b"preserve foreign fixture bytes\n")
        target, state = case / "target", case / "state"
        response = invoke(executable, "install", "--package", broken, "--root", target,
                          "--state-root", state, "--acceptance-root", case, "--yes", expected=4)
        error = response.get("error", {})
        if name == "bad-crc":
            detail = json.loads(error.get("detail", "{}"))
            if (error.get("code") != "self_setup_provider_refused" or
                    detail.get("error", {}).get("code") != "lifecycle_refused" or
                    "CRC" not in detail.get("error", {}).get("message", "")):
                raise AssertionError("CRC fixture did not reach the provider payload-integrity refusal")
        elif error.get("code") != "self_setup_payload_invalid":
            raise AssertionError("truncation fixture did not reach the FacMan payload refusal")
        if (response.get("status") != "error" or target.exists() or
                sentinel.read_bytes() != b"preserve foreign fixture bytes\n" or
                broken.read_bytes() != raw or package.read_bytes() != original):
            raise AssertionError("damaged archive refusal changed foreign input or published target")
        inventory = [{"path": p.relative_to(case).as_posix(),
                      "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                     for p in sorted(case.rglob("*")) if p.is_file()]
        (case / "refusal-effects.json").write_text(json.dumps(
            {"response": response, "target_exists": False, "files": inventory}, indent=2) + "\n",
            encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup-exe", type=Path, required=True)
    parser.add_argument(
        "--payload",
        type=Path,
        help="Exercise an exact produced self-setup payload instead of the synthetic fixture.",
    )
    parser.add_argument(
        "--workspace-lifecycle-evidence",
        type=Path,
        help="Also qualify the exact installed CLI workspace lifecycle and write its receipt.",
    )
    parser.add_argument(
        "--resource-package-evidence",
        type=Path,
        help="Qualify the exact installed CLI resources before damage and uninstall.",
    )
    parser.add_argument("--compression", choices=("stored", "deflate"), default="stored")
    parser.add_argument("--fixture-root", type=Path,
                        help="New disposable fixture path; retain all effects including failed runs.")
    args = parser.parse_args()
    if args.payload is not None and args.compression != "stored":
        parser.error("--compression applies only to synthetic fixtures")
    if args.fixture_root is not None:
        if not args.fixture_root.is_absolute() or args.fixture_root.exists():
            parser.error("--fixture-root must be an absent absolute disposable path")
        args.fixture_root.mkdir(parents=False)
        global CALL_EVIDENCE
        CALL_EVIDENCE = args.fixture_root / "calls"
        CALL_EVIDENCE.mkdir()

    if args.resource_package_evidence is not None and args.payload is None:
        parser.error("--resource-package-evidence requires --payload")
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

    fixture = (contextlib.nullcontext(str(args.fixture_root)) if args.fixture_root is not None
               else tempfile.TemporaryDirectory(prefix="facman-self-setup-"))
    with fixture as temporary:
        root = Path(temporary)
        programs = root / "Programs"
        programs.mkdir()
        install = programs / "FacMan"
        state = root / "SetupState"
        if args.payload is None:
            package = root / "setup-payload.zip"
            stored_payload(package, executable, version,
                           zipfile.ZIP_DEFLATED if args.compression == "deflate" else zipfile.ZIP_STORED)
        else:
            package = args.payload.resolve(strict=True)

        if args.fixture_root is not None and args.payload is None:
            damaged_archive_controls(root, executable, package)

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
        gui = install / "generations" / version / "FacMan.exe"
        if not gui.is_file() or not (install / "maintenance/FacManSetup.exe").is_file():
            raise AssertionError("versioned generation or maintenance shell is missing")

        verified = invoke(
            executable, "verify", "--root", install, "--state-root", state,
            "--acceptance-root", root,
        )
        if verified["provider"]["payload"]["status"] != "pass":
            raise AssertionError("fresh install did not verify")

        if args.workspace_lifecycle_evidence is not None:
            if args.payload is None:
                raise AssertionError(
                    "installed workspace lifecycle proof requires an exact produced payload"
                )
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/workspace_lifecycle_package_proof.py"),
                    "--executable", str(install / "generations" / version / "bin/facman.exe"),
                    "--profile", "windows_product_x64",
                    "--package-mode", "installed_stage",
                    "--evidence", str(args.workspace_lifecycle_evidence),
                ],
                cwd=ROOT,
                check=True,
            )

        if args.resource_package_evidence is not None:
            if args.payload is None:
                raise AssertionError("installed resource proof requires an exact produced payload")
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/resource_package_proof.py"),
                    "--executable", str(install / "generations" / version / "bin/facman.exe"),
                    "--profile", "windows_product_x64",
                    "--package-mode", "installed_stage",
                    "--evidence", str(args.resource_package_evidence),
                ],
                cwd=ROOT,
                check=True,
            )

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
