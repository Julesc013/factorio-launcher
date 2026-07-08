import copy
import hashlib
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

BASE_TEST_PATH = REPO_ROOT / ".aide/scripts/tests/test_aide_dominium_readonly_seam.py"
BASE_SPEC = importlib.util.spec_from_file_location("aide_dominium_readonly_seam_base_tests_repair03", BASE_TEST_PATH)
base_tests = importlib.util.module_from_spec(BASE_SPEC)
sys.modules["aide_dominium_readonly_seam_base_tests_repair03"] = base_tests
BASE_SPEC.loader.exec_module(base_tests)

from core.interop import dominium
from core.interop.dominium import bundle as seam_bundle
from core.interop.dominium import conformance, fixture_replay, models, operations, validation


class AIDEDominiumReadonlySeamRepair03Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.tmp_root = Path(cls._tmp.name)
        cls.dom_root = cls.tmp_root / "dominium"
        cls.aide_root = cls.tmp_root / "aide"
        cls.revision = base_tests.create_dominium_fixture(cls.dom_root)
        base_tests.copy_dominium_seam_source_files(cls.aide_root)
        cls.project_report = dominium.project_dominium_seam(cls.aide_root, dominium_root=cls.dom_root, revision=cls.revision, write_portability=False)
        cls.bundle = models.read_json(cls.aide_root / models.SEAM_BUNDLE_JSON)
        cls.validation_report = validation.validate_bundle(cls.bundle, dominium_root=cls.dom_root)
        cls.demo_report = dominium.run_dominium_seam_demo(cls.aide_root, dominium_root=cls.dom_root, revision=cls.revision)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_schema_has_explicit_kind_specific_spec_properties(self) -> None:
        schema = json.loads((self.aide_root / models.SCHEMA_PATH).read_text(encoding="utf-8"))
        for name in [
            "HostManifestSpec",
            "HostCapabilitySetSpec",
            "WorkspaceDescriptorSpec",
            "ContextDescriptorSpec",
            "ArtifactReferenceSpec",
            "DiagnosticProjectionSpec",
            "RefusalProjectionSpec",
            "EvidenceReferenceSetSpec",
            "EventEnvelopeSpec",
            "DominiumBridgeManifestSpec",
        ]:
            with self.subTest(name=name):
                spec = schema["$defs"][name]
                self.assertFalse(spec["additionalProperties"])
                self.assertTrue(set(spec["required"]).issubset(spec["properties"]))

    def test_schema_uses_allof_for_kind_discrimination(self) -> None:
        schema = json.loads((self.aide_root / models.SCHEMA_PATH).read_text(encoding="utf-8"))
        host = schema["$defs"]["HostManifestRecord"]
        self.assertIn("allOf", host)
        self.assertEqual(host["allOf"][1]["properties"]["kind"]["const"], "HostManifest")
        self.assertEqual(host["allOf"][1]["properties"]["spec"]["$ref"], "#/$defs/HostManifestSpec")

    def test_false_boundary_status_requires_every_false_field(self) -> None:
        schema = json.loads((self.aide_root / models.SCHEMA_PATH).read_text(encoding="utf-8"))
        required = set(schema["$defs"]["FalseStatus"]["required"])
        self.assertEqual(required, set(models.FALSE_STATUS_FIELDS))
        self.assertIn("source_repository_mutated", required)
        for field in models.FALSE_STATUS_FIELDS:
            self.assertEqual(schema["$defs"]["FalseStatus"]["properties"][field]["const"], False)

    def test_authority_changing_extensions_are_refused_semantically(self) -> None:
        candidate = copy.deepcopy(self.bundle)
        candidate["records"]["host_manifest"]["spec"]["extensions"] = {"network_allowed": True}
        report = validation.validate_bundle(candidate, dominium_root=self.dom_root)
        self.assertIn("schema.authority_extension", {item["code"] for item in report["error_records"]})

    def test_fixture_replay_rejects_missing_object_targets(self) -> None:
        with self.assertRaises(fixture_replay.FixtureReplayError):
            fixture_replay.apply_operations(self.bundle, [{"op": "remove", "path": "/records/host_manifest/spec/missing"}])
        with self.assertRaises(fixture_replay.FixtureReplayError):
            fixture_replay.apply_operations(self.bundle, [{"op": "replace", "path": "/records/host_manifest/spec/missing", "value": "x"}])

    def test_fixture_replay_rejects_noncanonical_array_indexes(self) -> None:
        for index in ["-1", "+1", "01", "00", "1.0", "1e2", " ", ""]:
            with self.subTest(index=index):
                with self.assertRaises(fixture_replay.FixtureReplayError):
                    fixture_replay.apply_operations(self.bundle, [{"op": "replace", "path": f"/records/artifact_references/{index}", "value": {}}])
        for op in ["remove", "replace"]:
            with self.subTest(op=op):
                with self.assertRaises(fixture_replay.FixtureReplayError):
                    fixture_replay.apply_operations(self.bundle, [{"op": op, "path": "/records/artifact_references/-"}])

    def test_fixture_replay_rejects_root_and_executable_metadata(self) -> None:
        with self.assertRaises(fixture_replay.FixtureReplayError):
            fixture_replay.apply_operations(self.bundle, [{"op": "replace", "path": "", "value": {}}])
        for key in ["callable", "module", "command", "shell", "eval", "exec", "python", "entrypoint", "script"]:
            with self.subTest(key=key):
                with self.assertRaises(fixture_replay.FixtureReplayError):
                    fixture_replay.apply_operations(self.bundle, [{"op": "replace", "path": "/kind", "value": "x", key: "x"}])

    def test_conformance_evidence_is_explicit_and_missing_aggregate_is_not_proven(self) -> None:
        evidence = conformance.conformance_evidence(self.bundle, self.validation_report, dominium_root=self.dom_root)
        self.assertTrue(evidence["unsupported_operation_probes"]["all_typed_refusals"])
        self.assertEqual(evidence["dominium_before_after_state"]["status"], "PASS")
        self.assertEqual(evidence["operation_guard"]["network_attempts"]["result"], "PASS")
        aggregate_only = conformance.conformance_results(self.validation_report)
        self.assertTrue(all(item["result"] == "NOT_PROVEN" for item in aggregate_only["results"]))

    def test_operation_trace_is_complete_and_recomputable(self) -> None:
        trace = models.read_json(self.aide_root / models.OPERATION_TRACE_JSON)
        ledger = self.demo_report["operation_ledger"]
        self.assertEqual(len(trace["observations"]), ledger["raw_observation_count"])
        digest = "sha256:" + hashlib.sha256(json.dumps(trace["observations"], sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        self.assertEqual(digest, ledger["raw_trace_sha256"])
        self.assertEqual(ledger["allowed_observation_count"] + ledger["forbidden_observation_count"], ledger["raw_observation_count"])

    def test_git_operation_classification_refuses_remote_and_ref_mutations(self) -> None:
        for verb in ["fetch", "pull", "clone", "push", "ls-remote"]:
            with self.subTest(verb=verb):
                self.assertEqual(operations.classify_git_args([verb])[0], "network_attempts")
                self.assertFalse(operations.classify_git_args([verb])[1])
        for verb in ["checkout", "switch", "reset", "merge", "rebase", "branch", "worktree", "tag", "update-ref", "commit"]:
            with self.subTest(verb=verb):
                self.assertEqual(operations.classify_git_args([verb])[0], "branch_worktree_ref_ops")
                self.assertFalse(operations.classify_git_args([verb])[1])

    def test_guard_conformance_artifact_covers_all_required_families(self) -> None:
        report = models.read_json(self.aide_root / models.OPERATION_GUARD_CONFORMANCE_JSON)
        families = {item["family"] for item in report["probes"]}
        self.assertEqual(families, set(operations.REQUIRED_FAMILIES) - {"git_reads"})
        self.assertTrue(all(item["execution_prevented"] and item["result"] == "PASS" for item in report["probes"]))

    def test_manifest_validation_refuses_hash_mismatch_and_path_escape(self) -> None:
        manifest = seam_bundle.load_runtime_dependency_manifest(self.aide_root)
        bad_hash = copy.deepcopy(manifest)
        bad_hash["dependencies"][0]["sha256"] = "sha256:" + "0" * 64
        bad_hash["manifest_digest"] = seam_bundle.integrity.stable_digest({key: value for key, value in bad_hash.items() if key != "manifest_digest"})
        with self.assertRaises(ValueError):
            seam_bundle._validate_runtime_dependency_manifest(self.aide_root, bad_hash)
        bad_path = copy.deepcopy(manifest)
        bad_path["dependencies"][0]["path"] = "../escape.py"
        bad_path["manifest_digest"] = seam_bundle.integrity.stable_digest({key: value for key, value in bad_path.items() if key != "manifest_digest"})
        with self.assertRaises(ValueError):
            seam_bundle._validate_runtime_dependency_manifest(self.aide_root, bad_path)

    def test_import_closure_has_no_missing_required_dependencies(self) -> None:
        closure = seam_bundle.local_import_closure(self.aide_root)
        self.assertEqual(closure["undeclared_dependency_count"], 0)
        self.assertEqual(closure["missing_declarations"], [])

    def test_portability_uses_sanitized_isolated_environment(self) -> None:
        report = seam_bundle.portability_check(self.aide_root, dominium_root=self.dom_root, revision=self.revision)
        self.assertEqual(report["status"], "PASS")
        self.assertTrue(report["required_output_set_equal"])
        self.assertEqual(report["undeclared_dependency_count"], 0)
        self.assertTrue(report["sanitized_environment"]["PYTHONPATH_removed"])
        self.assertTrue(report["sanitized_environment"]["PYTHONHOME_removed"])
        self.assertTrue(report["sanitized_environment"]["python_isolated_mode"])

    def test_extended_unsupported_cli_verbs_are_typed_refusals(self) -> None:
        for verb in conformance.UNSUPPORTED_VERBS:
            with self.subTest(verb=verb):
                stdout = io.StringIO()
                stderr = io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    code = base_tests.aide_lite.main(["--repo-root", str(self.aide_root), "dominium-seam", verb])
                output = stdout.getvalue() + stderr.getvalue()
                self.assertEqual(code, 2, output)
                self.assertIn("result: REFUSED", output)
                self.assertIn("reason_code: AIDE_DOMINIUM_SEAM_UNSUPPORTED_OPERATION", output)
                self.assertIn(f"operation: {verb}", output)
                self.assertIn("source_repository_mutated: false", output)


if __name__ == "__main__":
    unittest.main()
