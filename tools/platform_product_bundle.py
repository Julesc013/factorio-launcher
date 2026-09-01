#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Assemble the native macOS and Linux alpha product bundles."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import shutil
import stat
import subprocess
import tarfile
import tempfile
import tomllib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = ROOT / "release/index/version.v2.toml"
FORBIDDEN_PUBLIC_NAMES = {
    "FacMan.WinForms.exe",
    "FacMan.AppKit",
    "facman-gui-gtk",
    "facman-gui-qt",
    "facman-tui",
    "facman-tui.exe",
    "facmand",
    "facmand.exe",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def version_truth() -> str:
    with VERSION.open("rb") as stream:
        return str(tomllib.load(stream)["semver"])


def git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()


def copy_tree(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise ValueError(f"required package tree is missing: {source}")
    shutil.copytree(source, destination, dirs_exist_ok=True, symlinks=False)


def copy_file(source: Path, destination: Path, executable: bool = False) -> None:
    if not source.is_file() or source.is_symlink():
        raise ValueError(f"required package file is missing or linked: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    if executable:
        destination.chmod(destination.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def terminal_payload(terminal: Path, destination: Path) -> None:
    for name in ("licenses", "docs"):
        copy_tree(terminal / name, destination / name)
    resource_candidates = (
        terminal / "facman.resources",
        terminal / "share/facman/facman.resources",
    )
    resource = next((path for path in resource_candidates if path.is_file()), None)
    if resource is None:
        raise ValueError("terminal package is missing deterministic facman.resources")
    copy_file(resource, destination / "facman.resources")
    copy_tree(terminal / "manifest", destination / "manifest" / "terminal-package")


def file_inventory(root: Path) -> list[dict[str, object]]:
    records = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_symlink():
            raise ValueError(f"product stage contains a symbolic link: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if path.name in FORBIDDEN_PUBLIC_NAMES:
            raise ValueError(f"product stage exposes forbidden public entrypoint: {relative}")
        records.append({
            "path": relative,
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
            "mode": stat.S_IMODE(path.stat().st_mode),
        })
    return records


def inventory_digest(records: list[dict[str, object]]) -> str:
    encoded = json.dumps(records, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


def write_manifest(
    root: Path,
    manifest_root: Path,
    *,
    platform_id: str,
    version: str,
    gui: str,
    cli: str,
) -> dict[str, object]:
    manifest_root.mkdir(parents=True, exist_ok=True)
    records = file_inventory(root)
    record = {
        "schema": "facman.platform_product_stage.v1",
        "product_id": "facman",
        "product_name": "FacMan",
        "version": version,
        "platform": platform_id,
        "architecture": "x64",
        "source_revision": git("rev-parse", "HEAD"),
        "source_tree": git("rev-parse", "HEAD^{tree}"),
        "source_dirty": bool(git("status", "--porcelain")),
        "entrypoints": {"gui": gui, "cli": cli, "tui": cli},
        "terminal_modes": ["human_cli", "json", "rpc", "tui"],
        "provider_closure": "static_in_facman_terminal_host",
        "portable": True,
        "app_installation_mutation": False,
        "factorio_mutation": False,
        "signed": False,
        "notarized": False,
        "files": records,
        "stage_digest": inventory_digest(records),
    }
    path = manifest_root / "product-stage.v1.json"
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    closure = file_inventory(root)
    (manifest_root / "MANIFEST.sha256").write_text(
        "".join(f"{item['sha256']}  {item['path']}\n" for item in closure),
        encoding="utf-8",
        newline="\n",
    )
    return record


def source_epoch() -> int:
    return int(git("show", "-s", "--format=%ct", "HEAD"))


def deterministic_zip(root: Path, archive: Path) -> None:
    stamp = dt.datetime.fromtimestamp(max(source_epoch(), 315532800), tz=dt.timezone.utc)
    timestamp = (stamp.year, stamp.month, stamp.day, stamp.hour, stamp.minute, stamp.second)
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.relative_to(root).as_posix()):
            info = zipfile.ZipInfo(path.relative_to(root).as_posix(), timestamp)
            info.create_system = 3
            info.external_attr = stat.S_IMODE(path.stat().st_mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(info, path.read_bytes(), compresslevel=9)


def deterministic_tar_zst(root: Path, archive: Path) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="facman-alpha3-tar-") as temporary:
        raw = Path(temporary) / "product.tar"
        with tarfile.open(raw, "w", format=tarfile.PAX_FORMAT) as output:
            for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
                relative = path.relative_to(root).as_posix()
                info = output.gettarinfo(str(path), arcname=relative)
                info.uid = info.gid = 0
                info.uname = info.gname = "root"
                info.mtime = source_epoch()
                if path.is_file():
                    with path.open("rb") as stream:
                        output.addfile(info, stream)
                else:
                    output.addfile(info)
        subprocess.run(
            ["zstd", "-19", "--no-progress", "--force", str(raw), "-o", str(archive)],
            check=True,
        )


def build_macos(terminal: Path, gui: Path, stage: Path, dist: Path, evidence: Path) -> dict[str, object]:
    version = version_truth()
    if stage.exists():
        raise ValueError(f"stage must be new: {stage}")
    app = stage / "FacMan.app"
    copy_tree(gui, app)
    executable_root = app / "Contents/MacOS"
    copy_file(terminal / "bin/facman", executable_root / "facman", executable=True)
    resources = app / "Contents/Resources"
    terminal_payload(terminal, resources)
    manifest = write_manifest(
        app,
        resources / "manifest",
        platform_id="macos",
        version=version,
        gui="FacMan.app/Contents/MacOS/FacMan",
        cli="FacMan.app/Contents/MacOS/facman",
    )
    archive = dist / f"FacMan-{version}-macos-x64-portable.zip"
    deterministic_zip(stage, archive)
    return finish_evidence(manifest, archive, evidence, "macos_13_plus_intel_x64_experimental")


def build_linux(terminal: Path, gui: Path, stage: Path, dist: Path, evidence: Path) -> dict[str, object]:
    version = version_truth()
    if stage.exists():
        raise ValueError(f"stage must be new: {stage}")
    product = stage / f"FacMan-{version}"
    product.mkdir(parents=True)
    copy_file(gui, product / "FacMan", executable=True)
    copy_file(terminal / "bin/facman", product / "facman", executable=True)
    terminal_payload(terminal, product / "share/facman")
    desktop = product / "share/applications/facman.desktop"
    copy_file(ROOT / "apps/gui/linux/gtk/io.github.julesc013.facman.preview.desktop", desktop)
    icons = ROOT / "apps/gui/linux/gtk/icons/hicolor"
    copy_tree(icons, product / "share/icons/hicolor")
    manifest = write_manifest(
        product,
        product / "share/facman/manifest",
        platform_id="linux",
        version=version,
        gui="FacMan",
        cli="facman",
    )
    archive = dist / f"FacMan-{version}-linux-x64-portable.tar.zst"
    deterministic_tar_zst(stage, archive)
    return finish_evidence(manifest, archive, evidence, "ubuntu_24_04_x64_gtk3_x11_experimental")


def finish_evidence(
    manifest: dict[str, object], archive: Path, evidence: Path, claim: str
) -> dict[str, object]:
    record = {
        "schema": "facman.platform_product_package_proof.v1",
        "status": "pass",
        "platform": manifest["platform"],
        "version": manifest["version"],
        "claim": claim,
        "source_revision": manifest["source_revision"],
        "source_tree": manifest["source_tree"],
        "stage_digest": manifest["stage_digest"],
        "entrypoints": manifest["entrypoints"],
        "artifact": {
            "filename": archive.name,
            "bytes": archive.stat().st_size,
            "sha256": sha256(archive),
        },
        "authority": {
            "public_publication": False,
            "signing": False,
            "support": False,
            "factorio_execution": False,
        },
    }
    evidence.parent.mkdir(parents=True, exist_ok=True)
    evidence.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", choices=("macos", "linux"))
    parser.add_argument("--terminal-root", type=Path, required=True)
    parser.add_argument("--gui", type=Path, required=True)
    parser.add_argument("--stage", type=Path, required=True)
    parser.add_argument("--dist", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    dirty = bool(git("status", "--porcelain"))
    if dirty and not args.allow_dirty:
        raise SystemExit("refusing product package from a dirty source tree")
    function = build_macos if args.platform == "macos" else build_linux
    record = function(
        args.terminal_root.resolve(strict=True),
        args.gui.resolve(strict=True),
        args.stage.resolve(),
        args.dist.resolve(),
        args.evidence.resolve(),
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
