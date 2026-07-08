from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from core.protocol import event_record


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_event_record", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_event_record"] = aide_lite
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
    "core/protocol/reference_id.py",
    "core/protocol/event_record.py",
    ".aide/protocol/aide-envelope.schema.json",
    ".aide/protocol/aide-evidence-packet.schema.json",
    ".aide/protocol/aide-workunit.schema.json",
    ".aide/protocol/aide-worker-run.schema.json",
    ".aide/protocol/aide-test-job.schema.json",
    ".aide/protocol/aide-reference-id.schema.json",
    ".aide/protocol/aide-event-record.schema.json",
]

COMPATIBILITY_REPORT_FILES = [
    ".aide/reports/contract-envelope/validation.json",
    ".aide/reports/evidence-packet/validation.json",
    ".aide/reports/workunit-queue/validation.json",
    ".aide/reports/worker-run/validation.json",
    ".aide/reports/test-job/validation.json",
    ".aide/reports/test-job-accept/acceptance-report.json",
    ".aide/reports/reference-id/reference-map.json",
    ".aide/reports/reference-id/projection-report.json",
    ".aide/reports/reference-id/validation.json",
    ".aide/reports/reference-id-accept/acceptance-report.json",
    ".aide/queue/AIDE-ACCEPT-REFERENCE-ID-SCHEME-01/status.yaml",
]


def copy_event_record_files(root: Path) -> None:
    for rel in [*SOURCE_FILES, *COMPATIBILITY_REPORT_FILES]:
        source = REPO_ROOT / rel
        if source.exists():
            aide_lite.copy_pack_file(source, root / rel)


class AIDEEventRecordSchemaTests(unittest.TestCase):
    def test_schema_file_exists_and_parses_as_json(self) -> None:
        schema = event_record.load_event_record_schema(REPO_ROOT)
        self.assertEqual(schema["title"], "AIDE Minimal EventRecord")
        self.assertTrue(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["kind"]["enum"], ["EventRecord"])

    def test_schema_declares_event_record_public_shape(self) -> None:
        schema = event_record.load_event_record_schema(REPO_ROOT)
        self.assertEqual(schema["required"], ["apiVersion", "kind", "metadata", "spec", "status"])
        spec = schema["properties"]["spec"]
        for field in [
            "event_ref",
            "event_type",
            "subject",
            "occurred_at",
            "sequence",
            "actor",
            "payload",
            "evidence_refs",
            "report_refs",
            "explicit_non_capabilities",
        ]:
            self.assertIn(field, spec["required"])
        self.assertEqual(spec["properties"]["causation"]["type"], ["object", "null"])
        self.assertEqual(spec["properties"]["correlation"]["type"], ["object", "null"])

    def test_event_family_vocabulary_is_complete_and_projection_only(self) -> None:
        expected = {
            "WorkUnitStateChanged",
            "WorkerRunRecorded",
            "TestJobRecorded",
            "EvidencePacketRecorded",
            "AcceptanceRecorded",
            "ReferenceIDProjectionRecorded",
            "EventRecordProjectionRecorded",
            "CapabilityDeclared",
            "ConformanceResultRecorded",
            "OKFProjectionRecorded",
            "ReconcilerFindingRecorded",
            "PatchTransactionRecorded",
        }
        self.assertEqual(set(event_record.event_family_names()), expected)
        self.assertEqual(len(event_record.EVENT_FAMILIES), 12)
        self.assertTrue(all(item["status"] == "reserved_or_supported_for_schema" for item in event_record.EVENT_FAMILIES))
        self.assertTrue(all(item["implemented_subsystem"] is False for item in event_record.EVENT_FAMILIES))

    def test_event_type_parser_accepts_family_names_and_rejects_invalid_names(self) -> None:
        self.assertEqual(event_record.parse_event_type("AcceptanceRecorded"), "AcceptanceRecorded")
        invalid_names = ["acceptanceRecorded", "Acceptance-Recorded", "Acceptance Recorded", "1Acceptance", "Acceptance_Recorded"]
        for name in invalid_names:
            with self.subTest(name=name):
                self.assertFalse(event_record.validate_event_type(name, required=False).valid)

    def test_unknown_optional_event_type_warns_and_required_fails_closed(self) -> None:
        optional = event_record.validate_event_type("FutureEventType", required=False)
        required = event_record.validate_event_type("FutureEventType", required=True)
        self.assertTrue(optional.valid)
        self.assertTrue(optional.warnings)
        self.assertEqual(optional.status, "PASS_WITH_WARNINGS")
        self.assertFalse(required.valid)
        self.assertTrue(required.errors)
        self.assertEqual(required.status, "FAILED_VALIDATION")

    def test_event_ref_format_uses_reference_id_scheme(self) -> None:
        self.assertEqual(event_record.format_event_ref("EVT-REFERENCE-ID-ACCEPTED"), "aide://event/EVT-REFERENCE-ID-ACCEPTED")

    def test_build_event_record_validates_reference_id_backed_fields(self) -> None:
        record = event_record.sample_event_record()
        self.assertEqual(event_record.validate_event_record(record), [])
        self.assertEqual(record["spec"]["event_ref"], "aide://event/EVT-EVENT-RECORD-SAMPLE")
        self.assertEqual(record["spec"]["subject"]["ref"], "aide://queue-task/AIDE-ACCEPT-REFERENCE-ID-SCHEME-01")
        self.assertFalse(record["status"]["recorded"])
        self.assertTrue(record["status"]["projection_only"])

    def test_subject_kind_mismatch_fails_closed(self) -> None:
        record = event_record.build_event_record(
            repo_root=Path("."),
            event_ref="aide://event/EVT-BAD-SUBJECT",
            event_type="AcceptanceRecorded",
            subject_ref="aide://schema/reference-id",
        )
        errors = event_record.validate_event_record(record)
        self.assertTrue(any("not allowed for AcceptanceRecorded" in error for error in errors))

    def test_evidence_and_report_refs_require_expected_kinds(self) -> None:
        record = event_record.build_event_record(
            repo_root=Path("."),
            event_ref="aide://event/EVT-BAD-REF-KINDS",
            event_type="AcceptanceRecorded",
            subject_ref="aide://queue-task/AIDE-ACCEPT-REFERENCE-ID-SCHEME-01",
            evidence_refs=["aide://report/not-evidence"],
            report_refs=["aide://evidence/not-report"],
        )
        errors = event_record.validate_event_record(record)
        self.assertTrue(any("spec.evidence_refs[0]" in error for error in errors))
        self.assertTrue(any("spec.report_refs[0]" in error for error in errors))

    def test_unknown_required_event_record_is_invalid_but_optional_future_record_warns(self) -> None:
        required_record = event_record.sample_unknown_required_event_record()
        optional_record = event_record.sample_unknown_optional_event_record()
        self.assertFalse(required_record["status"]["valid"])
        self.assertTrue(required_record["status"]["validation_errors"])
        self.assertTrue(optional_record["status"]["valid"])
        self.assertTrue(optional_record["status"]["validation_warnings"])

    def test_schema_helper_alignment_passes_current_schema(self) -> None:
        schema = event_record.load_event_record_schema(REPO_ROOT)
        alignment = event_record.check_schema_helper_alignment(schema)
        self.assertEqual(alignment["schema_helper_alignment_status"], "PASS")
        self.assertEqual(alignment["errors"], [])

    def test_schema_validation_accepts_valid_event_record(self) -> None:
        schema = event_record.load_event_record_schema(REPO_ROOT)
        self.assertEqual(event_record.validate_event_record_with_schema(event_record.sample_event_record(), schema), [])

    def test_runtime_validation_fails_closed_for_unknown_required_event_type(self) -> None:
        schema = event_record.load_event_record_schema(REPO_ROOT)
        result = event_record.validate_event_record_runtime(event_record.sample_unknown_required_event_record(), schema)
        self.assertEqual(result["status"], "FAILED_VALIDATION")
        self.assertIn("unknown required event_type: FutureEventType", result["helper_validation_errors"])

    def test_projection_writes_reports_and_does_not_mutate_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_event_record_files(root)
            source_paths = event_record._source_paths(root)
            before = {path: path.read_bytes() for path in source_paths}
            report = event_record.project_event_record_reports(root)
            self.assertEqual(report["status"], "PASS_WITH_WARNINGS")
            self.assertFalse(report["source_artifacts_mutated"])
            self.assertEqual(report["event_family_count"], 12)
            self.assertEqual(report["example_event_count"], 4)
            self.assertEqual(before, {path: path.read_bytes() for path in source_paths})

    def test_projection_writes_parseable_family_index_and_example_events(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_event_record_files(root)
            event_record.project_event_record_reports(root)
            family_index = json.loads((root / ".aide/reports/event-record/event-family-index.json").read_text(encoding="utf-8"))
            examples = json.loads((root / ".aide/reports/event-record/example-events.json").read_text(encoding="utf-8"))
            self.assertEqual(family_index["kind"], "EventFamilyIndex")
            self.assertIn("EventRecordProjectionRecorded", [item["event_type"] for item in family_index["event_families"]])
            self.assertEqual(examples["kind"], "EventRecordExamples")
            self.assertTrue(examples["projection_only"])
            self.assertFalse(examples["recorded"])

    def test_validate_command_writes_validation_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_event_record_files(root)
            result = event_record.event_record_validate(root)
            self.assertEqual(result["status"], "PASS_WITH_WARNINGS")
            self.assertTrue(result["schema_validation_executed"])
            self.assertEqual(result["schema_validation_mode"], "minimal_json_schema_subset")
            self.assertEqual(result["schema_helper_alignment_status"], "PASS")
            self.assertTrue(result["family_index_json_valid"])
            self.assertTrue(result["example_events_json_valid"])
            self.assertTrue(result["all_example_events_validate"])
            self.assertTrue(result["all_example_refs_parse"])
            self.assertTrue(result["reference_id_integration_preserved"])
            self.assertTrue(result["predecessor_compatibility_preserved"])
            self.assertTrue(result["unknown_optional_event_type_warned"])
            self.assertTrue(result["unknown_required_event_type_fails_closed"])
            self.assertTrue(result["invalid_event_types_rejected"])
            self.assertFalse(result["runtime_event_store_implemented"])
            self.assertFalse(result["event_sourcing_runtime_implemented"])
            self.assertFalse(result["okf_knowledge_bundle_implemented"])
            self.assertFalse(result["patch_transaction_implemented"])
            self.assertEqual(result["recommended_next_task"], "AIDE-CHECK-EVENT-RECORD-SCHEMA-01")
            self.assertTrue((root / ".aide/reports/event-record/validation.json").exists())

    def test_event_record_cli_status_project_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_event_record_files(root)
            parser = aide_lite.build_parser(REPO_ROOT)
            for command in [
                ["--repo-root", str(root), "event-record", "status"],
                ["--repo-root", str(root), "event-record", "project"],
                ["--repo-root", str(root), "event-record", "validate"],
            ]:
                parsed = parser.parse_args(command)
                output = io.StringIO()
                with redirect_stdout(output):
                    result = parsed.handler(parsed)
                self.assertEqual(result, 0, output.getvalue())
                self.assertIn("recorded: false", output.getvalue())
                self.assertIn("projection_only: true", output.getvalue())
                self.assertIn("runtime_event_store_implemented: false", output.getvalue())
                self.assertIn("event_sourcing_runtime_implemented: false", output.getvalue())
                self.assertIn("okf_knowledge_bundle_implemented: false", output.getvalue())
                self.assertIn("provider_or_model_calls: none", output.getvalue())
                self.assertIn("network_calls: none", output.getvalue())

    def test_event_record_cli_rejects_runtime_subcommands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        for subcommand in ["append", "replay", "reconstruct", "daemon", "store", "stream", "submit", "run", "retry", "summarize"]:
            with self.subTest(subcommand=subcommand):
                stderr = io.StringIO()
                with redirect_stdout(io.StringIO()), redirect_stderr(stderr), self.assertRaises(SystemExit):
                    parser.parse_args(["event-record", subcommand])

    def test_reports_recommend_check_next_and_do_not_overclaim_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_event_record_files(root)
            event_record.event_record_validate(root)
            validation = json.loads((root / ".aide/reports/event-record/validation.json").read_text(encoding="utf-8"))
            future_text = (root / ".aide/reports/event-record/future-work.md").read_text(encoding="utf-8")
            self.assertEqual(validation["recommended_next_task"], "AIDE-CHECK-EVENT-RECORD-SCHEMA-01")
            self.assertIn("AIDE-CHECK-EVENT-RECORD-SCHEMA-01", future_text.splitlines()[4])
            for key in [
                "runtime_event_store_implemented",
                "event_sourcing_runtime_implemented",
                "append_only_runtime_store_implemented",
                "runtime_event_log_implemented",
                "state_reconstruction_implemented",
                "okf_knowledge_bundle_implemented",
                "patch_transaction_implemented",
                "adapter_manifest_implemented",
                "context_pack_v2_implemented",
                "runtime_reference_registry_implemented",
                "resolver_service_implemented",
                "target_mutation",
                "active_repo_apply_mutation",
                "branch_mutation",
                "provider_model_calls",
                "gateway_calls",
                "network_calls",
                "github_mutation",
            ]:
                self.assertFalse(validation[key], key)

    def test_parser_preserves_existing_protocol_commands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        commands = [
            ["contract-envelope", "status"],
            ["evidence-packet", "status"],
            ["workunit-queue", "status"],
            ["worker-run", "status"],
            ["test-job", "status"],
            ["reference-id", "status"],
            ["event-record", "status"],
            ["workunit", "status"],
        ]
        for command in commands:
            with self.subTest(command=command):
                parsed = parser.parse_args(command)
                self.assertTrue(callable(parsed.handler))


if __name__ == "__main__":
    unittest.main()
