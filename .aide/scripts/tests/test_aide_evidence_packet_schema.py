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

from core.protocol import evidence_packet


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_evidence_packet", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_evidence_packet"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


SOURCE_FILES = [
    "core/protocol/__init__.py",
    "core/protocol/envelope.py",
    "core/protocol/evidence_packet.py",
    ".aide/protocol/aide-envelope.schema.json",
    ".aide/protocol/aide-evidence-packet.schema.json",
    ".aide/reports/lifecycle-fixture-runner/latest-run.json",
    ".aide/reports/lifecycle-fixture-runner/verify.json",
    ".aide/reports/lifecycle-fixture-runner/latest-rollback-record.json",
    ".aide/reports/lifecycle-fixture-runner-acceptance/acceptance-report.json",
    ".aide/reports/contract-envelope/validation.json",
    ".aide/reports/contract-envelope-acceptance/acceptance-report.json",
]


def copy_evidence_packet_files(root: Path) -> None:
    for rel in SOURCE_FILES:
        source = REPO_ROOT / rel
        if source.exists():
            aide_lite.copy_pack_file(source, root / rel)


def sample_packet() -> dict[str, object]:
    return evidence_packet.sample_evidence_packet()


class AIDEEvidencePacketTests(unittest.TestCase):
    def test_build_evidence_packet_uses_public_shape(self) -> None:
        obj = sample_packet()
        self.assertEqual(obj["apiVersion"], "aide.dev/v1alpha1")
        self.assertEqual(obj["kind"], "EvidencePacket")
        self.assertIsInstance(obj["metadata"], dict)
        self.assertIsInstance(obj["spec"], dict)
        self.assertIsInstance(obj["status"], dict)

    def test_validate_evidence_packet_accepts_valid_minimal_packet(self) -> None:
        self.assertEqual(evidence_packet.validate_evidence_packet(sample_packet()), [])

    def test_validate_evidence_packet_rejects_missing_api_version(self) -> None:
        obj = sample_packet()
        obj.pop("apiVersion")
        self.assertIn("apiVersion must be a non-empty string", evidence_packet.validate_evidence_packet(obj))

    def test_validate_evidence_packet_rejects_missing_kind(self) -> None:
        obj = sample_packet()
        obj.pop("kind")
        self.assertIn("kind must be a non-empty string", evidence_packet.validate_evidence_packet(obj))

    def test_validate_evidence_packet_rejects_wrong_kind(self) -> None:
        obj = sample_packet()
        obj["kind"] = "WorkUnit"
        self.assertIn("unsupported kind: WorkUnit", evidence_packet.validate_evidence_packet(obj))

    def test_validate_evidence_packet_rejects_missing_metadata(self) -> None:
        obj = sample_packet()
        obj.pop("metadata")
        self.assertIn("missing required field: metadata", evidence_packet.validate_evidence_packet(obj))

    def test_validate_evidence_packet_rejects_missing_spec(self) -> None:
        obj = sample_packet()
        obj.pop("spec")
        self.assertIn("missing required field: spec", evidence_packet.validate_evidence_packet(obj))

    def test_validate_evidence_packet_rejects_missing_status(self) -> None:
        obj = sample_packet()
        obj.pop("status")
        self.assertIn("missing required field: status", evidence_packet.validate_evidence_packet(obj))

    def test_validate_evidence_packet_rejects_missing_source_task_id(self) -> None:
        obj = sample_packet()
        obj["spec"].pop("source_task_id")
        self.assertIn("missing required spec field: source_task_id", evidence_packet.validate_evidence_packet(obj))

    def test_validate_evidence_packet_rejects_missing_subject(self) -> None:
        obj = sample_packet()
        obj["spec"].pop("subject")
        self.assertIn("missing required spec field: subject", evidence_packet.validate_evidence_packet(obj))

    def test_validate_evidence_packet_rejects_missing_claims(self) -> None:
        obj = sample_packet()
        obj["spec"].pop("claims")
        self.assertIn("missing required spec field: claims", evidence_packet.validate_evidence_packet(obj))

    def test_validate_evidence_packet_rejects_non_array_claims(self) -> None:
        obj = sample_packet()
        obj["spec"]["claims"] = {}
        self.assertIn("spec.claims must be an array", evidence_packet.validate_evidence_packet(obj))

    def test_validate_evidence_packet_rejects_unknown_claim_status(self) -> None:
        obj = sample_packet()
        obj["spec"]["claims"][0]["status"] = "maybe"
        errors = evidence_packet.validate_evidence_packet(obj)
        self.assertTrue(any("status is unsupported" in error for error in errors))

    def test_validate_evidence_packet_accepts_supported_claim_status_values(self) -> None:
        for status in sorted(evidence_packet.CLAIM_STATUSES):
            obj = sample_packet()
            obj["spec"]["claims"][0]["status"] = status
            self.assertEqual(evidence_packet.validate_evidence_packet(obj), [], status)

    def test_validate_evidence_packet_preserves_explicit_non_capabilities(self) -> None:
        obj = sample_packet()
        non_caps = obj["spec"]["explicit_non_capabilities"]
        self.assertIn("workunit_schema", non_caps)
        self.assertIn("test_broker", non_caps)
        self.assertIn("service_ready", non_caps)

    def test_explicit_non_capabilities_are_not_implemented_capabilities(self) -> None:
        obj = sample_packet()
        self.assertFalse(
            evidence_packet.implemented_capabilities(obj)
            & set(obj["spec"]["explicit_non_capabilities"])
        )

    def test_validate_evidence_packet_tolerates_unknown_optional_fields(self) -> None:
        obj = evidence_packet.sample_unknown_optional_evidence_packet()
        self.assertEqual(evidence_packet.validate_evidence_packet(obj), [])

    def test_validate_evidence_packet_fails_closed_for_unknown_required_capability(self) -> None:
        obj = evidence_packet.sample_unknown_required_capability_evidence_packet()
        errors = evidence_packet.validate_evidence_packet(obj)
        self.assertIn("unknown required capability: future.required", errors)

    def test_schema_file_parses_and_declares_required_packet_fields(self) -> None:
        schema = evidence_packet.load_evidence_packet_schema(REPO_ROOT)
        self.assertEqual(schema["required"], ["apiVersion", "kind", "metadata", "spec", "status"])
        self.assertTrue(schema["additionalProperties"])

    def test_schema_helper_alignment_passes_current_schema(self) -> None:
        schema = evidence_packet.load_evidence_packet_schema(REPO_ROOT)
        alignment = evidence_packet.check_schema_helper_alignment(schema)
        self.assertEqual(alignment["schema_helper_alignment_status"], "PASS")
        self.assertEqual(alignment["errors"], [])

    def test_schema_validation_accepts_valid_packet(self) -> None:
        schema = evidence_packet.load_evidence_packet_schema(REPO_ROOT)
        self.assertEqual(evidence_packet.validate_evidence_packet_with_schema(sample_packet(), schema), [])

    def test_schema_validation_rejects_missing_required_fields(self) -> None:
        schema = evidence_packet.load_evidence_packet_schema(REPO_ROOT)
        for field in ["apiVersion", "kind", "metadata", "spec", "status"]:
            obj = sample_packet()
            obj.pop(field)
            errors = evidence_packet.validate_evidence_packet_with_schema(obj, schema)
            self.assertTrue(any(field in error for error in errors), field)

    def test_runtime_schema_validation_fails_closed_for_unknown_required_capability(self) -> None:
        schema = evidence_packet.load_evidence_packet_schema(REPO_ROOT)
        result = evidence_packet.validate_evidence_packet_runtime(
            evidence_packet.sample_unknown_required_capability_evidence_packet(),
            schema,
        )
        self.assertEqual(result["status"], "FAILED_VALIDATION")
        self.assertIn("unknown required capability: future.required", result["helper_validation_errors"])

    def test_project_lifecycle_runner_evidence_creates_valid_packets(self) -> None:
        packets = evidence_packet.project_lifecycle_runner_evidence(REPO_ROOT)
        schema = evidence_packet.load_evidence_packet_schema(REPO_ROOT)
        self.assertEqual(set(packets), {
            ".aide/reports/evidence-packet/projections/lifecycle-fixture-run.evidence-packet.json",
            ".aide/reports/evidence-packet/projections/lifecycle-fixture-verify.evidence-packet.json",
            ".aide/reports/evidence-packet/projections/lifecycle-fixture-acceptance.evidence-packet.json",
        })
        for packet in packets.values():
            self.assertEqual(evidence_packet.validate_evidence_packet(packet), [])
            self.assertEqual(evidence_packet.validate_evidence_packet_with_schema(packet, schema), [])

    def test_project_contract_envelope_evidence_creates_valid_packets(self) -> None:
        packets = evidence_packet.project_contract_envelope_evidence(REPO_ROOT)
        schema = evidence_packet.load_evidence_packet_schema(REPO_ROOT)
        self.assertEqual(set(packets), {
            ".aide/reports/evidence-packet/projections/contract-envelope-validation.evidence-packet.json",
            ".aide/reports/evidence-packet/projections/contract-envelope-acceptance.evidence-packet.json",
        })
        for packet in packets.values():
            self.assertEqual(evidence_packet.validate_evidence_packet(packet), [])
            self.assertEqual(evidence_packet.validate_evidence_packet_with_schema(packet, schema), [])

    def test_projection_does_not_mutate_source_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_evidence_packet_files(root)
            source_paths = [root / rel for rel in evidence_packet.SOURCE_ARTIFACTS.values() if (root / rel).exists()]
            before = {path: path.read_bytes() for path in source_paths}
            result = evidence_packet.project_accepted_slices(root)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(before, {path: path.read_bytes() for path in source_paths})

    def test_projection_writes_parseable_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_evidence_packet_files(root)
            result = evidence_packet.project_accepted_slices(root)
            for rel in result["projections_written"]:
                data = json.loads((root / rel).read_text(encoding="utf-8"))
                self.assertEqual(data["kind"], "EvidencePacket")

    def test_validate_command_writes_validation_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_evidence_packet_files(root)
            result = evidence_packet.evidence_packet_validate(root)
            self.assertEqual(result["status"], "PASS")
            self.assertTrue(result["schema_validation_executed"])
            self.assertEqual(result["schema_validation_mode"], "minimal_json_schema_subset")
            self.assertEqual(result["schema_helper_alignment_status"], "PASS")
            self.assertTrue(result["unknown_optional_fields_tolerated"])
            self.assertTrue(result["unknown_required_capability_fails_closed"])
            self.assertTrue(result["explicit_non_capabilities_preserved"])
            self.assertTrue((root / ".aide/reports/evidence-packet/validation.json").exists())

    def test_evidence_packet_cli_status_project_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_evidence_packet_files(root)
            parser = aide_lite.build_parser(REPO_ROOT)
            for command in [
                ["--repo-root", str(root), "evidence-packet", "status"],
                ["--repo-root", str(root), "evidence-packet", "project", "--source", "accepted-slices"],
                ["--repo-root", str(root), "evidence-packet", "validate"],
            ]:
                parsed = parser.parse_args(command)
                output = io.StringIO()
                with redirect_stdout(output):
                    result = parsed.handler(parsed)
                self.assertEqual(result, 0, output.getvalue())
                self.assertIn("target_mutation: false", output.getvalue())
                self.assertIn("provider_or_model_calls: none", output.getvalue())

    def test_parser_preserves_existing_lifecycle_and_contract_commands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        commands = [
            ["lifecycle-fixture", "status"],
            ["lifecycle-fixture", "run", "--scenario", "install-managed-section", "--mode", "apply-temp"],
            ["lifecycle-fixture", "verify"],
            ["contract-envelope", "status"],
            ["contract-envelope", "project", "--source", "lifecycle-fixture-runner"],
            ["contract-envelope", "validate"],
        ]
        for command in commands:
            parsed = parser.parse_args(command)
            self.assertTrue(callable(getattr(parsed, "handler", None)), command)

    def test_projection_packets_do_not_overclaim_future_primitives(self) -> None:
        packets = {
            **evidence_packet.project_lifecycle_runner_evidence(REPO_ROOT),
            **evidence_packet.project_contract_envelope_evidence(REPO_ROOT),
        }
        forbidden = {
            "workunit_schema",
            "workunit_cli",
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
        for packet in packets.values():
            self.assertFalse(evidence_packet.implemented_capabilities(packet) & forbidden)
            self.assertTrue(forbidden & set(packet["spec"]["explicit_non_capabilities"]))

    def test_claim_status_normalization_does_not_create_new_statuses(self) -> None:
        self.assertEqual(evidence_packet.normalize_claim_status("future"), "not_checked")
        self.assertEqual(evidence_packet.normalize_validation_status("MAYBE"), "NOT_RUN")

    def test_schema_helper_alignment_fails_malformed_schema_copy(self) -> None:
        schema = copy.deepcopy(evidence_packet.load_evidence_packet_schema(REPO_ROOT))
        schema["required"] = ["apiVersion", "kind", "metadata", "spec"]
        alignment = evidence_packet.check_schema_helper_alignment(schema)
        self.assertEqual(alignment["schema_helper_alignment_status"], "FAILED_VALIDATION")
        self.assertTrue(any("status" in error for error in alignment["errors"]))

    def test_supported_kind_list_stays_narrow(self) -> None:
        self.assertEqual(
            evidence_packet.SUPPORTED_KINDS,
            {"EvidencePacket", "EvidencePacketProjectionReport", "EvidencePacketValidationReport"},
        )

    def test_no_source_destructive_migration_flag_in_projection_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_evidence_packet_files(root)
            result = evidence_packet.project_accepted_slices(root)
            self.assertFalse(result["destructive_migration_performed"])
            self.assertFalse(result["source_reports_mutated"])


if __name__ == "__main__":
    unittest.main()
