# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate canonical in-flight queue membership, capacity, and primary selection."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from tools import aide_queue_records

PLAN_ACTIVE_STATES = {"active", "verified_pending_closeout"}
QUEUE_ACTIVE_STATES = {
    "active", "active_automated", "awaiting_operator",
    "verified_pending_closeout", "verified", "reviewed",
}


def load_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def plan_active_workunits(plan: dict[str, Any]) -> list[str]:
    active = [
        str(item["id"])
        for item in plan.get("workunit", [])
        if isinstance(item, dict) and item.get("status") in PLAN_ACTIVE_STATES
    ]
    gates = sum(item.get("status") == "active" for item in plan.get("gate", []))
    limit = plan.get("wip_limit", 1)
    if type(limit) is not int or limit < 1:
        raise ValueError("canonical plan WIP limit must be a positive integer")
    if len(active) + gates > limit:
        raise ValueError(
            "canonical plan exceeds its active WorkUnit WIP limit including gates: "
            f"{len(active) + gates} > {limit}"
        )
    return active


def programme_primary(plan: dict[str, Any], active: list[str]) -> str:
    programme = plan.get("execution_programme", {})
    if not isinstance(programme, dict):
        raise ValueError("execution_programme must be a table")
    declared = programme.get("primary_workunit", "")
    if not isinstance(declared, str) or (declared and declared not in active):
        raise ValueError("execution_programme.primary_workunit must name an active plan WorkUnit")
    if programme and len(active) > 1 and not declared:
        raise ValueError("concurrent programme work requires execution_programme.primary_workunit")
    return declared


def queue_state(root: Path) -> dict[str, Any]:
    records = [
        {
            "id": record.id,
            "queue": record.queue,
            "status": record.status,
            "lifecycle_state": record.lifecycle_state,
        }
        for record in aide_queue_records.read_queue_records(
            root / ".aide" / "queue"
        )
    ]
    counts: dict[str, int] = {}
    for record in records:
        state = record["lifecycle_state"] or "unknown"
        counts[state] = counts.get(state, 0) + 1
    current = [
        record["id"]
        for record in records
        if record["lifecycle_state"] in QUEUE_ACTIVE_STATES
    ]
    if any(record["queue"] != "active" for record in records
           if record["lifecycle_state"] in QUEUE_ACTIVE_STATES):
        raise aide_queue_records.QueueRecordError("active queue WorkUnits must be in the active lane")
    primary = ""
    plan_path = root / "release" / "index" / "plan.v1.toml"
    if plan_path.is_file():
        plan = load_toml(plan_path)
        plan_active = plan_active_workunits(plan)
        undeclared = set(current) - set(plan_active)
        if undeclared:
            raise aide_queue_records.QueueRecordError(
                "active queue WorkUnits are not active in the canonical plan: "
                + ", ".join(sorted(undeclared))
            )
        if plan.get("execution_programme") and set(current) != set(plan_active):
            raise aide_queue_records.QueueRecordError(
                "programme active queue membership differs from the canonical plan"
            )
        primary = programme_primary(plan, plan_active)
        if primary and primary not in current:
            raise aide_queue_records.QueueRecordError(
                "programme primary WorkUnit is not active in the AIDE queue"
            )
        if not primary and len(current) > 1:
            status_path = root / "release" / "index" / "project_status.v2.toml"
            if status_path.is_file():
                declared = load_toml(status_path).get("active_work_unit", "")
                if declared in current:
                    primary = declared
    if not primary and len(current) > 1:
        raise aide_queue_records.QueueRecordError(
            "concurrent active queue WorkUnits require an explicit primary: "
            + ", ".join(current)
        )
    archived = sum(
        1
        for checkpoint in (root / ".aide" / "history").iterdir()
        if checkpoint.is_dir()
        for task in checkpoint.iterdir()
        if task.is_dir()
    )
    return {
        "records": records,
        "counts": counts,
        "current": primary or (current[0] if current else None),
        "active_workunits": current,
        "archived_task_count": archived,
    }
