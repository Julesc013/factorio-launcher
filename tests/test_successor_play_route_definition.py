# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import successor_play_route_definition_check


class SuccessorPlayRouteDefinitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.definition = successor_play_route_definition_check.load_definition()

    def test_canonical_definition_is_closed_and_non_authorizing(self) -> None:
        self.assertEqual([], successor_play_route_definition_check.validate(self.definition))

    def test_provider_pin_drift_is_rejected(self) -> None:
        changed = copy.deepcopy(self.definition)
        changed["provider_pins"]["universal_launcher"] = "0" * 40
        problems = successor_play_route_definition_check.validate(changed)
        self.assertIn("successor route changed the stable universal_launcher pin", problems)

    def test_historical_operation_identity_reuse_is_rejected(self) -> None:
        changed = copy.deepcopy(self.definition)
        changed["evidence_identity"][7]["id"] = (
            "gate4c-instance-isolated-bae3edc4-8176-4677-b91d-32297a1aa5ab"
        )
        problems = successor_play_route_definition_check.validate(changed)
        self.assertTrue(any("revalidation-04 identity" in problem for problem in problems))

    def test_source_or_candidate_identity_cannot_be_filled_during_definition(self) -> None:
        changed = copy.deepcopy(self.definition)
        changed["future_bindings"]["source_revision"] = "1" * 40
        problems = successor_play_route_definition_check.validate(changed)
        self.assertIn(
            "definition-only route assigns source, package, or candidate evidence",
            problems,
        )

    def test_stage_or_execution_authority_is_rejected(self) -> None:
        changed = copy.deepcopy(self.definition)
        changed["authority"]["stage_created"] = True
        changed["authority"]["factorio_execution"] = True
        problems = successor_play_route_definition_check.validate(changed)
        self.assertTrue(any("opens authority" in problem for problem in problems))

    def test_automated_verdict_is_rejected(self) -> None:
        changed = copy.deepcopy(self.definition)
        changed["verdict_law"]["automated_inference_forbidden"] = False
        problems = successor_play_route_definition_check.validate(changed)
        self.assertIn(
            "successor verdict law requires automated_inference_forbidden",
            problems,
        )

    def test_verdict_never_promotes_a_route_directly(self) -> None:
        changed = copy.deepcopy(self.definition)
        changed["verdict_law"]["Pass"]["authority_granted"] = True
        problems = successor_play_route_definition_check.validate(changed)
        self.assertIn("successor Pass branch drifted or grants authority", problems)

    def test_digest_detects_unreviewed_contract_change(self) -> None:
        changed = copy.deepcopy(self.definition)
        changed["selector"]["factorio_version"] = "2.0.78"
        problems = successor_play_route_definition_check.validate(changed)
        self.assertIn(
            "successor route definition digest does not match canonical content",
            problems,
        )


if __name__ == "__main__":
    unittest.main()
