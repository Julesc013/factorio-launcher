# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import hashlib
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DECISION = ROOT / "release/index/factorio_route_version_decision.v1.toml"
ACTIVE_ROUTE = ROOT / "release/index/successor_play_route.v2.toml"
RELEASE_INDEX = ROOT / "release/index/release_index.v1.toml"
DOSSIER = ROOT / "docs/release/checkpoints/facman-route-version-decision-dossier-01.md"

EXPECTED_ROUTE_ID = (
    "facman.engineering.play.windows-x64.factorio-2.1.14."
    "standalone.menu.task-isolated.v1"
)
EXPECTED_ACTIVE_ROUTE_ID = (
    "facman.play.windows-x64.factorio-2.0.77.standalone.menu."
    "instance-isolated.successor.v2"
)
EXPECTED_ARCHIVE_SHA256 = (
    "cd96202e93ef93e170c8f37dda0ebacb9031011ab81770a5eec075a067e3da30"
)
EXPECTED_EXECUTABLE_SHA256 = (
    "2f5e2238a25c28bfbedf624bd49844f819971484abf24595e6fd27375b914999"
)
EXPECTED_TOP_LEVEL = {
    "schema",
    "work_unit",
    "decision_status",
    "decision_digest",
    "prior_dossier",
    "current_route_contract",
    "current_route_sha256",
    "current_route_id",
    "current_route_version",
    "current_route_state",
    "selected_engineering_route_id",
    "selected_engineering_version",
    "selected_engineering_build",
    "selection_law",
    "archive",
    "executable",
    "direct_engineering_evidence",
    "facman_engineering_composition",
    "transition",
    "authority",
}
EXPECTED_AUTHORITY = {
    "product_execution",
    "release_route_activation",
    "setup_mutation",
    "provider_adoption",
    "protected_merge",
    "route_capability",
    "route_promotion",
    "tagging",
    "signing",
    "publication",
    "support_promotion",
}
EXPECTED_TRANSITION = {
    "supersedes_prior_recommendation": True,
    "current_2_0_77_route_unchanged": True,
    "silent_substitution_allowed": False,
    "new_route_definition_required": True,
    "new_version_specific_policy_required": True,
    "new_evidence_identity_family_required": True,
    "canonical_provider_requalification_required": True,
    "clean_host_qualification_required": True,
    "human_verdict_required": True,
    "release_route_acceptance_required": True,
    "package_or_source_change_invalidates": True,
    "archive_or_executable_digest_change_invalidates": True,
    "route_policy_or_provider_change_invalidates": True,
    "evidence_transfer_from_2_0_77_allowed": False,
}


def load_record() -> dict[str, Any]:
    with DECISION.open("rb") as handle:
        return tomllib.load(handle)


def decision_digest(record: dict[str, Any]) -> str:
    canonical = copy.deepcopy(record)
    canonical.pop("decision_digest", None)
    encoded = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate(record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if set(record) != EXPECTED_TOP_LEVEL:
        problems.append("route-version decision top-level contract is incomplete or open")
    expected_scalars = {
        "schema": "facman.factorio_route_version_decision.v1",
        "work_unit": "FACMAN-FIRST-ROUTE-VERSION-DECISION-01",
        "decision_status": "engineering_route_selected_review_ready_no_activation",
        "prior_dossier": "docs/release/checkpoints/facman-route-version-decision-dossier-01.md",
        "current_route_contract": "release/index/successor_play_route.v2.toml",
        "current_route_id": EXPECTED_ACTIVE_ROUTE_ID,
        "current_route_version": "2.0.77",
        "current_route_state": "unchanged_integrated_non_authorizing_definition",
        "selected_engineering_route_id": EXPECTED_ROUTE_ID,
        "selected_engineering_version": "2.1.14",
        "selected_engineering_build": 87180,
    }
    for field, expected in expected_scalars.items():
        if record.get(field) != expected:
            problems.append(f"route-version decision {field} must be {expected!r}")
    if record.get("decision_digest") != decision_digest(record):
        problems.append("route-version decision digest does not match canonical content")
    try:
        active_route_sha256 = file_sha256(ACTIVE_ROUTE)
    except OSError as exc:
        problems.append(f"active route cannot be hashed: {exc}")
    else:
        if record.get("current_route_sha256") != active_route_sha256:
            problems.append("2.0.77 active route bytes changed or are not bound exactly")

    archive = record.get("archive", {})
    expected_archive = {
        "product": "Factorio Space Age",
        "distribution": "standalone_non_steam_private_official_archive",
        "platform": "windows",
        "architecture": "x86_64",
        "version": "2.1.14",
        "build": 87180,
        "size": 4597290876,
        "sha256": EXPECTED_ARCHIVE_SHA256,
        "entry_count": 20832,
        "uncompressed_bytes": 5350965797,
        "custody": "local_read_hash_copy_extract_test_only_never_upload",
    }
    if archive != expected_archive:
        problems.append("2.1.14 private archive identity or custody law drifted")
    executable = record.get("executable", {})
    expected_executable = {
        "relative_path": "bin/x64/factorio.exe",
        "version": "2.1.14",
        "build": 87180,
        "platform": "win64",
        "edition": "full_space_age",
        "sha256": EXPECTED_EXECUTABLE_SHA256,
    }
    if executable != expected_executable:
        problems.append("2.1.14 executable identity drifted")

    evidence = record.get("direct_engineering_evidence", {})
    expected_evidence_keys = {
        "status",
        "first_initialised_seconds",
        "relaunch_initialised_seconds",
        "clean_exit_observed",
        "main_menu_screenshot_sha256",
        "relaunch_screenshot_sha256",
        "relaunch_log_sha256",
        "source_tree_inventory_sha256",
        "default_user_data_inventory_sha256",
        "source_unchanged",
        "private_archive_unchanged",
        "live_installation_unchanged",
        "default_user_data_unchanged",
    }
    if set(evidence) != expected_evidence_keys:
        problems.append("direct engineering evidence fields are incomplete or open")
    if evidence.get("status") != "two_isolated_launches_to_main_menu_completed":
        problems.append("direct 2.1.14 launch evidence is not complete")
    for field in (
        "clean_exit_observed",
        "source_unchanged",
        "private_archive_unchanged",
        "live_installation_unchanged",
        "default_user_data_unchanged",
    ):
        if evidence.get(field) is not True:
            problems.append(f"direct engineering evidence {field} must be true")

    composition = record.get("facman_engineering_composition", {})
    expected_composition_keys = {
        "candidate_revision",
        "candidate_tree",
        "universal_launcher_revision",
        "universal_setup_revision",
        "installation_id",
        "instance_id",
        "instance_version",
        "instance_spec_digest",
        "instance_binding_digest",
        "readiness_digest",
        "effective_config_sha256",
        "installation_import",
        "instance_create",
        "readiness",
        "launch_plan",
        "launch_preflight",
        "shipping_run_execute",
        "engineering_harness",
    }
    if set(composition) != expected_composition_keys:
        problems.append("FacMan engineering composition fields are incomplete or open")
    if composition.get("instance_version") != "2.1.14":
        problems.append("FacMan engineering instance is not bound to 2.1.14")
    if composition.get("shipping_run_execute") != "refused_before_effects_isolation_not_proven":
        problems.append("shipping run.execute did not preserve its fail-closed boundary")
    if composition.get("engineering_harness") != "separate_default_off_exact_route_bound":
        problems.append("engineering execution is not isolated from the shipping composition")

    if record.get("transition") != EXPECTED_TRANSITION:
        problems.append("2.1.14 transition and invalidation law drifted")
    authority = record.get("authority", {})
    if set(authority) != EXPECTED_AUTHORITY or any(value is not False for value in authority.values()):
        problems.append("route-version decision opens product, release, or publication authority")

    try:
        release_index = tomllib.loads(RELEASE_INDEX.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        problems.append(f"release index cannot be read: {exc}")
    else:
        if release_index.get("factorio_route_version_decision") != (
            "release/index/factorio_route_version_decision.v1.toml"
        ):
            problems.append("release index does not bind the route-version decision")
    try:
        dossier = DOSSIER.read_text(encoding="utf-8")
    except OSError as exc:
        problems.append(f"route-version dossier cannot be read: {exc}")
    else:
        for anchor in (
            "engineering_route_selected_review_ready_no_activation",
            EXPECTED_ROUTE_ID,
            EXPECTED_ARCHIVE_SHA256,
            EXPECTED_EXECUTABLE_SHA256,
            "The active 2.0.77 route index remains unchanged",
        ):
            if anchor not in dossier:
                problems.append(f"route-version dossier is missing {anchor!r}")
    return problems


def check() -> list[str]:
    try:
        return validate(load_record())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [f"route-version decision cannot be loaded: {exc}"]


def main() -> int:
    problems = check()
    if problems:
        for problem in problems:
            print(f"factorio-route-version-decision-check: {problem}", file=sys.stderr)
        return 1
    print(
        "factorio-route-version-decision-check: ok "
        f"({EXPECTED_ROUTE_ID}; no activation)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
