# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
JOURNEY = ROOT / "tests/test_r37_lifecycle_journey.py"
PERFORMANCE = ROOT / "tests/test_r37_performance.py"
PROOF = ROOT / "docs/quality/r3.7-lifecycle-proof.md"


def validate() -> list[str]:
    problems: list[str] = []
    journey = JOURNEY.read_text(encoding="utf-8")
    performance = PERFORMANCE.read_text(encoding="utf-8")
    proof = PROOF.read_text(encoding="utf-8")
    for anchor in (
        "workspace.status", "installs", "instances", "profiles", "mods", "modsets", "saves",
        "snapshots", "snapshot:baseline", "archive", "restore", "servers", "retention", "recovery",
        "rpc", "--interactive", "--transport", "process", "WinForms.Probe",
    ):
        if anchor not in journey:
            problems.append(f"R3.7 main journey anchor is missing: {anchor}")
    adversarial = (
        "malicious ID", "reserved Windows name", "case collision", "Unicode-normalization collision",
        "link, reparse, or junction crossing", "hard-linked source", "source changed during clone/copy",
        "corrupt snapshot", "snapshot/archive bomb", "duplicate archive paths",
        "cross-volume commit failure boundary", "existing destination", "transaction interruption and recovery",
        "restore into incompatible install", "solver cycle", "solver budget exhaustion", "mod hash drift",
        "save hash drift", "retention target substitution", "server plaintext secret", "cancelled request",
        "transport timeout", "read-only package root",
    )
    for scenario in adversarial:
        if scenario not in proof:
            problems.append(f"R3.7 adversarial evidence is missing: {scenario}")
    for anchor in (
        "range(1000)", "range(10000)", "range(100)", "range(2000)",
        "--max-graph-edges", "--max-solver-states", "FACMAN_RUN_R37_FULL_PERFORMANCE",
    ):
        if anchor not in performance:
            problems.append(f"R3.7 performance proof is missing: {anchor}")
    product_anchors = {
        ROOT / "runtime/factorio/instance/flb_factorio_instance_lifecycle.cpp": (
            "load_for_instance_diff", "archive_files_copied_and_environment_identity_regenerated",
            "instance_restore_install_incompatible",
        ),
        ROOT / "runtime/factorio/saves/flb_factorio_save_index.cpp": (
            "kMaximumSaves = 10000", "FACMAN_SAVE_RETENTION_FAULT", "Moved save identity",
        ),
        ROOT / "runtime/client/facman_client.cpp": (
            "64U * 1024U * 1024U", "maximum_nodes = 1000000",
        ),
        ROOT / "apps/cli/command_dispatch.cpp": ("0xEFU", "kTransportOutputLimit = 16U"),
    }
    for path, anchors in product_anchors.items():
        text = path.read_text(encoding="utf-8")
        for anchor in anchors:
            if anchor not in text:
                problems.append(f"R3.7 product proof anchor is missing in {path.relative_to(ROOT)}: {anchor}")
    if not (ROOT / "tests/frontend_harness/FacMan.WinForms.Probe.csproj").is_file():
        problems.append("WinForms generated-client lifecycle probe is missing")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"r37-lifecycle-check: {problem}", file=sys.stderr)
        return 1
    print("r37-lifecycle-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
