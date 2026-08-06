# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import tomllib
import unittest
from pathlib import Path

import jsonschema

from tools import provider_pin_reconciliation


ROOT = Path(__file__).resolve().parents[1]


class ProviderPinReconciliationTests(unittest.TestCase):
    def test_atomic_provider_truth_and_route_v1_custody_pass(self) -> None:
        self.assertEqual(provider_pin_reconciliation.validate(), [])
        report = provider_pin_reconciliation.report()
        self.assertEqual(report["result"], "pass")
        self.assertTrue(report["provider_input_reconciled"])
        self.assertTrue(report["release_source_coherence_required"])
        self.assertFalse(any(report["authority"].values()))

    def test_sdk_matrix_is_exact_and_provider_package_digests_bind_it(self) -> None:
        with (ROOT / "release/index/providers.lock.v2.toml").open("rb") as handle:
            lock = tomllib.load(handle)
        keys = {
            (
                row["provider_id"],
                row["system"],
                row["architecture"],
                row["linkage"],
            )
            for row in lock["sdk_package"]
        }
        self.assertEqual(len(keys), 12)
        self.assertTrue(all(row["authorizing"] is False for row in lock["sdk_package"]))
        for provider in lock["provider"]:
            rows = [
                row
                for row in lock["sdk_package"]
                if row["provider_id"] == provider["id"]
            ]
            self.assertEqual(
                provider["package_digest"],
                provider_pin_reconciliation.domain_digest_value(
                    provider_pin_reconciliation.PACKAGE_SET_DOMAIN,
                    rows,
                ),
            )

    def test_adoption_decision_is_schema_valid_and_non_authorizing(self) -> None:
        evidence = json.loads(
            (
                ROOT
                / ".aide/queue/active/FACMAN-PROVIDER-PIN-RECONCILIATION-01"
                / "evidence/provider-adoption-decision.v1.json"
            ).read_text(encoding="utf-8")
        )
        schema = json.loads(
            (
                ROOT
                / "contracts/schema/release/provider_adoption_decision.v1.schema.json"
            ).read_text(encoding="utf-8")
        )
        jsonschema.Draft202012Validator(schema).validate(evidence)
        self.assertFalse(any(evidence["authority"].values()))
        self.assertTrue(evidence["route_v1"]["byte_identical"])
        self.assertFalse(evidence["route_v1"]["active"])

    def test_facman_required_ulk_abi_matches_reconciled_provider(self) -> None:
        compatibility = json.loads(
            (ROOT / "contracts/abi/flb/compatibility.v1.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            compatibility["required_ulk_abi"],
            {"major": 1, "minor": 8, "encoded": 0x00010008},
        )
        self.assertEqual(provider_pin_reconciliation.validate(), [])


if __name__ == "__main__":
    unittest.main()
