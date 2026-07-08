from __future__ import annotations

import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from core.protocol import workunit


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_workunit_queue", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_workunit_queue"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


SOURCE_FILES = [
    "core/protocol/__init__.py",
    "core/protocol/envelope.py",
    "core/protocol/evidence_packet.py",
    "core/protocol/workunit.py",
    ".aide/protocol/aide-envelope.schema.json",
    ".aide/protocol/aide-evidence-packet.schema.json",
    ".aide/protocol/aide-workunit.schema.json",
]


def copy_workunit_files(root: Path) -> None:
    for rel in SOURCE_FILES:
        source = REPO_ROOT / rel
        if source.exists():
            aide_lite.copy_pack_file(source, root / rel)
    for task_id in workunit.QUEUE_SOURCES.values():
        task_dir = REPO_ROOT / ".aide/queue" / task_id
        for name in ["task.yaml", "status.yaml", "ExecPlan.md", "prompt.md"]:
            source = task_dir / name
            if source.exists():
                aide_lite.copy_pack_file(source, root / ".aide/queue" / task_id / name)
        evidence_dir = task_dir / "evidence"
        if evidence_dir.exists():
            for source in evidence_dir.glob("*.md"):
                aide_lite.copy_pack_file(source, root / ".aide/queue" / task_id / "evidence" / source.name)


def sample_unit() -> dict[str, object]:
    return workunit.sample_workunit()


class AIDEWorkUnitQueueTests(unittest.TestCase):
    def test_build_workunit_uses_public_shape(self) -> None:
        obj = sample_unit()
        self.assertEqual(obj["apiVersion"], "aide.dev/v1alpha1")
        self.assertEqual(obj["kind"], "WorkUnit")
        self.assertIsInstance(obj["metadata"], dict)
        self.assertIsInstance(obj["spec"], dict)
        self.assertIsInstance(obj["status"], dict)

    def test_validate_workunit_accepts_valid_minimal_unit(self) -> None:
        self.assertEqual(workunit.validate_workunit(sample_unit()), [])

    def test_validate_workunit_rejects_missing_api_version(self) -> None:
        obj = sample_unit()
        obj.pop("apiVersion")
        self.assertIn("apiVersion must be a non-empty string", workunit.validate_workunit(obj))

    def test_validate_workunit_rejects_wrong_kind(self) -> None:
        obj = sample_unit()
        obj["kind"] = "EvidencePacket"
        self.assertIn("unsupported kind: EvidencePacket", workunit.validate_workunit(obj))

    def test_validate_workunit_rejects_missing_metadata_spec_and_status(self) -> None:
        for field in ["metadata", "spec", "status"]:
            obj = sample_unit()
            obj.pop(field)
            self.assertIn(f"missing required field: {field}", workunit.validate_workunit(obj))

    def test_validate_workunit_rejects_missing_source_path(self) -> None:
        obj = sample_unit()
        obj["metadata"].pop("sourcePath")
        self.assertIn("missing required metadata field: sourcePath", workunit.validate_workunit(obj))

    def test_validate_workunit_rejects_missing_required_spec_fields(self) -> None:
        for field in workunit.REQUIRED_SPEC_FIELDS:
            obj = sample_unit()
            obj["spec"].pop(field)
            errors = workunit.validate_workunit(obj)
            self.assertIn(f"missing required spec field: {field}", errors, field)

    def test_validate_workunit_rejects_scope_and_validation_type_errors(self) -> None:
        obj = sample_unit()
        obj["spec"]["scope"]["allowed_paths"] = {}
        obj["spec"]["validation"]["commands"] = {}
        errors = workunit.validate_workunit(obj)
        self.assertIn("spec.scope.allowed_paths must be an array", errors)
        self.assertIn("spec.validation.commands must be an array", errors)

    def test_validate_workunit_preserves_explicit_non_capabilities(self) -> None:
        obj = sample_unit()
        non_caps = obj["spec"]["explicit_non_capabilities"]
        self.assertIn("workunit_create_cli", non_caps)
        self.assertIn("test_broker", non_caps)
        self.assertIn("service_ready", non_caps)

    def test_explicit_non_capabilities_are_not_implemented_capabilities(self) -> None:
        obj = sample_unit()
        self.assertFalse(workunit.implemented_capabilities(obj) & set(obj["spec"]["explicit_non_capabilities"]))

    def test_validate_workunit_tolerates_unknown_optional_fields(self) -> None:
        obj = workunit.sample_unknown_optional_workunit()
        self.assertEqual(workunit.validate_workunit(obj), [])

    def test_validate_workunit_fails_closed_for_unknown_required_capability(self) -> None:
        obj = workunit.sample_unknown_required_capability_workunit()
        errors = workunit.validate_workunit(obj)
        self.assertIn("unknown required capability: future.required", errors)

    def test_schema_file_parses_and_declares_required_workunit_fields(self) -> None:
        schema = workunit.load_workunit_schema(REPO_ROOT)
        self.assertEqual(schema["required"], ["apiVersion", "kind", "metadata", "spec", "status"])
        self.assertTrue(schema["additionalProperties"])

    def test_schema_helper_alignment_passes_current_schema(self) -> None:
        schema = workunit.load_workunit_schema(REPO_ROOT)
        alignment = workunit.check_schema_helper_alignment(schema)
        self.assertEqual(alignment["schema_helper_alignment_status"], "PASS")
        self.assertEqual(alignment["errors"], [])

    def test_schema_validation_accepts_valid_workunit(self) -> None:
        schema = workunit.load_workunit_schema(REPO_ROOT)
        self.assertEqual(workunit.validate_workunit_with_schema(sample_unit(), schema), [])

    def test_schema_validation_rejects_missing_required_fields(self) -> None:
        schema = workunit.load_workunit_schema(REPO_ROOT)
        for field in ["apiVersion", "kind", "metadata", "spec", "status"]:
            obj = sample_unit()
            obj.pop(field)
            errors = workunit.validate_workunit_with_schema(obj, schema)
            self.assertTrue(any(field in error for error in errors), field)

    def test_runtime_schema_validation_fails_closed_for_unknown_required_capability(self) -> None:
        schema = workunit.load_workunit_schema(REPO_ROOT)
        result = workunit.validate_workunit_runtime(
            workunit.sample_unknown_required_capability_workunit(),
            schema,
        )
        self.assertEqual(result["status"], "FAILED_VALIDATION")
        self.assertIn("unknown required capability: future.required", result["helper_validation_errors"])

    def test_project_existing_queue_tasks_creates_valid_workunits(self) -> None:
        projections = workunit.project_existing_queue_tasks(REPO_ROOT)
        schema = workunit.load_workunit_schema(REPO_ROOT)
        self.assertEqual(set(projections), {path.as_posix() for path in workunit.PROJECTION_FILES.values()})
        for obj in projections.values():
            self.assertEqual(workunit.validate_workunit(obj), [])
            self.assertEqual(workunit.validate_workunit_with_schema(obj, schema), [])

    def test_projection_does_not_mutate_source_queue_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_workunit_files(root)
            source_paths = sorted((root / ".aide/queue").glob("AIDE-*/task.yaml")) + sorted(
                (root / ".aide/queue").glob("AIDE-*/status.yaml")
            )
            before = {path: path.read_bytes() for path in source_paths}
            result = workunit.project_queue_tasks(root)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(before, {path: path.read_bytes() for path in source_paths})

    def test_projection_writes_parseable_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_workunit_files(root)
            result = workunit.project_queue_tasks(root)
            for rel in result["workunit_projections_written"]:
                data = json.loads((root / rel).read_text(encoding="utf-8"))
                self.assertEqual(data["kind"], "WorkUnit")

    def test_validate_command_writes_validation_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_workunit_files(root)
            result = workunit.workunit_queue_validate(root)
            self.assertEqual(result["status"], "PASS")
            self.assertTrue(result["schema_validation_executed"])
            self.assertEqual(result["schema_validation_mode"], "minimal_json_schema_subset")
            self.assertEqual(result["schema_helper_alignment_status"], "PASS")
            self.assertTrue(result["unknown_optional_fields_tolerated"])
            self.assertTrue(result["unknown_required_capability_fails_closed"])
            self.assertTrue(result["explicit_non_capabilities_preserved"])
            self.assertFalse(result["workunit_cli_implemented"])
            self.assertTrue((root / ".aide/reports/workunit-queue/validation.json").exists())

    def test_workunit_queue_cli_status_project_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_workunit_files(root)
            parser = aide_lite.build_parser(REPO_ROOT)
            for command in [
                ["--repo-root", str(root), "workunit-queue", "status"],
                ["--repo-root", str(root), "workunit-queue", "project", "--source", "queue-tasks"],
                ["--repo-root", str(root), "workunit-queue", "validate"],
            ]:
                parsed = parser.parse_args(command)
                output = io.StringIO()
                with redirect_stdout(output):
                    result = parsed.handler(parsed)
                self.assertEqual(result, 0, output.getvalue())
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
            ["workunit-queue", "validate"],
        ]
        for command in commands:
            parsed = parser.parse_args(command)
            self.assertTrue(callable(getattr(parsed, "handler", None)), command)

    def test_workunit_projections_do_not_overclaim_future_primitives(self) -> None:
        projections = workunit.project_existing_queue_tasks(REPO_ROOT)
        forbidden = {
            "workunit_create_cli",
            "workunit_list_cli",
            "workunit_claim_cli",
            "workunit_block_cli",
            "workunit_finish_cli",
            "workunit_repair_cli",
            "testjob_schema",
            "test_broker",
            "service_ready",
            "commander_ready",
            "provider_adapter_ready",
            "branch_worktree_automation",
            "target_repo_apply",
            "active_repo_apply",
            "rollback_execution",
            "production_ready",
            "release_ready",
        }
        for obj in projections.values():
            self.assertFalse(workunit.implemented_capabilities(obj) & forbidden)
            self.assertTrue(forbidden & set(obj["spec"]["explicit_non_capabilities"]))

    def test_current_task_projection_authorizes_only_minimal_scope(self) -> None:
        obj = workunit.project_queue_task(REPO_ROOT, "AIDE-BUILD-WORKUNIT-QUEUE-V1-01")
        self.assertTrue(obj["spec"]["authorizes_implementation"])
        self.assertEqual(obj["spec"]["implementation_scope"], "minimal-workunit-queue-v1-only")
        self.assertEqual(obj["spec"]["stop_state"], "needs_review")
        self.assertEqual(obj["spec"]["capability_label"], "minimal_workunit_queue_v1")
        self.assertFalse(obj["spec"]["check_only"])
        self.assertFalse(obj["spec"]["acceptance_review"])

    def test_schema_helper_alignment_fails_malformed_schema_copy(self) -> None:
        schema = copy.deepcopy(workunit.load_workunit_schema(REPO_ROOT))
        schema["required"] = ["apiVersion", "kind", "metadata", "spec"]
        alignment = workunit.check_schema_helper_alignment(schema)
        self.assertEqual(alignment["schema_helper_alignment_status"], "FAILED_VALIDATION")
        self.assertTrue(any("status" in error for error in alignment["errors"]))

    def test_supported_kind_list_stays_narrow(self) -> None:
        self.assertEqual(
            workunit.SUPPORTED_KINDS,
            {"WorkUnit", "WorkUnitQueueProjectionReport", "WorkUnitQueueValidationReport"},
        )

    def test_no_source_destructive_migration_flag_in_projection_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_workunit_files(root)
            result = workunit.project_queue_tasks(root)
            self.assertFalse(result["destructive_migration_performed"])
            self.assertFalse(result["source_queue_tasks_mutated"])


if __name__ == "__main__":
    unittest.main()
