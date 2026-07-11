from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_DOCS = (
    "CONTRIBUTING.md",
    "docs/development/getting-started.md",
    "docs/development/adding-a-command.md",
    "docs/development/adding-a-persisted-model.md",
    "docs/development/adding-a-transactional-writer.md",
    "docs/development/adding-a-package-profile.md",
    "docs/development/adding-a-frontend.md",
    "docs/development/testing.md",
    "docs/architecture/module-graph.md",
    "docs/architecture/compatibility-policy.md",
    "docs/architecture/extension-policy.md",
    "docs/release/release-handbook.md",
)


def validate_history() -> list[str]:
    problems = []
    history = ROOT / ".aide" / "history"
    for index_path in sorted(history.glob("*/index.json")):
        data = json.loads(index_path.read_text(encoding="utf-8"))
        if data.get("immutable_task_records") is not True:
            problems.append(f"{index_path}: history does not declare immutable records")
        checkpoint = index_path.parent
        for task in data.get("tasks", []):
            task_root = checkpoint / task["task_id"]
            for relative, expected in task.get("files", {}).items():
                path = task_root / relative
                if not path.is_file():
                    problems.append(f"missing archived evidence: {path.relative_to(ROOT)}")
                elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                    problems.append(f"archived evidence hash drift: {path.relative_to(ROOT)}")
    return problems


def validate() -> list[str]:
    problems = validate_history()
    queue = ROOT / ".aide" / "queue"
    legacy = [path.name for path in queue.iterdir() if path.is_dir() and path.name not in {"active", "next"}]
    if legacy:
        problems.append("closed task bulk remains in active queue root: " + ", ".join(sorted(legacy)))
    index = (queue / "index.yaml").read_text(encoding="utf-8")
    if "needs_review" in index:
        problems.append("completed queue projection still contains needs_review")
    if "canonical_source: .aide/queue/{active,next}" not in index:
        problems.append("queue index does not declare active and next task lanes")
    ignore = (ROOT / ".aide" / "context" / "ignore.yaml").read_text(encoding="utf-8")
    if ".aide/history/**" not in ignore:
        problems.append("normal context does not exclude archived task bulk")
    compiler = (ROOT / ".aide" / "context" / "compiler.yaml").read_text(encoding="utf-8")
    for anchor in ("project-state.v1.json", "contracts/policy/test_impact.v1.json", "exclude_archived_task_bulk: true"):
        if anchor not in compiler:
            problems.append(f"context compiler is missing compact-state anchor: {anchor}")
    script = (ROOT / ".aide" / "scripts" / "aide_lite.py").read_text(encoding="utf-8")
    for command in ("create", "start", "verify", "review", "close", "archive"):
        if f'add_parser("{command}")' not in script and f'lifecycle_command in ("start", "verify", "review", "close"' not in script:
            problems.append(f"AIDE lifecycle command is missing: {command}")
    for relative in REQUIRED_DOCS:
        if not (ROOT / relative).is_file():
            problems.append(f"required consolidated documentation is missing: {relative}")
    future = (ROOT / "docs" / "architecture" / "future_layers_plan.md").read_text(encoding="utf-8")
    for stale in ("### R2.2", "### R2.3", "### R2.4", "### R3 Safe Beta"):
        if stale in future:
            problems.append(f"future-layers plan retains completed-era heading: {stale}")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"aide-compaction-check: {problem}", file=sys.stderr)
        return 1
    print("aide-compaction-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
