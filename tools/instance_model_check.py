# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MODEL_SOURCE = ROOT / "runtime/factorio/instance/flb_factorio_instance_model.cpp"
MODEL_HEADER = ROOT / "runtime/factorio/instance/flb_factorio_instance_model.h"
CLI_TEST = ROOT / "tests/test_cli.py"
NATIVE_TEST = ROOT / "tests/native/flb_factorio_instance_model_smoke.cpp"
COMMAND_ROOT = ROOT / "contracts/command/factorio"
SCHEMA_ROOT = ROOT / "contracts/schema/factorio"


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _nested_property_names(value: Any) -> set[str]:
    names: set[str] = set()
    if isinstance(value, dict):
        properties = value.get("properties")
        if isinstance(properties, dict):
            names.update(str(key) for key in properties)
        for child in value.values():
            names.update(_nested_property_names(child))
    elif isinstance(value, list):
        for child in value:
            names.update(_nested_property_names(child))
    return names


def validate() -> list[str]:
    problems: list[str] = []
    required_files = (
        MODEL_SOURCE,
        MODEL_HEADER,
        CLI_TEST,
        NATIVE_TEST,
        SCHEMA_ROOT / "factorio_instance_spec.v1.schema.json",
        SCHEMA_ROOT / "factorio_instance_binding.v1.schema.json",
        SCHEMA_ROOT / "factorio_instance_readiness.v1.schema.json",
        SCHEMA_ROOT / "factorio_instance_view.v1.schema.json",
        SCHEMA_ROOT / "factorio_launch_intent.v1.schema.json",
    )
    for path in required_files:
        if not path.is_file():
            problems.append(f"missing Gate 2 artifact: {path.relative_to(ROOT)}")
    if problems:
        return problems

    source = MODEL_SOURCE.read_text(encoding="utf-8")
    header = MODEL_HEADER.read_text(encoding="utf-8")
    cli_test = CLI_TEST.read_text(encoding="utf-8")
    native_test = NATIVE_TEST.read_text(encoding="utf-8")

    for command in ("instances.describe", "instances.readiness"):
        contract_path = COMMAND_ROOT / f"{command}.v1.toml"
        if not contract_path.is_file():
            problems.append(f"missing Gate 2 command contract: {command}")
            continue
        contract = tomllib.loads(contract_path.read_text(encoding="utf-8"))
        if contract.get("effects") != ["workspace_read"]:
            problems.append(f"{command}: effects must remain exactly workspace_read")
        for field in ("executes_process", "mutates_workspace"):
            if contract.get(field) is not False:
                problems.append(f"{command}: {field} must remain false")
        if contract.get("availability") != "implemented":
            problems.append(f"{command}: read-only projection must remain implemented")
        for golden_key in ("golden_success", "golden_refusal"):
            golden = contract.get(golden_key)
            if not isinstance(golden, str) or not (ROOT / golden).is_file():
                problems.append(f"{command}: missing {golden_key}")

    legacy_inspect = tomllib.loads(
        (COMMAND_ROOT / "instances.inspect.v1.toml").read_text(encoding="utf-8")
    )
    if legacy_inspect.get("response_schema") != (
        "contracts/schema/factorio/factorio_instance_inspection.v1.schema.json"
    ):
        problems.append("instances.inspect compatibility response changed during Gate 2")

    spec_schema = _load_json(SCHEMA_ROOT / "factorio_instance_spec.v1.schema.json")
    spec_properties = _nested_property_names(spec_schema)
    forbidden_spec_properties = {
        "path",
        "instance_root",
        "read_data_path",
        "write_data_path",
        "mod_root_path",
        "credential_value",
        "access_token",
    }
    leaked = forbidden_spec_properties & spec_properties
    if leaked:
        problems.append(f"portable InstanceSpec contains machine-local or secret fields: {sorted(leaked)}")
    spec_top = spec_schema.get("properties", {})
    if spec_top.get("default_launch_intent", {}).get("const") != "menu":
        problems.append("InstanceSpec default launch intent must remain menu")

    binding_schema = _load_json(SCHEMA_ROOT / "factorio_instance_binding.v1.schema.json")
    binding_properties = binding_schema.get("properties", {})
    for name in (
        "selected_installation_id",
        "installation_evidence_digest",
        "instance_root",
        "effective_config",
        "read_data_path",
        "write_data_path",
        "mod_root_path",
        "binding_dependencies",
        "binding_digest",
    ):
        if name not in binding_properties:
            problems.append(f"InstanceBinding lacks machine-local evidence field: {name}")

    readiness_schema = _load_json(SCHEMA_ROOT / "factorio_instance_readiness.v1.schema.json")
    readiness_properties = readiness_schema.get("properties", {})
    if readiness_properties.get("launch_intent", {}).get("const") != "menu":
        problems.append("Gate 2 readiness must remain menu-intent only")
    for field in (
        "mutation_executed",
        "preparation_executed",
        "execution_started",
        "permit_issued",
        "credential_accessed",
        "network_accessed",
        "preparation_available",
        "execution_available",
    ):
        if readiness_properties.get(field, {}).get("const") is not False:
            problems.append(f"readiness authority boundary is not contractual: {field}=false")

    view_schema = _load_json(SCHEMA_ROOT / "factorio_instance_view.v1.schema.json")
    view_properties = view_schema.get("properties", {})
    for field in ("instance_spec", "instance_binding", "instance_readiness", "view_digest"):
        if field not in view_properties:
            problems.append(f"InstanceView omits canonical component: {field}")

    for anchor in (
        'request.launch_intent != "menu"',
        '"unsupported_launch_intent"',
        '"factorio.instance_spec.v1"',
        '"factorio.instance_binding.v1"',
        '"factorio.instance_readiness.v1"',
        '"factorio.instance_view.v1"',
        '"real_play_gate_not_passed"',
        '"permit_issued", false',
        '"execution_started", false',
        '"credential_accessed", false',
        '"network_accessed", false',
        "open_no_follow(path)",
        "input.revalidate()",
    ):
        if anchor not in source:
            problems.append(f"instance model safety or contract anchor missing: {anchor}")

    for forbidden in (
        "create_directories(",
        "write_text_new_atomic(",
        "write_binary_new_atomic(",
        "remove_all(",
        "copy_file(",
        "rename(",
        "TransactionSession::begin(",
        "CreateProcess",
        "ShellExecute",
        "std::system(",
    ):
        if forbidden in source:
            problems.append(f"read-only instance projection contains mutating/execution primitive: {forbidden}")

    if "ProjectionRequest" not in header or 'launch_intent = "menu"' not in header:
        problems.append("typed projection request does not default explicitly to menu")

    combined_tests = cli_test + "\n" + native_test
    for anchor in (
        "instance_projection",
        "unsupported_launch_intent",
        "real_play_gate_not_passed",
        "mutation_executed",
        "permit_issued",
        "missing_workspace",
        "facman.transport_request.v1",
    ):
        if anchor not in combined_tests:
            problems.append(f"Gate 2 proof anchor missing from tests: {anchor}")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"instance-model-check: {problem}", file=sys.stderr)
        return 1
    print("instance-model-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
