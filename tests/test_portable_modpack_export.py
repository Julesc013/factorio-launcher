# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

import jsonschema

from native_cli import facman_executable
from test_local_modset_solver import ROOT, SCHEMA_ROOT, call, setup, snapshot, write_mod
from tools import json_contract


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class PortableModpackExportTests(unittest.TestCase):
    def test_manifest_binds_exact_selected_content_settings_and_raw_provenance(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman portable export ") as value:
            workspace = Path(value)
            instance = setup(workspace)
            mods = instance / "mods"
            write_mod(mods / "simple_1.0.0.zip", "simple", "1.0.0")
            write_mod(mods / "unused_1.0.0.zip", "unused", "1.0.0")
            call(workspace, "modsets", "apply", "solver", "--enable", "simple")
            settings = b"\x01\x00exact startup settings\x00\xff"
            (mods / "mod-settings.dat").write_bytes(settings)
            (instance / "config/config.ini").write_bytes(b"private-value=not-portable\n")
            before = snapshot(instance), snapshot(workspace / "modsets")
            output = workspace / "pack.zip"
            exported = call(workspace, "modsets", "export", "solver", str(output))
            with zipfile.ZipFile(output) as archive:
                self.assertEqual({"modpack-manifest.v1.json", "modset-lock.v1.json",
                                  "mods/simple_1.0.0.zip", "mods/mod-list.json",
                                  "mods/mod-settings.dat"}, set(archive.namelist()))
                self.assertEqual(5, exported["files"])
                manifest = json.loads(archive.read("modpack-manifest.v1.json"))
                validator = jsonschema.Draft202012Validator(json_contract.load_schema(
                    SCHEMA_ROOT / "factorio_modpack_manifest.v1.schema.json"))
                validator.validate(manifest)
                lock = manifest["content_lock"]
                jsonschema.Draft202012Validator(json_contract.load_schema(
                    SCHEMA_ROOT / "factorio_content_lock.v1.schema.json")).validate(lock)
                for invalid in ("duplicate_setting", "missing_source_lock", "absent_with_digest"):
                    changed_manifest = copy.deepcopy(manifest)
                    if invalid == "duplicate_setting":
                        changed_manifest["settings"][1] = changed_manifest["settings"][0]
                    elif invalid == "missing_source_lock":
                        del changed_manifest["source_lock"]
                    else:
                        changed_manifest["settings"][0]["state"] = "absent"
                    self.assertTrue(list(validator.iter_errors(changed_manifest)), invalid)
                raw_lock = (mods / "modset-lock.v1.json").read_bytes()
                self.assertEqual(raw_lock, archive.read("modset-lock.v1.json"))
                self.assertEqual({"path": "modset-lock.v1.json", "blob": {
                    "algorithm": "sha256", "sha256": digest(raw_lock), "size": len(raw_lock)}},
                    manifest["source_lock"])
                self.assertEqual(digest(raw_lock), lock["source_lock_sha256"])
                self.assertEqual("sha256_bound", lock["startup_settings_state"])
                self.assertEqual(digest(settings), lock["startup_settings_sha256"])
                self.assertTrue(manifest["startup_settings_bound"])
                self.assertEqual(["simple"], [item["name"] for item in manifest["artifacts"]])
                for item in manifest["artifacts"]:
                    data = archive.read("mods/" + item["file_name"])
                    self.assertEqual({"algorithm": "sha256", "sha256": digest(data), "size": len(data)}, item["blob"])
                    self.assertEqual((mods / item["file_name"]).read_bytes(), data)
                for item in manifest["settings"]:
                    data = archive.read(item["path"])
                    self.assertEqual({"path": item["path"], "state": "present", "size": len(data),
                                      "sha256": digest(data)}, item)
                    self.assertEqual((instance / item["path"]).read_bytes(), data)
                portable_text = json.dumps(manifest)
                self.assertNotIn(str(workspace), portable_text)
                self.assertNotIn("private-value", portable_text)
                self.assertFalse(manifest["network_authority"])
                self.assertFalse(manifest["contains_credentials"])
                self.assertFalse(manifest["contains_factorio_binaries"])
            repeated = workspace / "repeat.zip"
            call(workspace, "modsets", "export", "solver", str(repeated))
            self.assertEqual(output.read_bytes(), repeated.read_bytes())
            refused = call(workspace, "modsets", "export", "solver", str(output), success=False)
            self.assertEqual("persistent_target_exists", refused["refusal"]["code"])
            self.assertEqual(output.read_bytes(), repeated.read_bytes())
            self.assertEqual(before, (snapshot(instance), snapshot(workspace / "modsets")))

    def test_absent_and_empty_startup_settings_have_distinct_bound_identities(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman settings presence ") as value:
            workspace = Path(value)
            mods = setup(workspace) / "mods"
            call(workspace, "modsets", "apply", "solver", "--enable", "base")
            records = []
            for present in (False, True):
                if present:
                    (mods / "mod-settings.dat").write_bytes(b"")
                output = workspace / ("empty.zip" if present else "absent.zip")
                call(workspace, "modsets", "export", "solver", str(output))
                with zipfile.ZipFile(output) as archive:
                    manifest = json.loads(archive.read("modpack-manifest.v1.json"))
                    records.append(manifest)
                    self.assertEqual(present, "mods/mod-settings.dat" in archive.namelist())
                    self.assertEqual([], manifest["artifacts"])
                    self.assertTrue(manifest["startup_settings_bound"])
                    entry = next(item for item in manifest["settings"] if item["path"] == "mods/mod-settings.dat")
                    self.assertEqual({"path": "mods/mod-settings.dat", "state": "present" if present else "absent",
                                      "size": 0, "sha256": digest(b"") if present else ""}, entry)
                    self.assertEqual("sha256_bound" if present else "absent", manifest["content_lock"]["startup_settings_state"])
            self.assertNotEqual(records[0]["modpack_manifest_sha256"], records[1]["modpack_manifest_sha256"])
            self.assertNotEqual(records[0]["content_lock_sha256"], records[1]["content_lock_sha256"])

    def test_settings_changes_during_export_refuse_and_preserve_the_changed_source(self) -> None:
        for change in ("bytes", "appears", "disappears", "same_bytes_new_file", "mod_list"):
            with self.subTest(change=change), tempfile.TemporaryDirectory(prefix="facman settings drift ") as value:
                workspace = Path(value)
                mods = setup(workspace) / "mods"
                call(workspace, "modsets", "apply", "solver", "--enable", "base")
                settings = mods / "mod-settings.dat"
                if change != "appears":
                    settings.write_bytes(b"original settings")
                output = workspace / "refused.zip"
                process = self.start_paused_export(workspace, output)
                try:
                    staging = self.wait_for_stage(workspace, process)
                    if change == "disappears":
                        settings.unlink()
                    elif change == "same_bytes_new_file":
                        replacement = workspace / "replacement.dat"
                        replacement.write_bytes(settings.read_bytes())
                        os.replace(replacement, settings)
                    elif change == "mod_list":
                        (mods / "mod-list.json").write_bytes(b'{"mods":[]}\n')
                    else:
                        settings.write_bytes(b"changed settings")
                    changed = snapshot(mods)
                    (staging / ".facman-modset-export-release").touch()
                    stdout, stderr = process.communicate(timeout=20)
                    self.assertNotEqual(0, process.returncode, stdout + stderr)
                    self.assertEqual("modset_verification_failed", json.loads(stdout)["payload"]["refusal"]["code"])
                    self.assertFalse(output.exists())
                    self.assertEqual(changed, snapshot(mods))
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.communicate()

    def test_foreign_staging_content_survives_refused_export(self) -> None:
        for leaf in ("foreign-user-data.txt", "modpack-manifest.v1.json"):
            with self.subTest(leaf=leaf), tempfile.TemporaryDirectory(prefix="facman foreign export stage ") as value:
                workspace = Path(value)
                mods = setup(workspace) / "mods"
                call(workspace, "modsets", "apply", "solver", "--enable", "base")
                process = self.start_paused_export(workspace, workspace / "refused.zip")
                try:
                    staging = self.wait_for_stage(workspace, process)
                    foreign = staging / leaf
                    if foreign.exists():
                        os.replace(foreign, workspace / "original-manifest.json")
                    foreign.write_bytes(b"preserve this data")
                    (mods / "mod-settings.dat").write_bytes(b"new settings")
                    (staging / ".facman-modset-export-release").touch()
                    stdout, stderr = process.communicate(timeout=20)
                    self.assertNotEqual(0, process.returncode, stdout + stderr)
                    self.assertFalse((workspace / "refused.zip").exists())
                    self.assertEqual(b"preserve this data", foreign.read_bytes())
                    pending = call(workspace, "workspace", "recovery", "inspect")["transactions"]
                    transaction = next(item for item in pending if item["command_id"] == "modsets.export")
                    transaction_id = transaction["transaction_id"]
                    plan = call(workspace, "workspace", "recovery", "plan", transaction_id)
                    self.assertEqual(["preserve_portable_export_staging_for_review"], plan["transactions"][0]["actions"])
                    before_recovery = snapshot(staging), snapshot(mods)
                    refused = call(workspace, "workspace", "recovery", "apply", transaction_id, success=False)
                    self.assertEqual("recovery_staging_unrecognized", refused["refusal"]["code"])
                    self.assertEqual(before_recovery, (snapshot(staging), snapshot(mods)))
                finally:
                    if process.poll() is None:
                        process.kill()
                    process.communicate()

    def test_linked_startup_settings_are_refused_where_supported(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman linked settings ") as value:
            workspace = Path(value)
            mods = setup(workspace) / "mods"
            call(workspace, "modsets", "apply", "solver", "--enable", "base")
            foreign = workspace / "foreign.dat"
            foreign.write_bytes(b"foreign settings")
            try:
                (mods / "mod-settings.dat").symlink_to(foreign)
            except OSError as error:
                self.skipTest(f"not_applicable: settings symlink unavailable: {error}")
            output = workspace / "linked.zip"
            call(workspace, "modsets", "export", "solver", str(output), success=False)
            self.assertFalse(output.exists())
            self.assertTrue((mods / "mod-settings.dat").is_symlink())
            self.assertEqual(b"foreign settings", foreign.read_bytes())

    def start_paused_export(self, workspace: Path, output: Path) -> subprocess.Popen:
        return subprocess.Popen([str(facman_executable()), "--workspace", str(workspace),
                                 "modsets", "export", "solver", str(output), "--json"],
                                cwd=ROOT, env=dict(os.environ, FACMAN_TEST_MODSET_EXPORT_PAUSE_AFTER_STAGE="1"),
                                text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def wait_for_stage(self, workspace: Path, process: subprocess.Popen) -> Path:
        deadline = time.monotonic() + 10
        while process.poll() is None and time.monotonic() < deadline:
            for path in workspace.glob(".facman-modset-export-*"):
                if (path / ".facman-modset-export-paused").is_file():
                    return path
            time.sleep(0.02)
        self.fail("export did not reach the staged archive boundary")


if __name__ == "__main__":
    unittest.main()
