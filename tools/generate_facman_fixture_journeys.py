# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Generate deterministic fixture-only FacMan C1 journey transcripts."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import generate_presentation_fixtures

FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "presentation" / "journeys"
JOURNEY_ORDER = ("positive", "stale-readiness", "interrupted-recovery")


def _activity_operation(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    operations = snapshot["pages"]["activity"]["operations"]
    return operations[0] if operations else None


def _replace_identity(
    snapshot: dict[str, Any],
    *,
    operation_id: str,
    snapshot_id: str,
    revision: int,
    generated_at: str,
) -> dict[str, Any]:
    result = copy.deepcopy(snapshot)
    old_operation_id = "operation.fixture-play-001"

    def replace(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "operation_id" and child == old_operation_id:
                    value[key] = operation_id
                else:
                    replace(child)
        elif isinstance(value, list):
            for child in value:
                replace(child)

    replace(result)
    result.update(
        snapshot_id=snapshot_id,
        revision=revision,
        generated_at=generated_at,
    )
    return result


def _ready_after_rescan() -> dict[str, Any]:
    snapshot = copy.deepcopy(generate_presentation_fixtures.base_snapshot())
    snapshot.update(
        snapshot_id="shell.rescanned",
        revision=15,
        generated_at="2026-08-01T12:07:00Z",
    )
    readiness = snapshot["selected_instance"]["readiness"]
    readiness.update(
        revision=8,
        checked_at="2026-08-01T12:07:00Z",
        evidence_digest="c" * 64,
        summary="Readiness revision 8 is current after the deterministic rescan.",
    )
    snapshot["launch_deck"]["status_text"] = "Ready after rescan"
    return snapshot


def _ready_after_recovery() -> dict[str, Any]:
    snapshot = copy.deepcopy(generate_presentation_fixtures.base_snapshot())
    snapshot.update(
        snapshot_id="shell.recovered",
        revision=16,
        generated_at="2026-08-01T12:08:00Z",
    )
    readiness = snapshot["selected_instance"]["readiness"]
    readiness.update(
        revision=9,
        checked_at="2026-08-01T12:08:00Z",
        evidence_digest="d" * 64,
        summary="Recovery is complete; fresh fixture readiness is required for relaunch.",
    )
    snapshot["launch_deck"]["status_text"] = "Recovered; ready for fixture relaunch"
    return snapshot


def presentation_frames() -> dict[str, dict[str, Any]]:
    canonical = generate_presentation_fixtures.snapshots()
    operation_id = "operation.fixture-play-002"
    return {
        **canonical,
        "rescanned": _ready_after_rescan(),
        "recovered": _ready_after_recovery(),
        "relaunched": _replace_identity(
            canonical["running"],
            operation_id=operation_id,
            snapshot_id="shell.relaunched",
            revision=17,
            generated_at="2026-08-01T12:09:00Z",
        ),
        "relaunched-exited": _replace_identity(
            canonical["exited"],
            operation_id=operation_id,
            snapshot_id="shell.relaunched-exited",
            revision=18,
            generated_at="2026-08-01T12:12:00Z",
        ),
    }


def _step(
    index: int,
    event: str,
    snapshot: dict[str, Any],
    fixture_process_starts: int,
    assertion: str,
    *,
    client_outcome: str,
) -> dict[str, Any]:
    selected = snapshot["selected_instance"]
    readiness = selected["readiness"]
    deck = snapshot["launch_deck"]
    operation = _activity_operation(snapshot)
    refusal = snapshot.get("refusal")
    last_run = selected.get("last_run")
    recovery = snapshot["recovery"]
    return {
        "index": index,
        "event": event,
        "presentation_state": snapshot["fixture_state"],
        "snapshot_id": snapshot["snapshot_id"],
        "snapshot_revision": snapshot["revision"],
        "selected_instance_id": selected["instance_id"],
        "readiness_state": readiness["state"],
        "readiness_revision": readiness["revision"],
        "play_availability": deck["primary_action"]["availability"],
        "play_effects": deck["primary_action"]["effects"],
        "refusal_code": refusal["code"] if refusal else None,
        "operation_id": operation["operation_id"] if operation else None,
        "operation_status": operation["status"] if operation else None,
        "last_run_outcome": last_run["outcome"] if last_run else None,
        "recovery_state": recovery["state"],
        "recovery_id": recovery["recovery_id"],
        "fixture_process_starts": fixture_process_starts,
        "live_process_starts": 0,
        "ordinary_cancellation_observed": False,
        "client_outcome": client_outcome,
        "assertion": assertion,
    }


def _record(
    journey_id: str,
    evidence_id: str,
    claims: list[str],
    definitions: list[tuple[str, dict[str, Any], int, str, str]],
    *,
    structured_refusal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    steps = [
        _step(
            index,
            event,
            snapshot,
            fixture_starts,
            assertion,
            client_outcome=client_outcome,
        )
        for index, (event, snapshot, fixture_starts, client_outcome, assertion) in enumerate(
            definitions, start=1
        )
    ]
    return {
        "schema": "facman.fixture_journey.v0",
        "journey_id": journey_id,
        "evidence_id": evidence_id,
        "authority_scope": "fixture_only",
        "transport": "bounded_process_rpc",
        "claims": claims,
        "structured_refusal": structured_refusal,
        "steps": steps,
        "fixture_process_starts": steps[-1]["fixture_process_starts"],
        "live_process_starts": 0,
        "ordinary_cancellation_observed": False,
    }


def journeys() -> dict[str, dict[str, Any]]:
    frame = presentation_frames()
    positive = _record(
        "J01-P",
        "J01-FIXTURE-POSITIVE-01",
        ["FACMAN-CLAIM-001", "FACMAN-CLAIM-002", "FACMAN-CLAIM-003"],
        [
            ("instance.select_or_create", frame["positive"], 0, "not_started", "The selected instance and Create action are both present."),
            ("readiness.show", frame["positive"], 0, "not_started", "Current readiness is visible before Play."),
            ("play.invoke_fixture", frame["running"], 1, "running", "Fixture-only Play starts a backend-owned operation."),
            ("frontend.close", frame["running"], 1, "running", "Closing the frontend leaves the backend operation running."),
            ("frontend.reconnect", frame["running"], 1, "running", "Reconnect observes the same operation identity."),
            ("process.exit", frame["exited"], 1, "exited", "The backend records an ordinary zero exit."),
            ("last_run.show", frame["exited"], 1, "exited", "Last run and relaunch are visible together."),
            ("relaunch.invoke_fixture", frame["relaunched"], 2, "running", "Relaunch creates a fresh backend operation."),
            ("process.exit", frame["relaunched-exited"], 2, "exited", "The relaunched fixture records its own exit."),
        ],
    )
    refusal = copy.deepcopy(frame["refused"]["refusal"])
    stale = _record(
        "J01-F",
        "J01-FIXTURE-STALE-01",
        ["FACMAN-CLAIM-001", "FACMAN-CLAIM-010"],
        [
            ("instance.select_or_create", frame["positive"], 0, "not_started", "The same selected instance is retained."),
            ("readiness.show", frame["positive"], 0, "not_started", "Readiness revision 7 is initially current."),
            ("dependency.change", frame["refused"], 0, "not_started", "Dependency drift invalidates the observed readiness."),
            ("play.refused", frame["refused"], 0, "refused", "The exact structured refusal is returned before any process start."),
            ("readiness.rescan", frame["rescanned"], 0, "not_started", "A read-only rescan advances readiness without auto-launching."),
        ],
        structured_refusal=refusal,
    )
    interrupted = _record(
        "J01-I",
        "J01-FIXTURE-INTERRUPTED-01",
        ["FACMAN-CLAIM-004", "FACMAN-CLAIM-005"],
        [
            ("instance.select_or_create", frame["positive"], 0, "not_started", "The fixture journey starts from the selected ready instance."),
            ("play.invoke_fixture", frame["running"], 1, "running", "The backend owns the active fixture operation."),
            ("frontend.close", frame["running"], 1, "running", "Frontend closure does not cancel or complete the operation."),
            ("rpc.response_lost", frame["running"], 1, "outcome_unknown", "Response loss is reported as outcome_unknown and is not retried."),
            ("frontend.restart", frame["interrupted"], 1, "interrupted", "Restart presents the exact interrupted operation and recovery record."),
            ("recovery.inspect", frame["interrupted"], 1, "interrupted", "Inspection remains bound to the interrupted operation."),
            ("recovery.apply", frame["recovered"], 1, "not_started", "Recovery clears the record without auto-launching."),
            ("relaunch.invoke_fixture", frame["relaunched"], 2, "running", "Fresh readiness creates a distinct relaunch operation."),
            ("process.exit", frame["relaunched-exited"], 2, "exited", "The recovered relaunch reaches an ordinary exit."),
        ],
    )
    return {
        "positive": positive,
        "stale-readiness": stale,
        "interrupted-recovery": interrupted,
    }


def encode(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def render_fixtures() -> dict[Path, str]:
    records = journeys()
    rendered = {
        FIXTURE_ROOT / f"{name}.facman.fixture-journey.v0.json": encode(records[name])
        for name in JOURNEY_ORDER
    }
    manifest = {
        "schema": "facman.fixture_journey_manifest.v0",
        "journeys": [
            {
                "name": name,
                "evidence_id": records[name]["evidence_id"],
                "path": f"tests/fixtures/presentation/journeys/{name}.facman.fixture-journey.v0.json",
                "sha256": hashlib.sha256(
                    rendered[FIXTURE_ROOT / f"{name}.facman.fixture-journey.v0.json"].encode("utf-8")
                ).hexdigest(),
            }
            for name in JOURNEY_ORDER
        ],
    }
    rendered[FIXTURE_ROOT / "manifest.v0.json"] = encode(manifest)
    return rendered


def main() -> int:
    for path, content in render_fixtures().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"facman-fixture-journeys: wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
