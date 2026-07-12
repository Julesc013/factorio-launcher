# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def tui_executable() -> Path | None:
    configured = os.environ.get("FACMAN_TUI_EXE")
    candidates = [
        Path(configured) if configured else Path("__missing__"),
        ROOT / "build/r37-ux/Release/facman-tui.exe",
        ROOT / "build/r36-tui/Debug/facman-tui.exe",
        ROOT / "build/native-smoke/Debug/facman-tui.exe",
        ROOT / "build/native-smoke/facman-tui",
        ROOT / "build/macos-native/facman-tui",
    ]
    return next((path for path in candidates if path.is_file()), None)


def cli_executable() -> Path | None:
    candidates = [
        ROOT / "build/r37-ux/Release/facman.exe",
        ROOT / "build/Release/facman.exe",
        ROOT / "build/native-smoke/Debug/facman.exe",
        ROOT / "build/native-smoke/facman",
        ROOT / "build/macos-native/facman",
    ]
    return next((path for path in candidates if path.is_file()), None)


@unittest.skipUnless(tui_executable(), "functional TUI build is not available")
class TuiProductTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.executable = tui_executable()
        assert cls.executable is not None

    def invoke(self, args: list[str], *, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.executable), *args],
            cwd=ROOT,
            input=stdin,
            check=False,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
        )

    def test_catalog_and_empty_unicode_workspace(self) -> None:
        version = self.invoke(["--version"])
        self.assertEqual(version.returncode, 0, version.stderr)
        self.assertIn("FacMan 0.1.0 TUI", version.stdout)
        catalog = self.invoke(["--list", "--json"])
        self.assertEqual(catalog.returncode, 0, catalog.stderr)
        report = json.loads(catalog.stdout)
        self.assertGreaterEqual(len(report["commands"]), 56)
        run = next(item for item in report["commands"] if item["runtime_id"] == "run.execute")
        self.assertEqual(run["availability_reason"], "isolation_not_proven")

        with tempfile.TemporaryDirectory(prefix="facman-tui-Ω-") as temporary:
            workspace = Path(temporary) / "uncreated workspace"
            status = self.invoke(
                ["--workspace", str(workspace), "--command", "workspace.status", "--json"]
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            payload = json.loads(status.stdout)
            self.assertEqual(payload["observations"]["workspace"], str(workspace))
            self.assertFalse(workspace.exists())

            doctor = self.invoke(["--workspace", str(workspace), "--command", "doctor", "--json"])
            self.assertEqual(doctor.returncode, 0, doctor.stderr)
            self.assertEqual(json.loads(doctor.stdout)["schema"], "factorio.diagnostic_report.v1")

    def test_redirected_default_unavailable_and_cancellation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-tui-redirected-") as temporary:
            workspace = Path(temporary) / "workspace"
            redirected = self.invoke(["--workspace", str(workspace), "--json"], stdin="")
            self.assertEqual(redirected.returncode, 0, redirected.stderr)
            self.assertEqual(json.loads(redirected.stdout)["command"], "workspace.status")

            unavailable = self.invoke(
                [
                    "--workspace", str(workspace), "--command", "run.execute",
                    "--payload", '{"instance_id":"space-age-main"}', "--json",
                ]
            )
            self.assertEqual(unavailable.returncode, 1)
            self.assertEqual(json.loads(unavailable.stdout)["refusal"]["code"], "isolation_not_proven")

            cancelled = self.invoke(
                ["--workspace", str(workspace), "--command", "workspace.status", "--cancel", "--json"]
            )
            self.assertEqual(cancelled.returncode, 1)
            self.assertEqual(json.loads(cancelled.stdout)["outcome"], "cancelled")
            self.assertFalse(workspace.exists())

    def test_generated_guided_forms_plain_mode_and_transport_refusal(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-tui-guided-") as temporary:
            workspace = Path(temporary) / "guided workspace"
            guided = self.invoke(
                ["--workspace", str(workspace), "--interactive", "--plain", "--page-size", "5"],
                stdin="/workspace.status\n1\n\nq\n",
            )
            self.assertEqual(guided.returncode, 0, guided.stderr)
            self.assertIn("FacMan guided terminal", guided.stdout)
            self.assertIn("Commands matching search", guided.stdout)
            self.assertIn("Review", guided.stdout)
            self.assertIn("Risk: read_only", guided.stdout)
            self.assertIn("[progress]", guided.stdout)
            self.assertNotIn("JSON payload", guided.stdout)
            self.assertNotIn("\x1b[", guided.stdout)
            self.assertFalse(workspace.exists())

            cancelled_write = self.invoke(
                ["--workspace", str(workspace), "--interactive", "--plain"],
                stdin="/instances.rename\n1\nmain\nRenamed\nno\nq\n",
            )
            self.assertEqual(cancelled_write.returncode, 0, cancelled_write.stderr)
            self.assertIn("Type APPLY to confirm this local write", cancelled_write.stdout)
            self.assertIn("Command cancelled before dispatch", cancelled_write.stdout)
            self.assertFalse(workspace.exists())

            daemon = self.invoke(
                ["--workspace", str(workspace), "--command", "workspace.status", "--transport", "daemon", "--json"]
            )
            self.assertEqual(daemon.returncode, 1)
            refusal = json.loads(daemon.stdout)
            self.assertEqual(refusal["code"], "daemon_transport_unavailable")

            cli = cli_executable()
            if cli is not None:
                process = self.invoke(
                    [
                        "--workspace", str(workspace), "--command", "workspace.status",
                        "--transport", "process", "--cli-path", str(cli), "--json",
                    ]
                )
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertEqual(json.loads(process.stdout)["observations"]["workspace"], str(workspace))

            invalid = self.invoke(["--color", "sometimes", "--command", "workspace.status"])
            self.assertEqual(invalid.returncode, 2)


if __name__ == "__main__":
    unittest.main()
