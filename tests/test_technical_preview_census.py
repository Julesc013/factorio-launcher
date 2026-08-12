# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import technical_preview_census


class TechnicalPreviewCensusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.matrix = technical_preview_census._toml(technical_preview_census.MATRIX_PATH)
        cls.scope = technical_preview_census._toml(technical_preview_census.SCOPE_PATH)
        cls.catalog = technical_preview_census._json(technical_preview_census.CATALOG_PATH)

    def test_canonical_census_and_generated_outputs_are_current(self) -> None:
        self.assertEqual(technical_preview_census.check_outputs(), [])

    def test_product_matrix_is_outcome_sized_not_command_sized(self) -> None:
        outcomes = self.matrix["capability"]
        self.assertGreaterEqual(len(outcomes), 20)
        self.assertLessEqual(len(outcomes), 40)
        self.assertNotEqual(len(outcomes), len(self.catalog["commands"]))
        self.assertFalse(self.matrix["one_row_per_command_census_required"])

    def test_every_command_has_one_ledger_row_and_zero_or_more_outcome_mappings(self) -> None:
        ledger = technical_preview_census.build_ledger(self.matrix, self.catalog)
        self.assertEqual(ledger["command_count"], len(self.catalog["commands"]))
        self.assertEqual(len({item["command_id"] for item in ledger["commands"]}), ledger["command_count"])
        self.assertTrue(all(isinstance(item["product_capability_ids"], list) for item in ledger["commands"]))
        self.assertTrue(any(len(item["product_capability_ids"]) > 1 for item in ledger["commands"]))

    def test_preview_scope_and_frontend_cut_are_frozen(self) -> None:
        self.assertEqual(self.scope["platform"], "windows_x64")
        self.assertEqual(self.scope["primary_frontend"], "winforms")
        self.assertEqual(self.scope["normative_automation_contract"], "cli_json")
        self.assertEqual(
            self.scope["tui_status"],
            "required_same_facman_binary_ordinary_parity_and_advanced_command_coverage",
        )
        self.assertEqual(
            self.scope["terminal_artifact_law"],
            "facman provides cli_json, human_cli, and tui; no second tui executable is required",
        )
        self.assertFalse(self.scope["managed_install_required"])
        self.assertFalse(self.scope["public_release_allowed"])

    def test_factorio_product_authority_stays_in_facman(self) -> None:
        by_id = {item["id"]: item for item in self.matrix["capability"]}
        for item_id in (
            "instances.create_isolated",
            "profiles.create_select",
            "modsets.apply_instance_local",
            "saves.discover_select",
            "readiness.compute",
        ):
            self.assertEqual(by_id[item_id]["owner"], "facman")
        self.assertEqual(by_id["modsets.apply_instance_local"]["effect_class"], "instance_content_mutation")
        self.assertEqual(by_id["launch.menu_execute"]["provider_owner"], "universal_launcher")
        self.assertEqual(by_id["installations.managed_lifecycle"]["provider_owner"], "universal_setup")

    def test_registration_does_not_upgrade_unknown_commands(self) -> None:
        ledger = technical_preview_census.build_ledger(self.matrix, self.catalog)
        unspecified = [item for item in ledger["commands"] if item["availability"] == "unspecified"]
        self.assertTrue(unspecified)
        self.assertTrue(all(item["observed_classification"] in {"unknown_unverified", "outside_preview", "diagnostic_internal"} for item in unspecified))

    def test_invalid_preview_authority_is_rejected(self) -> None:
        invalid = copy.deepcopy(self.scope)
        invalid["authority"]["publication"] = True
        self.assertIn(
            "Technical Preview scope grants authority",
            technical_preview_census.validate_scope_authority(invalid),
        )


if __name__ == "__main__":
    unittest.main()
