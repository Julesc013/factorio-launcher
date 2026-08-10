# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the temporary, non-product-authorizing source-closure admission."""

from __future__ import annotations

import copy
import hashlib
import re
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
ROUTE_INDEX = ROOT / "release/index/successor_play_route.index.v1.toml"
PLAN = ROOT / "release/index/plan.v1.toml"
PROJECT_STATUS = ROOT / "release/index/project_status.v2.toml"
CURRENT_STATE = ROOT / "release/index/current_state.v1.toml"
QUEUE_ROOT = ROOT / ".aide/queue"

ADMISSION_WORK_UNIT = "FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-ADMISSION-01"
SOURCE_CLOSURE_WORK_UNIT = "FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01"
QUALIFICATION_WORK_UNIT = "FACMAN-SUCCESSOR-PLAY-QUALIFICATION-01"
ADMISSION_BRANCH = "task/facman-successor-play-source-closure-admission-01"
ADMISSION_BASE_REVISION = "4da0bf2c4c1df92d8e3a4d2d7eae39ebf65cba2f"
ADMISSION_BASE_TREE = "5e127a96825170c04b71736f6598aeb4a98ba0ef"
ACTIVE_ROUTE_ID = (
    "facman.play.windows-x64.factorio-2.0.77.standalone.menu."
    "instance-isolated.successor.v2"
)
SOURCE_CLOSURE_EVIDENCE_ID = "facman.successor-play.source-closure.02"

IMMUTABLE_INPUTS = {
    "release/index/successor_play_route.v1.toml": (
        "98561d1c956435d0d57fd7f184545c0fdfa3bf2586ec944c59b9ee75bdde8632"
    ),
    "release/index/successor_play_route.v2.toml": (
        "765545f0325b649a29c0dd175be52b879d7ada8db6b7ac2423da54c498d9bff8"
    ),
    "release/index/workspace_lock.v1.toml": (
        "510511d597ef4ff1ce58f198b7d45796d7723411d09ca15f0e87d539445408e3"
    ),
    "release/index/providers.lock.v2.toml": (
        "59376482126a8226bb28c5b5d73e980d21d3081b76bdf10bd5c10297f2462249"
    ),
    "tools/remote_source_closure.py": (
        "e48e1837ad897c7fff3a534deb9e98b5b5a045364b3c80a2a07e54fd56512506"
    ),
    "tools/repro_workspace_smoke.py": (
        "cd48080eef50d4b60d31efbdf2f23d83e8ed0cf6b2043a4155545f80330b3a59"
    ),
    "contracts/schema/release/remote_source_closure.v1.schema.json": (
        "5729afb042055405af4cebba6817090e2e0901227b2f614f973d5edc69cfbfc0"
    ),
}

REQUIRED_ALLOWED_PATHS = {
    "release/index/successor_play_route.index.v1.toml",
    "release/index/plan.v1.toml",
    "release/index/project_status.v2.toml",
    "release/index/current_state.v1.toml",
    "tools/source_closure_admission_check.py",
    "tests/test_source_closure_admission.py",
    "tests/test_aide_compaction.py",
    "tests/test_aide_target_truth.py",
}
REQUIRED_FORBIDDEN_PATHS = set(IMMUTABLE_INPUTS) | {
    "../universal-launcher/**",
    "../universal-setup/**",
}


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def workunit(plan: dict[str, Any], work_unit_id: str) -> dict[str, Any] | None:
    return next(
        (
            item
            for item in plan.get("workunit", [])
            if isinstance(item, dict) and item.get("id") == work_unit_id
        ),
        None,
    )


def yaml_list(path: Path, field: str) -> set[str]:
    text = path.read_text(encoding="utf-8")
    match = re.search(
        rf"(?m)^{re.escape(field)}:\s*\n((?:  - .*\n)*)",
        text,
    )
    if match is None:
        return set()
    return {
        line.removeprefix("  - ").strip()
        for line in match.group(1).splitlines()
        if line.startswith("  - ")
    }


def validate_index(record: dict[str, Any] | None = None) -> list[str]:
    from tools import successor_play_route_definition_check as route_check

    record = copy.deepcopy(record) if record is not None else load_toml(ROUTE_INDEX)
    problems = [
        f"route index: {problem}"
        for problem in route_check.validate_route_index(record, check_views=False)
    ]
    expected_top_level = {
        "new_evidence_execution_authorized": True,
        "mixed_route_evidence_allowed": False,
        "source_closure_execution_authorized": True,
        "route_capability_authorized": False,
        "route_promotion_authorized": False,
    }
    for field, expected in expected_top_level.items():
        if record.get(field) is not expected:
            problems.append(f"admission index {field} must be {expected}")

    routes = record.get("route", [])
    if not isinstance(routes, list) or len(routes) != 2:
        problems.append("admission index must contain exactly two route rows")
        return problems
    indexed = {
        str(item.get("route_id", "")): item
        for item in routes
        if isinstance(item, dict)
    }
    selected = indexed.get(ACTIVE_ROUTE_ID, {})
    if selected.get("new_evidence_target") is not True:
        problems.append("admission must keep route v2 as the sole evidence target")
    if selected.get("new_source_closure_evidence_allowed") is not True:
        problems.append("admission must open the route-v2 source-closure evidence gate")
    for field in (
        "new_qualification_evidence_allowed",
        "route_capability_creation_allowed",
        "route_promotion_allowed",
    ):
        if selected.get(field) is not False:
            problems.append(f"admission must keep route-v2 {field} false")
    for route_id, row in indexed.items():
        if route_id == ACTIVE_ROUTE_ID:
            continue
        for field in (
            "new_evidence_target",
            "new_source_closure_evidence_allowed",
            "new_qualification_evidence_allowed",
            "route_capability_creation_allowed",
            "route_promotion_allowed",
        ):
            if row.get(field) is not False:
                problems.append(f"admission unexpectedly opens historical route {field}")
    return problems


def validate_plan(record: dict[str, Any] | None = None) -> list[str]:
    record = copy.deepcopy(record) if record is not None else load_toml(PLAN)
    problems: list[str] = []
    active = [
        str(item.get("id"))
        for item in record.get("workunit", [])
        if isinstance(item, dict)
        and item.get("status") in {"active", "verified_pending_closeout"}
    ]
    if active != [ADMISSION_WORK_UNIT]:
        problems.append("canonical plan must expose only the admission WorkUnit as active")
    admission = workunit(record, ADMISSION_WORK_UNIT)
    source = workunit(record, SOURCE_CLOSURE_WORK_UNIT)
    qualification = workunit(record, QUALIFICATION_WORK_UNIT)
    if admission is None:
        return [*problems, "canonical plan is missing the admission WorkUnit"]
    expected = {
        "status": "active",
        "branch": ADMISSION_BRANCH,
        "base_revision": ADMISSION_BASE_REVISION,
        "base_tree": ADMISSION_BASE_TREE,
        "route_index_contract": "release/index/successor_play_route.index.v1.toml",
        "source_closure_evidence_id": SOURCE_CLOSURE_EVIDENCE_ID,
        "task_ref_run_limit": 1,
        "canonical_dev_run_limit": 1,
        "canonical_dev_run_requires_accepted_admission_merge": True,
        "self_revocation_required_after_canonical_closure": True,
    }
    for field, value in expected.items():
        if admission.get(field) != value:
            problems.append(f"admission WorkUnit {field} must be {value!r}")
    if admission.get("depends_on") != ["FACMAN-SUCCESSOR-PLAY-ROUTE-DEFINITION-02"]:
        problems.append("admission WorkUnit dependency is not exact")
    if source is None or source.get("status") != "blocked":
        problems.append("source-closure WorkUnit must remain blocked during admission")
    if qualification is None or qualification.get("status") != "planned":
        problems.append("qualification must remain planned during admission")
    return problems


def validate_queue() -> list[str]:
    from tools import aide_queue_records

    problems: list[str] = []
    try:
        records = aide_queue_records.read_queue_records(QUEUE_ROOT)
        problems.extend(aide_queue_records.validate_queue_index(QUEUE_ROOT, records))
    except aide_queue_records.QueueRecordError as exc:
        return [f"AIDE queue: {exc}"]
    active = [
        item.id
        for item in records
        if item.lifecycle_state in {"active", "active_automated", "awaiting_operator"}
    ]
    if active != [ADMISSION_WORK_UNIT]:
        problems.append("AIDE queue must expose only the admission WorkUnit as active")
    indexed = {item.id: item for item in records}
    admission = indexed.get(ADMISSION_WORK_UNIT)
    source = indexed.get(SOURCE_CLOSURE_WORK_UNIT)
    if admission is None or admission.status != "active" or admission.lifecycle_state != "active_automated":
        problems.append("AIDE admission record is not active_automated")
    if source is None or source.status != "blocked" or source.lifecycle_state != "blocked_external":
        problems.append("AIDE source-closure record is not blocked_external")
    return problems


def validate_task_scope() -> list[str]:
    task = QUEUE_ROOT / "active" / ADMISSION_WORK_UNIT / "task.yaml"
    if not task.is_file():
        return ["admission task record is missing"]
    allowed = yaml_list(task, "allowed_paths")
    forbidden = yaml_list(task, "forbidden_paths")
    problems: list[str] = []
    missing_allowed = sorted(REQUIRED_ALLOWED_PATHS - allowed)
    missing_forbidden = sorted(REQUIRED_FORBIDDEN_PATHS - forbidden)
    if missing_allowed:
        problems.append("admission allowed_paths omit: " + ", ".join(missing_allowed))
    if missing_forbidden:
        problems.append("admission forbidden_paths omit: " + ", ".join(missing_forbidden))
    if "release/index/successor_play_route.index.v1.toml" in forbidden:
        problems.append("admission route index cannot be both allowed and forbidden")
    return problems


def validate_project_truth(
    project: dict[str, Any] | None = None,
    current: dict[str, Any] | None = None,
) -> list[str]:
    project = copy.deepcopy(project) if project is not None else load_toml(PROJECT_STATUS)
    current = copy.deepcopy(current) if current is not None else load_toml(CURRENT_STATE)
    problems: list[str] = []
    for label, record in (("project status", project), ("current state", current)):
        if record.get("active_work_unit") != ADMISSION_WORK_UNIT:
            problems.append(f"{label} does not select the admission WorkUnit")
        convergence = record.get("provider_convergence", {})
        if convergence.get("active_work_unit") != ADMISSION_WORK_UNIT:
            problems.append(f"{label} provider convergence does not select admission")
        if convergence.get("next_work_unit") != ADMISSION_WORK_UNIT:
            problems.append(f"{label} provider convergence next WorkUnit drifted")
        if convergence.get("source_closure_state") != (
            "admission_active_task_ref_proof_pending"
        ):
            problems.append(f"{label} source-closure admission state drifted")
        for field in ("factorio_execution", "setup_mutation", "signing", "publication"):
            if convergence.get(field) is not False:
                problems.append(f"{label} unexpectedly opens {field}")
    project_product = project.get("product", {})
    if project_product.get("current_work_unit") != ADMISSION_WORK_UNIT:
        problems.append("project status product current WorkUnit drifted")
    if project_product.get("canonical_main_promotion") is not False:
        problems.append("project status unexpectedly opens canonical main promotion")
    current_product = current.get("product", {})
    if current_product.get("execution") != "unavailable":
        problems.append("current state unexpectedly makes product execution available")
    if current_product.get("release") != "unpublished":
        problems.append("current state unexpectedly publishes the product")
    if current_product.get("safe_beta") is not False:
        problems.append("current state unexpectedly promotes Safe beta")
    return problems


def validate_immutable_inputs() -> list[str]:
    problems: list[str] = []
    for relative, expected in IMMUTABLE_INPUTS.items():
        path = ROOT / relative
        if not path.is_file():
            problems.append(f"immutable admission input is missing: {relative}")
        elif sha256(path) != expected:
            problems.append(f"immutable admission input changed: {relative}")
    return problems


def validate_all() -> list[str]:
    return [
        *validate_index(),
        *validate_plan(),
        *validate_queue(),
        *validate_task_scope(),
        *validate_project_truth(),
        *validate_immutable_inputs(),
    ]


def main() -> int:
    problems = validate_all()
    if problems:
        for problem in problems:
            print(f"source-closure-admission-check: {problem}", file=sys.stderr)
        return 1
    print("source-closure-admission-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
