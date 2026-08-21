# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WAVE_PATH = ROOT / "release/index/universal_provider_contract_wave.v1.toml"
REQUIREMENTS_PATH = ROOT / "release/index/universal_consumer_requirements.v1.toml"
ARCHITECTURE_PATH = ROOT / "docs/architecture/universal_multi_consumer_productization.md"

WORKUNIT_IDS = [
    "ULK-PRODUCT-COMPOSITION-CONTRACT-01",
    "USK-PRODUCT-PACKAGE-AND-RECIPE-CONTRACT-01",
    "SYNTHETIC-PRODUCT-TCK-01",
]
ULK_DESIGN_INPUT = "417c8b705d7b1a320091aa20954e382dcb62be4c"
USK_DESIGN_INPUT = "1a3fe548d278da038b96579363c1ddb7d92edeee"
ULK_BASELINE = "db58cdffefe470cbd01a79558d177db3dda8aa32"
USK_BASELINE = "095a6cf4e5d9635201c29c466dcb71ce359f9374"
ULK_PIN = "1cafe4054297cc11e02458b83d230db0cd064471"
USK_PIN = "32488fc13bd2439f9f6e52e83a97f6da345a7650"


def load_toml(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


class UniversalProviderContractWaveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.wave = load_toml(WAVE_PATH)
        cls.requirements = load_toml(REQUIREMENTS_PATH)

    def test_provider_contracts_and_tck_are_fixture_qualified(self) -> None:
        self.assertEqual(
            self.wave["schema"], "facman.universal_provider_contract_wave.v1"
        )
        self.assertEqual(self.wave["status"], "synthetic_tck_complete")
        self.assertEqual(self.wave["phase"], "sdk_packaging_ready")
        self.assertEqual(self.wave["workunit_count"], 3)
        self.assertEqual(self.wave["workunit_ids"], WORKUNIT_IDS)
        workunits = self.wave["workunit"]
        self.assertEqual([workunit["id"] for workunit in workunits], WORKUNIT_IDS)
        self.assertEqual(
            [workunit["status"] for workunit in workunits],
            ["fixture_qualified", "fixture_qualified", "complete"],
        )
        self.assertTrue(all(item["implementation_started"] for item in workunits))
        self.assertEqual(
            [item["implementation_head"] for item in workunits[:2]],
            [
                "766fe181709eaee15139303f95a649caf30abbda",
                "629d3011f784e833b26887a4b8403602c181a055",
            ],
        )
        self.assertEqual(
            [item["promotion_head"] for item in workunits[:2]],
            [
                "719a3ec240831547071d69098e1fe8c76f327fb7",
                "7f8f2baa14e78b0329db8eef8ac872818c4cf30d",
            ],
        )

    def test_provider_bases_and_separately_reconciled_consumer_pins_are_exact(self) -> None:
        inputs = self.wave["contract_design_inputs"]
        self.assertEqual(inputs["universal_launcher"], ULK_DESIGN_INPUT)
        self.assertEqual(inputs["universal_setup"], USK_DESIGN_INPUT)
        baselines = self.wave["target_repository_bases"]
        self.assertEqual(baselines["universal_launcher"], ULK_BASELINE)
        self.assertEqual(baselines["universal_setup"], USK_BASELINE)
        self.assertEqual(baselines["required_ref"], "refs/heads/dev")
        self.assertEqual(
            baselines["use"], "exact_task_branch_bases_after_branch_model_ratification"
        )
        pins = self.wave["consumer_pins"]
        self.assertEqual(pins["universal_launcher"], ULK_PIN)
        self.assertEqual(pins["universal_setup"], USK_PIN)
        self.assertTrue(pins["changed"])
        self.assertFalse(pins["repin_requires_separate_workunit"])
        self.assertEqual(pins["reconciled_by"], "FACMAN-PROVIDER-PIN-RECONCILIATION-01")

    def test_ulk_contracts_and_capability_vocabulary_are_exact(self) -> None:
        ulk = self.wave["workunit"][0]
        self.assertEqual(ulk["target_repository"], "universal-launcher")
        self.assertEqual(ulk["target_baseline"], ULK_BASELINE)
        self.assertEqual(ulk["task_branch"], "task/product-composition-contract-01")
        self.assertEqual(
            ulk["contract_ids"],
            [
                "ulk.product_descriptor.v2",
                "ulk.entrypoint.v1",
                "ulk.launch_capability.v1",
                "ulk.product_composition.v1",
                "ulk.contract_set_identity.v1",
            ],
        )
        self.assertEqual(
            ulk["capability_vocabulary"],
            [
                "single_process",
                "open_document",
                "multi_instance",
                "profile_selection",
                "artifact_sets",
                "session_supervision",
                "background_service",
                "server",
            ],
        )
        self.assertEqual(ulk["forbidden_product_kinds"], ["game", "catalogue", "simulation"])

    def test_usk_contracts_fields_and_non_goals_are_exact(self) -> None:
        usk = self.wave["workunit"][1]
        self.assertEqual(usk["target_repository"], "universal-setup")
        self.assertEqual(usk["target_baseline"], USK_BASELINE)
        self.assertEqual(usk["task_branch"], "task/product-package-recipe-contract-01")
        self.assertEqual(
            usk["contract_ids"],
            [
                "usk.product_package.v1",
                "usk.setup_recipe.v1",
                "usk.component_manifest.v1",
                "usk.source_manifest.v1",
            ],
        )
        self.assertEqual(usk["compatibility_rule_target"], "usk.installed_state.v1")
        self.assertIn("entry paths, sizes and hashes", usk["contract_fields"])
        self.assertIn("mutable and preserved data paths", usk["contract_fields"])
        self.assertIn("license/SBOM/provenance/authenticity references", usk["contract_fields"])
        self.assertFalse(usk["product_specific_names_allowed"])
        self.assertIn("download URLs as authority", usk["forbidden_scope"])
        self.assertIn("live mutation", usk["forbidden_scope"])

    def test_synthetic_tck_location_dependencies_and_vocabulary_are_exact(self) -> None:
        synthetic = self.wave["workunit"][2]
        self.assertEqual(synthetic["depends_on"], WORKUNIT_IDS[:2])
        self.assertEqual(synthetic["target_repository"], "factorio-launcher_superbuild_tests")
        self.assertEqual(
            synthetic["forbidden_product_vocabulary"],
            [
                "factorio",
                "dominium",
                "domino",
                "c3",
                "cassette",
                "catalogue",
                "game",
                "simulation",
            ],
        )
        self.assertTrue(synthetic["fixture_executed"])
        self.assertEqual(synthetic["facman_task_branch"], "task/synthetic-product-tck-01")
        self.assertEqual(
            synthetic["facman_task_base"],
            "5dfef289aa98a1a8df62b8e32b81e1743d2aeaad",
        )
        self.assertEqual(
            synthetic["universal_launcher_head"],
            "719a3ec240831547071d69098e1fe8c76f327fb7",
        )
        self.assertEqual(
            synthetic["universal_setup_head"],
            "7f8f2baa14e78b0329db8eef8ac872818c4cf30d",
        )
        self.assertEqual(
            synthetic["implementation_head"],
            "926850007a72269ceddd7f85905e934b6c4dcfc7",
        )
        self.assertEqual(synthetic["hosted_tck_run"], "30877499521")
        self.assertEqual(synthetic["hosted_gate"], "passed")
        self.assertFalse(synthetic["contract_maturity_promoted"])
        self.assertFalse(synthetic["consumer_adoption"])
        self.assertEqual(
            [layer["repository"] for layer in self.wave["tck_layer"]],
            ["universal-launcher", "universal-setup", "factorio-launcher"],
        )

    def test_reconciliation_ownership_and_maturity_are_explicit(self) -> None:
        gate = self.wave["reconciliation_gate"]
        self.assertTrue(all(gate.values()))
        acquisition = self.wave["acquisition_boundary"]
        self.assertEqual(
            acquisition["network_discovery_and_download"],
            "consumer_or_consumer_owned_connector",
        )
        self.assertFalse(acquisition["download_url_is_package_authority"])
        stores = self.wave["store_ownership_boundary"]
        self.assertEqual(stores["product_runtime_pack_store_and_retention"], "product")
        self.assertEqual(
            stores["runnable_artifact_set_and_launch_plan_binding"],
            "universal_launcher",
        )
        maturity = self.wave["contract_maturity"]
        self.assertEqual(maturity["provider_local_fixtures"], "fixture-qualified")
        self.assertTrue(maturity["maturity_is_per_contract"])

    def test_wave_records_provider_implementation_without_external_authority(self) -> None:
        for key in (
            "implementation_moved",
            "product_code_implemented",
        ):
            self.assertFalse(self.wave[key], key)
        for key in (
            "provider_code_implemented",
            "provider_repository_branches_created",
            "provider_repository_tasks_created",
            "provider_repository_worktrees_created",
        ):
            self.assertTrue(self.wave[key], key)
        self.assertTrue(all(not value for value in self.wave["authority"].values()))

    def test_consumer_projection_and_architecture_match_the_reconciled_wave(self) -> None:
        projected = self.requirements["provider_contract_wave"]
        self.assertEqual(self.requirements["programme_state"], "synthetic_tck_complete")
        self.assertEqual(projected["status"], "synthetic_tck_complete")
        self.assertEqual(projected["workunits"], WORKUNIT_IDS)
        self.assertEqual(
            projected["workunit_status"],
            {
                "universal_launcher": "fixture_qualified",
                "universal_setup": "fixture_qualified",
                "synthetic_tck": "complete",
            },
        )
        self.assertTrue(projected["synthetic_tck_hosted_gate_passed"])
        document = ARCHITECTURE_PATH.read_text(encoding="utf-8")
        self.assertIn("## Reconciled provider contract wave", document)
        self.assertIn("`fixture_qualified`", document)
        self.assertIn("universal_provider_contract_wave.v1.toml", document)
        for identity in (
            *WORKUNIT_IDS,
            ULK_DESIGN_INPUT,
            USK_DESIGN_INPUT,
            ULK_BASELINE,
            USK_BASELINE,
            ULK_PIN,
            USK_PIN,
        ):
            self.assertIn(identity, document)


if __name__ == "__main__":
    unittest.main()
