from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools import source_format_check

ROOT = Path(__file__).resolve().parents[1]


class SourceFormatCheckTests(unittest.TestCase):
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

    def test_large_one_line_workflow_yaml_file_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "collapsed.yml"
            path.write_bytes(b"name: ci " + (b"jobs: build " * 150))

            problems = source_format_check.validate_file(path, ".github/workflows/collapsed.yml")

        self.assertTrue(any("looks minified or collapsed" in problem for problem in problems))

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
        self.assertIn("\n  native-and-python:\n", text)
        self.assertFalse(source_format_check.validate_file(path, rel))


if __name__ == "__main__":
    unittest.main()
