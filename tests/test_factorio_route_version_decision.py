# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import factorio_route_version_decision_check as decision_check


class FactorioRouteVersionDecisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.record = decision_check.load_record()

    def redigest(self, record: dict[str, object]) -> None:
        record["decision_digest"] = decision_check.decision_digest(record)

    def test_exact_non_activating_transition_is_valid(self) -> None:
        self.assertEqual([], decision_check.validate(self.record))

    def test_silent_version_substitution_is_rejected(self) -> None:
        changed = copy.deepcopy(self.record)
        changed["current_route_version"] = "2.1.14"
        self.redigest(changed)
        problems = decision_check.validate(changed)
        self.assertTrue(any("current_route_version" in item for item in problems))

    def test_executable_identity_change_is_rejected(self) -> None:
        changed = copy.deepcopy(self.record)
        changed["executable"]["sha256"] = "0" * 64
        self.redigest(changed)
        self.assertIn("2.1.14 executable identity drifted", decision_check.validate(changed))

    def test_release_activation_is_rejected(self) -> None:
        changed = copy.deepcopy(self.record)
        changed["authority"]["release_route_activation"] = True
        self.redigest(changed)
        self.assertTrue(any("opens product" in item for item in decision_check.validate(changed)))

    def test_evidence_transfer_from_2_0_77_is_rejected(self) -> None:
        changed = copy.deepcopy(self.record)
        changed["transition"]["evidence_transfer_from_2_0_77_allowed"] = True
        self.redigest(changed)
        self.assertIn(
            "2.1.14 transition and invalidation law drifted",
            decision_check.validate(changed),
        )

    def test_unknown_authority_surface_is_rejected(self) -> None:
        changed = copy.deepcopy(self.record)
        changed["authority"]["unknown"] = False
        self.redigest(changed)
        self.assertTrue(any("opens product" in item for item in decision_check.validate(changed)))


if __name__ == "__main__":
    unittest.main()
