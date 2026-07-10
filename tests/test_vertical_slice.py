from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from native_cli import invoke

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"


class VerticalSliceTests(unittest.TestCase):
    def test_inspect_import_instance_plan_dry_run_and_gated_execute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp) / "workspace"

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
                ["--workspace", str(workspace), "installs", "import", str(FIXTURE_INSTALL), "--id", "exec-fixture", "--json"]
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
            self.assertEqual(code, 1)
            self.assertEqual(execute["refusal"]["code"], "isolation_not_proven")
            history = workspace / "instances" / "vertical-slice" / "logs" / "launch_history.log"
            self.assertFalse(history.exists())


if __name__ == "__main__":
    unittest.main()
