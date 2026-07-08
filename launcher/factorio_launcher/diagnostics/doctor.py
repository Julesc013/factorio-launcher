from __future__ import annotations

import json
from pathlib import Path

from factorio_launcher.binding.product_manifest import load_product_manifest
from factorio_launcher.binding.validation import validate_product_manifest
from factorio_launcher.core.config import factorio_schema_dir, product_dir, schema_dir
from factorio_launcher.core.workspace import ensure_workspace, list_install_refs, list_instances


def run_doctor(workspace: Path) -> dict[str, object]:
    workspace = ensure_workspace(workspace)
    problems: list[str] = []
    suggestions: list[str] = []
    warnings: list[str] = []

    try:
        manifest = load_product_manifest()
    except OSError as exc:
        manifest = {}
        problems.append(f"product manifest cannot be read: {exc}")

    if manifest:
        problems.extend(validate_product_manifest(manifest))

    if not product_dir().exists():
        problems.append("product directory is missing")

    schema_problems = validate_schema_files(schema_dir())
    schema_problems.extend(validate_schema_files(factorio_schema_dir()))
    problems.extend(schema_problems)

    installs = list_install_refs(workspace)
    instances = list_instances(workspace)
    if not installs:
        warnings.append("no install references registered yet")
        suggestions.append("run: factorio-launcher installs scan")
        suggestions.append("run: factorio-launcher installs import <path>")

    status = "ok"
    if problems:
        status = "blocked"
    elif warnings:
        status = "warning"

    return {
        "status": status,
        "workspace": str(workspace),
        "registered_installs": len(installs),
        "instances": len(instances),
        "problems": problems,
        "warnings": warnings,
        "suggested_fixes": suggestions,
        "setup_integration": "disabled until managed installs are implemented",
    }


def validate_schema_files(root: Path) -> list[str]:
    problems: list[str] = []
    if not root.exists():
        return [f"schema directory is missing: {root}"]
    for path in sorted(root.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            problems.append(f"{path.name}: invalid JSON schema file: {exc}")
            continue
        if not isinstance(data, dict):
            problems.append(f"{path.name}: schema must be a JSON object")
        if "$schema" not in data:
            problems.append(f"{path.name}: missing $schema")
        if "title" not in data:
            problems.append(f"{path.name}: missing title")
    return problems
