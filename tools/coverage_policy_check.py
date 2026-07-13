# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "contracts" / "policy" / "critical_coverage.v1.json"


@dataclass
class Metrics:
    line_covered: int = 0
    line_total: int = 0
    branch_covered: int = 0
    branch_total: int = 0

    def add(self, other: "Metrics") -> None:
        self.line_covered += other.line_covered
        self.line_total += other.line_total
        self.branch_covered += other.branch_covered
        self.branch_total += other.branch_total

    def line_percent(self) -> float:
        return 100.0 * self.line_covered / self.line_total if self.line_total else 0.0

    def branch_percent(self) -> float:
        return 100.0 * self.branch_covered / self.branch_total if self.branch_total else 0.0


def normalize_path(value: str) -> str:
    return value.replace("\\", "/").removeprefix("./")


def metrics_for(entry: dict[str, Any]) -> Metrics:
    if "line_total" in entry:
        return Metrics(
            line_covered=int(entry.get("line_covered", 0)),
            line_total=int(entry.get("line_total", 0)),
            branch_covered=int(entry.get("branch_covered", 0)),
            branch_total=int(entry.get("branch_total", 0)),
        )
    metrics = Metrics()
    for line in entry.get("lines", []):
        if line.get("gcovr/excluded") or line.get("gcovr/noncode"):
            continue
        metrics.line_total += 1
        metrics.line_covered += int(line.get("count", 0)) > 0
        for branch in line.get("branches", []):
            if branch.get("gcovr/excluded"):
                continue
            metrics.branch_total += 1
            metrics.branch_covered += int(branch.get("count", 0)) > 0
    return metrics


def validate_policy(policy: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if policy.get("schema") != "facman.critical_coverage_policy.v2":
        problems.append("coverage policy has the wrong schema")
    for module, floors in policy.get("modules", {}).items():
        for metric in ("line_percent", "branch_percent"):
            value = floors.get(metric)
            if not isinstance(value, (int, float)) or not 0.0 < float(value) <= 100.0:
                problems.append(f"{module} has invalid {metric} floor {value!r}")
    for path, rule in policy.get("designated_files", {}).items():
        if not rule.get("reason"):
            problems.append(f"designated file {path} lacks a reason")
        if not any(path.startswith(module + "/") for module in policy.get("modules", {})):
            problems.append(f"designated file {path} is outside policy modules")
    for exclusion in policy.get("exclusions", []):
        if not exclusion.get("path") or not exclusion.get("reason"):
            problems.append("coverage exclusion requires path and reason")
    return problems


def validate(report: Path) -> list[str]:
    policy = json.loads(POLICY.read_text(encoding="utf-8"))
    problems = validate_policy(policy)
    data = json.loads(report.read_text(encoding="utf-8"))
    files = {
        normalize_path(str(entry.get("file", entry.get("filename", "")))): metrics_for(entry)
        for entry in data.get("files", [])
    }
    exclusions = {normalize_path(item["path"]) for item in policy.get("exclusions", [])}
    for module, floors in policy["modules"].items():
        aggregate = Metrics()
        matched = 0
        for path, metrics in files.items():
            if path in exclusions or not path.startswith(module + "/"):
                continue
            aggregate.add(metrics)
            matched += 1
        if not matched or aggregate.line_total == 0:
            problems.append(f"coverage report has no instrumented lines for {module}")
            continue
        line_floor = float(floors["line_percent"])
        if aggregate.line_percent() < line_floor:
            problems.append(
                f"{module} aggregate line coverage {aggregate.line_percent():.2f}% "
                f"({aggregate.line_covered}/{aggregate.line_total}) is below {line_floor:.2f}%"
            )
        branch_floor = float(floors["branch_percent"])
        if aggregate.branch_total == 0:
            problems.append(f"coverage report has no instrumented branches for {module}")
        elif aggregate.branch_percent() < branch_floor:
            problems.append(
                f"{module} aggregate branch coverage {aggregate.branch_percent():.2f}% "
                f"({aggregate.branch_covered}/{aggregate.branch_total}) is below {branch_floor:.2f}%"
            )
    for path, rule in policy.get("designated_files", {}).items():
        metrics = files.get(normalize_path(path))
        if metrics is None or metrics.line_total == 0:
            problems.append(f"coverage report has no instrumented lines for designated file {path}")
            continue
        floor = float(rule["line_percent"])
        if metrics.line_percent() < floor:
            problems.append(
                f"designated file {path} line coverage {metrics.line_percent():.2f}% "
                f"({metrics.line_covered}/{metrics.line_total}) is below {floor:.2f}%"
            )
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enforce aggregate line/branch and designated-file critical coverage floors."
    )
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
