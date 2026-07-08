import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

BASE_TEST_PATH = REPO_ROOT / ".aide/scripts/tests/test_aide_dominium_readonly_seam.py"
import importlib.util

BASE_SPEC = importlib.util.spec_from_file_location("aide_dominium_readonly_seam_base_tests_repair02", BASE_TEST_PATH)
base_tests = importlib.util.module_from_spec(BASE_SPEC)
sys.modules["aide_dominium_readonly_seam_base_tests_repair02"] = base_tests
BASE_SPEC.loader.exec_module(base_tests)

from core.interop import dominium
from core.interop.dominium import bundle as seam_bundle
from core.interop.dominium import conformance, fixture_replay, integrity, models, operations, validation


class AIDEDominiumReadonlySeamRepair02Tests(unittest.TestCase):
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

    def test_registry_projection_discloses_source_provenance(self) -> None:
        source_files = {item["path"]: item for item in self.bundle["source_snapshot"]["selected_files"]}
        for key in ["diagnostics", "refusals"]:
            with self.subTest(key=key):
                summary = self.bundle["registry_projection_summary"][key]
                source_file = source_files[summary["path"]]
                self.assertEqual(summary["source_registry_sha256"], source_file["sha256"])
                self.assertEqual(summary["source_revision"], self.revision)
                self.assertIn("mode", summary["source_registry_git_object"])
                self.assertEqual(summary["selected_ids_sha256"], integrity.stable_digest(summary["projected_ids"]))
                self.assertIsInstance(summary["truncation_disclosed"], bool)
                self.assertEqual(summary["truncation_disclosed"], summary["omitted_count"] > 0)

    def test_validation_error_records_include_expected_and_observed(self) -> None:
        candidate = json.loads(json.dumps(self.bundle))
        candidate["records"]["workspace_descriptor"]["status"]["workbench_started"] = True
        report = validation.validate_bundle(candidate, dominium_root=self.dom_root)
        record = next(item for item in report["error_records"] if item["code"] == "workbench.authority")
        self.assertIn("expected", record)
        self.assertIn("observed", record)
        self.assertIs(record["expected"], False)
        self.assertIs(record["observed"], True)

    def test_conformance_results_have_independent_assertion_fields(self) -> None:
        report = conformance.conformance_results(self.bundle, self.validation_report, dominium_root=self.dom_root)
        self.assertEqual(report["passed_count"], report["expectation_count"])
        for result in report["results"]:
            with self.subTest(assertion_id=result["assertion_id"]):
                self.assertTrue(result["assertion_id"].startswith("seam."))
                self.assertEqual(result["result"], "PASS")
                self.assertIn("expected", result)
                self.assertIn("observed", result)
                self.assertTrue(result["evidence_refs"])

    def test_aggregate_only_conformance_is_not_proven(self) -> None:
        report = conformance.conformance_results(self.validation_report)
        self.assertEqual(report["status"], "FAILED_VALIDATION")
        self.assertEqual(report["passed_count"], 0)
        self.assertTrue(all(item["result"] == "NOT_PROVEN" for item in report["results"]))

    def test_conformance_assertion_sidecar_is_written(self) -> None:
        report = models.read_json(self.aide_root / models.CONFORMANCE_ASSERTIONS_JSON)
        self.assertEqual(report["task_id"], models.REPAIR_TASK_ID)
        self.assertEqual(len(report["assertions"]), len(conformance.EXPECTATIONS))
        self.assertTrue(all(item["result"] == "PASS" for item in report["assertions"].values()))

    def test_operation_ledger_records_counts_and_family_methods(self) -> None:
        demo = dominium.run_dominium_seam_demo(self.aide_root, dominium_root=self.dom_root, revision=self.revision)
        ledger = demo["operation_ledger"]
        self.assertIn("allowed_operation_count", ledger)
        self.assertGreater(ledger["allowed_operation_count"], 0)
        self.assertEqual(ledger["forbidden_operation_count"], 0)
        self.assertEqual(set(ledger["required_operation_families"]), set(operations.REQUIRED_FAMILIES))
        self.assertEqual(set(ledger["coverage_methods"]), set(operations.REQUIRED_FAMILIES))
        self.assertTrue(all("family" in item and "observation_method" in item for item in ledger["observations"]))

    def test_runtime_dependency_manifest_is_complete(self) -> None:
        manifest = models.read_json(self.aide_root / models.RUNTIME_DEPENDENCY_MANIFEST_JSON)
        paths = {item["path"] for item in manifest["dependencies"]}
        self.assertEqual(paths, set(models.required_runtime_dependency_paths()))
        self.assertEqual(manifest["dependency_count"], len(paths))
        self.assertTrue(all(item["sha256"].startswith("sha256:") for item in manifest["dependencies"]))

    def test_portability_result_compares_isolated_cli_outputs(self) -> None:
        report = seam_bundle.portability_check(self.aide_root, dominium_root=self.dom_root, revision=self.revision)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["isolated_cli_roots"], 2)
        self.assertTrue(report["output_hashes_equal"])
        self.assertEqual(report["absolute_path_leak_count"], 0)
        self.assertEqual({item["command"] for item in report["commands"]}, {"status", "snapshot", "project", "validate", "diff", "demo"})
        self.assertTrue(all(item["returncode"] == 0 for item in report["commands"]))

    def test_portable_cli_runs_from_unrelated_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            portable_root = Path(tmp) / "portable"
            cwd = Path(tmp) / "cwd"
            cwd.mkdir()
            seam_bundle._copy_runtime_dependencies(self.aide_root, portable_root)
            env = os.environ.copy()
            env["AIDE_DOMINIUM_PORTABILITY_CHILD"] = "1"
            result = subprocess.run(
                [
                    sys.executable,
                    str(portable_root / ".aide/scripts/aide_lite.py"),
                    "--repo-root",
                    str(portable_root),
                    "dominium-seam",
                    "project",
                    "--dominium-root",
                    str(self.dom_root),
                    "--revision",
                    self.revision,
                ],
                cwd=cwd,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((portable_root / models.SEAM_BUNDLE_JSON).exists())

    def test_schema_has_kind_specific_record_refs_and_false_status(self) -> None:
        schema = json.loads((self.aide_root / models.SCHEMA_PATH).read_text(encoding="utf-8"))
        records = schema["properties"]["records"]["properties"]
        self.assertEqual(records["diagnostic_projections"]["items"]["$ref"], "#/$defs/DiagnosticProjectionRecord")
        self.assertEqual(records["refusal_projections"]["items"]["$ref"], "#/$defs/RefusalProjectionRecord")
        self.assertEqual(records["dominium_bridge_manifest"]["$ref"], "#/$defs/DominiumBridgeManifestRecord")
        self.assertEqual(schema["properties"]["status"]["$ref"], "#/$defs/FalseStatus")
        self.assertIn("workbench_started", schema["$defs"]["FalseStatus"]["required"])

    def test_fixture_operations_are_bounded_and_replay_all_expected_codes(self) -> None:
        for case in fixture_replay.negative_fixture_cases(self.bundle):
            with self.subTest(name=case["name"]):
                for op in case["operations"]:
                    self.assertIn(op["op"], fixture_replay.ALLOWED_OPERATIONS)
                    self.assertFalse(fixture_replay.FORBIDDEN_OPERATION_KEYS.intersection(op))
                invalid = fixture_replay.materialize_fixture(case, self.bundle)
                observed = {item["code"] for item in validation.validate_bundle(invalid, dominium_root=self.dom_root)["error_records"]}
                self.assertTrue(set(case["expected_error_codes"]).issubset(observed), observed)

    def test_executable_fixture_operation_is_rejected(self) -> None:
        with self.assertRaises(fixture_replay.FixtureReplayError):
            fixture_replay.apply_operations(self.bundle, [{"op": "replace", "path": "/kind", "value": "x", "command": "echo nope"}])


if __name__ == "__main__":
    unittest.main()
