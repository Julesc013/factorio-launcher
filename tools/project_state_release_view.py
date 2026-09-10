# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Project-state projection helpers for the selected release view."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


LoadToml = Callable[[Path], dict[str, Any]]
ACTIVE_VIEW = Path("release/index/active_release_view.v1.toml")
SUPPORT_MATRIX = Path("release/index/support_matrix.v1.toml")
ROADMAP_SEQUENCE = (
    "FACMAN-0.1-ALPHA5-FINAL-CANDIDATE-CLOSEOUT-01",
    "FACMAN-ACTIVE-RELEASE-VIEW-CONSOLIDATION-01",
    "FACMAN-BETA-REPOSITORY-IDENTITY-DECISION-01",
    "FACMAN-BETA-RULESET-AND-TAG-PROTECTION-01",
    "FACMAN-0.1-ALPHA6-WORKSPACE-MIGRATION-RECOVERY-01",
    "FACMAN-0.1-ALPHA6-MANAGED-INSTALL-LIFECYCLE-01",
    "FACMAN-0.1-ALPHA7-CONTENT-WORLD-ROUTES-01",
    "FACMAN-0.1-ALPHA7-PLAY-FRONTEND-CONVERGENCE-01",
    "FACMAN-0.1-FEATURE-FREEZE-01",
    "FACMAN-0.1-BETA1-EXACT-RELEASE-01",
)
ROADMAP_ACTIONS = (
    "Close final Alpha.5 candidate truth",
    "Consolidate active release and support truth",
    "Freeze one pre-release/0.1 repository identity",
    "Prepare report-only branch rules and immutable tag protection",
    "Close public workspace migration and recovery",
    "Close the bounded managed-install and exact portable/setup lifecycle",
    "Close content, modpack, world, save, and clean-root reconstruction routes",
    "Complete cross-platform terminal and fresh Play/session journeys, then WinForms/GTK3 references; retain AppKit preview until 0.4 graduation",
    "Enter feature freeze only after J01-J12 are machine-complete",
    "Build and accept the exact six-product beta.1 candidate",
)


def active_release_state(root: Path, load_toml: LoadToml) -> dict[str, Any]:
    active = load_toml(root / ACTIVE_VIEW)
    return {
        "authority": ACTIVE_VIEW.as_posix(),
        "view_role": active["view_role"],
        "product_version": active["product_version"],
        "candidate_receipt": active["candidate_receipt"],
        "active_profiles": list(active["active_profile_ids"]),
        "reference_profiles": list(active["reference_profile_ids"]),
        "selected_preview_profiles": list(active["selected_preview_profile_ids"]),
        "active_asset_count": int(active["active_asset_count"]),
        "primary_product_asset_count": int(active["primary_product_asset_count"]),
        "release_authority": bool(active["release_authority"]),
        "publication": bool(active["publication"]),
        "support_activation": bool(active["support_activation"]),
    }


def support_platforms(root: Path, load_toml: LoadToml) -> list[dict[str, str]]:
    selected = active_release_state(root, load_toml)["active_profiles"]
    rows = {
        str(row.get("id", "")): row
        for row in load_toml(root / SUPPORT_MATRIX)["platform"]
        if isinstance(row, dict)
    }
    keys = (
        "id",
        "frontend_family",
        "compile_status",
        "runtime_status",
        "package_status",
        "publication_status",
        "support_status",
        "evidence_revision",
    )
    return [
        {key: str(rows[profile_id].get(key, "")) for key in keys}
        for profile_id in selected
    ]


def current_state_lines(view: dict[str, Any]) -> list[str]:
    string = lambda value: json.dumps(str(value), ensure_ascii=False)
    array = lambda values: "[" + ", ".join(string(value) for value in values) + "]"
    return [
        "[active_release_view]",
        f"authority = {string(view['authority'])}",
        f"view_role = {string(view['view_role'])}",
        f"product_version = {string(view['product_version'])}",
        f"candidate_receipt = {string(view['candidate_receipt'])}",
        f"active_profiles = {array(view['active_profiles'])}",
        f"reference_profiles = {array(view['reference_profiles'])}",
        f"selected_preview_profiles = {array(view['selected_preview_profiles'])}",
        f"active_asset_count = {int(view['active_asset_count'])}",
        f"primary_product_asset_count = {int(view['primary_product_asset_count'])}",
        f"release_authority = {str(view['release_authority']).lower()}",
        f"publication = {str(view['publication']).lower()}",
        f"support_activation = {str(view['support_activation']).lower()}",
        "",
    ]


def roadmap_lines(workunits: list[dict[str, Any]]) -> list[str]:
    """Render unfinished canonical sequence work, including during parallel work.

    An active scope/verification task need not belong to the product sequence;
    it must not reset the roadmap to already completed historical work.
    """
    states = {item["id"]: item["status"] for item in workunits}
    terminal = {"complete", "cancelled", "superseded"}
    selected = (
        (action, workunit)
        for action, workunit in zip(ROADMAP_ACTIONS, ROADMAP_SEQUENCE)
        if workunit in states and states[workunit] not in terminal
    )
    return [
        f"{number}. {action} in `{work_unit}`."
        for number, (action, work_unit) in enumerate(selected, start=1)
    ]
