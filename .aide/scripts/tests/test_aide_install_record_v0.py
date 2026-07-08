from __future__ import annotations

import copy
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

from core.protocol import distribution_manifest, install_record, ownership_ledger, project_lock

MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_install_record", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_install_record"] = aide_lite
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
        "core/protocol/__init__.py",
        "core/protocol/envelope.py",
        "core/protocol/distribution_manifest.py",
        "core/protocol/project_lock.py",
        "core/protocol/ownership_ledger.py",
        "core/protocol/install_record.py",
        ".aide/release/latest-release-bundle.json",
        ".aide/reports/distribution-manifest-v1-accept/acceptance-report.json",
        ".aide/reports/project-lock-v0-accept/acceptance-report.json",
        ".aide/reports/ownership-ledger-v1-acceptance/acceptance-report.json",
    ]:
        copy_file(root, rel)
    copy_tree(root, ".aide/release/dist")
    copy_tree(root, ".aide/export/aide-lite-pack-v0")


class AIDEInstallRecordV0Tests(unittest.TestCase):
    def make_repo(self) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        copy_inputs(root)
        distribution_manifest.project(root)
        project_lock.project(root)
        ownership_ledger.project(root)
        return root

    def test_schema_file_exists_and_declares_contract(self) -> None:
        schema = install_record.load_schema(REPO_ROOT)
        self.assertEqual(schema["title"], "AIDE InstallRecord v0")
        self.assertEqual(schema["properties"]["kind"]["const"], "InstallRecord")
        self.assertIn("metadata", schema["required"])
        self.assertIn("spec", schema["required"])
        self.assertIn("status", schema["required"])
        spec_required = set(schema["$defs"]["spec"]["required"])
        for field in [
            "install_mode",
            "install_source",
            "observed_existing_state",
            "installed_component_refs",
            "installed_file_entry_refs",
            "installed_managed_section_refs",
            "validation_refs",
            "evidence_refs",
            "explicit_non_capabilities",
            "extensions",
        ]:
            self.assertIn(field, spec_required)

    def test_build_record_binds_distribution_lock_and_ownership_ledger(self) -> None:
        root = self.make_repo()
        manifest = install_record.load_distribution_manifest(root)
        lock = install_record.load_project_lock(root)
        ledger = install_record.load_ownership_ledger(root)
        record = install_record.build_install_record(root)
        self.assertEqual(record["kind"], "InstallRecord")
        self.assertEqual(record["metadata"]["source_distribution_ref"], manifest["metadata"]["distribution_ref"])
        self.assertEqual(record["metadata"]["project_lock_digest"], lock["status"]["project_lock_digest"])
        self.assertEqual(record["metadata"]["ownership_ledger_digest"], ledger["status"]["ownership_ledger_digest"])
        self.assertEqual(set(record["spec"]["installed_component_refs"]), set(install_record.component_refs(lock)))
        self.assertTrue(set(record["spec"]["installed_file_entry_refs"]).issubset(set(install_record.ledger_file_entry_refs(ledger))))
        self.assertTrue(set(record["spec"]["installed_managed_section_refs"]).issubset(set(install_record.ledger_managed_section_refs(ledger))))
        self.assertFalse(record["status"]["install_apply_implemented"])
        self.assertFalse(record["status"]["target_repository_mutation_implemented"])
        self.assertFalse(record["status"]["target_scan_authority_implemented"])

    def test_validation_rejects_required_install_record_defects(self) -> None:
        manifest = distribution_manifest.minimal_fixture_manifest()
        lock = project_lock.minimal_fixture_lock()
        ledger = ownership_ledger.minimal_fixture_ledger()
        cases = [
            ("install_record.distribution_missing", lambda d: d["metadata"].__setitem__("source_distribution_ref", "")),
            ("install_record.project_lock_missing", lambda d: d["metadata"].__setitem__("project_lock_ref", "")),
            ("install_record.ownership_ledger_missing", lambda d: d["metadata"].__setitem__("ownership_ledger_ref", "")),
            ("install_record.distribution_mismatch", lambda d: d["metadata"].__setitem__("source_distribution_digest", "sha256:" + "1" * 64)),
            ("install_record.project_lock_mismatch", lambda d: d["metadata"].__setitem__("project_lock_digest", "sha256:" + "2" * 64)),
            ("install_record.ownership_ledger_mismatch", lambda d: d["metadata"].__setitem__("ownership_ledger_digest", "sha256:" + "3" * 64)),
            ("install_record.component_ref_unknown", lambda d: d["spec"]["installed_component_refs"].append("aide://distribution/component/missing")),
            ("install_record.ownership_entry_ref_unknown", lambda d: d["spec"]["installed_file_entry_refs"].append("aide://ownership-entry/missing")),
            ("install_record.managed_section_ref_unknown", lambda d: d["spec"]["installed_managed_section_refs"].append("aide://ownership-entry/missing-section")),
            ("install_record.apply_authority_claimed", lambda d: d["status"].__setitem__("install_apply_implemented", True)),
            ("install_record.target_mutation_claimed", lambda d: d["status"].__setitem__("target_repository_mutation_implemented", True)),
            ("install_record.unknown_required_feature", lambda d: d["spec"]["required_features"].append("future.required.install-record")),
            ("install_record.absolute_path_forbidden", lambda d: d["spec"]["observed_existing_state"]["observed_paths"].append("C:/outside/file.txt")),
            ("install_record.path_traversal_forbidden", lambda d: d["spec"]["observed_existing_state"]["observed_paths"].append("../outside/file.txt")),
            ("install_record.source_state_contamination", lambda d: d["spec"]["observed_existing_state"]["observed_paths"].append(".aide/context/latest-task-packet.md")),
            ("install_record.source_output_as_target_truth", lambda d: d["spec"]["observed_existing_state"].__setitem__("source_output_used_as_target_truth", True)),
            ("install_record.evidence_missing", lambda d: d["spec"].__setitem__("evidence_refs", [])),
            ("install_record.extension_required_unknown", lambda d: d["spec"]["extensions"].__setitem__("requires.future", {"enabled": True})),
        ]
        for expected, mutator in cases:
            with self.subTest(expected=expected):
                record = install_record.minimal_fixture_record()
                mutator(record)
                record = install_record.finalize_install_record(record)
                result = install_record.validate_install_record_object(
                    record,
                    distribution=manifest,
                    lock=lock,
                    ledger=ledger,
                    require_ownership_acceptance=False,
                )
                self.assertIn(expected, result["refusal_codes"], result)

    def test_unknown_optional_features_and_extensions_are_preserved(self) -> None:
        record = install_record.minimal_fixture_record()
        record["spec"]["optional_features"].append("future.optional.install-record")
        record["extensions"] = {"future.optional": {"preserve": True}}
        record = install_record.finalize_install_record(record)
        result = install_record.validate_install_record_object(
            record,
            distribution=distribution_manifest.minimal_fixture_manifest(),
            lock=project_lock.minimal_fixture_lock(),
            ledger=ownership_ledger.minimal_fixture_ledger(),
            require_ownership_acceptance=False,
        )
        self.assertTrue(result["valid"], result)
        self.assertIn("unknown optional feature tolerated: future.optional.install-record", result["warnings"])
        self.assertEqual(record["extensions"]["future.optional"]["preserve"], True)

    def test_fixture_corpus_contains_required_cases_and_validate_passes(self) -> None:
        root = self.make_repo()
        install_record.write_fixture_corpus(root)
        required_valid = {
            "fresh-observed-install",
            "existing-observed-install",
            "managed-file-observation",
            "managed-section-observation",
            "warning-only-partial-observation",
            "optional-extension-preserved",
        }
        required_invalid = set(install_record.EXPECTED_INVALID_REFUSALS)
        valid_names = {path.stem for path in (root / install_record.FIXTURE_ROOT / "valid").glob("*.json")}
        invalid_names = {path.stem for path in (root / install_record.FIXTURE_ROOT / "invalid").glob("*.json")}
        self.assertTrue(required_valid.issubset(valid_names), required_valid - valid_names)
        self.assertTrue(required_invalid.issubset(invalid_names), required_invalid - invalid_names)
        validation = install_record.validate(root)
        self.assertEqual(validation["validation_status"], "PASS_WITH_WARNINGS", validation["errors"])
        self.assertTrue(validation["checks"]["fixture_matrix_passed"])
        self.assertTrue(validation["checks"]["ownership_ledger_accepted"])

    def test_project_and_cli_status_project_validate(self) -> None:
        root = self.make_repo()
        report = install_record.project(root)
        self.assertEqual(report["status"], "PASS_WITH_WARNINGS")
        self.assertTrue((root / ".aide/reports/install-record-v0/install-record.json").exists())
        parser = aide_lite.build_parser(REPO_ROOT)
        for command in [
            ["--repo-root", str(root), "install-record", "status"],
            ["--repo-root", str(root), "install-record", "project"],
            ["--repo-root", str(root), "install-record", "validate"],
        ]:
            parsed = parser.parse_args(command)
            output = io.StringIO()
            with redirect_stdout(output):
                result = parsed.handler(parsed)
            self.assertEqual(result, 0, output.getvalue())
            self.assertIn("proposed_capability: install_record_v0", output.getvalue())
            self.assertIn("install_apply_implemented: false", output.getvalue())
            self.assertIn("target_repository_mutation_implemented: false", output.getvalue())
            self.assertIn("target_scan_authority_implemented: false", output.getvalue())

    def test_cli_rejects_apply_or_runtime_subcommands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        for subcommand in ["apply", "install", "update", "mutate", "scan-target", "publish"]:
            with self.subTest(subcommand=subcommand):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    parser.parse_args(["install-record", subcommand])


if __name__ == "__main__":
    unittest.main()
