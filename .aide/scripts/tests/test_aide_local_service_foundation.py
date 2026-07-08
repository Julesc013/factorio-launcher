from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from core.service.artifact_store import ArtifactStore, ArtifactStoreError, sha256_bytes
from core.service.local_service import fixture
from core.service.sqlite_store import LocalServiceError, SQLiteStore, digest_json


class LocalServiceFoundationTests(unittest.TestCase):
    def test_migrations_are_idempotent_and_future_migration_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "state.sqlite")
            try:
                self.assertEqual(store.initialize(), 1)
                self.assertEqual(store.initialize(), 1)
                store.force_schema_version_for_test(999)
                with self.assertRaisesRegex(LocalServiceError, "future_migration"):
                    store.initialize()
            finally:
                store.close()

    def test_objects_events_version_conflict_and_atomic_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "state.sqlite")
            try:
                store.initialize()
                created = store.put_object("aide://object/one", "FixtureObject", {"value": 1})
                self.assertEqual(created.version, 1)
                self.assertEqual(store.get_object("aide://object/one").body, {"value": 1})
                self.assertEqual(len(store.list_objects(kind="FixtureObject")), 1)
                with self.assertRaisesRegex(LocalServiceError, "resource_version_conflict"):
                    store.put_object("aide://object/one", "FixtureObject", {"value": 2}, expected_version=99)
                updated, sequence = store.put_object_with_event(
                    "aide://object/one",
                    "FixtureObject",
                    {"value": 2},
                    event_ref="aide://event/one-updated",
                    event_type="object.updated",
                    expected_version=1,
                )
                self.assertEqual(updated.version, 2)
                self.assertEqual(sequence, 1)
                with self.assertRaisesRegex(LocalServiceError, "injected_atomic_failure"):
                    store.put_object_with_event(
                        "aide://object/rollback",
                        "FixtureObject",
                        {"value": "bad"},
                        event_ref="aide://event/rollback",
                        event_type="object.updated",
                        fail_after_object=True,
                    )
                with self.assertRaisesRegex(LocalServiceError, "object_missing"):
                    store.get_object("aide://object/rollback")
            finally:
                store.close()

    def test_events_cursors_and_idempotency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SQLiteStore(Path(tmp) / "state.sqlite")
            try:
                store.initialize()
                first = store.append_event("aide://event/one", "event.one", "aide://subject/one", {"n": 1})
                second = store.append_event("aide://event/two", "event.two", "aide://subject/one", {"n": 2})
                self.assertEqual([item["sequence"] for item in store.read_events_after(0)], [first, second])
                self.assertEqual([item["sequence"] for item in store.read_events_after(first)], [second])
                self.assertEqual(store.ack_cursor("aide://cursor/test", second)["last_sequence"], second)
                request_digest = digest_json({"request": "same"})
                self.assertEqual(store.record_idempotency("key", request_digest, "aide://result/one")["status"], "recorded")
                self.assertEqual(store.record_idempotency("key", request_digest, "aide://result/one")["status"], "duplicate")
                with self.assertRaisesRegex(LocalServiceError, "idempotency_conflict"):
                    store.record_idempotency("key", digest_json({"request": "different"}), "aide://result/one")
            finally:
                store.close()

    def test_artifact_store_integrity_dedupe_and_traversal_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = ArtifactStore(Path(tmp))
            payload = b"payload\n"
            first = store.write(payload)
            second = store.write(payload)
            self.assertEqual(first.digest, sha256_bytes(payload))
            self.assertTrue(second.deduplicated)
            self.assertEqual(store.read(first.digest), payload)
            with self.assertRaisesRegex(ArtifactStoreError, "artifact_digest_mismatch"):
                store.write(payload, expected_digest="sha256:" + ("0" * 64))
            with self.assertRaisesRegex(ArtifactStoreError, "artifact_digest_invalid"):
                store.read("sha256:../escape")

    def test_reopen_persistence_and_corruption_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state.sqlite"
            store = SQLiteStore(db)
            try:
                store.initialize()
                store.put_object("aide://object/persisted", "FixtureObject", {"ok": True})
                store.append_event("aide://event/persisted", "event.persisted", "aide://object/persisted", {"ok": True})
            finally:
                store.close()
            reopened = SQLiteStore(db)
            try:
                self.assertEqual(reopened.get_object("aide://object/persisted").body, {"ok": True})
                self.assertEqual(len(reopened.read_events_after(0)), 1)
            finally:
                reopened.close()
            corrupt = Path(tmp) / "corrupt.sqlite"
            corrupt.write_text("not sqlite", encoding="utf-8")
            bad = SQLiteStore(corrupt)
            try:
                with self.assertRaises(LocalServiceError):
                    bad.health()
            finally:
                bad.close()

    def test_fixture_report_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = fixture(REPO_ROOT, state_root=Path(tmp), write_reports=False)
            self.assertEqual(report["status"], "PASS_WITH_WARNINGS")
            self.assertTrue(report["migration_idempotent"])
            self.assertTrue(report["future_migration_refused"])
            self.assertTrue(report["object_put_get_list"])
            self.assertTrue(report["rollback_on_error"])
            self.assertEqual(report["event_delivery_semantics"], "at_least_once")
            self.assertTrue(report["reopen_persistence"])
            self.assertFalse(report["network_listener_opened"])
            self.assertFalse(report["worker_execution_implemented"])
            self.assertFalse(report["provider_model_calls_performed"])

    def test_cli_init_fixture_uses_temp_state_and_no_network(self) -> None:
        result = subprocess.run(
            [sys.executable, ".aide/scripts/aide_lite.py", "local-service", "init-fixture"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            shell=False,
        )
        self.assertIn("result: PASS_WITH_WARNINGS", result.stdout)
        self.assertIn("state_root_is_temp: true", result.stdout)
        self.assertIn("network_listener_opened: false", result.stdout)


if __name__ == "__main__":
    unittest.main()
