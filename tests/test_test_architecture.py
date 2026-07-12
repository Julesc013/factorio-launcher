# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path

from tools import coverage_policy_check, dev, test_architecture_check


class TestArchitectureTests(unittest.TestCase):
    def test_policy_is_complete_and_not_weakened(self) -> None:
        self.assertEqual([], test_architecture_check.validate())

    def test_impact_selection_is_deterministic(self) -> None:
        impact = dev.load_impact()
        first = dev.affected(impact, ["runtime/archive/fl_archive_reader.cpp"])
        second = dev.affected(impact, ["runtime/archive/fl_archive_reader.cpp"])
        self.assertEqual(first, second)
        self.assertIn("fl_archive_core_smoke", first["native_targets"])
        self.assertIn("tests.test_archive_core", first["python_tests"])

    def test_affected_python_runner_exposes_repo_and_test_helpers(self) -> None:
        source = (dev.ROOT / "tools" / "dev.py").read_text(encoding="utf-8")
        self.assertIn('str(ROOT / "tests")', source)
        self.assertIn("os.pathsep.join(python_paths)", source)

    def test_script_backed_native_tests_build_their_real_prerequisite(self) -> None:
        self.assertEqual("flb_factorio_shared", dev.NATIVE_BUILD_PREREQUISITES["facman_abi_symbol_smoke"])

    def test_native_executable_honors_requested_configuration(self) -> None:
        source = (dev.ROOT / "tools" / "dev.py").read_text(encoding="utf-8")
        self.assertIn('f"{configuration}/facman.exe"', source)
        self.assertIn("native_executable(build_root, args.configuration)", source)

    def test_operator_category_cannot_be_automatically_passed(self) -> None:
        self.assertFalse(dev.load_impact()["operator"]["automated"])

    def test_critical_coverage_requires_each_policy_module(self) -> None:
        policy = json.loads(coverage_policy_check.POLICY.read_text(encoding="utf-8"))
        files = []
        for module in policy["modules"]:
            files.append({"file": f"{module}/proof.cpp", "lines": [{"count": 1}]})
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "coverage.json"
            report.write_text(json.dumps({"files": files}), encoding="utf-8")
            self.assertEqual([], coverage_policy_check.validate(report))
            report.write_text(json.dumps({"files": files[:-1]}), encoding="utf-8")
            self.assertTrue(coverage_policy_check.validate(report))


if __name__ == "__main__":
    unittest.main()
