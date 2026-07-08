import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

BASE_TEST_PATH = REPO_ROOT / ".aide/scripts/tests/test_aide_dominium_readonly_seam.py"
BASE_SPEC = importlib.util.spec_from_file_location("aide_dominium_readonly_seam_base_tests", BASE_TEST_PATH)
base_tests = importlib.util.module_from_spec(BASE_SPEC)
sys.modules["aide_dominium_readonly_seam_base_tests"] = base_tests
BASE_SPEC.loader.exec_module(base_tests)

from core.interop import dominium
from core.interop.dominium import fixture_replay, identity, integrity, models, validation


class AIDEDominiumReadonlySeamRepairTests(unittest.TestCase):
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

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def assertCodes(self, candidate: dict, *codes: str) -> None:
        report = validation.validate_bundle(candidate, dominium_root=self.dom_root)
        observed = {item["code"] for item in report["error_records"]}
        for code in codes:
            self.assertIn(code, observed, report["error_records"])

    def refinalized(self, candidate: dict) -> dict:
        integrity.finalize_bundle(candidate)
        return candidate

    def test_exact_identity_accepts_only_canonical_remote_forms(self) -> None:
        accepted = [
            "https://github.com/Julesc013/dominium.git",
            "git@github.com:Julesc013/dominium.git",
            "ssh://git@github.com/Julesc013/dominium.git",
        ]
        for remote in accepted:
            with self.subTest(remote=remote):
                parsed = identity.assert_expected_repository_identity(remote)
                self.assertEqual(parsed.canonical_identity, "github.com/julesc013/dominium")

    def test_exact_identity_rejects_lookalikes(self) -> None:
        rejected = [
            "https://github.com/example/julesc013-dominium.git",
            "https://github.com/Julesc013/dominium-shadow.git",
            "https://evil.invalid/Julesc013/dominium.git",
        ]
        for remote in rejected:
            with self.subTest(remote=remote):
                with self.assertRaises(identity.RepositoryIdentityError):
                    identity.assert_expected_repository_identity(remote)

    def test_bundle_self_digest_recomputes(self) -> None:
        expected = integrity.stable_digest(integrity.bundle_payload_for_self_digest(self.bundle))
        self.assertEqual(self.bundle["content_digests"]["seam_bundle_without_self_digest"], expected)

    def test_bundle_self_digest_detects_tampering(self) -> None:
        candidate = copy.deepcopy(self.bundle)
        candidate["records"]["host_manifest"]["spec"]["host_id"] = "changed"
        self.assertCodes(candidate, "digest.projection_index", "digest.record", "digest.bundle_self")

    def test_registry_truncation_is_explicit_for_diagnostics_and_refusals(self) -> None:
        summary = self.bundle["registry_projection_summary"]
        for key in ["diagnostics", "refusals"]:
            with self.subTest(key=key):
                data = summary[key]
                self.assertEqual(data["selection_policy"], "source_order_first_n")
                self.assertGreaterEqual(data["native_count"], data["projected_count"])
                self.assertEqual(data["native_count"] - data["projected_count"], data["omitted_count"])
                self.assertIn("omitted_ids_sha256", data)

    def test_negative_fixtures_are_replayable(self) -> None:
        for fixture in fixture_replay.negative_fixture_cases(self.bundle):
            with self.subTest(name=fixture["name"]):
                invalid = fixture_replay.materialize_fixture(fixture, self.bundle)
                self.assertEqual(integrity.stable_digest(invalid), fixture["invalid_bundle_sha256"])
                report = validation.validate_bundle(invalid, dominium_root=self.dom_root)
                observed = {item["code"] for item in report["error_records"]}
                self.assertTrue(set(fixture["expected_error_codes"]).issubset(observed), report["error_records"])

    def test_conformance_results_are_not_aggregate_only(self) -> None:
        conformance = models.read_json(self.aide_root / models.CONFORMANCE_RESULTS_JSON)
        assertion_ids = {item["assertion_id"] for item in conformance["results"]}
        self.assertGreater(len(assertion_ids), 5)
        for item in conformance["results"]:
            self.assertIn("expected", item)
            self.assertIn("observed", item)
            self.assertIn("evidence_refs", item)
        self.assertEqual(conformance["passed_count"], conformance["expectation_count"])

    def test_demo_elapsed_time_is_truthfully_unmeasured(self) -> None:
        demo = dominium.run_dominium_seam_demo(self.aide_root, dominium_root=self.dom_root, revision=self.revision)
        self.assertEqual(demo["elapsed_time"]["status"], "not_measured")
        self.assertIsNone(demo["elapsed_time"]["elapsed_ms"])
        self.assertIn("operation_ledger", demo)

    def test_mixed_record_revision_is_rejected_after_refinalize(self) -> None:
        candidate = copy.deepcopy(self.bundle)
        candidate["records"]["host_manifest"]["metadata"]["source_revision"] = "0" * 40
        self.refinalized(candidate)
        self.assertCodes(candidate, "revision.binding")

    def test_snapshot_digest_is_validated(self) -> None:
        candidate = copy.deepcopy(self.bundle)
        candidate["source_snapshot"]["snapshot_digest"] = "sha256:" + "1" * 64
        self.assertCodes(candidate, "digest.snapshot")

    def test_second_host_capability_set_is_rejected(self) -> None:
        candidate = copy.deepcopy(self.bundle)
        candidate["records"]["host_capability_set"] = [
            self.bundle["records"]["host_capability_set"],
            self.bundle["records"]["host_capability_set"],
        ]
        self.assertCodes(candidate, "cardinality.singleton")

    def test_dangling_artifact_reference_is_rejected_after_refinalize(self) -> None:
        candidate = copy.deepcopy(self.bundle)
        candidate["records"]["context_descriptor"]["spec"]["artifact_refs"].append("aide://artifact/dangling")
        self.refinalized(candidate)
        self.assertCodes(candidate, "reference.closure")

    def test_wrong_semantic_owner_is_rejected_after_refinalize(self) -> None:
        candidate = copy.deepcopy(self.bundle)
        candidate["records"]["artifact_references"][0]["metadata"]["semantic_owner"] = "AIDE"
        self.refinalized(candidate)
        self.assertCodes(candidate, "ownership.semantic")

    def test_mutation_capability_labeled_readonly_is_rejected_after_refinalize(self) -> None:
        candidate = copy.deepcopy(self.bundle)
        candidate["records"]["host_capability_set"]["spec"]["capabilities"][0]["id"] = "dominium.patch.apply"
        self.refinalized(candidate)
        self.assertCodes(candidate, "capability.mutation")

    def test_duplicate_event_sequence_is_rejected_after_refinalize(self) -> None:
        candidate = copy.deepcopy(self.bundle)
        candidate["records"]["event_envelopes"][1]["spec"]["sequence"] = 1
        self.refinalized(candidate)
        self.assertCodes(candidate, "event.sequence")

    def test_arbitrary_diagnostic_severity_is_rejected_after_refinalize(self) -> None:
        candidate = copy.deepcopy(self.bundle)
        candidate["records"]["diagnostic_projections"][0]["spec"]["severity"] = "notice"
        self.refinalized(candidate)
        self.assertCodes(candidate, "diagnostic.registry")

    def test_invented_refusal_is_rejected_after_refinalize(self) -> None:
        candidate = copy.deepcopy(self.bundle)
        candidate["records"]["refusal_projections"][0]["spec"]["refusal_id"] = "dominium.refusal.invented"
        self.refinalized(candidate)
        self.assertCodes(candidate, "refusal.registry")

    def test_missing_host_id_is_rejected_after_refinalize(self) -> None:
        candidate = copy.deepcopy(self.bundle)
        candidate["records"]["host_manifest"]["spec"].pop("host_id")
        self.refinalized(candidate)
        self.assertCodes(candidate, "spec.required")

    def test_schema_is_structurally_effective(self) -> None:
        schema = json.loads((self.aide_root / models.SCHEMA_PATH).read_text(encoding="utf-8"))
        self.assertFalse(schema["additionalProperties"])
        self.assertIn("registry_projection_summary", schema["required"])
        self.assertFalse(schema["properties"]["records"]["additionalProperties"])
        self.assertIn("SourceFile", schema["$defs"])
        self.assertIn("HostManifestSpec", schema["$defs"])
        self.assertEqual(schema["properties"]["records"]["properties"]["host_manifest"]["$ref"], "#/$defs/HostManifestRecord")
        self.assertEqual(schema["properties"]["status"]["$ref"], "#/$defs/FalseStatus")

    def test_next_task_routes_to_repair_check(self) -> None:
        self.assertTrue(models.RECOMMENDED_NEXT_TASK.startswith("AIDE-CHECK-DOMINIUM-READONLY-SEAM-V0-REPAIR-"))
        self.assertEqual(self.project_report["recommended_next_task"], models.RECOMMENDED_NEXT_TASK)


if __name__ == "__main__":
    unittest.main()
