# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import aide_queue_records, architecture_fitness


def detect() -> set[str]:
    violations: set[str] = set()
    queue = architecture_fitness.ROOT / ".aide/queue"
    try:
        records = aide_queue_records.read_queue_records(queue)
        violations.update(aide_queue_records.validate_queue_index(queue, records))
    except aide_queue_records.QueueRecordError as error:
        return {str(error)}
    for record in records:
        status_path = record.root / "status.yaml"
        result = aide_queue_records.yaml_field(status_path, "result")
        completed = bool(
            aide_queue_records.yaml_field(status_path, "completed_at")
        ) or record.planning_state in {"implementation_completed", "closed"}
        if result == "PASS" and completed and record.status in {
            "active",
            "running",
            "needs_review",
        }:
            violations.add(f"{record.id}:{record.status}")
    return violations


def main() -> int:
    return architecture_fitness.run("aide_queue_state", detect)


if __name__ == "__main__":
    raise SystemExit(main())
