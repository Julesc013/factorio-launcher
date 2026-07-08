from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.distribution import apply_engine

MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_distribution_apply", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_distribution_apply"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


def copy_file(root: Path, rel: str) -> None:
    source = REPO_ROOT / rel
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())


def copy_inputs(root: Path, *, include_acceptance_reports: bool = True) -> None:
    for rel in [
        ".aide/scripts/aide_lite.py",
        "core/distribution/__init__.py",
        "core/distribution/apply_context.py",
        "core/distribution/apply_engine.py",
        "core/distribution/apply_reports.py",
        "core/distribution/operation_executor.py",
        "core/distribution/rollback_verifier.py",
        "core/distribution/temp_workspace.py",
    ]:
        copy_file(root, rel)
    if not include_acceptance_reports:
        return
    for rel in [
        ".aide/reports/distribution-manifest-v1-accept/acceptance-report.json",
        ".aide/reports/project-lock-v0-accept/acceptance-report.json",
        ".aide/reports/ownership-ledger-v1-acceptance/acceptance-report.json",
        ".aide/reports/install-record-v0-acceptance/acceptance-report.json",
        ".aide/reports/migration-record-v0-acceptance/acceptance-report.json",
        ".aide/reports/update-plan-v1-acceptance/validation-summary.json",
        ".aide/reports/rollback-bundle-v0-acceptance/validation-summary.json",
        ".aide/reports/update-receipt-v0-acceptance/validation-summary.json",
    ]:
        copy_file(root, rel)


class AIDEDistributionApplyEngineV0Tests(unittest.TestCase):
    def make_repo(self, *, include_acceptance_reports: bool = True) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        copy_inputs(root, include_acceptance_reports=include_acceptance_reports)
        return root

    def test_status_is_fixture_only_and_temp_workspace_only(self) -> None:
        root = self.make_repo()
        status = apply_engine.status(root)
        self.assertEqual(status["status"], "PASS_WITH_WARNINGS")
        self.assertTrue(status["fixture_only"])
        self.assertTrue(status["temp_workspace_only"])
        self.assertTrue(status["update_receipt_accepted"])
        self.assertEqual(status["recommended_next_task"], "AIDE-CHECK-DISTRIBUTION-APPLY-ENGINE-V0-01")

    def test_fixture_corpus_contains_required_positive_and_negative_scenarios(self) -> None:
        root = self.make_repo()
        apply_engine.write_fixture_corpus(root)
        scenario_ids = {
            path.parent.name
            for path in (root / apply_engine.FIXTURE_ROOT).glob("*/scenario.json")
        }
        self.assertTrue(set(apply_engine.POSITIVE_SCENARIOS).issubset(scenario_ids))
        self.assertTrue(set(apply_engine.NEGATIVE_SCENARIOS).issubset(scenario_ids))

    def test_valid_scenarios_execute_in_temp_and_preserve_canonical_fixtures(self) -> None:
        root = self.make_repo()
        for scenario_id in [
            "managed-file-add",
            "managed-file-update",
            "managed-section-update",
            "project-owned-preservation",
            "local-only-preservation",
            "rollback-success",
            "update-receipt-generation",
        ]:
            with self.subTest(scenario_id=scenario_id):
                result = apply_engine.execute_scenario(root, scenario_id)
                self.assertEqual(result["status"], "PASS_WITH_WARNINGS", result)
                self.assertTrue(result["passed"], result)
                self.assertTrue(result["canonical_fixture_unchanged"], result)
                self.assertTrue(result["temp_workspace_only"], result)
                self.assertFalse(result["temp_workspace_retained"], result)
                self.assertFalse(result["real_target_repo_modified"], result)
                self.assertFalse(result["source_repo_apply_occurred"], result)

    def test_negative_scenarios_fail_closed_with_expected_codes(self) -> None:
        root = self.make_repo()
        for scenario_id, expected in sorted(apply_engine.EXPECTED_REFUSALS.items()):
            with self.subTest(scenario_id=scenario_id):
                result = apply_engine.execute_scenario(root, scenario_id)
                self.assertEqual(result["status"], "FAILED_VALIDATION", result)
                self.assertEqual(result["refusal_code"], expected, result)
                self.assertTrue(result["passed"], result)
                self.assertFalse(result["real_target_repo_modified"], result)
                self.assertFalse(result["source_repo_apply_occurred"], result)

    def test_context_binding_regressions_fail_before_execution(self) -> None:
        root = self.make_repo()
        context_scenarios = {
            "missing-update-plan-binding": "distribution_apply_engine.update_plan_binding_missing",
            "missing-rollback-bundle-binding": "distribution_apply_engine.rollback_bundle_binding_missing",
            "mismatched-update-plan-rollback-bundle": "distribution_apply_engine.update_plan_rollback_bundle_mismatch",
            "predecessor-source-distribution-mismatch": "distribution_apply_engine.predecessor_mismatch",
            "predecessor-project-lock-mismatch": "distribution_apply_engine.predecessor_mismatch",
            "predecessor-ownership-ledger-mismatch": "distribution_apply_engine.predecessor_mismatch",
            "predecessor-install-record-mismatch": "distribution_apply_engine.predecessor_mismatch",
            "predecessor-migration-record-mismatch": "distribution_apply_engine.predecessor_mismatch",
            "run-without-accepted-context": "distribution_apply_engine.accepted_context_missing",
        }
        for scenario_id, expected in context_scenarios.items():
            with self.subTest(scenario_id=scenario_id):
                result = apply_engine.execute_scenario(root, scenario_id)
                self.assertEqual(result["status"], "FAILED_VALIDATION", result)
                self.assertEqual(result["refusal_code"], expected, result)
                self.assertTrue(result["passed"], result)
                self.assertFalse(result["accepted_context_valid"], result)
                self.assertFalse(result["update_receipt_generated"], result)
                self.assertEqual(result["operation_results"], [], result)
                self.assertIsNone(result["temp_workspace_digest_before"], result)
                self.assertTrue(result["canonical_fixture_unchanged"], result)
                self.assertFalse(result["real_target_repo_modified"], result)
                self.assertFalse(result["source_repo_apply_occurred"], result)

    def test_missing_acceptance_reports_refuse_before_execution(self) -> None:
        root = self.make_repo(include_acceptance_reports=False)
        result = apply_engine.execute_scenario(root, "managed-file-update")
        self.assertEqual(result["status"], "FAILED_VALIDATION", result)
        self.assertEqual(result["refusal_code"], "distribution_apply_engine.accepted_context_missing", result)
        self.assertFalse(result["accepted_context_valid"], result)
        self.assertFalse(result["update_receipt_generated"], result)
        self.assertEqual(result["operation_results"], [], result)
        self.assertIsNone(result["temp_workspace_digest_before"], result)
        self.assertTrue(result["canonical_fixture_unchanged"], result)

    def test_verify_writes_reports_and_passes_with_warnings(self) -> None:
        root = self.make_repo()
        report = apply_engine.verify(root)
        self.assertEqual(report["validation_status"], "PASS_WITH_WARNINGS", report["errors"])
        self.assertEqual(report["material_finding_count"], 0)
        self.assertEqual(report["missing_evidence"], 0)
        self.assertTrue(report["checks"]["fixture_matrix_passed"])
        self.assertTrue(report["checks"]["canonical_fixture_unchanged"])
        self.assertFalse(report["checks"]["real_target_repo_modified"])
        self.assertTrue((root / ".aide/reports/distribution-apply-engine-v0/validation.json").exists())
        self.assertTrue((root / ".aide/reports/distribution-apply-engine-v0/apply-run.json").exists())

    def test_cli_status_plan_run_verify(self) -> None:
        root = self.make_repo()
        parser = aide_lite.build_parser(REPO_ROOT)
        commands = [
            ["--repo-root", str(root), "distribution-apply", "status"],
            ["--repo-root", str(root), "distribution-apply", "plan", "--scenario", "managed-file-update"],
            ["--repo-root", str(root), "distribution-apply", "run", "--scenario", "managed-file-update", "--mode", "apply-temp"],
            ["--repo-root", str(root), "distribution-apply", "verify"],
        ]
        for command in commands:
            with self.subTest(command=command):
                parsed = parser.parse_args(command)
                output = io.StringIO()
                with redirect_stdout(output):
                    result = parsed.handler(parsed)
                self.assertEqual(result, 0, output.getvalue())
                text = output.getvalue()
                self.assertIn("proposed_capability: distribution_apply_engine_v0", text)
                self.assertIn("fixture_only: true", text)
                self.assertIn("temp_workspace_only: true", text)
                self.assertIn("real_target_apply_implemented: false", text)
                self.assertIn("source_repo_apply_implemented: false", text)

    def test_cli_rejects_non_temp_or_production_subcommands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        with self.assertRaises(SystemExit):
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                parser.parse_args(["distribution-apply", "run", "--scenario", "managed-file-update", "--mode", "apply-real"])
        for subcommand in ["apply", "install", "update", "rollback", "uninstall", "publish", "scan-target"]:
            with self.subTest(subcommand=subcommand), self.assertRaises(SystemExit):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                    parser.parse_args(["distribution-apply", subcommand])


if __name__ == "__main__":
    unittest.main()
