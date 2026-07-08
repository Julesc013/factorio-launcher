from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from core.protocol import workunit_cli


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_workunit_cli", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_workunit_cli"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


SOURCE_FILES = [
    "core/protocol/__init__.py",
    "core/protocol/envelope.py",
    "core/protocol/evidence_packet.py",
    "core/protocol/workunit.py",
    "core/protocol/workunit_cli.py",
    ".aide/protocol/aide-envelope.schema.json",
    ".aide/protocol/aide-evidence-packet.schema.json",
    ".aide/protocol/aide-workunit.schema.json",
    ".aide/reports/workunit-queue/validation.json",
    ".aide/reports/evidence-packet/validation.json",
    ".aide/reports/evidence-packet-acceptance/acceptance-report.json",
    ".aide/reports/contract-envelope/validation.json",
    ".aide/reports/lifecycle-fixture-runner/latest-run.json",
    ".aide/reports/lifecycle-fixture-runner/verify.json",
]


def copy_workunit_cli_files(root: Path) -> None:
    for rel in SOURCE_FILES:
        source = REPO_ROOT / rel
        if source.exists():
            aide_lite.copy_pack_file(source, root / rel)
    projections = REPO_ROOT / ".aide/reports/workunit-queue/projections"
    if projections.exists():
        for source in projections.glob("*.json"):
            aide_lite.copy_pack_file(source, root / ".aide/reports/workunit-queue/projections" / source.name)
    for task_dir in sorted((REPO_ROOT / ".aide/queue").glob("AIDE-*")):
        if not task_dir.is_dir():
            continue
        for name in ["task.yaml", "status.yaml", "ExecPlan.md", "prompt.md"]:
            source = task_dir / name
            if source.exists():
                aide_lite.copy_pack_file(source, root / ".aide/queue" / task_dir.name / name)
        evidence_dir = task_dir / "evidence"
        if evidence_dir.exists():
            for source in evidence_dir.glob("*.md"):
                aide_lite.copy_pack_file(source, root / ".aide/queue" / task_dir.name / "evidence" / source.name)


def queue_source_hashes(root: Path) -> dict[str, bytes]:
    paths: list[Path] = []
    queue_root = root / ".aide/queue"
    paths.extend(sorted(queue_root.glob("AIDE-*/task.yaml")))
    paths.extend(sorted(queue_root.glob("AIDE-*/status.yaml")))
    paths.extend(sorted(queue_root.glob("AIDE-*/evidence/*.md")))
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in paths}


class AIDEWorkUnitCliTests(unittest.TestCase):
    def test_status_reports_readonly_cli_capability(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_workunit_cli_files(root)
            report = workunit_cli.workunit_cli_status(root)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["capability_label"], "minimal_workunit_queue_metadata_mutation_cli")
            self.assertEqual(report["workunit_cli_mode"], "queue_metadata_mutation")
            self.assertTrue(report["workunit_create_implemented"])
            self.assertTrue(report["workunit_block_implemented"])
            self.assertTrue(report["workunit_evidence_add_implemented"])
            self.assertFalse(report["workunit_run_implemented"])
            self.assertFalse(report["source_queue_tasks_mutated"])
            self.assertTrue((root / ".aide/reports/workunit-cli/status.md").exists())

    def test_list_reports_queue_tasks_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_workunit_cli_files(root)
            before = queue_source_hashes(root)
            report = workunit_cli.workunit_cli_list(root)
            after = queue_source_hashes(root)
            self.assertEqual(report["status"], "PASS")
            self.assertGreater(report["task_count"], 0)
            self.assertIn("AIDE-BUILD-WORKUNIT-QUEUE-V1-01", {item["task_id"] for item in report["tasks"]})
            self.assertFalse(report["workunit_run_implemented"])
            self.assertEqual(before, after)
            self.assertTrue((root / ".aide/reports/workunit-cli/list.json").exists())

    def test_inspect_projects_known_task_with_source_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_workunit_cli_files(root)
            before = queue_source_hashes(root)
            report = workunit_cli.workunit_cli_inspect(root, "AIDE-BUILD-WORKUNIT-QUEUE-V1-01")
            after = queue_source_hashes(root)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["inspected_task_id"], "AIDE-BUILD-WORKUNIT-QUEUE-V1-01")
            self.assertTrue(report["source_presence"]["task_yaml_exists"])
            self.assertTrue(report["validation"]["status"] == "PASS")
            self.assertFalse(report["source_queue_tasks_mutated"])
            self.assertEqual(before, after)
            self.assertTrue(
                (root / ".aide/reports/workunit-cli/inspect/AIDE-BUILD-WORKUNIT-QUEUE-V1-01.json").exists()
            )

    def test_inspect_rejects_unsafe_task_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_workunit_cli_files(root)
            for task_id in ["../outside", str(root.resolve()), "AIDE-X/extra", "AIDE-*", ".git", "does-not-exist"]:
                errors = workunit_cli.task_id_errors(root, task_id)
                self.assertTrue(errors, task_id)
                with self.assertRaises(ValueError):
                    workunit_cli.workunit_cli_inspect(root, task_id)

    def test_symlink_escape_is_rejected_when_platform_supports_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_workunit_cli_files(root)
            outside = root / "outside"
            outside.mkdir()
            task_link = root / ".aide/queue/AIDE-SYMLINK-ESCAPE"
            try:
                task_link.symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("directory symlink creation unavailable on this platform")
            errors = workunit_cli.task_id_errors(root, "AIDE-SYMLINK-ESCAPE")
            self.assertTrue(any("outside .aide/queue" in error for error in errors))

    def test_validate_reports_path_safety_and_compatibility(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_workunit_cli_files(root)
            report = workunit_cli.workunit_cli_validate(root)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["capability_label"], "minimal_workunit_queue_metadata_mutation_cli")
            self.assertEqual(report["workunit_cli_mode"], "queue_metadata_mutation")
            self.assertTrue(report["path_traversal_rejected"])
            self.assertTrue(report["absolute_path_rejected"])
            self.assertTrue(report["separator_injection_rejected"])
            self.assertTrue(report["wildcard_rejected"])
            self.assertTrue(report["hidden_path_rejected"])
            self.assertFalse(report["source_queue_tasks_mutated"])
            self.assertFalse(report["destructive_migration_performed"])
            self.assertTrue(report["backwards_compatibility_preserved"])
            self.assertTrue(report["unknown_optional_fields_tolerated"])
            self.assertTrue(report["unknown_required_capability_fails_closed"])
            self.assertTrue((root / ".aide/reports/workunit-cli/validation.json").exists())
            self.assertTrue((root / ".aide/reports/workunit-cli/future-work.md").exists())
            self.assertTrue((root / ".aide/reports/workunit-cli/unfinished-work.md").exists())

    def test_list_inspect_and_validate_do_not_mutate_source_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_workunit_cli_files(root)
            before = queue_source_hashes(root)
            workunit_cli.workunit_cli_list(root)
            workunit_cli.workunit_cli_inspect(root, "AIDE-BUILD-WORKUNIT-QUEUE-V1-01")
            workunit_cli.workunit_cli_validate(root)
            self.assertEqual(before, queue_source_hashes(root))

    def test_workunit_cli_parser_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_workunit_cli_files(root)
            parser = aide_lite.build_parser(REPO_ROOT)
            commands = [
                ["--repo-root", str(root), "workunit", "status"],
                ["--repo-root", str(root), "workunit", "list"],
                ["--repo-root", str(root), "workunit", "inspect", "--task-id", "AIDE-BUILD-WORKUNIT-QUEUE-V1-01"],
                ["--repo-root", str(root), "workunit", "validate"],
            ]
            for command in commands:
                parsed = parser.parse_args(command)
                output = io.StringIO()
                with redirect_stdout(output):
                    result = parsed.handler(parsed)
                self.assertEqual(result, 0, output.getvalue())
                self.assertIn("target_mutation: false", output.getvalue())
                self.assertIn("provider_or_model_calls: none", output.getvalue())
                self.assertIn("network_calls: none", output.getvalue())

    def test_unsupported_mutation_commands_fail_closed(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        for command in ["claim", "run", "finish", "repair"]:
            stderr = io.StringIO()
            with self.assertRaises(SystemExit) as raised, redirect_stderr(stderr):
                parser.parse_args(["workunit", command])
            self.assertNotEqual(raised.exception.code, 0)
            self.assertIn("invalid choice", stderr.getvalue())

    def test_existing_protocol_commands_still_parse_and_run_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_workunit_cli_files(root)
            parser = aide_lite.build_parser(REPO_ROOT)
            for command in [
                ["--repo-root", str(root), "workunit-queue", "status"],
                ["--repo-root", str(root), "evidence-packet", "status"],
                ["--repo-root", str(root), "contract-envelope", "status"],
            ]:
                parsed = parser.parse_args(command)
                output = io.StringIO()
                with redirect_stdout(output):
                    result = parsed.handler(parsed)
                self.assertEqual(result, 0, output.getvalue())
                self.assertIn("target_mutation: false", output.getvalue())
                self.assertIn("network_calls: none", output.getvalue())


if __name__ == "__main__":
    unittest.main()
