# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from tools import (
    build_winforms_c1_portable,
    facman_winforms_c1_check,
    winforms_c1_runtime_smoke,
)

ROOT = Path(__file__).resolve().parents[1]


class FacManWinFormsC1ShellTests(unittest.TestCase):
    def test_complete_bounded_shell_contract(self) -> None:
        self.assertEqual(facman_winforms_c1_check.main(), 0)

    def test_runtime_keyboard_accessibility_and_scaling_receipt(self) -> None:
        self.assertEqual(winforms_c1_runtime_smoke.main(), 0)

    def test_window_close_does_not_request_effect_cancellation(self) -> None:
        shell = (
            ROOT / "apps/gui/windows/winforms/C1ShellForm.cs"
        ).read_text(encoding="utf-8")
        for call in (
            "RefreshReadinessAsync(CancellationToken.None)",
            "ScanInstallationsAsync(root, CancellationToken.None)",
            "RegisterInstallationAsync(\n                    installId, path, CancellationToken.None)",
            "CreateInstanceAsync(\n                    instanceId, displayName, installId, CancellationToken.None)",
            "ApplyRecoveryAsync(\n                    transactionId, CancellationToken.None)",
            "InspectUncertainActionAsync(\n                        CancellationToken.None)",
            "PlayAsync(CancellationToken.None)",
            "StopSessionAsync(\n                    CancellationToken.None)",
        ):
            self.assertIn(call, shell)
        self.assertIn("if (!CanUpdateWindow) return;", shell)

    def test_active_fixture_sessions_are_backend_projected_and_stoppable(self) -> None:
        models = (
            ROOT / "apps/gui/windows/winforms/PresentationModels.cs"
        ).read_text(encoding="utf-8")
        store = (
            ROOT / "apps/gui/windows/winforms/C1LivePresentationStore.cs"
        ).read_text(encoding="utf-8")

        self.assertIn('PresentationJson.Records(value, "active_operations")', models)
        self.assertIn("IList<PresentationOperation> ActiveOperations", models)
        self.assertIn('"activity_recovery", "sessions.stop"', store)
        self.assertIn('action.Role == "recovery" || action.Role == "session"', store)

    def test_content_and_saves_are_ordinary_descriptor_driven_pages(self) -> None:
        models = (
            ROOT / "apps/gui/windows/winforms/PresentationModels.cs"
        ).read_text(encoding="utf-8")
        store = (
            ROOT / "apps/gui/windows/winforms/C1LivePresentationStore.cs"
        ).read_text(encoding="utf-8")
        shell = (
            ROOT / "apps/gui/windows/winforms/C1ShellForm.cs"
        ).read_text(encoding="utf-8")

        for anchor in (
            "Identity",
            "Sha256",
            "AssociationStatus",
            "BackupStatus",
        ):
            self.assertIn(anchor, models)
        for scope in ('"content"', '"saves"'):
            self.assertIn(scope, store)
        self.assertIn('EnsureRecord(pages, "content")', store)
        self.assertIn('EnsureRecord(pages, "saves")', store)
        for action in (
            '"mods.inspect"',
            '"modsets.plan"',
            '"modsets.apply"',
            '"modsets.verify"',
            '"modsets.rollback"',
            '"saves.inspect"',
            '"saves.associate"',
            '"saves.backup"',
        ):
            self.assertIn(action, shell)
        self.assertIn('"content", "mods.inspect"', shell)
        self.assertIn('"saves", "saves.inspect"', shell)
        self.assertIn("InvokeDescriptorActionAsync(scope, actionId)", shell)

    def test_redacted_support_export_is_an_ordinary_descriptor_action(self) -> None:
        store = (
            ROOT / "apps/gui/windows/winforms/C1LivePresentationStore.cs"
        ).read_text(encoding="utf-8")
        shell = (
            ROOT / "apps/gui/windows/winforms/C1ShellForm.cs"
        ).read_text(encoding="utf-8")

        self.assertIn('action.Role == "manage" || action.Role == "diagnostic"', store)
        self.assertIn('"support.export_redacted_bundle"', shell)
        self.assertIn(
            'InvokeDescriptorActionAsync("settings_support", actionId)', shell
        )
        self.assertIn("PromptActionInputs(descriptor)", shell)
        self.assertIn("liveStore.LastActionPayload", shell)

    def test_initial_backend_refresh_keeps_window_close_available(self) -> None:
        shell = (
            ROOT / "apps/gui/windows/winforms/C1ShellForm.cs"
        ).read_text(encoding="utf-8")

        self.assertIn("FormClosing += delegate { lifetime.Cancel(); };", shell)
        self.assertIn("UseWaitCursor = true;", shell)
        self.assertIn("UseWaitCursor = false;", shell)
        self.assertNotIn("Enabled = false;", shell)

    def test_optional_cli_is_packaged_beside_shell(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            shell = root / "FacMan.WinForms.exe"
            cli = root / "facman.exe"
            shell.write_bytes(b"shell")
            cli.write_bytes(b"cli")
            output = build_winforms_c1_portable.build(shell, root / "prototype.zip", cli)
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(archive.read("bin/facman.exe"), b"cli")
                notice = archive.read("PROTOTYPE-NOTICE.txt").decode("utf-8")
                self.assertIn("no live Play authority", notice)
                self.assertIn("unsigned, unpublished", notice)


if __name__ == "__main__":
    unittest.main()
