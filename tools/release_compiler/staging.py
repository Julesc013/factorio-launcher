# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

from .canonical import digest_file, digest_value, normalize_relative_path, pretty_json
from .compiler import OUTPUT_FILES
from .outputs import load_resolution


STAGE_MANIFEST_PATH = "manifest/stage.v1.json"
BLOCK_SIZE = 1024 * 1024


def parse_source_overrides(values: list[str]) -> dict[str, Path]:
    output: dict[str, Path] = {}
    for value in values:
        identity, separator, raw_path = value.partition("=")
        if not separator or not identity or not raw_path:
            raise ValueError(f"source override must use NAME=PATH: {value!r}")
        if identity in output:
            raise ValueError(f"duplicate source override: {identity}")
        output[identity] = Path(os.path.abspath(raw_path))
    return output


def stage(
    resolution_root: Path,
    artifact_id: str,
    source_root: Path,
    source_overrides: dict[str, Path],
    output_root: Path,
) -> Path:
    outputs = load_resolution(resolution_root)
    artifact = _artifact(outputs, artifact_id)
    destination = Path(os.path.abspath(output_root))
    _require_empty_or_absent(destination, "stage output")
    destination.parent.mkdir(parents=True, exist_ok=True)
    entries: list[dict[str, Any]] = []
    declarations: list[dict[str, Any]] = []
    used_overrides: set[str] = set()
    with tempfile.TemporaryDirectory(prefix=".facman-stage-", dir=destination.parent) as temporary:
        temporary_root = Path(temporary)
        for declaration in outputs["paths"]["paths"]:
            source, override = _resolve_source(
                str(declaration["source"]),
                Path(os.path.abspath(source_root)),
                source_overrides,
            )
            if override:
                used_overrides.add(override)
            destination_relative = normalize_relative_path(
                str(declaration["destination"]),
                field=f"resolved path {declaration['id']}",
            )
            declarations.append(
                {
                    "id": str(declaration["id"]),
                    "destination": destination_relative,
                    "source_kind": str(declaration["source_kind"]),
                    "component_owner": str(declaration["component_owner"]),
                }
            )
            entries.extend(
                _materialize_declaration(
                    temporary_root,
                    source,
                    destination_relative,
                    declaration,
                )
            )

        for integration in artifact["integration_overlay"]:
            _materialize_integration(
                resolution_root.resolve(),
                temporary_root,
                artifact,
                integration,
                entries,
            )

        unused = sorted(set(source_overrides) - used_overrides)
        if unused:
            raise ValueError(f"unused build source overrides: {', '.join(unused)}")
        _reject_duplicate_entries(entries)
        entries.sort(key=lambda item: str(item["path"]))
        manifest_core = {
            "schema": "facman.stage_manifest.v1",
            "resolution_digest": outputs["composition"]["resolution_digest"],
            "target_id": outputs["composition"]["target_id"],
            "product_id": outputs["composition"]["product_id"],
            "product_version": outputs["composition"]["product_version"],
            "artifact_id": artifact_id,
            "adapter": artifact["adapter"],
            "declarations": sorted(declarations, key=lambda item: str(item["id"])),
            "entries": entries,
        }
        manifest = {**manifest_core, "stage_digest": digest_value(manifest_core)}
        manifest_path = temporary_root / STAGE_MANIFEST_PATH
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(pretty_json(manifest), encoding="utf-8")
        if destination.exists():
            destination.rmdir()
        os.replace(temporary_root, destination)
    verify_stage(resolution_root, artifact_id, destination)
    return destination


def _artifact(outputs: dict[str, dict[str, Any]], artifact_id: str) -> dict[str, Any]:
    matches = [
        item
        for item in outputs["package_plan"]["artifacts"]
        if item.get("id") == artifact_id
    ]
    if len(matches) != 1:
        raise ValueError(f"resolution does not select artifact {artifact_id!r}")
    return matches[0]


def _require_empty_or_absent(path: Path, label: str) -> None:
    if path.exists():
        if path.is_symlink() or _reparse_point(path):
            raise ValueError(f"{label} must not be a symbolic link or reparse point: {path}")
        if not path.is_dir():
            raise ValueError(f"{label} exists and is not a directory: {path}")
        if any(path.iterdir()):
            raise ValueError(f"{label} must be absent or empty: {path}")


def _resolve_source(
    source_spec: str,
    source_root: Path,
    source_overrides: dict[str, Path],
) -> tuple[Path, str | None]:
    if source_spec.startswith("repo://"):
        relative = normalize_relative_path(source_spec[7:], field="repo source")
        return _contained(source_root, source_root / PurePosixPath(relative)), None
    if source_spec.startswith("build://"):
        identity = source_spec[8:]
        if not identity or "/" in identity or "\\" in identity:
            raise ValueError(f"invalid build source identity: {source_spec!r}")
        if identity not in source_overrides:
            raise ValueError(f"missing explicit build source override for {identity!r}")
        return source_overrides[identity], identity
    raise ValueError(f"unsupported source scheme: {source_spec!r}")


def _contained(root: Path, path: Path) -> Path:
    absolute_root = Path(os.path.abspath(root))
    absolute = Path(os.path.abspath(path))
    if absolute != absolute_root and absolute_root not in absolute.parents:
        raise ValueError(f"source path escapes explicit source root: {path}")
    _require_safe_directory(absolute_root)
    current = absolute.parent
    parents = []
    while current != absolute_root:
        parents.append(current)
        if current.parent == current:
            raise ValueError(f"source path escapes explicit source root: {path}")
        current = current.parent
    for parent in reversed(parents):
        _require_safe_directory(parent)
    return absolute


def _materialize_declaration(
    stage_root: Path,
    source: Path,
    destination_relative: str,
    declaration: dict[str, Any],
) -> list[dict[str, Any]]:
    source_kind = str(declaration["source_kind"])
    if source_kind == "external_reference":
        return []
    if source_kind == "file":
        record = _copy_stable_file(
            source,
            stage_root / PurePosixPath(destination_relative),
            destination_relative,
            str(declaration["component_owner"]),
            str(declaration["ownership_class"]),
            str(declaration["source"]),
            int(declaration["mode"]),
        )
        expected_hash = declaration.get("content_sha256")
        if expected_hash is not None and record["sha256"] != expected_hash:
            raise ValueError(
                f"{declaration['id']}: source hash {record['sha256']} does not match {expected_hash}"
            )
        return [record]
    if source_kind != "tree":
        raise ValueError(f"{declaration['id']}: unsupported source kind {source_kind!r}")
    _require_safe_directory(source)
    records = []
    for source_file in _walk_regular_files(source):
        relative = source_file.relative_to(source).as_posix()
        destination = f"{destination_relative}/{relative}"
        records.append(
            _copy_stable_file(
                source_file,
                stage_root / PurePosixPath(destination),
                destination,
                str(declaration["component_owner"]),
                str(declaration["ownership_class"]),
                str(declaration["source"]) + "/" + relative,
                int(declaration["mode"]),
            )
        )
    if not records:
        raise ValueError(f"{declaration['id']}: source tree is empty")
    _require_safe_directory(source)
    return records


def _materialize_integration(
    resolution_root: Path,
    stage_root: Path,
    artifact: dict[str, Any],
    integration: dict[str, Any],
    entries: list[dict[str, Any]],
) -> None:
    destination = normalize_relative_path(
        str(integration["path"]),
        field=f"artifact {artifact['id']} integration path",
    )
    source = str(integration["source"])
    if source == "stage://manifest":
        if destination != STAGE_MANIFEST_PATH:
            raise ValueError("the stage manifest must use manifest/stage.v1.json")
        return
    if source != "resolution://outputs":
        raise ValueError(f"unsupported integration source {source!r}")
    if integration.get("kind") != "generated_tree":
        raise ValueError("resolution outputs must be declared as a generated tree")
    for filename in sorted(OUTPUT_FILES.values()):
        source_file = resolution_root / filename
        path = f"{destination}/{filename}"
        entries.append(
            _copy_stable_file(
                source_file,
                stage_root / PurePosixPath(path),
                path,
                str(integration["owner"]),
                "native_package_owned",
                f"resolution://outputs/{filename}",
                0o644,
            )
        )


def _walk_regular_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for current, directories, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in sorted(directories):
            _require_safe_directory(current_path / name)
        directories[:] = sorted(directories)
        for name in sorted(filenames):
            path = current_path / name
            _require_regular_file(path)
            files.append(path)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def _reparse_point(path: Path) -> bool:
    attributes = getattr(os.lstat(path), "st_file_attributes", 0)
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & flag)


def _require_safe_directory(path: Path) -> None:
    if path.is_symlink() or _reparse_point(path):
        raise ValueError(f"source directory is a symbolic link or reparse point: {path}")
    mode = os.lstat(path).st_mode
    if not stat.S_ISDIR(mode):
        raise ValueError(f"source tree entry is not a directory: {path}")


def _require_regular_file(path: Path) -> os.stat_result:
    if path.is_symlink() or _reparse_point(path):
        raise ValueError(f"source file is a symbolic link or reparse point: {path}")
    identity = os.lstat(path)
    if not stat.S_ISREG(identity.st_mode):
        raise ValueError(f"source entry is not a regular file: {path}")
    return identity


def _open_stable_source(path: Path) -> tuple[BinaryIO, os.stat_result]:
    before = _require_regular_file(path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    handle = os.fdopen(descriptor, "rb")
    opened = os.fstat(handle.fileno())
    if _identity(before) != _identity(opened):
        handle.close()
        raise ValueError(f"source identity changed while opening: {path}")
    return handle, before


def _identity(value: os.stat_result) -> tuple[int, int, int, int]:
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns)


def _copy_stable_file(
    source: Path,
    destination: Path,
    relative: str,
    owner: str,
    ownership_class: str,
    source_spec: str,
    declared_mode: int,
) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    handle, before = _open_stable_source(source)
    try:
        with destination.open("xb") as output:
            while True:
                block = handle.read(BLOCK_SIZE)
                if not block:
                    break
                digest.update(block)
                output.write(block)
        after = os.fstat(handle.fileno())
    finally:
        handle.close()
    current = _require_regular_file(source)
    if _identity(before) != _identity(after) or _identity(before) != _identity(current):
        raise ValueError(f"source identity changed during staging: {source}")
    mode = declared_mode
    if os.name != "nt":
        destination.chmod(mode)
    return {
        "path": relative,
        "owner": owner,
        "ownership_class": ownership_class,
        "source": source_spec,
        "sha256": digest.hexdigest(),
        "size": before.st_size,
        "mode": mode,
    }


def _reject_duplicate_entries(entries: list[dict[str, Any]]) -> None:
    exact: set[str] = set()
    folded: dict[str, str] = {}
    for entry in entries:
        path = str(entry["path"])
        if path in exact:
            raise ValueError(f"staged path has more than one owner: {path}")
        exact.add(path)
        casefolded = path.casefold()
        if casefolded in folded:
            raise ValueError(f"staged paths collide under case folding: {folded[casefolded]} and {path}")
        folded[casefolded] = path


def load_stage_manifest(stage_root: Path) -> dict[str, Any]:
    root = Path(os.path.abspath(stage_root))
    _require_safe_directory(root)
    path = root / STAGE_MANIFEST_PATH
    _require_regular_file(path)
    handle, before = _open_stable_source(path)
    try:
        with handle:
            raw = handle.read()
            after = os.fstat(handle.fileno())
        current = _require_regular_file(path)
        if _identity(before) != _identity(after) or _identity(before) != _identity(current):
            raise ValueError("stage manifest identity changed while reading")
        value = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"malformed stage manifest: {exc}") from exc
    return validate_stage_manifest(value)


def validate_stage_manifest(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get("schema") != "facman.stage_manifest.v1":
        raise ValueError("stage manifest has the wrong schema")
    core = dict(value)
    recorded_digest = core.pop("stage_digest", None)
    if recorded_digest != digest_value(core):
        raise ValueError("stage manifest digest does not match its canonical content")
    return value


def verify_stage(resolution_root: Path, artifact_id: str, stage_root: Path) -> dict[str, Any]:
    outputs = load_resolution(resolution_root)
    _artifact(outputs, artifact_id)
    root = Path(os.path.abspath(stage_root))
    _require_safe_directory(root)
    manifest = load_stage_manifest(root)
    if manifest.get("resolution_digest") != outputs["composition"]["resolution_digest"]:
        raise ValueError("stage manifest resolution digest does not match")
    if manifest.get("artifact_id") != artifact_id:
        raise ValueError("stage manifest artifact identity does not match")
    expected_rows = manifest.get("entries")
    if not isinstance(expected_rows, list):
        raise ValueError("stage manifest entries must be an array")
    expected = {str(item["path"]): item for item in expected_rows if isinstance(item, dict)}
    if len(expected) != len(expected_rows):
        raise ValueError("stage manifest contains duplicate or malformed entries")
    actual_paths = []
    for path in _walk_regular_files(root):
        relative = path.relative_to(root).as_posix()
        if relative == STAGE_MANIFEST_PATH:
            continue
        actual_paths.append(relative)
    actual_set = set(actual_paths)
    if actual_set != set(expected):
        missing = sorted(set(expected) - actual_set)
        extra = sorted(actual_set - set(expected))
        raise ValueError(f"stage payload differs from manifest: missing={missing}, extra={extra}")
    for relative in actual_paths:
        path = root / PurePosixPath(relative)
        identity = _require_regular_file(path)
        record = expected[relative]
        if identity.st_size != record.get("size") or digest_file(path) != record.get("sha256"):
            raise ValueError(f"staged file does not match manifest: {relative}")
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
        raise ValueError("stage declarations do not match resolved path ownership")
    for identity, destination in resolved_declarations.items():
        if destination not in expected and not any(path.startswith(destination + "/") for path in expected):
            raise ValueError(f"resolved path declaration materialized no files: {identity}")
    return {
        "schema": "facman.stage_verification.v1",
        "artifact_id": artifact_id,
        "resolution_digest": manifest["resolution_digest"],
        "stage_digest": manifest["stage_digest"],
        "entry_count": len(expected),
        "verified": True,
    }
