# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest
import json
import os
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

    def test_fast_runner_uses_required_and_configuration_optional_tests(self) -> None:
        impact = dev.load_impact()
        self.assertGreater(len(impact["fast_native_required"]), 0)
        self.assertNotIn("*", impact["fast_native_required"])
        self.assertIn("facman_tui_smoke", impact["fast_native_optional"])
        self.assertNotIn("facman_tui_smoke", impact["fast_native_required"])
        self.assertNotIn("tests.test_schema_tools", impact["fast_python"])

    def test_full_runner_persists_external_obligation_evidence(self) -> None:
        source = (dev.ROOT / "tools" / "dev.py").read_text(encoding="utf-8")
        self.assertIn('task_root / "evidence"', source)
        self.assertIn("python-obligations-{args.obligation_profile}.json", source)
        self.assertIn('"--evidence"', source)

    def test_configured_fast_selection_tracks_tui_on_and_off_graphs(self) -> None:
        impact = {
            "fast_native_required": ["core_smoke", "harness_smoke"],
            "fast_native_optional": ["tui_smoke"],
            "fast_native_target_overrides": {
                "harness_smoke": "shared_harness",
            },
        }
        graph = [
            {
                "name": "core_smoke",
                "command": ["/build/core_smoke"],
                "properties": [{"name": "LABELS", "value": ["fast-unit"]}],
            },
            {
                "name": "harness_smoke",
                "command": ["/build/shared_harness", "--self-test"],
                "properties": [{"name": "LABELS", "value": ["fast-unit"]}],
            },
        ]
        self.assertEqual(
            ["core_smoke", "shared_harness"],
            dev.configured_fast_targets(impact, graph),
        )
        graph.append(
            {
                "name": "tui_smoke",
                "command": ["/build/tui_smoke"],
                "properties": [{"name": "LABELS", "value": ["fast-unit"]}],
            }
        )
        self.assertEqual(
            ["core_smoke", "shared_harness", "tui_smoke"],
            dev.configured_fast_targets(impact, graph),
        )

    def test_configured_fast_selection_rejects_policy_drift(self) -> None:
        impact = {
            "fast_native_required": ["required_smoke"],
            "fast_native_optional": [],
            "fast_native_target_overrides": {},
        }
        with self.assertRaisesRegex(ValueError, "missing required"):
            dev.configured_fast_targets(impact, [])
        graph = [
            {
                "name": "required_smoke",
                "command": ["/build/required_smoke"],
                "properties": [{"name": "LABELS", "value": ["fast-unit"]}],
            },
            {
                "name": "unmapped_smoke",
                "command": ["/build/unmapped_smoke"],
                "properties": [{"name": "LABELS", "value": ["fast-unit"]}],
            },
        ]
        with self.assertRaisesRegex(ValueError, "policy omits"):
            dev.configured_fast_targets(impact, graph)

    def test_default_task_root_is_external_and_overrideable(self) -> None:
        with mock.patch.dict(os.environ, {"FACMAN_TASK_ROOT": ""}):
            self.assertFalse(dev.default_task_root().resolve().is_relative_to(dev.ROOT.resolve()))
        if os.name == "nt":
            local_app_data = Path("C:/facman-test-local-app-data")
            with mock.patch.dict(
                os.environ,
                {
                    "FACMAN_TASK_ROOT": "",
                    "LOCALAPPDATA": str(local_app_data),
                },
            ):
                self.assertTrue(
                    dev.default_task_root().is_relative_to(
                        local_app_data / "FacMan" / "Tasks"
                    )
                )
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.dict(os.environ, {"FACMAN_TASK_ROOT": temporary}):
                self.assertEqual(Path(temporary), dev.default_task_root())

    def test_in_tree_output_requires_explicit_legacy_override(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside the source checkout"):
            dev.validate_external_output(dev.ROOT / "build" / "test", allow_in_tree=False)
        allowed = dev.validate_external_output(
            dev.ROOT / "build" / "test",
            allow_in_tree=True,
        )
        self.assertTrue(allowed.is_relative_to(dev.ROOT.resolve()))

    def test_native_executable_honors_requested_configuration(self) -> None:
        source = (dev.ROOT / "tools" / "dev.py").read_text(encoding="utf-8")
        self.assertIn('f"{configuration}/facman.exe"', source)
        self.assertIn("native_executable(build_root, args.configuration)", source)
        self.assertIn('env["FACMAN_NATIVE_BUILD_ROOT"] = str(build_root.resolve())', source)
        self.assertIn('env["FACMAN_NATIVE_CONFIGURATION"] = args.configuration', source)

    def test_tui_executable_honors_requested_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            build_root = Path(temporary)
            executable = build_root / "Debug" / "facman-tui.exe"
            executable.parent.mkdir(parents=True)
            executable.write_bytes(b"tui")
            self.assertEqual(
                executable,
                dev.native_tui_executable(build_root, "Debug"),
            )
        source = (dev.ROOT / "tools" / "dev.py").read_text(encoding="utf-8")
        self.assertIn('env["FACMAN_TUI_EXE"]', source)

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

    def test_raw_python_runner_rejects_a_stale_canonical_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical = root / "build" / "native-smoke" / "Debug" / "facman.exe"
            current = root / "build" / "m2-wu9" / "Release" / "facman.exe"
            canonical.parent.mkdir(parents=True)
            current.parent.mkdir(parents=True)
            canonical.write_bytes(b"stale")
            current.write_bytes(b"current")
            os.utime(canonical, ns=(1_000_000_000, 1_000_000_000))
            os.utime(current, ns=(2_000_000_000, 2_000_000_000))
            with (
                mock.patch.object(native_cli, "ROOT", root),
                mock.patch.dict("os.environ", {"FACMAN_CLI_EXE": ""}),
            ):
                self.assertEqual(current, native_cli.facman_executable())

    def test_raw_python_runner_excludes_newer_packaged_and_install_staging_binaries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            canonical = root / "build" / "native-smoke" / "Debug" / "facman.exe"
            packaged = root / "build" / "packages" / "profile" / "bin" / "facman.exe"
            installed = (
                root
                / "build"
                / "packages"
                / ".install"
                / "profile"
                / "bin"
                / "facman.exe"
            )
            for path, payload in (
                (canonical, b"canonical"),
                (packaged, b"packaged"),
                (installed, b"installed"),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
            os.utime(canonical, ns=(1_000_000_000, 1_000_000_000))
            os.utime(packaged, ns=(3_000_000_000, 3_000_000_000))
            os.utime(installed, ns=(4_000_000_000, 4_000_000_000))
            with (
                mock.patch.object(native_cli, "ROOT", root),
                mock.patch.dict("os.environ", {"FACMAN_CLI_EXE": ""}),
            ):
                self.assertEqual(canonical, native_cli.facman_executable())

    def test_raw_python_runner_caches_build_tree_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            current = root / "build" / "m2-wu9" / "Release" / "facman.exe"
            current.parent.mkdir(parents=True)
            current.write_bytes(b"current")
            with (
                mock.patch.object(native_cli, "ROOT", root),
                mock.patch.dict("os.environ", {"FACMAN_CLI_EXE": ""}),
                mock.patch.object(
                    Path,
                    "glob",
                    autospec=True,
                    wraps=Path.glob,
                ) as glob,
            ):
                self.assertEqual(current, native_cli.facman_executable())
                self.assertEqual(current, native_cli.facman_executable())
                self.assertEqual(glob.call_count, 2)

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
