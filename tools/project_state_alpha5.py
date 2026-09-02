#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Alpha.5 candidate truth used by the canonical project-state projection."""

from __future__ import annotations

import json
from typing import Any


IMPLEMENTATION_REVISION = "d5bd6a18abd21d48359a05be6c3798fa224e95e3"
CANDIDATE_REVISION = "a7a518dbfe2a6d54da7b9c84fbd318300265e31d"
DEV_SYNC_REVISION = "43af71f8231c5a1b843636df7fd0ab8a6040d25c"
CANDIDATE_TREE = "1ebcd2b230ed188e021880ffa4c438de2ede655b"
CANDIDATE_RUN = 33576140943
CANDIDATE_ATTEMPT = 1
CANDIDATE_RECEIPT = "release/index/alpha5_promotion_candidate_closeout.v1.toml"
CLOSEOUT_WORK_UNIT = "FACMAN-0.1-ALPHA5-PROMOTION-CANDIDATE-CLOSEOUT-01"
BETA_WORK_UNIT = "FACMAN-0.1-BETA-READINESS-01"
ARCHIVE_CHECKPOINT = "facman-0-1-alpha5-foundation-closed-2026-09-02"
ARCHIVE_INDEX_SHA256 = (
    "eecc84950b0905e14f22ea5ad35066ec39cbd8fabf1d75ccb5a8b62164435c73"
)
PHASE = "facman_0_1_0_alpha_5_promotion_candidate_closeout"
PHASE_CONTRACT = {
    "checkpoint": "facman-0-1-alpha5-promotion-candidate-closeout-active",
    "active": CLOSEOUT_WORK_UNIT,
    "last_closed": BETA_WORK_UNIT,
    "next": CLOSEOUT_WORK_UNIT,
    "next_authority_gate": (
        "alpha6_managed_install_alpha7_play_frontend_parity_then_exact_beta_"
        "human_accessibility_and_release_authority"
    ),
    "phase_status": (
        "alpha5_promoted_synchronized_exact_candidate_qualified_closeout_"
        "active_beta_gates_pending"
    ),
    "safety": (
        "exact_candidate_machine_evidence_only_real_play_install_acceptance_"
        "signing_notarization_publication_and_support_authority_closed"
    ),
    "execution_reason": (
        "alpha5_exact_candidate_machine_qualified_closeout_active_exact_play_"
        "route_unaccepted"
    ),
    "truth_scope": (
        "alpha5_exact_candidate_source_qualified_closeout_active_alpha3_"
        "immutable_all_human_execution_and_release_authority_closed"
    ),
    "user_workflow": (
        "alpha5_exact_candidate_passed_then_complete_alpha6_managed_install_"
        "alpha7_play_frontend_parity_and_exact_beta_human_gates"
    ),
    "canonical_main_promotion": True,
    "canonical_integration": True,
    "local_counts_promoted": False,
    "playability": "product_complete_real_route_unaccepted",
    "platform_support": (
        "windows_x64_exact_candidate_reference_pending_human_macos_intel_and_"
        "linux_x64_exact_candidate_semantic_previews"
    ),
    "user_validation": (
        "exact_alpha5_candidate_machine_qualification_passed_human_"
        "acceptance_pending"
    ),
    "current_gate_status": (
        "alpha5_exact_candidate_passed_external_play_install_accessibility_"
        "performance_security_and_release_gates_pending"
    ),
}


def _toml_string(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def current_state_lines(value: dict[str, Any]) -> list[str]:
    """Render the exact compact alpha.5 candidate TOML table."""

    return [
        "[alpha5_exact_candidate]",
        f"status = {_toml_string(value['status'])}",
        f"work_unit = {_toml_string(value['work_unit'])}",
        f"closeout_work_unit = {_toml_string(value['closeout_work_unit'])}",
        f"receipt = {_toml_string(value['receipt'])}",
        f"source_revision = {_toml_string(value['candidate_source_revision'])}",
        f"source_tree = {_toml_string(value['candidate_source_tree'])}",
        f"run = {int(value['candidate_run'])}",
        f"attempt = {int(value['candidate_attempt'])}",
        f"archive_checkpoint = {_toml_string(value['archive_checkpoint'])}",
        f"archive_index_sha256 = {_toml_string(value['archive_index_sha256'])}",
        f"bundle_artifact_id = {int(value['bundle_artifact_id'])}",
        f"bundle_file_count = {int(value['bundle_file_count'])}",
        "candidate_source_is_closeout_revision = "
        f"{str(bool(value['candidate_source_is_closeout_revision'])).lower()}",
        "candidate_source_is_dev_sync_revision = "
        f"{str(bool(value['candidate_source_is_dev_sync_revision'])).lower()}",
        "closeout_revision_candidate_qualified = "
        f"{str(bool(value['closeout_revision_candidate_qualified'])).lower()}",
        "synchronized_tree_extends_revision_qualification = "
        f"{str(bool(value['synchronized_tree_extends_revision_qualification'])).lower()}",
        "current_main_after_closeout_qualified_by_this_receipt = "
        f"{str(bool(value['current_main_after_closeout_qualified_by_this_receipt'])).lower()}",
        "future_revision_requires_new_candidate_run = "
        f"{str(bool(value['future_revision_requires_new_candidate_run'])).lower()}",
        f"required_journeys = {int(value['required_journeys'])}",
        f"beta_ready = {str(bool(value['beta_ready'])).lower()}",
        f"factorio_execution = {str(bool(value['factorio_execution'])).lower()}",
        "managed_install_human_verdict = "
        f"{str(bool(value['managed_install_human_verdict'])).lower()}",
        "accessibility_human_verdict = "
        f"{str(bool(value['accessibility_human_verdict'])).lower()}",
        f"signing = {str(bool(value['signing'])).lower()}",
        f"notarization = {str(bool(value['notarization'])).lower()}",
        f"publication = {str(bool(value['publication'])).lower()}",
        f"support = {str(bool(value['support'])).lower()}",
        "",
    ]


def markdown_lines(value: dict[str, Any]) -> list[str]:
    """Render the exact human-facing alpha.5 candidate summary lines."""

    return [
        f"- alpha.5 exact candidate: source `{value['candidate_source_revision']}` "
        f"(tree `{value['candidate_source_tree']}`), run "
        f"`{value['candidate_run']}` attempt `{value['candidate_attempt']}`;",
        "- alpha.5 candidate boundary: closeout qualified "
        f"`{str(value['closeout_revision_candidate_qualified']).lower()}`; "
        "future revision requires a new run "
        f"`{str(value['future_revision_requires_new_candidate_run']).lower()}`;",
    ]


def summary_line(value: dict[str, Any]) -> str:
    """Return the compact command-line alpha.5 candidate summary."""

    return (
        f"alpha5_candidate: {value['candidate_source_revision']} "
        f"run={value['candidate_run']}/{value['candidate_attempt']} "
        "future_revision_requires_new_run="
        f"{str(value['future_revision_requires_new_candidate_run']).lower()}"
    )


def validate_status(status: dict[str, Any]) -> list[str]:
    """Validate exact alpha.5 topology, candidate, and authority truth."""

    problems: list[str] = []
    exact_revision_roles = {
        "implementation_proof_revision": IMPLEMENTATION_REVISION,
        "hosted_matrix_revision": CANDIDATE_REVISION,
        "accepted_integration_revision": DEV_SYNC_REVISION,
        "reviewed_dev_checkpoint_revision": DEV_SYNC_REVISION,
        "reviewed_dev_checkpoint_tree": CANDIDATE_TREE,
        "canonical_main_revision": CANDIDATE_REVISION,
        "promotion_source_revision": IMPLEMENTATION_REVISION,
        "planning_promotion_revision": CANDIDATE_REVISION,
        "dev_synchronization_revision": DEV_SYNC_REVISION,
        "runtime_candidate_revision": CANDIDATE_REVISION,
        "qualification_source_revision": CANDIDATE_REVISION,
        "qualification_evidence_revision": CANDIDATE_REVISION,
        "qualification_integration_revision": DEV_SYNC_REVISION,
        "truth_closeout_revision": DEV_SYNC_REVISION,
    }
    for field, expected in exact_revision_roles.items():
        if status.get(field) != expected:
            problems.append(f"{field} must bind alpha.5 role {expected!r}")

    closeout = status.get("canonical_plan_and_truth_closeout", {})
    expected_closeout_roles = {
        "work_unit": CLOSEOUT_WORK_UNIT,
        "promotion_source_revision": status.get("promotion_source_revision"),
        "canonical_main_revision": status.get("canonical_main_revision"),
        "planning_promotion_revision": status.get("planning_promotion_revision"),
        "dev_synchronization_revision": DEV_SYNC_REVISION,
        "candidate_source_tree": CANDIDATE_TREE,
        "candidate_run": CANDIDATE_RUN,
        "candidate_attempt": CANDIDATE_ATTEMPT,
        "candidate_receipt": CANDIDATE_RECEIPT,
        "candidate_source_is_closeout_revision": False,
        "closeout_revision_candidate_qualified": False,
        "synchronized_tree_extends_revision_qualification": False,
        "future_revision_requires_new_candidate_run": True,
        "main_is_ancestor_of_dev": True,
        "trees_equal": True,
    }
    for field, expected in expected_closeout_roles.items():
        if closeout.get(field) != expected:
            problems.append(
                f"canonical plan truth closeout {field} must be {expected!r}"
            )
    if closeout.get("external_gate") != (
        "FACMAN-WINDOWS-INSTANCE-ISOLATED-PLAY-REVALIDATION-04"
    ):
        problems.append("canonical plan truth closeout must observe revalidation-04")
    if closeout.get("external_gate_stage") != "staged_not_prepared":
        problems.append(
            "canonical plan truth closeout must preserve staged_not_prepared"
        )
    for field in (
        "prepare_authorized",
        "factorio_execution",
        "observer_capture",
        "permit_issuance",
        "route_promotion",
        "setup_mutation",
        "credential_authority",
        "network_authority",
        "signing",
        "publication",
    ):
        if closeout.get(field) is not False:
            problems.append(f"canonical plan truth closeout must keep {field} false")
    if closeout.get("human_verdict") != "unset":
        problems.append("canonical plan truth closeout must keep human verdict unset")

    readiness = status.get("alpha5_beta_readiness", {})
    expected_readiness = {
        "status": "exact_candidate_qualified_closeout_active_beta_not_ready",
        "work_unit": BETA_WORK_UNIT,
        "closeout_work_unit": CLOSEOUT_WORK_UNIT,
        "contract": "release/index/foundation_beta_readiness.v1.toml",
        "report": "docs/product/facman_0_1_beta_grand_master_plan.md",
        "receipt": CANDIDATE_RECEIPT,
        "candidate_source_revision": CANDIDATE_REVISION,
        "candidate_source_tree": CANDIDATE_TREE,
        "candidate_run": CANDIDATE_RUN,
        "candidate_attempt": CANDIDATE_ATTEMPT,
        "archive_checkpoint": ARCHIVE_CHECKPOINT,
        "archive_index_sha256": ARCHIVE_INDEX_SHA256,
        "bundle_artifact_id": 9826850751,
        "bundle_file_count": 14,
        "candidate_source_is_closeout_revision": False,
        "candidate_source_is_dev_sync_revision": False,
        "closeout_revision_candidate_qualified": False,
        "synchronized_tree_extends_revision_qualification": False,
        "current_main_after_closeout_qualified_by_this_receipt": False,
        "future_revision_requires_new_candidate_run": True,
        "required_journeys": 12,
        "beta_ready": False,
        "factorio_execution": False,
        "managed_install_human_verdict": False,
        "accessibility_human_verdict": False,
        "signing": False,
        "notarization": False,
        "publication": False,
        "support": False,
    }
    for field, expected in expected_readiness.items():
        if readiness.get(field) != expected:
            problems.append(f"alpha.5 exact candidate {field} must be {expected!r}")
    if readiness.get("candidate_source_revision") in {
        IMPLEMENTATION_REVISION,
        DEV_SYNC_REVISION,
    }:
        problems.append(
            "alpha.5 qualification must bind only the canonical main candidate revision"
        )
    return problems
