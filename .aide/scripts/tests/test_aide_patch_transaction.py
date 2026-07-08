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

from core.protocol import patch_transaction


REPO_ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_patch_transaction", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_patch_transaction"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


def patch_transaction_source_files() -> list[str]:
    files = {
        ".aide/scripts/aide_lite.py",
        ".aide/scripts/tests/test_aide_patch_transaction.py",
        ".aide/protocol/aide-patch-transaction.schema.json",
        "core/protocol/__init__.py",
        "core/protocol/envelope.py",
        "core/protocol/reference_id.py",
        "core/protocol/patch_transaction.py",
    }
    files.update(patch_transaction.source_artifact_paths(REPO_ROOT))
    return sorted(files)


def copy_patch_transaction_files(root: Path) -> None:
    for rel in patch_transaction_source_files():
        source = REPO_ROOT / rel
        if source.exists():
            aide_lite.copy_pack_file(source, root / rel)


def validation_errors(record: dict[str, object]) -> tuple[list[str], list[str]]:
    schema = patch_transaction.load_patch_transaction_schema(REPO_ROOT)
    return patch_transaction.validate_patch_transaction_with_schema(record, schema)


class AIDEPatchTransactionTests(unittest.TestCase):
    def test_schema_file_exists_and_parses(self) -> None:
        schema = patch_transaction.load_patch_transaction_schema(REPO_ROOT)
        self.assertEqual(schema["title"], "AIDE Minimal PatchTransaction")
        self.assertEqual(schema["properties"]["kind"]["enum"], ["PatchTransaction"])
        self.assertEqual(schema["required"], ["apiVersion", "kind", "metadata", "spec", "status"])

    def test_valid_minimal_patch_transaction_passes_with_warnings(self) -> None:
        record = patch_transaction.build_patch_transaction(REPO_ROOT)
        errors, warnings = validation_errors(record)
        self.assertFalse(errors)
        self.assertTrue(warnings)
        self.assertEqual(record["kind"], "PatchTransaction")
        self.assertEqual(record["spec"]["patch_artifact"]["format"], "unified_diff")
        self.assertFalse(record["status"]["apply_performed"])
        self.assertFalse(record["status"]["target_mutated"])

    def test_stable_reference_id_form(self) -> None:
        record = patch_transaction.build_patch_transaction(REPO_ROOT)
        self.assertEqual(
            record["spec"]["provenance"]["transaction_ref"],
            "aide://patch-transaction/synthetic-managed-section-review-candidate-01",
        )

    def test_projection_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_patch_transaction_files(root)
            patch_transaction.write_patch_transaction_reports(root)
            first = (root / patch_transaction.TRANSACTIONS_JSON).read_text(encoding="utf-8")
            first_patch = (root / patch_transaction.SAMPLE_PATCH_PATH).read_text(encoding="utf-8")
            patch_transaction.write_patch_transaction_reports(root)
            second = (root / patch_transaction.TRANSACTIONS_JSON).read_text(encoding="utf-8")
            second_patch = (root / patch_transaction.SAMPLE_PATCH_PATH).read_text(encoding="utf-8")
            self.assertEqual(first, second)
            self.assertEqual(first_patch, second_patch)

    def test_projection_does_not_mutate_source_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_patch_transaction_files(root)
            source_paths = [root / rel for rel in patch_transaction.source_artifact_paths(root)]
            before = {path: path.read_bytes() for path in source_paths if path.exists()}
            report = patch_transaction.write_patch_transaction_reports(root)
            self.assertFalse(report["source_artifacts_mutated"])
            self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_invalid_or_missing_required_refs_fail(self) -> None:
        record = patch_transaction.build_patch_transaction(REPO_ROOT)
        record["spec"]["provenance"]["work_unit_ref"] = ""
        errors, _warnings = validation_errors(record)
        self.assertTrue(any("work_unit_ref" in item or "required reference" in item for item in errors))

        unknown = patch_transaction.build_patch_transaction(REPO_ROOT)
        unknown["spec"]["requirements"]["required_conformance_result_refs"] = [
            "aide://conformance-result/unknown-future-result",
        ]
        errors, _warnings = validation_errors(unknown)
        self.assertTrue(any("unknown required ConformanceResult" in item for item in errors))

    def test_invalid_digest_shape_fails(self) -> None:
        record = patch_transaction.build_patch_transaction(REPO_ROOT)
        record["spec"]["patch_artifact"]["sha256"] = "sha256:not-a-digest"
        errors, _warnings = validation_errors(record)
        self.assertTrue(any("patch_artifact.sha256" in item for item in errors))

    def test_patch_artifact_payload_change_changes_digest(self) -> None:
        original = patch_transaction.patch_artifact_digest(patch_transaction.sample_unified_diff_text())
        changed = patch_transaction.patch_artifact_digest(patch_transaction.sample_unified_diff_text() + "\n")
        self.assertNotEqual(original, changed)

    def test_absolute_paths_fail(self) -> None:
        report = patch_transaction.validate_scope(["src/**"], [], ["C:/repo/src/file.py"])
        self.assertFalse(report["scope_valid"])
        self.assertTrue(any("repo-relative" in item for item in report["errors"]))

        report = patch_transaction.validate_scope(["src/**"], [], ["/etc/passwd"])
        self.assertFalse(report["scope_valid"])
        self.assertTrue(any("repo-relative" in item for item in report["errors"]))

    def test_drive_prefixed_relative_paths_fail(self) -> None:
        report = patch_transaction.validate_scope(["C:repo/**"], [], ["C:repo/file.txt"])
        self.assertFalse(report["scope_valid"])
        self.assertTrue(any("drive prefix" in item for item in report["errors"]))

    def test_drive_prefixed_path_variants_fail_portably(self) -> None:
        for path in [
            "C:repo/file.txt",
            "C:repo\\file.txt",
            "C:/repo/file.txt",
            "C:\\repo\\file.txt",
            "z:relative.txt",
        ]:
            with self.subTest(path=path):
                report = patch_transaction.validate_scope(["src/**"], [], [path])
                self.assertFalse(report["scope_valid"])
                self.assertTrue(any("drive prefix" in item for item in report["errors"]))

    def test_ordinary_repo_relative_path_remains_valid(self) -> None:
        report = patch_transaction.validate_scope(["src/**"], [], ["src/module/file.py"])
        self.assertTrue(report["scope_valid"], report["errors"])

    def test_traversal_paths_fail(self) -> None:
        report = patch_transaction.validate_scope(["src/**"], [], ["src/../secret.txt"])
        self.assertFalse(report["scope_valid"])
        self.assertTrue(any("traversal" in item for item in report["errors"]))

    def test_declared_path_outside_allowed_scope_fails(self) -> None:
        report = patch_transaction.validate_scope(["src/**"], [], ["docs/readme.md"])
        self.assertFalse(report["scope_valid"])
        self.assertTrue(any("outside allowed scope" in item for item in report["errors"]))

    def test_forbidden_path_match_fails(self) -> None:
        report = patch_transaction.validate_scope(["src/**"], ["src/private/**"], ["src/private/key.txt"])
        self.assertFalse(report["scope_valid"])
        self.assertTrue(any("matches forbidden scope" in item for item in report["errors"]))

    def test_ambiguous_allowed_forbidden_overlap_fails(self) -> None:
        report = patch_transaction.validate_scope(["src/**"], ["src/**"], ["src/file.py"])
        self.assertFalse(report["scope_valid"])
        self.assertTrue(any("overlap" in item for item in report["errors"]))

    def test_duplicate_normalized_declared_paths_fail(self) -> None:
        report = patch_transaction.validate_scope(["src/**"], [], ["src//file.py", "src/file.py"])
        self.assertFalse(report["scope_valid"])
        self.assertTrue(any("duplicate normalized path" in item for item in report["errors"]))

    def test_duplicate_normalized_allowed_paths_fail(self) -> None:
        report = patch_transaction.validate_scope(["src//**", "src/**"], [], ["src/file.py"])
        self.assertFalse(report["scope_valid"])
        self.assertTrue(any("allowed_paths: duplicate normalized path" in item for item in report["errors"]))

    def test_duplicate_normalized_forbidden_paths_fail(self) -> None:
        report = patch_transaction.validate_scope(["src/**"], ["src//private/**", "src/private/**"], ["src/file.py"])
        self.assertFalse(report["scope_valid"])
        self.assertTrue(any("forbidden_paths: duplicate normalized path" in item for item in report["errors"]))

    def test_duplicate_normalized_diagnostic_names_originals_and_canonical_path(self) -> None:
        report = patch_transaction.validate_scope(["src/**"], [], ["src//file.py", "src/file.py"])
        self.assertFalse(report["scope_valid"])
        diagnostic = "\n".join(report["errors"])
        self.assertIn("src//file.py", diagnostic)
        self.assertIn("src/file.py", diagnostic)
        self.assertIn("duplicate normalized path: src/file.py", diagnostic)

    def test_duplicate_normalized_backslash_paths_fail(self) -> None:
        report = patch_transaction.validate_scope(["src/**"], [], ["src\\file.py", "src/file.py"])
        self.assertFalse(report["scope_valid"])
        self.assertTrue(any("duplicate normalized path: src/file.py" in item for item in report["errors"]))

    def test_valid_distinct_normalized_paths_remain_accepted(self) -> None:
        report = patch_transaction.validate_scope(["src/**"], [], ["src/file.py", "src/other.py"])
        self.assertTrue(report["scope_valid"], report["errors"])

    def test_apply_performed_true_fails_projection(self) -> None:
        record = patch_transaction.build_patch_transaction(REPO_ROOT)
        record["status"]["apply_performed"] = True
        errors, _warnings = validation_errors(record)
        self.assertTrue(any("apply_performed" in item for item in errors))

    def test_target_mutated_true_fails_projection(self) -> None:
        record = patch_transaction.build_patch_transaction(REPO_ROOT)
        record["status"]["target_mutated"] = True
        errors, _warnings = validation_errors(record)
        self.assertTrue(any("target_mutated" in item for item in errors))

    def test_approval_granted_without_authority_fails(self) -> None:
        record = patch_transaction.build_patch_transaction(REPO_ROOT)
        record["status"]["approval_granted"] = True
        errors, _warnings = validation_errors(record)
        self.assertTrue(any("approval_granted" in item for item in errors))

    def test_applied_lifecycle_with_apply_false_fails(self) -> None:
        record = patch_transaction.build_patch_transaction(REPO_ROOT)
        record["spec"]["lifecycle"] = "applied"
        errors, _warnings = validation_errors(record)
        self.assertTrue(any("applied lifecycle" in item or "projection lifecycle" in item for item in errors))

    def test_rolled_back_lifecycle_with_rollback_false_fails(self) -> None:
        record = patch_transaction.build_patch_transaction(REPO_ROOT)
        record["spec"]["lifecycle"] = "rolled_back"
        errors, _warnings = validation_errors(record)
        self.assertTrue(any("rolled_back lifecycle" in item or "projection lifecycle" in item for item in errors))

    def test_conformance_result_ref_does_not_set_trusted(self) -> None:
        record = patch_transaction.build_patch_transaction(REPO_ROOT)
        self.assertTrue(record["spec"]["requirements"]["required_conformance_result_refs"])
        self.assertFalse(record["status"]["trusted"])
        errors, _warnings = validation_errors(record)
        self.assertFalse(errors)

        overclaim = copy.deepcopy(record)
        overclaim["status"]["trusted"] = True
        errors, _warnings = validation_errors(overclaim)
        self.assertTrue(any("trusted" in item for item in errors))

    def test_unknown_required_capability_or_reference_kind_fails_closed(self) -> None:
        record = patch_transaction.build_patch_transaction(REPO_ROOT)
        record["spec"]["requirements"]["required_capability_refs"] = [
            "aide://future-kind/unknown-required-capability",
        ]
        errors, _warnings = validation_errors(record)
        self.assertTrue(any("unknown required ref kind" in item or "reference kind must be capability" in item for item in errors))

        unknown_capability = patch_transaction.build_patch_transaction(REPO_ROOT)
        unknown_capability["spec"]["requirements"]["required_capability_refs"] = [
            "aide://capability/unknown-required-capability",
        ]
        errors, _warnings = validation_errors(unknown_capability)
        self.assertTrue(any("unknown required capability ref" in item for item in errors))

    def test_explicit_non_capabilities_remain_in_projection_and_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_patch_transaction_files(root)
            patch_transaction.write_patch_transaction_reports(root)
            record = json.loads((root / patch_transaction.TRANSACTIONS_JSON).read_text(encoding="utf-8"))["transactions"][0]
            self.assertEqual(record["spec"]["explicit_non_capabilities"], patch_transaction.EXPLICIT_NON_CAPABILITIES)
            report = (root / patch_transaction.EXPLICIT_NON_CAPABILITIES_MD).read_text(encoding="utf-8")
            self.assertIn("patch_application", report)
            self.assertIn("target_repository_mutation", report)
            self.assertIn("provider_model_calls", report)

    def test_cli_status_project_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            copy_patch_transaction_files(root)
            parser = aide_lite.build_parser(REPO_ROOT)
            for command in ["status", "project", "validate"]:
                with self.subTest(command=command):
                    buffer = io.StringIO()
                    args = parser.parse_args(["--repo-root", str(root), "patch-transaction", command])
                    with redirect_stdout(buffer):
                        code = args.handler(args)
                    self.assertEqual(code, 0, buffer.getvalue())
                    self.assertIn("AIDE Lite patch-transaction", buffer.getvalue())


if __name__ == "__main__":
    unittest.main()
