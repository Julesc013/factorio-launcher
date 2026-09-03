# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate closed source-closure state and the bounded admission contract."""

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
RECONCILIATION_WORK_UNIT = "FACMAN-DEV-RECONCILIATION-01"
SOURCE_CLOSURE_WORK_UNIT = "FACMAN-SUCCESSOR-PLAY-SOURCE-CLOSURE-01"
QUALIFICATION_WORK_UNIT = "FACMAN-SUCCESSOR-PLAY-QUALIFICATION-01"
CLOSEOUT_WORK_UNIT = "FACMAN-D1-INTEGRATION-CLOSEOUT-01"
ADOPTION_WORK_UNIT = "FACMAN-ULK-SESSION-PIN-ADOPTION-01"
WINDOWS_JOURNEY_WORK_UNIT = "FACMAN-WINDOWS-EXISTING-INSTALL-JOURNEY-01"
TECHNICAL_PREVIEW_CANDIDATE_WORK_UNIT = (
    "FACMAN-WINDOWS-TECHNICAL-PREVIEW-CANDIDATE-01"
)
ALPHA_RELEASE_SOURCE_WORK_UNIT = "FACMAN-0.1.0-ALPHA.1-RELEASE-SOURCE-01"
ALPHA_RELEASE_ROUTE_WORK_UNIT = "FACMAN-2.1.14-RELEASE-ROUTE-01"
ROUTE_PERMIT_ENFORCEMENT_WORK_UNIT = "FACMAN-2.1.14-ROUTE-PERMIT-ENFORCEMENT-01"
ALPHA_DELEGATION_WORK_UNIT = "FACMAN-AUTONOMOUS-ALPHA-DELEGATION-01"
FINAL_DISTRIBUTION_WORK_UNIT = "FACMAN-0.1.0-ALPHA.1-FINAL-INTEGRATION-01"
ALPHA_DEV_INTEGRATION_CLOSEOUT_WORK_UNIT = (
    "FACMAN-0.1.0-ALPHA.1-DEV-INTEGRATION-CLOSEOUT-01"
)
ALPHA4_FOUNDATION_WORK_UNIT = "FACMAN-0.1-ULTIMATE-REBASE-01"
BETA_READINESS_WORK_UNIT = "FACMAN-0.1-BETA-READINESS-01"
ALPHA5_CLOSEOUT_WORK_UNIT = "FACMAN-0.1-ALPHA5-PROMOTION-CANDIDATE-CLOSEOUT-01"
ALPHA5_TRUTH_REMEDIATION_WORK_UNIT = "FACMAN-0.1-ALPHA5-TRUTH-REMEDIATION-01"
ALPHA5_FINAL_CANDIDATE_WORK_UNIT = "FACMAN-0.1-ALPHA5-FINAL-CANDIDATE-CLOSEOUT-01"
ACTIVE_RELEASE_VIEW_WORK_UNIT = "FACMAN-ACTIVE-RELEASE-VIEW-CONSOLIDATION-01"
BETA_REPOSITORY_IDENTITY_WORK_UNIT = "FACMAN-BETA-REPOSITORY-IDENTITY-DECISION-01"
BETA_RULESET_WORK_UNIT = "FACMAN-BETA-RULESET-AND-TAG-PROTECTION-01"
REPOSITORY_IDENTITY_WORK_UNIT = "FACMAN-REPOSITORY-IDENTITY-DECOUPLING-01"
REPOSITORY_SLUG_DECISION_WORK_UNIT = "FACMAN-REPOSITORY-SLUG-DECISION-01"
POST_INTEGRATION_PHASES = {
    "ulk_session_promotion_and_adoption_01",
    "ulk_session_pin_adoption_01",
    "same_binary_tui_parity_01",
    "same_binary_tui_parity_closeout_01",
    "windows_existing_install_journey_01",
    "windows_technical_preview_candidate_01",
    "repository_identity_decoupling_01",
    "repository_slug_decision_01",
    "alpha_1_release_source_01",
    "alpha_1_release_route_01",
    "alpha_1_route_permit_integration_01",
    "facman_0_1_0_alpha_1_final_integration",
    "facman_0_1_0_alpha_1_dev_integration_closeout",
    "facman_0_1_0_alpha_1_tag_truth_closeout",
    "facman_2_1_14_route_d3_d4_request",
    "facman_0_1_0_alpha_1_publication_preparation",
    "facman_0_1_0_alpha_1_human_acceptance_pending",
    "facman_0_1_0_alpha_3_distribution_convergence",
    "facman_0_1_0_alpha_3_human_acceptance_pending",
    "facman_0_1_0_alpha_4_foundation_implementation",
    "facman_0_1_0_alpha_5_beta_readiness_convergence",
    "facman_0_1_0_alpha_5_promotion_candidate_closeout",
    "facman_0_1_0_alpha_5_truth_remediation",
    "facman_0_1_0_alpha_5_final_candidate_closeout",
    "facman_0_1_active_release_view_consolidation",
    "facman_0_1_beta_repository_identity_decision",
    "facman_0_1_beta_repository_identity_frozen",
    "facman_0_1_beta_ruleset_report_complete",
}
ADMISSION_BRANCH = "task/facman-successor-play-source-closure-admission-01"
ADMISSION_BASE_REVISION = "4da0bf2c4c1df92d8e3a4d2d7eae39ebf65cba2f"
ADMISSION_BASE_TREE = "5e127a96825170c04b71736f6598aeb4a98ba0ef"
RECONCILIATION_BRANCH = "task/facman-dev-reconciliation-01"
RECONCILIATION_BASE_REVISION = "4da0bf2c4c1df92d8e3a4d2d7eae39ebf65cba2f"
SYNTHESIZED_HEAD = "85648ff0bf0bef30b71bfb25a805c4082f144f9b"
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
    "tests/**",
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
        "new_evidence_execution_authorized": False,
        "mixed_route_evidence_allowed": False,
        "source_closure_execution_authorized": False,
        "route_capability_authorized": False,
        "route_promotion_authorized": False,
    }
    for field, expected in expected_top_level.items():
        if record.get(field) is not expected:
            problems.append(f"deferred index {field} must be {expected}")

    routes = record.get("route", [])
    if not isinstance(routes, list) or len(routes) != 2:
        problems.append("deferred index must contain exactly two route rows")
        return problems
    indexed = {
        str(item.get("route_id", "")): item
        for item in routes
        if isinstance(item, dict)
    }
    selected = indexed.get(ACTIVE_ROUTE_ID, {})
    if selected.get("new_evidence_target") is not True:
        problems.append("deferred state must keep route v2 as the sole evidence target")
    if selected.get("new_source_closure_evidence_allowed") is not False:
        problems.append("deferred state must close the route-v2 source-closure evidence gate")
    for field in (
        "new_qualification_evidence_allowed",
        "route_capability_creation_allowed",
        "route_promotion_allowed",
    ):
        if selected.get(field) is not False:
            problems.append(f"deferred state must keep route-v2 {field} false")
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
                problems.append(f"deferred state unexpectedly opens historical route {field}")
    return problems


def validate_integrated_admission(record: dict[str, Any]) -> list[str]:
    """Validate an explicitly constructed admission candidate, never current state."""

    from tools import successor_play_route_definition_check as route_check

    record = copy.deepcopy(record)
    problems = [
        f"admission candidate: {problem}"
        for problem in route_check.validate_route_index(
            record,
            check_views=False,
            admission_open=True,
        )
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
            problems.append(f"admission candidate {field} must be {expected}")
    routes = record.get("route", [])
    indexed = {
        str(item.get("route_id", "")): item
        for item in routes
        if isinstance(item, dict)
    }
    selected = indexed.get(ACTIVE_ROUTE_ID, {})
    if selected.get("new_source_closure_evidence_allowed") is not True:
        problems.append("admission candidate must open only route-v2 source closure")
    return problems


def validate_plan(record: dict[str, Any] | None = None) -> list[str]:
    record = copy.deepcopy(record) if record is not None else load_toml(PLAN)
    problems: list[str] = []
    reconciliation_lifecycle_ids = {
        ADMISSION_WORK_UNIT,
        RECONCILIATION_WORK_UNIT,
        SOURCE_CLOSURE_WORK_UNIT,
        QUALIFICATION_WORK_UNIT,
        CLOSEOUT_WORK_UNIT,
    }
    active = [
        str(item.get("id"))
        for item in record.get("workunit", [])
        if isinstance(item, dict)
        and item.get("id") in reconciliation_lifecycle_ids
        and item.get("status") in {"active", "verified_pending_closeout"}
    ]
    closeout = workunit(record, CLOSEOUT_WORK_UNIT)
    post_integration = closeout is not None and closeout.get("status") == "complete"
    expected_active = [] if post_integration else [RECONCILIATION_WORK_UNIT]
    if active != expected_active:
        problems.append(
            "canonical plan active WorkUnits do not match the reconciliation lifecycle"
        )
    reconciliation = workunit(record, RECONCILIATION_WORK_UNIT)
    admission = workunit(record, ADMISSION_WORK_UNIT)
    source = workunit(record, SOURCE_CLOSURE_WORK_UNIT)
    qualification = workunit(record, QUALIFICATION_WORK_UNIT)
    if reconciliation is None:
        return [*problems, "canonical plan is missing the reconciliation WorkUnit"]
    reconciliation_expected = {
        "status": "complete" if post_integration else "active",
        "branch": RECONCILIATION_BRANCH,
        "base_revision": RECONCILIATION_BASE_REVISION,
        "synthesized_head": SYNTHESIZED_HEAD,
        "source_closure_status": "deferred_external",
        "source_closure_result": "not_run",
        "current_valid_evidence": [],
    }
    for field, value in reconciliation_expected.items():
        if reconciliation.get(field) != value:
            problems.append(f"reconciliation WorkUnit {field} must be {value!r}")
    if admission is None:
        return [*problems, "canonical plan is missing the admission WorkUnit"]
    expected = {
        "status": "superseded",
        "branch": ADMISSION_BRANCH,
        "base_revision": ADMISSION_BASE_REVISION,
        "base_tree": ADMISSION_BASE_TREE,
        "route_index_contract": "release/index/successor_play_route.index.v1.toml",
        "source_closure_evidence_id": SOURCE_CLOSURE_EVIDENCE_ID,
        "task_ref_run_limit": 1,
        "canonical_dev_run_limit": 1,
        "canonical_dev_run_requires_accepted_admission_merge": True,
        "self_revocation_required_after_canonical_closure": True,
        "source_closure_status": "deferred_external",
        "source_closure_result": "not_run",
        "current_valid_evidence": [],
    }
    for field, value in expected.items():
        if admission.get(field) != value:
            problems.append(f"admission WorkUnit {field} must be {value!r}")
    if admission.get("depends_on") != ["FACMAN-SUCCESSOR-PLAY-ROUTE-DEFINITION-02"]:
        problems.append("admission WorkUnit dependency is not exact")
    expected_source_status = "superseded" if post_integration else "blocked"
    if source is None or source.get("status") != expected_source_status:
        problems.append(
            "source-closure WorkUnit status does not match the reconciliation lifecycle"
        )
    elif any(
        source.get(field) != expected
        for field, expected in {
            "source_closure_status": "deferred_external",
            "source_closure_result": "not_run",
            "current_valid_evidence": [],
        }.items()
    ):
        problems.append("source-closure WorkUnit does not record the exact deferred result")
    expected_qualification_status = "cancelled" if post_integration else "planned"
    if qualification is None or qualification.get("status") != expected_qualification_status:
        problems.append("qualification status does not match the reconciliation lifecycle")
    if post_integration:
        adoption = workunit(record, ADOPTION_WORK_UNIT)
        if adoption is None:
            problems.append("post-integration plan must retain FacMan ULK adoption")
        elif adoption.get("status") == "blocked":
            if not adoption.get("blockers"):
                problems.append("blocked FacMan ULK adoption must name its promotion blocker")
        elif adoption.get("status") in {"ready", "complete"}:
            if adoption.get("blockers") != []:
                problems.append(
                    f"{adoption.get('status')} FacMan ULK adoption must have no remaining blocker"
                )
        else:
            problems.append(
                "post-integration FacMan ULK adoption must be blocked, ready, or complete"
            )
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
    closeout = indexed_closeout = next(
        (item for item in records if item.id == CLOSEOUT_WORK_UNIT), None
    )
    post_integration = (
        load_toml(PROJECT_STATUS).get("product", {}).get("phase")
        in POST_INTEGRATION_PHASES
    )
    expected_active_sets = (
        {CLOSEOUT_WORK_UNIT},
        {REPOSITORY_IDENTITY_WORK_UNIT},
        {REPOSITORY_SLUG_DECISION_WORK_UNIT},
        {TECHNICAL_PREVIEW_CANDIDATE_WORK_UNIT},
        {ALPHA_RELEASE_SOURCE_WORK_UNIT},
        {ALPHA_RELEASE_ROUTE_WORK_UNIT},
        {ROUTE_PERMIT_ENFORCEMENT_WORK_UNIT},
        {ALPHA_DELEGATION_WORK_UNIT},
        {FINAL_DISTRIBUTION_WORK_UNIT},
        {ALPHA_DEV_INTEGRATION_CLOSEOUT_WORK_UNIT},
        {"FACMAN-ALPHA3-DISTRIBUTION-CONVERGENCE-01"},
        {ALPHA4_FOUNDATION_WORK_UNIT},
        {BETA_READINESS_WORK_UNIT},
        {ALPHA5_CLOSEOUT_WORK_UNIT},
        {ALPHA5_TRUTH_REMEDIATION_WORK_UNIT},
        {ALPHA5_FINAL_CANDIDATE_WORK_UNIT},
        {ACTIVE_RELEASE_VIEW_WORK_UNIT},
        {BETA_REPOSITORY_IDENTITY_WORK_UNIT},
        {BETA_RULESET_WORK_UNIT},
        set(),
    ) if post_integration else ({RECONCILIATION_WORK_UNIT},)
    if set(active) not in expected_active_sets:
        problems.append("AIDE queue active set does not match the reconciliation lifecycle")
    indexed = {item.id: item for item in records}
    reconciliation = indexed.get(RECONCILIATION_WORK_UNIT)
    admission = indexed.get(ADMISSION_WORK_UNIT)
    source = indexed.get(SOURCE_CLOSURE_WORK_UNIT)
    if post_integration:
        if reconciliation is None or reconciliation.status != "passed" or reconciliation.lifecycle_state != "closed":
            problems.append("AIDE reconciliation record is not closed after integration")
    elif reconciliation is None or reconciliation.status != "active" or reconciliation.lifecycle_state != "active_automated":
        problems.append("AIDE reconciliation record is not active_automated")
    if admission is None or admission.status != "superseded" or admission.lifecycle_state != "superseded":
        problems.append("AIDE admission record is not superseded")
    if post_integration:
        if source is None or source.status != "superseded" or source.lifecycle_state != "superseded":
            problems.append("AIDE source-closure record is not superseded after integration")
    elif source is None or source.status != "blocked" or source.lifecycle_state != "blocked_external":
        problems.append("AIDE source-closure record is not blocked_external")
    return problems


def validate_task_scope() -> list[str]:
    task = QUEUE_ROOT / "active" / RECONCILIATION_WORK_UNIT / "task.yaml"
    if not task.is_file():
        return ["reconciliation task record is missing"]
    allowed = yaml_list(task, "allowed_paths")
    forbidden = yaml_list(task, "forbidden_paths")
    problems: list[str] = []
    missing_allowed = sorted(REQUIRED_ALLOWED_PATHS - allowed)
    missing_forbidden = sorted(REQUIRED_FORBIDDEN_PATHS - forbidden)
    if missing_allowed:
        problems.append("reconciliation allowed_paths omit: " + ", ".join(missing_allowed))
    if missing_forbidden:
        problems.append("reconciliation forbidden_paths omit: " + ", ".join(missing_forbidden))
    if "release/index/successor_play_route.index.v1.toml" in forbidden:
        problems.append("reconciliation route index cannot be both allowed and forbidden")
    return problems


def validate_project_truth(
    project: dict[str, Any] | None = None,
    current: dict[str, Any] | None = None,
) -> list[str]:
    project = copy.deepcopy(project) if project is not None else load_toml(PROJECT_STATUS)
    current = copy.deepcopy(current) if current is not None else load_toml(CURRENT_STATE)
    problems: list[str] = []
    post_integration = project.get("product", {}).get("phase") in POST_INTEGRATION_PHASES
    expected_active = (
        str(project.get("product", {}).get("current_work_unit", ""))
        if post_integration else RECONCILIATION_WORK_UNIT
    )
    expected_provider_active = "" if post_integration else RECONCILIATION_WORK_UNIT
    provider_convergence = project.get("provider_convergence", {})
    adoption_complete = (
        provider_convergence.get("completed_phase") == "ulk_session_pin_adoption"
        and provider_convergence.get("universal_launcher_consumed_pin")
            == "09f0639ab6529fba2f2aa22e9bf68e5eebed0553"
    )
    phase = project.get("product", {}).get("phase")
    if phase in {
        "repository_identity_decoupling_01",
        "repository_slug_decision_01",
        "alpha_1_release_source_01",
        "alpha_1_release_route_01",
        "alpha_1_route_permit_integration_01",
        "facman_0_1_0_alpha_1_final_integration",
        "facman_0_1_0_alpha_1_dev_integration_closeout",
        "facman_0_1_0_alpha_1_tag_truth_closeout",
        "facman_2_1_14_route_d3_d4_request",
        "facman_0_1_0_alpha_1_publication_preparation",
        "facman_0_1_0_alpha_1_human_acceptance_pending",
        "facman_0_1_0_alpha_3_distribution_convergence",
        "facman_0_1_0_alpha_3_human_acceptance_pending",
        "facman_0_1_0_alpha_4_foundation_implementation",
        "facman_0_1_0_alpha_5_beta_readiness_convergence",
        "facman_0_1_0_alpha_5_promotion_candidate_closeout",
        "facman_0_1_0_alpha_5_truth_remediation",
        "facman_0_1_0_alpha_5_final_candidate_closeout",
        "facman_0_1_active_release_view_consolidation",
        "facman_0_1_beta_repository_identity_decision",
        "facman_0_1_beta_repository_identity_frozen",
        "facman_0_1_beta_ruleset_report_complete",
    }:
        expected_next = TECHNICAL_PREVIEW_CANDIDATE_WORK_UNIT
    elif phase == "windows_technical_preview_candidate_01":
        expected_next = TECHNICAL_PREVIEW_CANDIDATE_WORK_UNIT
    elif phase == "windows_existing_install_journey_01":
        expected_next = WINDOWS_JOURNEY_WORK_UNIT
    elif adoption_complete:
        expected_next = "FACMAN-SAME-BINARY-TUI-PARITY-CLOSEOUT-01"
    else:
        expected_next = ADOPTION_WORK_UNIT if post_integration else RECONCILIATION_WORK_UNIT
    for label, record in (("project status", project), ("current state", current)):
        if record.get("active_work_unit") != expected_active:
            problems.append(f"{label} active WorkUnit does not match the reconciliation lifecycle")
        convergence = record.get("provider_convergence", {})
        if convergence.get("active_work_unit") != expected_provider_active:
            problems.append(f"{label} provider convergence active WorkUnit drifted")
        if convergence.get("next_work_unit") != expected_next:
            problems.append(f"{label} provider convergence next WorkUnit drifted")
        expected_deferred = {
            "source_closure_state": "deferred_external",
            "source_closure_status": "deferred_external",
            "source_closure_result": "not_run",
            "current_valid_evidence": [],
        }
        for field, expected in expected_deferred.items():
            if convergence.get(field) != expected:
                problems.append(f"{label} source-closure {field} drifted")
        for field in ("factorio_execution", "setup_mutation", "signing", "publication"):
            if convergence.get(field) is not False:
                problems.append(f"{label} unexpectedly opens {field}")
    project_product = project.get("product", {})
    if project_product.get("current_work_unit") != expected_active:
        problems.append("project status product current WorkUnit drifted")
    expected_main_promotion = phase in {
        "repository_slug_decision_01",
        "windows_technical_preview_candidate_01",
        "facman_0_1_0_alpha_3_human_acceptance_pending",
        "facman_0_1_0_alpha_5_promotion_candidate_closeout",
        "facman_0_1_0_alpha_5_truth_remediation",
        "facman_0_1_0_alpha_5_final_candidate_closeout",
        "facman_0_1_active_release_view_consolidation",
        "facman_0_1_beta_repository_identity_decision",
        "facman_0_1_beta_repository_identity_frozen",
        "facman_0_1_beta_ruleset_report_complete",
    }
    if project_product.get("canonical_main_promotion") is not expected_main_promotion:
        problems.append("project status canonical main promotion truth drifted")
    current_product = current.get("product", {})
    if current_product.get("execution") != "unavailable":
        problems.append("current state unexpectedly makes product execution available")
    if current_product.get("release") != "unpublished":
        problems.append("current state unexpectedly publishes the product")
    if current_product.get("safe_beta") is not False:
        problems.append("current state unexpectedly promotes Safe beta")
    if phase in {
        "facman_0_1_0_alpha_5_promotion_candidate_closeout",
        "facman_0_1_0_alpha_5_truth_remediation",
        "facman_0_1_0_alpha_5_final_candidate_closeout",
        "facman_0_1_active_release_view_consolidation",
        "facman_0_1_beta_repository_identity_decision",
        "facman_0_1_beta_repository_identity_frozen",
        "facman_0_1_beta_ruleset_report_complete",
    }:
        current_dev = (
            "b94365074835c092b3c9a60b71d4ec985d0849d0"
            if phase == "facman_0_1_beta_ruleset_report_complete"
            else "0d61feede2acd49bf54a4a7a1cd00bba3c867fb2"
        )
        expected_roles = {
            "promotion_source_revision": "4683ecd9a1b9ead5eb84be152760d12583da0f0e",
            "canonical_main_revision": "4683ecd9a1b9ead5eb84be152760d12583da0f0e",
            "dev_synchronization_revision": current_dev,
            "qualification_source_revision": "4683ecd9a1b9ead5eb84be152760d12583da0f0e",
            "qualification_integration_revision": "488994a81ddb5eb54d541ef3a48b64ca83f67d4a",
            "truth_closeout_revision": current_dev,
        }
        for field, expected in expected_roles.items():
            if project.get(field) != expected:
                problems.append(f"project status alpha.5 {field} drifted")
        alpha5 = project.get("alpha5_beta_readiness", {})
        expected_boundaries = {
            "candidate_source_revision": "4683ecd9a1b9ead5eb84be152760d12583da0f0e",
            "candidate_source_tree": "c07938618bc0f533fd12756cba123f54b8592048",
            "candidate_source_is_closeout_revision": False,
            "candidate_source_is_dev_sync_revision": False,
            "closeout_revision_candidate_qualified": False,
            "synchronized_tree_extends_revision_qualification": False,
            "current_main_after_closeout_qualified_by_this_receipt": False,
            "future_revision_requires_new_candidate_run": True,
            "beta_ready": False,
            "factorio_execution": False,
            "signing": False,
            "notarization": False,
            "publication": False,
            "support": False,
        }
        for field, expected in expected_boundaries.items():
            if alpha5.get(field) != expected:
                problems.append(f"project status alpha.5 boundary {field} drifted")
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
