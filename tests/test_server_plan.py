# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import tempfile
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


def setup(workspace: Path) -> tuple[Path, Path]:
    call(workspace, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture")
    call(workspace, "instances", "create", "Server Base", "--id", "server-base", "--install", "fixture")
    instance = workspace / "instances" / "server-base"
    save = instance / "saves" / "world.zip"
    with zipfile.ZipFile(save, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("world/level-init.dat", b"opaque server fixture")
    call(workspace, "modsets", "lock", "server-base")
    call(workspace, "servers", "create", "Main Server", "--id", "main", "--instance", "server-base")
    call(workspace, "servers", "create", "Other Server", "--id", "other", "--instance", "server-base")
    return instance, save


def validate(value: dict, schema: str) -> list[str]:
    return json_contract.validate(value, json_contract.load_schema(SCHEMAS / schema))


class ServerPlanTests(unittest.TestCase):
    def test_profile_plan_diff_and_execution_boundaries(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman server plan ") as value:
            workspace = Path(value)
            setup(workspace)
            inspected = call(workspace, "servers", "inspect", "main")
            self.assertEqual("factorio.server_profile.v2", inspected["profile"]["schema"])
            self.assertFalse(inspected["process_started"])
            profile_path = workspace / "servers" / "main.server.v1.json"
            self.assertEqual([], validate(json.loads(profile_path.read_text(encoding="utf-8")), "factorio_server_profile.v2.schema.json"))

            planned = call(workspace, "servers", "plan", "main", "--save", "world")
            self.assertEqual([], validate(planned, "factorio_server_plan.v1.schema.json"))
            self.assertTrue(all(planned["preflight"].values()) if "global_factorio_roots" not in planned["preflight"] else
                all(value for key, value in planned["preflight"].items() if key != "global_factorio_roots"))
            self.assertFalse(planned["preflight"]["global_factorio_roots"])
            self.assertFalse(planned["effective_launch_plan"]["execution_enabled"])
            self.assertFalse(planned["network_socket_opened"])
            self.assertFalse(planned["firewall_changed"])
            self.assertEqual(34197, planned["port"])

            difference = call(workspace, "servers", "diff", "main", "other")
            self.assertEqual([], validate(difference, "factorio_server_plan.v1.schema.json"))
            for action in ("start", "stop", "rcon"):
                refused = call(workspace, "servers", action, "main", success=False)
                self.assertEqual("execution_not_enabled", refused["refusal"]["code"])

    def test_portable_export_excludes_save_and_execution_assets_by_default(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman server export ") as value:
            workspace = Path(value)
            _instance, save = setup(workspace)
            bundle = workspace / "server-plan.zip"
            exported = call(workspace, "servers", "export", "main", str(bundle), "--save", "world")
            self.assertEqual([], validate(exported, "factorio_server_export.v1.schema.json"))
            self.assertFalse(exported["contains_save"])
            self.assertFalse(exported["contains_secrets"])
            self.assertFalse(exported["contains_factorio_binary"])
            self.assertFalse(exported["contains_execution_scripts"])
            with zipfile.ZipFile(bundle) as archive:
                names = sorted(archive.namelist())
                self.assertEqual(
                    ["manifest.json", "map-gen-settings.json", "map-settings.json", "server-plan.json", "server-profile.v2.json", "server-settings.json"],
                    names,
                )
                payload = b"\n".join(archive.read(name) for name in names).lower()
                self.assertNotIn(b"password", payload)
                self.assertNotIn(b"token", payload)
                self.assertNotIn(b".exe", payload)
                self.assertNotIn(b".sh", payload)
                self.assertNotIn(str(workspace).encode().lower(), payload)

            included = workspace / "server-plan-with-save.zip"
            result = call(
                workspace, "servers", "export", "main", str(included), "--save", "world", "--include-save"
            )
            self.assertTrue(result["contains_save"])
            with zipfile.ZipFile(included) as archive:
                self.assertEqual(save.read_bytes(), archive.read("save/world.zip"))

    def test_plaintext_sensitive_profile_fields_are_refused(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman server secret ") as value:
            workspace = Path(value)
            setup(workspace)
            profile = workspace / "servers" / "main.server.v1.json"
            document = json.loads(profile.read_text(encoding="utf-8"))
            document["server_settings"]["password"] = "plaintext-not-allowed"
            profile.write_text(json.dumps(document, separators=(",", ":")) + "\n", encoding="utf-8")
            refused = call(workspace, "servers", "plan", "main", "--save", "world", success=False)
            self.assertEqual("server_profile_secret_refused", refused["refusal"]["code"])


if __name__ == "__main__":
    unittest.main()
