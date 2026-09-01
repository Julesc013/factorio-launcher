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
ARTIFACT_MATRIX = ROOT / "release/index/artifact_matrix.v1.toml"

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
    "final_release_asset_finalization": {"deferred_exact_candidate_pending"},
    "content_world_application_integration": {
        "internal_foundation_implemented_user_routes_pending"
    },
    "performance_regression_baselines": {"budgets_defined_measurement_pending"},
    "repository_promotion_and_cleanup": {
        "pending_validated_promotion",
        "promoted_synchronized_clean",
    },
    "human_play_install_accessibility": {"blocked_external"},
    "sign_notarize_publish_support": {"blocked_no_authority"},
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
) -> list[str]:
    problems: list[str] = []
    artifact_matrix = artifact_matrix or _load(ARTIFACT_MATRIX)
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
        if isinstance(row, dict) and row.get("current_state") not in PLATFORM_STATES.get(
            str(row.get("id", "")), set()
        ):
            problems.append(f"{row.get('id', '<unknown>')} has an invalid evidence state")
    lanes = readiness.get("frontend_lane", [])
    if _ids(lanes) != FRONTENDS:
        problems.append("frontend admission order has drifted")
    if [row.get("order") for row in lanes if isinstance(row, dict)] != list(range(1, 7)):
        problems.append("frontend lane order must be contiguous")
    for row in lanes[3:] if isinstance(lanes, list) else []:
        if row.get("release_lane") != "post_beta_admission" or row.get("state") != "placeholder":
            problems.append("Qt6, WinUI, and SwiftUI must remain post-beta placeholders")

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
    gates = readiness.get("gate", [])
    if _ids(gates) != GATE_IDS:
        problems.append("beta gates must exactly cover the canonical ordered gate set")
    for row in gates if isinstance(gates, list) else []:
        if not isinstance(row, dict) or not row.get("state") or not row.get("owner"):
            problems.append("every beta gate must name a state and owner")
        elif row.get("state") not in GATE_STATES.get(str(row.get("id", "")), set()):
            problems.append(f"{row.get('id', '<unknown>')} has an invalid gate state")
    if any(row.get("state") == "complete" for row in gates if isinstance(row, dict)):
        problems.append("no beta gate may claim complete while beta_ready is false")
    return problems


def detect() -> list[str]:
    return validate(
        _load(READINESS), _load(VERSION), _load(RELEASE_INDEX), _load(ARTIFACT_MATRIX)
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
