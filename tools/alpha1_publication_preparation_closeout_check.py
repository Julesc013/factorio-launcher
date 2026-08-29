# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the protected-dev alpha.1 publication-preparation closeout."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CLOSEOUT = ROOT / "release/index/alpha1_publication_preparation_closeout.v1.toml"
PREPARATION = ROOT / "release/index/alpha1_publication_preparation.v1.toml"
ROUTE_REQUEST = ROOT / "release/index/factorio_2_1_14_route_d3_d4_request.v1.toml"
PROJECT = ROOT / "release/index/project_status.v2.toml"
CURRENT = ROOT / "release/index/current_state.v1.toml"
PLAN = ROOT / "release/index/plan.v1.toml"

WORK_UNIT = "FACMAN-0.1.0-ALPHA.1-PUBLICATION-PREPARATION-01"
HUMAN_WORK_UNIT = "FACMAN-0.1.0-ALPHA.1-HUMAN-ACCEPTANCE-01"
PRODUCT_REVISION = "fa60aaa17e9044bef7bb7347261056959690f1cd"
PRODUCT_TREE = "5536891662461d3617ee40e93654cb2f0659905c"
BASE_REVISION = "772238ccd9a11481657b9525011ff6dfc8dfaaab"
BASE_TREE = "ceeb725dabe0e51912b05890795069b2c2355a52"
TASK_REVISION = "24688847f8b2ed0f54aafe96150ba68dce6a78b4"
MERGE_REVISION = "edf61bdf0fe00692a73a58c3586ac4f7c0dbfec4"
MERGE_TREE = "7dc49419a7127a70b6085952d03d1acd179985e4"
PREPARATION_DIGEST = "5e6ceb433770d5ef17faaf20b5e7a45e9e1bccd02db87ccb665272b482f04685"
HUMAN_RECEIPT = "7f64271c91cfb0417cd205b5f22bfe79d66d746a60eef5ded33a627453950928"
ROUTE_REQUEST_DIGEST = "eaf8fb1a1b92638ff1d0cd71a6403263beae87e41dddd9e3109af81e2e0ee630"
PHASE = "facman_0_1_0_alpha_1_human_acceptance_pending"
CHECKPOINT = "facman-alpha1-publication-preparation-closeout-01"
NEXT_AUTHORITY_GATE = (
    "named_nine_lane_human_verdict_and_separately_authorized_route_v5_d3_d4"
)

PULL_REQUEST_WORKFLOWS = {
    "schema-check": 33264607411,
    "security-policy": 33264607418,
    "ci": 33264607421,
    "synthetic-product-tck": 33264607426,
    "code-security": 33264607466,
}
POST_MERGE_WORKFLOWS = {
    "schema-check": 33265801696,
    "ci": 33265801707,
    "security-policy": 33265801710,
    "synthetic-product-tck": 33265801748,
    "code-security": 33265801809,
}
EXPECTED_AUTHORITY = {
    "human_verdict": False,
    "d3_active": False,
    "d4_active": False,
    "permit_issuance": False,
    "factorio_execution": False,
    "route_capability": False,
    "route_promotion": False,
    "tagging": False,
    "publication": False,
    "production_signing": False,
    "support_activation": False,
    "main_promotion": False,
    "beta_rc_stable_promotion": False,
}


def load(path: Path = CLOSEOUT) -> dict[str, Any]:
    with path.open("rb") as stream:
        value = tomllib.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a TOML table")
    return value


def _expect(
    problems: list[str], record: dict[str, Any], key: str, expected: Any, label: str
) -> None:
    if record.get(key) != expected:
        problems.append(f"{label}.{key} must equal {expected!r}")


def _validate_workflows(
    problems: list[str],
    rows: object,
    expected: dict[str, int],
    head_sha: str,
    label: str,
) -> None:
    if not isinstance(rows, list):
        problems.append(f"{label} must be a list")
        return
    by_name = {
        row.get("name"): row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("name"), str)
    }
    if set(by_name) != set(expected):
        problems.append(f"{label} must contain the exact five required workflows")
    for name, run_id in expected.items():
        row = by_name.get(name, {})
        _expect(problems, row, "run_id", run_id, f"{label}.{name}")
        _expect(problems, row, "head_sha", head_sha, f"{label}.{name}")
        _expect(problems, row, "conclusion", "success", f"{label}.{name}")


def validate(value: dict[str, Any] | None = None) -> list[str]:
    closeout = value if value is not None else load()
    preparation = load(PREPARATION)
    route_request = load(ROUTE_REQUEST)
    project = load(PROJECT)
    current = load(CURRENT)
    plan = load(PLAN)
    problems: list[str] = []

    for key, expected in {
        "schema": "facman.alpha1_publication_preparation_closeout.v1",
        "status": "protected_dev_integration_verified_g2_g3_and_publication_authority_pending",
        "work_unit": WORK_UNIT,
        "repository": "Julesc013/factorio-launcher",
        "product_version": "0.1.0-alpha.1",
    }.items():
        _expect(problems, closeout, key, expected, "closeout")

    frozen = closeout.get("frozen_product", {})
    for key, expected in {
        "source_revision": PRODUCT_REVISION,
        "source_tree": PRODUCT_TREE,
        "tag": "v0.1.0-alpha.1",
        "tag_object": "52a7a66092ff2b3b3c1059e9c29260f95b1cb287",
        "immutable": True,
    }.items():
        _expect(problems, frozen, key, expected, "frozen_product")

    prepared = closeout.get("preparation", {})
    for key, expected in {
        "record": "release/index/alpha1_publication_preparation.v1.toml",
        "digest": PREPARATION_DIGEST,
        "base_revision": BASE_REVISION,
        "base_tree": BASE_TREE,
        "task_branch": "task/facman-alpha1-public-preparation-01",
        "task_head_revision": TASK_REVISION,
        "task_head_tree": MERGE_TREE,
    }.items():
        _expect(problems, prepared, key, expected, "preparation")
    _expect(
        problems,
        preparation,
        "preparation_digest",
        PREPARATION_DIGEST,
        "prepared_record",
    )

    integration = closeout.get("integration", {})
    for key, expected in {
        "pull_request": 201,
        "base_ref": "dev",
        "base_revision": BASE_REVISION,
        "head_ref": "task/facman-alpha1-public-preparation-01",
        "head_revision": TASK_REVISION,
        "merge_revision": MERGE_REVISION,
        "merge_tree": MERGE_TREE,
        "merge_parents": [BASE_REVISION, TASK_REVISION],
        "merge_method": "merge_commit",
        "merge_actor": "Julesc013",
        "merged_at": "2026-08-29T17:30:22Z",
        "task_head_contained": True,
        "pull_request_required_checks": "13_of_13_success",
        "post_merge_required_checks": "12_of_12_success",
    }.items():
        _expect(problems, integration, key, expected, "integration")

    _validate_workflows(
        problems,
        closeout.get("pull_request_workflow"),
        PULL_REQUEST_WORKFLOWS,
        TASK_REVISION,
        "pull_request_workflow",
    )
    _validate_workflows(
        problems,
        closeout.get("post_merge_workflow"),
        POST_MERGE_WORKFLOWS,
        MERGE_REVISION,
        "post_merge_workflow",
    )
    codeql = closeout.get("pull_request_codeql", {})
    for key, expected in {
        "check_run_id": 99132484832,
        "name": "CodeQL",
        "app": "github-advanced-security",
        "head_sha": TASK_REVISION,
        "conclusion": "success",
    }.items():
        _expect(problems, codeql, key, expected, "pull_request_codeql")

    next_gate = closeout.get("next_gate", {})
    for key, expected in {
        "next_work_unit": HUMAN_WORK_UNIT,
        "owner": "Jules",
        "human_receipt": "facman-0.1.0-alpha.1-human-test-receipt.v1.json",
        "human_receipt_sha256": HUMAN_RECEIPT,
        "human_result": "Inconclusive",
        "human_tester": "UNASSIGNED",
        "route_request": "release/index/factorio_2_1_14_route_d3_d4_request.v1.toml",
        "route_request_digest": ROUTE_REQUEST_DIGEST,
        "route_result": "UNRECORDED",
        "publication_authority": "UNASSIGNED",
    }.items():
        _expect(problems, next_gate, key, expected, "next_gate")
    _expect(
        problems,
        route_request,
        "request_digest",
        ROUTE_REQUEST_DIGEST,
        "route_request",
    )

    if closeout.get("gate_state") != {
        "g1_tag": "complete",
        "g2_human_alpha": "pending",
        "g3_route": "pending",
        "g4_public_alpha": "not_authorized",
        "beta": "not_reached",
        "rc": "not_reached",
        "stable_0_1_0": "not_reached",
    }:
        problems.append("gate_state must preserve the exact finite GO ladder")
    if closeout.get("authority") != EXPECTED_AUTHORITY:
        problems.append("authority must remain exactly and entirely closed")

    for key, expected in {
        "current_checkpoint": CHECKPOINT,
        "accepted_integration_revision": MERGE_REVISION,
        "active_work_unit": "",
        "last_closed_work_unit": WORK_UNIT,
        "reviewed_dev_checkpoint_revision": MERGE_REVISION,
        "reviewed_dev_checkpoint_tree": MERGE_TREE,
        "dev_synchronization_revision": MERGE_REVISION,
        "truth_closeout_revision": MERGE_REVISION,
        "next_authority_gate": NEXT_AUTHORITY_GATE,
    }.items():
        _expect(problems, project, key, expected, "project")
    product = project.get("product", {})
    for key, expected in {
        "phase": PHASE,
        "current_work_unit": "",
        "next_work_unit": HUMAN_WORK_UNIT,
    }.items():
        _expect(problems, product, key, expected, "project.product")

    for key, expected in {
        "phase": PHASE,
        "checkpoint": CHECKPOINT,
        "active_work_unit": "",
        "next_work_unit": HUMAN_WORK_UNIT,
        "last_closed_work_unit": WORK_UNIT,
        "next_authority_gate": NEXT_AUTHORITY_GATE,
    }.items():
        _expect(problems, current, key, expected, "current")

    workunits = {
        row.get("id"): row
        for row in plan.get("workunit", [])
        if isinstance(row, dict)
    }
    publication = workunits.get(WORK_UNIT, {})
    human = workunits.get(HUMAN_WORK_UNIT, {})
    _expect(problems, publication, "status", "complete", "plan.publication")
    _expect(problems, human, "status", "blocked", "plan.human")
    _expect(problems, human, "base_revision", MERGE_REVISION, "plan.human")
    if not human.get("blockers"):
        problems.append("plan.human.blockers must explain the external human gate")
    return problems


def main(argv: list[str] | None = None) -> int:
    del argv
    try:
        problems = validate()
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"alpha1-publication-preparation-closeout-check: {exc}", file=sys.stderr)
        return 1
    if problems:
        for problem in problems:
            print(
                f"alpha1-publication-preparation-closeout-check: {problem}",
                file=sys.stderr,
            )
        return 1
    print(
        "alpha1-publication-preparation-closeout-check: ok "
        f"merge={MERGE_REVISION[:12]} G2=pending G3=pending publication=false"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
