from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from native_cli import invoke
from tools import json_contract

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"


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
                self.skipTest(f"hard links unavailable: {error}")
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


if __name__ == "__main__":
    unittest.main()
