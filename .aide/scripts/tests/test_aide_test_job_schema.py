from __future__ import annotations

import copy
import importlib.util
import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from core.protocol import test_job


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_test_job", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_test_job"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


SOURCE_FILES = [
    "core/protocol/__init__.py",
    "core/protocol/envelope.py",
    "core/protocol/evidence_packet.py",
    "core/protocol/workunit.py",
    "core/protocol/workunit_cli.py",
    "core/protocol/worker_run.py",
    "core/protocol/test_job.py",
    ".aide/protocol/aide-envelope.schema.json",
    ".aide/protocol/aide-evidence-packet.schema.json",
    ".aide/protocol/aide-workunit.schema.json",
    ".aide/protocol/aide-worker-run.schema.json",
    ".aide/protocol/aide-test-job.schema.json",
]

REPORT_FILES = sorted(
    {
        *(meta["path"].as_posix() for meta in test_job.SOURCE_ARTIFACTS.values()),
        *(path.as_posix() for path in test_job.COMPATIBILITY_REPORTS.values()),
    }
)


def copy_test_job_files(root: Path) -> None:
    for rel in [*SOURCE_FILES, *REPORT_FILES]:
        source = REPO_ROOT / rel
        if source.exists():
            aide_lite.copy_pack_file(source, root / rel)


def sample_job() -> dict[str, object]:
    return test_job.sample_test_job()


class AIDETestJobSchemaTests(unittest.TestCase):
    def test_schema_file_exists_and_parses_as_json(self) -> None:
        schema = test_job.load_test_job_schema(REPO_ROOT)
        self.assertEqual(schema["title"], "AIDE Minimal TestJob")
        self.assertTrue(schema["additionalProperties"])

    def test_schema_declares_test_job_kind_and_public_shape(self) -> None:
        schema = test_job.load_test_job_schema(REPO_ROOT)
        self.assertEqual(schema["required"], ["apiVersion", "kind", "metadata", "spec", "status"])
        self.assertEqual(schema["properties"]["kind"]["enum"], ["TestJob"])
        for field in ["apiVersion", "kind", "metadata", "spec", "status"]:
            self.assertIn(field, schema["properties"])

    def test_schema_includes_compatibility_metadata(self) -> None:
        schema = test_job.load_test_job_schema(REPO_ROOT)
        compatibility = schema["properties"]["metadata"]["properties"]["compatibility"]
        for field in ["schemaVersion", "protocolVersion", "minReaderVersion", "minWriterVersion", "featureFlags"]:
            self.assertIn(field, compatibility["properties"])
        self.assertIn("requiredCapabilities", compatibility["properties"])

    def test_schema_includes_test_job_metadata_fields(self) -> None:
        schema = test_job.load_test_job_schema(REPO_ROOT)
        spec = schema["properties"]["spec"]["properties"]
        for field in [
            "command",
            "environment",
            "framework",
            "timeout",
            "artifacts",
            "logs",
            "evidence_packet_refs",
            "explicit_non_capabilities",
        ]:
            self.assertIn(field, spec)
        self.assertIn("env_policy", spec["command"]["properties"])
        self.assertIn("runner_kind", spec["environment"]["properties"])
        self.assertIn("result_format", spec["framework"]["properties"])
        self.assertIn("timeout_policy", spec["timeout"]["properties"])

    def test_schema_includes_status_result_start_end_exit_duration(self) -> None:
        schema = test_job.load_test_job_schema(REPO_ROOT)
        status = schema["properties"]["status"]["properties"]
        for field in ["phase", "result", "startedAt", "endedAt", "exitCode", "durationSeconds"]:
            self.assertIn(field, status)

    def test_build_test_job_uses_public_shape(self) -> None:
        obj = sample_job()
        self.assertEqual(obj["apiVersion"], "aide.dev/v1alpha1")
        self.assertEqual(obj["kind"], "TestJob")
        self.assertIsInstance(obj["metadata"], dict)
        self.assertIsInstance(obj["spec"], dict)
        self.assertIsInstance(obj["status"], dict)
        self.assertEqual(obj["spec"]["capability_label"], "minimal_test_job_schema")

    def test_validate_test_job_accepts_valid_minimal_job(self) -> None:
        self.assertEqual(test_job.validate_test_job(sample_job()), [])

    def test_validate_test_job_rejects_wrong_kind(self) -> None:
        obj = sample_job()
        obj["kind"] = "WorkerRun"
        self.assertIn("unsupported kind: WorkerRun", test_job.validate_test_job(obj))

    def test_validate_test_job_rejects_missing_top_level_fields(self) -> None:
        for field in ["apiVersion", "kind", "metadata", "spec", "status"]:
            obj = sample_job()
            obj.pop(field)
            errors = test_job.validate_test_job(obj)
            self.assertTrue(any(field in error for error in errors), field)

    def test_validate_test_job_rejects_missing_required_spec_fields(self) -> None:
        for field in test_job.REQUIRED_SPEC_FIELDS:
            obj = sample_job()
            obj["spec"].pop(field)
            errors = test_job.validate_test_job(obj)
            self.assertIn(f"missing required spec field: {field}", errors, field)

    def test_validate_test_job_tolerates_unknown_optional_fields(self) -> None:
        self.assertEqual(test_job.validate_test_job(test_job.sample_unknown_optional_test_job()), [])

    def test_validate_test_job_fails_closed_for_unknown_required_capability(self) -> None:
        obj = test_job.sample_unknown_required_capability_test_job()
        errors = test_job.validate_test_job(obj)
        self.assertIn("unknown required capability: future.required", errors)

    def test_explicit_non_capabilities_are_preserved(self) -> None:
        obj = sample_job()
        non_caps = obj["spec"]["explicit_non_capabilities"]
        for capability in ["test_broker_runtime", "async_test_execution", "scheduler", "worker_execution", "service"]:
            self.assertIn(capability, non_caps)
        self.assertFalse(test_job.implemented_capabilities(obj) & set(non_caps))

    def test_schema_helper_alignment_passes_current_schema(self) -> None:
        schema = test_job.load_test_job_schema(REPO_ROOT)
        alignment = test_job.check_schema_helper_alignment(schema)
        self.assertEqual(alignment["schema_helper_alignment_status"], "PASS")
        self.assertEqual(alignment["errors"], [])

    def test_schema_validation_accepts_valid_test_job(self) -> None:
        schema = test_job.load_test_job_schema(REPO_ROOT)
        self.assertEqual(test_job.validate_test_job_with_schema(sample_job(), schema), [])

    def test_runtime_schema_validation_fails_closed_for_unknown_required_capability(self) -> None:
        schema = test_job.load_test_job_schema(REPO_ROOT)
        result = test_job.validate_test_job_runtime(
            test_job.sample_unknown_required_capability_test_job(),
            schema,
        )
        self.assertEqual(result["status"], "FAILED_VALIDATION")
        self.assertIn("unknown required capability: future.required", result["helper_validation_errors"])

    def test_project_existing_reports_creates_metadata_only_test_jobs(self) -> None:
        projections = test_job.project_existing_reports(REPO_ROOT)
        schema = test_job.load_test_job_schema(REPO_ROOT)
        self.assertTrue(projections)
        for rel, obj in projections.items():
            self.assertTrue(rel.endswith(".test-job.json"))
            self.assertEqual(test_job.validate_test_job(obj), [])
            self.assertEqual(test_job.validate_test_job_with_schema(obj, schema), [])
            self.assertIn(obj["spec"]["job_kind"], {"metadata_only", "validation_observation"})
            self.assertFalse(obj["spec"]["test_broker_runtime_implemented"])
            self.assertFalse(obj["spec"]["async_test_execution_implemented"])
            self.assertFalse(obj["spec"]["worker_execution_implemented"])

    def test_projection_does_not_mutate_source_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_test_job_files(root)
            source_paths = [
                root / meta["path"]
                for meta in test_job.SOURCE_ARTIFACTS.values()
                if (root / meta["path"]).exists()
            ]
            before = {path: path.read_bytes() for path in source_paths}
            result = test_job.project_accepted_artifacts(root)
            self.assertEqual(result["status"], "PASS")
            self.assertFalse(result["source_reports_mutated"])
            self.assertEqual(before, {path: path.read_bytes() for path in source_paths})

    def test_projection_writes_parseable_test_job_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_test_job_files(root)
            result = test_job.project_accepted_artifacts(root)
            for rel in result["projections_written"]:
                data = json.loads((root / rel).read_text(encoding="utf-8"))
                self.assertEqual(data["kind"], "TestJob")

    def test_projection_records_missing_optional_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_test_job_files(root)
            optional_source = root / ".aide/reports/workunit-cli-acceptance/acceptance-report.json"
            if optional_source.exists():
                optional_source.unlink()
            result = test_job.project_accepted_artifacts(root)
            self.assertIn(".aide/reports/workunit-cli-acceptance/acceptance-report.json", result["missing_sources"])

    def test_validate_command_writes_validation_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_test_job_files(root)
            result = test_job.test_job_validate(root)
            self.assertEqual(result["status"], "PASS")
            self.assertTrue(result["schema_validation_executed"])
            self.assertEqual(result["schema_validation_mode"], "minimal_json_schema_subset")
            self.assertEqual(result["schema_helper_alignment_status"], "PASS")
            self.assertTrue(result["unknown_optional_fields_tolerated"])
            self.assertTrue(result["unknown_required_capability_fails_closed"])
            self.assertTrue(result["explicit_non_capabilities_preserved"])
            self.assertTrue(result["metadata_only_truthful"])
            self.assertFalse(result["test_broker_runtime_implemented"])
            self.assertFalse(result["async_test_execution_implemented"])
            self.assertTrue((root / ".aide/reports/test-job/validation.json").exists())

    def test_test_job_cli_status_project_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_test_job_files(root)
            parser = aide_lite.build_parser(REPO_ROOT)
            for command in [
                ["--repo-root", str(root), "test-job", "status"],
                ["--repo-root", str(root), "test-job", "project", "--source", "accepted-artifacts"],
                ["--repo-root", str(root), "test-job", "validate"],
            ]:
                parsed = parser.parse_args(command)
                output = io.StringIO()
                with redirect_stdout(output):
                    result = parsed.handler(parsed)
                self.assertEqual(result, 0, output.getvalue())
                self.assertIn("test_broker_runtime_implemented: false", output.getvalue())
                self.assertIn("async_test_execution_implemented: false", output.getvalue())
                self.assertIn("worker_execution_implemented: false", output.getvalue())
                self.assertIn("network_calls: none", output.getvalue())

    def test_parser_preserves_existing_protocol_commands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        commands = [
            ["contract-envelope", "status"],
            ["evidence-packet", "status"],
            ["workunit-queue", "status"],
            ["workunit", "status"],
            ["worker-run", "status"],
            ["test-job", "status"],
            ["test-job", "project", "--source", "accepted-artifacts"],
            ["test-job", "validate"],
        ]
        for command in commands:
            parsed = parser.parse_args(command)
            self.assertTrue(callable(getattr(parsed, "handler", None)), command)

    def test_parser_rejects_test_job_execution_commands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        for command in [["test-job", "submit"], ["test-job", "run"], ["test-job", "retry"], ["test-job", "summarize"]]:
            stderr = io.StringIO()
            with self.assertRaises(SystemExit), redirect_stderr(stderr):
                parser.parse_args(command)
            self.assertIn("invalid choice", stderr.getvalue())

    def test_projection_report_has_no_runtime_claims(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_test_job_files(root)
            report = test_job.project_accepted_artifacts(root)
            self.assertFalse(report["test_broker_runtime_implemented"])
            self.assertFalse(report["async_test_execution_implemented"])
            self.assertFalse(report["test_job_submission_implemented"])
            self.assertFalse(report["worker_execution_performed"])
            self.assertFalse(report["scheduler_behavior"])
            self.assertFalse(report["leases_created"])

    def test_reports_do_not_overclaim_runtime_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_test_job_files(root)
            report = test_job.test_job_validate(root)
            self.assertFalse(report["service_implemented"])
            self.assertFalse(report["commander_implemented"])
            self.assertFalse(report["provider_adapter_implemented"])
            self.assertFalse(report["network_calls"])
            self.assertFalse(report["github_mutation"])
            text = (root / ".aide/reports/test-job/validation.md").read_text(encoding="utf-8")
            for phrase in [
                "Test Broker implemented: true",
                "async test execution implemented: true",
                "scheduler implemented: true",
                "provider calls enabled",
                "network enabled",
                "production-ready",
                "release-ready",
            ]:
                self.assertNotIn(phrase, text)

    def test_report_paths_are_deterministic_and_safe(self) -> None:
        for rel in test_job.PROJECTION_FILES.values():
            self.assertEqual(rel.suffixes[-2:], [".test-job", ".json"])
            self.assertNotIn("..", rel.parts)
            self.assertTrue(rel.as_posix().startswith(".aide/reports/test-job/projections/"))

    def test_no_secrets_are_emitted_into_generated_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_test_job_files(root)
            test_job.test_job_validate(root)
            report_root = root / ".aide/reports/test-job"
            secret_pattern = re.compile(r"(api[_-]?key|password|credential|bearer)\s*[:=]|BEGIN [A-Z ]*PRIVATE KEY", re.I)
            for path in report_root.rglob("*"):
                if path.is_file():
                    self.assertIsNone(secret_pattern.search(path.read_text(encoding="utf-8")), path)

    def test_schema_helper_alignment_fails_malformed_schema_copy(self) -> None:
        schema = copy.deepcopy(test_job.load_test_job_schema(REPO_ROOT))
        schema["required"] = ["apiVersion", "kind", "metadata", "spec"]
        alignment = test_job.check_schema_helper_alignment(schema)
        self.assertEqual(alignment["schema_helper_alignment_status"], "FAILED_VALIDATION")
        self.assertTrue(any("status" in error for error in alignment["errors"]))


if __name__ == "__main__":
    unittest.main()
