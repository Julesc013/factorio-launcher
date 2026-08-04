# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DELTA_PATH = ROOT / "release/index/c3_universal_consumer_profile_delta.v1.toml"
REPORT_PATH = ROOT / "docs/product/c3_universal_consumer_profile_delta_01.md"
BASE = "ea984df9b7ab99cf47fcdbd8edcb571e6ce80d52"
HEAD = "f27c1d0c6798ea68b81ac0b0889ef770ad19d2d9"


class C3UniversalConsumerProfileDeltaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        with DELTA_PATH.open("rb") as handle:
            cls.delta = tomllib.load(handle)
        cls.report = REPORT_PATH.read_text(encoding="utf-8")

    def test_exact_read_only_delta_and_result(self) -> None:
        self.assertEqual(
            self.delta["schema"],
            "facman.c3_universal_consumer_profile_delta.v1",
        )
        self.assertEqual(self.delta["base_revision"], BASE)
        self.assertEqual(self.delta["head_revision"], HEAD)
        self.assertEqual(self.delta["commit_count"], 11)
        self.assertTrue(self.delta["read_only"])
        self.assertFalse(self.delta["consumer_repository_written"])
        self.assertFalse(self.delta["implementation_moved"])
        self.assertFalse(self.delta["full_audit_repeated"])
        self.assertEqual(
            self.delta["result"],
            "original_profile_remains_valid_with_exact_amendments",
        )

    def test_exact_bounded_gates(self) -> None:
        gates = {gate["id"]: gate for gate in self.delta["gate"]}
        self.assertEqual(
            set(gates),
            {
                "package_closure_and_lane_identity",
                "update_discovery_and_acquisition",
                "catalogue_and_user_data_preservation",
                "minimum_os_and_toolchain_claims",
                "application_activation_and_session",
                "maintenance_and_self_replacement",
            },
        )
        self.assertEqual(gates["update_discovery_and_acquisition"]["result"], "ownership_amended")
        self.assertEqual(gates["maintenance_and_self_replacement"]["result"], "unchanged_absent")

    def test_update_ownership_stops_at_local_package_boundary(self) -> None:
        ownership = {
            row["responsibility"]: row["owner"]
            for row in self.delta["update_responsibility"]
        }
        self.assertEqual(ownership["network discovery and acquisition"], "c3_or_c3_owned_connector")
        self.assertEqual(
            ownership["local package integrity and authenticity verification"],
            "universal_setup",
        )
        amendments = {row["row_id"]: row for row in self.delta["amendment"]}
        self.assertEqual(amendments["C3-20"]["current"], "split_adapt")

    def test_no_authority_is_opened(self) -> None:
        self.assertTrue(all(not value for value in self.delta["authority"].values()))
        self.assertIn(BASE, self.report)
        self.assertIn(HEAD, self.report)
        self.assertIn("ULK remains absent from C3", self.report)


if __name__ == "__main__":
    unittest.main()
