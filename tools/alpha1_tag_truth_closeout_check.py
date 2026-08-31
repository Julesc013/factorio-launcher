# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the sealed alpha.1 tag/control-plane truth closeout."""

from __future__ import annotations

import hashlib
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "release/index/alpha1_tag_truth_closeout.v1.toml"
ROUTE = ROOT / "release/index/successor_play_route.v5.toml"
PROJECT = ROOT / "release/index/project_status.v2.toml"
PLAN = ROOT / "release/index/plan.v1.toml"
RULESET_OBSERVATION = (
    ROOT / "release/receipts/facman-immutable-alpha-tag-ruleset-observation.v1.json"
)

WORK_UNIT = "FACMAN-0.1.0-ALPHA.1-TAG-TRUTH-CLOSEOUT-01"
PRODUCT_SOURCE = "fa60aaa17e9044bef7bb7347261056959690f1cd"
PRODUCT_TREE = "5536891662461d3617ee40e93654cb2f0659905c"
CONTROL_REVISION = "871fee8d63ead4493d4ef07d0442d6e0b06c8b3d"
DEV_REVISION = "31548e443955179d1fdfff2fe79d0019907d0a31"
DEV_TREE = "76c2075703c8ad83ddf415861b1a9294a5db2de5"
TAG = "v0.1.0-alpha.1"
TAG_OBJECT = "52a7a66092ff2b3b3c1059e9c29260f95b1cb287"
CANDIDATE = "8e18cf7b35d34aee2e39bc6bae0710db48dceef4196d5ff0373b880bfc866573"
TAG_RECEIPT = "b89822ae041e6b8c910f2aaec8c0105bd507998120fe5c4b5d05750d1e62f2c6"
CONTRACT_SET = "7d59831268babc1be96192f8ed74f5aa5f5c85d9d1fdf9e392cc943f99eae264"
PROVIDER_LOCK = "d33943841431afdeffb7961c7453d8999619ef371793a6310ad2c2952b118f00"
ROUTE_DIGEST = "d4627348d997ab20d8f5a540b8571bca145048ff6da365d0b42fdc18714c689e"
RULESET_OBSERVATION_SHA256 = (
    "9df8cbdd5e744096f58ba1ac058ecea2f0b9b9d89d6a4a42b92c2e655ff49a7d"
)

EXPECTED_PACKAGES = [
    {
        "id": "windows_cli_x64_portable",
        "filename": "facman-0.1.0-alpha.1-windows-cli-x64-portable.zip",
        "bytes": 4170461,
        "sha256": "62e45380674728cf7712238d96fd241bc1954780f24c5fe1dfea7e9bdde20fc5",
    },
    {
        "id": "windows_tui_x64_portable",
        "filename": "facman-0.1.0-alpha.1-windows-tui-x64-portable.zip",
        "bytes": 4166631,
        "sha256": "cadd6277438ec188946fd0ea6b6b77a52f430e784583af39fc2a3ca78de39b48",
    },
    {
        "id": "windows_winforms_x64_portable",
        "filename": "FacMan-0.1.0-alpha.1-windows-x64-portable.zip",
        "bytes": 6127233,
        "sha256": "00fcf5dfc9597a7118ad8d81ff4489d5ace6019c272e79bcc12e966547149c86",
    },
]

EXPECTED_WORKFLOWS = {
    "code-security": 33250441092,
    "bounded-provider-input-conformance": 33250441102,
    "ci": 33250441103,
    "schema-check": 33250441124,
    "synthetic-product-tck": 33250441129,
    "provider-sdk-consumption": 33250441148,
    "security-policy": 33250441162,
}

EXPECTED_AUTHORITY = {
    "tag_creation": False,
    "factorio_execution": False,
    "permit_issuance": False,
    "route_promotion": False,
    "publication": False,
    "signing": False,
    "support_activation": False,
    "main_promotion": False,
    "beta_rc_stable_promotion": False,
    "human_verdict": False,
}


def load(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        value = tomllib.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a TOML table")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _expect(
    problems: list[str], record: dict[str, Any], key: str, expected: Any, label: str
) -> None:
    if record.get(key) != expected:
        problems.append(f"{label}.{key} must equal {expected!r}")


def validate_receipt(value: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    for key, expected in {
        "schema": "facman.alpha1_tag_truth_closeout.v1",
        "status": "immutable_tag_and_tag_only_assets_verified",
        "work_unit": WORK_UNIT,
        "repository": "Julesc013/factorio-launcher",
        "product_version": "0.1.0-alpha.1",
        "machine_complete_rows": 29,
        "machine_total_rows": 29,
        "machine_completeness": "pass_29_of_29_product_machine_requirements",
    }.items():
        _expect(problems, value, key, expected, "closeout")

    frozen = value.get("frozen_product", {})
    for key, expected in {
        "source_revision": PRODUCT_SOURCE,
        "source_tree": PRODUCT_TREE,
        "release_significance": "package_bytes",
        "immutable": True,
        "next_product_byte_change": "0.1.0-alpha.2",
    }.items():
        _expect(problems, frozen, key, expected, "frozen_product")

    control = value.get("control_plane", {})
    for key, expected in {
        "tag_workflow_revision": CONTROL_REVISION,
        "tag_workflow_tree": "5cd260c461c75b93b60b0eaf3d9cf0d76f22cc4d",
        "reviewed_dev_revision": DEV_REVISION,
        "reviewed_dev_tree": DEV_TREE,
        "main_revision": "22d54a6c6a844f93db2d86dabcc35284bb074986",
    }.items():
        _expect(problems, control, key, expected, "control_plane")

    qualification = value.get("qualification", {})
    for key, expected in {
        "run_id": 33200886091,
        "result": "success",
        "candidate_sha256": CANDIDATE,
        "qualification_sha256": "83b439c4d6fff3dfabfd3f93d0d61f125ccb1113f5745c435e802631156e4c44",
        "three_root_evidence_sha256": "d73f310a45fcb9d5ae08b434b5d0323da212c201055b438ad4a056f05b381446",
        "machine_assets_artifact_id": 9699145778,
        "machine_assets_artifact_digest": "sha256:4d0e70c70df61c2d97cf8c155af02797d23d7d62f3a95bd9cfe7c01024160805",
        "qualification_evidence_artifact_id": 9699146540,
        "qualification_evidence_artifact_digest": "sha256:fed0b4744dbd6b881c2ca4f4dff08aa2ab7783abe9031249996989718c1421ed",
        "provider_lock_sha256": PROVIDER_LOCK,
        "workspace_lock_sha256": "b1590cc87bd50e5913196f1e3aa7a044028b30e9f1354b46a355b3db3f42c9bf",
        "contract_set_sha256": CONTRACT_SET,
    }.items():
        _expect(problems, qualification, key, expected, "qualification")

    ruleset = value.get("tag_ruleset", {})
    for key, expected in {
        "id": 21787868,
        "name": "FacMan immutable alpha tags",
        "target": "tag",
        "enforcement": "active",
        "include": ["refs/tags/v0.1.0-alpha.*"],
        "exclude": [],
        "rules": ["deletion", "update"],
        "bypass_actors": [],
        "current_user_can_bypass": "never",
        "observation_path": "release/receipts/facman-immutable-alpha-tag-ruleset-observation.v1.json",
        "observation_sha256": RULESET_OBSERVATION_SHA256,
    }.items():
        _expect(problems, ruleset, key, expected, "tag_ruleset")

    eligibility = value.get("eligibility", {})
    for key, expected in {
        "run_id": 33243814307,
        "control_revision": CONTROL_REVISION,
        "artifact_id": 9712179481,
        "artifact_name": "facman-alpha-tag-eligibility",
        "artifact_digest": "sha256:240d308c8c5297ec802a6ed1d1534dda6276ac5e7db304cc2d5504336a451d75",
        "eligibility_sha256": "799aa721ae16c2e4ec184ad7d975e87316280c2c530b07fff7aa3ffdb938cb49",
        "producer_receipt_sha256": "a5eb2bb7bd51b85913121b2a8fa7b14f853c178e8310bfce77e7d27d92f35068",
        "result": "success",
    }.items():
        _expect(problems, eligibility, key, expected, "eligibility")

    tag = value.get("tag", {})
    for key, expected in {
        "name": TAG,
        "target_revision": PRODUCT_SOURCE,
        "object_sha": TAG_OBJECT,
        "object_type": "annotated",
        "immutable": True,
        "run_id": 33243912537,
        "artifact_id": 9712214467,
        "artifact_name": "facman-alpha-tag-receipt",
        "artifact_digest": "sha256:7a7647ed641e8419195d4a70927c67e07649eec90bc3fb50fbfbdd1d4e5fcd7f",
        "receipt_sha256": TAG_RECEIPT,
        "result": "success",
    }.items():
        _expect(problems, tag, key, expected, "tag")

    assets = value.get("tag_asset_set", {})
    for key, expected in {
        "run_id": 33243989847,
        "control_revision": CONTROL_REVISION,
        "asset_artifact_id": 9712236798,
        "asset_artifact_name": "facman-alpha-1-tag-assets",
        "asset_artifact_digest": "sha256:40ba140657d9d7a53d1f4d614b6addd58e2513cbeb73094f77ac1ad6bf155191",
        "evidence_artifact_id": 9712236933,
        "evidence_artifact_name": "facman-alpha-1-tag-assembly-evidence",
        "evidence_artifact_digest": "sha256:4bd7b056a7396ca93ffd8c4b1f248311d4b2b6d0a3dc555b8988c363f14d5612",
        "asset_set_receipt_sha256": "d38cfd6ea9280dcda7e842707a145fa3e9e19b311434fe6a3713614968c5c1aa",
        "checksums_sha256": "d71d41d7050ff7e3c39900954f8c96d771b227ea6dea6029344c33e8800df487",
        "known_limitations_sha256": "ff9202a438aa22e5818b4482c5c8205e5e828bae3ddbbef4094e10c1e455e5d7",
        "file_count": 16,
        "checksum_failures": 0,
        "pending": [],
        "result": "success",
    }.items():
        _expect(problems, assets, key, expected, "tag_asset_set")

    if value.get("package") != EXPECTED_PACKAGES:
        problems.append("package set must match the exact three frozen archives")

    platform = value.get("platform_classification", {})
    for key, expected in {
        "windows": "Windows 10/11 x64 unsupported unsigned unpublished portable tag-only alpha",
        "linux_cli_tui": "exploratory package-preview evidence only",
        "linux_gtk": "frontend-only prototype; not a complete portable product package",
        "facman_sdk": "experimental engineering consumers; no public SDK compatibility promise",
    }.items():
        _expect(problems, platform, key, expected, "platform_classification")

    route = value.get("route_v5", {})
    for key, expected in {
        "status": "integrated_non_authorizing",
        "work_unit": "FACMAN-2.1.14-RELEASE-ROUTE-V5-01",
        "pull_request": 198,
        "pull_request_head": "89b9ec1d7a269aecc87a5b8f6910e2f898d99d21",
        "dev_merge_revision": DEV_REVISION,
        "dev_merge_tree": DEV_TREE,
        "definition_digest": ROUTE_DIGEST,
        "source_closure_digest": "6e3345e887540ac085d64b7fd0eeb54aa5e5ea77d2642abccd93549dcb9267dc",
        "accepted": False,
        "d3_active": False,
        "d4_active": False,
    }.items():
        _expect(problems, route, key, expected, "route_v5")
    workflows = {
        item.get("name"): item
        for item in route.get("workflow", [])
        if isinstance(item, dict)
    }
    if set(workflows) != set(EXPECTED_WORKFLOWS):
        problems.append("route_v5 workflows must contain the exact seven merged-dev runs")
    for name, run_id in EXPECTED_WORKFLOWS.items():
        workflow = workflows.get(name, {})
        if workflow.get("run_id") != run_id:
            problems.append(f"route_v5 workflow {name} has the wrong run ID")
        if workflow.get("head_sha") != DEV_REVISION:
            problems.append(f"route_v5 workflow {name} has the wrong head SHA")
        if workflow.get("conclusion") != "success":
            problems.append(f"route_v5 workflow {name} is not successful")

    human = value.get("human", {})
    for key, expected in {
        "packet_status": "exact_artifacts_bound_pending_human_execution",
        "receipt_id": "facman-0.1.0-alpha.1-portable-human-fa60aaa17e90",
        "receipt_sha256": "7f64271c91cfb0417cd205b5f22bfe79d66d746a60eef5ded33a627453950928",
        "result": "Inconclusive",
        "lane_count": 9,
        "inconclusive_lane_count": 9,
        "accepted_real_play_routes": 0,
        "tester": "UNASSIGNED_TEMPLATE_DO_NOT_ACCEPT",
    }.items():
        _expect(problems, human, key, expected, "human")

    release_state = value.get("release_state", {})
    if release_state.get("github_release_count") != 0:
        problems.append("release_state must record zero GitHub releases")
    if any(
        release_state.get(key) is not False
        for key in (
            "public_alpha", "beta_reached", "rc_reached", "main_promoted",
            "signed", "supported",
        )
    ):
        problems.append("release state must keep every later release state false")
    if value.get("authority") != EXPECTED_AUTHORITY:
        problems.append("authority must remain exactly and entirely closed")
    return problems


def validate_repository_bindings(
    value: dict[str, Any], route: dict[str, Any], project: dict[str, Any], plan: dict[str, Any]
) -> list[str]:
    problems: list[str] = []
    candidate = route.get("candidate", {})
    for key, expected in {
        "source_revision": PRODUCT_SOURCE,
        "source_tree": PRODUCT_TREE,
        "source_ref": f"refs/tags/{TAG}",
        "tag_object": TAG_OBJECT,
        "candidate_record_sha256": CANDIDATE,
        "tag_receipt_sha256": TAG_RECEIPT,
        "qualification_run_id": 33200886091,
        "contract_set_sha256": CONTRACT_SET,
        "package_sha256": EXPECTED_PACKAGES[2]["sha256"],
    }.items():
        if candidate.get(key) != expected:
            problems.append(f"route candidate {key} differs from sealed alpha.1 truth")
    if route.get("definition_digest") != ROUTE_DIGEST:
        problems.append("route definition digest differs from the integrated closeout")
    if any(value is not False for value in route.get("authority", {}).values()):
        problems.append("route v5 authority must remain entirely false")
    if sha256(RULESET_OBSERVATION) != RULESET_OBSERVATION_SHA256:
        problems.append("tracked tag-ruleset observation bytes changed")

    project_closeout = project.get("alpha1_tag_truth_closeout", {})
    if project_closeout.get("receipt") != "release/index/alpha1_tag_truth_closeout.v1.toml":
        problems.append("project status does not bind the tag truth closeout receipt")
    if project.get("last_closed_work_unit") != "FACMAN-ALPHA3-RELEASE-RECOVERY-01":
        problems.append("project status does not preserve tag truth through the alpha.3 draft recovery")
    if project.get("active_work_unit") != "":
        problems.append("project status must leave coding idle during alpha.3 human acceptance")
    product = project.get("product", {})
    if product.get("phase") != "facman_0_1_0_alpha_3_human_acceptance_pending":
        problems.append("project status does not expose the exact post-draft human gate")

    workunits = {
        item.get("id"): item
        for item in plan.get("workunit", [])
        if isinstance(item, dict)
    }
    if workunits.get(WORK_UNIT, {}).get("status") != "complete":
        problems.append("canonical plan does not record the tag truth closeout complete")
    for completed in (
        "FACMAN-0.1.0-ALPHA.1-DEV-INTEGRATION-CLOSEOUT-01",
        "FACMAN-2.1.14-RELEASE-ROUTE-V5-01",
    ):
        if workunits.get(completed, {}).get("status") != "complete":
            problems.append(f"canonical plan does not record {completed} complete")
    return problems


def check() -> list[str]:
    try:
        value = load(RECEIPT)
        route = load(ROUTE)
        project = load(PROJECT)
        plan = load(PLAN)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        return [f"tag truth closeout cannot be read: {exc}"]
    return validate_receipt(value) + validate_repository_bindings(
        value, route, project, plan
    )


def main() -> int:
    problems = check()
    if problems:
        for problem in problems:
            print(f"alpha1-tag-truth-closeout-check: {problem}", file=sys.stderr)
        return 1
    print("alpha1-tag-truth-closeout-check: ok (G1 sealed; later authorities closed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
