# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FacManLiveShellIntegrationTests(unittest.TestCase):
    def test_cross_shell_integration_checker(self) -> None:
        completed = subprocess.run(
            [sys.executable, str(ROOT / "tools/facman_live_shell_integration_check.py")],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("3 shells", completed.stdout)

    def test_workunit_closes_and_windows_candidate_is_active(self) -> None:
        with (ROOT / "release/index/plan.v1.toml").open("rb") as handle:
            plan = tomllib.load(handle)
        work = {item["id"]: item for item in plan["workunit"]}
        self.assertEqual(work["FACMAN-C1-LIVE-SHELL-INTEGRATION-01"]["status"], "complete")
        candidate = work["C1-WINDOWS-RELEASE-CANDIDATE-01"]
        self.assertEqual(candidate["status"], "active")
        self.assertEqual(candidate["branch"], "task/c1-windows-release-candidate-01")
        self.assertEqual(
            candidate["base_revision"], "3bf9998fd36b74b287ebf64b972dd26f7e47e1c8"
        )
        self.assertIn(
            "FACMAN-C1-LIVE-SHELL-INTEGRATION-01",
            work["C1-WINDOWS-RELEASE-CANDIDATE-01"]["depends_on"],
        )

    def test_current_truth_keeps_live_play_unavailable(self) -> None:
        with (ROOT / "release/index/current_state.v1.toml").open("rb") as handle:
            state = tomllib.load(handle)
        self.assertEqual(
            state["revisions"]["observed_dev"],
            "8b260d07e5182d4ccfa0156b434948b5080caaa1",
        )
        self.assertEqual(state["product"]["execution"], "unavailable")
        self.assertEqual(state["scorecard"]["accepted_real_play_routes"], 0)
        self.assertNotEqual(state["product"]["user_workflow"], "advanced_command_surface_only")

    def test_gtk_completed_launch_reads_payload_schema_not_envelope_schema(self) -> None:
        fixture_path = (
            ROOT
            / "tests/fixtures/presentation/live/completed-launch.transport_response.v2.json"
        )
        response = json.loads(fixture_path.read_text(encoding="utf-8"))
        self.assertEqual(response["schema"], "facman.transport_response.v2")
        self.assertEqual(response["payload"]["schema"], "factorio.launch_session.v1")
        self.assertTrue(response["payload"]["complete"])

        gtk = (ROOT / "apps/gui/linux/gtk/main.c").read_text(encoding="utf-8")
        generated = (
            ROOT / "apps/gui/linux/gtk/generated_live_presentation.c"
        ).read_text(encoding="utf-8")
        self.assertIn('facman_payload_text(result, "schema")', gtk)
        self.assertIn('facman_payload_boolean(result, "complete")', gtk)
        self.assertNotIn('facman_record_text(result, "schema")', gtk)
        self.assertIn('facman_scoped_member(document, "payload", key', generated)
        self.assertIn("g_strstr_len(begin, end - begin, needle)", generated)

        native_test = (
            ROOT / "apps/gui/linux/gtk/live_presentation_test.c"
        ).read_text(encoding="utf-8")
        ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        self.assertIn("facman_payload_text(document, \"schema\")", native_test)
        self.assertIn("facman_payload_boolean(document, \"complete\")", native_test)
        self.assertIn("meson test -C build/gtk-preview --print-errorlogs", ci)


if __name__ == "__main__":
    unittest.main()
