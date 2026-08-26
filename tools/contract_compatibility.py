# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Produce an advisory compatibility diff between FacMan contract bundles."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _type(value: dict[str, Any]) -> Any:
    return value.get("type", "object")


def compare(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    changes: list[dict[str, str]] = []
    old = {item["schema_id"]: item for item in previous.get("contracts", [])}
    new = {item["schema_id"]: item for item in current.get("contracts", [])}
    for schema_id in sorted(old.keys() - new.keys()):
        changes.append({"schema_id": schema_id, "kind": "semantic_id_removed", "path": "$", "classification": "breaking"})
    for schema_id in sorted(new.keys() - old.keys()):
        changes.append({"schema_id": schema_id, "kind": "semantic_id_added", "path": "$", "classification": "non_breaking"})
    for schema_id in sorted(old.keys() & new.keys()):
        before = old[schema_id]["schema"]
        after = new[schema_id]["schema"]
        before_props = before.get("properties", {})
        after_props = after.get("properties", {})
        before_required = set(before.get("required", []))
        after_required = set(after.get("required", []))
        for name in sorted(before_props.keys() - after_props.keys()):
            changes.append({"schema_id": schema_id, "kind": "field_removed", "path": f"$.{name}", "classification": "breaking"})
        for name in sorted(after_props.keys() - before_props.keys()):
            classification = "breaking" if name in after_required else "non_breaking"
            kind = "required_field_added" if name in after_required else "optional_field_added"
            changes.append({"schema_id": schema_id, "kind": kind, "path": f"$.{name}", "classification": classification})
        for name in sorted(before_props.keys() & after_props.keys()):
            if _type(before_props[name]) != _type(after_props[name]):
                changes.append({"schema_id": schema_id, "kind": "type_changed", "path": f"$.{name}", "classification": "breaking"})
            if before_props[name].get("enum") != after_props[name].get("enum"):
                if "enum" in before_props[name] or "enum" in after_props[name]:
                    changes.append({"schema_id": schema_id, "kind": "enum_changed", "path": f"$.{name}", "classification": "migration_required"})
            if name not in before_required and name in after_required:
                changes.append({"schema_id": schema_id, "kind": "field_became_required", "path": f"$.{name}", "classification": "breaking"})
            if name in before_required and name not in after_required:
                changes.append({"schema_id": schema_id, "kind": "field_became_optional", "path": f"$.{name}", "classification": "non_breaking"})
        if before.get("additionalProperties", True) != after.get("additionalProperties", True):
            classification = "breaking" if after.get("additionalProperties") is False else "non_breaking"
            changes.append({"schema_id": schema_id, "kind": "object_openness_changed", "path": "$", "classification": classification})
    breaking = any(item["classification"] in {"breaking", "migration_required"} for item in changes)
    return {
        "schema": "facman.contract_compatibility_report.v1",
        "status": "migration_required" if breaking else "compatible",
        "semver_allocation_authorized": False,
        "previous_source_digest": previous.get("source_digest"),
        "current_source_digest": current.get("source_digest"),
        "changes": changes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("previous")
    parser.add_argument("current")
    parser.add_argument("--output")
    args = parser.parse_args()
    previous = json.loads(Path(args.previous).read_text(encoding="utf-8"))
    current = json.loads(Path(args.current).read_text(encoding="utf-8"))
    text = json.dumps(compare(previous, current), indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8", newline="\n")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
