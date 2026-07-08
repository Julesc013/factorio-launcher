from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from native_cli import facman_executable, invoke

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"


class VerticalSliceTests(unittest.TestCase):
    def test_inspect_import_instance_plan_dry_run_and_gated_execute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"
            install_root = Path(tmp) / "fake_exec_install"
            exe_dir = install_root / "bin" / "x64"
            info_dir = install_root / "data" / "base"
            exe_dir.mkdir(parents=True)
            info_dir.mkdir(parents=True)
            executable = exe_dir / ("factorio.exe" if facman_executable().suffix == ".exe" else "factorio")
            shutil.copy2(facman_executable(), executable)
            info_dir.joinpath("info.json").write_text('{"name":"base","version":"2.0.77"}\n', encoding="utf-8")

            code, stdout, stderr = invoke(["--workspace", str(workspace), "product", "inspect", "--json"])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["product_id"], "factorio")

            code, stdout, stderr = invoke(["--workspace", str(workspace), "doctor", "--json"])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["status"], "warning")

            code, stdout, stderr = invoke(
                ["--workspace", str(workspace), "installs", "scan", "--path", str(FIXTURE_INSTALL), "--json"]
            )
            self.assertEqual(code, 0, stderr)
            scan = json.loads(stdout)
            self.assertEqual(scan["schema"], "factorio.discovery_report.v1")
            self.assertTrue(scan["installs"])
            self.assertEqual(scan["installs"][0]["verification"]["status"], "structural")

            code, stdout, stderr = invoke(
                ["--workspace", str(workspace), "installs", "import", str(install_root), "--id", "exec-fixture", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["install_id"], "exec-fixture")

            code, stdout, stderr = invoke(
                [
                    "--workspace",
                    str(workspace),
                    "instances",
                    "create",
                    "Vertical Slice",
                    "--install",
                    "exec-fixture",
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["instance_id"], "vertical-slice")

            code, stdout, stderr = invoke(["--workspace", str(workspace), "launch", "plan", "vertical-slice", "--json"])
            self.assertEqual(code, 0, stderr)
            plan = json.loads(stdout)
            self.assertTrue(plan["dry_run_default"])
            self.assertIn("--config", plan["args"])
            self.assertIn("--mod-directory", plan["args"])

            code, stdout, stderr = invoke(["--workspace", str(workspace), "run", "vertical-slice", "--json"])
            self.assertEqual(code, 0, stderr)
            self.assertTrue(json.loads(stdout)["dry_run_default"])

            code, stdout, _stderr = invoke(["--workspace", str(workspace), "run", "vertical-slice", "--execute", "--json"])
            execute = json.loads(stdout)
            self.assertEqual(code, 2)
            self.assertTrue(execute["started"])
            self.assertEqual(execute["exit_code"], 2)
            history = workspace / "instances" / "vertical-slice" / "logs" / "launch_history.log"
            self.assertIn("--mod-directory", history.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
