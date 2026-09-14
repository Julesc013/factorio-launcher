# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate current provider adoption without relabelling historical evidence."""

from __future__ import annotations

import hashlib
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "release/index/provider_adoption_successor.v1.json"
SCHEMA = ROOT / "contracts/schema/release/provider_adoption_successor.v1.schema.json"
RELEASE_INDEX = ROOT / "release/index/release_index.v1.toml"
PROJECT_STATUS = ROOT / "release/index/project_status.v2.toml"

CURRENT_INPUTS = {
    "workspace_lock": "83a000bbc6ed1f8585f97d4462b41860dd50c19b7b85c35a38daa8b3e0ce7395",
    "dependency_lock": "9c28173442fdaf497bf6da2dc24b746f9abd6254374c8b0351e78884b042e420",
    "providers_lock": "732c675ae982e940c5662bb9d2487f32e6c1fe3d7b9bdd854a2972963cf4f4a9",
    "build_manifest": "92044fdc925243e813852050fa87590d2467adf2f5c954249620c87c404443be",
    "sbom": "cff10ca2e7ead40c889100078c89c79fdedb71c9d9f7ab9446ce1029a3cd8c79",
}
PRIOR_INPUTS = {
    "workspace_lock": "b1590cc87bd50e5913196f1e3aa7a044028b30e9f1354b46a355b3db3f42c9bf",
    "dependency_lock": "d2e131e300f9b20bea0aa2a4169f86a95e48740c4cda35b424f5f8ae942060a3",
    "providers_lock": "d33943841431afdeffb7961c7453d8999619ef371793a6310ad2c2952b118f00",
    "build_manifest": "92044fdc925243e813852050fa87590d2467adf2f5c954249620c87c404443be",
    "sbom": "c1be8ed61893107e335de4cbbef32d7449ca72d26670b4735ac1a6cba88880c2",
}
INPUT_PATHS = {
    "workspace_lock": "release/index/workspace_lock.v1.toml",
    "dependency_lock": "release/index/dependency_lock.v1.toml",
    "providers_lock": "release/index/providers.lock.v2.toml",
    "build_manifest": "release/index/build_manifest.v1.toml",
    "sbom": "release/index/sbom.components.v1.json",
}
PROJECTION_SOURCE = {
    "workflow_run": 34793208025,
    "aggregate_job": 103821556004,
    "head_revision": "e6b1a3439bee3f6cdceaffa0f303cf26cada7cae",
    "evidence_revision": "8bbe5051339d828ad7d39aae880be0d293ef2a89",
}
EXPECTED_PROVIDERS = [
    {
        "id": "universal_launcher",
        "prior_revision": "5479939ca5cbc9ee0f901608a92012778b4752ae",
        "revision": "5479939ca5cbc9ee0f901608a92012778b4752ae",
        "tree": "7728e4d415539a0f24e6f17aa7d22be00cc99d80",
        "package_version": "1.9.1",
        "abi_version": "1.9",
        "contract_digest": "edb62fda28fac02bf7e07a6295c867b3813f4881886c6783f379b52b5c8761f9",
        "package_set_digest": "51e3f7ba5d9f72b0d06ddb409fd190d3e613597d6a0a19a90adb12d5d4898dff",
        "license": "MIT",
    },
    {
        "id": "universal_setup",
        "prior_revision": "d2a2aae7e61c47035c92334b0522143b4fea3880",
        "revision": "279ad4876dc325f8e1fcdc918c91b098a11bc616",
        "tree": "499013a2099f872c998932505a51489343606382",
        "package_version": "1.0.0",
        "abi_version": "1.0",
        "contract_digest": "045a570f305a9e578dccbe22ec1d3c1945d6743a5e8d55d3c754dc3c2efd6f56",
        "package_set_digest": "a47cb9b409c365d4639cc4879941321f0bbfe6d4dbccb9910dcf0bccf550f09f",
        "license": "MIT AND Zlib",
    },
]
EXPECTED_INVALIDATIONS = {
    "alpha5_promotion_candidate_closeout.v1": (
        PRIOR_INPUTS["providers_lock"], PRIOR_INPUTS["workspace_lock"]
    ),
    "alpha5_final_candidate_closeout.v1": (
        PRIOR_INPUTS["providers_lock"], PRIOR_INPUTS["workspace_lock"]
    ),
    "facman_accessibility_human_test_packet.alpha1": (
        PRIOR_INPUTS["providers_lock"], None
    ),
    "successor_play_route.v2": (
        "59376482126a8226bb28c5b5d73e980d21d3081b76bdf10bd5c10297f2462249",
        "510511d597ef4ff1ce58f198b7d45796d7723411d09ca15f0e87d539445408e3",
    ),
    "factorio_2_1_14_release_route.v3": (PRIOR_INPUTS["providers_lock"], None),
    "factorio_2_1_14_release_route.v4": (PRIOR_INPUTS["providers_lock"], None),
    "factorio_2_1_14_release_route.v5": (PRIOR_INPUTS["providers_lock"], None),
    "factorio_2_1_14_route_packet.v1": (PRIOR_INPUTS["providers_lock"], None),
}


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _invalidations(record: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    rows: dict[str, dict[str, Any]] = {}
    problems: list[str] = []
    for item in record.get("invalidated_evidence", []):
        if not isinstance(item, dict):
            problems.append("invalidation list contains a non-object")
            continue
        identity = str(item.get("id", ""))
        if not identity or identity in rows:
            problems.append(f"invalidation identity is missing or duplicated: {identity!r}")
            continue
        rows[identity] = item
    return rows, problems


def historical_binding_problems(
    identity: str,
    provider_lock_sha256: str,
    workspace_lock_sha256: str | None = None,
) -> list[str]:
    """Require one exact closed-authority invalidation for historical evidence."""

    try:
        record = _load_json(RECORD)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return [f"provider adoption successor cannot be read: {exc}"]
    rows, problems = _invalidations(record)
    item = rows.get(identity, {})
    expected = {
        "id": identity,
        "provider_lock_sha256": provider_lock_sha256,
        "fresh_evidence_required": True,
        "authority_reused": False,
    }
    if workspace_lock_sha256 is not None:
        expected["workspace_lock_sha256"] = workspace_lock_sha256
    if item != expected:
        problems.append(f"historical evidence lacks exact provider-adoption invalidation: {identity}")
    if any(record.get("authority", {}).values()):
        problems.append("provider adoption successor unexpectedly reuses authority")
    return problems


def validate(root: Path = ROOT, record: dict[str, Any] | None = None) -> list[str]:
    problems: list[str] = []
    try:
        value = record if record is not None else _load_json(root / RECORD.relative_to(ROOT))
        schema = _load_json(root / SCHEMA.relative_to(ROOT))
        jsonschema.Draft202012Validator.check_schema(schema)
        for error in jsonschema.Draft202012Validator(schema).iter_errors(value):
            location = ".".join(str(part) for part in error.absolute_path) or "$"
            problems.append(f"schema rejection at {location}: {error.message}")
    except (OSError, ValueError, json.JSONDecodeError, jsonschema.SchemaError) as exc:
        return [f"provider adoption successor cannot be validated: {exc}"]

    if value.get("facman_base_revision") != "77c37e4cd9278c42307cf6b752e1ff2225bc914a":
        problems.append("provider adoption successor has the wrong FacMan base")
    if value.get("projection_source") != PROJECTION_SOURCE:
        problems.append("provider adoption successor has the wrong hosted projection source")
    if value.get("prior_inputs") != PRIOR_INPUTS:
        problems.append("provider adoption successor prior input closure differs")
    if value.get("current_inputs") != CURRENT_INPUTS:
        problems.append("provider adoption successor current input closure differs")
    if value.get("providers") != EXPECTED_PROVIDERS:
        problems.append("provider adoption successor provider identities differ")

    rows, row_problems = _invalidations(value)
    problems.extend(row_problems)
    if set(rows) != set(EXPECTED_INVALIDATIONS):
        problems.append("provider adoption successor invalidation set differs")
    for identity, (provider_sha256, workspace_sha256) in EXPECTED_INVALIDATIONS.items():
        expected = {
            "id": identity,
            "provider_lock_sha256": provider_sha256,
            "fresh_evidence_required": True,
            "authority_reused": False,
        }
        if workspace_sha256 is not None:
            expected["workspace_lock_sha256"] = workspace_sha256
        if rows.get(identity) != expected:
            problems.append(f"provider adoption successor invalidation differs: {identity}")

    for name, relative in INPUT_PATHS.items():
        path = root / relative
        try:
            actual = _sha256(path)
        except OSError as exc:
            problems.append(f"current provider input cannot be hashed: {relative}: {exc}")
        else:
            if actual != CURRENT_INPUTS[name]:
                problems.append(f"current provider input differs: {relative}")

    try:
        release_index = _load_toml(root / RELEASE_INDEX.relative_to(ROOT))
        project = _load_toml(root / PROJECT_STATUS.relative_to(ROOT))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        problems.append(f"provider adoption repository binding cannot be read: {exc}")
    else:
        if release_index.get("provider_adoption_successor") != (
            "release/index/provider_adoption_successor.v1.json"
        ):
            problems.append("release index does not bind the provider adoption successor")
        convergence = project.get("provider_convergence", {})
        if convergence.get("universal_launcher_consumed_pin") != EXPECTED_PROVIDERS[0]["revision"]:
            problems.append("project truth does not consume the adopted Universal Launcher")
        if convergence.get("universal_setup_consumed_pin") != EXPECTED_PROVIDERS[1]["revision"]:
            problems.append("project truth does not consume the adopted Universal Setup")
        if convergence.get("active_route_integration") != (
            "invalidated_by_protected_provider_package_adoption"
        ):
            problems.append("project truth does not invalidate the active route")
        for field in (
            "factorio_execution",
            "setup_mutation",
            "signing",
            "publication",
        ):
            if convergence.get(field) is not False:
                problems.append(f"project provider adoption opens {field}")
        if convergence.get("accepted_play_routes") != 0:
            problems.append("project provider adoption retains an accepted play route")

    if any(value.get("authority", {}).values()):
        problems.append("provider adoption successor opens authority")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"provider-adoption-successor-check: {problem}", file=sys.stderr)
        return 1
    print(
        "provider-adoption-successor-check: ok "
        "(five projections; eight evidence families invalidated; all authority false)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
