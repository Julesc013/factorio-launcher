# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def source_cmake_files(root: Path) -> list[Path]:
    """Return source CMake files while excluding only build dirs inside root."""
    return [
        path
        for path in sorted(root.glob("**/CMakeLists.txt"))
        if "build" not in path.relative_to(root).parts
    ]


def validate() -> list[str]:
    problems: list[str] = []
    root = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
    modules = [
        "external", "runtime/core", "runtime/platform", "runtime/base", "runtime/workspace",
        "runtime/archive", "runtime/transaction", "runtime/preferences", "runtime/package", "runtime/factorio",
        "runtime/client", "apps", "tests/native",
    ]
    for module in modules:
        if not (ROOT / module / "CMakeLists.txt").is_file():
            problems.append(f"module-local CMake file missing: {module}")
        if f"add_subdirectory({module})" not in root and module != "tests/native":
            problems.append(f"root does not compose module: {module}")

    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in source_cmake_files(ROOT)
    )
    for alias in (
        "facman::core", "facman::platform", "facman::workspace", "facman::archive", "facman::preferences",
        "facman::package", "facman::factorio_model", "facman::factorio_application",
        "facman::launch_planning", "facman::product_execution",
        "facman::candidate_policy", "facman::candidate_projection",
        "facman::play_observer",
        "facman::binding", "facman::client_model", "facman::transport_direct",
        "facman::transport_process", "facman::transport_daemon", "facman::client", "facman::cli",
    ):
        if f"{alias} ALIAS" not in combined:
            problems.append(f"namespaced target missing: {alias}")

    policies = (ROOT / "cmake/FacManPolicies.cmake").read_text(encoding="utf-8")
    for target in ("facman_warnings", "facman_hardening", "facman_sanitizers", "facman_coverage"):
        if f"add_library({target} INTERFACE)" not in policies:
            problems.append(f"interface policy target missing: {target}")
    options = (ROOT / "cmake/FacManOptions.cmake").read_text(encoding="utf-8")
    for option in (
        "FACMAN_BUILD_CLI", "FACMAN_BUILD_TUI", "FACMAN_BUILD_DAEMON", "FACMAN_BUILD_GUI",
        "FACMAN_BUILD_TESTS", "FACMAN_BUILD_PLAY_EVIDENCE_TOOLS",
        "FACMAN_WITH_SETUP", "FACMAN_ENABLE_SANITIZERS",
        "FACMAN_ENABLE_COVERAGE", "FACMAN_WARNINGS_AS_ERRORS",
    ):
        if f"option({option} " not in options:
            problems.append(f"canonical CMake option missing: {option}")
    for compatibility in ("FLAUNCH_BUILD_NATIVE_APPS", "FLAUNCH_BUILD_TESTS", "FLAUNCH_ENABLE_SANITIZERS"):
        if compatibility not in options:
            problems.append(f"compatibility option alias missing: {compatibility}")

    install = (ROOT / "cmake/FacManInstall.cmake").read_text(encoding="utf-8")
    for component in ("Runtime", "CLI", "Contracts", "Content", "Documentation", "Licenses", "Development"):
        if f"COMPONENT {component}" not in install and f'\\"{component}\\"' not in install:
            problems.append(f"install component missing: {component}")
    for anchor in (
        "EXPORT FacManTargets",
        "FacManConfig.cmake",
        "FacManConfigVersion.cmake",
        "facman-flb.pc",
        "include/ulk",
        "compatibility.v1.json",
    ):
        if anchor not in install:
            problems.append(f"installed SDK contract is missing: {anchor}")
    if "bin/Debug" in install:
        problems.append("install graph contains a hard-coded Debug frontend artifact")
    for operator_target in (
        "facman_gate4c_verdict_harness",
        "facman_play_observer_static",
        "facman_play_evidence_classification",
    ):
        if operator_target in install:
            problems.append(
                f"default install graph includes operator-only target: {operator_target}"
            )
    apps = (ROOT / "apps/CMakeLists.txt").read_text(encoding="utf-8")
    if "if(FACMAN_BUILD_GUI)" not in apps or "does not build an in-tree GUI target" not in apps:
        problems.append("FACMAN_BUILD_GUI remains a silent no-op")

    factorio = (ROOT / "runtime/factorio/CMakeLists.txt").read_text(encoding="utf-8")
    source_owners = {
        "launch/flb_factorio_launch_plan.cpp": "flb_factorio_launch_planning_static",
        "launch/flb_factorio_launch_permit.cpp": "flb_factorio_launch_planning_static",
        "launch/flb_factorio_execution.cpp": "flb_factorio_product_execution_static",
        "launch/flb_factorio_candidate_manifest.cpp": "flb_factorio_candidate_policy_static",
        "launch/flb_factorio_hermetic_candidate.cpp": "flb_factorio_candidate_policy_static",
        "instance/flb_factorio_candidate_projection.cpp": "flb_factorio_candidate_projection_static",
    }
    for source, owner in source_owners.items():
        if factorio.count(source) != 1:
            problems.append(f"Play source must have one CMake owner: {source}")
        owner_block = factorio.split(f"add_library({owner}", 1)
        if len(owner_block) != 2 or source not in owner_block[1].split("add_library(", 1)[0]:
            problems.append(f"Play source has the wrong CMake owner: {source} -> {owner}")
    if "add_library(flb_factorio_launch_static INTERFACE)" not in factorio:
        problems.append("legacy launch target is not a compatibility-only aggregate")
    model_block = factorio.split(
        "target_link_libraries(facman_factorio_model INTERFACE", 1
    )
    model_links = model_block[1].split("add_library(", 1)[0] if len(model_block) == 2 else ""
    for required_target in (
        "flb_factorio_launch_planning_static",
        "flb_factorio_product_execution_static",
    ):
        if required_target not in model_links:
            problems.append(f"product model omits exact runtime target: {required_target}")
    for operator_target in (
        "flb_factorio_candidate_policy_static",
        "flb_factorio_candidate_projection_static",
        "facman_play_observer_static",
        "facman_gate4c_verdict_harness",
    ):
        if operator_target in model_links:
            problems.append(f"product model links operator/candidate target: {operator_target}")

    native_tests = (ROOT / "tests/native/CMakeLists.txt").read_text(encoding="utf-8")
    for anchor in (
        "if(FACMAN_BUILD_PLAY_EVIDENCE_TOOLS)",
        "add_library(facman_play_observer_static STATIC",
        "add_custom_target(facman_play_evidence_classification",
        "add_executable(facman_gate4c_verdict_harness",
    ):
        if anchor not in native_tests:
            problems.append(f"operator evidence target separation is missing: {anchor}")
    presets = json.loads((ROOT / "CMakePresets.json").read_text(encoding="utf-8"))
    names = {item["name"] for item in presets.get("configurePresets", [])}
    required = {"dev-windows", "dev-linux", "dev-macos", "ci-debug", "ci-release", "asan-ubsan", "coverage", "package-windows-x64", "package-linux-x64", "package-macos-x64"}
    for name in sorted(required - names):
        problems.append(f"configure preset missing: {name}")

    package = (ROOT / "tools/package/pipeline.py").read_text(encoding="utf-8")
    resolve = package.split("def resolve_source_target", 1)[1].split("def pinned_source_revisions", 1)[0]
    if ".rglob(" in resolve:
        problems.append("package builder recursively searches build trees")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"cmake-architecture-check: {problem}", file=sys.stderr)
        return 1
    print("cmake-architecture-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
