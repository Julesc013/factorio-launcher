# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Generate deterministic facman.presentation.v0 C1 semantic fixtures."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "presentation"
STATES = ("positive", "refused", "running", "exited", "interrupted")


def action(
    action_id: str,
    command_id: str | None,
    label: str,
    role: str = "secondary",
    *,
    availability: str = "available",
    effects: list[str] | None = None,
    confirmation: str = "none",
    backend_owned: bool = True,
    refusal: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "action_id": action_id,
        "command_id": command_id,
        "label": label,
        "accessibility_label": label,
        "role": role,
        "availability": availability,
        "effects": effects or ["read_only"],
        "confirmation": confirmation,
        "backend_owned": backend_owned,
        "refusal": refusal,
    }


def navigation() -> list[dict[str, str]]:
    return [
        {
            "page_id": "instances",
            "label": "Instances",
            "accessibility_label": "Instances page",
        },
        {
            "page_id": "installations",
            "label": "Installations",
            "accessibility_label": "Installations page",
        },
        {
            "page_id": "activity",
            "label": "Activity",
            "accessibility_label": "Activity page",
        },
        {
            "page_id": "settings_about",
            "label": "Settings / About",
            "accessibility_label": "Settings and About page",
        },
    ]


def clear_recovery() -> dict[str, Any]:
    return {
        "state": "clear",
        "recovery_id": None,
        "operation_id": None,
        "reason_code": None,
        "summary": "No recovery action is required.",
        "actions": [],
    }


def readiness_refresh_action() -> dict[str, Any]:
    return action(
        "instance.readiness.refresh",
        "instances.readiness",
        "Rescan readiness",
    )


def play_action() -> dict[str, Any]:
    return action(
        "instance.play",
        "run.execute",
        "Play",
        "primary",
        effects=["fixture_process"],
    )


def stale_refusal() -> dict[str, Any]:
    return {
        "code": "stale_readiness",
        "title": "Readiness changed",
        "detail": "Play was refused because readiness revision 7 is stale; rescan revision 8 before retrying.",
        "observed_readiness_revision": 7,
        "current_readiness_revision": 8,
        "actions": [readiness_refresh_action()],
    }


def base_snapshot() -> dict[str, Any]:
    create = action(
        "instance.create",
        "instances.create",
        "Create instance",
        effects=["local_write"],
        confirmation="explicit",
    )
    scan = action(
        "installation.scan",
        "installs.scan",
        "Scan for installations",
    )
    selected = {
        "instance_id": "instance.c1-vanilla",
        "name": "C1 Vanilla",
        "journey_state": "positive",
        "installation": {
            "installation_id": "installation.standalone-2.0.77",
            "label": "Factorio 2.0.77 standalone",
            "version": "2.0.77",
            "kind": "standalone",
        },
        "readiness": {
            "state": "ready",
            "revision": 7,
            "checked_at": "2026-08-01T12:00:00Z",
            "evidence_digest": "a" * 64,
            "summary": "Ready for the deterministic fixture Play journey.",
            "blockers": [],
        },
        "last_run": None,
        "operation_id": None,
        "recovery_id": None,
        "actions": [readiness_refresh_action()],
    }
    launch_deck = {
        "instance_id": selected["instance_id"],
        "instance_name": selected["name"],
        "journey_state": "positive",
        "status_text": "Ready",
        "primary_action": play_action(),
        "secondary_actions": [readiness_refresh_action()],
        "last_run": None,
        "operation_id": None,
        "refusal": None,
        "recovery_id": None,
    }
    return {
        "contract": "facman.presentation.v0",
        "snapshot_id": "shell.positive",
        "revision": 10,
        "generated_at": "2026-08-01T12:00:00Z",
        "fixture_state": "positive",
        "authority_scope": "fixture_only",
        "transport": {
            "mode": "bounded_process_rpc",
            "session_owner": "facman_backend",
            "journal_owner": "facman_backend",
            "frontend_disconnect": "operation_continues",
            "route_authority": "unchanged",
        },
        "navigation": navigation(),
        "active_page": "instances",
        "pages": {
            "instances": {
                "summary": "1 isolated vanilla instance",
                "items": [
                    {
                        "instance_id": selected["instance_id"],
                        "name": selected["name"],
                        "journey_state": "positive",
                        "selected": True,
                    }
                ],
                "actions": [create],
            },
            "installations": {
                "page_id": "installations",
                "title": "Installations",
                "summary": "1 existing standalone installation; FacMan will not repair or update it.",
                "state": "ready",
                "actions": [scan],
            },
            "activity": {
                "summary": "No active operations.",
                "operations": [],
                "actions": [],
            },
            "settings_about": {
                "page_id": "settings_about",
                "title": "Settings / About",
                "summary": "FacMan 0.1 C1; System Native or FacMan OEM+ appearance.",
                "state": "ready",
                "actions": [
                    action("product.inspect", "product.inspect", "Product details")
                ],
            },
        },
        "selected_instance": selected,
        "launch_deck": launch_deck,
        "refusal": None,
        "recovery": clear_recovery(),
    }


def refused_snapshot() -> dict[str, Any]:
    snapshot = copy.deepcopy(base_snapshot())
    refusal = stale_refusal()
    snapshot.update(
        snapshot_id="shell.refused",
        revision=11,
        generated_at="2026-08-01T12:01:00Z",
        fixture_state="refused",
        authority_scope="unavailable",
        refusal=refusal,
    )
    snapshot["selected_instance"]["journey_state"] = "refused"
    snapshot["selected_instance"]["readiness"] = {
        "state": "stale",
        "revision": 8,
        "checked_at": "2026-08-01T12:01:00Z",
        "evidence_digest": "b" * 64,
        "summary": "Readiness is stale and must be rescanned.",
        "blockers": [copy.deepcopy(refusal)],
    }
    refused_play = action(
        "instance.play",
        "run.execute",
        "Play",
        "primary",
        availability="refused",
        effects=["process_execution"],
        refusal=copy.deepcopy(refusal),
    )
    snapshot["launch_deck"].update(
        journey_state="refused",
        status_text="Play unavailable: readiness changed",
        primary_action=refused_play,
        refusal=copy.deepcopy(refusal),
    )
    snapshot["pages"]["instances"]["items"][0]["journey_state"] = "refused"
    return snapshot


def fixture_operation(status: str) -> dict[str, Any]:
    terminal = status != "running"
    interrupted = status == "interrupted"
    return {
        "operation_id": "operation.fixture-play-001",
        "kind": "fixture_play",
        "instance_id": "instance.c1-vanilla",
        "status": status,
        "phase": "supervise" if status == "running" else "finalize",
        "summary": {
            "running": "Fixture process is running under backend supervision.",
            "succeeded": "Fixture process exited normally.",
            "interrupted": "Frontend reconnected to an interrupted backend operation.",
        }[status],
        "started_at": "2026-08-01T12:02:00Z",
        "ended_at": "2026-08-01T12:06:00Z" if terminal else None,
        "progress": {
            "completed": 3 if terminal else 1,
            "total": 3,
            "unit": "steps",
        },
        "backend_operation_owner": "facman_backend",
        "frontend_disconnect": "observe_or_recover",
        "terminal_outcome": "interrupted" if interrupted else ("exited" if terminal else None),
        "recovery_id": "recovery.fixture-play-001" if interrupted else None,
    }


def running_snapshot() -> dict[str, Any]:
    snapshot = copy.deepcopy(base_snapshot())
    operation = fixture_operation("running")
    snapshot.update(
        snapshot_id="shell.running",
        revision=12,
        generated_at="2026-08-01T12:02:30Z",
        fixture_state="running",
    )
    snapshot["selected_instance"].update(
        journey_state="running",
        operation_id=operation["operation_id"],
    )
    snapshot["pages"]["instances"]["items"][0]["journey_state"] = "running"
    snapshot["pages"]["activity"] = {
        "summary": "1 operation is running.",
        "operations": [operation],
        "actions": [],
    }
    snapshot["launch_deck"].update(
        journey_state="running",
        status_text="Running under backend supervision",
        primary_action=action(
            "activity.show_operation",
            None,
            "Show in Activity",
            "manage",
            backend_owned=False,
        ),
        operation_id=operation["operation_id"],
    )
    return snapshot


def exited_snapshot() -> dict[str, Any]:
    snapshot = copy.deepcopy(base_snapshot())
    operation = fixture_operation("succeeded")
    last_run = {
        "operation_id": operation["operation_id"],
        "started_at": operation["started_at"],
        "ended_at": "2026-08-01T12:05:00Z",
        "outcome": "exited",
        "exit_code": 0,
    }
    operation["ended_at"] = last_run["ended_at"]
    snapshot.update(
        snapshot_id="shell.exited",
        revision=13,
        generated_at="2026-08-01T12:05:10Z",
        fixture_state="exited",
    )
    snapshot["selected_instance"].update(
        journey_state="exited",
        last_run=last_run,
    )
    snapshot["pages"]["instances"]["items"][0]["journey_state"] = "exited"
    snapshot["pages"]["activity"] = {
        "summary": "Last fixture operation exited normally.",
        "operations": [operation],
        "actions": [],
    }
    snapshot["launch_deck"].update(
        journey_state="exited",
        status_text="Last run exited normally; ready to relaunch",
        last_run=last_run,
    )
    return snapshot


def interrupted_snapshot() -> dict[str, Any]:
    snapshot = copy.deepcopy(base_snapshot())
    operation = fixture_operation("interrupted")
    recovery_actions = [
        action(
            "recovery.inspect",
            "workspace.recovery.inspect",
            "Inspect recovery",
            "recovery",
        ),
        action(
            "recovery.apply",
            "workspace.recovery.apply",
            "Recover operation",
            "recovery",
            effects=["local_write"],
            confirmation="explicit",
        ),
    ]
    recovery = {
        "state": "required",
        "recovery_id": operation["recovery_id"],
        "operation_id": operation["operation_id"],
        "reason_code": "operation.interrupted",
        "summary": "The backend operation ended without an ordinary completion record.",
        "actions": recovery_actions,
    }
    last_run = {
        "operation_id": operation["operation_id"],
        "started_at": operation["started_at"],
        "ended_at": operation["ended_at"],
        "outcome": "interrupted",
        "exit_code": None,
    }
    snapshot.update(
        snapshot_id="shell.interrupted",
        revision=14,
        generated_at="2026-08-01T12:06:10Z",
        fixture_state="interrupted",
        authority_scope="unavailable",
        recovery=recovery,
    )
    snapshot["selected_instance"].update(
        journey_state="interrupted",
        last_run=last_run,
        operation_id=operation["operation_id"],
        recovery_id=operation["recovery_id"],
        actions=recovery_actions,
    )
    snapshot["pages"]["instances"]["items"][0]["journey_state"] = "interrupted"
    snapshot["pages"]["activity"] = {
        "summary": "1 interrupted operation requires recovery.",
        "operations": [operation],
        "actions": recovery_actions,
    }
    snapshot["launch_deck"].update(
        journey_state="interrupted",
        status_text="Recovery required after interruption",
        primary_action=copy.deepcopy(recovery_actions[0]),
        secondary_actions=[copy.deepcopy(recovery_actions[1])],
        last_run=last_run,
        operation_id=operation["operation_id"],
        recovery_id=operation["recovery_id"],
    )
    return snapshot


def snapshots() -> dict[str, dict[str, Any]]:
    return {
        "positive": base_snapshot(),
        "refused": refused_snapshot(),
        "running": running_snapshot(),
        "exited": exited_snapshot(),
        "interrupted": interrupted_snapshot(),
    }


def encode(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def render_fixtures() -> dict[Path, str]:
    rendered = {
        FIXTURE_ROOT / f"{state}.facman.presentation.v0.json": encode(snapshot)
        for state, snapshot in snapshots().items()
    }
    manifest = {
        "schema": "facman.presentation_fixture_manifest.v0",
        "contract": "facman.presentation.v0",
        "states": [
            {
                "state": state,
                "path": f"tests/fixtures/presentation/{state}.facman.presentation.v0.json",
                "sha256": hashlib.sha256(
                    rendered[FIXTURE_ROOT / f"{state}.facman.presentation.v0.json"].encode("utf-8")
                ).hexdigest(),
            }
            for state in STATES
        ],
    }
    rendered[FIXTURE_ROOT / "manifest.v0.json"] = encode(manifest)
    return rendered


def main() -> int:
    for path, content in render_fixtures().items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
        print(f"presentation-fixtures: wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
