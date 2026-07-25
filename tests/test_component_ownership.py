# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import tomllib
import unittest

from tools import component_ownership_check


class ComponentOwnershipTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
