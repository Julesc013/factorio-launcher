# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "contracts/generated-index/frontend_command_catalog.v1.json"

PLAN_COMMANDS = {
    "installs.install.plan",
    "installs.repair.plan",
    "installs.move.plan",
    "installs.uninstall.plan",
}
APPLY_COMMANDS = {
    "installs.install.apply",
    "installs.repair.apply",
    "installs.move.apply",
    "installs.uninstall.apply",
    "installs.recovery.apply",
}
READ_COMMANDS = {"installs.verify", "installs.recovery.inspect"}
LEGACY_FRONTEND_COMMANDS = {
    "installs.install_version",
    "installs.repair",
    "installs.uninstall",
}


def validate() -> list[str]:
    problems: list[str] = []
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    commands = {item["runtime_id"]: item for item in data.get("commands", [])}
    expected = PLAN_COMMANDS | APPLY_COMMANDS | READ_COMMANDS
    missing = sorted(expected - commands.keys())
    if missing:
        problems.append(f"generated frontend catalog is missing setup workflows: {missing}")
    leaked = sorted(LEGACY_FRONTEND_COMMANDS & commands.keys())
    if leaked:
        problems.append(f"legacy setup aliases leaked into generated frontends: {leaked}")

    for command_id in sorted(expected & commands.keys()):
        command = commands[command_id]
        if command.get("availability") != "unavailable_until_gateway":
            problems.append(f"{command_id}: ordinary lifecycle authority must remain unavailable")
        if command.get("executes_process"):
            problems.append(f"{command_id}: setup workflows must never execute Factorio")
        effects = set(command.get("effects", []))
        if effects - {"setup_preview", "workspace_write"}:
            problems.append(f"{command_id}: setup workflow declares an out-of-scope effect")

    for command_id in sorted(PLAN_COMMANDS & commands.keys()):
        if commands[command_id].get("risk_tier") != "read_only":
            problems.append(f"{command_id}: planning must remain read-only")

    for command_id in sorted(APPLY_COMMANDS & commands.keys()):
        command = commands[command_id]
        if command.get("risk_tier") != "persistent_local_write":
            problems.append(f"{command_id}: apply must be classified as a persistent local write")
        fields = {field["name"]: field for field in command.get("request_fields", [])}
        if fields.get("plan_id", {}).get("type") != "identifier":
            problems.append(f"{command_id}: apply must consume an identified reviewed plan")
        if fields.get("plan_digest", {}).get("type") != "sha256":
            problems.append(f"{command_id}: apply must consume the reviewed plan digest")
        confirmation = fields.get("confirmation", {})
        if confirmation.get("choices") != ["APPLY"] or not confirmation.get("required"):
            problems.append(f"{command_id}: apply must require exact APPLY confirmation")
        options = {item["name"]: item for item in command.get("cli_grammar", {}).get("options", [])}
        if options.get("--confirm", {}).get("value") != "APPLY":
            problems.append(f"{command_id}: CLI grammar must expose the APPLY value")

    install_fields = {
        field["name"] for field in commands.get("installs.install.plan", {}).get("request_fields", [])
        if field.get("required")
    }
    if install_fields != {"version", "archive", "target_root", "install_id"}:
        problems.append("installs.install.plan must bind version, archive, target, and install identity")

    cli = (ROOT / "apps/cli/command_dispatch.cpp").read_text(encoding="utf-8")
    handler = (ROOT / "runtime/factorio/application/handlers/setup.cpp").read_text(encoding="utf-8")
    for command_id in sorted(expected):
        if f'"{command_id}"' not in cli + handler:
            problems.append(f"{command_id}: explicit CLI/application route is missing")
    if "setup_apply_not_authorized" not in handler:
        problems.append("setup apply authority guard is missing")

    run_execute = commands.get("run.execute")
    if run_execute is None or run_execute.get("availability_refusal_code") != "isolation_not_proven":
        problems.append("run.execute isolation quarantine changed during setup workflow work")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"setup-workflow-check: {problem}", file=sys.stderr)
        return 1
    print(
        "setup-workflow-check: ok "
        f"({len(PLAN_COMMANDS)} plans, {len(APPLY_COMMANDS)} guarded applies, {len(READ_COMMANDS)} reads)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
