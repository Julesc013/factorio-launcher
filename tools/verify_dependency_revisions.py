#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.validators.release import _common

TOOL = "verify-dependency-revisions"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify or align pinned dependency revisions.")
    parser.add_argument(
        "--lock",
        default=str(ROOT / "release" / "index" / "workspace_lock.v1.toml"),
        help="Path to a workspace lock file.",
    )
    parser.add_argument(
        "--align",
        action="store_true",
        help="Align dependency paths to locked commits before verifying.",
    )
    args = parser.parse_args(argv)
    lock_path = Path(args.lock)
    if not lock_path.is_file():
        print(f"{TOOL}: missing lock file {lock_path}")
        return 1
    try:
        lock = _common.load_toml(lock_path)
    except OSError as exc:
        print(f"{TOOL}: {exc}")
        return 1
    problems = []
    for component in components(lock):
        if component["id"] in {"factorio_binding"}:
            continue
        path = resolve_repo_path(component)
        if path is None:
            problems.append(f"{lock_path}: missing repository path {component['path']}")
            continue
        if not path.exists():
            problems.append(f"{lock_path}: missing repository path {component['path']}")
            continue
        if args.align:
            if run_git(["checkout", component["pin"]], path) != 0:
                problems.append(f"{lock_path}: failed to align {component['id']} to {component['pin']}")
        if run_git(["rev-parse", "HEAD"], path) != 0:
            problems.append(f"{lock_path}: not a git repo at {path}")
            continue
        head = git_output(["rev-parse", "HEAD"], path)
        if head != component["pin"]:
            problems.append(
                f"{lock_path}: dependency {component['id']} at {path} has {head}, expected {component['pin']}"
            )
    if problems:
        for problem in problems:
            print(f"{TOOL}: {problem}")
        return 1
    print(f"{TOOL}: ok")
    return 0


def resolve_repo_path(component: dict[str, Any]) -> Path | None:
    explicit = component.get("path", "").strip()
    source = component.get("source", "").strip()
    candidates = []
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
        if (candidate / ".git").is_dir():
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
