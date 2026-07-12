# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runtime/factorio/instance/flb_factorio_instance_lifecycle.cpp"
INDEX = ROOT / "contracts/command/factorio/index.v1.toml"
TEST = ROOT / "tests/test_instance_lifecycle.py"


def validate() -> list[str]:
    problems: list[str] = []
    source = SOURCE.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")
    test = TEST.read_text(encoding="utf-8")
    commands = (
        "instances.inspect",
        "instances.verify",
        "instances.diff",
        "instances.clone",
        "instances.rename",
        "instances.archive",
        "instances.restore",
    )
    for command in commands:
        contract = ROOT / "contracts/command/factorio" / f"{command}.v1.toml"
        if not contract.is_file() or command not in index:
            problems.append(f"typed instance lifecycle command is not indexed: {command}")
    combined_contracts = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "contracts/command/factorio").glob("*.toml")
    )
    if "instances.purge" in combined_contracts:
        problems.append("hard-delete instances.purge command is forbidden in R3.7")
    for anchor in (
        'root / "trash" / "instances"',
        "CrossVolumeCopyVerifyCommit::commit",
        "commit_directory_no_clobber",
        '"archive.v1.json"',
        '"locks" / "run.lock"',
        '"hard_delete_available"',
        "incomplete_count(root)",
        "FACMAN_INSTANCE_LIFECYCLE_FAULT",
    ):
        if anchor not in source:
            problems.append(f"instance lifecycle safety anchor missing: {anchor}")
    if "remove_all(" in source:
        problems.append("instance lifecycle source may not hard-delete directory trees")
    for stage in ("after_validated", "during_copy", "after_verified", "before_commit", "after_commit", "after_metadata"):
        if stage not in source or stage not in test:
            problems.append(f"instance lifecycle fault stage lacks implementation and proof: {stage}")
    schema = (ROOT / "contracts/schema/factorio/factorio_instance_lifecycle.v1.schema.json").read_text(
        encoding="utf-8"
    )
    if '"hard_delete_available": {"const": false}' not in schema:
        problems.append("instance lifecycle schema does not make hard-delete absence contractual")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"instance-lifecycle-check: {problem}", file=sys.stderr)
        return 1
    print("instance-lifecycle-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
