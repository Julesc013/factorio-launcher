# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_ROOT = ROOT / "tests" / "golden" / "commands"

REQUIRED_GOLDENS = {
    "product.inspect.success.json": {"command": "product.inspect"},
    "command_graph.inspect.success.json": {"command": "command_graph.inspect"},
    "diagnostics.report.success.json": {"command": "diagnostics.report"},
    "diagnostics.export.success.json": {"command": "diagnostics.export"},
    "installs.import.success.json": {"command": "installs.import"},
    "installs.inspect.success.json": {"command": "installs.inspect"},
    "instances.create.success.json": {"command": "instances.create"},
    "launch.plan.success.json": {"command": "launch.plan"},
    "run.preview.success.json": {"command": "run.preview"},
    "launch_plan.preflight.success.json": {"command": "launch_plan.preflight"},
    "run.execute.refusal.json": {"command": "run.execute", "refusal_code": "isolation_not_proven"},
    "modsets.lock.success.json": {"command": "modsets.lock"},
    "modsets.export.success.json": {"command": "modsets.export"},
    "saves.backup.success.json": {"command": "saves.backup"},
    "instance.export.success.json": {"command": "instance.export"},
    "instance.import.success.json": {"command": "instance.import"},
    "installs.install.plan.refusal.json": {"command": "installs.install.plan", "refusal_code": "setup_plan_inputs_not_confirmed"},
    "installs.install.apply.refusal.json": {"command": "installs.install.apply", "refusal_code": "setup_apply_not_authorized"},
    "installs.repair.plan.refusal.json": {"command": "installs.repair.plan", "refusal_code": "setup_lifecycle_fixture_proof_required"},
    "mods.search.refusal.json": {"command": "mods.search", "refusal_code": "network_forbidden"},
    "servers.start.refusal.json": {"command": "servers.start", "refusal_code": "execution_not_enabled"},
    "dev.dump_data.refusal.json": {"command": "dev.dump_data", "refusal_code": "execution_not_enabled"},
}


def main() -> int:
    problems: list[str] = []
    for name, expected in REQUIRED_GOLDENS.items():
        path = GOLDEN_ROOT / name
        problems.extend(validate_golden(path, expected))
    problems.extend(validate_authoritative_preview_route())

    if problems:
        for problem in problems:
            print(f"alpha-vertical-slice-check: {problem}", file=sys.stderr)
        return 1
    print(f"alpha-vertical-slice-check: ok ({len(REQUIRED_GOLDENS)} goldens)")
    return 0


def validate_golden(path: Path, expected: dict[str, str]) -> list[str]:
    if not path.is_file():
        return [f"{path.relative_to(ROOT)}: missing required alpha golden"]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path.relative_to(ROOT)}: {exc}"]
    if not isinstance(data, dict):
        return [f"{path.relative_to(ROOT)}: golden output must be a JSON object"]

    problems: list[str] = []
    command = expected["command"]
    if data.get("command") != command:
        problems.append(f"{path.relative_to(ROOT)}: command must be {command}")
    if "schema" not in data:
        problems.append(f"{path.relative_to(ROOT)}: missing schema")

    refusal_code = expected.get("refusal_code")
    if refusal_code is not None:
        problems.extend(validate_refusal(path, data, refusal_code))
    else:
        if data.get("status") == "refused":
            problems.append(f"{path.relative_to(ROOT)}: success golden must not have refused status")
    return problems


def validate_authoritative_preview_route() -> list[str]:
    cli_path = ROOT / "apps" / "cli" / "command_dispatch.cpp"
    binding_path = ROOT / "runtime" / "factorio" / "binding" / "flb_api.c"
    cli_text = cli_path.read_text(encoding="utf-8")
    start = cli_text.find("int command_launch(const Options& options, bool run)")
    end = cli_text.find("int command_transfer(", start)
    if start < 0 or end < 0:
        return [f"{cli_path.relative_to(ROOT)}: cannot locate command_run body"]
    run_body = cli_text[start:end]
    problems: list[str] = []
    for anchor in ['call(options,', '"run.preview"']:
        if anchor not in run_body:
            problems.append(f"{cli_path.relative_to(ROOT)}: run preview is missing route anchor {anchor}")
    for forbidden in ["load_instance(", "load_install(", "build_launch_args(", "build_launch_plan_json("]:
        if forbidden in run_body:
            problems.append(f"{cli_path.relative_to(ROOT)}: run preview retains frontend backend behavior {forbidden}")

    binding_text = binding_path.read_text(encoding="utf-8")
    binding_text += (ROOT / "runtime/core/generated/command_catalog.h").read_text(encoding="utf-8")
    for anchor in ["ulk_command_descriptor_v2", '"run.preview"', '"launch_plan.preflight"']:
        if anchor not in binding_text:
            problems.append(f"{binding_path.relative_to(ROOT)}: missing authoritative descriptor anchor {anchor}")
    return problems


def validate_refusal(path: Path, data: dict, code: str) -> list[str]:
    problems: list[str] = []
    if data.get("status") != "refused":
        problems.append(f"{path.relative_to(ROOT)}: refusal golden must have status refused")
    refusal = data.get("refusal")
    if not isinstance(refusal, dict):
        return problems + [f"{path.relative_to(ROOT)}: refusal golden missing refusal object"]
    if refusal.get("code") != code:
        problems.append(f"{path.relative_to(ROOT)}: refusal code must be {code}")
    if not refusal.get("reason"):
        problems.append(f"{path.relative_to(ROOT)}: refusal must include reason")
    if "recoverable" not in refusal and "retryable" not in refusal:
        problems.append(f"{path.relative_to(ROOT)}: refusal must declare recoverable or retryable")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
