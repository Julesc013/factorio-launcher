#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Build the unsigned self-contained macOS FacMan installer package."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLED_APP = "/Applications/FacMan.app"
INTERNAL_TERMINAL = "Contents/Helpers/facman"
PUBLIC_TERMINAL = "/usr/local/bin/facman"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def version_truth() -> str:
    with (ROOT / "release/index/version.v2.toml").open("rb") as stream:
        return str(tomllib.load(stream)["semver"])


def git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def app_digest(app: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted((item for item in app.rglob("*") if item.is_file()), key=lambda item: item.relative_to(app).as_posix()):
        relative = path.relative_to(app).as_posix()
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(sha256(path).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def terminal_shim() -> str:
    return f'#!/bin/sh\nexec "{INSTALLED_APP}/{INTERNAL_TERMINAL}" "$@"\n'


def validate_app_payload(app: Path) -> None:
    required = (
        app / "Contents/MacOS/FacMan",
        app / INTERNAL_TERMINAL,
    )
    for path in required:
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"macOS setup input lacks a regular required executable: {path}")
    folded: dict[str, str] = {}
    for path in sorted(app.rglob("*"), key=lambda item: item.relative_to(app).as_posix()):
        if path.is_symlink():
            raise ValueError(f"macOS setup input contains a symbolic link: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(app).as_posix()
        key = relative.casefold()
        if key in folded:
            raise ValueError(
                f"macOS setup input contains a case-fold collision: {folded[key]} and {relative}"
            )
        folded[key] = relative


def build(app: Path, output: Path, evidence: Path) -> dict[str, object]:
    app = app.resolve(strict=True)
    version = version_truth()
    if app.name != "FacMan.app":
        raise ValueError("macOS setup input must be the canonical FacMan.app")
    validate_app_payload(app)
    output.mkdir(parents=True, exist_ok=True)
    package = output / f"FacMan-{version}-macos-x64-setup.pkg"
    package.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="facman-macos-setup-") as temporary:
        payload = Path(temporary) / "payload"
        applications = payload / "Applications"
        applications.mkdir(parents=True)
        shutil.copytree(app, applications / "FacMan.app", symlinks=False)
        shim = payload / "usr/local/bin/facman"
        shim.parent.mkdir(parents=True)
        shim.write_text(
            terminal_shim(),
            encoding="utf-8",
            newline="\n",
        )
        shim.chmod(0o755)
        subprocess.run(
            [
                "pkgbuild",
                "--root", str(payload),
                "--identifier", "io.github.julesc013.facman",
                "--version", "0.1.0",
                "--install-location", "/",
                str(package),
            ],
            check=True,
        )
    record = {
        "schema": "facman.macos_self_setup.v1",
        "status": "pass",
        "version": version,
        "platform": "macos",
        "architecture": "x64",
        "source_revision": git("rev-parse", "HEAD"),
        "source_tree": git("rev-parse", "HEAD^{tree}"),
        "runtime_stage": {"app_digest": app_digest(app)},
        "setup": {
            "filename": package.name,
            "bytes": package.stat().st_size,
            "sha256": sha256(package),
            "format": "pkg",
            "self_contained": True,
            "offline": True,
            "install_location": INSTALLED_APP,
            "terminal_command": PUBLIC_TERMINAL,
            "terminal_target": f"{INSTALLED_APP}/{INTERNAL_TERMINAL}",
        },
        "authority": {"signed": False, "notarized": False, "support": False},
    }
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    if git("status", "--porcelain") and not args.allow_dirty:
        raise SystemExit("refusing macOS setup from a dirty source tree")
    record = build(args.app, args.out.resolve(), args.evidence.resolve())
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
