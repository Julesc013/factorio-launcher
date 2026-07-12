# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "runtime/factorio/profiles/flb_factorio_profiles.cpp"
HEADER = ROOT / "runtime/factorio/profiles/flb_factorio_profiles.h"
INDEX = ROOT / "contracts/command/factorio/index.v1.toml"
TEST = ROOT / "tests/test_profiles_templates.py"


def validate() -> list[str]:
    problems: list[str] = []
    source = SOURCE.read_text(encoding="utf-8")
    header = HEADER.read_text(encoding="utf-8")
    launch = (ROOT / "runtime/factorio/launch/flb_factorio_launch_plan.cpp").read_text(encoding="utf-8")
    index = INDEX.read_text(encoding="utf-8")
    test = TEST.read_text(encoding="utf-8")
    commands = (
        "templates.list", "templates.inspect", "templates.validate", "profiles.list", "profiles.inspect",
        "profiles.create", "profiles.clone", "profiles.diff", "profiles.plan", "profiles.apply", "profiles.archive",
    )
    for command in commands:
        if command not in index or not (ROOT / "contracts/command/factorio" / f"{command}.v1.toml").is_file():
            problems.append(f"profile/template command is not indexed: {command}")
    for model in (
        "factorio.instance_template.v1", "factorio.launch_profile.v1", "factorio.instance_overrides.v1",
        "factorio.effective_profile.v1",
    ):
        if model not in source:
            problems.append(f"customization model is missing: {model}")
    for anchor in (
        "safe_arguments", "--config", "--mod-directory", "arbitrary_execution", "execution_enabled",
        "profile_plan_and_reserved_argument_policy_validated", "plan_backup_stage", "owned_trash_move_no_delete",
        "permanent_delete", "profile_shipped_immutable", "effective_profile_for_instance",
    ):
        combined = source + header + launch
        if anchor not in combined:
            problems.append(f"profile safety anchor is missing: {anchor}")
    for forbidden in ("std::system", "CreateProcess", "ShellExecute", "credential_value"):
        if forbidden in source:
            problems.append(f"customization source contains forbidden authority: {forbidden}")
    for proof in ("--config", "--low-vram", "execution_enabled", "instance-overrides.v1.json", "permanent_delete"):
        if proof not in test:
            problems.append(f"profile acceptance proof is missing: {proof}")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"profile-template-check: {problem}", file=sys.stderr)
        return 1
    print("profile-template-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
