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

import jsonschema

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
        jsonschema.Draft202012Validator(json_contract.load_schema(
            SCHEMA_ROOT / "factorio_modpack_import.v1.schema.json")).validate(receipt)
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
            self.assertEqual(point != "verified", "reconstructed" in ids)
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
            refused = call(workspace, "workspace", "recovery", "apply", tx, success=False)
            self.assertEqual("recovery_modpack_import_unsafe", refused["refusal"]["code"])
            self.assertEqual(before, snapshot(stage))
            self.assertFalse((workspace / "instances/reconstructed").exists())


if __name__ == "__main__":
    unittest.main()
