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


if __name__ == "__main__":
    unittest.main()
