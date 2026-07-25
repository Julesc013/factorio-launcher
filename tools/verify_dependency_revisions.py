#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.validators.release import _common

TOOL = "verify-dependency-revisions"
DEFAULT_LOCK = ROOT / "release" / "index" / "workspace_lock.v1.toml"
ENV_BY_COMPONENT = {
    "universal_launcher": "FLAUNCH_UNIVERSAL_LAUNCHER_ROOT",
    "universal_setup": "FLAUNCH_UNIVERSAL_SETUP_ROOT",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify or align pinned dependency revisions.")
    parser.add_argument(
        "--lock",
        default=str(DEFAULT_LOCK),
        help="Path to a workspace lock file.",
    )
    parser.add_argument(
        "--align",
        action="store_true",
        help="Align dependency paths to locked commits before verifying.",
    )
    args = parser.parse_args(argv)
    problems = verify(Path(args.lock), align=args.align)
    if problems:
        for problem in problems:
            print(f"{TOOL}: {problem}")
        return 1
    print(f"{TOOL}: ok")
    return 0


def verify(
    lock_path: Path = DEFAULT_LOCK,
    *,
    align: bool = False,
    repository_paths: dict[str, Path] | None = None,
) -> list[str]:
    if not lock_path.is_file():
        return [f"missing lock file {lock_path}"]
    try:
        lock = _common.load_toml(lock_path)
    except OSError as exc:
        return [str(exc)]
    problems: list[str] = []
    for component in components(lock):
        if component["id"] in {"factorio_binding"}:
            continue
        path = resolve_repo_path(component, repository_paths)
        if path is None:
            problems.append(f"{lock_path}: missing repository path {component['path']}")
            continue
        if not path.exists():
            problems.append(f"{lock_path}: missing repository path {component['path']}")
            continue
        if align:
            if run_git(["checkout", component["pin"]], path) != 0:
                problems.append(f"{lock_path}: failed to align {component['id']} to {component['pin']}")
                continue
        head = git_output(["rev-parse", "HEAD"], path)
        if head == "unknown":
            problems.append(f"{lock_path}: not a git repo at {path}")
            continue
        if head != component["pin"]:
            problems.append(
                f"{lock_path}: dependency {component['id']} at {path} has {head}, expected {component['pin']}"
            )
    return problems


def resolve_repo_path(
    component: dict[str, Any],
    repository_paths: dict[str, Path] | None = None,
) -> Path | None:
    explicit = component.get("path", "").strip()
    source = component.get("source", "").strip()
    candidates = []
    component_id = str(component.get("id", ""))
    if repository_paths and component_id in repository_paths:
        candidates.append(repository_paths[component_id])
    environment = ENV_BY_COMPONENT.get(component_id)
    if environment and os.environ.get(environment):
        candidates.append(Path(os.environ[environment]))
    universal_root = os.environ.get("FLAUNCH_UNIVERSAL_ROOT")
    if universal_root and source:
        candidates.append(Path(universal_root) / source)
    workspace_root = os.environ.get("FLAUNCH_WORKSPACE_ROOT")
    if workspace_root and source:
        candidates.append(Path(workspace_root) / "Universal" / source)
        candidates.append(Path(workspace_root) / source)
    if explicit:
        candidate = Path(explicit)
        candidates.append(candidate if candidate.is_absolute() else ROOT / candidate)
        candidates.append((ROOT.parent / explicit.strip("/\\")).resolve())
    if source:
        candidates.extend(
            [
                (ROOT.parent / source).resolve(),
                (ROOT.parent / "Universal" / source).resolve(),
                (ROOT.parent.parent / "Universal" / source).resolve(),
            ]
        )
    for candidate in candidates:
        if (candidate / ".git").exists():
            return candidate.resolve()
    return None


def components(lock: dict[str, Any]) -> list[dict[str, str]]:
    raw = lock.get("component")
    if not isinstance(raw, list):
        return []
    result = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        component = {
            "id": str(item.get("id", "")).strip(),
            "pin": str(item.get("pin", "")).strip(),
            "path": str(item.get("path", "")).strip(),
            "source": str(item.get("source", "")).strip(),
        }
        if component["id"] and component["pin"] and component["path"]:
            result.append(component)
    return result


def run_git(args: list[str], cwd: Path) -> int:
    return subprocess.run(["git", *args], cwd=cwd, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode


def git_output(args: list[str], cwd: Path) -> str:
    completed = subprocess.run(["git", *args], cwd=cwd, check=False, text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if completed.returncode != 0:
        return "unknown"
    return completed.stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
