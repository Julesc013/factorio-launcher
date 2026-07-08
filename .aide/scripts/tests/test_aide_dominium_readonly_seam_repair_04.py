from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.interop.dominium import conformance, fixture_replay, models, operations, validation


FALSE_BOUNDARY_FIELDS = [
    "dominium_command_invoked",
    "generated_projection_marked_canonical",
    "host_runtime_started",
    "workbench_started",
    "bridge_runtime_started",
    "service_started",
    "database_opened",
    "transport_started",
    "network_call_performed",
    "provider_or_model_called",
    "worker_executed",
    "patch_transaction_applied",
    "preview_or_apply_performed",
    "source_repository_mutated",
    "target_repository_mutated",
    "branch_or_worktree_created",
    "github_mutation_performed",
    "release_or_promotion_performed",
]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class DominiumReadonlySeamRepair04Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = load_json(ROOT / models.SCHEMA_PATH)
        cls.bundle = load_json(ROOT / models.SEAM_BUNDLE_JSON)

    def test_schema_has_record_union_and_bounded_extensions(self) -> None:
        defs = self.schema["$defs"]
        self.assertIn("SeamRecord", defs)
        union_refs = {item["$ref"] for item in defs["SeamRecord"]["oneOf"]}
        expected_refs = {
            "#/$defs/HostManifestRecord",
            "#/$defs/HostCapabilitySetRecord",
            "#/$defs/WorkspaceDescriptorRecord",
            "#/$defs/ContextDescriptorRecord",
            "#/$defs/ArtifactReferenceRecord",
            "#/$defs/DiagnosticProjectionRecord",
            "#/$defs/RefusalProjectionRecord",
            "#/$defs/EvidenceReferenceSetRecord",
            "#/$defs/EventEnvelopeRecord",
            "#/$defs/DominiumBridgeManifestRecord",
        }
        self.assertEqual(union_refs, expected_refs)
        extension_map = defs["ExtensionMap"]
        self.assertIsInstance(extension_map["additionalProperties"], dict)
        denied = extension_map["propertyNames"]["allOf"][1]["not"]["enum"]
        for name in ["canonical", "network_allowed", "provider_enabled", "worker_enabled"]:
            self.assertIn(name, denied)

    def test_validation_rejects_nested_authority_extension_keys(self) -> None:
        candidate = copy.deepcopy(self.bundle)
        candidate["records"]["host_manifest"]["spec"]["extensions"] = {
            "safe_namespace": {"worker_enabled": True}
        }
        report = validation.validate_bundle(candidate)
        codes = {item["code"] for item in report["error_records"]}
        self.assertIn("schema.authority_extension", codes)

    def test_fixture_replay_is_strict_about_values_indexes_and_executable_keys(self) -> None:
        base = {"items": [{"name": "a"}]}
        with self.assertRaises(fixture_replay.FixtureReplayError):
            fixture_replay.apply_operations(base, [{"op": "replace", "path": "/items/0/name"}])
        with self.assertRaises(fixture_replay.FixtureReplayError):
            fixture_replay.apply_operations(base, [{"op": "remove", "path": "/items/١"}])
        with self.assertRaises(fixture_replay.FixtureReplayError):
            fixture_replay.apply_operations(base, [{"op": "add", "path": "/items/-", "value": {}, "kwargs": {}}])

    def test_conformance_uses_cli_for_arbitrary_unsupported_verbs(self) -> None:
        probes = conformance.unsupported_operation_probe_matrix(ROOT)
        arbitrary = [item for item in probes["results"] if item["verb"] == "repair04-arbitrary-unsupported-verb"]
        self.assertEqual(len(arbitrary), 1)
        self.assertTrue(arbitrary[0]["typed_refusal"])
        self.assertEqual(arbitrary[0]["exit_code"], 2)

    def test_unknown_dominium_seam_cli_verb_returns_typed_refusal(self) -> None:
        proc = subprocess.run(
            [sys.executable, ".aide/scripts/aide_lite.py", "dominium-seam", "repair04-unknown-verb"],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        output = proc.stdout + proc.stderr
        self.assertEqual(proc.returncode, 2, output)
        self.assertIn("result: REFUSED", output)
        self.assertIn("reason_code: AIDE_DOMINIUM_SEAM_UNSUPPORTED_OPERATION", output)
        self.assertIn("operation: repair04-unknown-verb", output)
        for field in FALSE_BOUNDARY_FIELDS:
            self.assertIn(f"{field}: false", output)

    def test_operation_aggregate_preserves_target_classification_and_source(self) -> None:
        ledger = operations.OperationLedger()
        ledger.record(
            "probe",
            family="filesystem_writes",
            target="Dominium/a",
            classification="forbidden_write",
            allowed=False,
            source="test-one",
            observation_method="guard",
        )
        ledger.record(
            "probe",
            family="filesystem_writes",
            target="Dominium/b",
            classification="forbidden_write_other",
            allowed=False,
            source="test-two",
            observation_method="guard",
        )
        report = ledger.as_report()
        self.assertEqual(len([item for item in report["operations"] if item["operation"] == "probe"]), 2)
        keys = {(item["target"], item["classification"], item["source"]) for item in report["operations"] if item["operation"] == "probe"}
        self.assertEqual(keys, {("Dominium/a", "forbidden_write", "test-one"), ("Dominium/b", "forbidden_write_other", "test-two")})

    def test_guard_report_is_exercised_and_portability_outputs_are_complete(self) -> None:
        guard = operations.guard_conformance()
        self.assertEqual(guard["result"], "PASS")
        self.assertTrue(all(item["evidence_kind"] == "exercised_guard_probe" for item in guard["probes"]))
        self.assertTrue(all(item["guard_reached"] for item in guard["probes"]))
        self.assertTrue(all(item["executor_injected"] for item in guard["probes"]))
        self.assertFalse(any(item["executor_invoked"] for item in guard["probes"]))
        portability_path = ROOT / models.PORTABILITY_RESULT_JSON
        if portability_path.exists():
            portability = load_json(portability_path)
            compared = set(portability.get("compared_outputs", []))
            required = {
                models.CONFORMANCE_EVIDENCE_JSON.as_posix(),
                models.OPERATION_TRACE_JSON.as_posix(),
                models.OPERATION_GUARD_CONFORMANCE_JSON.as_posix(),
            }
            self.assertTrue(required.issubset(compared), sorted(required - compared))


if __name__ == "__main__":
    unittest.main()
