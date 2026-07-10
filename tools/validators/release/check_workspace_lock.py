from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.validators.release import _common

TOOL = "release-workspace-lock-check"

REQUIRED_COMPONENT_IDS = {"factorio_binding", "universal_launcher", "universal_setup"}
HASH_PATTERN = re.compile(r"^[0-9a-f]{40}$")


def main() -> int:
    try:
        problems = validate()
    except (OSError, ValueError) as exc:
        problems = [str(exc)]
    return _common.report(TOOL, problems)


def validate() -> list[str]:
    problems: list[str] = []
    workspace_lock_path = ROOT / "release" / "index" / "workspace_lock.v1.toml"
    workspace = _common.load_toml(workspace_lock_path)
    if workspace.get("schema") != "flaunch.workspace_lock.v1":
        problems.append(f"{relative(workspace_lock_path)}: wrong schema")
    components = _component_map(workspace.get("component"))
    for component_id in sorted(REQUIRED_COMPONENT_IDS - set(components)):
        problems.append(f"{relative(workspace_lock_path)}: missing component {component_id}")
    for component_id, component in sorted(components.items()):
        problems.extend(validate_component(workspace_lock_path, component_id, component))
    return problems


def validate_component(path: Path, component_id: str, component: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    prefix = f"{relative(path)} component {component_id}"
    pin = str(component.get("pin", "")).strip().lower()
    if not HASH_PATTERN.fullmatch(pin):
        problems.append(f"{prefix}: pin must be a 40-char hex SHA")
        return problems
    if component_id in {"universal_launcher", "universal_setup"}:
        relative_path = str(component.get("path", ""))
        repo_path = resolve_repo_path(component)
        if repo_path is None:
            if relative_path:
                problems.append(f"{prefix}: workspace path does not exist: {relative_path}")
            else:
                problems.append(f"{prefix}: path is required")
            return problems
        if not repo_path.is_dir():
            problems.append(f"{prefix}: workspace path does not exist: {relative_path}")
            return problems
        if not repo_head_matches(repo_path, pin):
            problems.append(
                f"{prefix}: workspace commit {repo_head(repo_path)} does not match pinned {pin} at {relative_path}"
            )
    return problems


def resolve_repo_path(component: dict[str, Any]) -> Path | None:
    explicit_path = str(component.get("path", "")).strip()
    source = str(component.get("source", "")).strip()
    candidates = []
    if explicit_path:
        candidates.append((ROOT / explicit_path).resolve())
    if source:
        candidates.extend(
            [
                (ROOT.parent / source).resolve(),
                (ROOT.parent / "Universal" / source).resolve(),
                (ROOT.parent.parent / "Universal" / source).resolve(),
            ]
        )
    if explicit_path:
        candidates.append((ROOT.parent.parent / explicit_path.strip("/\\")).resolve())
    for candidate in candidates:
        if (candidate / ".git").is_dir():
            return candidate
    return None


def repo_head_matches(repo_path: Path, expected: str) -> bool:
    return repo_head(repo_path) == expected


def repo_head(repo_path: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if completed.returncode != 0:
        return "unknown"
    return completed.stdout.strip()


def _component_map(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for item in value:
        if isinstance(item, dict):
            component_id = str(item.get("id", ""))
            if component_id:
                result[component_id] = item
    return result


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


if __name__ == "__main__":
    raise SystemExit(main())
