# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the non-authorizing release-train and autonomy design records."""

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "release" / "index"
SCHEMA_ROOT = ROOT / "contracts" / "schema" / "release"
LEDGER_README = ROOT / "release" / "ledger" / "README.md"
RELEASE_INDEX = INDEX / "release_index.v1.toml"

RECORD_PATHS = {
    "version_train": INDEX / "version_train.v1.toml",
    "autonomy_policy": INDEX / "autonomy_policy.v1.toml",
    "milestones": INDEX / "milestones.v1.toml",
    "capability_matrix": INDEX / "capability_frontend_matrix.v1.toml",
    "withdrawal_policy": INDEX / "withdrawal_policy.v1.toml",
}

RECORD_SCHEMAS = {
    "version_train": "facman.version_train.v1",
    "autonomy_policy": "facman.autonomy_policy.v1",
    "milestones": "facman.milestones.v1",
    "capability_matrix": "facman.capability_frontend_matrix.v1",
    "withdrawal_policy": "facman.withdrawal_policy.v1",
}

INDEX_BINDINGS = {
    "version_train": "release/index/version_train.v1.toml",
    "autonomy_policy": "release/index/autonomy_policy.v1.toml",
    "milestones": "release/index/milestones.v1.toml",
    "capability_frontend_matrix": "release/index/capability_frontend_matrix.v1.toml",
    "withdrawal_policy": "release/index/withdrawal_policy.v1.toml",
}

SCHEMA_PATHS = {
    "release_candidate": SCHEMA_ROOT / "release_candidate.v1.schema.json",
    "human_test_receipt": SCHEMA_ROOT / "human_test_receipt.v1.schema.json",
    "release_ledger_entry": SCHEMA_ROOT / "release_ledger_entry.v1.schema.json",
    "withdrawal_record": SCHEMA_ROOT / "withdrawal_record.v1.schema.json",
}

SCHEMA_IDS = {
    "release_candidate": "facman.release_candidate.v1",
    "human_test_receipt": "facman.human_test_receipt.v1",
    "release_ledger_entry": "facman.release_ledger_entry.v1",
    "withdrawal_record": "facman.withdrawal_record.v1",
}

AUTHORITY_KEYS = {
    "version_train": {
        "version_allocation",
        "tag_creation",
        "signing",
        "publication",
        "withdrawal",
        "stable_promotion",
    },
    "autonomy_policy": {
        "delegated_dev_merge",
        "isolated_lab_effects",
        "alpha_tag_creation",
        "alpha_publication",
        "beta_publication",
        "stable_publication",
        "production_credentials",
        "production_signing",
        "public_route_promotion",
        "human_verdict",
    },
    "milestones": {
        "milestone_activation",
        "scope_freeze",
        "beta_promotion",
        "stable_promotion",
        "signing",
        "publication",
    },
    "capability_matrix": {
        "capability_admission",
        "completion_claim",
        "support_promotion",
        "execution",
        "setup_mutation",
        "signing",
        "publication",
    },
    "withdrawal_policy": {
        "withdrawal",
        "tag_mutation",
        "asset_mutation",
        "channel_mutation",
        "production_notification",
        "publication",
    },
}

RELEASE_CLASSES = ["snapshot", "alpha", "beta", "rc", "stable_0x", "stable_1x"]
MILESTONE_IDS = [
    "FACMAN-C1",
    "0.1.0",
    "0.2.0",
    "0.3.0",
    "0.4.0",
    "0.5.0",
    "0.6.0",
    "0.7.0",
    "0.8.0",
    "0.9.0",
    "1.0.0",
]
PROJECTIONS_0_1 = ["cli_human", "cli_json", "tui", "winforms"]
PROJECTIONS_1_0 = [*PROJECTIONS_0_1, "appkit", "gtk", "qt"]
EVIDENCE_CLASSES = [
    "positive",
    "negative",
    "fault_and_recovery",
    "package",
    "documentation",
    "support",
]
SEED_CAPABILITY_IDS = {
    "workspace.onboarding",
    "installations.discovery_import",
    "installations.managed_portable_lifecycle",
    "instances.lifecycle",
    "profiles.configuration",
    "content.local_modsets",
    "saves.snapshots",
    "launch.menu_and_selected_save",
    "sessions.supervision",
    "recovery.operations",
    "diagnostics.support_bundle",
    "maintenance.manual_offline",
}
STATUS_VALUES = {"census_pending", "planned", "partial", "complete", "not_required"}
SEMVER_PATTERN = (
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)


def _toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def load_records() -> dict[str, dict[str, Any]]:
    return {name: _toml(path) for name, path in RECORD_PATHS.items()}


def load_schemas() -> dict[str, dict[str, Any]]:
    return {name: _json(path) for name, path in SCHEMA_PATHS.items()}


def load_release_index() -> dict[str, Any]:
    return _toml(RELEASE_INDEX)


def _duplicates(values: list[Any]) -> set[Any]:
    return {value for value in values if values.count(value) > 1}


def _validate_common(records: dict[str, dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    for name, expected_schema in RECORD_SCHEMAS.items():
        record = records.get(name, {})
        if record.get("schema") != expected_schema:
            problems.append(f"{name} has the wrong schema")
        if record.get("design_status") != "ratified":
            problems.append(f"{name} design_status must be ratified")
        if record.get("activation_status") != "pending_workunits":
            problems.append(f"{name} activation_status must be pending_workunits")
        workunits = record.get("activation_workunits")
        if not isinstance(workunits, list) or not workunits:
            problems.append(f"{name} must name activation WorkUnits")
        elif len(workunits) != len(set(workunits)):
            problems.append(f"{name} repeats an activation WorkUnit")
        authority = record.get("authority")
        if not isinstance(authority, dict) or not authority:
            problems.append(f"{name} must carry an explicit authority ceiling")
        else:
            if set(authority) != AUTHORITY_KEYS[name]:
                problems.append(f"{name} authority ceiling has the wrong closed fields")
            if any(value is not False for value in authority.values()):
                problems.append(f"{name} grants authority before activation")
    return problems


def _validate_version_train(record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if record.get("current_product_target") != "0.1.0":
        problems.append("version train current target must be 0.1.0")
    if record.get("development_base_version") != "0.1.0-alpha.0":
        problems.append("development identity must use the alpha.0 prerelease base")
    if record.get("tracked_contract_identity") != (
        "facman-0.1.0-alpha.0+dev.contract"
    ):
        problems.append("tracked development contract identity has drifted")
    if record.get("tracked_contract_identity_is_publishable") is not False:
        problems.append("tracked development contract identity cannot be publishable")
    if record.get("dynamic_snapshot_identity_projected_at_build_time") is not True:
        problems.append("dynamic snapshot identity must be projected at build time")
    if not record.get("published_tags_are_immutable"):
        problems.append("version train must keep published tags immutable")
    if record.get("tag_every_commit") is not False:
        problems.append("version train must not tag every commit")
    for field in (
        "version_allocation_authorized",
        "tag_creation_authorized",
        "signing_authorized",
        "publication_authorized",
    ):
        if record.get(field) is not False:
            problems.append(f"version train {field} must remain false")

    classes = record.get("release_class", [])
    ids = [item.get("id") for item in classes if isinstance(item, dict)]
    if ids != RELEASE_CLASSES:
        problems.append(f"version train release classes must be {RELEASE_CLASSES!r}")
        return problems
    source_refs = {
        "snapshot": "task_or_dev",
        "alpha": "dev",
        "beta": "release/<minor>",
        "rc": "release/<minor>",
        "stable_0x": "main",
        "stable_1x": "main",
    }
    source_requirements = {
        "snapshot": "exact_task_or_accepted_dev_commit",
        "alpha": "exact_three_key_accepted_dev_commit",
        "beta": "exact_human_tested_stabilization_commit",
        "rc": "exact_frozen_stabilization_commit",
        "stable_0x": "exact_owner_accepted_main_commit",
        "stable_1x": "exact_owner_accepted_main_commit",
    }
    human_receipts = {
        "snapshot": False,
        "alpha": False,
        "beta": True,
        "rc": True,
        "stable_0x": True,
        "stable_1x": True,
    }
    for release_class in classes:
        class_id = release_class["id"]
        if release_class.get("source_ref") != source_refs[class_id]:
            problems.append(f"{class_id} has the wrong source ref")
        if release_class.get("source_requirement") != source_requirements[class_id]:
            problems.append(f"{class_id} has the wrong source requirement")
        if release_class.get("human_receipt_required") is not human_receipts[class_id]:
            problems.append(f"{class_id} has the wrong human-receipt rule")
        if release_class.get("currently_authorized") is not False:
            problems.append(f"{class_id} is authorized before its WorkUnit")
    domains = record.get("version_domains", [])
    if len(domains) != len(set(domains)) or "product" not in domains or "c_abi" not in domains:
        problems.append("version domains must be unique and include product and C ABI")
    return problems


def _validate_autonomy(record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    roles = record.get("role", [])
    role_ids = [item.get("id") for item in roles if isinstance(item, dict)]
    if role_ids != ["control", "implementation", "assurance", "human"]:
        problems.append("autonomy roles must remain control, implementation, assurance, human")
    model_by_role = {item.get("id"): item.get("default_model") for item in roles}
    if model_by_role != {
        "control": "sol",
        "implementation": "terra",
        "assurance": "luna",
        "human": "none",
    }:
        problems.append("autonomy default model routing has drifted")

    three_key = record.get("three_key", {})
    key_roles = [
        three_key.get("implementation_role"),
        three_key.get("assurance_role"),
        three_key.get("policy_role"),
    ]
    if key_roles != ["implementation", "assurance", "control"] or len(set(key_roles)) != 3:
        problems.append("three-key roles must be distinct implementation, assurance, and control")
    if three_key.get("all_required_checks_must_pass") is not True:
        problems.append("three-key decisions cannot waive required checks")
    if record.get("implementation_author_may_self_approve") is not False:
        problems.append("implementation authors cannot self-approve")
    if record.get("red_gate_override_allowed") is not False:
        problems.append("autonomy cannot override a red gate")
    if record.get("high_risk", {}).get("independent_technical_review_required") is not True:
        problems.append("high-risk changes require an independent technical review")

    classes = record.get("authority_class", [])
    class_ids = [item.get("id") for item in classes if isinstance(item, dict)]
    if class_ids != ["D0", "D1", "D2", "D3", "D4"]:
        problems.append("autonomy classes must remain D0 through D4")
    for item in classes:
        if item.get("currently_authorized") is not False:
            problems.append(f"{item.get('id')} is authorized before activation")
        expected_delegable = item.get("id") != "D4"
        if item.get("delegable_after_activation") is not expected_delegable:
            problems.append(f"{item.get('id')} has the wrong delegation rule")
    lab = record.get("disposable_lab", {})
    if not lab or any(value is not True for value in lab.values()):
        problems.append("disposable-lab isolation requirements must all remain mandatory")
    return problems


def _validate_milestones(record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    milestones = record.get("milestone", [])
    ids = [item.get("id") for item in milestones if isinstance(item, dict)]
    if ids != MILESTONE_IDS:
        problems.append(f"milestone order must be {MILESTONE_IDS!r}")
        return problems
    if any(item.get("currently_authorized") is not False for item in milestones):
        problems.append("milestones cannot authorize their own activation")
    by_id = {item["id"]: item for item in milestones}
    c1 = by_id["FACMAN-C1"]
    if c1.get("kind") != "internal_engineering_capability" or c1.get("public_release") is not False:
        problems.append("C1 must remain an internal alpha foundation")
    public_beta = by_id["0.1.0"]
    if public_beta.get("required_platforms") != ["windows_10_11_x64"]:
        problems.append("0.1.0 must remain the bounded Windows public beta")
    if public_beta.get("required_frontends") != PROJECTIONS_0_1:
        problems.append("0.1.0 must require CLI human/JSON, TUI, and WinForms")
    if "matrix" not in str(public_beta.get("completion_predicate", "")):
        problems.append("0.1.0 completion must be bound to its frozen matrix")
    one_zero = by_id["1.0.0"]
    if one_zero.get("required_frontends") != PROJECTIONS_1_0:
        problems.append("1.0.0 must require all admitted CLI, TUI, and GUI projections")
    if one_zero.get("required_platforms") != ["windows", "macos", "linux"]:
        problems.append("1.0.0 must require Windows, macOS, and Linux")
    for item in milestones:
        if not item.get("human_gate"):
            problems.append(f"{item.get('id')} must name its human gate")
    return problems


def _validate_capability_matrix(record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if record.get("matrix_scope") != "seed_release_slices":
        problems.append("capability matrix must identify itself as seed release slices")
    if record.get("census_state") != "not_started":
        problems.append("command-level capability census must remain not started")
    if record.get("command_level_census_complete") is not False:
        problems.append("seed release slices cannot claim a complete command census")
    if record.get("one_row_per_command_census_required") is not True:
        problems.append("the activated matrix must require a one-row-per-command census")
    if record.get("required_projections_0_1") != PROJECTIONS_0_1:
        problems.append("capability matrix 0.1 projections have drifted")
    if record.get("required_projections_1_0") != PROJECTIONS_1_0:
        problems.append("capability matrix 1.0 projections have drifted")
    if record.get("required_evidence_classes") != EVIDENCE_CLASSES:
        problems.append("capability matrix evidence classes have drifted")
    if record.get("completion_claim_authorized") is not False:
        problems.append("capability matrix cannot authorize a completion claim")
    scope = record.get("scope", {})
    required_scope = {
        "completion_means_semantic_parity": True,
        "ordinary_workflow_may_require_advanced": False,
        "fixture_only_may_be_complete": False,
        "scaffold_may_be_complete": False,
        "permanent_refusal_may_be_complete": False,
        "compile_only_may_create_support": False,
    }
    for field, expected in required_scope.items():
        if scope.get(field) is not expected:
            problems.append(f"capability matrix scope.{field} must be {expected!r}")

    capabilities = record.get("capability", [])
    ids = [item.get("id") for item in capabilities if isinstance(item, dict)]
    if set(ids) != SEED_CAPABILITY_IDS or len(ids) != len(SEED_CAPABILITY_IDS):
        problems.append("capability matrix must contain the 12 seed release slices")
    if record.get("seed_release_slice_count") != len(ids):
        problems.append("capability matrix seed release slice count has drifted")
    if _duplicates(ids):
        problems.append("capability matrix repeats a capability id")
    for item in capabilities:
        item_id = item.get("id")
        if item.get("classification") not in {"ordinary", "advanced"}:
            problems.append(f"{item_id} has an invalid classification")
        if item.get("backend_status") not in STATUS_VALUES:
            problems.append(f"{item_id} has an invalid backend status")
        if item.get("evidence_status") not in STATUS_VALUES:
            problems.append(f"{item_id} has an invalid evidence status")
        if item.get("implementation_state") not in STATUS_VALUES:
            problems.append(f"{item_id} has an invalid implementation state")
        frontends = item.get("frontends", {})
        if set(frontends) != set(PROJECTIONS_1_0):
            problems.append(f"{item_id} must classify every frontend projection")
        elif any(value not in STATUS_VALUES for value in frontends.values()):
            problems.append(f"{item_id} has an invalid frontend status")
        required_by = item.get("required_by", [])
        if not required_by or any(value not in MILESTONE_IDS for value in required_by):
            problems.append(f"{item_id} has an invalid milestone binding")
        if item.get("implementation_state") == "complete":
            required_projections: set[str] = set()
            if "0.1.0" in required_by:
                required_projections.update(PROJECTIONS_0_1)
            if "1.0.0" in required_by:
                required_projections.update(PROJECTIONS_1_0)
            if item.get("backend_status") != "complete":
                problems.append(f"{item_id} completion requires a complete backend")
            if item.get("evidence_status") != "complete":
                problems.append(f"{item_id} completion requires complete evidence")
            incomplete = sorted(
                projection
                for projection in required_projections
                if frontends.get(projection) != "complete"
            )
            if incomplete:
                problems.append(
                    f"{item_id} completion has incomplete projections: {', '.join(incomplete)}"
                )
    return problems


def _validate_withdrawal(record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    immutable_expectations = {
        "published_tags_are_immutable": True,
        "published_assets_are_retained": True,
        "tag_move_allowed": False,
        "tag_delete_allowed": False,
        "asset_replacement_allowed": False,
        "replacement_requires_new_version": True,
        "withdrawal_record_required": True,
        "production_external_consequence_requires_human": True,
        "withdrawal_authorized": False,
    }
    for field, expected in immutable_expectations.items():
        if record.get(field) is not expected:
            problems.append(f"withdrawal policy {field} must be {expected!r}")
    states = [item.get("id") for item in record.get("state", [])]
    if states != ["active", "superseded", "withdrawn", "revoked"]:
        problems.append("withdrawal states have drifted")
    transitions = record.get("transition", [])
    pairs = [(item.get("from"), item.get("to")) for item in transitions]
    if len(pairs) != len(set(pairs)):
        problems.append("withdrawal policy repeats a transition")
    classes = record.get("release_class_authority", [])
    class_ids = [item.get("release_class") for item in classes]
    if class_ids != RELEASE_CLASSES[1:]:
        problems.append("withdrawal release classes have drifted")
    for item in classes:
        class_id = item.get("release_class")
        if item.get("currently_authorized") is not False:
            problems.append(f"{class_id} withdrawal is authorized before activation")
        if class_id == "alpha":
            if item.get("automated_after_activation") is not True:
                problems.append("alpha withdrawal must be design-delegable after activation")
        elif (
            item.get("automated_after_activation") is not False
            or item.get("human_decision_required") is not True
        ):
            problems.append(f"{class_id} withdrawal must remain human-controlled")
    return problems


def _validate_schemas(schemas: dict[str, dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    observed_ids: list[str] = []
    for name, expected_id in SCHEMA_IDS.items():
        schema = schemas.get(name, {})
        if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            problems.append(f"{name} must use JSON Schema draft 2020-12")
        if schema.get("$id") != expected_id:
            problems.append(f"{name} has the wrong schema identity")
        observed_ids.append(str(schema.get("$id")))
        if schema.get("type") != "object" or schema.get("additionalProperties") is not False:
            problems.append(f"{name} must be a closed object schema")
        if "authority" not in schema.get("required", []):
            problems.append(f"{name} must require an authority ceiling")
        authority = schema.get("$defs", {}).get("authority", {})
        authority_properties = authority.get("properties", {})
        authority_required = authority.get("required", [])
        if authority.get("additionalProperties") is not False:
            problems.append(f"{name} authority schema must be a closed object")
        if set(authority_required) != set(authority_properties):
            problems.append(f"{name} authority schema must require every grant")
        if not authority_properties or any(
            not isinstance(value, dict) or value.get("const") is not False
            for value in authority_properties.values()
        ):
            problems.append(f"{name} authority schema must keep every grant false")
        schema_const = schema.get("properties", {}).get("schema", {}).get("const")
        if schema_const != expected_id:
            problems.append(f"{name} document schema const has drifted")
    if len(observed_ids) != len(set(observed_ids)):
        problems.append("general release schemas repeat an identity")
    for name in ("release_candidate", "release_ledger_entry", "withdrawal_record"):
        pattern = schemas.get(name, {}).get("$defs", {}).get("semver", {}).get(
            "pattern"
        )
        if pattern != SEMVER_PATTERN:
            problems.append(f"{name} must use the canonical strict SemVer pattern")
    return problems


def _validate_ledger_readme(text: str) -> list[str]:
    required = (
        "append-only custody root",
        "No ledger record",
        "Published tags and assets are never moved, deleted, or replaced.",
        "facman.release_candidate.v1",
        "facman.human_test_receipt.v1",
        "facman.release_ledger_entry.v1",
        "facman.withdrawal_record.v1",
        "remain inactive",
    )
    return [
        f"release ledger README is missing {anchor!r}"
        for anchor in required
        if anchor not in text
    ]


def _validate_release_index(release_index: dict[str, Any]) -> list[str]:
    return [
        f"release index does not bind {key} to {expected}"
        for key, expected in INDEX_BINDINGS.items()
        if release_index.get(key) != expected
    ]


def validate(
    records: dict[str, dict[str, Any]],
    schemas: dict[str, dict[str, Any]],
    ledger_readme: str,
    release_index: dict[str, Any] | None = None,
) -> list[str]:
    problems: list[str] = []
    problems.extend(_validate_common(records))
    problems.extend(_validate_version_train(records.get("version_train", {})))
    problems.extend(_validate_autonomy(records.get("autonomy_policy", {})))
    problems.extend(_validate_milestones(records.get("milestones", {})))
    problems.extend(_validate_capability_matrix(records.get("capability_matrix", {})))
    problems.extend(_validate_withdrawal(records.get("withdrawal_policy", {})))
    problems.extend(_validate_schemas(schemas))
    problems.extend(_validate_ledger_readme(ledger_readme))
    if release_index is not None:
        problems.extend(_validate_release_index(release_index))
    return problems


def check() -> list[str]:
    missing = [
        str(path.relative_to(ROOT))
        for path in [
            *RECORD_PATHS.values(),
            *SCHEMA_PATHS.values(),
            LEDGER_README,
            RELEASE_INDEX,
        ]
        if not path.is_file()
    ]
    if missing:
        return ["missing release-programme file: " + path for path in missing]
    return validate(
        load_records(),
        load_schemas(),
        LEDGER_README.read_text(encoding="utf-8"),
        load_release_index(),
    )


def main() -> int:
    problems = check()
    if problems:
        for problem in problems:
            print(f"release-programme-check: {problem}", file=sys.stderr)
        return 1
    print("release-programme-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
