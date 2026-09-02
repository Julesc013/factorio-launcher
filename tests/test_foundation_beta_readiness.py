# SPDX-FileCopyrightText: 2026 Jules C
# SPDX-License-Identifier: MIT

from __future__ import annotations

import copy
import unittest

from tools import foundation_beta_readiness_check


class FoundationBetaReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.readiness = foundation_beta_readiness_check._load(
            foundation_beta_readiness_check.READINESS
        )
        self.version = foundation_beta_readiness_check._load(
            foundation_beta_readiness_check.VERSION
        )
        self.release_index = foundation_beta_readiness_check._load(
            foundation_beta_readiness_check.RELEASE_INDEX
        )
        self.artifact_matrix = foundation_beta_readiness_check._load(
            foundation_beta_readiness_check.ARTIFACT_MATRIX
        )
        self.candidate_receipt = foundation_beta_readiness_check._load(
            foundation_beta_readiness_check.CANDIDATE_RECEIPT
        )

    def validate(
        self, readiness: dict, candidate_receipt: dict | None = None
    ) -> list[str]:
        return foundation_beta_readiness_check.validate(
            readiness,
            self.version,
            self.release_index,
            self.artifact_matrix,
            candidate_receipt or self.candidate_receipt,
        )

    def test_canonical_readiness_is_valid_and_non_authorizing(self) -> None:
        self.assertEqual(self.validate(copy.deepcopy(self.readiness)), [])
        self.assertFalse(self.readiness["beta_ready"])
        self.assertTrue(all(value is False for value in self.readiness["authority"].values()))

    def test_rejects_missing_journey_and_false_beta_claim(self) -> None:
        changed = copy.deepcopy(self.readiness)
        changed["journey"].pop()
        changed["beta_ready"] = True
        problems = self.validate(changed)
        self.assertTrue(any("J01-J12" in problem for problem in problems), problems)
        self.assertTrue(any("beta_ready" in problem for problem in problems), problems)

    def test_future_toolkits_cannot_leak_into_beta(self) -> None:
        changed = copy.deepcopy(self.readiness)
        changed["frontend_lane"][3]["release_lane"] = "beta_preview"
        problems = self.validate(changed)
        self.assertTrue(any("qt6 frontend qualification" in problem for problem in problems), problems)

    def test_machine_qualification_cannot_be_worded_as_support_or_cleanup(self) -> None:
        changed = copy.deepcopy(self.readiness)
        changed["platform"][0]["beta_claim"] = "supported_prerelease"
        changed["frontend_lane"][0]["state"] = "implemented_unqualified"
        repository_gate = next(
            row
            for row in changed["gate"]
            if row["id"] == "repository_promotion_and_cleanup"
        )
        repository_gate["state"] = "promoted_synchronized_clean"
        problems = self.validate(changed)
        self.assertTrue(any("windows_x64 has an invalid beta claim" in item for item in problems), problems)
        self.assertTrue(any("winforms frontend qualification" in item for item in problems), problems)
        self.assertTrue(any("repository_promotion_and_cleanup" in item for item in problems), problems)

    def test_exact_six_asset_law_is_closed(self) -> None:
        changed = copy.deepcopy(self.readiness)
        changed["public_product_assets"].append("FacMan-extra.zip")
        problems = self.validate(changed)
        self.assertTrue(any("exactly six" in problem for problem in problems), problems)

    def test_gate_set_cannot_hide_work_or_claim_premature_completion(self) -> None:
        changed = copy.deepcopy(self.readiness)
        changed["gate"].pop()
        changed["gate"][0]["state"] = "complete"
        problems = self.validate(changed)
        self.assertTrue(any("canonical ordered gate set" in problem for problem in problems), problems)
        self.assertTrue(any("claim complete" in problem for problem in problems), problems)

    def test_semantic_states_and_artifact_matrix_are_cross_bound(self) -> None:
        changed = copy.deepcopy(self.readiness)
        changed["journey"][2]["implementation_state"] = "implemented_unqualified"
        changed["platform"][0]["current_state"] = "implemented_exact_candidate"
        changed["gate"][0]["state"] = "arbitrary_green_label"
        changed["public_product_assets"][0] = "FacMan-wrong.zip"
        problems = self.validate(changed)
        self.assertTrue(any("partial implementation" in problem for problem in problems), problems)
        self.assertTrue(any("invalid evidence state" in problem for problem in problems), problems)
        self.assertTrue(any("invalid gate state" in problem for problem in problems), problems)
        self.assertTrue(any("artifact matrix" in problem for problem in problems), problems)

    def test_exact_candidate_binding_cannot_drift_or_qualify_closeout(self) -> None:
        changed = copy.deepcopy(self.readiness)
        changed["exact_candidate"]["source_revision"] = "0" * 40
        changed["exact_candidate"]["closeout_revision_candidate_qualified"] = True
        problems = self.validate(changed)
        self.assertTrue(any("non-circular" in problem for problem in problems), problems)

    def test_machine_candidate_does_not_grant_beta_or_external_authority(self) -> None:
        changed = copy.deepcopy(self.readiness)
        changed["beta_ready"] = True
        changed["authority"]["publication"] = True
        problems = self.validate(changed)
        self.assertTrue(any("beta_ready" in problem for problem in problems), problems)
        self.assertTrue(any("external authority" in problem for problem in problems), problems)

    def test_candidate_receipt_source_run_and_boundary_are_cross_bound(self) -> None:
        changed = copy.deepcopy(self.candidate_receipt)
        changed["candidate"]["run_id"] = 1
        changed["non_circular"]["future_revision_requires_new_candidate_run"] = False
        problems = self.validate(copy.deepcopy(self.readiness), changed)
        self.assertTrue(any("source/run" in problem for problem in problems), problems)
        self.assertTrue(any("circular" in problem for problem in problems), problems)


if __name__ == "__main__":
    unittest.main()
