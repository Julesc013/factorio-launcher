# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = ("mods.import", "modsets.lock", "modsets.verify", "modsets.export")


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
    application += (ROOT / "runtime/factorio/application/handlers/mods.cpp").read_text(encoding="utf-8")
    application += (ROOT / "runtime/factorio/application/handlers/modsets.cpp").read_text(encoding="utf-8")
    operations = (ROOT / "runtime/factorio/modsets/flb_factorio_modset_operations.cpp").read_text(
        encoding="utf-8"
    )
    mods = (ROOT / "runtime/factorio/mods/flb_factorio_mods.cpp").read_text(encoding="utf-8")
    cli = (ROOT / "apps/cli/command_dispatch.cpp").read_text(encoding="utf-8")
    for command in COMMANDS:
        if f'"{command}"' not in binding:
            problems.append(f"FLB does not register canonical command: {command}")
        if f'"{command}"' not in application:
            problems.append(f"typed application does not decode canonical command: {command}")
    for anchor in (
        "inspect_archive(",
        "stream_entry(",
        "write_to_new_owned_staging(",
        "tx::StagedFileCommit::commit(",
    ):
        combined = operations + mods
        if anchor not in combined:
            problems.append(f"production mod route is missing archive anchor: {anchor}")
    if "read_stored_zip(" in mods:
        problems.append("stored-only mod ZIP parser returned")

    mods_function = function_slice(cli, "int command_mods(", "int command_modsets(")
    mods_cli = mods_function
    modsets_cli = function_slice(cli, "int command_modsets(", "int command_saves(")
    for name, source in (("mods", mods_cli), ("modsets", modsets_cli)):
        if "call(options," not in source:
            problems.append(f"{name} CLI does not use FacManClient")
        for forbidden in (
            "load_instance(",
            "inspect_mod_zip(",
            "validate_instance_modset(",
            "write_stored_zip(",
            "copy_file(",
        ):
            if forbidden in source:
                problems.append(f"{name} CLI retains backend behavior: {forbidden}")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"modset-route-check: {problem}", file=sys.stderr)
        return 1
    print("modset-route-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
