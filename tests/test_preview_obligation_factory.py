# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

from tools import json_contract, preview_obligation_factory as factory


class PreviewObligationFactoryTests(unittest.TestCase):
    def test_registry_exactly_matches_release_compiler(self) -> None:
        self.assertEqual(factory.validate_registry(), [])
        self.assertEqual(len(factory.resolved_obligations()), 23)
        self.assertEqual(set(factory.resolved_obligations()), set(factory.SPECS))

    def test_canary_plan_fails_closed_for_package_custody(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            args = argparse.Namespace(
                build_root=None,
                package_root=None,
                artifact=None,
                resolution=None,
                configuration="Debug",
                provider_class="repaired_provider_canary",
                execute=False,
                evidence_dir=root / "evidence",
            )
            report = factory.run_factory(args)
        by_id = {item["id"]: item for item in report["obligations"]}
        self.assertEqual(len(by_id), 23)
        self.assertEqual(by_id["schema_validate"]["status"], "planned")
        self.assertEqual(by_id["package_runtime_smoke"]["status"], "blocked")
        self.assertEqual(
            by_id["package_runtime_smoke"]["classification"],
            "canonical_provider_identity_pending",
        )
        self.assertFalse(report["authority"]["release_authorized"])
        self.assertEqual(
            report["qualification_plan"]["schema"],
            "facman.resolved_qualification_plan.v1",
        )
        self.assertFalse(report["qualification_plan"]["qualified"])
        self.assertRegex(report["qualification_plan"]["resolution_digest"], r"^[0-9a-f]{64}$")
        schema = json_contract.load_schema(
            factory.SCHEMA
        )
        self.assertEqual(json_contract.validate(report, schema), [])

    def test_every_obligation_has_commands_and_invalidation_law(self) -> None:
        for obligation, spec in factory.SPECS.items():
            with self.subTest(obligation=obligation):
                self.assertTrue(spec.commands)
                self.assertTrue(spec.invalidation_paths)


if __name__ == "__main__":
    unittest.main()
