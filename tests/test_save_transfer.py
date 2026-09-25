# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

from native_cli import facman_executable, invoke
from tools import json_contract

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"
SAVE_FIXTURES = ROOT / "tests" / "fixtures" / "factorio_saves"


class SaveTransferTests(unittest.TestCase):
    def prepare(self, workspace: Path) -> None:
        code, _stdout, stderr = invoke(
            ["--workspace", str(workspace), "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture"]
        )
        self.assertEqual(code, 0, stderr)
        for name in ("Source World", "Target World"):
            code, _stdout, stderr = invoke(
                ["--workspace", str(workspace), "instances", "create", name, "--install", "fixture"]
            )
            self.assertEqual(code, 0, stderr)

    def test_deflated_save_recognition_is_structural_and_never_claims_deep_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.prepare(workspace)
            save = workspace / "instances" / "source-world" / "saves" / "deflated.zip"
            with zipfile.ZipFile(save, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("level-init.dat", b"factorio-shaped fixture")
                archive.writestr("mod-list.json", b'{"mods":[]}')

            code, stdout, stderr = invoke(
                ["--workspace", tmp, "saves", "list", "--instance", "source-world", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            result = json.loads(stdout)
            listed = result["saves"][0]
            self.assertTrue(listed["archive_structurally_valid"])
            self.assertTrue(listed["factorio_save_recognized"])
            self.assertFalse(listed["deep_save_semantics_inspected"])
            schema = json.loads(
                (ROOT / "contracts/schema/factorio/factorio_saves.v1.schema.json").read_text(encoding="utf-8")
            )
            self.assertEqual(json_contract.validate(result, schema), [])

            backup = workspace / "deflated.backup.zip"
            code, stdout, stderr = invoke(
                [
                    "--workspace",
                    tmp,
                    "saves",
                    "backup",
                    "deflated",
                    "--instance",
                    "source-world",
                    "--to",
                    str(backup),
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            backed_up = json.loads(stdout)
            self.assertFalse(backed_up["deep_save_semantics_inspected"])
            self.assertEqual(backup.read_bytes(), save.read_bytes())

    def test_export_hash_closure_and_import_tamper_refusal_leave_no_partial_instance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.prepare(workspace)
            save = workspace / "instances" / "source-world" / "saves" / "world.zip"
            with zipfile.ZipFile(save, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("level-init.dat", b"world")
            pack = workspace / "portable.zip"
            code, stdout, stderr = invoke(
                ["--workspace", tmp, "export", "instance", "source-world", str(pack), "--json"]
            )
            self.assertEqual(code, 0, stderr)
            exported = json.loads(stdout)
            self.assertEqual(exported["command"], "instance.export")
            self.assertTrue(exported["file_hash_closure"])
            with zipfile.ZipFile(pack) as archive:
                manifest = json.loads(archive.read("manifest/export.v1.json"))
                for item in manifest["file_hashes"]:
                    self.assertEqual(hashlib.sha256(archive.read(item["path"])).hexdigest(), item["sha256"])
                entries = {name: archive.read(name) for name in archive.namelist()}

            entries["saves/world.zip"] += b"tampered"
            tampered = workspace / "tampered.zip"
            with zipfile.ZipFile(tampered, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name, payload in entries.items():
                    archive.writestr(name, payload)
            code, stdout, _stderr = invoke(
                ["--workspace", tmp, "import", "instance", str(tampered), "--id", "tampered-world", "--json"]
            )
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["refusal"]["code"], "instance_import_manifest_invalid")
            self.assertFalse((workspace / "instances" / "tampered-world").exists())
            self.assertEqual(list((workspace / "instances").glob(".facman-instance-import-*")), [])

    def test_unsafe_transfer_entry_refuses_before_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.prepare(workspace)
            pack = workspace / "unsafe.zip"
            with zipfile.ZipFile(pack, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("../outside.txt", b"escape")
                archive.writestr("instance.v1.json", b"{}")
            outside = workspace / "outside.txt"
            code, stdout, _stderr = invoke(
                ["--workspace", tmp, "import", "instance", str(pack), "--id", "unsafe-world", "--json"]
            )
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["refusal"]["code"], "unsafe_archive_path")
            self.assertFalse(outside.exists())
            self.assertFalse((workspace / "instances" / "unsafe-world").exists())

    def test_import_refuses_instance_outside_target_version_families(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.prepare(workspace)
            pack = workspace / "portable.zip"
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "export", "instance", "source-world", str(pack), "--json"]
            )
            self.assertEqual(code, 0, stderr)
            with zipfile.ZipFile(pack) as archive:
                entries = {name: archive.read(name) for name in archive.namelist()}
            instance = json.loads(entries["instance.v1.json"])
            instance["factorio_version"] = "0.18.40"
            entries["instance.v1.json"] = (json.dumps(instance, separators=(",", ":")) + "\n").encode()
            manifest = json.loads(entries["manifest/export.v1.json"])
            for item in manifest["file_hashes"]:
                if item["path"] == "instance.v1.json":
                    item["size"] = len(entries["instance.v1.json"])
                    item["sha256"] = hashlib.sha256(entries["instance.v1.json"]).hexdigest()
            entries["manifest/export.v1.json"] = (json.dumps(manifest, separators=(",", ":")) + "\n").encode()
            outside = workspace / "outside-family.zip"
            with zipfile.ZipFile(outside, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name, payload in entries.items():
                    archive.writestr(name, payload)

            code, stdout, _stderr = invoke(
                ["--workspace", tmp, "import", "instance", str(outside), "--id", "outside", "--json"]
            )
            self.assertEqual(code, 1)
            self.assertEqual(
                "instance_version_family_unsupported",
                json.loads(stdout)["refusal"]["code"],
            )
            self.assertFalse((workspace / "instances" / "outside").exists())

    def test_import_fault_matrix_leaves_no_partial_or_a_recognized_committed_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.prepare(workspace)
            save = workspace / "instances" / "source-world" / "saves" / "world.zip"
            with zipfile.ZipFile(save, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("level-init.dat", b"fault matrix")
            pack = workspace / "portable.zip"
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "export", "instance", "source-world", str(pack), "--json"]
            )
            self.assertEqual(code, 0, stderr)

            stages = (
                "after_manifest_read",
                "after_target_planning",
                "during_first_file",
                "during_middle_file",
                "after_extraction",
                "after_verification",
                "before_commit",
                "after_commit_before_journal_close",
            )
            try:
                for index, stage in enumerate(stages):
                    instance_id = f"fault-{index}"
                    os.environ["FACMAN_TEST_SAVE_TRANSFER_FAIL_STAGE"] = stage
                    code, stdout, _stderr = invoke(
                        ["--workspace", tmp, "import", "instance", str(pack), "--id", instance_id, "--json"]
                    )
                    self.assertEqual(code, 1, stage)
                    refusal = json.loads(stdout)
                    target = workspace / "instances" / instance_id
                    if stage == "after_commit_before_journal_close":
                        self.assertEqual(refusal["refusal"]["code"], "transaction_recovery_required")
                        self.assertTrue(target.is_dir())
                        self.assertTrue((target / ".facman-archive-staging.v1").is_file())
                        self.assertTrue((target / "instance.v1.json").is_file())
                    else:
                        self.assertFalse(target.exists(), stage)
                    self.assertEqual(list((workspace / "instances").glob(".facman-instance-import-*")), [])
            finally:
                os.environ.pop("FACMAN_TEST_SAVE_TRANSFER_FAIL_STAGE", None)
            code, stdout, stderr = invoke(
                ["--workspace", tmp, "workspace", "recovery", "inspect", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            committed = next(
                item for item in json.loads(stdout)["transactions"] if Path(item["target"]).name == "fault-7"
            )
            code, stdout, stderr = invoke(
                [
                    "--workspace",
                    tmp,
                    "workspace",
                    "recovery",
                    "apply",
                    committed["transaction_id"],
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["transactions"][0]["state"], "complete")
            self.assertFalse((workspace / "instances" / "fault-7" / ".facman-archive-staging.v1").exists())

    def test_backup_refuses_multiply_linked_source_before_destination(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.prepare(workspace)
            external = workspace / "external.zip"
            with zipfile.ZipFile(external, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("level-init.dat", b"linked")
            linked = workspace / "instances" / "source-world" / "saves" / "linked.zip"
            try:
                os.link(external, linked)
            except OSError as error:
                self.skipTest(f"unsupported: hard links unavailable: {error}")
            destination = workspace / "linked.backup.zip"
            code, stdout, _stderr = invoke(
                [
                    "--workspace",
                    tmp,
                    "saves",
                    "backup",
                    "linked",
                    "--instance",
                    "source-world",
                    "--to",
                    str(destination),
                    "--json",
                ]
            )
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["refusal"]["code"], "save_source_changed")
            self.assertFalse(destination.exists())

    def test_backup_preserves_explicit_destination_and_records_consistency(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workspace = root / "workspace"
            workspace.mkdir()
            foreign = root / "foreign"
            foreign.mkdir()
            self.prepare(workspace)
            save = workspace / "instances" / "source-world" / "saves" / "world.zip"
            shutil.copyfile(
                SAVE_FIXTURES / "valid_simple_save" / "starter.zip", save
            )

            outside = foreign / "world.backup.zip"
            code, stdout, _stderr = invoke([
                "--workspace", str(workspace), "saves", "backup", "world",
                "--instance", "source-world", "--to", str(outside), "--json",
            ])
            self.assertEqual(code, 0)
            self.assertEqual(outside.read_bytes(), save.read_bytes())
            self.assertEqual(
                Path(json.loads(stdout)["destination_path"]), outside
            )
            self.assertTrue(Path(str(outside) + ".manifest.json").is_file())
            self.assertEqual(
                sorted(path.name for path in foreign.iterdir()),
                ["world.backup.zip", "world.backup.zip.manifest.json"],
            )
            code, stdout, _stderr = invoke([
                "--workspace", str(workspace), "saves", "backup", "world",
                "--instance", "source-world", "--to", str(outside), "--json",
            ])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["refusal"]["code"], "save_backup_target_exists")
            self.assertEqual(outside.read_bytes(), save.read_bytes())

            linked_parent = root / "linked-output"
            try:
                linked_parent.symlink_to(foreign, target_is_directory=True)
            except OSError:
                pass
            else:
                linked_target = linked_parent / "linked.backup.zip"
                code, stdout, _stderr = invoke([
                    "--workspace", str(workspace), "saves", "backup", "world",
                    "--instance", "source-world", "--to", str(linked_target),
                    "--json",
                ])
                self.assertEqual(code, 1)
                self.assertEqual(
                    json.loads(stdout)["refusal"]["code"],
                    "save_backup_destination_unsafe",
                )
                self.assertFalse((foreign / "linked.backup.zip").exists())

            dangling_target = foreign / "dangling.backup.zip"
            try:
                dangling_target.symlink_to(foreign / "missing.zip")
            except OSError:
                pass
            else:
                code, stdout, _stderr = invoke([
                    "--workspace", str(workspace), "saves", "backup", "world",
                    "--instance", "source-world", "--to", str(dangling_target),
                    "--json",
                ])
                self.assertEqual(code, 1)
                self.assertEqual(
                    json.loads(stdout)["refusal"]["code"],
                    "save_backup_target_exists",
                )
                self.assertTrue(dangling_target.is_symlink())

            missing_parent = workspace / "not-claimed" / "world.backup.zip"
            code, stdout, _stderr = invoke([
                "--workspace", str(workspace), "saves", "backup", "world",
                "--instance", "source-world", "--to", str(missing_parent),
                "--json",
            ])
            self.assertEqual(code, 1)
            self.assertEqual(
                json.loads(stdout)["refusal"]["code"],
                "save_backup_destination_unsafe",
            )
            self.assertFalse(missing_parent.parent.exists())

            save_lock = save.parent.parent / "locks" / "save.write.lock"
            save_lock.parent.mkdir(exist_ok=True)
            save_lock.write_text("session owns save writes\n", encoding="utf-8")
            code, stdout, _stderr = invoke([
                "--workspace", str(workspace), "saves", "backup", "world",
                "--instance", "source-world", "--json",
            ])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["refusal"]["code"], "save_locked")
            self.assertFalse((save.parent.parent / "backups").exists())
            save_lock.unlink()

            run_lock = save.parent.parent / "locks" / "run.lock"
            run_lock.write_text("active production run\n", encoding="utf-8")
            code, stdout, _stderr = invoke([
                "--workspace", str(workspace), "saves", "backup", "world",
                "--instance", "source-world", "--json",
            ])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["refusal"]["code"], "save_locked")
            self.assertFalse((save.parent.parent / "backups").exists())
            run_lock.unlink()

            interrupted = workspace / "interrupted.backup.zip"
            fault_environment = os.environ.copy()
            fault_environment["FACMAN_TEST_SAVE_TRANSFER_FAIL_STAGE"] = (
                "during_cross_volume_copy"
            )
            code, stdout, _stderr = invoke([
                "--workspace", str(workspace), "saves", "backup", "world",
                "--instance", "source-world", "--to", str(interrupted),
                "--json",
            ], env=fault_environment)
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["refusal"]["code"], "persistent_write_refused")
            self.assertFalse(interrupted.exists())
            self.assertFalse(Path(str(interrupted) + ".manifest.json").exists())
            self.assertEqual(list(workspace.rglob(".facman-copy-*")), [])
            self.assertEqual(list(workspace.rglob(".facman-save-backup-*")), [])

            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "saves", "backup", "world",
                "--instance", "source-world", "--json",
            ])
            self.assertEqual(code, 0, stderr)
            receipt = json.loads(stdout)
            destination = Path(receipt["destination_path"])
            self.assertEqual(
                destination,
                workspace / "instances" / "source-world" / "backups"
                / "world.backup.zip",
            )
            self.assertEqual(destination.read_bytes(), save.read_bytes())
            self.assertEqual(receipt["source_size"], save.stat().st_size)
            self.assertEqual(receipt["sha256"], hashlib.sha256(save.read_bytes()).hexdigest())
            self.assertEqual(
                receipt["consistency_policy"], "pinned_source_two_pass_sha256_v1"
            )
            self.assertTrue(receipt["workspace_id"])
            sidecar = json.loads(Path(receipt["manifest_path"]).read_text(encoding="utf-8"))
            self.assertEqual(sidecar, receipt)
            schema = json.loads(
                (ROOT / "contracts/schema/factorio/factorio_save_backup.v1.schema.json")
                .read_text(encoding="utf-8")
            )
            self.assertEqual(json_contract.validate(receipt, schema), [])

    def test_backup_refuses_same_bytes_source_replacement_during_staging(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.prepare(workspace)
            save = workspace / "instances" / "source-world" / "saves" / "world.zip"
            shutil.copyfile(
                SAVE_FIXTURES / "valid_simple_save" / "starter.zip", save
            )
            original = save.read_bytes()
            destination = workspace / "concurrent.backup.zip"
            environment = os.environ.copy()
            environment["FACMAN_TEST_SAVE_TRANSFER_FAIL_STAGE"] = (
                "pause_after_staged_copy"
            )
            process = subprocess.Popen(
                [str(facman_executable()), "--workspace", tmp, "saves", "backup",
                 "world", "--instance", "source-world", "--to",
                 str(destination), "--json"],
                cwd=ROOT, env=environment, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            try:
                deadline = time.monotonic() + 10
                while (not list(workspace.glob(".facman-save-backup-*")) and
                       process.poll() is None and time.monotonic() < deadline):
                    time.sleep(0.02)
                self.assertIsNone(process.poll(), "backup exited before staged replacement")
                displaced = save.with_name("displaced-world.zip")
                os.replace(save, displaced)
                save.write_bytes(original)
                stdout, stderr = process.communicate(timeout=20)
                self.assertEqual(process.returncode, 1, stderr)
                envelope = json.loads(stdout)
                self.assertEqual(
                    envelope["payload"]["refusal"]["code"], "save_source_changed"
                )
                self.assertEqual(save.read_bytes(), original)
                self.assertFalse(destination.exists())
                self.assertFalse(Path(str(destination) + ".manifest.json").exists())
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()

    def test_backup_process_loss_recovers_owned_stage_and_retries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            output = Path(tmp) / "output"
            output.mkdir()
            self.prepare(workspace)
            save = workspace / "instances" / "source-world" / "saves" / "world.zip"
            shutil.copyfile(
                SAVE_FIXTURES / "valid_simple_save" / "starter.zip", save
            )
            destination = output / "restarted.backup.zip"
            environment = os.environ.copy()
            environment["FACMAN_TEST_SAVE_TRANSFER_FAIL_STAGE"] = (
                "pause_after_staged_copy"
            )
            process = subprocess.Popen(
                [str(facman_executable()), "--workspace", str(workspace), "saves", "backup",
                 "world", "--instance", "source-world", "--to",
                 str(destination), "--json"],
                cwd=ROOT, env=environment, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            try:
                deadline = time.monotonic() + 10
                while process.poll() is None and time.monotonic() < deadline:
                    stages = list(workspace.glob(
                        ".facman-save-backup-*/restarted.backup.zip"
                    ))
                    if stages:
                        break
                    time.sleep(0.02)
                self.assertIsNone(process.poll(), "backup exited before process-loss test")
                self.assertTrue(stages, "backup did not produce a staged file")
                process.kill()
                process.communicate(timeout=20)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()

            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "workspace", "recovery", "inspect", "--json",
            ])
            self.assertEqual(code, 0, stderr)
            records = [
                record for record in json.loads(stdout)["transactions"]
                if record["command_id"] == "saves.backup"
                and Path(record["target"]) == destination
            ]
            self.assertEqual(len(records), 1)
            transaction_id = records[0]["transaction_id"]
            self.assertFalse(records[0]["target_exists"])
            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "workspace", "recovery", "plan",
                transaction_id, "--json",
            ])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(
                json.loads(stdout)["transactions"][0]["actions"],
                ["remove_owned_staging"],
            )
            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "workspace", "recovery", "apply",
                transaction_id, "--json",
            ])
            self.assertEqual(code, 0, stderr + stdout)
            self.assertEqual(
                json.loads(stdout)["transactions"][0]["state"], "rolled_back"
            )
            self.assertEqual(list(workspace.glob(".facman-save-backup-*")), [])
            self.assertEqual(list(output.glob(".facman-save-backup-*")), [])
            self.assertFalse(destination.exists())
            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "saves", "backup", "world", "--instance",
                "source-world", "--to", str(destination), "--json",
            ])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(destination.read_bytes(), save.read_bytes())

    def test_backup_process_loss_after_commit_recovers_bound_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            output = Path(tmp) / "output"
            output.mkdir()
            self.prepare(workspace)
            save = workspace / "instances" / "source-world" / "saves" / "world.zip"
            shutil.copyfile(SAVE_FIXTURES / "valid_simple_save" / "starter.zip", save)
            destination = output / "committed.backup.zip"
            sidecar = Path(str(destination) + ".manifest.json")
            environment = os.environ.copy()
            environment["FACMAN_TEST_SAVE_TRANSFER_FAIL_STAGE"] = (
                "pause_after_backup_file_committed"
            )
            process = subprocess.Popen(
                [str(facman_executable()), "--workspace", str(workspace), "saves",
                 "backup", "world", "--instance", "source-world", "--to",
                 str(destination), "--json"],
                cwd=ROOT, env=environment, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            try:
                deadline = time.monotonic() + 10
                while not destination.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertIsNone(process.poll(), "backup exited before committed-loss test")
                self.assertTrue(destination.is_file())
                self.assertFalse(sidecar.exists())
                process.kill()
                process.communicate(timeout=20)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "workspace", "recovery", "inspect", "--json",
            ])
            self.assertEqual(code, 0, stderr)
            records = [
                record for record in json.loads(stdout)["transactions"]
                if record["command_id"] == "saves.backup"
                and Path(record["target"]) == destination
            ]
            self.assertEqual(len(records), 1)
            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "workspace", "recovery", "apply",
                records[0]["transaction_id"], "--json",
            ])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["transactions"][0]["state"], "complete")
            self.assertEqual(destination.read_bytes(), save.read_bytes())
            manifest = json.loads(sidecar.read_text(encoding="utf-8"))
            self.assertEqual(manifest["sha256"], hashlib.sha256(save.read_bytes()).hexdigest())
            self.assertEqual(Path(manifest["destination_path"]), destination)
            self.assertEqual(list(workspace.glob(".facman-save-backup-*")), [])
            self.assertEqual(list(output.glob(".facman-save-backup-*")), [])

    def test_backup_recovery_rejects_foreign_identical_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            output = Path(tmp) / "output"
            output.mkdir()
            self.prepare(workspace)
            save = workspace / "instances" / "source-world" / "saves" / "world.zip"
            shutil.copyfile(SAVE_FIXTURES / "valid_simple_save" / "starter.zip", save)
            destination = output / "colliding.backup.zip"
            sidecar = Path(str(destination) + ".manifest.json")
            environment = os.environ.copy()
            environment["FACMAN_TEST_SAVE_TRANSFER_FAIL_STAGE"] = (
                "pause_before_backup_publish"
            )
            process = subprocess.Popen(
                [str(facman_executable()), "--workspace", str(workspace), "saves",
                 "backup", "world", "--instance", "source-world", "--to",
                 str(destination), "--json"],
                cwd=ROOT, env=environment, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            try:
                deadline = time.monotonic() + 10
                while process.poll() is None and time.monotonic() < deadline:
                    stages = list(output.glob(".facman-save-backup-*.staging.zip"))
                    if stages and stages[0].stat().st_size == save.stat().st_size:
                        break
                    time.sleep(0.02)
                self.assertIsNone(process.poll(), "backup exited before collision")
                self.assertTrue(stages, "backup did not prepare relative publication")
                with destination.open("xb") as foreign:
                    foreign.write(save.read_bytes())
                foreign_bytes = destination.read_bytes()
                process.kill()
                process.communicate(timeout=20)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "workspace", "recovery", "inspect", "--json",
            ])
            self.assertEqual(code, 0, stderr)
            records = [
                record for record in json.loads(stdout)["transactions"]
                if record["command_id"] == "saves.backup"
                and Path(record["target"]) == destination
            ]
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["state"], "committing")
            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "workspace", "recovery", "apply",
                records[0]["transaction_id"], "--json",
            ])
            self.assertEqual(code, 1, stderr + stdout)
            self.assertEqual(json.loads(stdout)["refusal"]["code"],
                             "recovery_backup_manifest_unsafe")
            self.assertEqual(destination.read_bytes(), foreign_bytes)
            self.assertFalse(sidecar.exists())

    def test_backup_process_loss_before_temp_identity_checkpoint_rotates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            output = Path(tmp) / "output"
            output.mkdir()
            self.prepare(workspace)
            save = workspace / "instances" / "source-world" / "saves" / "world.zip"
            shutil.copyfile(SAVE_FIXTURES / "valid_simple_save" / "starter.zip", save)
            destination = output / "precheckpoint.backup.zip"
            environment = os.environ.copy()
            environment["FACMAN_TEST_SAVE_TRANSFER_FAIL_STAGE"] = (
                "pause_after_backup_temp_created"
            )
            process = subprocess.Popen(
                [str(facman_executable()), "--workspace", str(workspace), "saves",
                 "backup", "world", "--instance", "source-world", "--to",
                 str(destination), "--json"],
                cwd=ROOT, env=environment, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            try:
                deadline = time.monotonic() + 10
                while process.poll() is None and time.monotonic() < deadline:
                    stages = list(output.glob(".facman-save-backup-*.staging.zip"))
                    if stages:
                        break
                    time.sleep(0.02)
                self.assertIsNone(process.poll(), "backup exited before temp checkpoint")
                self.assertEqual(len(stages), 1)
                self.assertEqual(stages[0].stat().st_size, 0)
                process.kill()
                process.communicate(timeout=20)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
            stages[0].unlink()
            stages[0].write_bytes(b"foreign temporary file")
            if os.name != "nt":
                stages[0].chmod(0o666)
            records = [
                json.loads(path.read_text(encoding="utf-8"))
                for path in (workspace / "transactions").glob("*.transaction.v1.json")
            ]
            backups = [
                record for record in records
                if record["command_id"] == "saves.backup"
                and Path(record["target"]) == destination
            ]
            self.assertEqual(len(backups), 1)
            record = backups[0]
            self.assertEqual(record["state"], "committing")
            self.assertEqual(record["effect_file_identity"], "")
            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "workspace", "recovery", "apply",
                record["transaction_id"], "--json",
            ])
            self.assertEqual(code, 0, stderr + stdout)
            self.assertEqual(json.loads(stdout)["transactions"][0]["state"], "complete")
            self.assertEqual(destination.read_bytes(), save.read_bytes())
            self.assertTrue(Path(str(destination) + ".manifest.json").is_file())
            self.assertEqual(stages[0].read_bytes(), b"foreign temporary file")
            self.assertEqual(list(output.glob(".facman-save-backup-*.staging.zip")), stages)
            self.assertTrue(any(
                action.startswith("retained_ambiguous_backup_temporary:")
                for action in json.loads(stdout)["transactions"][0]["actions"]
            ))

    def test_backup_process_loss_during_relative_publication_resumes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            output = Path(tmp) / "output"
            output.mkdir()
            self.prepare(workspace)
            save = workspace / "instances" / "source-world" / "saves" / "world.zip"
            with zipfile.ZipFile(save, "w", compression=zipfile.ZIP_STORED) as archive:
                archive.writestr("level-init.dat", b"ready")
                archive.writestr("filler.bin", bytes(range(250)) * 1000)
            destination = output / "resumed.backup.zip"
            environment = os.environ.copy()
            environment["FACMAN_TEST_SAVE_TRANSFER_FAIL_STAGE"] = (
                "pause_during_backup_publication"
            )
            process = subprocess.Popen(
                [str(facman_executable()), "--workspace", str(workspace), "saves",
                 "backup", "world", "--instance", "source-world", "--to",
                 str(destination), "--json"],
                cwd=ROOT, env=environment, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            try:
                deadline = time.monotonic() + 10
                stages: list[Path] = []
                while process.poll() is None and time.monotonic() < deadline:
                    stages = list(output.glob(".facman-save-backup-*.staging.zip"))
                    if stages and stages[0].stat().st_size > 0:
                        break
                    time.sleep(0.02)
                self.assertIsNone(process.poll(), "backup exited before relative-copy loss")
                self.assertEqual(len(stages), 1)
                self.assertLess(stages[0].stat().st_size, save.stat().st_size)
                self.assertFalse(destination.exists())
                process.kill()
                process.communicate(timeout=20)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()
            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "workspace", "recovery", "inspect", "--json",
            ])
            self.assertEqual(code, 0, stderr)
            records = [
                record for record in json.loads(stdout)["transactions"]
                if record["command_id"] == "saves.backup"
                and Path(record["target"]) == destination
            ]
            self.assertEqual(len(records), 1)
            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "workspace", "recovery", "apply",
                records[0]["transaction_id"], "--json",
            ])
            self.assertEqual(code, 0, stderr + stdout)
            self.assertEqual(json.loads(stdout)["transactions"][0]["state"], "complete")
            self.assertEqual(destination.read_bytes(), save.read_bytes())
            sidecar = json.loads(Path(str(destination) + ".manifest.json").read_text(
                encoding="utf-8"))
            self.assertEqual(sidecar["sha256"], hashlib.sha256(save.read_bytes()).hexdigest())
            self.assertEqual(list(output.glob(".facman-save-backup-*.staging.zip")), [])
            self.assertEqual(list(workspace.glob(".facman-save-backup-*")), [])

    @unittest.skipIf(os.name == "nt", "not_applicable: Windows pins the directory against rename")
    def test_backup_external_parent_swap_cannot_redirect_publication(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            workspace.mkdir()
            output = Path(tmp) / "output"
            output.mkdir()
            displaced = Path(tmp) / "original-output"
            self.prepare(workspace)
            save = workspace / "instances" / "source-world" / "saves" / "world.zip"
            shutil.copyfile(SAVE_FIXTURES / "valid_simple_save" / "starter.zip", save)
            destination = output / "redirected.backup.zip"
            pause_marker = Path(tmp) / "backup-publication-paused.marker"
            environment = os.environ.copy()
            environment["FACMAN_TEST_SAVE_TRANSFER_FAIL_STAGE"] = (
                "pause_before_backup_publish"
            )
            environment["FACMAN_TEST_SAVE_TRANSFER_PAUSE_MARKER"] = str(pause_marker)
            process = subprocess.Popen(
                [str(facman_executable()), "--workspace", str(workspace), "saves",
                 "backup", "world", "--instance", "source-world", "--to",
                 str(destination), "--json"],
                cwd=ROOT, env=environment, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            try:
                deadline = time.monotonic() + 10
                while (process.poll() is None and not pause_marker.exists()
                       and time.monotonic() < deadline):
                    time.sleep(0.02)
                self.assertTrue(pause_marker.exists(),
                                "backup did not reach publication pause")
                self.assertIsNone(process.poll(), "backup exited before parent swap")
                output.rename(displaced)
                output.mkdir()
                stdout, stderr = process.communicate(timeout=20)
                self.assertEqual(process.returncode, 1, stderr + stdout)
                self.assertFalse(destination.exists())
                self.assertFalse(Path(str(destination) + ".manifest.json").exists())
                self.assertFalse((displaced / destination.name).exists())
                self.assertFalse(Path(str(displaced / destination.name) + ".manifest.json").exists())
                code, stdout, stderr = invoke([
                    "--workspace", str(workspace), "workspace", "recovery",
                    "inspect", "--json",
                ])
                self.assertEqual(code, 0, stderr)
                records = [
                    record for record in json.loads(stdout)["transactions"]
                    if record["command_id"] == "saves.backup"
                    and Path(record["target"]) == destination
                ]
                self.assertEqual(len(records), 1)
                code, stdout, stderr = invoke([
                    "--workspace", str(workspace), "workspace", "recovery", "apply",
                    records[0]["transaction_id"], "--json",
                ])
                self.assertEqual(code, 0, stderr + stdout)
                self.assertEqual(json.loads(stdout)["transactions"][0]["state"],
                                 "rolled_back")
                self.assertFalse(destination.exists())
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()

    def test_backup_refuses_run_lock_created_during_staging(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.prepare(workspace)
            save = workspace / "instances" / "source-world" / "saves" / "world.zip"
            shutil.copyfile(
                SAVE_FIXTURES / "valid_simple_save" / "starter.zip", save
            )
            destination = workspace / "late-lock.backup.zip"
            environment = os.environ.copy()
            environment["FACMAN_TEST_SAVE_TRANSFER_FAIL_STAGE"] = (
                "pause_after_staged_copy"
            )
            process = subprocess.Popen(
                [str(facman_executable()), "--workspace", tmp, "saves", "backup",
                 "world", "--instance", "source-world", "--to",
                 str(destination), "--json"],
                cwd=ROOT, env=environment, text=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            try:
                deadline = time.monotonic() + 10
                stages: list[Path] = []
                while process.poll() is None and time.monotonic() < deadline:
                    stages = list(workspace.glob(
                        ".facman-save-backup-*/late-lock.backup.zip"
                    ))
                    if stages:
                        break
                    time.sleep(0.02)
                self.assertIsNone(process.poll(), "backup exited before lock test")
                self.assertTrue(stages, "backup did not produce a staged file")
                run_lock = save.parent.parent / "locks" / "run.lock"
                run_lock.write_text("active production run\n", encoding="utf-8")
                stdout, stderr = process.communicate(timeout=20)
                self.assertEqual(process.returncode, 1, stderr)
                self.assertEqual(
                    json.loads(stdout)["payload"]["refusal"]["code"],
                    "save_locked",
                )
                self.assertFalse(destination.exists())
                self.assertFalse(Path(str(destination) + ".manifest.json").exists())
                self.assertEqual(list(workspace.glob(".facman-save-backup-*")), [])
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()

    def test_transaction_state_faults_never_leave_an_apparently_partial_instance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            self.prepare(workspace)
            save = workspace / "instances" / "source-world" / "saves" / "world.zip"
            with zipfile.ZipFile(save, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr("level-init.dat", b"transaction states")
            pack = workspace / "portable.zip"
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "export", "instance", "source-world", str(pack), "--json"]
            )
            self.assertEqual(code, 0, stderr)
            states = (
                "requested",
                "validated",
                "planned",
                "staging",
                "staged",
                "verified",
                "committing",
                "committed",
                "audited",
                "complete",
            )
            try:
                for index, state in enumerate(states):
                    instance_id = f"state-{index}"
                    os.environ["FACMAN_TEST_TRANSACTION_FAIL_STATE"] = state
                    code, _stdout, _stderr = invoke(
                        ["--workspace", tmp, "import", "instance", str(pack), "--id", instance_id, "--json"]
                    )
                    self.assertEqual(code, 1, state)
                    target = workspace / "instances" / instance_id
                    if state in {"committed", "audited", "complete"}:
                        self.assertTrue((target / "instance.v1.json").is_file(), state)
                        self.assertTrue((target / "config" / "config.ini").is_file(), state)
                    else:
                        self.assertFalse(target.exists(), state)
            finally:
                os.environ.pop("FACMAN_TEST_TRANSACTION_FAIL_STATE", None)


if __name__ == "__main__":
    unittest.main()
