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

from core.protocol import distribution_manifest, install_record, ownership_ledger, project_lock, rollback_bundle, update_plan

MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_rollback_bundle", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_rollback_bundle"] = aide_lite
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
        "core/protocol/__init__.py",
        "core/protocol/envelope.py",
        "core/protocol/distribution_manifest.py",
        "core/protocol/project_lock.py",
        "core/protocol/ownership_ledger.py",
        "core/protocol/install_record.py",
        "core/protocol/migration_record.py",
        "core/protocol/update_plan.py",
        "core/protocol/rollback_bundle.py",
        ".aide/release/latest-release-bundle.json",
        ".aide/reports/distribution-manifest-v1-accept/acceptance-report.json",
        ".aide/reports/project-lock-v0-accept/acceptance-report.json",
        ".aide/reports/ownership-ledger-v1-acceptance/acceptance-report.json",
        ".aide/reports/install-record-v0-acceptance/acceptance-report.json",
        ".aide/reports/migration-record-v0-acceptance/acceptance-report.json",
        ".aide/reports/update-plan-v1-acceptance/validation-summary.json",
    ]:
        copy_file(root, rel)
    copy_tree(root, ".aide/release/dist")
    copy_tree(root, ".aide/export/aide-lite-pack-v0")


class AIDERollbackBundleV0Tests(unittest.TestCase):
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
        return root

    def test_schema_file_exists_and_declares_contract(self) -> None:
        schema = rollback_bundle.load_schema(REPO_ROOT)
        self.assertEqual(schema["title"], "AIDE RollbackBundle v0")
        self.assertEqual(schema["properties"]["kind"]["const"], "RollbackBundle")
        self.assertIn("metadata", schema["required"])
        self.assertIn("spec", schema["required"])
        self.assertIn("status", schema["required"])
        spec_required = set(schema["$defs"]["spec"]["required"])
        for field in [
            "prior_install_record_refs",
            "preimage_artifact_refs",
            "managed_file_preimages",
            "managed_section_preimages",
            "reverse_operations",
            "operation_rollback_map",
            "validation_plan",
            "integrity_checks",
            "manual_review_items",
            "limitations",
            "risk_class",
            "evidence_refs",
            "explicit_non_capabilities",
            "extensions",
        ]:
            self.assertIn(field, spec_required)

    def test_build_record_binds_update_plan_and_predecessors(self) -> None:
        root = self.make_repo()
        manifest = rollback_bundle.load_distribution_manifest(root)
        lock = rollback_bundle.load_project_lock(root)
        ledger = rollback_bundle.load_ownership_ledger(root)
        install_source = rollback_bundle.load_install_record_source(root)
        plan = rollback_bundle.load_update_plan_source(root)
        record = rollback_bundle.build_rollback_bundle(root)
        self.assertEqual(record["kind"], "RollbackBundle")
        self.assertEqual(record["metadata"]["update_plan_ref"], plan["metadata"]["update_plan_ref"])
        self.assertEqual(record["metadata"]["source_distribution_ref"], manifest["metadata"]["distribution_ref"])
        self.assertEqual(record["metadata"]["prior_project_lock_digest"], lock["status"]["project_lock_digest"])
        self.assertEqual(record["metadata"]["prior_ownership_ledger_digest"], ledger["status"]["ownership_ledger_digest"])
        self.assertIn(install_source["metadata"]["install_record_ref"], record["spec"]["prior_install_record_refs"])
        self.assertGreater(len(record["spec"]["reverse_operations"]), 0)
        self.assertFalse(record["status"]["rollback_apply_implemented"])
        self.assertFalse(record["status"]["target_repository_mutation_implemented"])
        self.assertFalse(record["status"]["target_scan_authority_implemented"])

    def test_validation_rejects_required_rollback_bundle_defects(self) -> None:
        manifest = distribution_manifest.minimal_fixture_manifest()
        lock = project_lock.minimal_fixture_lock()
        ledger = ownership_ledger.minimal_fixture_ledger()
        install_source = install_record.minimal_fixture_record()
        plan = update_plan.minimal_fixture_record()
        cases = [
            ("rollback_bundle.update_plan_missing", lambda d: d["metadata"].__setitem__("update_plan_ref", "")),
            ("rollback_bundle.project_lock_missing", lambda d: d["metadata"].__setitem__("prior_project_lock_ref", "")),
            ("rollback_bundle.ownership_ledger_missing", lambda d: d["metadata"].__setitem__("prior_ownership_ledger_ref", "")),
            (
                "rollback_bundle.preimage_artifact_missing",
                lambda d: (d["spec"].__setitem__("managed_file_preimages", []), d["spec"].__setitem__("managed_section_preimages", []), d["spec"].__setitem__("preimage_artifact_refs", [])),
            ),
            ("rollback_bundle.preimage_digest_mismatch", lambda d: rollback_bundle._first_preimage_reverse_operation(d).__setitem__("preimage_digest", "sha256:" + "1" * 64)),
            ("rollback_bundle.project_owned_reverse_mutation", lambda d: rollback_bundle._replace_first_reverse(d, reverse_class="restore_managed_file_preimage", ownership_class="project_owned", path="README.md")),
            ("rollback_bundle.local_only_reverse_mutation", lambda d: rollback_bundle._replace_first_reverse(d, reverse_class="restore_managed_file_preimage", ownership_class="local_only", path="local-only/settings.json")),
            ("rollback_bundle.never_touch_reverse_mutation", lambda d: rollback_bundle._replace_first_reverse(d, reverse_class="restore_managed_file_preimage", ownership_class="never_touch", path=".git/config")),
            ("rollback_bundle.unknown_ownership_reverse_operation", lambda d: rollback_bundle._replace_first_reverse(d, reverse_class="restore_managed_file_preimage", ownership_class="unknown", path="unknown/file.txt")),
            ("rollback_bundle.reverse_operation_evidence_missing", lambda d: rollback_bundle._first_reverse_operation(d).__setitem__("evidence_refs", [])),
            ("rollback_bundle.absolute_path_forbidden", lambda d: rollback_bundle._first_reverse_operation(d).__setitem__("target_relative_path", "C:/outside/file.txt")),
            ("rollback_bundle.path_traversal_forbidden", lambda d: rollback_bundle._first_reverse_operation(d).__setitem__("target_relative_path", "../outside/file.txt")),
            ("rollback_bundle.source_state_contamination", lambda d: d["spec"]["limitations"].append({"limitation_ref": ".aide/context/latest-task-packet.md", "limitation_class": "source_output_misuse", "evidence_refs": [rollback_bundle.DEFAULT_EVIDENCE_REF], "extensions": {}})),
            ("rollback_bundle.unknown_required_feature", lambda d: d["spec"]["required_features"].append("future.required.rollback-bundle")),
            ("rollback_bundle.rollback_apply_authority_claimed", lambda d: d["status"].__setitem__("rollback_apply_implemented", True)),
            ("rollback_bundle.target_mutation_claimed", lambda d: d["status"].__setitem__("target_repository_mutation_implemented", True)),
        ]
        for expected, mutator in cases:
            with self.subTest(expected=expected):
                record = rollback_bundle.minimal_fixture_record()
                mutator(record)
                record = rollback_bundle.finalize_rollback_bundle(record)
                result = rollback_bundle.validate_rollback_bundle_object(
                    record,
                    manifest=manifest,
                    lock=lock,
                    ledger=ledger,
                    install_source=install_source,
                    plan=plan,
                    require_update_plan_acceptance=False,
                )
                self.assertIn(expected, result["refusal_codes"], result)

    def test_unknown_optional_features_and_extensions_are_preserved(self) -> None:
        manifest = distribution_manifest.minimal_fixture_manifest()
        lock = project_lock.minimal_fixture_lock()
        ledger = ownership_ledger.minimal_fixture_ledger()
        install_source = install_record.minimal_fixture_record()
        plan = update_plan.minimal_fixture_record()
        record = rollback_bundle.minimal_fixture_record()
        record["spec"]["optional_features"].append("future.optional.rollback-bundle")
        record["extensions"] = {"future.optional": {"preserve": True}}
        record = rollback_bundle.finalize_rollback_bundle(record)
        result = rollback_bundle.validate_rollback_bundle_object(
            record,
            manifest=manifest,
            lock=lock,
            ledger=ledger,
            install_source=install_source,
            plan=plan,
            require_update_plan_acceptance=False,
        )
        self.assertTrue(result["valid"], result)
        self.assertIn("unknown optional feature tolerated: future.optional.rollback-bundle", result["warnings"])
        self.assertEqual(record["extensions"]["future.optional"]["preserve"], True)

    def test_fixture_corpus_contains_required_cases_and_validate_passes(self) -> None:
        root = self.make_repo()
        rollback_bundle.write_fixture_corpus(root)
        required_valid = {
            "no-op-rollback-bundle",
            "managed-file-preimage-rollback-plan",
            "managed-section-preimage-rollback-plan",
            "remove-added-managed-file-reverse-plan",
            "remove-added-managed-section-reverse-plan",
            "project-lock-restore-plan",
            "install-record-restore-plan",
            "ownership-ledger-restore-plan",
            "manual-review-limitation",
            "rollback-unavailable-limitation",
            "mixed-managed-file-and-section-plan",
            "conflict-only-rollback-bundle",
            "optional-extensions-preservation",
        }
        required_invalid = set(rollback_bundle.EXPECTED_INVALID_REFUSALS)
        valid_names = {path.stem for path in (root / rollback_bundle.FIXTURE_ROOT / "valid").glob("*.json")}
        invalid_names = {path.stem for path in (root / rollback_bundle.FIXTURE_ROOT / "invalid").glob("*.json")}
        self.assertTrue(required_valid.issubset(valid_names), required_valid - valid_names)
        self.assertTrue(required_invalid.issubset(invalid_names), required_invalid - invalid_names)
        validation = rollback_bundle.validate(root)
        self.assertEqual(validation["validation_status"], "PASS_WITH_WARNINGS", validation["errors"])
        self.assertTrue(validation["checks"]["fixture_matrix_passed"])
        self.assertTrue(validation["checks"]["update_plan_accepted"])
        for item in validation["fixture_results"]:
            self.assertFalse(Path(item["path"]).is_absolute(), item)
            self.assertTrue(item["path"].startswith(".aide/fixtures/rollback-bundle-v0/"), item)

    def test_project_and_cli_status_project_validate(self) -> None:
        root = self.make_repo()
        report = rollback_bundle.project(root)
        self.assertEqual(report["status"], "PASS_WITH_WARNINGS")
        self.assertTrue((root / ".aide/reports/rollback-bundle-v0/projection.json").exists())
        parser = aide_lite.build_parser(REPO_ROOT)
        for command in [
            ["--repo-root", str(root), "rollback-bundle", "status"],
            ["--repo-root", str(root), "rollback-bundle", "project"],
            ["--repo-root", str(root), "rollback-bundle", "validate"],
        ]:
            parsed = parser.parse_args(command)
            output = io.StringIO()
            with redirect_stdout(output):
                result = parsed.handler(parsed)
            self.assertEqual(result, 0, output.getvalue())
            self.assertIn("proposed_capability: rollback_bundle_v0", output.getvalue())
            self.assertIn("rollback_apply_implemented: false", output.getvalue())
            self.assertIn("target_repository_mutation_implemented: false", output.getvalue())
            self.assertIn("target_scan_authority_implemented: false", output.getvalue())

    def test_cli_rejects_apply_or_runtime_subcommands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        for subcommand in ["apply", "rollback", "update", "install", "uninstall", "mutate", "scan-target", "publish"]:
            with self.subTest(subcommand=subcommand):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    parser.parse_args(["rollback-bundle", subcommand])


if __name__ == "__main__":
    unittest.main()
