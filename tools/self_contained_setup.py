#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Build the deterministic single-file Windows FacMan self-setup package."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
VERSION = ROOT / "release/index/version.v2.toml"
PROVIDERS = ROOT / "release/index/providers.lock.v2.toml"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
MAX_FILE_BYTES = 8 * 1024 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024 * 1024


@dataclass(frozen=True)
class Entry:
    path: str
    data: bytes


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_member(value: str) -> str:
    if not value or "\\" in value or value.startswith("/"):
        raise ValueError(f"unsafe ZIP member: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe ZIP member: {value!r}")
    return path.as_posix()


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def version_truth() -> str:
    with VERSION.open("rb") as stream:
        return str(tomllib.load(stream)["semver"])


def provider_revision() -> str:
    with PROVIDERS.open("rb") as stream:
        values = tomllib.load(stream)
    for provider in values.get("provider", []):
        if provider.get("id") == "universal_setup":
            return str(provider["source_revision"])
    raise ValueError("Universal Setup is absent from the provider lock")


def source_revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()


def source_dirty() -> bool:
    return bool(subprocess.run(
        ["git", "status", "--porcelain=v1"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip())


def portable_entries(path: Path) -> list[Entry]:
    entries: list[Entry] = []
    folded: set[str] = set()
    total = 0
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            name = safe_member(info.filename)
            key = name.casefold()
            if key in folded:
                raise ValueError(f"case-insensitive portable path collision: {name}")
            folded.add(key)
            if info.flag_bits & 0x1 or ((info.external_attr >> 16) & 0o170000) == 0o120000:
                raise ValueError(f"encrypted or linked portable member is forbidden: {name}")
            if info.file_size > MAX_FILE_BYTES:
                raise ValueError(f"portable member exceeds size budget: {name}")
            total += info.file_size
            if total > MAX_TOTAL_BYTES:
                raise ValueError("portable package exceeds setup size budget")
            entries.append(Entry(name, archive.read(info)))
    exact = {entry.path for entry in entries}
    if "FacMan.exe" not in exact or "bin/facman.exe" not in exact:
        raise ValueError(
            "portable package must expose FacMan.exe and bin/facman.exe"
        )
    return entries


def zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.flag_bits = 0x800
    # Universal Setup deliberately materializes only stored entries in the
    # public lifecycle path. The outer setup is still one file; preserving
    # stored members keeps extraction bounded and auditable by that provider.
    info.compress_type = zipfile.ZIP_STORED
    return info


def tree_digest(entries: list[Entry]) -> str:
    digest = hashlib.sha256()
    for entry in sorted(entries, key=lambda item: item.path.encode()):
        digest.update(entry.path.encode())
        digest.update(b"\0")
        digest.update(str(len(entry.data)).encode())
        digest.update(b"\0")
        digest.update(sha256_bytes(entry.data).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def build(
    portable: Path,
    bootstrap: Path,
    output: Path,
    *,
    version: str,
    facman_revision: str,
    usk_revision: str,
    dirty: bool,
) -> dict[str, object]:
    portable = portable.resolve(strict=True)
    bootstrap = bootstrap.resolve(strict=True)
    output.mkdir(parents=True, exist_ok=True)
    generation = f"facman/generations/{version}/"
    runtime = portable_entries(portable)
    entries = [Entry(generation + item.path, item.data) for item in runtime]
    entries.append(Entry("facman/maintenance/FacManSetup.exe", bootstrap.read_bytes()))
    entries.append(Entry(
        "facman/state/current-generation.v1.json",
        canonical_json({
            "schema": "facman.current_generation.v1",
            "product_id": "facman",
            "version": version,
            "generation": f"generations/{version}",
            "portable_package": portable.name,
            "portable_sha256": sha256_file(portable),
            "facman_source_revision": facman_revision,
            "universal_setup_revision": usk_revision,
            "workspace_preserved": True,
            "automatic_update": False,
        }),
    ))
    names: set[str] = set()
    for entry in entries:
        key = safe_member(entry.path).casefold()
        if key in names:
            raise ValueError(f"self-setup path collision: {entry.path}")
        names.add(key)

    executable = output / f"FacMan-{version}-windows-x64-setup.exe"
    shutil.copyfile(bootstrap, executable)
    bootstrap_size = executable.stat().st_size
    payload = output / f".{executable.name}.payload.tmp"
    payload.unlink(missing_ok=True)
    try:
        with zipfile.ZipFile(payload, "w", allowZip64=True) as archive:
            for entry in sorted(entries, key=lambda item: item.path.encode()):
                archive.writestr(zip_info(entry.path), entry.data)
        with executable.open("ab") as destination, payload.open("rb") as source:
            shutil.copyfileobj(source, destination, length=1024 * 1024)
    finally:
        payload.unlink(missing_ok=True)

    with zipfile.ZipFile(executable) as archive:
        archived = {info.filename for info in archive.infolist() if not info.is_dir()}
    if archived != {entry.path for entry in entries}:
        raise ValueError("self-contained setup ZIP overlay is incomplete")

    record: dict[str, object] = {
        "schema": "facman.self_contained_setup.v1",
        "version": version,
        "profile": "windows_product_x64",
        "facman_source_revision": facman_revision,
        "source_dirty": dirty,
        "universal_setup_revision": usk_revision,
        "default_scope": "per_user_non_administrator",
        "ordinary_launch": "guided_install",
        "offline": True,
        "factorio_mutation": False,
        "workspace_preserved": True,
        "portable_input": {
            "filename": portable.name,
            "sha256": sha256_file(portable),
            "runtime_file_count": len(runtime),
        },
        "embedded_payload": {
            "archive_offset": bootstrap_size,
            "file_count": len(entries),
            "tree_digest": tree_digest(entries),
        },
        "setup": {
            "filename": executable.name,
            "sha256": sha256_file(executable),
            "size_bytes": executable.stat().st_size,
        },
    }
    record_path = output / f"FacMan-{version}-windows-x64-setup.evidence.json"
    record_path.write_bytes(canonical_json(record))
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portable", type=Path, required=True)
    parser.add_argument("--bootstrap", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    dirty = source_dirty()
    if dirty and not args.allow_dirty:
        raise SystemExit("refusing self-contained setup from a dirty source tree")
    record = build(
        args.portable,
        args.bootstrap,
        args.out,
        version=version_truth(),
        facman_revision=source_revision(),
        usk_revision=provider_revision(),
        dirty=dirty,
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
