# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "contracts" / "command" / "frontend" / "frontend.required_commands.v1.toml"

EXPECTED_REQUIRED = {
    "help",
    "version",
    "doctor",
    "product.inspect",
    "command_graph.inspect",
    "installs.scan",
    "installs.import",
    "installs.inspect",
    "instances.list",
    "instances.create",
    "launch_plan.build",
    "launch_plan.preflight",
    "run.preview",
}

EXPECTED_OPTIONAL = {
    "diagnostics.export",
    "diagnostics.redact",
    "dev.bug_report",
    "mods.import",
    "mods.list",
    "mods.index",
    "mods.inspect",
    "mods.verify",
    "mods.explain",
    "modsets.lock",
    "modsets.verify",
    "modsets.export",
    "modsets.plan",
    "modsets.diff",
    "modsets.explain",
    "modsets.apply",
    "modsets.rollback",
    "saves.list",
    "saves.backup",
    "saves.clone",
    "instance.export",
    "instance.import",
    "instances.inspect",
    "instances.verify",
    "instances.diff",
    "instances.clone",
    "instances.rename",
    "instances.archive",
    "instances.restore",
    "snapshots.create",
    "snapshots.list",
    "snapshots.inspect",
    "snapshots.verify",
    "snapshots.diff",
    "snapshots.restore",
    "snapshots.retention.plan",
    "snapshots.retention.apply",
    "templates.list",
    "templates.inspect",
    "templates.validate",
    "profiles.list",
    "profiles.inspect",
    "profiles.create",
    "profiles.clone",
    "profiles.diff",
    "profiles.plan",
    "profiles.apply",
    "profiles.archive",
    "preferences.apply",
    "preferences.inspect",
    "preferences.plan",
    "preferences.reset.apply",
    "preferences.reset.plan",
    "preferences.validate",
    "workspace.recovery.inspect",
    "workspace.recovery.plan",
    "workspace.recovery.apply",
    "servers.create",
    "servers.list",
}

EXPECTED_UNAVAILABLE = {
    "dev.benchmark",
    "dev.dump_data",
    "dev.dump_icons",
    "dev.instrument_mod",
    "installs.install_version",
    "installs.repair",
    "installs.uninstall",
    "installs.verify",
    "mods.install",
    "mods.search",
    "mods.update",
    "package.verify",
    "run.execute",
    "servers.rcon",
    "servers.start",
    "servers.stop",
    "setup.preview",
}

EXPECTED_FRONTENDS = {
    "cli": "apps/cli",
    "tui": "apps/tui",
    "daemon": "apps/daemon",
    "windows.winforms": "apps/gui/windows/winforms",
    "windows.winui": "apps/gui/windows/winui",
    "macos.appkit": "apps/gui/macos/appkit",
    "macos.swiftui": "apps/gui/macos/swiftui",
    "linux.gtk": "apps/gui/linux/gtk",
    "linux.qt": "apps/gui/linux/qt",
}

ALLOWED_STATUS = {"implemented", "stubbed_with_refusal", "not_supported_with_reason"}


def main() -> int:
    problems: list[str] = []
    data, load_problems = load_contract()
    problems.extend(load_problems)
    if data:
        problems.extend(validate_contract(data))
    if problems:
        for problem in problems:
            print(f"frontend-contract-check: {problem}", file=sys.stderr)
        return 1
    print("frontend-contract-check: ok")
    return 0


def load_contract() -> tuple[dict[str, Any], list[str]]:
    try:
        with CONTRACT.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return {}, [f"{CONTRACT.relative_to(ROOT)}: {exc}"]
    return data, []


def validate_contract(data: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if data.get("schema") != "facman.frontend.required_commands.v1":
        problems.append("frontend contract schema must be facman.frontend.required_commands.v1")

    sets = data.get("sets", {})
    required = set(sets.get("required", []))
    optional = set(sets.get("optional", []))
    unavailable = set(sets.get("unavailable", []))
    if required != EXPECTED_REQUIRED:
        problems.append(f"required frontend commands mismatch: missing={sorted(EXPECTED_REQUIRED - required)} extra={sorted(required - EXPECTED_REQUIRED)}")
    if optional != EXPECTED_OPTIONAL:
        problems.append(f"optional frontend commands mismatch: missing={sorted(EXPECTED_OPTIONAL - optional)} extra={sorted(optional - EXPECTED_OPTIONAL)}")
    if unavailable != EXPECTED_UNAVAILABLE:
        problems.append(f"unavailable frontend commands mismatch: missing={sorted(EXPECTED_UNAVAILABLE - unavailable)} extra={sorted(unavailable - EXPECTED_UNAVAILABLE)}")
    overlaps = (required & optional) | (required & unavailable) | (optional & unavailable)
    if overlaps:
        problems.append(f"frontend command lifecycle sets must be disjoint: {sorted(overlaps)}")

    all_commands = required | optional | unavailable
    problems.extend(validate_command_descriptors(data.get("commands", []), required, optional, unavailable))
    problems.extend(validate_frontends(data.get("frontends", []), all_commands))
    for schema in [
        "contracts/schema/ui/frontend_capabilities.v1.schema.json",
        "contracts/schema/ui/frontend_command_surface.v1.schema.json",
    ]:
        if not (ROOT / schema).is_file():
            problems.append(f"missing frontend schema {schema}")
    if not (ROOT / "docs" / "architecture" / "frontend_contract.md").is_file():
        problems.append("missing docs/architecture/frontend_contract.md")
    return problems


def validate_command_descriptors(
    commands: Any,
    required: set[str],
    optional: set[str],
    unavailable: set[str],
) -> list[str]:
    problems: list[str] = []
    if not isinstance(commands, list):
        return ["commands must be an array of tables"]
    seen: set[str] = set()
    for command in commands:
        if not isinstance(command, dict):
            problems.append("each command descriptor must be a table")
            continue
        command_id = str(command.get("id", ""))
        seen.add(command_id)
        phase = command.get("phase")
        if command_id in required and phase != "required":
            problems.append(f"{command_id}: required command must have phase=required")
        if command_id in optional and phase != "optional":
            problems.append(f"{command_id}: optional command must have phase=optional")
        if command_id in unavailable and phase != "unavailable":
            problems.append(f"{command_id}: unavailable command must have phase=unavailable")
        for key in ["backend_id", "cli"]:
            if not command.get(key):
                problems.append(f"{command_id}: missing {key}")
    expected = required | optional | unavailable
    for command_id in sorted(expected - seen):
        problems.append(f"missing command descriptor {command_id}")
    for command_id in sorted(seen - expected):
        problems.append(f"unexpected command descriptor {command_id}")
    return problems


def validate_frontends(frontends: Any, all_commands: set[str]) -> list[str]:
    problems: list[str] = []
    if not isinstance(frontends, list):
        return ["frontends must be an array of tables"]
    seen: set[str] = set()
    for frontend in frontends:
        if not isinstance(frontend, dict):
            problems.append("each frontend descriptor must be a table")
            continue
        frontend_id = str(frontend.get("id", ""))
        seen.add(frontend_id)
        expected_path = EXPECTED_FRONTENDS.get(frontend_id)
        if expected_path is None:
            problems.append(f"unexpected frontend {frontend_id}")
            continue
        path = str(frontend.get("path", ""))
        if path != expected_path:
            problems.append(f"{frontend_id}: path must be {expected_path}")
        if not (ROOT / expected_path).is_dir():
            problems.append(f"{frontend_id}: frontend path does not exist: {expected_path}")
        commands = frontend.get("commands", {})
        if not isinstance(commands, dict):
            problems.append(f"{frontend_id}: commands must be a table")
            continue
        declared = set(commands)
        for command_id in sorted(all_commands - declared):
            problems.append(f"{frontend_id}: missing command status {command_id}")
        for command_id in sorted(declared - all_commands):
            problems.append(f"{frontend_id}: unexpected command status {command_id}")
        for command_id, status in commands.items():
            if status not in ALLOWED_STATUS:
                problems.append(f"{frontend_id}: {command_id} has invalid status {status!r}")
        default_refusal = str(frontend.get("default_refusal", ""))
        default_reason = str(frontend.get("default_reason", ""))
        refusals = frontend.get("refusals", {})
        reasons = frontend.get("reasons", {})
        for command_id, status in commands.items():
            if status == "stubbed_with_refusal" and not (default_refusal or (isinstance(refusals, dict) and refusals.get(command_id))):
                problems.append(f"{frontend_id}: {command_id} is stubbed but has no refusal code")
            if status == "not_supported_with_reason" and not (default_reason or (isinstance(reasons, dict) and reasons.get(command_id))):
                problems.append(f"{frontend_id}: {command_id} is not supported but has no reason")
    for frontend_id in sorted(set(EXPECTED_FRONTENDS) - seen):
        problems.append(f"missing frontend descriptor {frontend_id}")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
