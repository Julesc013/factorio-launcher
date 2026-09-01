#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate unpublished product-candidate evidence and bundle closure."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from tools.package.payload_equivalence import PAYLOAD_ADAPTERS


SEMVER = re.compile(
    r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
)
ASSET_SUFFIXES = {
    "windows": ("windows-x64-portable.zip", "windows-x64-setup.exe"),
    "macos": ("macos-x64-portable.zip", "macos-x64-setup.pkg"),
    "linux": ("linux-x64-portable.tar.zst", "linux-x64-setup.run"),
}
ADAPTERS = {
    "windows": "windows_setup_overlay_v1",
    "macos": "macos_pkg_root_v1",
    "linux": "linux_run_embedded_archive_v1",
}
AUTHORITY = {
    "tag": False,
    "release": False,
    "publication": False,
    "signing": False,
    "support": False,
}
BUNDLE_SCHEMA = "facman.product_candidate_bundle.v1"
PLATFORM_SCHEMA = "facman.product_candidate_platform.v1"
CANDIDATE_CLASS = "unsigned_unpublished_manual_workflow"
GITHUB_FIELDS = {"repository", "workflow_ref", "run_id", "run_attempt", "job"}
EQUIVALENCE_FIELDS = {
    "schema", "status", "authority", "adapter", "profile",
    "canonical_file_count", "canonical_stage_digest",
    "payload_runtime_file_count", "payload_runtime_digest",
    "adapter_owned_files", "canonical_artifact", "payload_artifact", "problems",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON record is not an object: {path}")
    return value


def file_record(path: Path) -> dict[str, object]:
    if not path.is_file() or path.is_symlink() or path.stat().st_size == 0:
        raise ValueError(f"candidate file is empty, missing, or linked: {path}")
    return {"filename": path.name, "bytes": path.stat().st_size, "sha256": sha256_file(path)}


def validate_identity(version: str, source_revision: str) -> None:
    if not isinstance(version, str) or not SEMVER.fullmatch(version):
        raise ValueError(f"invalid candidate SemVer: {version!r}")
    if not isinstance(source_revision, str) or not re.fullmatch(
        r"[0-9a-f]{40}", source_revision
    ):
        raise ValueError("source revision must be a lowercase full Git SHA")


def github_provenance(
    repository: str,
    workflow_ref: str,
    run_id: str,
    run_attempt: str,
    job: str,
) -> dict[str, str]:
    if not all(
        isinstance(value, str)
        for value in (repository, workflow_ref, run_id, run_attempt, job)
    ):
        raise ValueError("GitHub provenance values must be strings")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise ValueError("GitHub repository identity is invalid")
    prefix = f"{repository}/.github/workflows/"
    if not re.fullmatch(
        re.escape(prefix) + r"[A-Za-z0-9_.-]+\.ya?ml@[^\s]+", workflow_ref
    ):
        raise ValueError("GitHub workflow_ref does not bind a workflow path and ref")
    for label, value in (("run_id", run_id), ("run_attempt", run_attempt)):
        if not value.isdigit() or int(value) < 1 or str(int(value)) != value:
            raise ValueError(f"GitHub {label} must be a canonical positive integer")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", job):
        raise ValueError("GitHub job identity is invalid")
    return {
        "repository": repository,
        "workflow_ref": workflow_ref,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "job": job,
    }


def canonical_provenance(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != GITHUB_FIELDS:
        raise ValueError(f"{label} GitHub provenance fields differ")
    try:
        expected = github_provenance(
            value["repository"], value["workflow_ref"], value["run_id"],
            value["run_attempt"], value["job"],
        )
    except ValueError as exc:
        raise ValueError(f"{label} GitHub provenance is invalid: {exc}") from exc
    validate_provenance(value, expected, label)
    return expected


def validate_provenance(value: Any, expected: dict[str, str], label: str) -> None:
    if value != expected:
        raise ValueError(f"{label} GitHub provenance differs from the requested run")


def validate_equivalence(
    value: dict[str, Any], platform: str, assets: list[dict[str, object]]
) -> None:
    adapter_id = ADAPTERS[platform]
    adapter = PAYLOAD_ADAPTERS[adapter_id]
    count = value.get("canonical_file_count")
    payload_count = value.get("payload_runtime_file_count")
    digest = value.get("canonical_stage_digest")
    if (
        set(value) != EQUIVALENCE_FIELDS
        or not isinstance(assets, list)
        or len(assets) != 2
        or value.get("schema") != "facman.package_payload_equivalence_tck.v1"
        or value.get("status") != "pass"
        or value.get("authority") != "contract_test_only_no_release_qualification"
        or value.get("adapter") != adapter_id
        or value.get("profile") != adapter.profile_id
        or value.get("problems") != []
        or not isinstance(count, int)
        or isinstance(count, bool)
        or count < 1
        or not isinstance(payload_count, int)
        or isinstance(payload_count, bool)
        or payload_count != count
        or not isinstance(digest, str)
        or not re.fullmatch(r"[0-9a-f]{64}", digest)
        or value.get("payload_runtime_digest") != digest
        or value.get("adapter_owned_files") != list(adapter.required_adapter_files)
        or value.get("canonical_artifact") != assets[0]
        or value.get("payload_artifact") != assets[1]
    ):
        raise ValueError(f"payload-equivalence receipt is invalid for {platform}")


def validate_platform_evidence(
    value: dict[str, Any], platform: str, version: str, revision: str, tree: str,
    github: dict[str, str], assets: list[dict[str, object]], equivalence_sha: str,
) -> None:
    expected_binding = {
        "adapter": ADAPTERS[platform],
        "profile": PAYLOAD_ADAPTERS[ADAPTERS[platform]].profile_id,
        "sha256": equivalence_sha,
    }
    if (
        set(value) != {
            "schema", "status", "candidate_class", "version", "platform",
            "source_revision", "source_tree", "github", "assets",
            "payload_equivalence", "authority",
        }
        or value.get("schema") != PLATFORM_SCHEMA
        or value.get("status") != "pass"
        or value.get("candidate_class") != CANDIDATE_CLASS
        or value.get("version") != version
        or value.get("source_revision") != revision
        or value.get("source_tree") != tree
        or value.get("platform") != platform
        or value.get("authority") != AUTHORITY
        or value.get("assets") != assets
        or value.get("payload_equivalence") != expected_binding
    ):
        raise ValueError(f"candidate platform evidence is invalid: {platform}")
    validate_provenance(value.get("github"), github, platform)


def expected_asset_names(version: str) -> set[str]:
    return {
        f"FacMan-{version}-{suffix}"
        for suffixes in ASSET_SUFFIXES.values()
        for suffix in suffixes
    }


def expected_evidence_names() -> set[str]:
    return {
        *(f"{platform}-candidate-evidence.v1.json" for platform in ASSET_SUFFIXES),
        *(f"{platform}-payload-equivalence.v1.json" for platform in ASSET_SUFFIXES),
    }


def _record_index(value: Any, label: str) -> dict[str, dict[str, object]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError(f"bundle {label} must be an array of records")
    result = {str(item.get("filename", "")): item for item in value}
    if len(result) != len(value) or "" in result:
        raise ValueError(f"bundle {label} filenames must be unique and non-empty")
    return result


def _verify_recorded_files(root: Path, records: dict[str, dict[str, object]]) -> None:
    for name, expected in records.items():
        if file_record(root / name) != expected:
            raise ValueError(f"bundle file identity differs: {name}")


def verify_bundle(root: Path) -> dict[str, Any]:
    if root.is_symlink():
        raise ValueError("candidate bundle root must not be a symbolic link")
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("candidate bundle root is not a directory")
    manifest_path = root / "product-candidate-bundle.v1.json"
    record = read_json(manifest_path)
    if manifest_path.read_text(encoding="utf-8") != (
        json.dumps(record, indent=2, sort_keys=True) + "\n"
    ):
        raise ValueError("candidate bundle record is not canonical JSON")
    version = record.get("version")
    revision = record.get("source_revision")
    validate_identity(version, revision)
    if (
        set(record) != {
            "schema", "status", "candidate_class", "version", "source_revision",
            "source_tree", "github", "platform_job", "assets", "evidence",
            "checksum", "payload_equivalence_adapters", "authority",
        }
        or record.get("schema") != BUNDLE_SCHEMA
        or record.get("status") != "pass"
        or record.get("candidate_class") != CANDIDATE_CLASS
        or record.get("authority") != AUTHORITY
        or record.get("payload_equivalence_adapters") != list(ADAPTERS.values())
        or not isinstance(record.get("source_tree"), str)
        or not re.fullmatch(r"[0-9a-f]{40}", record["source_tree"])
    ):
        raise ValueError("candidate bundle record has invalid identity or authority")
    github = canonical_provenance(record.get("github"), "bundle")
    platform_job = record.get("platform_job")
    if not isinstance(platform_job, str):
        raise ValueError("candidate platform job identity must be a string")
    platform_github = github_provenance(
        github["repository"], github["workflow_ref"], github["run_id"],
        github["run_attempt"], platform_job,
    )
    if platform_job == github["job"]:
        raise ValueError("candidate platform and bundle jobs must be distinct")
    assets = _record_index(record.get("assets"), "assets")
    evidence = _record_index(record.get("evidence"), "evidence")
    if set(assets) != expected_asset_names(version) or set(evidence) != expected_evidence_names():
        raise ValueError("candidate bundle asset or evidence allowlist differs")
    checksum = record.get("checksum")
    if not isinstance(checksum, dict) or checksum.get("filename") != "SHA256SUMS":
        raise ValueError("candidate bundle checksum record is invalid")
    expected_files = set(assets) | set(evidence) | {"SHA256SUMS", manifest_path.name}
    observed_files: set[str] = set()
    for path in root.iterdir():
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"candidate bundle has non-file or linked output: {path.name}")
        observed_files.add(path.name)
    if observed_files != expected_files:
        raise ValueError("candidate bundle output allowlist differs")
    _verify_recorded_files(root, assets | evidence)
    if file_record(root / "SHA256SUMS") != checksum:
        raise ValueError("candidate bundle checksum identity differs")
    expected_sums = "".join(
        f"{item['sha256']}  {item['filename']}\n"
        for item in list(assets.values()) + list(evidence.values())
    )
    if (root / "SHA256SUMS").read_text(encoding="utf-8") != expected_sums:
        raise ValueError("candidate bundle checksum content differs")
    for platform in ASSET_SUFFIXES:
        platform_record = read_json(root / f"{platform}-candidate-evidence.v1.json")
        platform_assets = [
            assets[f"FacMan-{version}-{suffix}"] for suffix in ASSET_SUFFIXES[platform]
        ]
        equivalence_path = root / f"{platform}-payload-equivalence.v1.json"
        equivalence = read_json(equivalence_path)
        validate_equivalence(equivalence, platform, platform_assets)
        validate_platform_evidence(
            platform_record, platform, version, revision, str(record["source_tree"]),
            platform_github, platform_assets, sha256_file(equivalence_path),
        )
    return record
