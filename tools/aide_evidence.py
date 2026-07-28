# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
TASK_ID = re.compile(r"^[A-Z0-9][A-Z0-9._-]*$")


def task_roots(task_id: str) -> list[Path]:
    if not TASK_ID.fullmatch(task_id):
        raise ValueError(f"invalid AIDE task id: {task_id!r}")
    roots = [
        ROOT / ".aide" / "queue" / state / task_id
        for state in ("active", "next")
    ]
    history = ROOT / ".aide" / "history"
    if history.is_dir():
        roots.extend(
            candidate
            for candidate in history.glob(f"*/{task_id}")
            if candidate.is_dir()
        )
    return sorted({root.resolve() for root in roots if root.is_dir()})


def resolve_task_file(task_id: str, relative: str) -> Path | None:
    normalized = PurePosixPath(relative)
    if normalized.is_absolute() or ".." in normalized.parts:
        raise ValueError(f"invalid task-relative evidence path: {relative!r}")
    matches = [
        root.joinpath(*normalized.parts)
        for root in task_roots(task_id)
        if root.joinpath(*normalized.parts).is_file()
    ]
    if len(matches) > 1:
        rendered = ", ".join(str(path.relative_to(ROOT)) for path in matches)
        raise ValueError(f"ambiguous AIDE task evidence for {task_id}: {rendered}")
    return matches[0] if matches else None
