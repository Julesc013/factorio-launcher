# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "contracts" / "policy" / "capabilities.v1.toml"
EFFECTS = ROOT / "contracts" / "policy" / "effects.v1.toml"
CATALOG = ROOT / "contracts" / "generated-index" / "command_catalog.v2.json"

REQUIRED_CAPABILITIES = {
    "install.discover",
    "install.reference.register",
    "install.model.inspect",
    "install.reconciliation.plan",
    "install.managed.plan",
    "install.managed.apply",
    "install.existing.inspect",
    "install.existing.adoption.plan",
    "install.existing.adoption.apply",
    "launch.preview",
    "launch.preflight",
    "launch.execute.instance_isolated",
    "launch.execute.hermetic",
    "process.execute",
    "network.mod_portal.read",
    "network.mod_portal.write",
    "credential.factorio.read",
    "release.sign",
    "release.publish",
}
ALLOWED_STATUS = {"available", "conditional", "backlog", "unavailable"}


def load_toml(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def validate(policy: dict, effects: set[str], commands: set[str]) -> list[str]:
    problems: list[str] = []
    if policy.get("schema") != "facman.capabilities.v1" or policy.get("version") != 1:
        problems.append("capability policy must use facman.capabilities.v1 version 1")
    records = policy.get("capability", [])
    if not isinstance(records, list):
        return problems + ["capability policy records must be an array"]
    ids = [str(record.get("id", "")) for record in records if isinstance(record, dict)]
    duplicates = sorted({value for value in ids if ids.count(value) > 1})
    if duplicates:
        problems.append(f"duplicate capability ids: {duplicates}")
    missing = sorted(REQUIRED_CAPABILITIES - set(ids))
    unexpected = sorted(set(ids) - REQUIRED_CAPABILITIES)
    if missing:
        problems.append(f"missing durable capabilities: {missing}")
    if unexpected:
        problems.append(f"unexpected durable capabilities: {unexpected}")
    for record in records:
        if not isinstance(record, dict):
            problems.append("capability record must be a table")
            continue
        capability_id = str(record.get("id", "<missing>"))
        if record.get("status") not in ALLOWED_STATUS:
            problems.append(f"{capability_id}: invalid status {record.get('status')!r}")
        if not str(record.get("domain", "")) or not str(record.get("description", "")):
            problems.append(f"{capability_id}: domain and description are required")
        required_effects = record.get("required_effects", [])
        if not isinstance(required_effects, list) or not required_effects:
            problems.append(f"{capability_id}: required_effects must be a non-empty array")
        else:
            unknown_effects = sorted(set(map(str, required_effects)) - effects)
            if unknown_effects:
                problems.append(f"{capability_id}: unknown effects {unknown_effects}")
        mapped_commands = record.get("commands", [])
        if not isinstance(mapped_commands, list):
            problems.append(f"{capability_id}: commands must be an array")
        else:
            unknown_commands = sorted(set(map(str, mapped_commands)) - commands)
            if unknown_commands:
                problems.append(f"{capability_id}: unknown commands {unknown_commands}")
    return problems


def validate_execution_foundation(policy: dict, catalog: dict) -> list[str]:
    problems: list[str] = []
    commands = {
        str(item.get("command_id", "")): item
        for item in catalog.get("commands", [])
        if isinstance(item, dict)
    }
    execute = commands.get("run.execute", {})
    expected_effects = {"workspace_read", "workspace_write", "process_execute"}
    if set(map(str, execute.get("effects", []))) != expected_effects:
        problems.append("run.execute must declare its exact execution and audit effect set")
    if not execute.get("executes_process") or not execute.get("mutates_workspace"):
        problems.append("run.execute process and workspace mutation truth must be explicit")
    if execute.get("cli") != "facman play <instance-id> --json":
        problems.append("facman play must be the preferred run.execute CLI spelling")
    if execute.get("compatibility_cli") != "facman run <instance-id> --execute --json":
        problems.append("run --execute compatibility spelling must remain declared")
    if execute.get("result_schema") != "contracts/schema/factorio/factorio_launch_session.v1.schema.json":
        problems.append("run.execute must bind the versioned launch-session result")
    capabilities = {
        str(item.get("id", "")): item
        for item in policy.get("capability", [])
        if isinstance(item, dict)
    }
    if capabilities.get("process.execute", {}).get("status") != "conditional":
        problems.append("process.execute must describe the conditional internal foundation")
    for capability in ("launch.execute.instance_isolated", "launch.execute.hermetic"):
        if capabilities.get(capability, {}).get("status") != "unavailable":
            problems.append(f"{capability} must remain unavailable before its real-play gate")
    return problems


def main() -> int:
    policy = load_toml(POLICY)
    effects = set(load_toml(EFFECTS).get("effects", {}))
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    commands = {str(item.get("command_id", "")) for item in catalog.get("commands", [])}
    problems = validate(policy, effects, commands)
    problems.extend(validate_execution_foundation(policy, catalog))
    if problems:
        for problem in problems:
            print(f"capability-policy-check: {problem}", file=sys.stderr)
        return 1
    print("capability-policy-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
