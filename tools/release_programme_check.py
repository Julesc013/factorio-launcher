# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate release-train policy and the bounded alpha-tag delegation."""

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
PLAN = INDEX / "plan.v1.toml"

RECORD_PATHS = {
    "version_train": INDEX / "version_train.v1.toml",
    "autonomy_policy": INDEX / "autonomy_policy.v1.toml",
    "capability_matrix": INDEX / "capability_frontend_matrix.v1.toml",
    "alpha_delegation": INDEX / "alpha_delegation.v1.toml",
}

RECORD_SCHEMAS = {
    "version_train": "facman.version_train.v1",
    "autonomy_policy": "facman.autonomy_policy.v1",
    "capability_matrix": "facman.capability_frontend_matrix.v1",
    "alpha_delegation": "facman.alpha_delegation.v1",
}

INDEX_BINDINGS = {
    "version_train": "release/index/version_train.v1.toml",
    "autonomy_policy": "release/index/autonomy_policy.v1.toml",
    "alpha_delegation": "release/index/alpha_delegation.v1.toml",
    "alpha1_dev_integration_closeout": "release/index/alpha1_dev_integration_closeout.v1.toml",
    "alpha1_tag_truth_closeout": "release/index/alpha1_tag_truth_closeout.v1.toml",
    "factorio_2_1_14_route_d3_d4_request": "release/index/factorio_2_1_14_route_d3_d4_request.v1.toml",
    "capability_frontend_matrix": "release/index/capability_frontend_matrix.v1.toml",
    "technical_preview_scope": "release/index/technical_preview_scope.v1.toml",
    "factorio_route_version_decision": "release/index/factorio_route_version_decision.v1.toml",
    "factorio_version_families": "release/index/factorio_version_families.v1.toml",
    "technical_preview_incubator_debt": "release/index/technical_preview_incubator_debt.v1.toml",
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
    "capability_matrix": {
        "capability_admission",
        "completion_claim",
        "support_promotion",
        "execution",
        "setup_mutation",
        "signing",
        "publication",
    },
    "alpha_delegation": {
        "version_allocation",
        "tag_creation",
        "alpha_supersession",
        "protected_dev_merge",
        "publication",
        "signing",
        "beta_rc_stable_tags",
        "route_effects",
        "support_activation",
        "human_verdict",
    },
}

AUTHORITY_VALUES = {
    "version_train": {
        "version_allocation": True,
        "tag_creation": True,
        "signing": False,
        "publication": False,
        "withdrawal": False,
        "stable_promotion": False,
    },
    "autonomy_policy": {
        "delegated_dev_merge": False,
        "isolated_lab_effects": False,
        "alpha_tag_creation": True,
        "alpha_publication": False,
        "beta_publication": False,
        "stable_publication": False,
        "production_credentials": False,
        "production_signing": False,
        "public_route_promotion": False,
        "human_verdict": False,
    },
    "capability_matrix": {
        "capability_admission": False,
        "completion_claim": False,
        "support_promotion": False,
        "execution": False,
        "setup_mutation": False,
        "signing": False,
        "publication": False,
    },
    "alpha_delegation": {
        "version_allocation": True,
        "tag_creation": True,
        "alpha_supersession": True,
        "protected_dev_merge": False,
        "publication": False,
        "signing": False,
        "beta_rc_stable_tags": False,
        "route_effects": False,
        "support_activation": False,
        "human_verdict": False,
    },
}

RELEASE_CLASSES = ["snapshot", "alpha", "beta", "rc", "stable_0x", "stable_1x"]
PLAN_RELEASE_IDS = [
    "FACMAN-C1",
    "FACMAN-0.1-WINDOWS-TECHNICAL-PREVIEW",
    "FACMAN-1.0-SUPPORTED-RELEASE",
    "FACMAN-0.1.0-ALPHA.1",
]
PROJECTIONS_0_1 = ["cli_json", "tui", "winforms"]
PROJECTIONS_1_0 = ["cli_json", "cli_human", "tui", "winforms", "appkit", "gtk"]
PROJECTIONS_ALPHA_1 = ["cli_json", "cli_human", "tui", "winforms"]
FACTORIO_FAMILIES_ALPHA_1 = ["F100", "F110", "F200", "F210"]
EVIDENCE_CLASSES = [
    "positive",
    "negative",
    "fault",
    "recovery",
    "persistence_and_migration",
    "package",
    "accessibility",
    "documentation",
    "support",
]
MATURITY_VALUES = {
    "release_qualified",
    "qualified",
    "implemented_unqualified",
    "fixture_only",
    "frontend_only",
    "backend_only",
    "planned",
    "diagnostic_internal",
    "deprecated",
    "outside_preview",
    "unknown_unverified",
}
EFFECT_VALUES = {"read_only", "local_state", "instance_content_mutation", "external_process", "setup_mutation", "mixed_effect"}
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


def load_plan() -> dict[str, Any]:
    return _toml(PLAN)


def _duplicates(values: list[Any]) -> set[Any]:
    return {value for value in values if values.count(value) > 1}


def _validate_common(records: dict[str, dict[str, Any]]) -> list[str]:
    problems: list[str] = []
    for name, expected_schema in RECORD_SCHEMAS.items():
        record = records.get(name, {})
        if record.get("schema") != expected_schema:
            problems.append(f"{name} has the wrong schema")
        if name == "alpha_delegation":
            if record.get("status") != "active_when_reachable_from_protected_dev_and_tag_ruleset_enforced":
                problems.append(
                    "alpha_delegation status must require protected dev and the tag ruleset"
                )
            authority = record.get("authority")
            if not isinstance(authority, dict) or set(authority) != AUTHORITY_KEYS[name]:
                problems.append(f"{name} authority ceiling has the wrong closed fields")
            elif authority != AUTHORITY_VALUES[name]:
                problems.append(f"{name} authority ceiling has drifted")
            continue
        if record.get("design_status") != "ratified":
            problems.append(f"{name} design_status must be ratified")
        expected_activation = (
            "partial_alpha_tagging_active"
            if name in {"version_train", "autonomy_policy"}
            else "pending_workunits"
        )
        if record.get("activation_status") != expected_activation:
            problems.append(f"{name} activation_status must be {expected_activation}")
        workunits = record.get("activation_workunits")
        if not isinstance(workunits, list):
            problems.append(f"{name} must carry an activation WorkUnit list")
        elif name != "autonomy_policy" and not workunits:
            problems.append(f"{name} must name remaining activation WorkUnits")
        elif len(workunits) != len(set(workunits)):
            problems.append(f"{name} repeats an activation WorkUnit")
        authority = record.get("authority")
        if not isinstance(authority, dict) or not authority:
            problems.append(f"{name} must carry an explicit authority ceiling")
        else:
            if set(authority) != AUTHORITY_KEYS[name]:
                problems.append(f"{name} authority ceiling has the wrong closed fields")
            elif authority != AUTHORITY_VALUES[name]:
                problems.append(f"{name} authority ceiling has drifted")
    return problems


def _validate_version_train(record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if record.get("current_product_target") != "0.1.0":
        problems.append("version train current target must be 0.1.0")
    if record.get("development_base_version") != "0.1.0-alpha.1":
        problems.append("current distribution source must use the allocated 0.1.0-alpha.1 identity")
    if record.get("tracked_contract_identity") != (
        "facman-0.1.0-alpha.1"
    ):
        problems.append("tracked 0.1.0-alpha.1 release identity has drifted")
    if record.get("tracked_contract_identity_is_publishable") is not True:
        problems.append("tracked alpha identity must be structurally publishable after its gates")
    if record.get("dynamic_snapshot_identity_projected_at_build_time") is not False:
        problems.append("tracked alpha identity cannot be a dynamic snapshot")
    allocation = {
        "release_source_workunit": "FACMAN-0.1.0-ALPHA.1-RELEASE-SOURCE-01",
        "release_source_status": "allocated_pending_exact_head_acceptance",
        "allocated_release_class": "alpha",
        "allocated_version": "0.1.0-alpha.1",
    }
    for field, expected in allocation.items():
        if record.get(field) != expected:
            problems.append(f"version train {field} must be {expected!r}")
    if not record.get("published_tags_are_immutable"):
        problems.append("version train must keep published tags immutable")
    if record.get("tag_every_commit") is not False:
        problems.append("version train must not tag every commit")
    for field in ("version_allocation_authorized", "tag_creation_authorized"):
        if record.get(field) is not True:
            problems.append(f"version train {field} must be true")
    for field in ("signing_authorized", "publication_authorized"):
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
        expected_authorized = class_id == "alpha"
        if release_class.get("currently_authorized") is not expected_authorized:
            problems.append(
                f"{class_id} currently_authorized must be {expected_authorized}"
            )
    if next(item for item in classes if item.get("id") == "alpha").get(
        "publication_kind"
    ) != "unpublished_annotated_tag":
        problems.append("alpha publication kind must remain an unpublished annotated tag")
    domains = record.get("version_domains", [])
    if len(domains) != len(set(domains)) or "product" not in domains or "c_abi" not in domains:
        problems.append("version domains must be unique and include product and C ABI")

    withdrawal = record.get("withdrawal", {})
    withdrawal_expectations = {
        "record_schema": "facman.withdrawal_record.v1",
        "published_tags_are_immutable": True,
        "published_assets_are_retained": True,
        "tag_move_allowed": False,
        "tag_delete_allowed": False,
        "asset_replacement_allowed": False,
        "replacement_requires_new_version": True,
        "append_only_record_required": True,
        "states": ["active", "superseded", "withdrawn", "revoked"],
        "alpha_supersession_automatable_after_activation": True,
        "beta_rc_stable_external_withdrawal_requires_human": True,
        "production_notification_requires_human": True,
        "currently_authorized": False,
    }
    for field, expected in withdrawal_expectations.items():
        if withdrawal.get(field) != expected:
            problems.append(f"version train withdrawal.{field} must be {expected!r}")
    withdrawal_classes = withdrawal.get("release_class", [])
    withdrawal_ids = [item.get("id") for item in withdrawal_classes]
    if withdrawal_ids != RELEASE_CLASSES[1:]:
        problems.append("version train withdrawal release classes have drifted")
    for item in withdrawal_classes:
        class_id = item.get("id")
        expected_authorized = class_id == "alpha"
        if item.get("currently_authorized") is not expected_authorized:
            problems.append(
                f"{class_id} withdrawal currently_authorized must be {expected_authorized}"
            )
        if class_id == "alpha":
            if item.get("automated_supersession_after_activation") is not True:
                problems.append("alpha supersession must remain delegable after activation")
            if item.get("human_decision_required") is not False:
                problems.append("alpha supersession cannot require a human by default")
        elif (
            item.get("automated_supersession_after_activation") is not False
            or item.get("human_decision_required") is not True
        ):
            problems.append(f"{class_id} withdrawal must remain human-controlled")
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
    routing = record.get("model_routing", {})
    if routing.get("routing_basis") != "task_semantics_risk_and_escalation":
        problems.append("model routing must remain semantic and risk-based")
    if routing.get("fixed_quota_forbidden") is not True:
        problems.append("model routing cannot become a fixed quota")
    return problems


def _validate_alpha_delegation(record: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    expected = {
        "policy_id": "FACMAN-AUTONOMOUS-ALPHA-DELEGATION-01",
        "product_id": "facman",
        "release_train": "0.1.0-alpha.N",
        "source_ref": "dev",
        "source_requirement": "exact_current_protected_dev_commit_and_tree",
        "tag_type": "annotated",
        "tag_every_commit": False,
        "required_check_freshness_hours": 24,
        "required_check_app_id": 15368,
        "required_contract_set_source": "runtime/core/generated/version.h",
        "required_state_identity": "facman.workspace.v1",
        "required_package_profiles": [
            "windows_portable_cli_x64",
            "windows_portable_tui_x64",
            "windows_legacy_winforms_x64",
        ],
        "required_tag_ruleset_include": "refs/tags/v0.1.0-alpha.*",
        "required_tag_ruleset_enforcement": "active",
        "required_tag_rules": ["deletion", "update"],
        "tag_ruleset_bypass_actors_allowed": False,
    }
    for field, value in expected.items():
        if record.get(field) != value:
            problems.append(f"alpha delegation {field} must be {value!r}")
    checks = record.get("required_checks", [])
    if not checks or len(checks) != len(set(checks)):
        problems.append("alpha delegation must bind unique required checks")
    significance = record.get("release_significant_reasons", [])
    if not significance or len(significance) != len(set(significance)):
        problems.append("alpha delegation must bind unique release-significant reasons")
    attestations = record.get("attestations", {})
    if attestations.get("required_roles") != ["implementation", "assurance", "control"]:
        problems.append("alpha delegation must require implementation, assurance, and control")
    if any(
        attestations.get(field) is not True
        for field in (
            "roles_must_be_logically_independent",
            "exact_source_and_tree_required",
            "immutable_evidence_digest_required",
            "all_results_must_pass",
        )
    ):
        problems.append("alpha delegation attestation law has drifted")
    immutability = record.get("immutability", {})
    if any(
        immutability.get(field) is not False
        for field in ("tag_movement", "tag_deletion", "tag_reuse", "retroactive_bulk_tagging")
    ):
        problems.append("alpha delegation permits tag mutation, reuse, or bulk backfill")
    if any(
        immutability.get(field) is not True
        for field in (
            "next_number_from_tags_and_ledger",
            "replacement_requires_new_number",
        )
    ):
        problems.append("alpha delegation allocation immutability has drifted")
    return problems


def _validate_plan_milestones(plan: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    releases = plan.get("release", [])
    ids = [item.get("id") for item in releases if isinstance(item, dict)]
    if ids != PLAN_RELEASE_IDS:
        problems.append(f"canonical plan release order must be {PLAN_RELEASE_IDS!r}")
        return problems
    if plan.get("active_release") != "FACMAN-0.1.0-ALPHA.1":
        problems.append("FacMan 0.1.0-alpha.1 must be the active release")
    by_id = {item["id"]: item for item in releases}
    c1 = by_id["FACMAN-C1"]
    if c1.get("status") != "cancelled" or "alpha foundation" not in c1.get("title", ""):
        problems.append("the superseded C1 train must remain a closed internal alpha foundation")
    if "Superseded by" not in c1.get("disposition", ""):
        problems.append("the superseded C1 train must name its Technical Preview replacement")
    if not any(
        "public" in item.lower() and "beta" in item.lower()
        for item in c1.get("non_goals", [])
    ):
        problems.append("C1 must explicitly exclude the public beta claim")
    preview = by_id["FACMAN-0.1-WINDOWS-TECHNICAL-PREVIEW"]
    if preview.get("version") != "0.1.0" or preview.get("status") != "complete":
        problems.append("0.1.0 must remain the completed bounded Windows Technical Preview")
    if preview.get("required_frontends") != PROJECTIONS_0_1:
        problems.append("0.1.0 Technical Preview must require CLI JSON, same-binary TUI, and WinForms")
    if preview.get("required_human_cli_surfaces") != [
        "doctor", "diagnostics", "status", "support", "recovery"
    ]:
        problems.append("0.1.0 must require human CLI for diagnostic/recovery surfaces")
    if preview.get("tui_parity_blocking") is not True:
        problems.append("0.1.0 TUI ordinary-workflow parity must be release-blocking")
    if preview.get("contract") != "docs/product/facman_0_1_windows_technical_preview.md":
        problems.append("0.1.0 must bind its Technical Preview contract")
    if not any(
        "matrix row" in item.lower() or "capability row" in item.lower()
        for item in preview.get("exit", [])
    ):
        problems.append("0.1.0 completion must be bound to its frozen matrix")
    one_zero = by_id["FACMAN-1.0-SUPPORTED-RELEASE"]
    if one_zero.get("version") != "1.0.0" or one_zero.get("status") != "planned":
        problems.append("1.0.0 must remain a planned supported release")
    if one_zero.get("required_frontends") != PROJECTIONS_1_0:
        problems.append("1.0.0 must require the bounded CLI and primary native GUI projections")
    if one_zero.get("separate_admission_frontends") != ["qt"]:
        problems.append("1.0.0 must require separate admission for Qt")
    if "qt_quick_kirigami" not in one_zero.get("optional_post_1_0_frontends", []):
        problems.append("Qt Quick/Kirigami must remain an optional post-1.0 projection")
    if "Windows, macOS, and Linux" not in one_zero.get("platform_cut", ""):
        problems.append("1.0.0 must require Windows, macOS, and Linux")
    alpha = by_id["FACMAN-0.1.0-ALPHA.1"]
    if alpha.get("version") != "0.1.0-alpha.1" or alpha.get("status") != "active":
        problems.append("0.1.0-alpha.1 must be the active alpha integration")
    if alpha.get("required_frontends") != PROJECTIONS_ALPHA_1:
        problems.append("alpha.1 must require CLI JSON, human CLI, same-binary TUI, and WinForms")
    if alpha.get("required_factorio_families") != FACTORIO_FAMILIES_ALPHA_1:
        problems.append("alpha.1 must require exact F100, F110, F200, and F210 qualification")
    authority_text = " ".join(alpha.get("non_goals", [])).lower()
    for boundary in ("tagging", "signing", "publication", "merging"):
        if boundary not in authority_text:
            problems.append(f"alpha.1 integration must keep {boundary} outside this WorkUnit")
    return problems


def _validate_capability_matrix(
    record: dict[str, Any], plan: dict[str, Any]
) -> list[str]:
    problems: list[str] = []
    if record.get("matrix_scope") != "user_outcomes":
        problems.append("capability matrix must be organized by user outcomes")
    if record.get("census_state") != "implemented_and_evidence_census_complete":
        problems.append("capability implementation/evidence census must be complete")
    if record.get("command_api_ledger_complete") is not True:
        problems.append("separate command/API ledger must be complete")
    if record.get("one_row_per_command_census_required") is not False:
        problems.append("product planning cannot require one row per command")
    if record.get("required_projections_0_1") != PROJECTIONS_0_1:
        problems.append("Technical Preview projections have drifted")
    if record.get("required_projections_1_0") != PROJECTIONS_1_0:
        problems.append("capability matrix 1.0 projections have drifted")
    if record.get("required_evidence_classes") != EVIDENCE_CLASSES:
        problems.append("capability matrix evidence classes have drifted")
    if set(record.get("maturity_states", [])) != MATURITY_VALUES:
        problems.append("capability matrix maturity vocabulary has drifted")
    if record.get("tui_1_0_status") != "required_same_facman_binary":
        problems.append("capability matrix must require the same-binary TUI for 1.0")
    if record.get("qt_1_0_status") != "separate_admission_required":
        problems.append("capability matrix must require separate Qt admission for 1.0")
    if record.get("qt_quick_kirigami_status") != "optional_post_1_0_projection":
        problems.append("capability matrix must defer Qt Quick/Kirigami")
    if record.get("completion_claim_authorized") is not False:
        problems.append("capability matrix cannot authorize a completion claim")
    scope = record.get("scope", {})
    required_scope = {
        "completion_means_semantic_parity": True,
        "ordinary_workflow_may_require_advanced": False,
        "fixture_only_may_be_complete": False,
        "frontend_only_may_be_complete": False,
        "backend_only_may_be_complete": False,
        "permanent_refusal_may_be_complete": False,
        "compile_only_may_create_support": False,
        "command_registration_may_imply_completion": False,
        "schemas_may_imply_implementation": False,
    }
    for field, expected in required_scope.items():
        if scope.get(field) is not expected:
            problems.append(f"capability matrix scope.{field} must be {expected!r}")

    capabilities = record.get("capability", [])
    ids = [item.get("id") for item in capabilities if isinstance(item, dict)]
    if not 20 <= len(ids) <= 40:
        problems.append("capability matrix must contain 20-40 user outcomes")
    if record.get("outcome_count") != len(ids):
        problems.append("capability matrix outcome count has drifted")
    if _duplicates(ids):
        problems.append("capability matrix repeats a capability id")
    for item in capabilities:
        item_id = item.get("id")
        if item.get("classification") not in {"ordinary", "advanced"}:
            problems.append(f"{item_id} has an invalid classification")
        if item.get("status") not in MATURITY_VALUES:
            problems.append(f"{item_id} has an invalid census status")
        if item.get("effect_class") not in EFFECT_VALUES:
            problems.append(f"{item_id} has an invalid effect class")
        for field in (
            "provider_owner",
            "persistence_migration",
            "accessibility",
            "documentation",
            "support",
            "limits",
        ):
            if not isinstance(item.get(field), str) or not item[field]:
                problems.append(f"{item_id} must bind {field}")
        for field in (
            "required_interfaces",
            "backend_evidence",
            "positive_evidence",
            "negative_evidence",
            "fault_recovery_evidence",
            "package_evidence",
            "invalidation_triggers",
            "dependent_commands",
        ):
            value = item.get(field)
            if not isinstance(value, list):
                problems.append(f"{item_id} must bind {field} as a list")
        if not item.get("invalidation_triggers"):
            problems.append(f"{item_id} must bind invalidation triggers")
        if item.get("scope") not in {"technical_preview_required", "deferred"}:
            problems.append(f"{item_id} has an invalid milestone scope")
        if (
            item.get("scope") == "technical_preview_required"
            and item_id != "accessibility.winforms"
            and "tui" not in item.get("required_interfaces", [])
        ):
            problems.append(f"{item_id} must bind required same-binary TUI parity")
    by_id = {item.get("id"): item for item in capabilities}
    if by_id.get("modsets.apply_instance_local", {}).get("effect_class") != "instance_content_mutation":
        problems.append("local modsets must be instance_content_mutation")
    if by_id.get("installations.managed_lifecycle", {}).get("scope") != "deferred":
        problems.append("managed installation must remain deferred from the Technical Preview")
    if record.get("tui_ordinary_workflow_parity_blocking") is not True:
        problems.append("TUI must block Technical Preview ordinary-workflow parity")
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
    problems = [
        f"release index does not bind {key} to {expected}"
        for key, expected in INDEX_BINDINGS.items()
        if release_index.get(key) != expected
    ]
    for obsolete in ("milestones", "withdrawal_policy"):
        if obsolete in release_index:
            problems.append(f"release index retains duplicate programme truth: {obsolete}")
    return problems


def validate(
    records: dict[str, dict[str, Any]],
    schemas: dict[str, dict[str, Any]],
    ledger_readme: str,
    release_index: dict[str, Any] | None = None,
    plan: dict[str, Any] | None = None,
) -> list[str]:
    problems: list[str] = []
    selected_plan = plan if plan is not None else load_plan()
    problems.extend(_validate_common(records))
    problems.extend(_validate_version_train(records.get("version_train", {})))
    problems.extend(_validate_autonomy(records.get("autonomy_policy", {})))
    problems.extend(_validate_alpha_delegation(records.get("alpha_delegation", {})))
    problems.extend(_validate_plan_milestones(selected_plan))
    problems.extend(
        _validate_capability_matrix(
            records.get("capability_matrix", {}),
            selected_plan,
        )
    )
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
            PLAN,
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
        load_plan(),
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
