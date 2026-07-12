# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runtime/factorio/server/flb_factorio_server_plan.cpp"
PROFILE_SOURCE = ROOT / "runtime/factorio/application/handlers/utility.cpp"
INDEX = ROOT / "contracts/command/factorio/index.v1.toml"
TEST = ROOT / "tests/test_server_plan.py"


def validate() -> list[str]:
    problems: list[str] = []
    source = SOURCE.read_text(encoding="utf-8")
    profile_source = PROFILE_SOURCE.read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")
    test = TEST.read_text(encoding="utf-8")
    commands = ("servers.inspect", "servers.validate", "servers.plan", "servers.diff", "servers.export")
    for command in commands:
        if command not in index or not (ROOT / "contracts/command/factorio" / f"{command}.v1.toml").is_file():
            problems.append(f"server planning command is not indexed: {command}")
    for anchor in (
        "factorio.server_profile.v2", "StableInputFile", "open_no_follow", "revalidate", "credential_references",
        "server-settings.json", "map-gen-settings.json", "map-settings.json", "effective_launch_plan",
        "required_input_files", "expected_output_roots", "process_started", "network_socket_opened",
        "firewall_changed", "contains_execution_scripts", "contains_factorio_binary",
    ):
        if anchor not in source + profile_source:
            problems.append(f"server planning safety anchor is missing: {anchor}")
    for forbidden in ("CreateProcess", "ShellExecute", "connect(", "bind(", "firewall add"):
        if forbidden in source:
            problems.append(f"server planning enables forbidden execution or networking: {forbidden}")
    for proof in ("include-save", "execution_not_enabled", "password", "contains_factorio_binary", "world.zip"):
        if proof not in test:
            problems.append(f"server planning acceptance proof is missing: {proof}")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"server-plan-check: {problem}", file=sys.stderr)
        return 1
    print("server-plan-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
