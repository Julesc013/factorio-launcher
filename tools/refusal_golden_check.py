# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_ROOT = ROOT / "tests" / "golden" / "commands"


def main() -> int:
    problems: list[str] = []
    paths = sorted(GOLDEN_ROOT.glob("*.refusal.json"))
    if not paths:
        problems.append(f"{GOLDEN_ROOT.relative_to(ROOT)}: no refusal goldens found")
    for path in paths:
        problems.extend(validate_refusal_golden(path))

    if problems:
        for problem in problems:
            print(f"refusal-golden-check: {problem}", file=sys.stderr)
        return 1
    print(f"refusal-golden-check: ok ({len(paths)} refusals)")
    return 0


def validate_refusal_golden(path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path.relative_to(ROOT)}: {exc}"]
    if not isinstance(data, dict):
        return [f"{path.relative_to(ROOT)}: refusal golden must be a JSON object"]

    problems: list[str] = []
    if data.get("status") != "refused":
        problems.append(f"{path.relative_to(ROOT)}: status must be refused")
    if "schema" not in data:
        problems.append(f"{path.relative_to(ROOT)}: missing top-level schema")
    if "command" not in data:
        problems.append(f"{path.relative_to(ROOT)}: missing command")

    refusal = data.get("refusal")
    if not isinstance(refusal, dict):
        return problems + [f"{path.relative_to(ROOT)}: missing refusal object"]
    if refusal.get("schema") != "common.refusal.v1":
        problems.append(f"{path.relative_to(ROOT)}: refusal schema must be common.refusal.v1")
    for key in ["code", "reason", "recoverable"]:
        if key not in refusal:
            problems.append(f"{path.relative_to(ROOT)}: refusal missing {key}")
    if "recoverable" in refusal and not isinstance(refusal["recoverable"], bool):
        problems.append(f"{path.relative_to(ROOT)}: refusal recoverable must be boolean")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
