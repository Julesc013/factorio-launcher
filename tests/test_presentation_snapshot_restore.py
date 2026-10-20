# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
"""Ordinary snapshot reconstruction delegates to the existing typed owner."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from native_cli import invoke_machine
from test_instance_snapshots import FIXTURE_INSTALL, FIXTURE_SAVE, assert_schema, call, fixture
from test_local_modset_solver import snapshot
from test_make_ready_joined import PausedAction, wait_for_owned_marker
from tools.winforms_build import msbuild_executable


def domain_snapshot(workspace: Path) -> dict:
    return {name: data for name, data in snapshot(workspace).items()
            if not name.startswith(".facman/action-receipts-v2/")}


def raw_field(document: str, name: str) -> str:
    source = document.split(json.dumps(name) + ":", 1)[1].lstrip()
    _, end = json.JSONDecoder().raw_decode(source)
    return source[:end]


class PresentationSnapshotRestoreTests(unittest.TestCase):
    def prepare(self, root: Path) -> tuple[Path, Path, Path]:
        source, destination, local = root / "source", root / "destination", root / "local-game"
        instance = fixture(source)
        # Snapshot v1 carries lock references and selected worlds. Opaque mod
        # settings remain source input; offline packs own their reconstruction.
        (instance / "mods/mod-settings.dat").write_bytes(b"\x00source settings\xff")
        call(source, "snapshots", "create", "main", "world", "--save", "starter.zip")
        shutil.copytree(FIXTURE_INSTALL, local)
        call(destination, "installs", "import", str(local), "--id", "local")
        return source / "snapshots/main/world.zip", destination, local

    def query(self, workspace: Path, scope: str = "saves") -> dict:
        code, out, err = invoke_machine(["--workspace", str(workspace), "presentation", "query", scope, "--json"])
        self.assertEqual((0, ""), (code, err), out)
        return json.loads(out)["payload"]

    def arguments(self, workspace: Path, archive: Path, revision: str, identity: str = "restore") -> list[str]:
        return ["--workspace", str(workspace), "presentation", "action", "snapshots.restore",
                "--scope", "saves", "--expected-revision", revision,
                "--request-id", "request-" + identity, "--idempotency-key", "key-" + identity,
                "--operation-id", "operation-" + identity, "--attempt-id", "attempt-" + identity,
                "--confirmation", "explicit", "--source-path", str(archive),
                "--new-instance", "restored", "--installation", "local", "--json"]

    def recovery_arguments(self, workspace: Path, transaction: str, identity: str = "recover") -> list[str]:
        return ["--workspace", str(workspace), "presentation", "action", "recovery.apply_supported",
                "--scope", "activity_recovery", "--expected-revision", self.query(workspace, "activity_recovery")["revision"],
                "--transaction", transaction, "--request-id", "request-" + identity,
                "--idempotency-key", "key-" + identity, "--operation-id", "operation-" + identity,
                "--attempt-id", "attempt-" + identity, "--confirmation", "explicit", "--json"]

    def transaction(self, workspace: Path) -> dict:
        journals = [json.loads(p.read_bytes()) for p in (workspace / "transactions").glob("*.transaction.v1.json")]
        matches = [record for record in journals if record["command_id"] == "snapshots.restore"]
        self.assertEqual(1, len(matches))
        return matches[0]

    def semantic_receipt(self, workspace: Path) -> Path:
        return next(p for p in (workspace / ".facman/action-receipts-v2").glob("*.v2.json")
                    if json.loads(p.read_bytes())["action_id"] == "snapshots.restore")

    def test_saves_advertises_reconstruction_without_an_instance_and_refuses_without_installations(self) -> None:
        with tempfile.TemporaryDirectory(prefix="snapshot-ui-") as value:
            root = Path(value)
            empty = root / "empty"
            absent = self.query(empty)
            blocked = next(a for a in absent["available_semantic_actions"] if a["action_id"] == "snapshots.restore")
            self.assertEqual("no_installations", blocked["refusal"]["code"])
            args = self.arguments(empty, root / "absent.zip", absent["revision"])
            code, out, _ = invoke_machine(args)
            self.assertNotEqual(0, code)
            self.assertEqual("no_installations", json.loads(out)["error"]["code"])
            self.assertFalse(empty.exists())
            _, destination, _ = self.prepare(root)
            before = snapshot(destination)
            current = self.query(destination)
            self.assertIsNone(current["selected_context"]["instance_id"])
            self.assertEqual([], call(destination, "instances", "list")["instances"])
            action = next(a for a in current["available_semantic_actions"] if a["action_id"] == "snapshots.restore")
            self.assertEqual(("available", "explicit", ["workspace_write"]),
                             (action["availability"], action["confirmation"], action["effects"]))
            fields = {f["field_id"]: f for f in action["input_fields"]}
            self.assertEqual({"source_path", "new_instance_id", "installation_id"}, set(fields))
            self.assertTrue(all(f["required"] for f in fields.values()))
            self.assertEqual("path", fields["source_path"]["type"])
            self.assertEqual(["local"], fields["installation_id"]["choices"])
            self.assertEqual(before, snapshot(destination))

    def test_exact_owner_report_local_selection_provenance_and_new_process_replay(self) -> None:
        with tempfile.TemporaryDirectory(prefix="snapshot-ui-") as value:
            root = Path(value)
            archive, destination, local = self.prepare(root)
            inputs = snapshot(archive.parents[2]), snapshot(local)
            args = self.arguments(destination, archive, self.query(destination)["revision"])
            code, out, err = invoke_machine(args)
            self.assertEqual((0, ""), (code, err), out)
            semantic = json.loads(out)["payload"]
            self.assertEqual("completed", semantic["outcome"])
            self.assertEqual("restored", semantic["replacement_snapshot"]["selected_context"]["instance_id"])
            self.assertEqual("local", semantic["replacement_snapshot"]["selected_context"]["installation_id"])
            self.assertFalse(semantic["replacement_snapshot"]["readiness"]["execution_available"])
            report = semantic["action_payload"]
            assert_schema(self, report, "factorio_snapshot_report.v1.schema.json")
            self.assertEqual(("snapshots.restore", "restored", ["starter.zip"]),
                             (report["command"], report["instance_id"], report["selected_saves"]))
            direct = root / "direct"
            call(direct, "installs", "import", str(local), "--id", "local")
            direct_code, direct_out, direct_err = invoke_machine([
                "--workspace", str(direct), "snapshots", "restore", str(archive), "restored", "--install", "local", "--json"])
            self.assertEqual((0, ""), (direct_code, direct_err), direct_out)
            self.assertEqual(raw_field(direct_out, "payload"), raw_field(out, "action_payload"))
            target = destination / "instances/restored"
            manifest = json.loads((target / "instance.v1.json").read_bytes())
            self.assertEqual(("local", "fixture", "world"),
                             (manifest["install_ref"], manifest["restored_from_install_ref"], manifest["restored_from_snapshot"]))
            self.assertIn(str(local).replace("\\", "/"), (target / "config/config.ini").read_text().replace("\\", "/"))
            self.assertEqual(FIXTURE_SAVE.read_bytes(), (target / "saves/starter.zip").read_bytes())
            self.assertFalse((target / "mods/mod-settings.dat").exists())
            self.assertEqual(inputs, (snapshot(archive.parents[2]), snapshot(local)))
            before = snapshot(destination)
            self.assertEqual((0, out, ""), invoke_machine(args))
            self.assertEqual(before, snapshot(destination))
            self.assertEqual("complete", self.transaction(destination)["state"])
            for option, changed in (("--source-path", str(root / "other.zip")), ("--new-instance", "other"), ("--installation", "missing")):
                conflict = list(args); conflict[conflict.index(option) + 1] = changed
                code, response, err = invoke_machine(conflict)
                self.assertEqual((1, ""), (code, err), response)
                self.assertEqual("idempotency_key_conflict", json.loads(response)["error"]["code"])
                self.assertEqual(before, snapshot(destination))

    def test_missing_inputs_confirmation_stale_revision_and_wrong_scope_have_no_effects(self) -> None:
        with tempfile.TemporaryDirectory(prefix="snapshot-ui-gates-") as value:
            archive, destination, _ = self.prepare(Path(value))
            args = self.arguments(destination, archive, self.query(destination)["revision"])
            for option in ("--source-path", "--new-instance", "--installation", "--confirmation"):
                with self.subTest(option=option):
                    missing = list(args); index = missing.index(option); del missing[index:index + 2]
                    before = snapshot(destination)
                    code, out, _ = invoke_machine(missing)
                    self.assertNotEqual(0, code)
                    self.assertEqual("refused_before_effects", json.loads(out)["payload"]["outcome"])
                    self.assertEqual(before, snapshot(destination))
            wrong = list(args); wrong[wrong.index("--scope") + 1] = "content"
            wrong[wrong.index("--expected-revision") + 1] = self.query(destination, "content")["revision"]
            before = snapshot(destination)
            code, out, _ = invoke_machine(wrong)
            self.assertNotEqual(0, code)
            self.assertEqual("semantic_action_unknown", json.loads(out)["error"]["code"])
            self.assertEqual(before, snapshot(destination))
            call(destination, "installs", "import", str(destination.parent / "local-game"), "--id", "changed")
            self.assertNotEqual(args[args.index("--expected-revision") + 1], self.query(destination)["revision"])
            before = snapshot(destination)
            code, out, _ = invoke_machine(args)
            self.assertNotEqual(0, code)
            self.assertEqual("stale_snapshot_revision", json.loads(out)["error"]["code"])
            self.assertEqual(before, snapshot(destination))

    def test_existing_destination_and_non_snapshot_source_preserve_inputs(self) -> None:
        for kind in ("existing", "save-file", "missing", "installation"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix="snapshot-ui-refuse-") as value:
                archive, destination, local = self.prepare(Path(value))
                if kind == "existing":
                    target = destination / "instances/restored"; target.mkdir()
                    (target / "foreign-world.dat").write_bytes(b"existing user world")
                selected = FIXTURE_SAVE if kind == "save-file" else archive.with_name("missing.zip") if kind == "missing" else archive
                args = self.arguments(destination, selected, self.query(destination)["revision"])
                if kind == "installation": args[args.index("--installation") + 1] = "missing"
                before, inputs = domain_snapshot(destination), (snapshot(archive.parents[2]), snapshot(local))
                code, out, _ = invoke_machine(args)
                self.assertNotEqual(0, code)
                self.assertEqual("refused_before_effects", json.loads(out)["payload"]["outcome"])
                if kind == "existing": self.assertEqual("snapshot_restore_target_exists", json.loads(out)["payload"]["problems"][0]["code"])
                self.assertEqual(before, domain_snapshot(destination))
                self.assertEqual(inputs, (snapshot(archive.parents[2]), snapshot(local)))

    def test_before_and_after_publication_death_recover_without_rewriting_unknown_semantic_receipt(self) -> None:
        for point, exit_code, state in (("VERIFIED", 86, "rolled_back"), ("PUBLICATION", 87, "complete")):
            with self.subTest(point=point), tempfile.TemporaryDirectory(prefix="snapshot-ui-death-") as value:
                archive, destination, local = self.prepare(Path(value))
                inputs = archive.read_bytes(), snapshot(local)
                args = self.arguments(destination, archive, self.query(destination)["revision"])
                code, _, _ = invoke_machine(args, env=dict(os.environ, **{"FACMAN_TEST_SNAPSHOT_RESTORE_EXIT_AFTER_" + point: "1"}))
                self.assertEqual(exit_code, code)
                pending = self.semantic_receipt(destination)
                pending_bytes = pending.read_bytes()
                self.assertEqual("accepted_outcome_unknown", json.loads(pending_bytes)["state"])
                journal = self.transaction(destination)
                preserved = snapshot(destination)
                activity = self.query(destination, "activity_recovery")
                if point == "VERIFIED":
                    self.assertTrue(any(p["code"] == "invalid_legacy_identifier" for p in activity["specific_blockers"]), activity)
                    self.assertTrue(any(a["action_id"] == "recovery.apply_supported" for a in activity["available_semantic_actions"]))
                    for scope in ("saves", "instances"):
                        code, unavailable, _ = invoke_machine(["--workspace", str(destination), "presentation", "query", scope, "--json"])
                        self.assertNotEqual(0, code)
                        self.assertEqual("presentation_repository_unavailable", json.loads(unavailable)["error"]["code"])
                self.assertEqual(preserved, snapshot(destination))
                code, out, err = invoke_machine(args)
                self.assertEqual((4, ""), (code, err), out)
                self.assertEqual("outcome_unknown", json.loads(out)["payload"]["outcome"])
                self.assertEqual(preserved, snapshot(destination))
                code, recovery, err = invoke_machine(self.recovery_arguments(destination, journal["transaction_id"]))
                self.assertEqual((0, ""), (code, err), recovery)
                self.assertEqual(state, json.loads(recovery)["payload"]["action_payload"]["transactions"][0]["state"])
                self.assertEqual(pending_bytes, pending.read_bytes())
                recovered = snapshot(destination)
                self.assertEqual((4, out, ""), invoke_machine(args))
                self.assertEqual(recovered, snapshot(destination))
                target = destination / "instances/restored"
                self.assertEqual(state == "complete", target.is_dir())
                if target.is_dir():
                    self.assertEqual("local", json.loads((target / "instance.v1.json").read_bytes())["install_ref"])
                    self.assertEqual(FIXTURE_SAVE.read_bytes(), (target / "saves/starter.zip").read_bytes())
                self.assertEqual(inputs, (archive.read_bytes(), snapshot(local)))

    def test_recovery_refuses_changed_archive_target_registration_and_orphan_lock(self) -> None:
        for kind in ("archive", "target", "registration", "lock"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix="snapshot-ui-binding-") as value:
                archive, destination, _ = self.prepare(Path(value))
                args = self.arguments(destination, archive, self.query(destination)["revision"])
                self.assertEqual(87, invoke_machine(args, env=dict(os.environ, FACMAN_TEST_SNAPSHOT_RESTORE_EXIT_AFTER_PUBLICATION="1"))[0])
                journal = self.transaction(destination)
                target = destination / "instances/restored"
                changed = (archive if kind == "archive" else target / "saves/starter.zip" if kind == "target"
                           else destination / "installs/refs/local.json" if kind == "registration"
                           else Path(str(destination / "transactions" / (journal["transaction_id"] + ".transaction.v1.json")) + ".recovery.lock"))
                changed.write_bytes(b'{"schema":"foreign","owner":"preserved"}' if kind == "lock" else changed.read_bytes() + b" ")
                before, receipt = domain_snapshot(destination), self.semantic_receipt(destination).read_bytes()
                code, out, _ = invoke_machine(self.recovery_arguments(destination, journal["transaction_id"]))
                self.assertNotEqual(0, code)
                refusal = json.loads(out)["payload"]
                self.assertEqual("recovery_required", refusal["outcome"])
                self.assertIsInstance(refusal["action_payload"], dict)
                self.assertEqual("workspace.recovery.apply", refusal["action_payload"]["command"])
                self.assertEqual(before, domain_snapshot(destination))
                self.assertEqual(receipt, self.semantic_receipt(destination).read_bytes())

    def test_live_installation_drift_is_recovery_required_and_replays_without_redispatch(self) -> None:
        with tempfile.TemporaryDirectory(prefix="snapshot-ui-live-") as value:
            archive, destination, _ = self.prepare(Path(value))
            record = destination / "installs/refs/local.json"
            original, archive_bytes = record.read_bytes(), archive.read_bytes()
            args = self.arguments(destination, archive, self.query(destination)["revision"])
            marker = destination / ".facman-test-snapshot-restore-before-publication"
            release = destination / ".facman-test-snapshot-restore-publication-release"
            worker = PausedAction(args, dict(os.environ,
                FACMAN_TEST_SNAPSHOT_RESTORE_BEFORE_PUBLICATION_PAUSE="1"))
            try:
                wait_for_owned_marker(worker, marker, release)
                record.write_bytes(original + b" ")
            finally:
                release.write_text("go")
                worker.finish()
            self.assertIsNotNone(worker.response)
            code, out, err = worker.response
            self.assertEqual((3, ""), (code, err), out)
            self.assertEqual("recovery_required", json.loads(out)["payload"]["outcome"])
            self.assertFalse((destination / "instances/restored").exists())
            journal = self.transaction(destination)
            self.assertTrue(any(Path(p).is_dir() for p in journal["owned_staging_roots"]))
            before = snapshot(destination)
            self.assertEqual((3, out, ""), invoke_machine(args))
            self.assertEqual(before, snapshot(destination))
            record.write_bytes(original)
            code, recovered, err = invoke_machine(self.recovery_arguments(destination, journal["transaction_id"]))
            self.assertEqual((0, ""), (code, err), recovered)
            self.assertEqual("rolled_back", json.loads(recovered)["payload"]["action_payload"]["transactions"][0]["state"])
            self.assertEqual((3, out, ""), invoke_machine(args))
            self.assertEqual(archive_bytes, archive.read_bytes())

    @unittest.skipUnless(os.name == "nt", "unsupported: compiled WinForms entry requires Windows")
    def test_compiled_scoped_button_fields_returned_selection_and_uncertain_input(self) -> None:
        with tempfile.TemporaryDirectory(prefix="snapshot-ui-form-") as value:
            root = Path(value)
            archive, destination, _ = self.prepare(root)
            scopes = ("launch_deck", "instances", "installations", "content", "saves", "activity_recovery", "settings_support")
            gallery = root / "gallery.json"
            gallery.write_text(json.dumps(dict(schema="facman.control_gallery_case.v1", state="blocked",
                variant="ordinary-snapshot-restore", observed_at="2026-10-15T00:00:00Z",
                snapshots={scope: self.query(destination, scope) for scope in scopes})), encoding="utf-8")
            code, out, err = invoke_machine(self.arguments(destination, archive, self.query(destination)["revision"]))
            self.assertEqual((0, ""), (code, err), out)
            receipt = root / "receipt.json"; receipt.write_text(out, encoding="utf-8")
            repository = Path(__file__).resolve().parents[1]
            project = repository / "tests/winforms_control_gallery/FacMan.PackImport.Harness.csproj"
            output, intermediate = root / "bin", root / "obj"
            build = subprocess.run([msbuild_executable(), str(project), "/m:2", "/nr:false",
                "/p:Configuration=Debug", "/p:Platform=x64", f"/p:OutputPath={output}{os.sep}",
                f"/p:IntermediateOutputPath={intermediate}{os.sep}", f"/p:BaseIntermediateOutputPath={intermediate}{os.sep}"],
                cwd=repository, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
            self.assertEqual(0, build.returncode, build.stdout + build.stderr)
            before = domain_snapshot(destination), snapshot(archive.parents[2])
            result = subprocess.run([str(output / "FacMan.PackImport.Harness.exe"), str(gallery), str(receipt), str(archive), "snapshot"],
                cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(1, result.stdout.count("PASS "))
            self.assertEqual(before, (domain_snapshot(destination), snapshot(archive.parents[2])))


if __name__ == "__main__":
    unittest.main()
