# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from native_cli import facman_executable, invoke


ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "tests/fixtures/fake_factorio_install"
MOD = ROOT / "tests/fixtures/factorio_mods/valid_simple/simple_mod_1.0.0.zip"
SAVE = ROOT / "tests/fixtures/factorio_saves/valid_simple_save/starter.zip"


def tui_executable() -> Path | None:
    configured = os.environ.get("FACMAN_TUI_EXE")
    candidates = [
        Path(configured) if configured else Path("__missing__"),
        ROOT / "build/r37-ux/Release/facman-tui.exe",
        ROOT / "build/native-smoke/Debug/facman-tui.exe",
        ROOT / "build/native-smoke/facman-tui",
        ROOT / "build/macos-native/facman-tui",
    ]
    return next((path for path in candidates if path.is_file()), None)


def fixture_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class R37LifecycleJourneyTests(unittest.TestCase):
    def call(self, workspace: Path, *args: str) -> dict:
        code, stdout, stderr = invoke(["--workspace", str(workspace), *args, "--json"])
        self.assertEqual(0, code, stderr or stdout)
        return json.loads(stdout)

    def rpc(self, workspace: Path, command: str, payload: dict) -> dict:
        request = {
            "schema": "facman.transport_request.v1",
            "protocol_version": 1,
            "request_id": "r37-lifecycle",
            "workspace": str(workspace),
            "command": command,
            "dry_run": True,
            "payload": payload,
        }
        completed = subprocess.run(
            [str(facman_executable()), "rpc", "--stdio"], cwd=ROOT,
            input=json.dumps(request), text=True, encoding="utf-8", check=False,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
        )
        self.assertEqual(0, completed.returncode, completed.stderr or completed.stdout)
        self.assertEqual("", completed.stderr)
        return json.loads(completed.stdout)

    def test_reversible_instance_content_lifecycle_across_live_transports(self) -> None:
        fixture_before = {"mod": fixture_digest(MOD), "save": fixture_digest(SAVE)}
        with tempfile.TemporaryDirectory(prefix="facman-r37-lifecycle-Ω-") as temporary:
            workspace = Path(temporary) / "empty Unicode workspace"
            status = self.call(workspace, "workspace", "status")
            self.assertEqual("workspace.status", status["command"])
            self.assertFalse(workspace.exists())

            self.call(workspace, "installs", "scan", "--path", str(INSTALL))
            self.call(workspace, "installs", "import", str(INSTALL), "--id", "fixture")
            self.call(workspace, "instances", "create", "R3.7 Journey", "--id", "journey", "--install", "fixture")
            self.assertEqual("journey", self.call(workspace, "instances", "inspect", "journey")["instance_id"])
            self.assertIn(self.call(workspace, "instances", "verify", "journey")["status"], {"pass", "warning"})
            self.call(workspace, "instances", "clone", "journey", "journey-copy")

            self.call(workspace, "profiles", "create", "lifecycle", "--audio", "disabled", "--graphics-quality", "low")
            planned_profile = self.call(workspace, "profiles", "plan", "journey", "lifecycle", "--window-mode", "fullscreen")
            self.assertFalse(planned_profile["mutation_executed"])
            self.call(workspace, "profiles", "apply", "journey", "lifecycle", "--window-mode", "fullscreen")

            instance = workspace / "instances" / "journey"
            shutil.copyfile(MOD, instance / "mods" / MOD.name)
            indexed_mods = self.call(workspace, "mods", "index", "--root", str(instance / "mods"))
            self.assertGreaterEqual(indexed_mods["record_count"], 1)
            self.assertIn("simple_mod", {record["name"] for record in indexed_mods["records"]})
            plan = self.call(workspace, "modsets", "plan", "journey", "--enable", "simple_mod")
            self.assertTrue(plan["local_artifacts_only"])
            self.call(workspace, "modsets", "apply", "journey", "--enable", "simple_mod")
            self.assertEqual("ok", self.call(workspace, "modsets", "verify", "journey")["status"])

            shutil.copyfile(SAVE, instance / "saves" / SAVE.name)
            self.assertEqual(1, self.call(workspace, "saves", "index", "--instance", "journey")["save_count"])
            self.call(workspace, "saves", "associate", SAVE.name, "--instance", "journey", "--profile", "lifecycle")
            self.call(workspace, "snapshots", "create", "journey", "baseline", "--save", SAVE.name)
            difference = self.call(workspace, "instances", "diff", "journey", "snapshot:baseline")
            self.assertEqual("snapshot:baseline", difference["right_ref"])

            archived = self.call(workspace, "instances", "archive", "journey")
            restored = self.call(workspace, "instances", "restore", archived["archive_id"], "--new-id", "restored")
            self.assertEqual("restored", restored["instance_id"])
            restored_lock = json.loads(
                (workspace / "instances" / "restored" / "mods" / "modset-lock.v1.json").read_text(encoding="utf-8")
            )
            self.assertEqual("restored", restored_lock["instance_id"])
            self.assertIn(self.call(workspace, "instances", "verify", "restored")["status"], {"pass", "warning"})

            self.call(workspace, "servers", "create", "Lifecycle Server", "--id", "lifecycle", "--instance", "restored")
            server_plan = self.call(workspace, "servers", "plan", "lifecycle", "--save", "starter")
            self.assertFalse(server_plan["effective_launch_plan"]["execution_enabled"])
            bundle = workspace / "exports" / "server-plan.zip"
            exported = self.call(workspace, "servers", "export", "lifecycle", str(bundle), "--save", "starter")
            self.assertTrue(bundle.is_file())
            self.assertFalse(exported["contains_save"])
            self.call(workspace, "snapshots", "retention", "plan", "journey", "--keep-last", "1")
            self.call(workspace, "saves", "retention", "plan", "--instance", "restored", "--keep-last", "1")
            recovery = self.call(workspace, "workspace", "recovery", "inspect")
            self.assertTrue(all(item["state"] == "complete" for item in recovery["transactions"]))

            machine = self.rpc(workspace, "workspace.status", {})
            self.assertEqual("ok", machine["outcome"])
            tui = tui_executable()
            if tui is not None:
                noninteractive = subprocess.run(
                    [str(tui), "--workspace", str(workspace), "--command", "workspace.status", "--json"],
                    cwd=ROOT, text=True, encoding="utf-8", check=False,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
                )
                self.assertEqual(0, noninteractive.returncode, noninteractive.stderr)
                guided = subprocess.run(
                    [str(tui), "--workspace", str(workspace), "--interactive", "--plain"],
                    cwd=ROOT, input="/workspace.status\n1\n\nq\n", text=True, encoding="utf-8", check=False,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
                )
                self.assertEqual(0, guided.returncode, guided.stderr)
                self.assertIn("FacMan guided terminal", guided.stdout)
                process = subprocess.run(
                    [
                        str(tui), "--workspace", str(workspace), "--command", "workspace.status",
                        "--transport", "process", "--cli-path", str(facman_executable()), "--json",
                    ], cwd=ROOT, text=True, encoding="utf-8", check=False,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
                )
                self.assertEqual(0, process.returncode, process.stderr)

            winforms_probe = ROOT / "tests/frontend_harness/bin/Release/FacMan.WinForms.Probe.exe"
            if winforms_probe.is_file():
                winforms = subprocess.run(
                    [str(winforms_probe), str(workspace), str(facman_executable())], cwd=ROOT,
                    text=True, encoding="utf-8", check=False,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60,
                )
                self.assertEqual(0, winforms.returncode, winforms.stderr or winforms.stdout)
                self.assertIn("servers.plan: PASS", winforms.stdout)

        self.assertEqual(fixture_before, {"mod": fixture_digest(MOD), "save": fixture_digest(SAVE)})


if __name__ == "__main__":
    unittest.main()
