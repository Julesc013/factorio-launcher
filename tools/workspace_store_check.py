# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = {
    "runtime/workspace/fl_workspace_store.h",
    "runtime/workspace/fl_workspace_store.cpp",
    "tests/native/fl_workspace_store_smoke.cpp",
    "contracts/schema/facman/facman_workspace_migration.v1.schema.json",
}


def validate() -> list[str]:
    problems: list[str] = []
    for relative in sorted(REQUIRED_FILES):
        if not (ROOT / relative).is_file():
            problems.append(f"missing workspace-store file: {relative}")

    header = (ROOT / "runtime/workspace/fl_workspace_store.h").read_text(encoding="utf-8")
    source = (ROOT / "runtime/workspace/fl_workspace_store.cpp").read_text(encoding="utf-8")
    cmake = (ROOT / "runtime/workspace/CMakeLists.txt").read_text(encoding="utf-8")
    tests_cmake = (ROOT / "tests/native/CMakeLists.txt").read_text(encoding="utf-8")
    app = (ROOT / "runtime/factorio/application/flb_factorio_application.cpp").read_text(encoding="utf-8")
    cli = (ROOT / "apps/cli/command_dispatch.cpp").read_text(encoding="utf-8")
    index = (ROOT / "contracts/command/factorio/index.v1.toml").read_text(encoding="utf-8")

    for anchor in (
        "class WorkspaceLayout",
        "class InstallRepository",
        "class InstanceRepository",
        "class ModsetRepository",
        "class TransactionRepository",
        "class WorkspaceRepository",
        "inspect_migration",
        "plan_migration",
        "apply_migration",
    ):
        if anchor not in header:
            problems.append(f"workspace store is missing API anchor: {anchor}")
    for anchor in (
        "StableInputFile",
        "DurableOutputFile",
        "workspace_record_future_or_unknown_schema",
        "workspace_layout_future_or_unknown",
        "workspace_migration_apply_unproven",
        "uuid_from_random",
    ):
        if anchor not in source:
            problems.append(f"workspace store is missing safety anchor: {anchor}")
    if "add_library(facman_workspace_static STATIC" not in cmake or "fl_workspace_store_smoke" not in tests_cmake:
        problems.append("CMake does not define the workspace store and native proof targets")

    for command in (
        "workspace.migration.inspect",
        "workspace.migration.plan",
        "workspace.migration.apply",
    ):
        if command not in app or command not in index:
            problems.append(f"workspace migration command is not registered end to end: {command}")
    if '"workspace." + family + "." + action' not in cli or "call(options," not in cli:
        problems.append("workspace migration CLI does not route through FacManClient")

    forbidden_outside_store = (
        '"installs/installed_state"',
        '"instance.manifest.json"',
        '"workspace_id": "local"',
    )
    for path in (ROOT / "runtime").rglob("*"):
        if not path.is_file() or path.suffix not in {".cpp", ".h"}:
            continue
        if path.parent == ROOT / "runtime" / "workspace":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for token in forbidden_outside_store:
            if token in text:
                problems.append(f"persistent workspace fallback escaped the central store: {path.relative_to(ROOT)} ({token})")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"workspace-store-check: {problem}", file=sys.stderr)
        return 1
    print("workspace-store-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
