from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def validate() -> list[str]:
    problems: list[str] = []
    source = (ROOT / "runtime/transaction/fl_transaction.cpp").read_text(encoding="utf-8")
    header = (ROOT / "runtime/transaction/fl_transaction.h").read_text(encoding="utf-8")
    platform = (ROOT / "runtime/platform/fl_file_io.cpp").read_text(encoding="utf-8")
    binding = (ROOT / "runtime/factorio/binding/flb_api.c").read_text(encoding="utf-8")
    binding += (ROOT / "runtime/core/generated/command_catalog.h").read_text(encoding="utf-8")
    application = (ROOT / "runtime/factorio/application/flb_factorio_application.cpp").read_text(
        encoding="utf-8"
    )
    application += (ROOT / "runtime/factorio/application/command_dispatch.cpp").read_text(encoding="utf-8")
    application += (ROOT / "runtime/factorio/application/handlers/recovery.cpp").read_text(encoding="utf-8")
    consumers = {
        "application": (ROOT / "runtime/factorio/application/handlers/instances.cpp").read_text(encoding="utf-8") +
            (ROOT / "runtime/factorio/application/handlers/installs.cpp").read_text(encoding="utf-8"),
        "modsets": (ROOT / "runtime/factorio/modsets/flb_factorio_modset_operations.cpp").read_text(encoding="utf-8"),
        "saves": (ROOT / "runtime/factorio/saves/flb_factorio_save_operations.cpp").read_text(encoding="utf-8"),
        "diagnostics": (ROOT / "runtime/factorio/diagnostics/flb_factorio_diagnostics.cpp").read_text(encoding="utf-8"),
    }
    cli = (ROOT / "apps/cli/command_dispatch.cpp").read_text(encoding="utf-8")
    for command in ("workspace.recovery.inspect", "workspace.recovery.plan", "workspace.recovery.apply"):
        if f'"{command}"' not in binding or f'"{command}"' not in application:
            problems.append(f"recovery command is not registered and typed: {command}")
    for anchor in (
        "facman.transaction.v1",
        "facman.transaction.v2",
        "enum class State",
        "can_transition",
        "TransactionSession",
        "transaction_staging.v2",
        "ExpectedFile",
        "StagedFileCommit",
        "StagedDirectoryCommit",
        "CrossVolumeCopyVerifyCommit",
        "RetentionPolicy",
        "preserve_committed_target",
        "remove_owned_staging_tree(",
        "recovery.lock",
        "DurableOutputFile",
        "replace_existing_durable",
        "transaction_id",
        "commit_strategy",
        "expected_files",
    ):
        if anchor not in source + header + platform:
            problems.append(f"transaction recovery proof anchor missing: {anchor}")
    if "call(options," not in cli or '"workspace." + family + "." + action' not in cli:
        problems.append("workspace recovery CLI does not use FacManClient")
    for name, consumer in consumers.items():
        if "TransactionSession::begin(" not in consumer:
            problems.append(f"transactional writer family does not use TransactionSession: {name}")
        for legacy in ("tx::begin(", "tx::advance(", "tx::complete(", "tx::fail("):
            if legacy in consumer:
                problems.append(f"transactional writer family retains raw choreography: {name}: {legacy}")
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
