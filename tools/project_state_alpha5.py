#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Alpha.5 candidate truth used by the canonical project-state projection."""

from __future__ import annotations

import json
from typing import Any


IMPLEMENTATION_REVISION = "4683ecd9a1b9ead5eb84be152760d12583da0f0e"
CANDIDATE_REVISION = "4683ecd9a1b9ead5eb84be152760d12583da0f0e"
CANDIDATE_INTEGRATION_REVISION = "488994a81ddb5eb54d541ef3a48b64ca83f67d4a"
DEV_SYNC_REVISION = CANDIDATE_INTEGRATION_REVISION
CANDIDATE_TREE = "c07938618bc0f533fd12756cba123f54b8592048"
PHASE0_DEV_REVISION = "0d61feede2acd49bf54a4a7a1cd00bba3c867fb2"
PHASE0_DEV_TREE = "5ff92f7ee668a900dfe26bbdcba2c061492358de"
CURRENT_DEV_REVISION = "b94365074835c092b3c9a60b71d4ec985d0849d0"
CURRENT_DEV_TREE = "00c991ac4c6713da838534e66cc861e029d26f6d"
CANDIDATE_RUN = 33603385303
CANDIDATE_ATTEMPT = 1
CANDIDATE_RECEIPT = "release/index/alpha5_final_candidate_closeout.v1.toml"
CLOSEOUT_WORK_UNIT = "FACMAN-0.1-ALPHA5-FINAL-CANDIDATE-CLOSEOUT-01"
REMEDIATION_WORK_UNIT = "FACMAN-0.1-ALPHA5-TRUTH-REMEDIATION-01"
BETA_WORK_UNIT = "FACMAN-0.1-BETA-READINESS-01"
FINAL_ARTIFACT_ID = 9836639957
FINAL_ARTIFACT_DIGEST = (
    "sha256:1c53c1e1337dced910f8aa88c9d32c9a36a68d5b87dff2cce7172381f386e736"
)
FINAL_ARTIFACT_NAME = (
    "FacMan-0.1.0-alpha.5-unsigned-unpublished-candidate-"
    "33603385303-1-4683ecd9a1b9ead5eb84be152760d12583da0f0e"
)
CUSTODY_LOCATOR = (
    "facman-custody://candidates/"
    "facman-0.1-beta-candidate-main-4683ecd9-run-33603385303"
)
CUSTODY_MANIFEST_SHA256 = (
    "1be3a4ade7370a6c0ed51dc04eff5ce2ad86eb8034393cdaefa961acd8d4a923"
)
CUSTODY_CHECKSUMS_SHA256 = (
    "a9b8d06fc6d5062b41e68215399680dfa66689e3dacf9d062424f5d1547944b7"
)
PHASE = "facman_0_1_0_alpha_5_final_candidate_closeout"
PHASE_CONTRACT = {
    "checkpoint": "facman-0-1-alpha5-final-candidate-closeout",
    "active": CLOSEOUT_WORK_UNIT,
    "last_closed": REMEDIATION_WORK_UNIT,
    "next": CLOSEOUT_WORK_UNIT,
    "next_authority_gate": (
        "alpha6_workspace_migration_and_managed_install_then_alpha7_content_"
        "world_play_and_frontend_parity_then_feature_freeze_and_exact_beta_"
        "human_release_authority"
    ),
    "phase_status": (
        "alpha5_final_candidate_machine_qualified_truth_closeout_active_"
        "beta_gates_pending"
    ),
    "safety": (
        "final_candidate_machine_evidence_only_real_play_install_acceptance_"
        "signing_notarization_publication_and_support_authority_closed"
    ),
    "execution_reason": (
        "alpha5_final_candidate_truth_closeout_active_"
        "exact_play_route_unaccepted"
    ),
    "truth_scope": (
        "alpha5_final_candidate_machine_evidence_current_older_receipts_"
        "historical_all_human_execution_and_release_authority_closed"
    ),
    "user_workflow": (
        "close_final_alpha5_truth_then_consolidate_release_views_and_governance_"
        "then_alpha6_workspace_migration_"
        "managed_install_alpha7_content_world_play_frontends_feature_freeze_"
        "and_exact_beta_human_gates"
    ),
    "canonical_main_promotion": True,
    "canonical_integration": True,
    "local_counts_promoted": False,
    "playability": "product_complete_real_route_unaccepted",
    "platform_support": (
        "windows_x64_exact_candidate_reference_pending_human_macos_intel_and_"
        "linux_x64_machine_qualified_packages_semantic_gui_previews"
    ),
    "user_validation": (
        "exact_alpha5_candidate_machine_qualification_passed_human_"
        "acceptance_pending"
    ),
    "current_gate_status": (
        "alpha5_final_candidate_truth_closeout_active_external_play_"
        "install_accessibility_performance_security_and_release_gates_pending"
    ),
}

ACTIVE_RELEASE_PHASE = "facman_0_1_active_release_view_consolidation"
ACTIVE_RELEASE_WORK_UNIT = "FACMAN-ACTIVE-RELEASE-VIEW-CONSOLIDATION-01"
ACTIVE_RELEASE_PHASE_CONTRACT = {
    **PHASE_CONTRACT,
    "active": ACTIVE_RELEASE_WORK_UNIT,
    "next": ACTIVE_RELEASE_WORK_UNIT,
    "phase_status": (
        "alpha5_final_candidate_truth_closed_active_release_selection_"
        "consolidation_active_beta_gates_pending"
    ),
    "execution_reason": (
        "active_release_view_consolidation_active_exact_play_route_unaccepted"
    ),
    "truth_scope": (
        "one_active_release_selector_three_product_profiles_eight_assets_"
        "alpha5_final_candidate_machine_evidence_current_older_profiles_"
        "receipts_and_distributions_historical_all_human_execution_and_"
        "release_authority_closed"
    ),
    "user_workflow": (
        "consolidate_active_release_views_then_governance_alpha6_workspace_"
        "migration_managed_install_alpha7_content_world_play_frontends_"
        "feature_freeze_and_exact_beta_human_gates"
    ),
    "current_gate_status": (
        "active_release_view_consolidation_active_external_play_install_"
        "accessibility_performance_security_and_release_gates_pending"
    ),
}

REPOSITORY_IDENTITY_PHASE = "facman_0_1_beta_repository_identity_decision"
REPOSITORY_IDENTITY_WORK_UNIT = "FACMAN-BETA-REPOSITORY-IDENTITY-DECISION-01"
REPOSITORY_IDENTITY_PHASE_CONTRACT = {
    **ACTIVE_RELEASE_PHASE_CONTRACT,
    "checkpoint": "facman-0-1-phase0-integration-closeout",
    "active": REPOSITORY_IDENTITY_WORK_UNIT,
    "last_closed": ACTIVE_RELEASE_WORK_UNIT,
    "next": REPOSITORY_IDENTITY_WORK_UNIT,
    "phase_status": "phase0_integrations_closed_repository_identity_freeze_active",
    "execution_reason": (
        "repository_identity_freeze_active_exact_play_route_unaccepted"
    ),
    "truth_scope": (
        "phase0_integrations_verified_one_active_release_selector_repository_"
        "identity_freeze_active_alpha5_candidate_revision_exact_all_human_"
        "execution_and_release_authority_closed"
    ),
    "user_workflow": (
        "freeze_repository_identity_then_report_only_ruleset_assessment_then_"
        "alpha6_workspace_migration_managed_install_alpha7_content_world_play_"
        "frontends_feature_freeze_and_exact_beta_human_gates"
    ),
    "current_gate_status": (
        "repository_identity_freeze_active_ruleset_and_alpha6_pending"
    ),
}

REPOSITORY_IDENTITY_FROZEN_PHASE = "facman_0_1_beta_repository_identity_frozen"
RULESET_WORK_UNIT = "FACMAN-BETA-RULESET-AND-TAG-PROTECTION-01"
REPOSITORY_IDENTITY_FROZEN_PHASE_CONTRACT = {
    **REPOSITORY_IDENTITY_PHASE_CONTRACT,
    "active": "",
    "last_closed": REPOSITORY_IDENTITY_WORK_UNIT,
    "next": RULESET_WORK_UNIT,
    "phase_status": (
        "phase0_integrations_closed_repository_identity_frozen_"
        "ruleset_report_pending"
    ),
    "execution_reason": (
        "repository_identity_frozen_ruleset_report_pending_"
        "exact_play_route_unaccepted"
    ),
    "truth_scope": (
        "phase0_integrations_verified_one_active_release_selector_repository_"
        "identity_frozen_alpha5_candidate_revision_exact_ruleset_report_"
        "pending_all_human_execution_and_release_authority_closed"
    ),
    "user_workflow": (
        "complete_report_only_ruleset_assessment_then_alpha6_workspace_"
        "migration_managed_install_alpha7_content_world_play_frontends_"
        "feature_freeze_and_exact_beta_human_gates"
    ),
    "current_gate_status": (
        "repository_identity_frozen_ruleset_report_pending_alpha6_after_"
        "governance"
    ),
}

RULESET_REPORT_COMPLETE_PHASE = "facman_0_1_beta_ruleset_report_complete"
ALPHA6_WORKSPACE_WORK_UNIT = "FACMAN-0.1-ALPHA6-WORKSPACE-MIGRATION-RECOVERY-01"
RULESET_REPORT_COMPLETE_PHASE_CONTRACT = {
    **REPOSITORY_IDENTITY_FROZEN_PHASE_CONTRACT,
    "checkpoint": "facman-beta-ruleset-and-tag-protection-report",
    "active": "",
    "last_closed": RULESET_WORK_UNIT,
    "next": ALPHA6_WORKSPACE_WORK_UNIT,
    "phase_status": (
        "phase0_integrations_closed_repository_identity_frozen_"
        "ruleset_report_complete_alpha6_ready"
    ),
    "execution_reason": (
        "ruleset_report_complete_alpha6_ready_exact_play_route_unaccepted"
    ),
    "truth_scope": (
        "phase0_integrations_verified_one_active_release_selector_repository_"
        "identity_frozen_ruleset_report_complete_github_settings_unchanged_"
        "alpha5_candidate_revision_exact_all_human_execution_and_release_"
        "authority_closed"
    ),
    "user_workflow": (
        "start_alpha6_workspace_migration_managed_install_then_alpha7_content_"
        "world_play_frontends_feature_freeze_and_exact_beta_human_gates"
    ),
    "current_gate_status": (
        "ruleset_report_complete_alpha6_workspace_migration_ready"
    ),
}

RELEASE_TRAIN_PHASE_CONTRACTS = {
    PHASE: PHASE_CONTRACT,
    ACTIVE_RELEASE_PHASE: ACTIVE_RELEASE_PHASE_CONTRACT,
    REPOSITORY_IDENTITY_PHASE: REPOSITORY_IDENTITY_PHASE_CONTRACT,
    REPOSITORY_IDENTITY_FROZEN_PHASE: REPOSITORY_IDENTITY_FROZEN_PHASE_CONTRACT,
    RULESET_REPORT_COMPLETE_PHASE: RULESET_REPORT_COMPLETE_PHASE_CONTRACT,
}


def _toml_string(value: Any) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def current_state_release_train_lines(
    data: dict[str, Any], toml_string: Any
) -> list[str]:
    phase0 = data["phase0_integration_closeout"]
    identity = data["beta_repository_identity_decision"]
    ruleset = data["beta_ruleset_and_tag_protection"]
    return [
        "[phase0_integration_closeout]",
        f"status = {toml_string(phase0['status'])}",
        f"receipt = {toml_string(phase0['receipt'])}",
        f"canonical_dev_revision = {toml_string(phase0['canonical_dev_revision'])}",
        f"canonical_dev_tree = {toml_string(phase0['canonical_dev_tree'])}",
        f"merge_head_workflow_groups = {toml_string(phase0['merge_head_workflow_groups'])}",
        f"merge_head_checks = {toml_string(phase0['merge_head_checks'])}",
        "candidate_qualification_inherited = "
        f"{str(bool(phase0['candidate_qualification_inherited'])).lower()}",
        "",
        "[beta_repository_identity_decision]",
        f"status = {toml_string(identity['status'])}",
        f"work_unit = {toml_string(identity['work_unit'])}",
        f"receipt = {toml_string(identity['receipt'])}",
        f"canonical_slug = {toml_string(identity['canonical_slug'])}",
        f"github_repository_id = {int(identity['github_repository_id'])}",
        f"slug_status = {toml_string(identity['slug_status'])}",
        f"freeze_through = {toml_string(identity['freeze_through'])}",
        f"rename_authorized = {str(bool(identity['rename_authorized'])).lower()}",
        f"future_slug_candidate = {toml_string(identity['future_slug_candidate'])}",
        "future_slug_candidate_is_current_plan = "
        f"{str(bool(identity['future_slug_candidate_is_current_plan'])).lower()}",
        "",
        "[beta_ruleset_and_tag_protection]",
        f"status = {toml_string(ruleset['status'])}",
        f"work_unit = {toml_string(ruleset['work_unit'])}",
        f"decision = {toml_string(ruleset['decision'])}",
        f"observation_receipt = {toml_string(ruleset['observation_receipt'])}",
        f"cleanup_receipt = {toml_string(ruleset['cleanup_receipt'])}",
        f"branch_ruleset_id = {int(ruleset['branch_ruleset_id'])}",
        f"alpha_tag_ruleset_id = {int(ruleset['alpha_tag_ruleset_id'])}",
        "github_settings_changed = "
        f"{str(bool(ruleset['github_settings_changed'])).lower()}",
        "beta_rc_stable_tag_protection_present = "
        f"{str(bool(ruleset['beta_rc_stable_tag_protection_present'])).lower()}",
        f"next_work_unit = {toml_string(ruleset['next_work_unit'])}",
        "",
    ]


def expected_repository_identity(identity: Any) -> dict[str, Any]:
    return {
        "work_unit": REPOSITORY_IDENTITY_WORK_UNIT,
        "status": "canonical_slug_frozen_for_0_1_release_train",
        "manifest": "release/index/repository_identity.v1.toml",
        "facman_role": identity.role,
        "facman_github_repository_id": identity.github_repository_id,
        "facman_canonical_slug": identity.canonical_slug,
        "facman_canonical_https_remote": identity.canonical_https_remote,
        "facman_legacy_slugs": list(identity.legacy_slugs),
        "facman_product_name": identity.product_name,
        "facman_preferred_future_slug": identity.preferred_future_slug,
        "facman_rename_status": identity.rename_status,
        "facman_slug_status": identity.slug_status,
        "facman_freeze_through": identity.freeze_through,
        "facman_rename_authorized": identity.rename_authorized,
        "facman_future_slug_candidate": identity.future_slug_candidate,
        "facman_future_slug_candidate_is_current_plan": (
            identity.future_slug_candidate_is_current_plan
        ),
        "facman_workspace_names": list(identity.workspace_names),
        "observed_live_remote_classification": "canonical",
    }


def current_state_lines(value: dict[str, Any]) -> list[str]:
    """Render the exact compact alpha.5 candidate TOML table."""

    return [
        "[alpha5_exact_candidate]",
        f"status = {_toml_string(value['status'])}",
        f"work_unit = {_toml_string(value['work_unit'])}",
        f"closeout_work_unit = {_toml_string(value['closeout_work_unit'])}",
        "truth_remediation_work_unit = "
        f"{_toml_string(value['truth_remediation_work_unit'])}",
        f"receipt = {_toml_string(value['receipt'])}",
        f"source_revision = {_toml_string(value['candidate_source_revision'])}",
        f"source_tree = {_toml_string(value['candidate_source_tree'])}",
        f"run = {int(value['candidate_run'])}",
        f"attempt = {int(value['candidate_attempt'])}",
        f"archive_checkpoint = {_toml_string(value['archive_checkpoint'])}",
        f"candidate_artifact_name = {_toml_string(value['candidate_artifact_name'])}",
        f"bundle_artifact_digest = {_toml_string(value['bundle_artifact_digest'])}",
        f"custody_locator = {_toml_string(value['custody_locator'])}",
        f"custody_manifest_sha256 = {_toml_string(value['custody_manifest_sha256'])}",
        f"custody_checksums_sha256 = {_toml_string(value['custody_checksums_sha256'])}",
        f"bundle_artifact_id = {int(value['bundle_artifact_id'])}",
        f"bundle_file_count = {int(value['bundle_file_count'])}",
        "candidate_source_is_closeout_revision = "
        f"{str(bool(value['candidate_source_is_closeout_revision'])).lower()}",
        "candidate_source_is_dev_sync_revision = "
        f"{str(bool(value['candidate_source_is_dev_sync_revision'])).lower()}",
        "candidate_source_is_canonical_main_revision = "
        f"{str(bool(value['candidate_source_is_canonical_main_revision'])).lower()}",
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
        "accepted_integration_revision": CURRENT_DEV_REVISION,
        "reviewed_dev_checkpoint_revision": CURRENT_DEV_REVISION,
        "reviewed_dev_checkpoint_tree": CURRENT_DEV_TREE,
        "canonical_main_revision": CANDIDATE_REVISION,
        "promotion_source_revision": IMPLEMENTATION_REVISION,
        "planning_promotion_revision": CANDIDATE_REVISION,
        "dev_synchronization_revision": CURRENT_DEV_REVISION,
        "runtime_candidate_revision": CANDIDATE_REVISION,
        "qualification_source_revision": CANDIDATE_REVISION,
        "qualification_evidence_revision": CANDIDATE_REVISION,
        "qualification_integration_revision": CANDIDATE_INTEGRATION_REVISION,
        "truth_closeout_revision": CURRENT_DEV_REVISION,
    }
    for field, expected in exact_revision_roles.items():
        if status.get(field) != expected:
            problems.append(f"{field} must bind alpha.5 role {expected!r}")

    closeout = status.get("canonical_plan_and_truth_closeout", {})
    expected_closeout_roles = {
        "status": "phase0_integrations_closed",
        "work_unit": CLOSEOUT_WORK_UNIT,
        "promotion_source_revision": CANDIDATE_REVISION,
        "canonical_main_revision": status.get("canonical_main_revision"),
        "planning_promotion_revision": status.get("planning_promotion_revision"),
        "dev_synchronization_revision": PHASE0_DEV_REVISION,
        "dev_synchronization_tree": PHASE0_DEV_TREE,
        "candidate_source_tree": CANDIDATE_TREE,
        "candidate_run": CANDIDATE_RUN,
        "candidate_attempt": CANDIDATE_ATTEMPT,
        "candidate_receipt": CANDIDATE_RECEIPT,
        "candidate_source_is_closeout_revision": False,
        "closeout_revision_candidate_qualified": False,
        "synchronized_tree_extends_revision_qualification": False,
        "future_revision_requires_new_candidate_run": True,
        "main_is_ancestor_of_dev": True,
        "trees_equal": False,
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
        "status": "final_candidate_machine_qualified_beta_not_ready",
        "work_unit": CLOSEOUT_WORK_UNIT,
        "closeout_work_unit": CLOSEOUT_WORK_UNIT,
        "truth_remediation_work_unit": REMEDIATION_WORK_UNIT,
        "contract": "release/index/foundation_beta_readiness.v1.toml",
        "report": "docs/product/facman_0_1_beta_grand_master_plan.md",
        "receipt": CANDIDATE_RECEIPT,
        "candidate_source_revision": CANDIDATE_REVISION,
        "candidate_source_tree": CANDIDATE_TREE,
        "candidate_run": CANDIDATE_RUN,
        "candidate_attempt": CANDIDATE_ATTEMPT,
        "archive_checkpoint": "facman-0-1-alpha5-foundation-closed-2026-09-02",
        "candidate_artifact_name": FINAL_ARTIFACT_NAME,
        "bundle_artifact_digest": FINAL_ARTIFACT_DIGEST,
        "custody_locator": CUSTODY_LOCATOR,
        "custody_manifest_sha256": CUSTODY_MANIFEST_SHA256,
        "custody_checksums_sha256": CUSTODY_CHECKSUMS_SHA256,
        "bundle_artifact_id": FINAL_ARTIFACT_ID,
        "bundle_file_count": 14,
        "candidate_source_is_closeout_revision": False,
        "candidate_source_is_dev_sync_revision": False,
        "candidate_source_is_canonical_main_revision": True,
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
    if readiness.get("candidate_source_revision") != CANDIDATE_REVISION:
        problems.append(
            "alpha.5 qualification must bind the final canonical main candidate revision"
        )
    if readiness.get("candidate_source_revision") == DEV_SYNC_REVISION:
        problems.append("alpha.5 qualification must not transfer to the dev sync revision")
    ruleset = status.get("beta_ruleset_and_tag_protection", {})
    expected_ruleset = {
        "status": "report_complete_settings_unchanged",
        "work_unit": RULESET_WORK_UNIT,
        "decision": "release/index/beta_ruleset_and_tag_protection.v1.toml",
        "observation_receipt": (
            "release/receipts/facman-beta-ruleset-and-tag-protection-"
            "observation.v1.json"
        ),
        "cleanup_receipt": (
            "release/receipts/facman-phase0-workspace-cleanup.v1.json"
        ),
        "branch_ruleset_id": 20445007,
        "alpha_tag_ruleset_id": 21787868,
        "github_settings_changed": False,
        "beta_rc_stable_tag_protection_present": False,
        "next_work_unit": ALPHA6_WORKSPACE_WORK_UNIT,
    }
    for field, expected in expected_ruleset.items():
        if ruleset.get(field) != expected:
            problems.append(f"beta ruleset report {field} must be {expected!r}")
    return problems
