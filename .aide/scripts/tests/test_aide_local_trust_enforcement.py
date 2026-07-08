from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.protocol import trust_authorization
from core.service import local_trust_enforcement as local_trust
from core.service.sqlite_store import LocalServiceError, SQLiteStore


class LocalTrustEnforcementTests(unittest.TestCase):
    def _store(self, temp_root: Path) -> SQLiteStore:
        store = SQLiteStore(temp_root / "state.sqlite")
        store.initialize()
        return store

    def test_allowed_evaluation_persists_event_and_consumes_grant(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(Path(tmp))
            try:
                records = local_trust._records_for_fixture()
                evaluation = local_trust.evaluate_local_authorization(records)
                result = local_trust.persist_evaluation(store, records, evaluation, idempotency_key="allowed")
                self.assertEqual(result["idempotency"]["status"], "recorded")
                self.assertEqual(result["event_sequence"], 1)
                self.assertEqual(result["grant_event_sequence"], 2)
                self.assertTrue(result["grant_consumed"])
                stored_evaluation = store.get_object(evaluation["spec"]["evaluation_ref"])
                stored_grant = store.get_object(records["grant"]["spec"]["grant_ref"])
                self.assertEqual(stored_evaluation.body["spec"]["result"], "allowed")
                self.assertEqual(stored_grant.body["spec"]["status"], "consumed")
                self.assertEqual(stored_grant.body["spec"]["remaining_uses"], 0)
                self.assertEqual([event["sequence"] for event in store.read_events_after(0)], [1, 2])
            finally:
                store.close()

    def test_idempotent_replay_does_not_append_events_or_reconsume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(Path(tmp))
            try:
                records = local_trust._records_for_fixture()
                evaluation = local_trust.evaluate_local_authorization(records)
                local_trust.persist_evaluation(store, records, evaluation, idempotency_key="same")
                replay = local_trust.persist_evaluation(store, records, evaluation, idempotency_key="same")
                self.assertEqual(replay["idempotency"]["status"], "duplicate")
                self.assertIsNone(replay["event_sequence"])
                self.assertFalse(replay["grant_consumed"])
                self.assertEqual([event["sequence"] for event in store.read_events_after(0)], [1, 2])
            finally:
                store.close()

    def test_concurrent_final_use_refuses_after_grant_consumed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = self._store(Path(tmp))
            try:
                records = local_trust._records_for_fixture()
                evaluation = local_trust.evaluate_local_authorization(records)
                local_trust.persist_evaluation(store, records, evaluation, idempotency_key="first")
                with self.assertRaisesRegex(LocalServiceError, "grant_exhausted"):
                    local_trust.persist_evaluation(store, records, evaluation, idempotency_key="second")
                self.assertEqual([event["sequence"] for event in store.read_events_after(0)], [1, 2])
            finally:
                store.close()

    def test_required_refusal_matrix_covers_contract_codes(self) -> None:
        matrix = trust_authorization.negative_evaluation_matrix()
        self.assertEqual(set(matrix), set(trust_authorization.REFUSAL_CODES))
        for code, evaluation in matrix.items():
            with self.subTest(code=code):
                self.assertIn(code, evaluation["spec"]["reason_codes"])
                self.assertIn(evaluation["spec"]["result"], {"denied", "approval_required", "quarantined"})
                self.assertEqual(trust_authorization.validate_trust_authorization_contract(evaluation), [])

    def test_fixture_report_boundaries_and_restart_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = local_trust.fixture(REPO_ROOT, state_root=Path(tmp), write_reports=False)
            self.assertEqual(report["status"], "PASS_WITH_WARNINGS")
            self.assertEqual(report["evaluation_result"], "allowed")
            self.assertTrue(report["persisted_evaluation"])
            self.assertTrue(report["grant_consumed"])
            self.assertEqual(report["grant_remaining_uses"], 0)
            self.assertTrue(report["idempotent_replay_no_second_event"])
            self.assertTrue(report["concurrent_final_use_refused"])
            self.assertEqual(report["event_sequences"], [1, 2])
            self.assertEqual(report["reopened_event_sequences"], [1, 2])
            self.assertTrue(report["all_required_refusal_codes_covered"])
            self.assertEqual(report["process_launch_count"], 0)
            self.assertFalse(report["network_calls_performed"])
            self.assertFalse(report["worker_execution_performed"])
            self.assertFalse(report["provider_model_calls_performed"])

    def test_cli_fixture_outputs_false_boundaries(self) -> None:
        result = subprocess.run(
            [sys.executable, ".aide/scripts/aide_lite.py", "local-trust", "fixture"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            shell=False,
        )
        self.assertIn("result: PASS_WITH_WARNINGS", result.stdout)
        self.assertIn("capability_label: local_trust_enforcement_v0", result.stdout)
        self.assertIn("evaluation_result: allowed", result.stdout)
        self.assertIn("grant_consumed: true", result.stdout)
        self.assertIn("concurrent_final_use_refused: true", result.stdout)
        self.assertIn("process_launch_count: 0", result.stdout)
        self.assertIn("process_launch_performed: false", result.stdout)
        self.assertIn("network_calls_performed: false", result.stdout)
        self.assertIn("worker_execution_performed: false", result.stdout)


if __name__ == "__main__":
    unittest.main()
