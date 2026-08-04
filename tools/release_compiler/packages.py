# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import os
import stat
import tarfile
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Iterator

from .canonical import digest_value, normalize_relative_path
from .compiler import OUTPUT_FILES
from .outputs import load_resolution
from .staging import RUNTIME_METADATA_KEYS, STAGE_MANIFEST_PATH, validate_stage_manifest


BLOCK_SIZE = 1024 * 1024
MAX_ENTRIES = 100_000
MAX_ENTRY_SIZE = 2 * 1024 * 1024 * 1024
MAX_TOTAL_SIZE = 4 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1_000
MAX_MANIFEST_SIZE = 16 * 1024 * 1024


def inspect_package(package: Path) -> dict[str, Any]:
    path = Path(os.path.abspath(package))
    container_sha256 = None
    if path.is_dir():
        _require_directory(path)
        package_format = "directory"
        entries = list(_inspect_directory(path))
    elif path.is_file() and path.suffix.lower() == ".zip":
        container_sha256 = _stable_digest(path)
        package_format = "zip"
        entries = list(_inspect_zip(path))
    elif path.is_file() and _is_tar_name(path.name):
        container_sha256 = _stable_digest(path)
        package_format = "tar"
        entries = list(_inspect_tar(path))
    else:
        raise ValueError(f"unsupported package input: {path}")
    _validate_inventory(entries)
    if container_sha256 is not None and _stable_digest(path) != container_sha256:
        raise ValueError("package container changed during inspection")
    core = {
        "schema": "facman.package_inspection.v1",
        "format": package_format,
        "container_sha256": container_sha256,
        "entries": entries,
    }
    return {**core, "inventory_digest": digest_value(core)}


def _is_tar_name(name: str) -> bool:
    lowered = name.lower()
    return lowered.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz"))


def _inspect_directory(root: Path) -> Iterator[dict[str, Any]]:
    count = 0
    total = 0
    for current, directories, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in sorted(directories):
            _require_directory(current_path / name)
        directories[:] = sorted(directories)
        for name in sorted(filenames):
            count += 1
            _check_entry_count(count)
            path = current_path / name
            identity = _require_file(path)
            total += identity.st_size
            _check_sizes(identity.st_size, total)
            relative = path.relative_to(root).as_posix()
            yield {
                "path": _member_path(relative),
                "sha256": _stable_digest(path),
                "size": identity.st_size,
                "mode": stat.S_IMODE(identity.st_mode),
            }


def _inspect_zip(path: Path) -> Iterator[dict[str, Any]]:
    total = 0
    with zipfile.ZipFile(path, "r") as archive:
        for count, item in enumerate(archive.infolist(), start=1):
            _check_entry_count(count)
            relative = _member_path(item.filename)
            mode = (item.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                raise ValueError(f"package contains a symbolic link: {relative}")
            if item.flag_bits & 0x1:
                raise ValueError(f"package contains an encrypted entry: {relative}")
            if item.is_dir():
                continue
            total += item.file_size
            _check_sizes(item.file_size, total)
            if item.file_size and item.compress_size == 0:
                raise ValueError(f"package entry has impossible compressed size: {relative}")
            if item.compress_size and item.file_size / item.compress_size > MAX_COMPRESSION_RATIO:
                raise ValueError(f"package entry exceeds compression ratio limit: {relative}")
            with archive.open(item, "r") as handle:
                digest, size = _hash_stream(handle, MAX_ENTRY_SIZE)
            if size != item.file_size:
                raise ValueError(f"package entry size changed while reading: {relative}")
            yield {
                "path": relative,
                "sha256": digest,
                "size": size,
                "mode": stat.S_IMODE(mode) if mode else 0,
            }


def _inspect_tar(path: Path) -> Iterator[dict[str, Any]]:
    total = 0
    with tarfile.open(path, "r:*") as archive:
        count = 0
        for item in archive:
            count += 1
            _check_entry_count(count)
            relative = _member_path(item.name)
            if item.isdir():
                continue
            if not item.isreg():
                raise ValueError(f"package contains a non-regular entry: {relative}")
            total += item.size
            _check_sizes(item.size, total)
            handle = archive.extractfile(item)
            if handle is None:
                raise ValueError(f"package entry cannot be read: {relative}")
            with handle:
                digest, size = _hash_stream(handle, MAX_ENTRY_SIZE)
            if size != item.size:
                raise ValueError(f"package entry size changed while reading: {relative}")
            yield {
                "path": relative,
                "sha256": digest,
                "size": size,
                "mode": stat.S_IMODE(item.mode),
            }


def _member_path(value: str) -> str:
    if "\x00" in value or "\\" in value or ":" in value:
        raise ValueError(f"package entry is not a portable path: {value!r}")
    raw = value.rstrip("/")
    normalized = normalize_relative_path(raw, field="package entry")
    if raw != normalized:
        raise ValueError(f"package entry path is not canonical: {value!r}")
    return normalized


def _check_entry_count(count: int) -> None:
    if count > MAX_ENTRIES:
        raise ValueError(f"package exceeds entry-count limit of {MAX_ENTRIES}")


def _check_sizes(entry_size: int, total_size: int) -> None:
    if entry_size < 0 or entry_size > MAX_ENTRY_SIZE:
        raise ValueError(f"package entry exceeds size limit of {MAX_ENTRY_SIZE}")
    if total_size > MAX_TOTAL_SIZE:
        raise ValueError(f"package exceeds expanded-size limit of {MAX_TOTAL_SIZE}")


def _hash_stream(handle: BinaryIO, limit: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    while True:
        block = handle.read(BLOCK_SIZE)
        if not block:
            break
        size += len(block)
        if size > limit:
            raise ValueError(f"package stream exceeds size limit of {limit}")
        digest.update(block)
    return digest.hexdigest(), size


def _attributes(path: Path) -> int:
    return getattr(os.lstat(path), "st_file_attributes", 0)


def _is_reparse(path: Path) -> bool:
    return bool(_attributes(path) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))


def _require_directory(path: Path) -> os.stat_result:
    if path.is_symlink() or _is_reparse(path):
        raise ValueError(f"package directory is a symbolic link or reparse point: {path}")
    identity = os.lstat(path)
    if not stat.S_ISDIR(identity.st_mode):
        raise ValueError(f"package entry is not a directory: {path}")
    return identity


def _require_file(path: Path) -> os.stat_result:
    if path.is_symlink() or _is_reparse(path):
        raise ValueError(f"package file is a symbolic link or reparse point: {path}")
    identity = os.lstat(path)
    if not stat.S_ISREG(identity.st_mode):
        raise ValueError(f"package entry is not a regular file: {path}")
    return identity


def _stable_digest(path: Path) -> str:
    before = _require_file(path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as handle:
        opened = os.fstat(handle.fileno())
        digest, size = _hash_stream(handle, MAX_TOTAL_SIZE)
        after = os.fstat(handle.fileno())
    current = _require_file(path)
    identities = {
        (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns)
        for item in (before, opened, after, current)
    }
    if len(identities) != 1 or size != before.st_size:
        raise ValueError(f"package file identity changed while reading: {path}")
    return digest


def _validate_inventory(entries: list[dict[str, Any]]) -> None:
    paths: set[str] = set()
    folded: dict[str, str] = {}
    for entry in entries:
        path = str(entry["path"])
        if path in paths:
            raise ValueError(f"package repeats an entry: {path}")
        paths.add(path)
        key = path.casefold()
        if key in folded:
            raise ValueError(f"package paths collide under case folding: {folded[key]} and {path}")
        folded[key] = path
    entries.sort(key=lambda item: str(item["path"]))


def read_package_member(package: Path, member: str, limit: int = MAX_MANIFEST_SIZE) -> bytes:
    path = Path(os.path.abspath(package))
    canonical_member = _member_path(member)
    if path.is_dir():
        candidate = path / PurePosixPath(canonical_member)
        if candidate.parent != path:
            candidate_parent = candidate.parent.resolve()
            if candidate_parent != path and path not in candidate_parent.parents:
                raise ValueError("package member escapes directory root")
        identity = _require_file(candidate)
        if identity.st_size > limit:
            raise ValueError(f"package member exceeds read limit: {canonical_member}")
        return candidate.read_bytes()
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path, "r") as archive:
            matches = [item for item in archive.infolist() if _member_path(item.filename) == canonical_member]
            if len(matches) != 1:
                raise ValueError(f"package must contain exactly one {canonical_member}")
            if matches[0].file_size > limit:
                raise ValueError(f"package member exceeds read limit: {canonical_member}")
            with archive.open(matches[0], "r") as handle:
                value = handle.read(limit + 1)
    elif _is_tar_name(path.name):
        with tarfile.open(path, "r:*") as archive:
            matches = [item for item in archive if _member_path(item.name) == canonical_member]
            if len(matches) != 1 or not matches[0].isreg():
                raise ValueError(f"package must contain exactly one regular {canonical_member}")
            if matches[0].size > limit:
                raise ValueError(f"package member exceeds read limit: {canonical_member}")
            handle = archive.extractfile(matches[0])
            if handle is None:
                raise ValueError(f"package member cannot be read: {canonical_member}")
            with handle:
                value = handle.read(limit + 1)
    else:
        raise ValueError(f"unsupported package input: {path}")
    if len(value) > limit:
        raise ValueError(f"package member exceeds read limit: {canonical_member}")
    return value


def verify_package(
    resolution_root: Path,
    artifact_id: str,
    package: Path,
) -> dict[str, Any]:
    outputs = load_resolution(resolution_root)
    artifacts = [
        item
        for item in outputs["package_plan"]["artifacts"]
        if item.get("id") == artifact_id
    ]
    if len(artifacts) != 1:
        raise ValueError(f"resolution does not select artifact {artifact_id!r}")
    inspection = inspect_package(package)
    try:
        manifest_value = json.loads(read_package_member(package, STAGE_MANIFEST_PATH))
    except json.JSONDecodeError as exc:
        raise ValueError(f"package stage manifest is malformed: {exc}") from exc
    manifest = validate_stage_manifest(manifest_value)
    if manifest.get("artifact_id") != artifact_id:
        raise ValueError("package stage manifest has the wrong artifact identity")
    resolution_digest = outputs["composition"]["resolution_digest"]
    if manifest.get("resolution_digest") != resolution_digest:
        raise ValueError("package stage manifest has the wrong resolution digest")
    resolution_root_digest = outputs["resolution_set"]["root_digest"]
    if manifest.get("resolution_root_digest") != resolution_root_digest:
        raise ValueError("package stage manifest has the wrong resolution root digest")
    expected_rows = manifest.get("entries")
    if not isinstance(expected_rows, list):
        raise ValueError("package stage manifest entries must be an array")
    expected = {str(item["path"]): item for item in expected_rows if isinstance(item, dict)}
    actual = {str(item["path"]): item for item in inspection["entries"]}
    expected_paths = set(expected) | {STAGE_MANIFEST_PATH}
    if set(actual) != expected_paths:
        missing = sorted(expected_paths - set(actual))
        extra = sorted(set(actual) - expected_paths)
        raise ValueError(f"package is not a projection of the staged graph: missing={missing}, extra={extra}")
    for relative, record in expected.items():
        packaged = actual[relative]
        if packaged.get("sha256") != record.get("sha256") or packaged.get("size") != record.get("size"):
            raise ValueError(f"package entry differs from canonical stage: {relative}")
    for key in RUNTIME_METADATA_KEYS:
        filename = OUTPUT_FILES[key]
        relative = f"manifest/resolution/{filename}"
        if relative not in actual:
            raise ValueError(f"package omits resolved graph record: {filename}")
        if actual[relative]["sha256"] != _stable_digest(resolution_root / filename):
            raise ValueError(f"package embeds a different resolved graph record: {filename}")
    resolved_declarations = {
        str(item["id"]): str(item["destination"])
        for item in outputs["paths"]["paths"]
        if item.get("source_kind") != "external_reference"
    }
    manifest_declarations = {
        str(item["id"]): str(item["destination"])
        for item in manifest.get("declarations", [])
        if isinstance(item, dict)
    }
    if manifest_declarations != resolved_declarations:
        raise ValueError("package stage manifest path ownership differs from the resolution")
    final_inspection = inspect_package(package)
    if final_inspection["inventory_digest"] != inspection["inventory_digest"]:
        raise ValueError("package identity changed during verification")
    return {
        "schema": "facman.package_verification.v1",
        "artifact_id": artifact_id,
        "resolution_digest": resolution_digest,
        "resolution_root_digest": resolution_root_digest,
        "stage_digest": manifest["stage_digest"],
        "inventory_digest": inspection["inventory_digest"],
        "entry_count": len(actual),
        "verified": True,
    }
