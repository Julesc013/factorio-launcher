# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "contracts" / "policy" / "critical_coverage.v1.json"


def validate(report: Path) -> list[str]:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    data = json.loads(report.read_text(encoding="utf-8"))
    files = data.get("files", [])
    problems: list[str] = []
    for module, floor in policy["modules"].items():
        summaries = []
        for entry in files:
            if str(entry.get("file", entry.get("filename", ""))).replace("\\", "/").find(module + "/") < 0:
                continue
            if "line_percent" in entry:
                summaries.append(float(entry["line_percent"]))
                continue
            if "line_total" in entry:
                summaries.append(float(entry.get("line_covered", 0)) * 100.0 / max(int(entry["line_total"]), 1))
                continue
            lines = entry.get("lines", [])
            if lines:
                summaries.append(sum(int(line.get("count", 0)) > 0 for line in lines) * 100.0 / len(lines))
        if not summaries:
            problems.append(f"coverage report has no files for {module}")
        elif max(summaries) < float(floor):
            problems.append(f"{module} coverage {max(summaries):.2f}% is below {floor:.2f}%")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Enforce critical-module coverage evidence floors.")
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    problems = validate(args.report)
    if problems:
        for problem in problems:
            print(f"coverage-policy-check: {problem}", file=sys.stderr)
        return 1
    print("coverage-policy-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
