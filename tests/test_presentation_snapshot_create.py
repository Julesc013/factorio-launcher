# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Ordinary snapshot production uses the existing archive and recovery owners."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

from native_cli import ROOT, facman_executable, invoke_machine
from test_instance_snapshots import FIXTURE_INSTALL, FIXTURE_SAVE, assert_schema, call, fixture
from test_local_modset_solver import snapshot
from test_make_ready_joined import PausedAction, wait_for_owned_marker
import test_presentation_snapshot_restore as restore_owner
from test_presentation_snapshot_restore import raw_field
from tools.winforms_build import msbuild_executable


class PresentationSnapshotCreateTests(unittest.TestCase):
    def prepare(self, root: Path) -> tuple[Path, Path]:
        workspace = root / "source"
        instance = fixture(workspace)
        (instance / "mods/mod-settings.dat").write_bytes(b"\x00opaque settings\xff")
        return workspace, instance

    def query(self, workspace: Path, scope: str = "saves", instance: str = "main") -> dict:
        args = ["--workspace", str(workspace), "presentation", "query", scope, "--json"]
        if instance:
            args += ["--instance", instance]
        code, out, err = invoke_machine(args)
        self.assertEqual((0, ""), (code, err), out)
        return json.loads(out)["payload"]

    def arguments(self, workspace: Path, identity: str = "create", save: str = "starter.zip") -> list[str]:
        args = ["--workspace", str(workspace), "presentation", "action", "snapshots.create",
                "--scope", "saves", "--instance", "main", "--snapshot-id", "world",
                "--expected-revision", self.query(workspace)["revision"],
                "--request-id", "request-" + identity, "--idempotency-key", "key-" + identity,
                "--operation-id", "operation-" + identity, "--attempt-id", "attempt-" + identity,
                "--confirmation", "explicit", "--json"]
        if save:
            args += ["--save", save]
        return args

    def receipt(self, workspace: Path) -> Path:
        return next(p for p in (workspace / ".facman/action-receipts-v2").glob("*.v2.json")
                    if json.loads(p.read_bytes())["action_id"] == "snapshots.create")

    def owner_transaction(self, workspace: Path) -> dict:
        matches = [json.loads(p.read_bytes()) for p in (workspace / "transactions").glob("*.transaction.v1.json")
                   if json.loads(p.read_bytes())["command_id"] == "snapshots.create"]
        self.assertEqual(1, len(matches))
        return matches[0]

    def result(self, args: list[str], expected: int = 0) -> tuple[dict, str]:
        code, out, err = invoke_machine(args)
        self.assertEqual((expected, ""), (code, err), out)
        return json.loads(out)["payload"], out

    def test_descriptor_requires_instance_but_save_is_optional_even_without_saves(self) -> None:
        with tempfile.TemporaryDirectory(prefix="snapshot-producer-") as value:
            root = Path(value)
            empty = self.query(root / "empty", instance="")
            blocked = next(a for a in empty["available_semantic_actions"] if a["action_id"] == "snapshots.create")
            self.assertEqual("no_instance_selected", blocked["refusal"]["code"])
            self.assertFalse((root / "empty").exists())
            workspace, instance = self.prepare(root)
            (instance / "saves/starter.zip").unlink()
            before = snapshot(workspace)
            descriptor = next(a for a in self.query(workspace)["available_semantic_actions"] if a["action_id"] == "snapshots.create")
            self.assertEqual(("available", "explicit", ["workspace_write"]),
                             (descriptor["availability"], descriptor["confirmation"], descriptor["effects"]))
            fields = {f["field_id"]: f for f in descriptor["input_fields"]}
            self.assertEqual({"selected_instance_id", "snapshot_id", "save"}, set(fields))
            self.assertTrue(fields["snapshot_id"]["required"])
            self.assertEqual("identifier", fields["snapshot_id"]["type"])
            self.assertIsNone(fields["snapshot_id"]["default"])
            self.assertFalse(fields["save"]["required"])
            self.assertIsNone(fields["save"]["default"])
            self.assertIn("blank includes no saves", fields["save"]["label"])
            self.assertEqual(before, snapshot(workspace))

    def test_exact_owner_archive_world_bundle_roundtrip_and_replay(self) -> None:
        with tempfile.TemporaryDirectory(prefix="snapshot-producer-") as value:
            root = Path(value)
            workspace, instance = self.prepare(root)
            inputs = snapshot(instance), snapshot(workspace / "installs")
            direct_args = ["--workspace", str(workspace), "snapshots", "create", "main", "world", "--save", "starter.zip", "--json"]
            code, direct, err = invoke_machine(direct_args)
            self.assertEqual((0, ""), (code, err), direct)
            archive = workspace / "snapshots/main/world.zip"
            archive_bytes = archive.read_bytes()
            # Remove only this test's exact direct-owner outputs, permitting an
            # independent semantic dispatch to the identical final pathname.
            archive.unlink()
            archive.with_suffix(".record.json").unlink()
            args = self.arguments(workspace)
            semantic, out = self.result(args)
            self.assertEqual("completed", semantic["outcome"])
            self.assertEqual("main", semantic["replacement_snapshot"]["selected_context"]["instance_id"])
            self.assertEqual(raw_field(direct, "payload"), raw_field(out, "action_payload"))
            self.assertEqual(archive_bytes, archive.read_bytes())
            assert_schema(self, semantic["action_payload"], "factorio_snapshot_report.v1.schema.json")
            with zipfile.ZipFile(archive) as zipped:
                manifest = json.loads(zipped.read("manifest/snapshot.v1.json"))
                self.assertEqual(["starter.zip"], manifest["selected_saves"])
                self.assertEqual(FIXTURE_SAVE.read_bytes(), zipped.read("saves/starter.zip"))
                self.assertNotIn("mods/mod-settings.dat", zipped.namelist())
                self.assertNotIn("logs/excluded.log", zipped.namelist())
                self.assertEqual(set(zipped.namelist()) - {"manifest/snapshot.v1.json"},
                                 {entry["path"] for entry in manifest["file_hashes"]})
            self.assertEqual("available", call(workspace, "snapshots", "inspect", "main", "world")["world_bundle_state"])
            before = snapshot(workspace)
            self.assertEqual((0, out, ""), invoke_machine(args))
            self.assertEqual(before, snapshot(workspace))
            for option, change in (("--snapshot-id", "different"), ("--save", "other.zip"), ("--instance", "other")):
                altered = list(args); altered[altered.index(option) + 1] = change
                code, conflict, _ = invoke_machine(altered)
                self.assertEqual(1, code, conflict)
                self.assertEqual("idempotency_key_conflict", json.loads(conflict)["error"]["code"])
                self.assertEqual(before, snapshot(workspace))
            self.assertEqual(inputs, (snapshot(instance), snapshot(workspace / "installs")))
            local, destination = root / "local-game", root / "destination"
            shutil.copytree(FIXTURE_INSTALL, local)
            call(destination, "installs", "import", str(local), "--id", "local")
            restore = restore_owner.PresentationSnapshotRestoreTests()
            mapped, _ = self.result(restore.arguments(destination, archive, restore.query(destination)["revision"]))
            self.assertEqual("restored", mapped["replacement_snapshot"]["selected_context"]["instance_id"])
            target = destination / "instances/restored"
            record = json.loads((target / "instance.v1.json").read_bytes())
            self.assertEqual(("local", "fixture", "world"),
                             (record["install_ref"], record["restored_from_install_ref"], record["restored_from_snapshot"]))
            self.assertIn(str(local).replace("\\", "/"), (target / "config/config.ini").read_text().replace("\\", "/"))
            self.assertEqual(FIXTURE_SAVE.read_bytes(), (target / "saves/starter.zip").read_bytes())
            self.assertEqual(archive_bytes, archive.read_bytes())

    def test_blank_save_matches_existing_owner_and_excludes_all_worlds(self) -> None:
        with tempfile.TemporaryDirectory(prefix="snapshot-producer-empty-") as value:
            workspace, instance = self.prepare(Path(value))
            inputs = snapshot(instance)
            semantic, _ = self.result(self.arguments(workspace, save=""))
            self.assertEqual([], semantic["action_payload"]["selected_saves"])
            with zipfile.ZipFile(workspace / "snapshots/main/world.zip") as zipped:
                self.assertFalse(any(p.startswith("saves/") for p in zipped.namelist()))
                self.assertEqual([], json.loads(zipped.read("manifest/snapshot.v1.json"))["selected_saves"])
            self.assertEqual(inputs, snapshot(instance))

    def test_legacy_twenty_field_backup_request_bytes_and_replay_stay_exact(self) -> None:
        with tempfile.TemporaryDirectory(prefix="snapshot-producer-legacy-") as value:
            workspace, _ = self.prepare(Path(value))
            args = self.arguments(workspace, identity="backup")
            args[args.index("snapshots.create")] = "saves.backup"
            index = args.index("--snapshot-id"); del args[index:index+2]
            revision = args[args.index("--expected-revision")+1]
            semantic, out = self.result(args)
            path = next(p for p in (workspace/".facman/action-receipts-v2").glob("*.v2.json")
                        if json.loads(p.read_bytes())["action_id"] == "saves.backup")
            recorded = json.loads(path.read_bytes())
            # Independent frozen vocabulary/order, not the production encoder.
            expected = dict(action_id="saves.backup",scope="saves",expected_snapshot_revision=revision,
                request_id="request-backup",selected_instance_id="main",durable_operation_id="operation-backup",
                attempt_id="attempt-backup",confirmation="explicit",installation_id="",installation_path="",
                new_instance_id="",display_name="",template_id="vanilla",profile_id="",mod_identity="",
                save="starter.zip",output_path="",source_data_root="",transaction_id="",roots=[])
            canonical = json.dumps(expected,separators=(",", ":"))
            self.assertEqual(canonical, recorded["request_json"])
            self.assertEqual(hashlib.sha256(canonical.encode()).hexdigest(), recorded["request_fingerprint"])
            self.assertEqual("completed", semantic["outcome"])
            self.assertEqual("main", semantic["replacement_snapshot"]["selected_context"]["instance_id"])
            self.assertEqual(["workspace_write"], semantic["effects"])
            before = snapshot(workspace)
            self.assertEqual((0, out, ""), invoke_machine(args))
            self.assertEqual(before, snapshot(workspace))

    def test_input_identity_confirmation_scope_stale_and_target_gates(self) -> None:
        with tempfile.TemporaryDirectory(prefix="snapshot-producer-gates-") as value:
            workspace, _ = self.prepare(Path(value))
            args = self.arguments(workspace)
            for option in ("--snapshot-id", "--instance", "--confirmation", "--operation-id"):
                with self.subTest(option=option):
                    missing = list(args); index = missing.index(option); del missing[index:index + 2]
                    before = snapshot(workspace)
                    code, out, _ = invoke_machine(missing)
                    self.assertNotEqual(0, code, out)
                    self.assertEqual("refused_before_effects", json.loads(out)["payload"]["outcome"])
                    self.assertEqual(before, snapshot(workspace))
            for bad in ("../escape", "x" * 129, "CON", "x" * 65):
                invalid = list(args); invalid[invalid.index("--snapshot-id") + 1] = bad
                before = snapshot(workspace)
                self.assertNotEqual(0, invoke_machine(invalid)[0])
                self.assertEqual(before, snapshot(workspace))
            missing_value = list(args); missing_value.remove("world")
            before = snapshot(workspace)
            self.assertNotEqual(0, invoke_machine(missing_value)[0])
            self.assertEqual(before, snapshot(workspace))
            wrong = list(args); wrong[wrong.index("--scope") + 1] = "content"
            wrong[wrong.index("--expected-revision") + 1] = self.query(workspace, "content")["revision"]
            self.assertEqual("semantic_action_unknown", json.loads(invoke_machine(wrong)[1])["error"]["code"])
            call(workspace, "installs", "import", str(FIXTURE_INSTALL), "--id", "changed")
            self.assertNotEqual(args[args.index("--expected-revision") + 1], self.query(workspace)["revision"])
            before = snapshot(workspace)
            self.assertEqual("stale_snapshot_revision", json.loads(invoke_machine(args)[1])["error"]["code"])
            self.assertEqual(before, snapshot(workspace))
            self.result(self.arguments(workspace))
            before = snapshot(workspace)
            semantic, _ = self.result(self.arguments(workspace, identity="collision"), expected=1)
            self.assertEqual("refused_before_effects", semantic["outcome"])
            self.assertEqual("snapshot_target_exists", semantic["action_payload"]["refusal"]["code"])
            # A new durable refusal receipt is allowed; all domain files remain.
            self.assertEqual({k:v for k,v in before.items() if not k.startswith(".facman/action-receipts-v2/")},
                             {k:v for k,v in snapshot(workspace).items() if not k.startswith(".facman/action-receipts-v2/")})

    def test_publication_death_uses_existing_rollback_and_preserves_unknown_receipt(self) -> None:
        with tempfile.TemporaryDirectory(prefix="snapshot-producer-death-") as value:
            workspace, instance = self.prepare(Path(value))
            inputs = snapshot(instance)
            args = self.arguments(workspace)
            marker = workspace / ".facman-test-snapshot-before-publication"
            release = workspace / ".facman-test-snapshot-publication-release"
            worker = PausedAction(args, dict(os.environ, FACMAN_TEST_SNAPSHOT_BEFORE_PUBLICATION_PAUSE="1"))
            try:
                wait_for_owned_marker(worker, marker, release)
                self.assertIsNotNone(worker.process)
                worker.process.kill()
            finally:
                release.write_text("release\n")
                worker.finish()
            self.assertNotEqual(0, worker.response[0], worker.summary())
            receipt = self.receipt(workspace); original = receipt.read_bytes()
            self.assertEqual("accepted_outcome_unknown", json.loads(original)["state"])
            before = snapshot(workspace)
            unknown, out = self.result(args, expected=4)
            self.assertEqual("outcome_unknown", unknown["outcome"])
            self.assertEqual(before, snapshot(workspace))
            transaction = self.owner_transaction(workspace)
            restore = restore_owner.PresentationSnapshotRestoreTests()
            recovered, _ = self.result(restore.recovery_arguments(workspace, transaction["transaction_id"]))
            self.assertEqual("rolled_back", recovered["action_payload"]["transactions"][0]["state"])
            self.assertFalse((workspace / "snapshots/main/world.zip").exists())
            self.assertEqual(original, receipt.read_bytes())
            before = snapshot(workspace)
            self.assertEqual((4, out, ""), invoke_machine(args))
            self.assertEqual(before, snapshot(workspace))
            self.assertEqual(inputs, snapshot(instance))

    def test_retained_owner_failure_is_recovery_required_and_never_redispatched(self) -> None:
        with tempfile.TemporaryDirectory(prefix="snapshot-producer-refusal-") as value:
            workspace, instance = self.prepare(Path(value))
            args = self.arguments(workspace)
            marker = workspace / ".facman-test-snapshot-before-publication"
            release = workspace / ".facman-test-snapshot-publication-release"
            lock = instance / "locks/run.lock"
            worker = PausedAction(args, dict(os.environ, FACMAN_TEST_SNAPSHOT_BEFORE_PUBLICATION_PAUSE="1"))
            try:
                wait_for_owned_marker(worker, marker, release)
                lock.write_text("foreign running owner; preserve\n")
            finally:
                release.write_text("release\n")
                worker.finish()
            self.assertEqual(3, worker.response[0], worker.summary())
            semantic = json.loads(worker.response[1])["payload"]
            self.assertEqual("recovery_required", semantic["outcome"])
            self.assertTrue(lock.is_file())
            self.assertTrue(any(Path(p).is_dir() for p in self.owner_transaction(workspace)["owned_staging_roots"]))
            before = snapshot(workspace)
            self.assertEqual(tuple(worker.response), invoke_machine(args))
            self.assertEqual(before, snapshot(workspace))
        # Existing create can return a plain owner refusal after creating its
        # transaction/stage. The presentation must retain that recovery evidence.
        with tempfile.TemporaryDirectory(prefix="snapshot-producer-missing-save-") as value:
            workspace, instance = self.prepare(Path(value))
            inputs = snapshot(instance)
            unrelated = workspace / "user-notes.txt"
            unrelated.write_bytes(b"unrelated user data; preserve\n")
            self.assertFalse(any(json.loads(p.read_bytes())["command_id"] == "snapshots.create"
                                 for p in (workspace / "transactions").glob("*.transaction.v1.json")))
            args = self.arguments(workspace, save="missing.zip")
            semantic, out = self.result(args, expected=3)
            self.assertEqual("recovery_required", semantic["outcome"])
            self.assertEqual("facman.safety_refusal.v1", semantic["action_payload"]["schema"])
            self.assertEqual("common.refusal.v1", semantic["action_payload"]["refusal"]["schema"])
            transaction = self.owner_transaction(workspace)
            self.assertEqual(workspace / "snapshots/main/world.zip", Path(transaction["target"]))
            self.assertEqual([instance], [Path(p) for p in transaction["source_identities"]])
            self.assertTrue(any(Path(p).is_dir() for p in transaction["owned_staging_roots"]))
            self.assertFalse((workspace / "snapshots/main/world.zip").exists())
            before = snapshot(workspace)
            self.assertEqual((3, out, ""), invoke_machine(args))
            self.assertEqual(before, snapshot(workspace))
            self.assertEqual(inputs, snapshot(instance))
            self.assertEqual(b"unrelated user data; preserve\n", unrelated.read_bytes())

    def test_malformed_recorded_optional_identifier_refuses_without_rewriting_receipt(self) -> None:
        with tempfile.TemporaryDirectory(prefix="snapshot-producer-codec-") as value:
            workspace, _ = self.prepare(Path(value))
            args = self.arguments(workspace); self.result(args)
            path = self.receipt(workspace); original = path.read_bytes()
            for bad in ("", True, "../bad", "x" * 129):
                record = json.loads(original); request = json.loads(record["request_json"])
                request["snapshot_id"] = bad
                record["request_json"] = json.dumps(request, separators=(",", ":"))
                record["request_fingerprint"] = hashlib.sha256(record["request_json"].encode()).hexdigest()
                path.write_text(json.dumps(record), encoding="utf-8")
                before = snapshot(workspace)
                code, out, _ = invoke_machine(args)
                self.assertEqual(3, code, out)
                self.assertEqual("idempotency_receipt_invalid", json.loads(out)["error"]["code"])
                self.assertEqual(before, snapshot(workspace))
            path.write_bytes(original)

    def test_rpc_optional_identifier_replays_cli_bytes_and_invalid_fields_have_no_effects(self) -> None:
        with tempfile.TemporaryDirectory(prefix="snapshot-producer-rpc-") as value:
            workspace, _ = self.prepare(Path(value))
            args = self.arguments(workspace)
            semantic, out = self.result(args)
            recorded = json.loads(self.receipt(workspace).read_bytes())
            # Canonical receipts retain empty defaults; public identifier fields
            # are omitted when absent, exactly as in the ordinary CLI transport.
            payload = {key:value for key,value in json.loads(recorded["request_json"]).items() if value != ""}
            payload["idempotency_key"] = "key-create"
            request = dict(schema="facman.transport_request.v2",protocol_version=2,
                           request_id="request-create",operation_id="operation-create",
                           attempt_id="attempt-create",workspace=str(workspace),command="presentation.action",
                           dry_run=False,payload=payload)
            def rpc() -> subprocess.CompletedProcess:
                return subprocess.run([str(facman_executable()), "rpc", "--stdio"], cwd=ROOT,
                    input=json.dumps(request), text=True, encoding="utf-8", capture_output=True, timeout=30)
            before = snapshot(workspace)
            replay = rpc()
            self.assertEqual((0, ""), (replay.returncode, replay.stderr), replay.stdout)
            self.assertEqual(semantic, json.loads(replay.stdout)["payload"])
            self.assertEqual(raw_field(out, "action_payload"), raw_field(replay.stdout, "action_payload"))
            self.assertEqual(before, snapshot(workspace))
            for bad in ("", True, "../bad", "x" * 129):
                payload["snapshot_id"] = bad
                invalid = rpc()
                self.assertIsNotNone(json.loads(invalid.stdout)["error"], invalid.stdout)
                self.assertEqual(before, snapshot(workspace))

    @unittest.skipUnless(os.name == "nt", "unsupported: compiled WinForms requires Windows")
    def test_compiled_ordinary_entry_optional_save_and_immutable_pending_fields(self) -> None:
        with tempfile.TemporaryDirectory(prefix="snapshot-producer-form-") as value:
            root = Path(value); workspace, _ = self.prepare(root)
            scopes = ("launch_deck", "instances", "installations", "content", "saves", "activity_recovery", "settings_support")
            gallery = root / "gallery.json"
            gallery.write_text(json.dumps(dict(schema="facman.control_gallery_case.v1", state="blocked",
                variant="ordinary-snapshot-create", observed_at="2026-10-15T00:00:00Z",
                snapshots={scope:self.query(workspace, scope) for scope in scopes})), encoding="utf-8")
            _, out = self.result(self.arguments(workspace))
            receipt = root / "receipt.json"; receipt.write_text(out, encoding="utf-8")
            repository = Path(__file__).resolve().parents[1]
            project = repository / "tests/winforms_control_gallery/FacMan.PackImport.Harness.csproj"
            output, intermediate = root / "bin", root / "obj"
            build = subprocess.run([msbuild_executable(), str(project), "/m:2", "/nr:false",
                "/p:Configuration=Debug", "/p:Platform=x64", f"/p:OutputPath={output}{os.sep}",
                f"/p:IntermediateOutputPath={intermediate}{os.sep}", f"/p:BaseIntermediateOutputPath={intermediate}{os.sep}"],
                cwd=repository, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
            self.assertEqual(0, build.returncode, build.stdout+build.stderr)
            before = snapshot(workspace)
            result = subprocess.run([str(output/"FacMan.PackImport.Harness.exe"), str(gallery), str(receipt), "world", "producer"],
                cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
            self.assertEqual(0, result.returncode, result.stdout+result.stderr)
            self.assertEqual(1, result.stdout.count("PASS "))
            self.assertEqual(before, snapshot(workspace))


if __name__ == "__main__":
    unittest.main()
