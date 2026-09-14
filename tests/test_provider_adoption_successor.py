# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import provider_adoption_successor_check as successor


class ProviderAdoptionSuccessorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.record = successor._load_json(successor.RECORD)

    def test_canonical_successor_is_exact_and_non_authorizing(self) -> None:
        self.assertEqual([], successor.validate())
        self.assertFalse(any(self.record["authority"].values()))

    def test_current_projection_drift_is_rejected(self) -> None:
        changed = copy.deepcopy(self.record)
        changed["current_inputs"]["providers_lock"] = "0" * 64
        problems = successor.validate(record=changed)
        self.assertTrue(any("current input closure differs" in item for item in problems))

    def test_authority_reuse_is_rejected(self) -> None:
        changed = copy.deepcopy(self.record)
        changed["authority"]["route_promotion"] = True
        problems = successor.validate(record=changed)
        self.assertTrue(any("opens authority" in item for item in problems))

    def test_missing_historical_invalidation_is_rejected(self) -> None:
        changed = copy.deepcopy(self.record)
        changed["invalidated_evidence"] = changed["invalidated_evidence"][1:]
        problems = successor.validate(record=changed)
        self.assertTrue(any("invalidation set differs" in item for item in problems))


if __name__ == "__main__":
    unittest.main()
