# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import tomllib
import unittest
from pathlib import Path

from tools.codegen import generate_metadata

ROOT = Path(__file__).resolve().parents[1]


class GeneratedFrontendCatalogTests(unittest.TestCase):
    def test_native_language_catalogs_are_current_and_complete(self) -> None:
        self.assertEqual(generate_metadata.generate(write=False), [])
        catalog = json.loads(
            (ROOT / "contracts/generated-index/frontend_command_catalog.v1.json").read_text(encoding="utf-8")
        )
        commands = catalog["commands"]
        self.assertGreaterEqual(len(commands), 56)
        outputs = {
            "winforms": (ROOT / "apps/gui/windows/winforms/GeneratedCommandCatalog.cs").read_text(encoding="utf-8"),
            "appkit": (ROOT / "apps/gui/macos/appkit/FacManGeneratedCommandCatalog.m").read_text(encoding="utf-8"),
            "tui": (ROOT / "apps/tui/generated_command_catalog.hpp").read_text(encoding="utf-8"),
        }
        for command in commands:
            for field in command["request_fields"]:
                self.assertTrue(
                    {"name", "type", "required", "default", "repeatable", "request_field"}.issubset(field)
                )
            for name, text in outputs.items():
                self.assertIn(command["command_id"], text, f"{name} missing contract id")
                self.assertIn(command["runtime_id"], text, f"{name} missing runtime id")

    def test_desktop_adapters_have_no_manual_catalog_or_payload_switch(self) -> None:
        winforms_catalog = (ROOT / "apps/gui/windows/winforms/CommandCatalog.cs").read_text(encoding="utf-8")
        winforms_client = (ROOT / "apps/gui/windows/winforms/CommandClient.cs").read_text(encoding="utf-8")
        appkit_client = (ROOT / "apps/gui/macos/appkit/CommandClient.mm").read_text(encoding="utf-8")
        winforms_transport = (ROOT / "apps/gui/windows/winforms/CliProcessClient.cs").read_text(encoding="utf-8")
        appkit_transport = (ROOT / "apps/gui/macos/appkit/CliProcessClient.mm").read_text(encoding="utf-8")
        winforms_form = (ROOT / "apps/gui/windows/winforms/MainForm.cs").read_text(encoding="utf-8")
        appkit_form = (ROOT / "apps/gui/macos/appkit/MainWindowController.m").read_text(encoding="utf-8")
        self.assertIn("GeneratedCommandCatalog.All()", winforms_catalog)
        self.assertNotIn("commands.Add", winforms_catalog)
        self.assertIn("GeneratedCommandCatalog.BuildPayload", winforms_client)
        self.assertNotIn('command.Id == "', winforms_client)
        self.assertIn("FacManGeneratedCommandCatalog()", appkit_client)
        self.assertIn("FacManGeneratedPayload", appkit_client)
        self.assertNotIn("FacManPayloadForCommand", appkit_client)
        self.assertNotIn("FacManArgumentsForCommand", appkit_client)
        self.assertIn("CollectGeneratedInputs", winforms_form)
        self.assertNotIn("Inputs(params", winforms_form)
        self.assertIn("generatedInputsForCommand:", appkit_form)
        self.assertNotIn("inputsForCommandId:", appkit_form)
        self.assertIn('request["dry_run"] = command.DryRunDefault', winforms_transport)
        self.assertIn('@"dry_run": @(command.dryRunDefault)', appkit_transport)

    def test_diagnostics_export_and_localization_are_truthful(self) -> None:
        catalog = json.loads(
            (ROOT / "contracts/generated-index/frontend_command_catalog.v1.json").read_text(encoding="utf-8")
        )
        diagnostics = next(item for item in catalog["commands"] if item["command_id"] == "diagnostics.export")
        self.assertEqual(diagnostics["runtime_id"], "diagnostics.export")
        self.assertEqual(
            [field["name"] for field in diagnostics["request_fields"]],
            ["instance_id", "output_path"],
        )
        with (ROOT / "content/factorio/strings/en-US.toml").open("rb") as handle:
            strings = tomllib.load(handle)["strings"]
        expected = {
            key
            for command in catalog["commands"]
            for key in command["localization_keys"]
        }
        self.assertEqual({key for key in strings if key.startswith("command.")}, expected)


if __name__ == "__main__":
    unittest.main()
