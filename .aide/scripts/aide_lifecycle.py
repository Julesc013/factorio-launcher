"""Target-local mutable task lifecycle for the portable AIDE Lite CLI.

The imported AIDE pack remains provider/network free. This module mutates only
target-owned queue and history records and refuses to edit archived tasks.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

STATES = ("planned", "active", "implemented", "verified", "reviewed", "closed", "archived", "blocked")
TRANSITIONS = {
    "start": ({"planned"}, "active"),
    "verify": ({"active", "implemented"}, "verified"),
    "review": ({"verified"}, "reviewed"),
    "close": ({"reviewed"}, "closed"),
    "block": ({"planned", "active", "implemented", "verified", "reviewed"}, "blocked"),
}
TASK_ID = re.compile(r"^[A-Z0-9][A-Z0-9._-]{2,127}$")


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def field(text: str, name: str) -> str:
    match = re.search(rf"(?m)^{re.escape(name)}:\s*(.+?)\s*$", text)
    return match.group(1).strip().strip('"') if match else ""


def set_field(text: str, name: str, value: str) -> str:
    line = f"{name}: {value}"
    pattern = re.compile(rf"(?m)^{re.escape(name)}:\s*.*$")
    if pattern.search(text):
        return pattern.sub(line, text, count=1)
    return text.rstrip() + "\n" + line + "\n"


def task_locations(root: Path, task_id: str) -> list[Path]:
    queue = root / ".aide" / "queue"
    return [queue / "active" / task_id, queue / "next" / task_id, queue / task_id]


def locate_mutable(root: Path, task_id: str) -> Path:
    for path in task_locations(root, task_id):
        if path.is_dir():
            return path
    archived = list((root / ".aide" / "history").glob(f"*/{task_id}"))
    if archived:
        raise ValueError(f"archived task is immutable: {task_id}")
    raise ValueError(f"unknown task: {task_id}")


def state_for(path: Path) -> str:
    status_path = path / "status.yaml"
    text = status_path.read_text(encoding="utf-8")
    explicit = field(text, "lifecycle_state")
    if explicit in STATES:
        return explicit
    planning = field(text, "planning_state")
    status = field(text, "status")
    if planning == "closed" or status == "passed":
        return "closed"
    if status in {"active", "running"}:
        return "active"
    if status in {"blocked", "failed"}:
        return "blocked"
    return "planned"


def impact_for(root: Path, allowed_paths: list[str]) -> dict[str, list[str]]:
    contract = json.loads((root / "contracts" / "policy" / "test_impact.v1.json").read_text(encoding="utf-8"))
    result = {"native_targets": [], "python_tests": [], "strict_validators": [], "package_profiles": []}
    for module in contract["modules"]:
        if not any(
            path.rstrip("/").startswith(prefix.rstrip("/")) or prefix.rstrip("/").startswith(path.rstrip("/"))
            for path in allowed_paths for prefix in module["paths"]
        ):
            continue
        for key in result:
            result[key].extend(module[key])
    return {key: sorted(set(values)) for key, values in result.items()}


def yaml_list(name: str, values: list[str]) -> list[str]:
    lines = [f"{name}:"]
    lines.extend(f"  - {value}" for value in values)
    if not values:
        lines.append("  []")
    return lines


def create(root: Path, task_id: str, title: str, objective: str, allowed_paths: list[str]) -> Path:
    if not TASK_ID.fullmatch(task_id):
        raise ValueError("task id must use uppercase letters, digits, dot, underscore, or dash")
    if any(path.exists() for path in task_locations(root, task_id)) or list((root / ".aide/history").glob(f"*/{task_id}")):
        raise ValueError(f"task already exists: {task_id}")
    if not allowed_paths:
        raise ValueError("at least one --path is required")
    allowed_paths = [path + "**" if path.endswith("/") else path for path in allowed_paths]
    destination = root / ".aide" / "queue" / "next" / task_id
    destination.mkdir(parents=True)
    (destination / "evidence").mkdir()
    impact = impact_for(root, allowed_paths)
    stamp = now()
    task_lines = [
        "schema_version: aide.queue-task.v1",
        f"id: {task_id}",
        f"title: {title}",
        "status: planned",
        "lifecycle_state: planned",
        "planning_state: planned",
        f"created_at: {stamp}",
        "owner: unassigned",
        "objective: >",
        f"  {objective}",
        *yaml_list("allowed_paths", allowed_paths),
        *yaml_list("forbidden_paths", [".git/**", ".aide.local/**", ".aide/history/**"]),
        *yaml_list("affected_native_targets", impact["native_targets"]),
        *yaml_list("affected_python_tests", impact["python_tests"]),
        *yaml_list("affected_strict_validators", impact["strict_validators"]),
        *yaml_list("affected_package_profiles", impact["package_profiles"]),
        *yaml_list("architecture_invariants", [
            "frontends depend on runtime/client, not backend implementations",
            "AIDE remains development-only and is excluded from product packages",
            "focused validation does not replace the full promotion matrix",
            "human acceptance remains an operator verdict",
        ]),
        *yaml_list("claim_ledger_rows", ["docs/quality/safety_claim_ledger.md"]),
        "commit_template: .aide/git/commit-template.md",
        *yaml_list("closeout_checklist", [
            "allowed path scope reconciled",
            "affected validation passed",
            "full promotion requirements recorded honestly",
            "claim ledger and project state reconciled",
            "structured commit check passed",
        ]),
        "",
    ]
    status_lines = [
        "schema_version: aide.queue-status.v1",
        f"task_id: {task_id}",
        "status: planned",
        "lifecycle_state: planned",
        "planning_state: planned",
        f"created_at: {stamp}",
        "result: PENDING",
        f"evidence_path: .aide/queue/next/{task_id}/evidence/",
        "",
    ]
    (destination / "task.yaml").write_text("\n".join(task_lines), encoding="utf-8")
    (destination / "status.yaml").write_text("\n".join(status_lines), encoding="utf-8")
    rebuild_queue_index(root)
    return destination


def transition(root: Path, task_id: str, action: str, *, result: str = "") -> str:
    path = locate_mutable(root, task_id)
    old = state_for(path)
    allowed, new = TRANSITIONS[action]
    if old not in allowed:
        raise ValueError(f"invalid lifecycle transition: {old} -> {new}")
    if action == "start" and path.parent.name == "next":
        target = root / ".aide" / "queue" / "active" / task_id
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise ValueError(f"active task already exists: {task_id}")
        shutil.move(str(path), str(target))
        path = target
    stamp = now()
    for filename in ("task.yaml", "status.yaml"):
        target = path / filename
        text = target.read_text(encoding="utf-8")
        text = set_field(text, "lifecycle_state", new)
        text = set_field(text, "status", "passed" if new == "closed" else new)
        text = set_field(text, "planning_state", "closed" if new == "closed" else new)
        text = set_field(text, f"{new}_at", stamp)
        if action == "verify":
            text = set_field(text, "implementation_state", "implemented")
            text = set_field(text, "result", result or "PASS")
        if action == "start" and filename == "status.yaml":
            text = set_field(
                text,
                "evidence_path",
                f".aide/queue/active/{task_id}/evidence/",
            )
        target.write_text(text, encoding="utf-8")
    rebuild_queue_index(root)
    return new


def hashes(path: Path) -> dict[str, str]:
    result = {}
    for file in sorted(candidate for candidate in path.rglob("*") if candidate.is_file()):
        result[file.relative_to(path).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    return result


def rebuild_history_index(root: Path, checkpoint: str) -> None:
    checkpoint_root = root / ".aide" / "history" / checkpoint
    records = []
    for task in sorted(path for path in checkpoint_root.iterdir() if path.is_dir()):
        records.append({"task_id": task.name, "files": hashes(task)})
    data = {
        "schema": "aide.history_index.v1",
        "checkpoint": checkpoint,
        "immutable_task_records": True,
        "tasks": records,
    }
    (checkpoint_root / "index.json").write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def archive(root: Path, task_id: str, checkpoint: str) -> Path:
    path = locate_mutable(root, task_id)
    if state_for(path) != "closed":
        raise ValueError("only closed tasks may be archived")
    for filename in ("task.yaml", "status.yaml"):
        target = path / filename
        text = target.read_text(encoding="utf-8")
        text = set_field(text, "lifecycle_state", "archived")
        text = set_field(text, "archived_at", now())
        if filename == "status.yaml":
            text = set_field(
                text,
                "evidence_path",
                f".aide/history/{checkpoint}/{task_id}/evidence/",
            )
        target.write_text(text, encoding="utf-8")
    destination = root / ".aide" / "history" / checkpoint / task_id
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ValueError(f"archive destination already exists: {destination}")
    shutil.move(str(path), str(destination))
    rebuild_history_index(root, checkpoint)
    rebuild_queue_index(root)
    return destination


def queue_record(path: Path, queue_root: Path) -> dict[str, str]:
    task = (path / "task.yaml").read_text(encoding="utf-8")
    status = (path / "status.yaml").read_text(encoding="utf-8")
    return {
        "id": field(task, "id") or path.name,
        "status": field(status, "status") or state_for(path),
        "lifecycle_state": state_for(path),
        "title": field(task, "title"),
        "task": (path / "task.yaml").relative_to(queue_root.parent.parent).as_posix(),
        "evidence": (path / "evidence").relative_to(queue_root.parent.parent).as_posix(),
    }


def rebuild_queue_index(root: Path) -> None:
    queue = root / ".aide" / "queue"
    for lane in ("active", "next"):
        (queue / lane).mkdir(parents=True, exist_ok=True)
    records = []
    for lane in ("active", "next"):
        records.extend(queue_record(path, queue) for path in sorted((queue / lane).iterdir()) if path.is_dir())
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
        lines.extend([
            f"  - id: {record['id']}",
            f"    status: {record['status']}",
            f"    lifecycle_state: {record['lifecycle_state']}",
            f"    title: {record['title']}",
            f"    task: {record['task']}",
            f"    evidence: {record['evidence']}",
        ])
    (queue / "index.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
