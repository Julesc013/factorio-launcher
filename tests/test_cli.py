from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from factorio_launcher.ui.cli.cli import main

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_INSTALL = ROOT / "tests" / "fixtures" / "fake_factorio_install"


def invoke(args: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = main(args)
    return code, stdout.getvalue(), stderr.getvalue()


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

            code, stdout, stderr = invoke(["--workspace", tmp, "launch-plan", "space-age-main", "--json"])
            self.assertEqual(code, 0, stderr)
            plan = json.loads(stdout)
            self.assertEqual(plan["instance_id"], "space-age-main")
            self.assertIn("--config", plan["args"])
            self.assertIn("--mod-directory", plan["args"])
            self.assertTrue(plan["dry_run_default"])

            code, stdout, stderr = invoke(["--workspace", tmp, "run", "space-age-main"])
            self.assertEqual(code, 0, stderr)
            self.assertIn("Dry-run only", stdout)


if __name__ == "__main__":
    unittest.main()
