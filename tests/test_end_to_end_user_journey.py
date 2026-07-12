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


def tree_digest(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    }


def tui_executable() -> Path | None:
    configured = os.environ.get("FACMAN_TUI_EXE")
    candidates = [
        Path(configured) if configured else Path("__missing__"),
        ROOT / "build/r36-tui/Debug/facman-tui.exe",
        ROOT / "build/native-smoke/Debug/facman-tui.exe",
        ROOT / "build/native-smoke/facman-tui",
        ROOT / "build/macos-native/facman-tui",
    ]
    return next((path for path in candidates if path.is_file()), None)


class EndToEndUserJourneyTests(unittest.TestCase):
    def invoke_json(self, workspace: Path, args: list[str]) -> dict:
        code, stdout, stderr = invoke(["--workspace", str(workspace), *args, "--json"])
        self.assertEqual(code, 0, stderr or stdout)
        return json.loads(stdout)

    def rpc(self, workspace: Path, command: str, payload: dict, *, dry_run: bool = True) -> tuple[int, dict]:
        request = {
            "schema": "facman.transport_request.v1",
            "protocol_version": 1,
            "request_id": "r36-journey",
            "workspace": str(workspace),
            "command": command,
            "dry_run": dry_run,
            "payload": payload,
        }
        completed = subprocess.run(
            [str(facman_executable()), "rpc", "--stdio"],
            cwd=ROOT,
            input=json.dumps(request, ensure_ascii=False),
            check=False,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        self.assertEqual(completed.stderr, "")
        return completed.returncode, json.loads(completed.stdout)

    def test_complete_non_execution_journey_across_live_transports(self) -> None:
        fixture_before = {
            "install": tree_digest(INSTALL),
            "mod": hashlib.sha256(MOD.read_bytes()).hexdigest(),
            "save": hashlib.sha256(SAVE.read_bytes()).hexdigest(),
        }
        with tempfile.TemporaryDirectory(prefix="facman-r36-journey-Ω-") as temporary:
            root = Path(temporary)
            source = root / "source workspace"
            target = root / "restored workspace"

            empty_status = self.invoke_json(source, ["workspace", "status"])
            self.assertEqual(empty_status["command"], "workspace.status")
            self.assertFalse(source.exists())

            scan = self.invoke_json(source, ["installs", "scan", "--path", str(INSTALL)])
            self.assertTrue(scan["installs"])
            self.assertFalse(source.exists())

            imported_install = self.invoke_json(
                source, ["installs", "import", str(INSTALL), "--id", "fixture"]
            )
            self.assertEqual(imported_install["install_id"], "fixture")
            inspected = self.invoke_json(source, ["installs", "inspect", "fixture"])
            self.assertEqual(inspected["install_id"], "fixture")

            instance = self.invoke_json(
                source,
                ["instances", "create", "R3.6 Journey", "--install", "fixture"],
            )
            instance_id = instance["instance_id"]
            self.assertEqual(instance_id, "r3-6-journey")

            imported_mod = self.invoke_json(
                source, ["mods", "import", str(MOD), "--instance", instance_id]
            )
            self.assertEqual(imported_mod["name"], "simple_mod")
            locked = self.invoke_json(source, ["modsets", "lock", instance_id])
            self.assertEqual(locked["instance_id"], instance_id)
            verified = self.invoke_json(source, ["modsets", "verify", instance_id])
            self.assertEqual(verified["status"], "ok")

            save_path = source / "instances" / instance_id / "saves" / SAVE.name
            shutil.copyfile(SAVE, save_path)
            saves = self.invoke_json(source, ["saves", "list", "--instance", instance_id])
            self.assertEqual(saves["saves"][0]["file_name"], SAVE.name)
            backup = root / "outputs" / "starter.backup.zip"
            backup.parent.mkdir()
            backup_result = self.invoke_json(
                source,
                ["saves", "backup", "starter", "--instance", instance_id, "--to", str(backup)],
            )
            self.assertEqual(Path(backup_result["path"]), backup)
            self.assertEqual(backup.read_bytes(), SAVE.read_bytes())

            plan = self.invoke_json(source, ["launch", "plan", instance_id])
            self.assertEqual(plan["execution"], "not_started")
            preflight = self.invoke_json(source, ["launch", "plan", instance_id, "--preflight"])
            self.assertEqual(preflight["status"], "pass")
            self.assertFalse(preflight["started"])

            diagnostic_bundle = root / "outputs" / "diagnostics.zip"
            diagnostics = self.invoke_json(
                source,
                ["diagnostics", "export", "--instance", instance_id, "--out", str(diagnostic_bundle)],
            )
            self.assertEqual(diagnostics["command"], "diagnostics.export")
            self.assertTrue(diagnostic_bundle.is_file())

            instance_pack = root / "outputs" / "instance.zip"
            exported = self.invoke_json(source, ["export", "instance", instance_id, str(instance_pack)])
            self.assertEqual(exported["schema"], "factorio.instance_export.v1")
            self.invoke_json(target, ["installs", "import", str(INSTALL), "--id", "fixture"])
            restored = self.invoke_json(
                target, ["import", "instance", str(instance_pack), "--id", "restored-journey"]
            )
            self.assertEqual(restored["instance_id"], "restored-journey")
            recovery = self.invoke_json(target, ["workspace", "recovery", "inspect"])
            self.assertTrue(recovery["transactions"])
            self.assertTrue(all(item["state"] == "complete" for item in recovery["transactions"]))

            cli_status = self.invoke_json(target, ["workspace", "status"])
            code, machine = self.rpc(target, "workspace.status", {})
            self.assertEqual(code, 0)
            self.assertEqual(machine["outcome"], "ok")
            self.assertEqual(machine["payload"]["command"], cli_status["command"])

            tui = tui_executable()
            if tui is None:
                self.skipTest("functional TUI build is not available")
            completed = subprocess.run(
                [str(tui), "--workspace", str(target), "--command", "workspace.status", "--json"],
                cwd=ROOT,
                check=False,
                text=True,
                encoding="utf-8",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=30,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["command"], cli_status["command"])

            code, unavailable = self.rpc(
                target, "run.execute", {"instance_id": "restored-journey"}, dry_run=False
            )
            self.assertEqual(code, 1)
            self.assertEqual(unavailable["outcome"], "unavailable")
            self.assertEqual(unavailable["error"]["code"], "isolation_not_proven")

        self.assertEqual(tree_digest(INSTALL), fixture_before["install"])
        self.assertEqual(hashlib.sha256(MOD.read_bytes()).hexdigest(), fixture_before["mod"])
        self.assertEqual(hashlib.sha256(SAVE.read_bytes()).hexdigest(), fixture_before["save"])


if __name__ == "__main__":
    unittest.main()
