# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runtime/factorio/mods/flb_factorio_mods.cpp"
HEADER = ROOT / "runtime/factorio/mods/flb_factorio_mods.h"
INDEX = ROOT / "contracts/command/factorio/index.v1.toml"
TEST = ROOT / "tests/test_local_mod_inventory.py"


def validate() -> list[str]:
    problems: list[str] = []
    source = SOURCE.read_text(encoding="utf-8")
    header = HEADER.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")
    test = TEST.read_text(encoding="utf-8")
    for command in ("mods.list", "mods.inspect", "mods.verify", "mods.index", "mods.explain"):
        if command not in index or not (ROOT / "contracts/command/factorio" / f"{command}.v1.toml").is_file():
            problems.append(f"local mod inventory command is not indexed: {command}")
    for anchor in (
        "StableInputFile", "open_no_follow", "revalidate", "ModArchivePolicy::limits", "sha1_hex_file",
        "Sha256Hasher", "hidden_optional_dependencies", "archive_policy_result", "instance_references",
        "lock_references", "virtual_not_archive", 'install.root / "data"', "recursive_scan", "portal_access",
        "source_mutation",
    ):
        if anchor not in source + header:
            problems.append(f"local mod inventory safety anchor is missing: {anchor}")
    if "recursive_directory_iterator" in source:
        problems.append("local mod inventory must not recursively scan arbitrary roots")
    for proof in (
        "valid_optional_deps", "hidden_optional_dependencies", "virtual_package", "portal_access",
        "source_mutation", "relative-root", "nested",
    ):
        if proof not in test:
            problems.append(f"local mod inventory acceptance proof is missing: {proof}")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"mod-inventory-check: {problem}", file=sys.stderr)
        return 1
    print("mod-inventory-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
