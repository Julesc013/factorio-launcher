# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "release/index/universal_consumer_requirements.v1.toml"
ARCHITECTURE = ROOT / "docs/architecture/universal_multi_consumer_productization.md"


class UniversalConsumerRequirementsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with MATRIX.open("rb") as handle:
            cls.data = tomllib.load(handle)

    def test_exactly_three_characterization_lanes_are_admitted(self) -> None:
        expected = [
            "FACMAN-C1-BACKEND-IDENTITY-01",
            "DOMINIUM-UNIVERSAL-BOUNDARY-AUDIT-01",
            "C3-UNIVERSAL-CONSUMER-PROFILE-01",
        ]
        self.assertEqual(self.data["schema"], "facman.universal_consumer_requirements.v1")
        self.assertEqual(
            self.data["architecture"],
            "docs/architecture/universal_multi_consumer_productization.md",
        )
        self.assertTrue(ARCHITECTURE.is_file())
        self.assertEqual(self.data["admitted_lane_count"], 3)
        self.assertEqual(self.data["admitted_lane_ids"], expected)
        self.assertEqual([lane["id"] for lane in self.data["lane"]], expected)
        self.assertTrue(all(not lane["implementation_moved"] for lane in self.data["lane"]))

    def test_qualified_provider_pins_are_unchanged(self) -> None:
        pins = self.data["provider_pins"]
        self.assertEqual(
            pins["universal_launcher"],
            "7fc25340623131ba86c08dca4fb8a43b18a4520d",
        )
        self.assertEqual(
            pins["universal_setup"],
            "3048128963dc718a7c38c1cfcdda9e813a23b0db",
        )
        self.assertTrue(pins["repin_workunit_required"])

    def test_capability_matrix_is_complete_and_does_not_force_authority(self) -> None:
        expected = {
            "package_authoring",
            "package_verification",
            "install_repair_uninstall",
            "update_rollback",
            "product_references",
            "profiles_instances",
            "process_supervision",
            "launch_sessions",
            "product_gui",
            "legacy_os_constraints",
        }
        requirements = {row["capability"]: row for row in self.data["requirement"]}
        self.assertEqual(set(requirements), expected)
        for row in requirements.values():
            self.assertEqual(
                set(row),
                {"capability", "facman", "dominium", "c3_legacy_x86", "c3_modern_x64"},
            )
        self.assertEqual(requirements["profiles_instances"]["c3_legacy_x86"], "no")
        self.assertEqual(requirements["launch_sessions"]["c3_legacy_x86"], "no")

    def test_c3_profiles_and_provider_wave_are_bounded(self) -> None:
        profiles = {row["id"]: row for row in self.data["consumer_profile"]}
        self.assertEqual(profiles["c3_legacy_x86"]["provider_use"], "usk_package_authoring_only")
        self.assertEqual(profiles["c3_legacy_x86"]["ulk"], "absent")
        self.assertEqual(
            profiles["c3_modern_x64"]["ulk"],
            "absent_until_demonstrated_activation_or_session_journey",
        )
        wave = self.data["provider_contract_wave"]
        self.assertEqual(wave["status"], "active_implementation")
        self.assertEqual(
            wave["workunits"],
            [
                "ULK-PRODUCT-COMPOSITION-CONTRACT-01",
                "USK-PRODUCT-PACKAGE-AND-RECIPE-CONTRACT-01",
                "SYNTHETIC-PRODUCT-TCK-01",
            ],
        )
        self.assertEqual(
            wave["workunit_status"],
            {
                "universal_launcher": "active_implementation",
                "universal_setup": "active_implementation",
                "synthetic_tck": "blocked_on_provider_contracts",
            },
        )

    def test_c3_delta_and_corrected_ownership_are_gates(self) -> None:
        delta = self.data["c3_delta_gate"]
        self.assertEqual(delta["id"], "C3-UNIVERSAL-CONSUMER-PROFILE-DELTA-01")
        self.assertEqual(delta["status"], "complete")
        self.assertFalse(delta["implementation_moved"])
        self.assertTrue(self.data["audit_gate"]["c3_delta_complete"])
        self.assertTrue(
            self.data["audit_gate"]["dominium_lifecycle_ownership_corrected"]
        )
        self.assertFalse(self.data["acquisition_setup_boundary"]["usk_is_general_downloader"])
        self.assertIn("runtime pack store", self.data["content_store_boundary"]["product"])

    def test_no_new_authority_or_implementation_move_is_granted(self) -> None:
        for key in (
            "implementation_moves_allowed",
            "provider_repins_allowed",
            "real_setup_mutation_allowed",
            "product_execution_allowed",
            "signing_allowed",
            "publication_allowed",
            "successor_route_authority",
        ):
            self.assertFalse(self.data[key], key)
        gate = self.data["audit_gate"]
        self.assertTrue(gate["dominium_audit_complete"])
        self.assertTrue(gate["c3_audit_complete"])
        self.assertTrue(gate["c3_delta_complete"])
        self.assertFalse(gate["implementation_extraction_started"])
        self.assertTrue(gate["delete_rows_conditional"])


if __name__ == "__main__":
    unittest.main()
