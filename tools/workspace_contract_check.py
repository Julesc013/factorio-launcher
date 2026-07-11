# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE_SCHEMA = ROOT / "contracts" / "schema" / "factorio" / "factorio_workspace.v1.schema.json"
INSTANCE_SCHEMA = ROOT / "contracts" / "schema" / "factorio" / "factorio_instance_root.v1.schema.json"
PRODUCT_DOC = ROOT / "docs" / "product" / "workspace_model.md"
ARCH_DOC = ROOT / "docs" / "architecture" / "workspace_model.md"

WORKSPACE_TERMS = [
    "workspace.v1.json",
    "installs/",
    "refs/",
    "setup_state_refs/",
    "instances/",
    "profiles/",
    "modsets/",
    "accounts/",
    "cache/",
    "audit/",
    "diagnostics/",
    "exports/",
]

INSTANCE_TERMS = [
    "instance.v1.json",
    "config/",
    "mods/",
    "saves/",
    "scenarios/",
    "script-output/",
    "logs/",
    "crash/",
    "locks/",
    "cache/",
]


def main() -> int:
    problems: list[str] = []
    problems.extend(validate_schema(WORKSPACE_SCHEMA, "facman.factorio.workspace.v1"))
    problems.extend(validate_schema(INSTANCE_SCHEMA, "facman.factorio.instance_root.v1"))
    problems.extend(validate_doc(PRODUCT_DOC, WORKSPACE_TERMS + INSTANCE_TERMS))
    problems.extend(validate_doc(ARCH_DOC, WORKSPACE_TERMS + INSTANCE_TERMS))

    if problems:
        for problem in problems:
            print(f"workspace-contract-check: {problem}", file=sys.stderr)
        return 1
    print("workspace-contract-check: ok")
    return 0


def validate_schema(path: Path, schema_const: str) -> list[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path.relative_to(ROOT)}: {exc}"]
    problems: list[str] = []
    if data.get("type") != "object":
        problems.append(f"{path.relative_to(ROOT)}: schema root must be object")
    schema_property = data.get("properties", {}).get("schema", {})
    if schema_property.get("const") != schema_const:
        problems.append(f"{path.relative_to(ROOT)}: schema const must be {schema_const}")
    required = data.get("required", [])
    if "schema" not in required:
        problems.append(f"{path.relative_to(ROOT)}: schema must be required")
    return problems


def validate_doc(path: Path, terms: list[str]) -> list[str]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"{path.relative_to(ROOT)}: {exc}"]
    missing = [term for term in terms if term not in text]
    if missing:
        return [f"{path.relative_to(ROOT)}: missing layout terms {missing}"]
    return []


if __name__ == "__main__":
    raise SystemExit(main())
