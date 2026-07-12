# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runtime/factorio/saves/flb_factorio_save_index.cpp"
HEADER = ROOT / "runtime/factorio/saves/flb_factorio_save_index.h"
INDEX = ROOT / "contracts/command/factorio/index.v1.toml"
TEST = ROOT / "tests/test_save_index_retention.py"


def validate() -> list[str]:
    problems: list[str] = []
    source = SOURCE.read_text(encoding="utf-8")
    header = HEADER.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")
    test = TEST.read_text(encoding="utf-8")
    commands = (
        "saves.index", "saves.inspect", "saves.verify", "saves.associate", "saves.diff",
        "saves.retention.plan", "saves.retention.apply",
    )
    for command in commands:
        if command not in index or not (ROOT / "contracts/command/factorio" / f"{command}.v1.toml").is_file():
            problems.append(f"save intelligence command is not indexed: {command}")
    for anchor in (
        "StableInputFile", "open_no_follow", "revalidate", "SaveArchivePolicy::limits", "Sha256Hasher",
        "factorio.save_ref.v1", "deep_factorio_save_metadata", "unsupported", "save_content_modified",
        "backup_sidecar_status",
        "move_save_and_sidecar_to_owned_trash_no_delete", "permanent_delete", "reversible",
    ):
        if anchor not in source + header:
            problems.append(f"save intelligence safety anchor is missing: {anchor}")
    for forbidden in ("map version", "map settings", "DLC state", "recursive_directory_iterator"):
        if forbidden in source:
            problems.append(f"save intelligence crosses its structural truth boundary: {forbidden}")
    for proof in ("drifted", "save_content_modified", "old_bytes", "trash", "unsupported"):
        if proof not in test:
            problems.append(f"save intelligence acceptance proof is missing: {proof}")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"save-index-check: {problem}", file=sys.stderr)
        return 1
    print("save-index-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
