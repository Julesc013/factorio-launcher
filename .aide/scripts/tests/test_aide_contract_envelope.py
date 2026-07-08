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

from core.protocol import envelope


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_contract_envelope", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_contract_envelope"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


SOURCE_FILES = [
    "core/protocol/__init__.py",
    "core/protocol/envelope.py",
    ".aide/protocol/aide-envelope.schema.json",
    ".aide/reports/lifecycle-fixture-runner/latest-run.json",
    ".aide/reports/lifecycle-fixture-runner/verify.json",
    ".aide/reports/lifecycle-fixture-runner-acceptance/acceptance-report.json",
]


def copy_contract_envelope_files(root: Path) -> None:
    for rel in SOURCE_FILES:
        source = REPO_ROOT / rel
        if source.exists():
            aide_lite.copy_pack_file(source, root / rel)


def sample_envelope() -> dict[str, object]:
    return envelope.build_envelope(
        "LifecycleFixtureRunReport",
        {"id": "run-1"},
        {"scenario_id": "install-managed-section", "mode": "apply-temp"},
        {"phase": "PASS", "capability_label": "fixture_temp_apply_only"},
    )


class AIDEContractEnvelopeTests(unittest.TestCase):
    def test_build_envelope_uses_public_shape(self) -> None:
        obj = sample_envelope()
        self.assertEqual(obj["apiVersion"], "aide.dev/v1alpha1")
        self.assertEqual(obj["kind"], "LifecycleFixtureRunReport")
        self.assertIsInstance(obj["metadata"], dict)
        self.assertIsInstance(obj["spec"], dict)
        self.assertIsInstance(obj["status"], dict)

    def test_validate_envelope_accepts_valid_object(self) -> None:
        self.assertEqual(envelope.validate_envelope(sample_envelope(), envelope.SUPPORTED_KINDS), [])

    def test_validate_envelope_rejects_missing_api_version(self) -> None:
        obj = sample_envelope()
        obj.pop("apiVersion")
        self.assertIn("apiVersion must be a non-empty string", envelope.validate_envelope(obj))

    def test_validate_envelope_rejects_missing_kind(self) -> None:
        obj = sample_envelope()
        obj.pop("kind")
        self.assertIn("kind must be a non-empty string", envelope.validate_envelope(obj))

    def test_validate_envelope_rejects_non_object_metadata(self) -> None:
        obj = sample_envelope()
        obj["metadata"] = []
        self.assertIn("metadata must be an object", envelope.validate_envelope(obj))

    def test_validate_envelope_rejects_non_object_spec(self) -> None:
        obj = sample_envelope()
        obj["spec"] = []
        self.assertIn("spec must be an object", envelope.validate_envelope(obj))

    def test_validate_envelope_rejects_non_object_status(self) -> None:
        obj = sample_envelope()
        obj["status"] = []
        self.assertIn("status must be an object", envelope.validate_envelope(obj))

    def test_validate_envelope_tolerates_unknown_optional_fields(self) -> None:
        obj = sample_envelope()
        obj["x-aide-experimental"] = {"future": True}
        obj["metadata"]["x-new-field"] = "ignored"
        self.assertEqual(envelope.validate_envelope(obj, envelope.SUPPORTED_KINDS), [])

    def test_validate_envelope_rejects_unknown_required_capability(self) -> None:
        obj = sample_envelope()
        obj["metadata"]["compatibility"]["requiredCapabilities"] = ["future.required"]
        errors = envelope.validate_envelope(obj)
        self.assertIn("unknown required capability: future.required", errors)

    def test_validate_envelope_rejects_invalid_semverish_value(self) -> None:
        obj = sample_envelope()
        obj["metadata"]["compatibility"]["protocolVersion"] = "1"
        errors = envelope.validate_envelope(obj)
        self.assertIn("metadata.compatibility.protocolVersion must be SemVer-like", errors)

    def test_validate_envelope_rejects_unknown_capability_label(self) -> None:
        obj = sample_envelope()
        obj["status"]["capability_label"] = "target_repo_apply"
        errors = envelope.validate_envelope(obj)
        self.assertIn("unknown capability_label: target_repo_apply", errors)

    def test_schema_json_parses_and_requires_public_fields(self) -> None:
        schema = envelope.load_envelope_schema(REPO_ROOT)
        self.assertEqual(schema["required"], ["apiVersion", "kind", "metadata", "spec", "status"])
        self.assertTrue(schema["additionalProperties"])

    def test_validate_envelope_with_schema_accepts_valid_object(self) -> None:
        schema = envelope.load_envelope_schema(REPO_ROOT)
        self.assertEqual(envelope.validate_envelope_with_schema(sample_envelope(), schema), [])

    def test_validate_envelope_with_schema_rejects_missing_public_fields(self) -> None:
        schema = envelope.load_envelope_schema(REPO_ROOT)
        for field in ["apiVersion", "kind", "metadata", "spec", "status"]:
            obj = sample_envelope()
            obj.pop(field)
            errors = envelope.validate_envelope_with_schema(obj, schema)
            self.assertTrue(any(field in error for error in errors), field)

    def test_validate_envelope_with_schema_rejects_wrong_public_field_types(self) -> None:
        schema = envelope.load_envelope_schema(REPO_ROOT)
        for field in ["metadata", "spec", "status"]:
            obj = sample_envelope()
            obj[field] = []
            errors = envelope.validate_envelope_with_schema(obj, schema)
            self.assertTrue(any(field in error and "object" in error for error in errors), field)

    def test_runtime_schema_validation_tolerates_unknown_optional_fields(self) -> None:
        schema = envelope.load_envelope_schema(REPO_ROOT)
        result = envelope.validate_envelope_runtime(
            envelope.sample_optional_field_envelope(),
            schema,
            envelope.SUPPORTED_KINDS,
        )
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["schema_validation_executed"])

    def test_runtime_schema_validation_fails_closed_for_unknown_required_capability(self) -> None:
        schema = envelope.load_envelope_schema(REPO_ROOT)
        result = envelope.validate_envelope_runtime(
            envelope.sample_unknown_required_capability_envelope(),
            schema,
            envelope.SUPPORTED_KINDS,
        )
        self.assertEqual(result["status"], "FAILED_VALIDATION")
        self.assertIn("unknown required capability: future.required", result["helper_validation_errors"])

    def test_schema_and_helper_accept_lifecycle_run_projection(self) -> None:
        schema = envelope.load_envelope_schema(REPO_ROOT)
        report = json.loads((REPO_ROOT / ".aide/reports/lifecycle-fixture-runner/latest-run.json").read_text(encoding="utf-8"))
        projected = envelope.project_lifecycle_run_report(report, Path("source.json"))
        self.assertEqual(envelope.validate_envelope(projected, envelope.SUPPORTED_KINDS), [])
        self.assertEqual(envelope.validate_envelope_with_schema(projected, schema), [])

    def test_schema_and_helper_accept_lifecycle_verify_projection(self) -> None:
        schema = envelope.load_envelope_schema(REPO_ROOT)
        report = json.loads((REPO_ROOT / ".aide/reports/lifecycle-fixture-runner/verify.json").read_text(encoding="utf-8"))
        projected = envelope.project_lifecycle_verify_report(report, Path("verify.json"))
        self.assertEqual(envelope.validate_envelope(projected, envelope.SUPPORTED_KINDS), [])
        self.assertEqual(envelope.validate_envelope_with_schema(projected, schema), [])

    def test_schema_and_helper_reject_malformed_projection(self) -> None:
        schema = envelope.load_envelope_schema(REPO_ROOT)
        malformed = sample_envelope()
        malformed.pop("status")
        self.assertTrue(envelope.validate_envelope(malformed, envelope.SUPPORTED_KINDS))
        self.assertTrue(envelope.validate_envelope_with_schema(malformed, schema))

    def test_schema_helper_alignment_passes_current_schema(self) -> None:
        schema = envelope.load_envelope_schema(REPO_ROOT)
        alignment = envelope.check_schema_helper_alignment(schema)
        self.assertEqual(alignment["schema_helper_alignment_status"], "PASS")
        self.assertEqual(alignment["errors"], [])

    def test_schema_helper_alignment_fails_malformed_schema_copy(self) -> None:
        schema = copy.deepcopy(envelope.load_envelope_schema(REPO_ROOT))
        schema["required"] = ["apiVersion", "kind", "metadata", "spec"]
        alignment = envelope.check_schema_helper_alignment(schema)
        self.assertEqual(alignment["schema_helper_alignment_status"], "FAILED_VALIDATION")
        self.assertTrue(any("status" in error for error in alignment["errors"]))

    def test_project_lifecycle_run_report_is_valid_and_scoped(self) -> None:
        report = json.loads((REPO_ROOT / ".aide/reports/lifecycle-fixture-runner/latest-run.json").read_text(encoding="utf-8"))
        projected = envelope.project_lifecycle_run_report(report, Path("source.json"))
        self.assertEqual(envelope.validate_envelope(projected, envelope.SUPPORTED_KINDS), [])
        self.assertEqual(projected["status"]["capability_label"], "fixture_temp_apply_only")
        self.assertFalse(projected["status"]["target_repo_mutated"])
        self.assertIn("target_repo_apply", projected["status"]["explicit_non_capabilities"])
        self.assertIn("branch_worktree_automation", projected["status"]["explicit_non_capabilities"])

    def test_project_lifecycle_verify_report_is_valid_and_scoped(self) -> None:
        report = json.loads((REPO_ROOT / ".aide/reports/lifecycle-fixture-runner/verify.json").read_text(encoding="utf-8"))
        projected = envelope.project_lifecycle_verify_report(report, Path("verify.json"))
        self.assertEqual(envelope.validate_envelope(projected, envelope.SUPPORTED_KINDS), [])
        self.assertEqual(projected["status"]["capability_label"], "fixture_temp_apply_only")
        self.assertTrue(projected["status"]["canonical_fixture_unchanged"])
        self.assertTrue(projected["status"]["unsupported_capabilities_not_claimed"])

    def test_projection_does_not_mutate_source_object(self) -> None:
        report = json.loads((REPO_ROOT / ".aide/reports/lifecycle-fixture-runner/latest-run.json").read_text(encoding="utf-8"))
        before = copy.deepcopy(report)
        envelope.project_lifecycle_run_report(report, Path("source.json"))
        self.assertEqual(report, before)

    def test_project_command_writes_projection_without_changing_sources(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_contract_envelope_files(root)
            source_paths = [
                root / ".aide/reports/lifecycle-fixture-runner/latest-run.json",
                root / ".aide/reports/lifecycle-fixture-runner/verify.json",
            ]
            before = {path: path.read_bytes() for path in source_paths}

            result = envelope.project_lifecycle_fixture_runner(root)

            self.assertEqual(result["status"], "PASS")
            self.assertTrue((root / ".aide/reports/contract-envelope/projections/lifecycle-fixture-latest-run.envelope.json").exists())
            self.assertEqual(before, {path: path.read_bytes() for path in source_paths})

    def test_validate_command_writes_validation_report(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_contract_envelope_files(root)

            result = envelope.contract_envelope_validate(root)

            self.assertEqual(result["status"], "PASS")
            self.assertTrue(result["schema_validation_executed"])
            self.assertEqual(result["schema_validation_mode"], "minimal_json_schema_subset")
            self.assertTrue(result["schema_helper_alignment_checked"])
            self.assertEqual(result["schema_helper_alignment_status"], "PASS")
            self.assertTrue(result["unknown_optional_fields_tolerated"])
            self.assertTrue(result["unknown_required_capability_fails_closed"])
            self.assertIn("Full JSON Schema Draft 2020-12 validation remains future work.", result["schema_validation_limitations"])
            self.assertTrue(result["backwards_compatibility_preserved"])
            self.assertFalse(result["destructive_migration_performed"])
            self.assertTrue((root / ".aide/reports/contract-envelope/validation.json").exists())
            self.assertTrue((root / ".aide/reports/contract-envelope/future-work.md").exists())
            self.assertTrue((root / ".aide/reports/contract-envelope/unfinished-work.md").exists())

    def test_parser_accepts_contract_envelope_commands_and_preserves_lifecycle_fixture(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        commands = [
            ["contract-envelope", "status"],
            ["contract-envelope", "project", "--source", "lifecycle-fixture-runner"],
            ["contract-envelope", "validate"],
            ["lifecycle-fixture", "status"],
            ["lifecycle-fixture", "run", "--scenario", "install-managed-section", "--mode", "apply-temp"],
            ["lifecycle-fixture", "verify"],
        ]
        for command in commands:
            parsed = parser.parse_args(command)
            self.assertTrue(callable(getattr(parsed, "handler", None)), command)

    def test_contract_envelope_cli_status_project_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_contract_envelope_files(root)
            parser = aide_lite.build_parser(REPO_ROOT)
            for command in [
                ["--repo-root", str(root), "contract-envelope", "status"],
                ["--repo-root", str(root), "contract-envelope", "project", "--source", "lifecycle-fixture-runner"],
                ["--repo-root", str(root), "contract-envelope", "validate"],
            ]:
                parsed = parser.parse_args(command)
                output = io.StringIO()
                with redirect_stdout(output):
                    result = parsed.handler(parsed)
                self.assertEqual(result, 0, output.getvalue())
                self.assertIn("target_mutation: false", output.getvalue())
                self.assertIn("provider_or_model_calls: none", output.getvalue())


if __name__ == "__main__":
    unittest.main()
