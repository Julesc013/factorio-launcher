# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEADER = ROOT / "runtime" / "workspace" / "fl_workspace_root_authority.h"
SOURCE = ROOT / "runtime" / "workspace" / "fl_workspace_root_authority.cpp"
STORE = ROOT / "runtime" / "workspace" / "fl_workspace_store.cpp"
SMOKE = ROOT / "tests" / "native" / "fl_workspace_root_authority_smoke.cpp"


def validate() -> list[str]:
    problems: list[str] = []
    for path in (HEADER, SOURCE, STORE, SMOKE):
        if not path.is_file():
            problems.append(f"missing workspace-root authority file: {path.relative_to(ROOT)}")
    if problems:
        return problems

    header = HEADER.read_text(encoding="utf-8")
    source = SOURCE.read_text(encoding="utf-8")
    store = STORE.read_text(encoding="utf-8")
    smoke = SMOKE.read_text(encoding="utf-8")
    for state in (
        "missing",
        "empty_unowned",
        "facman_owned",
        "legacy_facman",
        "foreign_nonempty",
        "link_or_reparse",
        "inspection_failed",
    ):
        if state not in header or f'"{state}"' not in source:
            problems.append(f"workspace-root classifier is missing state {state}")
    for anchor in (
        "StableDirectoryObject",
        "StableInputFile",
        "inspect_path_no_follow",
        "path_crosses_link_or_reparse_point",
        "workspace_root_marker",
        "facman.workspace_root_owner.v1",
        "claim_workspace_root",
        "adopt_legacy_workspace_root",
        "rollback_legacy_workspace_root_adoption",
        "revalidate_workspace_root",
    ):
        if anchor not in header + source:
            problems.append(f"workspace-root authority is missing safety anchor {anchor}")
    for refusal in (
        "workspace_root_legacy_adoption_required",
        "workspace_root_foreign_refused",
        "workspace_root_link_refused",
        "workspace_root_inspection_failed",
    ):
        if refusal not in store:
            problems.append(f"workspace ensure is missing refusal {refusal}")
    for proof in (
        "prove_states",
        "prove_explicit_reversible_adoption",
        "prove_changed_marker_fails_closed",
    ):
        if proof not in smoke:
            problems.append(f"workspace-root native proof is missing {proof}")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"workspace-root-authority-check: {problem}", file=sys.stderr)
        return 1
    print("workspace-root-authority-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
