# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
from __future__ import annotations

import hashlib
import errno
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

from native_cli import facman_executable
from test_local_modset_solver import FIXTURE_INSTALL, SCHEMA_ROOT, call, setup, snapshot, write_mod
from tools import json_contract


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class PortableModpackImportTests(unittest.TestCase):
    def make_pack(self, workspace: Path, settings: bytes | None = None) -> tuple[Path, Path]:
        source = setup(workspace)
        write_mod(source / "mods/simple_1.0.0.zip", "simple", "1.0.0")
        write_mod(source / "mods/unselected_1.0.0.zip", "unselected", "1.0.0")
        call(workspace, "modsets", "apply", "solver", "--enable", "simple")
        if settings is not None:
            (source / "mods/mod-settings.dat").write_bytes(settings)
        pack = workspace / "pack.zip"
        call(workspace, "modsets", "export", "solver", str(pack))
        return source, pack

    def import_pack(self, workspace: Path, pack: Path, *, success: bool = True, install: str = "fixture",
                    env: dict[str, str] | None = None) -> dict:
        return call(workspace, "modsets", "import", str(pack), "--instance", "reconstructed",
                    "--install", install, "--name", "Restored pack", success=success, env=env)

    def assert_reconstruction(self, workspace: Path, pack: Path, install: str = "fixture") -> None:
        target = workspace / "instances/reconstructed"
        receipt = json.loads((target / "modpack-import.v1.json").read_bytes())
        schema = json_contract.load_schema(SCHEMA_ROOT / "factorio_modpack_import.v1.schema.json")
        self.assertEqual([], json_contract.supported_schema_problems(schema))
        self.assertEqual([], json_contract.validate(receipt, schema))
        with zipfile.ZipFile(pack) as archive:
            for leaf in ("modset-lock.v1.json", "modpack-manifest.v1.json"):
                self.assertEqual(archive.read(leaf), (target / leaf).read_bytes())
            for leaf in ("mods/simple_1.0.0.zip", "mods/mod-list.json", "mods/mod-settings.dat"):
                if leaf in archive.namelist():
                    self.assertEqual(archive.read(leaf), (target / leaf).read_bytes())
                else:
                    self.assertFalse((target / leaf).exists())
            self.assertEqual(digest(archive.read("modset-lock.v1.json")), receipt["source_lock_sha256"])
            self.assertEqual(digest(archive.read("modpack-manifest.v1.json")), receipt["source_manifest_sha256"])
        target_lock = (target / "mods/modset-lock.v1.json").read_bytes()
        self.assertEqual(digest(target_lock), receipt["target_lock_sha256"])
        lock = json.loads(target_lock)
        self.assertEqual("reconstructed", lock["instance_id"])
        self.assertEqual("install-data:" + install, next(mod["source"] for mod in lock["mods"] if mod["name"] == "base"))
        self.assertEqual(digest(pack.read_bytes()), receipt["archive_sha256"])
        self.assertEqual(pack.stat().st_size, receipt["archive_size"])
        self.assertEqual("solver", receipt["source_instance_id"])
        self.assertEqual(install, receipt["install_ref"])
        manifest = json.loads((target / "instance.v1.json").read_bytes())
        self.assertEqual("Restored pack", manifest["display_name"])
        self.assertEqual(install, manifest["install_ref"])
        self.assertEqual(str(target), manifest["local_data_root"])
        self.assertIn(str(target).replace("\\", "/"), (target / "config/config.ini").read_text().replace("\\", "/"))
        self.assertFalse((target / "mods/unselected_1.0.0.zip").exists())
        self.assertFalse((workspace / "modsets/reconstructed.modset-lock.v1.json").exists())
        self.assertFalse((workspace / ".facman-pack-import-reconstructed").exists())
        self.assertFalse((target / ".facman-archive-staging.v1").exists())
        self.assertFalse((target / ".facman-transaction-staging.v2.json").exists())
        call(workspace, "modsets", "verify", "reconstructed")
        call(workspace, "instances", "verify", "reconstructed")
        listed = call(workspace, "instances", "list")
        self.assertIn("reconstructed", [item["instance_id"] for item in listed["instances"]])

    def test_exported_pack_reconstructs_offline_exact_bytes_and_rebound_local_lock(self) -> None:
        for settings in (None, b"", b"\x01binary settings\x00\xff"):
            with self.subTest(settings=settings), tempfile.TemporaryDirectory(prefix="facman pack import ") as value:
                workspace = Path(value)
                source, pack = self.make_pack(workspace, settings)
                call(workspace, "installs", "import", str(FIXTURE_INSTALL), "--id", "different-install")
                before = snapshot(source), snapshot(workspace / "modsets")
                result = self.import_pack(workspace, pack, install="different-install")
                self.assertTrue(result["offline"])
                self.assertEqual(before, (snapshot(source), snapshot(workspace / "modsets")))
                self.assert_reconstruction(workspace, pack, "different-install")
                call(workspace, "modsets", "export", "reconstructed", str(workspace / "again.zip"))

    def test_existing_target_and_foreign_staging_are_preserved(self) -> None:
        for place in ("instances/reconstructed", ".facman-pack-import-reconstructed"):
            with self.subTest(place=place), tempfile.TemporaryDirectory() as value:
                workspace = Path(value)
                _, pack = self.make_pack(workspace)
                foreign = workspace / place
                foreign.mkdir(parents=True)
                (foreign / "user-save.dat").write_bytes(b"foreign data")
                before = snapshot(foreign)
                result = self.import_pack(workspace, pack, success=False)
                self.assertEqual("persistent_target_exists" if place.startswith("instances") else "staging_target_exists",
                                 result["refusal"]["code"])
                self.assertEqual(before, snapshot(foreign))

    def test_bound_absent_mod_list_remains_absent_and_human_cli_identifies_instance(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            workspace = Path(value)
            source = setup(workspace)
            write_mod(source / "mods/simple_1.0.0.zip", "simple", "1.0.0")
            call(workspace, "modsets", "lock", "solver")
            pack = workspace / "pack.zip"
            call(workspace, "modsets", "export", "solver", str(pack))
            with zipfile.ZipFile(pack) as archive:
                self.assertNotIn("mods/mod-list.json", archive.namelist())
            result = subprocess.run([str(facman_executable()), "--workspace", str(workspace), "modsets", "import",
                str(pack), "--instance", "reconstructed", "--install", "fixture"],
                check=False, text=True, capture_output=True)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("Modpack imported into instance reconstructed", result.stdout)
            target = workspace / "instances/reconstructed"
            self.assertFalse((target / "mods/mod-list.json").exists())
            self.assertFalse((target / "mods/mod-settings.dat").exists())
            call(workspace, "modsets", "verify", "reconstructed")

    def test_altered_extra_legacy_duplicate_and_unsafe_packs_refuse_before_staging(self) -> None:
        for alteration in ("artifact", "lock", "manifest", "extra", "legacy", "duplicate", "unsafe"):
            with self.subTest(alteration=alteration), tempfile.TemporaryDirectory() as value:
                workspace = Path(value)
                source, pack = self.make_pack(workspace)
                with zipfile.ZipFile(pack) as archive:
                    entries = [(name, archive.read(name)) for name in archive.namelist()]
                if alteration in ("artifact", "lock", "manifest"):
                    leaf = {"artifact": "mods/simple_1.0.0.zip", "lock": "modset-lock.v1.json",
                            "manifest": "modpack-manifest.v1.json"}[alteration]
                    if alteration == "manifest":
                        changed = json.loads(dict(entries)[leaf]); changed["network_authority"] = True
                        entries = [(name, json.dumps(changed).encode() if name == leaf else data) for name, data in entries]
                    else:
                        entries = [(name, data + b"altered" if name == leaf else data) for name, data in entries]
                elif alteration == "legacy":
                    changed = json.loads(dict(entries)["modpack-manifest.v1.json"])
                    del changed["settings"]; del changed["source_lock"]
                    entries = [(name, json.dumps(changed).encode() if name == "modpack-manifest.v1.json" else data) for name, data in entries]
                else:
                    entries.append(entries[0] if alteration == "duplicate" else
                                   ("../foreign.dat" if alteration == "unsafe" else "unbound.dat", b"unbound"))
                changed_pack = workspace / "invalid.zip"
                with zipfile.ZipFile(changed_pack, "w") as archive:
                    for name, data in entries:
                        archive.writestr(name, data)
                before = snapshot(source)
                self.import_pack(workspace, changed_pack, success=False)
                self.assertFalse((workspace / ".facman-pack-import-reconstructed").exists())
                self.assertFalse((workspace / "instances/reconstructed").exists())
                self.assertEqual(before, snapshot(source))

    def test_incompatible_local_builtin_is_refused_without_target_effects(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            workspace = Path(value)
            _, pack = self.make_pack(workspace)
            install = workspace / "incompatible-install"
            shutil.copytree(FIXTURE_INSTALL, install)
            info = install / "data/base/info.json"
            metadata = json.loads(info.read_text()); metadata["version"] = "2.0.76"
            info.write_text(json.dumps(metadata))
            call(workspace, "installs", "import", str(install), "--id", "incompatible")
            result = self.import_pack(workspace, pack, success=False, install="incompatible")
            self.assertEqual("modpack_install_incompatible", result["refusal"]["code"])
            self.assertFalse((workspace / "instances/reconstructed").exists())
            self.assertFalse((workspace / ".facman-pack-import-reconstructed").exists())

    def interrupt(self, workspace: Path, pack: Path, point: str, install: str = "fixture") -> str:
        env = dict(os.environ, FACMAN_TEST_MODPACK_IMPORT_PAUSE=point)
        process = subprocess.Popen([str(facman_executable()), "--workspace", str(workspace), "modsets", "import",
            str(pack), "--instance", "reconstructed", "--install", install, "--name", "Restored pack", "--json"],
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        signal = workspace / f".facman-modpack-import-{point}-paused"
        try:
            deadline = time.monotonic() + 20
            while not signal.exists() and time.monotonic() < deadline:
                if process.poll() is not None:
                    stdout, stderr = process.communicate()
                    self.fail(stdout + stderr)
                time.sleep(0.025)
            self.assertTrue(signal.exists(), "Import did not reach its public interruption seam")
            listed = call(workspace, "instances", "list")
            ids = [item["instance_id"] for item in listed["instances"]]
            self.assertEqual(point in ("published", "committed"), "reconstructed" in ids)
            inspected = call(workspace, "workspace", "recovery", "inspect")
            tx = next(item["transaction_id"] for item in inspected["transactions"] if item["command_id"] == "modsets.import")
            locked = call(workspace, "workspace", "recovery", "apply", tx, success=False)
            self.assertEqual("recovery_lock_contended", locked["refusal"]["code"])
            return tx
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)

    def test_process_loss_recovers_verified_staging_and_committed_finalization(self) -> None:
        for point in ("verified", "published", "committed"):
            with self.subTest(point=point), tempfile.TemporaryDirectory() as value:
                workspace = Path(value)
                source, pack = self.make_pack(workspace, b"exact settings")
                before = snapshot(source)
                tx = self.interrupt(workspace, pack, point)
                stale_lock = workspace / "transactions" / f"{tx}.transaction.v1.json.recovery.lock"
                self.assertTrue(stale_lock.exists(), "Process kill must leave the operation lock for adoption")
                lock_record = json.loads(stale_lock.read_bytes())
                self.assertEqual("facman.recovery_lock.v1", lock_record["schema"])
                self.assertTrue(lock_record["identity"])
                plan = call(workspace, "workspace", "recovery", "plan", tx)
                self.assertEqual(["verify_and_resume_owned_pack_instance"], plan["transactions"][0]["actions"])
                recovered = call(workspace, "workspace", "recovery", "apply", tx)
                self.assertEqual("complete", recovered["transactions"][0]["state"])
                self.assertFalse(stale_lock.exists(), "Recovered operation must release its exact adopted lock")
                self.assert_reconstruction(workspace, pack)
                self.assertEqual(before, snapshot(source))
                call(workspace, "workspace", "recovery", "apply", tx)

    def test_empty_or_foreign_stale_import_lock_is_not_adopted(self) -> None:
        for foreign_bytes in (b"", b'{"schema":"facman.recovery_lock.v1","identity":"foreign"}\n'):
            with self.subTest(foreign_bytes=foreign_bytes), tempfile.TemporaryDirectory() as value:
                workspace = Path(value)
                _, pack = self.make_pack(workspace)
                tx = self.interrupt(workspace, pack, "verified")
                stale_lock = workspace / "transactions" / f"{tx}.transaction.v1.json.recovery.lock"
                self.assertTrue(stale_lock.exists())
                stale_lock.write_bytes(foreign_bytes)
                stage = workspace / ".facman-pack-import-reconstructed"
                before = snapshot(stage)
                refused = call(workspace, "workspace", "recovery", "apply", tx, success=False)
                self.assertEqual("recovery_lock_contended", refused["refusal"]["code"])
                self.assertEqual(foreign_bytes, stale_lock.read_bytes())
                self.assertEqual(before, snapshot(stage))
                self.assertFalse((workspace / "instances/reconstructed").exists())

    def test_published_marker_substitution_refuses_and_preserves_incomplete_journal(self) -> None:
        for point in ("published", "committed"):
            for substitution in ("dangling_symlink", "foreign_bytes"):
                with self.subTest(point=point, substitution=substitution), tempfile.TemporaryDirectory() as value:
                    workspace = Path(value)
                    _, pack = self.make_pack(workspace)
                    tx = self.interrupt(workspace, pack, point)
                    target = workspace / "instances/reconstructed"
                    marker = target / ".facman-transaction-staging.v2.json"
                    if substitution == "dangling_symlink":
                        marker.unlink()
                        try:
                            marker.symlink_to(workspace / "foreign-missing-marker")
                        except OSError as error:
                            if error.errno in (errno.EPERM, errno.ENOSYS, errno.EOPNOTSUPP) or getattr(error, "winerror", None) in (50, 1314):
                                self.skipTest(f"not_applicable: host cannot create symbolic links: {error}")
                            raise
                        link_before = os.readlink(marker)
                    else:
                        marker.write_bytes(b"foreign marker bytes")
                    before = snapshot(target)
                    journal = workspace / "transactions" / f"{tx}.transaction.v1.json"
                    journal_before = journal.read_bytes()
                    refused = call(workspace, "workspace", "recovery", "apply", tx, success=False)
                    self.assertEqual("recovery_modpack_import_unsafe", refused["refusal"]["code"])
                    self.assertEqual(before, snapshot(target))
                    self.assertEqual(journal_before, journal.read_bytes())
                    self.assertNotEqual("complete", json.loads(journal.read_bytes())["state"])
                    if substitution == "dangling_symlink":
                        self.assertTrue(marker.is_symlink())
                        self.assertEqual(link_before, os.readlink(marker))

    def test_foreign_target_appearing_before_native_publication_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            workspace = Path(value)
            _, pack = self.make_pack(workspace)
            process = subprocess.Popen([str(facman_executable()), "--workspace", str(workspace), "modsets", "import",
                str(pack), "--instance", "reconstructed", "--install", "fixture", "--json"],
                env=dict(os.environ, FACMAN_TEST_MODPACK_IMPORT_PAUSE="verified"),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                signal = workspace / ".facman-modpack-import-verified-paused"
                deadline = time.monotonic() + 20
                while not signal.exists() and time.monotonic() < deadline:
                    if process.poll() is not None:
                        stdout, stderr = process.communicate()
                        self.fail(stdout + stderr)
                    time.sleep(0.025)
                self.assertTrue(signal.exists())
                stage = workspace / ".facman-pack-import-reconstructed"
                before = snapshot(stage)
                target = workspace / "instances/reconstructed"
                target.mkdir()
                (target / "foreign-save.dat").write_bytes(b"foreign player bytes")
                foreign = snapshot(target)
                (workspace / ".facman-modpack-import-verified-release").write_bytes(b"release")
                stdout, stderr = process.communicate(timeout=20)
                self.assertNotEqual(0, process.returncode, stdout + stderr)
                self.assertEqual("transaction_recovery_required", json.loads(stdout)["payload"]["refusal"]["code"])
                self.assertEqual(foreign, snapshot(target))
                self.assertEqual(before, snapshot(stage))
            finally:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=10)

    def test_foreign_staging_appearing_before_exclusive_create_is_never_marked_or_adopted(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            workspace = Path(value)
            _, pack = self.make_pack(workspace)
            process = subprocess.Popen([str(facman_executable()), "--workspace", str(workspace), "modsets", "import",
                str(pack), "--instance", "reconstructed", "--install", "fixture", "--json"],
                env=dict(os.environ, FACMAN_TEST_MODPACK_IMPORT_PAUSE="precreate"),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                signal = workspace / ".facman-modpack-import-precreate-paused"
                deadline = time.monotonic() + 20
                while not signal.exists() and time.monotonic() < deadline:
                    if process.poll() is not None:
                        stdout, stderr = process.communicate()
                        self.fail(stdout + stderr)
                    time.sleep(0.025)
                self.assertTrue(signal.exists())
                stage = workspace / ".facman-pack-import-reconstructed"
                stage.mkdir()
                (stage / "foreign-save.dat").write_bytes(b"foreign staging bytes")
                before = snapshot(stage)
                (workspace / ".facman-modpack-import-precreate-release").write_bytes(b"release")
                stdout, stderr = process.communicate(timeout=20)
                self.assertNotEqual(0, process.returncode, stdout + stderr)
                self.assertEqual("archive_staging_root_exists", json.loads(stdout)["payload"]["refusal"]["code"])
                self.assertEqual(before, snapshot(stage))
                self.assertFalse((stage / ".facman-transaction-staging.v2.json").exists())
                self.assertFalse((stage / ".facman-archive-staging.v1").exists())
                self.assertFalse((workspace / "instances/reconstructed").exists())
                transactions = call(workspace, "workspace", "recovery", "inspect")["transactions"]
                tx = next(item["transaction_id"] for item in transactions if item["command_id"] == "modsets.import")
                journal = workspace / "transactions" / f"{tx}.transaction.v1.json"
                self.assertEqual("", json.loads(journal.read_bytes())["effect_file_identity"])
                refused = call(workspace, "workspace", "recovery", "apply", tx, success=False)
                self.assertEqual("recovery_modpack_import_unsafe", refused["refusal"]["code"])
                self.assertEqual(before, snapshot(stage))
            finally:
                if process.poll() is None:
                    process.kill()
                process.communicate(timeout=10)

    def test_recovery_preserves_foreign_target_changed_inventory_and_install_metadata(self) -> None:
        for change in ("foreign_target", "extra", "changed_file", "changed_install", "replacement"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as value:
                workspace = Path(value)
                _, pack = self.make_pack(workspace)
                if change == "changed_install":
                    local_install = workspace / "local-install"
                    shutil.copytree(FIXTURE_INSTALL, local_install)
                    call(workspace, "installs", "import", str(local_install), "--id", "recovery-install")
                tx = self.interrupt(workspace, pack, "verified",
                                    "recovery-install" if change == "changed_install" else "fixture")
                stage = workspace / ".facman-pack-import-reconstructed"
                target = workspace / "instances/reconstructed"
                if change == "foreign_target":
                    target.mkdir(); (target / "foreign.txt").write_bytes(b"player data")
                elif change == "extra":
                    (stage / "foreign.txt").write_bytes(b"player data")
                elif change == "changed_file":
                    (stage / "mods/mod-list.json").write_bytes(b"foreign changed settings")
                elif change == "replacement":
                    parked = workspace / "original-owned-stage"
                    stage.rename(parked)
                    shutil.copytree(parked, stage)
                else:
                    (local_install / "data/base/info.json").write_bytes(b"changed install")
                before = snapshot(stage), snapshot(target) if target.exists() else None
                refused = call(workspace, "workspace", "recovery", "apply", tx, success=False)
                self.assertEqual("recovery_modpack_import_unsafe", refused["refusal"]["code"])
                self.assertEqual(before, (snapshot(stage), snapshot(target) if target.exists() else None))
                if change == "replacement":
                    self.assertEqual(snapshot(parked), snapshot(stage))

    def test_extraction_retains_the_original_install_binding_on_metadata_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pack-install-drift-") as value:
            workspace = Path(value)
            source, pack = self.make_pack(workspace)
            source_before = snapshot(source)
            local_install = workspace / "local-install"
            shutil.copytree(FIXTURE_INSTALL, local_install)
            call(workspace, "installs", "import", str(local_install), "--id", "drift")
            metadata = local_install / "data/base/info.json"
            original = metadata.read_bytes()
            process = subprocess.Popen([str(facman_executable()), "--workspace", str(workspace),
                "modsets", "import", str(pack), "--instance", "reconstructed", "--install", "drift", "--json"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                env=dict(os.environ, FACMAN_TEST_MODPACK_IMPORT_PAUSE="precreate"))
            try:
                signal = workspace / ".facman-modpack-import-precreate-paused"
                deadline = time.monotonic() + 20
                while not signal.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue(signal.exists(), "Import did not reach the write-ahead binding boundary")
                self.assertFalse((workspace / ".facman-pack-import-reconstructed").exists())
                metadata.write_bytes(original + b"\n ")
                (workspace / ".facman-modpack-import-precreate-release").write_bytes(b"release\n")
                out, err = process.communicate(timeout=20)
                self.assertEqual((3, ""), (process.returncode, err), out)
                envelope = json.loads(out)
                self.assertEqual("facman.transport_response.v2", envelope["schema"])
                payload = envelope.get("payload")
                refusal_code = payload["refusal"]["code"] if payload is not None else envelope["error"]["code"]
                self.assertEqual("modpack_install_incompatible", refusal_code)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate(timeout=10)
            stage = workspace / ".facman-pack-import-reconstructed"
            self.assertTrue(stage.is_dir())
            self.assertFalse((stage / "instance.v1.json").exists())
            self.assertFalse((stage / "config/config.ini").exists())
            self.assertFalse((workspace / "instances/reconstructed").exists())
            transactions = call(workspace, "workspace", "recovery", "inspect")["transactions"]
            tx = next(item["transaction_id"] for item in transactions if item["command_id"] == "modsets.import")
            journal = json.loads((workspace / "transactions" / f"{tx}.transaction.v1.json").read_bytes())
            binding = json.loads(journal["operation_context"])
            bound = next(item for item in binding["files"] if Path(item["path"]) == metadata)
            self.assertEqual((len(original), digest(original)), (bound["size"], bound["sha256"]))
            self.assertEqual(original + b"\n ", metadata.read_bytes())
            self.assertNotIn("pack_inventory_bound", journal["completed_steps"])
            self.assertEqual(source_before, snapshot(source))

    def test_incomplete_extraction_is_retained_and_recovery_does_not_delete_it(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            workspace = Path(value)
            _, pack = self.make_pack(workspace)
            self.import_pack(workspace, pack, success=False,
                             env=dict(os.environ, FACMAN_TEST_MODPACK_IMPORT_EXTRACT_FAULT="after_entry"))
            stage = workspace / ".facman-pack-import-reconstructed"
            (stage / "foreign.txt").write_bytes(b"retained player data")
            before = snapshot(stage)
            transactions = call(workspace, "workspace", "recovery", "inspect")["transactions"]
            tx = next(item["transaction_id"] for item in transactions if item["command_id"] == "modsets.import")
            journal_path = workspace / "transactions" / f"{tx}.transaction.v1.json"
            journal_before = journal_path.read_bytes()
            journal = json.loads(journal_before)
            self.assertIn("pack_source_inventory_bound", journal["completed_steps"])
            self.assertNotIn("pack_inventory_bound", journal["completed_steps"])
            binding = json.loads(journal["operation_context"])
            self.assertEqual("facman.modpack_import_install.v1", binding["schema"])
            self.assertTrue(binding["root_identity"])
            self.assertTrue(binding["files"])
            source_binding = binding["source_binding"]
            with zipfile.ZipFile(pack) as archive:
                expected = {name: (len(archive.read(name)), digest(archive.read(name))) for name in archive.namelist()}
                self.assertEqual(expected, {item["path"]: (item["size"], item["sha256"]) for item in journal["expected_files"]})
                self.assertEqual(dict(schema="facman.modpack_import_source.v1", archive_sha256=digest(pack.read_bytes()),
                    archive_size=pack.stat().st_size, manifest_sha256=digest(archive.read("modpack-manifest.v1.json")),
                    lock_sha256=digest(archive.read("modset-lock.v1.json")), instance_id="reconstructed", install_id="fixture",
                    display_name="Restored pack"), source_binding)
            workspace_before_plan = snapshot(workspace)
            plan = call(workspace, "workspace", "recovery", "plan", tx)
            self.assertEqual(["verify_bound_source_and_resume_missing_pack_files"], plan["transactions"][0]["actions"])
            self.assertEqual(workspace_before_plan, snapshot(workspace))
            refused = call(workspace, "workspace", "recovery", "apply", tx, success=False)
            self.assertEqual("recovery_modpack_import_unsafe", refused["refusal"]["code"])
            self.assertEqual(before, snapshot(stage))
            self.assertEqual(journal_before, journal_path.read_bytes())
            self.assertFalse((workspace / "instances/reconstructed").exists())

    def partial_import(self, workspace: Path, pack: Path, *, generated: bool = False, install: str = "fixture") -> tuple[str, Path, Path]:
        setting = "FACMAN_TEST_MODPACK_IMPORT_GENERATE_FAULT" if generated else "FACMAN_TEST_MODPACK_IMPORT_EXTRACT_FAULT"
        self.import_pack(workspace, pack, success=False, install=install, env=dict(os.environ, **{setting: "after_entry"}))
        transactions = call(workspace, "workspace", "recovery", "inspect")["transactions"]
        tx = next(item["transaction_id"] for item in transactions if item["command_id"] == "modsets.import")
        return tx, workspace / ".facman-pack-import-reconstructed", workspace / "transactions" / f"{tx}.transaction.v1.json"

    def assert_retained_files(self, stage: Path, saved: dict[str, tuple[int, bytes]]) -> None:
        for name, (inode, data) in saved.items():
            path = stage / name
            self.assertEqual(data, path.read_bytes(), name)
            self.assertEqual(inode, path.stat().st_ino, name)

    def retained_files(self, stage: Path) -> dict[str, tuple[int, bytes]]:
        return {path.relative_to(stage).as_posix(): (path.stat().st_ino, path.read_bytes())
                for path in stage.rglob("*") if path.is_file()}

    def test_missing_entry_recovery_survives_a_second_interruption_and_preserves_existing_objects(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman partial pack ") as value:
            workspace = Path(value)
            source, pack = self.make_pack(workspace, b"exact offline binary settings\0\xff")
            source_before = snapshot(source)
            tx, stage, journal_path = self.partial_import(workspace, pack)
            original = self.retained_files(stage)
            journal_before = journal_path.read_bytes()
            with zipfile.ZipFile(pack) as archive:
                self.assertLess(len(original) - 2, len(archive.namelist()))
            plan = call(workspace, "workspace", "recovery", "plan", tx)
            self.assertEqual(["verify_bound_source_and_resume_missing_pack_files"], plan["transactions"][0]["actions"])
            call(workspace, "workspace", "recovery", "apply", tx, success=False,
                 env=dict(os.environ, FACMAN_TEST_MODPACK_IMPORT_EXTRACT_FAULT="after_entry"))
            self.assert_retained_files(stage, original)
            second = self.retained_files(stage)
            self.assertGreater(len(second), len(original))
            self.assertEqual(journal_before, journal_path.read_bytes())
            self.assertFalse((workspace / "instances/reconstructed").exists())
            recovered = call(workspace, "workspace", "recovery", "apply", tx)
            self.assertEqual("complete", recovered["transactions"][0]["state"])
            target = workspace / "instances/reconstructed"
            self.assert_retained_files(target, {name: item for name, item in second.items() if not name.startswith(".facman-")})
            self.assert_reconstruction(workspace, pack)
            self.assertEqual(source_before, snapshot(source))
            call(workspace, "workspace", "recovery", "apply", tx)

    def test_generated_intent_precedes_writes_and_resumes_missing_generated_files(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            workspace = Path(value)
            _, pack = self.make_pack(workspace, b"preserved settings")
            tx, stage, journal_path = self.partial_import(workspace, pack, generated=True)
            journal = json.loads(journal_path.read_bytes())
            self.assertIn("pack_generated_inventory_bound", journal["completed_steps"])
            self.assertNotIn("pack_inventory_bound", journal["completed_steps"])
            generated = {"mods/modset-lock.v1.json", "instance.v1.json", "config/config.ini", "modpack-import.v1.json"}
            with zipfile.ZipFile(pack) as archive:
                self.assertEqual(set(archive.namelist()) | generated, {item["path"] for item in journal["expected_files"]})
            self.assertEqual(1, sum((stage / name).exists() for name in generated))
            before = self.retained_files(stage)
            call(workspace, "workspace", "recovery", "apply", tx, success=False,
                 env=dict(os.environ, FACMAN_TEST_MODPACK_IMPORT_GENERATE_FAULT="after_entry"))
            self.assert_retained_files(stage, before)
            self.assertEqual(2, sum((stage / name).exists() for name in generated))
            second = self.retained_files(stage)
            recovered = call(workspace, "workspace", "recovery", "apply", tx)
            self.assertEqual("complete", recovered["transactions"][0]["state"])
            self.assert_retained_files(workspace / "instances/reconstructed",
                {name: item for name, item in second.items() if not name.startswith(".facman-")})
            self.assert_reconstruction(workspace, pack)

    def test_partial_recovery_refuses_changed_source_context_inventory_and_markers_without_effects(self) -> None:
        for change in ("archive", "complete_file", "truncated_file", "source_inventory", "context_extra", "binding_extra",
                       "binding_request", "transaction_marker", "archive_marker", "missing_marker", "fractional_inventory", "negative_inventory",
                       "oversize_inventory", "beyond_exact_integer", "beyond_uint64", "inventory_extra", "workspace_identity", "legacy"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as value:
                workspace = Path(value)
                _, pack = self.make_pack(workspace)
                tx, stage, journal_path = self.partial_import(workspace, pack)
                journal = json.loads(journal_path.read_bytes())
                if change == "archive":
                    pack.write_bytes(pack.read_bytes() + b"changed source")
                elif change in ("complete_file", "truncated_file"):
                    path = next(path for path in stage.rglob("*") if path.is_file() and not path.name.startswith(".facman-"))
                    data = path.read_bytes()
                    path.write_bytes(data[:-1] if change == "truncated_file" else bytes([data[0] ^ 1]) + data[1:])
                elif change in ("source_inventory", "fractional_inventory", "negative_inventory", "oversize_inventory", "beyond_exact_integer", "beyond_uint64", "inventory_extra", "workspace_identity"):
                    if change == "source_inventory": journal["expected_files"][0]["sha256"] = "0" * 64
                    elif change == "fractional_inventory": journal["expected_files"][0]["size"] += 0.5
                    elif change == "negative_inventory": journal["expected_files"][0]["size"] = -1
                    elif change == "oversize_inventory": journal["expected_files"][0]["size"] = 4 * 1024**3 + 1
                    elif change == "beyond_exact_integer": journal["expected_files"][0]["size"] = 2**53 + 1
                    elif change == "beyond_uint64": journal["expected_files"][0]["size"] = 1e100
                    elif change == "inventory_extra": journal["expected_files"][0]["grant_write"] = True
                    else: journal["workspace_id"] = "different-workspace"
                elif change.startswith("context") or change.startswith("binding") or change == "legacy":
                    context = json.loads(journal["operation_context"])
                    if change == "context_extra": context["grant_write"] = True
                    elif change == "binding_extra": context["source_binding"]["grant_write"] = True
                    elif change == "binding_request": context["source_binding"]["instance_id"] = "some-other-instance"
                    else:
                        del context["source_binding"]
                        journal["completed_steps"].remove("pack_source_inventory_bound")
                    journal["operation_context"] = json.dumps(context)
                else:
                    marker = stage / (".facman-archive-staging.v1" if change == "archive_marker" else ".facman-transaction-staging.v2.json")
                    if change == "missing_marker": marker.unlink()
                    else: marker.write_bytes(b"foreign marker")
                if change in ("source_inventory", "context_extra", "binding_extra", "binding_request", "fractional_inventory", "negative_inventory",
                              "oversize_inventory", "beyond_exact_integer", "beyond_uint64", "inventory_extra", "workspace_identity", "legacy"):
                    journal_path.write_text(json.dumps(journal))
                stage_before, journal_before = snapshot(stage), journal_path.read_bytes()
                if change == "legacy":
                    plan = call(workspace, "workspace", "recovery", "plan", tx)
                    self.assertEqual(["preserve_incomplete_pack_staging_for_review"], plan["transactions"][0]["actions"])
                refused = call(workspace, "workspace", "recovery", "apply", tx, success=False)
                self.assertEqual("recovery_modpack_import_unsafe", refused["refusal"]["code"])
                self.assertEqual(stage_before, snapshot(stage))
                self.assertEqual(journal_before, journal_path.read_bytes())
                self.assertFalse((workspace / "instances/reconstructed").exists())

    def test_generated_recovery_refuses_drift_without_new_file_or_journal_effects(self) -> None:
        for change in ("file", "truncated", "intent", "missing_raw", "foreign", "foreign_lock"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as value:
                workspace = Path(value)
                _, pack = self.make_pack(workspace)
                tx, stage, journal_path = self.partial_import(workspace, pack, generated=True)
                if change in ("file", "truncated"):
                    path = stage / "mods/modset-lock.v1.json"
                    data = path.read_bytes(); path.write_bytes(data[:-1] if change == "truncated" else data + b"changed")
                elif change == "intent":
                    journal = json.loads(journal_path.read_bytes())
                    next(item for item in journal["expected_files"] if item["path"] == "config/config.ini")["sha256"] = "0" * 64
                    journal_path.write_text(json.dumps(journal))
                elif change == "missing_raw": (stage / "modpack-manifest.v1.json").unlink()
                elif change == "foreign": (stage / "saves/player-data.dat").write_bytes(b"keep player data")
                else:
                    (workspace / "transactions" / f"{tx}.transaction.v1.json.recovery.lock").write_bytes(b"foreign lock")
                stage_before, journal_before = snapshot(stage), journal_path.read_bytes()
                refused = call(workspace, "workspace", "recovery", "apply", tx, success=False)
                self.assertEqual("recovery_lock_contended" if change == "foreign_lock" else "recovery_modpack_import_unsafe",
                                 refused["refusal"]["code"])
                self.assertEqual(stage_before, snapshot(stage))
                self.assertEqual(journal_before, journal_path.read_bytes())
                self.assertFalse((workspace / "instances/reconstructed").exists())

    def test_live_recovery_lock_and_late_foreign_or_expected_entries_prevent_further_writes(self) -> None:
        for change in ("foreign", "expected", "directory"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as value:
                workspace = Path(value)
                _, pack = self.make_pack(workspace)
                tx, stage, journal_path = self.partial_import(workspace, pack)
                journal_before = journal_path.read_bytes()
                process = subprocess.Popen([str(facman_executable()), "--workspace", str(workspace), "workspace", "recovery",
                    "apply", tx, "--json"], env=dict(os.environ, FACMAN_TEST_MODPACK_IMPORT_PAUSE="recovery-ready"),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    signal = workspace / ".facman-modpack-import-recovery-ready-paused"
                    deadline = time.monotonic() + 20
                    while not signal.exists() and time.monotonic() < deadline:
                        if process.poll() is not None:
                            stdout, stderr = process.communicate(); self.fail(stdout + stderr)
                        time.sleep(0.025)
                    self.assertTrue(signal.exists())
                    refused = call(workspace, "workspace", "recovery", "apply", tx, success=False)
                    self.assertEqual("recovery_lock_contended", refused["refusal"]["code"])
                    if change == "foreign": (stage / "player-save.dat").write_bytes(b"foreign bytes")
                    elif change == "directory":
                        # A known directory which was absent at admission has no captured identity.
                        self.assertFalse((stage / "mods").exists()); (stage / "mods").mkdir()
                    else:
                        with zipfile.ZipFile(pack) as archive:
                            name = next(name for name in archive.namelist() if not (stage / name).exists() and "/" not in name)
                        (stage / name).write_bytes(b"late incomplete expected-name file")
                    before = snapshot(stage), sorted(path.relative_to(stage).as_posix() for path in stage.rglob("*") if path.is_dir())
                    (workspace / ".facman-modpack-import-recovery-ready-release").write_text("release\n")
                    stdout, stderr = process.communicate(timeout=20)
                    self.assertNotEqual(0, process.returncode, stdout + stderr)
                    self.assertEqual("recovery_modpack_import_unsafe", json.loads(stdout)["payload"]["refusal"]["code"])
                    self.assertEqual(before, (snapshot(stage), sorted(path.relative_to(stage).as_posix() for path in stage.rglob("*") if path.is_dir())))
                    self.assertEqual(journal_before, journal_path.read_bytes())
                    self.assertFalse((workspace / "instances/reconstructed").exists())
                finally:
                    if process.poll() is None: process.kill()
                    process.communicate(timeout=10)

    def test_partial_recovery_preserves_original_install_binding_after_metadata_drift(self) -> None:
        for generated in (False, True):
            with self.subTest(generated=generated), tempfile.TemporaryDirectory() as value:
                workspace = Path(value)
                _, pack = self.make_pack(workspace)
                install = workspace / "private-local-install"
                shutil.copytree(FIXTURE_INSTALL, install)
                call(workspace, "installs", "import", str(install), "--id", "private-local")
                tx, stage, journal_path = self.partial_import(workspace, pack, generated=generated, install="private-local")
                metadata = install / "data/base/info.json"
                metadata.write_bytes(metadata.read_bytes() + b"\n")
                before, journal_before = snapshot(stage), journal_path.read_bytes()
                refused = call(workspace, "workspace", "recovery", "apply", tx, success=False)
                self.assertEqual("recovery_modpack_import_unsafe", refused["refusal"]["code"])
                self.assertEqual(before, snapshot(stage))
                self.assertEqual(journal_before, journal_path.read_bytes())
                self.assertFalse((workspace / "instances/reconstructed").exists())


    def test_process_loss_adopts_original_lock_and_recovers_partial_raw_and_generated_states(self) -> None:
        for point in ("extracted-entry", "generated-entry"):
            with self.subTest(point=point), tempfile.TemporaryDirectory() as value:
                workspace = Path(value)
                source, pack = self.make_pack(workspace, b"process-loss settings\0\xff")
                source_before = snapshot(source)
                tx = self.interrupt(workspace, pack, point)
                stage = workspace / ".facman-pack-import-reconstructed"
                journal_path = workspace / "transactions" / f"{tx}.transaction.v1.json"
                journal = json.loads(journal_path.read_bytes())
                self.assertEqual("staging", journal["state"])
                self.assertIn("pack_source_inventory_bound", journal["completed_steps"])
                self.assertNotIn("pack_inventory_bound", journal["completed_steps"])
                self.assertEqual(point == "generated-entry", "pack_generated_inventory_bound" in journal["completed_steps"])
                stale_lock = workspace / "transactions" / f"{tx}.transaction.v1.json.recovery.lock"
                self.assertTrue(stale_lock.exists())
                lock = json.loads(stale_lock.read_bytes())
                self.assertEqual("facman.recovery_lock.v1", lock["schema"])
                self.assertTrue(lock["identity"])
                before = self.retained_files(stage)
                recovered = call(workspace, "workspace", "recovery", "apply", tx)
                self.assertEqual("complete", recovered["transactions"][0]["state"])
                self.assertFalse(stale_lock.exists())
                self.assert_retained_files(workspace / "instances/reconstructed",
                    {name: item for name, item in before.items() if not name.startswith(".facman-")})
                self.assert_reconstruction(workspace, pack)
                self.assertEqual(source_before, snapshot(source))

    def test_process_loss_before_staging_reconstructs_from_the_original_durable_source_binding(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman precreate pack ") as value:
            workspace = Path(value)
            source, pack = self.make_pack(workspace, b"before-create settings\0\xff")
            before = snapshot(source)
            tx = self.interrupt(workspace, pack, "precreate")
            stage = workspace / ".facman-pack-import-reconstructed"
            journal_path = workspace / "transactions" / f"{tx}.transaction.v1.json"
            journal = json.loads(journal_path.read_bytes())
            self.assertEqual("requested", journal["state"])
            self.assertFalse(stage.exists())
            self.assertFalse(journal["effect_file_identity"])
            self.assertIn("pack_source_inventory_bound", journal["completed_steps"])
            original_binding = journal["operation_context"]
            recovered = call(workspace, "workspace", "recovery", "apply", tx)
            self.assertEqual("complete", recovered["transactions"][0]["state"])
            self.assertEqual(original_binding, json.loads(journal_path.read_bytes())["operation_context"])
            self.assert_reconstruction(workspace, pack)
            self.assertEqual(before, snapshot(source))
            self.assertFalse((workspace / "transactions" / f"{tx}.transaction.v1.json.recovery.lock").exists())

    def test_recovery_before_staging_can_itself_be_interrupted_after_a_complete_entry(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            workspace = Path(value)
            _, pack = self.make_pack(workspace, b"restart the original import\0\xff")
            tx = self.interrupt(workspace, pack, "precreate")
            call(workspace, "workspace", "recovery", "apply", tx, success=False,
                 env=dict(os.environ, FACMAN_TEST_MODPACK_IMPORT_EXTRACT_FAULT="after_entry"))
            stage = workspace / ".facman-pack-import-reconstructed"
            original = self.retained_files(stage)
            self.assertGreater(len(original), 2)
            journal = json.loads((workspace / "transactions" / f"{tx}.transaction.v1.json").read_bytes())
            self.assertEqual("staging", journal["state"])
            self.assertTrue(journal["effect_file_identity"])
            self.assertIn("pack_extraction_started", journal["completed_steps"])
            call(workspace, "workspace", "recovery", "apply", tx)
            self.assert_retained_files(workspace / "instances/reconstructed",
                                       {name: item for name, item in original.items() if not name.startswith(".facman-")})
            self.assert_reconstruction(workspace, pack)

    def test_precreate_recovery_refuses_changed_source_install_or_existing_foreign_staging(self) -> None:
        for change in ("source", "install", "foreign", "formerly_bound"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as value:
                workspace = Path(value)
                _, pack = self.make_pack(workspace)
                tx = self.interrupt(workspace, pack, "precreate")
                stage = workspace / ".facman-pack-import-reconstructed"
                journal_path = workspace / "transactions" / f"{tx}.transaction.v1.json"
                if change == "source":
                    pack.write_bytes(pack.read_bytes() + b"changed original source")
                elif change == "install":
                    journal = json.loads(journal_path.read_bytes())
                    install_binding = json.loads(journal["operation_context"])
                    metadata = Path(install_binding["files"][0]["path"])
                    metadata.write_bytes(metadata.read_bytes() + b"\n")
                elif change == "foreign":
                    stage.mkdir(); (stage / "user-save.dat").write_bytes(b"preserve foreign data")
                else:
                    journal = json.loads(journal_path.read_bytes())
                    journal["effect_file_identity"] = "formerly-created-directory"
                    journal["completed_steps"].append("pack_extraction_started")
                    journal["state"] = "staging"
                    journal_path.write_text(json.dumps(journal), encoding="utf-8")
                before = snapshot(stage) if stage.exists() else None
                journal_before = journal_path.read_bytes()
                refused = call(workspace, "workspace", "recovery", "apply", tx, success=False)
                self.assertEqual("recovery_modpack_import_unsafe", refused["refusal"]["code"])
                self.assertEqual(journal_before, journal_path.read_bytes())
                self.assertEqual(before, snapshot(stage) if stage.exists() else None)
                self.assertFalse((workspace / "instances/reconstructed").exists())

    def test_late_foreign_staging_before_recovery_exclusive_creation_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            workspace = Path(value)
            _, pack = self.make_pack(workspace)
            tx = self.interrupt(workspace, pack, "precreate")
            journal_path = workspace / "transactions" / f"{tx}.transaction.v1.json"
            stage = workspace / ".facman-pack-import-reconstructed"
            process = subprocess.Popen([str(facman_executable()), "--workspace", str(workspace), "workspace", "recovery",
                "apply", tx, "--json"], env=dict(os.environ, FACMAN_TEST_MODPACK_IMPORT_PAUSE="recovery-precreate"),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                signal = workspace / ".facman-modpack-import-recovery-precreate-paused"
                deadline = time.monotonic() + 20
                while not signal.exists() and time.monotonic() < deadline:
                    if process.poll() is not None:
                        stdout, stderr = process.communicate(); self.fail(stdout + stderr)
                    time.sleep(0.025)
                self.assertTrue(signal.exists())
                stage.mkdir(); (stage / "player-world.dat").write_bytes(b"foreign player world")
                before = snapshot(stage)
                (workspace / ".facman-modpack-import-recovery-precreate-release").write_text("release\n")
                stdout, stderr = process.communicate(timeout=20)
                self.assertNotEqual(0, process.returncode, stdout + stderr)
                self.assertEqual("recovery_modpack_import_unsafe", json.loads(stdout)["payload"]["refusal"]["code"])
                self.assertEqual(before, snapshot(stage))
                self.assertFalse((stage / ".facman-transaction-staging.v2.json").exists())
                self.assertFalse(json.loads(journal_path.read_bytes())["effect_file_identity"])
                self.assertFalse((workspace / "instances/reconstructed").exists())
            finally:
                if process.poll() is None: process.kill()
                process.communicate(timeout=10)

    def test_precreate_recovery_refuses_later_unknown_duplicate_or_phase_inconsistent_evidence(self) -> None:
        for change in ("verified", "published", "unknown", "duplicate", "reversed", "phase", "missing_prefix"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as value:
                workspace = Path(value)
                _, pack = self.make_pack(workspace)
                tx = self.interrupt(workspace, pack, "precreate")
                stage = workspace / ".facman-pack-import-reconstructed"
                journal_path = workspace / "transactions" / f"{tx}.transaction.v1.json"
                journal = json.loads(journal_path.read_bytes())
                journal["state"] = "recovery_required"
                if change in ("verified", "published", "unknown"):
                    step = dict(verified="pack_instance_verified", published="pack_published_no_replace", unknown="unsupported_step")[change]
                    journal["completed_steps"].append(step)
                elif change == "duplicate": journal["completed_steps"].append("pack_source_inventory_bound")
                elif change == "reversed": journal["completed_steps"].insert(0, "request_validated")
                elif change == "phase": journal["state"] = "planned"
                else: journal["completed_steps"].append("target_and_sources_validated")
                journal_path.write_text(json.dumps(journal), encoding="utf-8")
                before = journal_path.read_bytes()
                refused = call(workspace, "workspace", "recovery", "apply", tx, success=False)
                self.assertEqual("recovery_modpack_import_unsafe", refused["refusal"]["code"])
                self.assertEqual(before, journal_path.read_bytes())
                self.assertFalse(stage.exists())
                self.assertFalse((workspace / "instances/reconstructed").exists())

    def test_precreate_recovery_resumes_valid_original_and_recovery_early_journal_boundaries(self) -> None:
        cases = (("validated", ["request_validated"]),
                 ("planned", ["request_validated", "target_and_sources_validated"]),
                 ("recovery_required", []),
                 ("planned", ["recovery_source_validated", "recovery_source_planned"]),
                 ("planned", ["request_validated", "recovery_source_planned"]))
        for state, steps in cases:
            with self.subTest(state=state, steps=steps), tempfile.TemporaryDirectory() as value:
                workspace = Path(value)
                _, pack = self.make_pack(workspace, b"preserve settings at every early boundary\0\xff")
                tx = self.interrupt(workspace, pack, "precreate")
                journal_path = workspace / "transactions" / f"{tx}.transaction.v1.json"
                journal = json.loads(journal_path.read_bytes())
                original_binding = journal["operation_context"]
                journal["state"] = state
                journal["completed_steps"].extend(steps)
                journal_path.write_text(json.dumps(journal), encoding="utf-8")
                call(workspace, "workspace", "recovery", "apply", tx)
                self.assertEqual(original_binding, json.loads(journal_path.read_bytes())["operation_context"])
                self.assert_reconstruction(workspace, pack)



if __name__ == "__main__":
    unittest.main()
