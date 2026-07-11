from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import re

from tools import architecture_fitness


def field(text: str, name: str) -> str:
    match = re.search(rf"(?m)^{re.escape(name)}:\s*(.+?)\s*$", text)
    return match.group(1) if match else ""


def detect() -> set[str]:
    violations: set[str] = set()
    queue = architecture_fitness.ROOT / ".aide/queue"
    for status_path in sorted(queue.glob("active/*/status.yaml")) + sorted(queue.glob("next/*/status.yaml")):
        text = status_path.read_text(encoding="utf-8", errors="replace")
        status = field(text, "status")
        result = field(text, "result")
        completed = bool(field(text, "completed_at")) or field(text, "planning_state") in {"implementation_completed", "closed"}
        if result == "PASS" and completed and status in {"active", "running", "needs_review"}:
            violations.add(f"{status_path.parent.name}:{status}")
    return violations


def main() -> int:
    return architecture_fitness.run("aide_queue_state", detect)


if __name__ == "__main__":
    raise SystemExit(main())
