from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from core.protocol import reference_id


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_reference_id", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_reference_id"] = aide_lite
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
    ".aide/protocol/aide-envelope.schema.json",
    ".aide/protocol/aide-evidence-packet.schema.json",
    ".aide/protocol/aide-workunit.schema.json",
    ".aide/protocol/aide-worker-run.schema.json",
    ".aide/protocol/aide-test-job.schema.json",
    ".aide/protocol/aide-reference-id.schema.json",
]

REFERENCE_LOCATOR_FILES = sorted(
    {
        item["path"]
        for item in reference_id.REFERENCE_DEFINITIONS
        if isinstance(item.get("path"), str) and not item["path"].startswith(".aide/reports/reference-id/")
    }
)

COMPATIBILITY_REPORT_FILES = [
    ".aide/reports/contract-envelope/validation.json",
    ".aide/reports/evidence-packet/validation.json",
    ".aide/reports/workunit-queue/validation.json",
    ".aide/reports/worker-run/validation.json",
    ".aide/reports/test-job/validation.json",
    ".aide/reports/test-job-accept/acceptance-report.json",
]


def copy_reference_id_files(root: Path) -> None:
    for rel in [*SOURCE_FILES, *REFERENCE_LOCATOR_FILES, *COMPATIBILITY_REPORT_FILES]:
        source = REPO_ROOT / rel
        if source.exists():
            aide_lite.copy_pack_file(source, root / rel)


class AIDEReferenceIDSchemeTests(unittest.TestCase):
    def test_schema_file_exists_and_parses_as_json(self) -> None:
        schema = reference_id.load_reference_id_schema(REPO_ROOT)
        self.assertEqual(schema["title"], "AIDE Minimal ReferenceID")
        self.assertTrue(schema["additionalProperties"])
        self.assertEqual(schema["properties"]["kind"]["enum"], ["ReferenceID"])

    def test_schema_declares_reference_id_public_shape(self) -> None:
        schema = reference_id.load_reference_id_schema(REPO_ROOT)
        self.assertEqual(schema["required"], ["apiVersion", "kind", "metadata", "spec", "status"])
        for field in ["ref", "ref_kind", "identity", "locator", "required", "relationship", "explicit_non_capabilities"]:
            self.assertIn(field, schema["properties"]["spec"]["required"])

    def test_parse_valid_reference_id(self) -> None:
        parsed = reference_id.parse_reference_id("aide://schema/test-job#primary")
        self.assertEqual(parsed.kind, "schema")
        self.assertEqual(parsed.object_id, "test-job")
        self.assertEqual(parsed.fragment, "primary")
        self.assertEqual(parsed.ref, "aide://schema/test-job#primary")

    def test_format_reference_id_round_trips(self) -> None:
        self.assertEqual(
            reference_id.format_reference_id("queue-task", "AIDE-CHECK-REFERENCE-ID-SCHEME-01"),
            "aide://queue-task/AIDE-CHECK-REFERENCE-ID-SCHEME-01",
        )

    def test_parse_reference_id_rejects_invalid_scheme_missing_kind_missing_id_and_extra_path(self) -> None:
        invalid_refs = [
            "https://schema/test-job",
            "aide:///test-job",
            "aide://schema/",
            "aide://schema/test-job/extra",
        ]
        for ref in invalid_refs:
            with self.assertRaises(ValueError, msg=ref):
                reference_id.parse_reference_id(ref)

    def test_parse_reference_id_rejects_traversal_and_whitespace(self) -> None:
        invalid_refs = [
            "aide://schema/..",
            "aide://schema/../test-job",
            "aide://schema/bad id",
            "aide://schema/test-job#bad fragment",
            "aide://schema/test-job\n",
        ]
        for ref in invalid_refs:
            with self.assertRaises(ValueError, msg=ref):
                reference_id.parse_reference_id(ref)

    def test_unknown_optional_ref_kind_warns(self) -> None:
        result = reference_id.validate_reference_id("aide://future-kind/optional", required=False)
        self.assertTrue(result.valid)
        self.assertTrue(result.warnings)
        self.assertEqual(result.status, "PASS_WITH_WARNINGS")

    def test_unknown_required_ref_kind_fails_closed(self) -> None:
        result = reference_id.validate_reference_id("aide://future-kind/required", required=True)
        self.assertFalse(result.valid)
        self.assertTrue(result.errors)
        self.assertEqual(result.status, "FAILED_VALIDATION")

    def test_reference_record_with_locator_validates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_reference_id_files(root)
            record = reference_id.build_reference_record(
                repo_root=root,
                ref="aide://schema/test-job",
                title="TestJob Schema",
                locator_path=".aide/protocol/aide-test-job.schema.json",
                media_type="application/schema+json",
                role="protocol_schema",
                required=True,
            )
            self.assertEqual(reference_id.validate_reference_record(record), [])
            self.assertIn("sha256", record["spec"]["locator"])

    def test_locator_path_is_not_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_reference_id_files(root)
            record = reference_id.build_reference_record(
                repo_root=root,
                ref="aide://schema/test-job",
                title="TestJob Schema",
                locator_path=".aide/protocol/aide-test-job.schema.json",
                media_type="application/schema+json",
                role="protocol_schema",
                required=True,
            )
            self.assertEqual(record["spec"]["stable_identity"], "aide://schema/test-job")
            self.assertEqual(record["spec"]["identity"]["id"], "test-job")
            self.assertEqual(record["spec"]["locator"]["path"], ".aide/protocol/aide-test-job.schema.json")

    def test_sha256_is_deterministic_for_same_locator(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_reference_id_files(root)
            kwargs = {
                "repo_root": root,
                "ref": "aide://schema/reference-id",
                "title": "ReferenceID Schema",
                "locator_path": ".aide/protocol/aide-reference-id.schema.json",
                "media_type": "application/schema+json",
                "role": "protocol_schema",
                "required": True,
            }
            first = reference_id.build_reference_record(**kwargs)
            second = reference_id.build_reference_record(**kwargs)
            self.assertEqual(first["spec"]["locator"]["sha256"], second["spec"]["locator"]["sha256"])

    def test_schema_helper_alignment_passes_current_schema(self) -> None:
        schema = reference_id.load_reference_id_schema(REPO_ROOT)
        alignment = reference_id.check_schema_helper_alignment(schema)
        self.assertEqual(alignment["schema_helper_alignment_status"], "PASS")
        self.assertEqual(alignment["errors"], [])

    def test_schema_validation_accepts_valid_reference_record(self) -> None:
        schema = reference_id.load_reference_id_schema(REPO_ROOT)
        self.assertEqual(reference_id.validate_reference_record_with_schema(reference_id.sample_reference_record(), schema), [])

    def test_runtime_validation_fails_closed_for_unknown_required_kind(self) -> None:
        schema = reference_id.load_reference_id_schema(REPO_ROOT)
        result = reference_id.validate_reference_record_runtime(reference_id.sample_unknown_required_reference_record(), schema)
        self.assertEqual(result["status"], "FAILED_VALIDATION")
        self.assertIn("unknown required ref kind: future-kind", result["helper_validation_errors"])

    def test_projection_writes_reference_map_and_does_not_mutate_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_reference_id_files(root)
            source_paths = reference_id._source_paths(root)
            before = {path: path.read_bytes() for path in source_paths}
            result = reference_id.project_reference_map(root)
            self.assertEqual(result["status"], "PASS_WITH_WARNINGS")
            self.assertFalse(result["source_artifacts_mutated"])
            self.assertGreaterEqual(result["projected_refs_count"], 20)
            self.assertEqual(before, {path: path.read_bytes() for path in source_paths})

    def test_projection_writes_parseable_reference_map_json(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_reference_id_files(root)
            reference_id.project_reference_map(root)
            data = json.loads((root / ".aide/reports/reference-id/reference-map.json").read_text(encoding="utf-8"))
            self.assertEqual(data["kind"], "ReferenceIDMap")
            self.assertIn("aide://schema/reference-id", [record["spec"]["ref"] for record in data["references"]])

    def test_validate_command_writes_validation_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_reference_id_files(root)
            result = reference_id.reference_id_validate(root)
            self.assertEqual(result["status"], "PASS_WITH_WARNINGS")
            self.assertTrue(result["schema_validation_executed"])
            self.assertEqual(result["schema_validation_mode"], "minimal_json_schema_subset")
            self.assertEqual(result["schema_helper_alignment_status"], "PASS")
            self.assertTrue(result["reference_map_json_valid"])
            self.assertTrue(result["all_projected_refs_parse"])
            self.assertTrue(result["required_locators_exist"])
            self.assertTrue(result["sha256_checked"])
            self.assertTrue(result["unknown_optional_ref_kind_warned"])
            self.assertTrue(result["unknown_required_ref_kind_fails_closed"])
            self.assertFalse(result["runtime_reference_registry_implemented"])
            self.assertFalse(result["event_record_implemented"])
            self.assertFalse(result["okf_knowledge_bundle_implemented"])
            self.assertFalse(result["patch_transaction_implemented"])
            self.assertEqual(result["recommended_next_task"], "AIDE-CHECK-REFERENCE-ID-SCHEME-01")
            self.assertTrue((root / ".aide/reports/reference-id/validation.json").exists())

    def test_reference_id_cli_status_project_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_reference_id_files(root)
            parser = aide_lite.build_parser(REPO_ROOT)
            for command in [
                ["--repo-root", str(root), "reference-id", "status"],
                ["--repo-root", str(root), "reference-id", "project"],
                ["--repo-root", str(root), "reference-id", "validate"],
            ]:
                parsed = parser.parse_args(command)
                output = io.StringIO()
                with redirect_stdout(output):
                    result = parsed.handler(parsed)
                self.assertEqual(result, 0, output.getvalue())
                self.assertIn("runtime_reference_registry_implemented: false", output.getvalue())
                self.assertIn("resolver_service_implemented: false", output.getvalue())
                self.assertIn("event_record_implemented: false", output.getvalue())
                self.assertIn("provider_or_model_calls: none", output.getvalue())
                self.assertIn("network_calls: none", output.getvalue())

    def test_reports_do_not_recommend_event_record_directly_or_overclaim_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_reference_id_files(root)
            reference_id.reference_id_validate(root)
            validation = json.loads((root / ".aide/reports/reference-id/validation.json").read_text(encoding="utf-8"))
            future_text = (root / ".aide/reports/reference-id/future-work.md").read_text(encoding="utf-8")
            self.assertEqual(validation["recommended_next_task"], "AIDE-CHECK-REFERENCE-ID-SCHEME-01")
            self.assertNotIn("AIDE-BUILD-EVENT-RECORD", future_text)
            for key in [
                "runtime_reference_registry_implemented",
                "resolver_service_implemented",
                "event_record_implemented",
                "okf_knowledge_bundle_implemented",
                "patch_transaction_implemented",
                "adapter_manifest_implemented",
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
            ["workunit", "status"],
        ]
        for command in commands:
            with self.subTest(command=command):
                parsed = parser.parse_args(command)
                self.assertTrue(callable(parsed.handler))


if __name__ == "__main__":
    unittest.main()
