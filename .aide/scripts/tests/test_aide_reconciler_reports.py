from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from core.reconciler import reconciler_reports


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_reconciler", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_reconciler"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


def reconciler_source_files() -> list[str]:
    files = {
        ".aide/scripts/aide_lite.py",
        "core/reconciler/__init__.py",
        "core/reconciler/reconciler_reports.py",
    }
    files.update(reconciler_reports.SOURCE_ARTIFACTS)
    okf_root = REPO_ROOT / ".aide/knowledge/okf"
    if okf_root.exists():
        for path in okf_root.rglob("*.md"):
            files.add(path.relative_to(REPO_ROOT).as_posix())
    okf_accept_task = REPO_ROOT / ".aide/queue/AIDE-ACCEPT-OKF-KNOWLEDGE-BUNDLE-01"
    if okf_accept_task.exists():
        for path in okf_accept_task.rglob("*"):
            if path.is_file():
                files.add(path.relative_to(REPO_ROOT).as_posix())
    okf_accept_reports = REPO_ROOT / ".aide/reports/okf-accept"
    if okf_accept_reports.exists():
        for path in okf_accept_reports.rglob("*"):
            if path.is_file():
                files.add(path.relative_to(REPO_ROOT).as_posix())
    return sorted(files)


def copy_reconciler_files(root: Path) -> None:
    for rel in reconciler_source_files():
        source = REPO_ROOT / rel
        if source.exists():
            aide_lite.copy_pack_file(source, root / rel)


class AIDEReconcilerReportsTests(unittest.TestCase):
    def test_collect_findings_reports_known_drift_without_repair(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_reconciler_files(root)
            findings = reconciler_reports.collect_findings(root)
            categories = {item["category"] for item in findings}
            self.assertIn("stale_context", categories)
            self.assertIn("acceptance_gate_debt", categories)
            self.assertIn("stale_generated_report", categories)
            for finding in findings:
                self.assertFalse(finding["repair_authorized"])
                self.assertFalse(finding["mutates_source_truth"])
                self.assertEqual(finding["report_only_disposition"], "reported_only_no_repair")

    def test_report_writes_required_files_and_preserves_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_reconciler_files(root)
            source_paths = [root / rel for rel in reconciler_source_files() if (root / rel).exists()]
            before = {path: path.read_bytes() for path in source_paths}
            report = reconciler_reports.write_reconciliation_reports(root)
            self.assertEqual(report["status"], "PASS_WITH_WARNINGS")
            self.assertTrue(report["report_only"])
            self.assertTrue(report["detects_drift"])
            self.assertFalse(report["repair_implemented"])
            self.assertFalse(report["mutation_performed"])
            self.assertFalse(report["source_truth_mutation"])
            self.assertFalse(report["source_artifacts_mutated"])
            self.assertEqual(before, {path: path.read_bytes() for path in source_paths})
            for rel in reconciler_reports.REQUIRED_REPORTS:
                self.assertTrue((root / rel).exists(), rel.as_posix())

    def test_validation_accepts_report_only_warning_findings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_reconciler_files(root)
            reconciler_reports.write_reconciliation_reports(root)
            validation = reconciler_reports.validate_reconciler_reports(root)
            self.assertEqual(validation["validation_status"], "PASS_WITH_WARNINGS")
            self.assertTrue(validation["report_files_present"])
            self.assertTrue(validation["json_reports_valid"])
            self.assertTrue(validation["required_fields_present"])
            self.assertTrue(validation["taxonomy_categories_present"])
            self.assertTrue(validation["finding_schema_valid"])
            self.assertTrue(validation["report_only_boundary_preserved"])
            self.assertTrue(validation["overclaiming_check_passed"])
            self.assertTrue(validation["forbidden_ops_preserved"])

    def test_taxonomy_contains_expected_categories(self) -> None:
        taxonomy = reconciler_reports.build_taxonomy_payload()
        categories = {item["category"] for item in taxonomy["categories"]}
        for expected in [
            "stale_context",
            "acceptance_gate_debt",
            "missing_evidence",
            "missing_report",
            "stale_generated_report",
            "source_hash_gap",
            "reference_mismatch",
            "event_mismatch",
            "capability_overclaim",
        ]:
            self.assertIn(expected, categories)

    def test_reconciler_cli_status_report_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_reconciler_files(root)
            parser = aide_lite.build_parser(REPO_ROOT)
            commands = [
                ["--repo-root", str(root), "reconciler", "status"],
                ["--repo-root", str(root), "reconciler", "report"],
                ["--repo-root", str(root), "reconciler", "validate"],
            ]
            for command in commands:
                parsed = parser.parse_args(command)
                output = io.StringIO()
                with redirect_stdout(output):
                    result = parsed.handler(parsed)
                self.assertEqual(result, 0, output.getvalue())
                self.assertIn("report_only: true", output.getvalue())
                self.assertIn("detects_drift: true", output.getvalue())
                self.assertIn("repair_implemented: false", output.getvalue())
                self.assertIn("mutation_performed: false", output.getvalue())
                self.assertIn("source_truth_mutation: false", output.getvalue())
                self.assertIn("provider_or_model_calls: none", output.getvalue())

    def test_reconciler_cli_rejects_repair_and_runtime_subcommands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        for subcommand in ["repair", "apply", "fix", "mutate", "serve", "schedule", "run", "sync"]:
            with self.subTest(subcommand=subcommand):
                stderr = io.StringIO()
                with redirect_stdout(io.StringIO()), redirect_stderr(stderr), self.assertRaises(SystemExit):
                    parser.parse_args(["reconciler", subcommand])

    def test_json_reports_parse(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_reconciler_files(root)
            reconciler_reports.write_reconciliation_reports(root)
            for rel in [
                ".aide/reports/reconciler/reconciliation-report.json",
                ".aide/reports/reconciler/validation.json",
                ".aide/reports/reconciler/findings.json",
                ".aide/reports/reconciler/finding-taxonomy.json",
            ]:
                data = json.loads((root / rel).read_text(encoding="utf-8"))
                self.assertEqual(data["task_id"], "AIDE-BUILD-RECONCILER-REPORTS-01")


if __name__ == "__main__":
    unittest.main()
