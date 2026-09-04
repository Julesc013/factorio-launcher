# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate and project the Technical Preview outcome/command census.

This tool is deliberately not a release resolver.  It consumes the existing
release compiler inputs and command catalogue, validates the reviewed product
outcome census, and emits deterministic review reports plus a many-to-many
command/API conformance ledger.
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
MATRIX_PATH = ROOT / "release/index/capability_frontend_matrix.v1.toml"
SCOPE_PATH = ROOT / "release/index/technical_preview_scope.v1.toml"
DEBT_PATH = ROOT / "release/index/technical_preview_incubator_debt.v1.toml"
INDEX_PATH = ROOT / "release/index/release_index.v1.toml"
CATALOG_PATH = ROOT / "contracts/generated-index/command_catalog.v2.json"
TARGETS_PATH = ROOT / "release/index/targets.v2.toml"
ARTIFACTS_PATH = ROOT / "release/index/artifacts.v2.toml"
PLAN_PATH = ROOT / "release/index/plan.v1.toml"
WINDOWS_PRODUCT_PROFILE_PATH = ROOT / "release/profiles/windows_product_x64/profile.toml"
PROFILE_CATALOG_PATH = ROOT / "release/profiles/profile_catalog.v1.toml"
PROFILE_LIFECYCLE_PATH = ROOT / "release/profiles/profile_lifecycle.v1.toml"
WINDOWS_PRODUCT_TARGET = "windows_winforms_technical_preview_x64"
WINDOWS_PRODUCT_ARTIFACT = "windows_winforms_technical_preview_zip"
LEDGER_PATH = ROOT / "release/generated/technical_preview_command_api_conformance.v1.json"
DOC_ROOT = ROOT / "docs/generated/technical_preview"

CLASSIFICATIONS = {
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
REQUIRED_FIELDS = {
    "id",
    "outcome",
    "family",
    "scope",
    "classification",
    "owner",
    "provider_owner",
    "status",
    "effect_class",
    "required_interfaces",
    "backend_evidence",
    "positive_evidence",
    "negative_evidence",
    "fault_recovery_evidence",
    "persistence_migration",
    "accessibility",
    "package_evidence",
    "documentation",
    "support",
    "limits",
    "invalidation_triggers",
    "dependent_commands",
}
FACMAN_FACTORIO_FAMILIES = {
    "installations",
    "instances",
    "profiles",
    "configuration",
    "content",
    "saves",
    "readiness",
    "launch",
    "sessions",
    "recovery",
    "servers",
}


def _toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _map_command(command_id: str) -> list[str]:
    if command_id == "presentation.query":
        return [
            "instances.select_inspect",
            "readiness.compute",
            "readiness.explain_blockers",
            "sessions.inspect",
            "last_run.inspect",
            "recovery.inspect_failure_unknown",
        ]
    if command_id == "presentation.action":
        return ["installations.discover_standalone"]
    if command_id == "capabilities.inspect":
        return ["identity.verify_backend_provider_package"]
    if command_id == "dev.bug_report":
        return ["support.export_redacted_bundle"]
    if command_id.startswith("dev."):
        return ["developer.instrumentation"]
    if command_id.startswith("diagnostics."):
        return ["support.export_redacted_bundle"]
    if command_id.startswith("doctor."):
        return ["doctor.safe_startup"]
    if command_id in {"factorio.product.inspect", "product.inspect", "package.verify"}:
        return ["identity.verify_backend_provider_package"]
    if command_id == "install_refs.list":
        return ["installations.inspect_identity_ownership"]
    if command_id == "installs.scan":
        return ["installations.discover_standalone"]
    if command_id == "installs.import":
        return ["installations.register_read_only"]
    if command_id in {
        "installs.describe", "installs.inspect", "installs.verify", "installs.reconcile.plan"
    }:
        return ["installations.inspect_identity_ownership"]
    if command_id.startswith("installs.") or command_id.startswith("setup."):
        return ["installations.managed_lifecycle"]
    if command_id in {"instances.create", "instances.clone"}:
        return ["instances.create_isolated"]
    if command_id == "instances.readiness":
        return ["readiness.compute", "readiness.explain_blockers"]
    if command_id.startswith("instances.") or command_id.startswith("instance."):
        return ["instances.select_inspect"]
    if command_id.startswith("profiles.") or command_id.startswith("templates."):
        return ["profiles.create_select"]
    if command_id.startswith("preferences."):
        return ["configuration.explain_effective"]
    if command_id.startswith("mods."):
        return ["mods.inspect_local"]
    if command_id.startswith("modsets."):
        return ["modsets.apply_instance_local"]
    if command_id in {"saves.backup", "saves.clone"} or command_id.startswith("snapshots."):
        return ["saves.backup"]
    if command_id.startswith("saves."):
        return ["saves.discover_select"]
    if command_id == "launch_plan.explain":
        return ["readiness.explain_blockers", "launch.menu_plan"]
    if command_id in {"launch.plan", "launch_plan.preflight", "run.preview"}:
        return ["launch.menu_plan"]
    if command_id == "run.execute":
        return ["launch.menu_execute", "sessions.inspect", "last_run.inspect"]
    if command_id.startswith("servers."):
        return ["servers.administration"]
    if command_id in {"workspace.recovery.inspect", "workspace.recovery.plan"}:
        return ["recovery.inspect_failure_unknown"]
    if command_id == "workspace.recovery.apply":
        return ["recovery.apply_supported"]
    if command_id.startswith("workspace.") or command_id == "onboarding.plan":
        return ["workspace.open_create_inspect"]
    if command_id == "utility.operation":
        return ["workspace.batch_utility"]
    return []


def _observed_classification(command: dict[str, Any], product_ids: list[str], matrix: dict[str, dict[str, Any]]) -> str:
    command_id = str(command["command_id"])
    if command_id.startswith("dev.") or command_id == "utility.operation":
        return "diagnostic_internal"
    if product_ids and all(matrix[item]["scope"] == "deferred" for item in product_ids):
        return "outside_preview"
    availability = command.get("availability")
    if availability == "implemented":
        return "implemented_unqualified"
    if availability in {"unavailable_until_gateway", "unavailable_until_isolation_proof"}:
        return "backend_only"
    return "unknown_unverified"


def build_ledger(matrix_record: dict[str, Any], catalog: dict[str, Any]) -> dict[str, Any]:
    matrix = {item["id"]: item for item in matrix_record["capability"]}
    entries: list[dict[str, Any]] = []
    for command in sorted(catalog["commands"], key=lambda item: item["command_id"]):
        product_ids = _map_command(str(command["command_id"]))
        human_cli = "required_unverified" if any(
            "cli_human" in matrix[item]["required_interfaces"] for item in product_ids
        ) else "not_required_for_preview"
        entries.append(
            {
                "command_id": command["command_id"],
                "runtime_id": command["runtime_id"],
                "native_id": command["native_id"],
                "product_capability_ids": product_ids,
                "runtime_capability_ids": command.get("required_capabilities", []),
                "effects": command.get("effects", []),
                "risk_tier": command.get("risk_tier", "unknown"),
                "availability": command.get("availability", "unspecified"),
                "observed_classification": _observed_classification(command, product_ids, matrix),
                "contract_path": command.get("contract_path", ""),
                "request_schema": command.get("request_schema", ""),
                "response_schema": command.get("response_schema", ""),
                "result_schema": command.get("result_schema", ""),
                "refusal_schema": command.get("refusal_schema", ""),
                "diagnostic_schema": command.get("diagnostic_schema", ""),
                "golden_success": command.get("golden_success", ""),
                "golden_refusal": command.get("golden_refusal", ""),
                "transports": {
                    "direct": "registered",
                    "process": "registered",
                    "daemon": "structured_refusal",
                },
                "frontends": {
                    "cli_json": "registered_contract",
                    "cli_human": human_cli,
                    "tui": "grammar_generated_command_explorer",
                    "winforms": "not_inferred_from_command_registration",
                },
            }
        )
    return {
        "schema": "facman.technical_preview_command_api_conformance.v1",
        "source_catalog": str(CATALOG_PATH.relative_to(ROOT)).replace("\\", "/"),
        "source_matrix": str(MATRIX_PATH.relative_to(ROOT)).replace("\\", "/"),
        "command_count": len(entries),
        "mapping_cardinality": "many_to_many_zero_or_more_product_capabilities_per_command",
        "completion_inference_from_registration": False,
        "commands": entries,
    }


def validate_scope_authority(scope: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if scope.get("public_release_allowed") is not False:
        problems.append("Technical Preview cannot authorize public release")
    if any(value is not False for value in scope.get("authority", {}).values()):
        problems.append("Technical Preview scope grants authority")
    if len(scope.get("publication_gate", [])) != 5 or any(
        gate.get("required_for_publication") is not True
        for gate in scope.get("publication_gate", [])
    ):
        problems.append("public publication law is incomplete")
    return problems


def validate() -> list[str]:
    problems: list[str] = []
    matrix_record = _toml(MATRIX_PATH)
    scope = _toml(SCOPE_PATH)
    debt = _toml(DEBT_PATH)
    index = _toml(INDEX_PATH)
    catalog = _json(CATALOG_PATH)
    targets = _toml(TARGETS_PATH)
    artifacts = _toml(ARTIFACTS_PATH)
    windows_product = _toml(WINDOWS_PRODUCT_PROFILE_PATH)
    profile_catalog = _toml(PROFILE_CATALOG_PATH)
    profile_lifecycle = _toml(PROFILE_LIFECYCLE_PATH)
    plan = _toml(PLAN_PATH)
    capabilities = matrix_record.get("capability", [])
    ids = [item.get("id") for item in capabilities]
    by_id = {item.get("id"): item for item in capabilities}
    if not 20 <= len(capabilities) <= 40:
        problems.append("product outcome matrix must contain 20-40 rows")
    if matrix_record.get("outcome_count") != len(capabilities):
        problems.append("product outcome count does not match the matrix")
    if len(ids) != len(set(ids)):
        problems.append("product outcome matrix repeats an id")
    if matrix_record.get("matrix_scope") != "user_outcomes":
        problems.append("matrix must be organized by user outcomes")
    if matrix_record.get("matrix_scope_detail") != (
        "windows_reference_technical_preview_with_cross_platform_beta_and_1_0_projection_laws"
    ):
        problems.append("matrix must distinguish its Windows reference scope from beta and 1.0 laws")
    if matrix_record.get("activation_status") != (
        "implemented_census_activation_graph_terminal"
    ):
        problems.append(
            "capability census activation status must reflect the terminal graph"
        )
    if matrix_record.get("activation_workunits_terminal") is not True:
        problems.append(
            "capability census activation WorkUnits must have accepted terminal dispositions"
        )
    activation_ids = matrix_record.get("activation_workunits")
    if activation_ids != [
        "FACMAN-TECHNICAL-PREVIEW-CENSUS-01",
        "FACMAN-SAME-BINARY-TUI-PARITY-01",
    ]:
        problems.append("capability census activation WorkUnit identities drifted")
    plan_workunits = {
        item.get("id"): item
        for item in plan.get("workunit", [])
        if isinstance(item, dict)
    }
    census_workunit = plan_workunits.get("FACMAN-TECHNICAL-PREVIEW-CENSUS-01", {})
    tui_workunit = plan_workunits.get("FACMAN-SAME-BINARY-TUI-PARITY-01", {})
    successor_id = matrix_record.get("activation_successor_workunit")
    successor = plan_workunits.get(successor_id, {})
    if (
        census_workunit.get("status") != "complete"
        or census_workunit.get("implementation_revision")
        != "909e9c62f447f72707cffb9ca9dbcb1b1bf5e274"
        or census_workunit.get("historical_aide_queue_record")
        != "not_created_before_current_queue_discipline"
    ):
        problems.append("Technical Preview census activation record is not exact")
    if (
        tui_workunit.get("status") != "superseded"
        or successor_id not in tui_workunit.get("superseded_by", [])
        or successor.get("status") != "complete"
    ):
        problems.append("TUI activation disposition or completed successor drifted")
    if matrix_record.get("one_row_per_command_census_required") is not False:
        problems.append("one-row-per-command product planning must remain false")
    if matrix_record.get("command_api_ledger_complete") is not True:
        problems.append("separate command/API ledger must be complete")
    if matrix_record.get("tui_ordinary_workflow_parity_blocking") is not True:
        problems.append("TUI must block ordinary Technical Preview workflow parity")
    if matrix_record.get("required_projections_windows_reference_0_1") != [
        "cli_json",
        "tui",
        "winforms",
    ]:
        problems.append("Technical Preview projections must be CLI JSON, same-binary TUI, and WinForms")
    if matrix_record.get("required_beta_terminal_surfaces") != [
        "cli_json",
        "cli_human",
        "tui",
    ]:
        problems.append("beta terminal surfaces must bind CLI JSON, human CLI, and same-binary TUI")
    if matrix_record.get("required_beta_preview_frontends") != [
        "winforms",
        "appkit",
        "gtk",
    ]:
        problems.append("beta preview frontends must bind WinForms, AppKit, and GTK")
    if set(matrix_record.get("maturity_states", [])) != CLASSIFICATIONS:
        problems.append("census classification vocabulary has drifted")
    required_ids = set(scope.get("required_capability_ids", []))
    deferred_ids = set(scope.get("deferred_capability_ids", []))
    if required_ids | deferred_ids != set(ids) or required_ids & deferred_ids:
        problems.append("Technical Preview scope must partition every outcome")
    for item in capabilities:
        item_id = str(item.get("id"))
        missing_fields = sorted(REQUIRED_FIELDS - set(item))
        if missing_fields:
            problems.append(f"{item_id} is missing fields: {', '.join(missing_fields)}")
            continue
        if item["status"] not in CLASSIFICATIONS:
            problems.append(f"{item_id} has an invalid census classification")
        expected_scope = "technical_preview_required" if item_id in required_ids else "deferred"
        if item["scope"] != expected_scope:
            problems.append(f"{item_id} has the wrong Technical Preview scope")
        if (
            expected_scope == "technical_preview_required"
            and item_id != "accessibility.winforms"
            and "tui" not in item.get("required_interfaces", [])
        ):
            problems.append(f"{item_id} must bind required same-binary TUI parity")
        if not item["invalidation_triggers"]:
            problems.append(f"{item_id} must bind invalidation triggers")
        for field in ("required_interfaces", "backend_evidence", "positive_evidence", "negative_evidence", "fault_recovery_evidence", "package_evidence", "dependent_commands"):
            if not isinstance(item[field], list):
                problems.append(f"{item_id}.{field} must be a list")
        if item["family"] in FACMAN_FACTORIO_FAMILIES and item["owner"] != "facman":
            problems.append(f"{item_id} moves Factorio product authority out of FacMan")
    if by_id.get("modsets.apply_instance_local", {}).get("effect_class") != "instance_content_mutation":
        problems.append("local modsets must be instance_content_mutation")
    if by_id.get("installations.managed_lifecycle", {}).get("scope") != "deferred":
        problems.append("managed installation must remain deferred")
    if by_id.get("instances.create_isolated", {}).get("provider_owner") != "facman":
        problems.append("Factorio instance lifecycle must remain FacMan-owned")
    if by_id.get("profiles.create_select", {}).get("provider_owner") != "facman":
        problems.append("Factorio profiles must remain FacMan-owned")
    workspace = by_id.get("workspace.open_create_inspect", {})
    if "journaled no-clobber apply" not in workspace.get("persistence_migration", ""):
        problems.append("workspace census must describe the admitted journaled migration apply")
    last_run = by_id.get("last_run.inspect", {})
    if last_run.get("status") != "implemented_unqualified" or (
        "runtime/factorio/application/last_run_provider.cpp"
        not in last_run.get("backend_evidence", [])
    ):
        problems.append("Last Run census must bind the ULK-authoritative backend projection")
    target = next(
        (item for item in targets.get("target", []) if item.get("id") == WINDOWS_PRODUCT_TARGET),
        None,
    )
    artifact = next(
        (item for item in artifacts.get("artifact", []) if item.get("id") == WINDOWS_PRODUCT_ARTIFACT),
        None,
    )
    catalog_profile = next(
        (item for item in profile_catalog.get("profile", []) if item.get("id") == "windows_product_x64"),
        None,
    )
    lifecycle = next(
        (item for item in profile_lifecycle.get("assignment", []) if item.get("profile_id") == "windows_product_x64"),
        None,
    )
    if (
        windows_product.get("id") != "windows_product_x64"
        or windows_product.get("lane") != "platform_product_bundle"
        or windows_product.get("linkage", {}).get("provider_source_linkage") != "shared"
        or catalog_profile is None
        or catalog_profile.get("status") != "current_product_active_unqualified"
        or lifecycle is None
        or lifecycle.get("lifecycle") != "active"
    ):
        problems.append("Technical Preview census must record the active shared-provider Windows product contract")
    if (
        target is None
        or target.get("frontend") != "winforms"
        or target.get("runtime_linkage") != "embedded_static"
        or artifact is None
        or artifact.get("target_id") != WINDOWS_PRODUCT_TARGET
    ):
        problems.append("Technical Preview census must record the distinct embedded-static v2 WinForms contract")
    problems.extend(validate_scope_authority(scope))
    if scope.get("tui_status") != "required_same_facman_binary_ordinary_parity_and_advanced_command_coverage":
        problems.append("TUI must provide required same-binary ordinary parity and Advanced command coverage")
    if scope.get("terminal_artifact_law") != (
        "facman provides cli_json, human_cli, and tui; no second tui executable is required"
    ):
        problems.append("Technical Preview must bind the single terminal artifact law")
    if scope.get("release_compiler") != "tools/facman_release.py":
        problems.append("Technical Preview must reuse the existing release compiler")
    if "SQLite" not in " ".join(item.get("stop_law", "") for item in debt.get("debt", [])):
        problems.append("persistence debt must keep SQLite derived-only")
    if index.get("technical_preview_scope") != "release/index/technical_preview_scope.v1.toml":
        problems.append("release index does not bind Technical Preview scope")
    if index.get("technical_preview_incubator_debt") != "release/index/technical_preview_incubator_debt.v1.toml":
        problems.append("release index does not bind Technical Preview incubator debt")
    ledger = build_ledger(matrix_record, catalog)
    command_ids = [item["command_id"] for item in ledger["commands"]]
    if len(command_ids) != len(set(command_ids)) or len(command_ids) != len(catalog["commands"]):
        problems.append("command/API ledger must contain every command exactly once")
    for entry in ledger["commands"]:
        unknown = set(entry["product_capability_ids"]) - set(ids)
        if unknown:
            problems.append(f"{entry['command_id']} maps unknown product outcomes")
    declared_commands = {
        command for item in capabilities for command in item.get("dependent_commands", [])
    }
    if declared_commands != set(command_ids):
        missing = sorted(set(command_ids) - declared_commands)
        extra = sorted(declared_commands - set(command_ids))
        if missing:
            problems.append("matrix omits dependent commands: " + ", ".join(missing))
        if extra:
            problems.append("matrix names unknown dependent commands: " + ", ".join(extra))
    return problems


def _table(headers: list[str], rows: list[list[str]]) -> str:
    def clean(value: str) -> str:
        return value.replace("|", "\\|").replace("\n", " ")
    result = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    result.extend("| " + " | ".join(clean(value) for value in row) + " |" for row in rows)
    return "\n".join(result)


def _wrapped_bullet(value: str) -> str:
    return textwrap.fill(
        value,
        width=100,
        initial_indent="- ",
        subsequent_indent="  ",
    )


def _wrapped_field(label: str, value: object) -> str:
    prefix = f"- {label}: "
    return textwrap.fill(
        str(value),
        width=100,
        initial_indent=prefix,
        subsequent_indent="  ",
    )


def _wrapped_paragraph(value: str) -> str:
    return textwrap.fill(value, width=100)


def build_outputs() -> dict[Path, str]:
    matrix_record = _toml(MATRIX_PATH)
    scope = _toml(SCOPE_PATH)
    debt = _toml(DEBT_PATH)
    targets = _toml(TARGETS_PATH)
    windows_product = _toml(WINDOWS_PRODUCT_PROFILE_PATH)
    ledger = build_ledger(matrix_record, _json(CATALOG_PATH))
    capabilities = matrix_record["capability"]
    generated = "<!-- Generated by tools/technical_preview_census.py; do not edit. -->\n\n"
    outputs: dict[Path, str] = {
        LEDGER_PATH: json.dumps(ledger, indent=2, sort_keys=True) + "\n",
    }
    product_rows = [
        [
            item["id"],
            item["scope"],
            item["status"],
            item["owner"],
            item["provider_owner"],
            ", ".join(item["required_interfaces"]) or "none",
        ]
        for item in capabilities
    ]
    outputs[DOC_ROOT / "product-capabilities.md"] = (
        generated
        + "# Technical Preview product capability census\n\n"
        + _table(
            ["Outcome", "Scope", "Status", "Owner", "Provider", "Interfaces"],
            product_rows,
        )
        + "\n"
    )
    class_counts: dict[str, int] = {}
    for entry in ledger["commands"]:
        class_counts[entry["observed_classification"]] = class_counts.get(entry["observed_classification"], 0) + 1
    command_rows = [[key, str(value)] for key, value in sorted(class_counts.items())]
    outputs[DOC_ROOT / "command-api-conformance.md"] = (
        generated
        + "# Command/API conformance census\n\n"
        + f"Commands: {ledger['command_count']}. Product mapping is many-to-many "
        + "and never creates a completion claim.\n\n"
        + _table(["Observed classification", "Commands"], command_rows)
        + "\n\nThe normative detailed ledger is "
        + "`release/generated/technical_preview_command_api_conformance.v1.json`.\n"
    )
    outputs[DOC_ROOT / "frontend-requirements.md"] = generated + (
        "# Technical Preview frontend requirements\n\n"
        "- WinForms is the primary ordinary-workflow projection.\n"
        "- CLI JSON is the normative automation and test contract.\n"
        "- Human CLI is required for Doctor, diagnostics, status, support, and recovery.\n"
        "- The task-oriented TUI is required through the same `facman` binary and "
        "blocks ordinary-workflow parity; the generated command explorer remains "
        "available under Advanced.\n"
        "- AppKit, GTK, Qt, WinUI, and SwiftUI are outside this milestone.\n"
    )
    persistence_items = [
        "FacMan owns human-readable JSON/TOML workspace records for Factorio "
        "installations, instances, profiles, modsets, saves, readiness inputs, "
        "and presentation intent.",
        "Universal Launcher owns only generic runnable references plus launch "
        "operation/session/Last Run outcome state.",
        "Universal Setup owns installed-state journals, setup transactions, "
        "recovery, and audit.",
        "The current path-based workspace store remains canonical. SQLite is not "
        "authoritative; a future SQLite index must be rebuildable and justified by "
        "measured query or concurrency pressure.",
        "FacMan migration apply is limited to journaled, no-clobber canonicalization "
        "of legacy install references and instance manifests; sources are preserved. "
        "Exact operation inspection, resume, recovery, and digest-safe rollback are "
        "public; unsupported, conflicting, corrupt, or future state fails closed.",
        "No frontend may own a second readiness or Last Run truth.",
    ]
    outputs[DOC_ROOT / "persistence-authority.md"] = (
        generated
        + "# Persistence authority\n\n"
        + "\n".join(_wrapped_bullet(item) for item in persistence_items)
        + "\n"
    )
    debt_sections = []
    for item in debt["debt"]:
        debt_sections.append(
            "\n".join(
                [
                    f"## `{item['id']}`",
                    "",
                    _wrapped_field("Current location", item["current_location"]),
                    _wrapped_field("Final owner", item["final_owner"]),
                    _wrapped_field(
                        "Preview dependency",
                        str(item["preview_dependency"]).lower(),
                    ),
                    _wrapped_field("Exit trigger", item["exit_trigger"]),
                ]
            )
        )
    outputs[DOC_ROOT / "incubator-debt.md"] = (
        generated
        + "# Technical Preview incubator debt\n\n"
        + "\n\n".join(debt_sections)
        + "\n"
    )
    outputs[DOC_ROOT / "scope.md"] = generated + (
        "# FacMan 0.1.0 — Technical Preview scope\n\n"
        f"Platform: `{scope['platform']}`. Primary frontend: "
        f"`{scope['primary_frontend']}`. Automation contract: "
        f"`{scope['normative_automation_contract']}`. Package class: "
        f"`{scope['package_class']}`.\n\n"
        f"Public release is not authorized. {scope['publication_law']}\n\n"
        f"Route/version decision: {scope['route_version_decision']}\n"
    )
    deferred = [item for item in capabilities if item["scope"] == "deferred"]
    deferred_rows = [[item["id"], item["status"], item["limits"]] for item in deferred]
    outputs[DOC_ROOT / "deferred-capabilities.md"] = (
        generated
        + "# Deferred capabilities\n\n"
        + _table(["Outcome", "Observed status", "Reason/limit"], deferred_rows)
        + "\n"
    )
    target_rows = [
        [item["id"], item["os"], item["frontend"], item["support_class"]]
        for item in targets["target"]
    ]
    windows_target = next(
        item for item in targets["target"] if item["id"] == WINDOWS_PRODUCT_TARGET
    )
    windows_composition = (
        "Two current reviewed combined WinForms composition contracts are "
        f"intentionally distinct: platform product profile `{windows_product['id']}` "
        f"uses support tier `{windows_product['support_tier']}` and provider linkage "
        f"`{windows_product['linkage']['provider_source_linkage']}`, while v2 Technical "
        f"Preview target `{WINDOWS_PRODUCT_TARGET}` uses runtime linkage "
        f"`{windows_target['runtime_linkage']}` and artifact "
        f"`{WINDOWS_PRODUCT_ARTIFACT}`. No authored profile-to-target binding exists "
        "between them. The separately retained legacy WinForms profile is "
        "compatibility evidence, not either current product composition."
    )
    outputs[DOC_ROOT / "release-compiler-targets.md"] = generated + (
        "# Release compiler target/package census\n\n"
        "The existing `tools/facman_release.py` remains the sole resolver. Its v2 "
        "target graph currently contains:\n\n"
        + _table(["Target", "OS", "Frontend", "Support"], target_rows)
        + "\n\n"
        + _wrapped_paragraph(windows_composition)
        + "\n"
    )
    return outputs


def check_outputs() -> list[str]:
    problems = validate()
    if problems:
        return problems
    for path, expected in build_outputs().items():
        if not path.is_file():
            problems.append(f"missing generated Technical Preview output: {path.relative_to(ROOT)}")
        elif path.read_text(encoding="utf-8") != expected:
            problems.append(f"stale generated Technical Preview output: {path.relative_to(ROOT)}")
    return problems


def write_outputs() -> None:
    problems = validate()
    if problems:
        raise ValueError("\n".join(problems))
    for path, content in build_outputs().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if args.check:
        problems = check_outputs()
        if problems:
            for problem in problems:
                print(f"technical-preview-census: {problem}", file=sys.stderr)
            return 1
        print("technical-preview-census: ok")
        return 0
    try:
        write_outputs()
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"technical-preview-census: {exc}", file=sys.stderr)
        return 1
    print("technical-preview-census: generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
