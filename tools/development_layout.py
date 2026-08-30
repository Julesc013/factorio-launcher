# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

MARKER_NAME = ".facman-development-root.v1.json"
MARKER_SCHEMA = "facman.development_root.v1"
DEFAULT_RETENTION_DAYS = 7
DEFAULT_MAX_TASK_ROOTS = 8
DEFAULT_MAX_BYTES = 20 * 1024 * 1024 * 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def repository_key(source_root: Path) -> str:
    resolved = source_root.resolve()
    digest = hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:12]
    name = slug(resolved.name, fallback="repository", limit=32)
    return f"{name}-{digest}"


def current_task_id(source_root: Path) -> str:
    for name in ("FACMAN_TASK_ID", "FACMAN_WORK_ITEM"):
        configured = os.environ.get(name, "").strip()
        if configured:
            return configured
    completed = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=source_root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    branch = completed.stdout.strip()
    if branch:
        return branch
    completed = subprocess.run(
        ["git", "rev-parse", "--short=12", "HEAD"],
        cwd=source_root,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    revision = completed.stdout.strip() or "unknown"
    return f"detached-{revision}"


def slug(value: str, *, fallback: str = "local", limit: int = 64) -> str:
    normalized = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._").lower()
    normalized = normalized or fallback
    if len(normalized) <= limit:
        return normalized
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:10]
    return f"{normalized[: limit - 11]}-{digest}"


def development_base() -> Path:
    configured = os.environ.get("FACMAN_DEV_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
        if local_app_data:
            return (Path(local_app_data) / "FacMan" / "Development").resolve()
    cache = os.environ.get("XDG_CACHE_HOME", "").strip()
    base = Path(cache).expanduser() if cache else Path.home() / ".cache"
    return (base / "facman" / "development").resolve()


def repository_root(source_root: Path) -> Path:
    return development_base() / "repositories" / repository_key(source_root)


def task_root(source_root: Path, task_id: str | None = None) -> Path:
    identity = task_id or current_task_id(source_root)
    return repository_root(source_root) / "tasks" / slug(identity)


def default_task_root(source_root: Path, task_id: str | None = None) -> Path:
    configured = os.environ.get("FACMAN_TASK_ROOT", "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    return task_root(source_root, task_id)


def worktree_root(source_root: Path) -> Path:
    return repository_root(source_root) / "worktrees"


def ensure_task_root(path: Path, source_root: Path, task_id: str) -> Path:
    resolved = path.expanduser().resolve()
    source = source_root.resolve()
    if resolved == source or resolved.is_relative_to(source):
        raise ValueError(f"development task root must be outside source checkout: {resolved}")
    if source.is_relative_to(resolved):
        raise ValueError(f"development task root must not contain source checkout: {resolved}")
    if resolved.exists() and not resolved.is_dir():
        raise ValueError(f"development task root is not a directory: {resolved}")
    marker = resolved / MARKER_NAME
    if resolved.exists() and not marker.is_file() and any(resolved.iterdir()):
        raise ValueError(f"refusing unowned development task root with content: {resolved}")
    resolved.mkdir(parents=True, exist_ok=True)
    now = utc_now()
    expected = {
        "schema": MARKER_SCHEMA,
        "owner": "facman-development",
        "kind": "task-root",
        "repository_key": repository_key(source),
        "source_root": str(source),
        "task_id": task_id,
    }
    created_at = now
    if marker.is_file():
        try:
            current = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid development ownership marker {marker}: {exc}") from exc
        for key, value in expected.items():
            if current.get(key) != value:
                raise ValueError(f"development ownership marker mismatch for {key}: {marker}")
        created_at = str(current.get("created_at", now))
    payload = {**expected, "created_at": created_at, "last_used_at": now}
    marker.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return resolved


def read_marker(path: Path, source_root: Path | None = None) -> dict[str, object]:
    marker = path.resolve() / MARKER_NAME
    try:
        payload = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid development ownership marker {marker}: {exc}") from exc
    if payload.get("schema") != MARKER_SCHEMA or payload.get("owner") != "facman-development":
        raise ValueError(f"unrecognized development ownership marker: {marker}")
    if payload.get("kind") != "task-root":
        raise ValueError(f"development marker does not authorize task-root cleanup: {marker}")
    if source_root is not None:
        source = source_root.resolve()
        expected = {
            "repository_key": repository_key(source),
            "source_root": str(source),
        }
        for key, value in expected.items():
            if payload.get(key) != value:
                raise ValueError(f"development ownership marker mismatch for {key}: {marker}")
        task_id = payload.get("task_id")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError(f"development ownership marker has no task identity: {marker}")
        expected_path = task_root(source, task_id).resolve()
        if path.resolve() != expected_path:
            raise ValueError(f"development ownership marker path mismatch: {marker}")
    return payload
