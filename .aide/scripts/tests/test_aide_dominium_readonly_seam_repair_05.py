from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]

from core.interop.dominium import conformance, fixture_replay, models, operations, schema_audit, validation


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class DominiumReadonlySeamRepair05Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = load_json(ROOT / models.SCHEMA_PATH)
        cls.bundle = load_json(ROOT / models.SEAM_BUNDLE_JSON)

    def test_schema_surface_audit_has_no_unintended_open_objects(self) -> None:
        report = schema_audit.schema_surface_audit(self.schema)
        self.assertEqual(report["unclassified_object_count"], 0, report["unclassified_objects"])
        self.assertEqual(report["unintentionally_open_object_count"], 0, report["unintentionally_open_objects"])
        classes = {item["classification"] for item in report["objects"]}
        self.assertIn("closed canonical object", classes)
        self.assertIn("typed dynamic map", classes)
        self.assertIn("explicit ExtensionMap", classes)

    def test_authority_extension_semantics_are_refused_after_normalization(self) -> None:
        denied = [
            "apply_allowed",
            "releaseAllowed",
            "runtime.enabled",
            "mutation/apply/allowed",
            "workbench.is-authority",
            "ｐｒｏｖｉｄｅｒ＿ｅｎａｂｌｅｄ",
            "safe.authoritative",
        ]
        for key in denied:
            with self.subTest(key=key):
                candidate = copy.deepcopy(self.bundle)
                candidate["records"]["host_manifest"]["spec"]["extensions"] = {key: True}
                report = validation.validate_bundle(candidate)
                records = [item for item in report["error_records"] if item["code"] == "extension.authority_change"]
                self.assertTrue(records, report["error_records"])
                observed = records[0]["observed"][0]
                self.assertEqual(observed["original_key"], key)
                self.assertIn("tokens", observed)
        benign = copy.deepcopy(self.bundle)
        benign["records"]["host_manifest"]["spec"]["extensions"] = {
            "vendor.color": "blue",
            "documentation.note": {"source.annotation": "ok"},
        }
        benign_report = validation.validate_bundle(benign)
        self.assertNotIn("extension.authority_change", {item["code"] for item in benign_report["error_records"]})

    def test_guard_dispatcher_exercises_every_forbidden_family(self) -> None:
        nonce = "repair05-nonce"
        report = operations.guard_conformance(nonce=nonce)
        self.assertEqual(report["result"], "PASS")
        self.assertEqual(report["probe_count"], 6)
        self.assertEqual(report["passed_count"], 6)
        self.assertEqual(report["unique_request_count"], 6)
        for probe in report["probes"]:
            with self.subTest(family=probe["family"]):
                self.assertIn(nonce, probe["request_id"])
                self.assertIn(nonce, probe["operation"])
                self.assertTrue(probe["guard_reached"])
                self.assertTrue(probe["executor_injected"])
                self.assertFalse(probe["executor_invoked"])
                self.assertTrue(probe["execution_prevented"])
                self.assertEqual(probe["reason_code"], "AIDE_DOMINIUM_SEAM_READ_ONLY_BOUNDARY")
                self.assertEqual(probe["state_before_digest"], probe["state_after_digest"])
                self.assertEqual(probe["result"], "PASS")

    def test_guard_unknown_family_fails_closed_without_executor(self) -> None:
        called = {"value": False}

        def sentinel() -> object:
            called["value"] = True
            raise AssertionError("executor should not run")

        request = operations.GuardRequest(
            request_id="unknown-family-probe",
            family="unknown_family",
            operation="future forbidden operation",
            target="Dominium/unknown",
            source="repair05-test",
            requested_effect="unknown side effect",
            metadata={},
        )
        decision = operations.dispatch_guarded_request(request, sentinel)
        self.assertFalse(called["value"])
        self.assertFalse(decision["executor_invoked"])
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason_code"], "AIDE_DOMINIUM_SEAM_UNSUPPORTED_OPERATION_FAMILY")
        self.assertEqual(decision["result"], "FAILED_VALIDATION")

    def test_guard_report_digest_recomputes_and_nonce_changes_report(self) -> None:
        one = operations.guard_conformance(nonce="repair05-one")
        two = operations.guard_conformance(nonce="repair05-two")
        for report in [one, two]:
            expected = "sha256:" + hashlib.sha256(
                json.dumps({k: v for k, v in report.items() if k != "report_digest"}, sort_keys=True, separators=(",", ":")).encode("utf-8")
            ).hexdigest()
            self.assertEqual(report["report_digest"], expected)
        self.assertNotEqual(one["report_digest"], two["report_digest"])

    def test_operation_coverage_consumes_guard_evidence(self) -> None:
        ledger = operations.OperationLedger()
        ledger.record(
            "git status",
            family="git_reads",
            target="Dominium",
            classification="read_only_git",
            allowed=True,
            source="repair05-test",
            observation_method="command_wrapper_observation",
        )
        report = ledger.as_report()
        for family in operations.REQUIRED_FAMILIES:
            self.assertEqual(report["coverage"][family]["status"], "PROVEN", family)
            if family != "git_reads":
                self.assertTrue(report["coverage"][family]["request_ids"])
                self.assertTrue(report["coverage"][family]["guard_ids"])

    def test_fixture_cli_and_operation_regressions_remain_closed(self) -> None:
        with self.assertRaises(fixture_replay.FixtureReplayError):
            fixture_replay.apply_operations({"items": [1]}, [{"op": "replace", "path": "/items/１", "value": 2}])
        probes = conformance.unsupported_operation_probe_matrix(ROOT)
        self.assertTrue(probes["all_typed_refusals"])
        guard = operations.guard_conformance()
        self.assertEqual(guard["result"], "PASS")


if __name__ == "__main__":
    unittest.main()
