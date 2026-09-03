#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the final, non-authorizing FacMan Alpha.5 candidate truth."""

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
RECEIPT_PATH = "release/index/alpha5_final_candidate_closeout.v1.toml"
RECEIPT = ROOT / RECEIPT_PATH
SCHEMA = ROOT / "contracts/schema/release/alpha5_final_candidate_closeout.v1.schema.json"
RELEASE_INDEX = ROOT / "release/index/release_index.v1.toml"
CURRENT_STATE = ROOT / "release/index/current_state.v1.toml"
PROJECT = ROOT / "release/index/project_status.v2.toml"
PLAN = ROOT / "release/index/plan.v1.toml"
VERSION_TRAIN = ROOT / "release/index/version_train.v1.toml"
READINESS = ROOT / "release/index/foundation_beta_readiness.v1.toml"
SUPPORT_MATRIX = ROOT / "release/index/support_matrix.v1.toml"
PACKAGE_PRODUCERS = ROOT / "release/index/package_producers.v1.toml"
PROFILE_LIFECYCLE = ROOT / "release/profiles/profile_lifecycle.v1.toml"
FINAL_DISTRIBUTION = ROOT / "release/index/final_distribution.v1.toml"
PROVIDER_LOCK = ROOT / "release/index/providers.lock.v2.toml"
WORKSPACE_LOCK = ROOT / "release/index/workspace_lock.v1.toml"
QUEUE_ACTIVE = ROOT / ".aide/queue/active"

WORK_UNIT = "FACMAN-0.1-ALPHA5-FINAL-CANDIDATE-CLOSEOUT-01"
OLD_CLOSEOUT = "FACMAN-0.1-ALPHA5-PROMOTION-CANDIDATE-CLOSEOUT-01"
OLD_REMEDIATION = "FACMAN-0.1-ALPHA5-TRUTH-REMEDIATION-01"
MAIN = "4683ecd9a1b9ead5eb84be152760d12583da0f0e"
DEV = "488994a81ddb5eb54d541ef3a48b64ca83f67d4a"
TREE = "c07938618bc0f533fd12756cba123f54b8592048"
RUN = 33603385303
ATTEMPT = 1
FINAL_ARTIFACT_ID = 9836639957
FINAL_ARTIFACT_DIGEST = (
    "sha256:1c53c1e1337dced910f8aa88c9d32c9a36a68d5b87dff2cce7172381f386e736"
)
FINAL_ARTIFACT_NAME = (
    "FacMan-0.1.0-alpha.5-unsigned-unpublished-candidate-"
    "33603385303-1-4683ecd9a1b9ead5eb84be152760d12583da0f0e"
)
OLD_RUN = 33576140943
OLD_MAIN = "a7a518dbfe2a6d54da7b9c84fbd318300265e31d"
OLD_TREE = "1ebcd2b230ed188e021880ffa4c438de2ede655b"

EXPECTED_JOBS = [
    (100161858379, "Version-current candidate contract"),
    (100161899775, "Windows x64 unsigned candidate"),
    (100161899829, "macOS Intel unsigned preview candidate"),
    (100161900003, "Linux x64 unsigned preview candidate"),
    (100166902527, "Exact six-asset unpublished candidate bundle"),
]
EXPECTED_ARTIFACTS = [
    (
        9836639957,
        "final_bundle",
        FINAL_ARTIFACT_NAME,
        39415203,
        FINAL_ARTIFACT_DIGEST,
    ),
    (
        9836247157,
        "windows_input",
        f"product-candidate-input-windows-{RUN}-{ATTEMPT}-{MAIN}",
        16038042,
        "sha256:88917bebd2861d33f7a893c266d7b03decb11cf65ddfb0642289ce788d758981",
    ),
    (
        9836629744,
        "macos_input",
        f"product-candidate-input-macos-{RUN}-{ATTEMPT}-{MAIN}",
        13398912,
        "sha256:9c87920676ba1a974e877915cec2423ea2b6228fe399b26e3ad17ee35788294d",
    ),
    (
        9836125335,
        "linux_input",
        f"product-candidate-input-linux-{RUN}-{ATTEMPT}-{MAIN}",
        9976347,
        "sha256:64be7ee79a234924cbf0a80f7bb2e463f049da6a2f7abf58d1341b0e63508bb6",
    ),
]
EXPECTED_FILES = {
    "FacMan-0.1.0-alpha.5-windows-x64-portable.zip": (7754778, "08d41985e1e93bc84f59d592867041bd859a85596c5b1f9fcd13bf4fb61f2255"),
    "FacMan-0.1.0-alpha.5-windows-x64-setup.exe": (16279273, "bef576270c9d1bdf2c9b56a19e1ae9593a432659b09a43572a8790d11e977e20"),
    "FacMan-0.1.0-alpha.5-macos-x64-portable.zip": (6703790, "64a6bba04c86aba1af5ccc17da099cf5693f4db3d40df9d468eef322c7373096"),
    "FacMan-0.1.0-alpha.5-macos-x64-setup.pkg": (6701884, "e2fad6657d3d25987c4ea00eee9c3b25ec436e180de13de8fd9655f0f818357c"),
    "FacMan-0.1.0-alpha.5-linux-x64-portable.tar.zst": (4986213, "2cf7fb53f4e21f3183c4226a80c7870ea08f4d424bb4c9201735bb43a7d6aca7"),
    "FacMan-0.1.0-alpha.5-linux-x64-setup.run": (4991752, "76323ff38fb1babac2e9e48b60566aaf79f7b4d468f01c49f1f31f3ee06a9164"),
    "linux-candidate-evidence.v1.json": (1282, "fc17542cf5f4b40a2dfd7208794f97aa317136723c523d0bebbb26bb3fea255c"),
    "linux-payload-equivalence.v1.json": (920, "820e6073637138f74a98108c17ec2684e80dee995550880ffb4988a9437c57c2"),
    "macos-candidate-evidence.v1.json": (1266, "17673068fcff6adb45098fadd889d8f22a36771a2a18f053a6331740641146d4"),
    "macos-payload-equivalence.v1.json": (934, "53ab66db5ca503f75980af472fb14f68eab74283e3e3995e858bfbf545225765"),
    "windows-candidate-evidence.v1.json": (1282, "54d0a6adebdb09273f2d63b3b76fc889fdaece6ca8af1c26bade2929a96a902b"),
    "windows-payload-equivalence.v1.json": (1011, "d12a5ed7e5c2bae98994cebbfd64f55d3053a8c2a1ca1123810fe013ab336caf"),
    "product-candidate-bundle.v1.json": (3163, "1be3a4ade7370a6c0ed51dc04eff5ce2ad86eb8034393cdaefa961acd8d4a923"),
    "SHA256SUMS": (1260, "a9b8d06fc6d5062b41e68215399680dfa66689e3dacf9d062424f5d1547944b7"),
}


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_receipt(receipt: dict[str, Any]) -> list[str]:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    problems = [
        f"schema: {error.message}"
        for error in sorted(
            jsonschema.Draft202012Validator(schema).iter_errors(receipt),
            key=lambda item: list(item.absolute_path),
        )
    ]
    exact_top = {
        "work_unit": WORK_UNIT,
        "record_role": "current_alpha5_candidate",
        "candidate_artifact_name": FINAL_ARTIFACT_NAME,
        "candidate_artifact_digest": FINAL_ARTIFACT_DIGEST,
    }
    for key, expected in exact_top.items():
        if receipt.get(key) != expected:
            problems.append(f"receipt {key} must be {expected!r}")
    topology = receipt.get("topology", {})
    for key, expected in {
        "main_revision": MAIN,
        "dev_revision": DEV,
        "shared_tree": TREE,
        "main_is_ancestor_of_dev": True,
        "trees_equal": True,
        "protected_main_promotion_pull_request": 240,
        "dev_back_sync_pull_request": 241,
    }.items():
        if topology.get(key) != expected:
            problems.append(f"topology.{key} must be {expected!r}")
    candidate = receipt.get("candidate", {})
    for key, expected in {
        "workflow_run": RUN,
        "workflow_attempt": ATTEMPT,
        "head_sha": MAIN,
        "head_tree": TREE,
        "status": "completed",
        "conclusion": "success",
        "job_count": 5,
        "workflow_artifact_count": 4,
        "bundle_file_count": 14,
    }.items():
        if candidate.get(key) != expected:
            problems.append(f"candidate.{key} must be {expected!r}")
    jobs = [
        (row.get("id"), row.get("name"), row.get("status"), row.get("conclusion"))
        for row in receipt.get("job", [])
        if isinstance(row, dict)
    ]
    expected_jobs = [(job_id, name, "completed", "success") for job_id, name in EXPECTED_JOBS]
    if jobs != expected_jobs:
        problems.append("candidate job inventory differs from final hosted run")
    artifacts = [
        (
            row.get("id"),
            row.get("role"),
            row.get("name"),
            row.get("bytes"),
            row.get("digest"),
            row.get("expired"),
        )
        for row in receipt.get("artifact", [])
        if isinstance(row, dict)
    ]
    expected_artifacts = [(*row, False) for row in EXPECTED_ARTIFACTS]
    if artifacts != expected_artifacts:
        problems.append("workflow artifact inventory differs from final hosted run")
    files = {
        row.get("name"): (row.get("bytes"), row.get("sha256"))
        for row in receipt.get("file", [])
        if isinstance(row, dict)
    }
    if files != EXPECTED_FILES:
        problems.append("durable candidate file inventory differs")
    axes = receipt.get("axes", {})
    for key in (
        "engineering_complete",
        "machine_qualified",
        "protected_dev_integration",
        "protected_main_promotion",
        "dev_back_sync",
    ):
        if axes.get(key) is not True:
            problems.append(f"candidate axis {key} must be true")
    for key in (
        "human_desktop_accepted",
        "real_play_accepted",
        "managed_install_accepted",
        "linux_human_accepted",
        "macos_human_accepted",
        "signed",
        "notarized",
        "tagged",
        "published",
        "supported",
    ):
        if axes.get(key) is not False:
            problems.append(f"candidate axis {key} must remain false")
    return problems


def validate_bundle_root(receipt: dict[str, Any], bundle_root: Path) -> list[str]:
    problems: list[str] = []
    if not bundle_root.is_dir():
        return [f"candidate custody root does not exist: {bundle_root}"]
    actual = {
        path.name: path
        for path in bundle_root.iterdir()
        if path.is_file()
    }
    if set(actual) != set(EXPECTED_FILES):
        problems.append("candidate custody root is not the exact closed inventory")
        return problems
    for name, (expected_bytes, expected_hash) in EXPECTED_FILES.items():
        path = actual[name]
        if path.stat().st_size != expected_bytes or sha256(path) != expected_hash:
            problems.append(f"candidate custody file differs: {name}")
    try:
        manifest = json.loads(actual["product-candidate-bundle.v1.json"].read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        problems.append(f"candidate bundle manifest cannot be read: {error}")
    else:
        for key, expected in {
            "source_revision": MAIN,
            "source_tree": TREE,
            "status": "pass",
            "version": "0.1.0-alpha.5",
        }.items():
            if manifest.get(key) != expected:
                problems.append(f"candidate bundle manifest {key} differs")
        github = manifest.get("github", {})
        if github.get("run_id") != str(RUN) or github.get("run_attempt") != str(ATTEMPT):
            problems.append("candidate bundle manifest run binding differs")
        if any(value is not False for value in manifest.get("authority", {}).values()):
            problems.append("candidate bundle manifest grants external authority")
    return problems


def current_binding_problems(values: dict[str, dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    release_index = values["release_index"]
    if release_index.get("alpha5_final_candidate_closeout") != RECEIPT_PATH:
        problems.append("release index does not bind the final Alpha.5 candidate")
    project = values["project"]
    for key, expected in {
        "hosted_matrix_revision": MAIN,
        "canonical_main_revision": MAIN,
        "planning_promotion_revision": MAIN,
        "runtime_candidate_revision": MAIN,
        "qualification_source_revision": MAIN,
        "qualification_evidence_revision": MAIN,
        "qualification_integration_revision": DEV,
    }.items():
        if project.get(key) != expected:
            problems.append(f"project candidate role {key} differs from final candidate")
    closeout = project.get("canonical_plan_and_truth_closeout", {})
    for key, expected in {
        "work_unit": WORK_UNIT,
        "canonical_main_revision": MAIN,
        "candidate_source_tree": TREE,
        "candidate_run": RUN,
        "candidate_attempt": ATTEMPT,
        "candidate_receipt": RECEIPT_PATH,
    }.items():
        if closeout.get(key) != expected:
            problems.append(f"project final closeout {key} differs")
    current = values["current_state"]
    exact = current.get("alpha5_exact_candidate", {})
    for key, expected in {
        "status": "final_candidate_machine_qualified_beta_not_ready",
        "closeout_work_unit": WORK_UNIT,
        "receipt": RECEIPT_PATH,
        "source_revision": MAIN,
        "source_tree": TREE,
        "run": RUN,
        "attempt": ATTEMPT,
        "bundle_artifact_id": FINAL_ARTIFACT_ID,
        "bundle_artifact_digest": FINAL_ARTIFACT_DIGEST,
    }.items():
        if exact.get(key) != expected:
            problems.append(f"compact current candidate {key} differs")
    version_train = values["version_train"]
    for key, expected in {
        "release_source_workunit": WORK_UNIT,
        "release_source_status": "final_candidate_machine_qualified_unpublished",
        "release_source_revision": MAIN,
        "release_source_tree": TREE,
        "release_source_candidate_run": RUN,
        "release_source_candidate_attempt": ATTEMPT,
        "release_source_receipt": RECEIPT_PATH,
    }.items():
        if version_train.get(key) != expected:
            problems.append(f"version train {key} differs")
    readiness = values["readiness"].get("exact_candidate", {})
    for key, expected in {
        "receipt": RECEIPT_PATH,
        "source_revision": MAIN,
        "source_tree": TREE,
        "workflow_run": RUN,
        "workflow_attempt": ATTEMPT,
        "final_artifact_id": FINAL_ARTIFACT_ID,
        "final_artifact_digest": FINAL_ARTIFACT_DIGEST,
    }.items():
        if readiness.get(key) != expected:
            problems.append(f"foundation readiness exact_candidate.{key} differs")
    support = {
        row.get("id"): row
        for row in values["support_matrix"].get("platform", [])
        if isinstance(row, dict)
    }
    for profile in ("windows_product_x64", "macos_product_x64", "linux_product_x64"):
        row = support.get(profile, {})
        if row.get("evidence_revision") != MAIN or row.get("candidate_receipt") != RECEIPT_PATH:
            problems.append(f"support matrix current profile {profile} is stale")
    producers = {
        row.get("id"): row
        for row in values["package_producers"].get("producer", [])
        if isinstance(row, dict)
    }
    setup = producers.get("platform_self_setup", {})
    for key, expected in {
        "payload_equivalence_receipt": RECEIPT_PATH,
        "payload_equivalence_source_revision": MAIN,
        "payload_equivalence_source_tree": TREE,
        "payload_equivalence_candidate_run": RUN,
        "payload_equivalence_candidate_attempt": ATTEMPT,
    }.items():
        if setup.get(key) != expected:
            problems.append(f"package producer {key} differs")
    return problems


def lifecycle_problems(
    plan: dict[str, Any],
    package_producers: dict[str, Any],
    profile_lifecycle: dict[str, Any],
    queue_active: Path = QUEUE_ACTIVE,
) -> list[str]:
    problems: list[str] = []
    workunits = {
        row.get("id"): row
        for row in plan.get("workunit", [])
        if isinstance(row, dict)
    }
    for task_id in (OLD_CLOSEOUT, OLD_REMEDIATION):
        if workunits.get(task_id, {}).get("status") != "complete":
            problems.append(f"integrated Alpha.5 WorkUnit remains incomplete: {task_id}")
        if (queue_active / task_id).exists():
            problems.append(f"integrated Alpha.5 WorkUnit remains active: {task_id}")
    current = workunits.get(WORK_UNIT, {})
    if current.get("status") != "complete":
        problems.append("final Alpha.5 candidate closeout is absent from the plan")
    if (queue_active / WORK_UNIT).exists():
        problems.append("final Alpha.5 candidate closeout remains active after integration")
    active_view = workunits.get("FACMAN-ACTIVE-RELEASE-VIEW-CONSOLIDATION-01", {})
    if active_view.get("status") != "complete":
        problems.append("active release-view consolidation is not complete")
    if (queue_active / "FACMAN-ACTIVE-RELEASE-VIEW-CONSOLIDATION-01").exists():
        problems.append("active release-view consolidation remains active after integration")
    lifecycle = {
        row.get("profile_id"): row.get("lifecycle")
        for row in profile_lifecycle.get("assignment", [])
        if isinstance(row, dict)
    }
    complete = {
        task_id for task_id, row in workunits.items() if row.get("status") == "complete"
    }
    for producer in package_producers.get("producer", []):
        if not isinstance(producer, dict) or producer.get("state") != "temporary_exception":
            continue
        if producer.get("expiry_workunit") not in complete:
            continue
        release_active = [
            profile
            for profile in producer.get("profiles", [])
            if lifecycle.get(profile) in {"active", "preview"}
        ]
        if release_active:
            problems.append(
                f"expired producer exception remains release-active: {producer.get('id')} "
                + ",".join(release_active)
            )
    return problems


def historical_role_problems(final_distribution: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if final_distribution.get("record_role") != "historical_alpha3_draft":
        problems.append("historical final_distribution record lacks an explicit historical role")
    if final_distribution.get("current_candidate") is not False:
        problems.append("historical final_distribution record presents itself as current")
    if final_distribution.get("successor_current_candidate_receipt") != RECEIPT_PATH:
        problems.append("historical final_distribution record lacks its current successor")
    return problems


def current_view_problems() -> list[str]:
    problems: list[str] = []
    requirements = {
        "README.md": (str(RUN), MAIN, RECEIPT_PATH),
        "docs/roadmap.md": (
            "FACMAN-0.1-ALPHA6-WORKSPACE-MIGRATION-RECOVERY-01",
            "facman_0_1_beta_ruleset_report_complete",
            "release/index/active_release_view.v1.toml",
        ),
        "docs/platform/support_matrix.md": (MAIN,),
        ".aide/memory/project-state.md": (str(RUN), MAIN),
    }
    for relative, required in requirements.items():
        text = (ROOT / relative).read_text(encoding="utf-8")
        if any(value not in text for value in required):
            problems.append(f"generated current view binds an older closeout: {relative}")
    return problems


def repository_problems() -> list[str]:
    values = {
        "release_index": load_toml(RELEASE_INDEX),
        "current_state": load_toml(CURRENT_STATE),
        "project": load_toml(PROJECT),
        "plan": load_toml(PLAN),
        "version_train": load_toml(VERSION_TRAIN),
        "readiness": load_toml(READINESS),
        "support_matrix": load_toml(SUPPORT_MATRIX),
        "package_producers": load_toml(PACKAGE_PRODUCERS),
        "profile_lifecycle": load_toml(PROFILE_LIFECYCLE),
        "final_distribution": load_toml(FINAL_DISTRIBUTION),
    }
    problems = current_binding_problems(values)
    problems.extend(
        lifecycle_problems(
            values["plan"],
            values["package_producers"],
            values["profile_lifecycle"],
        )
    )
    problems.extend(historical_role_problems(values["final_distribution"]))
    problems.extend(current_view_problems())
    if sha256(PROVIDER_LOCK) != "d33943841431afdeffb7961c7453d8999619ef371793a6310ad2c2952b118f00":
        problems.append("provider lock bytes differ from the final candidate binding")
    if sha256(WORKSPACE_LOCK) != "b1590cc87bd50e5913196f1e3aa7a044028b30e9f1354b46a355b3db3f42c9bf":
        problems.append("workspace lock bytes differ from the final candidate binding")
    return problems


def check(bundle_root: Path | None = None) -> list[str]:
    try:
        receipt = load_toml(RECEIPT)
        problems = validate_receipt(receipt) + repository_problems()
        if bundle_root is not None:
            problems.extend(validate_bundle_root(receipt, bundle_root))
        return problems
    except (
        OSError,
        ValueError,
        json.JSONDecodeError,
        tomllib.TOMLDecodeError,
        jsonschema.SchemaError,
    ) as error:
        return [str(error)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-root", type=Path)
    args = parser.parse_args(argv)
    problems = check(args.bundle_root)
    if problems:
        for problem in problems:
            print(f"alpha5-final-candidate-closeout: {problem}", file=sys.stderr)
        return 1
    print("alpha5-final-candidate-closeout: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
