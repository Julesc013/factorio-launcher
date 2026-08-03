# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the bounded facman.presentation.v0 contract and C1 fixtures."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import generate_presentation_fixtures

try:
    import jsonschema
except ModuleNotFoundError:
    jsonschema = None

SCHEMA = ROOT / "contracts" / "schema" / "ui" / "facman.presentation.v0.schema.json"
CONTRACT = ROOT / "docs" / "product" / "facman_presentation_v0.md"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "presentation"
MANIFEST = FIXTURE_ROOT / "manifest.v0.json"

EXPECTED_STATES = ("positive", "refused", "running", "exited", "interrupted")
EXPECTED_PAGES = ("instances", "installations", "activity", "settings_about")
EXPECTED_RECORDS = {
    "ActionDescriptor",
    "ActivityView",
    "InstanceListItem",
    "InstanceListView",
    "InstanceSummaryView",
    "LastRunView",
    "LaunchDeckView",
    "NavigationNode",
    "OperationView",
    "PageSummary",
    "ReadinessView",
    "RecoveryView",
    "RefusalView",
    "ShellSnapshot",
}
HELPER_DEFINITIONS = {"Identifier", "JourneyState", "NonEmptyString", "PageId"}
PROHIBITED_SEMANTIC_TERMS = {
    "Control",
    "FrameworkElement",
    "GtkWidget",
    "NSView",
    "QQuickItem",
    "QObject",
    "QWidget",
    "System.Windows.Forms",
    "SwiftUI.View",
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def iter_actions(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        if "action_id" in value:
            yield value
        for child in value.values():
            yield from iter_actions(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_actions(child)


def validate_contract(schema: dict[str, Any], contract_text: str) -> list[str]:
    problems: list[str] = []
    definitions = set(schema.get("$defs", {}))
    records = definitions - HELPER_DEFINITIONS
    if records != EXPECTED_RECORDS:
        problems.append(
            "semantic record set mismatch: "
            f"missing={sorted(EXPECTED_RECORDS - records)} "
            f"extra={sorted(records - EXPECTED_RECORDS)}"
        )
    required_markers = [
        "facman.presentation.v0",
        "experimental and FacMan-local",
        "bounded process RPC",
        "backend owns",
        "four top-level pages",
        "fixture_only",
        "route authority",
        "not a Universal Launcher ABI",
    ]
    for marker in required_markers:
        if marker not in contract_text:
            problems.append(f"contract documentation is missing marker: {marker}")

    encoded_schema = json.dumps(schema, sort_keys=True)
    for term in sorted(PROHIBITED_SEMANTIC_TERMS):
        if term in encoded_schema:
            problems.append(f"schema contains toolkit type {term}")
    return problems


def validate_action(action: dict[str, Any], authority_scope: str) -> list[str]:
    problems: list[str] = []
    action_id = action.get("action_id", "<missing>")
    availability = action.get("availability")
    refusal = action.get("refusal")
    effects = set(action.get("effects", []))
    if availability == "refused" and not isinstance(refusal, dict):
        problems.append(f"{action_id}: refused action requires structured refusal")
    if availability == "available" and refusal is not None:
        problems.append(f"{action_id}: available action cannot carry refusal")
    if action.get("command_id") is None:
        if action.get("backend_owned") is not False:
            problems.append(f"{action_id}: local navigation must not claim backend ownership")
        if effects != {"read_only"}:
            problems.append(f"{action_id}: local navigation must be read-only")
    if "process_execution" in effects:
        if availability != "refused" or authority_scope != "unavailable":
            problems.append(
                f"{action_id}: live process execution must remain refused and unavailable"
            )
    if "fixture_process" in effects and authority_scope != "fixture_only":
        problems.append(f"{action_id}: fixture process action requires fixture_only scope")
    return problems


def validate_snapshot(snapshot: dict[str, Any], state: str) -> list[str]:
    problems: list[str] = []
    if snapshot.get("contract") != "facman.presentation.v0":
        problems.append(f"{state}: wrong contract identity")
    if snapshot.get("fixture_state") != state:
        problems.append(f"{state}: fixture_state mismatch")

    navigation = snapshot.get("navigation", [])
    page_ids = tuple(node.get("page_id") for node in navigation if isinstance(node, dict))
    if page_ids != EXPECTED_PAGES:
        problems.append(f"{state}: navigation must be the frozen four-page order")
    pages = snapshot.get("pages", {})
    if set(pages) != set(EXPECTED_PAGES):
        problems.append(f"{state}: page payloads must contain the frozen four pages")

    selected = snapshot.get("selected_instance", {})
    deck = snapshot.get("launch_deck", {})
    instance_items = pages.get("instances", {}).get("items", [])
    selected_items = [item for item in instance_items if item.get("selected") is True]
    if len(selected_items) != 1:
        problems.append(f"{state}: exactly one fixture instance must be selected")
    selected_id = selected.get("instance_id")
    if deck.get("instance_id") != selected_id:
        problems.append(f"{state}: persistent Launch Deck selection is inconsistent")
    if selected_items and selected_items[0].get("instance_id") != selected_id:
        problems.append(f"{state}: selected list item is inconsistent")

    transport = snapshot.get("transport", {})
    if transport != {
        "mode": "bounded_process_rpc",
        "session_owner": "facman_backend",
        "journal_owner": "facman_backend",
        "frontend_disconnect": "operation_continues",
        "route_authority": "unchanged",
    }:
        problems.append(f"{state}: process transport and backend ownership must remain frozen")

    authority_scope = str(snapshot.get("authority_scope"))
    for descriptor in iter_actions(snapshot):
        problems.extend(validate_action(descriptor, authority_scope))

    activity_operations = pages.get("activity", {}).get("operations", [])
    for operation in activity_operations:
        if operation.get("backend_operation_owner") != "facman_backend":
            problems.append(f"{state}: operation owner must remain facman_backend")
        if operation.get("frontend_disconnect") != "observe_or_recover":
            problems.append(f"{state}: frontend disconnect cannot cancel the operation")

    readiness = selected.get("readiness", {})
    refusal = snapshot.get("refusal")
    recovery = snapshot.get("recovery", {})
    if state == "positive":
        if readiness.get("state") != "ready" or refusal is not None:
            problems.append("positive: expected ready state without refusal")
        if deck.get("primary_action", {}).get("effects") != ["fixture_process"]:
            problems.append("positive: Play must be explicitly fixture-only")
        if activity_operations:
            problems.append("positive: no operation should have started")
    elif state == "refused":
        if readiness.get("state") != "stale" or not isinstance(refusal, dict):
            problems.append("refused: stale readiness and structured refusal are required")
        elif refusal.get("observed_readiness_revision", 0) >= refusal.get(
            "current_readiness_revision", 0
        ):
            problems.append("refused: current readiness revision must exceed observed")
        if deck.get("primary_action", {}).get("availability") != "refused":
            problems.append("refused: Launch Deck Play must refuse")
    elif state == "running":
        if len(activity_operations) != 1 or activity_operations[0].get("status") != "running":
            problems.append("running: Activity must contain one running operation")
        elif selected.get("operation_id") != activity_operations[0].get("operation_id"):
            problems.append("running: selected instance must bind the backend operation")
        if recovery.get("state") != "clear":
            problems.append("running: recovery must remain clear")
    elif state == "exited":
        last_run = selected.get("last_run") or {}
        if len(activity_operations) != 1 or activity_operations[0].get("status") != "succeeded":
            problems.append("exited: Activity must contain one succeeded operation")
        if last_run.get("outcome") != "exited" or last_run.get("exit_code") != 0:
            problems.append("exited: last run must report ordinary zero exit")
        if deck.get("primary_action", {}).get("action_id") != "instance.play":
            problems.append("exited: Launch Deck must offer deterministic relaunch")
    elif state == "interrupted":
        if len(activity_operations) != 1 or activity_operations[0].get("status") != "interrupted":
            problems.append("interrupted: Activity must contain one interrupted operation")
        operation_id = activity_operations[0].get("operation_id") if activity_operations else None
        if recovery.get("state") != "required":
            problems.append("interrupted: recovery must be required")
        if recovery.get("operation_id") != operation_id:
            problems.append("interrupted: recovery must bind the interrupted operation")
        if deck.get("recovery_id") != recovery.get("recovery_id"):
            problems.append("interrupted: Launch Deck must bind the recovery record")
    return problems


def validate_generated_files() -> list[str]:
    problems: list[str] = []
    for path, expected in generate_presentation_fixtures.render_fixtures().items():
        if not path.is_file():
            problems.append(f"missing generated fixture {path.relative_to(ROOT)}")
        elif path.read_text(encoding="utf-8") != expected:
            problems.append(f"stale generated fixture {path.relative_to(ROOT)}")
    return problems


def validate_manifest(manifest: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if manifest.get("schema") != "facman.presentation_fixture_manifest.v0":
        problems.append("fixture manifest schema identity is invalid")
    entries = manifest.get("states", [])
    if [entry.get("state") for entry in entries] != list(EXPECTED_STATES):
        problems.append("fixture manifest state order is invalid")
    for entry in entries:
        relative = entry.get("path", "")
        path = ROOT / relative
        if not path.is_file() or ROOT not in path.resolve().parents:
            problems.append(f"fixture manifest path is missing or unsafe: {relative}")
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != entry.get("sha256"):
            problems.append(f"fixture digest mismatch: {relative}")
    return problems


def main() -> int:
    problems: list[str] = []
    try:
        schema = load_json(SCHEMA)
        contract_text = CONTRACT.read_text(encoding="utf-8")
        manifest = load_json(MANIFEST)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"facman-presentation-check: {exc}", file=sys.stderr)
        return 1

    problems.extend(validate_contract(schema, contract_text))
    problems.extend(validate_generated_files())
    problems.extend(validate_manifest(manifest))
    if jsonschema is None:
        problems.append("jsonschema dependency is unavailable")
    else:
        try:
            jsonschema.validators.validator_for(schema).check_schema(schema)
        except jsonschema.exceptions.SchemaError as exc:
            problems.append(f"presentation schema is invalid: {exc.message}")

    encoded_fixtures: list[str] = []
    for state in EXPECTED_STATES:
        path = FIXTURE_ROOT / f"{state}.facman.presentation.v0.json"
        try:
            snapshot = load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"{path.relative_to(ROOT)}: {exc}")
            continue
        encoded_fixtures.append(json.dumps(snapshot, sort_keys=True))
        if jsonschema is not None:
            validator = jsonschema.validators.validator_for(schema)(schema)
            for error in sorted(validator.iter_errors(snapshot), key=lambda item: list(item.path)):
                location = ".".join(str(part) for part in error.absolute_path) or "$"
                problems.append(f"{state}: schema rejection at {location}: {error.message}")
        problems.extend(validate_snapshot(snapshot, state))

    combined = "\n".join(encoded_fixtures)
    for term in sorted(PROHIBITED_SEMANTIC_TERMS):
        if term in combined:
            problems.append(f"presentation fixtures contain toolkit type {term}")

    if problems:
        for problem in problems:
            print(f"facman-presentation-check: {problem}", file=sys.stderr)
        return 1
    print("facman-presentation-check: ok (5 deterministic C1 states)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
