# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import tempfile
import tomllib
import unittest
from pathlib import Path

from native_cli import invoke


class StatusOnboardingExplainTests(unittest.TestCase):
    def invoke_json(self, workspace: Path, args: list[str]) -> dict:
        code, stdout, stderr = invoke(["--workspace", str(workspace), *args, "--json"])
        self.assertEqual(code, 0, stderr or stdout)
        report = json.loads(stdout)
        self.assertEqual(report["schema"], "factorio.guidance_report.v1")
        self.assertFalse(report["mutation_executed"])
        self.assertIsInstance(report["observations"], dict)
        self.assertIsInstance(report["reasons"], list)
        self.assertIsInstance(report["remediation"], list)
        return report

    def test_empty_workspace_status_paths_and_capabilities_are_truthful(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman status Ω ") as temporary:
            workspace = Path(temporary) / "workspace"
            status = self.invoke_json(workspace, ["workspace", "status"])
            self.assertEqual(status["command"], "workspace.status")
            self.assertEqual(status["observations"]["execution_authority"], "blocked_pending_h1_h3")
            self.assertEqual(status["observations"]["install_count"], 0)
            with (Path(__file__).resolve().parents[1] / "release/index/workspace_lock.v1.toml").open("rb") as handle:
                lock = tomllib.load(handle)
            pins = {item["id"]: item["pin"] for item in lock["component"]}
            self.assertEqual(status["observations"]["universal_launcher_revision"], pins["universal_launcher"])
            self.assertEqual(status["observations"]["universal_setup_revision"], pins["universal_setup"])
            self.assertFalse(workspace.exists())

            paths = self.invoke_json(workspace, ["workspace", "paths"])
            self.assertEqual(paths["observations"]["root"], str(workspace))
            self.assertFalse(workspace.exists())

            capabilities = self.invoke_json(workspace, ["capabilities", "inspect"])
            run = next(item for item in capabilities["observations"]["capabilities"] if item["command"] == "run.execute")
            self.assertEqual(run["availability"], "human_gated")
            code, stdout, stderr = invoke(["--workspace", str(workspace), "workspace", "status"])
            self.assertEqual(code, 0, stderr or stdout)
            self.assertIn("workspace.status\nStatus: warning", stdout)
            self.assertIn("[isolation_not_proven]", stdout)
            self.assertIn("No steps were executed", stdout)

    def test_onboarding_and_explanations_are_deterministic_non_mutating_reports(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman onboarding ") as temporary:
            workspace = Path(temporary) / "workspace"
            onboarding = self.invoke_json(workspace, ["onboarding", "plan", "--name", "Orbital Ω"])
            self.assertEqual(onboarding["command"], "onboarding.plan")
            self.assertTrue(all(not step["executed"] for step in onboarding["steps"]))
            self.assertFalse(workspace.exists())

            doctor = self.invoke_json(workspace, ["doctor", "explain"])
            self.assertTrue(any(reason["code"] == "no_install_references" for reason in doctor["reasons"]))
            launch = self.invoke_json(workspace, ["launch", "explain", "missing-instance"])
            self.assertEqual(launch["status"], "blocked")
            modsets = self.invoke_json(workspace, ["modsets", "explain", "missing-instance"])
            self.assertEqual(modsets["status"], "warning")
            self.assertFalse(workspace.exists())


if __name__ == "__main__":
    unittest.main()
