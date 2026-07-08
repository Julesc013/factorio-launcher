from __future__ import annotations

import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.protocol import distribution_manifest, install_record, ownership_ledger, project_lock, rollback_bundle, update_plan, update_receipt

MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_update_receipt", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_update_receipt"] = aide_lite
assert SPEC.loader is not None
SPEC.loader.exec_module(aide_lite)


def copy_file(root: Path, rel: str) -> None:
    source = REPO_ROOT / rel
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(source.read_bytes())


def copy_tree(root: Path, rel: str) -> None:
    source_root = REPO_ROOT / rel
    for source in source_root.rglob("*"):
        if source.is_file():
            target = root / rel / source.relative_to(source_root)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())


def copy_inputs(root: Path) -> None:
    for rel in [
        ".aide/scripts/aide_lite.py",
        ".aide/protocol/aide-distribution-manifest-v1.schema.json",
        ".aide/protocol/aide-project-lock-v0.schema.json",
        ".aide/protocol/aide-ownership-ledger-v1.schema.json",
        ".aide/protocol/aide-install-record-v0.schema.json",
        ".aide/protocol/aide-migration-record-v0.schema.json",
        ".aide/protocol/aide-update-plan-v1.schema.json",
        ".aide/protocol/aide-rollback-bundle-v0.schema.json",
        ".aide/protocol/aide-update-receipt-v0.schema.json",
        "core/protocol/__init__.py",
        "core/protocol/envelope.py",
        "core/protocol/distribution_manifest.py",
        "core/protocol/project_lock.py",
        "core/protocol/ownership_ledger.py",
        "core/protocol/install_record.py",
        "core/protocol/migration_record.py",
        "core/protocol/update_plan.py",
        "core/protocol/rollback_bundle.py",
        "core/protocol/update_receipt.py",
        ".aide/release/latest-release-bundle.json",
        ".aide/reports/distribution-manifest-v1-accept/acceptance-report.json",
        ".aide/reports/project-lock-v0-accept/acceptance-report.json",
        ".aide/reports/ownership-ledger-v1-acceptance/acceptance-report.json",
        ".aide/reports/install-record-v0-acceptance/acceptance-report.json",
        ".aide/reports/migration-record-v0-acceptance/acceptance-report.json",
        ".aide/reports/update-plan-v1-acceptance/validation-summary.json",
        ".aide/reports/rollback-bundle-v0-acceptance/validation-summary.json",
    ]:
        copy_file(root, rel)
    copy_tree(root, ".aide/release/dist")
    copy_tree(root, ".aide/export/aide-lite-pack-v0")


class AIDEUpdateReceiptV0Tests(unittest.TestCase):
    def make_repo(self) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        copy_inputs(root)
        distribution_manifest.project(root)
        project_lock.project(root)
        ownership_ledger.project(root)
        install_record.project(root)
        update_plan.project(root)
        rollback_bundle.project(root)
        return root

    def test_schema_file_exists_and_declares_contract(self) -> None:
        schema = update_receipt.load_schema(REPO_ROOT)
        self.assertEqual(schema["title"], "AIDE UpdateReceipt v0")
        self.assertEqual(schema["properties"]["kind"]["const"], "UpdateReceipt")
        self.assertIn("metadata", schema["required"])
        self.assertIn("spec", schema["required"])
        self.assertIn("status", schema["required"])
        metadata_required = set(schema["$defs"]["metadata"]["required"])
        for field in [
            "update_receipt_ref",
            "update_plan_ref",
            "rollback_bundle_ref",
            "target_project_ref",
            "old_project_lock_ref",
            "new_project_lock_ref",
            "prior_ownership_ledger_ref",
            "new_ownership_ledger_ref",
            "source_distribution_ref",
            "candidate_distribution_ref",
            "created_at",
            "created_by",
            "extensions",
        ]:
            self.assertIn(field, metadata_required)
        spec_required = set(schema["$defs"]["spec"]["required"])
        for field in [
            "operation_receipts",
            "skipped_operations",
            "failed_operations",
            "changed_file_refs",
            "changed_section_refs",
            "preimage_digests",
            "postimage_digests",
            "artifact_refs",
            "validation_results",
            "approval_ref",
            "executor_ref",
            "execution_environment",
            "warnings",
            "limitations",
            "risk_class",
            "evidence_refs",
            "explicit_non_capabilities",
            "extensions",
        ]:
            self.assertIn(field, spec_required)

    def test_build_record_binds_update_plan_rollback_bundle_and_predecessors(self) -> None:
        root = self.make_repo()
        manifest = update_receipt.load_distribution_manifest(root)
        lock = update_receipt.load_project_lock(root)
        ledger = update_receipt.load_ownership_ledger(root)
        install_source = update_receipt.load_install_record_source(root)
        plan = update_receipt.load_update_plan_source(root)
        bundle = update_receipt.load_rollback_bundle_source(root)
        record = update_receipt.build_update_receipt(root)
        self.assertEqual(record["kind"], "UpdateReceipt")
        self.assertEqual(record["metadata"]["update_plan_ref"], plan["metadata"]["update_plan_ref"])
        self.assertEqual(record["metadata"]["rollback_bundle_ref"], bundle["metadata"]["rollback_bundle_ref"])
        self.assertEqual(record["metadata"]["source_distribution_ref"], manifest["metadata"]["distribution_ref"])
        self.assertEqual(record["metadata"]["old_project_lock_digest"], lock["status"]["project_lock_digest"])
        self.assertEqual(record["metadata"]["prior_ownership_ledger_digest"], ledger["status"]["ownership_ledger_digest"])
        self.assertIn(install_source["metadata"]["install_record_ref"], record["spec"]["prior_install_record_refs"])
        self.assertGreater(len(record["spec"]["operation_receipts"]), 0)
        self.assertFalse(record["status"]["update_apply_implemented"])
        self.assertFalse(record["status"]["target_repository_mutation_implemented"])
        self.assertFalse(record["status"]["distribution_apply_engine_started"])

    def test_validation_rejects_required_update_receipt_defects(self) -> None:
        manifest = distribution_manifest.minimal_fixture_manifest()
        lock = project_lock.minimal_fixture_lock()
        ledger = ownership_ledger.minimal_fixture_ledger()
        install_source = install_record.minimal_fixture_record()
        plan = update_plan.minimal_fixture_record()
        bundle = rollback_bundle.minimal_fixture_record()
        cases = [
            ("update_receipt.update_plan_missing", lambda d: d["metadata"].__setitem__("update_plan_ref", "")),
            ("update_receipt.rollback_bundle_missing", lambda d: d["metadata"].__setitem__("rollback_bundle_ref", "")),
            ("update_receipt.old_project_lock_missing", lambda d: d["metadata"].__setitem__("old_project_lock_ref", "")),
            ("update_receipt.new_project_lock_missing", lambda d: d["metadata"].__setitem__("new_project_lock_ref", "")),
            ("update_receipt.target_project_missing", lambda d: d["metadata"].__setitem__("target_project_ref", "")),
            ("update_receipt.operation_not_in_plan", lambda d: update_receipt._first_operation_receipt(d).__setitem__("operation_ref", "aide://update-plan/operation/not-in-plan")),
            ("update_receipt.unplanned_operation_claimed", lambda d: d["spec"]["changed_file_refs"].append({"changed_file_ref": "aide://update-receipt/artifact/unplanned", "operation_ref": "aide://update-plan/operation/unplanned", "target_relative_path": ".aide/unplanned.txt", "artifact_ref": "aide://update-receipt/artifact/unplanned", "evidence_refs": [update_receipt.DEFAULT_EVIDENCE_REF], "extensions": {}})),
            ("update_receipt.preimage_digest_mismatch", lambda d: update_receipt._first_operation_receipt(d, "managed_file_updated").__setitem__("preimage_digest", "sha256:" + "1" * 64)),
            ("update_receipt.postimage_digest_mismatch", lambda d: update_receipt._first_operation_receipt(d, "managed_file_updated").__setitem__("postimage_digest", "sha256:" + "2" * 64)),
            ("update_receipt.project_owned_changed", lambda d: update_receipt._replace_first_receipt(d, receipt_class="managed_file_updated", ownership_class="project_owned", path="README.md")),
            ("update_receipt.local_only_changed", lambda d: update_receipt._replace_first_receipt(d, receipt_class="managed_file_updated", ownership_class="local_only", path=".aide.local/config.json")),
            ("update_receipt.never_touch_changed", lambda d: update_receipt._replace_first_receipt(d, receipt_class="managed_file_updated", ownership_class="never_touch", path=".git/config")),
            ("update_receipt.unknown_ownership_changed", lambda d: update_receipt._replace_first_receipt(d, receipt_class="managed_file_updated", ownership_class="unknown", path="unknown/file.txt")),
            ("update_receipt.approval_ref_missing", lambda d: update_receipt._first_operation_receipt(d, "managed_file_updated").__setitem__("approval_ref", None)),
            ("update_receipt.validation_result_missing", lambda d: update_receipt._first_operation_receipt(d, "managed_file_updated").__setitem__("validation_result_ref", None)),
            ("update_receipt.apply_authority_claimed", lambda d: d["status"].__setitem__("update_apply_implemented", True)),
            ("update_receipt.release_readiness_claimed", lambda d: d["status"].__setitem__("release_readiness_claimed", True)),
            ("update_receipt.absolute_path_forbidden", lambda d: update_receipt._first_operation_receipt(d).__setitem__("target_relative_path", "C:/outside/file.txt")),
            ("update_receipt.path_traversal_forbidden", lambda d: update_receipt._first_operation_receipt(d).__setitem__("target_relative_path", "../outside/file.txt")),
            ("update_receipt.source_state_contamination", lambda d: d["spec"]["limitations"].append({"limitation_ref": ".aide/context/latest-task-packet.md", "limitation_class": "source_output_misuse", "evidence_refs": [update_receipt.DEFAULT_EVIDENCE_REF], "extensions": {}})),
            ("update_receipt.unknown_required_feature", lambda d: d["spec"]["required_features"].append("future.required.update-receipt")),
        ]
        for expected, mutator in cases:
            with self.subTest(expected=expected):
                record = update_receipt.minimal_fixture_record()
                mutator(record)
                record = update_receipt.finalize_update_receipt(record)
                result = update_receipt.validate_update_receipt_object(
                    record,
                    manifest=manifest,
                    lock=lock,
                    ledger=ledger,
                    install_source=install_source,
                    plan=plan,
                    bundle=bundle,
                    require_rollback_bundle_acceptance=False,
                )
                self.assertIn(expected, result["refusal_codes"], result)

    def test_unknown_optional_features_and_extensions_are_preserved(self) -> None:
        manifest = distribution_manifest.minimal_fixture_manifest()
        lock = project_lock.minimal_fixture_lock()
        ledger = ownership_ledger.minimal_fixture_ledger()
        install_source = install_record.minimal_fixture_record()
        plan = update_plan.minimal_fixture_record()
        bundle = rollback_bundle.minimal_fixture_record()
        record = update_receipt.minimal_fixture_record()
        record["spec"]["optional_features"].append("future.optional.update-receipt")
        record["extensions"] = {"future.optional": {"preserve": True}}
        record = update_receipt.finalize_update_receipt(record)
        result = update_receipt.validate_update_receipt_object(
            record,
            manifest=manifest,
            lock=lock,
            ledger=ledger,
            install_source=install_source,
            plan=plan,
            bundle=bundle,
            require_rollback_bundle_acceptance=False,
        )
        self.assertTrue(result["valid"], result)
        self.assertIn("unknown optional feature tolerated: future.optional.update-receipt", result["warnings"])
        self.assertEqual(record["extensions"]["future.optional"]["preserve"], True)

    def test_fixture_corpus_contains_required_cases_and_validate_passes(self) -> None:
        root = self.make_repo()
        update_receipt.write_fixture_corpus(root)
        required_valid = {
            "no-op-update-receipt",
            "managed-file-update-receipt",
            "managed-section-update-receipt",
            "managed-file-add-receipt",
            "managed-section-add-receipt",
            "managed-file-remove-receipt",
            "managed-section-remove-receipt",
            "project-owned-preservation-receipt",
            "local-only-preservation-receipt",
            "never-touch-preservation-receipt",
            "legacy-preservation-receipt",
            "manual-review-skipped-operation",
            "refused-operation",
            "validation-run-receipt",
            "validation-skipped-with-warning-receipt",
            "rollback-bundle-reference-receipt",
            "mixed-operation-receipt",
            "optional-extensions-preservation",
        }
        required_invalid = set(update_receipt.EXPECTED_INVALID_REFUSALS)
        valid_names = {path.stem for path in (root / update_receipt.FIXTURE_ROOT / "valid").glob("*.json")}
        invalid_names = {path.stem for path in (root / update_receipt.FIXTURE_ROOT / "invalid").glob("*.json")}
        self.assertTrue(required_valid.issubset(valid_names), required_valid - valid_names)
        self.assertTrue(required_invalid.issubset(invalid_names), required_invalid - invalid_names)
        validation = update_receipt.validate(root)
        self.assertEqual(validation["validation_status"], "PASS_WITH_WARNINGS", validation["errors"])
        self.assertTrue(validation["checks"]["fixture_matrix_passed"])
        self.assertTrue(validation["checks"]["rollback_bundle_accepted"])
        for item in validation["fixture_results"]:
            self.assertFalse(Path(item["path"]).is_absolute(), item)
            self.assertTrue(item["path"].startswith(".aide/fixtures/update-receipt-v0/"), item)

    def test_project_and_cli_status_project_validate(self) -> None:
        root = self.make_repo()
        report = update_receipt.project(root)
        self.assertEqual(report["status"], "PASS_WITH_WARNINGS")
        self.assertTrue((root / ".aide/reports/update-receipt-v0/projection.json").exists())
        parser = aide_lite.build_parser(REPO_ROOT)
        for command in [
            ["--repo-root", str(root), "update-receipt", "status"],
            ["--repo-root", str(root), "update-receipt", "project"],
            ["--repo-root", str(root), "update-receipt", "validate"],
        ]:
            parsed = parser.parse_args(command)
            output = io.StringIO()
            with redirect_stdout(output):
                result = parsed.handler(parsed)
            self.assertEqual(result, 0, output.getvalue())
            self.assertIn("proposed_capability: update_receipt_v0", output.getvalue())
            self.assertIn("receipt_authorization_claimed: false", output.getvalue())
            self.assertIn("update_apply_implemented: false", output.getvalue())
            self.assertIn("target_repository_mutation_implemented: false", output.getvalue())
            self.assertIn("distribution_apply_engine_started: false", output.getvalue())

    def test_cli_rejects_apply_or_runtime_subcommands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        for subcommand in ["apply", "update", "install", "migrate", "rollback", "uninstall", "mutate", "scan-target", "publish"]:
            with self.subTest(subcommand=subcommand):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    parser.parse_args(["update-receipt", subcommand])


if __name__ == "__main__":
    unittest.main()
