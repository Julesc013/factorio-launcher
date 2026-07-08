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

from core.protocol import install_record, migration_record

MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_migration_record", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_migration_record"] = aide_lite
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
        "core/protocol/__init__.py",
        "core/protocol/envelope.py",
        "core/protocol/distribution_manifest.py",
        "core/protocol/project_lock.py",
        "core/protocol/ownership_ledger.py",
        "core/protocol/install_record.py",
        "core/protocol/migration_record.py",
        ".aide/release/latest-release-bundle.json",
        ".aide/reports/distribution-manifest-v1-accept/acceptance-report.json",
        ".aide/reports/project-lock-v0-accept/acceptance-report.json",
        ".aide/reports/ownership-ledger-v1-acceptance/acceptance-report.json",
        ".aide/reports/install-record-v0-acceptance/acceptance-report.json",
    ]:
        copy_file(root, rel)
    copy_tree(root, ".aide/release/dist")
    copy_tree(root, ".aide/export/aide-lite-pack-v0")


class AIDEMigrationRecordV0Tests(unittest.TestCase):
    def make_repo(self) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        copy_inputs(root)
        install_record.project(root)
        return root

    def test_schema_file_exists_and_declares_contract(self) -> None:
        schema = migration_record.load_schema(REPO_ROOT)
        self.assertEqual(schema["title"], "AIDE MigrationRecord v0")
        self.assertEqual(schema["properties"]["kind"]["const"], "MigrationRecord")
        self.assertIn("metadata", schema["required"])
        self.assertIn("spec", schema["required"])
        self.assertIn("status", schema["required"])
        spec_required = set(schema["$defs"]["spec"]["required"])
        for field in [
            "migration_kind",
            "migration_plan_ref",
            "field_mapping_summary",
            "unknown_field_disposition",
            "manual_review_items",
            "risk_class",
            "validation_refs",
            "rollback_requirements",
            "evidence_refs",
            "explicit_non_capabilities",
            "extensions",
        ]:
            self.assertIn(field, spec_required)

    def test_build_record_binds_source_install_record(self) -> None:
        root = self.make_repo()
        source = migration_record.load_install_record_source(root)
        record = migration_record.build_migration_record(root)
        self.assertEqual(record["kind"], "MigrationRecord")
        self.assertEqual(record["metadata"]["source_object_ref"], source["metadata"]["install_record_ref"])
        self.assertEqual(record["metadata"]["source_schema_version"], source["schema_version"])
        self.assertEqual(record["metadata"]["input_digest"], source["status"]["install_record_digest"])
        self.assertEqual(record["metadata"]["output_digest"], source["status"]["install_record_digest"])
        self.assertFalse(record["status"]["migration_apply_implemented"])
        self.assertFalse(record["status"]["target_repository_mutation_implemented"])

    def test_validation_rejects_required_migration_record_defects(self) -> None:
        source = install_record.minimal_fixture_record()
        source = install_record.finalize_install_record(source)
        cases = [
            ("migration_record.source_object_missing", lambda d: d["metadata"].__setitem__("source_object_ref", "")),
            ("migration_record.input_digest_missing", lambda d: d["metadata"].__setitem__("input_digest", "")),
            ("migration_record.output_digest_mismatch", lambda d: d["metadata"].__setitem__("output_digest", "sha256:" + "1" * 64)),
            ("migration_record.unknown_required_feature", lambda d: d["spec"]["required_features"].append("future.required.migration-record")),
            (
                "migration_record.destructive_without_rollback",
                lambda d: (d["spec"].__setitem__("destructive_migration", True), d["spec"].__setitem__("rollback_requirements", [])),
            ),
            ("migration_record.ambiguous_without_manual_review", lambda d: d["spec"].__setitem__("ambiguous_migration", True)),
            (
                "migration_record.source_state_contamination",
                lambda d: d["spec"]["field_mapping_summary"].append({"source_field": ".aide/context/latest-task-packet.md"}),
            ),
            ("migration_record.source_output_as_target_truth", lambda d: d["spec"].__setitem__("source_output_used_as_target_truth", True)),
            ("migration_record.apply_authority_claimed", lambda d: d["status"].__setitem__("migration_apply_implemented", True)),
            ("migration_record.extension_required_unknown", lambda d: d["spec"]["extensions"].__setitem__("requires.future", {"enabled": True})),
            ("migration_record.evidence_missing", lambda d: d["spec"].__setitem__("evidence_refs", [])),
        ]
        for expected, mutator in cases:
            with self.subTest(expected=expected):
                record = migration_record.minimal_fixture_record()
                mutator(record)
                record = migration_record.finalize_migration_record(record)
                result = migration_record.validate_migration_record_object(
                    record,
                    source_object=source,
                    require_install_record_acceptance=False,
                )
                self.assertIn(expected, result["refusal_codes"], result)

    def test_unknown_optional_features_and_extensions_are_preserved(self) -> None:
        source = install_record.minimal_fixture_record()
        source = install_record.finalize_install_record(source)
        record = migration_record.minimal_fixture_record()
        record["spec"]["optional_features"].append("future.optional.migration-record")
        record["extensions"] = {"future.optional": {"preserve": True}}
        record = migration_record.finalize_migration_record(record)
        result = migration_record.validate_migration_record_object(
            record,
            source_object=source,
            require_install_record_acceptance=False,
        )
        self.assertTrue(result["valid"], result)
        self.assertIn("unknown optional feature tolerated: future.optional.migration-record", result["warnings"])
        self.assertEqual(record["extensions"]["future.optional"]["preserve"], True)

    def test_fixture_corpus_contains_required_cases_and_validate_passes(self) -> None:
        root = self.make_repo()
        migration_record.write_fixture_corpus(root)
        required_valid = {"no-op-compatibility", "manual-review-ambiguous", "optional-extension-preserved"}
        required_invalid = set(migration_record.EXPECTED_INVALID_REFUSALS)
        valid_names = {path.stem for path in (root / migration_record.FIXTURE_ROOT / "valid").glob("*.json")}
        invalid_names = {path.stem for path in (root / migration_record.FIXTURE_ROOT / "invalid").glob("*.json")}
        self.assertTrue(required_valid.issubset(valid_names), required_valid - valid_names)
        self.assertTrue(required_invalid.issubset(invalid_names), required_invalid - invalid_names)
        validation = migration_record.validate(root)
        self.assertEqual(validation["validation_status"], "PASS_WITH_WARNINGS", validation["errors"])
        self.assertTrue(validation["checks"]["fixture_matrix_passed"])
        self.assertTrue(validation["checks"]["install_record_accepted"])
        for item in validation["fixture_results"]:
            self.assertFalse(Path(item["path"]).is_absolute(), item)
            self.assertTrue(item["path"].startswith(".aide/fixtures/migration-record-v0/"), item)

    def test_project_and_cli_status_project_validate(self) -> None:
        root = self.make_repo()
        report = migration_record.project(root)
        self.assertEqual(report["status"], "PASS_WITH_WARNINGS")
        self.assertTrue((root / ".aide/reports/migration-record-v0/migration-record.json").exists())
        parser = aide_lite.build_parser(REPO_ROOT)
        for command in [
            ["--repo-root", str(root), "migration-record", "status"],
            ["--repo-root", str(root), "migration-record", "project"],
            ["--repo-root", str(root), "migration-record", "validate"],
        ]:
            parsed = parser.parse_args(command)
            output = io.StringIO()
            with redirect_stdout(output):
                result = parsed.handler(parsed)
            self.assertEqual(result, 0, output.getvalue())
            self.assertIn("proposed_capability: migration_record_v0", output.getvalue())
            self.assertIn("migration_apply_implemented: false", output.getvalue())
            self.assertIn("target_repository_mutation_implemented: false", output.getvalue())

    def test_cli_rejects_apply_or_runtime_subcommands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        for subcommand in ["apply", "migrate", "install", "update", "mutate", "scan-target", "publish"]:
            with self.subTest(subcommand=subcommand):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    parser.parse_args(["migration-record", subcommand])


if __name__ == "__main__":
    unittest.main()
