from __future__ import annotations

import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.protocol import distribution_manifest, project_lock

MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_project_lock", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_project_lock"] = aide_lite
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


def copy_project_lock_inputs(root: Path) -> None:
    for rel in [
        ".aide/scripts/aide_lite.py",
        ".aide/protocol/aide-distribution-manifest-v1.schema.json",
        ".aide/protocol/aide-project-lock-v0.schema.json",
        "core/protocol/__init__.py",
        "core/protocol/envelope.py",
        "core/protocol/distribution_manifest.py",
        "core/protocol/project_lock.py",
        ".aide/release/latest-release-bundle.json",
        ".aide/reports/distribution-manifest-v1-accept/acceptance-report.json",
    ]:
        copy_file(root, rel)
    copy_tree(root, ".aide/release/dist")
    copy_tree(root, ".aide/export/aide-lite-pack-v0")


class AIDEProjectLockV0Tests(unittest.TestCase):
    def make_repo(self) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        copy_project_lock_inputs(root)
        distribution_manifest.project(root)
        return root

    def test_schema_file_exists_and_parses(self) -> None:
        schema = project_lock.load_schema(REPO_ROOT)
        self.assertEqual(schema["title"], "AIDE ProjectLock v0")
        self.assertEqual(schema["properties"]["kind"]["const"], "ProjectLock")
        self.assertIn("metadata", schema["required"])
        self.assertIn("spec", schema["required"])
        self.assertIn("status", schema["required"])
        self.assertIn("extensions", schema["required"])

    def test_build_lock_binds_accepted_distribution_manifest(self) -> None:
        root = self.make_repo()
        manifest = project_lock.load_distribution_manifest(root)
        lock = project_lock.build_project_lock(root)
        self.assertEqual(lock["kind"], "ProjectLock")
        self.assertEqual(lock["metadata"]["selected_distribution_digest"], manifest["status"]["distribution_digest"])
        self.assertEqual(lock["metadata"]["manifest_payload_digest"], manifest["status"]["manifest_payload_digest"])
        self.assertTrue(project_lock.distribution_is_accepted(root, manifest))
        self.assertFalse(lock["status"]["install_apply_implemented"])
        self.assertFalse(lock["status"]["admission_implemented"])
        self.assertFalse(lock["status"]["authorization_implemented"])
        self.assertFalse(lock["status"]["target_repository_mutation_implemented"])

    def test_channel_is_informational_and_spec_digest_changes_are_authoritative(self) -> None:
        lock = project_lock.minimal_fixture_lock()
        base_digest = lock["status"]["project_lock_digest"]
        changed_channel = copy.deepcopy(lock)
        changed_channel["metadata"]["selected_channel"] = "stable"
        changed_channel = project_lock.finalize_project_lock(changed_channel)
        self.assertEqual(base_digest, changed_channel["status"]["project_lock_digest"])
        changed_digest = copy.deepcopy(lock)
        changed_digest["metadata"]["selected_distribution_digest"] = "sha256:" + "1" * 64
        changed_digest = project_lock.finalize_project_lock(changed_digest)
        self.assertNotEqual(base_digest, changed_digest["status"]["project_lock_digest"])

    def test_validation_rejects_digest_component_dependency_and_protocol_errors(self) -> None:
        manifest = distribution_manifest.minimal_fixture_manifest()
        cases = [
            ("project_lock.digest_mismatch", project_lock.manifest_digest_mismatch),
            ("project_lock.payload_digest_mismatch", project_lock.manifest_payload_digest_mismatch),
            ("project_lock.component_digest_mismatch", project_lock.component_digest_mismatch),
            ("project_lock.required_component_omitted", project_lock.missing_required_component),
            ("project_lock.component_missing", project_lock.unknown_component),
            ("project_lock.dependency_unsatisfied", project_lock.unsatisfied_dependency),
            ("project_lock.dependency_cycle", project_lock.dependency_cycle),
            ("project_lock.protocol_incompatible", project_lock.unsupported_protocol),
            ("project_lock.unknown_required_feature", project_lock.unknown_required_feature),
        ]
        for expected, mutator in cases:
            with self.subTest(expected=expected):
                lock = project_lock.minimal_fixture_lock()
                mutator(lock)
                lock = project_lock.finalize_project_lock(lock)
                result = project_lock.validate_project_lock_object(lock, distribution=manifest, require_manifest_acceptance=False)
                self.assertIn(expected, result["refusal_codes"])

    def test_optional_components_must_be_explicit(self) -> None:
        manifest = distribution_manifest.minimal_fixture_manifest()
        optional_ref = project_lock.add_optional_component(manifest)
        manifest = distribution_manifest.finalize_manifest(manifest)
        omitted = project_lock.build_lock_from_manifest(manifest)
        self.assertTrue(project_lock.validate_project_lock_object(omitted, distribution=manifest, require_manifest_acceptance=False)["valid"])
        ambiguous = copy.deepcopy(omitted)
        ambiguous["spec"]["omitted_optional_components"] = []
        ambiguous = project_lock.finalize_project_lock(ambiguous)
        result = project_lock.validate_project_lock_object(ambiguous, distribution=manifest, require_manifest_acceptance=False)
        self.assertIn("project_lock.optional_component_ambiguous", result["refusal_codes"])
        selected = copy.deepcopy(omitted)
        optional_component = next(component for component in manifest["spec"]["components"] if component["component_ref"] == optional_ref)
        selected["spec"]["selected_components"].append(project_lock.selected_component_from_manifest(optional_component, manifest))
        selected["spec"]["omitted_optional_components"] = []
        selected["spec"]["required_component_closure"] = project_lock.required_component_closure(selected["spec"]["selected_components"])
        selected = project_lock.finalize_project_lock(selected)
        self.assertTrue(project_lock.validate_project_lock_object(selected, distribution=manifest, require_manifest_acceptance=False)["valid"])

    def test_path_secret_source_state_and_extension_refusals(self) -> None:
        manifest = distribution_manifest.minimal_fixture_manifest()
        cases = [
            ("project_lock.absolute_path_forbidden", project_lock.absolute_path),
            ("project_lock.path_traversal_forbidden", project_lock.traversal_path),
            ("project_lock.secret_or_credential_forbidden", project_lock.secret_like_field),
            ("project_lock.source_state_contamination", project_lock.source_latest_reference),
            ("project_lock.source_state_contamination", project_lock.source_report_reference),
            ("project_lock.source_state_contamination", project_lock.aide_local_reference),
            ("project_lock.target_overlay_invalid", project_lock.target_overlay_invalid),
            ("project_lock.extension_required_unknown", project_lock.extension_required_unknown),
        ]
        for expected, mutator in cases:
            with self.subTest(expected=expected):
                lock = project_lock.minimal_fixture_lock()
                mutator(lock)
                lock = project_lock.finalize_project_lock(lock)
                result = project_lock.validate_project_lock_object(lock, distribution=manifest, require_manifest_acceptance=False)
                self.assertIn(expected, result["refusal_codes"])

    def test_unknown_optional_extensions_and_features_are_preserved(self) -> None:
        lock = project_lock.minimal_fixture_lock()
        lock["metadata"]["extensions"] = {"operator.note": {"value": "preserve"}}
        lock["spec"]["optional_features"].append("future.optional.project-lock")
        lock["spec"]["extensions"] = {"future.optional": {"enabled": True}}
        lock = project_lock.finalize_project_lock(lock)
        result = project_lock.validate_project_lock_object(lock, distribution=distribution_manifest.minimal_fixture_manifest(), require_manifest_acceptance=False)
        self.assertTrue(result["valid"], result)
        self.assertIn("unknown optional feature tolerated: future.optional.project-lock", result["warnings"])
        self.assertEqual(lock["metadata"]["extensions"]["operator.note"]["value"], "preserve")

    def test_fixture_corpus_contains_required_cases_and_validate_passes(self) -> None:
        root = self.make_repo()
        project_lock.write_fixture_corpus(root)
        required_valid = {
            "minimal-valid-lock",
            "full-valid-lock",
            "reordered-deterministic-lock",
            "optional-component-selected",
            "optional-component-omitted",
            "unknown-optional-feature-preserved",
            "extension-round-trip",
            "channel-changed-digest-unchanged",
        }
        required_invalid = {
            "manifest-digest-mismatch",
            "manifest-payload-digest-mismatch",
            "manifest-not-accepted",
            "component-digest-mismatch",
            "missing-required-component",
            "optional-component-ambiguous",
            "unknown-component",
            "unsatisfied-dependency",
            "dependency-cycle",
            "unsupported-protocol",
            "unknown-required-feature",
            "channel-changed-unapproved-digest",
            "target-overlay-invalid",
            "secret-like-field",
            "absolute-path",
            "traversal-path",
            "source-latest-reference",
            "source-report-reference",
            "aide-local-reference",
            "extension-required-unknown",
        }
        valid_names = {path.stem for path in (root / project_lock.FIXTURE_ROOT / "valid").glob("*.json")}
        invalid_names = {path.stem for path in (root / project_lock.FIXTURE_ROOT / "invalid").glob("*.json")}
        self.assertTrue(required_valid.issubset(valid_names), required_valid - valid_names)
        self.assertTrue(required_invalid.issubset(invalid_names), required_invalid - invalid_names)
        validation = project_lock.validate(root)
        self.assertEqual(validation["validation_status"], "PASS_WITH_WARNINGS", validation["errors"])
        self.assertTrue(validation["checks"]["fixture_matrix_passed"])

    def test_project_and_cli_status_project_validate(self) -> None:
        root = self.make_repo()
        report = project_lock.project(root)
        self.assertEqual(report["status"], "PASS_WITH_WARNINGS")
        self.assertTrue((root / ".aide/reports/project-lock-v0/project-lock.json").exists())
        parser = aide_lite.build_parser(REPO_ROOT)
        for command in [
            ["--repo-root", str(root), "project-lock", "status"],
            ["--repo-root", str(root), "project-lock", "project"],
            ["--repo-root", str(root), "project-lock", "validate"],
        ]:
            parsed = parser.parse_args(command)
            output = io.StringIO()
            with redirect_stdout(output):
                result = parsed.handler(parsed)
            self.assertEqual(result, 0, output.getvalue())
            self.assertIn("proposed_capability: project_lock_v0", output.getvalue())
            self.assertIn("install_apply_implemented: false", output.getvalue())
            self.assertIn("admission_implemented: false", output.getvalue())
            self.assertIn("authorization_implemented: false", output.getvalue())
            self.assertIn("target_repository_mutation_implemented: false", output.getvalue())

    def test_cli_rejects_apply_or_runtime_subcommands(self) -> None:
        parser = aide_lite.build_parser(REPO_ROOT)
        for subcommand in ["apply", "install", "update", "admit", "authorize", "mutate", "publish"]:
            with self.subTest(subcommand=subcommand):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    parser.parse_args(["project-lock", subcommand])


if __name__ == "__main__":
    unittest.main()
