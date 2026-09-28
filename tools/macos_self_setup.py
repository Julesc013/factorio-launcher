#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Build the unsigned self-contained macOS FacMan installer package."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLED_APP = "/Applications/FacMan.app"
INTERNAL_TERMINAL = "Contents/Helpers/facman"
PUBLIC_TERMINAL = "/usr/local/bin/facman"
PACKAGE_IDENTIFIER = "io.github.julesc013.facman"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def version_truth() -> dict[str, object]:
    with (ROOT / "release/index/version.v2.toml").open("rb") as stream:
        return tomllib.load(stream)


def native_package_version(semver: str, package_revision: str) -> str:
    """Map the allocated SemVer train to an ordered numeric Installer version.

    Installer compares packages by identifier and package version, while
    prerelease SemVer is retained in the artifact name and evidence. The last
    numeric component reserves decimal places for phase, train number, and
    package revision, so later phases and patch releases sort after earlier ones.
    """
    match = re.fullmatch(
        r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
        r"(?:-(alpha|beta|rc)\.(0|[1-9]\d*))?"
        r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?",
        semver,
    )
    if match is None or re.fullmatch(r"0|[1-9]\d*", package_revision) is None:
        raise ValueError("macOS package version requires allocated SemVer and numeric package revision")
    major, minor, patch, phase, serial = match.groups()
    number = int(serial or 0)
    revision = int(package_revision)
    if number > 99 or revision > 99:
        raise ValueError("macOS package version train or package revision exceeds reserved range")
    phase_rank = {"alpha": 1, "beta": 2, "rc": 3, None: 4}[phase]
    native_patch = int(patch) * 100000 + phase_rank * 10000 + number * 100 + revision
    return f"{major}.{minor}.{native_patch}"


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


def verify_native_package_info(package_info: Path, package_version: str) -> None:
    actual = ET.parse(package_info).getroot()
    if (
        actual.tag != "pkg-info"
        or actual.attrib.get("identifier") != PACKAGE_IDENTIFIER
        or actual.attrib.get("version") != package_version
    ):
        raise ValueError("macOS Installer package identity differs from canonical version truth")


def build(app: Path, output: Path, evidence: Path) -> dict[str, object]:
    app = app.resolve(strict=True)
    version_record = version_truth()
    version = str(version_record["semver"])
    package_version = native_package_version(version, str(version_record["package_revision"]))
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
        try:
            subprocess.run(
                [
                    "pkgbuild",
                    "--root", str(payload),
                    "--identifier", PACKAGE_IDENTIFIER,
                    "--version", package_version,
                    "--install-location", "/",
                    str(package),
                ],
                check=True,
            )
            subprocess.run(
                ["xar", "-x", "-f", str(package.resolve()), "PackageInfo"],
                cwd=temporary,
                check=True,
            )
            verify_native_package_info(Path(temporary) / "PackageInfo", package_version)
        except Exception:
            package.unlink(missing_ok=True)
            raise
    record = {
        "schema": "facman.macos_self_setup.v1",
        "status": "pass",
        "version": version,
        "package_version": package_version,
        "platform": "macos",
        "architecture": "x64",
        "source_revision": git("rev-parse", "HEAD"),
        "source_tree": git("rev-parse", "HEAD^{tree}"),
        "runtime_stage": {"app_digest": app_digest(app)},
        "setup": {
            "filename": package.name,
            "identifier": PACKAGE_IDENTIFIER,
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


def verify_package_info(package_info: Path, evidence: Path) -> None:
    record = json.loads(evidence.read_text(encoding="utf-8"))
    version = version_truth()
    expected = native_package_version(str(version["semver"]), str(version["package_revision"]))
    if (
        record.get("schema") != "facman.macos_self_setup.v1"
        or record.get("version") != version["semver"]
        or record.get("package_version") != expected
        or not isinstance(record.get("setup"), dict)
        or record["setup"].get("identifier") != PACKAGE_IDENTIFIER
    ):
        raise ValueError("macOS setup evidence differs from canonical version truth")
    verify_native_package_info(package_info, expected)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--verify-package-info", type=Path)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    if args.verify_package_info is not None:
        if args.evidence is None:
            parser.error("--verify-package-info requires --evidence")
        verify_package_info(args.verify_package_info, args.evidence)
        print("macOS Installer package version verified")
        return 0
    if args.app is None or args.out is None or args.evidence is None:
        parser.error("building macOS setup requires --app, --out and --evidence")
    if git("status", "--porcelain") and not args.allow_dirty:
        raise SystemExit("refusing macOS setup from a dirty source tree")
    record = build(args.app, args.out.resolve(), args.evidence.resolve())
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
