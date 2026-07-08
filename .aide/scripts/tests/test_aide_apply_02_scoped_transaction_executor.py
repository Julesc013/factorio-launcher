from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_apply_02", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_apply_02"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


COMMAND_VECTORS = [
    ["scoped-transaction", "status"],
    ["scoped-transaction", "validate"],
    ["scoped-transaction", "fixture-plan"],
    ["scoped-transaction", "fixture-verify"],
    ["scoped-transaction", "run", "--plan", ".aide/reports/scoped-transaction-executor-fixture-plan.json"],
    ["scoped-transaction", "run", "--plan", ".aide/examples/apply/scoped-transaction-executor.dry-run.example.json"],
]


def copy_scoped_transaction_files(root: Path) -> None:
    for rel in aide_lite.SCOPED_TRANSACTION_REQUIRED_FILES:
        source = REPO_ROOT / rel
        if source.exists():
            aide_lite.copy_pack_file(source, root / rel)
    aide_lite.copy_pack_file(REPO_ROOT / "core/apply/managed_sections.py", root / "core/apply/managed_sections.py")


class AIDEApply02ScopedTransactionExecutorTests(unittest.TestCase):
    def test_parser_accepts_scoped_transaction_commands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        for command in COMMAND_VECTORS:
            parsed = parser.parse_args(command)
            self.assertTrue(callable(getattr(parsed, "handler", None)), command)

    def test_fixture_verify_is_dry_run_and_writes_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_scoped_transaction_files(root)
            fixture = root / ".aide/examples/apply/scoped-transaction-executor-fixtures/valid_input.md"
            before = fixture.read_text(encoding="utf-8")
            json_result, md_result, rollback_result, plan, report = aide_lite.write_scoped_transaction_fixture_report_outputs(root)
            after = fixture.read_text(encoding="utf-8")
            self.assertIn(json_result.action, {"written", "unchanged"})
            self.assertIn(md_result.action, {"written", "unchanged"})
            self.assertIn(rollback_result.action, {"written", "unchanged"})
            self.assertEqual(before, after)
            self.assertEqual(plan["mode"], "dry-run")
            self.assertEqual(report["status"], "PASS")
            self.assertFalse(report["target_files_mutated"])
            self.assertEqual(report["staged_changes"][0]["operation_type"], "update_managed_section")
            self.assertFalse(report["rollback_record"]["apply_allowed"])
            saved_report = json.loads((root / aide_lite.SCOPED_TRANSACTION_FIXTURE_REPORT_JSON_PATH).read_text(encoding="utf-8"))
            self.assertEqual(saved_report["schema_version"], "aide.scoped-transaction-executor-report.v0")

    def test_scoped_transaction_validation_passes_in_fixture_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_scoped_transaction_files(root)
            write_result, checks = aide_lite.write_scoped_transaction_validation_outputs(root)
            failures = [check.message for check in checks if check.severity == "FAIL"]
            self.assertEqual(failures, [])
            self.assertIn(write_result.action, {"written", "unchanged"})

    def test_current_repo_scoped_transaction_validation_passes_without_reports(self) -> None:
        checks = aide_lite.validate_scoped_transaction_files(REPO_ROOT, require_reports=False)
        failures = [check.message for check in checks if check.severity == "FAIL"]
        self.assertEqual(failures, [])

    def test_run_command_dry_run_plan_preserves_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_scoped_transaction_files(root)
            aide_lite.write_scoped_transaction_fixture_plan_outputs(root)
            parser = aide_lite.build_parser(root)
            args = parser.parse_args(["scoped-transaction", "run", "--plan", aide_lite.SCOPED_TRANSACTION_FIXTURE_PLAN_JSON_PATH])
            fixture = root / ".aide/examples/apply/scoped-transaction-executor-fixtures/valid_input.md"
            before = fixture.read_text(encoding="utf-8")
            result = args.handler(args)
            after = fixture.read_text(encoding="utf-8")
            self.assertEqual(result, 0)
            self.assertEqual(before, after)

    def test_checked_in_dry_run_example_passes_and_preserves_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_scoped_transaction_files(root)
            parser = aide_lite.build_parser(root)
            args = parser.parse_args(["scoped-transaction", "run", "--plan", ".aide/examples/apply/scoped-transaction-executor.dry-run.example.json"])
            fixture = root / ".aide/examples/apply/scoped-transaction-executor-fixtures/valid_input.md"
            before = fixture.read_text(encoding="utf-8")
            result = args.handler(args)
            after = fixture.read_text(encoding="utf-8")
            report = json.loads((root / ".aide/reports/scoped-transaction-executor-example-report.json").read_text(encoding="utf-8"))
            self.assertEqual(result, 0)
            self.assertEqual(before, after)
            self.assertEqual(report["status"], "PASS")
            self.assertFalse(report["target_files_mutated"])
            self.assertEqual(report["report_path"], ".aide/reports/scoped-transaction-executor-example-report.json")


if __name__ == "__main__":
    unittest.main()
