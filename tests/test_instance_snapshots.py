# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from native_cli import invoke
from tools import json_contract


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"
FIXTURE_SAVE = ROOT / "tests" / "fixtures" / "factorio_saves" / "valid_simple_save" / "starter.zip"
SCHEMA_ROOT = ROOT / "contracts" / "schema" / "factorio"


def call(workspace: Path, *args: str) -> dict:
    code, stdout, stderr = invoke(["--workspace", str(workspace), *args, "--json"])
    if code != 0:
        raise AssertionError(stderr or stdout)
    return json.loads(stdout)


def refuse(workspace: Path, *args: str) -> dict:
    code, stdout, stderr = invoke(["--workspace", str(workspace), *args, "--json"])
    if code == 0:
        raise AssertionError(f"command unexpectedly succeeded: {stdout}")
    return json.loads(stdout or stderr)


def fixture(workspace: Path) -> Path:
    call(workspace, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture")
    call(workspace, "instances", "create", "Main", "--id", "main", "--install", "fixture")
    instance = workspace / "instances" / "main"
    shutil.copyfile(FIXTURE_SAVE, instance / "saves" / "starter.zip")
    (instance / "logs" / "excluded.log").write_text("volatile\n", encoding="utf-8")
    (instance / "cache" / "excluded.bin").write_bytes(b"cache")
    return instance


def assert_schema(test: unittest.TestCase, document: dict, schema_name: str) -> None:
    schema = json_contract.load_schema(SCHEMA_ROOT / schema_name)
    test.assertEqual([], json_contract.validate(document, schema), schema_name)


class InstanceSnapshotTests(unittest.TestCase):
    def test_reproducible_portable_snapshot_and_cross_workspace_restore(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman snapshot source ") as source_value, tempfile.TemporaryDirectory(
            prefix="facman snapshot destination "
        ) as destination_value:
            source = Path(source_value)
            destination = Path(destination_value)
            fixture(source)
            fixture(destination)

            created_source = call(source, "snapshots", "create", "main", "portable", "--save", "starter.zip")
            created_destination = call(destination, "snapshots", "create", "main", "portable", "--save", "starter.zip")
            assert_schema(self, created_source, "factorio_snapshot_report.v1.schema.json")
            self.assertTrue(created_source["portable"])
            self.assertTrue(created_source["deterministic"])
            self.assertFalse(created_source["secret_content_included"])

            source_archive = source / "snapshots" / "main" / "portable.zip"
            destination_archive = destination / "snapshots" / "main" / "portable.zip"
            self.assertEqual(source_archive.read_bytes(), destination_archive.read_bytes())
            self.assertEqual(
                hashlib.sha256(source_archive.read_bytes()).hexdigest(),
                hashlib.sha256(destination_archive.read_bytes()).hexdigest(),
            )

            with zipfile.ZipFile(source_archive) as archive:
                self.assertEqual(
                    ["config/config.ini", "instance.v1.json", "manifest/snapshot.v1.json", "saves/starter.zip"],
                    archive.namelist(),
                )
                manifest = json.loads(archive.read("manifest/snapshot.v1.json"))
                body = b"\n".join(archive.read(name) for name in archive.namelist())
            self.assertEqual("factorio.instance_snapshot.v1", manifest["schema"])
            self.assertEqual("lock_references_only", manifest["mod_policy"])
            self.assertIn("credentials", manifest["exclusions"])
            self.assertNotIn(str(source).encode(), body)
            self.assertNotIn(str(destination).encode(), body)
            self.assertFalse(any(
                item["path"].startswith(("logs/", "cache/", "locks/", "crash/"))
                for item in manifest["file_hashes"]
            ))

            listed = call(source, "snapshots", "list", "main")
            inspected = call(source, "snapshots", "inspect", "main", "portable")
            verified = call(source, "snapshots", "verify", "main", "portable")
            assert_schema(self, listed, "factorio_snapshots.v1.schema.json")
            assert_schema(self, inspected, "factorio_snapshot_report.v1.schema.json")
            assert_schema(self, verified, "factorio_snapshot_report.v1.schema.json")
            self.assertEqual("pass", verified["status"])

            live_difference = call(source, "instances", "diff", "main", "snapshot:portable")
            assert_schema(self, live_difference, "factorio_instance_diff.v1.schema.json")
            self.assertEqual("snapshot:portable", live_difference["right_ref"])
            self.assertTrue(all(live_difference["selected_settings_equal"].values()))
            self.assertTrue(live_difference["volatile_content_ignored"])

            restored = call(destination, "snapshots", "restore", str(source_archive), "restored")
            assert_schema(self, restored, "factorio_snapshot_report.v1.schema.json")
            self.assertEqual("restored", restored["instance_id"])
            restored_root = destination / "instances" / "restored"
            restored_manifest = json.loads((restored_root / "instance.v1.json").read_text(encoding="utf-8"))
            self.assertEqual("restored", restored_manifest["instance_id"])
            self.assertEqual("portable", restored_manifest["restored_from_snapshot"])
            self.assertEqual(FIXTURE_SAVE.read_bytes(), (restored_root / "saves" / "starter.zip").read_bytes())
            self.assertNotIn(str(source), (restored_root / "config" / "config.ini").read_text(encoding="utf-8"))
            refused = refuse(destination, "snapshots", "restore", str(source_archive), "restored")
            self.assertEqual("snapshot_restore_target_exists", refused["refusal"]["code"])

    def test_diff_integrity_refusal_and_retention_move_to_trash(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman snapshot policy ") as workspace_value:
            workspace = Path(workspace_value)
            instance = fixture(workspace)
            call(workspace, "snapshots", "create", "main", "before")
            (instance / "mods" / "modset-lock.v1.json").write_text(
                '{"schema":"factorio.modset_lock.v1","mods":[]}\n', encoding="utf-8"
            )
            call(workspace, "snapshots", "create", "main", "after")

            difference = call(workspace, "snapshots", "diff", "main", "before", "after")
            assert_schema(self, difference, "factorio_snapshot_diff.v1.schema.json")
            self.assertEqual(["mods/modset-lock.v1.json"], [item["path"] for item in difference["differences"]])

            plan = call(
                workspace, "snapshots", "retention", "plan", "main",
                "--keep-last", "1", "--maximum-total-bytes", "1",
            )
            assert_schema(self, plan, "factorio_snapshot_retention_report.v1.schema.json")
            self.assertEqual(1, plan["candidate_count"])
            self.assertFalse(plan["mutation_executed"])
            self.assertTrue((workspace / "snapshots" / "main" / "before.zip").is_file())

            applied = call(
                workspace, "snapshots", "retention", "apply", "main",
                "--keep-last", "1", "--maximum-total-bytes", "1",
            )
            assert_schema(self, applied, "factorio_snapshot_retention_report.v1.schema.json")
            self.assertEqual(1, applied["candidate_count"])
            self.assertFalse(applied["permanent_delete"])
            self.assertFalse((workspace / "snapshots" / "main" / "before.zip").exists())
            self.assertEqual(1, len(list((workspace / "trash" / "snapshots").rglob("before.zip"))))

            archive = workspace / "snapshots" / "main" / "after.zip"
            archive.write_bytes(archive.read_bytes() + b"tamper")
            refused = refuse(workspace, "snapshots", "verify", "main", "after")
            self.assertIn(refused["refusal"]["code"], {"snapshot_archive_invalid", "snapshot_hash_closure_mismatch"})


if __name__ == "__main__":
    unittest.main()
