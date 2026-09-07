# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

"""Inspect a concrete lab run's owned roots and actual input bytes; never execute."""
from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tools import development_layout as layout
from tools import lab_input_registry as lab


def inspect(record: dict[str, Any], registry: dict[str, Any], root: Path = ROOT) -> dict[str, Any]:
    lab.validate(registry, root)
    lab.fields(record, "schema scenario_id registry_sha256 source_commit source_tree task_root marker_sha256 roots effects reset export candidate input")
    lab.require(record["schema"] == "facman.lab-run-custody.v1", "unknown run custody schema")
    registry_pin = hashlib.sha256(json.dumps(registry, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    lab.require(record["registry_sha256"] == registry_pin, "run registry changed")
    rows = {row["id"]: row for row in lab.matrix(registry)}
    lab.require(record["scenario_id"] in rows, "unknown scenario cell")
    cell = rows[record["scenario_id"]]
    lab.require(cell["status"] == "fixture_preparation_available", "scenario has unresolved external custody")
    # Current available hosts admit only machine fixture preparation. Real game
    # and human observation require their separately reviewed host/route gate.
    lab.require(cell["kind"] == "machine_fixture", "this inspector admits machine-fixture custody only")
    for key in ("source_commit", "source_tree"):
        lab.identity(record[key], lab.OID)
    task_root = Path(record["task_root"])
    lab.require(task_root.is_absolute(), "task root must be absolute")
    marker = task_root / layout.MARKER_NAME
    _, marker_value = lab.inspect_json(marker, record["marker_sha256"])
    layout.validate_marker_payload(task_root, marker_value, root)
    lab.fields(record["roots"], "state export")
    for value in record["roots"].values():
        lab.text(value)
        lab.require(not any(part in (".", "..") for part in value.replace("\\", "/").split("/")),
                    "run root contains dot components")
    roots = {key: Path(value) for key, value in record["roots"].items()}
    for path in roots.values():
        lab.require(not path.exists() or path.is_dir(), "run root is not a directory")
        lab.require(not path.is_symlink(), "run root is a link")
        lab.require(path.is_absolute() and path != task_root and path.resolve().is_relative_to(task_root.resolve()),
                    "run root escaped owned task scope")
        lab.require(not any(part in (".", "..") for part in path.parts), "run root contains dot components")
        for parent in (path, *path.parents):
            try:
                info = parent.lstat()
            except FileNotFoundError:
                continue
            lab.require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400,
                        "run root traverses a link")
    lab.require(not roots["state"].resolve().is_relative_to(roots["export"].resolve()) and
                not roots["export"].resolve().is_relative_to(roots["state"].resolve()),
                "state and export roots must be disjoint")
    lab.require(record["effects"] == ["owned_fixture_files", "injected_or_fake_process", "evidence_export"],
                "fixture effects exceed admitted scope")
    lab.require(record["reset"] == "retain_then_marker_owned_cleanup" and
                record["export"] == "hash_and_archive_before_reset", "reset/export policy is incomplete")
    artifacts = {}
    for role in ("candidate", "input"):
        ref = record[role]
        lab.fields(ref, "path sha256")
        if role == "input":
            artifacts[role], fixture_value = lab.inspect_json(Path(ref["path"]), ref["sha256"])
            lab.require(lab.semantic_value(fixture_value) == registry["inputs"]["fixture"]["semantic_sha256"],
                        "fixture input is outside registered corpus")
        else:
            artifacts[role] = lab.inspect_file(Path(ref["path"]), ref["sha256"])
    return {"schema": "facman.lab-run-custody-result.v1", "scenario_id": cell["id"],
            "source_commit": record["source_commit"], "source_tree": record["source_tree"],
            "source_binding": "declared identity; candidate pipeline must verify package provenance",
            "host": cell["host"], "fresh_host_check_required": True,
            "task_root": str(task_root), "roots": record["roots"], "effects": record["effects"],
            "reset": record["reset"], "export": record["export"], "artifacts": artifacts,
            "execution_authorized": False, "qualification_granted": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("record", type=Path)
    args = parser.parse_args(argv)
    try:
        result = inspect(lab.load(args.record), lab.load(ROOT / lab.REGISTRY))
        print(json.dumps(result, indent=2))
        return 0
    except (ValueError, OSError, TypeError, KeyError) as error:
        print(f"lab-run-custody: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
