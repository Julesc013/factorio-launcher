# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def tui_executable() -> Path | None:
    configured = os.environ.get("FACMAN_TUI_EXE") or os.environ.get("FACMAN_CLI_EXE")
    candidates = [
        Path(configured) if configured else Path("__missing__"),
        ROOT / "build/r37-ux/Release/facman.exe",
        ROOT / "build/r36-tui/Debug/facman.exe",
        ROOT / "build/native-smoke/Debug/facman.exe",
        ROOT / "build/native-smoke/facman",
        ROOT / "build/macos-native/facman",
    ]
    return next((path for path in candidates if path.is_file()), None)


def cli_executable() -> Path | None:
    configured = os.environ.get("FACMAN_CLI_EXE")
    candidates = [
        Path(configured) if configured else Path("__missing__"),
        ROOT / "build/r37-ux/Release/facman.exe",
        ROOT / "build/Release/facman.exe",
        ROOT / "build/native-smoke/Debug/facman.exe",
        ROOT / "build/native-smoke/facman",
        ROOT / "build/macos-native/facman",
    ]
    return next((path for path in candidates if path.is_file()), None)


@unittest.skipUnless(tui_executable(), "optional: functional TUI build is not available")
class TuiProductTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.executable = tui_executable()
        assert cls.executable is not None

    def invoke(
        self,
        args: list[str],
        *,
        stdin: str | None = None,
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        process_environment = os.environ.copy()
        if environment:
            process_environment.update(environment)
        return subprocess.run(
            [str(self.executable), "tui", *args],
            cwd=ROOT,
            input=stdin,
            check=False,
            text=True,
            encoding="utf-8",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=15,
            env=process_environment,
        )

    def test_ordinary_shell_pages_launch_deck_and_advanced_handoff(self) -> None:
        with tempfile.TemporaryDirectory(prefix="facman-tui-ordinary-") as temporary:
            workspace = Path(temporary) / "ordinary workspace"
            ordinary = self.invoke(
                ["--workspace", str(workspace), "--ordinary", "--plain"],
                stdin="2\n7\n8\nenter\nq\n",
            )
            self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
            self.assertIn("FacMan - Factorio Manager", ordinary.stdout)
            self.assertIn("Launch Deck", ordinary.stdout)
            self.assertIn("[2 Instances]", ordinary.stdout)
            self.assertIn("[7 Settings]", ordinary.stdout)
            self.assertIn("[8 Advanced]", ordinary.stdout)
            self.assertIn("FacMan guided terminal", ordinary.stdout)
            self.assertNotIn("\x1b[", ordinary.stdout)
            self.assertFalse(workspace.exists())

            semantic_pages = self.invoke(
                ["--workspace", str(workspace), "--ordinary", "--plain"],
                stdin="4\n5\n7\nq\n",
            )
            self.assertEqual(semantic_pages.returncode, 0, semantic_pages.stderr)
            self.assertIn("Launch profiles and instance-local content", semantic_pages.stdout)
            self.assertIn("gui - launch_profile", semantic_pages.stdout)
            self.assertIn("Select an instance to inspect saves", semantic_pages.stdout)
            self.assertIn("Preferences, support, and exact runtime identity", semantic_pages.stdout)
            self.assertIn("Preferred transport", semantic_pages.stdout)
            self.assertNotIn("Open Advanced for the complete generated content", semantic_pages.stdout)
            self.assertNotIn("Open Advanced for all save inspection", semantic_pages.stdout)
            self.assertFalse(workspace.exists())

            doctor_action = self.invoke(
                ["--workspace", str(workspace), "--ordinary", "--plain"],
                stdin="tab\nshift-tab\nspace\nq\n",
            )
            self.assertEqual(doctor_action.returncode, 0, doctor_action.stderr)
            self.assertIn("Actions", doctor_action.stdout)
            self.assertIn("Run Doctor", doctor_action.stdout)
            self.assertIn("Doctor completed:", doctor_action.stdout)
            self.assertFalse(workspace.exists())

            refresh_action = self.invoke(
                ["--workspace", str(workspace), "--ordinary", "--plain"],
                stdin="4\nspace\nq\n",
            )
            self.assertEqual(refresh_action.returncode, 0, refresh_action.stderr)
            self.assertIn("Refresh completed", refresh_action.stdout)
            self.assertIn("Launch profiles and instance-local content", refresh_action.stdout)
            self.assertFalse(workspace.exists())

            cli = cli_executable()
            if cli is not None:
                doctor_process = self.invoke(
                    [
                        "--workspace", str(workspace), "--ordinary", "--plain",
                        "--transport", "process", "--cli-path", str(cli),
                    ],
                    stdin="space\nq\n",
                )
                self.assertEqual(doctor_process.returncode, 0, doctor_process.stderr)
                self.assertIn("Doctor completed:", doctor_process.stdout)
                self.assertFalse(workspace.exists())

            no_color = self.invoke(
                ["--workspace", str(workspace), "--ordinary"],
                stdin="/main\nq\n",
                environment={"NO_COLOR": "1"},
            )
            self.assertEqual(no_color.returncode, 0, no_color.stderr)
            self.assertIn("Filter: main", no_color.stdout)
            self.assertNotIn("\x1b[", no_color.stdout)
            self.assertFalse(workspace.exists())

            cli = cli_executable()
            if cli is not None:
                process = self.invoke(
                    [
                        "--workspace", str(workspace), "--ordinary", "--plain",
                        "--transport", "process", "--cli-path", str(cli),
                    ],
                    stdin="q\n",
                )
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertIn("FacMan - Factorio Manager", process.stdout)
                self.assertIn("Authoritative snapshot", process.stdout)
                self.assertFalse(workspace.exists())

    def test_catalog_and_empty_unicode_workspace(self) -> None:
        version = self.invoke(["--version"])
        self.assertEqual(version.returncode, 0, version.stderr)
        with (ROOT / "release/index/version.v2.toml").open("rb") as handle:
            expected_version = tomllib.load(handle)["semver"]
        self.assertEqual(version.stdout.strip(), f"FacMan {expected_version} TUI")
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

            dry_run_refusal = self.invoke(
                [
                    "--workspace", str(workspace), "--command", "run.execute",
                    "--payload", '{"instance_id":"space-age-main"}', "--json",
                ]
            )
            self.assertEqual(dry_run_refusal.returncode, 1)
            self.assertEqual(
                json.loads(dry_run_refusal.stdout)["refusal"]["code"],
                "dry_run_write_not_executed",
            )

            unavailable = self.invoke(
                [
                    "--workspace", str(workspace), "--command", "run.execute",
                    "--payload", '{"instance_id":"space-age-main"}', "--apply", "--json",
                ]
            )
            self.assertEqual(unavailable.returncode, 2)
            self.assertEqual(unavailable.stdout, "")
            self.assertIn("remains human-gated", unavailable.stderr)

            cancelled = self.invoke(
                ["--workspace", str(workspace), "--command", "workspace.status", "--cancel", "--json"]
            )
            self.assertEqual(cancelled.returncode, 1)
            cancelled_payload = json.loads(cancelled.stdout)
            self.assertEqual(cancelled_payload["outcome"], "cancelled")
            self.assertEqual(
                cancelled_payload["operation"]["outcome"],
                "cancelled_before_dispatch",
            )
            self.assertFalse(
                cancelled_payload["operation"]["effects_may_have_occurred"],
            )
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
            self.assertEqual(
                refusal["operation"]["outcome"],
                "refused_before_effects",
            )
            self.assertFalse(refusal["operation"]["effects_may_have_occurred"])

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
