# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


LIFECYCLE_CLASSES = {"active", "preview", "lab", "legacy", "retired"}
INSTALL_MODES = {"portable", "user", "system"}
INSTALL_MODE_CLAIM_STATES = {
    "qualified",
    "implemented_unqualified",
    "planned",
    "not_applicable",
}


def load(root: Path, profile_id: str) -> tuple[Path, dict[str, Any]]:
    path = root / "release" / "profiles" / profile_id / "profile.toml"
    if not path.is_file():
        raise ValueError(f"unknown release profile: {profile_id}")
    with path.open("rb") as handle:
        profile = tomllib.load(handle)
    if profile.get("id") != profile_id:
        raise ValueError(f"{path}: profile id mismatch")
    return path, profile


def proof(profile: dict[str, Any]) -> dict[str, Any]:
    value = profile.get("proof", {})
    if not isinstance(value, dict):
        raise ValueError(f"{profile.get('id', '<profile>')}: proof must be a table")
    return value


def _toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _table(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _assignments(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def lifecycle_problems(root: Path) -> list[str]:
    """Validate catalog/lifecycle authority and current install-mode claims.

    The catalog intentionally includes planned records that have no executable
    ``profile.toml``.  The lifecycle map makes that distinction explicit while
    preserving stable profile paths used by existing release contracts.
    """

    root = root.resolve()
    profile_root = root / "release" / "profiles"
    catalog_path = profile_root / "profile_catalog.v1.toml"
    lifecycle_path = profile_root / "profile_lifecycle.v1.toml"
    catalog_data = _toml(catalog_path)
    lifecycle_data = _toml(lifecycle_path)
    problems: list[str] = []

    if catalog_data.get("schema") != "facman.release_profile_catalog.v1":
        problems.append("profile catalog has the wrong schema")
    if catalog_data.get("lifecycle_taxonomy") != (
        "release/profiles/profile_lifecycle.v1.toml"
    ):
        problems.append("profile catalog does not bind the lifecycle taxonomy")
    if catalog_data.get("catalog_role") != "reviewed_aggregate":
        problems.append("profile catalog role must be reviewed_aggregate")
    if catalog_data.get("catalog_is_generated") is not False:
        problems.append("profile catalog must not claim to be generated output")
    if lifecycle_data.get("schema") != "facman.release_profile_lifecycle.v1":
        problems.append("profile lifecycle map has the wrong schema")

    relationship = _table(lifecycle_data.get("catalog_relationship"))
    expected_relationship = {
        "catalog": "release/profiles/profile_catalog.v1.toml",
        "catalog_role": "reviewed_aggregate",
        "catalog_is_generated": False,
        "authored_profile_glob": "release/profiles/*/profile.toml",
        "authored_profile_role": "executable_package_contract",
        "catalog_only_role": "planning_record_without_package_authority",
    }
    for key, expected in expected_relationship.items():
        if relationship.get(key) != expected:
            problems.append(f"profile lifecycle catalog relationship has invalid {key}")
    generated_outputs = relationship.get("generated_outputs")
    if generated_outputs != []:
        problems.append("profile lifecycle must declare that it has no generated outputs")

    lifecycle_tables = _table(lifecycle_data.get("lifecycle"))
    if set(lifecycle_tables) != LIFECYCLE_CLASSES:
        problems.append(
            "profile lifecycle classes must be exactly active, preview, lab, legacy, retired"
        )
    for lifecycle_name in sorted(LIFECYCLE_CLASSES):
        definition = _table(lifecycle_tables.get(lifecycle_name))
        if not isinstance(definition.get("release_eligible"), bool):
            problems.append(f"profile lifecycle {lifecycle_name} lacks release_eligible")
        if not str(definition.get("meaning", "")):
            problems.append(f"profile lifecycle {lifecycle_name} lacks meaning")

    semantics = _table(lifecycle_data.get("install_mode_semantics"))
    if semantics.get("legacy_field_meaning") != "design_contract_surface_only":
        problems.append("legacy install_modes semantics are not bounded to design scope")
    declared_claim_states = {
        str(item) for item in semantics.get("claim_states", [])
    } if isinstance(semantics.get("claim_states"), list) else set()
    if declared_claim_states != INSTALL_MODE_CLAIM_STATES:
        problems.append("install-mode claim states differ from the validator contract")

    raw_catalog = catalog_data.get("profile", [])
    if not isinstance(raw_catalog, list):
        return problems + ["profile catalog entries must be an array"]
    catalog: dict[str, dict[str, Any]] = {}
    for item in raw_catalog:
        if not isinstance(item, dict):
            problems.append("profile catalog entry must be a table")
            continue
        profile_id = str(item.get("id", ""))
        if not profile_id:
            problems.append("profile catalog entry lacks id")
        elif profile_id in catalog:
            problems.append(f"profile catalog duplicates {profile_id}")
        else:
            catalog[profile_id] = item

    raw_assignments = lifecycle_data.get("assignment", [])
    assignments: dict[str, dict[str, Any]] = {}
    if not isinstance(raw_assignments, list):
        problems.append("profile lifecycle assignments must be an array")
    for assignment in _assignments(raw_assignments):
        profile_id = str(assignment.get("profile_id", ""))
        if not profile_id:
            problems.append("profile lifecycle assignment lacks profile_id")
        elif profile_id in assignments:
            problems.append(f"profile lifecycle duplicates assignment {profile_id}")
        else:
            assignments[profile_id] = assignment
    if set(assignments) != set(catalog):
        missing = sorted(set(catalog) - set(assignments))
        unknown = sorted(set(assignments) - set(catalog))
        if missing:
            problems.append(f"profile lifecycle lacks catalog assignments: {missing}")
        if unknown:
            problems.append(f"profile lifecycle has unknown assignments: {unknown}")

    authored_paths = {
        path.relative_to(root).as_posix(): path
        for path in profile_root.glob("*/profile.toml")
        if path.is_file()
    }
    assigned_authored_paths: set[str] = set()
    for profile_id, assignment in assignments.items():
        lifecycle = str(assignment.get("lifecycle", ""))
        origin = str(assignment.get("record_origin", ""))
        if lifecycle not in LIFECYCLE_CLASSES:
            problems.append(f"{profile_id}: unknown lifecycle {lifecycle!r}")
        if origin not in {"authored_profile", "catalog_only"}:
            problems.append(f"{profile_id}: unknown record_origin {origin!r}")
            continue
        definition = str(assignment.get("definition", ""))
        if origin == "authored_profile":
            if definition not in authored_paths:
                problems.append(f"{profile_id}: authored definition is missing: {definition}")
                continue
            assigned_authored_paths.add(definition)
            authored = _toml(authored_paths[definition])
            if authored.get("id") != profile_id:
                problems.append(f"{profile_id}: authored definition id differs")
        elif definition:
            problems.append(f"{profile_id}: catalog-only assignment must not name a definition")
        if lifecycle in {"active", "preview"} and origin != "authored_profile":
            problems.append(f"{profile_id}: current product lifecycle requires an authored profile")
        catalog_profile = catalog.get(profile_id, {})
        if lifecycle in {"active", "preview"} and catalog_profile.get("contract_backed") is not True:
            problems.append(f"{profile_id}: current product lifecycle must be contract-backed")
        if lifecycle in {"lab", "retired"} and catalog_profile.get("contract_backed") is not False:
            problems.append(f"{profile_id}: {lifecycle} profile cannot be contract-backed")
        if lifecycle == "retired" and origin != "catalog_only":
            problems.append(f"{profile_id}: retired profile cannot retain an authored package contract")
        if lifecycle in {"active", "preview"}:
            problems.extend(
                _install_mode_claim_problems(
                    profile_id,
                    assignment,
                    catalog_profile,
                    _toml(authored_paths[definition]) if definition in authored_paths else {},
                )
            )

    if assigned_authored_paths != set(authored_paths):
        missing = sorted(set(authored_paths) - assigned_authored_paths)
        duplicate_or_unknown = sorted(assigned_authored_paths - set(authored_paths))
        if missing:
            problems.append(f"authored profiles lack lifecycle assignments: {missing}")
        if duplicate_or_unknown:
            problems.append(f"lifecycle assignments name unknown definitions: {duplicate_or_unknown}")
    return problems


def _install_mode_claim_problems(
    profile_id: str,
    assignment: dict[str, Any],
    catalog_profile: dict[str, Any],
    authored_profile: dict[str, Any],
) -> list[str]:
    problems: list[str] = []
    claims = _table(assignment.get("install_mode_claims"))
    catalog_claims = _table(catalog_profile.get("install_mode_claims"))
    authored_claims = _table(authored_profile.get("install_mode_claims"))
    if set(claims) != INSTALL_MODES:
        problems.append(f"{profile_id}: lifecycle install-mode claims must cover all modes")
    for mode, state in claims.items():
        if mode not in INSTALL_MODES:
            problems.append(f"{profile_id}: unknown install mode claim {mode}")
        if state not in INSTALL_MODE_CLAIM_STATES:
            problems.append(f"{profile_id}: invalid {mode} install-mode state {state!r}")
        if state == "qualified":
            evidence = _table(assignment.get("qualification_evidence"))
            if not str(evidence.get(mode, "")):
                problems.append(f"{profile_id}: qualified {mode} mode lacks sealed evidence")
    if claims != catalog_claims:
        problems.append(f"{profile_id}: catalog install-mode claims differ from lifecycle truth")
    if claims != authored_claims:
        problems.append(f"{profile_id}: authored install-mode claims differ from lifecycle truth")
    if set(catalog_profile.get("install_modes", [])) != INSTALL_MODES:
        problems.append(f"{profile_id}: catalog design install-mode surface is incomplete")
    if set(authored_profile.get("install_modes", [])) != INSTALL_MODES:
        problems.append(f"{profile_id}: authored design install-mode surface is incomplete")
    return problems
