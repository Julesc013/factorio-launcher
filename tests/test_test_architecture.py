# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest
import json
import tempfile
from pathlib import Path
from unittest import mock

import native_cli
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

    def test_raw_python_runner_prefers_canonical_native_smoke_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            legacy = root / "build" / "Debug" / "facman.exe"
            canonical = root / "build" / "native-smoke" / "Debug" / "facman.exe"
            legacy.parent.mkdir(parents=True)
            canonical.parent.mkdir(parents=True)
            legacy.write_bytes(b"legacy")
            canonical.write_bytes(b"canonical")
            with (
                mock.patch.object(native_cli, "ROOT", root),
                mock.patch.dict("os.environ", {"FACMAN_CLI_EXE": ""}),
            ):
                self.assertEqual(canonical, native_cli.facman_executable())

    def test_operator_category_cannot_be_automatically_passed(self) -> None:
        self.assertFalse(dev.load_impact()["operator"]["automated"])

    def coverage_files(self) -> list[dict]:
        policy = json.loads(coverage_policy_check.POLICY.read_text(encoding="utf-8"))
        return [
            {
                "file": path,
                "lines": [
                    {"count": count, "branches": [{"count": 1}, {"count": 0}]}
                    for count in (1, 1, 1, 0)
                ],
            }
            for path in policy["designated_files"]
        ]

    def validate_coverage(self, files: list[dict]) -> list[str]:
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "coverage.json"
            report.write_text(json.dumps({"files": files}), encoding="utf-8")
            return coverage_policy_check.validate(report)

    def test_critical_coverage_requires_each_policy_module_and_designated_file(self) -> None:
        files = self.coverage_files()
        self.assertEqual([], self.validate_coverage(files))
        problems = self.validate_coverage(files[:-1])
        self.assertTrue(any("designated file" in problem for problem in problems), problems)

    def test_critical_coverage_uses_module_aggregate_not_best_file(self) -> None:
        files = self.coverage_files()
        files.append({
            "file": "runtime/base/uncovered_bulk.cpp",
            "lines": [
                {"count": 0, "branches": [{"count": 0}, {"count": 0}]}
                for _ in range(100)
            ],
        })
        problems = self.validate_coverage(files)
        self.assertTrue(
            any("runtime/base aggregate line coverage" in problem for problem in problems),
            problems,
        )

    def test_critical_coverage_enforces_aggregate_branches(self) -> None:
        files = self.coverage_files()
        for entry in files:
            if entry["file"].startswith("runtime/archive/"):
                for line in entry["lines"]:
                    for branch in line["branches"]:
                        branch["count"] = 0
        problems = self.validate_coverage(files)
        self.assertTrue(
            any("runtime/archive aggregate branch coverage" in problem for problem in problems),
            problems,
        )


if __name__ == "__main__":
    unittest.main()
