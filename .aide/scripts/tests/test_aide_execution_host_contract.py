from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.protocol import execution_host


MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_execution_host_contract", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_execution_host_contract"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


SOURCE_FILES = [
    ".aide/scripts/aide_lite.py",
    ".aide/protocol/aide-execution-host.schema.json",
    "core/__init__.py",
    "core/protocol/__init__.py",
    "core/protocol/envelope.py",
    "core/protocol/execution_host.py",
]


def copy_contract_files(root: Path) -> None:
    for rel in SOURCE_FILES:
        source = REPO_ROOT / rel
        if source.exists():
            destination = root / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)


class AIDEExecutionHostContractTests(unittest.TestCase):
    def test_descriptor_shape_is_projection_only_and_provider_distinct(self) -> None:
        descriptor = execution_host.build_execution_host_descriptor()
        self.assertEqual(descriptor["apiVersion"], "aide.dev/v1alpha1")
        self.assertEqual(descriptor["kind"], "ExecutionHostDescriptor")
        self.assertEqual(descriptor["schema_version"], "aide.execution-host-contract.v0")
        self.assertTrue(descriptor["spec"]["capability_execution_distinct"])
        self.assertEqual(descriptor["spec"]["capability_provider_ref"], "registered_process_execution_provider_v0")
        self.assertTrue(descriptor["spec"]["worker_session_contract"])
        self.assertTrue(descriptor["status"]["projection_only"])
        self.assertFalse(descriptor["spec"]["execution_host_runtime_implemented"])
        self.assertFalse(descriptor["spec"]["worker_execution_implemented"])

    def test_all_sample_records_validate(self) -> None:
        for name, record in execution_host.sample_records().items():
            with self.subTest(name=name):
                self.assertEqual(execution_host.validate_execution_host_contract(record), [])

    def test_validate_rejects_missing_top_level_fields_and_wrong_kind(self) -> None:
        sample = execution_host.build_execution_host_descriptor()
        for field in ["apiVersion", "kind", "metadata", "spec", "status"]:
            obj = copy.deepcopy(sample)
            obj.pop(field)
            errors = execution_host.validate_execution_host_contract(obj)
            self.assertTrue(any(field in error for error in errors), field)
        wrong = copy.deepcopy(sample)
        wrong["kind"] = "WorkerRun"
        self.assertIn("unsupported kind: WorkerRun", execution_host.validate_execution_host_contract(wrong))

    def test_descriptor_requires_exact_v0_operation_set(self) -> None:
        descriptor = execution_host.build_execution_host_descriptor()
        self.assertEqual(set(descriptor["spec"]["supported_operations"]), execution_host.OPERATION_NAMES)
        broken = copy.deepcopy(descriptor)
        broken["spec"]["supported_operations"] = ["probe"]
        errors = execution_host.validate_execution_host_contract(broken)
        self.assertIn("spec.supported_operations must equal the v0 operation set", errors)

    def test_false_boundaries_and_non_capabilities_are_preserved(self) -> None:
        for record in execution_host.sample_records().values():
            non_caps = record["spec"]["explicit_non_capabilities"]
            for item in [
                "live_execution_host",
                "local_process_execution_host",
                "worker_execution",
                "provider_model_calls",
                "network_calls",
                "repository_mutation",
            ]:
                self.assertIn(item, non_caps)
            self.assertFalse(execution_host.implemented_capabilities(record) & set(non_caps))
            for field in execution_host.FALSE_BOUNDARY_FIELDS:
                self.assertIs(record["spec"][field], False, field)

    def test_unknown_optional_fields_tolerated_and_required_capability_fails_closed(self) -> None:
        self.assertEqual(execution_host.validate_execution_host_contract(execution_host.sample_unknown_optional_record()), [])
        errors = execution_host.validate_execution_host_contract(execution_host.sample_unknown_required_capability_record())
        self.assertIn("unknown required capability: future.required", errors)

    def test_schema_parses_and_aligns_with_helper(self) -> None:
        schema = execution_host.load_execution_host_schema(REPO_ROOT)
        self.assertEqual(schema["required"], ["apiVersion", "kind", "metadata", "spec", "status"])
        self.assertEqual(set(schema["properties"]["kind"]["enum"]), execution_host.SUPPORTED_KINDS)
        alignment = execution_host.check_schema_helper_alignment(schema)
        self.assertEqual(alignment["schema_helper_alignment_status"], "PASS")
        self.assertEqual(alignment["errors"], [])

    def test_schema_validation_accepts_sample_records(self) -> None:
        schema = execution_host.load_execution_host_schema(REPO_ROOT)
        for name, record in execution_host.sample_records().items():
            with self.subTest(name=name):
                self.assertEqual(execution_host.validate_execution_host_with_schema(record, schema), [])

    def test_schema_alignment_fails_when_kind_is_missing(self) -> None:
        schema = copy.deepcopy(execution_host.load_execution_host_schema(REPO_ROOT))
        schema["properties"]["kind"]["enum"].remove("ExecutionHostUsage")
        alignment = execution_host.check_schema_helper_alignment(schema)
        self.assertEqual(alignment["schema_helper_alignment_status"], "FAILED_VALIDATION")
        self.assertTrue(any("ExecutionHostUsage" in error for error in alignment["errors"]))

    def test_projection_writes_contract_records_without_runtime_claims(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_contract_files(root)
            report = execution_host.project_execution_host_contract(root)
            self.assertEqual(report["status"], "PASS_WITH_WARNINGS")
            self.assertTrue(report["projection_only"])
            self.assertFalse(report["execution_host_runtime_implemented"])
            self.assertFalse(report["worker_execution_implemented"])
            self.assertFalse(report["network_calls_performed"])
            for rel in report["projections_written"]:
                record = json.loads((root / rel).read_text(encoding="utf-8"))
                self.assertEqual(execution_host.validate_execution_host_contract(record), [])

    def test_validate_command_writes_pass_with_warnings_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_contract_files(root)
            result = execution_host.execution_host_validate(root)
            self.assertEqual(result["status"], "PASS_WITH_WARNINGS")
            self.assertTrue(result["schema_validation_executed"])
            self.assertEqual(result["schema_helper_alignment_status"], "PASS")
            self.assertTrue(result["projection_only_truthful"])
            self.assertTrue(result["capability_execution_distinct"])
            self.assertTrue(result["worker_session_contract_defined"])
            self.assertFalse(result["execution_host_runtime_implemented"])
            self.assertTrue((root / ".aide/reports/execution-host-contract/validation.json").exists())

    def test_execution_host_cli_status_project_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_contract_files(root)
            parser = aide_lite.build_parser(REPO_ROOT)
            commands = [
                ["--repo-root", str(root), "execution-host", "status"],
                ["--repo-root", str(root), "execution-host", "project", "--source", "contract-projection"],
                ["--repo-root", str(root), "execution-host", "validate"],
            ]
            for command in commands:
                parsed = parser.parse_args(command)
                output = StringIO()
                with redirect_stdout(output):
                    exit_code = parsed.handler(parsed)
                self.assertEqual(exit_code, 0, output.getvalue())
                self.assertIn("execution_host_runtime_implemented: false", output.getvalue())
                self.assertIn("worker_execution_implemented: false", output.getvalue())
                self.assertIn("provider_or_model_calls: none", output.getvalue())
                self.assertIn("network_calls: none", output.getvalue())

    def test_parser_rejects_live_execution_commands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        stderr = StringIO()
        with self.assertRaises(SystemExit), redirect_stderr(stderr):
            parser.parse_args(["execution-host", "run"])
        self.assertIn("invalid choice", stderr.getvalue())

    def test_parser_preserves_neighbor_protocol_commands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        for command in [
            ["worker-run", "status"],
            ["execution-host", "status"],
            ["execution-host", "project", "--source", "contract-projection"],
            ["execution-host", "validate"],
            ["test-job", "status"],
            ["event-record", "status"],
        ]:
            parsed = parser.parse_args(command)
            self.assertTrue(callable(getattr(parsed, "handler", None)), command)


if __name__ == "__main__":
    unittest.main()
