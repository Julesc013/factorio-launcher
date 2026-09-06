# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Deterministic backend-shaped inputs for the production-control gallery."""

from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATES = ("ready", "blocked", "busy", "recovery", "empty", "error")
SCOPES = ("launch_deck", "instances", "installations", "content", "saves", "activity_recovery", "settings_support")


def action(identifier: str, label: str, role: str = "primary", *, refused: bool = False) -> dict:
    return {
        "action_id": identifier, "command_id": "presentation.action",
        "label": label, "accessibility_label": label, "role": role,
        "availability": "refused" if refused else "available",
        "effects": ["local_write"], "confirmation": "explicit",
        "input_contract": "facman.semantic_action_input.v1", "input_fields": [],
        "backend_owned": True,
        "refusal": {"code": "gallery_blocked", "summary": "Action unavailable", "detail": "Fixture refusal"} if refused else None,
    }


def scenario(state: str, *, overflow: bool = False) -> dict:
    if state not in STATES:
        raise ValueError(f"Unknown gallery state: {state}")
    base = json.loads((ROOT / "tests/golden/commands/presentation.query.success.json").read_text(encoding="utf-8"))
    variant = "overflow" if overflow else "baseline"
    case = {
        "schema": "facman.control_gallery_case.v1", "state": state,
        "variant": variant, "observed_at": "2026-09-07T00:00:00Z",
        "snapshots": {}, "error": "Deterministic backend response unavailable.",
    }
    if state == "error":
        return case
    name = "Gallery Factory" if not overflow else "工場 e\u0301 🚂 — " + "Long identity " * 20
    selected = {} if state == "empty" else {
        "instance_id": "gallery-instance", "display_name": name,
        "installation_id": "gallery-install", "factorio_version": "2.0.0",
    }
    problem = {"code": "stale_readiness", "summary": "Readiness changed", "detail": "Rescan the selected instance before Play."}
    for scope in SCOPES:
        record = copy.deepcopy(base)
        record["snapshot_id"] = f"gallery-{state}-{scope}"
        record["revision"] = "1" * 64
        record["selected_context"] = selected
        record["page"] = {"scope": scope, "summary": f"{state}: {scope}", "items": []}
        record["last_run"] = {"authority_state": "no_record"}
        record["readiness"] = {
            "overall_state": "ready" if state == "ready" else state,
            "freshness": "current", "execution_available": state == "ready",
            "play_authority_state": "available" if state == "ready" else "unavailable",
            "readiness_digest": "2" * 64, "blockers": [problem] if state == "blocked" else [],
        }
        if state != "empty":
            if scope == "instances":
                record["page"]["items"] = [{"instance_id": "gallery-instance", "display_name": name, "selected": True}]
                if overflow:
                    record["page"]["items"] += [{"instance_id": f"gallery-{i}", "display_name": f"Other factory {i}"} for i in range(40)]
            if scope == "installations":
                record["page"]["items"] = [{"installation_id": "gallery-install", "ownership": "read_only", "version": "2.0.0", "root": "C:/Gallery/fixture-only"}]
            if scope == "launch_deck":
                record["available_semantic_actions"] = [
                    action("launch.play", "Play", refused=state != "ready"),
                    action("readiness.refresh", "Rescan readiness", "secondary"),
                ]
        if state == "blocked":
            record["specific_blockers"] = [problem]
        if state == "busy":
            record["active_operations"] = [{"operation_id": "gallery-operation", "session_id": "gallery-session", "target_instance_id": "gallery-instance", "state": "running", "authority_scope": "fixture_only"}]
        if state == "recovery":
            record["recovery"] = {"transactions": [{"transaction_id": "gallery-transaction", "operation_id": "gallery-operation", "state": "interrupted", "reason_code": "outcome_unknown"}]}
            if scope == "activity_recovery":
                record["available_semantic_actions"] = [action("recovery.apply_supported", "Recover operation", "recovery")]
        if scope == "settings_support":
            record["workspace_health"] = {"status": "uninitialized", "workspace": "", "workspace_id": "", "initialized": False}
            record["available_semantic_actions"] = [action("doctor.run", "Run Doctor", "diagnostic")]
        case["snapshots"][scope] = record
    return case


def cases() -> dict[str, dict]:
    result = {state: scenario(state) for state in STATES}
    result["ready-overflow"] = scenario("ready", overflow=True)
    return result
