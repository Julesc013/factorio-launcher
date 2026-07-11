# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = ("saves.list", "saves.backup", "saves.clone", "instance.export", "instance.import")


def function_slice(text: str, start: str, end: str) -> str:
    begin = text.find(start)
    finish = text.find(end, begin + len(start))
    if begin < 0 or finish < 0:
        return ""
    return text[begin:finish]


def validate() -> list[str]:
    problems: list[str] = []
    binding = (ROOT / "runtime/factorio/binding/flb_api.c").read_text(encoding="utf-8")
    binding += (ROOT / "runtime/core/generated/command_catalog.h").read_text(encoding="utf-8")
    application = (ROOT / "runtime/factorio/application/flb_factorio_application.cpp").read_text(
        encoding="utf-8"
    )
    application += (ROOT / "runtime/factorio/application/command_dispatch.cpp").read_text(encoding="utf-8")
    application += (ROOT / "runtime/factorio/application/handlers/saves.cpp").read_text(encoding="utf-8")
    operations = (ROOT / "runtime/factorio/saves/flb_factorio_save_operations.cpp").read_text(
        encoding="utf-8"
    )
    cli = (ROOT / "apps/cli/command_dispatch.cpp").read_text(encoding="utf-8")
    for command in COMMANDS:
        if f'"{command}"' not in binding:
            problems.append(f"FLB does not register canonical command: {command}")
        if f'"{command}"' not in application:
            problems.append(f"typed application does not decode canonical command: {command}")
    for anchor in (
        "inspect_archive(",
        "extract_to_new_owned_staging(",
        "write_to_new_owned_staging(",
        "tx::StagedFileCommit::commit(",
        "tx::StagedDirectoryCommit::commit(",
        "tx::CrossVolumeCopyVerifyCommit::commit(",
        "archive_structurally_valid",
        "factorio_save_recognized",
        "deep_save_semantics_inspected",
    ):
        if anchor not in operations:
            problems.append(f"typed save/transfer route is missing proof anchor: {anchor}")
    for legacy in ("read_stored_zip(", "legacy_command_saves", "legacy_command_export", "legacy_command_import"):
        if legacy in cli:
            problems.append(f"migrated CLI backend returned: {legacy}")
    slices = {
        "saves": function_slice(cli, "int command_saves(", "int command_diagnostics("),
        "instance.transfer": function_slice(cli, "int command_transfer(", "int command_servers("),
    }
    for name, source in slices.items():
        if "call(options," not in source:
            problems.append(f"{name} CLI does not use FacManClient")
        for forbidden in (
            "load_instance(",
            "inspect_archive(",
            "copy_file(",
            "write_to_new_owned_staging(",
            "extract_to_new_owned_staging(",
            "commit_directory_no_clobber(",
        ):
            if forbidden in source:
                problems.append(f"{name} CLI retains backend behavior: {forbidden}")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"save-transfer-route-check: {problem}", file=sys.stderr)
        return 1
    print("save-transfer-route-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
