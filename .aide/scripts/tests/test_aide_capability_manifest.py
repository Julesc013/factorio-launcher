from __future__ import annotations

import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from core.protocol import capability_manifest, reference_id


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_capability_manifest", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_capability_manifest"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


def capability_manifest_source_files() -> list[str]:
    files = {
        ".aide/scripts/aide_lite.py",
        ".aide/protocol/aide-capability-manifest.schema.json",
        "core/protocol/__init__.py",
        "core/protocol/capability_manifest.py",
        "core/protocol/envelope.py",
        "core/protocol/reference_id.py",
    }
    files.update(capability_manifest.source_artifact_paths(REPO_ROOT))
    return sorted(files)


def copy_capability_manifest_files(root: Path) -> None:
    for rel in capability_manifest_source_files():
        source = REPO_ROOT / rel
        if source.exists():
            aide_lite.copy_pack_file(source, root / rel)


class AIDECapabilityManifestTests(unittest.TestCase):
    def test_schema_file_exists_and_parses(self) -> None:
        schema = capability_manifest.load_capability_manifest_schema(REPO_ROOT)
        self.assertEqual(schema["title"], "AIDE Minimal CapabilityManifest")
        self.assertEqual(schema["properties"]["kind"]["enum"], ["CapabilityManifest"])
        self.assertEqual(schema["required"], ["apiVersion", "kind", "metadata", "spec", "status"])

    def test_project_writes_required_reports_and_preserves_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_capability_manifest_files(root)
            source_paths = [root / rel for rel in capability_manifest.source_artifact_paths(root)]
            before = {path: path.read_bytes() for path in source_paths if path.exists()}
            report = capability_manifest.write_capability_reports(root)
            self.assertEqual(report["status"], "PASS_WITH_WARNINGS")
            self.assertFalse(report["source_artifacts_mutated"])
            self.assertEqual(report["capabilities_count"], 11)
            self.assertEqual(report["accepted_capabilities_count"], 11)
            self.assertEqual(report["accepted_with_warnings_count"], 11)
            self.assertEqual(report["metadata_only_count"], 2)
            self.assertEqual(report["report_only_count"], 1)
            self.assertGreaterEqual(report["projection_only_count"], 4)
            self.assertEqual(before, {path: path.read_bytes() for path in before})
            for rel in capability_manifest.REQUIRED_REPORTS:
                self.assertTrue((root / rel).exists(), rel.as_posix())

    def test_capabilities_json_and_index_parse(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_capability_manifest_files(root)
            capability_manifest.write_capability_reports(root)
            capabilities = json.loads((root / ".aide/reports/capability-manifest/capabilities.json").read_text(encoding="utf-8"))
            index = json.loads((root / ".aide/reports/capability-manifest/capability-index.json").read_text(encoding="utf-8"))
            self.assertEqual(capabilities["kind"], "CapabilityManifest")
            self.assertEqual(index["report_type"], "capability_manifest_index")
            labels = [item["capability_label"] for item in capabilities["spec"]["capabilities"]]
            self.assertEqual(labels, capability_manifest.REQUIRED_CAPABILITY_LABELS)

    def test_accepted_capabilities_have_evidence_and_preserve_status_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_capability_manifest_files(root)
            manifest = capability_manifest.build_capability_manifest(root)
            records = {item["capability_label"]: item for item in manifest["spec"]["capabilities"]}
            for label in capability_manifest.REQUIRED_CAPABILITY_LABELS:
                record = records[label]
                self.assertTrue(record["accepted"], label)
                self.assertTrue(record["accepted_with_warnings"], label)
                self.assertEqual(record["acceptance_state"], "accepted_with_warnings")
                self.assertTrue(record["evidence_refs"], label)
                self.assertFalse(record["runtime"], label)
                self.assertFalse(record["admitted_by_conformance"], label)
            self.assertTrue(records["minimal_worker_run_schema"]["metadata_only"])
            self.assertTrue(records["minimal_test_job_schema"]["metadata_only"])
            self.assertTrue(records["minimal_reconciler_reports"]["report_only"])
            self.assertTrue(records["minimal_reference_id_scheme"]["projection_only"])
            self.assertTrue(records["minimal_event_record_schema"]["projection_only"])
            self.assertTrue(records["minimal_okf_knowledge_bundle"]["projection_only"])
            self.assertTrue(records["minimal_workunit_queue_metadata_mutation_cli"]["mutating"])

    def test_conformance_placeholders_do_not_imply_admission(self) -> None:
        manifest = capability_manifest.build_capability_manifest(REPO_ROOT)
        self.assertFalse(manifest["status"]["conformance_implemented"])
        self.assertFalse(manifest["status"]["admission_implemented"])
        self.assertFalse(manifest["status"]["execution_implemented"])
        self.assertFalse(manifest["spec"]["conformance"]["profile_implemented"])
        self.assertFalse(manifest["spec"]["conformance"]["result_implemented"])
        self.assertFalse(manifest["spec"]["conformance"]["admitted_by_conformance"])
        for record in manifest["spec"]["capabilities"]:
            self.assertIsNone(record["conformance"]["profile_ref"])
            self.assertIsNone(record["conformance"]["result_ref"])
            self.assertFalse(record["conformance"]["admitted"])

    def test_future_and_deferred_capabilities_are_not_marked_accepted(self) -> None:
        manifest = capability_manifest.build_capability_manifest(REPO_ROOT)
        labels = {record["capability_label"] for record in manifest["spec"]["capabilities"] if record["accepted"]}
        for future_label in [
            "conformance_profile",
            "conformance_result",
            "patch_transaction",
            "adapter_manifest",
            "context_pack_v2",
            "runtime_capability_registry",
        ]:
            self.assertNotIn(future_label, labels)

    def test_refs_parse_and_okf_reconciler_refs_are_present(self) -> None:
        manifest = capability_manifest.build_capability_manifest(REPO_ROOT)
        records = manifest["spec"]["capabilities"]
        for record in records:
            for field in ["source_refs", "evidence_refs", "report_refs", "event_refs"]:
                for ref in record[field]:
                    result = reference_id.validate_reference_id(ref, required=True)
                    self.assertTrue(result.valid, ref)
            self.assertTrue(record["capability_ref"].startswith("aide://capability/"))
        self.assertTrue(any(record["okf_refs"] for record in records))
        reconciler = next(record for record in records if record["capability_label"] == "minimal_reconciler_reports")
        self.assertTrue(reconciler["reconciler_findings"])

    def test_validate_reports_pass_with_warnings_and_required_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_capability_manifest_files(root)
            capability_manifest.write_capability_reports(root)
            validation = capability_manifest.validate_capability_manifest(root)
            self.assertEqual(validation["validation_status"], "PASS_WITH_WARNINGS")
            for key in [
                "schema_exists",
                "helper_exists",
                "cli_registered",
                "reports_generated",
                "capabilities_json_valid",
                "capability_index_json_valid",
                "required_capabilities_projected",
                "accepted_capabilities_have_evidence",
                "accepted_with_warnings_preserved",
                "status_semantics_valid",
                "conformance_not_overclaimed",
                "execution_not_overclaimed",
                "reconciler_integration_checked",
                "okf_integration_checked",
                "reference_id_refs_valid",
                "predecessor_compatibility_preserved",
                "overclaiming_check_passed",
                "forbidden_ops_preserved",
            ]:
                self.assertTrue(validation[key], key)

    def test_capability_manifest_cli_status_project_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_capability_manifest_files(root)
            parser = aide_lite.build_parser(REPO_ROOT)
            commands = [
                ["--repo-root", str(root), "capability-manifest", "status"],
                ["--repo-root", str(root), "capability-manifest", "project"],
                ["--repo-root", str(root), "capability-manifest", "validate"],
            ]
            for command in commands:
                parsed = parser.parse_args(command)
                output = io.StringIO()
                with redirect_stdout(output):
                    result = parsed.handler(parsed)
                self.assertEqual(result, 0, output.getvalue())
                self.assertIn("declaration_only: true", output.getvalue())
                self.assertIn("conformance_implemented: false", output.getvalue())
                self.assertIn("admission_implemented: false", output.getvalue())
                self.assertIn("execution_implemented: false", output.getvalue())
                self.assertIn("provider_or_model_calls: none", output.getvalue())
                self.assertIn("network_calls: false", output.getvalue())

    def test_cli_rejects_forbidden_runtime_or_admission_subcommands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        for subcommand in ["run", "execute", "admit", "conformance", "adapter-run", "repair", "mutate"]:
            with self.subTest(subcommand=subcommand):
                stderr = io.StringIO()
                with redirect_stdout(io.StringIO()), redirect_stderr(stderr), self.assertRaises(SystemExit):
                    parser.parse_args(["capability-manifest", subcommand])

    def test_reports_do_not_overclaim_future_layers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_capability_manifest_files(root)
            capability_manifest.write_capability_reports(root)
            combined = "\n".join(
                (root / rel).read_text(encoding="utf-8").lower()
                for rel in [
                    ".aide/reports/capability-manifest/projection-report.md",
                    ".aide/reports/capability-manifest/validation.md",
                    ".aide/reports/capability-manifest/capabilities.md",
                    ".aide/reports/capability-manifest/future-work.md",
                ]
            )
            for forbidden in [
                "capabilitymanifest proves capability",
                "capabilitymanifest admits capability",
                "conformanceprofile implemented",
                "patchtransaction implemented",
                "adaptermanifest implemented",
                "contextpack v2 implemented",
                "runtime implemented",
                "provider/model calls implemented",
                "release ready",
                "production ready",
            ]:
                self.assertNotIn(forbidden, combined)


if __name__ == "__main__":
    unittest.main()
