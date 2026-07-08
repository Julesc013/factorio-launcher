from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from native_cli import facman_executable, invoke

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"


class CliTests(unittest.TestCase):
    def test_version(self) -> None:
        code, stdout, stderr = invoke(["--version"])
        self.assertEqual(code, 0, stderr)
        self.assertIn("FacMan 0.1.0", stdout)

    def test_product_inspect_json(self) -> None:
        code, stdout, stderr = invoke(["product", "inspect", "--json"])
        self.assertEqual(code, 0, stderr)
        data = json.loads(stdout)
        self.assertEqual(data["product_id"], "factorio")
        self.assertFalse(data["boundaries"]["bundles_factorio_binaries"])

    def test_doctor_warns_without_installs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, stderr = invoke(["--workspace", tmp, "doctor"])
        self.assertEqual(code, 0, stderr)
        self.assertIn("Status: warning", stdout)
        self.assertIn("no install references registered yet", stdout)

    def test_import_instance_and_launch_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            code, stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture"]
            )
            self.assertEqual(code, 0, stderr)
            self.assertIn("Registered fixture", stdout)

            code, stdout, stderr = invoke(
                [
                    "--workspace",
                    tmp,
                    "instances",
                    "create",
                    "Space Age Main",
                    "--install",
                    "fixture",
                    "--template",
                    "modded",
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            instance = json.loads(stdout)
            self.assertEqual(instance["instance_id"], "space-age-main")
            self.assertTrue((Path(tmp) / "instances" / "space-age-main" / "instance.v1.json").is_file())

            code, stdout, stderr = invoke(["--workspace", tmp, "launch-plan", "space-age-main", "--json"])
            self.assertEqual(code, 0, stderr)
            plan = json.loads(stdout)
            self.assertEqual(plan["instance_id"], "space-age-main")
            self.assertIn("--config", plan["args"])
            self.assertIn("--mod-directory", plan["args"])
            self.assertTrue(plan["dry_run_default"])

            code, stdout, stderr = invoke(["--workspace", tmp, "launch", "plan", "space-age-main", "--json"])
            self.assertEqual(code, 0, stderr)
            alias_plan = json.loads(stdout)
            self.assertEqual(alias_plan["instance_id"], "space-age-main")

            code, stdout, stderr = invoke(["--workspace", tmp, "run", "space-age-main"])
            self.assertEqual(code, 0, stderr)
            self.assertIn("Dry-run only", stdout)

    def test_run_execute_invokes_isolated_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            install_root = Path(tmp) / "fake_exec_install"
            exe_dir = install_root / "bin" / "x64"
            info_dir = install_root / "data" / "base"
            exe_dir.mkdir(parents=True)
            info_dir.mkdir(parents=True)
            executable = exe_dir / ("factorio.exe" if facman_executable().suffix == ".exe" else "factorio")
            shutil.copy2(facman_executable(), executable)
            info_dir.joinpath("info.json").write_text('{"name":"base","version":"2.0.77"}\n', encoding="utf-8")

            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(install_root), "--id", "exec-fixture"]
            )
            self.assertEqual(code, 0, stderr)
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "instances", "create", "Exec Fixture", "--install", "exec-fixture"]
            )
            self.assertEqual(code, 0, stderr)

            code, stdout, _stderr = invoke(["--workspace", tmp, "run", "exec-fixture", "--execute", "--json"])
            result = json.loads(stdout)

            self.assertEqual(code, 2)
            self.assertTrue(result["started"])
            self.assertEqual(result["exit_code"], 2)
            history = Path(tmp) / "instances" / "exec-fixture" / "logs" / "launch_history.log"
            self.assertIn("--mod-directory", history.read_text(encoding="utf-8"))

    def test_local_mod_import_lock_verify_and_export(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mod_zip = Path(tmp) / "example_1.2.3.zip"
            mod_zip.write_bytes(b"fake local mod zip")

            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture"]
            )
            self.assertEqual(code, 0, stderr)
            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "instances", "create", "Modded", "--install", "fixture"]
            )
            self.assertEqual(code, 0, stderr)

            code, stdout, stderr = invoke(
                ["--workspace", tmp, "mods", "import", str(mod_zip), "--instance", "modded", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            imported = json.loads(stdout)
            self.assertEqual(imported["name"], "example")
            self.assertEqual(imported["version"], "1.2.3")
            self.assertEqual(len(imported["sha1"]), 40)

            code, stdout, stderr = invoke(["--workspace", tmp, "modsets", "lock", "modded", "--json"])
            self.assertEqual(code, 0, stderr)
            lock = json.loads(stdout)
            self.assertEqual(lock["factorio_version"], "2.0.77")
            self.assertEqual(lock["mods"][0]["file_name"], "example_1.2.3.zip")
            self.assertTrue((Path(tmp) / "modsets" / "modded.modset-lock.v1.json").is_file())

            code, stdout, stderr = invoke(["--workspace", tmp, "modsets", "verify", "modded", "--json"])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["status"], "ok")

            copied_mod = Path(tmp) / "instances" / "modded" / "mods" / "example_1.2.3.zip"
            copied_mod.write_bytes(b"tampered")
            code, stdout, _stderr = invoke(["--workspace", tmp, "modsets", "verify", "modded", "--json"])
            self.assertEqual(code, 1)
            self.assertEqual(json.loads(stdout)["status"], "error")

            code, _stdout, stderr = invoke(["--workspace", tmp, "modsets", "lock", "modded"])
            self.assertEqual(code, 0, stderr)
            pack = Path(tmp) / "pack.zip"
            code, stdout, stderr = invoke(["--workspace", tmp, "modsets", "export", "modded", str(pack), "--json"])
            self.assertEqual(code, 0, stderr)
            exported = json.loads(stdout)
            self.assertEqual(exported["files"], 2)
            self.assertTrue(pack.read_bytes().startswith(b"PK\x03\x04"))

    def test_managed_install_operations_are_setup_gated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "factorio-2.0.77.zip"
            archive.write_bytes(b"fake local archive")

            code, stdout, stderr = invoke(
                [
                    "--workspace",
                    tmp,
                    "installs",
                    "install-version",
                    "2.0.77",
                    "--archive",
                    str(archive),
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            install_plan = json.loads(stdout)
            self.assertEqual(install_plan["setup_authority"], "universal-setup")
            self.assertEqual(install_plan["setup_command"], "install_local.plan")
            self.assertFalse(install_plan["mutates_install"])
            self.assertEqual(install_plan["setup_response"]["payload"]["schema"], "usk.install_plan.v1")

            code, _stdout, stderr = invoke(
                ["--workspace", tmp, "installs", "import", str(FIXTURE_INSTALL), "--id", "fixture"]
            )
            self.assertEqual(code, 0, stderr)

            code, stdout, stderr = invoke(["--workspace", tmp, "installs", "verify", "fixture", "--json"])
            self.assertEqual(code, 0, stderr)
            verify = json.loads(stdout)
            self.assertEqual(verify["setup_command"], "verify.report")
            self.assertEqual(verify["setup_response"]["payload"]["schema"], "usk.verify_report.v1")

            code, stdout, _stderr = invoke(["--workspace", tmp, "installs", "repair", "fixture", "--json"])
            self.assertEqual(code, 1)
            repair = json.loads(stdout)
            self.assertEqual(repair["status"], "refused")
            self.assertEqual(repair["refusal"]["code"], "ownership_denied")
            self.assertFalse(repair["mutates_install"])

            code, stdout, _stderr = invoke(["--workspace", tmp, "installs", "uninstall", "fixture", "--json"])
            self.assertEqual(code, 1)
            uninstall = json.loads(stdout)
            self.assertEqual(uninstall["status"], "refused")
            self.assertEqual(uninstall["refusal"]["code"], "ownership_denied")
            self.assertFalse(uninstall["mutates_install"])


if __name__ == "__main__":
    unittest.main()
