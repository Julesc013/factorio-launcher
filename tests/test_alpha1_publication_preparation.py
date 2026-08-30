# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

from copy import deepcopy
import unittest

from tools import alpha1_publication_preparation_check


class Alpha1PublicationPreparationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.preparation = alpha1_publication_preparation_check.load()

    def validate(self, value: dict | None = None) -> list[str]:
        return alpha1_publication_preparation_check.validate(
            value if value is not None else deepcopy(self.preparation)
        )

    def test_exact_preparation_is_non_authorizing_and_truthful(self) -> None:
        self.assertEqual(self.validate(), [])
        self.assertTrue(self.preparation["g1_tag"]["status"] == "complete")
        self.assertEqual(self.preparation["g2_human_alpha"]["current_result"], "Inconclusive")
        self.assertFalse(any(self.preparation["authority"].values()))

    def test_digest_drift_is_rejected(self) -> None:
        changed = deepcopy(self.preparation)
        changed["g2_human_alpha"]["current_tester"] = "fabricated"
        problems = self.validate(changed)
        self.assertTrue(any("digest mismatch" in item for item in problems), problems)

    def test_human_receipt_cannot_be_skipped_or_self_authorize(self) -> None:
        changed = deepcopy(self.preparation)
        changed["g2_human_alpha"]["required_result"] = "Inconclusive"
        changed["g2_human_alpha"]["receipt_grants_publication"] = True
        changed["preparation_digest"] = alpha1_publication_preparation_check.preparation_digest(changed)
        problems = self.validate(changed)
        self.assertTrue(any("schema rejection" in item for item in problems), problems)
        self.assertTrue(any("must require a human Pass" in item for item in problems), problems)
        self.assertTrue(any("must not grant publication" in item for item in problems), problems)

    def test_route_request_cannot_be_relabelled_as_route_acceptance(self) -> None:
        changed = deepcopy(self.preparation)
        changed["g3_route"]["route_promotion_integrated"] = True
        changed["preparation_digest"] = alpha1_publication_preparation_check.preparation_digest(changed)
        problems = self.validate(changed)
        self.assertTrue(any("schema rejection" in item for item in problems), problems)
        self.assertTrue(any("route_promotion_integrated false" in item for item in problems), problems)

    def test_preparation_cannot_activate_publication_or_signing(self) -> None:
        changed = deepcopy(self.preparation)
        changed["authority"]["publication"] = True
        changed["signing_policy"]["production_signing_authorized"] = True
        changed["signing_preparation"]["production_private_key_access"] = True
        changed["signing_preparation"]["signing_identity"] = "CN=FacMan"
        changed["preparation_digest"] = alpha1_publication_preparation_check.preparation_digest(changed)
        problems = self.validate(changed)
        self.assertTrue(any("schema rejection" in item for item in problems), problems)
        self.assertTrue(any("grants authority" in item for item in problems), problems)
        self.assertTrue(any("production signing" in item for item in problems), problems)
        self.assertTrue(any("production_private_key_access false" in item for item in problems), problems)
        self.assertTrue(any("signing_identity unassigned" in item for item in problems), problems)

    def test_signing_rehearsal_cannot_use_release_package_bytes(self) -> None:
        changed = deepcopy(self.preparation)
        changed["signing_preparation"]["rehearsal_scope"] = "frozen_alpha1_packages"
        changed["signing_preparation"]["frozen_alpha1_signing_permitted"] = True
        changed["preparation_digest"] = alpha1_publication_preparation_check.preparation_digest(changed)
        problems = self.validate(changed)
        self.assertTrue(any("schema rejection" in item for item in problems), problems)
        self.assertTrue(any("exclude release package bytes" in item for item in problems), problems)
        self.assertTrue(any("frozen_alpha1_signing_permitted false" in item for item in problems), problems)


if __name__ == "__main__":
    unittest.main()
