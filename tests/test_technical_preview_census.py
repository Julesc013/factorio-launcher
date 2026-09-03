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

    def test_generated_census_prose_respects_source_line_limits(self) -> None:
        for path, content in technical_preview_census.build_outputs().items():
            if path.suffix == ".md":
                self.assertLessEqual(
                    max(len(line) for line in content.splitlines()),
                    240,
                    path.name,
                )

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

    def test_implemented_workspace_migration_routes_are_not_unknown(self) -> None:
        ledger = technical_preview_census.build_ledger(self.matrix, self.catalog)
        by_id = {item["command_id"]: item for item in ledger["commands"]}
        for command_id in (
            "workspace.migration.inspect",
            "workspace.migration.plan",
            "workspace.migration.apply",
            "workspace.migration.operation.inspect",
            "workspace.migration.resume",
            "workspace.migration.recover",
            "workspace.migration.rollback",
        ):
            self.assertEqual(by_id[command_id]["availability"], "implemented")
            self.assertEqual(
                by_id[command_id]["observed_classification"],
                "implemented_unqualified",
            )
        counts: dict[str, int] = {}
        for item in ledger["commands"]:
            classification = item["observed_classification"]
            counts[classification] = counts.get(classification, 0) + 1
        self.assertEqual(counts["implemented_unqualified"], 14)
        self.assertEqual(counts["unknown_unverified"], 80)

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

    def test_matrix_distinguishes_windows_reference_beta_and_one_zero_laws(self) -> None:
        self.assertEqual(
            self.matrix["activation_status"],
            "implemented_census_activation_graph_terminal",
        )
        self.assertTrue(self.matrix["activation_workunits_terminal"])
        self.assertEqual(
            self.matrix["activation_successor_workunit"],
            "FACMAN-WINDOWS-EXISTING-INSTALL-JOURNEY-01",
        )
        self.assertEqual(
            self.matrix["required_projections_windows_reference_0_1"],
            ["cli_json", "tui", "winforms"],
        )
        self.assertEqual(
            self.matrix["required_beta_terminal_surfaces"],
            ["cli_json", "cli_human", "tui"],
        )
        self.assertEqual(
            self.matrix["required_beta_preview_frontends"],
            ["winforms", "appkit", "gtk"],
        )

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

    def test_alpha5_foundation_truth_is_not_regressed(self) -> None:
        by_id = {item["id"]: item for item in self.matrix["capability"]}
        workspace = by_id["workspace.open_create_inspect"]
        self.assertIn("journaled no-clobber apply", workspace["persistence_migration"])
        self.assertNotIn("migration apply remains fail-closed", workspace["persistence_migration"])
        self.assertIn("canonicalize_legacy_install_ref", workspace["persistence_migration"])
        self.assertIn("Legacy sources are preserved", workspace["limits"])
        self.assertIn(
            "exact interrupted operations can be inspected, resumed, recovered, or rolled back",
            workspace["limits"],
        )

        last_run = by_id["last_run.inspect"]
        self.assertEqual(last_run["status"], "implemented_unqualified")
        self.assertIn(
            "runtime/factorio/application/last_run_provider.cpp",
            last_run["backend_evidence"],
        )
        self.assertIn("sole live Last Run authority", last_run["persistence_migration"])
        self.assertIn("never persisted or consulted as authority or fallback", last_run["persistence_migration"])
        self.assertNotIn("GUI-local", last_run["persistence_migration"])
        self.assertNotIn("frontends never cache", last_run["persistence_migration"])

        package = by_id["package.reproduce_windows"]
        self.assertIn("combined Windows WinForms Technical Preview target", package["limits"])
        self.assertNotIn("legacy profile gap", package["limits"])

        profile = technical_preview_census._toml(
            technical_preview_census.WINDOWS_PRODUCT_PROFILE_PATH
        )
        targets = technical_preview_census._toml(technical_preview_census.TARGETS_PATH)
        artifacts = technical_preview_census._toml(technical_preview_census.ARTIFACTS_PATH)
        target = next(
            item
            for item in targets["target"]
            if item["id"] == technical_preview_census.WINDOWS_PRODUCT_TARGET
        )
        artifact = next(
            item
            for item in artifacts["artifact"]
            if item["id"] == technical_preview_census.WINDOWS_PRODUCT_ARTIFACT
        )
        self.assertEqual(profile["linkage"]["provider_source_linkage"], "shared")
        self.assertEqual(target["runtime_linkage"], "embedded_static")
        self.assertEqual(artifact["target_id"], target["id"])

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
