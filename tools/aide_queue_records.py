# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Canonical reader and projection for mutable AIDE queue records."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

QUEUE_LANES = ("active", "next")
VALID_LIFECYCLE_STATES = frozenset(
    {
        # Current vocabulary.
        "planned",
        "ready",
        "active_automated",
        "awaiting_operator",
        "blocked_defect",
        "blocked_external",
        "verified_pending_closeout",
        "closed",
        "superseded",
        "archived",
        # Legacy records remain readable until their reviewed closeout.
        "active",
        "implemented",
        "verified",
        "reviewed",
        "blocked",
    }
)


class QueueRecordError(ValueError):
    """Raised when the mutable queue is not one deterministic record set."""


@dataclass(frozen=True)
class QueueRecord:
    id: str
    queue: str
    status: str
    lifecycle_state: str
    planning_state: str
    title: str
    root: Path


def yaml_field(path: Path, name: str) -> str:
    match = re.search(
        rf"(?m)^{re.escape(name)}:\s*(.*?)\s*$",
        path.read_text(encoding="utf-8"),
    )
    return match.group(1).strip("\"'") if match else ""


def mutable_record_paths(lane: Path) -> list[Path]:
    if not lane.is_dir():
        return []
    records: list[Path] = []
    for path in sorted(candidate for candidate in lane.iterdir() if candidate.is_dir()):
        task_path = path / "task.yaml"
        status_path = path / "status.yaml"
        task_exists = task_path.is_file()
        status_exists = status_path.is_file()
        if not task_exists and not status_exists:
            if any(path.iterdir()):
                raise QueueRecordError(
                    f"nonempty queue directory is not a task record: {path.name}"
                )
            continue
        if task_exists != status_exists:
            raise QueueRecordError(f"incomplete mutable queue record: {path.name}")
        records.append(path)
    return records


def read_queue_records(queue_root: Path) -> list[QueueRecord]:
    records: list[QueueRecord] = []
    seen: dict[str, Path] = {}
    for lane in QUEUE_LANES:
        for root in mutable_record_paths(queue_root / lane):
            task_path = root / "task.yaml"
            status_path = root / "status.yaml"
            task_id = yaml_field(task_path, "id")
            status_task_id = yaml_field(status_path, "task_id")
            if not task_id or task_id != root.name:
                raise QueueRecordError(
                    f"task id does not match queue directory: {root.name}"
                )
            if status_task_id != task_id:
                raise QueueRecordError(
                    f"status task id does not match task record: {root.name}"
                )
            if task_id in seen:
                raise QueueRecordError(
                    f"duplicate mutable queue task id: {task_id}"
                )
            seen[task_id] = root
            lifecycle_state = yaml_field(status_path, "lifecycle_state")
            if lifecycle_state not in VALID_LIFECYCLE_STATES:
                raise QueueRecordError(
                    f"invalid lifecycle state for {task_id}: "
                    f"{lifecycle_state or '<missing>'}"
                )
            status = yaml_field(status_path, "status")
            if not status:
                raise QueueRecordError(f"missing status for {task_id}")
            if yaml_field(task_path, "lifecycle_state") != lifecycle_state:
                raise QueueRecordError(
                    f"task/status lifecycle disagreement for {task_id}"
                )
            if yaml_field(task_path, "status") != status:
                raise QueueRecordError(
                    f"task/status state disagreement for {task_id}"
                )
            records.append(
                QueueRecord(
                    id=task_id,
                    queue=lane,
                    status=status,
                    lifecycle_state=lifecycle_state,
                    planning_state=yaml_field(status_path, "planning_state"),
                    title=yaml_field(task_path, "title"),
                    root=root,
                )
            )
    return records


def render_queue_index(queue_root: Path, records: list[QueueRecord]) -> str:
    repo_root = queue_root.parent.parent
    lines = [
        "schema_version: aide.queue-index.v1",
        "profile: .aide/profile.yaml",
        "canonical_source: .aide/queue/{active,next}",
        "default_concurrency: 1",
        "items:",
    ]
    if not records:
        lines.append("  []")
    for record in records:
        task = (record.root / "task.yaml").relative_to(repo_root).as_posix()
        evidence = (record.root / "evidence").relative_to(repo_root).as_posix()
        lines.extend(
            [
                f"  - id: {record.id}",
                f"    status: {record.status}",
                f"    lifecycle_state: {record.lifecycle_state}",
                f"    title: {record.title}",
                f"    task: {task}",
                f"    evidence: {evidence}",
            ]
        )
    return "\n".join(lines) + "\n"


def validate_queue_index(queue_root: Path, records: list[QueueRecord]) -> list[str]:
    index_path = queue_root / "index.yaml"
    if not index_path.is_file():
        return ["queue index is missing"]
    expected = render_queue_index(queue_root, records)
    if index_path.read_text(encoding="utf-8") != expected:
        return ["queue index disagrees with complete mutable task records"]
    return []
