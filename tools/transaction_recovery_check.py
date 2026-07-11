from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate() -> list[str]:
    problems: list[str] = []
    source = (ROOT / "runtime/transaction/fl_transaction.cpp").read_text(encoding="utf-8")
    header = (ROOT / "runtime/transaction/fl_transaction.h").read_text(encoding="utf-8")
    binding = (ROOT / "runtime/factorio/binding/flb_api.c").read_text(encoding="utf-8")
    binding += (ROOT / "runtime/core/generated/command_catalog.h").read_text(encoding="utf-8")
    application = (ROOT / "runtime/factorio/application/flb_factorio_application.cpp").read_text(
        encoding="utf-8"
    )
    cli = (ROOT / "apps/cli/command_dispatch.cpp").read_text(encoding="utf-8")
    for command in ("workspace.recovery.inspect", "workspace.recovery.plan", "workspace.recovery.apply"):
        if f'"{command}"' not in binding or f'"{command}"' not in application:
            problems.append(f"recovery command is not registered and typed: {command}")
    for anchor in (
        "facman.transaction.v1",
        "preserve_committed_target",
        "remove_owned_staging_tree(",
        "recovery.lock",
        "MOVEFILE_WRITE_THROUGH",
        "fsync(",
        "transaction_id",
        "commit_strategy",
        "expected_file_hashes",
    ):
        if anchor not in source + header:
            problems.append(f"transaction recovery proof anchor missing: {anchor}")
    if "route_factorio_command(" not in cli or '"workspace.recovery."' not in cli:
        problems.append("workspace recovery CLI does not use the authoritative route")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"transaction-recovery-check: {problem}", file=sys.stderr)
        return 1
    print("transaction-recovery-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
