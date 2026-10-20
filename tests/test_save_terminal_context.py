# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from native_cli import facman_executable, invoke_machine
from test_save_association_context import inventory
from test_save_index_retention import call, setup, write_save


ROOT = Path(__file__).resolve().parents[1]


class SaveTerminalContextTests(unittest.TestCase):
    def test_owner_context_is_readable_without_changing_byte_status_or_workspace(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman save terminal ") as directory:
            workspace = Path(directory)
            instance = setup(workspace)
            code, output, error = invoke_machine(["--workspace", str(workspace), "saves", "index",
                "--instance", "save-index"])
            self.assertEqual((0, ""), (code, error))
            self.assertIn("Saves: 0", output)
            save = instance / "saves/world.zip"
            write_save(save, b"opaque terminal context fixture")
            original_save = save.read_bytes()
            lock = instance / "mods/modset-lock.v1.json"
            original_lock = b'{"mods":[]}\n'
            lock.write_bytes(original_lock)
            code, output, error = invoke_machine(["--workspace", str(workspace), "saves", "associate",
                "world.zip", "--instance", "save-index"])
            self.assertEqual((0, ""), (code, error))
            self.assertIn("Report status: associated", output)
            self.assertIn("Save bytes: current", output)
            self.assertIn("Declared context: match", output)
            sidecar = instance / "metadata/save-refs/world.zip.save-ref.v1.json"
            original_sidecar = sidecar.read_bytes()
            manifest = instance / "instance.v1.json"
            original_manifest = manifest.read_bytes()

            def observe(context: str, version: str, content: str, byte_status: str = "current") -> None:
                before = inventory(workspace)
                owner = call(workspace, "saves", "verify", "world.zip", "--instance", "save-index")
                self.assertEqual("drifted" if byte_status == "drifted" else "pass", owner["status"])
                self.assertEqual(byte_status, owner["saves"][0]["association"]["status"])
                self.assertEqual(context, owner["saves"][0]["association"]["context"]["status"])
                for action in ("index", "inspect", "verify"):
                    args = ["--workspace", str(workspace), "saves", action]
                    if action != "index":
                        args.append("world.zip")
                    args.extend(["--instance", "save-index"])
                    code, output, error = invoke_machine(args)
                    self.assertEqual((0, ""), (code, error), output)
                    for text in ("world.zip", "Save bytes: " + byte_status, "Declared context: " + context,
                            "Version: " + version, "Content: " + content, "Gameplay compatibility: unclaimed",
                            "Deep Factorio save metadata: unsupported"):
                        self.assertIn(text, output)
                    if version == "drifted":
                        self.assertIn("recorded 2.0.77; current 2.0.78", output)
                        self.assertIn("declared_factorio_version_changed", output)
                tui = subprocess.run([str(facman_executable()), "tui", "--workspace", str(workspace),
                    "--ordinary", "--plain"], cwd=ROOT, input="5\nq\n", capture_output=True,
                    text=True, encoding="utf-8", errors="replace", timeout=30)
                self.assertEqual((0, ""), (tui.returncode, tui.stderr), tui.stdout)
                for text in ("world.zip", "Save bytes: " + byte_status, "Declared context: " + context,
                        "Version: " + version, "Content: " + content, "gameplay compatibility is unclaimed"):
                    self.assertIn(text, tui.stdout)
                self.assertNotIn("\x1b[", tui.stdout)
                self.assertEqual(before, inventory(workspace))

            observe("match", "match", "match")
            record = json.loads(original_manifest)
            record["factorio_version"] = "2.0.78"
            manifest.write_text(json.dumps(record) + "\n", encoding="utf-8")
            observe("drifted", "drifted", "match")
            manifest.write_bytes(original_manifest)
            lock.write_bytes(b'{"mods":[],"changed":true}\n')
            observe("drifted", "match", "drifted")
            lock.write_bytes(original_lock)
            record = json.loads(original_sidecar)
            record.pop("factorio_version")
            record["modset_lock_sha256"] = ""
            sidecar.write_text(json.dumps(record) + "\n", encoding="utf-8")
            observe("unknown", "unknown", "unknown")
            sidecar.write_bytes(original_sidecar)
            peer = lock.with_name("lock-peer.json")
            os.link(lock, peer)
            observe("unavailable", "match", "unavailable")
            peer.unlink()
            write_save(save, b"changed opaque terminal context fixture")
            observe("match", "match", "match", "drifted")
            save.write_bytes(original_save)
            self.assertEqual(original_sidecar, sidecar.read_bytes())
            before = inventory(workspace)
            code, output, error = invoke_machine(["--workspace", str(workspace), "saves", "inspect",
                "missing.zip", "--instance", "save-index"])
            self.assertNotEqual(0, code)
            self.assertEqual("", output)
            self.assertTrue(error)
            self.assertEqual(before, inventory(workspace))


if __name__ == "__main__":
    unittest.main()
