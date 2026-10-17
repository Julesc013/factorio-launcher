# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Explicit local installation reconstruction and retained recovery bindings."""
from __future__ import annotations

import json
import os
import shutil
import tempfile
import threading
import time
import unittest
from pathlib import Path

from native_cli import invoke
from test_instance_snapshots import call, refuse, fixture, FIXTURE_INSTALL, assert_schema
from test_local_modset_solver import snapshot


class SnapshotLocalInstallTests(unittest.TestCase):
    def prepare(self, root: Path) -> tuple[Path, Path, Path]:
        source, destination, local = root / "source", root / "destination", root / "local-game"
        fixture(source)
        call(source, "snapshots", "create", "main", "world", "--save", "starter.zip")
        shutil.copytree(FIXTURE_INSTALL, local)
        call(destination, "installs", "import", str(local), "--id", "local")
        return source / "snapshots/main/world.zip", destination, local

    def restore(self, workspace: Path, archive: Path, boundary: str) -> tuple[Path, dict]:
        environment = dict(os.environ, **{boundary: "1"})
        code, _, _ = invoke(["--workspace", str(workspace), "snapshots", "restore", str(archive),
                            "restored", "--install", "local", "--json"], env=environment)
        self.assertIn(code, (86, 87))
        journals = [(path, json.loads(path.read_bytes())) for path in
                    (workspace / "transactions").glob("*.transaction.v1.json")]
        return next((path, record) for path, record in journals if record["command_id"] == "snapshots.restore")

    def test_explicit_selection_binds_local_manifest_configuration_and_preserves_source(self) -> None:
        with tempfile.TemporaryDirectory(prefix="snapshot-local-") as value:
            archive, workspace, local = self.prepare(Path(value))
            original = snapshot(archive.parents[2]), snapshot(local)
            before = snapshot(workspace)
            self.assertEqual("snapshot_install_incompatible", refuse(workspace, "snapshots", "restore", str(archive), "default")["refusal"]["code"])
            self.assertEqual(before, snapshot(workspace))
            result = call(workspace, "snapshots", "restore", str(archive), "restored", "--install", "local")
            assert_schema(self, result, "factorio_snapshot_report.v1.schema.json")
            target = workspace / "instances/restored"
            manifest = json.loads((target / "instance.v1.json").read_bytes())
            self.assertEqual(("local", "fixture", "world"), (manifest["install_ref"], manifest["restored_from_install_ref"], manifest["restored_from_snapshot"]))
            self.assertIn(str(local).replace("\\", "/"), (target / "config/config.ini").read_text().replace("\\", "/"))
            self.assertEqual(original, (snapshot(archive.parents[2]), snapshot(local)))
            frozen = snapshot(workspace)
            self.assertEqual("snapshot_restore_target_exists", refuse(workspace, "snapshots", "restore", str(archive), "restored", "--install", "local")["refusal"]["code"])
            self.assertEqual(frozen, snapshot(workspace))

    def test_missing_incompatible_invalid_and_default_compatible_installations(self) -> None:
        with tempfile.TemporaryDirectory(prefix="snapshot-install-gates-") as value:
            archive, workspace, local = self.prepare(Path(value))
            before = snapshot(workspace)
            code, _, _ = invoke(["--workspace", str(workspace), "snapshots", "restore", str(archive), "restored", "--install", "--json"])
            self.assertNotEqual(0, code)
            self.assertEqual(before, snapshot(workspace))
            for selected in ("missing", "../local"):
                before = snapshot(workspace)
                refused = refuse(workspace, "snapshots", "restore", str(archive), "restored", "--install", selected)
                self.assertIn(refused["refusal"]["code"], ("snapshot_install_incompatible", "invalid_identifier", "invalid_request"))
                self.assertEqual(before, snapshot(workspace))
            record = workspace / "installs/refs/local.json"
            original = record.read_bytes()
            changed = json.loads(original); changed["version"] = "2.0.78"
            record.write_text(json.dumps(changed))
            before = snapshot(workspace)
            self.assertEqual("snapshot_install_incompatible", refuse(workspace, "snapshots", "restore", str(archive), "restored", "--install", "local")["refusal"]["code"])
            self.assertEqual(before, snapshot(workspace))
            record.write_bytes(original)
            call(workspace, "installs", "import", str(local), "--id", "fixture")
            call(workspace, "snapshots", "restore", str(archive), "default")
            self.assertEqual("fixture", json.loads((workspace / "instances/default/instance.v1.json").read_bytes())["install_ref"])

    def test_prepublication_install_record_drift_preserves_staging_and_blocks_recovery(self) -> None:
        with tempfile.TemporaryDirectory(prefix="snapshot-precommit-") as value:
            archive, workspace, _ = self.prepare(Path(value))
            result = []
            worker = threading.Thread(target=lambda: result.append(invoke([
                "--workspace", str(workspace), "snapshots", "restore", str(archive), "restored", "--install", "local", "--json"],
                env=dict(os.environ, FACMAN_TEST_SNAPSHOT_RESTORE_BEFORE_PUBLICATION_PAUSE="1"))))
            worker.start()
            try:
                marker = workspace / ".facman-test-snapshot-restore-before-publication"
                for _ in range(100):
                    if marker.is_file(): break
                    time.sleep(0.03)
                self.assertTrue(marker.is_file())
                pending = call(workspace, "workspace", "recovery", "inspect")["transactions"]
                live_tx = next(item["transaction_id"] for item in pending if item["command_id"] == "snapshots.restore")
                live_lock = workspace / "transactions" / (live_tx + ".transaction.v1.json.recovery.lock")
                excluded = live_lock if os.name == "nt" else None
                lock_identity = live_lock.stat()
                if os.name == "nt":
                    with self.assertRaises(PermissionError): live_lock.read_bytes()
                live_bytes = snapshot(workspace, excluded)
                live = refuse(workspace, "workspace", "recovery", "apply", live_tx)
                self.assertEqual("recovery_lock_contended", live["refusal"]["code"])
                self.assertEqual(live_bytes, snapshot(workspace, excluded))
                after_lock = live_lock.stat()
                self.assertEqual((lock_identity.st_dev, lock_identity.st_ino, lock_identity.st_size),
                                 (after_lock.st_dev, after_lock.st_ino, after_lock.st_size))
                record = workspace / "installs/refs/local.json"
                original = record.read_bytes(); record.write_bytes(original + b" ")
                (workspace / ".facman-test-snapshot-restore-publication-release").write_text("go")
            finally:
                worker.join(10)
            self.assertFalse(worker.is_alive())
            self.assertEqual("snapshot_restore_binding_changed", json.loads(result[0][1])["refusal"]["code"])
            self.assertFalse((workspace / "instances/restored").exists())
            pending = call(workspace, "workspace", "recovery", "inspect")["transactions"]
            tx = next(item["transaction_id"] for item in pending if item["command_id"] == "snapshots.restore")
            retained = snapshot(workspace)
            self.assertEqual("recovery_snapshot_binding_changed", refuse(workspace, "workspace", "recovery", "apply", tx)["refusal"]["code"])
            self.assertEqual(retained, snapshot(workspace))
            record.write_bytes(original)
            recovered = call(workspace, "workspace", "recovery", "apply", tx)
            self.assertEqual("rolled_back", recovered["transactions"][0]["state"])

    def test_interrupted_publication_recovers_exact_selected_identity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="snapshot-recover-local-") as value:
            archive, workspace, local = self.prepare(Path(value))
            source = archive.read_bytes(), snapshot(local)
            _, journal = self.restore(workspace, archive, "FACMAN_TEST_SNAPSHOT_RESTORE_EXIT_AFTER_PUBLICATION")
            context = json.loads(journal["operation_context"])
            assert_schema(self, context, "facman_snapshot_restore_binding.v1.schema.json")
            self.assertEqual("local", context["install_id"])
            self.assertEqual("fixture", context["original_install_id"])
            target = workspace / "instances/restored"
            content = snapshot(target)
            result = call(workspace, "workspace", "recovery", "apply", journal["transaction_id"])
            self.assertEqual("complete", result["transactions"][0]["state"])
            self.assertEqual({p: b for p, b in content.items() if not p.startswith(".facman-")}, snapshot(target))
            self.assertEqual("local", json.loads((target / "instance.v1.json").read_bytes())["install_ref"])
            self.assertEqual(source, (archive.read_bytes(), snapshot(local)))
            before = snapshot(workspace)
            call(workspace, "workspace", "recovery", "apply", journal["transaction_id"])
            self.assertEqual(before, snapshot(workspace))

    def test_recovery_refuses_source_record_context_and_target_substitution_without_cleanup(self) -> None:
        cases = ("archive", "record", "record-object", "base", "context", "partial-context", "nested-context", "closure", "lock", "target-file", "target-object", "staging-file", "staging-missing", "collision")
        for kind in cases:
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix="snapshot-recovery-gate-") as value:
                archive, workspace, local = self.prepare(Path(value))
                before_publication = kind in ("staging-file", "staging-missing", "collision")
                journal_path, journal = self.restore(workspace, archive, "FACMAN_TEST_SNAPSHOT_RESTORE_EXIT_AFTER_VERIFIED" if before_publication else "FACMAN_TEST_SNAPSHOT_RESTORE_EXIT_AFTER_PUBLICATION")
                target = workspace / "instances/restored"
                if kind == "archive": archive.write_bytes(archive.read_bytes() + b" ")
                elif kind in ("record", "record-object"):
                    record = workspace / "installs/refs/local.json"
                    if kind == "record": record.write_bytes(record.read_bytes() + b" ")
                    else:
                        replacement = record.with_suffix(".next"); replacement.write_bytes(record.read_bytes()); replacement.replace(record)
                elif kind == "base": (local / "data/base/info.json").write_bytes(b'{"name":"base","version":"2.0.78"}')
                elif kind in ("context", "partial-context", "nested-context", "closure"):
                    journal["operation_context"] = "" if kind == "context" else '{"schema":"facman.snapshot_restore_binding.v1"}'
                    if kind in ("nested-context", "closure"):
                        original = json.loads(journal_path.read_bytes())["operation_context"]
                        context = json.loads(original)
                        context["installation" if kind == "nested-context" else "closure_sha256"] = "{}" if kind == "nested-context" else "invalid"
                        journal["operation_context"] = json.dumps(context)
                    journal_path.write_text(json.dumps(journal))
                elif kind == "lock": Path(str(journal_path) + ".recovery.lock").write_text("foreign lock metadata")
                elif kind == "target-file": (target / "config/config.ini").write_bytes(b"foreign")
                elif kind == "target-object":
                    target.rename(target.with_name("retained")); shutil.copytree(target.with_name("retained"), target)
                elif kind == "staging-file": (Path(journal["owned_staging_roots"][0]) / "config/config.ini").write_bytes(b"foreign")
                elif kind == "staging-missing": Path(journal["owned_staging_roots"][0]).rename(workspace / "instances/retained-staging")
                else: target.mkdir(); (target / "foreign.dat").write_bytes(b"foreign")
                retained = snapshot(workspace), archive.read_bytes()
                refused = refuse(workspace, "workspace", "recovery", "apply", journal["transaction_id"])
                self.assertIn(refused["refusal"]["code"], ("recovery_snapshot_binding_changed", "recovery_snapshot_target_unsafe", "recovery_lock_contended"))
                self.assertEqual(retained, (snapshot(workspace), archive.read_bytes()))

    def test_recovery_rechecks_journal_target_and_stage_after_acquiring_shared_lease(self) -> None:
        for kind in ("target", "stage", "journal"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix="snapshot-late-recovery-") as value:
                archive, workspace, _ = self.prepare(Path(value))
                journal_path, journal = self.restore(workspace, archive, "FACMAN_TEST_SNAPSHOT_RESTORE_EXIT_AFTER_VERIFIED")
                result = []
                worker = threading.Thread(target=lambda: result.append(invoke([
                    "--workspace", str(workspace), "workspace", "recovery", "apply", journal["transaction_id"], "--json"],
                    env=dict(os.environ, FACMAN_TEST_SNAPSHOT_RECOVERY_BEFORE_LOCK_PAUSE="1"))))
                worker.start()
                release = workspace / ".facman-test-snapshot-recovery-lock-release"
                try:
                    marker = workspace / ".facman-test-snapshot-recovery-before-lock"
                    for _ in range(100):
                        if marker.is_file(): break
                        time.sleep(0.03)
                    self.assertTrue(marker.is_file())
                    if kind == "target":
                        target = workspace / "instances/restored"; target.mkdir(); (target / "foreign").write_bytes(b"foreign")
                    elif kind == "stage": (Path(journal["owned_staging_roots"][0]) / "config/config.ini").write_bytes(b"foreign")
                    else:
                        journal["operation_context"] = "{}"; journal_path.write_text(json.dumps(journal))
                    # Freeze every retained byte before the owner can acquire
                    # its Windows exclusive lease; the release file is ours.
                    retained = snapshot(workspace)
                    retained[release.relative_to(workspace).as_posix()] = b"go"
                finally:
                    release.write_bytes(b"go")
                    worker.join(10)
                self.assertFalse(worker.is_alive())
                self.assertEqual("recovery_snapshot_binding_changed", json.loads(result[0][1])["refusal"]["code"])
                self.assertEqual(retained, snapshot(workspace))

    def test_historical_unbound_default_journal_keeps_legacy_rollback_behavior(self) -> None:
        with tempfile.TemporaryDirectory(prefix="snapshot-legacy-") as value:
            archive, workspace, _ = self.prepare(Path(value))
            path, journal = self.restore(workspace, archive, "FACMAN_TEST_SNAPSHOT_RESTORE_EXIT_AFTER_VERIFIED")
            # Construct the historical journal shape explicitly; this does not
            # claim that old transactions carried the new installation binding.
            journal["commit_strategy"] = "verified_snapshot_extract_regenerate_atomic_no_replace"
            journal["operation_context"] = ""
            journal["effect_file_identity"] = ""
            path.write_text(json.dumps(journal))
            lock = Path(str(path) + ".recovery.lock")
            metadata = json.loads(lock.read_bytes())
            self.assertEqual("facman.snapshot_restore_recovery_lock.v1", metadata["schema"])
            self.assertEqual(journal["transaction_id"], metadata["transaction_id"])
            self.assertEqual(journal["marker_nonce"], metadata["marker_nonce"])
            # The historical implementation never wrote this new lease. Remove
            # only this exact test-owned new lock to construct its full old shape.
            lock.unlink()
            (workspace / "installs/refs/local.json").unlink()
            result = call(workspace, "workspace", "recovery", "apply", journal["transaction_id"])
            self.assertEqual("rolled_back", result["transactions"][0]["state"])

    @unittest.skipUnless(os.name == "posix", "unsupported: Same-inode concurrent lock-byte edits require POSIX; Windows denied-sharing behavior does not qualify this case")
    def test_same_inode_foreign_lock_metadata_survives_live_writer_and_recovery(self) -> None:
        for owner in ("writer", "recovery"):
            with self.subTest(owner=owner), tempfile.TemporaryDirectory(prefix="snapshot-lock-bytes-") as value:
                archive, workspace, _ = self.prepare(Path(value))
                if owner == "writer":
                    args = ["--workspace", str(workspace), "snapshots", "restore", str(archive), "restored", "--install", "local", "--json"]
                    environment = dict(os.environ, FACMAN_TEST_SNAPSHOT_RESTORE_BEFORE_PUBLICATION_PAUSE="1")
                    marker = workspace / ".facman-test-snapshot-restore-before-publication"
                    release = workspace / ".facman-test-snapshot-restore-publication-release"
                else:
                    _, journal = self.restore(workspace, archive, "FACMAN_TEST_SNAPSHOT_RESTORE_EXIT_AFTER_VERIFIED")
                    args = ["--workspace", str(workspace), "workspace", "recovery", "apply", journal["transaction_id"], "--json"]
                    environment = dict(os.environ, FACMAN_TEST_SNAPSHOT_RECOVERY_AFTER_LEASE_PAUSE="1")
                    marker = workspace / ".facman-test-snapshot-recovery-after-lease"
                    release = workspace / ".facman-test-snapshot-recovery-lease-release"
                result = []
                worker = threading.Thread(target=lambda: result.append(invoke(args, env=environment)))
                worker.start()
                try:
                    for _ in range(150):
                        if marker.is_file(): break
                        time.sleep(0.03)
                    self.assertTrue(marker.is_file())
                    path = next(path for path in (workspace / "transactions").glob("*.transaction.v1.json")
                                if json.loads(path.read_bytes())["command_id"] == "snapshots.restore")
                    lock = Path(str(path) + ".recovery.lock")
                    native_before = (lock.stat().st_dev, lock.stat().st_ino)
                    foreign = b"foreign same-inode lease metadata\n"
                    with lock.open("r+b") as output:
                        output.write(foreign); output.truncate(); output.flush(); os.fsync(output.fileno())
                    self.assertEqual(native_before, (lock.stat().st_dev, lock.stat().st_ino))
                    release.write_text("go")
                    retained = snapshot(workspace)
                finally:
                    worker.join(10)
                self.assertFalse(worker.is_alive())
                expected = "snapshot_restore_lock_changed" if owner == "writer" else "recovery_snapshot_binding_changed"
                self.assertEqual(expected, json.loads(result[0][1])["refusal"]["code"])
                self.assertEqual(retained, snapshot(workspace))
                self.assertEqual(foreign, lock.read_bytes())


if __name__ == "__main__":
    unittest.main()
