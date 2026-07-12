# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runtime/factorio/modsets/flb_factorio_modset_solver.cpp"
HEADER = ROOT / "runtime/factorio/modsets/flb_factorio_modset_solver.h"
INDEX = ROOT / "contracts/command/factorio/index.v1.toml"
TEST = ROOT / "tests/test_local_modset_solver.py"


def validate() -> list[str]:
    problems: list[str] = []
    source = SOURCE.read_text(encoding="utf-8")
    header = HEADER.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")
    test = TEST.read_text(encoding="utf-8")
    for command in ("modsets.plan", "modsets.diff", "modsets.explain", "modsets.apply", "modsets.rollback"):
        if command not in index or not (ROOT / "contracts/command/factorio" / f"{command}.v1.toml").is_file():
            problems.append(f"local modset command is not indexed: {command}")
    for anchor in (
        "maximum_packages", "maximum_versions_per_package", "maximum_graph_edges", "maximum_solver_states",
        "maximum_backtracks", "maximum_elapsed_ms", "maximum_explanation_nodes", "local_dependency_unavailable",
        "solver_budget_exceeded", "current_state_sha256", "StableInputFile", "revalidate", "TransactionSession",
        "backup_then_atomic_replace_with_rollback", "mod-list.json", "portal_access", "local_artifacts_only",
    ):
        if anchor not in source + header:
            problems.append(f"local modset safety anchor is missing: {anchor}")
    for forbidden in ("http://", "https://", "Mod Portal"):
        if forbidden in source:
            problems.append(f"local modset solver contains a network or portal route: {forbidden}")
    for proof in (
        "byte_deterministic", "local_dependency_unavailable", "solver_budget_exceeded", "after_first_commit",
        "rollback", "virtual", "portal_access",
    ):
        if proof not in test:
            problems.append(f"local modset acceptance proof is missing: {proof}")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"modset-solver-check: {problem}", file=sys.stderr)
        return 1
    print("modset-solver-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
