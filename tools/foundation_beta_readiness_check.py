#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the bounded, non-authorizing FacMan 0.1 beta-readiness contract."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "release/index/foundation_beta_readiness.v1.toml"
VERSION = ROOT / "release/index/version.v2.toml"
RELEASE_INDEX = ROOT / "release/index/release_index.v1.toml"
PLAN = ROOT / "release/index/plan.v1.toml"
ARTIFACT_MATRIX = ROOT / "release/index/artifact_matrix.v1.toml"
CANDIDATE_RECEIPT = ROOT / "release/index/alpha5_promotion_candidate_closeout.v1.toml"
CANDIDATE_SOURCE_REVISION = "a7a518dbfe2a6d54da7b9c84fbd318300265e31d"
CANDIDATE_SOURCE_TREE = "1ebcd2b230ed188e021880ffa4c438de2ede655b"
CANDIDATE_RUN = 33576140943
CANDIDATE_ATTEMPT = 1

JOURNEY_IDS = [f"J{number:02d}_{name}" for number, name in enumerate(
    (
        "first_run_workspace",
        "installation_library",
        "managed_local_install",
        "instance_lifecycle",
        "profile_configuration",
        "local_content_modpack",
        "worlds",
        "readiness_make_ready",
        "play_session",
        "recovery",
        "product_setup_maintenance",
        "diagnostics_support",
    ),
    start=1,
)]
PLATFORMS = ["windows_x64", "macos_intel_x64", "linux_x64"]
FRONTENDS = ["winforms", "gtk3", "appkit", "qt6", "winui", "swiftui"]
GATE_IDS = [
    "canonical_truth",
    "workspace_migration",
    "canonical_stage_equivalence",
    "gtk_appkit_semantic_parity",
    "exact_platform_machine_qualification",
    "final_release_asset_finalization",
    "content_world_application_integration",
    "performance_regression_baselines",
    "native_ux_visual_localization_acceptance",
    "repository_promotion_and_cleanup",
    "human_play_install_accessibility",
    "sign_notarize_publish_support",
]
JOURNEY_STATES = {
    "implemented_unqualified",
    "partially_implemented",
    "authority_blocked",
}
IMPLEMENTATION_STATES = {"implemented_unqualified", "partially_implemented"}
AUTHORITY_STATES = {"not_applicable", "blocked_external"}
PLATFORM_STATES = {
    "windows_x64": {
        "implemented_baseline_exact_candidate_pending",
        "exact_candidate_machine_qualified",
    },
    "macos_intel_x64": {
        "compatibility_shell_and_prototype_delivery",
        "exact_candidate_machine_qualified_semantic_preview_pending",
    },
    "linux_x64": {
        "compatibility_shell_and_prototype_delivery",
        "exact_candidate_machine_qualified_semantic_preview_pending",
    },
}
PLATFORM_BETA_CLAIMS = {
    "windows_x64": "reference_candidate_machine_qualified_human_support_pending",
    "macos_intel_x64": (
        "experimental_preview_machine_qualified_semantic_human_support_pending"
    ),
    "linux_x64": (
        "experimental_preview_machine_qualified_semantic_human_support_pending"
    ),
}
FRONTEND_LANES = {
    "winforms": (
        "beta_reference",
        "exact_candidate_machine_qualified_human_accessibility_visual_localization_support_pending",
    ),
    "gtk3": (
        "beta_preview",
        "exact_candidate_machine_qualified_transport_hardened_semantic_human_support_pending",
    ),
    "appkit": (
        "beta_preview",
        "exact_candidate_machine_qualified_semantic_human_support_pending",
    ),
    "qt6": ("post_beta_admission", "placeholder"),
    "winui": ("post_beta_admission", "placeholder"),
    "swiftui": ("post_beta_admission", "placeholder"),
}
GATE_STATES = {
    "canonical_truth": {"implemented_validation_pending", "machine_qualified"},
    "workspace_migration": {"known_actions_implemented_explicit_recovery_pending"},
    "canonical_stage_equivalence": {
        "contract_and_exact_workflow_implemented_candidate_pending",
        "exact_candidate_passed",
    },
    "gtk_appkit_semantic_parity": {
        "gtk_transport_hardened_semantic_convergence_pending"
    },
    "exact_platform_machine_qualification": {
        "workflow_ready_not_run",
        "exact_candidate_qualified",
    },
    "final_release_asset_finalization": {
        "deferred_exact_candidate_pending",
        "deferred_human_and_release_authority_pending",
    },
    "content_world_application_integration": {
        "internal_foundation_implemented_user_routes_pending"
    },
    "performance_regression_baselines": {"budgets_defined_measurement_pending"},
    "native_ux_visual_localization_acceptance": {
        "blocked_exact_candidate_human_review_pending"
    },
    "repository_promotion_and_cleanup": {
        "candidate_promoted_synchronized_closeout_cleanup_pending"
    },
    "human_play_install_accessibility": {"blocked_external"},
    "sign_notarize_publish_support": {"blocked_no_authority"},
}
NATIVE_UX_GATE = {
    "id": "native_ux_visual_localization_acceptance",
    "state": "blocked_exact_candidate_human_review_pending",
    "owner": "Jules",
    "frontends": ["winforms", "gtk3", "appkit"],
    "standards": [
        "windows_system_native_oem_plus",
        "gnome_hig_gtk3",
        "apple_hig_appkit",
    ],
    "requirements": [
        "platform_native_layout_and_interaction",
        "visual_hierarchy_spacing_typography_iconography_and_scaling",
        "localized_copy_and_pseudolocalized_text_expansion",
        "keyboard_focus_screen_reader_reduced_motion_and_contrast",
    ],
    "required_receipt_classes": [
        "exact_candidate_native_interaction_review",
        "exact_candidate_visual_review",
        "exact_candidate_localization_text_expansion_review",
        "exact_candidate_accessibility_review",
    ],
    "receipt_binding": "distinct_per_frontend_platform_exact_package_bytes",
    "human_verdict_required": True,
    "automation_cannot_satisfy": True,
}
FUTURE_WAVE_PLAN_GRAPH = {
    "alpha6_managed_install": (
        "FACMAN-0.1.0-ALPHA.6",
        "EPIC-0.1.0-ALPHA.6-MANAGED-INSTALL",
        "FACMAN-0.1-ALPHA6-MANAGED-INSTALL-LIFECYCLE-01",
        (
            (
                "FACMAN-0.1-ALPHA6-WORKSPACE-MIGRATION-RECOVERY-01",
                "FACMAN-0.1-ALPHA5-TRUTH-REMEDIATION-01",
            ),
            (
                "FACMAN-0.1-ALPHA6-MANAGED-INSTALL-LIFECYCLE-01",
                "FACMAN-0.1-ALPHA6-WORKSPACE-MIGRATION-RECOVERY-01",
            ),
        ),
    ),
    "alpha7_play_frontends": (
        "FACMAN-0.1.0-ALPHA.7",
        "EPIC-0.1.0-ALPHA.7-PLAY-FRONTENDS",
        "FACMAN-0.1-ALPHA7-PLAY-FRONTEND-CONVERGENCE-01",
        (
            (
                "FACMAN-0.1-ALPHA7-CONTENT-WORLD-ROUTES-01",
                "FACMAN-0.1-ALPHA6-MANAGED-INSTALL-LIFECYCLE-01",
            ),
            (
                "FACMAN-0.1-ALPHA7-PLAY-FRONTEND-CONVERGENCE-01",
                "FACMAN-0.1-ALPHA7-CONTENT-WORLD-ROUTES-01",
            ),
        ),
    ),
    "alphaN_feature_freeze": (
        "FACMAN-0.1-FEATURE-FREEZE",
        "EPIC-0.1-FEATURE-FREEZE",
        "FACMAN-0.1-FEATURE-FREEZE-01",
        (("FACMAN-0.1-FEATURE-FREEZE-01", "FACMAN-0.1-ALPHA7-PLAY-FRONTEND-CONVERGENCE-01"),),
    ),
    "beta1_exact_candidate": (
        "FACMAN-0.1.0-BETA.1",
        "EPIC-0.1.0-BETA.1-EXACT-RELEASE",
        "FACMAN-0.1-BETA1-EXACT-RELEASE-01",
        (("FACMAN-0.1-BETA1-EXACT-RELEASE-01", "FACMAN-0.1-FEATURE-FREEZE-01"),),
    ),
}


def _load(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        return tomllib.load(stream)


def _ids(rows: Any) -> list[str]:
    if not isinstance(rows, list):
        return []
    return [str(row.get("id", "")) for row in rows if isinstance(row, dict)]


def validate(
    readiness: dict[str, Any],
    version: dict[str, Any],
    release_index: dict[str, Any],
    artifact_matrix: dict[str, Any] | None = None,
    candidate_receipt: dict[str, Any] | None = None,
    plan: dict[str, Any] | None = None,
) -> list[str]:
    problems: list[str] = []
    artifact_matrix = artifact_matrix or _load(ARTIFACT_MATRIX)
    plan = plan or _load(PLAN)
    if candidate_receipt is None and CANDIDATE_RECEIPT.is_file():
        candidate_receipt = _load(CANDIDATE_RECEIPT)
    if readiness.get("schema") != "facman.foundation_beta_readiness.v1":
        problems.append("beta readiness has the wrong schema")
    if readiness.get("current_candidate") != version.get("semver"):
        problems.append("beta readiness current_candidate must match canonical version")
    if readiness.get("target_candidate") != "0.1.0-beta.1":
        problems.append("beta readiness must target 0.1.0-beta.1")
    if readiness.get("beta_ready") is not False:
        problems.append("beta_ready must remain false until exact machine and human gates close")
    if not str(readiness.get("status", "")).startswith("not_ready"):
        problems.append("readiness status must remain explicitly not-ready")
    if release_index.get("foundation_beta_readiness") != (
        "release/index/foundation_beta_readiness.v1.toml"
    ):
        problems.append("release index does not bind beta readiness")
    if release_index.get("alpha5_promotion_candidate_closeout") != (
        "release/index/alpha5_promotion_candidate_closeout.v1.toml"
    ):
        problems.append("release index does not bind alpha5 candidate closeout")
    if not CANDIDATE_RECEIPT.is_file():
        problems.append("alpha5 candidate closeout receipt is missing")
    contract = ROOT / str(readiness.get("contract", ""))
    if not contract.is_file():
        problems.append("beta readiness contract document is missing")

    required = readiness.get("required_journey_ids")
    if required != JOURNEY_IDS:
        problems.append("required journey identity/order must be the canonical J01-J12 set")
    journeys = readiness.get("journey", [])
    if _ids(journeys) != JOURNEY_IDS:
        problems.append("journey rows must exactly cover the canonical J01-J12 set")
    for row in journeys if isinstance(journeys, list) else []:
        if not isinstance(row, dict):
            problems.append("journey rows must be tables")
            continue
        journey_id = str(row.get("id", "<unknown>"))
        if row.get("required") is not True:
            problems.append(f"{journey_id} must remain beta-required")
        if row.get("state") not in JOURNEY_STATES:
            problems.append(f"{journey_id} has an invalid maturity state")
        implementation_state = row.get("implementation_state")
        authority_state = row.get("authority_state")
        if implementation_state not in IMPLEMENTATION_STATES:
            problems.append(f"{journey_id} has an invalid implementation state")
        if authority_state not in AUTHORITY_STATES:
            problems.append(f"{journey_id} has an invalid authority state")
        if row.get("state") == "authority_blocked":
            if implementation_state != "partially_implemented" or authority_state != "blocked_external":
                problems.append(f"{journey_id} authority block must retain a partial implementation state")
        elif row.get("state") != implementation_state or authority_state != "not_applicable":
            problems.append(f"{journey_id} combined state must agree with implementation and authority")
        if not row.get("beta_exit") or not row.get("blocking_evidence"):
            problems.append(f"{journey_id} must name exit and blocking evidence")

    platforms = readiness.get("platform", [])
    if _ids(platforms) != PLATFORMS:
        problems.append("platform rows must be Windows x64, macOS Intel x64, and Linux x64")
    for row in platforms if isinstance(platforms, list) else []:
        if not isinstance(row, dict):
            continue
        platform_id = str(row.get("id", ""))
        if row.get("current_state") not in PLATFORM_STATES.get(platform_id, set()):
            problems.append(f"{row.get('id', '<unknown>')} has an invalid evidence state")
        if row.get("beta_claim") != PLATFORM_BETA_CLAIMS.get(platform_id):
            problems.append(f"{row.get('id', '<unknown>')} has an invalid beta claim")
    lanes = readiness.get("frontend_lane", [])
    if _ids(lanes) != FRONTENDS:
        problems.append("frontend admission order has drifted")
    if [row.get("order") for row in lanes if isinstance(row, dict)] != list(range(1, 7)):
        problems.append("frontend lane order must be contiguous")
    for row in lanes if isinstance(lanes, list) else []:
        if not isinstance(row, dict):
            continue
        frontend_id = str(row.get("id", ""))
        expected_lane = FRONTEND_LANES.get(frontend_id)
        if expected_lane is None or (
            row.get("release_lane"), row.get("state")
        ) != expected_lane:
            problems.append(f"{frontend_id or '<unknown>'} frontend qualification state drifted")

    assets = readiness.get("public_product_assets", [])
    if not isinstance(assets, list) or len(assets) != 6 or len(set(assets)) != 6:
        problems.append("beta product contract must expose exactly six unique product assets")
    artifact_rows = artifact_matrix.get("artifact", [])
    matrix_products = [
        str(row.get("pattern", "")).replace("<version>", "{version}")
        for row in artifact_rows if isinstance(row, dict)
        and row.get("profile_id") != "release_metadata"
    ] if isinstance(artifact_rows, list) else []
    if assets != matrix_products:
        problems.append("beta product assets must equal the six product rows in artifact matrix")
    if artifact_matrix.get("release_version") != version.get("semver"):
        problems.append("artifact matrix release version must match canonical version")
    if artifact_matrix.get("authored_asset_count") != 8 or artifact_matrix.get(
        "primary_product_asset_count"
    ) != 6:
        problems.append("artifact matrix must distinguish six products from eight final assets")
    architecture = readiness.get("architecture", {})
    for field in (
        "one_domain_core",
        "one_semantic_presentation_boundary",
        "one_terminal_host",
        "one_canonical_stage_per_platform",
        "portable_and_setup_are_adapters",
        "foreign_installations_are_read_only",
        "owned_mutation_requires_plan_confirmation_journal_recovery",
        "providers_are_exact_external_inputs",
        "network_optional",
    ):
        if architecture.get(field) is not True:
            problems.append(f"architecture.{field} must be true")
    if architecture.get("rewrite_required") is not False:
        problems.append("the accepted architecture must not require a rewrite")

    candidate = readiness.get("exact_candidate", {})
    expected_candidate = {
        "status": "pass_unsigned_unpublished_non_authorizing",
        "receipt": "release/index/alpha5_promotion_candidate_closeout.v1.toml",
        "source_revision": CANDIDATE_SOURCE_REVISION,
        "source_tree": CANDIDATE_SOURCE_TREE,
        "workflow_run": CANDIDATE_RUN,
        "workflow_attempt": CANDIDATE_ATTEMPT,
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
    if candidate != expected_candidate:
        problems.append("exact candidate binding or non-circular qualification boundary differs")
    if not isinstance(candidate_receipt, dict):
        problems.append("alpha5 candidate closeout receipt could not be loaded")
    else:
        receipt_candidate = candidate_receipt.get("candidate", {})
        receipt_topology = candidate_receipt.get("revision_topology", {})
        if (
            candidate_receipt.get("candidate_producer")
            != "FACMAN-0.1-BETA-READINESS-01"
            or receipt_candidate.get("run_id") != CANDIDATE_RUN
            or receipt_candidate.get("attempt") != CANDIDATE_ATTEMPT
            or receipt_candidate.get("head_sha") != CANDIDATE_SOURCE_REVISION
            or receipt_candidate.get("head_tree") != CANDIDATE_SOURCE_TREE
            or receipt_topology.get("main_candidate_revision")
            != CANDIDATE_SOURCE_REVISION
            or receipt_topology.get("source_tree") != CANDIDATE_SOURCE_TREE
        ):
            problems.append("beta readiness and candidate receipt source/run binding differs")
        if candidate_receipt.get("non_circular") != {
            "candidate_source_is_closeout_revision": False,
            "candidate_source_is_dev_sync_revision": False,
            "closeout_revision_candidate_qualified": False,
            "synchronized_tree_extends_revision_qualification": False,
            "current_main_after_closeout_qualified_by_this_receipt": False,
            "future_revision_requires_new_candidate_run": True,
        }:
            problems.append("candidate receipt has a circular qualification boundary")
        receipt_authority = candidate_receipt.get("authority", {})
        if not receipt_authority or any(
            value is not False for value in receipt_authority.values()
        ):
            problems.append("candidate receipt must not grant external authority")

    authority = readiness.get("authority", {})
    if not authority or any(value is not False for value in authority.values()):
        problems.append("beta readiness must not grant external authority")
    waves = readiness.get("wave", [])
    wave_ids = _ids(waves)
    if wave_ids != [
        "alpha5_content_world_migration",
        "alpha6_managed_install",
        "alpha7_play_frontends",
        "alphaN_feature_freeze",
        "beta1_exact_candidate",
    ]:
        problems.append("the finite alpha-to-beta wave sequence has drifted")
    beta_wave = next((row for row in waves if row.get("id") == "beta1_exact_candidate"), {})
    if beta_wave.get("state") != "blocked":
        problems.append("beta.1 must remain blocked until all exact gates close")
    alpha5_wave = next(
        (row for row in waves if row.get("id") == "alpha5_content_world_migration"), {}
    )
    if alpha5_wave.get("state") != "promoted_synchronized_exact_candidate_qualified":
        problems.append("alpha5 wave must record protected exact-candidate qualification")
    releases = {
        row.get("id"): row for row in plan.get("release", []) if isinstance(row, dict)
    }
    epics = {
        row.get("id"): row for row in plan.get("epic", []) if isinstance(row, dict)
    }
    workunits = {
        row.get("id"): row for row in plan.get("workunit", []) if isinstance(row, dict)
    }
    waves_by_id = {
        row.get("id"): row for row in waves if isinstance(row, dict)
    }
    for wave_id, (release_id, epic_id, workunit_id, graph) in FUTURE_WAVE_PLAN_GRAPH.items():
        wave = waves_by_id.get(wave_id, {})
        if (
            wave.get("release_id"),
            wave.get("epic_id"),
            wave.get("workunit_id"),
        ) != (release_id, epic_id, workunit_id):
            problems.append(f"{wave_id} future wave plan binding has drifted")
            continue
        release = releases.get(release_id, {})
        epic = epics.get(epic_id, {})
        graph_ids = [item[0] for item in graph]
        if wave.get("workunit_ids") != graph_ids:
            problems.append(f"{wave_id} future wave WorkUnit sequence has drifted")
        if release.get("status") != "planned" or epic.get("status") != "planned":
            problems.append(f"{wave_id} future plan records must remain planned")
        if epic.get("release") != release_id:
            problems.append(f"{wave_id} future plan release/epic graph has drifted")
        for graph_workunit_id, dependency_id in graph:
            workunit = workunits.get(graph_workunit_id, {})
            if workunit.get("status") != "planned" or workunit.get("epic") != epic_id:
                problems.append(f"{wave_id} future plan WorkUnit graph has drifted")
            if workunit.get("depends_on") != [dependency_id]:
                problems.append(f"{wave_id} future plan dependency has drifted")
            if any(field in workunit for field in ("branch", "base_revision", "evidence")):
                problems.append(f"{wave_id} planned WorkUnit must not claim activation or evidence")
    gates = readiness.get("gate", [])
    if _ids(gates) != GATE_IDS:
        problems.append("beta gates must exactly cover the canonical ordered gate set")
    for row in gates if isinstance(gates, list) else []:
        if not isinstance(row, dict) or not row.get("state") or not row.get("owner"):
            problems.append("every beta gate must name a state and owner")
        elif row.get("state") not in GATE_STATES.get(str(row.get("id", "")), set()):
            problems.append(f"{row.get('id', '<unknown>')} has an invalid gate state")
    native_ux_gate = next(
        (
            row
            for row in gates
            if isinstance(row, dict)
            and row.get("id") == "native_ux_visual_localization_acceptance"
        ),
        {},
    )
    if native_ux_gate != NATIVE_UX_GATE:
        problems.append(
            "native UX, visual, localization, and exact receipt law has drifted"
        )
    if any(row.get("state") == "complete" for row in gates if isinstance(row, dict)):
        problems.append("no beta gate may claim complete while beta_ready is false")
    return problems


def detect() -> list[str]:
    return validate(
        _load(READINESS),
        _load(VERSION),
        _load(RELEASE_INDEX),
        _load(ARTIFACT_MATRIX),
        plan=_load(PLAN),
    )


def main() -> int:
    problems = detect()
    if problems:
        for problem in problems:
            print(f"foundation-beta-readiness-check: {problem}", file=sys.stderr)
        return 1
    print("foundation-beta-readiness-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
