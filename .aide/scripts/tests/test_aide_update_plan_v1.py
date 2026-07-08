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

from core.protocol import distribution_manifest, install_record, migration_record, ownership_ledger, project_lock, update_plan

MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_update_plan", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_update_plan"] = aide_lite
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
        "core/protocol/__init__.py",
        "core/protocol/envelope.py",
        "core/protocol/distribution_manifest.py",
        "core/protocol/project_lock.py",
        "core/protocol/ownership_ledger.py",
        "core/protocol/install_record.py",
        "core/protocol/migration_record.py",
        "core/protocol/update_plan.py",
        ".aide/release/latest-release-bundle.json",
        ".aide/reports/distribution-manifest-v1-accept/acceptance-report.json",
        ".aide/reports/project-lock-v0-accept/acceptance-report.json",
        ".aide/reports/ownership-ledger-v1-acceptance/acceptance-report.json",
        ".aide/reports/install-record-v0-acceptance/acceptance-report.json",
        ".aide/reports/migration-record-v0-acceptance/acceptance-report.json",
    ]:
        copy_file(root, rel)
    copy_tree(root, ".aide/release/dist")
    copy_tree(root, ".aide/export/aide-lite-pack-v0")


class AIDEUpdatePlanV1Tests(unittest.TestCase):
    def make_repo(self) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        copy_inputs(root)
        distribution_manifest.project(root)
        project_lock.project(root)
        ownership_ledger.project(root)
        install_record.project(root)
        migration_record.project(root)
        return root

    def test_schema_file_exists_and_declares_contract(self) -> None:
        schema = update_plan.load_schema(REPO_ROOT)
        self.assertEqual(schema["title"], "AIDE UpdatePlan v1")
        self.assertEqual(schema["properties"]["kind"]["const"], "UpdatePlan")
        self.assertIn("metadata", schema["required"])
        self.assertIn("spec", schema["required"])
        self.assertIn("status", schema["required"])
        spec_required = set(schema["$defs"]["spec"]["required"])
        for field in [
            "install_record_refs",
            "migration_record_refs",
            "planned_operations",
            "preserved_paths",
            "managed_file_updates",
            "managed_section_updates",
            "conflicts",
            "manual_review_items",
            "validation_plan",
            "rollback_requirements",
            "risk_class",
            "approval_requirements",
            "evidence_refs",
            "explicit_non_capabilities",
            "extensions",
        ]:
            self.assertIn(field, spec_required)

    def test_build_record_binds_predecessor_objects(self) -> None:
        root = self.make_repo()
        manifest = update_plan.load_distribution_manifest(root)
        lock = update_plan.load_project_lock(root)
        ledger = update_plan.load_ownership_ledger(root)
        install_source = update_plan.load_install_record_source(root)
        migration_source = update_plan.load_migration_record_source(root)
        record = update_plan.build_update_plan(root)
        self.assertEqual(record["kind"], "UpdatePlan")
        self.assertEqual(record["metadata"]["candidate_distribution_ref"], manifest["metadata"]["distribution_ref"])
        self.assertEqual(record["metadata"]["current_project_lock_digest"], lock["status"]["project_lock_digest"])
        self.assertEqual(record["metadata"]["candidate_project_lock_digest"], lock["status"]["project_lock_digest"])
        self.assertEqual(record["metadata"]["ownership_ledger_digest"], ledger["status"]["ownership_ledger_digest"])
        self.assertIn(install_source["metadata"]["install_record_ref"], record["spec"]["install_record_refs"])
        self.assertIn(migration_source["metadata"]["migration_record_ref"], record["spec"]["migration_record_refs"])
        self.assertFalse(record["status"]["update_apply_implemented"])
        self.assertFalse(record["status"]["target_repository_mutation_implemented"])
        self.assertFalse(record["status"]["target_scan_authority_implemented"])

    def test_validation_rejects_required_update_plan_defects(self) -> None:
        manifest = distribution_manifest.minimal_fixture_manifest()
        lock = project_lock.minimal_fixture_lock()
        ledger = ownership_ledger.minimal_fixture_ledger()
        install_source = install_record.minimal_fixture_record()
        migration_source = migration_record.minimal_fixture_record()
        cases = [
            ("update_plan.unknown_ownership", lambda d: update_plan._replace_first_managed_operation(d, operation_class="update_managed_file", ownership_class="unknown", path="unclassified/file.txt")),
            ("update_plan.never_touch_target", lambda d: update_plan._replace_first_managed_operation(d, operation_class="update_managed_file", ownership_class="never_touch", path=".git/config")),
            ("update_plan.project_owned_overwrite", lambda d: update_plan._replace_first_managed_operation(d, operation_class="update_managed_file", ownership_class="project_owned", path="README.md")),
            ("update_plan.local_only_overwrite", lambda d: update_plan._replace_first_managed_operation(d, operation_class="update_managed_file", ownership_class="local_only", path="local-only/settings.json")),
            ("update_plan.path_traversal_forbidden", lambda d: update_plan._first_operation(d).__setitem__("target_relative_path", "../outside/file.txt")),
            ("update_plan.absolute_path_forbidden", lambda d: update_plan._first_operation(d).__setitem__("target_relative_path", "C:/outside/file.txt")),
            (
                "update_plan.case_collision",
                lambda d: d["spec"]["planned_operations"].append(
                    {**d["spec"]["planned_operations"][0], "operation_ref": "aide://update-plan/operation/case-collision", "target_relative_path": str(d["spec"]["planned_operations"][0]["target_relative_path"]).upper()}
                ),
            ),
            ("update_plan.symlink_reparse_uncertain", lambda d: update_plan._first_operation(d).__setitem__("symlink_reparse_uncertain", True)),
            (
                "update_plan.rollback_requirement_missing",
                lambda d: (
                    update_plan._replace_first_managed_operation(d, operation_class="update_managed_file", ownership_class="vendor_managed_file"),
                    next(operation for operation in d["spec"]["planned_operations"] if operation.get("operation_class") == "update_managed_file").__setitem__("rollback_requirement_ref", ""),
                ),
            ),
            ("update_plan.distribution_mismatch", lambda d: d["metadata"].__setitem__("candidate_distribution_digest", "sha256:" + "1" * 64)),
            ("update_plan.project_lock_mismatch", lambda d: d["metadata"].__setitem__("candidate_project_lock_digest", "sha256:" + "2" * 64)),
            ("update_plan.ownership_ledger_mismatch", lambda d: d["metadata"].__setitem__("ownership_ledger_digest", "sha256:" + "3" * 64)),
            ("update_plan.install_record_mismatch", lambda d: d["spec"].__setitem__("install_record_refs", ["aide://install-record/missing"])),
            ("update_plan.migration_record_mismatch", lambda d: d["spec"].__setitem__("migration_record_refs", ["aide://migration-record/missing"])),
            ("update_plan.unknown_required_feature", lambda d: d["spec"]["required_features"].append("future.required.update-plan")),
            ("update_plan.apply_authority_claimed", lambda d: d["status"].__setitem__("update_apply_implemented", True)),
            ("update_plan.target_mutation_claimed", lambda d: d["status"].__setitem__("target_repository_mutation_implemented", True)),
            ("update_plan.source_output_as_target_truth", lambda d: d["spec"].__setitem__("source_output_used_as_target_truth", True)),
            ("update_plan.evidence_missing", lambda d: d["spec"].__setitem__("evidence_refs", [])),
            ("update_plan.extension_required_unknown", lambda d: d["spec"]["extensions"].__setitem__("requires.future", {"enabled": True})),
        ]
        for expected, mutator in cases:
            with self.subTest(expected=expected):
                record = update_plan.minimal_fixture_record()
                mutator(record)
                record = update_plan.finalize_update_plan(record)
                result = update_plan.validate_update_plan_object(
                    record,
                    manifest=manifest,
                    current_lock=lock,
                    candidate_lock=lock,
                    ledger=ledger,
                    install_source=install_source,
                    migration_source=migration_source,
                    require_predecessor_acceptance=False,
                )
                self.assertIn(expected, result["refusal_codes"], result)

    def test_unknown_optional_features_and_extensions_are_preserved(self) -> None:
        manifest = distribution_manifest.minimal_fixture_manifest()
        lock = project_lock.minimal_fixture_lock()
        ledger = ownership_ledger.minimal_fixture_ledger()
        install_source = install_record.minimal_fixture_record()
        migration_source = migration_record.minimal_fixture_record()
        record = update_plan.minimal_fixture_record()
        record["spec"]["optional_features"].append("future.optional.update-plan")
        record["extensions"] = {"future.optional": {"preserve": True}}
        record = update_plan.finalize_update_plan(record)
        result = update_plan.validate_update_plan_object(
            record,
            manifest=manifest,
            current_lock=lock,
            candidate_lock=lock,
            ledger=ledger,
            install_source=install_source,
            migration_source=migration_source,
            require_predecessor_acceptance=False,
        )
        self.assertTrue(result["valid"], result)
        self.assertIn("unknown optional feature tolerated: future.optional.update-plan", result["warnings"])
        self.assertEqual(record["extensions"]["future.optional"]["preserve"], True)

    def test_fixture_corpus_contains_required_cases_and_validate_passes(self) -> None:
        root = self.make_repo()
        update_plan.write_fixture_corpus(root)
        required_valid = {
            "no-op-update",
            "managed-file-add",
            "managed-file-update",
            "managed-section-add",
            "managed-section-update",
            "project-owned-preservation",
            "local-only-preservation",
            "legacy-preservation",
            "manual-review-item",
            "migration-dependent-plan",
            "conflict-only-plan",
            "optional-extension-preserved",
        }
        required_invalid = set(update_plan.EXPECTED_INVALID_REFUSALS)
        valid_names = {path.stem for path in (root / update_plan.FIXTURE_ROOT / "valid").glob("*.json")}
        invalid_names = {path.stem for path in (root / update_plan.FIXTURE_ROOT / "invalid").glob("*.json")}
        self.assertTrue(required_valid.issubset(valid_names), required_valid - valid_names)
        self.assertTrue(required_invalid.issubset(invalid_names), required_invalid - invalid_names)
        validation = update_plan.validate(root)
        self.assertEqual(validation["validation_status"], "PASS_WITH_WARNINGS", validation["errors"])
        self.assertTrue(validation["checks"]["fixture_matrix_passed"])
        self.assertTrue(validation["checks"]["install_record_accepted"])
        self.assertTrue(validation["checks"]["migration_record_accepted"])
        for item in validation["fixture_results"]:
            self.assertFalse(Path(item["path"]).is_absolute(), item)
            self.assertTrue(item["path"].startswith(".aide/fixtures/update-plan-v1/"), item)

    def test_project_and_cli_status_project_validate(self) -> None:
        root = self.make_repo()
        report = update_plan.project(root)
        self.assertEqual(report["status"], "PASS_WITH_WARNINGS")
        self.assertTrue((root / ".aide/reports/update-plan-v1/projection.json").exists())
        parser = aide_lite.build_parser(REPO_ROOT)
        for command in [
            ["--repo-root", str(root), "update-plan", "status"],
            ["--repo-root", str(root), "update-plan", "project"],
            ["--repo-root", str(root), "update-plan", "validate"],
        ]:
            parsed = parser.parse_args(command)
            output = io.StringIO()
            with redirect_stdout(output):
                result = parsed.handler(parsed)
            self.assertEqual(result, 0, output.getvalue())
            self.assertIn("proposed_capability: update_plan_v1", output.getvalue())
            self.assertIn("update_apply_implemented: false", output.getvalue())
            self.assertIn("target_repository_mutation_implemented: false", output.getvalue())
            self.assertIn("target_scan_authority_implemented: false", output.getvalue())

    def test_cli_rejects_apply_or_runtime_subcommands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        for subcommand in ["apply", "update", "install", "rollback", "mutate", "scan-target", "publish"]:
            with self.subTest(subcommand=subcommand):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    parser.parse_args(["update-plan", subcommand])


if __name__ == "__main__":
    unittest.main()
