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
SPEC = importlib.util.spec_from_file_location("aide_lite_workunit_cli_mutation", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_workunit_cli_mutation"] = aide_lite
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
]


def copy_workunit_cli_files(root: Path) -> None:
    for rel in SOURCE_FILES:
        aide_lite.copy_pack_file(REPO_ROOT / rel, root / rel)


def make_queue_root(root: Path) -> None:
    (root / ".aide/queue").mkdir(parents=True)
    (root / ".aide/queue/index.yaml").write_text(
        "schema_version: aide.queue-index.v0\nitems:\n",
        encoding="utf-8",
        newline="\n",
    )


def write_create_spec(root: Path, task_id: str = "AIDE-SAMPLE-METADATA-TASK-01") -> Path:
    spec = {
        "apiVersion": "aide.dev/v1alpha1",
        "kind": "WorkUnitCreateRequest",
        "metadata": {"id": task_id, "name": task_id},
        "spec": {
            "task_id": task_id,
            "title": "Sample metadata-only queued WorkUnit",
            "work_type": "build",
            "authorizes_implementation": False,
            "check_only": False,
            "acceptance_review": False,
            "implementation_scope": "metadata-only-placeholder",
            "stop_state": "needs_review",
            "predecessors": [],
            "dependencies": [],
            "scope": {"allowed_paths": [], "forbidden_paths": []},
            "validation": {"commands": []},
            "evidence_requirements": [],
            "explicit_non_capabilities": [
                "workunit_claim",
                "workunit_run",
                "workunit_finish",
                "workunit_repair",
                "runtime",
                "scheduler",
                "provider_adapter",
            ],
        },
    }
    path = root / ".aide/tmp/workunit-cli-mutation/create-request.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec, indent=2), encoding="utf-8", newline="\n")
    return path


def queue_hashes(root: Path) -> dict[str, bytes]:
    paths = sorted((root / ".aide/queue").glob("**/*"))
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in paths if path.is_file()}


class AIDEWorkUnitCliMutationTests(unittest.TestCase):
    def test_create_dry_run_writes_report_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_queue_root(root)
            spec = write_create_spec(root)
            before = queue_hashes(root)
            report = workunit_cli.workunit_cli_create(root, spec, dry_run=True)
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["mode"], "dry-run")
            self.assertFalse((root / ".aide/queue/AIDE-SAMPLE-METADATA-TASK-01").exists())
            self.assertEqual(before, queue_hashes(root))
            self.assertTrue((root / ".aide/reports/workunit-cli-mutation/latest-create.json").exists())

    def test_create_apply_writes_only_new_task_and_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_queue_root(root)
            spec = write_create_spec(root)
            report = workunit_cli.workunit_cli_create(root, spec, apply=True)
            task_dir = root / ".aide/queue/AIDE-SAMPLE-METADATA-TASK-01"
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["mode"], "apply")
            self.assertTrue((task_dir / "task.yaml").exists())
            self.assertTrue((task_dir / "status.yaml").exists())
            self.assertTrue((task_dir / "ExecPlan.md").exists())
            self.assertTrue((task_dir / "prompt.md").exists())
            self.assertTrue((task_dir / "evidence/validation.md").exists())
            index = (root / ".aide/queue/index.yaml").read_text(encoding="utf-8")
            self.assertIn("AIDE-SAMPLE-METADATA-TASK-01", index)
            self.assertFalse(report["run_executed"])
            self.assertFalse(report["worker_lease_created"])

    def test_create_rejects_duplicate_and_unsafe_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_queue_root(root)
            spec = write_create_spec(root)
            workunit_cli.workunit_cli_create(root, spec, apply=True)
            with self.assertRaises(ValueError):
                workunit_cli.workunit_cli_create(root, spec, apply=True)
            unsafe = write_create_spec(root, "../escape")
            with self.assertRaises(ValueError):
                workunit_cli.workunit_cli_create(root, unsafe, dry_run=True)

    def test_block_dry_run_does_not_mutate_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_queue_root(root)
            spec = write_create_spec(root)
            workunit_cli.workunit_cli_create(root, spec, apply=True)
            before = queue_hashes(root)
            report = workunit_cli.workunit_cli_block(
                root,
                "AIDE-SAMPLE-METADATA-TASK-01",
                reason="human_decision",
                note="validation dry-run",
                dry_run=True,
            )
            self.assertEqual(report["status"], "PASS")
            self.assertEqual(report["mode"], "dry-run")
            self.assertEqual(before, queue_hashes(root))

    def test_block_apply_updates_status_and_blocker_record_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_queue_root(root)
            spec = write_create_spec(root)
            workunit_cli.workunit_cli_create(root, spec, apply=True)
            report = workunit_cli.workunit_cli_block(
                root,
                "AIDE-SAMPLE-METADATA-TASK-01",
                reason="human_decision",
                note="validation apply",
                apply=True,
            )
            self.assertEqual(report["status"], "PASS")
            status_text = (root / ".aide/queue/AIDE-SAMPLE-METADATA-TASK-01/status.yaml").read_text(encoding="utf-8")
            self.assertIn("status: blocked", status_text)
            self.assertIn("blocked_reason: human_decision", status_text)
            self.assertTrue((root / ".aide/queue/AIDE-SAMPLE-METADATA-TASK-01/evidence/blocker.md").exists())
            self.assertFalse(report["run_executed"])

    def test_evidence_add_apply_updates_pointer_without_copying_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_queue_root(root)
            spec = write_create_spec(root)
            workunit_cli.workunit_cli_create(root, spec, apply=True)
            evidence = root / ".aide/reports/workunit-cli-mutation/sample-validation.json"
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_text('{"status":"PASS"}\n', encoding="utf-8")
            report = workunit_cli.workunit_cli_evidence_add(
                root,
                "AIDE-SAMPLE-METADATA-TASK-01",
                evidence,
                role="validation",
                apply=True,
            )
            self.assertEqual(report["status"], "PASS")
            self.assertFalse(report["referenced_artifact_mutated"])
            status_text = (root / ".aide/queue/AIDE-SAMPLE-METADATA-TASK-01/status.yaml").read_text(encoding="utf-8")
            self.assertIn(".aide/reports/workunit-cli-mutation/sample-validation.json", status_text)
            self.assertTrue((root / ".aide/queue/AIDE-SAMPLE-METADATA-TASK-01/evidence/evidence-pointers.json").exists())

    def test_evidence_add_rejects_external_or_secret_like_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            make_queue_root(root)
            spec = write_create_spec(root)
            workunit_cli.workunit_cli_create(root, spec, apply=True)
            external = Path(temp).parent / "outside-evidence.txt"
            external.write_text("outside\n", encoding="utf-8")
            try:
                with self.assertRaises(ValueError):
                    workunit_cli.workunit_cli_evidence_add(
                        root,
                        "AIDE-SAMPLE-METADATA-TASK-01",
                        external,
                        role="validation",
                        dry_run=True,
                    )
            finally:
                external.unlink(missing_ok=True)
            secret_like = root / "secrets/report.md"
            secret_like.parent.mkdir()
            secret_like.write_text("secret-like\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                workunit_cli.workunit_cli_evidence_add(
                    root,
                    "AIDE-SAMPLE-METADATA-TASK-01",
                    secret_like,
                    role="validation",
                    dry_run=True,
                )

    def test_parser_supports_metadata_mutation_commands_and_modes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_workunit_cli_files(root)
            make_queue_root(root)
            spec = write_create_spec(root)
            parser = aide_lite.build_parser(REPO_ROOT)
            create_command = ["--repo-root", str(root), "workunit", "create", "--from-spec", str(spec), "--dry-run"]
            parsed = parser.parse_args(create_command)
            output = io.StringIO()
            with redirect_stdout(output):
                result = parsed.handler(parsed)
            self.assertEqual(result, 0, output.getvalue())
            self.assertIn("runtime_state_created: false", output.getvalue())
            self.assertIn("provider_or_model_calls: none", output.getvalue())
            workunit_cli.workunit_cli_create(root, spec, apply=True)
            commands = [
                [
                    "--repo-root",
                    str(root),
                    "workunit",
                    "block",
                    "--task-id",
                    "AIDE-SAMPLE-METADATA-TASK-01",
                    "--reason",
                    "human_decision",
                    "--note",
                    "parser dry-run",
                    "--dry-run",
                ],
            ]
            for command in commands:
                parsed = parser.parse_args(command)
                output = io.StringIO()
                with redirect_stdout(output):
                    result = parsed.handler(parsed)
                self.assertEqual(result, 0, output.getvalue())
                self.assertIn("runtime_state_created: false", output.getvalue())
                self.assertIn("provider_or_model_calls: none", output.getvalue())

    def test_claim_run_finish_repair_still_fail_closed(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        for command in ["claim", "run", "finish", "repair"]:
            stderr = io.StringIO()
            with self.assertRaises(SystemExit) as raised, redirect_stderr(stderr):
                parser.parse_args(["workunit", command])
            self.assertNotEqual(raised.exception.code, 0)
            self.assertIn("invalid choice", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
