#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Build the deterministic FacMan self-setup payload and setup executable asset."""

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
VERSION_FILE = ROOT / "release/index/version.v2.toml"
PROVIDER_LOCK = ROOT / "release/index/providers.lock.v2.toml"
MAX_FILES = 100_000
MAX_FILE_BYTES = 8 * 1024 * 1024 * 1024
MAX_TOTAL_BYTES = 16 * 1024 * 1024 * 1024
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


@dataclass(frozen=True)
class InputEntry:
    path: str
    data: bytes


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def version_truth() -> str:
    with VERSION_FILE.open("rb") as source:
        value = tomllib.load(source)
    version = value.get("semver")
    if not isinstance(version, str) or not version:
        raise ValueError("release/index/version.v2.toml has no semantic version")
    return version


def universal_setup_revision() -> str:
    with PROVIDER_LOCK.open("rb") as source:
        value = tomllib.load(source)
    for provider in value.get("provider", []):
        if provider.get("id") == "universal_setup":
            revision = provider.get("source_revision")
            if isinstance(revision, str) and len(revision) == 40:
                return revision
    raise ValueError("provider lock has no exact Universal Setup revision")


def source_revision() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip().lower()


def source_dirty() -> bool:
    return bool(subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=normal"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip())


def safe_member(name: str) -> str:
    if not name or "\\" in name or name.startswith("/"):
        raise ValueError(f"unsafe portable ZIP member: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe portable ZIP member: {name!r}")
    return path.as_posix()


def portable_entries(path: Path) -> list[InputEntry]:
    entries: list[InputEntry] = []
    names: set[str] = set()
    total = 0
    with zipfile.ZipFile(path, "r") as archive:
        for info in archive.infolist():
            name = safe_member(info.filename.rstrip("/"))
            if info.is_dir():
                continue
            if info.flag_bits & 0x1:
                raise ValueError(f"encrypted portable ZIP member is forbidden: {info.filename}")
            mode = (info.external_attr >> 16) & 0o170000
            if mode == 0o120000:
                raise ValueError(f"symbolic-link portable ZIP member is forbidden: {info.filename}")
            folded = name.casefold()
            if folded in names:
                raise ValueError(f"case-insensitive portable ZIP collision: {info.filename}")
            names.add(folded)
            if info.file_size > MAX_FILE_BYTES:
                raise ValueError(f"portable ZIP member exceeds size budget: {info.filename}")
            total += info.file_size
            if total > MAX_TOTAL_BYTES:
                raise ValueError("portable ZIP exceeds total size budget")
            with archive.open(info, "r") as source:
                data = source.read(MAX_FILE_BYTES + 1)
            if len(data) != info.file_size:
                raise ValueError(f"portable ZIP member size changed while reading: {info.filename}")
            entries.append(InputEntry(name, data))
    if not entries or len(entries) > MAX_FILES:
        raise ValueError("portable ZIP file count is outside the setup budget")
    required = {"bin/facman.exe", "bin/facman.winforms.exe"}
    observed = {entry.path.casefold() for entry in entries}
    missing = sorted(required - observed)
    if missing:
        raise ValueError(f"portable ZIP lacks setup entrypoints: {missing}")
    return entries


def zip_info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, ZIP_TIMESTAMP)
    info.compress_type = zipfile.ZIP_STORED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.flag_bits = 0x800
    return info


def tree_digest(entries: list[InputEntry]) -> str:
    digest = hashlib.sha256()
    for entry in sorted(entries, key=lambda value: value.path.encode("utf-8")):
        digest.update(entry.path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(len(entry.data)).encode("ascii"))
        digest.update(b"\0")
        digest.update(sha256_bytes(entry.data).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def build(
    portable: Path,
    setup_exe: Path,
    output: Path,
    *,
    version: str,
    facman_revision: str,
    usk_revision: str,
    dirty: bool,
) -> dict[str, object]:
    portable = portable.resolve(strict=True)
    setup_exe = setup_exe.resolve(strict=True)
    output.mkdir(parents=True, exist_ok=True)
    if not portable.is_file() or not setup_exe.is_file():
        raise ValueError("portable package and setup executable must be regular files")
    portable_hash = sha256_file(portable)
    setup_bytes = setup_exe.read_bytes()
    setup_hash = sha256_bytes(setup_bytes)
    generation_prefix = f"facman/generations/{version}/"
    entries = [InputEntry(generation_prefix + entry.path, entry.data) for entry in portable_entries(portable)]
    entries.append(InputEntry("facman/maintenance/FacManSetup.exe", setup_bytes))
    activation = {
        "schema": "facman.current_generation.v1",
        "product_id": "facman",
        "version": version,
        "generation": f"generations/{version}",
        "portable_package": portable.name,
        "portable_sha256": portable_hash,
        "facman_source_revision": facman_revision,
        "universal_setup_revision": usk_revision,
        "workspace_preserved": True,
        "automatic_update": False,
    }
    entries.append(InputEntry("facman/state/current-generation.v1.json", canonical_json(activation)))
    folded: set[str] = set()
    for entry in entries:
        name = safe_member(entry.path).casefold()
        if name in folded:
            raise ValueError(f"setup payload path collision: {entry.path}")
        folded.add(name)

    payload_name = f"facman-{version}-windows-x64-self-setup-payload.zip"
    payload = output / payload_name
    with zipfile.ZipFile(payload, "w", allowZip64=True) as archive:
        for entry in sorted(entries, key=lambda value: value.path.encode("utf-8")):
            archive.writestr(zip_info(entry.path), entry.data)
    payload_hash = sha256_file(payload)

    executable_name = f"FacManSetup-{version}-windows-x64.exe"
    executable = output / executable_name
    shutil.copyfile(setup_exe, executable)

    record = {
        "schema": "facman.self_setup_package.v1",
        "version": version,
        "profile": "windows_x64_per_user_self_setup",
        "support": "unsupported_private_alpha_candidate",
        "facman_source_revision": facman_revision,
        "source_dirty": dirty,
        "universal_setup_revision": usk_revision,
        "default_scope": "per_user_non_administrator",
        "offline": True,
        "automatic_update": False,
        "factorio_mutation": False,
        "workspace_preserved": True,
        "payload": {
            "filename": payload_name,
            "sha256": payload_hash,
            "size_bytes": payload.stat().st_size,
            "file_count": len(entries),
            "tree_digest": tree_digest(entries),
            "compression": "stored",
        },
        "setup_executable": {
            "filename": executable_name,
            "sha256": setup_hash,
            "size_bytes": executable.stat().st_size,
        },
        "portable_input": {
            "filename": portable.name,
            "sha256": portable_hash,
            "generation_file_count": len(entries) - 2,
        },
    }
    record_path = output / f"facman-{version}-self-setup-package.v1.json"
    record_path.write_bytes(canonical_json(record))
    record["record"] = {
        "filename": record_path.name,
        "sha256": sha256_file(record_path),
    }
    return record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portable", type=Path, required=True)
    parser.add_argument("--setup-exe", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--allow-dirty", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    dirty = source_dirty()
    if dirty and not args.allow_dirty:
        raise SystemExit("refusing release setup package from a dirty FacMan source tree")
    record = build(
        args.portable,
        args.setup_exe,
        args.out,
        version=version_truth(),
        facman_revision=source_revision(),
        usk_revision=universal_setup_revision(),
        dirty=dirty,
    )
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
