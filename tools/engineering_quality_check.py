#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Validate current-candidate maintainability and performance regression budgets."""

from __future__ import annotations

import sys
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import resource_pack  # noqa: E402


BUDGET = ROOT / "release/index/engineering_quality_budget.v1.toml"
VERSION = ROOT / "release/index/version.v2.toml"
COMPLEXITY_METRIC = "lexical_decision_points_v2"
_DECISION_TOKENS = re.compile(
    r"\b(?:if|elif|for|foreach|while|case|catch|except|when|and|or)\b|&&|\|\|"
)


def lexical_decision_points(text: str, suffix: str = "") -> int:
    """Return a deterministic, language-neutral decision-point approximation.

    The metric deliberately removes quoted strings and line/block comments,
    then counts control-flow words and short-circuit operators. It is a ratchet
    for comparing a file with itself over time, not a cross-language quality
    score or a substitute for review.
    """

    cleaned: list[str] = []
    in_block_comment = False
    quote = ""
    triple_quote = False
    escaped = False
    directive_suffixes = {".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".m", ".mm", ".cs"}
    for original in text.splitlines():
        line = original
        stripped = line.lstrip()
        if not quote and stripped.startswith("#"):
            if suffix.casefold() not in directive_suffixes:
                continue
            directive = re.match(r"#\s*(if|elif)\b(.*)", stripped)
            if directive is None:
                continue
            line = directive.group(1) + directive.group(2)
        output: list[str] = []
        index = 0
        while index < len(line):
            if in_block_comment:
                end = line.find("*/", index)
                if end < 0:
                    index = len(line)
                    continue
                in_block_comment = False
                index = end + 2
                continue
            if quote:
                if triple_quote and line.startswith(quote * 3, index):
                    quote = ""
                    triple_quote = False
                    escaped = False
                    index += 3
                    continue
                char = line[index]
                if triple_quote:
                    index += 1
                    continue
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == quote:
                    quote = ""
                index += 1
                continue
            if line.startswith("/*", index):
                in_block_comment = True
                index += 2
                continue
            if line.startswith("//", index) or line[index] == "#":
                break
            if line.startswith("'''", index) or line.startswith('"""', index):
                quote = line[index]
                triple_quote = True
                escaped = False
                index += 3
                continue
            if line[index] in {"'", '"', "`"}:
                quote = line[index]
                triple_quote = False
                escaped = False
                index += 1
                continue
            output.append(line[index])
            index += 1
        cleaned.append("".join(output))
    return len(_DECISION_TOKENS.findall("\n".join(cleaned)))


def detect() -> list[str]:
    with BUDGET.open("rb") as stream:
        budget = tomllib.load(stream)
    with VERSION.open("rb") as stream:
        version = tomllib.load(stream)
    problems: list[str] = []
    if budget.get("schema") != "facman.engineering_quality_budget.v1":
        problems.append("engineering quality budget has the wrong schema")
    if budget.get("release") != version.get("semver"):
        problems.append("engineering quality budget must bind the canonical candidate")

    complexity = budget.get("complexity", {})
    if complexity.get("metric") != COMPLEXITY_METRIC:
        problems.append("engineering quality budget has the wrong complexity metric")
    if complexity.get("budgets_are_ratchets_not_quality_scores") is not True:
        problems.append("complexity budgets must be declared as ratchets, not quality scores")

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
        maximum_complexity = entry.get("max_complexity_points")
        if not isinstance(maximum_complexity, int) or maximum_complexity < 0:
            problems.append(f"source complexity budget is invalid: {relative}")
        else:
            actual_complexity = lexical_decision_points(
                path.read_text(encoding="utf-8"), path.suffix
            )
            if actual_complexity > maximum_complexity:
                problems.append(
                    "source complexity budget exceeded: "
                    f"{relative} has {actual_complexity} {COMPLEXITY_METRIC} points "
                    f"(max {maximum_complexity})"
                )
        if not entry.get("rationale"):
            problems.append(f"source budget lacks rationale: {relative}")

    performance = budget.get("performance", {})
    for field in (
        "resource_pack_build_seconds_ci",
        "resource_pack_verify_seconds_ci",
        "cli_startup_milliseconds_reference",
        "presentation_query_milliseconds_regression_ceiling",
        "tui_key_to_paint_milliseconds_regression_ceiling",
        "gui_startup_milliseconds_regression_ceiling",
        "max_process_reply_bytes",
    ):
        value = performance.get(field)
        if not isinstance(value, int) or value < 1:
            problems.append(f"performance.{field} must be a positive integer")
    if performance.get("budgets_are_regression_thresholds_not_support_claims") is not True:
        problems.append("performance budgets must not imply support authority")
    if performance.get("baseline_status") != "measurement_required_before_beta":
        problems.append("performance baselines must remain an explicit beta gate")

    maintenance = budget.get("maintenance", {})
    if maintenance.get("new_public_binaries_permitted") != 0:
        problems.append("the current candidate must not admit additional public binaries")
    if maintenance.get("public_resource_formats") != ["facman.resources"]:
        problems.append("the current candidate must expose one canonical resource format")
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
