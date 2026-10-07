# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from native_cli import facman_executable, invoke_machine
from test_local_modset_solver import FIXTURE_INSTALL, call, snapshot
import test_portable_modpack_import as pack_oracle
from tools.winforms_build import msbuild_executable


class PresentationPackImportTests(unittest.TestCase):
    def prepare(self, root: Path, settings: bytes | None = None) -> tuple[Path, Path, Path]:
        producer, consumer = root / "producer", root / "consumer"
        oracle = pack_oracle.PortableModpackImportTests()
        _, pack = oracle.make_pack(producer, settings)
        call(consumer, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture")
        return producer, consumer, pack

    def query(self, workspace: Path, scope: str = "content") -> dict:
        code, out, err = invoke_machine([
            "--workspace", str(workspace), "presentation", "query", scope, "--json"])
        self.assertEqual((code, err), (0, ""), out)
        return json.loads(out)["payload"]

    def arguments(self, workspace: Path, pack: Path, revision: str, identity: str = "import") -> list[str]:
        return ["--workspace", str(workspace), "presentation", "action", "modsets.import",
                "--scope", "content", "--expected-revision", revision,
                "--request-id", "request-" + identity, "--idempotency-key", "key-" + identity,
                "--operation-id", "operation-" + identity, "--attempt-id", "attempt-" + identity,
                "--confirmation", "explicit", "--source-path", str(pack),
                "--new-instance", "reconstructed", "--installation", "fixture",
                "--display-name", "Restored pack", "--json"]

    def test_import_is_advertised_without_selected_instance(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pack-ui-") as value:
            _, consumer, _ = self.prepare(Path(value))
            before = snapshot(consumer)
            current = self.query(consumer)
            action = next((item for item in current["available_semantic_actions"] if item["action_id"] == "modsets.import"), None)
            self.assertIsNotNone(action, "Content must expose the existing offline reconstruction owner")
            self.assertEqual("available", action["availability"])
            self.assertEqual("explicit", action["confirmation"])
            fields = {item["field_id"]: item for item in action["input_fields"]}
            self.assertEqual({"source_path", "new_instance_id", "installation_id", "display_name"}, set(fields))
            self.assertTrue(all(fields[key]["required"] for key in ("source_path", "new_instance_id", "installation_id")))
            self.assertNotIn("selected_instance_id", fields)
            self.assertEqual(before, snapshot(consumer))

    def test_exact_offline_reconstruction_and_new_process_replay(self) -> None:
        for settings in (None, b"", b"\x00binary settings\xff"):
            with self.subTest(settings=settings), tempfile.TemporaryDirectory(prefix="pack-ui-") as value:
                producer, consumer, pack = self.prepare(Path(value), settings)
                before = snapshot(producer)
                args = self.arguments(consumer, pack, self.query(consumer)["revision"])
                code, out, err = invoke_machine(args)
                self.assertEqual((code, err), (0, ""), out)
                result = json.loads(out)["payload"]
                self.assertEqual("completed", result["outcome"])
                self.assertEqual("reconstructed", result["replacement_snapshot"]["selected_context"]["instance_id"])
                self.assertEqual("reconstructed", result["action_payload"]["instance_id"])
                pack_oracle.PortableModpackImportTests().assert_reconstruction(consumer, pack)
                self.assertEqual(before, snapshot(producer))
                after = snapshot(consumer)
                self.assertEqual((0, out, ""), invoke_machine(args))
                self.assertEqual(after, snapshot(consumer))
                changed = list(args)
                changed[changed.index("--source-path") + 1] = str(pack.parent / "another.zip")
                code, response, err = invoke_machine(changed)
                self.assertEqual((code, err), (1, ""), response)
                self.assertEqual("idempotency_key_conflict", json.loads(response)["error"]["code"])
                self.assertEqual(after, snapshot(consumer))

    def test_stale_snapshot_and_existing_target_preserve_user_data(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pack-ui-") as value:
            _, consumer, pack = self.prepare(Path(value))
            old = self.query(consumer)
            call(consumer, "profiles", "create", "changed")
            before = snapshot(consumer)
            code, out, err = invoke_machine(self.arguments(consumer, pack, old["revision"]))
            self.assertEqual((code, err), (1, ""), out)
            self.assertEqual("stale_snapshot_revision", json.loads(out)["error"]["code"])
            self.assertEqual(before, snapshot(consumer))
            target = consumer / "instances/reconstructed"
            target.mkdir()
            (target / "user-save.dat").write_bytes(b"existing user data")
            before = snapshot(target)
            code, out, err = invoke_machine(self.arguments(consumer, pack, self.query(consumer)["revision"], "foreign"))
            self.assertEqual((code, err), (1, ""), out)
            self.assertEqual("refused_before_effects", json.loads(out)["payload"]["outcome"])
            self.assertEqual(before, snapshot(target))

    @unittest.skipUnless(os.name == "nt", "not_applicable: WinForms requires Windows")
    def test_compiled_content_entry_preserves_inputs_and_adopts_returned_selection(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pack-ui-") as value:
            root = Path(value)
            producer, consumer, pack = self.prepare(root, b"preserved settings")
            call(consumer, "instances", "create", "Existing", "--id", "existing", "--install", "fixture")
            scopes = ("launch_deck", "instances", "installations", "content", "saves", "activity_recovery", "settings_support")
            fixture = root / "gallery.json"
            fixture.write_text(json.dumps(dict(schema="facman.control_gallery_case.v1", state="blocked",
                variant="ordinary-pack-import", observed_at="2026-10-07T00:00:00Z",
                snapshots={scope: self.query(consumer, scope) for scope in scopes})) + "\n", encoding="utf-8")
            code, out, err = invoke_machine(self.arguments(consumer, pack, self.query(consumer)["revision"]))
            self.assertEqual((code, err), (0, ""), out)
            receipt = root / "receipt.json"
            receipt.write_text(out, encoding="utf-8")
            pack_oracle.PortableModpackImportTests().assert_reconstruction(consumer, pack)
            before = {str(path): snapshot(path) for path in (producer, consumer)}
            repository = Path(__file__).resolve().parents[1]
            project = repository / "tests/winforms_control_gallery/FacMan.PackImport.Harness.csproj"
            output, intermediate = root / "bin", root / "obj"
            build = subprocess.run([msbuild_executable(), str(project), "/m:2", "/nr:false",
                "/p:Configuration=Debug", "/p:Platform=x64", f"/p:OutputPath={output}{os.sep}",
                f"/p:IntermediateOutputPath={intermediate}{os.sep}", f"/p:BaseIntermediateOutputPath={intermediate}{os.sep}"],
                cwd=repository, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
            self.assertEqual(0, build.returncode, build.stdout + build.stderr)
            result = subprocess.run([str(output / "FacMan.PackImport.Harness.exe"), str(fixture), str(receipt), str(pack)],
                cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual(1, result.stdout.count("PASS "))
            self.assertEqual(before, {str(path): snapshot(path) for path in (producer, consumer)})

    def test_retained_partial_extraction_reports_recovery_required(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pack-ui-") as value:
            producer, consumer, pack = self.prepare(Path(value))
            before = snapshot(producer)
            args = self.arguments(consumer, pack, self.query(consumer)["revision"])
            code, out, err = invoke_machine(args, env=dict(os.environ, FACMAN_TEST_MODPACK_IMPORT_EXTRACT_FAULT="after_entry"))
            self.assertEqual((code, err), (3, ""), out)
            self.assertEqual("recovery_required", json.loads(out)["payload"]["outcome"])
            stage = consumer / ".facman-pack-import-reconstructed"
            self.assertTrue(stage.is_dir())
            stage_before = snapshot(stage)
            self.assertFalse((consumer / "instances/reconstructed").exists())
            self.assertEqual((3, out, ""), invoke_machine(args))
            self.assertEqual(stage_before, snapshot(stage))
            self.assertEqual(before, snapshot(producer))

    def test_process_loss_recovers_through_ordinary_recovery_action(self) -> None:
        for point in ("verified", "published", "committed"):
            with self.subTest(point=point), tempfile.TemporaryDirectory(prefix="pack-ui-") as value:
                producer, consumer, pack = self.prepare(Path(value), b"preserved settings")
                before = snapshot(producer)
                args = self.arguments(consumer, pack, self.query(consumer)["revision"])
                child = subprocess.Popen([str(facman_executable()), *args],
                    env=dict(os.environ, FACMAN_TEST_MODPACK_IMPORT_PAUSE=point),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    signal = consumer / f".facman-modpack-import-{point}-paused"
                    deadline = time.monotonic() + 20
                    while not signal.exists() and child.poll() is None and time.monotonic() < deadline:
                        time.sleep(0.05)
                    self.assertTrue(signal.exists(), "Import did not reach the owned process-loss boundary")
                    child.kill()
                    child.communicate(timeout=10)
                finally:
                    if child.poll() is None:
                        child.kill()
                        child.communicate(timeout=10)
                code, out, err = invoke_machine(args)
                self.assertEqual((code, err), (4, ""), out)
                self.assertEqual("outcome_unknown", json.loads(out)["payload"]["outcome"])
                transactions = call(consumer, "workspace", "recovery", "inspect")["transactions"]
                tx = next(item["transaction_id"] for item in transactions if item["command_id"] == "modsets.import")
                recovery = ["--workspace", str(consumer), "presentation", "action", "recovery.apply_supported",
                    "--scope", "activity_recovery", "--expected-revision", self.query(consumer, "activity_recovery")["revision"],
                    "--transaction", tx, "--request-id", "request-recover", "--idempotency-key", "key-recover",
                    "--operation-id", "operation-recover", "--attempt-id", "attempt-recover", "--confirmation", "explicit", "--json"]
                code, out, err = invoke_machine(recovery)
                self.assertEqual((code, err), (0, ""), out)
                self.assertEqual("completed", json.loads(out)["payload"]["outcome"])
                pack_oracle.PortableModpackImportTests().assert_reconstruction(consumer, pack)
                self.assertEqual(before, snapshot(producer))


if __name__ == "__main__":
    unittest.main()
