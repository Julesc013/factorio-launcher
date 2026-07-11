# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import json_contract

LIVE_SCHEMA_POLICY = ROOT / "contracts" / "policy" / "live_schema_subset.v1.toml"


def main() -> int:
    problems: list[str] = []
    schemas = sorted((ROOT / "contracts" / "schema").glob("**/*.json"))
    if not schemas:
        problems.append("no schema files found")
    for path in schemas:
        problems.extend(validate_schema_file(path))
    problems.extend(validate_live_schema_subset(LIVE_SCHEMA_POLICY))
    problems.extend(validate_product_manifest(ROOT / "content" / "factorio" / "product" / "factorio.product.toml"))
    if problems:
        for problem in problems:
            print(f"schema-check: {problem}", file=sys.stderr)
        return 1
    print(f"schema-check: ok ({len(schemas)} schemas)")
    return 0


def validate_schema_file(path: Path) -> list[str]:
    problems: list[str] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        return [f"{path}: {exc}"]
    if not isinstance(data, dict):
        return [f"{path}: schema must be an object"]
    for key in ["$schema", "$id", "title", "type"]:
        if key not in data:
            problems.append(f"{path}: missing {key}")
    if data.get("type") != "object":
        problems.append(f"{path}: root type should be object")
    return problems


def validate_product_manifest(path: Path) -> list[str]:
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [f"{path}: {exc}"]
    problems: list[str] = []
    if data.get("product_id") != "factorio":
        problems.append(f"{path}: product_id must be factorio")
    boundaries = data.get("boundaries", {})
    if boundaries.get("bundles_factorio_binaries") is not False:
        problems.append(f"{path}: must not bundle Factorio binaries")
    if boundaries.get("repairs_foreign_installs") is not False:
        problems.append(f"{path}: must not repair foreign installs")
    return problems


def validate_live_schema_subset(path: Path) -> list[str]:
    try:
        with path.open("rb") as handle:
            policy = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return [f"{path}: {exc}"]
    problems: list[str] = []
    if policy.get("schema") != "facman.live_schema_subset.v1":
        problems.append(f"{path}: unexpected schema id")
    if policy.get("claim") != "supported_subset_only":
        problems.append(f"{path}: claim must remain supported_subset_only")
    entries = policy.get("live_schema")
    if not isinstance(entries, list) or not entries:
        return problems + [f"{path}: live_schema entries are required"]
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            problems.append(f"{path}: live_schema[{index}] must be a table")
            continue
        relative = entry.get("path")
        if not isinstance(relative, str) or not relative:
            problems.append(f"{path}: live_schema[{index}] has no path")
            continue
        if relative in seen:
            problems.append(f"{path}: duplicate live schema {relative}")
            continue
        seen.add(relative)
        schema_path = ROOT / relative
        if not schema_path.is_file() or ROOT not in schema_path.resolve().parents:
            problems.append(f"{path}: live schema is missing or escapes the repository: {relative}")
            continue
        try:
            schema = json_contract.load_schema(schema_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            problems.append(f"{schema_path}: {exc}")
            continue
        for problem in json_contract.supported_schema_problems(schema):
            problems.append(f"{schema_path}: {problem}")
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
