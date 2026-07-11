# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPACT_PATH = ROOT / "contracts" / "policy" / "test_impact.v1.json"
EXPECTED_CATEGORIES = {
    "fast-unit", "contract", "integration", "filesystem", "archive",
    "transaction", "package", "platform", "fuzz", "operator",
}
FROZEN_MINIMUMS = {"ctest": 16, "python_test_files": 55, "strict_validators": 44}


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def validate() -> list[str]:
    problems: list[str] = []
    impact = json.loads(IMPACT_PATH.read_text(encoding="utf-8"))
    categories = set(impact.get("categories", []))
    if categories != EXPECTED_CATEGORIES:
        problems.append("test categories do not match the R3.4 category contract")
    category_python = impact.get("category_python", {})
    if set(category_python) != EXPECTED_CATEGORIES:
        problems.append("every test category must have a matching Python suite declaration")
    operator = impact.get("operator", {})
    if operator.get("automated") is not False:
        problems.append("operator acceptance must remain an explicit human verdict")
    for module in impact.get("modules", []):
        for key in ("paths", "native_targets", "python_tests", "strict_validators", "package_profiles"):
            if key not in module or not isinstance(module[key], list):
                problems.append(f"impact module is missing list field {key}")
        for validator in module.get("strict_validators", []):
            if not (ROOT / validator).is_file():
                problems.append(f"mapped validator does not exist: {validator}")
        for module_name in module.get("python_tests", []):
            path = ROOT / (module_name.replace(".", "/") + ".py")
            if not path.is_file():
                problems.append(f"mapped Python test does not exist: {module_name}")
    for module_name in impact.get("fast_python", []):
        path = ROOT / (module_name.replace(".", "/") + ".py")
        if not path.is_file():
            problems.append(f"fast Python test does not exist: {module_name}")
    minimums = impact.get("minimums", {})
    for key, floor in FROZEN_MINIMUMS.items():
        if int(minimums.get(key, 0)) < floor:
            problems.append(f"{key} policy minimum was weakened below {floor}")
    python_tests = list((ROOT / "tests").rglob("test_*.py"))
    if len(python_tests) < int(minimums.get("python_test_files", 0)):
        problems.append("Python test inventory fell below its frozen minimum")
    strict_text = (ROOT / "tools" / "strict_check.py").read_text(encoding="utf-8")
    validator_count = len(re.findall(r'^\s*\("[^"]+",\s*[A-Za-z0-9_]+\.main\),', strict_text, re.MULTILINE))
    if validator_count < int(minimums.get("strict_validators", 0)):
        problems.append("strict validator inventory fell below its frozen minimum")
    native_text = (ROOT / "tests" / "native" / "CMakeLists.txt").read_text(encoding="utf-8")
    native_count = len(re.findall(r"facman_native_test\(", native_text)) - 1
    direct_count = len(re.findall(r"add_test\(NAME\s+", native_text))
    external_count = 3
    if native_count + direct_count + external_count < int(minimums.get("ctest", 0)):
        problems.append("CTest inventory fell below its frozen minimum")
    for label in EXPECTED_CATEGORIES - {"operator", "package", "fuzz"}:
        if label not in native_text:
            problems.append(f"CTest label is not represented: {label}")
    dev_text = (ROOT / "tools" / "dev.py").read_text(encoding="utf-8")
    for command in ("--affected", "--fast", "--full", "package", "verify-all"):
        if command not in dev_text:
            problems.append(f"developer command is missing: {command}")
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for proof in (
        "FACMAN_WARNINGS_AS_ERRORS=ON", "clang_tidy_changed.py", "core-sanitized",
        "FACMAN_ENABLE_LIBFUZZER=ON", "coverage_policy_check.py", "--config Release",
    ):
        if proof not in workflow:
            problems.append(f"CI native-quality proof is missing: {proof}")
    baseline = json.loads(
        (ROOT / "docs" / "quality" / "benchmarks" / "baseline.v1.json").read_text(encoding="utf-8")
    )
    expected_benchmarks = {
        "startup", "command_dispatch", "archive_inspect", "mod_inspection",
        "diagnostic_export_traversal", "package_hashing",
    }
    if set(baseline.get("measurements", {})) != expected_benchmarks:
        problems.append("performance baseline does not cover every required operation")
    return problems


def main() -> int:
    problems = validate()
    if problems:
        for problem in problems:
            print(f"test-architecture-check: {problem}", file=sys.stderr)
        return 1
    print("test-architecture-check: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
