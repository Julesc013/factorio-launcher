# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from native_cli import invoke
from tools import json_contract


ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"
SCHEMA_ROOT = ROOT / "contracts" / "schema" / "factorio"


def assert_schema(test: unittest.TestCase, document: dict, name: str) -> None:
    schema = json_contract.load_schema(SCHEMA_ROOT / name)
    test.assertEqual([], json_contract.validate(document, schema), name)


def snapshot(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def create_fixture(workspace: Path, instance_id: str = "main") -> Path:
    code, stdout, stderr = invoke([
        "--workspace", str(workspace), "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture", "--json",
    ])
    if code != 0:
        raise AssertionError(stderr or stdout)
    code, stdout, stderr = invoke([
        "--workspace", str(workspace), "instances", "create", instance_id,
        "--id", instance_id, "--install", "fixture", "--json",
    ])
    if code != 0:
        raise AssertionError(stderr or stdout)
    root = workspace / "instances" / instance_id
    (root / "script-output" / "preserved.txt").write_text("preserved\n", encoding="utf-8")
    (root / "logs" / "volatile.log").write_text("volatile\n", encoding="utf-8")
    return root


class InstanceLifecycleTests(unittest.TestCase):
    def test_clone_rename_archive_restore_is_reversible_and_id_immutable(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman lifecycle ") as temporary:
            workspace = Path(temporary)
            source = create_fixture(workspace)
            source_before = snapshot(source)

            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "instances", "inspect", "main", "--json",
            ])
            self.assertEqual(0, code, stderr or stdout)
            inspected = json.loads(stdout)
            assert_schema(self, inspected, "factorio_instance_inspection.v1.schema.json")
            self.assertEqual("main", inspected["instance_id"])
            self.assertEqual("not_granted", inspected["run_authority_state"])
            self.assertFalse(inspected["mutation_executed"])

            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "instances", "clone", "main", "copy",
                "--name", "Copy Display", "--json",
            ])
            self.assertEqual(0, code, stderr or stdout)
            cloned = json.loads(stdout)
            assert_schema(self, cloned, "factorio_instance_lifecycle.v1.schema.json")
            self.assertFalse(cloned["hard_delete_available"])
            copy = workspace / "instances" / "copy"
            self.assertTrue((copy / "script-output" / "preserved.txt").is_file())
            self.assertFalse((copy / "logs" / "volatile.log").exists())
            self.assertEqual(source_before, snapshot(source))

            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "instances", "verify", "copy", "--json",
            ])
            self.assertEqual(0, code, stderr or stdout)
            verified = json.loads(stdout)
            assert_schema(self, verified, "factorio_instance_verification.v1.schema.json")
            self.assertIn(verified["status"], {"pass", "warning"})

            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "instances", "rename", "copy",
                "--name", "Renamed Display", "--json",
            ])
            self.assertEqual(0, code, stderr or stdout)
            manifest = json.loads((copy / "instance.v1.json").read_text(encoding="utf-8"))
            self.assertEqual("copy", manifest["instance_id"])
            self.assertEqual("Renamed Display", manifest["display_name"])
            self.assertTrue(any((workspace / "backups" / "instances").rglob("instance.v1.json")))

            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "instances", "diff", "main", "copy", "--json",
            ])
            self.assertEqual(0, code, stderr or stdout)
            compared = json.loads(stdout)
            assert_schema(self, compared, "factorio_instance_diff.v1.schema.json")
            self.assertTrue(compared["volatile_content_ignored"])

            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "instances", "archive", "copy", "--json",
            ])
            self.assertEqual(0, code, stderr or stdout)
            archived = json.loads(stdout)
            assert_schema(self, archived, "factorio_instance_lifecycle.v1.schema.json")
            archive_id = archived["archive_id"]
            archive_root = workspace / "trash" / "instances" / archive_id
            self.assertFalse(copy.exists())
            self.assertTrue((archive_root / "archive.v1.json").is_file())
            self.assertTrue((archive_root / "script-output" / "preserved.txt").is_file())

            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "instances", "restore", archive_id, "--json",
            ])
            self.assertEqual(0, code, stderr or stdout)
            restored = json.loads(stdout)
            assert_schema(self, restored, "factorio_instance_lifecycle.v1.schema.json")
            self.assertEqual("copy", restored["instance_id"])
            self.assertTrue(copy.is_dir())
            self.assertTrue(archive_root.is_dir(), "restore preserves the owned trash record")
            restored_manifest = json.loads((copy / "instance.v1.json").read_text(encoding="utf-8"))
            self.assertEqual("copy", restored_manifest["instance_id"])
            self.assertEqual("Renamed Display", restored_manifest["display_name"])

            code, stdout, stderr = invoke([
                "--workspace", str(workspace), "instances", "restore", archive_id,
                "--new-id", "restored-alt", "--json",
            ])
            self.assertEqual(0, code, stderr or stdout)
            alternate = json.loads(stdout)
            assert_schema(self, alternate, "factorio_instance_lifecycle.v1.schema.json")
            self.assertEqual("restored-alt", alternate["instance_id"])
            alternate_manifest = json.loads(
                (workspace / "instances" / "restored-alt" / "instance.v1.json").read_text(encoding="utf-8")
            )
            self.assertEqual("restored-alt", alternate_manifest["instance_id"])

    def test_faults_never_clobber_destination_or_hard_delete_source(self) -> None:
        cases = [
            ("clone", "after_validated"),
            ("clone", "during_copy"),
            ("clone", "after_verified"),
            ("archive", "before_commit"),
        ]
        for operation, stage in cases:
            with self.subTest(operation=operation, stage=stage), tempfile.TemporaryDirectory(
                prefix="facman lifecycle fault "
            ) as temporary:
                workspace = Path(temporary)
                source = create_fixture(workspace)
                before = snapshot(source)
                env = os.environ.copy()
                env["FACMAN_INSTANCE_LIFECYCLE_FAULT"] = stage
                args = ["--workspace", str(workspace), "instances", operation, "main"]
                if operation == "clone":
                    args.append("fault-copy")
                args.append("--json")
                code, _, _ = invoke(args, env=env)
                self.assertNotEqual(0, code)
                self.assertTrue(source.is_dir())
                self.assertEqual(before, snapshot(source))
                self.assertFalse((workspace / "instances" / "fault-copy").exists())
                self.assertFalse(any((workspace / "instances").glob("*.staging")))

    def test_archive_refuses_run_lock_without_moving_content(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman lifecycle lock ") as temporary:
            workspace = Path(temporary)
            source = create_fixture(workspace)
            (source / "locks" / "run.lock").write_text("active\n", encoding="utf-8")
            before = snapshot(source)
            code, stdout, _ = invoke([
                "--workspace", str(workspace), "instances", "archive", "main", "--json",
            ])
            self.assertNotEqual(0, code)
            self.assertEqual("run_lock_contended", json.loads(stdout)["refusal"]["code"])
            self.assertEqual(before, snapshot(source))

    def test_archive_fault_matrix_preserves_live_or_owned_trash_content(self) -> None:
        for stage in ("after_validated", "before_commit", "after_commit", "after_metadata"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory(
                prefix="facman archive fault "
            ) as temporary:
                workspace = Path(temporary)
                source = create_fixture(workspace)
                before = snapshot(source)
                env = os.environ.copy()
                env["FACMAN_INSTANCE_LIFECYCLE_FAULT"] = stage
                code, _, _ = invoke([
                    "--workspace", str(workspace), "instances", "archive", "main", "--json",
                ], env=env)
                self.assertNotEqual(0, code)
                archives = list((workspace / "trash" / "instances").glob("*-main"))
                if stage in {"after_validated", "before_commit"}:
                    self.assertTrue(source.is_dir())
                    self.assertEqual(before, snapshot(source))
                    self.assertEqual([], archives)
                else:
                    self.assertFalse(source.exists())
                    self.assertEqual(1, len(archives))
                    moved = snapshot(archives[0])
                    moved.pop("archive.v1.json", None)
                    self.assertEqual(before, moved)

    def test_restore_fault_matrix_preserves_archive_and_bounded_destination_state(self) -> None:
        for stage in ("after_validated", "during_copy", "after_verified", "after_commit"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory(
                prefix="facman restore fault "
            ) as temporary:
                workspace = Path(temporary)
                create_fixture(workspace)
                code, stdout, stderr = invoke([
                    "--workspace", str(workspace), "instances", "archive", "main", "--json",
                ])
                self.assertEqual(0, code, stderr or stdout)
                archive_id = json.loads(stdout)["archive_id"]
                archive_root = workspace / "trash" / "instances" / archive_id
                archive_before = snapshot(archive_root)
                env = os.environ.copy()
                env["FACMAN_INSTANCE_LIFECYCLE_FAULT"] = stage
                code, _, _ = invoke([
                    "--workspace", str(workspace), "instances", "restore", archive_id, "--json",
                ], env=env)
                self.assertNotEqual(0, code)
                self.assertEqual(archive_before, snapshot(archive_root))
                destination = workspace / "instances" / "main"
                if stage == "after_commit":
                    self.assertTrue((destination / "instance.v1.json").is_file())
                    self.assertTrue((destination / ".facman-staging.v1").is_file())
                else:
                    self.assertFalse(destination.exists())

    def test_clone_post_commit_fault_leaves_recognizable_committed_target(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman clone commit fault ") as temporary:
            workspace = Path(temporary)
            source = create_fixture(workspace)
            source_before = snapshot(source)
            env = os.environ.copy()
            env["FACMAN_INSTANCE_LIFECYCLE_FAULT"] = "after_commit"
            code, _, _ = invoke([
                "--workspace", str(workspace), "instances", "clone", "main", "copy", "--json",
            ], env=env)
            self.assertNotEqual(0, code)
            self.assertEqual(source_before, snapshot(source))
            destination = workspace / "instances" / "copy"
            self.assertTrue((destination / "instance.v1.json").is_file())
            self.assertTrue((destination / ".facman-staging.v1").is_file())
            code, stdout, _ = invoke([
                "--workspace", str(workspace), "instances", "verify", "copy", "--json",
            ])
            self.assertNotEqual(0, code)
            self.assertEqual(
                "instance_transaction_recovery_required", json.loads(stdout)["refusal"]["code"]
            )


if __name__ == "__main__":
    unittest.main()
