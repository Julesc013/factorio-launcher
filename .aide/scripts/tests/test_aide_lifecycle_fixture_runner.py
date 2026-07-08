from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

from core.apply import lifecycle_fixture_runner as runner


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_lifecycle_fixture_runner", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_lifecycle_fixture_runner"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


COMMAND_VECTORS = [
    ["lifecycle-fixture", "status"],
    ["lifecycle-fixture", "run", "--scenario", "install-managed-section", "--mode", "apply-temp"],
    ["lifecycle-fixture", "verify"],
]

REQUIRED_FILES = [
    "core/apply/__init__.py",
    "core/apply/managed_sections.py",
    "core/apply/lifecycle_fixture_runner.py",
    ".aide/examples/apply/lifecycle-fixtures/scenarios.json",
    ".aide/examples/apply/lifecycle-fixtures/generated-plans/install-managed-section.plan.json",
    ".aide/examples/apply/lifecycle-fixtures/expected-reports/install-managed-section.report.json",
    ".aide/examples/apply/lifecycle-fixtures/rollback-records/install-managed-section.rollback.json",
    ".aide/examples/apply/lifecycle-fixtures/target/existing-managed-section/manual/with-managed-section.md",
    ".aide/examples/apply/lifecycle-fixtures/expected/install-managed-section/manual/with-managed-section.md",
]


def copy_lifecycle_fixture_files(root: Path) -> None:
    for rel in REQUIRED_FILES:
        aide_lite.copy_pack_file(REPO_ROOT / rel, root / rel)


class AIDELifecycleFixtureRunnerTests(unittest.TestCase):
    def test_parser_accepts_lifecycle_fixture_commands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        for command in COMMAND_VECTORS:
            parsed = parser.parse_args(command)
            self.assertTrue(callable(getattr(parsed, "handler", None)), command)

    def test_run_mutates_temp_workspace_only_and_matches_expected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_lifecycle_fixture_files(root)
            canonical = root / ".aide/examples/apply/lifecycle-fixtures/target/existing-managed-section/manual/with-managed-section.md"
            expected = root / ".aide/examples/apply/lifecycle-fixtures/expected/install-managed-section/manual/with-managed-section.md"
            before = canonical.read_text(encoding="utf-8")

            report = runner.run_lifecycle_fixture(root, workspace_name="test")

            after = canonical.read_text(encoding="utf-8")
            temp_target = root / str(report["temp_target_path"])
            self.assertEqual(before, after)
            self.assertEqual(temp_target.read_text(encoding="utf-8"), expected.read_text(encoding="utf-8"))
            self.assertEqual(report["capability_label"], "fixture_temp_apply_only")
            self.assertIn("active_repo_apply", report["not_capabilities"])
            self.assertFalse(report["canonical_fixture_mutated"])
            self.assertFalse(report["target_repo_mutated"])
            self.assertFalse(report["active_repo_apply_mutation"])
            self.assertFalse(report["rollback_execution_implemented"])
            self.assertFalse(report["rollback_executed"])
            self.assertFalse(report["service_ready"])
            self.assertFalse(report["commander_ready"])
            self.assertFalse(report["provider_adapter_ready"])
            self.assertEqual(report["mutation_scope"], "temp_workspace_only")
            self.assertEqual(report["operation_type"], "update_managed_section")
            self.assertEqual(report["scoped_transaction_target_class"], "temp_fixture")
            self.assertTrue(report["scoped_transaction_apply_executed"])
            self.assertTrue(report["validation"]["canonical_fixture_unchanged"])
            self.assertTrue((root / ".aide/reports/lifecycle-fixture-runner/verify.json").exists())
            self.assertTrue((root / ".aide/reports/lifecycle-fixture-runner/verify.md").exists())
            self.assertTrue((root / ".aide/reports/lifecycle-fixture-runner/future-work.md").exists())
            self.assertTrue((root / ".aide/reports/lifecycle-fixture-runner/unfinished-work.md").exists())

    def test_status_writes_future_and_unfinished_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_lifecycle_fixture_files(root)

            report = runner.lifecycle_fixture_status(root)

            self.assertEqual(report["result"], "PASS")
            self.assertTrue((root / ".aide/reports/lifecycle-fixture-runner/future-work.md").exists())
            self.assertTrue((root / ".aide/reports/lifecycle-fixture-runner/unfinished-work.md").exists())

    def test_verify_latest_completed_run_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_lifecycle_fixture_files(root)
            runner.run_lifecycle_fixture(root, workspace_name="test")

            report = runner.verify_lifecycle_fixture(root)

            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["capability_label"], "fixture_temp_apply_only")
            self.assertTrue(report["latest_run_report_parsed"])
            self.assertTrue(report["temp_workspace_exists"])
            self.assertTrue(report["rollback_record_exists"])
            self.assertTrue(report["report_hashes_match_observed_files"])
            self.assertTrue(report["canonical_fixture_unchanged"])
            self.assertTrue(report["temp_postimage_matches_expected"])
            self.assertTrue(report["manual_content_preserved"])
            self.assertTrue(report["no_overclaiming_detected"])
            self.assertTrue(report["unsupported_capabilities_not_claimed"])
            failures = [check for check in report["checks"] if check["result"] == "FAIL"]
            self.assertEqual(failures, [])

    def test_verify_fails_closed_without_latest_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_lifecycle_fixture_files(root)

            report = runner.verify_lifecycle_fixture(root)

            self.assertEqual(report["status"], "FAIL")
            self.assertTrue((root / ".aide/reports/lifecycle-fixture-runner/latest-verify.json").exists())
            self.assertTrue((root / ".aide/reports/lifecycle-fixture-runner/verify.json").exists())

    def test_verify_fails_closed_with_malformed_latest_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_lifecycle_fixture_files(root)
            report_path = root / ".aide/reports/lifecycle-fixture-runner/latest-run.json"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text("{bad-json", encoding="utf-8")

            report = runner.verify_lifecycle_fixture(root)

            self.assertEqual(report["status"], "FAIL")
            self.assertFalse(report["latest_run_report_parsed"])

    def test_cli_status_run_and_verify_use_temp_repo_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_lifecycle_fixture_files(root)
            parser = aide_lite.build_parser(root)

            status_args = parser.parse_args(["lifecycle-fixture", "status"])
            run_args = parser.parse_args(["lifecycle-fixture", "run", "--scenario", "install-managed-section", "--mode", "apply-temp"])
            verify_args = parser.parse_args(["lifecycle-fixture", "verify"])

            self.assertEqual(status_args.handler(status_args), 0)
            self.assertEqual(run_args.handler(run_args), 0)
            self.assertEqual(verify_args.handler(verify_args), 0)

    def test_unsupported_scenario_and_mode_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_lifecycle_fixture_files(root)
            with self.assertRaises(runner.LifecycleFixtureError):
                runner.run_lifecycle_fixture(root, scenario_id="unsupported", mode="apply-temp")
            with self.assertRaises(runner.LifecycleFixtureError):
                runner.run_lifecycle_fixture(root, scenario_id="install-managed-section", mode="unsupported")

    def test_scoped_executor_rejects_unsupported_operation_and_malformed_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            workspace.mkdir()
            executor = runner.ScopedExecutor()
            with self.assertRaises(runner.LifecycleFixtureError):
                executor.apply({"operations": []}, workspace)
            with self.assertRaises(runner.LifecycleFixtureError):
                executor.apply({"operations": [{}, {}]}, workspace)
            with self.assertRaises(runner.LifecycleFixtureError):
                executor.apply({"operations": [{"operation_type": "delete_file", "path": "manual/with-managed-section.md"}]}, workspace)

    def test_rollback_record_is_compatible_but_not_executed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_lifecycle_fixture_files(root)
            report = runner.run_lifecycle_fixture(root, workspace_name="test")
            rollback = runner.load_json(root / report["rollback_record_path"])

            self.assertEqual(rollback["record_type"], "LifecycleFixtureRollbackCompatibleRecord")
            self.assertEqual(rollback["operation_type"], "update_managed_section")
            self.assertFalse(rollback["apply_allowed"])
            self.assertFalse(rollback["rollback_execution_implemented"])
            self.assertFalse(rollback["rollback_executed"])

    def test_verify_fails_closed_on_overclaiming_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_lifecycle_fixture_files(root)
            runner.run_lifecycle_fixture(root, workspace_name="test")
            report_path = root / ".aide/reports/lifecycle-fixture-runner/latest-run.json"
            report = runner.load_json(report_path)
            report["production_ready"] = True
            runner.write_json(report_path, report)

            verify = runner.verify_lifecycle_fixture(root)

            self.assertEqual(verify["status"], "FAIL")
            self.assertFalse(verify["no_overclaiming_detected"])

    def test_verify_fails_closed_on_malformed_rollback_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_lifecycle_fixture_files(root)
            report = runner.run_lifecycle_fixture(root, workspace_name="test")
            (root / report["rollback_record_path"]).write_text("{bad-json", encoding="utf-8")

            verify = runner.verify_lifecycle_fixture(root)

            self.assertEqual(verify["status"], "FAIL")

    def test_verify_fails_closed_on_missing_required_run_field(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_lifecycle_fixture_files(root)
            runner.run_lifecycle_fixture(root, workspace_name="test")
            report_path = root / ".aide/reports/lifecycle-fixture-runner/latest-run.json"
            report = runner.load_json(report_path)
            del report["created_at"]
            runner.write_json(report_path, report)

            verify = runner.verify_lifecycle_fixture(root)

            self.assertEqual(verify["status"], "FAIL")

    def test_aide_lite_keeps_lifecycle_fixture_behavior_in_runner_module(self) -> None:
        source = MODULE_PATH.read_text(encoding="utf-8")

        self.assertIn("load_lifecycle_fixture_runner_module", source)
        self.assertNotIn("class ScenarioLoader", source)
        self.assertNotIn("class ScopedExecutor", source)
        self.assertIn("class ScenarioLoader", (REPO_ROOT / "core/apply/lifecycle_fixture_runner.py").read_text(encoding="utf-8"))

    def test_path_jail_rejects_absolute_and_parent_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp) / "workspace"
            workspace.mkdir()
            with self.assertRaises(runner.PathJailError):
                runner.resolve_under_jail(workspace, "../outside.md")
            with self.assertRaises(runner.PathJailError):
                runner.resolve_under_jail(workspace, "C:/outside.md")
            with self.assertRaises(runner.PathJailError):
                runner.resolve_under_jail(workspace, "")
            with self.assertRaises(runner.PathJailError):
                runner.resolve_under_jail(workspace, "*.md")

    def test_replace_managed_section_block_fails_on_missing_marker(self) -> None:
        with self.assertRaises(runner.LifecycleFixtureError):
            runner.replace_managed_section_block(
                "manual before\nmanual after\n",
                "manual before\nmanual after\n",
                "missing.section",
                "manual/with-managed-section.md",
            )

    def test_path_jail_rejects_symlink_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = root / "workspace"
            outside = root / "outside"
            workspace.mkdir()
            outside.mkdir()
            outside_file = outside / "fixture.md"
            outside_file.write_text("outside\n", encoding="utf-8")
            link = workspace / "link.md"
            try:
                link.symlink_to(outside_file)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlink unavailable: {exc}")
            with self.assertRaises(runner.PathJailError):
                runner.resolve_under_jail(workspace, "link.md")


if __name__ == "__main__":
    unittest.main()
