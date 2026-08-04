# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import unittest

from tools import synthetic_product_tck, synthetic_product_tck_check


class SyntheticProductTckTests(unittest.TestCase):
    def test_tracked_definition_is_authority_free_and_lock_stable(self) -> None:
        self.assertEqual(synthetic_product_tck_check.check(), [])

    def test_provider_contracts_bind_as_one_neutral_fixture(self) -> None:
        orchestration = synthetic_product_tck.load_json(
            synthetic_product_tck.ORCHESTRATION
        )
        journal = synthetic_product_tck.load_json(synthetic_product_tck.JOURNAL)
        composition = {
            "product": {
                "product_id": "org.example.fixture",
                "exact_version": "1.0.0",
            },
            "entrypoints": [
                {
                    "relative_path": "bin/fixture",
                    "artifact_set_id": "core",
                    "capabilities": [{"kind": "single_process"}],
                }
            ],
        }
        package = {
            "product_id": "org.example.fixture",
            "product_version": "1.0.0",
            "components": [
                {
                    "component_id": "core",
                    "entries": [
                        {"path": "bin/fixture"},
                        {"path": "share/message.txt"},
                    ],
                }
            ],
            "immutable_paths": ["bin/fixture", "share/message.txt"],
        }
        recipe = {
            "product_id": "org.example.fixture",
            "product_version": "1.0.0",
            "component_ids": ["core"],
            "migrations": [
                {"from_version": "1.0.0", "to_version": "1.1.0"}
            ],
        }
        self.assertEqual(
            synthetic_product_tck.validate_cross_provider_contracts(
                composition, package, recipe, orchestration, journal
            ),
            [],
        )

    def test_provider_orchestration_fails_closed_on_authority_drift(self) -> None:
        orchestration = synthetic_product_tck.load_json(
            synthetic_product_tck.ORCHESTRATION
        )
        journal = synthetic_product_tck.load_json(synthetic_product_tck.JOURNAL)
        composition = {
            "product": {
                "product_id": "org.example.fixture",
                "exact_version": "1.0.0",
            },
            "entrypoints": [
                {
                    "relative_path": "bin/fixture",
                    "artifact_set_id": "core",
                    "capabilities": [{"kind": "single_process"}],
                }
            ],
        }
        package = {
            "product_id": "org.example.fixture",
            "product_version": "1.0.0",
            "components": [
                {
                    "component_id": "core",
                    "entries": [
                        {"path": "bin/fixture"},
                        {"path": "share/message.txt"},
                    ],
                }
            ],
            "immutable_paths": ["bin/fixture", "share/message.txt"],
        }
        recipe = {
            "product_id": "org.example.fixture",
            "product_version": "1.0.0",
            "component_ids": ["core"],
            "migrations": [
                {"from_version": "1.0.0", "to_version": "1.1.0"}
            ],
        }
        orchestration["authority"]["product_execution"] = True
        problems = synthetic_product_tck.validate_cross_provider_contracts(
            composition, package, recipe, orchestration, journal
        )
        self.assertIn("all TCK authority booleans must remain false", problems)


if __name__ == "__main__":
    unittest.main()
