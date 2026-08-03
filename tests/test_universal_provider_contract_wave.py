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
ULK_BASELINE = "417c8b705d7b1a320091aa20954e382dcb62be4c"
USK_BASELINE = "1a3fe548d278da038b96579363c1ddb7d92edeee"
ULK_PIN = "7fc25340623131ba86c08dca4fb8a43b18a4520d"
USK_PIN = "3048128963dc718a7c38c1cfcdda9e813a23b0db"


def load_toml(path: Path) -> dict:
    with path.open("rb") as handle:
        return tomllib.load(handle)


class UniversalProviderContractWaveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.wave = load_toml(WAVE_PATH)
        cls.requirements = load_toml(REQUIREMENTS_PATH)

    def test_exact_three_workunits_are_active_contract_design(self) -> None:
        self.assertEqual(
            self.wave["schema"], "facman.universal_provider_contract_wave.v1"
        )
        self.assertEqual(self.wave["status"], "active_contract_design")
        self.assertEqual(self.wave["phase"], "contract_design_only")
        self.assertEqual(self.wave["workunit_count"], 3)
        self.assertEqual(self.wave["workunit_ids"], WORKUNIT_IDS)

        workunits = self.wave["workunit"]
        self.assertEqual([workunit["id"] for workunit in workunits], WORKUNIT_IDS)
        self.assertTrue(
            all(workunit["status"] == "active_contract_design" for workunit in workunits)
        )
        self.assertTrue(all(not workunit["implementation_started"] for workunit in workunits))

    def test_provider_baselines_are_distinct_from_unchanged_consumer_pins(self) -> None:
        baselines = self.wave["target_repository_baselines"]
        self.assertEqual(baselines["universal_launcher"], ULK_BASELINE)
        self.assertEqual(baselines["universal_setup"], USK_BASELINE)
        self.assertEqual(
            baselines["use"], "immutable_contract_design_input_not_consumer_pin"
        )

        pins = self.wave["consumer_pins"]
        self.assertEqual(pins["universal_launcher"], ULK_PIN)
        self.assertEqual(pins["universal_setup"], USK_PIN)
        self.assertFalse(pins["changed"])
        self.assertTrue(pins["repin_requires_separate_workunit"])

    def test_ulk_contracts_and_capability_vocabulary_are_exact(self) -> None:
        ulk = self.wave["workunit"][0]
        self.assertEqual(ulk["target_repository"], "universal-launcher")
        self.assertEqual(ulk["target_baseline"], ULK_BASELINE)
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

    def test_usk_contracts_and_fields_are_exact(self) -> None:
        usk = self.wave["workunit"][1]
        self.assertEqual(usk["target_repository"], "universal-setup")
        self.assertEqual(usk["target_baseline"], USK_BASELINE)
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
        self.assertEqual(
            usk["contract_fields"],
            [
                "product_id",
                "product_version",
                "publisher identity/reference",
                "component IDs",
                "platform/architecture",
                "entry paths and hashes",
                "source identity",
                "target policy",
                "mutable versus immutable paths",
                "data/config roots",
                "migration requirements",
                "install/repair/update/uninstall support",
                "rollback/recovery disposition",
                "license/SBOM/provenance references",
            ],
        )
        self.assertFalse(usk["product_specific_names_allowed"])

    def test_synthetic_tck_obligations_and_forbidden_vocabulary_are_exact(self) -> None:
        synthetic = self.wave["workunit"][2]
        self.assertEqual(
            synthetic["proof_obligations"],
            [
                "package authoring",
                "inspection",
                "plan preview",
                "installation fixture",
                "reference composition",
                "launch preview",
                "structured refusal",
                "recovery fixture",
            ],
        )
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
        self.assertFalse(synthetic["fixture_executed"])

    def test_wave_grants_no_implementation_or_external_authority(self) -> None:
        for key in (
            "implementation_moved",
            "provider_code_implemented",
            "product_code_implemented",
            "provider_repository_branches_created",
            "provider_repository_tasks_created",
            "provider_repository_worktrees_created",
        ):
            self.assertFalse(self.wave[key], key)

        for key in (
            "provider_repin",
            "real_setup_mutation",
            "product_execution",
            "signing",
            "publication",
            "successor_route",
        ):
            self.assertFalse(self.wave["authority"][key], key)

        for workunit in self.wave["workunit"]:
            self.assertFalse(workunit["provider_repository_branch_created"])
            self.assertFalse(workunit["provider_repository_task_created"])

    def test_consumer_projection_and_architecture_match_the_active_wave(self) -> None:
        projected = self.requirements["provider_contract_wave"]
        self.assertEqual(self.requirements["programme_state"], "provider_contract_design")
        self.assertEqual(projected["status"], "active_contract_design")
        self.assertEqual(projected["workunits"], WORKUNIT_IDS)
        self.assertEqual(
            projected["design_record"],
            "release/index/universal_provider_contract_wave.v1.toml",
        )
        self.assertTrue(projected["contract_design_only"])
        self.assertFalse(projected["provider_repository_branches_created"])
        self.assertFalse(projected["provider_repository_tasks_created"])
        self.assertFalse(projected["provider_code_implemented"])
        self.assertFalse(projected["product_code_implemented"])

        document = ARCHITECTURE_PATH.read_text(encoding="utf-8")
        self.assertIn("## Active provider contract-design wave", document)
        self.assertIn("`active_contract_design`", document)
        self.assertIn("universal_provider_contract_wave.v1.toml", document)
        for identity in (*WORKUNIT_IDS, ULK_BASELINE, USK_BASELINE, ULK_PIN, USK_PIN):
            self.assertIn(identity, document)


if __name__ == "__main__":
    unittest.main()
