# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import source_format_check

ROOT = Path(__file__).resolve().parents[1]


class SourceFormatCheckTests(unittest.TestCase):
    def test_precommit_discovery_includes_untracked_nonignored_files(self) -> None:
        source = (ROOT / "tools" / "source_format_check.py").read_text(encoding="utf-8")
        self.assertIn('"--others"', source)
        self.assertIn('"--exclude-standard"', source)

    def test_large_one_line_python_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "collapsed.py"
            path.write_bytes(b"print('x');" * 200)

            problems = source_format_check.validate_file(path, "tools/collapsed.py")

        self.assertTrue(any("looks minified or collapsed" in problem for problem in problems))

    def test_large_one_line_toml_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "collapsed.toml"
            path.write_bytes(b'key = "value"\n' + (b'other = "x" ' * 150))

            problems = source_format_check.validate_file(path, "contracts/command/frontend/collapsed.toml")

        self.assertTrue(any("looks minified or collapsed" in problem for problem in problems))
        self.assertTrue(any("must stay physically reviewable" in problem for problem in problems))

    def test_large_one_line_workflow_yaml_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "collapsed.yml"
            path.write_bytes(b"name: ci " + (b"jobs: build " * 150))

            problems = source_format_check.validate_file(path, ".github/workflows/collapsed.yml")

        self.assertTrue(any("looks minified or collapsed" in problem for problem in problems))
        self.assertTrue(any("must stay physically reviewable" in problem for problem in problems))

    def test_package_and_discovery_tool_scopes_have_explicit_physical_line_guard(self) -> None:
        guarded = [
            "tools/package_skeleton_check.py",
            "release/packaging/portable/portable_cli.v1.toml",
            "contracts/command/frontend/frontend.required_commands.v1.toml",
            ".github/workflows/security.yml",
        ]
        for rel in guarded:
            with self.subTest(rel=rel):
                self.assertTrue(source_format_check.requires_physical_line_guard(rel))

    def test_generated_golden_collapse_is_not_scope_guarded_by_default(self) -> None:
        self.assertFalse(
            source_format_check.requires_physical_line_guard(
                "tests/golden/discovery/windows_steam.discovery_report.v1.json"
            )
        )

    def test_only_admitted_miniz_tree_is_classified_as_vendored_source(self) -> None:
        self.assertTrue(source_format_check.vendored_source("external/miniz/miniz.c"))
        self.assertFalse(source_format_check.vendored_source("external/other/vendor.c"))
        self.assertFalse(source_format_check.vendored_source("runtime/archive/miniz.c"))

    def test_cr_only_line_endings_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cr_only.py"
            path.write_bytes(("x = 1\r" * 400).encode("utf-8"))

            problems = source_format_check.validate_file(path, "tools/cr_only.py")

        self.assertTrue(any("CR-only line endings" in problem for problem in problems))
        self.assertTrue(any("looks minified or collapsed" in problem for problem in problems))

    def test_generated_collapse_requires_explicit_allowlist(self) -> None:
        rel = "docs/reference/generated_collapsed.toml"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "generated_collapsed.toml"
            path.write_bytes(b"generated = true " * 150)

            without_allowlist = source_format_check.validate_file(path, rel)
            source_format_check.MINIFIED_ALLOWLIST_FILES.add(rel)
            try:
                with_allowlist = source_format_check.validate_file(path, rel)
            finally:
                source_format_check.MINIFIED_ALLOWLIST_FILES.remove(rel)

        self.assertTrue(any("looks minified or collapsed" in problem for problem in without_allowlist))
        self.assertFalse(with_allowlist)

    def test_critical_files_are_physically_reviewable(self) -> None:
        critical_files = [
            ".github/workflows/ci.yml",
            ".github/workflows/security.yml",
            "tools/source_format_check.py",
            "tools/strict_check.py",
            "tools/package_layout_check.py",
            "contracts/command/frontend/frontend.required_commands.v1.toml",
        ]
        for rel in critical_files:
            path = ROOT / rel
            text = path.read_bytes().decode("utf-8", errors="ignore")
            self.assertGreaterEqual(source_format_check.physical_lf_line_count(text), 4, rel)
            self.assertFalse(source_format_check.validate_file(path, rel), rel)

    def test_ci_workflow_has_normal_yaml_structure(self) -> None:
        rel = ".github/workflows/ci.yml"
        path = ROOT / rel
        text = path.read_text(encoding="utf-8")

        self.assertIn("\njobs:\n", text)
        self.assertIn("\n  linux-native:\n", text)
        self.assertIn("\n  windows-native-package:\n", text)
        self.assertFalse(source_format_check.validate_file(path, rel))


if __name__ == "__main__":
    unittest.main()
