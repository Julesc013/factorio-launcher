# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runtime/factorio/snapshots/flb_factorio_snapshots.cpp"
HEADER = ROOT / "runtime/factorio/snapshots/flb_factorio_snapshots.h"
INDEX = ROOT / "contracts/command/factorio/index.v1.toml"
TEST = ROOT / "tests/test_instance_snapshots.py"


def validate() -> list[str]:
    problems: list[str] = []
    source = SOURCE.read_text(encoding="utf-8")
    header = HEADER.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")
    test = TEST.read_text(encoding="utf-8")
    generated = (ROOT / "runtime/factorio/application/generated/command_ids.inc").read_text(encoding="utf-8")
    commands = (
        "snapshots.create", "snapshots.list", "snapshots.inspect", "snapshots.verify",
        "snapshots.diff", "snapshots.restore", "snapshots.retention.plan", "snapshots.retention.apply",
    )
    for command in commands:
        contract = ROOT / "contracts/command/factorio" / f"{command}.v1.toml"
        if not contract.is_file() or command not in index or command.replace(".", "_") not in generated:
            problems.append(f"typed snapshot command is not indexed and registered: {command}")
    for anchor in (
        "factorio.instance_snapshot.v1", "InstanceSnapshotPolicy::limits", "CompressionMethod::deflate",
        "options.reproducible = true", "verify_all", "snapshot_hash_closure_mismatch",
        "snapshot_secret_content_refused", "lock_references_only", 'workspace / "trash" / "snapshots"',
        "move_snapshot_pairs_to_owned_trash_no_delete", "commit_no_replace",
        "snapshot_transaction_recovery_required",
    ):
        if anchor not in source:
            problems.append(f"snapshot lifecycle safety anchor missing: {anchor}")
    for anchor in ("CreateRequest", "RestoreRequest", "RetentionRequest", "maximum_total_bytes", "minimum_age_days"):
        if anchor not in header:
            problems.append(f"snapshot typed API anchor missing: {anchor}")
    for proof in (
        "source_archive.read_bytes(), destination_archive.read_bytes()", "secret_content_included",
        "snapshot_restore_target_exists", "move_to_trash", "tamper",
    ):
        if proof not in test:
            problems.append(f"snapshot acceptance proof missing: {proof}")
    if "snapshots.purge" in index or 'permanent_delete", true' in source:
        problems.append("snapshot lifecycle must not expose permanent deletion")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"snapshot-lifecycle-check: {problem}", file=sys.stderr)
        return 1
    print("snapshot-lifecycle-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
