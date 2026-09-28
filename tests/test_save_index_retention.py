# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path

from native_cli import invoke
from tools import json_contract


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"
SCHEMAS = ROOT / "contracts" / "schema" / "factorio"


def call(workspace: Path, *args: str, success: bool = True) -> dict:
    code, stdout, stderr = invoke(["--workspace", str(workspace), *args, "--json"])
    if success and code != 0:
        raise AssertionError(stderr or stdout)
    if not success and code == 0:
        raise AssertionError(f"command unexpectedly succeeded: {stdout}")
    return json.loads(stdout or stderr)


def setup(workspace: Path) -> Path:
    call(workspace, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture")
    call(workspace, "instances", "create", "Save Index", "--id", "save-index", "--install", "fixture")
    return workspace / "instances" / "save-index"


def write_save(path: Path, payload: bytes) -> None:
    entry = zipfile.ZipInfo("world/level-init.dat", (2026, 7, 12, 0, 0, 0))
    entry.external_attr = 0o644 << 16
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(entry, payload)
        archive.writestr("world/control.dat", b"opaque structural fixture")


def validate(value: dict, schema: str) -> list[str]:
    return json_contract.validate(value, json_contract.load_schema(SCHEMAS / schema))


def retention_selection_digest(document: dict) -> str:
    selection = {
        "schema": "facman.retention_selection.v1",
        "transaction_id": document["transaction_id"],
        "command_id": document["command_id"],
        "workspace_id": document["workspace_id"],
        "target": document["target"],
        "sources": document["source_identities"],
        "expected_files": document["expected_files"],
    }
    encoded = json.dumps(selection, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class SaveIndexRetentionTests(unittest.TestCase):
    def test_retention_refuses_active_run_and_save_write_locks(self) -> None:
        for lock_name in ("run.lock", "save.write.lock"):
            with self.subTest(lock_name=lock_name), tempfile.TemporaryDirectory(
                prefix="facman locked save retention "
            ) as value:
                workspace = Path(value)
                instance = setup(workspace)
                old = instance / "saves" / "old.zip"
                new = instance / "saves" / "new.zip"
                write_save(old, b"old save")
                write_save(new, b"new save")
                call(workspace, "saves", "backup", "old", "--instance", "save-index")
                call(workspace, "saves", "backup", "new", "--instance", "save-index")
                stamp = int(time.time()) - 10 * 24 * 60 * 60
                os.utime(instance / "backups" / "old.backup.zip", (stamp, stamp))
                original = old.read_bytes()
                lock_dir = instance / "locks"
                lock_dir.mkdir(exist_ok=True)
                (lock_dir / lock_name).write_text("active\n", encoding="utf-8")

                refused = call(
                    workspace, "saves", "retention", "apply", "--instance", "save-index",
                    "--keep-last", "1", "--min-age-days", "1", success=False,
                )
                self.assertEqual("save_locked", refused["refusal"]["code"])
                self.assertEqual(original, old.read_bytes())
                self.assertTrue(new.is_file())
                self.assertFalse((workspace / "trash" / "saves").exists())

    def test_association_refuses_outside_or_non_exact_version_before_mutation(self) -> None:
        for factorio_version in ("0.18.40", "2.0"):
            with self.subTest(factorio_version=factorio_version):
                with tempfile.TemporaryDirectory(prefix="facman save family refusal ") as value:
                    workspace = Path(value)
                    instance = setup(workspace)
                    save = instance / "saves" / "outside.zip"
                    write_save(save, b"outside family save")
                    record_path = instance / "instance.v1.json"
                    record = json.loads(record_path.read_text(encoding="utf-8"))
                    record["factorio_version"] = factorio_version
                    record_path.write_text(
                        json.dumps(record, separators=(",", ":")) + "\n",
                        encoding="utf-8",
                    )

                    refused = call(
                        workspace,
                        "saves",
                        "associate",
                        "outside.zip",
                        "--instance",
                        "save-index",
                        success=False,
                    )
                    self.assertEqual(
                        "instance_version_family_unsupported",
                        refused["refusal"]["code"],
                    )
                    self.assertFalse(
                        (instance / "metadata" / "save-refs" / "outside.zip.save-ref.v1.json").exists()
                    )

    def test_index_association_drift_and_diff_are_structural_only(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman save index ") as value:
            workspace = Path(value)
            instance = setup(workspace)
            first = instance / "saves" / "first.zip"
            second = instance / "saves" / "second.zip"
            write_save(first, b"first opaque save")
            write_save(second, b"second opaque save")
            before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (first, second)}
            call(workspace, "saves", "backup", "first", "--instance", "save-index")

            indexed = call(workspace, "saves", "index", "--instance", "save-index")
            self.assertEqual([], validate(indexed, "factorio_save_intelligence.v1.schema.json"))
            self.assertEqual("unsupported", indexed["deep_factorio_save_metadata"])
            self.assertFalse(indexed["save_content_modified"])
            records = {record["filename"]: record for record in indexed["saves"]}
            self.assertEqual(before["first.zip"], records["first.zip"]["sha256"])
            self.assertTrue(records["first.zip"]["factorio_save_recognized"])
            self.assertGreater(records["first.zip"]["archive_structure"]["member_count"], 0)
            self.assertEqual("present", records["first.zip"]["backup_sidecar_status"])

            associated = call(
                workspace, "saves", "associate", "first.zip", "--instance", "save-index",
                "--profile", "vanilla", "--source-operation", "test-fixture",
            )
            self.assertEqual("current", associated["saves"][0]["association"]["status"])
            self.assertEqual(before["first.zip"], hashlib.sha256(first.read_bytes()).hexdigest())
            sidecar = instance / "metadata" / "save-refs" / "first.zip.save-ref.v1.json"
            self.assertEqual([], validate(json.loads(sidecar.read_text(encoding="utf-8")), "factorio_save_ref.v1.schema.json"))
            sidecar_document = json.loads(sidecar.read_text(encoding="utf-8"))
            stored_digest = sidecar_document["save_sha256"]
            self.assertEqual("2.0.77", sidecar_document["factorio_version"])
            self.assertEqual("F200", sidecar_document["factorio_version_family"])
            self.assertTrue(sidecar_document["factorio_version_exact_patch"])
            self.assertEqual("unclaimed", sidecar_document["factorio_support_claim"])

            write_save(first, b"changed opaque save")
            verified = call(workspace, "saves", "verify", "first.zip", "--instance", "save-index")
            self.assertEqual("drifted", verified["status"])
            self.assertEqual("drifted", verified["saves"][0]["association"]["status"])
            self.assertEqual(stored_digest, json.loads(sidecar.read_text(encoding="utf-8"))["save_sha256"])

            difference = call(workspace, "saves", "diff", "first.zip", "second.zip", "--instance", "save-index")
            self.assertEqual([], validate(difference, "factorio_save_diff.v1.schema.json"))
            self.assertIn("sha256", {item["field"] for item in difference["differences"]})
            self.assertEqual("unsupported", difference["deep_factorio_save_metadata"])

    def test_retention_moves_only_proven_backup_and_manifest_to_reversible_trash(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman save retention ") as value:
            workspace = Path(value)
            instance = setup(workspace)
            old = instance / "saves" / "old.zip"
            new = instance / "saves" / "new.zip"
            write_save(old, b"old save")
            write_save(new, b"new save")
            call(workspace, "saves", "backup", "old", "--instance", "save-index")
            call(workspace, "saves", "backup", "new", "--instance", "save-index")
            old_backup = instance / "backups" / "old.backup.zip"
            new_backup = instance / "backups" / "new.backup.zip"
            foreign_backup = instance / "backups" / "foreign.zip"
            write_save(foreign_backup, b"unowned backup-shaped file")
            tampered_backup = instance / "backups" / "tampered.zip"
            tampered_backup.write_bytes(old_backup.read_bytes())
            tampered_manifest = json.loads(
                (instance / "backups" / "old.backup.zip.manifest.json").read_text(encoding="utf-8")
            )
            tampered_manifest["destination_path"] = tampered_backup.as_posix()
            tampered_manifest["path"] = tampered_backup.as_posix()
            tampered_manifest["manifest_path"] = (instance / "backups" / "tampered.zip.manifest.json").as_posix()
            tampered_manifest["sha256"] = "0" * 64
            (instance / "backups" / "tampered.zip.manifest.json").write_text(
                json.dumps(tampered_manifest), encoding="utf-8"
            )
            stamp = int(time.time()) - 10 * 24 * 60 * 60
            os.utime(old_backup, (stamp, stamp))
            os.utime(foreign_backup, (stamp, stamp))
            call(workspace, "saves", "associate", "old.zip", "--instance", "save-index")
            old_bytes = old_backup.read_bytes()

            planned = call(
                workspace, "saves", "retention", "plan", "--instance", "save-index",
                "--keep-last", "1", "--min-age-days", "1",
            )
            self.assertEqual([], validate(planned, "factorio_save_retention_report.v1.schema.json"))
            actions = {item["filename"]: item["action"] for item in planned["saves"]}
            self.assertEqual("move_to_trash", actions["old.backup.zip"])
            self.assertEqual("keep", actions["new.backup.zip"])
            self.assertEqual("keep", actions["foreign.zip"])
            self.assertEqual("keep", actions["tampered.zip"])
            self.assertFalse(next(item for item in planned["saves"] if item["filename"] == "foreign.zip")["proven_owned_backup"])
            self.assertFalse(next(item for item in planned["saves"] if item["filename"] == "tampered.zip")["proven_owned_backup"])
            self.assertFalse(planned["permanent_delete"])
            self.assertTrue(planned["reversible"])

            applied = call(
                workspace, "saves", "retention", "apply", "--instance", "save-index",
                "--keep-last", "1", "--min-age-days", "1",
            )
            self.assertTrue(applied["mutation_executed"])
            trash = Path(applied["trash_path"])
            self.assertFalse(old_backup.exists())
            self.assertTrue(old.exists())
            self.assertTrue(new.exists())
            self.assertTrue(new_backup.exists())
            self.assertTrue(foreign_backup.exists())
            self.assertTrue(tampered_backup.exists())
            self.assertEqual(old_bytes, (trash / "old.backup.zip").read_bytes())
            self.assertTrue((trash / "old.backup.zip.manifest.json").is_file())
            self.assertTrue((instance / "metadata" / "save-refs" / "old.zip.save-ref.v1.json").is_file())
            self.assertFalse(applied["save_content_modified"])

    def test_retention_target_substitution_enters_recovery_without_losing_original(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman save substitution ") as value:
            workspace = Path(value)
            instance = setup(workspace)
            old = instance / "saves" / "old.zip"
            new = instance / "saves" / "new.zip"
            write_save(old, b"original save")
            write_save(new, b"new save")
            call(workspace, "saves", "backup", "old", "--instance", "save-index")
            call(workspace, "saves", "backup", "new", "--instance", "save-index")
            old_backup = instance / "backups" / "old.backup.zip"
            stamp = int(time.time()) - 10 * 24 * 60 * 60
            os.utime(old_backup, (stamp, stamp))
            original = old_backup.read_bytes()
            environment = dict(os.environ)
            environment["FACMAN_SAVE_RETENTION_FAULT"] = "target_substitution"
            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "saves", "retention", "apply", "--instance", "save-index",
                "--keep-last", "1", "--min-age-days", "1", "--json",
            ], env=environment)
            self.assertNotEqual(0, code, stderr or stdout)
            self.assertEqual("save_transaction_recovery_required", json.loads(stdout)["refusal"]["code"])
            preserved = list((instance / "backups").glob(".facman-retention-preserved-*-old.backup.zip"))
            self.assertEqual(1, len(preserved))
            self.assertEqual(original, preserved[0].read_bytes())
            self.assertTrue(old.is_file())

            pending = call(workspace, "workspace", "recovery", "inspect")
            transaction = next(item for item in pending["transactions"]
                               if item["command_id"] == "saves.retention.apply")
            recovery = call(workspace, "workspace", "recovery", "apply",
                            transaction["transaction_id"], success=False)
            self.assertEqual("recovery_retention_unsafe", recovery["refusal"]["code"])
            self.assertEqual(original, preserved[0].read_bytes())

    def test_retention_restart_finishes_verified_backup_manifest_pair(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman retention restart ") as value:
            workspace = Path(value)
            instance = setup(workspace)
            old = instance / "saves" / "old.zip"
            new = instance / "saves" / "new.zip"
            write_save(old, b"original save")
            write_save(new, b"new save")
            call(workspace, "saves", "backup", "old", "--instance", "save-index")
            call(workspace, "saves", "backup", "new", "--instance", "save-index")
            backup = instance / "backups" / "old.backup.zip"
            manifest = instance / "backups" / "old.backup.zip.manifest.json"
            backup_bytes = backup.read_bytes()
            manifest_bytes = manifest.read_bytes()
            stamp = int(time.time()) - 10 * 24 * 60 * 60
            os.utime(backup, (stamp, stamp))

            environment = dict(os.environ)
            environment["FACMAN_SAVE_RETENTION_FAULT"] = "process_exit_after_backup_move"
            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "saves", "retention", "apply", "--instance", "save-index",
                "--keep-last", "1", "--min-age-days", "1", "--json",
            ], env=environment)
            self.assertEqual(91, code, stderr or stdout)
            pending = call(workspace, "workspace", "recovery", "inspect")
            transaction = next(item for item in pending["transactions"]
                               if item["command_id"] == "saves.retention.apply")
            trash = Path(transaction["target"])
            self.assertEqual(backup_bytes, (trash / backup.name).read_bytes())
            self.assertEqual(manifest_bytes, manifest.read_bytes())

            plan = call(workspace, "workspace", "recovery", "plan", transaction["transaction_id"])
            self.assertEqual(["verify_and_resume_owned_backup_moves"], plan["transactions"][0]["actions"])
            lock = instance / "locks" / "run.lock"
            lock.parent.mkdir(exist_ok=True)
            lock.write_text("active\n", encoding="utf-8")
            blocked = call(workspace, "workspace", "recovery", "apply",
                           transaction["transaction_id"], success=False)
            self.assertEqual("recovery_retention_locked", blocked["refusal"]["code"])
            self.assertEqual(manifest_bytes, manifest.read_bytes())
            lock.unlink()
            recovered = call(workspace, "workspace", "recovery", "apply", transaction["transaction_id"])
            self.assertEqual("complete", recovered["transactions"][0]["state"])
            self.assertEqual(backup_bytes, (trash / backup.name).read_bytes())
            self.assertEqual(manifest_bytes, (trash / manifest.name).read_bytes())
            self.assertFalse(backup.exists())
            self.assertFalse(manifest.exists())
            self.assertTrue(old.is_file())
            repeated = call(workspace, "workspace", "recovery", "apply", transaction["transaction_id"])
            self.assertEqual("complete", repeated["transactions"][0]["state"])

    def test_retention_restart_before_trash_preserves_sources_and_closes_journal(self) -> None:
        for fault, exit_code in (("process_exit_after_begin", 93),
                                 ("process_exit_before_trash", 92),
                                 ("process_exit_after_marker_create", 94)):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory(
                prefix="facman retention preeffect "
            ) as value:
                workspace = Path(value)
                instance = setup(workspace)
                save = instance / "saves" / "world.zip"
                write_save(save, b"world")
                call(workspace, "saves", "backup", "world", "--instance", "save-index")
                backup = instance / "backups" / "world.backup.zip"
                manifest = instance / "backups" / "world.backup.zip.manifest.json"
                backup_bytes = backup.read_bytes()
                manifest_bytes = manifest.read_bytes()
                environment = dict(os.environ)
                environment["FACMAN_SAVE_RETENTION_FAULT"] = fault
                code, stdout, stderr = invoke([
                    "--workspace", str(workspace), "saves", "retention", "apply", "--instance", "save-index",
                    "--keep-last", "0", "--max-total-bytes", "1", "--json",
                ], env=environment)
                self.assertEqual(exit_code, code, stderr or stdout)
                pending = call(workspace, "workspace", "recovery", "inspect")
                transaction = next(item for item in pending["transactions"]
                                   if item["command_id"] == "saves.retention.apply")
                if fault != "process_exit_after_marker_create":
                    self.assertFalse(Path(transaction["target"]).exists())
                recovered = call(workspace, "workspace", "recovery", "apply", transaction["transaction_id"])
                self.assertEqual("rolled_back", recovered["transactions"][0]["state"])
                self.assertEqual(backup_bytes, backup.read_bytes())
                self.assertEqual(manifest_bytes, manifest.read_bytes())
                self.assertTrue(save.is_file())

    def test_retention_recovery_rejects_journal_claim_over_foreign_backup(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman retention journal tamper ") as value:
            workspace = Path(value)
            instance = setup(workspace)
            for name in ("old", "new"):
                write_save(instance / "saves" / f"{name}.zip", name.encode())
                call(workspace, "saves", "backup", name, "--instance", "save-index")
            old_backup = instance / "backups" / "old.backup.zip"
            old_manifest = instance / "backups" / "old.backup.zip.manifest.json"
            os.utime(old_backup, (time.time() - 10 * 86400, time.time() - 10 * 86400))
            environment = dict(os.environ)
            environment["FACMAN_SAVE_RETENTION_FAULT"] = "process_exit_after_backup_move"
            code, _, stderr = invoke([
                "--workspace", str(workspace), "saves", "retention", "apply", "--instance", "save-index",
                "--keep-last", "1", "--min-age-days", "1", "--json",
            ], env=environment)
            self.assertEqual(91, code, stderr)
            pending = call(workspace, "workspace", "recovery", "inspect")
            transaction = next(item for item in pending["transactions"]
                               if item["command_id"] == "saves.retention.apply")
            trash_backup = Path(transaction["target"]) / old_backup.name
            self.assertTrue(trash_backup.is_file())
            self.assertTrue(old_manifest.is_file())

            foreign = instance / "backups" / "foreign.zip"
            foreign_manifest = instance / "backups" / "foreign.zip.manifest.json"
            write_save(foreign, b"foreign content")
            foreign_manifest.write_text('{"schema":"foreign"}\n', encoding="utf-8")
            journal = next((workspace / "transactions").glob(f'{transaction["transaction_id"]}*.json'))
            document = json.loads(journal.read_text(encoding="utf-8"))
            document["source_identities"] = [str(foreign), str(foreign_manifest)]
            document["expected_files"] = [
                {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                 "size": path.stat().st_size}
                for path in (foreign, foreign_manifest)
            ]
            journal.write_text(json.dumps(document) + "\n", encoding="utf-8")
            refused = call(workspace, "workspace", "recovery", "apply",
                           transaction["transaction_id"], success=False)
            self.assertEqual("recovery_retention_unsafe", refused["refusal"]["code"])
            self.assertTrue(foreign.is_file())
            self.assertTrue(foreign_manifest.is_file())
            self.assertTrue(trash_backup.is_file())

            foreign.write_bytes(b"not a Factorio archive")
            claim = json.loads(old_manifest.read_text(encoding="utf-8"))
            claim.update({
                "save": "foreign.zip",
                "source_path": (instance / "saves" / "foreign.zip").as_posix(),
                "destination_path": foreign.as_posix(),
                "path": foreign.as_posix(),
                "manifest_path": foreign_manifest.as_posix(),
                "sha256": hashlib.sha256(foreign.read_bytes()).hexdigest(),
                "source_size": foreign.stat().st_size,
            })
            foreign_manifest.write_text(json.dumps(claim) + "\n", encoding="utf-8")
            document["expected_files"] = [
                {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                 "size": path.stat().st_size}
                for path in (foreign, foreign_manifest)
            ]
            journal.write_text(json.dumps(document) + "\n", encoding="utf-8")
            refused_archive = call(workspace, "workspace", "recovery", "apply",
                                   transaction["transaction_id"], success=False)
            self.assertEqual("recovery_retention_unsafe", refused_archive["refusal"]["code"])
            self.assertEqual(b"not a Factorio archive", foreign.read_bytes())
            self.assertTrue(trash_backup.is_file())

    def test_retention_recovery_rejects_new_valid_backup_added_to_journal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman retention selection tamper ") as value:
            workspace = Path(value)
            instance = setup(workspace)
            for name in ("old", "new", "other"):
                write_save(instance / "saves" / f"{name}.zip", name.encode())
                call(workspace, "saves", "backup", name, "--instance", "save-index")
            old_backup = instance / "backups" / "old.backup.zip"
            os.utime(old_backup, (time.time() - 10 * 86400, time.time() - 10 * 86400))
            environment = dict(os.environ)
            environment["FACMAN_SAVE_RETENTION_FAULT"] = "process_exit_after_backup_move"
            code, _, stderr = invoke([
                "--workspace", str(workspace), "saves", "retention", "apply", "--instance", "save-index",
                "--keep-last", "2", "--min-age-days", "1", "--json",
            ], env=environment)
            self.assertEqual(91, code, stderr)
            pending = call(workspace, "workspace", "recovery", "inspect")
            transaction = next(item for item in pending["transactions"]
                               if item["command_id"] == "saves.retention.apply")
            journal = next((workspace / "transactions").glob(f'{transaction["transaction_id"]}*.json'))
            document = json.loads(journal.read_text(encoding="utf-8"))
            self.assertEqual(document["operation_context"], retention_selection_digest(document))
            marker = Path(document["target"]) / ".facman-retention-selection.v1"
            self.assertEqual(document["operation_context"] + "\n", marker.read_text(encoding="utf-8"))

            other = instance / "backups" / "other.backup.zip"
            other_manifest = instance / "backups" / "other.backup.zip.manifest.json"
            other_bytes = other.read_bytes()
            document["source_identities"].extend((str(other), str(other_manifest)))
            document["expected_files"].extend(
                {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                 "size": path.stat().st_size}
                for path in (other, other_manifest)
            )
            document["operation_context"] = retention_selection_digest(document)
            journal.write_text(json.dumps(document, separators=(",", ":")) + "\n", encoding="utf-8")
            refused = call(workspace, "workspace", "recovery", "apply",
                           transaction["transaction_id"], success=False)
            self.assertEqual("recovery_retention_unsafe", refused["refusal"]["code"])
            self.assertEqual(other_bytes, other.read_bytes())
            self.assertTrue(other_manifest.is_file())
            self.assertTrue((Path(document["target"]) / old_backup.name).is_file())

    def test_retention_recovery_refuses_lock_created_at_move_boundary(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman retention late lock ") as value:
            workspace = Path(value)
            instance = setup(workspace)
            for name in ("old", "new"):
                write_save(instance / "saves" / f"{name}.zip", name.encode())
                call(workspace, "saves", "backup", name, "--instance", "save-index")
            old_backup = instance / "backups" / "old.backup.zip"
            old_manifest = instance / "backups" / "old.backup.zip.manifest.json"
            os.utime(old_backup, (time.time() - 10 * 86400, time.time() - 10 * 86400))
            environment = dict(os.environ)
            environment["FACMAN_SAVE_RETENTION_FAULT"] = "process_exit_after_backup_move"
            code, _, stderr = invoke([
                "--workspace", str(workspace), "saves", "retention", "apply", "--instance", "save-index",
                "--keep-last", "1", "--min-age-days", "1", "--json",
            ], env=environment)
            self.assertEqual(91, code, stderr)
            pending = call(workspace, "workspace", "recovery", "inspect")
            transaction = next(item for item in pending["transactions"]
                               if item["command_id"] == "saves.retention.apply")
            marker = workspace / ".facman-test-retention-recovery-paused"
            release = workspace / ".facman-test-retention-recovery-release"
            environment.pop("FACMAN_SAVE_RETENTION_FAULT")
            environment["FACMAN_TEST_RETENTION_RECOVERY_PAUSE"] = "1"
            outcome: list[tuple[int, str, str]] = []
            worker = threading.Thread(target=lambda: outcome.append(invoke([
                "--workspace", str(workspace), "workspace", "recovery", "apply",
                transaction["transaction_id"], "--json",
            ], env=environment)))
            worker.start()
            for _ in range(100):
                if marker.is_file():
                    break
                time.sleep(0.05)
            self.assertTrue(marker.is_file(), "recovery did not reach its move boundary")
            lock = instance / "locks" / "run.lock"
            lock.parent.mkdir(exist_ok=True)
            lock.write_text("active\n", encoding="utf-8")
            release.write_text("continue\n", encoding="utf-8")
            worker.join(timeout=10)
            self.assertFalse(worker.is_alive())
            self.assertEqual(1, len(outcome))
            self.assertNotEqual(0, outcome[0][0])
            self.assertEqual("recovery_retention_locked", json.loads(outcome[0][1])["refusal"]["code"])
            self.assertTrue(old_manifest.is_file())
            lock.unlink()
            recovered = call(workspace, "workspace", "recovery", "apply", transaction["transaction_id"])
            self.assertEqual("complete", recovered["transactions"][0]["state"])

    def test_retention_recovery_cannot_close_live_apply_before_first_move(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman retention live writer ") as value:
            workspace = Path(value)
            instance = setup(workspace)
            write_save(instance / "saves" / "world.zip", b"world")
            call(workspace, "saves", "backup", "world", "--instance", "save-index")
            backup = instance / "backups" / "world.backup.zip"
            environment = dict(os.environ)
            environment["FACMAN_TEST_RETENTION_APPLY_PAUSE"] = "1"
            result: list[tuple[int, str, str]] = []
            worker = threading.Thread(target=lambda: result.append(invoke([
                "--workspace", str(workspace), "saves", "retention", "apply", "--instance", "save-index",
                "--keep-last", "0", "--max-total-bytes", "1", "--json",
            ], env=environment)))
            worker.start()
            marker = workspace / ".facman-test-retention-apply-paused"
            release = workspace / ".facman-test-retention-apply-release"
            try:
                for _ in range(100):
                    if marker.is_file():
                        break
                    time.sleep(0.05)
                self.assertTrue(marker.is_file(), "apply did not reach the held pre-move boundary")
                pending = call(workspace, "workspace", "recovery", "inspect")
                transaction = next(item for item in pending["transactions"]
                                   if item["command_id"] == "saves.retention.apply")
                refused = call(workspace, "workspace", "recovery", "apply",
                               transaction["transaction_id"], success=False)
                self.assertEqual("recovery_lock_contended", refused["refusal"]["code"])
                self.assertTrue(backup.is_file())
            finally:
                release.write_text("continue\n", encoding="utf-8")
                worker.join(timeout=10)
            self.assertFalse(worker.is_alive())
            self.assertEqual(1, len(result))
            self.assertEqual(0, result[0][0], result[0][2] or result[0][1])
            self.assertFalse(backup.exists())
            repeated = call(workspace, "workspace", "recovery", "apply", transaction["transaction_id"])
            self.assertEqual("complete", repeated["transactions"][0]["state"])

    def test_retention_refuses_unowned_trash_parent_without_moving_backup(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman save trash refusal ") as value:
            workspace = Path(value)
            instance = setup(workspace)
            save = instance / "saves" / "original.zip"
            write_save(save, b"original save")
            call(workspace, "saves", "backup", "original", "--instance", "save-index")
            backup = instance / "backups" / "original.backup.zip"
            original = backup.read_bytes()
            blocked_trash = workspace / "trash"
            blocked_trash.write_text("unowned obstruction\n", encoding="utf-8")

            refused = call(
                workspace, "saves", "retention", "apply", "--instance", "save-index",
                "--keep-last", "0", "--max-total-bytes", "1", success=False,
            )
            self.assertEqual("save_retention_failed", refused["refusal"]["code"])
            self.assertEqual(original, backup.read_bytes())
            self.assertTrue((instance / "backups" / "original.backup.zip.manifest.json").is_file())
            self.assertTrue(save.is_file())
            self.assertEqual("unowned obstruction\n", blocked_trash.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
