#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the sole current FacMan release-obligation selection."""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path
from typing import Any

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "release" / "index"
SCHEMAS = ROOT / "contracts" / "schema" / "release"
ACTIVE_VIEW_PATH = "release/index/active_release_view.v1.toml"

ACTIVE_PROFILES = (
    "windows_product_x64",
    "macos_product_x64",
    "linux_product_x64",
)
REFERENCE_PROFILES = ("windows_product_x64",)
PREVIEW_PROFILES = ("macos_product_x64", "linux_product_x64")
HISTORICAL_PROFILES = (
    "linux_portable_cli_x64",
    "macos_portable_cli_x64",
    "windows_portable_cli_x64",
    "windows_portable_tui_x64",
    "linux_portable_tui_x64",
    "macos_portable_tui_x64",
    "windows_legacy_winforms_x64",
    "macos_legacy_appkit_x64",
    "linux_x11_gtk_x64",
    "portable_cli_x64",
    "portable_tui_x64",
)
ACTIVE_PROFILE_PATHS = tuple(
    f"release/profiles/{profile_id}/profile.toml" for profile_id in ACTIVE_PROFILES
)
HISTORICAL_PROFILE_PATHS = tuple(
    f"release/profiles/{profile_id}/profile.toml"
    for profile_id in HISTORICAL_PROFILES
)
ASSET_PATTERNS = (
    "FacMan-<version>-windows-x64-portable.zip",
    "FacMan-<version>-windows-x64-setup.exe",
    "FacMan-<version>-macos-x64-portable.zip",
    "FacMan-<version>-macos-x64-setup.pkg",
    "FacMan-<version>-linux-x64-portable.tar.zst",
    "FacMan-<version>-linux-x64-setup.run",
    "FacMan-<version>-SHA256SUMS.txt",
    "FacMan-<version>-evidence.zip",
)
ACTIVE_PRODUCERS = ("platform_product_bundle", "platform_self_setup")


def _toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected an object")
    return value


def load_inputs() -> dict[str, dict[str, Any]]:
    return {
        "active": _toml(INDEX / "active_release_view.v1.toml"),
        "release_index": _toml(INDEX / "release_index.v1.toml"),
        "package_manifest": _toml(INDEX / "package_manifest.v1.toml"),
        "support": _toml(INDEX / "support_matrix.v1.toml"),
        "producers": _toml(INDEX / "package_producers.v1.toml"),
        "lanes": _toml(INDEX / "distribution_lanes.v1.toml"),
        "catalog": _toml(ROOT / "release/profiles/profile_catalog.v1.toml"),
        "update": _toml(INDEX / "update_report.v1.toml"),
        "artifacts": _toml(INDEX / "artifact_matrix.v1.toml"),
        "current_candidate": _toml(
            INDEX / "alpha5_final_candidate_closeout.v1.toml"
        ),
        "historical_candidate": _toml(
            INDEX / "alpha5_promotion_candidate_closeout.v1.toml"
        ),
        "historical_distribution": _toml(INDEX / "final_distribution.v1.toml"),
        "active_schema": _json(
            SCHEMAS / "active_release_view.v1.schema.json"
        ),
        "release_index_schema": _json(
            SCHEMAS / "release_index.v1.schema.json"
        ),
        "package_manifest_schema": _json(
            SCHEMAS / "package_manifest.v1.schema.json"
        ),
        "support_schema": _json(SCHEMAS / "support_matrix.v1.schema.json"),
        "lanes_schema": _json(SCHEMAS / "distribution_lane.v1.schema.json"),
        "update_schema": _json(SCHEMAS / "update_report.v1.schema.json"),
    }


def _exact(
    problems: list[str],
    label: str,
    observed: Any,
    expected: tuple[Any, ...],
) -> None:
    if not isinstance(observed, list):
        problems.append(f"{label} must be an ordered list")
        return
    if tuple(observed) != expected:
        problems.append(f"{label} must equal {list(expected)!r}")
    if len(observed) != len(set(observed)):
        problems.append(f"{label} contains duplicates")


def _rows_by_id(
    problems: list[str],
    label: str,
    rows: Any,
) -> dict[str, dict[str, Any]]:
    if not isinstance(rows, list):
        problems.append(f"{label} must be a list")
        return {}
    selected: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), str):
            problems.append(f"{label} contains a row without an id")
            continue
        row_id = str(row["id"])
        if row_id in selected:
            problems.append(f"{label} repeats {row_id}")
        selected[row_id] = row
    return selected


def _schema_problems(
    label: str,
    instance: dict[str, Any],
    schema: dict[str, Any],
) -> list[str]:
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"{label}: {error.json_path}: {error.message}"
        for error in sorted(validator.iter_errors(instance), key=lambda item: list(item.path))
    ]


def validate(values: dict[str, dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    active = values["active"]
    for name, instance, schema in (
        ("active release view", active, values["active_schema"]),
        ("release index", values["release_index"], values["release_index_schema"]),
        (
            "package manifest",
            values["package_manifest"],
            values["package_manifest_schema"],
        ),
        ("support matrix", values["support"], values["support_schema"]),
        ("distribution lanes", values["lanes"], values["lanes_schema"]),
        ("update report", values["update"], values["update_schema"]),
    ):
        problems.extend(_schema_problems(name, instance, schema))

    bindings = {
        "candidate_receipt": "release/index/alpha5_final_candidate_closeout.v1.toml",
        "artifact_matrix": "release/index/artifact_matrix.v1.toml",
        "package_manifest": "release/index/package_manifest.v1.toml",
        "support_matrix": "release/index/support_matrix.v1.toml",
        "package_producers": "release/index/package_producers.v1.toml",
        "distribution_lanes": "release/index/distribution_lanes.v1.toml",
        "profile_catalog": "release/profiles/profile_catalog.v1.toml",
    }
    for key, expected in bindings.items():
        if active.get(key) != expected:
            problems.append(f"active release view {key} must bind {expected}")
        path = ROOT / expected
        if not path.is_file() or ROOT not in path.resolve().parents:
            problems.append(f"active release view {key} is missing or escapes the repository")
    if values["release_index"].get("active_release_view") != ACTIVE_VIEW_PATH:
        problems.append("release index does not bind the active release view")
    if values["release_index"].get("profiles_role") != (
        "construction_catalog_not_active_release_selection"
    ):
        problems.append("release index profile inventory can present as current")

    _exact(problems, "active profile ids", active.get("active_profile_ids"), ACTIVE_PROFILES)
    _exact(
        problems,
        "reference profile ids",
        active.get("reference_profile_ids"),
        REFERENCE_PROFILES,
    )
    _exact(
        problems,
        "selected preview profile ids",
        active.get("selected_preview_profile_ids"),
        PREVIEW_PROFILES,
    )
    _exact(
        problems,
        "historical profile ids",
        active.get("historical_profile_ids"),
        HISTORICAL_PROFILES,
    )
    _exact(
        problems,
        "active asset patterns",
        active.get("active_asset_patterns"),
        ASSET_PATTERNS,
    )
    if set(ACTIVE_PROFILES) & set(HISTORICAL_PROFILES):
        problems.append("active and historical profile selections overlap")
    if set(REFERENCE_PROFILES) | set(PREVIEW_PROFILES) != set(ACTIVE_PROFILES):
        problems.append("reference and preview profiles must partition active profiles")

    package = values["package_manifest"]
    if package.get("profile_collection_role") != (
        "construction_catalog_not_active_release_selection"
    ):
        problems.append("package manifest profile inventory can present as current")
    if package.get("active_release_view") != ACTIVE_VIEW_PATH:
        problems.append("package manifest does not bind the active release view")
    _exact(
        problems,
        "package manifest active profiles",
        package.get("active_release_profiles"),
        ACTIVE_PROFILE_PATHS,
    )
    _exact(
        problems,
        "package manifest historical profiles",
        package.get("historical_profiles"),
        HISTORICAL_PROFILE_PATHS,
    )
    catalog_paths = tuple(package.get("release_profiles", []))
    expected_catalog_paths = set(ACTIVE_PROFILE_PATHS) | set(HISTORICAL_PROFILE_PATHS)
    if set(catalog_paths) != expected_catalog_paths:
        problems.append("package manifest release_profiles must remain the complete profile catalog")
    if set(values["release_index"].get("profiles", [])) != expected_catalog_paths:
        problems.append("release index profiles must remain the complete profile catalog")

    expected_roles = {
        "windows_product_x64": "reference_product",
        "macos_product_x64": "selected_preview_product",
        "linux_product_x64": "selected_preview_product",
    }
    for label, document, rows_key in (
        ("support matrix", values["support"], "platform"),
        ("distribution lanes", values["lanes"], "lane"),
    ):
        if document.get("active_release_view") != ACTIVE_VIEW_PATH:
            problems.append(f"{label} does not bind the active release view")
        rows = _rows_by_id(problems, label, document.get(rows_key))
        current = {
            row_id
            for row_id, row in rows.items()
            if row.get("current_release_obligation") is True
        }
        if current != set(ACTIVE_PROFILES):
            problems.append(f"{label} current obligations must be exactly the active profiles")
        for profile_id in ACTIVE_PROFILES:
            if rows.get(profile_id, {}).get("release_role") != expected_roles[profile_id]:
                problems.append(f"{label} has the wrong active role for {profile_id}")
        for profile_id in HISTORICAL_PROFILES:
            row = rows.get(profile_id, {})
            if row.get("current_release_obligation") is not False:
                problems.append(f"{label} historical profile is current: {profile_id}")
            if row.get("release_role") != "historical_compatibility_evidence":
                problems.append(f"{label} historical role is missing: {profile_id}")

    producers = _rows_by_id(
        problems, "package producers", values["producers"].get("producer")
    )
    if values["producers"].get("active_release_view") != ACTIVE_VIEW_PATH:
        problems.append("package producers do not bind the active release view")
    current_producers = {
        producer_id
        for producer_id, producer in producers.items()
        if producer.get("current_release_obligation") is True
    }
    if current_producers != set(ACTIVE_PRODUCERS):
        problems.append("only canonical product and setup producers may be current")
    for producer_id in ACTIVE_PRODUCERS:
        if producers.get(producer_id, {}).get("release_role") != "active_product_producer":
            problems.append(f"active producer role is missing: {producer_id}")
    product = producers.get("platform_product_bundle", {})
    setup = producers.get("platform_self_setup", {})
    if set(product.get("profiles", [])) != set(ACTIVE_PROFILES):
        problems.append("canonical product producer must select exactly the active profiles")
    if set(setup.get("consumes_profiles", [])) != set(ACTIVE_PROFILES):
        problems.append("canonical setup producer must consume exactly the active profiles")
    for producer_id, producer in producers.items():
        if producer_id in ACTIVE_PRODUCERS:
            continue
        if producer.get("current_release_obligation") is not False:
            problems.append(f"non-current producer presents as current: {producer_id}")
        expected_role = (
            "future_unadmitted_producer"
            if producer.get("state") == "not_yet_admitted"
            else "historical_compatibility_producer"
        )
        if producer.get("release_role") != expected_role:
            problems.append(f"non-current producer has the wrong role: {producer_id}")

    update = values["update"]
    if update.get("active_release_view") != ACTIVE_VIEW_PATH:
        problems.append("update report does not bind the active release view")
    if update.get("compatible_lanes_role") != (
        "compatibility_inventory_not_active_release_selection"
    ):
        problems.append("update compatibility lanes can present as current")
    _exact(
        problems,
        "update active release lanes",
        update.get("active_release_lanes"),
        ACTIVE_PROFILES,
    )
    _exact(
        problems,
        "update selected preview lanes",
        update.get("selected_preview_lanes"),
        PREVIEW_PROFILES,
    )

    catalog = values["catalog"]
    if catalog.get("active_release_selection") != ACTIVE_VIEW_PATH:
        problems.append("profile catalog does not defer selection to the active release view")
    if catalog.get("catalog_grants_current_release_obligation") is not False:
        problems.append("profile catalog can grant current release obligations")
    catalog_rows = _rows_by_id(problems, "profile catalog", catalog.get("profile"))
    current_catalog_ids = {
        profile_id
        for profile_id, profile in catalog_rows.items()
        if str(profile.get("status", "")).startswith("current_product_")
    }
    if current_catalog_ids != set(ACTIVE_PROFILES):
        problems.append("profile catalog current-product rows differ from active profiles")

    artifacts = values["artifacts"]
    patterns = tuple(
        row.get("pattern")
        for row in artifacts.get("artifact", [])
        if isinstance(row, dict)
    )
    if patterns != ASSET_PATTERNS:
        problems.append("artifact matrix patterns differ from the active eight-asset shape")
    if (
        artifacts.get("authored_asset_count") != active.get("active_asset_count")
        or active.get("active_asset_count") != 8
    ):
        problems.append("active authored asset count must be eight")
    if (
        artifacts.get("primary_product_asset_count")
        != active.get("primary_product_asset_count")
        or active.get("primary_product_asset_count") != 6
    ):
        problems.append("active primary product asset count must be six")
    artifact_profiles = {
        str(row.get("profile_id"))
        for row in artifacts.get("artifact", [])
        if isinstance(row, dict) and row.get("profile_id") != "release_metadata"
    }
    if artifact_profiles != set(ACTIVE_PROFILES):
        problems.append("artifact matrix product rows differ from active profiles")

    current_candidate = values["current_candidate"]
    historical_candidate = values["historical_candidate"]
    historical_distribution = values["historical_distribution"]
    if current_candidate.get("record_role") != "current_alpha5_candidate":
        problems.append("final Alpha.5 receipt is not the current candidate")
    if historical_candidate.get("record_role") != "historical_alpha5_candidate":
        problems.append("earlier Alpha.5 receipt lacks a historical role")
    if historical_candidate.get("current_candidate") is not False:
        problems.append("earlier Alpha.5 receipt presents as current")
    if historical_candidate.get("successor_current_candidate_receipt") != (
        active.get("candidate_receipt")
    ):
        problems.append("earlier Alpha.5 receipt does not bind its current successor")
    _exact(
        problems,
        "historical candidate receipts",
        active.get("historical_candidate_receipts"),
        ("release/index/alpha5_promotion_candidate_closeout.v1.toml",),
    )
    _exact(
        problems,
        "historical distribution records",
        active.get("historical_distribution_records"),
        ("release/index/final_distribution.v1.toml",),
    )
    if historical_distribution.get("record_role") != "historical_alpha3_draft":
        problems.append("Alpha.3 distribution lacks its historical role")
    if historical_distribution.get("current_candidate") is not False:
        problems.append("Alpha.3 distribution presents as current")
    if historical_distribution.get("successor_current_candidate_receipt") != (
        active.get("candidate_receipt")
    ):
        problems.append("Alpha.3 distribution does not bind its current successor")

    for key in (
        "release_authority",
        "human_acceptance",
        "signing",
        "tagging",
        "publication",
        "support_activation",
    ):
        if active.get(key) is not False:
            problems.append(f"active release view must not grant {key}")
    return problems


def main() -> int:
    try:
        problems = validate(load_inputs())
    except (OSError, ValueError, tomllib.TOMLDecodeError, json.JSONDecodeError) as exc:
        problems = [str(exc)]
    if problems:
        for problem in problems:
            print(f"active-release-view-check: {problem}", file=sys.stderr)
        return 1
    print(
        "active-release-view-check: ok "
        "(3 product profiles, 2 selected previews, 8 assets, legacy history quarantined)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
