# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "fixtures" / "compatibility"

EXPECTED = {
    "r3.2/workspace.v1.json": "facman.factorio.workspace.v1",
    "r3.2/legacy-install.json": "usk.installed_state.v1",
    "r3.2/legacy-instance.json": None,
    "r3.3/workspace.v1.json": "facman.factorio.workspace.v1",
    "r3.3/transaction.v1.json": "facman.transaction.v1",
    "r3.4/workspace.v1.json": "facman.factorio.workspace.v1",
    "r3.4/transaction.v2.json": "facman.transaction.v2",
}


def validate() -> list[str]:
    problems: list[str] = []
    for relative, schema in EXPECTED.items():
        path = CORPUS / relative
        if not path.is_file():
            problems.append(f"missing compatibility fixture: {relative}")
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"invalid compatibility JSON {relative}: {exc}")
            continue
        if not isinstance(value, dict) or value.get("schema") != schema:
            if schema is not None or not isinstance(value, dict):
                problems.append(f"unexpected compatibility schema: {relative}")
    native = (ROOT / "tests/native/fl_workspace_store_smoke.cpp").read_text(encoding="utf-8")
    for anchor in ("prove_compatibility_corpus", '"r3.2"', '"r3.3"', '"r3.4"', "facman::transaction::inspect"):
        if anchor not in native:
            problems.append(f"native compatibility reader is missing anchor: {anchor}")
    cmake = (ROOT / "tests/native/CMakeLists.txt").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    for anchor in ("fl_json_fuzz", "fl_json_libfuzzer"):
        if anchor not in cmake or anchor not in workflow:
            problems.append(f"JSON fuzz matrix is missing target: {anchor}")
    baseline = json.loads((ROOT / "docs/quality/benchmarks/baseline.v1.json").read_text(encoding="utf-8"))
    required_benchmarks = {
        "startup", "command_dispatch", "command_graph_materialization", "archive_inspect", "mod_inspection",
        "diagnostic_export_traversal", "package_hashing",
    }
    if set(baseline.get("measurements", {})) != required_benchmarks:
        problems.append("benchmark matrix does not cover all required operations")
    version_corpus = (ROOT / "tools/factorio_version_capability_corpus.py").read_text(encoding="utf-8")
    for anchor in (
        "read_only_install_probe",
        "user_state_environment_redirected",
        "raw_process_output_persisted",
        "install_tree_unchanged",
    ):
        if anchor not in version_corpus:
            problems.append(f"Factorio version capability corpus is missing anchor: {anchor}")
    for required in (
        "contracts/schema/factorio/factorio_version_capability_corpus.v1.schema.json",
        "docs/quality/factorio_version_capability_corpus.md",
        "tests/test_factorio_version_capability_corpus.py",
    ):
        if not (ROOT / required).is_file():
            problems.append(f"Factorio version capability corpus support is missing: {required}")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"compatibility-corpus-check: {problem}", file=sys.stderr)
        return 1
    print("compatibility-corpus-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
