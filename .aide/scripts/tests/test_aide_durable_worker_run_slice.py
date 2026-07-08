from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.execution import local_process_host as host
from core.service import durable_worker_run


def write_text(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def run_git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True, shell=False)
    return result.stdout.strip()


def create_aide_fixture(root: Path) -> str:
    root.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True, text=True, shell=False)
    run_git(root, "config", "user.email", "aide-tests@example.invalid")
    run_git(root, "config", "user.name", "AIDE Tests")
    for rel in [
        host.FIXTURE_WORKER_REL,
        host.HOST_MODULE_REL,
        host.PROVIDER_REL,
        host.PROCESS_INVOCATION_REL,
        host.EXECUTION_RECEIPT_REL,
        host.AIDE_LITE_REL,
    ]:
        source = REPO_ROOT / rel
        write_text(root, rel.as_posix(), source.read_text(encoding="utf-8") if source.is_file() else f"fixture {rel.as_posix()}\n")
    run_git(root, "add", ".")
    run_git(root, "commit", "-m", "fixture: add durable worker run sources")
    return run_git(root, "rev-parse", "HEAD")


def stable_json(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def event(kind: str, sequence: int, payload: dict | None = None) -> dict:
    return {
        "schema_version": host.FIXTURE_EVENT_SCHEMA,
        "run_ref": host.RUN_REF,
        "sequence": sequence,
        "event_kind": kind,
        "timestamp": host.DETERMINISTIC_TIMESTAMP,
        "payload": payload or {},
    }


def event_stream(artifact_text: str) -> str:
    digest = host.sha256_text(artifact_text)
    size = len(artifact_text.encode("utf-8"))
    events = [
        event("run_created", 1, {"workunit_ref": host.WORKUNIT_REF}),
        event("run_started", 2, {"worker_kind": "local_reference_worker"}),
        event("worker_message", 3, {"message": "fixture worker executed"}),
        event("artifact_produced", 4, {"path": host.ARTIFACT_MEMBER, "media_type": "application/json", "byte_count": size, "sha256": digest}),
        event("usage_updated", 5, {"events": 6, "artifacts": 1, "processes": 1}),
        event("run_completed", 6, {"result": "PASS"}),
    ]
    return "\n".join(json.dumps(item, sort_keys=True) for item in events) + "\n"


class FakeRunner:
    def __init__(self, artifact_text: str):
        self.artifact_text = artifact_text
        self.stdout = event_stream(artifact_text)
        self.calls: list[dict] = []

    def __call__(self, argv, cwd, env, timeout):
        self.calls.append({"argv": list(argv), "cwd": str(cwd), "env": dict(env), "timeout": timeout, "shell": False})
        artifact = host.resolve_workspace_member(Path(cwd), host.ARTIFACT_MEMBER)
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(self.artifact_text, encoding="utf-8", newline="\n")
        return subprocess.CompletedProcess(list(argv), 0, self.stdout, "")


class DurableLocalWorkerRunSliceTests(unittest.TestCase):
    def test_fixture_persists_worker_run_events_artifacts_and_restarts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "aide"
            create_aide_fixture(root)
            state_root = Path(tmp) / "state"
            artifact_text = stable_json({"fixture_version": "durable", "result": "PASS", "run_ref": host.RUN_REF})
            fake = FakeRunner(artifact_text)

            report = durable_worker_run.fixture(root, state_root=state_root, runner=fake, python_executable=sys.executable, write_reports=False)

            self.assertEqual(report["status"], "PASS_WITH_WARNINGS")
            self.assertEqual(report["authorization_result"], "allowed")
            self.assertEqual(report["process_call_count"], 1)
            self.assertEqual(len(fake.calls), 1)
            self.assertTrue(report["trust_grant_consumed"])
            self.assertEqual(report["service_event_sequences"], [1, 2, 3, 4, 5, 6])
            self.assertEqual(report["reopened_event_sequences"], [1, 2, 3, 4, 5, 6])
            self.assertTrue(report["idempotent_replay_no_second_host_launch"])
            self.assertEqual(report["host_call_count_after_replay"], 1)
            self.assertEqual(sorted(report["service_objects_persisted"]), ["event_record", "evidence_packet", "host_outcome", "worker_run", "workunit"])
            self.assertEqual(len(report["artifact_metadata"]), 2)
            self.assertTrue(report["source_snapshot_unchanged"])
            self.assertFalse(report["network_calls_performed"])
            self.assertFalse(report["provider_model_calls_performed"])
            self.assertFalse(report["repository_mutation_performed"])
            event_record = durable_worker_run.build_event_record(report)
            self.assertEqual(event_record["spec"]["payload"]["result"], "PASS")

    def test_validation_rejects_missing_durable_evidence(self) -> None:
        validation = durable_worker_run.validate_fixture_report(
            {
                "authorization_result": "allowed",
                "trust_grant_consumed": True,
                "host_result": "PASS",
                "process_call_count": 1,
                "reference_worker_process_started": True,
                "workspace_state_unchanged": True,
                "service_objects_persisted": ["workunit"],
                "service_event_sequences": [1, 2],
                "service_event_types": ["trust.authorization_evaluated", "trust.grant_consumed"],
                "reopened_event_sequences": [1, 2],
                "artifact_metadata": [],
                "reopened_artifact_metadata": [],
                "idempotent_replay_no_second_host_launch": True,
                "host_call_count_after_replay": 1,
                "source_snapshot_unchanged": True,
                **{field: False for field in durable_worker_run.FALSE_BOUNDARY_FIELDS},
            }
        )
        self.assertEqual(validation["status"], "FAILED_VALIDATION")
        self.assertIn("objects_persisted", validation["validation_errors"])
        self.assertIn("events_monotonic", validation["validation_errors"])
        self.assertIn("artifact_metadata_persisted", validation["validation_errors"])

    def test_report_outputs_are_deterministic_with_fake_runner(self) -> None:
        reports: list[dict] = []
        with tempfile.TemporaryDirectory() as tmp:
            for index in range(2):
                root = Path(tmp) / f"aide-{index}"
                create_aide_fixture(root)
                artifact_text = stable_json({"fixture_version": "durable", "result": "PASS", "run_ref": host.RUN_REF})
                fake = FakeRunner(artifact_text)
                report = durable_worker_run.fixture(root, state_root=Path(tmp) / f"state-{index}", runner=fake, python_executable=sys.executable, write_reports=False)
                report.pop("artifact_metadata", None)
                report.pop("reopened_artifact_metadata", None)
                reports.append(report)
        self.assertEqual(stable_json(reports[0]), stable_json(reports[1]))

    def test_status_cli_is_safe_without_running_fixture(self) -> None:
        result = subprocess.run(
            [sys.executable, ".aide/scripts/aide_lite.py", "durable-worker-run", "status"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            shell=False,
        )
        self.assertIn("AIDE Lite durable-worker-run status", result.stdout)
        self.assertIn("proposed_capability_label: durable_local_worker_run_slice_v0", result.stdout)
        self.assertIn("network_calls_performed: false", result.stdout)


if __name__ == "__main__":
    unittest.main()
