# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import stat
import tarfile
import tempfile
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Iterator

from .canonical import digest_value, normalize_relative_path
from .compiler import OUTPUT_FILES
from .outputs import load_resolution
from .staging import (
    RUNTIME_METADATA_KEYS,
    STAGE_MANIFEST_PATH,
    load_stage_manifest,
    validate_stage_manifest,
    validate_stage_manifest_for_resolution,
    verify_stage,
)


BLOCK_SIZE = 1024 * 1024
MAX_ENTRIES = 100_000
MAX_ENTRY_SIZE = 2 * 1024 * 1024 * 1024
MAX_TOTAL_SIZE = 4 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1_000
MAX_MANIFEST_SIZE = 16 * 1024 * 1024
FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def archive_stage(
    resolution_root: Path,
    artifact_id: str,
    stage_root: Path,
    output_root: Path,
) -> Path:
    """Create the resolution-named deterministic archive for one verified v2 stage."""
    outputs = load_resolution(resolution_root)
    artifact = _artifact(outputs, artifact_id)
    package_format = str(artifact["format"])
    filename = _archive_filename(str(artifact["filename"]), package_format)
    stage_path = Path(os.path.abspath(stage_root))
    stage_verification = verify_stage(resolution_root, artifact_id, stage_path)
    manifest = load_stage_manifest(stage_path)
    if manifest["stage_digest"] != stage_verification["stage_digest"]:
        raise ValueError("stage identity changed before archive construction")

    destination_root = Path(os.path.abspath(output_root))
    if destination_root == stage_path or stage_path in destination_root.parents:
        raise ValueError("archive output directory must be outside the verified stage")
    destination_root.mkdir(parents=True, exist_ok=True)
    _require_directory(destination_root)
    destination = destination_root / filename
    if os.path.lexists(destination):
        raise ValueError(f"archive output already exists: {destination}")

    suffix = ".zip" if package_format == "zip" else ".tar.gz"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".facman-archive-",
        suffix=suffix,
        dir=destination_root,
    )
    temporary = Path(temporary_name)
    published = False
    try:
        with os.fdopen(descriptor, "w+b") as raw:
            if package_format == "zip":
                _write_stage_zip(raw, stage_path, manifest)
            else:
                _write_stage_tar_gz(raw, stage_path, manifest)

        package_verification = verify_package(
            resolution_root,
            artifact_id,
            temporary,
        )
        exact_fields = ("artifact_id", "resolution_digest", "resolution_root_digest", "stage_digest")
        for field in exact_fields:
            if package_verification[field] != stage_verification[field]:
                raise ValueError(f"archive verification changed exact stage identity: {field}")
        container_sha256 = _stable_digest(temporary)

        try:
            os.link(temporary, destination)
        except FileExistsError as exc:
            raise ValueError(f"archive output already exists: {destination}") from exc
        published = True
        temporary.unlink()
        if _stable_digest(destination) != container_sha256:
            raise ValueError("archive container identity changed during publication")
        published_verification = verify_package(
            resolution_root,
            artifact_id,
            destination,
        )
        if published_verification != package_verification:
            raise ValueError("archive package identity changed during publication")
        published = False
        return destination
    finally:
        if published:
            destination.unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)


def _artifact(outputs: dict[str, dict[str, Any]], artifact_id: str) -> dict[str, Any]:
    matches = [
        item
        for item in outputs["package_plan"]["artifacts"]
        if item.get("id") == artifact_id
    ]
    if len(matches) != 1:
        raise ValueError(f"resolution does not select artifact {artifact_id!r}")
    return matches[0]


def _archive_filename(filename: str, package_format: str) -> str:
    normalized = _member_path(filename)
    if "/" in normalized:
        raise ValueError("resolved artifact filename must not contain directories")
    if package_format == "zip":
        if not normalized.lower().endswith(".zip"):
            raise ValueError("resolved ZIP artifact filename must end with .zip")
    elif package_format == "tar_gz":
        if not normalized.lower().endswith(".tar.gz"):
            raise ValueError("resolved TAR.GZ artifact filename must end with .tar.gz")
    else:
        raise ValueError(f"unsupported resolved archive format: {package_format!r}")
    return normalized


def _stage_records(stage_root: Path, manifest: dict[str, Any]) -> list[dict[str, Any]]:
    records = [dict(item) for item in manifest["entries"]]
    manifest_path = stage_root / PurePosixPath(STAGE_MANIFEST_PATH)
    manifest_identity = _require_file(manifest_path)
    records.append(
        {
            "path": STAGE_MANIFEST_PATH,
            "sha256": _stable_digest(manifest_path),
            "size": manifest_identity.st_size,
            "mode": 0o644,
        }
    )
    records.sort(key=lambda item: str(item["path"]))
    total_size = 0
    for count, record in enumerate(records, start=1):
        record["path"] = _member_path(str(record["path"]))
        size = int(record["size"])
        total_size += size
        _check_entry_count(count)
        _check_sizes(size, total_size)
    return records


def _write_stage_zip(
    raw: BinaryIO,
    stage_root: Path,
    manifest: dict[str, Any],
) -> None:
    with zipfile.ZipFile(
        raw,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
        allowZip64=True,
    ) as archive:
        for record in _stage_records(stage_root, manifest):
            relative = str(record["path"])
            mode = int(record["mode"])
            info = zipfile.ZipInfo(relative, FIXED_ZIP_TIME)
            info.create_system = 3
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = mode << 16
            with archive.open(info, "w", force_zip64=True) as output:
                _copy_verified_stage_file(
                    stage_root / PurePosixPath(relative),
                    output,
                    record,
                )


def _write_stage_tar_gz(
    raw: BinaryIO,
    stage_root: Path,
    manifest: dict[str, Any],
) -> None:
    with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for record in _stage_records(stage_root, manifest):
                relative = str(record["path"])
                info = tarfile.TarInfo(relative)
                info.size = int(record["size"])
                info.mode = int(record["mode"])
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.mtime = 0
                handle, before = _open_stable_file(stage_root / PurePosixPath(relative))
                try:
                    archive.addfile(info, handle)
                    after = os.fstat(handle.fileno())
                finally:
                    handle.close()
                _require_unchanged(stage_root / PurePosixPath(relative), before, after)


def _copy_verified_stage_file(
    source: Path,
    destination: BinaryIO,
    record: dict[str, Any],
) -> None:
    handle, before = _open_stable_file(source)
    digest = hashlib.sha256()
    size = 0
    try:
        while True:
            block = handle.read(BLOCK_SIZE)
            if not block:
                break
            size += len(block)
            if size > int(record["size"]):
                raise ValueError(f"staged file grew during archive construction: {record['path']}")
            digest.update(block)
            destination.write(block)
        after = os.fstat(handle.fileno())
    finally:
        handle.close()
    _require_unchanged(source, before, after)
    if size != int(record["size"]) or digest.hexdigest() != record["sha256"]:
        raise ValueError(f"staged file changed during archive construction: {record['path']}")


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
        expanded_size = sum(int(item["size"]) for item in entries)
        container_size = path.stat().st_size
        if expanded_size and (
            container_size == 0
            or expanded_size / container_size > MAX_COMPRESSION_RATIO
        ):
            raise ValueError("package exceeds compression ratio limit")
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
            entry_type = stat.S_IFMT(mode)
            if entry_type and not stat.S_ISREG(mode) and not stat.S_ISDIR(mode):
                raise ValueError(f"package contains a non-regular entry: {relative}")
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
    for part in PurePosixPath(normalized).parts:
        if part.endswith((" ", ".")):
            raise ValueError(f"package entry is not a portable path: {value!r}")
        stem = part.split(".", 1)[0].casefold()
        if stem in {"con", "prn", "aux", "nul"} or re.fullmatch(
            r"(?:com|lpt)[1-9]", stem
        ):
            raise ValueError(f"package entry uses a reserved portable name: {value!r}")
    if unicodedata.normalize("NFC", raw) != raw:
        raise ValueError(f"package entry path is not Unicode-normalized: {value!r}")
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
    if identity.st_nlink != 1:
        raise ValueError(f"package file must not be hard-linked: {path}")
    return identity


def _file_identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)


def _open_stable_file(path: Path) -> tuple[BinaryIO, os.stat_result]:
    before = _require_file(path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    handle = os.fdopen(descriptor, "rb")
    opened = os.fstat(handle.fileno())
    if _file_identity(before) != _file_identity(opened):
        handle.close()
        raise ValueError(f"package file identity changed while opening: {path}")
    return handle, before


def _require_unchanged(
    path: Path,
    before: os.stat_result,
    after: os.stat_result,
) -> None:
    current = _require_file(path)
    if len({_file_identity(before), _file_identity(after), _file_identity(current)}) != 1:
        raise ValueError(f"package file identity changed while reading: {path}")


def _stable_digest(path: Path) -> str:
    handle, before = _open_stable_file(path)
    with handle:
        digest, size = _hash_stream(handle, MAX_TOTAL_SIZE)
        after = os.fstat(handle.fileno())
    _require_unchanged(path, before, after)
    if size != before.st_size:
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
        for other_key, other_path in folded.items():
            if key.startswith(other_key + "/") or other_key.startswith(key + "/"):
                raise ValueError(
                    "package file/directory paths collide under case folding: "
                    f"{other_path} and {path}"
                )
        folded[key] = path
    entries.sort(key=lambda item: str(item["path"]))


def read_package_member(package: Path, member: str, limit: int = MAX_MANIFEST_SIZE) -> bytes:
    path = Path(os.path.abspath(package))
    canonical_member = _member_path(member)
    if path.is_dir():
        candidate = path / PurePosixPath(canonical_member)
        if candidate == path or path not in candidate.parents:
            raise ValueError("package member escapes directory root")
        current = candidate.parent
        while current != path:
            _require_directory(current)
            current = current.parent
        _require_directory(path)
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
    _artifact(outputs, artifact_id)
    inspection = inspect_package(package)
    try:
        manifest_value = json.loads(read_package_member(package, STAGE_MANIFEST_PATH))
    except json.JSONDecodeError as exc:
        raise ValueError(f"package stage manifest is malformed: {exc}") from exc
    manifest = validate_stage_manifest(manifest_value)
    expected = validate_stage_manifest_for_resolution(outputs, artifact_id, manifest)
    resolution_digest = outputs["composition"]["resolution_digest"]
    if manifest.get("resolution_digest") != resolution_digest:
        raise ValueError("package stage manifest has the wrong resolution digest")
    resolution_root_digest = outputs["resolution_set"]["root_digest"]
    if manifest.get("resolution_root_digest") != resolution_root_digest:
        raise ValueError("package stage manifest has the wrong resolution root digest")
    actual = {str(item["path"]): item for item in inspection["entries"]}
    expected_paths = set(expected) | {STAGE_MANIFEST_PATH}
    if set(actual) != expected_paths:
        missing = sorted(expected_paths - set(actual))
        extra = sorted(set(actual) - expected_paths)
        raise ValueError(f"package is not a projection of the staged graph: missing={missing}, extra={extra}")
    for relative, record in expected.items():
        packaged = actual[relative]
        if (
            packaged.get("sha256") != record.get("sha256")
            or packaged.get("size") != record.get("size")
            or (
                inspection["format"] != "directory"
                and packaged.get("mode") != record.get("mode")
            )
        ):
            raise ValueError(f"package entry differs from canonical stage: {relative}")
    if (
        inspection["format"] != "directory"
        and actual[STAGE_MANIFEST_PATH].get("mode") != 0o644
    ):
        raise ValueError("package stage manifest has the wrong portable mode")
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
