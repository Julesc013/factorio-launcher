#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Build, inspect, verify, and safely export the FacMan runtime resource pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import tempfile
import tomllib
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
PACK_SCHEMA = "facman.runtime_resource_pack.v1"
MANIFEST_PATH = "manifest/resource-pack.v1.json"
ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)
MAX_ENTRY_BYTES = 32 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024
MAX_ENTRIES = 20_000
SOURCE_TREES = (
    "contracts/schema",
    "contracts/command",
    "contracts/generated-index",
    "contracts/policy",
    "content/factorio",
)
IDENTITY_FILES = (
    "release/index/version.v2.toml",
    "release/index/product.v2.toml",
    "release/index/providers.lock.v2.toml",
    "release/index/workspace_lock.v1.toml",
    "release/index/support.v2.toml",
    "release/index/technical_preview_scope.v1.toml",
    "release/index/foundation_public_beta_scope.v2.toml",
)
FORBIDDEN_SUFFIXES = {
    ".bat",
    ".cmd",
    ".com",
    ".dll",
    ".dylib",
    ".exe",
    ".msi",
    ".ps1",
    ".sh",
    ".so",
}


@dataclass(frozen=True)
class Entry:
    path: str
    source: Path
    size: int
    sha256: str


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
        raise ValueError(f"unsafe resource-pack member: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe resource-pack member: {value!r}")
    normalized = path.as_posix()
    if path.suffix.casefold() in FORBIDDEN_SUFFIXES:
        raise ValueError(f"executable resource-pack member is forbidden: {normalized}")
    return normalized


def source_entries(root: Path) -> list[Entry]:
    root = root.resolve(strict=True)
    candidates: list[Path] = []
    for relative in SOURCE_TREES:
        source = root / relative
        if not source.is_dir():
            raise ValueError(f"missing runtime resource tree: {relative}")
        candidates.extend(path for path in source.rglob("*") if path.is_file())
    for relative in IDENTITY_FILES:
        source = root / relative
        if not source.is_file():
            raise ValueError(f"missing runtime identity resource: {relative}")
        candidates.append(source)

    entries: list[Entry] = []
    folded: set[str] = set()
    total = 0
    for source in sorted(set(candidates), key=lambda path: path.relative_to(root).as_posix()):
        if source.is_symlink():
            raise ValueError(f"linked runtime resource is forbidden: {source}")
        relative = safe_member(source.relative_to(root).as_posix())
        key = relative.casefold()
        if key in folded:
            raise ValueError(f"case-insensitive resource collision: {relative}")
        folded.add(key)
        size = source.stat().st_size
        if size > MAX_ENTRY_BYTES:
            raise ValueError(f"runtime resource exceeds entry budget: {relative}")
        total += size
        if total > MAX_TOTAL_BYTES:
            raise ValueError("runtime resource set exceeds total size budget")
        entries.append(Entry(relative, source, size, sha256_file(source)))
    if len(entries) > MAX_ENTRIES:
        raise ValueError("runtime resource set exceeds entry-count budget")
    return entries


def content_digest(entries: Iterable[Entry]) -> str:
    digest = hashlib.sha256()
    for entry in entries:
        digest.update(entry.path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(entry.size).encode("ascii"))
        digest.update(b"\0")
        digest.update(entry.sha256.encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def pack_manifest(root: Path, entries: list[Entry]) -> dict[str, object]:
    with (root / "release/index/version.v2.toml").open("rb") as stream:
        version = tomllib.load(stream)
    with (root / "release/index/providers.lock.v2.toml").open("rb") as stream:
        providers = tomllib.load(stream)
    provider_identity: dict[str, dict[str, str]] = {}
    for item in providers.get("sdk_package", []):
        if not isinstance(item, dict) or "provider_id" not in item or "source_revision" not in item:
            continue
        provider_id = str(item["provider_id"])
        identity = {
            "source_revision": str(item["source_revision"]),
            "package_version": str(item.get("package_version", "")),
        }
        previous = provider_identity.setdefault(provider_id, identity)
        if previous != identity:
            raise ValueError(f"provider lock has inconsistent identity for {provider_id}")
    return {
        "schema": PACK_SCHEMA,
        "product_id": "facman",
        "product_name": "FacMan",
        "version": str(version["semver"]),
        "compression": "deflate",
        "deterministic": True,
        "executable_content": False,
        "entry_count": len(entries),
        "expanded_bytes": sum(entry.size for entry in entries),
        "content_sha256": content_digest(entries),
        "providers": provider_identity,
        "entries": [
            {"path": entry.path, "bytes": entry.size, "sha256": entry.sha256}
            for entry in entries
        ],
    }


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")


def zip_info(path: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, ZIP_TIMESTAMP)
    info.create_system = 3
    info.external_attr = (stat.S_IFREG | 0o444) << 16
    info.flag_bits = 0x800
    info.compress_type = zipfile.ZIP_DEFLATED
    return info


def build(root: Path, output: Path) -> dict[str, object]:
    root = root.resolve(strict=True)
    output = output.resolve()
    entries = source_entries(root)
    manifest = pack_manifest(root, entries)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        prefix=f".{output.name}.", suffix=".tmp", dir=output.parent, delete=False
    ) as temporary:
        staging = Path(temporary.name)
    try:
        with zipfile.ZipFile(
            staging, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9, allowZip64=True
        ) as archive:
            archive.writestr(zip_info(MANIFEST_PATH), canonical_json(manifest), compresslevel=9)
            for entry in entries:
                archive.writestr(zip_info(entry.path), entry.source.read_bytes(), compresslevel=9)
        verify(staging)
        os.replace(staging, output)
    finally:
        staging.unlink(missing_ok=True)
    return {
        "schema": "facman.runtime_resource_pack_build.v1",
        "path": str(output),
        "bytes": output.stat().st_size,
        "sha256": sha256_file(output),
        "content_sha256": manifest["content_sha256"],
        "entry_count": manifest["entry_count"],
    }


def read_manifest(archive: zipfile.ZipFile) -> dict[str, object]:
    try:
        value = json.loads(archive.read(MANIFEST_PATH))
    except KeyError as exc:
        raise ValueError(f"resource pack is missing {MANIFEST_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError("resource-pack manifest is not valid JSON") from exc
    if not isinstance(value, dict) or value.get("schema") != PACK_SCHEMA:
        raise ValueError("resource-pack manifest has the wrong schema")
    return value


def verify(path: Path) -> dict[str, object]:
    path = path.resolve(strict=True)
    folded: set[str] = set()
    observed: dict[str, tuple[int, str]] = {}
    total = 0
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            member = safe_member(info.filename)
            if info.is_dir():
                raise ValueError(f"directory entries are forbidden: {member}")
            key = member.casefold()
            if key in folded:
                raise ValueError(f"duplicate or case-colliding resource member: {member}")
            folded.add(key)
            if info.flag_bits & 0x1 or info.compress_type not in {
                zipfile.ZIP_STORED,
                zipfile.ZIP_DEFLATED,
            }:
                raise ValueError(f"encrypted or unsupported resource member: {member}")
            if info.file_size > MAX_ENTRY_BYTES:
                raise ValueError(f"resource member exceeds entry budget: {member}")
            total += info.file_size
            if total > MAX_TOTAL_BYTES:
                raise ValueError("resource pack exceeds total expanded-size budget")
            data = archive.read(info)
            observed[member] = (len(data), sha256_bytes(data))
        if len(observed) > MAX_ENTRIES + 1:
            raise ValueError("resource pack exceeds entry-count budget")
        manifest = read_manifest(archive)

    declared_entries = manifest.get("entries")
    if not isinstance(declared_entries, list):
        raise ValueError("resource-pack manifest entries must be an array")
    declared: dict[str, tuple[int, str]] = {}
    for item in declared_entries:
        if not isinstance(item, dict):
            raise ValueError("resource-pack manifest entry must be an object")
        member = safe_member(str(item.get("path", "")))
        if member == MANIFEST_PATH or member in declared:
            raise ValueError(f"invalid duplicate resource-pack manifest entry: {member}")
        declared[member] = (int(item.get("bytes", -1)), str(item.get("sha256", "")))
    payload = {key: value for key, value in observed.items() if key != MANIFEST_PATH}
    if payload != declared:
        missing = sorted(set(declared) - set(payload))
        unexpected = sorted(set(payload) - set(declared))
        mismatched = sorted(key for key in set(payload) & set(declared) if payload[key] != declared[key])
        raise ValueError(
            f"resource-pack payload mismatch: missing={missing} unexpected={unexpected} "
            f"mismatched={mismatched}"
        )
    digest_entries = [
        Entry(member, path, metadata[0], metadata[1])
        for member, metadata in sorted(declared.items())
    ]
    digest = content_digest(digest_entries)
    if manifest.get("content_sha256") != digest:
        raise ValueError("resource-pack content digest mismatch")
    if manifest.get("entry_count") != len(declared):
        raise ValueError("resource-pack entry count mismatch")
    if manifest.get("expanded_bytes") != sum(item[0] for item in declared.values()):
        raise ValueError("resource-pack expanded-byte count mismatch")
    return {
        "schema": "facman.runtime_resource_pack_verification.v1",
        "status": "pass",
        "path": str(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "content_sha256": digest,
        "entry_count": len(declared),
        "entries": sorted(declared),
    }


def export(path: Path, destination: Path) -> dict[str, object]:
    verification = verify(path)
    destination = destination.resolve()
    if destination.exists():
        raise ValueError(f"resource export destination must not exist: {destination}")
    staging = destination.with_name(f".{destination.name}.facman-resource-export")
    if staging.exists():
        raise ValueError(f"resource export staging path already exists: {staging}")
    staging.mkdir(parents=True)
    try:
        with zipfile.ZipFile(path) as archive:
            for info in archive.infolist():
                member = safe_member(info.filename)
                target = staging.joinpath(*PurePosixPath(member).parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(info))
        staging.replace(destination)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {
        "schema": "facman.runtime_resource_pack_export.v1",
        "status": "pass",
        "source_sha256": verification["sha256"],
        "destination": str(destination),
        "entry_count": verification["entry_count"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build_parser = subparsers.add_parser("build")
    build_parser.add_argument("--root", type=Path, default=ROOT)
    build_parser.add_argument("--out", type=Path, required=True)
    inspect_parser = subparsers.add_parser("list")
    inspect_parser.add_argument("pack", type=Path)
    verify_parser = subparsers.add_parser("verify")
    verify_parser.add_argument("pack", type=Path)
    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("pack", type=Path)
    export_parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.command == "build":
        result = build(args.root, args.out)
    elif args.command == "verify":
        result = verify(args.pack)
    elif args.command == "export":
        result = export(args.pack, args.destination)
    else:
        result = verify(args.pack)
        result = {
            "schema": "facman.runtime_resource_pack_inventory.v1",
            "path": result["path"],
            "sha256": result["sha256"],
            "entry_count": result["entry_count"],
            "entries": result["entries"],
        }
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
