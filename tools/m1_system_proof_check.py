# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(text: str, anchors: tuple[str, ...], scope: str) -> list[str]:
    return [f"{scope} is missing proof anchor: {anchor}" for anchor in anchors if anchor not in text]


def validate() -> list[str]:
    problems: list[str] = []
    cmake = (ROOT / "tests/native/CMakeLists.txt").read_text(encoding="utf-8")
    problems.extend(require(cmake, (
        "m1_three_repository_system_proof",
        "flb_factorio_application_static",
        "usk_lifecycle_static",
        "ulk_static",
        '"contract;filesystem;integration;transaction"',
    ), "M1 system-proof target"))

    proof = (ROOT / "tests/native/m1_three_repository_system_proof.cpp").read_text(
        encoding="utf-8"
    )
    problems.extend(require(proof, (
        "inspect_install_archive",
        "usk::lifecycle::apply_install",
        "ULK_SETUP_OPERATION_INSTALL",
        "handlers::create_instance",
        "handlers::preview_launch",
        "handlers::refuse_execute",
        "usk::lifecycle::verify_installed",
        "usk::lifecycle::apply_move",
        "ULK_SETUP_OPERATION_MOVE",
        "usk::lifecycle::apply_repair",
        "ULK_SETUP_OPERATION_REPAIR",
        "usk::lifecycle::apply_uninstall",
        "ULK_SETUP_OPERATION_UNINSTALL",
        "TransactionSession::inspect_recovery",
        "recover_install_finalization",
        '"isolation_not_proven"',
    ), "M1 system-proof journey"))
    if proof.count("usk::lifecycle::apply_uninstall") < 2:
        problems.append("M1 proof must cover foreign-content refusal and later clean uninstall")

    setup = (ROOT / "runtime/factorio/application/handlers/setup.cpp").read_text(
        encoding="utf-8"
    )
    if setup.count("live_target_acceptance_required") < 6:
        problems.append("ordinary setup apply routes are no longer uniformly gated by human M2 acceptance")

    docs = (ROOT / "docs/quality/m1-three-repository-system-proof.v1.md").read_text(
        encoding="utf-8"
    )
    problems.extend(require(docs, (
        "fixture-only authority",
        "Universal Setup",
        "Universal Launcher",
        "FacMan",
        "old root retained",
        "H1 Fail",
        "no proprietary binaries",
    ), "M1 proof documentation"))
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"m1-system-proof-check: {problem}", file=sys.stderr)
        return 1
    print("m1-system-proof-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
