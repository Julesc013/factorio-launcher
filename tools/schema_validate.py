from __future__ import annotations

import json
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    problems: list[str] = []
    schemas = sorted((ROOT / "schemas").glob("*.json"))
    if not schemas:
        problems.append("no schema files found")
    for path in schemas:
        problems.extend(validate_schema_file(path))
    problems.extend(validate_product_manifest(ROOT / "product" / "factorio.product.toml"))
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


if __name__ == "__main__":
    raise SystemExit(main())

