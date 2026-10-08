# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path

from native_cli import facman_executable, invoke_machine
from test_local_modset_solver import FIXTURE_INSTALL, call, setup, snapshot, write_mod
import test_portable_modpack_export as pack_export_oracle
import test_portable_modpack_import as pack_import_oracle
from tools.winforms_build import msbuild_executable


class PresentationPackExportTests(unittest.TestCase):
    def prepare(self, workspace: Path, settings: bytes | None = None) -> Path:
        source = setup(workspace)
        write_mod(source / "mods/simple_1.0.0.zip", "simple", "1.0.0")
        write_mod(source / "mods/unselected_1.0.0.zip", "unselected", "1.0.0")
        call(workspace, "modsets", "apply", "solver", "--enable", "simple")
        if settings is not None:
            (source / "mods/mod-settings.dat").write_bytes(settings)
        return source

    def query(self, workspace: Path, scope: str = "content", selected: bool = True) -> dict:
        args = ["--workspace", str(workspace), "presentation", "query", scope, "--json"]
        if selected:
            args += ["--instance", "solver"]
        code, out, err = invoke_machine(args)
        self.assertEqual((code, err), (0, ""), out)
        return json.loads(out)["payload"]

    def arguments(self, workspace: Path, output: Path, revision: str, identity: str = "export") -> list[str]:
        return ["--workspace", str(workspace), "presentation", "action", "modsets.export",
                "--scope", "content", "--instance", "solver", "--output", str(output),
                "--expected-revision", revision, "--request-id", "request-" + identity,
                "--idempotency-key", "key-" + identity, "--operation-id", "operation-" + identity,
                "--attempt-id", "attempt-" + identity, "--confirmation", "explicit", "--json"]

    def test_projection_requires_selected_locked_instance_and_explicit_destination(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pack-export-ui-") as value:
            workspace = Path(value)
            source = setup(workspace)
            before = snapshot(workspace)
            for selected, refusal in ((False, "no_instance_selected"), (True, "no_modset_lock")):
                action = next(item for item in self.query(workspace, selected=selected)["available_semantic_actions"]
                              if item["action_id"] == "modsets.export")
                self.assertNotEqual("available", action["availability"])
                self.assertEqual(refusal, action["refusal"]["code"])
            self.assertEqual(before, snapshot(workspace))
            call(workspace, "modsets", "apply", "solver", "--enable", "base")
            action = next(item for item in self.query(workspace)["available_semantic_actions"]
                          if item["action_id"] == "modsets.export")
            self.assertEqual(("available", "explicit"), (action["availability"], action["confirmation"]))
            fields = {item["field_id"]: item for item in action["input_fields"]}
            self.assertEqual({"selected_instance_id", "output_path"}, set(fields))
            self.assertTrue(all(item["required"] for item in fields.values()))
            self.assertEqual("path", fields["output_path"]["type"])
            self.assertTrue((source / "mods/modset-lock.v1.json").is_file())

    def test_exact_selected_pack_reconstructs_offline_and_replays_without_rewriting(self) -> None:
        for settings in (None, b"", b"\x00startup settings\xff"):
            with self.subTest(settings=settings), tempfile.TemporaryDirectory(prefix="pack-export-ui-") as value:
                root = Path(value)
                workspace, consumer = root / "producer", root / "consumer"
                source = self.prepare(workspace, settings)
                before = snapshot(source), snapshot(workspace / "modsets")
                output = root / "selected.zip"
                args = self.arguments(workspace, output, self.query(workspace)["revision"])
                code, out, err = invoke_machine(args)
                self.assertEqual((code, err), (0, ""), out)
                result = json.loads(out)["payload"]
                self.assertEqual("completed", result["outcome"])
                self.assertEqual("solver", result["replacement_snapshot"]["selected_context"]["instance_id"])
                with zipfile.ZipFile(output) as archive:
                    expected = {"modpack-manifest.v1.json", "modset-lock.v1.json",
                                "mods/simple_1.0.0.zip", "mods/mod-list.json"}
                    if settings is not None:
                        expected.add("mods/mod-settings.dat")
                        self.assertEqual(settings, archive.read("mods/mod-settings.dat"))
                    self.assertEqual(expected, set(archive.namelist()))
                    raw_lock = (source / "mods/modset-lock.v1.json").read_bytes()
                    self.assertEqual(raw_lock, archive.read("modset-lock.v1.json"))
                    manifest = json.loads(archive.read("modpack-manifest.v1.json"))
                    self.assertEqual(hashlib.sha256(raw_lock).hexdigest(), manifest["source_lock"]["blob"]["sha256"])
                after = snapshot(workspace), output.read_bytes(), output.stat().st_mtime_ns
                self.assertEqual((0, out, ""), invoke_machine(args))
                self.assertEqual(after, (snapshot(workspace), output.read_bytes(), output.stat().st_mtime_ns))
                changed = list(args)
                changed[changed.index("--output") + 1] = str(root / "another.zip")
                code, response, err = invoke_machine(changed)
                self.assertEqual((code, err), (1, ""), response)
                self.assertEqual("idempotency_key_conflict", json.loads(response)["error"]["code"])
                self.assertFalse((root / "another.zip").exists())
                self.assertEqual(after, (snapshot(workspace), output.read_bytes(), output.stat().st_mtime_ns))
                call(consumer, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture")
                oracle = pack_import_oracle.PortableModpackImportTests()
                oracle.import_pack(consumer, output)
                oracle.assert_reconstruction(consumer, output)
                self.assertEqual(before, (snapshot(source), snapshot(workspace / "modsets")))

    def test_stale_confirmation_missing_input_and_existing_target_preserve_data(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pack-export-ui-") as value:
            workspace = Path(value)
            source = self.prepare(workspace)
            output = workspace / "user-data.zip"
            output.write_bytes(b"existing user bytes")
            old = self.query(workspace)["revision"]
            call(workspace, "profiles", "create", "changed")
            before = snapshot(workspace)
            code, out, err = invoke_machine(self.arguments(workspace, output, old))
            self.assertEqual((code, err), (1, ""), out)
            self.assertEqual("stale_snapshot_revision", json.loads(out)["error"]["code"])
            self.assertEqual(before, snapshot(workspace))
            args = self.arguments(workspace, output, self.query(workspace)["revision"], "foreign")
            code, out, err = invoke_machine(args)
            self.assertEqual((code, err), (1, ""), out)
            self.assertEqual("refused_before_effects", json.loads(out)["payload"]["outcome"])
            self.assertEqual(b"existing user bytes", output.read_bytes())
            self.assertEqual(before["instances/solver/mods/modset-lock.v1.json"],
                             (source / "mods/modset-lock.v1.json").read_bytes())
            for flag in ("--output", "--confirmation"):
                current = self.arguments(workspace, workspace / "new.zip", self.query(workspace)["revision"], flag)
                index = current.index(flag)
                del current[index:index + 2]
                before = snapshot(workspace)
                code, out, err = invoke_machine(current)
                self.assertEqual((code, err), (2 if flag == "--output" else 1, ""), out)
                self.assertEqual("semantic_action_input_required" if flag == "--output" else "semantic_action_effect_confirmation_required",
                                 json.loads(out)["error"]["code"])
                self.assertEqual(before, snapshot(workspace))
                self.assertFalse((workspace / "new.zip").exists())

    def test_retained_archive_after_journal_failure_is_recovery_required_and_replayable(self) -> None:
        for point in ("staged", "verified", "committing"):
            with self.subTest(point=point), tempfile.TemporaryDirectory(prefix="pack-export-ui-") as value:
                workspace = Path(value)
                source = self.prepare(workspace)
                before = snapshot(source)
                output = workspace / "selected.zip"
                args = self.arguments(workspace, output, self.query(workspace)["revision"])
                code, out, err = invoke_machine(args, env=dict(os.environ, FACMAN_TEST_TRANSACTION_FAIL_STATE=point))
                self.assertEqual((code, err), (3, ""), out)
                self.assertEqual("recovery_required", json.loads(out)["payload"]["outcome"])
                self.assertFalse(output.exists())
                stages = list(workspace.glob(".facman-modset-export-*"))
                self.assertEqual(1, len(stages))
                self.assertTrue((stages[0] / "archive/selected.zip").is_file())
                retained = snapshot(workspace)
                self.assertEqual((3, out, ""), invoke_machine(args))
                self.assertEqual(retained, snapshot(workspace))
                pending = call(workspace, "workspace", "recovery", "inspect")["transactions"]
                self.assertTrue(any(item["command_id"] == "modsets.export" for item in pending))
                self.assertEqual(before, snapshot(source))

    def test_interrupted_export_and_foreign_staging_survive_ordinary_recovery(self) -> None:
        for interrupted in (True, False):
            with self.subTest(interrupted=interrupted), tempfile.TemporaryDirectory(prefix="pack-export-ui-") as value:
                workspace = Path(value)
                source = self.prepare(workspace)
                output = workspace / "selected.zip"
                args = self.arguments(workspace, output, self.query(workspace)["revision"])
                child = subprocess.Popen([str(facman_executable()), *args],
                    env=dict(os.environ, FACMAN_TEST_MODSET_EXPORT_PAUSE_AFTER_STAGE="1"),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    stage = pack_export_oracle.PortableModpackExportTests().wait_for_stage(workspace, child)
                    foreign = stage / "foreign-user-data.txt"
                    foreign.write_bytes(b"preserve this user data")
                    if interrupted:
                        child.kill()
                        child.communicate(timeout=10)
                        code, out, err = invoke_machine(args)
                        self.assertEqual((code, err), (4, ""), out)
                        self.assertEqual("outcome_unknown", json.loads(out)["payload"]["outcome"])
                    else:
                        (source / "mods/mod-settings.dat").write_bytes(b"changed source settings")
                        (stage / ".facman-modset-export-release").touch()
                        out, err = child.communicate(timeout=20)
                        self.assertEqual((child.returncode, err), (3, ""), out)
                        self.assertEqual("recovery_required", json.loads(out)["payload"]["outcome"])
                    self.assertFalse(output.exists())
                    pending = call(workspace, "workspace", "recovery", "inspect")["transactions"]
                    tx = next(item["transaction_id"] for item in pending if item["command_id"] == "modsets.export")
                    retained = snapshot(stage), snapshot(source)
                    recovery = ["--workspace", str(workspace), "presentation", "action", "recovery.apply_supported",
                        "--scope", "activity_recovery", "--expected-revision", self.query(workspace, "activity_recovery", selected=False)["revision"],
                        "--transaction", tx, "--request-id", "request-recover", "--idempotency-key", "key-recover",
                        "--operation-id", "operation-recover", "--attempt-id", "attempt-recover", "--confirmation", "explicit", "--json"]
                    code, out, err = invoke_machine(recovery)
                    self.assertEqual((code, err), (3, ""), out)
                    self.assertEqual("recovery_staging_unrecognized", json.loads(out)["payload"]["problems"][0]["code"])
                    self.assertEqual(retained, (snapshot(stage), snapshot(source)))
                    self.assertEqual(b"preserve this user data", foreign.read_bytes())
                    # A distinct explicitly requested destination still uses no-replace publication.
                    if not interrupted:
                        again = workspace / "another.zip"
                        fresh = self.arguments(workspace, again, self.query(workspace)["revision"], "fresh")
                        code, out, err = invoke_machine(fresh)
                        self.assertEqual((code, err), (0, ""), out)
                        self.assertTrue(again.is_file())
                        self.assertEqual(retained, (snapshot(stage), snapshot(source)))
                finally:
                    if child.poll() is None:
                        child.kill()
                        child.communicate(timeout=10)

    @unittest.skipUnless(os.name == "nt", "not_applicable: WinForms requires Windows")
    def test_compiled_content_entry_preserves_destination_and_selection(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pack-export-ui-") as value:
            root = Path(value)
            workspace = root / "producer"
            self.prepare(workspace, b"preserved settings")
            scopes = ("launch_deck", "instances", "installations", "content", "saves", "activity_recovery", "settings_support")
            fixture = root / "gallery.json"
            fixture.write_text(json.dumps(dict(schema="facman.control_gallery_case.v1", state="blocked",
                variant="ordinary-pack-export", observed_at="2026-10-08T00:00:00Z",
                snapshots={scope: self.query(workspace, scope) for scope in scopes})) + "\n", encoding="utf-8")
            output = root / "selected.zip"
            code, out, err = invoke_machine(self.arguments(workspace, output, self.query(workspace)["revision"]))
            self.assertEqual((code, err), (0, ""), out)
            receipt = root / "receipt.json"
            receipt.write_text(out, encoding="utf-8")
            before = snapshot(workspace), output.read_bytes()
            repository = Path(__file__).resolve().parents[1]
            project = repository / "tests/winforms_control_gallery/FacMan.PackExport.Harness.csproj"
            build = subprocess.run([msbuild_executable(), str(project), "/m:2", "/nr:false",
                "/p:Configuration=Debug", "/p:Platform=x64", f"/p:OutputPath={root / 'bin'}{os.sep}",
                f"/p:IntermediateOutputPath={root / 'obj'}{os.sep}", f"/p:BaseIntermediateOutputPath={root / 'obj'}{os.sep}"],
                cwd=repository, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
            self.assertEqual(0, build.returncode, build.stdout + build.stderr)
            result = subprocess.run([str(root / "bin/FacMan.PackExport.Harness.exe"), str(fixture), str(receipt), str(output)],
                cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(1, result.stdout.count("PASS "))
            self.assertEqual(before, (snapshot(workspace), output.read_bytes()))


if __name__ == "__main__":
    unittest.main()
