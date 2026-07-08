from __future__ import annotations

import copy
import importlib.util
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.protocol import distribution_manifest

MODULE_PATH = REPO_ROOT / ".aide/scripts/aide_lite.py"
SPEC = importlib.util.spec_from_file_location("aide_lite_distribution_manifest", MODULE_PATH)
aide_lite = importlib.util.module_from_spec(SPEC)
sys.modules["aide_lite_distribution_manifest"] = aide_lite
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


def copy_distribution_inputs(root: Path) -> None:
    for rel in [
        ".aide/scripts/aide_lite.py",
        ".aide/protocol/aide-distribution-manifest-v1.schema.json",
        "core/protocol/__init__.py",
        "core/protocol/envelope.py",
        "core/protocol/distribution_manifest.py",
        ".aide/release/latest-release-bundle.json",
    ]:
        copy_file(root, rel)
    copy_tree(root, ".aide/release/dist")
    copy_tree(root, ".aide/export/aide-lite-pack-v0")


class AIDEDistributionManifestV1Tests(unittest.TestCase):
    def make_repo(self) -> Path:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        copy_distribution_inputs(root)
        return root

    def test_schema_file_exists_and_parses(self) -> None:
        schema = distribution_manifest.load_schema(REPO_ROOT)
        self.assertEqual(schema["title"], "AIDE DistributionManifest v1")
        self.assertEqual(schema["properties"]["kind"]["const"], "DistributionManifest")
        self.assertIn("metadata", schema["required"])
        self.assertIn("spec", schema["required"])
        self.assertIn("status", schema["required"])

    def test_build_manifest_maps_q47_without_absolute_paths(self) -> None:
        manifest = distribution_manifest.build_distribution_manifest(REPO_ROOT)
        self.assertEqual(manifest["kind"], "DistributionManifest")
        self.assertEqual(manifest["status"]["proposed_capability"], "distribution_manifest_v1")
        self.assertGreaterEqual(len(manifest["spec"]["artifacts"]), 3)
        self.assertFalse(distribution_manifest.contains_absolute_local_path(manifest))
        self.assertFalse(manifest["spec"]["source"]["q48_publication_draft_is_distribution_truth"])
        self.assertTrue(manifest["spec"]["provenance"]["source_repo_local_path_suppressed"])
        self.assertFalse(manifest["status"]["install_apply_implemented"])
        self.assertFalse(manifest["status"]["release_publication_implemented"])

    def test_validation_rejects_duplicate_component_and_artifact(self) -> None:
        manifest = distribution_manifest.minimal_fixture_manifest()
        duplicate_component = copy.deepcopy(manifest)
        distribution_manifest.duplicate_first_component(duplicate_component)
        duplicate_component = distribution_manifest.finalize_manifest(duplicate_component)
        result = distribution_manifest.validate_distribution_manifest_object(duplicate_component)
        self.assertIn("distribution.duplicate_component", result["refusal_codes"])
        duplicate_artifact = copy.deepcopy(manifest)
        distribution_manifest.duplicate_first_artifact(duplicate_artifact)
        duplicate_artifact = distribution_manifest.finalize_manifest(duplicate_artifact)
        result = distribution_manifest.validate_distribution_manifest_object(duplicate_artifact)
        self.assertIn("distribution.duplicate_artifact", result["refusal_codes"])

    def test_validation_rejects_feature_protocol_source_and_path_boundaries(self) -> None:
        cases = [
            ("distribution.unknown_required_feature", distribution_manifest.add_unknown_required_feature),
            ("distribution.unsupported_protocol_range", distribution_manifest.unsupported_protocol),
            ("distribution.unsupported_source_kind", distribution_manifest.unsupported_source_kind),
            ("distribution.forbidden_member", lambda m: distribution_manifest.set_artifact_path(m, ".aide.local/state.sqlite")),
            ("distribution.forbidden_member", lambda m: distribution_manifest.set_artifact_path(m, "C:/tmp/aide.zip")),
            ("distribution.forbidden_member", lambda m: distribution_manifest.set_artifact_path(m, "../outside.zip")),
        ]
        for expected, mutator in cases:
            with self.subTest(expected=expected):
                manifest = distribution_manifest.minimal_fixture_manifest()
                mutator(manifest)
                manifest = distribution_manifest.finalize_manifest(manifest)
                result = distribution_manifest.validate_distribution_manifest_object(manifest)
                self.assertIn(expected, result["refusal_codes"])

    def test_validation_rejects_digest_signature_sbom_and_migration_claims(self) -> None:
        cases = [
            ("distribution.artifact_digest_mismatch", distribution_manifest.wrong_artifact_digest, True),
            ("distribution.manifest_digest_mismatch", distribution_manifest.wrong_manifest_digest, False),
            ("distribution.signature_unverified", distribution_manifest.false_verified_signature, True),
            ("distribution.sbom_unavailable", distribution_manifest.sbom_generated_claim, True),
            ("distribution.incompatible_migration", distribution_manifest.add_incompatible_migration, True),
            ("distribution.missing_checksum", distribution_manifest.missing_checksum, True),
        ]
        for expected, mutator, should_finalize in cases:
            with self.subTest(expected=expected):
                manifest = distribution_manifest.minimal_fixture_manifest()
                mutator(manifest)
                if should_finalize:
                    manifest = distribution_manifest.finalize_manifest(manifest)
                result = distribution_manifest.validate_distribution_manifest_object(manifest)
                self.assertIn(expected, result["refusal_codes"])

    def test_reordered_input_keeps_distribution_digest(self) -> None:
        manifest = distribution_manifest.build_distribution_manifest(REPO_ROOT)
        reordered = distribution_manifest.reordered_manifest(manifest)
        self.assertEqual(manifest["status"]["distribution_digest"], reordered["status"]["distribution_digest"])

    def test_status_fields_do_not_affect_distribution_identity(self) -> None:
        manifest = distribution_manifest.minimal_fixture_manifest()
        base_payload = manifest["status"]["manifest_payload_digest"]
        base_distribution = manifest["status"]["distribution_digest"]
        status_mutations = [
            ("recommended_next_task", "AIDE-SOME-FUTURE-TASK"),
            ("status", "PASS"),
            ("proposed_capability", "distribution_manifest_v1_proposed_alias"),
            ("install_apply_implemented", False),
        ]
        for field, value in status_mutations:
            with self.subTest(field=field):
                mutated = copy.deepcopy(manifest)
                mutated["status"][field] = value
                mutated = distribution_manifest.finalize_manifest(mutated)
                self.assertEqual(base_payload, mutated["status"]["manifest_payload_digest"])
                self.assertEqual(base_distribution, mutated["status"]["distribution_digest"])

    def test_spec_and_metadata_fields_affect_distribution_identity(self) -> None:
        manifest = distribution_manifest.minimal_fixture_manifest()
        base_distribution = manifest["status"]["distribution_digest"]
        mutations = [
            lambda m: m["metadata"].__setitem__("release_id", "fixture-minimal-2"),
            lambda m: m["spec"]["artifacts"][0].__setitem__("content_digest", "sha256:" + "1" * 64),
            lambda m: m["spec"]["components"][0].__setitem__("content_digest", "sha256:" + "2" * 64),
        ]
        for mutator in mutations:
            mutated = copy.deepcopy(manifest)
            mutator(mutated)
            mutated = distribution_manifest.finalize_manifest(mutated)
            self.assertNotEqual(base_distribution, mutated["status"]["distribution_digest"])

    def test_optional_extensions_survive_round_trip(self) -> None:
        manifest = distribution_manifest.minimal_fixture_manifest()
        manifest["metadata"]["extensions"] = {"operator.note": {"value": "preserve"}}
        manifest["spec"]["protocol"]["extensions"] = {"future.optional": {"enabled": True}}
        manifest["spec"]["components"][0]["extensions"] = {"component.optional": 7}
        manifest = distribution_manifest.finalize_manifest(manifest)
        result = distribution_manifest.validate_distribution_manifest_object(manifest)
        self.assertTrue(result["valid"], result)
        self.assertEqual(manifest["metadata"]["extensions"]["operator.note"]["value"], "preserve")
        self.assertEqual(manifest["spec"]["protocol"]["extensions"]["future.optional"]["enabled"], True)

    def test_component_graph_integrity_is_validated(self) -> None:
        cases = [
            ("distribution.component_digest_mismatch", distribution_manifest.wrong_component_digest),
            ("distribution.missing_artifact_ref", distribution_manifest.missing_artifact_ref),
            ("distribution.excluded_artifact_ref", distribution_manifest.excluded_artifact_ref),
            ("distribution.missing_component_dependency", distribution_manifest.missing_component_dependency),
            ("distribution.duplicate_component_id", distribution_manifest.duplicate_component_id),
            ("distribution.component_dependency_cycle", distribution_manifest.component_dependency_cycle),
        ]
        for expected, mutator in cases:
            with self.subTest(expected=expected):
                manifest = distribution_manifest.minimal_fixture_manifest()
                mutator(manifest)
                manifest = distribution_manifest.finalize_manifest(manifest)
                result = distribution_manifest.validate_distribution_manifest_object(manifest)
                self.assertIn(expected, result["refusal_codes"])

    def test_artifact_metadata_integrity_is_validated_against_files(self) -> None:
        root = self.make_repo()
        manifest = distribution_manifest.build_distribution_manifest(root)
        mutations = [
            ("distribution.artifact_byte_count_mismatch", lambda a: a.__setitem__("byte_count", int(a["byte_count"]) + 1)),
            ("distribution.artifact_media_type_mismatch", lambda a: a.__setitem__("media_type", "application/x-wrong")),
            ("distribution.artifact_compression_mismatch", lambda a: a.__setitem__("compression_format", "wrong")),
        ]
        for expected, mutator in mutations:
            with self.subTest(expected=expected):
                case = copy.deepcopy(manifest)
                artifact = next(item for item in case["spec"]["artifacts"] if item["source_kind"] != "local_directory")
                mutator(artifact)
                case = distribution_manifest.finalize_manifest(case)
                result = distribution_manifest.validate_distribution_manifest_object(case, repo_root=root, require_artifact_files=True)
                self.assertIn(expected, result["refusal_codes"])

    def test_release_artifact_path_is_validated_before_filesystem_access(self) -> None:
        record = {
            "asset_id": "outside.zip",
            "included": True,
            "kind": "zip_archive",
            "path": "C:/outside/outside.zip",
            "sha256": "0" * 64,
            "size_bytes": 1,
        }
        with mock.patch("pathlib.Path.exists", side_effect=AssertionError("exists called before path validation")):
            artifact = distribution_manifest._artifact_from_release_record(Path("C:/repo"), record)
        self.assertEqual(artifact["relative_source_location"], "C:/outside/outside.zip")
        self.assertFalse(artifact["extensions"]["path_validation"]["valid"])

    def test_checksum_values_and_basename_collisions_are_validated(self) -> None:
        root = self.make_repo()
        manifest = distribution_manifest.build_distribution_manifest(root)
        checksum_path = root / distribution_manifest.RELEASE_CHECKSUMS_JSON
        checksums = distribution_manifest.read_json(checksum_path)
        checksums["checksums"]["aide-lite-pack-v0.zip"] = "0" * 64
        distribution_manifest.write_json(checksum_path, checksums)
        result = distribution_manifest.validate_distribution_manifest_object(manifest, repo_root=root, require_artifact_files=True)
        self.assertIn("distribution.checksum_digest_mismatch", result["refusal_codes"])

        collision = distribution_manifest.minimal_fixture_manifest()
        second = copy.deepcopy(collision["spec"]["artifacts"][0])
        second["artifact_ref"] = distribution_manifest.artifact_ref("nested-minimal")
        second["relative_source_location"] = "nested/minimal.json"
        collision["spec"]["artifacts"].append(second)
        collision["spec"]["components"][0]["artifact_refs"].append(second["artifact_ref"])
        collision = distribution_manifest.finalize_manifest(collision)
        result = distribution_manifest.validate_distribution_manifest_object(collision)
        self.assertIn("distribution.checksum_basename_collision", result["refusal_codes"])

    def test_protocol_range_semantics_are_enforced(self) -> None:
        cases = [
            ("distribution.unsupported_protocol_range", lambda m: m["spec"]["protocol"]["protocol_range"].__setitem__("min", "2.0.0")),
            ("distribution.unsupported_protocol_range", lambda m: m["spec"]["protocol"]["protocol_range"].__setitem__("max", "0.x")),
            ("distribution.unsupported_protocol_range", lambda m: m["spec"]["protocol"]["protocol_range"].__setitem__("max", "2.x")),
            ("distribution.unsupported_protocol_range", lambda m: m["spec"]["protocol"]["protocol_range"].__setitem__("max", "2.0.0")),
            ("distribution.unsupported_protocol_range", lambda m: m["spec"]["protocol"]["protocol_range"].pop("min", None)),
            ("distribution.unsupported_protocol_range", lambda m: m["spec"]["protocol"].pop("min_reader_version", None)),
            ("distribution.unsupported_protocol_range", lambda m: m["spec"]["protocol"].pop("min_writer_version", None)),
            ("distribution.unsupported_protocol_range", lambda m: m["spec"]["components"][0]["compatibility_constraints"].__setitem__("min_reader_version", "2.0.0")),
            ("distribution.unsupported_protocol_range", lambda m: m["spec"]["components"][0]["compatibility_constraints"].__setitem__("max_reader_version", "2.x")),
        ]
        for expected, mutator in cases:
            with self.subTest(expected=expected):
                manifest = distribution_manifest.minimal_fixture_manifest()
                mutator(manifest)
                manifest = distribution_manifest.finalize_manifest(manifest)
                result = distribution_manifest.validate_distribution_manifest_object(manifest)
                self.assertIn(expected, result["refusal_codes"])

        valid = distribution_manifest.minimal_fixture_manifest()
        valid["spec"]["protocol"]["protocol_range"] = {"min": "1.0.0", "max": "1.x"}
        valid = distribution_manifest.finalize_manifest(valid)
        self.assertTrue(distribution_manifest.validate_distribution_manifest_object(valid)["valid"])

    def test_files_packaging_prefix_classifies_target_root_members(self) -> None:
        forbidden_cases = {
            "files/.aide.local/state.sqlite": ("forbidden_prefix:.aide.local/", ".aide.local/state.sqlite"),
            "files/.env": ("forbidden_exact_member", ".env"),
            "files/raw-prompt.txt": ("forbidden_exact_member", "raw-prompt.txt"),
            "files/raw-response.txt": ("forbidden_exact_member", "raw-response.txt"),
            "files/.aide/context/latest-task-packet.md": ("forbidden_prefix:.aide/context/latest-", ".aide/context/latest-task-packet.md"),
            "files/.aide/reports/distribution-manifest-v1/manifest.json": ("forbidden_prefix:.aide/reports/", ".aide/reports/distribution-manifest-v1/manifest.json"),
            "files/.aide/repo/latest-inventory.json": ("forbidden_prefix:.aide/repo/latest-", ".aide/repo/latest-inventory.json"),
            "files/.aide/roots/latest-classification.json": ("forbidden_prefix:.aide/roots/latest-", ".aide/roots/latest-classification.json"),
            "files/.aide/tools/latest-tools.json": ("forbidden_prefix:.aide/tools/latest-", ".aide/tools/latest-tools.json"),
            "files/.aide/install/latest-plan.json": ("forbidden_prefix:.aide/install/latest-", ".aide/install/latest-plan.json"),
            "files/.aide/repair/latest-plan.json": ("forbidden_prefix:.aide/repair/latest-", ".aide/repair/latest-plan.json"),
            "files/.aide/upgrade/latest-plan.json": ("forbidden_prefix:.aide/upgrade/latest-", ".aide/upgrade/latest-plan.json"),
            "files/.aide/rollback/latest-plan.json": ("forbidden_prefix:.aide/rollback/latest-", ".aide/rollback/latest-plan.json"),
            "files/.aide/uninstall/latest-plan.json": ("forbidden_prefix:.aide/uninstall/latest-", ".aide/uninstall/latest-plan.json"),
            "files/logs/run.log": ("forbidden_prefix:logs/", "logs/run.log"),
            "files/.cache/cache.bin": ("forbidden_prefix:.cache/", ".cache/cache.bin"),
            "files/secrets/token.txt": ("forbidden_prefix:secrets/", "secrets/token.txt"),
        }
        for member, (reason, target_member) in forbidden_cases.items():
            with self.subTest(member=member):
                classification = distribution_manifest.forbidden_member_classification(member)
                self.assertIsNotNone(classification)
                assert classification is not None
                self.assertEqual(classification["reason"], reason)
                self.assertEqual(classification["target_member"], target_member)
                self.assertEqual(classification["packaging_prefix"], "files")

        self.assertIsNone(distribution_manifest.forbidden_member_classification("files/src/main.py"))
        self.assertIsNone(distribution_manifest.forbidden_member_classification("files/docs/reference.md"))
        payload = distribution_manifest.forbidden_member_classification("payload/.env")
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["packaging_prefix"], "")
        self.assertEqual(payload["target_member"], "payload/.env")

    def test_forbidden_directory_member_records_contamination(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        members = {
            "files/.aide.local/state.sqlite": "state",
            "files/.env": "TOKEN=fixture",
            "files/.aide/reports/report.json": "{}",
            "files/.aide/context/latest-context-packet.md": "context",
            "files/src/allowed.py": "print('ok')\n",
        }
        for rel, text in members.items():
            target = root / distribution_manifest.EXPORT_PACK_ROOT / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        inventory = distribution_manifest.directory_inventory_report(root / distribution_manifest.EXPORT_PACK_ROOT)
        forbidden_paths = {item["path"] for item in inventory["forbidden_members"]}
        allowed_paths = {item["path"] for item in inventory["allowed_members"]}
        self.assertIn("files/.aide.local/state.sqlite", forbidden_paths)
        self.assertIn("files/.env", forbidden_paths)
        self.assertIn("files/.aide/reports/report.json", forbidden_paths)
        self.assertIn("files/.aide/context/latest-context-packet.md", forbidden_paths)
        self.assertIn("files/src/allowed.py", allowed_paths)
        self.assertTrue(inventory["source_state_contamination_detected"])
        artifact = distribution_manifest._directory_artifact(root)
        self.assertGreater(artifact["directory_forbidden_member_count"], 0)
        artifact_paths = {item["path"] for item in artifact["directory_forbidden_members"]}
        self.assertIn("files/.aide.local/state.sqlite", artifact_paths)
        manifest = distribution_manifest.minimal_fixture_manifest()
        manifest["spec"]["artifacts"] = [artifact]
        manifest["spec"]["components"] = distribution_manifest.build_components([artifact])
        manifest = distribution_manifest.finalize_manifest(manifest)
        result = distribution_manifest.validate_distribution_manifest_object(manifest)
        self.assertIn("distribution.source_state_contamination", result["refusal_codes"])

    def test_fixture_corpus_contains_required_repair_cases(self) -> None:
        root = self.make_repo()
        distribution_manifest.write_fixture_corpus(root)
        required_valid = {
            "minimal-unsigned",
            "full-local-archive",
            "local-directory",
            "reordered-input",
            "unknown-optional-feature",
            "unknown-optional-extension-round-trip",
            "signature-placeholder",
        }
        required_invalid = {
            "duplicate-component-id",
            "malformed-digest",
            "wrong-component-digest",
            "wrong-payload-digest",
            "wrong-distribution-digest",
            "missing-artifact-ref",
            "missing-dependency",
            "dependency-cycle",
            "unsupported-source",
            "unsupported-protocol-range",
            "protocol-range-max-2x",
            "protocol-range-max-2-0-0",
            "protocol-range-min-2-0-0",
            "component-protocol-future-major",
            "inverted-protocol-range",
            "forbidden-member",
            "source-contamination",
            "checksum-missing",
            "checksum-wrong-value",
            "checksum-basename-collision",
            "false-signature-verification",
            "missing-sbom",
        }
        valid_names = {path.stem for path in (root / distribution_manifest.FIXTURE_ROOT / "valid").glob("*.json")}
        invalid_names = {path.stem for path in (root / distribution_manifest.FIXTURE_ROOT / "invalid").glob("*.json")}
        self.assertTrue(required_valid.issubset(valid_names), required_valid - valid_names)
        self.assertTrue(required_invalid.issubset(invalid_names), required_invalid - invalid_names)

    def test_future_major_protocol_fixture_files_fail(self) -> None:
        root = self.make_repo()
        distribution_manifest.write_fixture_corpus(root)
        for case_id in [
            "protocol-range-max-2x",
            "protocol-range-max-2-0-0",
            "protocol-range-min-2-0-0",
            "component-protocol-future-major",
        ]:
            with self.subTest(case_id=case_id):
                fixture = distribution_manifest.read_json(
                    root / distribution_manifest.FIXTURE_ROOT / "invalid" / f"{case_id}.json"
                )
                result = distribution_manifest.validate_distribution_manifest_object(fixture)
                self.assertIn("distribution.unsupported_protocol_range", result["refusal_codes"])

    def test_project_and_validate_write_reports_and_fixture_corpus(self) -> None:
        root = self.make_repo()
        project_report = distribution_manifest.project(root)
        self.assertEqual(project_report["status"], "PASS_WITH_WARNINGS")
        validation = distribution_manifest.validate(root)
        self.assertEqual(validation["validation_status"], "PASS_WITH_WARNINGS")
        self.assertTrue(validation["checks"]["fixture_matrix_passed"])
        for rel in [
            ".aide/reports/distribution-manifest-v1/manifest.json",
            ".aide/reports/distribution-manifest-v1/validation.json",
            ".aide/reports/distribution-manifest-v1/q47-source-mapping.json",
            ".aide/fixtures/distribution-manifest-v1/valid/minimal-unsigned.json",
            ".aide/fixtures/distribution-manifest-v1/invalid/unknown-required-feature.json",
        ]:
            self.assertTrue((root / rel).exists(), rel)

    def test_cli_status_project_validate_and_no_apply_subcommands(self) -> None:
        root = self.make_repo()
        parser = aide_lite.build_parser(REPO_ROOT)
        for command in [
            ["--repo-root", str(root), "distribution-manifest", "status"],
            ["--repo-root", str(root), "distribution-manifest", "project"],
            ["--repo-root", str(root), "distribution-manifest", "validate"],
        ]:
            parsed = parser.parse_args(command)
            output = io.StringIO()
            with redirect_stdout(output):
                result = parsed.handler(parsed)
            self.assertEqual(result, 0, output.getvalue())
            self.assertIn("proposed_capability: distribution_manifest_v1", output.getvalue())
            self.assertIn("install_apply_implemented: false", output.getvalue())
            self.assertIn("release_publication_implemented: false", output.getvalue())
            self.assertIn("target_repository_mutation_implemented: false", output.getvalue())
        for subcommand in ["apply", "publish", "install", "update", "rollback", "uninstall"]:
            with self.subTest(subcommand=subcommand):
                with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    parser.parse_args(["distribution-manifest", subcommand])


if __name__ == "__main__":
    unittest.main()
