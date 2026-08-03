# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate the deterministic, fixture-only FacMan C1 vertical slice."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import facman_presentation_check, generate_facman_fixture_journeys

FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "presentation" / "journeys"
MANIFEST = FIXTURE_ROOT / "manifest.v0.json"
EXPECTED_EVENTS = {
    "J01-P": [
        "instance.select_or_create",
        "readiness.show",
        "play.invoke_fixture",
        "frontend.close",
        "frontend.reconnect",
        "process.exit",
        "last_run.show",
        "relaunch.invoke_fixture",
        "process.exit",
    ],
    "J01-F": [
        "instance.select_or_create",
        "readiness.show",
        "dependency.change",
        "play.refused",
        "readiness.rescan",
    ],
    "J01-I": [
        "instance.select_or_create",
        "play.invoke_fixture",
        "frontend.close",
        "rpc.response_lost",
        "frontend.restart",
        "recovery.inspect",
        "recovery.apply",
        "relaunch.invoke_fixture",
        "process.exit",
    ],
}


def _event(journey: dict[str, Any], name: str) -> dict[str, Any]:
    return next(step for step in journey["steps"] if step["event"] == name)


def _events(journey: dict[str, Any], name: str) -> list[dict[str, Any]]:
    return [step for step in journey["steps"] if step["event"] == name]


def validate_journey(journey: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    journey_id = journey.get("journey_id", "<missing>")
    steps = journey.get("steps", [])
    if journey.get("schema") != "facman.fixture_journey.v0":
        problems.append(f"{journey_id}: wrong schema identity")
    if journey.get("authority_scope") != "fixture_only":
        problems.append(f"{journey_id}: authority must remain fixture_only")
    if journey.get("transport") != "bounded_process_rpc":
        problems.append(f"{journey_id}: bounded process RPC must remain unchanged")
    if [step.get("event") for step in steps] != EXPECTED_EVENTS.get(journey_id):
        problems.append(f"{journey_id}: event sequence is incomplete or out of order")
    if [step.get("index") for step in steps] != list(range(1, len(steps) + 1)):
        problems.append(f"{journey_id}: step indexes must be contiguous")

    start_counts = [step.get("fixture_process_starts") for step in steps]
    if not all(isinstance(count, int) for count in start_counts):
        problems.append(f"{journey_id}: fixture process counts must be integers")
    elif start_counts != sorted(start_counts):
        problems.append(f"{journey_id}: fixture process counts must be monotonic")
    if any(step.get("live_process_starts") != 0 for step in steps):
        problems.append(f"{journey_id}: live process execution is forbidden")
    if journey.get("live_process_starts") != 0:
        problems.append(f"{journey_id}: journey reports live process execution")
    if journey.get("ordinary_cancellation_observed") is not False or any(
        step.get("ordinary_cancellation_observed") is not False for step in steps
    ):
        problems.append(f"{journey_id}: interruption cannot become ordinary cancellation")

    if journey_id == "J01-P":
        first_run, relaunch = _event(journey, "play.invoke_fixture"), _event(
            journey, "relaunch.invoke_fixture"
        )
        closed, reconnected = _event(journey, "frontend.close"), _event(
            journey, "frontend.reconnect"
        )
        exits = _events(journey, "process.exit")
        if first_run.get("operation_status") != "running" or first_run.get(
            "fixture_process_starts"
        ) != 1:
            problems.append("J01-P: first fixture Play must enter running")
        if closed.get("operation_id") != first_run.get("operation_id") or closed.get(
            "operation_status"
        ) != "running":
            problems.append("J01-P: frontend close must leave the operation running")
        if reconnected.get("operation_id") != first_run.get("operation_id"):
            problems.append("J01-P: reconnect must observe the same operation")
        if len(exits) != 2 or any(step.get("last_run_outcome") != "exited" for step in exits):
            problems.append("J01-P: initial and relaunched processes must record exit")
        if relaunch.get("operation_id") == first_run.get("operation_id") or relaunch.get(
            "fixture_process_starts"
        ) != 2:
            problems.append("J01-P: relaunch must create a distinct second operation")
    elif journey_id == "J01-F":
        refusal = journey.get("structured_refusal")
        play = _event(journey, "play.refused")
        rescan = _event(journey, "readiness.rescan")
        if refusal != generate_facman_fixture_journeys.presentation_frames()["refused"]["refusal"]:
            problems.append("J01-F: structured refusal differs from the presentation fixture")
        if not isinstance(refusal, dict) or refusal.get("code") != "stale_readiness":
            problems.append("J01-F: exact stale_readiness refusal is required")
        elif refusal.get("current_readiness_revision", 0) <= refusal.get(
            "observed_readiness_revision", 0
        ):
            problems.append("J01-F: refusal must identify a newer readiness revision")
        if play.get("play_availability") != "refused" or play.get(
            "refusal_code"
        ) != "stale_readiness":
            problems.append("J01-F: unavailable Play must expose the exact refusal")
        if any(count != 0 for count in start_counts) or journey.get(
            "fixture_process_starts"
        ) != 0:
            problems.append("J01-F: refused Play must never start a fixture process")
        if rescan.get("readiness_state") != "ready" or rescan.get(
            "readiness_revision"
        ) != refusal.get("current_readiness_revision"):
            problems.append("J01-F: rescan must publish the new current readiness")
    elif journey_id == "J01-I":
        running = _event(journey, "play.invoke_fixture")
        closed = _event(journey, "frontend.close")
        unknown = _event(journey, "rpc.response_lost")
        restarted = _event(journey, "frontend.restart")
        inspected = _event(journey, "recovery.inspect")
        recovered = _event(journey, "recovery.apply")
        relaunched = _event(journey, "relaunch.invoke_fixture")
        if closed.get("operation_id") != running.get("operation_id") or closed.get(
            "operation_status"
        ) != "running":
            problems.append("J01-I: frontend closure must preserve the running operation")
        if unknown.get("client_outcome") != "outcome_unknown" or unknown.get(
            "fixture_process_starts"
        ) != 1:
            problems.append("J01-I: response loss must be outcome_unknown without retry")
        if restarted.get("operation_status") != "interrupted" or restarted.get(
            "recovery_state"
        ) != "required":
            problems.append("J01-I: restart must show interrupted recovery truth")
        if inspected.get("operation_id") != restarted.get("operation_id") or inspected.get(
            "recovery_id"
        ) != restarted.get("recovery_id"):
            problems.append("J01-I: recovery inspection must retain exact identities")
        if recovered.get("recovery_state") != "clear" or recovered.get(
            "fixture_process_starts"
        ) != 1:
            problems.append("J01-I: recovery must clear without auto-launching")
        if relaunched.get("operation_status") != "running" or relaunched.get(
            "operation_id"
        ) == running.get("operation_id"):
            problems.append("J01-I: fresh relaunch must create a distinct running operation")
    return problems


def validate_presentation_frames() -> list[str]:
    problems: list[str] = []
    for name, snapshot in generate_facman_fixture_journeys.presentation_frames().items():
        state = snapshot["fixture_state"]
        for problem in facman_presentation_check.validate_snapshot(snapshot, state):
            problems.append(f"frame {name}: {problem}")
        if facman_presentation_check.jsonschema is not None:
            schema = facman_presentation_check.load_json(facman_presentation_check.SCHEMA)
            validator = facman_presentation_check.jsonschema.validators.validator_for(schema)(schema)
            for error in validator.iter_errors(snapshot):
                location = ".".join(str(part) for part in error.absolute_path) or "$"
                problems.append(f"frame {name}: schema rejection at {location}: {error.message}")
    return problems


def validate_generated_files() -> list[str]:
    problems: list[str] = []
    rendered = generate_facman_fixture_journeys.render_fixtures()
    for path, expected in rendered.items():
        if not path.is_file():
            problems.append(f"missing generated journey {path.relative_to(ROOT)}")
        elif path.read_text(encoding="utf-8") != expected:
            problems.append(f"stale generated journey {path.relative_to(ROOT)}")
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return problems + [f"journey manifest: {exc}"]
    if manifest.get("schema") != "facman.fixture_journey_manifest.v0":
        problems.append("journey manifest schema identity is invalid")
    entries = manifest.get("journeys", [])
    if [entry.get("name") for entry in entries] != list(
        generate_facman_fixture_journeys.JOURNEY_ORDER
    ):
        problems.append("journey manifest order is invalid")
    for entry in entries:
        relative = entry.get("path", "")
        path = ROOT / relative
        if not path.is_file() or ROOT not in path.resolve().parents:
            problems.append(f"journey manifest path is missing or unsafe: {relative}")
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry.get("sha256"):
            problems.append(f"journey digest mismatch: {relative}")
    return problems


def main() -> int:
    problems = validate_generated_files()
    problems.extend(validate_presentation_frames())
    records = generate_facman_fixture_journeys.journeys()
    for name in generate_facman_fixture_journeys.JOURNEY_ORDER:
        problems.extend(validate_journey(records[name]))
    if problems:
        for problem in problems:
            print(f"facman-fixture-journey-check: {problem}", file=sys.stderr)
        return 1
    step_count = sum(len(record["steps"]) for record in records.values())
    print(f"facman-fixture-journey-check: ok (3 journeys, {step_count} steps)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
