# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import datetime
import tomllib
import unittest

from tools import component_ownership_check


class ComponentOwnershipTests(unittest.TestCase):
    def test_manifest_records_latest_whole_authority_review(self) -> None:
        with component_ownership_check.MANIFEST.open("rb") as handle:
            manifest = tomllib.load(handle)
        self.assertEqual(
            datetime.date.fromisoformat(manifest["reviewed_on"]),
            datetime.date(2026, 8, 4),
        )

    def test_manifest_classifies_all_current_components(self) -> None:
        self.assertEqual(component_ownership_check.check(), [])

    def test_only_setup_has_install_mutation_authority(self) -> None:
        with component_ownership_check.MANIFEST.open("rb") as handle:
            manifest = tomllib.load(handle)
        authorities = {
            repository["id"]: repository["install_mutation_authority"]
            for repository in manifest["repository"]
        }
        self.assertEqual(
            authorities,
            {
                "factorio-launcher": False,
                "universal-launcher": False,
                "universal-setup": True,
            },
        )

    def test_temporary_incubators_have_extraction_obligations(self) -> None:
        with component_ownership_check.MANIFEST.open("rb") as handle:
            manifest = tomllib.load(handle)
        incubators = [
            component
            for component in manifest["component"]
            if component["owner"] == "temporary_incubator"
        ]
        self.assertGreaterEqual(len(incubators), 5)
        for component in incubators:
            self.assertEqual(component["final_owner"], "universal_launcher")
            self.assertTrue(component["extraction_dependency"])
            self.assertTrue(component["expires_at"])

    def test_coverage_rejects_an_unclassified_component(self) -> None:
        with component_ownership_check.MANIFEST.open("rb") as handle:
            manifest = tomllib.load(handle)
        components = copy.deepcopy(manifest["component"])
        components = [
            component
            for component in components
            if component.get("path") != "runtime/client"
        ]
        self.assertFalse(component_ownership_check.is_covered("runtime/client", components))

    def test_application_modules_are_factorio_owned_after_decomposition(self) -> None:
        with component_ownership_check.MANIFEST.open("rb") as handle:
            manifest = tomllib.load(handle)
        application = next(
            component
            for component in manifest["component"]
            if component["path"] == "runtime/factorio/application"
        )
        self.assertEqual(application["owner"], "factorio_binding")
        self.assertNotIn("final_owner", application)

    def test_archive_ownership_distinguishes_setup_inputs_from_factorio_data(self) -> None:
        with component_ownership_check.MANIFEST.open("rb") as handle:
            manifest = tomllib.load(handle)
        components = {
            component["id"]: component for component in manifest["component"]
        }
        setup_contract = components["usk-runtime"]["public_contract"]
        facman_contract = components["facman-archive"]["public_contract"]
        self.assertIn("Installable-software package/source archive", setup_contract)
        for product_term in (
            "mods/modsets/modpacks",
            "saves/worlds/scenarios",
            "snapshots",
            "backups",
            "diagnostics",
        ):
            self.assertIn(product_term, facman_contract)
            self.assertNotIn(product_term, setup_contract)


if __name__ == "__main__":
    unittest.main()
