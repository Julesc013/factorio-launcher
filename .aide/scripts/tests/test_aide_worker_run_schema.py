from __future__ import annotations

import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from core.protocol import worker_run


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_worker_run", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_worker_run"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


SOURCE_FILES = [
    "core/protocol/__init__.py",
    "core/protocol/envelope.py",
    "core/protocol/evidence_packet.py",
    "core/protocol/workunit.py",
    "core/protocol/workunit_cli.py",
    "core/protocol/worker_run.py",
    ".aide/protocol/aide-envelope.schema.json",
    ".aide/protocol/aide-evidence-packet.schema.json",
    ".aide/protocol/aide-workunit.schema.json",
    ".aide/protocol/aide-worker-run.schema.json",
]

REPORT_FILES = sorted(
    {
        *(meta["path"].as_posix() for meta in worker_run.SOURCE_ARTIFACTS.values()),
        *(path.as_posix() for path in worker_run.COMPATIBILITY_REPORTS.values()),
    }
)


def copy_worker_run_files(root: Path) -> None:
    for rel in [*SOURCE_FILES, *REPORT_FILES]:
        source = REPO_ROOT / rel
        if source.exists():
            aide_lite.copy_pack_file(source, root / rel)


def sample_run() -> dict[str, object]:
    return worker_run.sample_worker_run()


class AIDEWorkerRunSchemaTests(unittest.TestCase):
    def test_build_worker_run_uses_public_shape(self) -> None:
        obj = sample_run()
        self.assertEqual(obj["apiVersion"], "aide.dev/v1alpha1")
        self.assertEqual(obj["kind"], "WorkerRun")
        self.assertIsInstance(obj["metadata"], dict)
        self.assertIsInstance(obj["spec"], dict)
        self.assertIsInstance(obj["status"], dict)
        self.assertEqual(obj["spec"]["capability_label"], "minimal_worker_run_schema")

    def test_validate_worker_run_accepts_valid_minimal_run(self) -> None:
        self.assertEqual(worker_run.validate_worker_run(sample_run()), [])

    def test_validate_worker_run_rejects_missing_top_level_fields(self) -> None:
        for field in ["apiVersion", "kind", "metadata", "spec", "status"]:
            obj = sample_run()
            obj.pop(field)
            errors = worker_run.validate_worker_run(obj)
            self.assertTrue(any(field in error for error in errors), field)

    def test_validate_worker_run_rejects_wrong_kind(self) -> None:
        obj = sample_run()
        obj["kind"] = "WorkUnit"
        self.assertIn("unsupported kind: WorkUnit", worker_run.validate_worker_run(obj))

    def test_validate_worker_run_rejects_missing_required_spec_fields(self) -> None:
        for field in worker_run.REQUIRED_SPEC_FIELDS:
            obj = sample_run()
            obj["spec"].pop(field)
            errors = worker_run.validate_worker_run(obj)
            self.assertIn(f"missing required spec field: {field}", errors, field)

    def test_validate_worker_run_preserves_explicit_non_capabilities(self) -> None:
        obj = sample_run()
        non_caps = obj["spec"]["explicit_non_capabilities"]
        for capability in ["worker_execution", "workunit_claim", "scheduler", "test_broker", "service_ready"]:
            self.assertIn(capability, non_caps)
        self.assertFalse(worker_run.implemented_capabilities(obj) & set(non_caps))

    def test_validate_worker_run_tolerates_unknown_optional_fields(self) -> None:
        self.assertEqual(worker_run.validate_worker_run(worker_run.sample_unknown_optional_worker_run()), [])

    def test_validate_worker_run_fails_closed_for_unknown_required_capability(self) -> None:
        obj = worker_run.sample_unknown_required_capability_worker_run()
        errors = worker_run.validate_worker_run(obj)
        self.assertIn("unknown required capability: future.required", errors)

    def test_schema_file_parses_and_declares_required_worker_run_fields(self) -> None:
        schema = worker_run.load_worker_run_schema(REPO_ROOT)
        self.assertEqual(schema["required"], ["apiVersion", "kind", "metadata", "spec", "status"])
        self.assertEqual(schema["properties"]["kind"]["enum"], ["WorkerRun"])
        self.assertTrue(schema["additionalProperties"])

    def test_schema_helper_alignment_passes_current_schema(self) -> None:
        schema = worker_run.load_worker_run_schema(REPO_ROOT)
        alignment = worker_run.check_schema_helper_alignment(schema)
        self.assertEqual(alignment["schema_helper_alignment_status"], "PASS")
        self.assertEqual(alignment["errors"], [])

    def test_schema_validation_accepts_valid_worker_run(self) -> None:
        schema = worker_run.load_worker_run_schema(REPO_ROOT)
        self.assertEqual(worker_run.validate_worker_run_with_schema(sample_run(), schema), [])

    def test_schema_validation_rejects_missing_required_fields(self) -> None:
        schema = worker_run.load_worker_run_schema(REPO_ROOT)
        for field in ["apiVersion", "kind", "metadata", "spec", "status"]:
            obj = sample_run()
            obj.pop(field)
            errors = worker_run.validate_worker_run_with_schema(obj, schema)
            self.assertTrue(any(field in error for error in errors), field)

    def test_runtime_schema_validation_fails_closed_for_unknown_required_capability(self) -> None:
        schema = worker_run.load_worker_run_schema(REPO_ROOT)
        result = worker_run.validate_worker_run_runtime(
            worker_run.sample_unknown_required_capability_worker_run(),
            schema,
        )
        self.assertEqual(result["status"], "FAILED_VALIDATION")
        self.assertIn("unknown required capability: future.required", result["helper_validation_errors"])

    def test_project_existing_reports_creates_metadata_only_worker_runs(self) -> None:
        projections = worker_run.project_existing_reports(REPO_ROOT)
        schema = worker_run.load_worker_run_schema(REPO_ROOT)
        self.assertTrue(projections)
        for rel, obj in projections.items():
            self.assertTrue(rel.endswith(".worker-run.json"))
            self.assertEqual(worker_run.validate_worker_run(obj), [])
            self.assertEqual(worker_run.validate_worker_run_with_schema(obj, schema), [])
            self.assertEqual(obj["spec"]["provider_kind"], "metadata_only")
            self.assertEqual(obj["spec"]["adapter_kind"], "validation_observation")
            self.assertEqual(obj["spec"]["run_mode"], "validation_observation")
            self.assertFalse(obj["spec"]["worker_execution_performed"])
            self.assertFalse(obj["spec"]["workunit_claim_implemented"])
            self.assertFalse(obj["spec"]["worker_lease_created"])

    def test_projection_does_not_mutate_source_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_worker_run_files(root)
            source_paths = [root / meta["path"] for meta in worker_run.SOURCE_ARTIFACTS.values() if (root / meta["path"]).exists()]
            before = {path: path.read_bytes() for path in source_paths}
            result = worker_run.project_accepted_artifacts(root)
            self.assertEqual(result["status"], "PASS")
            self.assertFalse(result["source_reports_mutated"])
            self.assertEqual(before, {path: path.read_bytes() for path in source_paths})

    def test_projection_writes_parseable_worker_run_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_worker_run_files(root)
            result = worker_run.project_accepted_artifacts(root)
            for rel in result["projections_written"]:
                data = json.loads((root / rel).read_text(encoding="utf-8"))
                self.assertEqual(data["kind"], "WorkerRun")

    def test_validate_command_writes_validation_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_worker_run_files(root)
            result = worker_run.worker_run_validate(root)
            self.assertEqual(result["status"], "PASS")
            self.assertTrue(result["schema_validation_executed"])
            self.assertEqual(result["schema_validation_mode"], "minimal_json_schema_subset")
            self.assertEqual(result["schema_helper_alignment_status"], "PASS")
            self.assertTrue(result["unknown_optional_fields_tolerated"])
            self.assertTrue(result["unknown_required_capability_fails_closed"])
            self.assertTrue(result["explicit_non_capabilities_preserved"])
            self.assertTrue(result["metadata_only_truthful"])
            self.assertFalse(result["worker_execution_implemented"])
            self.assertFalse(result["workunit_claim_implemented"])
            self.assertTrue((root / ".aide/reports/worker-run/validation.json").exists())

    def test_worker_run_cli_status_project_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_worker_run_files(root)
            parser = aide_lite.build_parser(REPO_ROOT)
            for command in [
                ["--repo-root", str(root), "worker-run", "status"],
                ["--repo-root", str(root), "worker-run", "project", "--source", "accepted-artifacts"],
                ["--repo-root", str(root), "worker-run", "validate"],
            ]:
                parsed = parser.parse_args(command)
                output = io.StringIO()
                with redirect_stdout(output):
                    result = parsed.handler(parsed)
                self.assertEqual(result, 0, output.getvalue())
                self.assertIn("worker_execution_implemented: false", output.getvalue())
                self.assertIn("target_mutation: false", output.getvalue())
                self.assertIn("provider_or_model_calls: none", output.getvalue())
                self.assertIn("network_calls: none", output.getvalue())

    def test_parser_preserves_existing_protocol_commands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        commands = [
            ["lifecycle-fixture", "status"],
            ["contract-envelope", "status"],
            ["contract-envelope", "project", "--source", "lifecycle-fixture-runner"],
            ["evidence-packet", "status"],
            ["evidence-packet", "project", "--source", "accepted-slices"],
            ["workunit-queue", "status"],
            ["workunit-queue", "project", "--source", "queue-tasks"],
            ["workunit", "status"],
            ["worker-run", "status"],
            ["worker-run", "project", "--source", "accepted-artifacts"],
            ["worker-run", "validate"],
        ]
        for command in commands:
            parsed = parser.parse_args(command)
            self.assertTrue(callable(getattr(parsed, "handler", None)), command)

    def test_parser_rejects_worker_run_execution_command(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        stderr = io.StringIO()
        with self.assertRaises(SystemExit), redirect_stderr(stderr):
            parser.parse_args(["worker-run", "run"])
        self.assertIn("invalid choice", stderr.getvalue())

    def test_supported_kind_list_stays_narrow(self) -> None:
        self.assertEqual(
            worker_run.SUPPORTED_KINDS,
            {"WorkerRun", "WorkerRunProjectionReport", "WorkerRunValidationReport"},
        )

    def test_projection_report_has_no_execution_claim_lease_or_scheduler(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_worker_run_files(root)
            report = worker_run.project_accepted_artifacts(root)
            self.assertFalse(report["worker_execution_performed"])
            self.assertFalse(report["workunit_claim_executed"])
            self.assertFalse(report["worker_lease_created"])
            self.assertFalse(report["scheduler_behavior"])
            self.assertFalse(report["test_broker_behavior"])

    def test_schema_helper_alignment_fails_malformed_schema_copy(self) -> None:
        schema = copy.deepcopy(worker_run.load_worker_run_schema(REPO_ROOT))
        schema["required"] = ["apiVersion", "kind", "metadata", "spec"]
        alignment = worker_run.check_schema_helper_alignment(schema)
        self.assertEqual(alignment["schema_helper_alignment_status"], "FAILED_VALIDATION")
        self.assertTrue(any("status" in error for error in alignment["errors"]))


if __name__ == "__main__":
    unittest.main()
