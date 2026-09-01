#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Compare canonical FacMan stages with normalized setup payloads."""

from __future__ import annotations

import hashlib
import json
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Sequence


@dataclass(frozen=True)
class FileIdentity:
    path: str
    size: int
    sha256: str
    mode: int | None = None


@dataclass(frozen=True)
class PayloadAdapterContract:
    id: str
    profile_id: str
    payload_prefix_template: str
    required_adapter_files: tuple[str, ...]
    exact_adapter_file_sha256: tuple[tuple[str, str], ...]
    executable_adapter_files: tuple[str, ...]
    case_insensitive_paths: bool
    compare_posix_mode: bool

    def payload_prefix(self, version: str) -> str:
        if "{version}" in self.payload_prefix_template:
            safe_version_characters = (
                "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.-+"
            )
            if not version or any(
                character not in safe_version_characters for character in version
            ):
                raise ValueError("adapter version is empty or contains an unsafe character")
        return self.payload_prefix_template.format(version=version)


PAYLOAD_ADAPTERS = {
    "windows_setup_overlay_v1": PayloadAdapterContract(
        id="windows_setup_overlay_v1",
        profile_id="windows_product_x64",
        payload_prefix_template="facman/generations/{version}",
        required_adapter_files=(
            "facman/maintenance/FacManSetup.exe",
            "facman/state/current-generation.v1.json",
        ),
        exact_adapter_file_sha256=(),
        executable_adapter_files=(),
        case_insensitive_paths=True,
        compare_posix_mode=False,
    ),
    "macos_pkg_root_v1": PayloadAdapterContract(
        id="macos_pkg_root_v1",
        profile_id="macos_product_x64",
        payload_prefix_template="Applications",
        required_adapter_files=("usr/local/bin/facman",),
        exact_adapter_file_sha256=(
            (
                "usr/local/bin/facman",
                hashlib.sha256(
                    b'#!/bin/sh\nexec "/Applications/FacMan.app/Contents/Helpers/facman" "$@"\n'
                ).hexdigest(),
            ),
        ),
        executable_adapter_files=("usr/local/bin/facman",),
        case_insensitive_paths=True,
        compare_posix_mode=True,
    ),
    "linux_run_embedded_archive_v1": PayloadAdapterContract(
        id="linux_run_embedded_archive_v1",
        profile_id="linux_product_x64",
        payload_prefix_template="",
        required_adapter_files=(),
        exact_adapter_file_sha256=(),
        executable_adapter_files=(),
        case_insensitive_paths=False,
        compare_posix_mode=True,
    ),
}


def safe_inventory_path(value: str) -> str:
    if not value or "\\" in value or value.startswith("/"):
        raise ValueError(f"unsafe inventory path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError(f"unsafe inventory path: {value!r}")
    return path.as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_inventory(root: Path) -> list[FileIdentity]:
    if root.is_symlink():
        raise ValueError(f"inventory root is a symbolic link: {root}")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError(f"inventory root is not a directory: {root}")
    records: list[FileIdentity] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()):
        if path.is_symlink():
            raise ValueError(f"inventory contains a symbolic link: {path.relative_to(root)}")
        if path.is_file():
            records.append(
                FileIdentity(
                    path=path.relative_to(root).as_posix(),
                    size=path.stat().st_size,
                    sha256=sha256_file(path),
                    mode=stat.S_IMODE(path.stat().st_mode),
                )
            )
    return records


def inventory_digest(
    records: Sequence[FileIdentity], *, include_posix_mode: bool = False
) -> str:
    canonical: list[dict[str, object]] = []
    for item in sorted(records, key=lambda item: item.path.encode("utf-8")):
        value: dict[str, object] = {
            "path": item.path,
            "size": item.size,
            "sha256": item.sha256,
        }
        if include_posix_mode:
            value["mode"] = item.mode
        canonical.append(value)
    encoded = json.dumps(canonical, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _inventory_index(
    records: Sequence[FileIdentity], *, label: str, case_insensitive: bool
) -> tuple[dict[str, FileIdentity], list[str]]:
    indexed: dict[str, FileIdentity] = {}
    problems: list[str] = []
    for record in records:
        try:
            path = safe_inventory_path(record.path)
        except ValueError as exc:
            problems.append(f"{label}: {exc}")
            continue
        if path != record.path:
            problems.append(f"{label}: inventory path is not canonical: {record.path!r}")
        if record.size < 0:
            problems.append(f"{label}: negative file size for {path}")
        if record.mode is not None and not 0 <= record.mode <= 0o7777:
            problems.append(f"{label}: invalid POSIX mode for {path}")
        digest = record.sha256
        if (
            len(digest) != 64
            or digest != digest.lower()
            or any(character not in "0123456789abcdef" for character in digest)
        ):
            problems.append(f"{label}: invalid SHA-256 for {path}")
        key = path.casefold() if case_insensitive else path
        if key in indexed:
            problems.append(f"{label}: path collision: {indexed[key].path} and {path}")
        else:
            indexed[key] = FileIdentity(
                path=path,
                size=record.size,
                sha256=digest,
                mode=record.mode,
            )
    return indexed, problems


def payload_equivalence_receipt(
    canonical_stage: Sequence[FileIdentity],
    payload: Sequence[FileIdentity],
    *,
    adapter_id: str,
    version: str = "",
) -> dict[str, Any]:
    """Compare an extracted installer payload with one canonical product stage.

    Adapter-owned bootstrap/state files are explicit and bounded. The result is
    a contract-test receipt only: callers must separately bind exact candidate
    bytes and platform qualification evidence before making a release claim.
    """

    adapter = PAYLOAD_ADAPTERS.get(adapter_id)
    if adapter is None:
        return {
            "schema": "facman.package_payload_equivalence_tck.v1",
            "status": "fail",
            "authority": "contract_test_only_no_release_qualification",
            "adapter": adapter_id,
            "problems": [f"unknown payload adapter: {adapter_id}"],
        }
    problems: list[str] = []
    try:
        prefix = adapter.payload_prefix(version)
    except ValueError as exc:
        prefix = ""
        problems.append(str(exc))
    canonical_index, canonical_problems = _inventory_index(
        canonical_stage,
        label="canonical stage",
        case_insensitive=adapter.case_insensitive_paths,
    )
    payload_index, payload_problems = _inventory_index(
        payload,
        label="installer payload",
        case_insensitive=adapter.case_insensitive_paths,
    )
    problems.extend(canonical_problems)
    problems.extend(payload_problems)
    if not canonical_index:
        problems.append("canonical stage is empty")

    def key(value: str) -> str:
        return value.casefold() if adapter.case_insensitive_paths else value

    expected: dict[str, tuple[str, FileIdentity]] = {}
    for stage_record in canonical_index.values():
        projected = "/".join(part for part in (prefix, stage_record.path) if part)
        projected = safe_inventory_path(projected)
        projected_key = key(projected)
        if projected_key in expected:
            problems.append(f"adapter projection collides at {projected}")
        expected[projected_key] = (projected, stage_record)

    adapter_files = {key(path): path for path in adapter.required_adapter_files}
    exact_adapter_hashes = {
        key(path): digest for path, digest in adapter.exact_adapter_file_sha256
    }
    executable_adapter_files = {key(path) for path in adapter.executable_adapter_files}
    for adapter_key, adapter_path in adapter_files.items():
        adapter_record = payload_index.get(adapter_key)
        if adapter_record is None:
            problems.append(f"installer payload is missing adapter-owned file: {adapter_path}")
        elif adapter_record.path != adapter_path:
            problems.append(
                f"installer payload adapter-owned path spelling differs: "
                f"{adapter_record.path} != {adapter_path}"
            )
        elif adapter_record.size == 0:
            problems.append(f"installer payload adapter-owned file is empty: {adapter_path}")
        else:
            expected_hash = exact_adapter_hashes.get(adapter_key)
            if expected_hash is not None and adapter_record.sha256 != expected_hash:
                problems.append(
                    f"installer payload adapter-owned content differs: {adapter_path}"
                )
            if adapter_key in executable_adapter_files:
                if adapter_record.mode is None or not adapter_record.mode & 0o111:
                    problems.append(
                        f"installer payload adapter-owned file is not executable: {adapter_path}"
                    )

    logical_payload: list[FileIdentity] = []
    for expected_key, (expected_path, stage_record) in expected.items():
        payload_record = payload_index.get(expected_key)
        if payload_record is None:
            problems.append(f"installer payload is missing canonical file: {expected_path}")
            continue
        if payload_record.path != expected_path:
            problems.append(
                f"installer payload path spelling differs: {payload_record.path} != {expected_path}"
            )
        if payload_record.size != stage_record.size or payload_record.sha256 != stage_record.sha256:
            problems.append(f"installer payload content differs: {expected_path}")
        if adapter.compare_posix_mode:
            if stage_record.mode is None or payload_record.mode is None:
                problems.append(f"installer payload POSIX mode is unspecified: {expected_path}")
            elif payload_record.mode != stage_record.mode:
                problems.append(f"installer payload POSIX mode differs: {expected_path}")
        logical_payload.append(
            FileIdentity(
                stage_record.path,
                payload_record.size,
                payload_record.sha256,
                payload_record.mode,
            )
        )
    allowed_keys = set(expected) | set(adapter_files)
    for unexpected_key in sorted(set(payload_index) - allowed_keys):
        problems.append(
            f"installer payload has an unowned extra file: {payload_index[unexpected_key].path}"
        )

    stage_records = sorted(canonical_index.values(), key=lambda item: item.path.encode("utf-8"))
    logical_records = sorted(logical_payload, key=lambda item: item.path.encode("utf-8"))
    return {
        "schema": "facman.package_payload_equivalence_tck.v1",
        "status": "pass" if not problems else "fail",
        "authority": "contract_test_only_no_release_qualification",
        "adapter": adapter.id,
        "profile": adapter.profile_id,
        "canonical_file_count": len(stage_records),
        "canonical_stage_digest": inventory_digest(
            stage_records,
            include_posix_mode=adapter.compare_posix_mode,
        ),
        "payload_runtime_file_count": len(logical_records),
        "payload_runtime_digest": inventory_digest(
            logical_records,
            include_posix_mode=adapter.compare_posix_mode,
        ),
        "adapter_owned_files": list(adapter.required_adapter_files),
        "problems": problems,
    }
