# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import universal_delivery_programme_check


class UniversalDeliveryProgrammeTests(unittest.TestCase):
    def setUp(self) -> None:
        (
            self.plan,
            self.trust,
            self.support,
            self.providers,
            self.doctrine,
        ) = universal_delivery_programme_check.load_inputs()

    def _validate(self) -> list[str]:
        return universal_delivery_programme_check.validate(
            self.plan,
            self.trust,
            self.support,
            self.providers,
            self.doctrine,
        )

    def test_preparation_is_complete_and_non_authorizing(self) -> None:
        self.assertEqual(self._validate(), [])

    def test_source_sdk_conformance_cannot_be_activated_implicitly(self) -> None:
        changed = copy.deepcopy(self.plan)
        workunit = next(
            item
            for item in changed["workunit"]
            if item["id"] == "THREE-REPO-SOURCE-VS-SDK-CONFORMANCE-01"
        )
        workunit["status"] = "ready"
        problems = universal_delivery_programme_check.validate(
            changed,
            self.trust,
            self.support,
            self.providers,
            self.doctrine,
        )
        self.assertTrue(any("status must remain 'planned'" in item for item in problems))

    def test_provider_sdk_consumption_cannot_be_inferred_from_planning(self) -> None:
        changed = copy.deepcopy(self.providers)
        changed["provider"][0]["consumption_mode"] = "installed_sdk"
        problems = universal_delivery_programme_check.validate(
            self.plan,
            self.trust,
            self.support,
            changed,
            self.doctrine,
        )
        self.assertTrue(any("SDK consumption has not been accepted" in item for item in problems))

    def test_planning_cannot_grant_release_authority(self) -> None:
        changed_trust = copy.deepcopy(self.trust)
        changed_support = copy.deepcopy(self.support)
        changed_trust["role"][1]["authorized"] = True
        changed_support["support"][0]["release_authorized"] = True
        problems = universal_delivery_programme_check.validate(
            self.plan,
            changed_trust,
            changed_support,
            self.providers,
            self.doctrine,
        )
        self.assertTrue(any("cannot authorize build_operator" in item for item in problems))
        self.assertTrue(any("cannot authorize support" in item for item in problems))

    def test_constitutional_anchor_removal_is_detected(self) -> None:
        changed = self.doctrine.replace("not a fourth repository", "another repository")
        problems = universal_delivery_programme_check.validate(
            self.plan,
            self.trust,
            self.support,
            self.providers,
            changed,
        )
        self.assertIn(
            "programme doctrine is missing anchor: not a fourth repository",
            problems,
        )


if __name__ == "__main__":
    unittest.main()
