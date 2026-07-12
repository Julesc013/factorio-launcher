# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import os
import tempfile
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


class SaveIndexRetentionTests(unittest.TestCase):
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
            stored_digest = json.loads(sidecar.read_text(encoding="utf-8"))["save_sha256"]

            write_save(first, b"changed opaque save")
            verified = call(workspace, "saves", "verify", "first.zip", "--instance", "save-index")
            self.assertEqual("drifted", verified["status"])
            self.assertEqual("drifted", verified["saves"][0]["association"]["status"])
            self.assertEqual(stored_digest, json.loads(sidecar.read_text(encoding="utf-8"))["save_sha256"])

            difference = call(workspace, "saves", "diff", "first.zip", "second.zip", "--instance", "save-index")
            self.assertEqual([], validate(difference, "factorio_save_diff.v1.schema.json"))
            self.assertIn("sha256", {item["field"] for item in difference["differences"]})
            self.assertEqual("unsupported", difference["deep_factorio_save_metadata"])

    def test_retention_moves_save_and_sidecar_to_owned_reversible_trash(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman save retention ") as value:
            workspace = Path(value)
            instance = setup(workspace)
            old = instance / "saves" / "old.zip"
            new = instance / "saves" / "new.zip"
            write_save(old, b"old save")
            write_save(new, b"new save")
            stamp = int(time.time()) - 10 * 24 * 60 * 60
            os.utime(old, (stamp, stamp))
            call(workspace, "saves", "associate", "old.zip", "--instance", "save-index")
            old_bytes = old.read_bytes()

            planned = call(
                workspace, "saves", "retention", "plan", "--instance", "save-index",
                "--keep-last", "1", "--min-age-days", "1",
            )
            self.assertEqual([], validate(planned, "factorio_save_retention_report.v1.schema.json"))
            actions = {item["filename"]: item["action"] for item in planned["saves"]}
            self.assertEqual("move_to_trash", actions["old.zip"])
            self.assertEqual("keep", actions["new.zip"])
            self.assertFalse(planned["permanent_delete"])
            self.assertTrue(planned["reversible"])

            applied = call(
                workspace, "saves", "retention", "apply", "--instance", "save-index",
                "--keep-last", "1", "--min-age-days", "1",
            )
            self.assertTrue(applied["mutation_executed"])
            trash = Path(applied["trash_path"])
            self.assertFalse(old.exists())
            self.assertTrue(new.exists())
            self.assertEqual(old_bytes, (trash / "old.zip").read_bytes())
            self.assertTrue((trash / "old.zip.save-ref.v1.json").is_file())
            self.assertFalse(applied["save_content_modified"])

    def test_retention_target_substitution_enters_recovery_without_losing_original(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman save substitution ") as value:
            workspace = Path(value)
            instance = setup(workspace)
            old = instance / "saves" / "old.zip"
            new = instance / "saves" / "new.zip"
            write_save(old, b"original save")
            write_save(new, b"new save")
            stamp = int(time.time()) - 10 * 24 * 60 * 60
            os.utime(old, (stamp, stamp))
            original = old.read_bytes()
            environment = dict(os.environ)
            environment["FACMAN_SAVE_RETENTION_FAULT"] = "target_substitution"
            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "saves", "retention", "apply", "--instance", "save-index",
                "--keep-last", "1", "--min-age-days", "1", "--json",
            ], env=environment)
            self.assertNotEqual(0, code, stderr or stdout)
            self.assertEqual("save_transaction_recovery_required", json.loads(stdout)["refusal"]["code"])
            preserved = list((instance / "saves").glob(".facman-retention-preserved-*-old.zip"))
            self.assertEqual(1, len(preserved))
            self.assertEqual(original, preserved[0].read_bytes())


if __name__ == "__main__":
    unittest.main()
