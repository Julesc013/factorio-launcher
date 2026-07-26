# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMPACT_PATH = ROOT / "contracts" / "policy" / "test_impact.v1.json"
OBLIGATION_PATH = ROOT / "contracts" / "policy" / "test_obligations.v1.json"
EXPECTED_CATEGORIES = {
    "fast-unit", "contract", "integration", "filesystem", "archive",
    "transaction", "package", "platform", "fuzz", "operator",
}
FROZEN_MINIMUMS = {"ctest": 16, "python_test_files": 55, "strict_validators": 44}


def skip_reason_prefix(value: ast.AST) -> str | None:
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value.partition(":")[0]
    if isinstance(value, ast.JoinedStr) and value.values:
        first = value.values[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            return first.value.partition(":")[0]
    return None


def skip_policy_problems(classes: set[str]) -> list[str]:
    problems: list[str] = []
    reason_index = {
        "skip": 0,
        "skipIf": 1,
        "skipUnless": 1,
        "skipTest": 0,
        "SkipTest": 0,
    }
    for path in sorted((ROOT / "tests").rglob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.attr if isinstance(node.func, ast.Attribute) else ""
            if name not in reason_index:
                continue
            index = reason_index[name]
            if len(node.args) <= index:
                problems.append(f"{relative(path)}:{node.lineno} skip reason is missing")
                continue
            prefix = skip_reason_prefix(node.args[index])
            if prefix not in classes:
                problems.append(
                    f"{relative(path)}:{node.lineno} skip reason has no accepted obligation class"
                )
    return problems


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def validate() -> list[str]:
    problems: list[str] = []
    impact = json.loads(IMPACT_PATH.read_text(encoding="utf-8"))
    obligations = json.loads(OBLIGATION_PATH.read_text(encoding="utf-8"))
    obligation_classes = set(obligations.get("classes", []))
    expected_obligation_classes = {
        "required_blocked",
        "unsupported",
        "optional",
        "not_applicable",
        "historical_only",
    }
    if obligation_classes != expected_obligation_classes:
        problems.append("test obligation classes do not match the reviewed vocabulary")
    if obligations.get("required_class") != "required_blocked":
        problems.append("required test obligation class must remain required_blocked")
    promotion = obligations.get("profiles", {}).get("promotion", {})
    if promotion.get("required_skip_limit") != 0:
        problems.append("promotion must permit zero required-obligation skips")
    if obligations.get("unknown_skip_limit") != 0:
        problems.append("unknown skip reasons must fail closed")
    problems.extend(skip_policy_problems(obligation_classes))
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
    fast_required = impact.get("fast_native_required", [])
    fast_optional = impact.get("fast_native_optional", [])
    if not isinstance(fast_required, list) or not fast_required:
        problems.append("required fast native test list must be non-empty")
    if not isinstance(fast_optional, list):
        problems.append("optional fast native test list must be a list")
        fast_optional = []
    if set(fast_required) & set(fast_optional):
        problems.append("required and optional fast native tests must be disjoint")
    fast_overrides = impact.get("fast_native_target_overrides", {})
    if not isinstance(fast_overrides, dict):
        problems.append("fast native target overrides must be an object")
        fast_overrides = {}
    if not set(fast_overrides).issubset(set(fast_required) | set(fast_optional)):
        problems.append("fast native target overrides contain an undeclared test")
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
    for target in [*fast_required, *fast_optional]:
        if target not in native_text:
            problems.append(f"fast native test is absent from CMake: {target}")
    for target in fast_overrides.values():
        if str(target) not in native_text:
            problems.append(f"fast native target override is absent from CMake: {target}")
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
    for anchor in (
        "--show-only=json-v1",
        "configured_fast_targets",
        "fast_native_required",
        "fast_native_optional",
        "FACMAN_TASK_ROOT",
        "--allow-in-tree-output",
    ):
        if anchor not in dev_text:
            problems.append(f"developer test runner is missing truth anchor: {anchor}")
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    for proof in (
        "FACMAN_WARNINGS_AS_ERRORS=ON", "clang_tidy_changed.py", "core-sanitized",
        "FACMAN_ENABLE_LIBFUZZER=ON", "coverage_policy_check.py", "--config Release",
    ):
        if proof not in workflow:
            problems.append(f"CI native-quality proof is missing: {proof}")
    if workflow.count("tools/test_obligations.py --profile promotion") < 3:
        problems.append("every portable hosted Python lane must enforce promotion skip obligations")
    baseline = json.loads(
        (ROOT / "docs" / "quality" / "benchmarks" / "baseline.v1.json").read_text(encoding="utf-8")
    )
    expected_benchmarks = {
        "startup", "command_dispatch", "command_graph_materialization", "archive_inspect", "mod_inspection",
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
