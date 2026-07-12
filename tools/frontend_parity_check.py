# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_CONTRACT = ROOT / "contracts" / "command" / "frontend" / "frontend.required_commands.v1.toml"
SURFACE_CONTRACT = ROOT / "contracts" / "command" / "frontend" / "frontend_surface.v1.toml"
GOLDEN = ROOT / "tests" / "golden" / "frontend" / "frontend_surface_status.v1.json"


def main() -> int:
    problems: list[str] = []
    required_contract, required_problems = load_toml(REQUIRED_CONTRACT)
    surface_contract, surface_problems = load_toml(SURFACE_CONTRACT)
    problems.extend(required_problems)
    problems.extend(surface_problems)
    if problems:
        return report(problems)

    problems.extend(validate_surface(required_contract, surface_contract))
    problems.extend(validate_golden())
    return report(problems)


def load_toml(path: Path) -> tuple[dict[str, Any], list[str]]:
    try:
        with path.open("rb") as handle:
            return tomllib.load(handle), []
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return {}, [f"{path.relative_to(ROOT)}: {exc}"]


def validate_surface(required_contract: dict[str, Any], surface_contract: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if surface_contract.get("schema") != "facman.frontend.surface.v1":
        problems.append(f"{SURFACE_CONTRACT.relative_to(ROOT)}: invalid schema")
    if surface_contract.get("source_contract") != str(REQUIRED_CONTRACT.relative_to(ROOT)).replace("\\", "/"):
        problems.append(f"{SURFACE_CONTRACT.relative_to(ROOT)}: source_contract must point to required command contract")

    frontends = {
        str(frontend.get("id")): frontend
        for frontend in required_contract.get("frontends", [])
        if isinstance(frontend, dict)
    }
    required_commands = set(required_contract.get("sets", {}).get("required", []))
    optional_commands = set(required_contract.get("sets", {}).get("optional", []))
    unavailable_commands = set(required_contract.get("sets", {}).get("unavailable", []))

    for group in surface_contract.get("parity_group", []):
        if not isinstance(group, dict):
            problems.append(f"{SURFACE_CONTRACT.relative_to(ROOT)}: parity_group entries must be tables")
            continue
        group_id = str(group.get("id", ""))
        group_frontends = [str(frontend_id) for frontend_id in group.get("frontends", [])]
        for frontend_id in group_frontends:
            if frontend_id not in frontends:
                problems.append(f"{SURFACE_CONTRACT.relative_to(ROOT)}: group {group_id} unknown frontend {frontend_id}")
        if group_id == "native_shell_proof":
            problems.extend(
                validate_native_shell_group(
                    group,
                    frontends,
                    required_commands,
                    optional_commands,
                    unavailable_commands,
                )
            )

    proof_requirements = set(surface_contract.get("proof_requirements", []))
    for requirement in ["command_graph", "result_shape", "refusal_shape", "effect_risk"]:
        if requirement not in proof_requirements:
            problems.append(f"{SURFACE_CONTRACT.relative_to(ROOT)}: missing proof requirement {requirement}")
    return problems


def validate_native_shell_group(
    group: dict[str, Any],
    frontends: dict[str, dict[str, Any]],
    required_commands: set[str],
    optional_commands: set[str],
    unavailable_commands: set[str],
) -> list[str]:
    problems: list[str] = []
    group_frontends = [str(frontend_id) for frontend_id in group.get("frontends", [])]
    if set(group_frontends) != {"windows.winforms", "macos.appkit"}:
        problems.append("native_shell_proof must compare windows.winforms and macos.appkit")
        return problems

    expected_required = group.get("required_status")
    expected_optional = group.get("optional_status")
    expected_unavailable = group.get("unavailable_status")
    baseline: dict[str, str] | None = None
    for frontend_id in group_frontends:
        commands = frontends[frontend_id].get("commands", {})
        if not isinstance(commands, dict):
            problems.append(f"{frontend_id}: commands must be a table")
            continue
        for command_id in sorted(required_commands):
            if commands.get(command_id) != expected_required:
                problems.append(f"{frontend_id}: {command_id} must be {expected_required}")
        for command_id in sorted(optional_commands):
            if commands.get(command_id) != expected_optional:
                problems.append(f"{frontend_id}: {command_id} must be {expected_optional}")
        for command_id in sorted(unavailable_commands):
            if commands.get(command_id) != expected_unavailable:
                problems.append(f"{frontend_id}: {command_id} must be {expected_unavailable}")
        comparable = {command_id: str(status) for command_id, status in commands.items()}
        if baseline is None:
            baseline = comparable
        elif comparable != baseline:
            problems.append("native shell command statuses must match between WinForms and AppKit")
    return problems


def validate_golden() -> list[str]:
    try:
        data = json.loads(GOLDEN.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{GOLDEN.relative_to(ROOT)}: {exc}"]
    problems: list[str] = []
    if data.get("schema") != "facman.frontend_surface_status.v1":
        problems.append(f"{GOLDEN.relative_to(ROOT)}: invalid schema")
    shell = data.get("native_shell_proof", {})
    if shell.get("frontends") != ["windows.winforms", "macos.appkit"]:
        problems.append(f"{GOLDEN.relative_to(ROOT)}: native shell proof frontends changed")
    if shell.get("required_status") != "implemented":
        problems.append(f"{GOLDEN.relative_to(ROOT)}: native shell required status must be implemented")
    if shell.get("optional_status") != "implemented":
        problems.append(f"{GOLDEN.relative_to(ROOT)}: native shell optional status must be implemented")
    if shell.get("unavailable_status") != "not_supported_with_reason":
        problems.append(f"{GOLDEN.relative_to(ROOT)}: native shell unavailable status must be not_supported_with_reason")
    return problems


def report(problems: list[str]) -> int:
    if problems:
        for problem in problems:
            print(f"frontend-parity-check: {problem}", file=sys.stderr)
        return 1
    print("frontend-parity-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
