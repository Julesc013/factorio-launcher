# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMAND_ROOT = ROOT / "contracts" / "command" / "factorio"
EFFECTS_POLICY = ROOT / "contracts" / "policy" / "effects.v1.toml"

EXPECTED_COMMANDS = {
    "capabilities.inspect",
    "product.inspect",
    "factorio.product.inspect",
    "doctor.run",
    "doctor.explain",
    "installs.scan",
    "installs.import",
    "installs.inspect",
    "installs.describe",
    "installs.reconcile.plan",
    "install_refs.list",
    "instances.create",
    "instances.describe",
    "instances.inspect",
    "instances.readiness",
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
    "instance.list",
    "launch.plan",
    "launch_plan.preflight",
    "launch_plan.explain",
    "run.preview",
    "run.execute",
    "setup.preview",
    "setup.operation",
    "utility.operation",
    "mods.import",
    "mods.list",
    "mods.index",
    "mods.inspect",
    "mods.verify",
    "mods.explain",
    "modsets.lock",
    "modsets.verify",
    "modsets.export",
    "modsets.explain",
    "modsets.plan",
    "modsets.diff",
    "modsets.apply",
    "modsets.rollback",
    "onboarding.plan",
    "saves.list",
    "saves.backup",
    "saves.clone",
    "saves.index",
    "saves.inspect",
    "saves.verify",
    "saves.associate",
    "saves.diff",
    "saves.retention.plan",
    "saves.retention.apply",
    "instance.export",
    "instance.import",
    "workspace.recovery.inspect",
    "workspace.recovery.plan",
    "workspace.recovery.apply",
    "workspace.migration.inspect",
    "workspace.migration.plan",
    "workspace.migration.apply",
    "workspace.paths",
    "workspace.status",
    "diagnostics.export",
    "diagnostics.redact",
    "package.verify",
    "preferences.apply",
    "preferences.inspect",
    "preferences.plan",
    "preferences.reset.apply",
    "preferences.reset.plan",
    "preferences.validate",
    "installs.install_version",
    "installs.install.plan",
    "installs.install.apply",
    "installs.verify",
    "installs.repair",
    "installs.repair.plan",
    "installs.repair.apply",
    "installs.move.plan",
    "installs.move.apply",
    "installs.uninstall",
    "installs.uninstall.plan",
    "installs.uninstall.apply",
    "installs.recovery.inspect",
    "installs.recovery.apply",
    "mods.search",
    "mods.install",
    "mods.update",
    "servers.list",
    "servers.create",
    "servers.inspect",
    "servers.validate",
    "servers.plan",
    "servers.diff",
    "servers.export",
    "servers.start",
    "servers.stop",
    "servers.rcon",
    "dev.bug_report",
    "dev.dump_data",
    "dev.dump_icons",
    "dev.benchmark",
    "dev.instrument_mod",
}

COMMAND_PATTERN = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_-]+)+$")


def main() -> int:
    problems: list[str] = []
    allowed_effects, effects_problems = load_effects_policy()
    problems.extend(effects_problems)
    contracts = sorted(path for path in COMMAND_ROOT.glob("*.v1.toml") if path.name != "index.v1.toml")
    seen: set[str] = set()
    for path in contracts:
        contract, contract_problems = load_contract(path)
        problems.extend(contract_problems)
        if contract_problems:
            continue
        command_id = contract["command_id"]
        seen.add(command_id)
        problems.extend(validate_contract(path, contract, allowed_effects))

    missing = EXPECTED_COMMANDS - seen
    extra = seen - EXPECTED_COMMANDS
    for command_id in sorted(missing):
        problems.append(f"missing command contract {command_id}")
    for command_id in sorted(extra):
        problems.append(f"unexpected command contract {command_id}")

    if problems:
        for problem in problems:
            print(f"command-contract-check: {problem}", file=sys.stderr)
        return 1
    print(f"command-contract-check: ok ({len(seen)} commands)")
    return 0


def load_contract(path: Path) -> tuple[dict, list[str]]:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return {}, [f"{path.relative_to(ROOT)}: {exc}"]
    if not isinstance(data, dict):
        return {}, [f"{path.relative_to(ROOT)}: contract must be a TOML table"]
    return data, []


def load_effects_policy() -> tuple[set[str], list[str]]:
    try:
        with EFFECTS_POLICY.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return set(), [f"{EFFECTS_POLICY.relative_to(ROOT)}: {exc}"]
    effects = data.get("effects", {})
    if not isinstance(effects, dict) or not effects:
        return set(), [f"{EFFECTS_POLICY.relative_to(ROOT)}: effects table must be non-empty"]
    return set(effects), []


def validate_contract(path: Path, contract: dict, allowed_effects: set[str]) -> list[str]:
    problems: list[str] = []
    required = [
        "command_id",
        "cli",
        "effects",
        "request_schema",
        "response_schema",
        "result_schema",
        "refusal_schema",
        "diagnostic_schema",
        "dry_run_default",
        "executes_process",
        "mutates_workspace",
        "golden_refusal",
    ]
    for key in required:
        if key not in contract:
            problems.append(f"{path.relative_to(ROOT)}: missing {key}")
    if problems:
        return problems

    command_id = contract["command_id"]
    if not isinstance(command_id, str) or not COMMAND_PATTERN.match(command_id):
        problems.append(f"{path.relative_to(ROOT)}: invalid command_id {command_id!r}")
    if path.name != f"{command_id}.v1.toml":
        problems.append(f"{path.relative_to(ROOT)}: filename must match command_id")

    for key in ["request_schema", "response_schema", "result_schema", "refusal_schema", "diagnostic_schema"]:
        referenced = ROOT / contract[key]
        if not referenced.is_file():
            problems.append(f"{path.relative_to(ROOT)}: {key} does not exist: {contract[key]}")
    if not str(contract["request_schema"]).startswith("contracts/schema/command/"):
        problems.append(f"{path.relative_to(ROOT)}: request_schema must be command-specific and generated")

    availability = contract.get("availability", "implemented")
    if availability not in {"implemented", "unavailable_until_isolation_proof", "unavailable_until_gateway"}:
        problems.append(f"{path.relative_to(ROOT)}: unsupported availability {availability!r}")
    if availability == "implemented" and "golden_success" not in contract:
        problems.append(f"{path.relative_to(ROOT)}: implemented command missing golden_success")

    golden_keys = ["golden_refusal"]
    if "golden_success" in contract:
        golden_keys.insert(0, "golden_success")
    for key in golden_keys:
        referenced = ROOT / contract[key]
        if not referenced.is_file():
            problems.append(f"{path.relative_to(ROOT)}: {key} does not exist: {contract[key]}")
            continue
        problems.extend(validate_golden(command_id, key, referenced))

    for key in ["dry_run_default", "executes_process", "mutates_workspace"]:
        if not isinstance(contract[key], bool):
            problems.append(f"{path.relative_to(ROOT)}: {key} must be boolean")
    effects = contract["effects"]
    if not isinstance(effects, list) or not effects:
        problems.append(f"{path.relative_to(ROOT)}: effects must be a non-empty array")
    else:
        unknown = sorted(effect for effect in effects if effect not in allowed_effects)
        if unknown:
            problems.append(f"{path.relative_to(ROOT)}: unknown effects {unknown}")
        if "none" in effects and len(effects) != 1:
            problems.append(f"{path.relative_to(ROOT)}: none effect must be used alone")
        if contract["executes_process"] and "process_execute" not in effects:
            problems.append(f"{path.relative_to(ROOT)}: process commands must declare process_execute")
        if contract["mutates_workspace"] and "workspace_write" not in effects:
            problems.append(f"{path.relative_to(ROOT)}: workspace mutation commands must declare workspace_write")
    return problems


def validate_golden(command_id: str, key: str, path: Path) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path.relative_to(ROOT)}: {exc}"]
    problems: list[str] = []
    if not isinstance(data, dict):
        return [f"{path.relative_to(ROOT)}: golden output must be an object"]
    if "schema" not in data:
        problems.append(f"{path.relative_to(ROOT)}: missing schema")
    if data.get("command") != command_id:
        problems.append(f"{path.relative_to(ROOT)}: command must be {command_id}")
    if key == "golden_refusal":
        if data.get("status") != "refused":
            problems.append(f"{path.relative_to(ROOT)}: refusal golden must have status refused")
        if "refusal" not in data:
            problems.append(f"{path.relative_to(ROOT)}: refusal golden missing refusal object")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
