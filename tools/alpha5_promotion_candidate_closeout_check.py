#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the source-bound, non-authorizing FacMan alpha.5 candidate closeout."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "release/index/alpha5_promotion_candidate_closeout.v1.toml"
SCHEMA = (
    ROOT
    / "contracts/schema/release/alpha5_promotion_candidate_closeout.v1.schema.json"
)
RELEASE_INDEX = ROOT / "release/index/release_index.v1.toml"
READINESS = ROOT / "release/index/foundation_beta_readiness.v1.toml"
PACKAGE_PRODUCERS = ROOT / "release/index/package_producers.v1.toml"
PROJECT = ROOT / "release/index/project_status.v2.toml"
PLAN = ROOT / "release/index/plan.v1.toml"
VERSION_TRAIN = ROOT / "release/index/version_train.v1.toml"
PROVIDER_LOCK = ROOT / "release/index/providers.lock.v2.toml"
WORKSPACE_LOCK = ROOT / "release/index/workspace_lock.v1.toml"
ARCHIVE_INDEX = (
    ROOT
    / ".aide/history/facman-0-1-alpha5-foundation-closed-2026-09-02/index.json"
)

WORK_UNIT = "FACMAN-0.1-ALPHA5-PROMOTION-CANDIDATE-CLOSEOUT-01"
PRODUCER = "FACMAN-0.1-BETA-READINESS-01"
D = "d5bd6a18abd21d48359a05be6c3798fa224e95e3"
M = "a7a518dbfe2a6d54da7b9c84fbd318300265e31d"
S = "43af71f8231c5a1b843636df7fd0ab8a6040d25c"
T = "1ebcd2b230ed188e021880ffa4c438de2ede655b"
RUN_ID = 33576140943
ATTEMPT = 1
RECEIPT_PATH = "release/index/alpha5_promotion_candidate_closeout.v1.toml"
CHECKPOINT = "facman-0-1-alpha5-foundation-closed-2026-09-02"
ARCHIVE_SHA256 = "eecc84950b0905e14f22ea5ad35066ec39cbd8fabf1d75ccb5a8b62164435c73"
PROVIDER_LOCK_SHA256 = (
    "d33943841431afdeffb7961c7453d8999619ef371793a6310ad2c2952b118f00"
)
WORKSPACE_LOCK_SHA256 = (
    "b1590cc87bd50e5913196f1e3aa7a044028b30e9f1354b46a355b3db3f42c9bf"
)

EXPECTED_TOPOLOGY = {
    "repair_dev_revision": D,
    "repair_head_revision": "f43049d4db4b20c14f0a637bf426f95873ba7892",
    "main_candidate_revision": M,
    "dev_sync_revision": S,
    "source_tree": T,
    "repair_pull_request": 236,
    "promotion_pull_request": 237,
    "sync_pull_request": 238,
    "repair_parents": [
        "f8ae04ac2d20ea3f4948222da4e0149629755a34",
        "f43049d4db4b20c14f0a637bf426f95873ba7892",
    ],
    "main_parents": ["680c22aa0a457668475d8087ee28b9cb6e0791d6", D],
    "sync_parents": [D, M],
    "repair_tree_equals_source_tree": True,
    "main_tree_equals_source_tree": True,
    "sync_tree_equals_source_tree": True,
}
EXPECTED_COUNTS = {
    "job_count": 5,
    "artifact_count": 4,
    "bundle_file_count": 14,
    "failure_chain_count": 3,
    "provider_count": 2,
}
EXPECTED_NON_CIRCULAR = {
    "candidate_source_is_closeout_revision": False,
    "candidate_source_is_dev_sync_revision": False,
    "closeout_revision_candidate_qualified": False,
    "synchronized_tree_extends_revision_qualification": False,
    "current_main_after_closeout_qualified_by_this_receipt": False,
    "future_revision_requires_new_candidate_run": True,
}
EXPECTED_AUTHORITY = {
    "tag": False,
    "release": False,
    "beta_tag": False,
    "signing": False,
    "notarization": False,
    "publication": False,
    "support": False,
    "human_verdict": False,
    "factorio_execution": False,
    "route_promotion": False,
    "live_managed_install_acceptance": False,
}
EXPECTED_MANIFEST_AUTHORITY = {
    "tag": False,
    "release": False,
    "publication": False,
    "signing": False,
    "support": False,
}
EXPECTED_CANDIDATE = {
    "workflow_id": 347619223,
    "workflow_name": "product-candidate",
    "workflow_path": ".github/workflows/product-candidate.yml",
    "workflow_state": "active",
    "workflow_blob": "35c98c40fd8710d567ecd2157584c9ea5c56dfa2",
    "workflow_file_sha256": (
        "11f56d06b3154c883beee20d278ae4a36690680c7718136478f815c416ebb00d"
    ),
    "workflow_ref": (
        "Julesc013/factorio-launcher/.github/workflows/"
        "product-candidate.yml@refs/heads/main"
    ),
    "ref": "main",
    "event": "workflow_dispatch",
    "dispatch_timestamp": "2026-09-02T00:38:10.3149216Z",
    "run_id": RUN_ID,
    "run_number": 9,
    "attempt": ATTEMPT,
    "status": "completed",
    "conclusion": "success",
    "head_branch": "main",
    "head_sha": M,
    "head_tree": T,
    "actor": "Julesc013",
    "triggering_actor": "Julesc013",
    "created_at": "2026-09-02T00:38:12Z",
    "run_started_at": "2026-09-02T00:38:12Z",
    "updated_at": "2026-09-02T00:45:42Z",
    "url": (
        "https://github.com/Julesc013/factorio-launcher/actions/runs/33576140943"
    ),
    "existing_run_ids_before_dispatch": [33567017006, 33557664813, 33544283452],
    "active_overlap_before_dispatch": 0,
    "active_overlap_after_completion": 0,
    "dispatch_count": 1,
}
EXPECTED_FAILURES = [
    {
        "sequence": 1,
        "run_created": False,
        "run_id": 0,
        "attempt": 0,
        "conclusion": "not_created_http_422",
        "request_timestamp": "UNRECORDED",
        "response_body": "UNRECORDED",
        "evidence_source": "github_pull_request_230_body",
        "failure": "workflow_dispatch_http_422_before_run_creation",
        "repair_revision": "c18d6743c306b884615b7134504a00f7716b818f",
        "repair_sync_revision": "d38dbc30650c8cdb9d40f711c6677734d5247c2b",
        "successor_candidate_revision": (
            "67e25b38130a2f939bdbf67a2623bb71a41ab0bd"
        ),
    },
    {
        "sequence": 2,
        "run_created": True,
        "run_id": 33557664813,
        "attempt": 1,
        "source_revision": "67e25b38130a2f939bdbf67a2623bb71a41ab0bd",
        "created_at": "2026-09-01T20:50:29Z",
        "updated_at": "2026-09-01T20:50:43Z",
        "conclusion": "failure",
        "evidence_source": "github_actions_run_33557664813",
        "failure": "contract_job_repository_module_import",
        "repair_revision": "10da832ef7777f6224de54fb01c972991aae297c",
        "successor_candidate_revision": (
            "680c22aa0a457668475d8087ee28b9cb6e0791d6"
        ),
    },
    {
        "sequence": 3,
        "run_created": True,
        "run_id": 33567017006,
        "attempt": 1,
        "source_revision": "680c22aa0a457668475d8087ee28b9cb6e0791d6",
        "created_at": "2026-09-01T22:35:08Z",
        "updated_at": "2026-09-01T22:39:04Z",
        "conclusion": "failure",
        "evidence_source": "github_actions_run_33567017006",
        "windows_failure": (
            "checkout_owned_credential_include_in_source_observation"
        ),
        "macos_failure": "runner_temporary_root_resolved_through_symlink",
        "linux_artifact_id": 9823610585,
        "linux_artifact_digest": (
            "sha256:e46a2e644613d376f59cbef1491407bb72709790df8f90e661c3e3158b6693ea"
        ),
        "repair_revision": "f43049d4db4b20c14f0a637bf426f95873ba7892",
        "repair_dev_revision": D,
        "successor_candidate_revision": M,
    },
]
EXPECTED_JOBS = [
    (100080412106, "Version-current candidate contract", "contract",
     "2026-09-02T00:38:15Z", "2026-09-02T00:38:26Z", 1000038158),
    (100080456660, "Linux x64 unsigned preview candidate", "platform",
     "2026-09-02T00:38:29Z", "2026-09-02T00:42:12Z", 1000038160),
    (100080456693, "macOS Intel unsigned preview candidate", "platform",
     "2026-09-02T00:38:31Z", "2026-09-02T00:43:10Z", 1000038159),
    (100080456726, "Windows x64 unsigned candidate", "platform",
     "2026-09-02T00:38:29Z", "2026-09-02T00:45:21Z", 1000038161),
    (100081901409, "Exact six-asset unpublished candidate bundle", "bundle",
     "2026-09-02T00:45:26Z", "2026-09-02T00:45:41Z", 1000038162),
]
EXPECTED_JOB_ROWS = [
    {
        "id": job_id,
        "name": name,
        "logical_job": logical,
        "status": "completed",
        "conclusion": "success",
        "started_at": started,
        "completed_at": completed,
        "runner_id": runner_id,
        "runner_name": f"GitHub Actions {runner_id}",
        "runner_group_id": 0,
        "runner_group_name": "GitHub Actions",
        "url": (
            "https://github.com/Julesc013/factorio-launcher/actions/runs/"
            f"{RUN_ID}/job/{job_id}"
        ),
    }
    for job_id, name, logical, started, completed, runner_id in EXPECTED_JOBS
]


def _artifact(
    kind: str,
    artifact_id: int,
    node_id: str,
    name: str,
    size: int,
    created: str,
    updated: str,
    expires: str,
    digest: str,
) -> dict[str, Any]:
    api = (
        "https://api.github.com/repos/Julesc013/factorio-launcher/actions/artifacts/"
        f"{artifact_id}"
    )
    return {
        "kind": kind,
        "id": artifact_id,
        "node_id": node_id,
        "name": name,
        "size_in_bytes": size,
        "url": api,
        "archive_download_url": f"{api}/zip",
        "expired": False,
        "created_at": created,
        "updated_at": updated,
        "expires_at": expires,
        "digest": digest,
        "workflow_run_id": RUN_ID,
        "workflow_head_branch": "main",
        "workflow_head_sha": M,
        "workflow_repository_id": 1293124404,
        "workflow_head_repository_id": 1293124404,
    }


EXPECTED_ARTIFACTS = [
    _artifact(
        "final_bundle", 9826850751, "MDg6QXJ0aWZhY3Q5ODI2ODUwNzUx",
        "FacMan-0.1.0-alpha.5-unsigned-unpublished-candidate-"
        "33576140943-1-a7a518dbfe2a6d54da7b9c84fbd318300265e31d",
        39362081, "2026-09-02T00:45:39Z", "2026-09-02T00:45:39Z",
        "2026-09-16T00:45:36Z",
        "sha256:2afe4529f056ac4400352400418e5cede776146e9ef803aa4901cc76944f71c5",
    ),
    _artifact(
        "windows_input", 9826842304, "MDg6QXJ0aWZhY3Q5ODI2ODQyMzA0",
        "product-candidate-input-windows-33576140943-1-"
        "a7a518dbfe2a6d54da7b9c84fbd318300265e31d",
        16009430, "2026-09-02T00:45:17Z", "2026-09-02T00:45:17Z",
        "2026-09-16T00:45:16Z",
        "sha256:a2b58ef796dfc7daf35d0993e02bdf5807937cf1c3dea5ae035fd4d45b510f82",
    ),
    _artifact(
        "macos_input", 9826791575, "MDg6QXJ0aWZhY3Q5ODI2NzkxNTc1",
        "product-candidate-input-macos-33576140943-1-"
        "a7a518dbfe2a6d54da7b9c84fbd318300265e31d",
        13386375, "2026-09-02T00:43:06Z", "2026-09-02T00:43:06Z",
        "2026-09-16T00:43:01Z",
        "sha256:530533736e47233f0f005a27b576760261bef44a7b3ace19c386047a7804bf8b",
    ),
    _artifact(
        "linux_input", 9826768803, "MDg6QXJ0aWZhY3Q5ODI2NzY4ODAz",
        "product-candidate-input-linux-33576140943-1-"
        "a7a518dbfe2a6d54da7b9c84fbd318300265e31d",
        9964384, "2026-09-02T00:42:09Z", "2026-09-02T00:42:09Z",
        "2026-09-16T00:42:08Z",
        "sha256:6c8f0854d863de5bea7d9b5d97ad74be3c8720020c815b531b43835987065e0d",
    ),
]


def _file(role: str, filename: str, size: int, digest: str) -> dict[str, Any]:
    return {"role": role, "filename": filename, "bytes": size, "sha256": digest}


EXPECTED_FILES = [
    _file("product", "FacMan-0.1.0-alpha.5-linux-x64-portable.tar.zst", 4980269,
          "9b755ba86219196c539f87d2f84cd52b8ddda9ce8b925c8fcb54fea09d8702d7"),
    _file("product", "FacMan-0.1.0-alpha.5-linux-x64-setup.run", 4985808,
          "8f5b6cf5c3b718504d894a28e74cb6bdfc9a9c95cacfd038d59df96ec74f38a8"),
    _file("product", "FacMan-0.1.0-alpha.5-macos-x64-portable.zip", 6696326,
          "7875f80208d40d58749d88802e26722a5ea548b11c4afe38ed496e6a5e7ccc95"),
    _file("product", "FacMan-0.1.0-alpha.5-macos-x64-setup.pkg", 6697281,
          "7586af881dae0868e600fa19e51197c23db46b02989c40ddf92e2c37db06afd4"),
    _file("product", "FacMan-0.1.0-alpha.5-windows-x64-portable.zip", 7739882,
          "58672cf8a332d1d8b5229401e1b38ff423a9fcbd72222d64521dc2a304af26de"),
    _file("product", "FacMan-0.1.0-alpha.5-windows-x64-setup.exe", 16242657,
          "7c0a2cdf0395fae16af71499bc36cd57adc23ef96e5c07bb2cbd601bd727b32f"),
    _file("evidence", "linux-candidate-evidence.v1.json", 1282,
          "dc2974ac86317f86ef5df8cfaec9c6b0cc591cda6044a9ffa493e94c5a2b446c"),
    _file("evidence", "linux-payload-equivalence.v1.json", 920,
          "d32d2c7bb00a131db8465bd0ccd1e23e5b82483e76c42bf0a5b81226f52f77c7"),
    _file("evidence", "macos-candidate-evidence.v1.json", 1266,
          "1ceb8e806d410b82ce70bbd028fbe7b413001f3f88fef7eb47f081fd2580356e"),
    _file("evidence", "macos-payload-equivalence.v1.json", 934,
          "9a51a1b90a0458f163e19bf0d8d855d8c6b5cd96e5eb073c56ae2f25d8006a9d"),
    _file("manifest", "product-candidate-bundle.v1.json", 3163,
          "8791fdd14b088cd8d4a89ae791b71327a5c9007bc495fbee59fd79f17528eb36"),
    _file("checksum", "SHA256SUMS", 1260,
          "24e2aa5abf9f35ea6dfe6298a817cc50c846a6506be14ed5da2e46d48fd1b357"),
    _file("evidence", "windows-candidate-evidence.v1.json", 1282,
          "785d85fdc4f70573a3e330abb3ebe26d9907436da96baeaa7fe9a9de5ef470bd"),
    _file("evidence", "windows-payload-equivalence.v1.json", 1011,
          "ca579b0a0d87d8e606210e54a983662f563bf38e5f0b6c1f914bdd3d6cf86055"),
]
EXPECTED_EQUIVALENCE = [
    {
        "platform": "linux", "profile": "linux_product_x64",
        "adapter": "linux_run_embedded_archive_v1", "status": "pass",
        "authority": "contract_test_only_no_release_qualification",
        "canonical_file_count": 53, "payload_file_count": 53,
        "canonical_digest": "4011b135f971109c8f942799428f694ddd8707963fa44ae29e0ab07c741a7a41",
        "payload_digest": "4011b135f971109c8f942799428f694ddd8707963fa44ae29e0ab07c741a7a41",
        "adapter_owned_files": [], "problem_count": 0,
    },
    {
        "platform": "macos", "profile": "macos_product_x64",
        "adapter": "macos_pkg_root_v1", "status": "pass",
        "authority": "contract_test_only_no_release_qualification",
        "canonical_file_count": 44, "payload_file_count": 44,
        "canonical_digest": "4db2e53fbf90ed0da5c5d213190da3885d7ad3f1f7f5ed459b6037577e369f8a",
        "payload_digest": "4db2e53fbf90ed0da5c5d213190da3885d7ad3f1f7f5ed459b6037577e369f8a",
        "adapter_owned_files": ["usr/local/bin/facman"], "problem_count": 0,
    },
    {
        "platform": "windows", "profile": "windows_product_x64",
        "adapter": "windows_setup_overlay_v1", "status": "pass",
        "authority": "contract_test_only_no_release_qualification",
        "canonical_file_count": 106, "payload_file_count": 106,
        "canonical_digest": "d699b2c45f67205dcef58e53f78b27dbb59effe792f8692c3d26327486600e03",
        "payload_digest": "d699b2c45f67205dcef58e53f78b27dbb59effe792f8692c3d26327486600e03",
        "adapter_owned_files": [
            "facman/maintenance/FacManSetup.exe",
            "facman/state/current-generation.v1.json",
        ],
        "problem_count": 0,
    },
]
EXPECTED_PROVIDER_BINDING = {
    "provider_lock_path": "release/index/providers.lock.v2.toml",
    "provider_lock_sha256": PROVIDER_LOCK_SHA256,
    "workspace_lock_path": "release/index/workspace_lock.v1.toml",
    "workspace_lock_sha256": WORKSPACE_LOCK_SHA256,
    "pins_atomically_reconciled": True,
}
EXPECTED_PROVIDERS = [
    {
        "id": "universal_launcher",
        "workspace_pin": "5479939ca5cbc9ee0f901608a92012778b4752ae",
        "workspace_tree": "7728e4d415539a0f24e6f17aa7d22be00cc99d80",
        "source_revision": "5479939ca5cbc9ee0f901608a92012778b4752ae",
        "source_tree": "7728e4d415539a0f24e6f17aa7d22be00cc99d80",
        "package_version": "1.9.1",
        "package_digest": "012fd91d49a235493223a32793b536aa73437d759ad627ce1180db3b570f4a57",
        "abi_version": "1.9",
        "abi_manifest_digest": "ce17990b20ee3730cb73a709d8a649fdc5234df8b8e9735bf9a6ea0ea992210e",
        "contract_digest": "edb62fda28fac02bf7e07a6295c867b3813f4881886c6783f379b52b5c8761f9",
    },
    {
        "id": "universal_setup",
        "workspace_pin": "d2a2aae7e61c47035c92334b0522143b4fea3880",
        "workspace_tree": "291d63214cdd0cd3d15c809de5744ee3514fb2b2",
        "source_revision": "d2a2aae7e61c47035c92334b0522143b4fea3880",
        "source_tree": "291d63214cdd0cd3d15c809de5744ee3514fb2b2",
        "package_version": "1.0.0",
        "package_digest": "04c61554ad37ef7fb3def46485e3558bb37edfc06347c7fc9ef0618e56294e1e",
        "abi_version": "1.0",
        "abi_manifest_digest": "07c2d023d4ecf6854301f10babb779a8ccd20eafb8f088a4cc29e361ca7beea0",
        "contract_digest": "045a570f305a9e578dccbe22ec1d3c1945d6743a5e8d55d3c754dc3c2efd6f56",
    },
]
EXPECTED_ARCHIVE = {
    "path": (
        ".aide/history/facman-0-1-alpha5-foundation-closed-2026-09-02/"
        "index.json"
    ),
    "schema": "aide.history_index.v1",
    "checkpoint": CHECKPOINT,
    "hash_canonicalization": "text_lf_v1",
    "index_sha256": ARCHIVE_SHA256,
    "task_count": 2,
    "immutable": True,
}
EXPECTED_BUNDLE = {
    "final_artifact_id": 9826850751,
    "final_artifact_name": EXPECTED_ARTIFACTS[0]["name"],
    "final_artifact_digest": EXPECTED_ARTIFACTS[0]["digest"],
    "only_final_artifact_downloaded": True,
    "marker_root_locator": (
        "facman-development://tasks/"
        "FACMAN-0.1-BETA-CANDIDATE-33576140943-20260902T0046Z"
    ),
    "download_root_locator": (
        "facman-development://tasks/"
        "FACMAN-0.1-BETA-CANDIDATE-33576140943-20260902T0046Z/bundle"
    ),
    "marker_schema": "facman.development_root.v1",
    "marker_owner": "facman-development",
    "marker_kind": "task-root",
    "marker_task_id": "FACMAN-0.1-BETA-CANDIDATE-33576140943-20260902T0046Z",
    "marker_created_at": "2026-09-02T00:46:49.451735Z",
    "verification_tool": "tools/product_candidate.py",
    "verification_result": "pass",
    "manifest_schema": "facman.product_candidate_bundle.v1",
    "manifest_status": "pass",
    "candidate_class": "unsigned_unpublished_manual_workflow",
    "version": "0.1.0-alpha.5",
    "source_revision": M,
    "source_tree": T,
    "github_repository": "Julesc013/factorio-launcher",
    "github_workflow_ref": EXPECTED_CANDIDATE["workflow_ref"],
    "github_run_id": RUN_ID,
    "github_run_attempt": ATTEMPT,
    "github_job": "bundle",
    "platform_job": "platform",
    "payload_equivalence_adapters": [
        "windows_setup_overlay_v1",
        "macos_pkg_root_v1",
        "linux_run_embedded_archive_v1",
    ],
    "product_file_count": 6,
    "evidence_file_count": 6,
    "checksum_file_count": 1,
    "manifest_file_count": 1,
    "file_count": 14,
    "nested_directory_count": 0,
    "total_bytes": 47353341,
    "manifest_filename": "product-candidate-bundle.v1.json",
    "manifest_bytes": 3163,
    "manifest_sha256": "8791fdd14b088cd8d4a89ae791b71327a5c9007bc495fbee59fd79f17528eb36",
    "checksum_filename": "SHA256SUMS",
    "checksum_bytes": 1260,
    "checksum_sha256": "24e2aa5abf9f35ea6dfe6298a817cc50c846a6506be14ed5da2e46d48fd1b357",
    "manifest_authority": EXPECTED_MANIFEST_AUTHORITY,
}


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        value = tomllib.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a TOML table")
    return value


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text_lf(path: Path) -> str:
    """Hash UTF-8 text after the archive's declared text_lf_v1 conversion."""
    text = path.read_bytes().decode("utf-8")
    canonical = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def schema_problems(value: dict[str, Any]) -> list[str]:
    schema = load_json(SCHEMA)
    validator = jsonschema.Draft202012Validator(
        schema, format_checker=jsonschema.FormatChecker()
    )
    return [
        "schema: " + error.message
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.path))
    ]


def _exact(problems: list[str], actual: Any, expected: Any, label: str) -> None:
    if actual != expected:
        problems.append(f"{label} must equal the exact recorded value")


def validate_receipt(value: dict[str, Any]) -> list[str]:
    problems = schema_problems(value)
    _exact(problems, value.get("schema"),
           "facman.alpha5_promotion_candidate_closeout.v1", "schema")
    _exact(problems, value.get("status"),
           "exact_candidate_passed_source_bound_non_authorizing", "status")
    _exact(problems, value.get("work_unit"), WORK_UNIT, "work_unit")
    _exact(problems, value.get("candidate_producer"), PRODUCER, "candidate_producer")
    _exact(
        problems,
        value.get("candidate_producer_work_unit"),
        PRODUCER,
        "candidate_producer_work_unit",
    )
    _exact(problems, value.get("repository"), "Julesc013/factorio-launcher", "repository")
    _exact(problems, value.get("product_version"), "0.1.0-alpha.5", "product_version")
    _exact(problems, value.get("recorded_date"), "2026-09-02", "recorded_date")
    _exact(problems, value.get("revision_topology"), EXPECTED_TOPOLOGY,
           "revision_topology")
    _exact(problems, value.get("counts"), EXPECTED_COUNTS, "counts")
    _exact(problems, value.get("candidate"), EXPECTED_CANDIDATE, "candidate")
    _exact(problems, value.get("failure_chain"), EXPECTED_FAILURES, "failure_chain")
    _exact(problems, value.get("job"), EXPECTED_JOB_ROWS, "job")
    _exact(problems, value.get("artifact"), EXPECTED_ARTIFACTS, "artifact")
    _exact(problems, value.get("bundle"), EXPECTED_BUNDLE, "bundle")
    _exact(problems, value.get("bundle_file"), EXPECTED_FILES, "bundle_file")
    _exact(problems, value.get("payload_equivalence"), EXPECTED_EQUIVALENCE,
           "payload_equivalence")
    _exact(problems, value.get("provider_binding"), EXPECTED_PROVIDER_BINDING,
           "provider_binding")
    _exact(problems, value.get("provider"), EXPECTED_PROVIDERS, "provider")
    _exact(problems, value.get("archive_checkpoint"), EXPECTED_ARCHIVE,
           "archive_checkpoint")
    _exact(problems, value.get("non_circular"), EXPECTED_NON_CIRCULAR,
           "non_circular")
    _exact(problems, value.get("authority"), EXPECTED_AUTHORITY, "authority")

    counts = value.get("counts", {})
    for key, rows in (
        ("job_count", value.get("job", [])),
        ("artifact_count", value.get("artifact", [])),
        ("bundle_file_count", value.get("bundle_file", [])),
        ("failure_chain_count", value.get("failure_chain", [])),
        ("provider_count", value.get("provider", [])),
    ):
        if not isinstance(rows, list) or counts.get(key) != len(rows):
            problems.append(f"counts.{key} does not match its exact row set")
    files = value.get("bundle_file", [])
    if isinstance(files, list):
        roles = [row.get("role") for row in files if isinstance(row, dict)]
        if roles.count("product") != 6 or roles.count("evidence") != 6:
            problems.append("bundle_file must contain exactly six products and six evidence files")
        if roles.count("checksum") != 1 or roles.count("manifest") != 1:
            problems.append("bundle_file must contain exactly one checksum and one manifest")
    topology = value.get("revision_topology", {})
    if len({topology.get("repair_dev_revision"), topology.get("main_candidate_revision"),
            topology.get("dev_sync_revision")}) != 3:
        problems.append("D, M, and S must remain three distinct revisions")
    return problems


def validate_downloaded_manifest(
    receipt: dict[str, Any], manifest: dict[str, Any]
) -> list[str]:
    problems: list[str] = []
    bundle = receipt.get("bundle", {})
    expected_core = {
        "schema": bundle.get("manifest_schema"),
        "status": bundle.get("manifest_status"),
        "candidate_class": bundle.get("candidate_class"),
        "version": bundle.get("version"),
        "source_revision": bundle.get("source_revision"),
        "source_tree": bundle.get("source_tree"),
        "github": {
            "job": bundle.get("github_job"),
            "repository": bundle.get("github_repository"),
            "run_attempt": str(bundle.get("github_run_attempt")),
            "run_id": str(bundle.get("github_run_id")),
            "workflow_ref": bundle.get("github_workflow_ref"),
        },
        "platform_job": bundle.get("platform_job"),
        "payload_equivalence_adapters": bundle.get("payload_equivalence_adapters"),
        "authority": bundle.get("manifest_authority"),
    }
    for key, expected in expected_core.items():
        if manifest.get(key) != expected:
            problems.append(f"downloaded manifest {key} differs from the receipt")
    rows = receipt.get("bundle_file", [])
    products = {
        row["filename"]: {key: row[key] for key in ("filename", "bytes", "sha256")}
        for row in rows if row.get("role") == "product"
    }
    evidence = {
        row["filename"]: {key: row[key] for key in ("filename", "bytes", "sha256")}
        for row in rows if row.get("role") == "evidence"
    }
    for label, expected, actual in (
        ("assets", products, manifest.get("assets")),
        ("evidence", evidence, manifest.get("evidence")),
    ):
        if not isinstance(actual, list):
            problems.append(f"downloaded manifest {label} is not a list")
            continue
        by_name = {
            item.get("filename"): item for item in actual if isinstance(item, dict)
        }
        if len(by_name) != len(actual) or by_name != expected:
            problems.append(f"downloaded manifest {label} differs from exact bundle files")
    checksum = next(
        (row for row in rows if row.get("role") == "checksum"), {}
    )
    expected_checksum = {
        key: checksum.get(key) for key in ("filename", "bytes", "sha256")
    }
    if manifest.get("checksum") != expected_checksum:
        problems.append("downloaded manifest checksum differs from exact bundle file")
    return problems


def validate_bundle_root(receipt: dict[str, Any], bundle_root: Path) -> list[str]:
    problems: list[str] = []
    if bundle_root.is_symlink():
        return ["bundle root must not be a symbolic link"]
    try:
        resolved = bundle_root.resolve(strict=True)
    except OSError as exc:
        return [f"bundle root cannot be resolved: {exc}"]
    if resolved == ROOT or resolved.is_relative_to(ROOT):
        return ["bundle root must remain outside the source checkout"]
    if not resolved.is_dir():
        return ["bundle root must be a directory"]
    children = list(resolved.iterdir())
    if any(not path.is_file() or path.is_symlink() for path in children):
        problems.append("bundle root must contain exactly flat, regular files")
    expected = {row["filename"]: row for row in receipt.get("bundle_file", [])}
    actual = {path.name: path for path in children if path.is_file()}
    if set(actual) != set(expected) or len(actual) != 14:
        problems.append("bundle root does not contain the exact 14-file closure")
        return problems
    for name, record in expected.items():
        path = actual[name]
        if path.stat().st_size != record["bytes"] or sha256(path) != record["sha256"]:
            problems.append(f"bundle file differs from receipt: {name}")
    try:
        manifest = load_json(actual["product-candidate-bundle.v1.json"])
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        problems.append(f"downloaded manifest cannot be read: {exc}")
    else:
        problems.extend(validate_downloaded_manifest(receipt, manifest))
    return problems


def validate_repository_bindings(
    receipt: dict[str, Any],
    release_index: dict[str, Any],
    readiness: dict[str, Any],
    package_producers: dict[str, Any],
    project: dict[str, Any],
    plan: dict[str, Any],
    version_train: dict[str, Any],
    provider_lock: dict[str, Any],
    workspace_lock: dict[str, Any],
) -> list[str]:
    problems: list[str] = []
    if release_index.get("alpha5_promotion_candidate_closeout") != RECEIPT_PATH:
        problems.append("release index does not bind the alpha.5 closeout receipt")

    exact = readiness.get("exact_candidate", {})
    readiness_expected = {
        "status": "pass_unsigned_unpublished_non_authorizing",
        "receipt": RECEIPT_PATH,
        "source_revision": M,
        "source_tree": T,
        "workflow_run": RUN_ID,
        "workflow_attempt": ATTEMPT,
        "final_artifact_id": 9826850751,
        "workflow_artifact_count": 4,
        "bundle_file_count": 14,
        "product_file_count": 6,
        "evidence_file_count": 6,
        "candidate_source_is_closeout_revision": False,
        "candidate_source_is_dev_sync_revision": False,
        "closeout_revision_candidate_qualified": False,
        "synchronized_tree_extends_revision_qualification": False,
        "future_revision_requires_new_candidate_run": True,
    }
    if readiness.get("current_candidate") == "0.1.0-alpha.5":
        for key, expected in readiness_expected.items():
            if exact.get(key) != expected:
                problems.append(f"foundation readiness exact_candidate.{key} differs")
        if readiness.get("beta_ready") is not False:
            problems.append("foundation readiness must not claim beta ready")
        if any(value is not False for value in readiness.get("authority", {}).values()):
            problems.append("foundation readiness authority must remain closed")

    producers = {
        row.get("id"): row
        for row in package_producers.get("producer", [])
        if isinstance(row, dict)
    }
    setup = producers.get("platform_self_setup", {})
    setup_expected = {
        "payload_equivalence_authority": "exact_candidate_proof_recorded_non_authorizing",
        "payload_equivalence_receipt": RECEIPT_PATH,
        "payload_equivalence_source_revision": M,
        "payload_equivalence_source_tree": T,
        "payload_equivalence_candidate_run": RUN_ID,
        "payload_equivalence_candidate_attempt": ATTEMPT,
    }
    for key, expected in setup_expected.items():
        if setup.get(key) != expected:
            problems.append(f"package producer {key} differs from candidate receipt")
    if package_producers.get("release_authority") is not False:
        problems.append("package producer release authority must remain false")

    project_candidate = project.get("alpha5_beta_readiness", {})
    project_expected = {
        "closeout_work_unit": WORK_UNIT,
        "receipt": RECEIPT_PATH,
        "candidate_source_revision": M,
        "candidate_source_tree": T,
        "candidate_run": RUN_ID,
        "candidate_attempt": ATTEMPT,
        "archive_checkpoint": CHECKPOINT,
        "archive_index_sha256": ARCHIVE_SHA256,
        "bundle_artifact_id": 9826850751,
        "bundle_file_count": 14,
        **EXPECTED_NON_CIRCULAR,
        "beta_ready": False,
        "factorio_execution": False,
        "managed_install_human_verdict": False,
        "accessibility_human_verdict": False,
        "signing": False,
        "notarization": False,
        "publication": False,
        "support": False,
    }
    for key, expected in project_expected.items():
        if project_candidate.get(key) != expected:
            problems.append(f"project alpha5_beta_readiness.{key} differs")
    topology = project.get("canonical_plan_and_truth_closeout", {})
    for key, expected in {
        "work_unit": WORK_UNIT,
        "promotion_source_revision": D,
        "canonical_main_revision": M,
        "dev_synchronization_revision": S,
        "candidate_source_tree": T,
        "candidate_run": RUN_ID,
        "candidate_attempt": ATTEMPT,
        "candidate_receipt": RECEIPT_PATH,
    }.items():
        if topology.get(key) != expected:
            problems.append(f"project closeout topology {key} differs")

    workunits = {
        row.get("id"): row
        for row in plan.get("workunit", [])
        if isinstance(row, dict)
    }
    planned = workunits.get(WORK_UNIT, {})
    if planned.get("status") not in {"active", "verified_pending_closeout"}:
        problems.append("canonical plan does not retain the closeout WorkUnit")
    if planned.get("base_revision") != S or planned.get("depends_on") != [PRODUCER]:
        problems.append("canonical plan closeout source/dependency differs")
    expected_evidence = {
        RECEIPT_PATH,
        "docs/release/checkpoints/facman-0-1-alpha5-promotion-candidate-closeout-01.md",
        EXPECTED_ARCHIVE["path"],
    }
    if set(planned.get("evidence", [])) != expected_evidence:
        problems.append("canonical plan closeout evidence set differs")

    if version_train.get("release_source_workunit") != PRODUCER:
        problems.append("version train release-source WorkUnit differs")
    if version_train.get("allocated_version") == "0.1.0-alpha.5":
        if version_train.get("signing_authorized") is not False:
            problems.append("version train signing authority must remain false")
        if version_train.get("publication_authorized") is not False:
            problems.append("version train publication authority must remain false")

    providers = {
        row.get("id"): row
        for row in provider_lock.get("provider", [])
        if isinstance(row, dict)
    }
    workspace = {
        row.get("id"): row
        for row in workspace_lock.get("component", [])
        if isinstance(row, dict) and row.get("id") in providers
    }
    receipt_providers = {row["id"]: row for row in receipt.get("provider", [])}
    if set(receipt_providers) != {"universal_launcher", "universal_setup"}:
        problems.append("receipt provider set differs")
    for provider_id, record in receipt_providers.items():
        current = providers.get(provider_id, {})
        pinned = workspace.get(provider_id, {})
        if readiness.get("current_candidate") == "0.1.0-alpha.5":
            for receipt_key, current_key in (
                ("source_revision", "source_revision"),
                ("source_tree", "source_tree"),
                ("package_version", "package_version"),
                ("package_digest", "package_digest"),
                ("abi_version", "abi_version"),
                ("abi_manifest_digest", "abi_manifest_digest"),
                ("contract_digest", "contract_digest"),
            ):
                if record.get(receipt_key) != current.get(current_key):
                    problems.append(f"{provider_id} provider lock {current_key} differs")
            if record.get("workspace_pin") != pinned.get("pin"):
                problems.append(f"{provider_id} workspace pin differs")
            if record.get("workspace_tree") != pinned.get("tree"):
                problems.append(f"{provider_id} workspace tree differs")
    return problems


def repository_problems(receipt: dict[str, Any]) -> list[str]:
    values = [
        load_toml(path)
        for path in (
            RELEASE_INDEX, READINESS, PACKAGE_PRODUCERS, PROJECT, PLAN,
            VERSION_TRAIN, PROVIDER_LOCK, WORKSPACE_LOCK,
        )
    ]
    problems = validate_repository_bindings(receipt, *values)
    if sha256_text_lf(ARCHIVE_INDEX) != ARCHIVE_SHA256:
        problems.append("immutable alpha.5 archive index canonical LF bytes changed")
    archive = load_json(ARCHIVE_INDEX)
    if archive.get("schema") != "aide.history_index.v1":
        problems.append("archive index has the wrong schema")
    if archive.get("checkpoint") != CHECKPOINT:
        problems.append("archive index has the wrong checkpoint")
    if archive.get("immutable_task_records") is not True:
        problems.append("archive index does not mark task records immutable")
    task_ids = {
        row.get("task_id") for row in archive.get("tasks", []) if isinstance(row, dict)
    }
    if task_ids != {"FACMAN-0.1-BETA-READINESS-01", "FACMAN-0.1-ULTIMATE-REBASE-01"}:
        problems.append("archive index does not contain the exact two foundation tasks")
    if sha256(PROVIDER_LOCK) != PROVIDER_LOCK_SHA256:
        problems.append("current provider-lock bytes differ from the alpha.5 binding")
    if sha256(WORKSPACE_LOCK) != WORKSPACE_LOCK_SHA256:
        problems.append("current workspace-lock bytes differ from the alpha.5 binding")
    return problems


def check(bundle_root: Path | None = None) -> list[str]:
    try:
        receipt = load_toml(RECEIPT)
        problems = validate_receipt(receipt) + repository_problems(receipt)
        if bundle_root is not None:
            problems.extend(validate_bundle_root(receipt, bundle_root))
        return problems
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        tomllib.TOMLDecodeError,
        jsonschema.SchemaError,
    ) as exc:
        return [f"alpha.5 promotion candidate closeout cannot be read: {exc}"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", type=Path)
    args = parser.parse_args(argv)
    problems = check(args.bundle_root)
    if problems:
        for problem in problems:
            print(f"alpha5-promotion-candidate-closeout-check: {problem}", file=sys.stderr)
        return 1
    suffix = " + external bundle" if args.bundle_root is not None else ""
    print(
        "alpha5-promotion-candidate-closeout-check: ok "
        f"source={M[:12]} run={RUN_ID}/1 authority=closed{suffix}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
