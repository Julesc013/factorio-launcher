#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate alpha.4 maintainability and performance regression budgets."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import resource_pack  # noqa: E402


BUDGET = ROOT / "release/index/engineering_quality_budget.v1.toml"


def detect() -> list[str]:
    with BUDGET.open("rb") as stream:
        budget = tomllib.load(stream)
    problems: list[str] = []
    if budget.get("schema") != "facman.engineering_quality_budget.v1":
        problems.append("engineering quality budget has the wrong schema")
    if budget.get("release") != "0.1.0-alpha.4":
        problems.append("engineering quality budget must bind alpha.4")

    pack = budget.get("resource_pack", {})
    expected_pack = {
        "max_entries": resource_pack.MAX_ENTRIES,
        "max_entry_bytes": resource_pack.MAX_ENTRY_BYTES,
        "max_total_bytes": resource_pack.MAX_TOTAL_BYTES,
        "deterministic": True,
        "verify_before_use": True,
    }
    if pack != expected_pack:
        problems.append("resource-pack implementation and quality budgets have drifted")

    seen: set[str] = set()
    for entry in budget.get("source_budget", []):
        relative = entry.get("path", "")
        if not relative or relative in seen:
            problems.append(f"source budget path is empty or duplicated: {relative!r}")
            continue
        seen.add(relative)
        path = ROOT / relative
        if not path.is_file():
            problems.append(f"source budget path does not exist: {relative}")
            continue
        maximum = entry.get("max_lines")
        if not isinstance(maximum, int) or maximum < 1:
            problems.append(f"source budget is invalid: {relative}")
            continue
        actual = len(path.read_text(encoding="utf-8").splitlines())
        if actual > maximum:
            problems.append(f"source budget exceeded: {relative} has {actual} lines (max {maximum})")
        if not entry.get("rationale"):
            problems.append(f"source budget lacks rationale: {relative}")

    performance = budget.get("performance", {})
    for field in (
        "resource_pack_build_seconds_ci",
        "resource_pack_verify_seconds_ci",
        "cli_startup_milliseconds_reference",
    ):
        value = performance.get(field)
        if not isinstance(value, int) or value < 1:
            problems.append(f"performance.{field} must be a positive integer")
    if performance.get("budgets_are_regression_thresholds_not_support_claims") is not True:
        problems.append("performance budgets must not imply support authority")

    maintenance = budget.get("maintenance", {})
    if maintenance.get("new_public_binaries_permitted") != 0:
        problems.append("alpha.4 must not admit additional public binaries")
    if maintenance.get("public_resource_formats") != ["facman.resources"]:
        problems.append("alpha.4 must expose one canonical resource format")
    if maintenance.get("compatibility_tui_is_product_artifact") is not False:
        problems.append("compatibility TUI must remain outside product artifacts")
    if maintenance.get("daemon_is_product_artifact") is not False:
        problems.append("daemon must remain outside product artifacts")
    return problems


def main() -> int:
    problems = detect()
    if problems:
        for problem in problems:
            print(f"engineering-quality-check: {problem}", file=sys.stderr)
        return 1
    print("engineering-quality-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
