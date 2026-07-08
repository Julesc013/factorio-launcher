from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMAND_ROOT = ROOT / "contracts" / "command" / "factorio"

EXPECTED_COMMANDS = {
    "product.inspect",
    "doctor.run",
    "installs.scan",
    "installs.import",
    "instances.create",
    "launch.plan",
    "run.preview",
    "run.execute",
    "modsets.lock",
    "saves.backup",
    "export.instance",
    "import.instance",
}

COMMAND_PATTERN = re.compile(r"^[a-z0-9]+(\.[a-z0-9-]+)+$")


def main() -> int:
    problems: list[str] = []
    contracts = sorted(path for path in COMMAND_ROOT.glob("*.v1.toml") if path.name != "README.md")
    seen: set[str] = set()
    for path in contracts:
        contract, contract_problems = load_contract(path)
        problems.extend(contract_problems)
        if contract_problems:
            continue
        command_id = contract["command_id"]
        seen.add(command_id)
        problems.extend(validate_contract(path, contract))

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


def validate_contract(path: Path, contract: dict) -> list[str]:
    problems: list[str] = []
    required = [
        "command_id",
        "cli",
        "request_schema",
        "response_schema",
        "result_schema",
        "refusal_schema",
        "diagnostic_schema",
        "dry_run_default",
        "executes_process",
        "mutates_workspace",
        "golden_success",
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

    for key in ["golden_success", "golden_refusal"]:
        referenced = ROOT / contract[key]
        if not referenced.is_file():
            problems.append(f"{path.relative_to(ROOT)}: {key} does not exist: {contract[key]}")
            continue
        problems.extend(validate_golden(command_id, key, referenced))

    for key in ["dry_run_default", "executes_process", "mutates_workspace"]:
        if not isinstance(contract[key], bool):
            problems.append(f"{path.relative_to(ROOT)}: {key} must be boolean")
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
